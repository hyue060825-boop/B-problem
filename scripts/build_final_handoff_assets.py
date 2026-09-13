"""从最终原始数据复算交付表；只更新 handoff 衍生表和对应来源清单。"""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'results/final-20260913'
OUT = ROOT / 'handoff/tables/final-20260913'
RECORD = ROOT / 'records/acceptance/experiment_result-8ef9ef8'
INPUTS = {}


def read(path):
    path = Path(path)
    INPUTS[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())


def table(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def stats(rows):
    times = np.array([r['virtual_time_s'] for r in rows])
    counts = np.array([r['N'] for r in rows])
    return dict(episodes=len(rows), completed=sum(r['completion'] for r in rows),
                total_sources=int(counts.sum()), mean_T_s=float(times.mean()),
                mean_T_per_N_s=float((times/counts).mean()), p95_T_s=float(np.percentile(times, 95)))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mapping = {r['source_path']: r['suggested_target'] for r in csv.DictReader(
        (RECORD/'资产落位建议.csv').open(encoding='utf-8-sig'))}
    registry = read(RECORD/'source-adapted/paper/model_registry.json')
    for model in registry['models']:
        model['source_path'] = model['path']
        model['path'] = mapping[model['path']]
        model['runtime_root'] = 'deployment/runtime_public_v2'
    registry['source_commit'] = '8ef9ef87d8c5413e85e02d18a99eee083da8d66f'
    (ROOT/'records/inventory/models-final-20260913.json').write_text(
        json.dumps(registry, ensure_ascii=False, indent=2)+'\n')
    q3p = RUNS/'q34_deadline_test3000_20260913/q3_baseline_samples.json'
    q3f = RUNS/'q34_deadline_test3000_20260913/q3_candidate_samples.json'
    q4p = RUNS/'q4_baseline_8gpu_1h_20260913/train/final_test.json'
    q4 = read(q4p)
    pairs = [(3, read(q3p), read(q3f), q3p, q3f),
             (4, q4['baseline'], q4['student'], q4p, q4p)]
    summaries, strata, effects = [], [], []
    for q, parent, final, parent_path, final_path in pairs:
        assert len(parent) == len(final) == 3000
        assert len({r['seed'] for r in final}) == 3000
        assert all((a['seed'], a['N'], a['profile']) == (b['seed'], b['N'], b['profile'])
                   for a, b in zip(parent, final))
        for row in parent + final:
            assert row['completion'] and row['C'] == row['N'] and not row['error']
            cost = row['path_length_m']/5 + 5*row['measures'] + row['switches'] + 3*row['clear_failures'] + 5*row['C']
            assert abs(cost-row['virtual_time_s']) < .001
        for label, rows, path in [('parent', parent, parent_path), ('final', final, final_path)]:
            mid = f'q{q}_{label}'
            digest = next(m['sha256'] for m in registry['models'] if m['id'] == mid)
            evidence = path.relative_to(ROOT).as_posix()
            summaries.append(dict(model=mid, checkpoint_sha256=digest, **stats(rows), evidence=evidence))
            for n in range(10, 17):
                strata.append(dict(model=mid, N=n, **stats([r for r in rows if r['N'] == n]), evidence=evidence))
        delta = np.array([b['virtual_time_s']-a['virtual_time_s'] for a, b in zip(parent, final)])
        ns = np.array([r['N'] for r in final])
        for metric, values in [('T_s', delta), ('T_per_N_s', delta/ns)]:
            half = 1.96*values.std(ddof=1)/len(values)**.5
            effects.append(dict(problem=q, metric=metric, episodes=len(values),
                mean_final_minus_parent=float(values.mean()), ci95_low=float(values.mean()-half),
                ci95_high=float(values.mean()+half), ci_method='paired normal approximation mean +/- 1.96 SE',
                parent_evidence=parent_path.relative_to(ROOT).as_posix(),
                final_evidence=final_path.relative_to(ROOT).as_posix()))
    table('final_main_results.csv', summaries)
    table('final_by_source_count.csv', strata)
    table('paired_effects.csv', effects)
    training, validation = [], []
    for q, folder, selected in [(3, 'q3_legacy_deadline_20260913', 4400),
                                (4, 'q4_baseline_8gpu_1h_20260913/train', 600)]:
        path = RUNS/folder/'metrics.jsonl'
        INPUTS[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        events = [json.loads(line) for line in path.read_text().splitlines()]
        ppo = [r for r in events if r['stage'] == 'PPO']
        assert [r['update'] for r in ppo] == list(range(1, len(ppo)+1))
        for scope, rows in [('through_selected_best', ppo[:selected]), ('whole_run', ppo)]:
            training.append(dict(model=f'q{q}_final', scope=scope, iterations=len(rows),
                episodes=sum(r['episodes'] for r in rows), macro_transitions=sum(r['macros'] for r in rows),
                elapsed_at_last_ppo_s=rows[-1]['elapsed_s'], ddp_world_size=events[0]['world_size'],
                sync_all=all(r['sync'] for r in rows), evidence=path.relative_to(ROOT).as_posix()))
        for row in events:
            if row['stage'] == 'VALIDATION':
                validation.append(dict(model=f'q{q}_final', iteration=row['update'],
                    mean_paired_T_per_N_delta_s=row['mean_delta_s'], ci95_halfwidth_s=row['ci95_halfwidth_s'],
                    selection_pass=row['selection_pass'], evidence=path.relative_to(ROOT).as_posix()))
    table('training_data_accounting.csv', training)
    table('validation_curves.csv', validation)
    # 补充表保持原数值与模型归属，只把证据路径指向 main；原件另存。
    originals = RECORD/'source-adapted/paper/tables'
    for path in sorted(originals.glob('*.csv')):
        if path.name in {'final_main_results.csv', 'final_by_source_count.csv', 'paired_effects.csv',
                          'training_data_accounting.csv', 'validation_curves.csv'}:
            continue
        INPUTS[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in ('evidence', 'source', 'fixture'):
                if key in row:
                    row[key] = row[key].removeprefix('/data5/hy/B-problem/').replace('runs/', 'results/final-20260913/')
        table(path.name, rows)
    timing = read(originals/'official_log_timing.json')
    timing['evidence'] = 'results/official/q4-20260913/logQ4.jsonl'
    timing['run_type'] = '未注明演练或正式；仅提供这一份交互日志'
    (OUT/'official_log_timing.json').write_text(json.dumps(timing, ensure_ascii=False, indent=2)+'\n')
    (RECORD/'table-inputs-main.json').write_text(json.dumps(INPUTS, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status='PASS', episodes=12000, training=training), ensure_ascii=False))


if __name__ == '__main__':
    main()
