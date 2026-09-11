#!/usr/bin/env python3
"""Synchronous multi-GPU research training with one DDP model per GPU."""
import argparse, json, os, random, time
from pathlib import Path
import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

ROOT=Path(__file__).resolve().parents[1]
import sys; sys.path.insert(0,str(ROOT))
from solution.rl.model import CandidatePolicy
from solution.rl.training import (collect, summarize, bc_update, ppo_update,
                                  save_checkpoint, load_checkpoint, paired_evaluation)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); a=ap.parse_args()
    cfg=json.loads(Path(a.config).read_text())
    if cfg.get('profile')!='compatible_research' or not cfg.get('authorized'):
        raise SystemExit('BLOCKED: compatible_research authorization is required')
    if not torch.cuda.is_available(): raise SystemExit('CUDA is required for DDP training')
    dist.init_process_group(backend='nccl')
    rank=dist.get_rank(); world=dist.get_world_size(); local=int(os.environ.get('LOCAL_RANK',rank))
    torch.cuda.set_device(local); device=torch.device('cuda',local)
    seed=int(cfg['seed'])+rank; random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    out=Path(cfg['output']); out.mkdir(parents=True,exist_ok=True)
    # BC uses only actor logits while PPO also trains the critic, so some
    # parameters are intentionally unused during the BC phase.
    model=DDP(CandidatePolicy().to(device),device_ids=[local],output_device=local,
              find_unused_parameters=True)
    opt=torch.optim.Adam(model.parameters(),lr=cfg.get('lr',3e-4))
    started=time.perf_counter(); updates=int(cfg.get('ppo_updates',256)); global_eps=int(cfg.get('episodes_per_update',64))
    local_eps=max(1,global_eps//world)
    # BC uses disjoint teacher episodes on each rank, then synchronizes updates.
    base=collect(None,int(cfg['problem']),range(int(cfg['seed'])+rank*100000, int(cfg['seed'])+rank*100000+int(cfg.get('bc_episodes',128))))
    rows=[r for ep,_ in base for r in ep]
    with model.join():
        bc=bc_update(model,opt,rows,device,cfg.get('bc_epochs',6),cfg.get('batch_size',256))
    dist.barrier()
    if rank==0:
        (out/'config.json').write_text(json.dumps({**cfg,'ddp_world_size':world},ensure_ascii=False,indent=2))
        print(json.dumps({'stage':'DDP_INIT','world_size':world,'device_count':torch.cuda.device_count(),'local_episodes':local_eps},ensure_ascii=False),flush=True)
        print(json.dumps({'stage':'BC','elapsed_s':time.perf_counter()-started,**bc},ensure_ascii=False),flush=True)
    best=float('inf')
    for idx in range(updates):
        t=time.perf_counter()
        start=int(cfg['seed'])+200000+idx*global_eps+rank*10000000
        episodes=collect(None,int(cfg['problem']),range(start,start+local_eps),model.module,'sample',cfg.get('max_macros',400))
        # Episode lengths differ by random scene, so ranks can have different
        # numbers of mini-batches. DDP.join() shadow-collectives keep shorter
        # ranks synchronized until the longest rank finishes.
        with model.join():
            stats=ppo_update(model,opt,episodes,device,cfg.get('ppo_epochs',4),cfg.get('batch_size',256),.01)
        local_n=torch.tensor([len(episodes),sum(int(m['completion']) for _,m in episodes),sum(len(ep) for ep,_ in episodes)],device=device,dtype=torch.long)
        dist.all_reduce(local_n,op=dist.ReduceOp.SUM)
        elapsed=time.perf_counter()-t; dist.barrier()
        if rank==0:
            completion=float(local_n[1].item()/max(1,local_n[0].item()))
            eta=elapsed*(updates-idx-1)
            event={'stage':'DDP_PPO','update':idx+1,'total_updates':updates,'world_size':world,'global_episodes':int(local_n[0]),'completion_rate':completion,'macros':int(local_n[2]),'macros_per_s':float(local_n[2].item()/max(elapsed,1e-9)),'eta_s':eta,**stats}
            print(json.dumps(event,ensure_ascii=False),flush=True)
            with (out/'metrics.jsonl').open('a') as fh:
                fh.write(json.dumps(event,ensure_ascii=False)+'\n')
            save_checkpoint(out/'latest.pt',model.module,opt,cfg,'DDP_PPO',idx,stats,{'world_size':world})
        dist.barrier()
    if rank==0:
        # Evaluate the synchronized rank-0 weights on fresh seeds.
        val=paired_evaluation(None,int(cfg['problem']),range(int(cfg['seed'])+900000,int(cfg['seed'])+900016),model.module)
        (out/'validation_final.json').write_text(json.dumps(val,ensure_ascii=False,indent=2))
        if val['selection_pass']:
            save_checkpoint(out/'best.pt',model.module,opt,cfg,'DDP_PPO',updates-1,val,{'world_size':world})
        print(json.dumps({'stage':'DDP_COMPLETE','updates':updates,'selection_pass':val['selection_pass'],'paired_delta_s':val['mean_paired_delta_s'],'checkpoint':str(out/'latest.pt')},ensure_ascii=False),flush=True)
    dist.barrier(); dist.destroy_process_group()

if __name__=='__main__': main()
