"""Four paired planning interventions with a single frozen Q4 checkpoint."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import asdict
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'deployment/runtime_public_v2'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUNTIME))
from solution.rl.environment import TrainingEnv, model_state
from solution.rl.model import CandidatePolicy
from experiments.q4.planning import VARIANTS, TWO_OPT_PASSES, select_action
from analyze_q4_absence_tail import summarize_events

CHECKPOINT = ROOT / 'results/final-20260913/q4_legacy_deadline_20260913/best.pt'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def init_worker():
    global MODEL
    torch.set_num_threads(1)
    checkpoint = torch.load(CHECKPOINT, map_location='cpu', weights_only=False)
    for p, h in checkpoint['provenance']['files'].items():
        if p.startswith(('solution/', 'bsim/')):
            assert digest(RUNTIME / p) == h, p
    MODEL = CandidatePolicy().eval()
    MODEL.load_state_dict(checkpoint['model'], strict=True)


def episode(job):
    seed, variant, clock_mode = job
    env = TrainingEnv(4, seed, max_macros=400)
    events, altered, scheduling, route_changes = [], 0, 0, 0
    original_request = env._request
    def traced(path, pos, channel):
        old = env.session.state
        response = original_request(path, pos, channel)
        if path in ('/measure', '/clear'):
            start, end = old.virtual_us / 1e6, env.session.state.virtual_us / 1e6
            kind = response.get('measure_result') or ('clear_success' if response['clear_result'] == 'success' else 'clear_failed')
            measure = 5. if path == '/measure' else 0.
            switch = float(path == '/measure' and channel != old.channel)
            clear = 0. if path == '/measure' else 5. if kind == 'clear_success' else 3.
            events.append(dict(start=start, end=end, kind=kind, channel=channel,
                               move_s=end-start-measure-switch-clear,
                               measure_s=measure, switch_s=switch, clear_s=clear))
        return response
    env._request = traced
    while not env.done:
        started = time.perf_counter()
        state, actions = env.observe()
        if clock_mode == 'fixed':
            # Remove CPU contention/planning latency as an input confound in all arms.
            state['global_'][4] = 1.
        with torch.inference_mode():
            logits, _ = MODEL({k: torch.from_numpy(v).unsqueeze(0) for k, v in model_state(state).items()})
        if not torch.isfinite(logits).all():
            raise RuntimeError('nonfinite policy logits')
        chosen = actions[int(logits.argmax(-1))]
        action = select_action(env.controller, actions, chosen, variant)
        altered += int(action != chosen)
        scheduling += int(chosen.kind == 'COVER' and action.kind == 'CLEAR')
        route_changes += int(chosen.kind == action.kind == 'COVER' and chosen.station != action.station)
        env.decision_times.append(time.perf_counter()-started)
        env.step(action)
    metrics = env.metrics()
    parts = summarize_events(events, metrics['virtual_time_s'], metrics['N'])
    return dict(**metrics, **{k: v for k, v in parts.items() if k not in metrics},
                variant=variant, overrides=altered, scheduling_overrides=scheduling,
                route_overrides=route_changes,
                scenario_sha256=hashlib.sha256(json.dumps(asdict(env.session.kernel.scenario), sort_keys=True).encode()).hexdigest())


def paired_job(job):
    seed, clock_mode = job
    # Rotate execution order to spread process warmup/CPU scheduling effects.
    offset = seed % len(VARIANTS)
    order = VARIANTS[offset:] + VARIANTS[:offset]
    rows = {v: episode((seed, v, clock_mode)) for v in order}
    assert len({r['scenario_sha256'] for r in rows.values()}) == 1
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--episodes', type=int, default=3000)
    p.add_argument('--seed', type=int, default=1713000000)
    p.add_argument('--workers', type=int, default=32)
    p.add_argument('--clock-mode', choices=['fixed', 'live'], default='fixed')
    p.add_argument('--original-parity', action='store_true')
    a = p.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    source_paths = [ROOT / 'experiments/q4/planning.py', Path(__file__), ROOT / 'scripts/analyze_q4_absence_tail.py']
    source_hashes = {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    runtime_hashes = {str(p.relative_to(RUNTIME)): digest(p) for p in RUNTIME.rglob('*.py')}
    weight_hash = digest(CHECKPOINT)
    manifest = dict(checkpoint=str(CHECKPOINT), checkpoint_sha256=weight_hash,
                    variants=VARIANTS, seed_start=a.seed, episodes_per_variant=a.episodes,
                    total_episodes=4*a.episodes, clock_mode=a.clock_mode, workers=a.workers,
                    frozen_source=source_hashes, frozen_runtime=runtime_hashes,
                    route_search=dict(two_opt_passes=TWO_OPT_PASSES, starts=['policy_first', 'nearest_first'], endpoint='free'),
                    schedule='cheapest insertion of legal certified CLEAR actions; preserve backbone order',
                    override_scope='Only after policy chooses COVER; localization/probe/exit unchanged',
                    primary_metric='All-sample mean virtual seconds, valid only with completion retained; per-case T/N also reported',
                    preregistered='No algorithm or parameter selection on the 3000 final scenes; all four arms reported',
                    distribution='research-v1-20260911; default profiles, not official distribution',
                    budget='400 macros in all arms; wall latency reported separately')
    save(out / 'manifest.json', manifest)
    snapshot = out / 'source'
    for path in source_paths:
        target = snapshot / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    init_worker()
    if a.original_parity:
        original = json.loads((ROOT / 'results/final-20260913/q34_deadline_test3000_20260913/q4_best_samples.json').read_text())
        matches = []
        for r in original[::max(1, len(original)//32)][:32]:
            live = episode((r['seed'], 'baseline', 'live'))
            fixed = episode((r['seed'], 'baseline', 'fixed'))
            assert live['scenario_sha256'] == r['scenario_sha256'] == fixed['scenario_sha256']
            matches.append(dict(seed=r['seed'], live_delta=live['virtual_time_s']-r['virtual_time_s'],
                                fixed_delta=fixed['virtual_time_s']-r['virtual_time_s'],
                                complete=live['completion'] and fixed['completion']))
        save(out / 'original_parity.json', matches)
        assert all(r['complete'] and r['live_delta'] == r['fixed_delta'] == 0 for r in matches)
    started = time.perf_counter()
    with (out / 'samples.jsonl').open('x') as stream, ProcessPoolExecutor(
            a.workers, mp_context=mp.get_context('spawn'), initializer=init_worker) as pool:
        all_rows = []
        for index, result in enumerate(pool.map(paired_job, [(s, a.clock_mode) for s in range(a.seed, a.seed+a.episodes)], chunksize=2), 1):
            for variant in VARIANTS:
                row = result[variant]
                all_rows.append(row)
                stream.write(json.dumps(row, allow_nan=False) + '\n')
            if index % 50 == 0 or index == a.episodes:
                stream.flush()
                elapsed = time.perf_counter()-started
                status = dict(status='RUNNING', paired_scenarios=index, total=a.episodes,
                              elapsed_s=elapsed, estimated_remaining_s=(a.episodes-index)*elapsed/index,
                              failures=sum(not r['completion'] for r in all_rows))
                save(out / 'status.json', status)
                print(json.dumps(status), flush=True)
    assert source_hashes == {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    assert runtime_hashes == {str(p.relative_to(RUNTIME)): digest(p) for p in RUNTIME.rglob('*.py')}
    assert weight_hash == digest(CHECKPOINT)
    assert all(abs(r['cost_accounting_error']) < 1e-5 for r in all_rows)
    fields = [k for k in all_rows[0] if k != 'profile']
    with (out / 'samples.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)
    save(out / 'status.json', dict(status='COMPLETE', paired_scenarios=a.episodes,
                                  total_episodes=len(all_rows), elapsed_s=time.perf_counter()-started,
                                  failures=sum(not r['completion'] for r in all_rows)))


if __name__ == '__main__':
    main()
