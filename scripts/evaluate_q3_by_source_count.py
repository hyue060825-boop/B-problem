#!/usr/bin/env python3
"""Evaluate a frozen Q3 policy with its matching source, stratified by N."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    tmp.replace(path)


def init_worker(checkpoint, source):
    global MODEL, ENV, MODEL_STATE
    torch.set_num_threads(1)
    sys.path.insert(0, str(Path(source).resolve()))
    from solution.rl.environment import TrainingEnv, model_state, FEATURE_VERSION
    from solution.rl.model import CandidatePolicy
    from bsim.research import PROFILE_VERSION
    data = torch.load(checkpoint, map_location='cpu', weights_only=False)
    recorded = data['provenance']['files']
    # Check every archived strategy/simulator file, rather than bypassing a
    # version error or truncating the current feature schema to fit old weights.
    for name, digest in recorded.items():
        if name.startswith(('solution/', 'bsim/')) and sha(Path(source)/name) != digest:
            raise ValueError(f'checkpoint/source mismatch: {name}')
    if data['features'] != FEATURE_VERSION or data['profile'] != PROFILE_VERSION:
        raise ValueError('checkpoint schema/profile mismatch')
    MODEL = CandidatePolicy().eval()
    MODEL.load_state_dict(data['model'], strict=True)
    ENV, MODEL_STATE = TrainingEnv, model_state


def episode(job):
    n, seed = job
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    # N is supplied only to the scenario generator, never to the policy.
    env = ENV(3, seed, count=n, max_macros=400)
    while not env.done:
        started = time.perf_counter()
        state, actions = env.observe()
        tensors = {k: torch.from_numpy(v).unsqueeze(0) for k, v in MODEL_STATE(state).items()}
        with torch.inference_mode():
            logits, _ = MODEL(tensors)
        if not torch.isfinite(logits).all():
            raise FloatingPointError(f'nonfinite policy logits, seed={seed}')
        env.decision_times.append(time.perf_counter()-started)
        env.step(actions[int(logits.argmax(-1))])
    row = env.metrics()
    if n is not None and row['N'] != n:
        raise ValueError('generator did not honor requested source count')
    return row


def summarize(rows):
    times = np.array([r['virtual_time_s'] for r in rows])
    completed = [r for r in rows if r['completion']]
    per = [r['time_per_clear_s'] for r in rows if r['C'] > 0]
    return dict(episodes=len(rows), completed=len(completed),
                completion_rate=len(completed)/len(rows),
                mean_virtual_s=float(times.mean()), median_virtual_s=float(np.median(times)),
                p95_virtual_s=float(np.percentile(times,95)), p99_virtual_s=float(np.percentile(times,99)),
                mean_per_source_s=float(np.mean(per)) if len(per)==len(rows) else None,
                mean_completed_per_source_s=float(np.mean([r['time_per_clear_s'] for r in completed])) if completed else None,
                p95_per_source_s=float(np.percentile(per,95)) if per else None,
                mean_path_m=float(np.mean([r['path_length_m'] for r in rows])),
                errors=dict(Counter(r['error'] or 'incomplete' for r in rows if not r['completion'])),
                distributions=dict(Counter(r['profile']['distribution'] for r in rows)),
                fields=dict(Counter(r['profile']['field'] for r in rows)))


def plots(out, grouped):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    vals = {n: [r['time_per_clear_s'] for r in rr if r['completion']] for n,rr in grouped.items()}
    bins = np.histogram_bin_edges([v for vs in vals.values() for v in vs], bins=40)
    max_height = max(np.histogram(vs,bins)[0].max() for vs in vals.values())
    # Seven groups in exactly six figures: the last has two separate panels.
    figures = []
    for counts in ((10,), (11,), (12,), (13,), (14,), (15,16)):
        fig, axes = plt.subplots(1,len(counts),figsize=(7*len(counts),4.5),dpi=180,squeeze=False)
        for ax,n in zip(axes[0],counts):
            v = vals[n]
            ax.hist(v,bins=bins,color='#2563eb',alpha=.82,edgecolor='white',linewidth=.3)
            if v:
                ax.axvline(np.mean(v),color='#b91c1c',label=f'Mean {np.mean(v):.2f} s/source')
                ax.legend()
            ax.set(xlabel='Total virtual time / sources (s/source)',ylabel='Scenarios',
                   title=f'Q3 N={n} | completed {len(v)}/{len(grouped[n])}',ylim=(0,max_height*1.15))
            ax.grid(axis='y',alpha=.2)
        fig.suptitle('LOCAL-RESEARCH | frozen final Q3 best | completed episodes',fontsize=10)
        fig.tight_layout()
        name='N'+'_'.join(map(str,counts))+'_distribution'
        for ext in ('png','pdf'):
            fig.savefig(out/f'{name}.{ext}')
        plt.close(fig)
        figures.append(name)
    return figures


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--episodes',type=int,default=1000)
    parser.add_argument('--workers',type=int,default=24)
    parser.add_argument('--seed',type=int,default=710000000)
    args=parser.parse_args()
    if not 1 <= args.episodes <= 10000 or args.workers < 1:
        raise ValueError('invalid episode/worker count')
    out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    init_worker(args.checkpoint,args.source)  # Fail before spawning workers.
    checkpoint_hash=sha(args.checkpoint)
    source_hashes={str(p.relative_to(args.source)):sha(p) for p in Path(args.source).rglob('*.py')}
    manifest=dict(checkpoint=str(Path(args.checkpoint).resolve()),sha256=checkpoint_hash,
                  source=str(Path(args.source).resolve()),source_hashes=source_hashes,
                  evaluator_sha256=sha(__file__),workers=args.workers,device='cpu',policy='greedy',
                  max_macros=400,remaining_real_time_feature='live per-episode wall clock; original evaluator behavior',
                  metric='mean_i(T_i/C_i); completion and failures retained; T/N equals T/C only for full completion',
                  distribution='LOCAL-RESEARCH research-v1-20260911; original seeded spatial/noise mixture, fixed N',
                  seeds={str(n):list(range(args.seed+(n-10)*10000,args.seed+(n-10)*10000+args.episodes)) for n in range(10,17)})
    save(out/'manifest.json',manifest)
    jobs=[(n,s) for n in range(10,17) for s in manifest['seeds'][str(n)]]
    grouped={n:[] for n in range(10,17)}
    started=time.perf_counter()
    with (out/'samples.jsonl').open('x') as stream, ProcessPoolExecutor(
            args.workers,mp_context=mp.get_context('spawn'),initializer=init_worker,
            initargs=(args.checkpoint,args.source)) as pool:
        for index,row in enumerate(pool.map(episode,jobs,chunksize=4),1):
            grouped[row['N']].append(row)
            stream.write(json.dumps(row,allow_nan=False)+'\n')
            if index%100==0 or index==len(jobs):
                stream.flush()
                elapsed=time.perf_counter()-started
                status=dict(status='RUNNING',finished=index,total=len(jobs),elapsed_s=elapsed,
                            eta_s=(len(jobs)-index)*elapsed/index)
                save(out/'status.json',status)
                print(json.dumps(status),flush=True)
    for n,rows in grouped.items():
        assert len(rows)==args.episodes and len({r['seed'] for r in rows})==args.episodes
        save(out/f'N{n}_samples.json',rows)
    report={str(n):summarize(rows) for n,rows in grouped.items()}
    figures=plots(out,grouped)
    with (out/'samples.csv').open('x',newline='') as f:
        fields=['N','seed','C','completion','virtual_time_s','time_per_clear_s','path_length_m','macro_steps','error']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        for rows in grouped.values(): writer.writerows(rows)
    with (out/'averages.csv').open('x',newline='') as f:
        fields=['N','episodes','completed','mean_virtual_s','mean_per_source_s','p95_per_source_s']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(dict(N=n,**values) for n,values in report.items())
    if sha(args.checkpoint)!=checkpoint_hash or any(sha(Path(args.source)/p)!=h for p,h in source_hashes.items()):
        raise RuntimeError('checkpoint/source changed during evaluation')
    save(out/'summary.json',dict(checkpoint=manifest['checkpoint'],sha256=checkpoint_hash,counts=report,figures=figures))
    text=['# Q3 最终 best：按干扰源数量独立测评','',
          '使用图片中 3276.62 秒/局模型及其训练时配套代码；每组使用独立 seed，源数只传给场景生成器。',
          '这是 LOCAL-RESEARCH 结果，不是官方成绩。空间/误差分布沿用原生成器的关联混合。',
          f'Checkpoint：`{manifest["checkpoint"]}`；SHA256：`{checkpoint_hash}`。','',
          '| 源数 | 完成/样本 | 平均整局秒 | 平均每源秒 | P95每源秒 |',
          '|---|---:|---:|---:|---:|']
    for n,r in report.items():
        text.append(f'| {n} | {r["completed"]}/{r["episodes"]} | {r["mean_virtual_s"]:.2f} | {r["mean_per_source_s"]:.2f} | {r["p95_per_source_s"]:.2f} |')
    text+=['','每源均值为逐局总虚拟时间（包括搜索、测量、移动、清除、退出）除以已清除数后取平均。失败未删除；分布图仅展示完整完成局。',
           '10–16 源共七组，以六张图展示：前五张分别为10–14源，第六张为15和16源两个独立子图。所有图使用相同分箱和纵轴。','']
    for name in figures: text.append(f'![{name}]({name}.png)')
    (out/'report.md').write_text('\n'.join(text)+'\n')
    save(out/'status.json',dict(status='COMPLETE',finished=len(jobs),total=len(jobs),elapsed_s=time.perf_counter()-started))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
