"""Bounded TEST campaigns, not scenario training or official sampling."""
import random
import time
import platform
import os
from .evaluation import create_fixture_session
from .reference import ReferenceKernel, State
from .fast import FastKernel
from .scenarios import Scenario, Source
from .profiles import Blocked


def compare_kernels(fixture, steps=2000, seed=20260911):
    session=create_fixture_session(fixture)
    # Arbitrary deterministic TEST inputs; seed is unrelated to official cases.
    rng=random.Random(seed)
    sources=tuple(Source(c,rng.uniform(-800,800),rng.uniform(-800,800),rng.uniform(1000,1500),
                         'omni' if c%2 else 'directional',None if c%2 else rng.uniform(0,360)) for c in range(1,17))
    scenario=Scenario('LOCAL-equivalence-inputs',4,'official_constraints',sources)
    ref=ReferenceKernel(scenario,session.kernel.noise,session.kernel.numerics)
    fast=FastKernel(scenario,session.kernel.noise,session.kernel.numerics)
    a=b=State();mismatches=[]
    for i in range(steps):
        path='/measure' if rng.random()<.8 else '/clear'
        channel=rng.randint(1,20)
        p=(rng.uniform(-2200,2200),rng.uniform(-2200,2200))
        a,ra=ref.transition(a,path,p,channel)
        b,rb=fast.transition(b,path,p,channel)
        if a!=b or ra!=rb:mismatches.append({'step':i+1,'reference':str((a,ra)),'fast':str((b,rb))})
        if i%100==99:a=b=State()  # explicit TEST reset; physical kernel not lifecycle
    # Exact near/clear/receive boundaries and adjacent floating-point values.
    boundary_cases=0
    for radius in (5,20,1000,1500):
        for x in (radius,math_next(radius,False),math_next(radius,True)):
            for p in ((x,0),(-x,0),(0,x),(0,-x)):
                boundary_cases+=1
                if ref.within((0,0),p,radius)!=fast.within((0,0),p,radius):
                    mismatches.append({'boundary':p,'radius':radius})
    return {'label':'LOCAL-kernel-comparison','status':'FAIL' if mismatches else 'PASS','steps':steps,
            'boundary_cases':boundary_cases,'test_seed':seed,'mismatches':mismatches,
            'qualification':'TEST inputs; shared angle/error/time policies do not resolve G02-G06'}


def math_next(x,positive):
    import math
    return math.nextafter(float(x),math.inf if positive else -math.inf)


def benchmark(fixture, device='cpu',num_envs=64,steps=128):
    if device!='cpu':
        raise Blocked('CUDA backend NOT_RUN/NOT_IMPLEMENTED: no CUDA server connected; CPU fixture benchmark remains available')
    if not 1<=num_envs<=4096 or not 1<=steps<=10000:
        raise ValueError('benchmark size outside bounded TEST range')
    session=create_fixture_session(fixture)
    results=[]
    for kernel_cls in (ReferenceKernel,FastKernel):
        kernels=[kernel_cls(session.kernel.scenario,session.kernel.noise,session.kernel.numerics) for _ in range(num_envs)]
        states=[State() for _ in kernels]
        t=time.perf_counter()
        for i in range(steps):
            for j,k in enumerate(kernels):
                states[j],_=k.transition(states[j],'/measure',(float(i%100+6),float(j%20)),7)
        elapsed=time.perf_counter()-t
        results.append({'kernel':kernel_cls.__name__,'elapsed_s':elapsed,'transitions':steps*num_envs,
                        'transitions_per_s':steps*num_envs/elapsed})
    return {'label':'LOCAL-CPU-fixture-benchmark','device':device,'platform':platform.platform(),
            'python':platform.python_version(),'cpu_count':os.cpu_count(),'num_envs':num_envs,'steps':steps,
            'results':results,'qualification':'single-process CPU physical transitions; excludes HTTP, belief update, training, GPU and interprocess transfer'}
