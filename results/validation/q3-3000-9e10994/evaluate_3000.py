#!/usr/bin/env python3
"""Run a trained Q3 policy on 3000 independent local research scenarios."""
import argparse
import json
import multiprocessing as mp
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from solution.rl.environment import TrainingEnv, features, model_state
from solution.rl.model import CandidatePolicy

WORKER_MODEL = None

def init_worker(checkpoint):
    global WORKER_MODEL
    torch.set_num_threads(1)
    WORKER_MODEL = CandidatePolicy()
    data = torch.load(checkpoint, map_location='cpu', weights_only=False)
    if data.get('features') != 'normalized-public-v2':
        raise ValueError('checkpoint feature version mismatch')
    WORKER_MODEL.load_state_dict(data['model'])
    WORKER_MODEL.eval()

def evaluate_one(seed):
    env = TrainingEnv(3, int(seed), max_macros=400)
    while not env.done:
        state, actions = env.observe()
        public = model_state(features(env.controller, actions))
        tensors = {k: torch.from_numpy(v).unsqueeze(0) for k, v in public.items()}
        with torch.inference_mode():
            logits, _ = WORKER_MODEL(tensors, torch.ones((1, len(actions)), dtype=torch.bool))
        env.step(actions[int(logits.argmax(-1).item())])
    metrics = env.metrics()
    sources = int(metrics['N'])
    cleared = int(metrics['C'])
    per_source = float(metrics['virtual_time_s'] / cleared) if cleared else None
    return {
        'seed': int(seed),
        'sources': sources,
        'cleared': cleared,
        'completion': bool(metrics['completion']),
        'virtual_time_s': float(metrics['virtual_time_s']),
        'per_source_time_s': per_source,
        'macro_steps': int(metrics['macro_steps']),
        'error': metrics['error'],
        'profile': metrics['profile'],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkpoint', required=True)
    ap.add_argument('--episodes', type=int, default=3000)
    ap.add_argument('--seed', type=int, default=1200000)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--output', default='runs/q3_3000_test_20260911')
    args = ap.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    seeds = list(range(args.seed, args.seed + args.episodes))
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context('spawn'),
                             initializer=init_worker, initargs=(args.checkpoint,)) as pool:
        rows = list(pool.map(evaluate_one, seeds, chunksize=4))
    completed = [r for r in rows if r['cleared'] > 0]
    per_sample = np.asarray([r['per_source_time_s'] for r in completed], dtype=float)
    total_time = float(sum(r['virtual_time_s'] for r in rows))
    total_sources = int(sum(r['cleared'] for r in rows))
    summary = {
        'status': 'COMPLETE',
        'problem': 3,
        'checkpoint': str(args.checkpoint),
        'episodes': args.episodes,
        'seed_start': args.seed,
        'seed_end_exclusive': args.seed + args.episodes,
        'completed_episodes': len([r for r in rows if r['completion']]),
        'completion_rate': float(np.mean([r['completion'] for r in rows])),
        'samples_with_cleared_source': len(completed),
        'mean_of_sample_per_source_times_s': float(per_sample.mean()) if len(per_sample) else None,
        'total_virtual_time_s': total_time,
        'total_cleared_sources': total_sources,
        'source_weighted_mean_time_s': total_time / total_sources if total_sources else None,
        'median_sample_per_source_time_s': float(np.median(per_sample)) if len(per_sample) else None,
        'p05_sample_per_source_time_s': float(np.percentile(per_sample, 5)) if len(per_sample) else None,
        'p95_sample_per_source_time_s': float(np.percentile(per_sample, 95)) if len(per_sample) else None,
        'min_sample_per_source_time_s': float(per_sample.min()) if len(per_sample) else None,
        'max_sample_per_source_time_s': float(per_sample.max()) if len(per_sample) else None,
        'elapsed_wall_s': time.perf_counter() - started,
        'distribution': 'LOCAL-RESEARCH research-v1-20260911; four seeded distributions and three error fields',
    }
    (out / 'samples.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    fig, ax = plt.subplots(figsize=(10, 6), dpi=160)
    ax.hist(per_sample, bins=50, color='#2563eb', alpha=0.82, edgecolor='white', linewidth=0.35)
    mean = float(per_sample.mean())
    ax.axvline(mean, color='#dc2626', linewidth=2, label=f'mean = {mean:.2f} s/source')
    ax.axvline(float(np.median(per_sample)), color='#111827', linewidth=1.5, linestyle='--', label=f'median = {np.median(per_sample):.2f} s/source')
    ax.set_title('Q3 3000-scenario distribution of average time per cleared source')
    ax.set_xlabel('Average virtual time per source in one scenario (s/source)')
    ax.set_ylabel('Number of scenarios')
    ax.grid(axis='y', alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / 'per_source_time_distribution.png')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()
