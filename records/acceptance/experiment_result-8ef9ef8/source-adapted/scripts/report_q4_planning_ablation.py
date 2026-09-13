"""Paired statistics and plots for the preregistered four-arm Q4 experiment."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

VARIANTS = ('baseline', 'route', 'schedule', 'combined')
LABELS = {'baseline': 'A 当前基线', 'route': 'B 仅覆盖路线',
          'schedule': 'C 仅清除调度', 'combined': 'D 路线＋调度'}
ENGLISH = ['A Baseline', 'B Coverage route', 'C Clear scheduling', 'D Combined']


def aggregate(rows):
    result = dict(episodes=len(rows), completed=sum(r['completion'] for r in rows),
                  errors=dict(Counter(r['error'] or 'incomplete' for r in rows if not r['completion'])))
    for key in ('virtual_time_s', 'last_discovery_s', 'last_clear_s', 'tail_s',
                'all_move_s', 'all_measure_s', 'all_switch_s', 'all_clear_s',
                'path_length_m', 'clear_failures', 'measures', 'overrides',
                'scheduling_overrides', 'route_overrides', 'elapsed_s'):
        result[key] = float(np.mean([r[key] for r in rows]))
    times = [r['virtual_time_s'] for r in rows]
    result['median_s'] = float(np.median(times))
    result['p95_s'] = float(np.percentile(times, 95))
    result['mean_t_per_n_s'] = float(np.mean([r['virtual_time_s']/r['N'] for r in rows]))
    result['all_cleared_by_6000'] = sum(r['all_cleared_by_6000'] for r in rows)
    result['late_discovery_episodes'] = sum(r['after6000_discovery_count'] > 0 for r in rows)
    result['max_decision_s'] = max(r['decision_max_s'] for r in rows)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    a = p.parse_args()
    out = Path(a.input)
    manifest = json.loads((out/'manifest.json').read_text())
    status = json.loads((out/'status.json').read_text())
    assert status['status'] == 'COMPLETE'
    rows = [json.loads(line) for line in (out/'samples.jsonl').read_text().splitlines()]
    groups = {v: sorted([r for r in rows if r['variant'] == v], key=lambda r:r['seed']) for v in VARIANTS}
    n = manifest['episodes_per_variant']
    assert len(rows) == n*4
    for v in VARIANTS:
        assert len(groups[v]) == n and len({r['seed'] for r in groups[v]}) == n
        assert [(r['seed'], r['scenario_sha256'], r['N']) for r in groups[v]] == [(r['seed'], r['scenario_sha256'], r['N']) for r in groups['baseline']]
    times = np.asarray([[r['virtual_time_s'] for r in groups[v]] for v in VARIANTS]).T
    counts = np.asarray([r['N'] for r in groups['baseline']])
    deltas = times[:,1:] - times[:,0,None]
    rng = np.random.default_rng(20260913)
    boots = []
    per_boots = []
    interaction_boots = []
    interaction = times[:,3] - times[:,1] - times[:,2] + times[:,0]
    for _ in range(40):
        indices = rng.integers(0, n, (100,n))
        boots.append(deltas[indices].mean(axis=1))
        per_boots.append((deltas/counts[:,None])[indices].mean(axis=1))
        interaction_boots.append(interaction[indices].mean(axis=1))
    boots, per_boots = np.concatenate(boots), np.concatenate(per_boots)
    summary = {v: aggregate(groups[v]) for v in VARIANTS}
    for i,v in enumerate(VARIANTS[1:]):
        d = deltas[:,i]
        summary[v]['vs_baseline'] = dict(
            delta_s=float(d.mean()), reduction_pct=float(-100*d.mean()/times[:,0].mean()),
            ci95_s=np.percentile(boots[:,i],[2.5,97.5]).tolist(),
            bonferroni_ci98_33_s=np.percentile(boots[:,i],[100*.05/6,100*(1-.05/6)]).tolist(),
            faster=int((d < -1e-6).sum()), tied=int((abs(d)<=1e-6).sum()), slower=int((d>1e-6).sum()),
            delta_t_per_n_s=float((d/counts).mean()),
            ci95_t_per_n_s=np.percentile(per_boots[:,i],[2.5,97.5]).tolist(),
            max_regression_s=float(d.max()), max_improvement_s=float(d.min()),
            eligible=summary[v]['completed']==summary['baseline']['completed']==n)
    strata = {}
    for key in ('N', 'distribution'):
        get = (lambda r: r['N']) if key=='N' else (lambda r:r['profile']['distribution'])
        strata[key] = {}
        for value in sorted({get(r) for r in groups['baseline']}):
            selected = {v:[r for r in groups[v] if get(r)==value] for v in VARIANTS}
            strata[key][str(value)] = {v:aggregate(selected[v]) for v in VARIANTS}
    result = dict(groups=summary, strata=strata,
                  interaction=dict(mean_s=float(interaction.mean()), ci95_s=np.percentile(np.concatenate(interaction_boots),[2.5,97.5]).tolist()),
                  bootstrap=dict(replicates=4000,seed=20260913,paired=True,positive_delta='worse'),
                  validation=dict(paired_scenarios=n, matched_hashes=True, total_episodes=len(rows),
                                  failures=sum(not r['completion'] for r in rows)))
    supported = [v for v in VARIANTS[1:] if summary[v]['vs_baseline']['eligible']
                 and summary[v]['vs_baseline']['bonferroni_ci98_33_s'][1] < 0]
    result['supported_improvements'] = supported
    (out/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    lines = [
        '# Q4 固定 best checkpoint：四组规划对照', '',
        f'四组各 {n} 局，共 {n*4} 局。所有组使用同一权重，完成后没有根据正式测试结果调整参数或重新训练。', '',
        ('结论：' + '、'.join(LABELS[v] for v in supported) + '在保持完成率的前提下显著降低平均总耗时。'
         if supported else '结论：本轮三种规划干预均未证明优于当前基线，继续保留原 best 和原部署规划。此结果针对本次具体启发式实现，不代表路线或调度方向没有优化空间。'), '',
        '| 组别 | 完成数 | 平均总耗时（秒） | 平均每源 T/N（秒） | P95 总耗时（秒） | 相对 A 的总耗时变化 | 配对变化 95% CI（秒） |',
        '|---|---:|---:|---:|---:|---:|---|',
    ]
    for v in VARIANTS:
        r=summary[v];d=r.get('vs_baseline')
        change='—' if d is None else f"{d['delta_s']:+.2f} 秒（{-d['reduction_pct']:+.2f}%）"
        ci='—' if d is None else f"[{d['ci95_s'][0]:+.2f}, {d['ci95_s'][1]:+.2f}]"
        lines.append(f"| {LABELS[v]} | {r['completed']}/{n} | {r['virtual_time_s']:.2f} | {r['mean_t_per_n_s']:.2f} | {r['p95_s']:.2f} | {change} | {ci} |")
    lines += ['', '变化为候选减基线，负数表示更快。T/N 先逐局计算再平均。失败局保留并单独计数；完成率未保持的版本不能仅凭耗时更短获胜。', '',
              '## 实现边界与公平性', '',
              f"- 权重：`{manifest['checkpoint']}`；SHA256 `{manifest['checkpoint_sha256']}`。",
              '- A：原模型选择原控制器候选，不附加规划干预。',
              '- B：仅当原模型选择 COVER 时，对全部未访问站点比较“模型首站”和“最近首站”两种初始路线，各做最多 12 次开放路径 2-opt 改进，执行较短路线首站。允许选择原来最近三个候选之外的合法认证站点；保持原扫描频道规则。',
              '- C：仅当原模型选择 COVER 时，以原模型首站及随后最近邻顺序构成覆盖路线；将已有合法 CLEAR 动作按最小额外路程插入，保持覆盖站点相对顺序。执行首项；只有首项为 CLEAR 时才覆盖模型原决定。',
              '- D：先按 B 优化覆盖顺序，再按 C 插入安全清除任务。',
              '- 所有组保留原定位、PROBE_CLEAR、测量/清除成本、31 站点证书、发现满 16 源的上限推理、退出条件及 400 宏动作预算。规划器只接收公开控制器状态和合法候选，不读取场景真值、隐藏源数或未来观测。',
              '- 清除任务仅来自原控制器已生成的安全 CLEAR 候选，并由原 execute 再次验证证书。执行一次任务后重新规划，不提前推进覆盖状态。',
              f"- 共同场景种子 {manifest['seed_start']}–{manifest['seed_start']+n-1}；每局四组场景 SHA256 核验一致。场景采用现有研究生成器默认 profile，不宣称等同官方分布。",
              '- 主实验把四组模型的剩余现实时间特征统一固定为 1200 秒，以避免额外规划耗时和 CPU 调度通过输入特征混入虚拟路线比较；这是受控离线实验，不等同完整官方部署测评。实际墙钟耗时另行记录。',
              '- 四组由同一 CPU 推理实现执行，32 个 worker 并行场景；本实验不更新参数，未进行 GPU 训练。权重、冻结运行时及算法源文件均在评测前后核验哈希；源代码快照与 manifest 已保存。',
              '- 独立 smoke 使用种子 1712000000–1712000127，共 512 局全部完成。另抽查 32 个旧评测场景，原实时特征和固定时间特征的基线总耗时均与旧记录一致。smoke 后没有根据收益调参。',
              '', '## 配对胜负与多重比较', '',
              '| 候选 | 更快 | 持平 | 更慢 | 三项比较 Bonferroni 调整区间（秒） |',
              '|---|---:|---:|---:|---|']
    for v in VARIANTS[1:]:
        d=summary[v]['vs_baseline'];ci=d['bonferroni_ci98_33_s']
        lines.append(f"| {LABELS[v]} | {d['faster']} | {d['tied']} | {d['slower']} | [{ci[0]:+.2f}, {ci[1]:+.2f}] |")
    lines += ['', '置信区间由 4000 次按场景配对 bootstrap 得到；同时展示普通 95% 区间和针对三项主比较的 98.33% 百分位区间。分层结果用于解释，不作为进一步挑选参数的验证集。', '',
              '## 按源数的平均总耗时', '',
              '| N | 样例数/组 | A 基线 | B 路线 | C 调度 | D 组合 |',
              '|---:|---:|---:|---:|---:|---:|']
    for k,g in strata['N'].items():
        lines.append(f"| {k} | {g['baseline']['episodes']} | " + ' | '.join(f"{g[v]['virtual_time_s']:.1f}" for v in VARIANTS)+' |')
    lines += ['', '## 按联合场景的平均总耗时', '',
              '| 场景 | 样例数/组 | A 基线 | B 路线 | C 调度 | D 组合 |',
              '|---|---:|---:|---:|---:|---:|']
    for k,g in strata['distribution'].items():
        lines.append(f"| {k} | {g['baseline']['episodes']} | " + ' | '.join(f"{g[v]['virtual_time_s']:.1f}" for v in VARIANTS)+' |')
    lines += ['', '默认 profile 为 area/smooth、edge/extreme、cluster/smooth、outward/zero。它们联合改变位置分布与场强模式，不能将组间差异全部归因于空间分布。', '',
              '## 动作成本与发现/清除里程碑', '',
              '| 组别 | 平均全部发现 F | 平均全部清除 C | 平均清除后收尾 H | 移动秒 | 测量秒 | 换频秒 | 清除秒（含失败） |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for v in VARIANTS:
        r=summary[v]
        lines.append('| '+LABELS[v]+' | '+' | '.join(f'{r[k]:.1f}' for k in ('last_discovery_s','last_clear_s','tail_s','all_move_s','all_measure_s','all_switch_s','all_clear_s'))+' |')
    lines += ['', 'F 是每个真实频道首次出现正信号的最晚时间，不等于精确定位。H=T−C，只计算最后一次清除后的收尾，不包含穿插的空频道覆盖；提前清除可能增大 H，因此不能单独把 H 下降当作性能提升。', '',
              '| 组别 | 平均测量次数 | 平均清除失败次数 | 平均覆盖站点改选次数 | 平均插入清除次数 | 平均每局现实耗时（秒） |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for v in VARIANTS:
        r=summary[v]
        lines.append('| '+LABELS[v]+' | '+' | '.join(f'{r[k]:.3f}' for k in ('measures','clear_failures','route_overrides','scheduling_overrides','elapsed_s'))+' |')
    b, route, schedule = summary['baseline'], summary['route'], summary['schedule']
    lines += ['', '现实耗时包含同机多 worker 争用，不能直接当作 Windows 单局推理性能。算法改变访问顺序后会改变信号、几何定位和模型后续选择，即使每次静态覆盖路线变短，整局总耗时也未必下降。', '',
              '## 对本轮结果的解释', '',
              f"B 相对 A 的平均全部发现时间变化为 {route['last_discovery_s']-b['last_discovery_s']:+.1f} 秒；总测量次数变化 {route['measures']-b['measures']:+.1f} 次。成本变化分别为移动 {route['all_move_s']-b['all_move_s']:+.1f} 秒、测量 {route['all_measure_s']-b['all_measure_s']:+.1f} 秒、换频 {route['all_switch_s']-b['all_switch_s']:+.1f} 秒、清除 {route['all_clear_s']-b['all_clear_s']:+.1f} 秒。",
              '静态路线目标仅计算走完剩余认证站点的路程，没有计算访问顺序对提前发现源、交叉定位、后续测量次数、以及发现满 16 源后免除剩余覆盖的影响。所有组使用同一权重，但 B/D 改变了后续观测历史，固定模型因此也会做出不同决策。上述成本和里程碑变化支持“静态路程目标与整局搜索目标不一致”的解释，不能仅凭静态 2-opt 路程下降就推断整局变快。',
              f"C 相对 A 的平均最后清除时间变化为 {schedule['last_clear_s']-b['last_clear_s']:+.1f} 秒，清除后收尾变化为 {schedule['tail_s']-b['tail_s']:+.1f} 秒；平均总耗时变化为 {schedule['virtual_time_s']-b['virtual_time_s']:+.1f} 秒。将清除提前不自动消除覆盖证书成本，必须检查整体路程及任务顺序。",
              '下一步更合理的研究是让覆盖候选同时考虑公开观测能够推断的信息收益、定位收益及剩余证书成本，并限制对已训练策略早期搜索顺序的干预；安全清除插入仍需比较完整任务路线成本。后续设计与训练应使用新的训练/验证集，不继续在这 3000 个正式场景上挑参数，再用另一批独立样例确认。', '',
              '## 产物', '',
              '- `samples.csv` / `samples.jsonl`：四组全部逐局记录。',
              '- `summary.json`：配对区间、源数和联合场景分层、成本分解。',
              '- `comparison.png` / `comparison.pdf`：四组耗时分布、源数分层、成本里程碑和场景差异。',
              '- `manifest.json` / `source/`：冻结参数、权重哈希、算法及评测代码快照。',
              '- 原 best 权重和官方部署运行时未被本实验替换。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = ['#475569','#e68613','#009e73','#6558c7']
    fig, axes = plt.subplots(2,2,figsize=(14,10),dpi=180)
    for i,v in enumerate(VARIANTS):
        t=np.sort(times[:,i]);axes[0,0].plot(t,np.arange(1,n+1)/n,label=ENGLISH[i],c=colors[i])
        keys=list(strata['N']);axes[0,1].plot([int(k) for k in keys],[strata['N'][k][v]['virtual_time_s'] for k in keys],marker='o',label=ENGLISH[i],c=colors[i])
    axes[0,0].set(xlabel='Total virtual seconds',ylabel='Fraction of scenarios',title=f'Paired {n} scenarios per arm')
    axes[0,1].set(xlabel='Source count N',ylabel='Mean total virtual seconds',title='Source-count strata')
    axes[0,0].legend(fontsize=8);axes[0,1].legend(fontsize=8)
    axes[1,0].bar(ENGLISH,[summary[v]['last_clear_s'] for v in VARIANTS],label='Before last clear',color='#4c78a8')
    axes[1,0].bar(ENGLISH,[summary[v]['tail_s'] for v in VARIANTS],bottom=[summary[v]['last_clear_s'] for v in VARIANTS],label='After last clear',color='#f2a541')
    axes[1,0].set(ylabel='Mean virtual seconds',title='Completion time, including post-clear tail');axes[1,0].legend(fontsize=8);axes[1,0].tick_params(axis='x',labelsize=8)
    ds=list(strata['distribution']);x=np.arange(len(ds))
    for i,v in enumerate(VARIANTS[1:]):
        axes[1,1].bar(x+(i-1)*.25,[strata['distribution'][d][v]['virtual_time_s']-strata['distribution'][d]['baseline']['virtual_time_s'] for d in ds],width=.25,color=colors[i+1],label=ENGLISH[i+1])
    axes[1,1].axhline(0,c='gray',lw=1);axes[1,1].set(xticks=x,xticklabels=ds,ylabel='Mean delta vs A (virtual seconds)',title='Joint profiles; negative is better');axes[1,1].legend(fontsize=8)
    for ax in axes.flat:ax.grid(axis='y',alpha=.18)
    fig.tight_layout();fig.savefig(out/'comparison.png');fig.savefig(out/'comparison.pdf');plt.close(fig)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
