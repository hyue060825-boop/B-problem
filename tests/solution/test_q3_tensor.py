from copy import deepcopy
import math
import numpy as np
import pytest
import torch
from bsim.reference import State
from bsim.research import make_research_session
from solution.search.gpu.kernel import Q3TensorKernel,BatchedHistoryConsistency


@pytest.mark.skipif(not torch.cuda.is_available(),reason='real CUDA required')
def test_tensor_reference_random_boundaries_and_inactive():
    kernels=[make_research_session(3,100000+i)[0].kernel for i in range(64)]
    engine=Q3TensorKernel(kernels,'cuda:0');states=[State() for _ in kernels];rng=np.random.default_rng(62)
    for step in range(30):
        ids=list(rng.permutation(len(kernels)));requests=[]
        for i in ids:
            s=kernels[i].scenario.sources[step%len(kernels[i].sources)]
            if step<20:
                radius=[0.,5.,20.,s.radius][step%4];radius=np.nextafter(radius,[-math.inf,math.inf][step%2]) if step%3 else radius
                p=(s.x+radius,s.y);ch=s.channel
            else:p=tuple(rng.uniform(-2000,2000,2));ch=int(rng.integers(1,21))
            requests.append(('/measure' if step%3 else '/clear',p,ch))
        answers=engine.step(ids,requests)
        for i,request,answer in zip(ids,requests,answers):
            states[i],result=kernels[i].transition(states[i],*request)
            assert all(answer.get(k)==v for k,v in result.items()), str((step,int(i),request,answer,result))
            assert round(answer['virtual_time_s']*1e6)==states[i].virtual_us
            assert engine.host_states[i]==states[i]
    assert engine.stats['reference_fallbacks']>0
    engine.active[0]=False;state=engine.host_states[0]
    assert engine.step([0],[('/measure',(0.,0.),1)])==[None] and engine.host_states[0]==state


@pytest.mark.skipif(not torch.cuda.is_available(),reason='real CUDA required')
def test_batch_history_accept_reject_and_fixed_response():
    kernels=[make_research_session(3,1100+i)[0].kernel for i in range(4)]
    histories=[]
    for k in kernels:
        state=State();rows=[]
        s=k.scenario.sources[0]
        for path,p in [('/measure',(s.x+6,s.y)),('/measure',(s.x+6,s.y)),('/clear',(s.x,s.y)),('/measure',(s.x,s.y))]:
            state,r=k.transition(state,path,p,s.channel)
            rows.append(dict(path=path,position=p,channel=s.channel,response=dict(virtual_time_s=state.virtual_us/1e6,**r)))
        histories.append(rows)
    checker=BatchedHistoryConsistency('cuda:0');valid,_=checker.validate(kernels,histories);assert all(valid)
    histories[1][0]['response']['svd_deg']+=.01
    valid,_=checker.validate(kernels,histories);assert valid==[True,False,True,True]
