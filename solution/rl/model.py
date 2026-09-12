"""Small candidate-set policy. Weights are initialized only; no trained model."""
import torch
from torch import nn


MODEL_VERSION='candidate-cross-attn-v1'

class CandidatePolicy(nn.Module):
    def __init__(self, global_dim=10, channel_dim=9, candidate_dim=14, hidden=128, heads=4):
        super().__init__()
        self.global_encoder = nn.Sequential(nn.Linear(global_dim, hidden), nn.LayerNorm(hidden), nn.Tanh())
        self.channel_encoder = nn.Sequential(nn.Linear(channel_dim, hidden), nn.LayerNorm(hidden), nn.Tanh())
        layer = nn.TransformerEncoderLayer(hidden, heads, batch_first=True, norm_first=True, dim_feedforward=256, dropout=0.0)
        self.channels = nn.TransformerEncoder(layer, 2, enable_nested_tensor=False)
        self.action_encoder = nn.Sequential(nn.Linear(candidate_dim, hidden), nn.LayerNorm(hidden), nn.Tanh())
        self.actor = nn.Sequential(nn.Linear(hidden * 3, hidden), nn.Tanh(), nn.Linear(hidden, 1))
        self.critic = nn.Sequential(nn.Linear(hidden * 2, hidden), nn.Tanh(), nn.Linear(hidden, 1))

    def forward(self, state, action_mask=None):
        g = self.global_encoder(state["global"])
        c = self.channels(self.channel_encoder(state["channels"])).mean(dim=1)
        candidates = state["candidates"]
        # Keep the public v2 schema usable by inspection tools and old unit
        # fixtures. Training/evaluation checkpoints still require v3 metadata.
        if candidates.shape[-1] < self.action_encoder[0].in_features:
            pad = candidates.new_zeros(*candidates.shape[:-1], self.action_encoder[0].in_features - candidates.shape[-1])
            candidates = torch.cat([candidates, pad], dim=-1)
        elif candidates.shape[-1] > self.action_encoder[0].in_features:
            raise ValueError('candidate feature dimension exceeds model schema')
        a = self.action_encoder(candidates)
        logits = self.actor(torch.cat([a, g[:, None, :].expand_as(a), c[:, None, :].expand_as(a)], dim=-1)).squeeze(-1)
        if action_mask is not None:
            logits = logits.masked_fill(~action_mask.bool(), torch.finfo(logits.dtype).min)
        value = self.critic(torch.cat([g, c], dim=-1)).squeeze(-1)
        return logits, value


class StructuralCandidatePolicy(nn.Module):
    """Candidate-query cross-attention policy for the structural v3 schema.

    Candidate embeddings are queries.  A candidate only attends to the
    channels in its public scan mask and, when it is station-bound, to the
    station token it names.  This is deliberately a new model family: old
    gather/concat checkpoints must not be silently loaded into it.
    """
    MODEL_VERSION = 'candidate-cross-attn-v2'
    def __init__(self, global_dim=10, channel_dim=28, station_dim=8, candidate_dim=20, hidden=128, heads=4):
        super().__init__()
        self.global_encoder=nn.Sequential(nn.Linear(global_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.channel_encoder=nn.Sequential(nn.Linear(channel_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.station_encoder=nn.Sequential(nn.Linear(station_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.action_encoder=nn.Sequential(nn.Linear(candidate_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.mask_encoder=nn.Sequential(nn.Linear(20,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.channels=nn.TransformerEncoder(nn.TransformerEncoderLayer(hidden,heads,batch_first=True,norm_first=True,dim_feedforward=256,dropout=0.),2,enable_nested_tensor=False)
        self.channel_attention=nn.MultiheadAttention(hidden,heads,batch_first=True)
        self.station_attention=nn.MultiheadAttention(hidden,heads,batch_first=True)
        self.null_channel=nn.Parameter(torch.zeros(1,1,hidden))
        self.null_station=nn.Parameter(torch.zeros(1,1,hidden))
        self.actor=nn.Sequential(nn.Linear(hidden*5,hidden),nn.Tanh(),nn.Linear(hidden,1))
        self.critic=nn.Sequential(nn.Linear(hidden*3,hidden),nn.Tanh(),nn.Linear(hidden,1))
    def forward(self,state,action_mask=None):
        g=self.global_encoder(state['global']); ct=self.channels(self.channel_encoder(state['channels']))
        st=self.station_encoder(state['stations']); a=self.action_encoder(state['candidates'])
        b,nq=a.shape[:2]; nc=ct.shape[1]; ns=st.shape[1]
        # One query per candidate.  MultiheadAttention's key padding mask is
        # true for disallowed keys; every query receives a learned null token
        # when its relation mask is empty, so EXIT cannot produce NaNs.
        q=a.reshape(b*nq,1,-1)
        channel_keys=ct[:,None,:,:].expand(b,nq,nc,-1).reshape(b*nq,nc,-1)
        cm=state['candidate_channel_mask'].bool().reshape(b*nq,nc)
        has_c=cm.any(-1)
        ck=torch.cat([channel_keys,self.null_channel.expand(b*nq,-1,-1)],1)
        cm_full=torch.cat([~cm,torch.zeros((b*nq,1),dtype=torch.bool,device=cm.device)],1)
        # For non-empty masks the null key is masked; for empty masks all
        # channels are masked and the null key is the sole valid key.
        cm_full[has_c,-1]=True
        cm_full[~has_c,:nc]=True
        channel_ctx,_=self.channel_attention(q,ck,ck,key_padding_mask=cm_full)
        station_keys=st[:,None,:,:].expand(b,nq,ns,-1).reshape(b*nq,ns,-1)
        station_index=state['candidate_station_index'].long().clamp(0,max(0,ns-1))
        station_valid=state.get('candidate_station_valid',torch.zeros((b,nq),device=a.device)).bool()
        station_padding=~state.get('station_mask',torch.ones((b,ns),dtype=torch.bool,device=a.device)).bool()
        selected=torch.zeros((b,nq,ns),dtype=torch.bool,device=a.device)
        selected.scatter_(2,station_index.unsqueeze(-1),station_valid.unsqueeze(-1))
        selected=selected.reshape(b*nq,ns)
        sk=torch.cat([station_keys,self.null_station.expand(b*nq,-1,-1)],1)
        sm_full=torch.ones((b*nq,ns+1),dtype=torch.bool,device=a.device)
        sm_full[:,:ns]=station_padding[:,None,:].expand(b,nq,ns).reshape(b*nq,ns) | ~selected
        sm_full[:,-1]=station_valid.reshape(-1)
        # Unbound candidates attend only the null station token.
        sm_full[~station_valid.reshape(-1),:ns]=True
        sm_full[~station_valid.reshape(-1),-1]=False
        station_ctx,_=self.station_attention(q,sk,sk,key_padding_mask=sm_full)
        mask=self.mask_encoder(state['candidate_channel_mask'])
        x=torch.cat([a,g[:,None,:].expand_as(a),channel_ctx.reshape(b,nq,-1),station_ctx.reshape(b,nq,-1),mask],-1)
        logits=self.actor(x).squeeze(-1)
        if action_mask is not None: logits=logits.masked_fill(~action_mask.bool(),torch.finfo(logits.dtype).min)
        station_mask=state.get('station_mask',torch.ones(st.shape[:2],dtype=torch.bool,device=st.device)).to(st.dtype)
        station_pool=(st*station_mask.unsqueeze(-1)).sum(1)/station_mask.sum(1,keepdim=True).clamp_min(1)
        value=self.critic(torch.cat([g,ct.mean(1),station_pool],-1)).squeeze(-1)
        return logits,value


def masked_distribution(logits, mask):
    if not mask.bool().any(dim=-1).all():
        raise ValueError('all actions masked')
    return torch.distributions.Categorical(logits=logits.masked_fill(~mask.bool(), torch.finfo(logits.dtype).min))
