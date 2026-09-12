"""Summarize the frozen held-out test without running or selecting another model."""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'train'


def main():
    test = json.loads((RUN / 'test_0100.json').read_text())
    status = json.loads((RUN / 'status.json').read_text())
    assert status['stage'] == 'COMPLETE'
    events = [json.loads(line) for line in (RUN / 'metrics.jsonl').read_text().splitlines()]
    updates = [r for r in events if r['stage'] == 'DDP_PPO']
    validations = [r for r in events if r['stage'] == 'VALIDATION']
    assert [r['update'] for r in updates]==list(range(1,101))
    training_seeds=[]
    for stage in ('bc','dagger','ppo'):
        for path in RUN.glob(f'{stage}_*_episodes.json'):
            training_seeds.extend(row['seed'] for row in json.loads(path.read_text()))
    assert len(training_seeds)==len(set(training_seeds))==13184
    val_seeds={row['seed'] for row in json.loads((RUN/'validation_0100.json').read_text())['rows']}
    test_seeds={row['seed'] for row in test['rows']}
    assert len(test_seeds)==3000 and len(val_seeds)==128
    assert not (set(training_seeds)&val_seeds or set(training_seeds)&test_seeds or val_seeds&test_seeds)
    selection = json.loads((RUN / 'test_selection.json').read_text())
    checkpoint = Path(selection['checkpoint'])
    diagnostics=[]
    for path in sorted(RUN.glob('validation_*.json')):
        v=json.loads(path.read_text())
        diagnostics.append(dict(update=int(path.stem.split('_')[-1]),
                                delta_s=v['mean_paired_delta_s'],
                                completion=v['student']['completion_rate'],
                                means={name:{key:float(np.mean([r[name][key] for r in v['rows']]))
                                             for key in ('path_length_m','measures','macro_steps','clear_failures')}
                                       for name in ('baseline','student')}))
    samples = []
    for row in test['rows']:
        s, b = row['student'], row['baseline']
        samples.append(dict(seed=row['seed'], N=s['N'], C=s['C'], completion=s['completion'],
                            virtual_time_s=s['virtual_time_s'],
                            per_source_s=s['time_per_clear_s'],
                            baseline_virtual_time_s=b['virtual_time_s'],
                            baseline_per_source_s=b['time_per_clear_s'],
                            paired_delta_s=s['virtual_time_s']-b['virtual_time_s'],
                            distribution=s['profile']['distribution'], field=s['profile']['field'],
                            macros=s['macro_steps'], error=s['error']))
    with (ROOT / 'test_samples.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(samples[0]))
        writer.writeheader(); writer.writerows(samples)
    # Never silently remove failed episodes or treat zero clears as zero time.
    valid = [r['per_source_s'] for r in samples if r['per_source_s'] is not None]
    t = np.asarray(valid)
    summary = dict(
        checkpoint=str(checkpoint), checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        test_episodes=len(samples), completed=sum(r['completion'] for r in samples),
        mean_of_case_per_source_s=float(t.mean()) if len(valid)==len(samples) else None,
        per_source_definition='total virtual time including search, clearing and exit / number cleared',
        all_cases_have_clears=len(valid)==len(samples),
        median_per_source_s=float(np.median(t)), p95_per_source_s=float(np.percentile(t,95)),
        baseline=test['baseline'], student=test['student'],
        mean_paired_delta_s=test['mean_paired_delta_s'],
        paired_delta_95ci_halfwidth_s=test['approximate_95ci_halfwidth_s'],
        test_selection_pass=test['selection_pass'],
        ppo_updates=len(updates), ppo_scenes=sum(r['episodes'] for r in updates),
        ppo_macros=sum(r['macros'] for r in updates),
        all_training_sync_checks_passed=all(r['parameter_and_optimizer_sync'] for r in events if 'parameter_and_optimizer_sync' in r),
        exact_sync_checks=sum('parameter_and_optimizer_sync' in r for r in events),
        training_validation_test_seed_disjoint_verified=True,
        min_ppo_completion_rate=min(r['completion_rate'] for r in updates),
        mean_ppo_iteration_s=float(np.mean([r['sample_s']+r['update_s'] for r in updates])),
        train_and_validation_s=validations[-1]['elapsed_s'], total_wall_s=status['elapsed_s'],
        seeds=json.loads((RUN/'seed_manifest.json').read_text()),
        validation_diagnostics=diagnostics,
        results_by_source_count={str(n):dict(cases=sum(r['N']==n for r in samples),
                                            completed=sum(r['completion'] for r in samples if r['N']==n),
                                            mean_per_source_s=float(np.mean([r['per_source_s'] for r in samples if r['N']==n and r['per_source_s'] is not None])))
                                 for n in range(10,17)})
    (ROOT/'evaluation_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False))
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),dpi=180)
    axes[0].hist(t,bins=50,color='#2563eb',edgecolor='white',linewidth=.4)
    axes[0].axvline(t.mean(),color='#c2410c',label=f'Mean: {t.mean():.2f} s/source')
    axes[0].set(ylabel='Number of scenarios',title=f'Q4 held-out test: {len(samples)} scenarios')
    axes[0].legend()
    axes[1].plot(np.sort(t),np.arange(1,len(t)+1)/len(t),color='#2563eb')
    axes[1].set(ylabel='Fraction of scenarios',title=f'Completed and exited: {summary["completed"]}/{len(samples)}')
    for ax in axes:
        ax.set_xlabel('Total virtual time / cleared sources (s/source)')
        ax.grid(alpha=.2)
    fig.suptitle('LOCAL-RESEARCH; includes search, clearing and exit; not official simulator results',fontsize=10)
    fig.tight_layout()
    for extension in ('png','pdf'):fig.savefig(ROOT/f'per_source_distribution.{extension}')
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),dpi=180)
    axes[0].plot([r['update'] for r in updates],[r['completion_rate']*100 for r in updates])
    axes[0].set(xlabel='PPO update',ylabel='Training episode completion (%)',ylim=(0,105))
    axes[1].plot([r['update'] for r in validations],[r['paired_delta_s'] for r in validations],marker='o')
    axes[1].axhline(0,color='gray',linestyle='--')
    axes[1].set(xlabel='PPO update',ylabel='Validation mean (student - teacher), seconds')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Q4 four-GPU synchronized training; fixed validation seeds; negative delta is faster')
    fig.tight_layout();fig.savefig(ROOT/'training_curve.png');plt.close(fig)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
