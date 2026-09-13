"""Visualize the final Q4 station layout and its exact all-heading absence certificate."""
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Circle,Polygon,Wedge
from solution.control.controller import Controller
from solution.coverage.certificates import triangular_grid
from experiments.q4_exact import cell_vertices,q

OUT=ROOT/'runs/q4_31_station_certificate_20260913'
PROOF=ROOT/'runs/q4_optimization_20260912/layout31_proof.json'


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    proc=subprocess.run([sys.executable,str(ROOT/'scripts/verify_q4_certificate_exact.py'),str(PROOF)],cwd=ROOT,capture_output=True,text=True,check=True)
    verified=json.loads(proc.stdout);assert verified['status']=='PROVED_MATH'
    proof=json.loads(PROOF.read_text());grid=triangular_grid();ctrl=Controller(4)
    assert len(ctrl.stations)==len(proof['stations'])==31
    # Bind the rational artifact to the actual JSON decimal coordinates sent by this runtime.
    assert all(q(s[k])==Fraction(str(p[j])) for s,p in zip(proof['stations'],ctrl.stations) for j,k in enumerate(('x','y')))
    registry=json.loads((ROOT/'paper/model_registry.json').read_text())['models']
    final=next(m for m in registry if m['id']=='q4_final')
    assert all(sha(ROOT/p)==h for p,h in final['runtime_files'].items())
    assert sha(ROOT/final['path'])==final['sha256']
    # Empty-channel state-machine demonstration, using accepted-observation semantics.
    for i,p in enumerate(ctrl.stations):
        ctrl.observe(1,p,'no_signal',station=i)
        if i<30:assert ctrl.channels[1].status=='UNKNOWN'
    assert ctrl.channels[1].status=='ABSENT_CERTIFIED' and not ctrl.exit_allowed()
    for channel in range(2,21):
        for i,p in enumerate(ctrl.stations):ctrl.observe(channel,p,'no_signal',station=i)
    assert ctrl.exit_allowed()
    verification=dict(**verified,station_coordinates_equal_runtime_json_exactly=True,
                      final_checkpoint=final['path'],final_checkpoint_sha256=final['sha256'],
                      runtime_hashes_match=True,triangle_count=grid['triangle_count'],
                      unknown_after_30_negatives=True,absent_after_31_negatives=True,
                      all_20_channels_absent_then_exit_allowed=True,
                      scope='Continuous source disk, reception radius >=1000m, closed directional half-plane; per-channel accepted observations. No minimum-station claim.')
    (OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'stations.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['station_id','x_m','y_m','inside_source_disk','exact_x','exact_y'])
        for s,p in zip(proof['stations'],grid['vertices']):w.writerow([s['id'],*p,np.linalg.norm(p)<=1800,s['x'],s['y']])

    plt.rcParams.update({'font.family':'Noto Sans CJK SC','font.size':10,'axes.unicode_minus':False,'pdf.fonttype':42,'ps.fonttype':42})
    fig,axes=plt.subplots(1,3,figsize=(19,8.6),gridspec_kw={'width_ratios':[1.15,1,1]})
    fig.subplots_adjust(left=.035,right=.985,top=.80,bottom=.32,wspace=.25)
    fig.suptitle('Q4：31 个固定站点如何完成无源确认',fontsize=22,y=.97,weight='bold')
    fig.text(.5,.90,'覆盖证书保证“任何真实源至少在一个站点可见”；同一未知频道在全部站点均无信号，才可判定无源。',ha='center',fontsize=12,color='#334155')
    pts=np.asarray(grid['vertices']);triangles=np.asarray(grid['triangles'])
    ax=axes[0]
    ax.add_collection(PolyCollection(triangles,facecolors='#dbeafe',edgecolors='#94a3b8',linewidths=.7,alpha=.7))
    ax.add_patch(Circle((0,0),1800,facecolor='#0ea5e9',alpha=.07))
    ax.add_patch(Circle((0,0),1800,fill=False,color='#0369a1',lw=2.2,label='可能源域：半径 1800 m'))
    ax.scatter(pts[:,0],pts[:,1],s=37,color='#0f172a',zorder=4,label='31 个固定测量站点')
    for i,(x,y) in enumerate(pts):ax.annotate(str(i),(x,y),xytext=(5,5),textcoords='offset points',fontsize=8,zorder=6)
    ax.set(xlim=(-2820,2820),ylim=(-2750,2750),xlabel='x (m)',ylabel='y (m)',title='(a) 固定布局与连续三角网格')
    ax.text(.5,1.01,'间距 995 m；42 个相交三角形',transform=ax.transAxes,ha='center',fontsize=9,color='#475569')

    ax=axes[1]
    tri=np.array([[0.,0.],[995.,0.],[497.5,995*np.sqrt(3)/2]])
    p=tri.mean(axis=0);heading=20.;angle=np.radians(heading);u=np.array([np.cos(angle),np.sin(angle)])
    ax.add_patch(Circle(p,1000,fill=False,ec='#94a3b8',ls='--',lw=1.1))
    ax.add_patch(Wedge(p,1000,heading-90,heading+90,facecolor='#bbf7d0',edgecolor='none',alpha=.65))
    perp=np.array([-u[1],u[0]])
    ax.plot(*np.stack([p-1050*perp,p+1050*perp]).T,color='#16a34a',ls='--',lw=1.2)
    ax.add_patch(Polygon(tri,facecolor='#dbeafe',edgecolor='#475569',lw=1.5,alpha=.8))
    for j,v in enumerate(tri):
        good=np.dot(u,v-p)>=0
        ax.plot([p[0],v[0]],[p[1],v[1]],color='#15803d' if good else '#b91c1c',lw=1.6,ls='-' if good else ':')
        ax.scatter(*v,s=68,c='#15803d' if good else '#b91c1c',zorder=5)
        ax.annotate(f'$v_{j+1}$'+(' 可见' if good else ' 背向'),v,xytext=(6,10),textcoords='offset points',fontsize=10)
    ax.scatter(*p,marker='*',s=160,c='#f59e0b',edgecolor='#92400e',zorder=7)
    ax.annotate('任意源位置 p',p,xytext=(-15,-28),textcoords='offset points',fontsize=10)
    ax.annotate('',p+650*u,p,arrowprops=dict(arrowstyle='-|>',lw=2.5,color='#15803d'))
    ax.text(*(p+600*u+[35,-95]),'朝向 u',fontsize=10,color='#166534')
    ax.text(.5,.97,'绿色：示例朝向的闭半圆接收区域',transform=ax.transAxes,ha='center',fontsize=9,color='#166534')
    ax.set(xlim=(p[0]-1160,p[0]+1160),ylim=(p[1]-1160,p[1]+1160),xlabel='x (m)',ylabel='y (m)',title='(b) 任意朝向均有可见顶点')

    ax=axes[2];cells=[];colors=[]
    for leaf in proof['leaves']:
        if leaf['status']!='WITNESS':continue
        cells.append([(float(x),float(y)) for x,y in cell_vertices(leaf['depth'],leaf['ix'],leaf['iy'],q(proof['source_domain_radius']))])
        colors.append(leaf['depth'])
    collection=PolyCollection(cells,array=np.array(colors),cmap='GnBu',edgecolors='#ffffff',linewidths=.18,clim=(3,8))
    ax.add_collection(collection)
    clip=Circle((0,0),1800,transform=ax.transData);collection.set_clip_path(clip)
    ax.add_patch(Circle((0,0),1800,fill=False,color='#0369a1',lw=1.7))
    ax.set(xlim=(-1900,1900),ylim=(-1900,1900),xlabel='x (m)',ylabel='y (m)',title='(c) 整个连续圆域已逐块验证')
    for ax in axes:
        ax.set_title(ax.get_title(),pad=28)
        ax.set_aspect('equal');ax.grid(alpha=.12)
        for spine in ax.spines.values():spine.set_color('#cbd5e1')
    fig.text(.045,.235,'布局保证\n黑点为31站；蓝圆为半径1800 m的可能源域。\n任意源落在闭三角形内，到三个顶点均小于1000 m。\n包含圆外站点；编号不表示访问顺序。',fontsize=10,va='top',linespacing=1.6)
    fig.text(.377,.235,'方向保证\n'+r'$p=\sum_i\lambda_i v_i\ \Rightarrow\ \sum_i\lambda_i\,u^T(v_i-p)=0$'+'\n因此不可能所有顶点均在背向开半平面。\n源与站点重合时，由周围非重合站点补证。',fontsize=10,va='top',linespacing=1.6)
    fig.text(.705,.235,'右图说明\n蓝圆内划分为2152个已验证单元；未决单元为0。\n小方格是证明区域，不是站点，也不是源的位置。\n颜色越深表示细分层级越深，不表示信号或成功率。\n每块区域内任意位置、任意朝向的源均能被至少一站发现。\n另有72个域外单元、13处重合点保护；认证距离≤999 m。',fontsize=10,va='top',linespacing=1.6)
    fig.text(.5,.025,'结论：该频道 31 站全部取得有效无信号观测 ⇒ 不存在满足上述接收规则的存活源。此图解释证书，不证明 31 是最少站数。',ha='center',fontsize=11,weight='bold',color='#0f172a')
    for ext in ('png','pdf','svg'):fig.savefig(OUT/f'coverage_certificate.{ext}',dpi=220,facecolor='white')
    plt.close(fig)
    # Standalone panel, with every explanatory sentence outside the plotting area.
    fig,ax=plt.subplots(figsize=(8.5,10))
    fig.subplots_adjust(left=.12,right=.97,top=.90,bottom=.29)
    collection=PolyCollection(cells,array=np.array(colors),cmap='GnBu',edgecolors='#ffffff',linewidths=.23,clim=(3,8))
    ax.add_collection(collection)
    collection.set_clip_path(Circle((0,0),1800,transform=ax.transData))
    ax.add_patch(Circle((0,0),1800,fill=False,color='#0369a1',lw=1.8))
    ax.set(xlim=(-1900,1900),ylim=(-1900,1900),xlabel='x (m)',ylabel='y (m)',title='Q4：31站覆盖证书的连续区域验证')
    ax.set_aspect('equal');ax.grid(alpha=.12);ax.set_title(ax.get_title(),pad=16)
    for spine in ax.spines.values():spine.set_color('#cbd5e1')
    fig.text(.12,.225,'读图说明',fontsize=13,weight='bold',va='top')
    fig.text(.12,.19,'蓝圆：半径1800 m的可能源域。\n小方格：用于数学验证的区域；不是测量站点，也不是源。\n深浅：仅表示细分层级，颜色越深说明方格细分得越小。\n结果：2152个区域均已验证，未决区域为0。',fontsize=11,va='top',linespacing=1.7)
    fig.text(.12,.065,'每个区域内，任意位置、任意朝向的源，都至少有一个可见站点。\n所以同一频道在31站均有效测得无信号，才可在既定规则下认证无源。',fontsize=11,va='top',linespacing=1.6,color='#0f172a')
    for ext in ('png','pdf','svg'):fig.savefig(OUT/f'coverage_cells.{ext}',dpi=220,facecolor='white')
    plt.close(fig)
    manifest=dict(checkpoint_sha256=final['sha256'],proof=str(PROOF.relative_to(ROOT)),proof_sha256=sha(PROOF),
                  plot_script='scripts/plot_q4_31_station_certificate.py',plot_script_sha256=sha(__file__),
                  files={p.name:sha(p) for p in OUT.iterdir() if p.suffix in ('.png','.pdf','.svg','.csv','.json') and p.name!='manifest.json'},
                  caveat='Exact proof under model rules, not a statistical plot or a claim of minimum station count.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(verification,ensure_ascii=False))

if __name__=='__main__':main()
