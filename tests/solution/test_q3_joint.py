from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP

from solution.rl.model import CandidatePolicy
from solution.rl.training import collate
from solution.rl.distributed import audit_sync
from solution.rl.joint_updates import joint_update,prepare_ppo


def data_rows(rank):
    rng=np.random.default_rng(900+rank);rows=[]
    for i in range(1 if rank==0 else 7):
        n=2+i%3;target=rng.uniform(.1,1,n);target/=target.sum()
        rows.append(dict(state={'global':rng.normal(size=10).astype('float32'),
                                'channels':rng.normal(size=(20,9)).astype('float32'),
                                'candidates':rng.normal(size=(n,11)).astype('float32')},
                         target=target,anchor=np.full(n,1/n),weight=float(i+1)/3))
    return rows


def worker(rank,root):
    torch.set_num_threads(1);torch.manual_seed(2026)
    dist.init_process_group('gloo',init_method='file://'+root+'/init',rank=rank,world_size=2)
    model=CandidatePolicy().double();ref=deepcopy(model);initial=deepcopy(model.state_dict())
    ddp=DDP(model);opt=torch.optim.Adam(model.parameters(),lr=1e-4)
    refopt=torch.optim.Adam(ref.parameters(),lr=1e-4)
    for turn in range(2):
        before_turn=deepcopy(model.state_dict())
        # Second turn includes a genuinely empty rank, with accumulation/padding.
        all_rows=[data_rows(0) if turn==0 else [],data_rows(1)]
        result=joint_update(ddp,opt,all_rows[rank],torch.device('cpu'),epochs=2,batch_size=2,accum=2,shuffle=False)
        assert result['parameter_and_optimizer_sync'] and result['optimizer_steps']==4
        for epoch in range(2):
            for step in range(2):
                batch=all_rows[0][step*4:(step+1)*4]+all_rows[1][step*4:(step+1)*4]
                state,mask=collate(batch,'cpu');state={k:v.double() for k,v in state.items()}
                logits,value=ref(state,mask);logp=logits.log_softmax(-1)
                target=torch.zeros_like(logits);anchor=torch.zeros_like(logits)
                for j,row in enumerate(batch):
                    target[j,:len(row['target'])]=torch.tensor(row['target'])
                    anchor[j,:len(row['anchor'])]=torch.tensor(row['anchor'])
                weight=torch.tensor([r['weight'] for r in batch],dtype=torch.float64)
                per=-(target*logp).sum(-1)+.1*(anchor*(anchor.clamp_min(1e-30).log()-logp)).sum(-1)+0*value
                loss=(per*weight).sum()/weight.sum()
                refopt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(ref.parameters(),.5);refopt.step()
        for a,b in zip(model.parameters(),ref.parameters()):torch.testing.assert_close(a,b,rtol=1e-6,atol=1e-7)
        for a,b in zip(opt.state.values(),refopt.state.values()):
            for key in a:torch.testing.assert_close(a[key],b[key],rtol=1e-6,atol=1e-8)
        if turn==1:
            # Rank 0 receives no data this turn; rank 1's gradients must still
            # update rank 0, and match the centralized nonempty batch exactly.
            assert any(not torch.equal(before_turn[k],v) for k,v in model.state_dict().items())
    assert any(not torch.equal(initial[k],v) for k,v in model.state_dict().items())
    # Save one rank's file and restore all model and Adam replicas from it.
    if rank==0:torch.save({'model':model.state_dict(),'opt':opt.state_dict()},root+'/joint.pt')
    dist.barrier();saved=torch.load(root+'/joint.pt',weights_only=False)
    model.load_state_dict(saved['model']);opt.load_state_dict(saved['opt']);audit_sync(model,opt)
    assert joint_update(ddp,opt,[],torch.device('cpu'))['reason']=='global_empty'
    # Mixed long/short, successful/failed terminals, variable candidates; rank 0 empty.
    episodes=[]
    if rank==1:
        for n,reward in [(1,-1000.),(5,-2.)]:
            ep=[]
            for i in range(n):
                row=deepcopy(data_rows(1)[i]);state,mask=collate([row],'cpu')
                with torch.no_grad():logits,val=model({k:v.double() for k,v in state.items()},mask)
                row.update(action=0,old_logp=float(logits.log_softmax(-1)[0,0]),value=float(val[0]),reward=reward,done=i==n-1)
                ep.append(row)
            episodes.append((ep,{}))
    ppo,stats=prepare_ppo(episodes,torch.device('cpu'));assert stats['count']==6
    sums=torch.tensor([sum(r['advantage'] for r in ppo),sum(r['advantage']**2 for r in ppo)],dtype=torch.float64)
    dist.all_reduce(sums);assert abs(sums[0])<1e-8 and abs(sums[1]-6)<1e-6
    result=joint_update(ddp,opt,ppo,torch.device('cpu'),kind='PPO',batch_size=2,accum=2,epochs=2,target_kl=.03)
    assert result['parameter_and_optimizer_sync'] and result['optimizer_steps']>0
    for r in ppo:r['old_logp']-=20
    before=deepcopy(model.state_dict())
    stopped=joint_update(ddp,opt,ppo,torch.device('cpu'),kind='PPO',batch_size=2,accum=2,target_kl=.001)
    assert stopped['global_kl_stop'] and stopped['optimizer_steps']==0
    assert all(torch.equal(before[k],v) for k,v in model.state_dict().items())
    bad=data_rows(rank)
    if rank==1:bad[0]['state']['global'][0]=float('nan')
    with pytest.raises(FloatingPointError,match='all ranks stop'):
        joint_update(ddp,opt,bad,torch.device('cpu'),batch_size=16)
    dist.destroy_process_group()


def test_weighted_joint_equivalence_accumulation_recovery_and_ppo(tmp_path):
    mp.spawn(worker,args=(str(tmp_path),),nprocs=2,join=True)
