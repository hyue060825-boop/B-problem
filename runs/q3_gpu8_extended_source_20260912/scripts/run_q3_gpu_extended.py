#!/usr/bin/env python3
"""GPU search -> eight-rank SFT -> timed DDP PPO -> independent paired report."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from solution.rl.training import atomic_json


def report(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    data=json.loads((out/'ppo/final_test.json').read_text())
    base=data['baseline'];rows=data['student']
    assert len(base)==len(rows) and [r['seed'] for r in base]==[r['seed'] for r in rows]
    def summary(rr):
        times=np.asarray([r['virtual_time_s'] for r in rr]);per=[r['time_per_clear_s'] for r in rr if r['C']]
        return dict(episodes=len(rr),completed=sum(r['completion'] for r in rr),completion_rate=sum(r['completion'] for r in rr)/len(rr),
                    mean_virtual_s=float(times.mean()),mean_per_source_s=float(np.mean(per)) if len(per)==len(rr) else None,
                    p95_virtual_s=float(np.percentile(times,95)),errors=[r for r in rr if not r['completion']])
    delta=np.asarray([s['virtual_time_s']-b['virtual_time_s'] for s,b in zip(rows,base)])
    half=1.96*delta.std(ddof=1)/np.sqrt(len(delta))
    result=dict(baseline=summary(base),candidate=summary(rows),mean_delta_s=float(delta.mean()),
                paired_ci95_s=[float(delta.mean()-half),float(delta.mean()+half)],
                faster=sum(d<0 for d in delta).item(),slower=sum(d>0 for d in delta).item(),
                checkpoint=data['checkpoint'],recommended_checkpoint=data['recommended_checkpoint'],
                validation_selected=data['validation_selected'],selection_used_test=False,
                profile='LOCAL-RESEARCH; not official simulator results')
    dest=out/'final_evaluation';dest.mkdir(exist_ok=True)
    atomic_json(dest/'summary.json',result)
    with (dest/'samples.csv').open('w',newline='') as f:
        fields=['model','seed','N','C','completion','virtual_time_s','time_per_clear_s','macro_steps','error']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader()
        for name,rr in [('baseline',base),('candidate',rows)]:writer.writerows(dict(model=name,**r) for r in rr)
    fig,ax=plt.subplots(figsize=(10,6),dpi=160)
    a=[r['time_per_clear_s'] for r in base if r['C']];b=[r['time_per_clear_s'] for r in rows if r['C']]
    bins=np.histogram_bin_edges(a+b,bins=50)
    ax.hist(a,bins=bins,histtype='step',color='#64748b',label='Frozen current-best Q3')
    ax.hist(b,bins=bins,color='#2563eb',alpha=.65,label='GPU-search + DDP candidate')
    ax.set(xlabel='Virtual time / cleared sources (s/source)',ylabel='Scenarios',title=f'Q3 independent comparison: {len(rows)} scenarios')
    ax.legend();fig.tight_layout()
    for ext in ('png','pdf'):fig.savefig(dest/f'per_source_distribution.{ext}')
    plt.close(fig)
    text=f'''# Q3 GPU 搜索后八卡同步训练独立测评

固定旧模型：`{data['baseline_checkpoint']}`。
本轮测试候选：`{data['checkpoint']}`。
验证集预先决定的推荐模型：`{data['recommended_checkpoint']}`。

| 模型 | 完成局数 | 平均每局虚拟秒 | 平均每源虚拟秒 |
|---|---:|---:|---:|
| 冻结当前最佳 Q3 | {result['baseline']['completed']}/{len(base)} | {result['baseline']['mean_virtual_s']:.2f} | {result['baseline']['mean_per_source_s']} |
| 本轮候选 | {result['candidate']['completed']}/{len(rows)} | {result['candidate']['mean_virtual_s']:.2f} | {result['candidate']['mean_per_source_s']} |

配对差值（新减旧）为 {delta.mean():.2f} 秒/局，近似 95% 置信区间为 [{delta.mean()-half:.2f}, {delta.mean()+half:.2f}] 秒。
最终测试没有参与训练或选模。若没有候选通过验证集收益门槛，仍推荐冻结基线，并将 latest 的测评明确作为诊断。
每源时间口径为每局总虚拟时间除以已清除源数后再对局求平均；失败样例保留于数据中并单独记录。研究分布不等同于官方分布。

[逐局数据](samples.csv) · [分布图](per_source_distribution.png) · [汇总](summary.json)
'''
    (dest/'report.md').write_text(text)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--devices',default='0,1,2,3,4,5,6,7');p.add_argument('--smoke',action='store_true')
    p.add_argument('--ppo-seconds',type=int,default=5400);p.add_argument('--report-only',action='store_true')
    a=p.parse_args();out=Path(a.output).resolve()
    if a.report_only:report(out);return
    out.mkdir(parents=True,exist_ok=False);started=time.time();world=len(a.devices.split(','))
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=a.devices,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
             NCCL_P2P_DISABLE='1',NCCL_IB_DISABLE='1',TORCH_NCCL_ASYNC_ERROR_HANDLING='1')
    baseline=out/'baseline.pt';shutil.copy2(a.checkpoint,baseline)
    atomic_json(out/'run_manifest.json',dict(baseline_original=str(Path(a.checkpoint).resolve()),
        baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),world_size=world,devices=a.devices,
        ppo_seconds=a.ppo_seconds,smoke=a.smoke,started_unix=started,source=str(ROOT),
        architecture='one student, synchronous DDP; search uses frozen replicas without optimizers'))
    def event(stage,**kw):
        row=dict(stage=stage,elapsed_s=time.time()-started,**kw);atomic_json(out/'pipeline_status.json',row)
        print(json.dumps(row),flush=True)
    def run(stage,args,distributed=False,timeout=1800):
        event(stage,command=args)
        command=([str(ROOT/'scripts/run_torchrun.sh'),'--standalone','--nnodes=1',f'--nproc-per-node={world}'] if distributed else [sys.executable])+args
        with (out/f'{stage}.log').open('a') as log:
            proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            atomic_json(out/'child.json',dict(stage=stage,pid=proc.pid,command=command))
            try:code=proc.wait(timeout=timeout)
            except BaseException:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                raise
        if code:raise RuntimeError(f'{stage} exited {code}; inspect {out/stage}.log')
    try:
        offset=400000000 if a.smoke else 410000000
        validation=list(range(offset+1000000,offset+1000000+(32 if a.smoke else 512)))
        atomic_json(out/'seeds.json',dict(validation=validation,ppo=[]))
        run('baseline_validation',['scripts/evaluate_q3_joint.py','--baseline',str(baseline),'--output',str(out/'baseline_validation'),
            '--seed',str(validation[0]),'--episodes',str(len(validation)),'--workers','16'])
        base_rows=json.loads((out/'baseline_validation/baseline_episodes.json').read_text())
        rule_rows=json.loads((out/'baseline_validation/rule_episodes.json').read_text())
        if not all(r['completion'] for r in base_rows+rule_rows):raise RuntimeError('baseline/teacher completeness gate failed')
        labels=out/'labels';search=out/'search'
        run('collect',['scripts/q3_gpu_labels.py','collect','--output',str(labels),'--checkpoint',str(baseline),'--seed',str(offset),
                       '--episodes',str(16 if a.smoke else 256),'--states','4','--workers','32'])
        args=['scripts/q3_gpu_search.py','run','--tasks',str(labels/'tasks.pt'),'--checkpoint',str(baseline),
              '--output',str(search),'--devices',','.join(str(i) for i in range(world)),'--mode','tensor','--batch-roots','2']
        if a.smoke:
            run('search_partial',args+['--max-roots','16'])
            reference=list(args);reference[reference.index('--mode')+1]='reference'
            reference[reference.index('--output')+1]=str(out/'search_reference')
            run('search_reference',reference+['--max-roots','16','--cpu-workers','8'])
            checked=0
            for path in (out/'search_reference').glob('*.json'):
                old=json.loads(path.read_text())
                if 'root_id' not in old:continue
                new=json.loads((search/path.name).read_text())
                if old['accepted']!=new['accepted'] or old.get('recommended')!=new.get('recommended'):
                    raise RuntimeError('CPU/GPU search recommendation mismatch')
                old_branches={tuple(r['branch_id']):r for r in old['full_branches']}
                new_branches={tuple(r['branch_id']):r for r in new['full_branches']}
                if old_branches.keys()!=new_branches.keys():raise RuntimeError('CPU/GPU branch IDs mismatch')
                for identity,b in old_branches.items():
                    c=new_branches[identity]
                    if any(b[k]!=c[k] for k in ('completion','cost_s','reason','trace')):
                        raise RuntimeError(f'CPU/GPU branch trajectory mismatch: {identity}')
                checked+=1
            if checked!=16:raise RuntimeError('missing CPU/GPU comparison roots')
            atomic_json(out/'gpu_reference_parity.json',dict(status='PASS',roots=checked,full_macro_trajectories_equal=True))
        run('search',args,timeout=3600)
        search_summary=json.loads((search/'summary.json').read_text())
        if search_summary['status']!='COMPLETE':raise RuntimeError('search tasks incomplete')
        run('export',['scripts/q3_gpu_labels.py','export','--output',str(labels),'--checkpoint',str(baseline),'--search-dir',str(search)])
        cfg=dict(run_id=out.name,output=str(out),world_size=world,rng_seed=190903,workers_per_rank=2 if a.smoke else 4,
                 sft_epochs=2 if a.smoke else 8,sft_eval_every=1 if a.smoke else 2,sft_lr=1e-5,ppo_lr=1e-5,
                 per_rank_batch_size=2 if a.smoke else 32,grad_accum_steps=2 if a.smoke else 1,
                 stability_kl=.5,max_macros=400,audit_every=1)
        atomic_json(out/'sft_config.json',cfg)
        sft=['scripts/train_q3_joint.py','--config',str(out/'sft_config.json'),'--stage','sft_gpu','--resume',str(baseline),'--data',str(labels/'data.pt')]
        if a.smoke:
            run('sft_partial',sft+['--stop-after','1'],True)
            sft[sft.index('--resume')+1]=str(out/'latest.pt')
        run('sft',sft,True)
        candidates=[]
        for path in (out/'sft_gpu').glob('validation_*.json'):
            data=json.loads(path.read_text());cmp=data['comparison']
            if cmp['eligible']:candidates.append((cmp['mean_delta_s'],path.name.replace('validation_','checkpoint_').replace('.json','.pt')))
        if not candidates:raise RuntimeError('no complete SFT candidate')
        score,name=min(candidates);initial=out/'sft_gpu'/name
        atomic_json(out/'ppo_initial_selection.json',dict(checkpoint=str(initial),mean_validation_delta_s=score,used_test=False,
            note='lowest validation mean among complete SFT snapshots; baseline remains frozen for robust deployment selection'))
        cfg=dict(problem=3,world_size=world,checkpoint=str(initial),baseline_checkpoint=str(baseline),output=str(out/'ppo'),
                 seed=offset+2000000,validation_seed=validation[0],test_seed=offset+9000000,
                 wall_seconds=120 if a.smoke else a.ppo_seconds,max_updates=2 if a.smoke else 20000,
                 episodes_per_update=16 if a.smoke else 256,validation_episodes=len(validation),test_episodes=32 if a.smoke else 3000,
                 workers_per_rank=2 if a.smoke else 4,lr=1e-5,ppo_epochs=2,per_rank_batch_size=32 if a.smoke else 64,
                 grad_accum_steps=1,entropy=.001,target_kl=.02,max_macros=400,save_every=1 if a.smoke else 10,
                 eval_every=1 if a.smoke else 100,restore_initial_optimizer=True,validate_initial=True,test_latest_if_no_best=True)
        assert cfg['seed']+cfg['max_updates']*cfg['episodes_per_update']<=cfg['test_seed']
        atomic_json(out/'ppo_config.json',cfg)
        ppo=['scripts/train_budget_ddp.py','--config',str(out/'ppo_config.json')]
        if a.smoke:
            run('ppo_partial',ppo+['--stop-after','1'],True)
            ppo+=['--resume',str(out/'ppo/latest.pt')]
        run('ppo_train',ppo,True,timeout=cfg['wall_seconds']+1800)
        result=report(out)
        event('COMPLETE',final_evaluation=str(out/'final_evaluation/summary.json'),mean_delta_s=result['mean_delta_s'],
              completion_rate=result['candidate']['completion_rate'],recommended_checkpoint=result['recommended_checkpoint'])
    except BaseException as exc:
        event('FAILED',error=f'{type(exc).__name__}: {exc}');raise


if __name__=='__main__':main()
