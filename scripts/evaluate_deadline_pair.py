#!/usr/bin/env python3
"""Frozen-checkpoint, paired Q3/Q4 evaluation on fresh LOCAL-RESEARCH seeds."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from solution.rl.environment import TrainingEnv, model_state
from solution.rl.model import CandidatePolicy
from solution.rl.training import atomic_json, load_checkpoint, provenance

MODELS = {}


def init_worker(checkpoints):
    torch.set_num_threads(1)
    for name, path in checkpoints.items():
        model = CandidatePolicy().eval()
        load_checkpoint(path, model)
        MODELS[name] = model


def episode(job):
    name, problem, seed, max_macros = job
    env = TrainingEnv(problem, seed, max_macros=max_macros)
    while not env.done:
        started = time.perf_counter()
        state, actions = env.observe()
        tensors = {k: torch.from_numpy(v).unsqueeze(0) for k, v in model_state(state).items()}
        with torch.inference_mode():
            logits, _ = MODELS[name](tensors)
        if not torch.isfinite(logits).all():
            raise RuntimeError(f'nonfinite logits: {name}, {seed}')
        env.decision_times.append(time.perf_counter() - started)
        env.step(actions[int(logits.argmax(-1).item())])
    from dataclasses import asdict
    row=env.metrics()
    row['scenario_sha256']=hashlib.sha256(json.dumps(asdict(env.session.kernel.scenario),sort_keys=True).encode()).hexdigest()
    return name,row


def summarize(rows):
    times = np.array([r['virtual_time_s'] for r in rows])
    per = [r['time_per_clear_s'] for r in rows if r['C'] > 0]
    complete = [r for r in rows if r['completion']]
    return dict(
        episodes=len(rows), completed_episodes=len(complete), completion_rate=len(complete)/len(rows),
        mean_virtual_s=float(times.mean()), median_virtual_s=float(np.median(times)),
        p95_virtual_s=float(np.percentile(times, 95)),
        mean_per_source_s=float(np.mean(per)) if len(per) == len(rows) else None,
        median_per_source_s=float(np.median(per)) if per else None,
        p95_per_source_s=float(np.percentile(per, 95)) if per else None,
        completed_only_mean_per_source_s=float(np.mean([r['time_per_clear_s'] for r in complete])) if complete else None,
        total_virtual_s=float(times.sum()), total_cleared_sources=sum(r['C'] for r in rows),
        total_sources=sum(r['N'] for r in rows),
        errors=dict(Counter(r['error'] or 'incomplete_without_error' for r in rows if not r['completion'])),
        max_macro_steps=max(r['macro_steps'] for r in rows),
        distribution_counts=dict(Counter(r['profile']['distribution'] for r in rows)),
        field_counts=dict(Counter(r['profile']['field'] for r in rows)),
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--episodes', type=int, default=3000)
    p.add_argument('--workers', type=int, default=32)
    p.add_argument('--q3-seed', type=int, default=310000000)
    p.add_argument('--q4-seed', type=int, default=320000000)
    a = p.parse_args()
    if a.episodes < 2 or a.workers < 1:
        raise ValueError('episodes >= 2 and workers >= 1 required')
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    checkpoints = {
        'q3_candidate': str(ROOT / 'runs/q3_legacy_deadline_20260913/best.pt'),
        'q3_baseline': str(ROOT / 'runs/q3_gpu8_extended_20260912/ppo/best.pt'),
        'q4_best': str(ROOT / 'runs/q4_legacy_deadline_20260913/best.pt'),
        'q4_baseline': str(ROOT / 'runs/q4_budget_20260912/train/best.pt'),
    }
    torch.set_num_threads(1)
    frozen = {}
    for name, path in checkpoints.items():
        data = load_checkpoint(path, CandidatePolicy())
        frozen[name] = dict(path=path, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                            stage=data.get('stage'), update=data.get('update'))
    seeds = {3: list(range(a.q3_seed, a.q3_seed+a.episodes)),
             4: list(range(a.q4_seed, a.q4_seed+a.episodes))}
    source = provenance()
    atomic_json(out/'manifest.json', dict(checkpoints=frozen, seeds=seeds, provenance=source,
        workers=a.workers, device='cpu', max_macros=400, policy='greedy',
        metric='mean_i(virtual_time_i / cleared_sources_i); failures retained and separately reported',
        selection='Both candidates selected by training validation only; frozen before final test',
        distribution='LOCAL-RESEARCH research-v1-20260911, not official test data',
        remaining_real_time_feature='live per-episode wall clock, same as TrainingEnv'))
    rows = {name: [] for name in checkpoints}
    jobs = [(name, q, seed, 400) for q in (3,4) for seed in seeds[q] for name in (([n for n in checkpoints if int(n[1])==q])[::1 if seed%2 else -1])]
    started = time.perf_counter()
    with (out/'samples.jsonl').open('x') as stream, ProcessPoolExecutor(
            a.workers, mp_context=mp.get_context('spawn'), initializer=init_worker,
            initargs=(checkpoints,)) as pool:
        for count, (name, row) in enumerate(pool.map(episode, jobs, chunksize=4), 1):
            rows[name].append(row)
            stream.write(json.dumps(dict(model=name, **row), allow_nan=False)+'\n')
            if count % 100 == 0 or count == len(jobs):
                stream.flush()
                elapsed = time.perf_counter()-started
                status = dict(status='RUNNING', finished=count, total=len(jobs), model=name,
                              elapsed_s=elapsed, episodes_per_s=count/elapsed,
                              estimated_remaining_s=(len(jobs)-count)*elapsed/count)
                atomic_json(out/'status.json', status)
                print(json.dumps(status), flush=True)
    report = {name: summarize(values) for name, values in rows.items()}
    for problem, candidate in ((3, 'q3_candidate'), (4, 'q4_best')):
        baseline = f'q{problem}_baseline'
        assert [r['seed'] for r in rows[candidate]] == [r['seed'] for r in rows[baseline]]
        assert [r['scenario_sha256'] for r in rows[candidate]] == [r['scenario_sha256'] for r in rows[baseline]]
        delta = np.array([s['virtual_time_s']-b['virtual_time_s'] for s, b in zip(rows[candidate], rows[baseline])])
        half = float(1.96*delta.std(ddof=1)/np.sqrt(len(delta)))
        report[candidate]['vs_baseline'] = dict(mean_delta_s=float(delta.mean()),
            ci95_s=[float(delta.mean()-half), float(delta.mean()+half)],
            reduction_percent=float(-100*delta.mean()/report[baseline]['mean_virtual_s']),
            faster_episodes=int((delta < 0).sum()), tied_episodes=int((delta == 0).sum()),
            slower_episodes=int((delta > 0).sum()),
            all_completed=all(r['completion'] for r in rows[candidate]+rows[baseline]))
        dn=np.array([s['virtual_time_s']/s['N']-b['virtual_time_s']/b['N'] for s,b in zip(rows[candidate],rows[baseline])])
        hn=float(1.96*dn.std(ddof=1)/np.sqrt(len(dn)))
        report[candidate]['vs_baseline']['paired_tn']=dict(mean=float(dn.mean()),ci95=[float(dn.mean()-hn),float(dn.mean()+hn)],reduction_percent=float(-100*dn.mean()/report[baseline]['mean_per_source_s']))
    for name, values in rows.items():
        atomic_json(out/f'{name}_samples.json', values)
        atomic_json(out/f'{name}_strata.json', {
            key: {str(v): summarize([r for r in values if (r['profile'].get(key) if key in ('distribution', 'field') else r[key]) == v])
                  for v in sorted({r['profile'].get(key) if key in ('distribution', 'field') else r[key] for r in values})}
            for key in ('N', 'distribution', 'field')})
    with (out/'samples.csv').open('x', newline='') as f:
        fields = ['model', 'seed', 'N', 'C', 'completion', 'virtual_time_s', 'time_per_clear_s', 'macro_steps', 'error']
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(dict(model=name, **r) for name, values in rows.items() for r in values)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), dpi=180)
    for ax, candidate in zip(axes, ('q3_candidate', 'q4_best')):
        problem = int(candidate[1])
        baseline = f'q{problem}_baseline'
        values = [r['time_per_clear_s'] for r in rows[candidate] if r['C']]
        old = [r['time_per_clear_s'] for r in rows[baseline] if r['C']]
        bins = np.histogram_bin_edges(values+old, bins=45)
        ax.hist(old, bins=bins, histtype='step', linewidth=1.5, color='#64748b', label='Baseline')
        ax.hist(values, bins=bins, alpha=.7, color='#2563eb', label='Latest candidate')
        if values:
            ax.axvline(np.mean(values), color='#dc2626', label=f'Mean: {np.mean(values):.2f} s/source')
        ax.set(title=f'Q{problem}: {a.episodes} scenarios; completed {report[candidate]["completed_episodes"]}/{a.episodes}',
               xlabel='Virtual time / cleared sources (s/source)', ylabel='Scenarios')
        ax.legend(fontsize=8)
        ax.grid(axis='y', alpha=.2)
    fig.tight_layout()
    for suffix in ('png', 'pdf'):
        fig.savefig(out/f'per_source_distribution.{suffix}')
    plt.close(fig)
    if provenance() != source:
        raise RuntimeError('source changed during evaluation')
    for name, info in frozen.items():
        if hashlib.sha256(Path(info['path']).read_bytes()).hexdigest() != info['sha256']:
            raise RuntimeError(f'checkpoint changed during evaluation: {name}')
    atomic_json(out/'summary.json', report)
    atomic_json(out/'status.json', dict(status='COMPLETE', finished=len(jobs),
                total=len(jobs), elapsed_s=time.perf_counter()-started))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
