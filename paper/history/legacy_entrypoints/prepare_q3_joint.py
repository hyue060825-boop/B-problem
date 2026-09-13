#!/usr/bin/env python3
"""Freeze the selected old Q3 model and persist a disjoint experiment ledger."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.rl.training import atomic_json,provenance
from solution.search.belief import CANDIDATE_VERSION


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='runs/q3_joint_20260912');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    source=Path('runs/large_20260911/q3_ext_gpu2/best.pt')
    if (out/'baseline.pt').exists():raise ValueError('baseline already frozen; do not overwrite')
    # Historical numeric seed references and conservative config envelopes.
    historical=set();envelopes=[];scanned=0
    def scan(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in ('seed','seed_start','seed_end_exclusive','start') and type(v)==int:historical.add(v)
                if isinstance(v,(dict,list)):scan(v)
        elif isinstance(value,list):
            for v in value:
                if isinstance(v,(dict,list)):scan(v)
    for path in Path('runs').rglob('*.json'):
        if out in path.parents:continue
        try:d=json.loads(path.read_text())
        except (ValueError,UnicodeError):continue
        scan(d);scanned+=1
        if 'config' in path.name and isinstance(d,dict) and type(d.get('seed'))==int:
            envelopes.append((str(path),d['seed'],d['seed']+5000000))
    seeds=dict(functional=list(range(100000000,100000016)),labels_round1=list(range(110000000,110000500)),
               labels_round2=list(range(110010000,110010500)),validation=list(range(120000000,120000128)),
               teacher_validation=list(range(120000000,120000128)),ppo=list(range(125000000,125004096)),
               test=list(range(130000000,130000512)))
    primary=[seeds[k] for k in ('functional','labels_round1','labels_round2','validation','ppo','test')]
    flat=[s for group in primary for s in group]
    assert len(flat)==len(set(flat)) and not set(flat)&historical
    assert not any(lo<=s<hi for _,lo,hi in envelopes for s in flat)
    atomic_json(out/'seeds.json',seeds)
    atomic_json(out/'seed_audit.json',dict(files_scanned=scanned,historical_numeric_references=len(historical),
                                         conservative_config_envelopes=envelopes,disjoint=True,
                                         teacher_validation_is_validation_subset=True))
    original=out/'baseline_original.pt';shutil.copy2(source,original)
    d=torch.load(source,map_location='cpu',weights_only=False);old_provenance=d['provenance']
    current=provenance();d.update(provenance=current,candidate_version=CANDIDATE_VERSION)
    d['baseline_revalidation']=dict(original_checkpoint=str(source),original_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                                    original_provenance=old_provenance,validation='baseline_validation/summary.json',
                                    note='weights unchanged; explicit current-controller revalidation; optimizer will reset once')
    torch.save(d,out/'baseline.pt')
    cfg=dict(run_id='q3-search-joint-20260912',output=str(out),world_size=4,rng_seed=190001,
             per_rank_batch_size=64,grad_accum_steps=2,global_batch_size=512,workers_per_rank=4,
             sft_epochs=8,sft_eval_every=2,sft_lr=1e-5,stability_kl=.5,ppo_lr=3e-5,
             global_episodes_per_update=64,ppo_updates=64,ppo_epochs=2,ppo_eval_every=16,
             entropy=.001,target_kl=.03,max_macros=400,audit_every=1,search_workers=32,
             collection_stage_seconds=2400,
             collection=dict(states_per_episode=8,max_macros=400,episode_search_seconds=240,teacher_salt=1701,
                             search=dict(worlds=8,candidate_limit=6,state_seconds=30.,sampler_seconds=10.,
                                         max_expansions=20000,max_macros=400,temperature_s=40.,min_gain_s=5.,confidence_z=1.)))
    atomic_json(out/'config.json',cfg);Path('configs').mkdir(exist_ok=True);atomic_json('configs/q3_joint_4gpu.json',cfg)
    atomic_json(out/'resources.json',dict(gpus=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv'],text=True),
                                         assigned_physical_devices='0,1,2,3',git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                                         branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
                                         baseline_hash=hashlib.sha256((out/'baseline.pt').read_bytes()).hexdigest()))
    print(json.dumps(dict(output=str(out),frozen=True,seed_overlap=False)))


if __name__=='__main__':main()
