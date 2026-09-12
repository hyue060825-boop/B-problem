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
    """Candidate policy with explicit channel/station gathers and scan masks."""
    MODEL_VERSION = 'candidate-cross-attn-v1'
    def __init__(self, global_dim=10, channel_dim=16, station_dim=8, candidate_dim=14, hidden=128, heads=4):
        super().__init__()
        self.global_encoder=nn.Sequential(nn.Linear(global_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.channel_encoder=nn.Sequential(nn.Linear(channel_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.station_encoder=nn.Sequential(nn.Linear(station_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.action_encoder=nn.Sequential(nn.Linear(candidate_dim,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.mask_encoder=nn.Sequential(nn.Linear(20,hidden),nn.LayerNorm(hidden),nn.Tanh())
        self.channels=nn.TransformerEncoder(nn.TransformerEncoderLayer(hidden,heads,batch_first=True,norm_first=True,dim_feedforward=256,dropout=0.),2,enable_nested_tensor=False)
        self.actor=nn.Sequential(nn.Linear(hidden*5,hidden),nn.Tanh(),nn.Linear(hidden,1))
        self.critic=nn.Sequential(nn.Linear(hidden*3,hidden),nn.Tanh(),nn.Linear(hidden,1))
    def forward(self,state,action_mask=None):
        g=self.global_encoder(state['global']); ct=self.channels(self.channel_encoder(state['channels']))
        st=self.station_encoder(state['stations']); a=self.action_encoder(state['candidates'])
        ci=state['candidate_channel_index'].long().clamp(0,ct.shape[1]-1); si=state['candidate_station_index'].long().clamp(0,st.shape[1]-1)
        gather_c=torch.gather(ct,1,ci.unsqueeze(-1).expand(-1,-1,ct.shape[-1]))
        gather_s=torch.gather(st,1,si.unsqueeze(-1).expand(-1,-1,st.shape[-1]))
        mask=self.mask_encoder(state['candidate_channel_mask'])
        x=torch.cat([a,g[:,None,:].expand_as(a),gather_c,gather_s,mask],-1)
        logits=self.actor(x).squeeze(-1)
        if action_mask is not None: logits=logits.masked_fill(~action_mask.bool(),torch.finfo(logits.dtype).min)
        value=self.critic(torch.cat([g,ct.mean(1),st.mean(1)],-1)).squeeze(-1)
        return logits,value


def masked_distribution(logits, mask):
    if not mask.bool().any(dim=-1).all():
        raise ValueError('all actions masked')
    return torch.distributions.Categorical(logits=logits.masked_fill(~mask.bool(), torch.finfo(logits.dtype).min))
