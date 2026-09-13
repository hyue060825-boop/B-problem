"""Frozen final Q4: independent fixed-N strata, matched to the Q3 appendix protocol."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import csv
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from solution.rl.environment import TrainingEnv, model_state
from solution.rl.model import CandidatePolicy
from solution.rl.training import atomic_json

FINAL = ROOT/'runs/q4_baseline_8gpu_1h_20260913/train/best.pt'
FINAL_SHA = 'c8812cedc2a755997dbd431873b3c4229d8411d827937225e34f1b8ac6949ffb'
MODEL = None


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def init_worker(checkpoint):
    global MODEL
    torch.set_num_threads(1)
    MODEL = CandidatePolicy().eval()
    MODEL.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=False)['model'])


def episode(job):
    n, seed = job
    env = TrainingEnv(4, seed, max_macros=400, count=n)
    scenario = asdict(env.session.kernel.scenario)
    scenario_sha = hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest()
    # Last-clear diagnostic is observed after public macros, without modifying policy inputs.
    last_clear = None
    while not env.done:
        started = time.perf_counter()
        state, actions = env.observe()
        tensors = {k: torch.from_numpy(v).unsqueeze(0) for k, v in model_state(state).items()}
        with torch.inference_mode():
            logits, value = MODEL(tensors)
        if not torch.isfinite(logits).all() or not torch.isfinite(value).all():
            raise RuntimeError(f'Nonfinite policy output: N={n}, seed={seed}')
        env.decision_times.append(time.perf_counter()-started)
        before = len(env.session.state.cleared)
        env.step(actions[int(logits.argmax(-1).item())])
        if len(env.session.state.cleared) > before:
            last_clear = env.session.state.virtual_us/1e6
    row = env.metrics()
    row.update(scenario_sha256=scenario_sha,
               directional_sources=sum(s.kind == 'directional' for s in env.session.kernel.scenario.sources),
               last_successful_clear_macro_end_s=last_clear)
    assert row['N'] == n
    return row


def summarize(rows):
    t = np.array([r['virtual_time_s'] for r in rows]); n = np.array([r['N'] for r in rows])
    complete = [r for r in rows if r['completion']]
    per = t/n
    half = float(1.96*per.std(ddof=1)/len(per)**.5) if len(per)>1 else None
    return dict(episodes=len(rows), completed=len(complete), completion_rate=len(complete)/len(rows),
                mean_virtual_s=float(t.mean()), median_virtual_s=float(np.median(t)), p95_virtual_s=float(np.percentile(t,95)),
                min_virtual_s=float(t.min()), max_virtual_s=float(t.max()),
                mean_per_source_s=float(per.mean()), median_per_source_s=float(np.median(per)),
                p95_per_source_s=float(np.percentile(per,95)), std_per_source_s=float(per.std(ddof=1)) if len(per)>1 else None,
                ci95_mean_per_source_s=[float(per.mean()-half),float(per.mean()+half)] if half is not None else None,
                completed_only_mean_per_source_s=float(np.mean([r['virtual_time_s']/r['N'] for r in complete])) if complete else None,
                errors=dict(Counter(r['error'] or 'incomplete' for r in rows if not r['completion'])),
                distributions=dict(Counter(r['profile']['distribution'] for r in rows)),
                fields=dict(Counter(r['profile']['field'] for r in rows)),
                directional_count_distribution=dict(Counter(r['directional_sources'] for r in rows)))


def report(out, rows, manifest):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = {n: sorted([r for r in rows if r['N']==n], key=lambda r:r['seed']) for n in range(10,17)}
    summary = {str(n): summarize(rs) for n,rs in groups.items()}
    for n,rs in groups.items():
        assert len(rs)==manifest['episodes_per_count'] and len({r['seed'] for r in rs})==len(rs)
        atomic_json(out/f'N{n}_samples.json', rs)
    atomic_json(out/'summary.json',summary)
    with (out/'averages.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['N','episodes','completed','completion_rate','mean_virtual_s','mean_per_source_s','median_per_source_s','p95_per_source_s','min_virtual_s','max_virtual_s']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        writer.writerows(dict(N=n,**summary[str(n)]) for n in groups)
    with (out/'samples.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['N','seed','C','completion','virtual_time_s','time_per_clear_s','macro_steps','measures','switches','clear_failures','path_length_m','directional_sources','scenario_sha256','last_successful_clear_macro_end_s','error']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(r for rs in groups.values() for r in rs)
    values={n:np.array([r['virtual_time_s']/n for r in rs if r['completion']]) for n,rs in groups.items()}
    all_values=np.concatenate(list(values.values()))
    if not len(all_values):raise RuntimeError('No completed episodes; cannot make performance distribution')
    bins=np.linspace(0, np.ceil(all_values.max()/100)*100, 51)
    ymax=max(np.histogram(v,bins=bins)[0].max(initial=0) for v in values.values())*1.12
    def draw(ax,n):
        v=values[n];s=summary[str(n)]
        ax.hist(v,bins=bins,color='#0f766e',edgecolor='white',alpha=.86)
        if len(v):ax.axvline(v.mean(),color='#c2410c',lw=1.8,label=f'Mean: {v.mean():.2f} s/source')
        ax.set(xlim=(bins[0],bins[-1]),ylim=(0,ymax),xlabel='Total virtual time / source count (s/source)',ylabel='Scenarios',title=f'Final Q4 c8812ced | N={n} | {s["completed"]}/{s["episodes"]} complete')
        ax.grid(axis='y',alpha=.18);ax.legend()
    # Match the historical Q3 layout: five single plots + one N15/N16 two-panel figure.
    names=[]
    for n in range(10,15):
        fig,ax=plt.subplots(figsize=(9,5),layout='constrained');draw(ax,n);name=f'N{n}_distribution';names.append(name)
        for ext in ('png','pdf'):fig.savefig(out/f'{name}.{ext}',dpi=220)
        plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(15,5),layout='constrained')
    for ax,n in zip(axs,(15,16)):draw(ax,n)
    names.append('N15_16_distribution')
    for ext in ('png','pdf'):fig.savefig(out/f'N15_16_distribution.{ext}',dpi=220)
    plt.close(fig)
    lines=[f'# 最终 Q4：10–16 源各{manifest["episodes_per_count"]}局独立分层测评','',
           f'固定模型：`runs/q4_baseline_8gpu_1h_20260913/train/best.pt`，SHA256 `{FINAL_SHA}`。',
           f'每组 {manifest["episodes_per_count"]} 个独立种子，共 {len(rows)} 局；仅评测，不训练、不据本测试重新选模。',
           '','| 源数 | 完成/样本 | 平均整局T（虚拟秒） | 平均T/N（秒/源） | T/N中位数 | T/N P95 |','|---|---:|---:|---:|---:|---:|']
    for n in groups:
        s=summary[str(n)];lines.append(f'| {n} | {s["completed"]}/{s["episodes"]} | {s["mean_virtual_s"]:.2f} | {s["mean_per_source_s"]:.2f} | {s["median_per_source_s"]:.2f} | {s["p95_per_source_s"]:.2f} |')
    lines+=['','## 协议与解释','',
            '- 时间包含搜索、移动、换频、测量、清除与合法退出前的无源确认。主指标是逐局T/N后取平均，不是首次发现每个源的时刻。完成局T/N=T/C；失败仍保留原始记录并单报，不能将失败局短时间解释为性能改善。',
            '- 场景采用原Q3分层实验的research-v1生成器并固定N，题目改为Q4：定向源数量在1到N−1随机，两种源并存。每组1000局时area/edge/cluster/outward各250；误差场与分布关联，沿用原协议，不能将差异只归因于位置。',
            '- 原Q3参考实验是8cc3父模型，不是5139最终Q3；两题场景与接收规则不同，本次不是Q3/Q4逐局配对优劣检验。',
            '- 源数只传入生成器，不提供给策略。策略仅看公开观测；评测使用greedy argmax、原实时剩余时间特征、400宏动作预算。CPU多进程执行完整参考模拟器，推理每进程单线程。',
            '- 七组用六张主分布图展示：10–14各一张，15/16合一张双子图，与Q3图形组织一致；本次所有子图统一分箱及纵轴。分布图只绘制完整完成局。',
            '- summary中的均值95%区间使用mean±1.96×SE，针对该关联混合研究分布，不是官方成绩区间。样本min/max为随机样本极值，不是专门搜索的理论界。',
            '- last_successful_clear_macro_end_s为成功清除所在宏动作结束时刻的附加诊断，不声称逐请求精确最后清除时刻；本报告主指标仅使用整局T。',
            '- 未将这7000局用于训练或验证选模；种子列表、场景内容哈希、源类型统计与运行时哈希见manifest及逐局数据。保留现实时间特征意味着跨硬件重跑不承诺逐位一致。',
            '', '[统计JSON](summary.json) · [均值CSV](averages.csv) · [逐局CSV](samples.csv) · [实验协议与身份](manifest.json)', '']
    lines += [f'![{name}]({name}.png)\n' for name in names]
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--episodes-per-count',type=int,default=1000)
    p.add_argument('--workers',type=int,default=24);p.add_argument('--seed-base',type=int,default=2100000000)
    a=p.parse_args()
    if not 2 <= a.episodes_per_count <= 100000 or a.workers<1:raise ValueError('Invalid sample count/workers')
    a.output.mkdir(parents=True,exist_ok=False)
    assert sha(FINAL)==FINAL_SHA
    ck=torch.load(FINAL,map_location='cpu',weights_only=False)
    sources={k:v for k,v in ck['provenance']['files'].items() if k.startswith(('solution/','bsim/'))}
    assert len(sources)==44 and all(sha(ROOT/k)==v for k,v in sources.items())
    seeds={str(n):list(range(a.seed_base+n*100000,a.seed_base+n*100000+a.episodes_per_count)) for n in range(10,17)}
    manifest=dict(problem=4,checkpoint=str(FINAL.relative_to(ROOT)),sha256=FINAL_SHA,source_hashes=sources,
                  evaluator_sha256=sha(__file__),episodes_per_count=a.episodes_per_count,seeds=seeds,
                  workers=a.workers,device='cpu',policy='greedy',max_macros=400,
                  remaining_real_time_feature='live per-episode wall clock; original Q3 protocol',
                  metric='mean_i(T_i/N_i); complete-only plot; failures retained',
                  distribution='LOCAL-RESEARCH research-v1-20260911; fixed N, seeded spatial/noise mixture',
                  selection='User-specified frozen final model; no training or checkpoint selection on this test',
                  python=platform.python_version(),torch=torch.__version__,numpy=np.__version__)
    atomic_json(a.output/'manifest.json',manifest)
    jobs=[(n,seed) for n in range(10,17) for seed in seeds[str(n)]]
    started=time.perf_counter();rows=[]
    with (a.output/'samples.jsonl').open('x') as f, ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn'),initializer=init_worker,initargs=(FINAL,)) as pool:
        for row in pool.map(episode,jobs,chunksize=2):
            rows.append(row);f.write(json.dumps(row,allow_nan=False)+'\n')
            if len(rows)%100==0 or len(rows)==len(jobs):
                f.flush();elapsed=time.perf_counter()-started
                status=dict(status='RUNNING',finished=len(rows),total=len(jobs),completed=sum(r['completion'] for r in rows),elapsed_s=elapsed,episodes_per_s=len(rows)/elapsed,remaining_s=(len(jobs)-len(rows))*elapsed/len(rows))
                atomic_json(a.output/'status.json',status);print(json.dumps(status),flush=True)
    assert sha(FINAL)==FINAL_SHA and all(sha(ROOT/k)==v for k,v in sources.items())
    summary=report(a.output,rows,manifest)
    atomic_json(a.output/'verification.json',dict(checkpoint_and_runtime_unchanged=True,unique_seed_count=len({r['seed'] for r in rows}),scene_count=len(rows),counts_match=True,finite_metrics=all(np.isfinite(r['virtual_time_s']) for r in rows),all_completed=all(r['completion'] and r['C']==r['N'] for r in rows)))
    atomic_json(a.output/'status.json',dict(status='COMPLETE',finished=len(rows),total=len(jobs),completed=sum(r['completion'] for r in rows),elapsed_s=time.perf_counter()-started))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
