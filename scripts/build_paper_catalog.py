"""Build paper tables, figures and exhaustive evidence indices from preserved data."""
import csv
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import quote
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'paper'

def read(rel):
    return json.loads((ROOT / rel).read_text())

def write_json(rel, data):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def table(name, rows):
    p = PAPER / 'tables' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def stats(rows):
    t = np.array([r['virtual_time_s'] for r in rows])
    n = np.array([r['N'] for r in rows])
    return dict(episodes=len(rows), completed=sum(r['completion'] for r in rows), total_sources=int(n.sum()),
                mean_T_s=float(t.mean()), mean_T_per_N_s=float((t/n).mean()), p95_T_s=float(np.percentile(t, 95)))

def link(path, label=None):
    path = Path(path)
    rel = path.relative_to(ROOT).as_posix()
    target = rel[6:] if rel.startswith('paper/') else '../' + rel
    return f'[{label or path.name}]({quote(target, safe="/")})'


def main():
    specs = [
        ('q3_final', 'final', 'runs/q3_legacy_deadline_20260913/best.pt', 'q3_parent'),
        ('q4_final', 'final', 'runs/q4_baseline_8gpu_1h_20260913/train/best.pt', 'q4_parent'),
        ('q3_parent', 'reference', 'runs/q3_gpu8_extended_20260912/ppo/best.pt', None),
        ('q4_parent', 'reference', 'runs/q4_legacy_deadline_20260913/best.pt', 'q4_earlier'),
        ('q4_parent_copy', 'reference_duplicate_for_pair', 'runs/q4_baseline_8gpu_1h_20260913/parent/best.pt', 'q4_earlier'),
        ('q4_earlier', 'reference', 'runs/q4_budget_20260912/train/best.pt', None),
    ]
    import torch
    models = []
    for name, role, rel, parent in specs:
        ck = torch.load(ROOT / rel, map_location='cpu', weights_only=False)
        models.append(dict(id=name, role=role, path=rel, sha256=sha(ROOT/rel), parent=parent,
                           architecture='CandidatePolicy', feature_version='normalized-public-v2',
                           parameters=sum(v.numel() for v in ck['model'].values()), checkpoint_update=ck.get('update'),
                           runtime_revision='3ddb2d9', runtime_files={k:v for k,v in ck['provenance']['files'].items() if k.startswith(('solution/', 'bsim/'))}))
    write_json('paper/model_registry.json', dict(models=models, final_selection='User explicitly selected these two weights; not a claim of global optimality.'))
    q3dir = 'runs/q34_deadline_test3000_20260913'
    q4dir = 'runs/q4_baseline_8gpu_1h_20260913'
    q3 = read(q3dir+'/q3_candidate_samples.json'); q3base = read(q3dir+'/q3_baseline_samples.json')
    q4test = read(q4dir+'/train/final_test.json'); q4=q4test['student']; q4base=q4test['baseline']
    pairs = [(3, q3base, q3, q3dir+'/q3_candidate_samples.json'), (4,q4base,q4,q4dir+'/train/final_test.json')]
    summaries=[]; strata=[]; effects=[]
    (PAPER/'figures').mkdir(exist_ok=True)
    fig, axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for i,(q,base,final,source) in enumerate(pairs):
        assert len(base)==len(final)==3000
        assert len({r['seed'] for r in final})==3000
        assert all((a['seed'],a['N'],a['profile'])==(b['seed'],b['N'],b['profile']) for a,b in zip(base,final))
        assert all(r['completion'] and r['C']==r['N'] and not r['error'] for r in base+final)
        for label,rows in [('parent',base),('final',final)]:
            mid=f'q{q}_{label}'; h=next(m['sha256'] for m in models if m['id']==mid)
            summaries.append(dict(model=mid, checkpoint_sha256=h, **stats(rows), evidence=source))
            for n in range(10,17):
                rs=[r for r in rows if r['N']==n]
                strata.append(dict(model=mid,N=n,**stats(rs),evidence=source))
        va=np.array([r['virtual_time_s'] for r in base]); vb=np.array([r['virtual_time_s'] for r in final]);n=np.array([r['N'] for r in final])
        for metric,delta in [('T_s',vb-va),('T_per_N_s',(vb-va)/n)]:
            half=1.96*delta.std(ddof=1)/len(delta)**.5
            effects.append(dict(problem=q,metric=metric,episodes=len(delta),mean_final_minus_parent=float(delta.mean()),ci95_low=float(delta.mean()-half),ci95_high=float(delta.mean()+half),ci_method='paired normal approximation mean +/- 1.96 SE',evidence=source))
        ax=axes[i,0];bins=np.histogram_bin_edges(np.r_[va/n,vb/n],bins=50)
        for values,label,color in [(va/n,'Parent','#64748b'),(vb/n,'Final','#0f766e')]:
            ax.hist(values,bins=bins,histtype='step',lw=1.6,label=f'{label}: {values.mean():.2f}',color=color)
        ax.set(xlabel='T / N (virtual seconds per source)',ylabel='Scenarios',title=f'Q{q}: 3000 scenes; includes absence confirmation');ax.legend()
        ax=axes[i,1];ax.hist((vb-va)/n,bins=60,color='#2563eb',alpha=.8);ax.axvline(0,c='black',ls='--');ax.set(xlabel='Final minus parent (virtual seconds per source)',ylabel='Scenarios',title=f'Q{q}: paired differences; negative is better')
    for suffix in ('png','pdf'):fig.savefig(PAPER/f'figures/final_paired_results.{suffix}',dpi=220)
    plt.close(fig)
    table('final_main_results.csv',summaries);table('final_by_source_count.csv',strata);table('paired_effects.csv',effects)
    # Truncate data accounting at the selected checkpoint, distinguish it from whole-run costs.
    training=[];validation=[]
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for q,folder,selected in [(3,'runs/q3_legacy_deadline_20260913',4400),(4,q4dir+'/train',600)]:
        events=[json.loads(l) for l in (ROOT/folder/'metrics.jsonl').read_text().splitlines()]
        ppo=[r for r in events if r['stage']=='PPO']; vals=[r for r in events if r['stage']=='VALIDATION']
        for scope,rs in [('through_selected_best',[r for r in ppo if r['update']<=selected]),('whole_run',ppo)]:
            training.append(dict(model=f'q{q}_final',scope=scope,iterations=len(rs),episodes=sum(r['episodes'] for r in rs),macro_transitions=sum(r['macros'] for r in rs),elapsed_at_last_ppo_s=rs[-1]['elapsed_s'],ddp_world_size=events[0]['world_size'],sync_all=all(r['sync'] for r in rs),evidence=folder+'/metrics.jsonl'))
        for r in vals:validation.append(dict(model=f'q{q}_final',iteration=r['update'],mean_paired_T_per_N_delta_s=r['mean_delta_s'],ci95_halfwidth_s=r['ci95_halfwidth_s'],selection_pass=r['selection_pass'],evidence=folder+'/metrics.jsonl'))
        x=np.array([r['update'] for r in vals]);y=np.array([r['mean_delta_s'] for r in vals]);h=np.array([r['ci95_halfwidth_s'] for r in vals]);ax=axes[q-3]
        ax.plot(x,y,lw=1.2);ax.fill_between(x,y-h,y+h,alpha=.16);ax.axhline(0,c='grey',ls='--');ax.axvline(selected,c='#c2410c',ls=':',label=f'Selected iteration {selected}');ax.set(xlabel='PPO iteration',ylabel='Paired validation delta T/N (s/source)',title=f'Q{q} validation vs parent; not test data');ax.legend()
    for suffix in ('png','pdf'):fig.savefig(PAPER/f'figures/validation_curves.{suffix}',dpi=220)
    plt.close(fig)
    table('training_data_accounting.csv',training);table('validation_curves.csv',validation)
    write_json('paper/provenance/table_inputs.json', {p:sha(ROOT/p) for p in [q3dir+'/q3_candidate_samples.json',q3dir+'/q3_baseline_samples.json',q4dir+'/train/final_test.json','runs/q3_legacy_deadline_20260913/metrics.jsonl',q4dir+'/train/metrics.jsonl']})
    count_run='runs/q4_final_best_counts_20260913/evaluation'
    if (ROOT/count_run/'status.json').exists() and read(count_run+'/status.json')['status']=='COMPLETE':
        count_manifest=read(count_run+'/manifest.json')
        assert count_manifest['sha256']==next(m['sha256'] for m in models if m['id']=='q4_final')
        count_rows=[]
        for n in range(10,17):
            rs=read(count_run+f'/N{n}_samples.json')
            assert len(rs)==1000 and all(r['N']==n for r in rs)
            count_rows.append(dict(model='q4_final',N=n,**stats(rs),evidence=count_run+f'/N{n}_samples.json'))
        table('q4_final_counts_1000.csv',count_rows)
        inputs=read('paper/provenance/table_inputs.json')
        inputs.update({count_run+f'/N{n}_samples.json':sha(ROOT/count_run/f'N{n}_samples.json') for n in range(10,17)})
        write_json('paper/provenance/table_inputs.json',inputs)
    # Appendix tables retain each experiment's actual model identity.
    import shutil
    for q,folder,mid in [(3,'q3_layout_extremes_20260913_v2','q3_final'),(4,'q4_layout_extremes_20260913','q4_parent')]:
        with (ROOT/'runs'/folder/'extremes.csv').open(encoding='utf-8-sig',newline='') as f:
            original=list(csv.DictReader(f))
        table(f'q{q}_layout_extremes.csv',[dict(model=mid,**r,evidence=f'runs/{folder}/extremes.csv') for r in original])
    source='runs/q4_absence_tail_analysis_20260913_v2/summary.json'
    tail=read(source)
    rows=[]
    for group in ('overall','lt16'):
        r=tail[group]
        rows.append(dict(model='q4_parent',group=group,episodes=r['episodes'],mean_T_s=r['total_s'],mean_last_clear_s=r['last_clear_s'],mean_tail_s=r['tail_s'],median_tail_s=r['tail_s_p50_p95'][0],p95_tail_s=r['tail_s_p50_p95'][1],pooled_tail_fraction=r['pooled_tail_time_fraction'],after6000_pooled_negative_rate=r['after_6000_pooled_negative_rate'],episodes_with_late_discovery=r['episodes_with_late_discovery'],evidence=source))
    table('q4_parent_absence_tail.csv',rows)
    source='runs/q4_planning_ablation_20260913/test3000/summary.json'
    ablation=read(source)['groups'];rows=[]
    for group,r in ablation.items():
        rows.append(dict(model='q4_parent',group=group,episodes=r['episodes'],completed=r['completed'],mean_T_s=r['virtual_time_s'],mean_T_per_N_s=r['mean_t_per_n_s'],mean_last_clear_s=r['last_clear_s'],mean_tail_s=r['tail_s'],mean_delta_T_s=r.get('vs_baseline',{}).get('delta_s',0),evidence=source))
    table('q4_parent_planning_ablation.csv',rows)
    # Preserve the original per-episode A/C curve data next to the paper tables.
    shutil.copyfile(ROOT/'runs/q4_planning_ablation_20260913/test3000/last_clear_comparison/paired_last_clear.csv', PAPER/'tables/q4_parent_AC_paired_last_clear_3000.csv')
    logpath=ROOT/'paper/official_logs/logQ4.jsonl'
    log=[json.loads(l) for l in logpath.read_text().splitlines()]
    enter=next(r['response'] for r in log if r.get('status')=='RESPONSE' and r.get('path')=='/enter')
    leave=next(r['response'] for r in reversed(log) if r.get('status')=='RESPONSE' and r.get('path')=='/exit')
    write_json('paper/tables/official_log_timing.json',dict(model='q4_parent',checkpoint_sha256=log[0]['checkpoint_sha256'],log_sha256=sha(logpath),enter_timestamp_ms=enter['real_timestamp_ms'],exit_timestamp_ms=leave['real_timestamp_ms'],real_enter_to_exit_s=(leave['real_timestamp_ms']-enter['real_timestamp_ms'])/1000,virtual_total_s=log[-1]['virtual_time_s'],requests=log[-1]['requests'],limitation='Single official session, previous parent checkpoint; excludes Python startup/model loading. Not the final Q4 or an official multi-scenario evaluation.'))
    # Exhaustive inventory of historical attempts, not just successful experiments.
    categories={
      'q4_final_best_counts_20260913':'附录：最终Q4 c8812ced，10–16源每组1000局，共7000局',
      'q34_deadline_test3000_20260913':'正文：最终Q3；该目录Q4行是父基线',
      'q3_legacy_deadline_20260913':'最终Q3训练谱系',
      'q4_baseline_8gpu_1h_20260913':'最终Q4训练与3000局配对主结果',
      'q3_layout_extremes_20260913_v2':'附录：最终Q3主动搜索极端布局',
      'q4_legacy_deadline_20260913':'Q4父基线；补充实验的重要参照',
      'q4_absence_tail_analysis_20260913_v2':'附录：Q4父基线3000局无源尾段复放',
      'q4_planning_ablation_20260913':'附录：Q4父基线A/B/C/D负结果与最后清除曲线',
      'q4_empty_arena_20260913':'附录：Q4父基线零源诊断（不属常规分布）',
      'q4_layout_extremes_20260913':'附录：Q4父基线主动搜索极端布局',
      'q3_final_best_counts_20260912':'附录：Q3父模型8cc3，10–16源每组1000局',
      'q4_certificate_search_20260912':'附录：几何证书/缩减布局反例，独立工具',
      'q4_optimization_20260912':'附录：精确覆盖证明与探索证据',
      'q3_gpu8_extended_20260912':'Q3父模型训练、GPU搜索与独立评估',
      'q4_budget_20260912':'更早Q4基线训练与验证',
      'q34_structural_20260912':'历史不同架构：结构化优化、DDP、瓶颈与对照',
      'q4_belief_attention_20260912':'历史不同架构：信念注意力尝试，不是最终方法',
      'q4_closed_loop_20260913':'历史闭环优化尝试，不是最终方法',
    }
    lines=['# 实验与证据索引','','入口：[论文写作指导说明书](论文写作指导说明书.md) · [模型身份](model_registry.json) · [图表索引](FIGURE_INDEX.md) · [统计表](tables/)','','正文数据见下表前四项。旧版、失败、中断与阴性结果也全部归档；名称中的 best/final 不代表本分支最终选型。计划材料本身不证明实验完成。','','## 正文与附录快速入口','',
      '| 材料 | 模型/用途 |','|---|---|']
    quick=[(ROOT/q3dir/'report.md','最终Q3；Q4行属于父基线'),(ROOT/q4dir/'evaluation/report.md','最终Q4与父模型配对'),(PAPER/'tables/final_main_results.csv','两份最终权重主表'),(PAPER/'tables/training_data_accounting.csv','整段训练和入选best之前的数据量'),(ROOT/'runs/q3_layout_extremes_20260913_v2/report.md','最终Q3构造极端布局'),(ROOT/'runs/q4_absence_tail_analysis_20260913_v2/tail_analysis.png','Q4父基线尾段图'),(ROOT/'runs/q4_planning_ablation_20260913','Q4父基线四组对照及3000局A/C曲线'),(ROOT/'runs/q4_empty_arena_20260913','Q4父基线空场景'),(ROOT/'runs/q4_layout_extremes_20260913','Q4父基线极端布局'),(PAPER/'official_logs/logQ4.jsonl','Q4父基线官方单例；非批量官方测试'),(PAPER/'protocols','所有用户提供的原方案与优化提示词'),(PAPER/'history/original_reports','原始报告（标题和结论保留写作时语境）'),(PAPER/'history/original_docs','原始设计/运行说明'),(ROOT/'artifacts','Q1/Q2输入、结果、图形与来源')]
    quick.append((ROOT/count_run/'report.md','新增：最终Q4 c8812ced，10–16源各1000局；六张分布图'))
    for p,note in quick:
        if p.exists():lines.append(f'| {link(p)} | {note} |')
    lines+=['','## 所有历史实验目录','', '| 原目录 | 证据归属 | 原始证据文件数 | 可浏览报告和图 | 完整压缩档案 |','|---|---|---:|---|---|']
    index=read('paper/provenance/archive_index.json')
    for a in index:
        path=PAPER/'history'/a['id'];label=categories.get(Path(a['id']).name,'历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果')
        lines.append(f"| `{a['id']}` | {label} | {a['files']} | {link(path/'readable','浏览') if (path/'readable').exists() else '见压缩包'} | {link(path/'archive_manifest.json','校验清单及分卷')} |")
    lines+=['','## 解包复核','','分卷均小于40 MiB。压缩包保留原相对路径，逐文件SHA256在清单中。用新目录解包，不覆盖当前代码：','','```bash','python scripts/extract_experiment_archive.py paper/history/runs/q4_planning_ablation_20260913/archive_manifest.json cache/replay_ablation','```','','压缩包包含逐局样本、日志、训练标签张量及原脚本；不用的模型权重只存本地cache。完整原件25984项均有原始SHA256。历史报告可能引用本地cache中的旧权重，不能将其当成独立部署包。']
    (PAPER/'EXPERIMENT_INDEX.md').write_text('\n'.join(lines)+'\n')
    lines=['# 图表素材索引','','新汇总图只使用指定最终模型。历史图原样保留，图注须说明实验实际权重。重复路径可能是同一原图的浏览副本；不能视为独立重复实验。','','| 文件 | 实验归属 |','|---|---|']
    figures=[]
    for folder in [PAPER/'figures', ROOT/'artifacts', ROOT/'runs',PAPER/'history']:
        for p in sorted(folder.rglob('*')):
            if p.suffix.lower() not in ('.png','.pdf','.svg'):continue
            match=next((key for key in categories if key in p.parts),None)
            note=categories.get(match,'Q1/Q2解析算例' if 'artifacts' in p.parts else '历史图表；以原报告和权重哈希为准')
            if p.parent==PAPER/'figures':note='最终Q3=51397bc8、Q4=c8812ced；各自与父模型配对' if 'paired' in p.name else '最终训练段验证曲线；非独立测试'
            lines.append(f'| {link(p,p.relative_to(ROOT).as_posix())} | {note} |')
            figures.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),attribution=note))
    (PAPER/'FIGURE_INDEX.md').write_text('\n'.join(lines)+'\n')
    write_json('paper/provenance/figure_inventory.json', figures)
    table('claim_evidence.csv',[
      dict(claim='最终Q3 3000局均值与配对改善',model='q3_final',source=q3dir+'/summary.json',field='q3_candidate; vs_baseline.paired_tn',limitation='自建研究分布；不代表官方隐藏分布'),
      dict(claim='最终Q4微小改善、区间跨零',model='q4_final',source=q4dir+'/evaluation/summary.json',field='candidate; paired',limitation='不能宣称显著提升'),
      dict(claim='最终Q4源数分层7000局',model='q4_final',source=count_run+'/summary.json',field='10–16各1000局；N*_samples.json',limitation='独立分层研究分布；与Q3不是逐局配对'),
      dict(claim='Q4收尾确认长尾',model='q4_parent',source='runs/q4_absence_tail_analysis_20260913_v2',field='逐局数据、report及tail_analysis图',limitation='不是最终Q4的直接复放'),
      dict(claim='Q4四组规划对照',model='q4_parent',source='runs/q4_planning_ablation_20260913/test3000',field='逐局数据与summary',limitation='含无显著改善及退化'),
      dict(claim='搜索到的极端布局',model='q3_final / q4_parent',source='runs/q3_layout_extremes_20260913_v2 ; runs/q4_layout_extremes_20260913',field='selected layouts and repeated replay',limitation='经验极值；不是理论全局界')])
    print(json.dumps(dict(models=len(models),archives=len(index),figures=len(figures),training=training),ensure_ascii=False))

if __name__=='__main__':main()
