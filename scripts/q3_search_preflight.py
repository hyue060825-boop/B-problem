#!/usr/bin/env python3
"""Finite baseline and public-search throughput check, no official endpoint."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
from solution.search.collection import collect_search_episode, init_search_worker, evaluate_policy_episode
from solution.rl.training import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True)
    p.add_argument('--seed',type=int,default=100000000);p.add_argument('--episodes',type=int,default=16)
    p.add_argument('--workers',type=int,default=8);p.add_argument('--states',type=int,default=4)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    d=torch.load(a.checkpoint,map_location='cpu',weights_only=False);weights=d['model']
    cfg=dict(states_per_episode=a.states,max_macros=400,search={'state_seconds':30.,'sampler_seconds':10.})
    started=time.perf_counter();results=[]
    with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn'),initializer=init_search_worker) as pool:
        for i,result in enumerate(pool.map(collect_search_episode,[(s,weights,cfg) for s in range(a.seed,a.seed+a.episodes)])):
            results.append(result)
            atomic_json(out/f'episode_{i:04d}.json',{k:v for k,v in result.items() if k!='rows'})
            print(json.dumps(dict(episode=i+1,complete=result['metrics']['completion'],labels=result['search_labels'],
                                  reasons=dict(Counter(r['reason'] for r in result['records'])),elapsed=time.perf_counter()-started)),flush=True)
    torch.save([r for result in results for r in result['rows']],out/'rows.pt')
    all_records=[r for result in results for r in result['records']]
    summary=dict(episodes=a.episodes,completion=sum(r['metrics']['completion'] for r in results)/a.episodes,
                 states=len(all_records),labels=sum(r['accepted'] for r in all_records),
                 reasons=dict(Counter(r['reason'] for r in all_records)),elapsed_s=time.perf_counter()-started,
                 config=cfg,estimated_branch_macros=sum(r['expansions'] for r in all_records))
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
