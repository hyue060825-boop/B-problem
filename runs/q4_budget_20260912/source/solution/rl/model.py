"""Small candidate-set policy. Weights are initialized only; no trained model."""
import torch
from torch import nn


class CandidatePolicy(nn.Module):
    def __init__(self, global_dim=10, channel_dim=9, candidate_dim=11, hidden=128, heads=4):
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
        a = self.action_encoder(state["candidates"])
        logits = self.actor(torch.cat([a, g[:, None, :].expand_as(a), c[:, None, :].expand_as(a)], dim=-1)).squeeze(-1)
        if action_mask is not None:
            logits = logits.masked_fill(~action_mask.bool(), torch.finfo(logits.dtype).min)
        value = self.critic(torch.cat([g, c], dim=-1)).squeeze(-1)
        return logits, value


def masked_distribution(logits, mask):
    if not mask.bool().any(dim=-1).all():
        raise ValueError('all actions masked')
    return torch.distributions.Categorical(logits=logits.masked_fill(~mask.bool(), torch.finfo(logits.dtype).min))
