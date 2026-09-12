"""Batch utilities and fit checks for the structural v3 policy."""
import numpy as np
import torch
from solution.rl.structural_features import CANDIDATE_DIM, CHANNEL_DIM, STATION_DIM


def structural_collate(rows, device):
    if not rows: raise ValueError('empty structural batch')
    n=len(rows); max_a=max(len(r['state']['candidates']) for r in rows); max_s=max(len(r['state']['stations']) for r in rows)
    state={
        'global':torch.from_numpy(np.stack([r['state']['global'] for r in rows])).to(device),
        'channels':torch.from_numpy(np.stack([r['state']['channels'] for r in rows])).to(device),
        'stations':torch.zeros((n,max_s,STATION_DIM),device=device),
        'station_mask':torch.zeros((n,max_s),dtype=torch.bool,device=device),
        'candidates':torch.zeros((n,max_a,CANDIDATE_DIM),device=device),
        'candidate_channel_index':torch.zeros((n,max_a),dtype=torch.long,device=device),
        'candidate_channel_valid':torch.zeros((n,max_a),device=device),
        'candidate_station_index':torch.zeros((n,max_a),dtype=torch.long,device=device),
        'candidate_station_valid':torch.zeros((n,max_a),device=device),
        'candidate_channel_mask':torch.zeros((n,max_a,20),device=device),
    }
    action_mask=torch.zeros((n,max_a),dtype=torch.bool,device=device)
    for i,row in enumerate(rows):
        s=row['state']; ns=len(s['stations']); na=len(s['candidates'])
        state['stations'][i,:ns]=torch.from_numpy(s['stations'])
        state['station_mask'][i,:ns]=True
        state['candidates'][i,:na]=torch.from_numpy(s['candidates'])
        for key in ('candidate_channel_index','candidate_channel_valid','candidate_station_index','candidate_station_valid','candidate_channel_mask'):
            state[key][i,:na]=torch.from_numpy(s[key])
        action_mask[i,:na]=True
    return state,action_mask


def fit_check(model, rows, device='cpu', epochs=32, target_accuracy=0.98):
    """Small-set SFT check; it never selects a final checkpoint."""
    from torch.optim import Adam
    model.to(device); opt=Adam(model.parameters(),lr=3e-4)
    history=[]
    for epoch in range(epochs):
        state,mask=structural_collate(rows,device); logits,_=model(state,mask)
        target=torch.tensor([r['teacher'] for r in rows],device=device)
        loss=torch.nn.functional.cross_entropy(logits,target)
        opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),.5);opt.step()
        acc=float((logits.argmax(-1)==target).float().mean());history.append({'epoch':epoch+1,'loss':float(loss),'accuracy':acc})
    return {'rows':len(rows),'final_loss':history[-1]['loss'],'final_accuracy':history[-1]['accuracy'],
            'passed':history[-1]['accuracy']>=target_accuracy,'history':history}
