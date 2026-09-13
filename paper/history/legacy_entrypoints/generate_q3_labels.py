#!/usr/bin/env python3
"""Bounded, resumable public-search label collection from one frozen student."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.search.collection import collect_search_episode,init_search_worker
from solution.rl.training import atomic_json,provenance


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--round',type=int,required=True);a=p.parse_args();cfg=json.loads(Path(a.config).read_text())
    root=Path(cfg['output']);out=root/f'labels_round{a.round}';out.mkdir(parents=True,exist_ok=True)
    ledger=json.loads((root/'seeds.json').read_text());seeds=ledger[f'labels_round{a.round}']
    checkpoint=Path(a.checkpoint);weights=torch.load(checkpoint,map_location='cpu',weights_only=False)['model']
    fingerprint=dict(checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                     seeds=seeds,collection=cfg['collection'],provenance=provenance())
    if (out/'manifest.json').exists():
        if json.loads((out/'manifest.json').read_text())!=fingerprint:raise ValueError('partial collection version mismatch; use new directory')
    else:atomic_json(out/'manifest.json',fingerprint)
    pending=[i for i in range(len(seeds)) if not (out/f'case_{i:04d}.pt').exists()]
    started=time.perf_counter();completed=[]
    with ProcessPoolExecutor(cfg['search_workers'],mp_context=mp.get_context('spawn'),initializer=init_search_worker) as pool:
        iterator=pool.map(collect_search_episode,[(seeds[i],weights,cfg['collection']) for i in pending])
        for i,result in zip(pending,iterator):
            if time.perf_counter()-started>cfg['collection_stage_seconds']:
                atomic_json(out/'incomplete.json',dict(reason='stage_time_budget',remaining=pending[len(completed):]));raise RuntimeError('collection budget exhausted; partial results preserved')
            if not result['metrics']['completion']:raise RuntimeError('student collection incomplete; inspect before continuing')
            atomic_json(out/f'case_{i:04d}.json',{k:v for k,v in result.items() if k!='rows'})
            tmp=out/f'case_{i:04d}.tmp';torch.save(result['rows'],tmp);tmp.replace(out/f'case_{i:04d}.pt')
            completed.append(i)
            if len(completed)%10==0:print(json.dumps(dict(round=a.round,completed=len(seeds)-len(pending)+len(completed),total=len(seeds),elapsed_s=time.perf_counter()-started)),flush=True)
    rows=[];reasons=Counter();sampling_rejections=Counter();labels=0;states=0;search_s=0.;expansions=0
    for i in range(len(seeds)):
        rows.extend(torch.load(out/f'case_{i:04d}.pt',weights_only=False))
        record=json.loads((out/f'case_{i:04d}.json').read_text());labels+=record['search_labels'];search_s+=record['search_seconds']
        states+=len(record['records']);expansions+=sum(r['expansions'] for r in record['records'])
        reasons.update(r['reason'] for r in record['records'])
        for r in record['records']:sampling_rejections.update(r.get('sampling',{}).get('rejections',{}))
    torch.save(rows,out/'data.pt')
    summary=dict(status='COMPLETE',episodes=len(seeds),states=states,search_labels=labels,
                 retention_rows=len(rows)-labels,filter_reasons=dict(reasons),sampling_rejections=dict(sampling_rejections),
                 expanded_macros=expansions,cpu_search_s=search_s,elapsed_s=time.perf_counter()-started,
                 labels_per_wall_s=labels/max(1e-9,time.perf_counter()-started),data_sha256=hashlib.sha256((out/'data.pt').read_bytes()).hexdigest())
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
