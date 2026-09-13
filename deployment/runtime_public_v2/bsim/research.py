"""用户2026-09-11授权的相容研究生成器；复用ReferenceKernel，不声称官方同分布。"""
import math
import numpy as np
from bsim.scenarios import Source,Scenario
from bsim.noise import Numerics
from bsim.reference import ReferenceKernel
from bsim.session import Session
from bsim.clocks import ManualClock

PROFILE_VERSION='research-v1-20260911'

class FixedField:
    def __init__(self,seed,kind='smooth'):
        rng=np.random.default_rng(seed)
        self.phases=rng.uniform(-math.pi,math.pi,20)
        self.kind=kind; self.k=rng.uniform(.0005,.02,2)
    def error(self,channel,x,y):
        if self.kind=='extreme': return float(np.sign(math.sin(self.phases[channel-1])))
        if self.kind=='zero': return 0.
        return .65*math.sin(x*self.k[0]+self.phases[channel-1])+.35*math.cos(y*self.k[1]-self.phases[channel-1])

def make_research_session(problem,seed,distribution=None,count=None,field=None,overlap='invisible'):
    rng=np.random.default_rng(seed)
    distribution=distribution or ('area','edge','cluster','outward')[seed%4]
    field=field or ('smooth','extreme','smooth','zero')[seed%4]
    n=int(rng.integers(10,17)) if count is None else count
    channels=rng.choice(np.arange(1,21),n,replace=False).tolist()
    if distribution=='cluster':
        center=rng.uniform(-900,900,2); xy=center+rng.normal(0,220,(n,2))
        scale=np.maximum(1,np.linalg.norm(xy,axis=1)/1799.999);xy/=scale[:,None]
    else:
        angle=rng.uniform(0,2*math.pi,n)
        radius=1800*np.sqrt(rng.uniform(0,1,n)) if distribution=='area' else rng.uniform(1600,1800,n)
        xy=np.column_stack((radius*np.cos(angle),radius*np.sin(angle)))
    nd=0 if problem==3 else int(rng.integers(1,n))
    sources=[]
    for k,(ch,(x,y)) in enumerate(zip(channels,xy)):
        r=1000. if seed%3==0 else (1500. if seed%3==1 else float(rng.uniform(1000,1500)))
        directional=k<nd
        heading=float(math.degrees(math.atan2(y,x))%360) if distribution=='outward' else float(rng.uniform(0,360))
        sources.append(Source(int(ch),float(x),float(y),r,'directional' if directional else 'omni',heading if directional else None))
    scenario=Scenario(f'LOCAL-RESEARCH-Q{problem}-{seed}',problem,'official_constraints' if n>=10 else 'test_fixture',tuple(sources))
    numerics=Numerics('TEST_INPUT','half_up','half_up',overlap,0.)
    session=Session(ReferenceKernel(scenario,FixedField(seed+917,field),numerics),ManualClock(),'LOCAL-TRAIN')
    session.ready_fixture()
    return session,dict(version=PROFILE_VERSION,seed=seed,problem=problem,distribution=distribution,field=field,
                        noise_seed=seed+917,quantization='half_up',overlap=overlap,assumption='非官方分布；常规10–16源；Q4两类并存')
