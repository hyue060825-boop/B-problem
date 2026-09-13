#!/usr/bin/env python3
"""Wall-budget synchronous DDP continuation with validation and frozen test."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import sys
import time
import signal
import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'deployment/runtime_public_v2'
if not RUNTIME.is_dir():
    RUNTIME = ROOT  # launcher 的独立冻结运行目录
if not (RUNTIME / 'manifest.json').is_file():
    raise RuntimeError('缺少冻结运行时清单')
sys.path.insert(0, str(RUNTIME))
from solution.rl.model import CandidatePolicy
from solution.rl.training import collect,init_worker,atomic_json,provenance,save_checkpoint,verify_checkpoint_code
from solution.rl.joint_updates import prepare_ppo,joint_update
from solution.rl.distributed import audit_sync


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--resume')
    ap.add_argument('--stop-after',type=int);args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text());torch.set_num_threads(1)
    if cfg['train_deadline_epoch'] <= time.time():
        raise ValueError('请在新配置中设置未来的 train_deadline_epoch，原配置只作证据')
    local=int(os.environ['LOCAL_RANK']);torch.cuda.set_device(local);device=torch.device('cuda',local)
    dist.init_process_group('nccl',timeout=timedelta(minutes=30));rank=dist.get_rank();world=dist.get_world_size()
    if world!=cfg.get('world_size',4):raise ValueError('world size does not match config')
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    if not args.resume and (out/'latest.pt').exists():raise ValueError('existing run: use --resume')
    random.seed(cfg['seed']+rank);np.random.seed(cfg['seed']+rank);torch.manual_seed(cfg['seed'])
    checkpoint=args.resume or cfg['checkpoint'];data=torch.load(checkpoint,map_location='cpu',weights_only=False);verify_checkpoint_code(data)
    model=CandidatePolicy().to(device);model.load_state_dict(data['model']);ddp=DDP(model,device_ids=[local]);opt=torch.optim.Adam(model.parameters(),lr=cfg['lr'])
    if args.resume or cfg.get('restore_initial_optimizer',False):opt.load_state_dict(data['optimizer'])
    for group in opt.param_groups:group['lr']=cfg['lr']
    if args.resume and data.get('extra',{}).get('rank_rng'):
        rng=data['extra']['rank_rng'][rank]
        random.setstate(rng['python']);np.random.set_state(rng['numpy']);torch.set_rng_state(rng['torch']);torch.cuda.set_rng_state(rng['cuda'],device)
    iteration=data.get('update',-1)+1 if args.resume else 0
    consumed=data.get('extra',{}).get('budget_consumed_s',0.) if args.resume else 0.
    best=data.get('extra',{}).get('best_delta',0.) if args.resume else 0.
    interrupted=False
    def stop_signal(signum,frame):
        nonlocal interrupted
        interrupted=True
    signal.signal(signal.SIGTERM,stop_signal);signal.signal(signal.SIGINT,stop_signal)
    started=time.perf_counter();source=provenance();baseline_model=CandidatePolicy().eval()
    baseline_path=cfg.get('baseline_checkpoint',cfg['checkpoint'])
    baseline_data=torch.load(baseline_path,weights_only=False,map_location='cpu');verify_checkpoint_code(baseline_data)
    baseline_model.load_state_dict(baseline_data['model'])
    def event(kind,**fields):
        if rank==0:
            row=dict(stage=kind,elapsed_s=time.perf_counter()-started,consumed_s=consumed+time.perf_counter()-started,**fields)
            atomic_json(out/'status.json',row)
            with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
            print(json.dumps(row),flush=True)
    def save(path):
        audit_sync(model,opt)
        rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state(device))
        rank_rng=[None]*world;dist.all_gather_object(rank_rng,rng)
        if rank==0:
            if provenance()!=source:raise RuntimeError('source changed within frozen run')
            save_checkpoint(path,model,opt,cfg,'BUDGET_DDP_PPO',iteration-1,{},dict(budget_consumed_s=consumed+time.perf_counter()-started,best_delta=best,rank_rng=rank_rng,parent_checkpoint=cfg['checkpoint'],parent_sha256=hashlib.sha256(Path(cfg['checkpoint']).read_bytes()).hexdigest(),parent_update=data['update'],
                baseline_sha256=hashlib.sha256(Path(baseline_path).read_bytes()).hexdigest(),world_size=world))
        dist.barrier()
    if rank==0:
        atomic_json(out/'config.json',cfg);atomic_json(out/'provenance.json',source)
        atomic_json(out/'seed_manifest.json',dict(train_start=cfg['seed'],train_max_count=cfg['max_updates']*cfg['episodes_per_update'],
                                                 validation_start=cfg['validation_seed'],validation_count=cfg['validation_episodes'],
                                                 test_start=cfg['test_seed'],test_count=cfg['test_episodes']))
    event('INIT',world_size=world,physical_gpus=os.environ.get('CUDA_VISIBLE_DEVICES'),checkpoint=checkpoint,
          baseline_checkpoint=baseline_path,optimizer_restored=bool(args.resume or cfg.get('restore_initial_optimizer',False)),
          resumed=bool(args.resume),update=iteration,state_sha256=audit_sync(model,opt))
    save(out/'initial.pt')
    with ProcessPoolExecutor(cfg['workers_per_rank'],mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
        def eval_rows(model0,start,n):
            local_rows=[m for _,m in collect(pool,cfg['problem'],range(start+rank,start+n,world),model0,'greedy',cfg['max_macros'])]
            gathered=[None]*world;dist.all_gather_object(gathered,local_rows)
            return sorted([r for part in gathered for r in part],key=lambda r:r['seed'])
        baseline=eval_rows(baseline_model,cfg['validation_seed'],cfg['validation_episodes'])
        teacher=eval_rows(None,cfg['validation_seed'],cfg['validation_episodes'])
        if not all(r['completion'] for r in baseline+teacher):raise RuntimeError('baseline/teacher completion gate failed')
        if rank==0:atomic_json(out/'baseline_validation.json',dict(baseline=baseline,teacher=teacher))
        def validate():
            nonlocal best
            rows=eval_rows(model,cfg['validation_seed'],cfg['validation_episodes'])
            delta=np.array([s['virtual_time_s']/s['N']-b['virtual_time_s']/b['N'] for s,b in zip(rows,baseline)])
            half=float(1.96*delta.std(ddof=1)/np.sqrt(len(delta)))
            eligible=all(r['completion'] for r in rows)
            latency_limit=max(.02,2*float(np.mean([r['decision_p95_s'] for r in baseline])))
            latency_pass=float(np.mean([r['decision_p95_s'] for r in rows]))<=latency_limit
            passed=eligible and delta.mean()+half<0 and latency_pass
            event('VALIDATION',update=iteration,completion_rate=sum(r['completion'] for r in rows)/len(rows),
                  mean_delta_s=float(delta.mean()),ci95_halfwidth_s=half,selection_pass=bool(passed),latency_pass=latency_pass)
            if rank==0:atomic_json(out/f'validation_{iteration:06d}.json',dict(rows=rows,mean_delta_s=float(delta.mean()),ci95_halfwidth_s=half))
            if passed and delta.mean()<best:best=float(delta.mean());save(out/'best.pt')
        last_validation=-1
        if not args.resume and cfg.get('validate_initial',False):validate();last_validation=iteration
        while iteration<cfg['max_updates']:
            remaining=cfg['wall_seconds']-consumed-(time.perf_counter()-started)
            stop=torch.tensor(int(remaining<=0 or interrupted or time.time()>=cfg['train_deadline_epoch']),device=device);dist.all_reduce(stop,op=dist.ReduceOp.MAX)
            if stop.item():break
            t=time.perf_counter();behavior=audit_sync(model,opt);start=cfg['seed']+iteration*cfg['episodes_per_update']
            episodes=collect(pool,cfg['problem'],range(start+rank,start+cfg['episodes_per_update'],world),model,'sample',cfg['max_macros'])
            metrics=[m for _,m in episodes];parts=[None]*world;dist.all_gather_object(parts,metrics);metrics=[m for part in parts for m in part]
            if any(m['error'] not in (None,'macro_budget','virtual_timeout') for m in metrics):
                if rank==0:atomic_json(out/'fatal_episodes.json',metrics)
                raise RuntimeError('rollout invariant failure')
            rows,adv=prepare_ppo(episodes,device)
            stats=joint_update(ddp,opt,rows,device,'PPO',cfg['ppo_epochs'],cfg['per_rank_batch_size'],cfg['grad_accum_steps'],
                               entropy=cfg['entropy']*max(.1,remaining/cfg['wall_seconds']),target_kl=cfg['target_kl'],audit_every=10)
            iteration+=1
            event('PPO',update=iteration,episodes=len(metrics),macros=sum(m['macro_steps'] for m in metrics),
                  completion_rate=sum(m['completion'] for m in metrics)/len(metrics),iteration_s=time.perf_counter()-t,
                  remaining_budget_s=max(0.,remaining),behavior_sha256=behavior,state_sha256=stats['state_sha256'],
                  optimizer_steps=stats['optimizer_steps'],global_kl_stop=stats['global_kl_stop'],sync=stats['parameter_and_optimizer_sync'],
                  global_samples=stats['global_samples'],per_rank_samples=stats['per_rank_samples'],last_global_kl=stats['last_global_kl'])
            if rank==0:atomic_json(out/f'episodes_{iteration:06d}.json',metrics)
            if iteration%cfg['save_every']==0 or iteration==1:save(out/'latest.pt')
            if iteration%cfg['eval_every']==0 and time.time()<cfg['train_deadline_epoch']-120:validate();last_validation=iteration
            if args.stop_after and iteration>=args.stop_after:
                save(out/'latest.pt');event('PAUSED',updates=iteration);dist.destroy_process_group();return
        save(out/'latest.pt')
        if cfg.get('defer_final_test',False):
            event('TRAINING_STOPPED',updates=iteration,checkpoint=str(out/'latest.pt'),final_test='NOT_RUN; separate frozen evaluation required')
            dist.destroy_process_group();return
        if last_validation!=iteration:validate()
        has_best=(out/'best.pt').exists()
        selected=out/'best.pt' if has_best else (out/'latest.pt' if cfg.get('test_latest_if_no_best',False) else Path(baseline_path))
        # All ranks load same frozen selection, no more optimization after test.
        model.load_state_dict(torch.load(selected,weights_only=False,map_location='cpu')['model'])
        base=eval_rows(baseline_model,cfg['test_seed'],cfg['test_episodes']);rows=eval_rows(model,cfg['test_seed'],cfg['test_episodes'])
        delta=np.array([r['virtual_time_s']-b['virtual_time_s'] for r,b in zip(rows,base)])
        if rank==0:atomic_json(out/'final_test.json',dict(checkpoint=str(selected),recommended_checkpoint=str(selected) if has_best else baseline_path,
                  baseline_checkpoint=baseline_path,validation_selected=has_best,selection_used_test=False,baseline=base,student=rows,
                  mean_delta_s=float(delta.mean()),ci95_halfwidth_s=float(1.96*delta.std(ddof=1)/np.sqrt(len(delta)))))
        event('COMPLETE',updates=iteration,checkpoint=str(selected),test_completion_rate=sum(r['completion'] for r in rows)/len(rows),mean_delta_s=float(delta.mean()))
    dist.destroy_process_group()


if __name__=='__main__':main()
