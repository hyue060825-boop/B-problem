#!/usr/bin/env python3
"""Frozen, paired Q4 continuation evaluation; never selects weights on test data."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solution.rl.environment import TrainingEnv, structural_model_state
from solution.rl.model import StructuralCandidatePolicy
from solution.rl.training import atomic_json, load_checkpoint


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def init_worker(parent, candidate):
    global MODELS
    torch.set_num_threads(1)
    MODELS = {}
    for name, path in [('parent', parent), ('candidate', candidate)]:
        model = StructuralCandidatePolicy().eval()
        data = load_checkpoint(path, model)
        for file, digest in data['provenance']['files'].items():
            if file.startswith(('solution/', 'bsim/')) and sha(file) != digest:
                raise ValueError(f'{name} checkpoint/source mismatch: {file}')
        MODELS[name] = model


def episode(name, seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    env = TrainingEnv(4, seed, max_macros=400)
    while not env.done:
        started = time.perf_counter()
        state, actions = env.observe(structural=True)
        tensors = {k: torch.from_numpy(v).unsqueeze(0)
                   for k, v in structural_model_state(state).items()}
        with torch.inference_mode():
            logits, value = MODELS[name](tensors)
        if not torch.isfinite(logits).all() or not torch.isfinite(value).all():
            raise FloatingPointError(f'nonfinite model output: {name}, {seed}')
        env.decision_times.append(time.perf_counter() - started)
        env.step(actions[int(logits.argmax(-1).item())])
    row = env.metrics()
    if row['error'] not in (None, 'macro_budget', 'virtual_timeout'):
        raise RuntimeError(f'unexpected evaluation error: {name}, {seed}, {row}')
    return row


def pair(seed):
    # Alternate execution order to reduce systematic wall-clock/order bias.
    order = ('parent', 'candidate') if seed % 2 == 0 else ('candidate', 'parent')
    rows = {name: episode(name, seed) for name in order}
    assert rows['parent']['profile'] == rows['candidate']['profile']
    assert rows['parent']['N'] == rows['candidate']['N']
    return dict(seed=seed, **rows)


def interval(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return None
    half = 1.96 * values.std(ddof=1) / np.sqrt(len(values)) if len(values) > 1 else 0.
    return dict(n=len(values), mean=float(values.mean()),
                approximate_ci95=[float(values.mean()-half), float(values.mean()+half)])


def summary(rows):
    from evaluate_q3_by_source_count import summarize
    result = {name: summarize([r[name] for r in rows]) for name in ('parent', 'candidate')}
    both = [r for r in rows if r['parent']['completion'] and r['candidate']['completion']]
    result['paired'] = dict(
        completion_rate_delta=interval([int(r['candidate']['completion'])-int(r['parent']['completion']) for r in rows]),
        all_episode_virtual_delta_s=interval([r['candidate']['virtual_time_s']-r['parent']['virtual_time_s'] for r in rows]),
        all_episode_per_clear_delta_s=interval([r['candidate']['time_per_clear_s']-r['parent']['time_per_clear_s'] for r in rows])
            if all(r[n]['C'] > 0 for r in rows for n in ('parent','candidate')) else None,
        both_completed=len(both),
        both_completed_virtual_delta_s=interval([r['candidate']['virtual_time_s']-r['parent']['virtual_time_s'] for r in both]),
        both_completed_per_source_delta_s=interval([r['candidate']['time_per_clear_s']-r['parent']['time_per_clear_s'] for r in both]),
        candidate_only_completed=sum(r['candidate']['completion'] and not r['parent']['completion'] for r in rows),
        parent_only_completed=sum(r['parent']['completion'] and not r['candidate']['completion'] for r in rows),
        both_failed=sum(not r['parent']['completion'] and not r['candidate']['completion'] for r in rows),
        faster_on_both_completed=sum(r['candidate']['virtual_time_s'] < r['parent']['virtual_time_s'] for r in both))
    result['diagnostics'] = {name: {k: float(np.mean([r[name][k] for r in rows])) for k in
        ('path_length_m','measures','switches','clear_failures','macro_steps','probe_failed_clear_count',
         'cover_unknown_measure_count','localize_insertion_count','active_localize_no_signal_count')}
        for name in ('parent','candidate')}
    return result


def artifacts(out, rows, manifest):
    report = summary(rows)
    report['by_source_count'] = {str(n): summary([r for r in rows if r['parent']['N'] == n])
                                for n in sorted({r['parent']['N'] for r in rows})}
    report['by_distribution'] = {d: summary([r for r in rows if r['parent']['profile']['distribution'] == d])
                                 for d in sorted({r['parent']['profile']['distribution'] for r in rows})}
    report['selection_uses_test'] = False
    atomic_json(out/'summary.json', report)
    atomic_json(out/'samples.json', rows)
    fields = ['seed','model','N','C','completion','virtual_time_s','time_per_clear_s','path_length_m','macro_steps','error']
    with (out/'samples.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            for name in ('parent','candidate'):
                writer.writerow(dict(row[name], model=name))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), dpi=160)
    vals = {n: [r[n]['time_per_clear_s'] for r in rows if r[n]['C'] > 0] for n in ('parent','candidate')}
    bins = np.histogram_bin_edges(vals['parent']+vals['candidate'], bins=50)
    for name, color in [('parent','#2563eb'),('candidate','#ea580c')]:
        axes[0].hist(vals[name], bins=bins, alpha=.5, label=f"{name}: mean {np.mean(vals[name]):.2f}", color=color)
    axes[0].set(xlabel='Episode virtual time / cleared sources (s/source)', ylabel='Scenarios', title='All episodes, including incomplete episodes')
    axes[0].legend()
    both = [r for r in rows if r['parent']['completion'] and r['candidate']['completion']]
    axes[1].hist([r['candidate']['time_per_clear_s']-r['parent']['time_per_clear_s'] for r in both], bins=50, color='#64748b')
    axes[1].axvline(0, color='black', linestyle='--')
    axes[1].set(xlabel='Candidate minus parent (s/source); negative = faster', ylabel='Paired scenarios', title=f'Both completed: {len(both)}/{len(rows)}')
    fig.suptitle('Q4 | LOCAL-RESEARCH | paired frozen checkpoints')
    fig.tight_layout()
    for ext in ('png','pdf'):
        fig.savefig(out/f'paired_distribution.{ext}')
    plt.close(fig)
    p, c = report['parent'], report['candidate']
    delta = report['paired']['all_episode_virtual_delta_s']
    lines = ['# Q4 八卡 30 分钟续训：独立配对测评', '',
        f"固定 {len(rows)} 个新样例，seed {manifest['seed_start']}–{manifest['seed_start']+len(rows)-1}；每个模型各运行一次。",
        '研究模拟器随机分布，10–16 源；非官方模拟器成绩。固定 greedy 策略和 400 宏动作预算。', '',
        f"续训前模型：`{manifest['parent']['path']}`，SHA256 `{manifest['parent']['sha256']}`。",
        f"续训结束模型：`{manifest['candidate']['path']}`，SHA256 `{manifest['candidate']['sha256']}`。", '',
        '| 指标 | 续训前 parent | 续训后 candidate |', '| --- | ---: | ---: |',
        f"| 完成局数 | {p['completed']}/{len(rows)} | {c['completed']}/{len(rows)} |",
        f"| 所有局平均虚拟耗时（秒） | {p['mean_virtual_s']:.3f} | {c['mean_virtual_s']:.3f} |",
        f"| 所有局 mean(T/C)（秒/已清除源） | {p['mean_per_source_s']} | {c['mean_per_source_s']} |",
        f"| 完整成功局 mean(T/N)（秒/源） | {p['mean_completed_per_source_s']} | {c['mean_completed_per_source_s']} |",
        f"| 整局 P95（秒） | {p['p95_virtual_s']:.3f} | {c['p95_virtual_s']:.3f} |", '',
        f"所有局配对差值（续训后减续训前）：{delta['mean']:.3f} 秒；近似 95% CI {delta['approximate_ci95']}。", '',
        '失败局全部保留；未完成局 T/C 只表示已清除源平均耗时，不能解释为找到全部源的时间。',
        '共同成功子集统计见 summary.json；该子集有选择偏差，必须结合整体完成率判断。',
        '策略保留每局实时剩余预算与路线搜索墙钟预算；同 seed 不保证动作逐步完全确定。',
        '两个模型均使用相同且与 checkpoint 哈希匹配的策略/模拟器源码；交替运行顺序。',
        '本次测试只诊断冻结模型，没有根据测试结果搜索或选择训练 checkpoint。', '',
        f"续训前失败原因：{p['errors']}；续训后失败原因：{c['errors']}。", '',
        '![配对分布](paired_distribution.png)', '']
    (out/'report.md').write_text('\n'.join(lines))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed', type=int, default=684000000)
    parser.add_argument('--episodes', type=int, default=3000)
    parser.add_argument('--workers', type=int, default=32)
    args = parser.parse_args()
    if args.episodes < 2 or args.workers < 1:
        raise ValueError('need at least two episodes and one worker')
    init_worker(args.parent, args.candidate)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    hashes = {str(p): sha(p) for root in ('solution','bsim') for p in Path(root).rglob('*.py')}
    manifest = dict(parent=dict(path=args.parent,sha256=sha(args.parent)),
                    candidate=dict(path=args.candidate,sha256=sha(args.candidate)),
                    seed_start=args.seed, episodes=args.episodes, workers=args.workers,
                    source_hashes=hashes, evaluator_sha256=sha(__file__), device='cpu',
                    policy='greedy', max_macros=400, selection_uses_test=False,
                    timing='live wall-clock features and route budgets; alternating evaluation order')
    atomic_json(out/'manifest.json', manifest)
    rows = []
    started = time.perf_counter()
    with (out/'samples.jsonl').open('x') as stream, ProcessPoolExecutor(
            args.workers, mp_context=mp.get_context('spawn'), initializer=init_worker,
            initargs=(args.parent,args.candidate)) as pool:
        for row in pool.map(pair, range(args.seed,args.seed+args.episodes), chunksize=1):
            rows.append(row)
            stream.write(json.dumps(row, allow_nan=False)+'\n')
            if len(rows) % 50 == 0 or len(rows) == args.episodes:
                stream.flush()
                elapsed = time.perf_counter()-started
                status = dict(status='RUNNING', pairs=len(rows), total=args.episodes, elapsed_s=elapsed,
                              eta_s=elapsed/len(rows)*(args.episodes-len(rows)),
                              completed={n:sum(r[n]['completion'] for r in rows) for n in ('parent','candidate')})
                atomic_json(out/'status.json', status)
                print(json.dumps(status), flush=True)
    assert len(rows) == args.episodes and len({r['seed'] for r in rows}) == args.episodes
    for file, digest in hashes.items():
        if sha(file) != digest:
            raise RuntimeError(f'source changed: {file}')
    for name in ('parent','candidate'):
        if sha(manifest[name]['path']) != manifest[name]['sha256']:
            raise RuntimeError(f'checkpoint changed: {name}')
    report = artifacts(out, rows, manifest)
    atomic_json(out/'status.json', dict(status='COMPLETE', pairs=len(rows), elapsed_s=time.perf_counter()-started))
    print(json.dumps({k:v for k,v in report.items() if not k.startswith('by_')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
