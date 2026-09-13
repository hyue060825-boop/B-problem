"""Equal-step DDP updates with zero-weight padding and exact state audits."""
import hashlib
import math
import random

import numpy as np
import torch
import torch.distributed as dist

from solution.rl.model import masked_distribution
from solution.rl.training import advantages, collate, checked_step


def state_digest(model, optimizer):
    h=hashlib.sha256()
    def visit(value):
        if isinstance(value, torch.Tensor):
            t=value.detach().cpu().contiguous()
            h.update(str((t.dtype,tuple(t.shape))).encode())
            h.update(t.numpy().tobytes())
        elif isinstance(value,dict):
            for k in sorted(value,key=str):
                h.update(str(k).encode());visit(value[k])
        elif isinstance(value,(list,tuple)):
            for item in value:visit(item)
        else:h.update(repr(value).encode())
    visit(model.state_dict());visit(optimizer.state_dict())
    return h.hexdigest()


def audit_sync(model,optimizer):
    digest=state_digest(model,optimizer)
    digests=[None]*dist.get_world_size()
    dist.all_gather_object(digests,digest)
    if len(set(digests))!=1:
        raise RuntimeError(f'model/Adam state divergence: {digests}')
    return digest


def synchronized_update(model,optimizer,episodes,device,kind,epochs,batch_size,entropy=.01):
    if kind=='PPO':
        rows=advantages(episodes,normalize=False)
        a=np.array([r['advantage'] for r in rows],dtype=np.float64)
        moments=torch.tensor([len(a),a.sum(),(a*a).sum()],device=device,dtype=torch.float64)
        dist.all_reduce(moments)
        n,s,ss=moments.tolist();mean=s/n;std=math.sqrt(max(0,ss/n-mean*mean))+1e-8
        for r in rows:r['advantage']=(r['advantage']-mean)/std
    else:rows=[r for ep,_ in episodes for r in ep]
    if not rows:raise ValueError('rank has no transitions')
    batches=torch.tensor(math.ceil(len(rows)/batch_size),device=device,dtype=torch.long)
    dist.all_reduce(batches,op=dist.ReduceOp.MAX)
    steps=int(batches.item());world=dist.get_world_size();stats=[]
    model.train()
    for _ in range(epochs):
        random.shuffle(rows)
        for step in range(steps):
            batch=rows[step*batch_size:(step+1)*batch_size];local_n=len(batch)
            n=torch.tensor(local_n,device=device,dtype=torch.float64);dist.all_reduce(n)
            # Empty ranks still perform forward/backward/Adam.step. The dummy
            # transition contributes zero loss and never changes the objective.
            state,mask=collate(batch or rows[:1],device)
            logits,value=model(state,mask)
            weight=torch.ones(len(batch) or 1,device=device) if batch else torch.zeros(1,device=device)
            used=batch or rows[:1]
            if kind=='PPO':
                tensor=lambda key:torch.tensor([r[key] for r in used],device=device,dtype=torch.float32)
                action=torch.tensor([r['action'] for r in used],device=device)
                distribution=masked_distribution(logits,mask)
                logp=distribution.log_prob(action);ratio=(logp-tensor('old_logp')).exp()
                adv=tensor('advantage')
                policy=-torch.minimum(ratio*adv,ratio.clamp(.8,1.2)*adv)
                value_loss=(value-tensor('return')).square()
                per_row=policy+.001*value_loss-entropy*distribution.entropy()
            else:
                target=torch.tensor([r['teacher'] for r in used],device=device)
                # Keep critic in the graph with zero contribution during BC.
                per_row=torch.nn.functional.cross_entropy(logits,target,reduction='none')+0*value
            # DDP averages gradients by world size. This scaling recovers the
            # exact global per-transition mean even for unequal last batches.
            loss=(per_row*weight).sum()*(world/n.item())
            grad_norm=checked_step(loss,model,optimizer)
            stats.append((float(loss.detach()),grad_norm))
    summary=torch.tensor(np.mean(stats,axis=0),device=device);dist.all_reduce(summary);summary/=world
    digest=audit_sync(model.module,optimizer)
    return dict(loss=float(summary[0]),gradient_norm=float(summary[1]),
                optimizer_steps=steps*epochs,local_transitions=len(rows),state_sha256=digest,
                parameter_and_optimizer_sync=True)
