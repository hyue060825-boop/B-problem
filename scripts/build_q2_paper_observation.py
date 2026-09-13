#!/usr/bin/env python3
"""从预先指定的原选点器补测记录绘制论文图2；不运行选点或训练。"""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from solution.geometry.core import circle_polygon,mec
raw=ROOT/'results/validation/LIT-Q2-01/pilot/records.json'
r=next(r for r in json.loads(raw.read_text()) if r['case']['seed']==412000 and r['metrics']['method']=='current')
a=np.array(r['initial']);b=np.array(r['posterior']);s=np.array(r['case']['start']);q=np.array(r['selection']['position'])
recv=circle_polygon(a[0],999.98,n=128,outer=False)
for v in a[1:]:recv=recv.intersection(circle_polygon(v,999.98,n=128,outer=False))
assert r['metrics']['second_received'] and r['metrics']['posterior_contains_truth']
assert max(np.linalg.norm(a-q,axis=1))<=999.98
center,rad=mec(a)
assert np.isclose(mec(b)[1],r['metrics']['posterior_radius_m'],atol=1e-8)
assert np.isclose(max(np.linalg.norm(a-q,axis=1)),r['selection']['receive_bound_m'],atol=1e-8)
plt.rcParams.update({'font.family':'STHeiti','font.size':10,'axes.unicode_minus':False,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(8.4,5.6),layout='constrained')
ax.add_patch(Polygon(np.array(recv.exterior.coords),fc='#e5f1ee',ec='#699c91',lw=1.2,label='保证接收候选区域（内近似）'))
ax.add_patch(Polygon(a,fc='#f7dfc4',ec='#c38846',lw=1.2,label='首次可行域凸包'))
ax.add_patch(Polygon(b,fc='#356aa0',ec='#234f7d',lw=1.3,label='第二次观测后定位区域'))
for pos,deg in [(s,r['trace'][0]['response']['svd_deg']),(q,r['trace'][1]['response']['svd_deg'])]:
 u=np.array([np.cos(np.deg2rad(deg)),np.sin(np.deg2rad(deg))]);end=pos+u*1000
 ax.plot([pos[0],end[0]],[pos[1],end[1]],ls='--',c='#718197',lw=.9,zorder=2)
ax.scatter(*s,marker='s',s=38,c='#243c55',zorder=4)
ax.annotate('首检测点 $s_1$',s,xytext=(10,-19),textcoords='offset points')
ax.scatter(*q,marker='o',s=48,c='#bf612e',zorder=4)
ax.annotate('第二检测点 $q$\n(743.65, 245.94) m',q,xytext=(18,-8),textcoords='offset points',fontsize=9)
ax.annotate('两次观测的交会区域',b.mean(0),xytext=(810,760),arrowprops={'arrowstyle':'-','color':'#356aa0'},fontsize=9,color='#234f7d')
ax.set_aspect('equal');ax.set(xlim=(-100,1380),ylim=(-160,1080),xlabel='东向坐标 $x$ / m',ylabel='北向坐标 $y$ / m');ax.grid(alpha=.14)
ins=ax.inset_axes([.025,.38,.27,.30]);ins.add_patch(Polygon(b,fc='#c9dcee',ec='#234f7d',lw=1.2));ins.set_aspect('equal');ins.set_xlim(b[:,0].min()-5,b[:,0].max()+5);ins.set_ylim(b[:,1].min()-5,b[:,1].max()+5);ins.tick_params(labelsize=7);ins.grid(alpha=.15);ins.set_title('交会区域局部放大（m）',fontsize=9);ins.text(.5,.06,'R = 13.87 m',transform=ins.transAxes,ha='center',fontsize=8)
ax.legend(loc='lower center',bbox_to_anchor=(.5,-.25),frameon=False,ncol=1,fontsize=9)
for ext in ['pdf','png']:
 fig.savefig(ROOT/f'paper/figures/F014-q2-observed-selection.{ext}',bbox_inches='tight',**({'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {'dpi':200}))
info={'source':str(raw.relative_to(ROOT)),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'seed':412000,'method':'current','first_svd_deg':r['trace'][0]['response']['svd_deg'],'second_svd_deg':r['trace'][1]['response']['svd_deg'],'second_point':q.tolist(),'initial_mec_radius_m':float(rad),'posterior_mec_radius_m':r['metrics']['posterior_radius_m'],'receive_bound_m':r['selection']['receive_bound_m'],'note':'同一原策略真实本地补测记录；非官方测试，真值未作为选点输入。保证接收区域按相同内接128边形方法从记录凸包重建。'}
(ROOT/'paper/figures/F014-q2-observed-selection.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n');print(json.dumps(info,ensure_ascii=False))
