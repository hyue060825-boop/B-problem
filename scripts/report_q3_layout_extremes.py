"""Summarize constructed best/worst layouts, with explicit finite-search scope."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);a=ap.parse_args()
    from _final_paths import require_report_workspace
    require_report_workspace(a.input)
    root=Path(a.input);summary=json.loads((root/'summary.json').read_text());selected=summary['selected']
    raw=[json.loads(x) for x in (root/'samples.jsonl').read_text().splitlines()]
    for n,pair in selected.items():
        complete=[r for r in raw if r['N']==int(n) and r['completion']]
        assert pair['best']['virtual_time_s']==min(r['virtual_time_s'] for r in complete)
        assert pair['worst']['virtual_time_s']==max(r['virtual_time_s'] for r in complete)
    rows=[]
    for n,pair in selected.items():
        for label,r in pair.items():
            rows.append(dict(N=int(n),case=label,total_s=r['virtual_time_s'],last_clear_s=r['last_clear_s'],
                             post_clear_s=r['tail_s'],mode=r['mode'],path_length_m=r['path_length_m'],
                             measures=r['measures'],clear_failures=r['clear_failures'],fixture=r['fixture']))
    with (root/'extremes.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# Q3：10–15 源的有利/不利分布搜索','',
           f"使用原最佳基线 `results/final-20260913/q3_legacy_deadline_20260913/best.pt`。共构造并测评 {summary['total_evaluated']} 个样例，每个源数 {summary['counts_per_N']['10']} 个；失败数 {summary['failures']}。下表为本轮找到的最短/最长总虚拟耗时，不是全局极值的数学证明，也不是随机测试的均值或置信区间。",'',
           '| 源数 | 本轮最短总耗时（秒） | 本轮最长总耗时（秒） | 差值（秒） | 最短样例全部清除时间 | 最长样例全部清除时间 |',
           '|---:|---:|---:|---:|---:|---:|']
    for n,pair in selected.items():
        b,w=pair['best'],pair['worst']
        lines.append(f"| {n} | {b['virtual_time_s']:.2f} | {w['virtual_time_s']:.2f} | {w['virtual_time_s']-b['virtual_time_s']:.2f} | {b['last_clear_s']:.2f} | {w['last_clear_s']:.2f} |")
    lines+=['','总耗时包括发现、定位、清除以及无源确认。全部清除时间单独列出，不包含最后清除后的搜索。最短与最长按总耗时选出，未分别优化全部清除时间。','',
            '## 构造与搜索范围','',
            '- 每个源数固定使用频道 1..N、全部为全向源、1000 米接收半径、零角度误差场；主要改变位置。这样比较的是位置分布的影响，不混入随机换频道、改变源类型数量或误差场的影响。',
            '- 所有源位置在半径 1800 米圆域内，Q3 全部源为全向，保持原参考内核、数值舍入、重合不可见约定及退出证书。源可在不同频道上靠近，使用项目现有约束，没有额外假设最小源间距。',
            '- 8 类初始构造：起点 5 米内聚集、紧密聚集、圆域分散、边缘随机分布、边缘均匀环、三簇、相对双簇、狭长近共线。每类每个源数 64 个，共 512 个/源数。',
            '- 再针对每个源数当前最快和最慢的样例做 4 轮局部搜索，每个端点每轮 24 次位置、整体平移/旋转或固定频道之间的位置交换，增加 192 个/源数。总计 704 个/源数，4224 个候选。',
            '- 搜索固定模型的剩余现实时间特征为 1200 秒，避免 CPU 并行负载干扰路线选择；最终 12 个样例各用原实时特征复跑两次，完成状态和总虚拟耗时均完全复现。',
            '- 只让模拟器使用真实源位置。策略只得到公开历史；checkpoint 没有更新或针对这些样例微调。在线八卡训练不参与本轮权重选择。',
            '- 这不是对所有可能半径、误差场、频道组合及连续位置空间的穷尽搜索。扩大搜索或改变固定条件，可能得到更短或更长的结果；若要确认理论最坏上界，需要另外的算法证明。','',
            '## 具体样例及成本','',
            '| N | 样例 | 构造类型 | 移动距离（米） | 测量次数 | 清除失败次数 | 清完后搜索（秒） |',
            '|---:|---|---|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['N']} | {'最快' if r['case']=='best' else '最慢'} | {r['mode']} | {r['path_length_m']:.1f} | {r['measures']} | {r['clear_failures']} | {r['post_clear_s']:.2f} |")
    lines+=['','起点附近的源能迅速触发 near 并清除，但 N<16 时，未发现频道仍要做完整无源确认，所以总耗时不会接近零。困难分布可能造成晚发现、几何定位困难和多次清除尝试；耗时原因以各样例的请求轨迹为准。','',
            '不同源数的最短/最长值不必单调：源数同时改变空频道数量、观测历史、模型决策和任务路线，本次每个源数也是独立搜索。','',
            '## 可复现文件','']
    for n in selected:
        lines.append(f'- {n} 源：[最短样例](N{n}/best_fixture.json)、[最长样例](N{n}/worst_fixture.json)；同目录的 best_trace.json / worst_trace.json 保存逐请求测评轨迹。')
    lines+=['','- extremes.csv：12 个代表样例的汇总。',
            '- summary.json / samples.jsonl：极值摘要与全部候选测评结果。',
            '- time_extremes.png / .pdf：各源数总耗时范围及清除时间。',
            '- layouts.png / .pdf：12 个代表样例的位置及实际路线。',
            '- manifest.json / search_source.py：固定条件、模型哈希与搜索脚本快照。','',
            '复跑单个样例（输出目录须不存在）：','',
            '```bash',f'./scripts/run_python.sh scripts/search_q3_layout_extremes.py --replay {root}/N10/worst_fixture.json --output {root}/N10_worst_replay','```']
    (root/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    font=next((f.fname for f in font_manager.fontManager.ttflist if f.name=='Noto Sans CJK SC'),None)
    if font:plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
    plt.rcParams['axes.unicode_minus']=False
    ns=np.array([int(n) for n in selected]);fig,axes=plt.subplots(1,2,figsize=(13,5),dpi=180)
    for label,color,name in [('best','#009e73','本轮最短样例'),('worst','#d55e00','本轮最长样例')]:
        axes[0].plot(ns,[selected[str(n)][label]['virtual_time_s'] for n in ns],'-o',color=color,label=name)
        axes[1].plot(ns,[selected[str(n)][label]['last_clear_s'] for n in ns],'-o',color=color,label=name)
    axes[0].set(title='包含无源确认的总完成时间',xlabel='源数 N',ylabel='虚拟秒',xticks=ns)
    axes[1].set(title='同一批代表样例的全部清除时间',xlabel='源数 N',ylabel='虚拟秒',xticks=ns)
    for ax in axes:ax.grid(alpha=.2);ax.legend()
    fig.suptitle('每个源数搜索 704 个候选；本轮极值，非理论上下界');fig.tight_layout()
    for ext in ('png','pdf'):fig.savefig(root/f'time_extremes.{ext}')
    plt.close(fig)
    fig,axes=plt.subplots(6,2,figsize=(12,24),dpi=160)
    theta=np.linspace(0,2*np.pi,241)
    for i,n in enumerate(ns):
        for j,label in enumerate(('best','worst')):
            ax=axes[i,j];r=selected[str(n)][label]
            case=json.loads((root/f'N{n}/{label}_fixture.json').read_text());trace=json.loads((root/f'N{n}/{label}_trace.json').read_text())
            route=np.array([(0,0)]+[e['position'] for e in trace['events'] if e['position'] is not None])
            ax.plot(route[:,0],route[:,1],color='#aab2bc',lw=.7,alpha=.6)
            ax.plot(1800*np.cos(theta),1800*np.sin(theta),'--',color='#64748b',lw=.8)
            for s in case['scenario']['sources']:
                ax.scatter(s['x'],s['y'],s=22,c='#d55e00' if s['kind']=='directional' else '#0072b2',zorder=3)
                if s['heading'] is not None:
                    angle=np.radians(s['heading']);ax.arrow(s['x'],s['y'],180*np.cos(angle),180*np.sin(angle),width=6,head_width=55,color='#d55e00',length_includes_head=True,zorder=4)
            ax.scatter(0,0,marker='x',c='black',s=35,zorder=5)
            ax.set(aspect='equal',xlim=(-2850,2850),ylim=(-2850,2850),title=f"{n} 源 · {'最短' if label=='best' else '最长'} {r['virtual_time_s']:.1f} 秒\n{r['mode']}")
            ax.grid(alpha=.15)
    fig.suptitle('蓝色为全向源；黑叉为起点，灰线为实际路线，虚线为源位置边界',fontsize=12)
    fig.tight_layout(rect=(0,0,1,.985))
    for ext in ('png','pdf'):fig.savefig(root/f'layouts.{ext}')
    plt.close(fig)
    print('\n'.join(lines[:14]))


if __name__=='__main__':main()
