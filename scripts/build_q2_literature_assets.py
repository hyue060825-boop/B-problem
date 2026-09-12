#!/usr/bin/env python3
"""从LIT-Q2-01固定原始记录生成中文表格和F010—F012；不运行策略。"""
import csv
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/b-problem-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'results/validation/LIT-Q2-01'
TABLE=ROOT/'handoff/tables/LIT-Q2-01'
FIG=ROOT/'handoff/figures'
LABELS={'on_bearing':'沿示向线','fixed_flank':'固定侧翼','current':'当前 Q2','shape':'几何候选'}
COLORS={'on_bearing':'#777777','fixed_flank':'#32856e','current':'#356db2','shape':'#d56a35'}
INPUTS={};OUTPUTS=[]


def read(p):
    INPUTS[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())


def csv_out(name,rows):
    path=TABLE/name
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    OUTPUTS.append(path)


def save(fig,stem):
    for ext in ('pdf','svg','png'):
        p=FIG/f'{stem}.{ext}'
        kwargs={'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else ({'metadata':{'Date':None}} if ext=='svg' else {'dpi':260})
        fig.savefig(p,bbox_inches='tight',**kwargs)
        if ext=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
        OUTPUTS.append(p)
    plt.close(fig)


def spec(stem,title,message,required,relation,avoid):
    text=f'''---
spec_version: "1.0"
figure_id: "{stem[:4]}"
working_title: "{title}"
status: "RENDERED"
outputs:
  source: "../../../scripts/build_q2_literature_assets.py"
  vector: "../{stem}.pdf"
  preview: "../{stem}.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Results / Diagnostics
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
{message}
## 2.2 Intended Reader Takeaway
依据实际观测比较几何精度与执行成本。
## 2.3 Role in the Paper
Q2补充实验；LIT-Q2-01。

# 3. Required Content
## 3.1 Must Show
- {required}
## 3.2 Exact Scientific Content
- 数据以对应批次记录为准；m为米，s为秒；当前Q2与几何候选分别标识。
## 3.3 Source Binding
- [原始批次](../../../results/validation/LIT-Q2-01/README.md)
- [整理表格](../../tables/LIT-Q2-01/README.md)
## 3.4 Optional / Removable Content
标题可并入论文图注。
## 3.5 Assumptions / Open Questions
本地单源研究；固定空间误差场，不代表官方成绩。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
{relation}

# 5. Figure Design
## 5.1 Reading Order
左到右。
## 5.2 Composition
横向双面板，共享字体与语义颜色；轴和图例就近标注。
## 5.3 Primary Visual Anchor
各方法实际数据之间的比较。
## 5.4 Information Hierarchy
### Primary
- {message}
### Secondary
- 单位、案例数和方法图例。
### Supporting
- 来源和适用边界见图注。
## 5.5 Simplification & Redundancy
不增加装饰图标或未经观测的数据点。

# 6. Visual & Content Constraints
## 6.1 Visual Semantics
当前Q2蓝色，几何候选橙色；用文字及线型同时区分。
## 6.2 Required Figure Labels
横纵轴带单位，配对差说明新减旧。
## 6.3 Must Not Imply / Avoid
{avoid}

# 7. References & Rendering Requirements
## 7.1 References
来源为绑定实验记录；文献只作方法背景，见[文献说明](../../../docs/references/README.md)。
## 7.2 Cross-Figure Consistency
与F001—F009保持中文和单位口径一致。
## 7.3 Rendering Requirements
**Intended Use:** 中文论文Q2补充实验。
**Target Size / Aspect Ratio:** 通栏约18 cm；双面板。
**Preferred Backend:** Python / Matplotlib
**Required Outputs:** PDF、SVG、PNG、生成代码及SHA-256。
'''
    p=FIG/'specs'/f'{stem}.md';p.write_text(text,encoding='utf-8');OUTPUTS.append(p)


def main():
    TABLE.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'WenQuanYi Zen Hei','font.weight':500,'font.size':10,
                         'axes.unicode_minus':False,'pdf.fonttype':42,'svg.hashsalt':'LIT-Q2-01',
                         'axes.spines.top':False,'axes.spines.right':False})
    pilot=read(RAW/'pilot/records.json')
    records=read(RAW/'evaluation/records.json');report=read(RAW/'evaluation/summary.json')
    sensitivity=read(RAW/'sensitivity/records.json')
    csv_out('summary.csv',report['methods']);csv_out('paired.csv',report['paired'])
    csv_out('samples.csv',[r['metrics'] for r in records])
    p=RAW/'sensitivity/sensitivity.csv';INPUTS[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    with p.open(encoding='utf-8-sig') as f:sens=list(csv.DictReader(f))
    csv_out('sensitivity.csv',sens)

    # 预先指定pilot第一个场景，避免按评估收益挑图。
    chosen={r['metrics']['method']:r for r in pilot if r['case']['seed']==412000}
    base=chosen['current'];target=np.array(base['case']['source'])
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),layout='constrained')
    for ax in axes:
        ax.set_aspect('equal');ax.set_xlabel('东向坐标 / m');ax.set_ylabel('北向坐标 / m');ax.grid(alpha=.15)
    ax=axes[0]
    ax.add_patch(Polygon(base['initial'],facecolor='#d7e2ee',edgecolor='#9aabbe',alpha=.6,label='首次可行域凸包'))
    ax.scatter(*base['case']['start'],c='black',marker='s',label='首检测点',s=35)
    for method in ('current','shape'):
        q=chosen[method]['selection']['position']
        ax.scatter(*q,color=COLORS[method],marker='o' if method=='current' else '^',s=48,label=LABELS[method]+' 补测点')
        ax.plot([q[0],target[0]],[q[1],target[1]],color=COLORS[method],ls=':',lw=1)
    ax.scatter(*target,marker='*',c='black',s=80,label='真值（仅评价端）')
    ax.autoscale_view();ax.legend(fontsize=8);ax.set_title('(a) 观测位置与首次几何范围')
    ax=axes[1]
    allpoints=[]
    for method in ('current','shape'):
        r=chosen[method];v=np.array(r['posterior']);allpoints.extend(v)
        ax.add_patch(Polygon(v,facecolor=COLORS[method],edgecolor=COLORS[method],alpha=.25,
                            linestyle='-' if method=='current' else '--',
                            label=f"{LABELS[method]}：R={r['metrics']['posterior_radius_m']:.1f} m"))
    ax.scatter(*target,marker='*',c='black',s=70);ax.autoscale_view();ax.margins(x=.15,y=.35)
    ax.legend(fontsize=9);ax.set_title('(b) 实际第二次观测后的凸包（放大）')
    fig.suptitle('Q2 一致场景：实际后验比较（试运行种子 412000）',fontsize=12)
    stem='F010-q2-observed-posterior';save(fig,stem)
    spec(stem,'Q2实际补测前后几何','同一场景的实际观测支持选点后的几何比较。','首点、两种补测点、真值与各自实际后验凸包。',
         '左图为共用初始信息与不同动作，右图为各自观测的几何更新。','真值不能作为选点输入；凸包不等于含孔可行集；本例不代表平均效果。')

    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for method in LABELS:
        vals=np.sort([r['metrics']['posterior_radius_m'] for r in records if r['metrics']['method']==method])
        axes[0].step(vals,np.arange(1,len(vals)+1)/len(vals),where='post',label=LABELS[method],color=COLORS[method])
    axes[0].set(xlabel='实际后验最小包围圆半径 / m',ylabel='场景累计比例',title='(a) 120 场景的第二次观测精度')
    axes[0].axvline(19.98,color='#999999',ls='--',lw=1,label='清除证书保护阈值');axes[0].legend(fontsize=8)
    current={r['metrics']['seed']:r['metrics'] for r in records if r['metrics']['method']=='current'}
    pairs=[r['metrics'] for r in records if r['metrics']['method']=='shape']
    x=np.array([current[r['seed']]['total_virtual_s'] for r in pairs]);y=np.array([r['total_virtual_s'] for r in pairs])
    axes[1].scatter(x,y,color=COLORS['shape'],s=17,alpha=.65)
    lo=min(x.min(),y.min())-5;hi=max(x.max(),y.max())+5
    axes[1].plot([lo,hi],[lo,hi],color='#777777',ls='--',lw=1,label='相同耗时')
    axes[1].set(xlabel='当前 Q2 总虚拟耗时 / s',ylabel='几何候选总虚拟耗时 / s',title='(b) 同场景配对：线下方为更快')
    delta=y-x
    axes[1].text(.03,.97,f'均值差（新减旧）：{delta.mean():.2f} s\n更快 {sum(delta<0)} 局 / 更慢 {sum(delta>0)} 局',
                 transform=axes[1].transAxes,va='top',fontsize=9)
    for ax in axes:ax.grid(alpha=.15)
    stem='F011-q2-paired-evaluation';save(fig,stem)
    spec(stem,'Q2精度与总耗时的配对评估','几何候选减少平均总耗时，但第二次观测精度存在代价。','四方法后验半径ECDF、120对耗时和等值线。',
         '每个散点连接相同场景的两种策略结果，后续规则一致。','不将总耗时改善写成每局改善或定位精度提高；不混同官方结果。')

    fig,axes=plt.subplots(1,2,figsize=(9.5,3.6),layout='constrained')
    for ax,key,title in zip(axes,['mean_posterior_radius_m','mean_total_virtual_s'],['(a) 实际后验半径 / m','(b) 总虚拟耗时 / s']):
        arr=np.array([[float(next(r[key] for r in sens if int(r['density'])==d and float(r['weight'])==w))
                       for w in (0.,.5,1.)] for d in (3,5,9)])
        ax.imshow(arr,cmap='Blues',aspect='auto')
        for i in range(3):
            for j in range(3):ax.text(j,i,f'{arr[i,j]:.1f}',ha='center',va='center',color='white' if arr[i,j]>(arr.min()+arr.max())/2 else '#222222')
        ax.set(xticks=range(3),xticklabels=['0','0.5','1.0'],yticks=range(3),yticklabels=['3','5','9'],
               xlabel='半径权重 / (s/m)',ylabel='径向采样档数',title=title)
    fig.suptitle('独立 12 场景敏感性：等距径向采样（主实验为非等距 5 档）',fontsize=11)
    stem='F012-q2-sensitivity';save(fig,stem)
    spec(stem,'Q2权重与候选离散化敏感性','后验精度与后续总耗时不必随同一评分参数同步改善。','3×3参数组合，两类实际指标，各12场景。',
         '同组场景在9组配置下重复评估；颜色按各指标独立刻度显示。','不将12场景称为最终评估集；5档等距敏感性网格不同于主实验5档非等距网格；不回选最优权重。')
    INPUTS[str(Path(__file__).relative_to(ROOT))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest=dict(batch='LIT-Q2-01',inputs=INPUTS,outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUTPUTS},
                  command='python scripts/build_q2_literature_assets.py',matplotlib=matplotlib.__version__,numpy=np.__version__)
    (TABLE/'provenance.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'figures':3,'tables':4,'bound_inputs':len(INPUTS)}))


if __name__=='__main__':main()
