#!/usr/bin/env python3
"""从已归档数据生成 handoff 表格和中文图件；不训练、不修改原始结果。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('MPLCONFIGDIR', '/tmp/b-problem-handoff-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, Polygon as PlotPolygon
import numpy as np

from solution.coverage.certificates import omni_skeleton, check_omni_parameters, triangular_grid
from solution.geometry.core import FeasibleRegion

LATEST = 'results/training/import-3ddb2d9/runs/q34_3000_test_20260912'
JOINT = 'results/training/import-3ddb2d9/runs/q3_joint_20260912'
BUDGET = 'results/training/import-3ddb2d9/runs/q4_budget_20260912/train'
Q1 = 'results/validation/import-c457828/artifacts/q1'
Q2 = 'results/validation/import-c457828/artifacts/q2/example'
FIG = ROOT / 'handoff/figures'
TABLE = ROOT / 'handoff/tables'
BLUE, ORANGE, TEAL, INK, GRAY = '#2563a6', '#c76824', '#17847c', '#243449', '#738296'
INPUTS: dict[str, dict] = {}
FIGURES: list[dict] = []


def bind(path: str | Path) -> Path:
    p = ROOT / path
    INPUTS[p.relative_to(ROOT).as_posix()] = {
        'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    return p


def read(path: str | Path):
    return json.loads(bind(path).read_text(encoding='utf-8'))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n',encoding='utf-8')


def write_csv(name: str, rows: list[dict]):
    if not rows:
        raise ValueError(f'empty table: {name}')
    with (TABLE / name).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def mean_ci(values):
    x = np.asarray(values, dtype=float)
    mu = float(np.mean(x))
    half = float(1.96 * np.std(x, ddof=1) / math.sqrt(len(x))) if len(x) > 1 else 0.
    return mu, half


def prepare_tables():
    TABLE.mkdir(parents=True, exist_ok=True)
    groups = {name: read(f'{LATEST}/{name}_samples.json') for name in
              ('q3_baseline', 'q3_candidate', 'q4_baseline', 'q4_best')}
    manifest = read(f'{LATEST}/manifest.json')
    for name, record in manifest['checkpoints'].items():
        checkpoint=bind('results/training/import-3ddb2d9/'+record['path'])
        assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==record['sha256'], name
    # 严格按种子配对，并核对每局指标；不凭汇总文件重画结果。
    summaries, paired, strata = [], [], []
    for name, rows in groups.items():
        assert len(rows) == 3000 and len({r['seed'] for r in rows}) == len(rows)
        for r in rows:
            assert r['completion'] and r['C'] == r['N'] and r['error'] is None
            assert math.isclose(r['time_per_clear_s'], r['virtual_time_s'] / r['C'], rel_tol=1e-12)
        t = np.array([r['virtual_time_s'] for r in rows])
        per = np.array([r['time_per_clear_s'] for r in rows])
        summaries.append(dict(model=name, problem=rows[0]['problem'], episodes=len(rows),
                              completed=sum(r['completion'] for r in rows),
                              mean_virtual_s=float(t.mean()), mean_per_source_s=float(per.mean()),
                              weighted_per_source_s=float(t.sum()/sum(r['C'] for r in rows)),
                              median_per_source_s=float(np.median(per)), p95_per_source_s=float(np.quantile(per,.95)),
                              max_virtual_s=float(t.max()), source=f'{LATEST}/{name}_samples.json'))
    for problem, candidate in ((3, 'q3_candidate'), (4, 'q4_best')):
        old = {r['seed']: r for r in groups[f'q{problem}_baseline']}
        new = {r['seed']: r for r in groups[candidate]}
        assert old.keys() == new.keys()
        rows = []
        for seed in sorted(old):
            a,b = old[seed],new[seed]
            assert a['N'] == b['N'] and a['profile'] == b['profile']
            rows.append(dict(seed=seed, N=a['N'], distribution=a['profile']['distribution'],
                             field=a['profile']['field'], old=a['virtual_time_s'], new=b['virtual_time_s'],
                             delta=b['virtual_time_s']-a['virtual_time_s'],
                             delta_per=b['time_per_clear_s']-a['time_per_clear_s']))
        delta, half = mean_ci([r['delta'] for r in rows])
        delta_per, half_per = mean_ci([r['delta_per'] for r in rows])
        base_per = np.mean([r['old']/r['N'] for r in rows])
        paired.append(dict(problem=problem, baseline=f'q{problem}_baseline', candidate=candidate, pairs=len(rows),
                           mean_delta_virtual_s=delta, ci95_low_s=delta-half, ci95_high_s=delta+half,
                           reduction_mean_virtual_percent=-100*delta/np.mean([r['old'] for r in rows]),
                           mean_delta_per_source_s=delta_per, ci95_low_per_source_s=delta_per-half_per,
                           ci95_high_per_source_s=delta_per+half_per,
                           reduction_mean_per_source_percent=-100*delta_per/base_per,
                           faster=sum(r['delta'] < 0 for r in rows), tied=sum(r['delta'] == 0 for r in rows),
                           slower=sum(r['delta'] > 0 for r in rows)))
        for dimension in ('N', 'distribution'):
            for value in sorted({r[dimension] for r in rows}):
                selected = [r for r in rows if r[dimension] == value]
                mu,h = mean_ci([r['delta'] for r in selected])
                mp,hp = mean_ci([r['delta_per'] for r in selected])
                strata.append(dict(problem=problem, dimension=dimension, group=value, pairs=len(selected),
                                   mean_delta_virtual_s=mu, ci95_low_s=mu-h, ci95_high_s=mu+h,
                                   mean_delta_per_source_s=mp, ci95_low_per_source_s=mp-hp,
                                   ci95_high_per_source_s=mp+hp))
    write_csv('q34_summary.csv', summaries)
    write_csv('q34_paired.csv', paired)
    write_csv('q34_strata.csv', strata)

    q1 = {name:read(f'{Q1}/{name}/result.json') for name in ('crossing','triangle')}
    write_csv('q1_examples.csv', [dict(case=k,kind=v['kind'],diameter_m=v['diameter_m'],
                 diameter_circle_covers=v['diameter_circle_covers'],mec_radius_m=v['mec']['radius_m'],
                 source=f'{Q1}/{k}/result.json') for k,v in q1.items()])
    q2 = read(f'{Q2}/result.json')
    q2_input = read(f'{Q2}/input.json')
    comparisons = {'best_evaluated':q2['best'], **q2['comparisons']}
    write_csv('q2_comparison.csv', [dict(name=k,x_m=v['position'][0],y_m=v['position'][1],
                 receive_bound_m=v['receive_bound_m'],sampled_posterior_radius_m=v['posterior_radius_m'],
                 estimated_remaining_s=v['remaining_time_s'],score_J_s=v['J_s'],
                 source=f'{Q2}/result.json') for k,v in comparisons.items()])
    write_csv('q2_candidates.csv', [dict(index=i,x_m=v['position'][0],y_m=v['position'][1],
                 guaranteed_receive=v['guaranteed_receive'],score_J_s=v.get('J_s'),
                 sampled_posterior_radius_m=v.get('posterior_radius_m')) for i,v in enumerate(q2['candidates'])])
    bind('src/solution/coverage/certificates.py')
    bind('src/solution/geometry/core.py')
    bind('src/solution/planning/q2.py')
    write_csv('q3_coverage_parameters.csv', [{k:v for k,v in r.items() if k!='points'} for r in check_omni_parameters()])
    grid = triangular_grid()
    assert grid['triangle_count'] == 42 and grid['vertex_count'] == 31
    assert grid['continuous_domain_covered'] and grid['diameter_checks']
    write_json(TABLE/'q4_grid.json',grid)

    monitor=[]
    for problem, folder, stage in ((3,f'{JOINT}/ppo','q3_joint_ppo'),(4,BUDGET,'q4_budget_ppo')):
        for p in sorted((ROOT/folder).glob('validation_*.json')):
            data=read(p.relative_to(ROOT))
            comparison=data.get('comparison',data)
            rows=data['rows']
            monitor.append(dict(problem=problem,stage=stage,update=int(p.stem.split('_')[-1]),
                                validation_episodes=len(rows),completion_rate=sum(r['completion'] for r in rows)/len(rows),
                                mean_virtual_s=float(np.mean([r['virtual_time_s'] for r in rows])),
                                mean_delta_virtual_s=comparison['mean_delta_s'],
                                ci95_halfwidth_s=comparison['ci95_halfwidth_s'],source=p.relative_to(ROOT).as_posix()))
    write_csv('training_validation.csv',monitor)
    return dict(groups=groups,summaries=summaries,paired=paired,strata=strata,q1=q1,q2=q2,
                q2_input=q2_input,grid=grid,monitor=monitor)


def style():
    names={f.name for f in font_manager.fontManager.ttflist}
    chosen=next((n for n in ('Noto Sans CJK SC','WenQuanYi Zen Hei','Droid Sans Fallback') if n in names),None)
    if chosen is None:
        raise RuntimeError('请安装中文字体 Noto Sans CJK SC 或文泉驿正黑后重绘。')
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':[chosen,'DejaVu Sans'],
                        'font.size':10,'font.weight':500,'axes.titleweight':500,'axes.labelweight':500,
                        'axes.titlesize':11,'axes.labelsize':10,
                        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':GRAY,
                        'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK,
                        'axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'none',
                        'savefig.facecolor':'white','figure.facecolor':'white','svg.hashsalt':'b-problem-handoff-v1'})


def register(number,slug,title,message,required,relationship,sources,archetype='Results / Diagnostics',avoid='',backend='Python / Matplotlib'):
    for path in sources:
        if (ROOT/path).is_file():bind(path)
    item=dict(id=f'F{number:03}',slug=slug,title=title,message=message,required=required,
              relationship=relationship,sources=sources,archetype=archetype,avoid=avoid,backend=backend)
    FIGURES.append(item)
    return f'{item["id"]}-{slug}'


def save(fig,stem):
    fig.savefig(FIG/f'{stem}.pdf',bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None})
    fig.savefig(FIG/f'{stem}.svg',bbox_inches='tight',metadata={'Date':None})
    svg = FIG/f'{stem}.svg'
    # 保留路径中的换行分隔，清除导出器附带的行末空格。
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    fig.savefig(FIG/f'{stem}.png',dpi=260,bbox_inches='tight')
    plt.close(fig)


def polygon(ax,vertices,**kwargs):
    ax.add_patch(PlotPolygon(np.asarray(vertices),closed=True,**kwargs))


def xy_axes(ax):
    ax.set_aspect('equal');ax.set_xlabel('东向坐标 x / m');ax.set_ylabel('北向坐标 y / m')
    ax.grid(alpha=.14,zorder=0)


def draw_geometry(d):
    stem=register(2,'q1-diameter-circle','Q1：直径圆与最小包围圆',
                  '合法测向交会区域的直径圆不一定覆盖整个区域。',
                  ['等边三角形可行域','直径圆与最小包围圆','直径 40.00 m、最小包围圆半径 23.094 m'],
                  '两个圆与同一个可行域作几何覆盖比较。',[f'{Q1}/triangle/result.json',f'{Q1}/triangle/input.json'],
                  archetype='Comparison',avoid='人工算例不是官方测试；两圆不是两种测量误差分布。')
    data=d['q1']['triangle'];fig,ax=plt.subplots(figsize=(5.6,4.5),layout='constrained')
    polygon(ax,data['vertices'],facecolor=TEAL,alpha=.12,edgecolor=TEAL,lw=1.6,label='测向交会区域')
    ax.add_patch(Circle(data['diameter_circle_center'],data['diameter_m']/2,fill=False,
                        edgecolor=ORANGE,ls='--',lw=1.8,label='直径圆（不能完整覆盖）'))
    ax.add_patch(Circle(data['mec']['center'],data['mec']['radius_m'],fill=False,
                        edgecolor=BLUE,lw=1.8,label='最小包围圆'))
    v=np.array(data['vertices']);ax.scatter(v[:,0],v[:,1],c=INK,s=24,zorder=4)
    ax.scatter(*data['mec']['center'],marker='+',c=BLUE,s=90,zorder=5)
    ax.plot(*np.array(data['farthest_pair']).T,color=ORANGE,lw=1.5)
    ax.text(20,-5,'直径 = 40.00 m',ha='center',fontsize=10)
    ax.plot([20,20],[data['mec']['center'][1],34.6410161514],c=BLUE,ls=':',lw=1)
    ax.annotate('半径 = 23.094 m',xy=(20,27),xytext=(47,37),ha='right',fontsize=10,
                arrowprops=dict(arrowstyle='-',color=BLUE))
    ax.set_xlim(-9,49);ax.set_ylim(-23,42);xy_axes(ax)
    ax.legend(loc='lower center',bbox_to_anchor=(.5,1.01),frameon=False,fontsize=9)
    save(fig,stem)


def draw_q2(d):
    stem=register(3,'q2-candidates','Q2：保证接收区域与候选点评分',
                  '先保证再次接收，再在有限候选点中权衡移动和估计定位代价。',
                  ['首次观测可行域','保证接收内近似','实际候选点及 J 值','最佳已评估点与 J≤最小值+10 s 的候选'],
                  '候选位于保证接收区域中，颜色只编码有限情景的综合评分。',
                  [f'{Q2}/input.json',f'{Q2}/result.json','src/solution/planning/q2.py'],
                  avoid='不画虚构的第二次观测后验；不插值成未经评估的连续热力面。')
    result=d['q2'];inp=d['q2_input'];region=FeasibleRegion(inp.get('epsilon_impl_deg',1.01));region.direction(inp['position'],inp['svd_deg'])
    fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
    polygon(ax,result['receive_polygon'],facecolor=TEAL,alpha=.1,edgecolor=TEAL,lw=1.5,label='保证接收区域（内近似）')
    polygon(ax,region.vertices,facecolor=ORANGE,alpha=.17,edgecolor=ORANGE,lw=1.4,label='首次观测可行域')
    cs=[c for c in result['candidates'] if c['guaranteed_receive']]
    v=np.array([c['position'] for c in cs]);js=np.array([c['J_s'] for c in cs]);good=js<=result['best']['J_s']+10
    dots=ax.scatter(v[:,0],v[:,1],c=js,cmap='viridis_r',s=24,zorder=3)
    ax.scatter(v[good,0],v[good,1],facecolors='none',edgecolors=ORANGE,s=62,lw=.9,zorder=4,label='评分 ≤ 最小值 + 10 s')
    ax.scatter(*result['best']['position'],marker='*',s=170,c=ORANGE,edgecolors='white',lw=.8,zorder=5,label='最佳已评估点')
    best_x,best_y=result['best']['position']
    ax.annotate(f'({best_x:.2f}, {best_y:.2f}) m',xy=result['best']['position'],xytext=(1090,435),fontsize=9,
                ha='center',arrowprops=dict(arrowstyle='-',color=ORANGE,lw=.9))
    ax.scatter(*inp['position'],marker='x',s=45,c=INK,zorder=4)
    ax.annotate('首次检测点',xy=inp['position'],xytext=(25,95),fontsize=9)
    ax.set_xlim(-70,1560);ax.set_ylim(-790,790);xy_axes(ax)
    fig.colorbar(dots,ax=ax,shrink=.78,label='有限情景评分 J / s')
    ax.legend(loc='upper left',fontsize=8.4,frameon=False)
    save(fig,stem)


def draw_coverage(d):
    stem=register(4,'q3-coverage','Q3：七站覆盖结构',
                  '中心和六个外圈站点的保守接收圆覆盖整个目标圆域。',
                  ['目标圆半径 1800 m','7 个站点','外圈半径 1135 m','保守接收半径 999.98 m'],
                  '目标圆被站点接收圆的并集覆盖，不表示实际访问顺序。',
                  ['src/solution/coverage/certificates.py','handoff/tables/q3_coverage_parameters.csv'],
                  archetype='Method Overview',avoid='不将示意站点连线称为最优路线。')
    points,cert=omni_skeleton();fig,ax=plt.subplots(figsize=(5.8,5.0),layout='constrained')
    for i,(key,p) in enumerate(points.items()):
        ax.add_patch(Circle(p,999.98,facecolor=TEAL,alpha=.06,edgecolor='none'))
        ax.add_patch(Circle(p,999.98,fill=False,edgecolor=TEAL,alpha=.55,lw=.8,
                            label='站点保守接收范围' if i==0 else None))
        ax.scatter(*p,c=TEAL,s=30,zorder=4)
        ax.annotate(f'S{i}',p,xytext=(7,5),textcoords='offset points',fontsize=9)
    ax.add_patch(Circle((0,0),1800,fill=False,edgecolor=INK,lw=1.6,label='目标圆（半径 1800 m）'))
    ax.plot([0,1135],[0,0],color=ORANGE,ls='--',lw=1.2)
    ax.text(560,-135,'1135 m',ha='center',fontsize=9,color=ORANGE)
    ax.set_xlim(-2300,2300);ax.set_ylim(-2250,2400);xy_axes(ax)
    ax.set_title(f'覆盖距离上界 {cert.max_distance_m:.2f} m < 999.98 m',pad=11)
    ax.legend(loc='lower center',bbox_to_anchor=(.5,-.26),ncol=2,frameon=False,fontsize=9)
    save(fig,stem)

    stem=register(5,'q4-directional-coverage','Q4：三角网格与定向发现依据',
                  '覆盖目标圆的三角网格中，每个普通内部点在任意闭发射半平面内至少有一个三角形顶点。',
                  ['42 个三角形、31 个站点','网格边长 995 m','目标圆半径 1800 m','半平面与三角形内部点的凸组合示意'],
                  '左侧展示完整网格，右侧解释非重合位置的局部发现依据；重合位置由六邻点补证。',
                  ['src/solution/coverage/certificates.py','handoff/tables/q4_grid.json'],
                  archetype='Mechanism',avoid='右侧为数学示意，不是已运行的干扰源场景；不能把一次无信号当圆盘排除。')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(7.4,4.1),gridspec_kw={'width_ratios':[1.2,1]},layout='constrained')
    for t in d['grid']['triangles']:polygon(ax,t,fill=False,edgecolor='#b2c8c6',lw=.65)
    v=np.array(d['grid']['vertices']);ax.scatter(v[:,0],v[:,1],c=TEAL,s=15,zorder=4)
    ax.add_patch(Circle((0,0),1800,fill=False,edgecolor=INK,lw=1.4))
    ax.set_xlim(v[:,0].min()-220,v[:,0].max()+220);ax.set_ylim(v[:,1].min()-220,v[:,1].max()+220);xy_axes(ax)
    ax.set_xticks([-2000,0,2000]);ax.set_yticks([-2000,0,2000]);ax.set_title('(a) 42 个三角形 · 31 个站点')
    ax.set_xlabel('东向坐标 x / m\n边长 995 m；目标圆半径 1800 m',fontsize=9)
    tri=np.array([[0,0],[1,0],[.5,math.sqrt(3)/2]]);x=np.array([.36,.23])
    bx.axvspan(x[0],1.14,facecolor=TEAL,alpha=.12)
    bx.axvline(x[0],color=TEAL,ls='--',lw=1)
    polygon(bx,tri,fill=False,edgecolor=GRAY,lw=1.3)
    bx.scatter(tri[:,0],tri[:,1],c=[GRAY,TEAL,TEAL],s=35,zorder=4)
    for i,p in enumerate(tri):bx.annotate(f'v{i+1}',p,xytext=(2,7),textcoords='offset points',fontsize=10)
    bx.scatter(*x,c=ORANGE,s=35,zorder=5);bx.text(x[0]-.12,x[1]-.06,'x',fontsize=12,color=ORANGE)
    for p in tri:bx.plot([x[0],p[0]],[x[1],p[1]],color=GRAY,lw=.7,ls=':')
    bx.annotate('',xy=(.88,.23),xytext=x,arrowprops=dict(arrowstyle='->',color=ORANGE,lw=1.5))
    bx.text(.74,.31,'发射方向',ha='center',fontsize=9,color=ORANGE)
    bx.text(.73,.68,'闭发射半平面',ha='center',fontsize=9,color=TEAL)
    bx.text(.5,-.22,'至少一个顶点可见\n且距离不超过网格边长',ha='center',fontsize=9)
    bx.set_xlim(-.12,1.14);bx.set_ylim(-.3,1.12);bx.set_aspect('equal');bx.axis('off');bx.set_title('(b) 非重合位置的几何示意')
    save(fig,stem)


def draw_results(d):
    stem=register(6,'q34-per-source-ecdf','Q3/Q4：每源耗时的经验分布',
                  '在各 3000 个配对研究场景中比较当前候选与各自对照的每局 T/C 分布。',
                  ['Q3 与 Q4 各 3000 个配对场景','四组均完成','经验累积分布','每局 T/C，单位 s/源'],
                  '同一问题内比较模型，两个问题使用不同耗时横轴；曲线越靠左表示耗时越小。',
                  [f'{LATEST}/{k}_samples.json' for k in d['groups']],
                  avoid='不将自建分布写成官方成绩；不把总时间降幅标作 T/C 降幅。')
    fig,axes=plt.subplots(1,2,figsize=(7.4,3.7),layout='constrained')
    fig.suptitle('自建研究场景：每题 3000 对，四组均完成',fontsize=10)
    for ax,problem,new,label in zip(axes,(3,4),('q3_candidate','q4_best'),('PPO 候选','预算训练 best')):
        for name,c,ls,txt in ((f'q{problem}_baseline',BLUE,'--','本批对照'),(new,ORANGE,'-',label)):
            values=np.sort([r['time_per_clear_s'] for r in d['groups'][name]])
            ax.step(values,np.arange(1,len(values)+1)/len(values),where='post',c=c,lw=1.7,ls=ls,label=txt)
        gain=next(r['reduction_mean_per_source_percent'] for r in d['paired'] if r['problem']==problem)
        ax.set_title(f'Q{problem}：每局 T/C 均值降低 {gain:.2f}%')
        ax.set_xlabel('每局 T/C / (s/源)');ax.set_ylim(0,1.02);ax.set_ylabel('经验累积比例')
        ax.legend(frameon=False,fontsize=9,loc='lower right');ax.grid(alpha=.15)
    save(fig,stem)

    stem=register(7,'q34-paired-by-count','Q3/Q4：按源数分组的配对耗时差',
                  '平均改进应结合源数和组内不确定性判断，而不是推断每个场景都更快。',
                  ['源数 10–16','新模型减对照的每局总耗时差','零差值线','近似 95% 区间'],
                  '误差条为配对差均值 ±1.96 SE；各组来自同一固定评估批次。',
                  ['handoff/tables/q34_strata.csv',f'{LATEST}/samples.csv'],
                  avoid='组间比较为探索性描述，不作多重检验后的显著性断言。')
    fig,axes=plt.subplots(1,2,figsize=(7.4,3.8),layout='constrained')
    fig.suptitle('配对差均值与近似 95% 区间（负值表示新模型更快）',fontsize=10)
    for ax,problem in zip(axes,(3,4)):
        rows=[r for r in d['strata'] if r['problem']==problem and r['dimension']=='N']
        x=np.array([r['group'] for r in rows],dtype=int);y=np.array([r['mean_delta_virtual_s'] for r in rows])
        err=np.array([r['ci95_high_s']-r['mean_delta_virtual_s'] for r in rows])
        ax.axhline(0,color=GRAY,ls='--',lw=1)
        ax.errorbar(x,y,yerr=err,fmt='o',c=ORANGE,ecolor=ORANGE,elinewidth=1.2,capsize=3,ms=4)
        ax.set_xticks(x);ax.set_xlabel('场景源数 N');ax.set_ylabel('配对总耗时差 ΔT / s')
        ax.set_title(f'Q{problem}：新模型 - 本批对照');ax.grid(axis='y',alpha=.15)
    save(fig,stem)


def draw_training(d):
    stem=register(8,'q34-validation-progress','Q3/Q4：训练期间的验证变化',
                  '训练中的模型选择依据固定验证集变化，与训练后配对测试分别记录。',
                  ['Q3 联合 PPO 阶段','Q4 预算 PPO 阶段','实际验证轮次','相对冻结对照的平均耗时差与近似区间'],
                  '同一面板按记录轮次排列；两个面板的更新尺度和对照不同，不比较收敛速度。',
                  [f'{JOINT}/ppo',BUDGET,'handoff/tables/training_validation.csv'],
                  avoid='不把反复使用的验证集称为独立测试；不插值成未记录的训练性能。')
    fig,axes=plt.subplots(1,2,figsize=(7.4,3.8),layout='constrained')
    for ax,problem,title in zip(axes,(3,4),('Q3：联合 PPO 阶段','Q4：预算 PPO 阶段')):
        rows=[r for r in d['monitor'] if r['problem']==problem]
        x=np.array([r['update'] for r in rows]);y=np.array([r['mean_delta_virtual_s'] for r in rows]);h=np.array([r['ci95_halfwidth_s'] for r in rows])
        ax.axhline(0,c=GRAY,ls='--',lw=1)
        ax.fill_between(x,y-h,y+h,color=BLUE,alpha=.12,label='均值 ±1.96 SE')
        ax.plot(x,y,'o-',color=BLUE,lw=1.3,ms=3,label='已记录验证均值')
        if problem==4:
            selected=next(i for i,r in enumerate(rows) if r['update']==3500)
            ax.scatter(x[selected],y[selected],s=75,marker='*',c=ORANGE,zorder=5,label='已交付 best：第 3500 轮')
        ax.set_title(title);ax.set_xlabel('该阶段 PPO 更新轮次');ax.set_ylabel('验证集配对总耗时差 ΔT / s')
        ax.grid(axis='y',alpha=.15);ax.legend(frameon=False,fontsize=8,loc='upper right')
    save(fig,stem)


class SVG:
    def __init__(self,width=940,height=550):
        self.width,self.height=width,height
        self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="{180*height/width:.3f}mm" viewBox="0 0 {width} {height}">',
                    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#738296"/></marker></defs>',
                    f'<rect width="{width}" height="{height}" fill="white"/>']
    def text(self,x,y,text,size=21,color=INK,weight='normal',anchor='middle'):
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="WenQuanYi Zen Hei,Noto Sans CJK SC,sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{html.escape(text)}</text>')
    def box(self,x,y,w,h,title,lines=(),color=BLUE,dashed=False):
        dash='stroke-dasharray="7 5"' if dashed else ''
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" fill-opacity=".055" stroke="{color}" stroke-width="1.5" {dash}/>')
        self.text(x+w/2,y+32,title,23,color,'bold')
        for i,line in enumerate(lines):self.text(x+w/2,y+65+i*28,line,19)
    def arrow(self,points,label=None,label_xy=None):
        pts=' '.join(f'{x},{y}' for x,y in points)
        self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{GRAY}" stroke-width="1.8" marker-end="url(#arrow)"/>')
        if label:self.text(*label_xy,label,size=18,color=GRAY)
    def save(self,stem):
        path=FIG/f'{stem}.svg';path.write_text('\n'.join(self.parts+['</svg>']),encoding='utf-8')
        convert=shutil.which('rsvg-convert')
        if not convert:raise RuntimeError('流程图导出需要 rsvg-convert（librsvg）；SVG 源文件已生成。')
        subprocess.run([convert,'-f','pdf','-o',str(FIG/f'{stem}.pdf'),str(path)],check=True)
        subprocess.run([convert,'-w','1900','-o',str(FIG/f'{stem}.png'),str(path)],check=True)


def draw_diagrams():
    bind('src/solution/control/controller.py');bind('src/solution/rl/environment.py')
    bind('src/solution/rl/model.py');bind('scripts/run_policy.py')
    stem=register(1,'controller-workflow','Q3/Q4：几何约束下的在线控制',
                  '几何与频道状态生成合法动作，调度器选择动作，公开响应反馈更新状态。',
                  ['公开响应与频道状态','可行域及几何证书','五类宏动作','规则或学习调度','串行 measure/clear/exit 与反馈'],
                  '箭头表示数据流或执行顺序；EXIT 仅在全部频道已清除或已认证不存在时出现。',
                  ['src/solution/control/controller.py','src/solution/rl/environment.py','scripts/run_policy.py'],
                  archetype='Workflow / Pipeline',backend='SVG / rsvg-convert',
                  avoid='不画 Q2 choose_second 作为现有控制器调用；不让隐藏真值进入策略。')
    s=SVG(940,580)
    s.text(470,36,'几何证书约束动作，调度器决定次序',26,INK,'bold')
    s.box(30,78,250,128,'公开历史',('测向 / near / 无信号','清除响应、时间与频道'),BLUE)
    s.box(345,78,250,128,'可行域与频道状态',('更新几何约束','清除证书、不存在认证'),TEAL)
    s.box(660,78,250,128,'合法宏动作',('覆盖 · 补测 · 保证清除','覆盖清除 · 合法退出'),TEAL)
    s.arrow([(280,142),(345,142)]);s.arrow([(595,142),(660,142)])
    s.box(660,308,250,126,'规则 / 学习调度',('启发式评分或网络排序','选择一个合法候选'),ORANGE)
    s.box(345,308,250,126,'展开并串行执行',('measure / clear / exit','每个响应后更新状态'),BLUE)
    s.arrow([(785,206),(785,308)]);s.arrow([(660,372),(595,372)])
    s.arrow([(345,372),(155,372),(155,206)],'公开响应',(233,358))
    s.text(470,493,'Q3：七站全向覆盖；Q4：三角网格与闭半平面发现证明',20)
    s.text(470,531,'退出条件：全部频道处于已清除或已认证不存在状态',20,TEAL)
    s.save(stem)

    for p in (f'{JOINT}/config.json',f'{JOINT}/frozen_selection.json',f'{JOINT}/final_recommendation.json',
              f'{BUDGET}/status.json','experiments/q4/repaired_20260912.json'):
        bind(p)
    stem=register(9,'training-evaluation-workflow','研究训练、验证与交付流程',
                  '模型训练、固定验证集选模和训练后的配对评估各自承担不同证据角色。',
                  ['自建研究场景','Q3 搜索标签与 SFT/DAgger/PPO','Q4 修复后 BC/DAgger/PPO 与预算训练',
                   '验证选模与冻结权重','3000 个配对场景评估','官方演练待执行'],
                  'Q3 与 Q4 是并行研究路线，汇入验证和冻结；官方环节使用虚线表示待形成仓库证据。',
                  [f'{JOINT}/config.json',f'{JOINT}/frozen_selection.json',f'{BUDGET}/status.json',f'{LATEST}/manifest.json'],
                  archetype='Workflow / Pipeline',backend='SVG / rsvg-convert',
                  avoid='不把历史八路独立训练画成同步 DDP；不把官方测试画成已经完成。')
    s=SVG(940,595)
    s.text(470,35,'训练、选模与配对评估分别留证',26,INK,'bold')
    s.box(305,68,330,100,'自建研究场景',('固定种子、公开观测与几何约束',),BLUE)
    s.box(30,225,420,130,'Q3：搜索辅助联合微调',('公开历史生成搜索标签','SFT → DAgger → PPO'),TEAL)
    s.box(490,225,420,130,'Q4：修复后训练与预算微调',('BC → DAgger → PPO','接续 best 进行预算训练'),TEAL)
    s.arrow([(385,168),(385,192),(240,192),(240,225)])
    s.arrow([(555,168),(555,192),(700,192),(700,225)])
    s.box(30,430,255,120,'验证与冻结',('固定验证集选模','保留对照和候选'),ORANGE)
    s.box(342,430,255,120,'训练后配对评估',('每题 3000 个场景','T、T/C、完成率'),BLUE)
    s.box(655,430,255,120,'官方演练与正式测试',('待补运行证据','另存官方原始结果'),GRAY,True)
    s.arrow([(240,355),(240,390),(158,390),(158,430)])
    s.arrow([(700,355),(700,390),(158,390)])
    s.arrow([(285,490),(342,490)]);s.arrow([(597,490),(655,490)])
    s.save(stem)


def write_specs():
    spec_dir=FIG/'specs';spec_dir.mkdir(exist_ok=True)
    exact={
        'F001':'五类动作对应 COVER / LOCALIZE / CLEAR / PROBE_CLEAR / EXIT；串行接口为 measure / clear / exit。',
        'F002':'直径 40.00 m；最小包围圆半径 23.094 m；同一组三角形顶点用于两个圆的比较。',
        'F003':'坐标与 J 从 result.json 读取；最佳点约 (735.90,262.92) m；高质量候选阈值为最小 J 加 10 s。',
        'F004':'目标圆 1800 m；外圈 1135 m；接收保护半径 999.98 m；覆盖上界约 994.81 m。',
        'F005':'网格边长 995 m；42 个三角形、31 个站点；半平面边界包含在可见区域中。',
        'F006':'每组 3000 局全部完成；每局先计算 T/C，均值降幅 Q3 约 0.40%、Q4 约 2.75%。',
        'F007':'N=10–16；误差条为 mean(新T-旧T) ±1.96 SE，单位 s。',
        'F008':'Q3 为第 16/32/48/64 轮；Q4 每 100 轮验证至 3800，best 为第 3500 轮。',
        'F009':'Q3 为 SFT/DAgger/PPO，Q4 为 BC/DAgger/PPO 及预算训练；每题最新配对场景 3000 个。',
    }
    for f in sorted(FIGURES,key=lambda x:x['id']):
        stem=f'{f["id"]}-{f["slug"]}'
        source=f'../{stem}.svg' if f['backend'].startswith('SVG') else '../../../scripts/build_handoff_assets.py'
        sources='\n'.join(f'- [{p}](../../../{p})' for p in f['sources'])
        required='\n'.join('- '+x for x in f['required'])
        text=f'''---
spec_version: "1.0"
figure_id: "{f['id']}"
working_title: "{f['title']}"
status: "RENDERED"
outputs:
  source: "{source}"
  vector: "../{stem}.pdf"
  preview: "../{stem}.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** {f['archetype']}
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
{f['message']}
## 2.2 Intended Reader Takeaway
{f['required'][0]}是理解本图的入口，结论以绑定来源为限。
## 2.3 Role in the Paper
为 Q1–Q4 的方法或实验说明提供可独立引用的中文图件。

# 3. Required Content
## 3.1 Must Show
{required}
## 3.2 Exact Scientific Content
{exact[f['id']]}
## 3.3 Source Binding
{sources}
## 3.4 Optional / Removable Content
可移除图内标题；保留轴、图例、单位和关键几何对象。
## 3.5 Assumptions / Open Questions
{f['avoid']}

# 4. Scientific Structure & Relationships
## 4.1 Relationships
{f['relationship']}

# 5. Figure Design
## 5.1 Reading Order
从左到右；图例与相邻对象或坐标轴共同阅读。
## 5.2 Composition
{'主流程沿节点连接展开，循环和待完成环节单独标明。' if f['backend'].startswith('SVG') else '数据面板使用明确坐标或等比例几何坐标；多面板分别解释同一问题的不同层面。'}
## 5.3 Primary Visual Anchor
{f['required'][0]}。
## 5.4 Information Hierarchy
### Primary
- {f['message']}
### Secondary
- 单位、图例和比较关系。
### Supporting
- 图注中的数据来源和适用范围。
## 5.5 Simplification & Redundancy
不使用装饰图标、虚构数据点或额外插值；完整数值与出处由表格及清单承载。

# 6. Visual & Content Constraints
## 6.1 Visual Semantics
蓝色表示对照/公开输入，橙色表示候选/动作选择，青色表示几何范围；颜色同时由线型、标签或图例解释。
## 6.2 Required Figure Labels
采用中文对象名称；几何坐标标注 m，耗时标注 s 或 s/源，统计差值说明新减旧；相关数值按 3.2 保留。
## 6.3 Must Not Imply / Avoid
{f['avoid']}

# 7. References & Rendering Requirements
## 7.1 References
使用绑定的仓库数据和实现，不复制旧图的排版或使用论文目录作为数据源。
## 7.2 Cross-Figure Consistency
中文说明、米与秒单位、统一字体和颜色；统计差值均为新减旧。
## 7.3 Rendering Requirements
**Intended Use:** 中文论文方法与实验图，供论文手选用。
**Target Size / Aspect Ratio:** 通栏约 17–18 cm；单幅几何图可按可读性缩放。
**Preferred Backend:** {f['backend']}
**Required Outputs:** SVG、PDF、PNG，以及重绘代码和输入哈希。
'''
        (spec_dir/f'{stem}.md').write_text(text,encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tables-only',action='store_true',help='只复算表格，不重绘图件')
    args=ap.parse_args()
    FIG.mkdir(parents=True,exist_ok=True)
    data=prepare_tables()
    if not args.tables_only:
        style();draw_diagrams();draw_geometry(data);draw_q2(data);draw_coverage(data);draw_results(data);draw_training(data)
        write_specs()
    bind(Path(__file__).relative_to(ROOT))
    common=dict(
        source_git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        generation_scope='对绑定数据重新汇总与绘图；源码可能含未提交整理，实际输入和生成脚本以 SHA-256 为准',
        command='python scripts/build_handoff_assets.py'+(' --tables-only' if args.tables_only else ''),
        environment=dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__),
        inputs=INPUTS)
    for folder in ((TABLE,) if args.tables_only else (TABLE,FIG)):
        outputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(folder.rglob('*')) if p.is_file()
                 and (p.suffix.lower() in {'.pdf','.svg','.png','.csv','.json'} or p.parent.name=='specs')
                 and p.name!='provenance.json'}
        payload=dict(common,outputs=outputs)
        if folder==FIG:payload['figures']=sorted(FIGURES,key=lambda x:x['id'])
        write_json(folder/'provenance.json',payload)
    print(json.dumps({'paired_records':12000,'table_files':len(list(TABLE.glob('*.csv'))),
                      'figures_rendered':len(FIGURES)},ensure_ascii=False))


if __name__=='__main__':
    main()
