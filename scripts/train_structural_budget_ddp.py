#!/usr/bin/env python3
"""Timed, resumable structural-policy PPO with synchronized safe stopping."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import signal
import sys
import time

import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solution.rl.distributed import audit_sync, synchronized_update
from solution.rl.model import StructuralCandidatePolicy
from solution.rl.structural_features import FEATURE_VERSION
from solution.rl.training import (atomic_json, collect, init_worker, load_checkpoint,
                                  provenance, require_authorized_research, save_checkpoint)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--resume')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    if require_authorized_research(cfg):
        raise ValueError('authorized research profile required')
    torch.set_num_threads(1)
    local = int(os.environ['LOCAL_RANK'])
    torch.cuda.set_device(local)
    device = torch.device('cuda', local)
    dist.init_process_group('nccl', timeout=timedelta(minutes=10))
    rank, world = dist.get_rank(), dist.get_world_size()
    if world != cfg['world_size'] or cfg['episodes_per_update'] % world:
        raise ValueError('world_size/episode sharding mismatch')
    ranges = [(cfg['seed'], cfg['seed'] + cfg['max_updates']*cfg['episodes_per_update']),
              (cfg['validation_seed'], cfg['validation_seed'] + cfg['validation_episodes']),
              (cfg['test_seed'], cfg['test_seed'] + cfg['test_episodes'])]
    if any(max(a,c)<min(b,d) for i,(a,b) in enumerate(ranges) for c,d in ranges[i+1:]):
        raise ValueError('seed ranges overlap')
    out = Path(cfg['output'])
    if not args.resume and out.exists():
        raise ValueError('use a fresh output directory')
    random.seed(cfg['seed']+rank)
    np.random.seed(cfg['seed']+rank)
    torch.manual_seed(cfg['seed'])
    model = StructuralCandidatePolicy().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg['lr'])
    parent = Path(cfg['checkpoint'])
    parent_hash = hashlib.sha256(parent.read_bytes()).hexdigest()
    data = load_checkpoint(args.resume or parent, model, opt)
    if args.resume and (data['extra']['parent_sha256'] != parent_hash or data['config'] != cfg):
        raise ValueError('resume parent/config mismatch')
    for group in opt.param_groups:
        group['lr'] = cfg['lr']
    ddp = DDP(model, device_ids=[local])
    baseline_model = StructuralCandidatePolicy().eval()
    load_checkpoint(parent, baseline_model)
    extra = data.get('extra', {}) if args.resume else {}
    iteration = data['update'] + 1 if args.resume else 0
    consumed = extra.get('budget_consumed_s', 0.)
    best = extra.get('best_delta_s', 0.)
    if args.resume:
        rng = extra['rank_rng'][rank]
        random.setstate(rng['python']); np.random.set_state(rng['numpy'])
        torch.set_rng_state(rng['torch']); torch.cuda.set_rng_state(rng['cuda'], device)
    source = provenance()
    started = time.perf_counter()
    training_started = None
    interrupted = False
    def on_signal(signum, frame):
        nonlocal interrupted
        interrupted = True
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    if rank == 0:
        out.mkdir(parents=True, exist_ok=bool(args.resume))
        atomic_json(out/'config.json', cfg)
        atomic_json(out/'provenance.json', source)
        atomic_json(out/'seed_manifest.json', dict(train=ranges[0],validation=ranges[1],test=ranges[2],end_exclusive=True))
    dist.barrier()
    def used():
        return consumed + (time.perf_counter()-training_started if training_started is not None else 0.)
    def event(stage, **fields):
        if rank == 0:
            row = dict(stage=stage,elapsed_s=time.perf_counter()-started,budget_consumed_s=used(),**fields)
            atomic_json(out/'status.json', row)
            with (out/'metrics.jsonl').open('a') as f:
                f.write(json.dumps(row,allow_nan=False)+'\n')
            print(json.dumps(row,allow_nan=False),flush=True)
    def save(path, stage='BUDGET_STRUCTURAL_PPO'):
        changed = torch.tensor(int(provenance()!=source),device=device)
        dist.all_reduce(changed,op=dist.ReduceOp.MAX)
        if changed.item():
            raise RuntimeError('source changed during frozen run')
        digest = audit_sync(model,opt)
        rng = dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state(device))
        rank_rng = [None]*world
        dist.all_gather_object(rank_rng,rng)
        if rank == 0:
            save_checkpoint(path,model,opt,cfg,stage,iteration-1,{},
                dict(parent_checkpoint=str(parent),parent_sha256=parent_hash,parent_update=data['update'] if not args.resume else extra['parent_update'],
                     world_size=world,rank_rng=rank_rng,budget_consumed_s=used(),best_delta_s=best,state_sha256=digest),
                feature_version=FEATURE_VERSION)
        dist.barrier()
    def gather_episodes(pool,start,n,policy,behavior):
        error = None
        episodes = []
        try:
            episodes = collect(pool,cfg['problem'],range(start+rank,start+n,world),policy,behavior,cfg['max_macros'],structural=True)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        parts = [None]*world
        dist.all_gather_object(parts,dict(error=error,rows=[m for _,m in episodes]))
        errors = [p['error'] for p in parts if p['error']]
        rows = sorted([r for p in parts for r in p['rows']],key=lambda r:r['seed'])
        anomalies = [r for r in rows if r['error'] not in (None,'macro_budget','virtual_timeout')]
        if errors or anomalies:
            if rank == 0: atomic_json(out/'fatal_sampling.json',dict(errors=errors,anomalies=anomalies))
            raise RuntimeError('sampling invariant failure; all ranks stop')
        return episodes,rows
    def compare(base,rows):
        assert [r['seed'] for r in base] == [r['seed'] for r in rows]
        delta = np.array([s['virtual_time_s']/s['N']-b['virtual_time_s']/b['N'] for s,b in zip(rows,base)])
        half = float(1.96*delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else 0.
        complete = sum(r['completion'] for r in rows)/len(rows)
        return dict(completion_rate=complete,baseline_completion_rate=sum(r['completion'] for r in base)/len(base),
                    mean_virtual_s=float(np.mean([r['virtual_time_s'] for r in rows])),
                    mean_case_time_per_source_s=float(np.mean([r['virtual_time_s']/r['N'] for r in rows])),
                    mean_delta_s=float(delta.mean()),ci95_halfwidth_s=half,
                    paired_metric='candidate T/N minus parent T/N, seconds/source',
                    selection_pass=bool(complete==1. and all(r['completion'] for r in base) and delta.mean()+half<0))
    event('RESUMED' if args.resume else 'INIT',world_size=world,physical_gpus=os.environ.get('CUDA_VISIBLE_DEVICES'),
          checkpoint=str(args.resume or parent),parent_sha256=parent_hash,parent_update=data['update'],
          optimizer_restored=True,state_sha256=audit_sync(model,opt),parameter_and_optimizer_sync=True)
    # Save before any rollout: a failed preflight no longer loses initialization.
    save(out/'initial.pt','INITIALIZED_FROM_PARENT')
    with ProcessPoolExecutor(cfg['workers_per_rank'],mp_context=mp.get_context('spawn'),
                             initializer=init_worker,initargs=(True,)) as pool:
        cache=out/'baseline_validation.json'
        if args.resume and cache.exists():
            baseline=json.loads(cache.read_text())
        else:
            _,baseline=gather_episodes(pool,cfg['validation_seed'],cfg['validation_episodes'],baseline_model,'greedy')
            if rank==0: atomic_json(cache,baseline)
        # A previously measured imperfect parent is an evaluation baseline,
        # not failed teacher data for BC. PPO retains terminal failure rewards.
        event('BASELINE_VALIDATION',episodes=len(baseline),completion_rate=sum(r['completion'] for r in baseline)/len(baseline))
        training_started=time.perf_counter()
        def validate(stage='VALIDATION'):
            nonlocal best
            if stage=='TEST':
                _,base=gather_episodes(pool,cfg['test_seed'],cfg['test_episodes'],baseline_model,'greedy')
                _,rows=gather_episodes(pool,cfg['test_seed'],cfg['test_episodes'],model,'greedy')
            else:
                base=baseline
                _,rows=gather_episodes(pool,cfg['validation_seed'],cfg['validation_episodes'],model,'greedy')
            metrics=compare(base,rows)
            if rank==0: atomic_json(out/f'{stage.lower()}_{iteration:06d}.json',dict(baseline=base,student=rows,**metrics))
            event(stage,update=iteration,**metrics)
            if stage=='VALIDATION' and metrics['selection_pass'] and metrics['mean_delta_s']<best:
                best=metrics['mean_delta_s'];save(out/'best.pt')
        while iteration<cfg['max_updates']:
            stop=torch.tensor([int(interrupted),int(used()>=cfg['wall_seconds'])],device=device)
            dist.all_reduce(stop,op=dist.ReduceOp.MAX)
            if stop.any().item():
                interrupted=bool(stop[0].item());break
            t=time.perf_counter()
            eps,rows=gather_episodes(pool,cfg['seed']+iteration*cfg['episodes_per_update'],cfg['episodes_per_update'],model,'sample')
            stats=synchronized_update(ddp,opt,eps,device,'PPO',cfg['ppo_epochs'],cfg['batch_size'],entropy=cfg['entropy'],structural=True)
            iteration+=1
            elapsed=torch.tensor(time.perf_counter()-t,device=device)
            dist.all_reduce(elapsed,op=dist.ReduceOp.MAX)
            if rank==0: atomic_json(out/f'episodes_{iteration:06d}.json',rows)
            save(out/'latest.pt')
            event('PPO',update=iteration,episodes=len(rows),completion_rate=sum(r['completion'] for r in rows)/len(rows),
                  macros=sum(r['macro_steps'] for r in rows),iteration_s=float(elapsed),
                  remaining_budget_s=max(0.,cfg['wall_seconds']-used()),**stats)
            if iteration%cfg['eval_every']==0: validate()
        reason='signal' if interrupted else 'wall_budget' if used()>=cfg['wall_seconds'] else 'max_updates'
        save(out/'latest.pt')
        event('TRAINING_STOPPED',reason=reason,updates=iteration,checkpoint=str(out/'latest.pt'))
        if interrupted:
            event('PAUSED',reason=reason,updates=iteration)
        else:
            validate()
            selected=out/'best.pt' if (out/'best.pt').exists() else out/'latest.pt'
            model.load_state_dict(torch.load(selected,map_location='cpu',weights_only=False)['model'])
            if rank==0: atomic_json(out/'test_selection.json',dict(checkpoint=str(selected),selection_uses_test=False,
                                      recommended=str(selected) if selected.name=='best.pt' else str(parent)))
            validate('TEST')
            event('COMPLETE',updates=iteration,checkpoint=str(selected),best_selected=selected.name=='best.pt')
    dist.destroy_process_group()


if __name__=='__main__':
    main()
