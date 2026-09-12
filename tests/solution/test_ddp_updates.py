from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP

from solution.rl.distributed import synchronized_update
from solution.rl.model import CandidatePolicy
from solution.rl.training import collate, checked_step


def rows_for(rank):
    rng=np.random.default_rng(902+rank)
    return [dict(state={'global':rng.normal(size=10).astype('float32'),
                       'channels':rng.normal(size=(20,9)).astype('float32'),
                       'candidates':rng.normal(size=(i%3+1,11)).astype('float32')},teacher=0)
            for i in range(1 if rank==0 else 5)]


def worker(rank,rendezvous):
    torch.set_num_threads(1);torch.manual_seed(888)
    dist.init_process_group('gloo',init_method='file://'+rendezvous,rank=rank,world_size=2)
    # Double precision isolates batching/weighting errors from float32 roundoff
    # in the softmax-invariant actor bias, which Adam can amplify through eps.
    model=CandidatePolicy().double();reference=deepcopy(model)
    ddp=DDP(model);opt=torch.optim.Adam(ddp.parameters(),lr=3e-4)
    reference_opt=torch.optim.Adam(reference.parameters(),lr=3e-4)
    # Rank 0 has one real batch and two empty batches, rank 1 has three.
    # Repeating the stage checks persistent Adam state, not just final weights.
    for _ in range(2):
        with patch('solution.rl.distributed.random.shuffle',lambda rows:None), patch('solution.rl.distributed.collate',double_collate):
            result=synchronized_update(ddp,opt,[(rows_for(rank),{})],torch.device('cpu'),'BC',1,2)
        assert result['optimizer_steps']==3 and result['parameter_and_optimizer_sync']
        for i in range(3):
            batch=rows_for(0)[i*2:(i+1)*2]+rows_for(1)[i*2:(i+1)*2]
            state,mask=double_collate(batch,'cpu');logits,value=reference(state,mask)
            loss=torch.nn.functional.cross_entropy(logits,torch.zeros(len(batch),dtype=torch.long))+0*value.sum()
            checked_step(loss,reference,reference_opt)
        for a,b in zip(model.parameters(),reference.parameters()):
            torch.testing.assert_close(a,b,atol=3e-6,rtol=3e-5)
        for a,b in zip(opt.state.values(),reference_opt.state.values()):
            for key in a:torch.testing.assert_close(a[key],b[key],atol=3e-6,rtol=3e-5)
    dist.destroy_process_group()


def double_collate(rows,device):
    state,mask=collate(rows,device)
    return {key:value.double() for key,value in state.items()},mask


def test_uneven_ddp_matches_global_batch_and_adam(tmp_path):
    mp.spawn(worker,args=(str(tmp_path/'rendezvous'),),nprocs=2,join=True)
