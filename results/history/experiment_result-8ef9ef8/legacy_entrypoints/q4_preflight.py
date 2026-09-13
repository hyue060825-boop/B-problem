#!/usr/bin/env python3
"""CPU preflight for repaired Q4; stores cases, timings and old-model diagnostics."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import multiprocessing as mp
from pathlib import Path
import sys
import time
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.rl.environment import TrainingEnv
from solution.rl.training import atomic_json, init_worker, collect, paired_evaluation, provenance
from solution.rl.model import CandidatePolicy


def teacher_case(job):
    count,distribution,field=job
    e=TrainingEnv(4,30000000+count,count=count,distribution=distribution,field=field)
    while not e.done:
        _,aa=e.observe();e.step(aa[e.controller.teacher_index(aa)])
    return e.metrics()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    torch.set_num_threads(1);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    jobs=[(n,d,f) for n in range(10,17) for d in ('area','edge','cluster','outward') for f in ('zero','smooth','extreme')]
    with ProcessPoolExecutor(4,mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
        rows=list(pool.map(teacher_case,jobs))
        atomic_json(out/'teacher_stratified_84.json',rows)
        assert all(m['completion'] for m in rows), 'teacher preflight failed'
    timings=[]
    for workers in (2,4,8):
        with ProcessPoolExecutor(workers,mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
            collect(pool,4,range(30500000,30500000+workers))
            t=time.perf_counter();eps=collect(pool,4,range(30500100,30500164),max_macros=400)
            dt=time.perf_counter()-t
        assert all(m['completion'] for _,m in eps)
        timings.append(dict(workers=workers,episodes=64,seconds=dt,episodes_per_s=64/dt))
    # Explicitly diagnostic: old weights run with the repaired controller.
    old=Path('runs/ddp_20260911/q4/latest.pt')
    model=CandidatePolicy();data=torch.load(old,map_location='cpu',weights_only=False)
    model.load_state_dict(data['model']);model.eval()
    with ProcessPoolExecutor(4,mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
        val=paired_evaluation(pool,4,range(30600000,30600064),model,400)
    atomic_json(out/'old_weights_repaired_controller_64.json',val)
    summary={'teacher_84_completion':sum(m['completion'] for m in rows)/len(rows),
             'worker_benchmark':timings,'old_weights_diagnostic':True,'checkpoint_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),
             'old_checkpoint_provenance':data['provenance'],'evaluation_provenance':provenance(),
             'old_weights_completion':val['student']['completion_rate'],
             'old_weights_delta_s':val['mean_paired_delta_s']}
    atomic_json(out/'summary.json',summary)
    print({k:v for k,v in summary.items() if 'provenance' not in k},flush=True)


if __name__=='__main__':main()
