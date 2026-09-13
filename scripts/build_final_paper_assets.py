"""从固定交付快照复算主结果，绘制完整搜索耗时比较；不修改原始数据。"""
from pathlib import Path
import csv,json,hashlib,statistics,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'results/final-8ef9ef8'; O=ROOT/'paper/figures'
def read(p):return json.loads((D/p).read_text())
def rows(p):return list(csv.DictReader((D/'paper/tables'/p).open(encoding='utf-8-sig')))
q3p=read('runs/q34_deadline_test3000_20260913/q3_baseline_samples.json');q3=read('runs/q34_deadline_test3000_20260913/q3_candidate_samples.json');q4d=read('runs/q4_baseline_8gpu_1h_20260913/train/final_test.json')
data={'q3_parent':q3p,'q3_final':q3,'q4_parent':q4d['baseline'],'q4_final':q4d['student']}
audit={}
for name,a in data.items():
 assert len(a)==3000 and len(set(x['seed'] for x in a))==3000
 assert all(x['completion'] and x['C']==x['N'] and x.get('error') is None for x in a)
 t=np.array([x['virtual_time_s'] for x in a]);n=np.array([x['N'] for x in a]);
 audit[name]={'completed':len(a),'sources':int(n.sum()),'mean_T':float(t.mean()),'mean_T_per_N':float((t/n).mean()),'p95_T':float(np.percentile(t,95))}
 for r in rows('final_main_results.csv'):
  if r['model']==name:
   assert abs(float(r['mean_T_s'])-t.mean())<1e-7
   assert abs(float(r['mean_T_per_N_s'])-(t/n).mean())<1e-7
 for x in a:
  recon=x['path_length_m']/5+5*x['measures']+x['switches']+3*x['clear_failures']+5*x['C']
  assert abs(recon-x['virtual_time_s'])<.01,(name,x['seed'],recon,x['virtual_time_s'])
for k in ['q3','q4']:
 a,b=data[k+'_parent'],data[k+'_final'];assert all(x['seed']==y['seed'] and x['N']==y['N'] and x['profile']==y['profile'] for x,y in zip(a,b))
 for metric in ['T','per_source']:
  diff=np.array([(y['virtual_time_s']-x['virtual_time_s'])/(x['N'] if metric=='per_source' else 1) for x,y in zip(a,b)])
  mean=float(diff.mean());se=float(diff.std(ddof=1)/math.sqrt(len(diff)))
  audit[k+'_'+metric+'_paired']={'mean':mean,'ci95':[mean-1.96*se,mean+1.96*se]}
reg=read('paper/model_registry.json')
import zipfile
with zipfile.ZipFile(D/'final-runtime.zip') as z:
 for m in reg['models']:
  if m['role']=='final': assert hashlib.sha256(z.read(m['path'])).hexdigest()==m['sha256']
(D/'paper_recalculation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
plt.rcParams.update({'font.family':'Arial Unicode MS','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'axes.unicode_minus':False})
fig,axs=plt.subplots(1,2,figsize=(10.3,4.2),constrained_layout=True)
means=rows('final_by_source_count.csv')
for i,ax in enumerate(axs):
 k=f'q{i+3}'; alln=np.arange(10,17)
 rr=[r for r in means if r['model']==k+'_final']
 ax.plot([int(r['N']) for r in rr],[float(r['mean_T_s']) for r in rr],color='#17648b',marker='o',lw=1.7,ms=4,label='最终策略：研究场景均值')
 if i==0:
  ext=[r for r in rows('q3_layout_extremes.csv') if r['case']=='best']
  ax.plot([int(r['N']) for r in ext],[float(r['total_s']) for r in ext],color='#bc742d',marker='D',ms=4,lw=1.7,ls='--',label='有利布局：最短已检验完整耗时')
  ax.plot([int(r['N']) for r in ext],[float(r['last_clear_s']) for r in ext],color='#847192',marker='x',ms=4,lw=1.3,ls=':',label='同一有利布局：最后清除时刻')
 else:
  ax.plot([int(r['N']) for r in rr],[float(r['p95_T_s']) for r in rr],color='#bc742d',marker='s',lw=1.5,ms=4,ls='--',label='最终策略：研究场景95%分位数')
 ax.set(xlabel='实际源数 N',ylabel='总虚拟时间 / s',xticks=alln,title=f'({chr(97+i)}) 问题{i+3}：完整任务耗时')
 ax.axvspan(15.65,16.25,color='#deece5',alpha=.7);ax.set_xlim(9.7,16.3);ax.grid(alpha=.16);ax.set_ylim(bottom=0)
 ax.text(.98,.14,'16源可提前结束覆盖',ha='right',va='top',transform=ax.transAxes,fontsize=8,color='#32614b')
 ax.legend(loc='center left',bbox_to_anchor=(0,.32 if i==0 else .5),fontsize=8,framealpha=.9)
fig.savefig(O/'F013-complete-search-comparison.pdf');fig.savefig(O/'F013-complete-search-comparison.png',dpi=180)
print(json.dumps(audit,ensure_ascii=False,indent=2))
