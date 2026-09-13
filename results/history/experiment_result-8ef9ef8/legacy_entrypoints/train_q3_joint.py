#!/usr/bin/env python3
"""One Q3 checkpoint lineage: resumable four-rank weighted SFT and PPO."""
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

import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.rl.distributed import audit_sync
from solution.rl.environment import FEATURE_VERSION,features,model_state
from solution.control.controller import Controller
from solution.rl.model import CandidatePolicy
from solution.rl.joint_updates import joint_update,prepare_ppo
from solution.rl.training import atomic_json,provenance,verify_checkpoint_code,collect,init_worker
from solution.search.belief import CANDIDATE_VERSION
from solution.search.collection import evaluate_policy_episode
from bsim.research import PROFILE_VERSION
from evaluate_q3_joint import summary,compare


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--stage',required=True)
    ap.add_argument('--resume',required=True);ap.add_argument('--data',action='append',default=[])
    ap.add_argument('--stop-after',type=int);a=ap.parse_args();cfg=json.loads(Path(a.config).read_text())
    torch.set_num_threads(1);local=int(os.environ['LOCAL_RANK']);torch.cuda.set_device(local)
    device=torch.device('cuda',local);dist.init_process_group('nccl',timeout=timedelta(minutes=15))
    rank=dist.get_rank();world=dist.get_world_size()
    if world!=cfg['world_size']:raise ValueError('world size does not match config')
    out=Path(cfg['output']);stage_dir=out/a.stage;stage_dir.mkdir(parents=True,exist_ok=True)
    seeds=json.loads((out/'seeds.json').read_text());resume=Path(a.resume)
    data=torch.load(resume,map_location='cpu',weights_only=False);verify_checkpoint_code(data)
    parent_hash=hashlib.sha256(resume.read_bytes()).hexdigest()
    if data.get('candidate_version',CANDIDATE_VERSION)!=CANDIDATE_VERSION:raise ValueError('candidate version mismatch')
    random.seed(cfg['rng_seed']+rank);np.random.seed(cfg['rng_seed']+rank);torch.manual_seed(cfg['rng_seed'])
    model=CandidatePolicy().to(device);model.load_state_dict(data['model']);ddp=DDP(model,device_ids=[local])
    is_ppo=a.stage.startswith('ppo');lr=cfg['ppo_lr'] if is_ppo else cfg['sft_lr']
    opt=torch.optim.Adam(model.parameters(),lr=lr)
    if data.get('joint_run_id')==cfg['run_id']:
        opt.load_state_dict(data['optimizer'])
        if 'rank_rng' in data:
            rng=data['rank_rng'][rank];random.setstate(rng['python']);np.random.set_state(rng['numpy']);torch.set_rng_state(rng['torch']);torch.cuda.set_rng_state(rng['cuda'],device)
    for group in opt.param_groups:group['lr']=lr
    offset=int(data.get('global_update',0));continuing=data.get('stage')==a.stage
    stage_step=int(data.get('stage_step',0)) if continuing else 0
    fingerprint=provenance();started=time.perf_counter();best_delta=float(data.get('best_delta',0.))
    def event(kind,**kwargs):
        if rank==0:
            if 'elapsed_s' in kwargs:kwargs={**kwargs,'update_elapsed_s':kwargs['elapsed_s']};kwargs.pop('elapsed_s',None)
            row=dict(kind=kind,stage=a.stage,run_id=cfg['run_id'],elapsed_s=time.perf_counter()-started,**kwargs)
            with (stage_dir/'metrics.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
            atomic_json(stage_dir/'status.json',row);print(json.dumps(row,allow_nan=False),flush=True)
    def checkpoint(path,step):
        rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state(device))
        gathered=[None]*world;dist.all_gather_object(gathered,rng)
        digest=audit_sync(model,opt)
        if rank==0:
            if provenance()!=fingerprint:raise RuntimeError('training source changed; stop')
            d=dict(model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),
                   config={**cfg,'problem':3},features=FEATURE_VERSION,profile=PROFILE_VERSION,provenance=fingerprint,
                   candidate_version=CANDIDATE_VERSION,joint_run_id=cfg['run_id'],stage=a.stage,stage_step=step,
                   global_update=offset,update=offset-1,rank_rng=gathered,best_delta=best_delta,parent=str(resume),
                   parent_sha256=parent_hash,state_sha256=digest)
            tmp=path.with_suffix('.tmp');torch.save(d,tmp);tmp.replace(path)
        dist.barrier()
    initial=audit_sync(model,opt)
    # All ranks must also agree on logits for the same public feature tensors.
    public_controller=Controller(3);public_controller.remaining_real_s=1200.
    fixture={k:torch.from_numpy(v).unsqueeze(0).to(device)
             for k,v in model_state(features(public_controller,public_controller.legal_actions())).items()}
    with torch.no_grad():logits,_=model(fixture)
    logit_rows=[torch.empty_like(logits) for _ in range(world)];dist.all_gather(logit_rows,logits)
    max_diff=max(float((x-logits).abs().max()) for x in logit_rows)
    if max_diff>1e-6:raise RuntimeError('rank logits mismatch')
    event('INIT',backend=dist.get_backend(),world_size=world,physical_gpus=os.environ.get('CUDA_VISIBLE_DEVICES'),
          resumed_from=str(resume),global_update=offset,stage_step=stage_step,state_sha256=initial,
          logits_max_abs_diff=max_diff,logits_fixture='Q3 empty public history',
          rank_device_map=[dict(rank=i,logical_device=i,physical_device=os.environ.get('CUDA_VISIBLE_DEVICES','').split(',')[i]) for i in range(world)],
          optimizer_restored=data.get('joint_run_id')==cfg['run_id'])
    checkpoint(stage_dir/f'initial_{stage_step:04d}.pt',stage_step)
    baseline=json.loads((out/'baseline_validation/baseline_episodes.json').read_text())
    with ProcessPoolExecutor(cfg['workers_per_rank'],mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
        def validate(step):
            nonlocal best_delta
            val_seeds=seeds['validation'];subset=val_seeds[rank::world]
            weights={k:v.detach().cpu() for k,v in model.state_dict().items()}
            local_rows=list(pool.map(evaluate_policy_episode,[(s,weights,cfg['max_macros'],None) for s in subset]))
            rows=[None]*world;dist.all_gather_object(rows,local_rows);rows=sorted([r for part in rows for r in part],key=lambda r:r['seed'])
            comparison=compare(baseline,rows);eligible=comparison['robust_gain'] and summary(rows)['decision_p95_s']<=max(.02,2*summary(baseline)['decision_p95_s'])
            event('VALIDATION',stage_step=step,global_update=offset,**comparison,selection_pass_with_latency=eligible,summary=summary(rows))
            if rank==0:atomic_json(stage_dir/f'validation_{step:04d}.json',dict(rows=rows,comparison=comparison))
            checkpoint(stage_dir/f'checkpoint_{step:04d}.pt',step)
            if eligible and comparison['mean_delta_s']<best_delta:
                best_delta=comparison['mean_delta_s'];checkpoint(out/'best.pt',step)
            return comparison
        if not is_ppo:
            if not a.data:raise ValueError('SFT needs search labels')
            rows=[]
            for path in a.data:rows.extend(torch.load(path,map_location='cpu',weights_only=False))
            if not any(r.get('kind')=='search' for r in rows):raise ValueError('no search labels; refuse relabelled rule BC')
            rows=rows[rank::world];epochs=cfg['sft_epochs']
            for epoch in range(stage_step,epochs):
                # Keep canonical dataset order across epoch boundaries so an
                # RNG-restored restart sees exactly the same shuffle input.
                stats=joint_update(ddp,opt,list(rows),device,'SFT',1,cfg['per_rank_batch_size'],cfg['grad_accum_steps'],
                                   stability_kl=cfg['stability_kl'],audit_every=cfg.get('audit_every',1))
                offset+=stats['optimizer_steps'];event('SFT',epoch=epoch+1,global_update=offset,**stats)
                checkpoint(out/'latest.pt',epoch+1)
                if (epoch+1)%cfg['sft_eval_every']==0 or epoch+1==epochs:validate(epoch+1)
                if a.stop_after and epoch+1>=a.stop_after:
                    event('PAUSED',global_update=offset,stage_step=epoch+1);dist.destroy_process_group();return
            checkpoint(out/f'{a.stage}.pt',epochs)
        else:
            n=cfg['global_episodes_per_update'];updates=cfg['ppo_updates']
            for index in range(stage_step,updates):
                policy_digest=audit_sync(model,opt);t=time.perf_counter()
                selected=seeds['ppo'][index*n:(index+1)*n];selected=selected[rank::world]
                episodes=collect(pool,3,selected,model,'sample',cfg['max_macros']);sample_s=time.perf_counter()-t
                versions={policy_digest};local_metrics=[m for _,m in episodes]
                gathered=[None]*world;dist.all_gather_object(gathered,local_metrics);metrics=[m for part in gathered for m in part]
                if rank==0:atomic_json(stage_dir/f'episodes_{index+1:04d}.json',dict(policy_sha256=policy_digest,episodes=metrics))
                if any(m['error'] not in (None,'macro_budget','virtual_timeout') for m in metrics):raise RuntimeError('PPO invariant failure')
                rows,adv=prepare_ppo(episodes,device)
                stats=joint_update(ddp,opt,rows,device,'PPO',cfg['ppo_epochs'],cfg['per_rank_batch_size'],cfg['grad_accum_steps'],
                                   entropy=cfg['entropy'],target_kl=cfg['target_kl'],audit_every=cfg.get('audit_every',1))
                offset+=stats['optimizer_steps'];event('PPO',ppo_update=index+1,global_update=offset,behavior_policy_sha256=policy_digest,
                        sample_s=sample_s,global_episodes=len(metrics),completion_rate=sum(m['completion'] for m in metrics)/len(metrics),
                        macros=sum(m['macro_steps'] for m in metrics),advantage=adv,**stats)
                checkpoint(out/'latest.pt',index+1)
                if (index+1)%cfg['ppo_eval_every']==0 or index+1==updates:validate(index+1)
                if a.stop_after and index+1>=a.stop_after:
                    event('PAUSED',global_update=offset,stage_step=index+1);dist.destroy_process_group();return
            checkpoint(out/f'{a.stage}.pt',updates)
    event('COMPLETE',global_update=offset);dist.destroy_process_group()


if __name__=='__main__':main()
