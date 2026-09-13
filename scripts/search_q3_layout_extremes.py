"""Construct and search Q3 layout extrema, holding non-layout inputs fixed."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import sys
import time

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deployment/runtime_public_v2'))
from bsim.clocks import ManualClock
from bsim.noise import FixtureNoise,Numerics
from bsim.reference import ReferenceKernel
from bsim.scenarios import Scenario,Source
from bsim.session import Session
from solution.rl import environment as environment_module
from solution.rl.environment import TrainingEnv,model_state
from solution.rl.model import CandidatePolicy
from solution.rl.training import verify_checkpoint_code

MODES=('near_start','compact','area','edge_random','edge_ring','three_clusters','two_clusters','thin_line')
CHECKPOINT=ROOT/'runs/q3_legacy_deadline_20260913/best.pt'


def init():
    global MODEL
    torch.set_num_threads(1)
    data=torch.load(CHECKPOINT,map_location='cpu',weights_only=False)
    verify_checkpoint_code(data)
    for p,h in data['provenance']['files'].items():
        if p.startswith(('solution/','bsim/')):
            assert hashlib.sha256((ROOT/'deployment/runtime_public_v2'/p).read_bytes()).hexdigest()==h
    MODEL=CandidatePolicy().eval();MODEL.load_state_dict(data['model'])


def project(points):
    points=np.asarray(points,dtype=float)
    return points/np.maximum(1.,np.linalg.norm(points,axis=1)/1799.9)[:,None]


def make_case(n,mode,seed):
    rng=np.random.default_rng(seed);phase=rng.uniform(0,2*np.pi)
    angle=rng.uniform(0,2*np.pi,n)
    if mode=='near_start':
        radius=rng.uniform(.5,4.,n);xy=np.column_stack((radius*np.cos(angle),radius*np.sin(angle)))
    elif mode=='compact':
        center=np.array([np.cos(phase),np.sin(phase)])*rng.uniform(100,1700)
        xy=center+rng.normal(0,rng.uniform(2,150),(n,2))
    elif mode=='area':
        radius=1800*np.sqrt(rng.uniform(0,1,n));xy=np.column_stack((radius*np.cos(angle),radius*np.sin(angle)))
    elif mode.startswith('edge'):
        radius=rng.uniform(1700,1799.9,n);xy=np.column_stack((radius*np.cos(angle),radius*np.sin(angle)))
    elif mode=='two_clusters':
        center=np.array([np.cos(phase),np.sin(phase)])*rng.uniform(1200,1750)
        xy=np.where(np.arange(n)[:,None]%2,center,-center)+rng.normal(0,30,(n,2))
    else:
        along=rng.uniform(-1750,1750,n);offset=rng.uniform(-300,300)
        xy=np.column_stack((along,rng.normal(offset,2,n))) @ np.array([[np.cos(phase),np.sin(phase)],[-np.sin(phase),np.cos(phase)]])
    if mode=='edge_ring':
        angles=phase+np.arange(n)*2*np.pi/n+rng.normal(0,.015,n)
        radius=rng.uniform(1750,1799.9,n)
        xy=np.column_stack((radius*np.cos(angles),radius*np.sin(angles)))
    elif mode=='three_clusters':
        angles=phase+(np.arange(n)%3)*2*np.pi/3
        xy=1600*np.column_stack((np.cos(angles),np.sin(angles)))+rng.normal(0,30,(n,2))
    xy=project(xy)
    sources=[Source(i+1,float(x),float(y),1000.,'omni',None) for i,(x,y) in enumerate(xy)]
    return fixture(Scenario(f'LOCAL-Q3-LAYOUT-{seed}',3,'official_constraints',tuple(sources)),seed,mode)


def fixture(scenario,seed,mode):
    return dict(scenario=asdict(scenario),seed=seed,mode=mode,
                noise=dict(label='TEST_INPUT',kind='constant',value=0.),
                numerics=dict(label='TEST_INPUT',angle_rounding='half_up',time_rounding='half_up',directional_overlap='invisible',boundary_epsilon=0.))


def mutate(case,seed,round_index):
    rng=np.random.default_rng(seed)
    spec=case['scenario'];sources=[dict(s) for s in spec['sources']]
    n=len(sources);xy=np.array([[s['x'],s['y']] for s in sources])
    kind=seed%4
    if kind==0:
        chosen=rng.choice(n,size=max(1,n//3),replace=False)
        xy[chosen]+=rng.normal(0,200/(round_index+1),(len(chosen),2))
    elif kind==1:
        xy+=rng.normal(0,120/(round_index+1),2)
    elif kind==2:
        angle=rng.normal(0,.15/(round_index+1));rot=np.array([[np.cos(angle),np.sin(angle)],[-np.sin(angle),np.cos(angle)]])
        xy=xy@rot
    else:
        chosen=rng.choice(n,size=2,replace=False)
        xy[chosen]=xy[chosen[::-1]]  # Swap positions between fixed channels.
    xy=project(xy)
    for i,s in enumerate(sources):
        s['x'],s['y']=map(float,xy[i])
    return fixture(Scenario(f'LOCAL-Q3-LAYOUT-{seed}',3,'official_constraints',tuple(Source(**s) for s in sources)),seed,'mutated:'+case['mode'].split(':')[-1])


def evaluate(job):
    case,record,clock_mode=job
    spec=case['scenario'];scenario=Scenario(spec['label'],3,spec['scope'],tuple(Source(**s) for s in spec['sources']))
    session=Session(ReferenceKernel(scenario,FixtureNoise(case['noise']),Numerics(**case['numerics'])),ManualClock(),'LOCAL-TRAIN')
    session.ready_fixture()
    profile=dict(seed=case['seed'],distribution=case['mode'],field='zero',version='layout-extremes-v1')
    original_factory=environment_module.make_research_session
    environment_module.make_research_session=lambda *args,**kwargs:(session,profile)
    try:env=TrainingEnv(3,case['seed'],max_macros=400)
    finally:environment_module.make_research_session=original_factory
    events=[];discoveries={};last_clear=0.;request=env._request
    def traced(path,pos,ch):
        nonlocal last_clear
        before=env.session.state.virtual_us/1e6
        response=request(path,pos,ch);end=env.session.state.virtual_us/1e6
        if response.get('measure_result') in ('near','direction'):discoveries.setdefault(ch,end)
        if response.get('clear_result')=='success':last_clear=end
        if record:events.append(dict(path=path,position=pos,channel=ch,start_s=before,end_s=end,response=response))
        return response
    env._request=traced
    while not env.done:
        state,actions=env.observe()
        if clock_mode=='fixed':state['global_'][4]=1.
        with torch.inference_mode():logits,_=MODEL({k:torch.from_numpy(v).unsqueeze(0) for k,v in model_state(state).items()})
        assert torch.isfinite(logits).all()
        env.step(actions[int(logits.argmax(-1))])
    result=env.metrics()
    result.update(mode=case['mode'],last_clear_s=last_clear,last_discovery_s=max(discoveries.values(),default=0.),
                  tail_s=result['virtual_time_s']-last_clear,clock_mode=clock_mode,
                  scenario_sha256=hashlib.sha256(json.dumps(asdict(scenario),sort_keys=True).encode()).hexdigest())
    if record:result['events']=events
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='runs/q3_layout_extremes_20260913')
    ap.add_argument('--workers',type=int,default=8);ap.add_argument('--per-mode',type=int,default=64)
    ap.add_argument('--rounds',type=int,default=4);ap.add_argument('--mutations',type=int,default=24)
    ap.add_argument('--replay');a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    init()
    if a.replay:
        case=json.loads(Path(a.replay).read_text());result=evaluate((case,True,'live'))
        (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps({k:v for k,v in result.items() if k!='events'},indent=2));return
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest=dict(checkpoint=str(CHECKPOINT),checkpoint_sha256=hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),
                  counts=list(range(10,16)),modes=MODES,per_mode=a.per_mode,refinement_rounds=a.rounds,mutations_per_extreme=a.mutations,
                  fixed_controls=dict(channels='1..N',directional_count=0,radius_m=1000,error_deg=0),
                  source_sha256=source_hash,scope='Constructed/adaptively selected extrema, not random-test averages or proven global bounds',
                  selection_metric='total virtual time, completed cases only; any failures separately retained',clock_feature='fixed 1200 for search; selected cases replayed with live feature',workers=a.workers)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
    (out/'search_source.py').write_bytes(Path(__file__).read_bytes())
    seed=2020000000;best={};worst={};failures=[];rows=[];case_by_seed={};start=time.perf_counter()
    initial=[]
    for n in range(10,16):
        for mode in MODES:
            for _ in range(a.per_mode):
                initial.append(make_case(n,mode,seed));seed+=1
    with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn'),initializer=init) as pool,(out/'samples.jsonl').open('w') as stream:
        def batch(cases):
            nonlocal best,worst
            for case,r in zip(cases,pool.map(evaluate,[(c,False,'fixed') for c in cases],chunksize=2)):
                n=r['N'];rows.append(r);case_by_seed[r['seed']]=case;stream.write(json.dumps(r,ensure_ascii=False)+'\n')
                if not r['completion']:failures.append(r)
                else:
                    if n not in best or r['virtual_time_s']<best[n]['virtual_time_s']:best[n]=r
                    if n not in worst or r['virtual_time_s']>worst[n]['virtual_time_s']:worst[n]=r
                if len(rows)%200==0:
                    stream.flush();status=dict(evaluated=len(rows),failures=len(failures),elapsed_s=time.perf_counter()-start)
                    (out/'status.json').write_text(json.dumps(status));print(json.dumps(status),flush=True)
        batch(initial)
        for round_index in range(a.rounds):
            candidates=[]
            for n in range(10,16):
                for parent in (best[n],worst[n]):
                    for _ in range(a.mutations):
                        candidates.append(mutate(case_by_seed[parent['seed']],seed,round_index));seed+=1
            batch(candidates)
    selected={}
    for n in range(10,16):
        selected[str(n)]={}
        target=out/f'N{n}';target.mkdir()
        for label,picked in (('best',best[n]),('worst',worst[n])):
            case=case_by_seed[picked['seed']]
            checks=[evaluate((case,i==0,'live')) for i in range(2)]
            assert all(r['completion'] and r['virtual_time_s']==picked['virtual_time_s'] for r in checks)
            (target/f'{label}_fixture.json').write_text(json.dumps(case,indent=2,ensure_ascii=False))
            (target/f'{label}_trace.json').write_text(json.dumps(checks[0],indent=2,ensure_ascii=False))
            selected[str(n)][label]=dict(picked,fixture=str((target/f'{label}_fixture.json').resolve()),verified_live_repeats=2)
    summary=dict(selected=selected,total_evaluated=len(rows),counts_per_N={str(n):sum(r['N']==n for r in rows) for n in range(10,16)},
                 failures=len(failures),elapsed_s=time.perf_counter()-start)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    (out/'failures.json').write_text(json.dumps(failures,indent=2,ensure_ascii=False))
    for r in failures[:12]:(out/f"failed_{r['seed']}_fixture.json").write_text(json.dumps(case_by_seed[r['seed']],indent=2,ensure_ascii=False))
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==source_hash
    (out/'status.json').write_text(json.dumps(dict(status='COMPLETE',evaluated=len(rows),failures=len(failures))))
    print(json.dumps({n:{k:round(v['virtual_time_s'],3) for k,v in d.items()} for n,d in selected.items()},indent=2),flush=True)


if __name__=='__main__':main()
