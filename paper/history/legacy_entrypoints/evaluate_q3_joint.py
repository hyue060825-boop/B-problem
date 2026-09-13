#!/usr/bin/env python3
"""Paired Q3 baseline/stages/search evaluation on an explicit seed manifest."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.search.collection import init_search_worker,evaluate_policy_episode
from solution.rl.training import atomic_json,provenance


def summary(rows):
    times=np.array([r['virtual_time_s'] for r in rows]);decisions=np.array([t for r in rows for t in r['decision_times_s']])
    return dict(episodes=len(rows),completion_rate=sum(r['completion'] for r in rows)/len(rows),
                mean_virtual_s=float(times.mean()),median_virtual_s=float(np.median(times)),p95_virtual_s=float(np.percentile(times,95)),
                mean_per_source_s=float(np.mean([r['time_per_clear_s'] for r in rows])) if all(r['C'] for r in rows) else None,
                decision_p50_s=float(np.median(decisions)),decision_p95_s=float(np.percentile(decisions,95)),decision_max_s=float(decisions.max()),
                mean_cleared_fraction=float(np.mean([r['cleared_fraction'] for r in rows])),failures=[r for r in rows if not r['completion']],
                means={k:float(np.mean([r[k] for r in rows])) for k in ('path_length_m','measures','switches','clear_failures','macro_steps')})


def compare(baseline,student):
    assert [r['seed'] for r in baseline]==[r['seed'] for r in student]
    d=np.array([s['virtual_time_s']-b['virtual_time_s'] for b,s in zip(baseline,student)])
    half=float(1.96*d.std(ddof=1)/np.sqrt(len(d))) if len(d)>1 else float('inf')
    eligible=all(r['completion'] for r in baseline+student)
    return dict(eligible=eligible,mean_delta_s=float(d.mean()),ci95_halfwidth_s=half,
                robust_gain=bool(eligible and d.mean()+half<0),selection_pass=bool(eligible and d.mean()<0))


def evaluate(pool,seeds,weights,max_macros=400,search=None):
    return list(pool.map(evaluate_policy_episode,[(s,weights,max_macros,search) for s in seeds]))


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--checkpoint',action='append',default=[])
    p.add_argument('--output',required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--episodes',type=int,default=128);p.add_argument('--workers',type=int,default=16)
    p.add_argument('--search-episodes',type=int,default=0);p.add_argument('--max-macros',type=int,default=400)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);seeds=list(range(a.seed,a.seed+a.episodes))
    frozen={'baseline':a.baseline,**{Path(path).stem:path for path in a.checkpoint}}
    if len(frozen)!=1+len(a.checkpoint):raise ValueError('unique checkpoint names required')
    manifest=dict(seeds=seeds,search_subset=seeds[:a.search_episodes],checkpoints={k:dict(path=v,sha256=hashlib.sha256(Path(v).read_bytes()).hexdigest()) for k,v in frozen.items()},provenance=provenance())
    atomic_json(out/'manifest.json',manifest);results={};report={};started=time.perf_counter()
    with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn'),initializer=init_search_worker) as pool:
        for name,path in [('rule',None),*frozen.items()]:
            weights=None if path is None else torch.load(path,map_location='cpu',weights_only=False)['model']
            rows=evaluate(pool,seeds,weights,a.max_macros);results[name]=rows;report[name]=summary(rows)
            atomic_json(out/f'{name}_episodes.json',rows);print(json.dumps({'name':name,**report[name]},ensure_ascii=False),flush=True)
        if a.search_episodes:
            weights=torch.load(a.baseline,map_location='cpu',weights_only=False)['model']
            rows=evaluate(pool,seeds[:a.search_episodes],weights,a.max_macros,{'state_seconds':30.,'sampler_seconds':10.,'states_per_episode':8})
            results['search_teacher']=rows;report['search_teacher']=summary(rows)
            atomic_json(out/'search_teacher_episodes.json',rows)
        for name,rows in results.items():
            if name!='baseline':report[name]['vs_baseline']=compare(results['baseline'][:len(rows)],rows)
            strata={}
            for key in ('N','radius_class'):
                strata[key]={str(v):summary([r for r in rows if r[key]==v]) for v in sorted({r[key] for r in rows},key=str)}
            for key in ('distribution','field'):
                strata[key]={v:summary([r for r in rows if r['profile'][key]==v]) for v in sorted({r['profile'][key] for r in rows})}
            atomic_json(out/f'{name}_strata.json',strata)
    report['elapsed_s']=time.perf_counter()-started
    atomic_json(out/'summary.json',report);print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
