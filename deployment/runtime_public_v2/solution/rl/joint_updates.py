"""Weighted global-batch SFT/PPO with accumulation, empty shards and KL stop."""
from contextlib import nullcontext
import math
import random
import time

import numpy as np
import torch
import torch.distributed as dist

from solution.rl.distributed import audit_sync
from solution.rl.training import advantages, collate
from solution.rl.model import masked_distribution


def prepare_ppo(episodes,device):
    rows=advantages(episodes,normalize=False)
    a=np.asarray([r['advantage'] for r in rows],np.float64)
    stats=torch.tensor([len(a),a.sum(),(a*a).sum()],device=device,dtype=torch.float64)
    dist.all_reduce(stats);n,s,ss=stats.tolist()
    if n:
        mean=s/n;std=math.sqrt(max(0.,ss/n-mean*mean))+1e-8
        for r in rows:r['advantage']=(r['advantage']-mean)/std
    return rows,dict(count=int(n),mean=s/n if n else None,std=std if n else None)


def joint_update(model,optimizer,rows,device,kind='SFT',epochs=1,batch_size=64,accum=1,
                 stability_kl=.1,entropy=.005,target_kl=.03,shuffle=True,audit_every=1):
    if kind not in ('SFT','PPO') or batch_size<1 or accum<1:raise ValueError('update config')
    world=dist.get_world_size();rank=dist.get_rank();started=time.perf_counter();comm_s=0.
    def reduce(tensor,op=dist.ReduceOp.SUM):
        nonlocal comm_s
        t=time.perf_counter();dist.all_reduce(tensor,op=op);comm_s+=time.perf_counter()-t;return tensor
    prototypes=[None]*world
    dist.all_gather_object(prototypes,rows[0] if rows else None)
    dummy=next((r for r in prototypes if r is not None),None)
    if dummy is None:return dict(skipped=True,optimizer_steps=0,reason='global_empty',sync=audit_sync(model.module,optimizer))
    steps=int(reduce(torch.tensor(math.ceil(len(rows)/(batch_size*accum)),device=device),dist.ReduceOp.MAX).item())
    local_counts=[None]*world;dist.all_gather_object(local_counts,len(rows))
    history=[];stop=False;fb_s=0.;opt_s=0.;padding=0;step_count=0
    model.train()
    for epoch in range(epochs):
        if shuffle:random.shuffle(rows)
        for step in range(steps):
            block=rows[step*batch_size*accum:(step+1)*batch_size*accum]
            z=reduce(torch.tensor(sum(float(r.get('weight',1.)) for r in block),device=device,dtype=torch.float64)).item()
            if z<=0:continue
            optimizer.zero_grad(set_to_none=True);loss_sum=0.;kl_sum=0.
            for micro in range(accum):
                batch=block[micro*batch_size:(micro+1)*batch_size];used=batch or [dummy]
                padding+=int(not batch)
                state,mask=collate(used,device)
                dtype=next(model.parameters()).dtype
                state={k:v.to(dtype=dtype) for k,v in state.items()}
                w=torch.tensor([float(r.get('weight',1.)) for r in batch] if batch else [0.],device=device,dtype=dtype)
                t=time.perf_counter()
                context=model.no_sync() if micro<accum-1 else nullcontext()
                with context:
                    logits,value=model(state,mask)
                    if kind=='SFT':
                        target=torch.zeros_like(logits);anchor=torch.zeros_like(logits)
                        for j,row in enumerate(used):
                            target[j,:len(row['target'])]=torch.as_tensor(row['target'],device=device,dtype=dtype)
                            anchor[j,:len(row['anchor'])]=torch.as_tensor(row['anchor'],device=device,dtype=dtype)
                        logp=torch.log_softmax(logits,dim=-1)
                        # Mask products before summing: finfo.min is finite, no 0*(-inf).
                        ce=-(target*logp).sum(-1)
                        kl=(anchor*(anchor.clamp_min(1e-30).log()-logp)).sum(-1)
                        per_row=ce+stability_kl*kl+0*value
                    else:
                        tensor=lambda k:torch.tensor([r[k] for r in used],device=device,dtype=dtype)
                        distn=masked_distribution(logits,mask)
                        action=torch.tensor([r['action'] for r in used],device=device,dtype=torch.long)
                        logratio=distn.log_prob(action)-tensor('old_logp');ratio=logratio.exp()
                        kl=(ratio-1)-logratio
                        adv=tensor('advantage')
                        per_row=-torch.minimum(ratio*adv,ratio.clamp(.8,1.2)*adv)+.001*(value-tensor('return')).square()-entropy*distn.entropy()
                    loss=(per_row*w).sum()*(world/z)
                    finite=reduce(torch.tensor(int(torch.isfinite(loss)),device=device),dist.ReduceOp.MIN)
                    if not finite.item():
                        optimizer.zero_grad(set_to_none=True);raise FloatingPointError('joint nonfinite loss: all ranks stop')
                    loss.backward()
                fb_s+=time.perf_counter()-t
                loss_sum+=float((per_row.detach()*w).sum());kl_sum+=float((kl.detach()*w).sum())
            global_kl=reduce(torch.tensor(kl_sum,device=device,dtype=torch.float64)).item()/z
            if kind=='PPO' and global_kl>target_kl:
                optimizer.zero_grad(set_to_none=True);stop=True;break
            t=time.perf_counter()
            norm=torch.nn.utils.clip_grad_norm_(model.parameters(),.5,error_if_nonfinite=True)
            optimizer.step();opt_s+=time.perf_counter()-t;step_count+=1
            finite=reduce(torch.tensor(int(all(torch.isfinite(p).all() for p in model.parameters())),device=device),dist.ReduceOp.MIN)
            if not finite.item():raise FloatingPointError('joint nonfinite parameters')
            total_loss=reduce(torch.tensor(loss_sum,device=device,dtype=torch.float64)).item()/z
            digest=audit_sync(model.module,optimizer) if step_count%audit_every==0 else None
            history.append(dict(step=step_count,epoch=epoch,loss=total_loss,kl=global_kl,
                                gradient_norm=float(norm),global_weight=z,state_sha256=digest))
        if stop:break
    digest=audit_sync(model.module,optimizer)
    times=[None]*world
    dist.all_gather_object(times,dict(rank=rank,valid_samples=len(rows),zero_weight_microbatches=padding,
                                    forward_backward_including_ddp_s=fb_s,explicit_collective_s=comm_s,optimizer_s=opt_s))
    return dict(optimizer_steps=step_count,global_samples=sum(local_counts),per_rank_samples=local_counts,
                global_batch_size=world*batch_size*accum,per_rank_batch_size=batch_size,grad_accum_steps=accum,
                global_kl_stop=stop,last_global_kl=global_kl if 'global_kl' in locals() else None,
                updates=history,parameter_and_optimizer_sync=True,state_sha256=digest,
                rank_timings=times,elapsed_s=time.perf_counter()-started)
