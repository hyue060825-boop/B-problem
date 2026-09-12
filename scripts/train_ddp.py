#!/usr/bin/env python3
"""Equal-step DDP BC -> DAgger -> PPO, one audited checkpoint family."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.rl.distributed import synchronized_update, audit_sync
from solution.rl.model import StructuralCandidatePolicy
from solution.rl.structural_features import FEATURE_VERSION as STRUCTURAL_FEATURE_VERSION
from solution.rl.training import (collect, init_worker, atomic_json, save_checkpoint,
                                  summarize, provenance, require_authorized_research)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    args=parser.parse_args();cfg=json.loads(Path(args.config).read_text())
    if require_authorized_research(cfg):raise ValueError('authorized compatible_research required')
    if cfg.get('model_version','candidate-cross-attn-v2')!='candidate-cross-attn-v2':
        raise ValueError('this entry point trains only the v2 candidate-query attention model')
    torch.set_num_threads(1)
    local=int(os.environ['LOCAL_RANK']);torch.cuda.set_device(local)
    device=torch.device('cuda',local)
    dist.init_process_group('nccl',timeout=timedelta(minutes=20))
    rank=dist.get_rank();world=dist.get_world_size()
    out=Path(cfg['output'])
    if (out/'latest.pt').exists():raise ValueError('use a fresh output directory; automatic overwrite forbidden')
    cfg={**cfg,'ddp_world_size':world,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),
         'training_algorithm':'ddp-equal-step-v2'}
    updates=cfg['ppo_updates'];budget=cfg.get('max_macros',400)
    block=1000000;base=cfg['seed']
    counts={'BC':cfg['bc_episodes'],'DAGGER':cfg['dagger_episodes'],
            'PPO':cfg['episodes_per_update'],'VALIDATION':cfg['eval_episodes'],
            'TEST':cfg.get('test_episodes',512)}
    offsets={'BC':0,'DAGGER':block,'PPO':2*block,'VALIDATION':3*block,'TEST':4*block}
    for stage in ('BC','DAGGER','PPO'):
        if counts[stage]<world or counts[stage]%world:
            raise ValueError(f'{stage} global episode count must be divisible by world_size')
    for stage in ('VALIDATION','TEST'):
        if counts[stage]<world or counts[stage]%world:
            raise ValueError(f'{stage} global episode count must be divisible by world_size')
    if updates*counts['PPO']>=block or cfg.get('dagger_rounds',2)*counts['DAGGER']>=block:
        raise ValueError('seed blocks would overlap')
    def seeds(stage,iteration=0,shard=True):
        start=base+offsets[stage]+iteration*counts[stage]
        n=counts[stage]
        return range(start+rank*n//world,start+(rank+1)*n//world) if shard else range(start,start+n)
    random.seed(base+rank);np.random.seed(base+rank);torch.manual_seed(base+rank)
    structural=True
    model=DDP(StructuralCandidatePolicy().to(device),device_ids=[local])
    opt=torch.optim.Adam(model.parameters(),lr=cfg.get('lr',3e-4))
    started=time.perf_counter();best=float('inf');recent=[]
    initial_provenance=provenance()
    def event(stage,**data):
        if rank!=0:return
        row=dict(stage=stage,elapsed_s=time.perf_counter()-started,**data)
        print(json.dumps(row,ensure_ascii=False,allow_nan=False),flush=True)
        with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        atomic_json(out/'status.json',row)
    if rank==0:
        out.mkdir(parents=True,exist_ok=True)
        atomic_json(out/'config.json',cfg);atomic_json(out/'provenance.json',initial_provenance)
        atomic_json(out/'seed_manifest.json',{
            stage:dict(start=base+offsets[stage],count=counts[stage]*(updates if stage=='PPO' else cfg.get('dagger_rounds',2) if stage=='DAGGER' else 1))
            for stage in offsets})
        event('INIT',world_size=world,physical_gpus=cfg['cuda_visible_devices'])
    dist.barrier()
    def campaign(pool,stage,iteration=0,policy=None,behavior='sample',require_complete=False):
        t=time.perf_counter()
        result=collect(pool,cfg['problem'],seeds(stage,iteration),policy,behavior,budget,structural=structural)
        metrics=[m for _,m in result];gathered=[None]*world
        dist.all_gather_object(gathered,metrics)
        all_metrics=[m for group in gathered for m in group]
        if rank==0:atomic_json(out/f'{stage.lower()}_{iteration:04d}_episodes.json',all_metrics)
        anomalies=[m for m in all_metrics if m['error'] not in (None,'macro_budget','virtual_timeout')]
        if anomalies:raise RuntimeError(f'{stage} invariant failure: {anomalies[0]}')
        complete=sum(m['completion'] for m in all_metrics)/len(all_metrics)
        if require_complete and complete<1.0:
            raise RuntimeError(f'{stage} completion {complete}; stopping before learning bad trajectories')
        return result,dict(completion_rate=complete,episodes=len(all_metrics),
                           macros=sum(m['macro_steps'] for m in all_metrics),sample_s=time.perf_counter()-t,
                           mean_virtual_s=float(np.mean([m['virtual_time_s'] for m in all_metrics])))
    def validate(pool,update,stage='VALIDATION'):
        nonlocal best
        dist.barrier()
        local_seeds=seeds(stage,shard=True)
        teacher=collect(pool,cfg['problem'],local_seeds,max_macros=budget,structural=structural)
        student=collect(pool,cfg['problem'],local_seeds,model.module,'greedy',budget,structural=structural)
        local_pairs=[dict(seed=t[1]['seed'],baseline=t[1],student=s[1]) for t,s in zip(teacher,student)]
        gathered=[None]*world;dist.all_gather_object(gathered,local_pairs)
        if rank==0:
            pairs=sorted((p for part in gathered for p in part),key=lambda p:p['seed'])
            base=[([],p['baseline']) for p in pairs];new=[([],p['student']) for p in pairs]
            a=summarize(base);b=summarize(new)
            delta=np.array([p['student']['virtual_time_s']/p['student']['N']-
                            p['baseline']['virtual_time_s']/p['baseline']['N'] for p in pairs])
            half=float(1.96*delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else 0.
            eligible=a['completion_rate']==1. and b['completion_rate']==1.
            val=dict(baseline=a,student=b,eligible=eligible,
                     mean_paired_delta_s=float(delta.mean()),approximate_95ci_halfwidth_s=half,
                     paired_metric='candidate T/N minus baseline T/N, seconds/source',
                     selection_pass=bool(eligible and delta.mean()+half<0),rows=pairs)
            atomic_json(out/f'{stage.lower()}_{update:04d}.json',val)
            event(stage,update=update,completion_rate=val['student']['completion_rate'],
                  paired_delta_s=val['mean_paired_delta_s'],selection_pass=val['selection_pass'])
            if stage=='VALIDATION' and val['selection_pass'] and val['mean_paired_delta_s']<best:
                best=val['mean_paired_delta_s']
                save_checkpoint(out/'best.pt',model.module,opt,cfg,'DDP_PPO',update-1,val,{'best_delta':best},feature_version=STRUCTURAL_FEATURE_VERSION)
        dist.barrier()
    with ProcessPoolExecutor(cfg.get('workers_per_rank',2),mp_context=mp.get_context('spawn'),initializer=init_worker,
                             initargs=(structural,)) as pool:
        base_episodes,metrics=campaign(pool,'BC',require_complete=True)
        event('BASELINE',**metrics)
        stats=synchronized_update(model,opt,base_episodes,device,'BC',cfg.get('bc_epochs',6),cfg.get('batch_size',128),structural=structural)
        event('BC',**stats)
        for iteration in range(cfg.get('dagger_rounds',2)):
            # Failed student trajectories are valuable DAgger states. Keep
            # and relabel them; the validation gate, not data collection,
            # enforces 100% completion before checkpoint admission.
            eps,metrics=campaign(pool,'DAGGER',iteration,model.module,'greedy',require_complete=False)
            stats=synchronized_update(model,opt,base_episodes+eps,device,'BC',cfg.get('dagger_epochs',3),cfg.get('batch_size',128),structural=structural)
            event('DAGGER',round=iteration+1,**metrics,**stats)
        validate(pool,0)
        for idx in range(updates):
            t=time.perf_counter()
            episodes,metrics=campaign(pool,'PPO',idx,model.module)
            update_start=time.perf_counter()
            stats=synchronized_update(model,opt,episodes,device,'PPO',cfg.get('ppo_epochs',4),cfg.get('batch_size',128),structural=structural)
            update_s=time.perf_counter()-update_start
            elapsed=torch.tensor(time.perf_counter()-t,device=device);dist.all_reduce(elapsed,op=dist.ReduceOp.MAX)
            recent.append(float(elapsed));eta=float(np.mean(recent[-10:]))*(updates-idx-1)
            event('DDP_PPO',update=idx+1,total_updates=updates,eta_s=eta,update_s=update_s,
                  macros_per_s=metrics['macros']/float(elapsed),**metrics,**stats)
            if rank==0:
                if provenance()!=initial_provenance:raise RuntimeError('source changed during training; preserve checkpoint and stop')
                save_checkpoint(out/'latest.pt',model.module,opt,cfg,'DDP_PPO',idx,stats,{'best_delta':best},feature_version=STRUCTURAL_FEATURE_VERSION)
            dist.barrier()
            if (idx+1)%cfg.get('eval_every',20)==0 or idx+1==updates:validate(pool,idx+1)
        # Held-out test is evaluated only once after model selection is frozen.
        if rank==0:
            selected=out/('best.pt' if (out/'best.pt').exists() else 'latest.pt')
            data=torch.load(selected,map_location='cpu',weights_only=False)
            model.module.load_state_dict(data['model'])
            atomic_json(out/'test_selection.json',{'checkpoint':str(selected),'selection_uses_test':False})
        validate(pool,updates,'TEST')
        event('COMPLETE',updates=updates,world_size=world,best_selected=(out/'best.pt').exists())
    dist.destroy_process_group()


if __name__=='__main__':main()
