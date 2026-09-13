"""Summarize frozen paired evaluation; no model selection or training."""
import csv,json
from pathlib import Path
import numpy as np

out=Path('/data5/hy/B-problem/runs/q34_deadline_test3000_20260913')
s=json.loads((out/'summary.json').read_text());manifest=json.loads((out/'manifest.json').read_text())
lines=['# Q3 / Q4 六小时微调后：3000 场景配对终测','',
'每题 3000 个新场景，新旧各运行一次，共 12000 局。候选在终测前按训练验证集冻结，终测不用于调参或重新选模。使用匹配的旧 normalized-public-v2 完整系统、greedy 策略及 400 宏动作预算。',
'','LOCAL-RESEARCH 自建模拟器结果，非官方成绩。保留实时剩余时间特征，按样例交替新旧执行顺序；不是固定墙钟输入的逐位等价实验。',
'','| 题目 | 旧完成 | 新完成 | 旧 T/N 秒/源 | 新 T/N 秒/源 | 改善比例 | 配对差 95% CI（新−旧） |',
'|---|---:|---:|---:|---:|---:|---|']
strata={};verification={}
for q,candidate in ((3,'q3_candidate'),(4,'q4_best')):
 b=f'q{q}_baseline';old=s[b];new=s[candidate];p=new['vs_baseline']['paired_tn']
 lines.append(f"| Q{q} | {old['completed_episodes']}/3000 | {new['completed_episodes']}/3000 | {old['mean_per_source_s']:.3f} | {new['mean_per_source_s']:.3f} | {p['reduction_percent']:.3f}% | [{p['ci95'][0]:.3f}, {p['ci95'][1]:.3f}] |")
 br=json.loads((out/f'{b}_samples.json').read_text());nr=json.loads((out/f'{candidate}_samples.json').read_text())
 assert len(br)==len(nr)==3000 and len({r['seed'] for r in nr})==3000
 assert all(x['scenario_sha256']==y['scenario_sha256'] and x['seed']==y['seed'] and x['N']==y['N'] for x,y in zip(br,nr))
 verification[str(q)]=dict(pairs=3000,scenario_hashes_match=True,all_complete=all(r['completion'] for r in br+nr))
 strata[str(q)]={}
 for n in range(10,17):
  pairs=[(x,y) for x,y in zip(br,nr) if x['N']==n];d=np.array([(y['virtual_time_s']-x['virtual_time_s'])/n for x,y in pairs])
  strata[str(q)][str(n)]={'pairs':len(pairs),'mean_delta_tn':float(d.mean()),'ci95_half':float(1.96*d.std(ddof=1)/np.sqrt(len(d)))}
 lines += ['',f'## Q{q} 细节','',f"平均每局虚拟耗时：{old['mean_virtual_s']:.3f} → {new['mean_virtual_s']:.3f} 秒。T/N 的 P95：{old['p95_per_source_s']:.3f} → {new['p95_per_source_s']:.3f} 秒/源。",f"更快 {new['vs_baseline']['faster_episodes']} 局，持平 {new['vs_baseline']['tied_episodes']} 局，更慢 {new['vs_baseline']['slower_episodes']} 局。",'',f"候选：`{manifest['checkpoints'][candidate]['path']}`",f"SHA256：`{manifest['checkpoints'][candidate]['sha256']}`",f"基线：`{manifest['checkpoints'][b]['path']}`",'', '| N | 样例数 | 平均配对 T/N 差（新−旧，秒/源） |','|---|---:|---:|']
 lines += [f"| {n} | {r['pairs']} | {r['mean_delta_tn']:.3f} |" for n,r in strata[str(q)].items()]
lines += ['', '## 核验和解释','',
'主指标是逐局 T/N 的算术平均；失败局保留并优先看完成能力。配对 95% 区间使用均值的正态近似，仅描述本研究生成器下的抽样不确定性。全部 4 份权重的 44 个运行源码文件均匹配 checkpoint 哈希；场景、噪声配置和样例种子一致，场景内容摘要逐局核验。',
'','生产推荐文件未替换。best 是训练验证集所选快照；末轮 latest 没有用于本次终测。',
'','![新旧模型分布](per_source_distribution.png)','', '[逐局 CSV](samples.csv) · [完整汇总](summary.json) · [运行及权重清单](manifest.json)']
(out/'report.md').write_text('\n'.join(lines)+'\n');(out/'paired_by_N.json').write_text(json.dumps(strata,indent=2));(out/'verification.json').write_text(json.dumps(verification,indent=2))
print(json.dumps({k:{field:value for field,value in v.items() if field in ('completed_episodes','mean_virtual_s','mean_per_source_s','p95_per_source_s','vs_baseline')} for k,v in s.items()},indent=2))
