"""Freeze/report joint Q3 validation selection; never tune using final tests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from solution.rl.training import atomic_json,provenance,verify_checkpoint_code


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    out=Path(__file__).resolve().parent
    if args.freeze:
        vals=[]
        for stage in ('sft_round1','dagger_round2','sft_round3','ppo'):
            for p in (out/stage).glob('validation_*.json'):
                d=json.loads(p.read_text());step=int(p.stem.split('_')[-1]);checkpoint=p.parent/f'checkpoint_{step:04d}.pt'
                vals.append(dict(stage=stage,step=step,checkpoint=str(checkpoint.relative_to(ROOT)),**d['comparison']))
        sft=[v for v in vals if not v['stage'].startswith('ppo') and v['eligible']]
        ppo=[v for v in vals if v['stage'].startswith('ppo') and v['eligible']]
        selected_sft=min(sft,key=lambda v:v['mean_delta_s']);selected_ppo=min(ppo,key=lambda v:v['mean_delta_s']) if ppo else None
        selected={'distilled':selected_sft,'ppo_candidate':selected_ppo}
        for name,v in selected.items():
            if v:
                dest=out/f'{name}.pt'
                if dest.exists():raise ValueError('frozen test model already exists')
                shutil.copy2(ROOT/v['checkpoint'],dest)
                v['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
        selected['validation_candidates']=vals
        eligible=[(name,v) for name,v in selected.items() if name in ('distilled','ppo_candidate') and v and v['robust_gain']]
        selected['validation_recommended']=min(eligible,key=lambda pair:pair[1]['mean_delta_s'])[0] if eligible else 'baseline'
        selected['test_seeds_used_for_selection']=False
        atomic_json(out/'frozen_selection.json',selected)
        print(json.dumps(selected,indent=2));return
    result=json.loads((out/'final_test/summary.json').read_text());selection=json.loads((out/'frozen_selection.json').read_text())
    base=result['baseline'];candidates=[]
    for name in ('distilled','ppo_candidate'):
        if name in result:
            r=result[name];latency=r['decision_p95_s']<=max(.02,2*base['decision_p95_s'])
            candidates.append(dict(name=name,robust_gain=r['vs_baseline']['robust_gain'],latency_pass=latency,
                                   mean_delta_s=r['vs_baseline']['mean_delta_s']))
    # Report-only deployment gate. No parameter update is allowed after this test.
    frozen_choice=selection['validation_recommended']
    passed=[r for r in candidates if r['name']==frozen_choice and r['robust_gain'] and r['latency_pass']]
    recommended=frozen_choice if passed else 'baseline'
    report=dict(recommended=recommended,candidates=candidates,
                note='frozen variants tested once; selection within stages used validation; no further tuning',
                checkpoint=str((out/f'{recommended}.pt').relative_to(ROOT)),
                checkpoint_sha256=hashlib.sha256((out/f'{recommended}.pt').read_bytes()).hexdigest(),results=result)
    atomic_json(out/'final_recommendation.json',report)
    fig,ax=plt.subplots(figsize=(10,5),dpi=180)
    for name in ('baseline','distilled','ppo_candidate'):
        p=out/f'final_test/{name}_episodes.json'
        if not p.exists():continue
        rows=json.loads(p.read_text());times=np.array([r['time_per_clear_s'] for r in rows])
        ax.hist(times,bins=35,histtype='step',linewidth=1.7,label=f'{name}: mean {times.mean():.2f} s/source')
    ax.set(xlabel='Total virtual time / cleared sources (s/source)',ylabel='Number of scenarios',
           title='Q3 frozen models: 512 independent LOCAL-RESEARCH scenarios')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'test_distribution.png');fig.savefig(out/'test_distribution.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5),dpi=180)
    vals=selection['validation_candidates']
    for stage in sorted({v['stage'] for v in vals}):
        v=sorted([v for v in vals if v['stage']==stage],key=lambda x:x['step'])
        ax.errorbar([x['step'] for x in v],[x['mean_delta_s'] for x in v],yerr=[x['ci95_halfwidth_s'] for x in v],marker='o',label=stage)
    ax.axhline(0,color='gray',linestyle='--');ax.set(xlabel='Stage epoch / PPO update',ylabel='Paired student - frozen baseline (seconds)',title='Q3 validation learning curves, approximate 95% intervals')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'validation_curve.png');plt.close(fig)
    current=provenance()
    with tarfile.open(out/'source_snapshot.tar.gz','w:gz') as archive:
        for name,digest in current['files'].items():
            p=ROOT/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==digest;archive.add(p,arcname=name)
        for name in ('configs/q3_joint_4gpu.json','tests/test_q3_joint.py','tests/test_q3_search.py'):
            archive.add(ROOT/name,arcname=name)
    for name in ('baseline','distilled','ppo_candidate'):
        p=out/f'{name}.pt'
        if p.exists():verify_checkpoint_code(torch.load(p,weights_only=False,map_location='cpu'))
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
