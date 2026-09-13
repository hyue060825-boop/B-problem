"""Plot paired baseline/C last-clear timestamps; preserve all 3000 observations."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='runs/q4_planning_ablation_20260913/test3000')
    args = parser.parse_args()
    source = Path(args.input) / 'samples.jsonl'
    records = [json.loads(line) for line in source.read_text().splitlines()]
    groups = {v: sorted((r for r in records if r['variant'] == v), key=lambda r:r['seed'])
              for v in ('baseline', 'schedule')}
    a, c = groups['baseline'], groups['schedule']
    assert len(a) == len(c) == 3000
    assert len({r['seed'] for r in a}) == 3000
    pairs = []
    for i, (left, right) in enumerate(zip(a,c)):
        assert (left['seed'],left['scenario_sha256'],left['N']) == (right['seed'],right['scenario_sha256'],right['N'])
        for r in (left,right):
            assert r['completion'] and r['C'] == r['cleared_total'] == r['N'] and not r['error']
            assert 0 <= r['last_clear_s'] <= r['virtual_time_s']
            assert abs(r['virtual_time_s']-r['last_clear_s']-r['tail_s']) < 1e-5
        pairs.append(dict(index=i,seed=left['seed'],N=left['N'],
                          baseline_last_clear_s=left['last_clear_s'],
                          c_last_clear_s=right['last_clear_s'],
                          delta_c_minus_baseline_s=right['last_clear_s']-left['last_clear_s']))
    out = source.parent / 'last_clear_comparison'
    out.mkdir(exist_ok=True)
    with (out/'paired_last_clear.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(pairs[0]))
        writer.writeheader();writer.writerows(pairs)
    y_a = np.array([r['baseline_last_clear_s'] for r in pairs])
    y_c = np.array([r['c_last_clear_s'] for r in pairs])
    delta = y_c-y_a
    rng = np.random.default_rng(20260913)
    boot = np.concatenate([delta[rng.integers(0,len(delta),(100,len(delta)))].mean(axis=1) for _ in range(50)])
    stats = dict(episodes=3000,source=str(source.resolve()),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                 metric='last successful clear timestamp in virtual seconds; post-clear absence certification excluded',
                 order='ascending scenario seed, indices 0..2999; x axis shown 0..3000',
                 baseline_mean_s=float(y_a.mean()),c_mean_s=float(y_c.mean()),
                 mean_delta_s=float(delta.mean()),reduction_percent=float(-100*delta.mean()/y_a.mean()),
                 ci95_mean_delta_s=np.percentile(boot,[2.5,97.5]).tolist(),
                 earlier=int((delta < -1e-6).sum()),tied=int((abs(delta)<=1e-6).sum()),later=int((delta>1e-6).sum()),
                 baseline_p95_s=float(np.percentile(y_a,95)),c_p95_s=float(np.percentile(y_c,95)),
                 bootstrap=dict(seed=20260913,replicates=5000,paired=True),matched_scenario_hashes=True)
    (out/'summary.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False),encoding='utf-8')
    cjk = next((f.fname for f in font_manager.fontManager.ttflist if f.name=='Noto Sans CJK SC'),None)
    if cjk:
        font_manager.fontManager.addfont(cjk)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=cjk).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['path.simplify'] = False
    fig,ax = plt.subplots(figsize=(22,7),dpi=220)
    x = np.arange(3000)
    ax.plot(x,y_a,color='#2563eb',lw=.48,alpha=.68,label=f"A 基线：平均 {y_a.mean():.2f} 秒")
    ax.plot(x,y_c,color='#ea580c',lw=.48,alpha=.68,label=f"C 提前清除调度：平均 {y_c.mean():.2f} 秒")
    ax.set(xlim=(0,3000),ylim=(0,max(y_a.max(),y_c.max())*1.04),
           xlabel='测评样本索引（按相同场景配对）',ylabel='清除全部干扰源的时间点（虚拟秒）',
           title='Q4：基线与 C 组最后一次成功清除时间｜3000 个配对样例')
    ax.set_xticks(np.arange(0,3001,250));ax.grid(alpha=.18)
    legend=ax.legend(loc='upper right',framealpha=.97)
    for line in legend.get_lines():line.set_linewidth(2)
    fig.text(.5,.015,'逐样例原始折线，未平滑、未按耗时排序；3000 个样例实际索引为 0–2999，横轴显示至 3000。',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.035,1,1))
    for ext in ('png','pdf','svg'):fig.savefig(out/f'last_clear_lines.{ext}')
    plt.close(fig)
    # Standalone zoomable companion, no CDN, network, or extra Python dependency.
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Q4 基线与 C 组：全部清除时间</title>
<style>body{font:16px system-ui;margin:24px;color:#172033}canvas{width:100%;height:560px;border:1px solid #dde3eb}input{width:90px;padding:5px}button{padding:6px 14px}#tip{min-height:28px;margin:10px 0}.blue{color:#2563eb}.orange{color:#ea580c}</style>
<h2>基线与 C 组：3000 个场景的全部清除时间</h2>
<p>纵轴为最后一次成功清除的虚拟时间，排除后续无源确认。原始索引顺序，无平滑；可缩小范围查看重叠曲线。</p>
<p><span class="blue">━━ A 基线</span>　<span class="orange">━━ C 提前清除调度</span>　范围：<input id="lo" type="number" min="0" max="2999" value="0"> 至 <input id="hi" type="number" min="0" max="2999" value="2999"> <button id="apply">查看</button> <button id="reset">全部 3000 例</button></p>
<canvas id="plot"></canvas><div id="tip">移动鼠标查看同一个样例的两组数据。</div>
<script>const rows=__DATA__;
const canvas=document.getElementById('plot'),ctx=canvas.getContext('2d'),lo=document.getElementById('lo'),hi=document.getElementById('hi'),tip=document.getElementById('tip');let state;
function draw(){const first=Math.max(0,Math.min(2998,Number(lo.value)||0)),last=Math.max(first+1,Math.min(2999,Number(hi.value)||2999));lo.value=first;hi.value=last;
const w=canvas.clientWidth,h=560,dpr=window.devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
const L=78,R=w-24,T=24,B=h-62,subset=rows.slice(first,last+1),ymax=Math.max(...subset.flatMap(r=>[r.baseline_last_clear_s,r.c_last_clear_s]))*1.05;
const end=last===2999?3000:last,X=i=>L+(i-first)/(end-first)*(R-L),Y=v=>B-v/ymax*(B-T);state={first,last,L,R,T,B,X,Y,w,h};ctx.font='13px system-ui';ctx.lineWidth=1;
for(let j=0;j<=5;j++){let yy=Y(ymax*j/5);ctx.strokeStyle='#e5e9f0';ctx.beginPath();ctx.moveTo(L,yy);ctx.lineTo(R,yy);ctx.stroke();ctx.fillStyle='#465268';ctx.fillText(Math.round(ymax*j/5),8,yy+4)}
for(let j=0;j<=6;j++){let i=Math.round(first+(end-first)*j/6);ctx.fillText(i,X(i)-12,B+25)}
ctx.fillText('测评样本索引',w/2-40,h-12);ctx.fillText('虚拟秒',8,17);
for(const [key,color] of [['baseline_last_clear_s','#2563eb'],['c_last_clear_s','#ea580c']]){ctx.strokeStyle=color;ctx.lineWidth=subset.length>500?.7:1.5;ctx.globalAlpha=.75;ctx.beginPath();subset.forEach((r,i)=>i?ctx.lineTo(X(r.index),Y(r[key])):ctx.moveTo(X(r.index),Y(r[key])));ctx.stroke()}ctx.globalAlpha=1;}
canvas.addEventListener('mousemove',e=>{const s=state,x=e.clientX-canvas.getBoundingClientRect().left;const i=Math.max(s.first,Math.min(s.last,Math.round(s.first+(x-s.L)/(s.X(s.last)-s.L)*(s.last-s.first))));const r=rows[i];tip.textContent=`索引 ${i}｜seed ${r.seed}｜${r.N} 源｜A ${r.baseline_last_clear_s.toFixed(2)} 秒｜C ${r.c_last_clear_s.toFixed(2)} 秒｜C−A ${r.delta_c_minus_baseline_s.toFixed(2)} 秒（负数表示 C 更早清完）`;});
document.getElementById('apply').onclick=draw;document.getElementById('reset').onclick=()=>{lo.value=0;hi.value=2999;draw()};window.addEventListener('resize',draw);draw();
</script></html>'''
    (out/'last_clear_interactive.html').write_text(html.replace('__DATA__',json.dumps(pairs,ensure_ascii=False)),encoding='utf-8')
    ci=stats['ci95_mean_delta_s']
    text=(f"# 基线与 C 组：全部清除时间对比\n\n"
          f"复用四组对照中的相同 3000 个场景，按 seed 升序配对；场景哈希、源数和完整清除均核验通过。指标为 last_clear_s，不包含后续证明无源的耗时。\n\n"
          f"| 指标 | 结果 |\n|---|---:|\n| 基线平均全部清除时间 | {y_a.mean():.2f} 秒 |\n| C 组平均全部清除时间 | {y_c.mean():.2f} 秒 |\n"
          f"| C−基线平均差值 | {delta.mean():+.2f} 秒 |\n| 平均时间降幅 | {stats['reduction_percent']:.3f}% |\n"
          f"| 配对差值 95% bootstrap 区间 | [{ci[0]:+.2f}, {ci[1]:+.2f}] 秒 |\n"
          f"| C 更早 / 持平 / 更晚清完 | {stats['earlier']} / {stats['tied']} / {stats['later']} |\n\n"
          "折线保留全部原始数据，未平滑或按耗时排序。3000 条数据对应索引 0–2999，横轴展示 0–3000。PNG/PDF/SVG 为同一张双折线图；HTML 可选取索引范围并悬停查看数值，CSV 提供逐样例配对数据。\n\n"
          "这是对已完成对照的补充指标分析，不是新一轮独立试验。最后清除更早不等于含无源证书的整局总耗时更短；原四组比较中 C 组总耗时未显著改善。\n")
    (out/'report.md').write_text(text,encoding='utf-8')
    print(json.dumps(stats,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
