"""Audit and report the already-completed one-hour Q4 paired terminal test."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'results/final-20260913/q4_baseline_8gpu_1h_20260913'
RUNTIME=ROOT/'deployment/runtime_public_v2'
sys.path.insert(0,str(RUNTIME))
from bsim.research import make_research_session


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(rows):
    t=np.array([r['virtual_time_s'] for r in rows]);n=np.array([r['N'] for r in rows])
    return dict(episodes=len(rows),completed=sum(r['completion'] for r in rows),
                total_sources=int(n.sum()),cleared_sources=sum(r['C'] for r in rows),
                mean_s=float(t.mean()),median_s=float(np.median(t)),p95_s=float(np.percentile(t,95)),
                mean_per_source_s=float((t/n).mean()),p95_per_source_s=float(np.percentile(t/n,95)),
                mean_path_length_m=float(np.mean([r['path_length_m'] for r in rows])),
                mean_measures=float(np.mean([r['measures'] for r in rows])),
                mean_clear_failures=float(np.mean([r['clear_failures'] for r in rows])))


def paired(a,b):
    delta=np.array([y['virtual_time_s']-x['virtual_time_s'] for x,y in zip(a,b)])
    dn=delta/np.array([r['N'] for r in a])
    def ci(v):
        half=1.96*v.std(ddof=1)/np.sqrt(len(v))
        return [float(v.mean()-half),float(v.mean()+half)]
    return dict(mean_delta_s=float(delta.mean()),ci95_delta_s=ci(delta),
                improvement_pct=float(-100*delta.mean()/np.mean([r['virtual_time_s'] for r in a])),
                mean_delta_per_source_s=float(dn.mean()),ci95_per_source_s=ci(dn),
                improvement_per_source_pct=float(-100*dn.mean()/np.mean([r['virtual_time_s']/r['N'] for r in a])),
                faster=int((delta < -1e-6).sum()),tied=int((abs(delta)<=1e-6).sum()),slower=int((delta>1e-6).sum()))


def main():
    torch.set_num_threads(1)
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--input', default=str(RUN));ap.add_argument('--output',required=True);args=ap.parse_args()
    run=Path(args.input)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    source=run/'train/final_test.json';data=json.loads(source.read_text())
    # 原记录中的服务器路径只在内存中映射；原始 JSON 保持不变。
    data['baseline_checkpoint']=str(run/'parent/best.pt')
    data['checkpoint']=str(run/'train/best.pt')
    a,b=data['baseline'],data['student']
    assert len(a)==len(b)==3000 and len({r['seed'] for r in a})==3000
    assert not data['selection_used_test'] and data['validation_selected']
    original=ROOT/'results/final-20260913/q4_legacy_deadline_20260913/best.pt'
    assert sha(data['baseline_checkpoint'])==sha(original)=='e8a525f78d176d9073372394b324bd585f4445fbf9cd1515141c483f38d5bd90'
    weight_info={}
    for label,path in [('baseline',data['baseline_checkpoint']),('candidate',data['checkpoint'])]:
        ck=torch.load(path,map_location='cpu',weights_only=False)
        critical={p:h for p,h in ck['provenance']['files'].items() if p.startswith(('solution/','bsim/'))}
        assert all(sha(RUNTIME/p)==h for p,h in critical.items())
        weight_info[label]=dict(path=path,sha256=sha(path),update=ck['update'],runtime_files=critical)
    assert weight_info['baseline']['runtime_files']==weight_info['candidate']['runtime_files']
    pairs=[]
    for x,y in zip(a,b):
        assert (x['seed'],x['N'],x['profile'])==(y['seed'],y['N'],y['profile'])
        assert x['completion'] and y['completion'] and x['C']==y['C']==x['N']
        assert not x['error'] and not y['error']
        for r in (x,y):assert abs(r['virtual_time_s']/r['N']-r['time_per_clear_s'])<1e-6
        pairs.append(dict(seed=x['seed'],N=x['N'],profile=x['profile'],baseline_s=x['virtual_time_s'],
                          candidate_s=y['virtual_time_s'],delta_s=y['virtual_time_s']-x['virtual_time_s'],
                          baseline_per_source_s=x['time_per_clear_s'],candidate_per_source_s=y['time_per_clear_s']))
    summary=dict(baseline=stats(a),candidate=stats(b),paired=paired(a,b),
                 by_N={str(n):dict(baseline=stats([r for r in a if r['N']==n]),candidate=stats([r for r in b if r['N']==n]),
                                  paired=paired([r for r in a if r['N']==n],[r for r in b if r['N']==n])) for n in range(10,17)},
                 by_distribution={d:dict(baseline=stats([r for r in a if r['profile']['distribution']==d]),
                                         candidate=stats([r for r in b if r['profile']['distribution']==d])) for d in sorted({r['profile']['distribution'] for r in a})})
    assert abs(summary['paired']['mean_delta_s']-data['mean_delta_s'])<1e-6
    logs=[json.loads(line) for line in (run/'train/metrics.jsonl').read_text().splitlines()]
    updates=[r for r in logs if r['stage']=='PPO']
    manifest=dict(weights=weight_info,raw_result_sha256=sha(source),raw_result=str(source),
                  seed_start=a[0]['seed'],seed_end=a[-1]['seed'],validation_selected_update=weight_info['candidate']['update']+1,
                  training=dict(updates=len(updates),episodes=sum(r['episodes'] for r in updates),
                                transitions=sum(r['global_samples'] for r in updates),all_ddp_sync=all(r['sync'] for r in updates)),
                  evaluation='Reuses automatic 3000-pair terminal evaluation; no redundant new games or test-driven checkpoint selection',
                  audit='Exact seed, profile and N alignment; same 44 runtime file hashes. Original evaluator did not save scenario-content hashes.',
                  timing='Original live remaining-wall-time feature; distributed CPU rollout; baseline and candidate evaluated sequentially per rank')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    with (out/'paired_samples.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=[k for k in pairs[0] if k!='profile'],extrasaction='ignore');writer.writeheader();writer.writerows(pairs)
    p,c,d=summary['baseline'],summary['candidate'],summary['paired']
    lines=['# Q4 八卡一小时续训：3000 场景配对测评','',
           '训练结束后的自动测试已完成；本报告复核并汇总已有结果，没有重复测试，也没有根据测试集重新选择 checkpoint。', '',
           '结论：新模型平均耗时小幅下降，但配对 95% 置信区间包含零，尚不能确认优于原最佳基线。保留原部署推荐，同时保存新候选供进一步独立验证。','',
           f"新候选：`{data['checkpoint']}`（验证集选出的第 {manifest['validation_selected_update']} 轮，文件 update 从 0 开始为 {weight_info['candidate']['update']}）。",
           f"原最佳：`{original}`，与本轮 parent/best.pt 字节哈希完全一致。",'',
           '| 指标 | 原最佳基线 | 一小时续训 best |','|---|---:|---:|',
           f"| 完成数 | {p['completed']}/3000 | {c['completed']}/3000 |",
           f"| 清除源数 | {p['cleared_sources']}/{p['total_sources']} | {c['cleared_sources']}/{c['total_sources']} |",
           f"| 平均整局虚拟秒 | {p['mean_s']:.3f} | {c['mean_s']:.3f} |",
           f"| 平均每源 T/N（秒） | {p['mean_per_source_s']:.3f} | {c['mean_per_source_s']:.3f} |",
           f"| 整局 P95（秒） | {p['p95_s']:.3f} | {c['p95_s']:.3f} |",
           f"| 每源 T/N 的 P95（秒） | {p['p95_per_source_s']:.3f} | {c['p95_per_source_s']:.3f} |",'',
           f"平均整局变化（新−旧）{d['mean_delta_s']:+.3f} 秒，降低 {d['improvement_pct']:.3f}%；配对 95% CI [{d['ci95_delta_s'][0]:+.3f}, {d['ci95_delta_s'][1]:+.3f}] 秒。",
           f"平均每源变化 {d['mean_delta_per_source_s']:+.3f} 秒/源，降低 {d['improvement_per_source_pct']:.3f}%；配对 95% CI [{d['ci95_per_source_s'][0]:+.3f}, {d['ci95_per_source_s'][1]:+.3f}] 秒/源。",
           f"新模型更快 {d['faster']} 例、持平 {d['tied']} 例、更慢 {d['slower']} 例。",'',
           '## 按源数比较','',
           '| N | 样例数 | 原最佳平均总秒 | 新 best 平均总秒 | 新−旧（秒） |',
           '|---:|---:|---:|---:|---:|']
    for n,r in summary['by_N'].items():
        lines.append(f"| {n} | {r['baseline']['episodes']} | {r['baseline']['mean_s']:.2f} | {r['candidate']['mean_s']:.2f} | {r['paired']['mean_delta_s']:+.2f} |")
    lines+=['','## 训练与统计口径','',
            f"- 共完成 {len(updates)} 轮，采样 {manifest['training']['episodes']} 个训练场景、{manifest['training']['transitions']} 个宏动作转移，八卡模型及 Adam 同步检查全部通过。",
            '- 所有候选保留原规划与退出证书，没有使用 B/C/D 规划改动。best 按 512 场景验证集选择；最终第 682 轮 latest 不是本报告的候选。',
            f"- 独立测试种子 {a[0]['seed']}–{a[-1]['seed']}，双方各 3000 局；逐局 seed、profile、源数一致，运行时代码 44 个文件的哈希与两份模型均一致。原评测没有保存逐场景内容哈希，本报告不声称已核对未记录的内容哈希。",
            '- T 为包含无源确认的整局虚拟时间。每源指标先逐局计算 T/N 再平均；没有从中扣除最后清除后的耗时。原自动评测没有记录最后清除时间。',
            '- LOCAL-RESEARCH 自建模拟器结果，不是官方成绩；默认分布与误差场 profile 关联。',
            '- 保留原实时剩余墙钟时间特征；同一 rank 先测基线再测候选，没有采用交替执行顺序。该条件下的微小差异需谨慎解释。',
            '- 区间使用配对均值正态近似。通过验证集选模不等于在独立测试集上也有显著改善；脚本 final_test.json 中的 recommended_checkpoint 按验证门槛填写，本报告结合测试不确定性仍建议保留原生产基线。',
            '- 本轮测试集用于本次报告，不继续用于选训练轮次或调参。', '',
            '[逐局 CSV](paired_samples.csv) · [详细汇总](summary.json) · [权重与核验记录](manifest.json)', '',
            '![分布对比](comparison.png)']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13,5),dpi=180)
    va=np.array([r['virtual_time_s']/r['N'] for r in a]);vb=np.array([r['virtual_time_s']/r['N'] for r in b]);bins=np.histogram_bin_edges(np.r_[va,vb],bins=50)
    axes[0].hist(va,bins=bins,histtype='step',lw=1.6,label=f'Previous best: {va.mean():.2f}',color='#475569')
    axes[0].hist(vb,bins=bins,histtype='step',lw=1.6,label=f'1h best: {vb.mean():.2f}',color='#ea580c')
    axes[0].set(xlabel='Total virtual seconds / source count',ylabel='Scenarios',title='Q4: 3000 paired scenarios');axes[0].legend()
    axes[1].hist(vb-va,bins=60,color='#2563eb',alpha=.75);axes[1].axvline(0,c='black',ls='--');axes[1].axvline((vb-va).mean(),c='#ea580c',label=f'Mean delta: {(vb-va).mean():.2f}');axes[1].legend()
    axes[1].set(xlabel='New minus previous (s/source); negative is better',ylabel='Scenarios',title='Paired differences; both complete 3000/3000')
    fig.tight_layout()
    for ext in ('png','pdf'):fig.savefig(out/f'comparison.{ext}')
    plt.close(fig)
    print(json.dumps({k:summary[k] for k in ['baseline','candidate','paired']},indent=2))


if __name__=='__main__':main()
