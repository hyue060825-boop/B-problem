"""Render the diagnostic replay statistics without rerunning the policy."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'deployment/runtime_public_v2'))
from solution.control.controller import Controller


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    args = parser.parse_args()
    from _final_paths import require_report_workspace
    require_report_workspace(args.input)
    dest = Path(args.input)
    summary = json.loads((dest / 'summary.json').read_text())
    official = json.loads((dest / 'official_log_summary.json').read_text())
    events = json.loads((dest / 'official_events.json').read_text())
    rows = [json.loads(line) for line in (dest / 'replay.jsonl').read_text().splitlines()]
    assert len(rows) == 3000 and all(r['completion'] and not r['error'] for r in rows)
    assert all(r['cleared_total'] == r['discovered_total'] == r['N'] for r in rows)
    assert summary['replay_validation']['max_absolute_delta_s'] == 0
    assert summary['replay_validation']['max_cost_error'] < 1e-5

    # Reconstruct clearance certificates from public observations alone.
    ctl = Controller(4)
    ready, request = {}, None
    for line in Path('results/official/q4-20260913/logQ4.jsonl').read_text(encoding='utf-8-sig').splitlines():
        row = json.loads(line)
        if row['status'] == 'REQUEST':
            request = row['request']
        elif row['status'] == 'RESPONSE' and row['response'].get('accepted'):
            response = row['response']
            if row['path'] == '/measure':
                pos = request['position']
                ch = request['channel']
                ctl.observe(ch, (pos['x'], pos['y']), response['measure_result'], response.get('svd_deg'))
                if ctl.channels[ch].status == 'CLEARABLE':
                    ready.setdefault(ch, response['virtual_time_s'])
            elif row['path'] == '/clear':
                ctl.clear_result(request['channel'], response['clear_result'] == 'success')
    cover_late = sum(max(0., e['end'] - max(6000., e['start'])) for e in events if e['kind'] == 'no_signal')
    extra = dict(official_first_clearable_s=ready, official_after6000_cover_action_s=cover_late)
    (dest / 'additional_statistics.json').write_text(json.dumps(extra, indent=2))
    lt = summary['lt16']
    n16 = summary['by_N']['16']
    group = [r for r in rows if r['N'] < 16]
    lines = [
        '# Q4 3000 样例：无源确认与末段搜索统计分析',
        '',
        '你的观察有数据支持：低于 16 源时，后段大量测量没有信号，空频道覆盖明显增加耗时。但“6000 秒以后都已清完，只在证明无源”并不符合全部样例；确认空频道与处理已发现源经常交错。',
        '',
        '## 数据与口径',
        '',
        '- 原始评测：`results/final-20260913/q34_deadline_test3000_20260913/q4_best_samples.json`，3000 个场景，种子 1245000000–1245002999。',
        '- 模型：`results/final-20260913/q4_legacy_deadline_20260913/best.pt`，SHA256 `e8a525f78d176d9073372394b324bd585f4445fbf9cd1515141c483f38d5bd90`，与提供的官方日志一致。',
        '- 原数据没有逐动作时间，故用同一模型、同一场景及匹配的冻结运行时补录。3000/3000 完成；场景哈希逐例核验；总虚拟耗时逐例完全一致，最大差值 0 秒；动作成本分解误差 0 秒。原记录未保存完整轨迹，不能额外声称原轨迹逐动作已核对。',
        '- 全文时间均为模拟器虚拟秒，不是 GPU 推理或现实等待时间。发现指该频道首次出现 direction/near 信号，不等于已精确定位或清除。',
        '- T 为退出总耗时；F 为最后一个真实源首次出现信号的时间；C 为最后一次成功清除时间；纯收尾 H=T−C。H 不包括清除前穿插的空频道搜索，也不是可直接兑现的加速收益。真实源数只用于事后统计，没有输入策略。',
        '- 无信号率按测量次数汇总（不包含 clear 请求）；6000 秒后按动作结束时间分类，跨过阈值的测量归入后段。分组耗时占比使用 sum(H)/sum(T)，与逐局 H/T 再平均不同。',
        '',
        '## 按源数统计',
        '',
        '| 源数 | 样例数 | 平均总耗时 T | 平均全部发现 F | 平均全部清除 C | 平均纯收尾 H | 纯收尾占总时 | 6000 秒后无信号率 |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for n in range(10, 17):
        r = summary['by_N'][str(n)]
        lines.append(f"| {n} | {r['episodes']} | {r['total_s']:.1f} | {r['last_discovery_s']:.1f} | {r['last_clear_s']:.1f} | {r['tail_s']:.1f} | {r['pooled_tail_time_fraction']:.2%} | {r['after_6000_pooled_negative_rate']:.2%} |")
    lines += [
        '',
        f"16 源平均 {n16['total_s']:.1f} 秒，中位数 {n16['total_s_p50_p95'][0]:.1f} 秒；423 例中只有 42 例（{42/423:.2%}）在 5000–6000 秒完成，154 例（{154/423:.2%}）在 6000 秒内完成。因而‘16 源基本 5000–6000 秒’适用于部分场景，不能概括这批测试集。",
        '',
        f"低于 16 源的 2577 例平均总耗时 {lt['total_s']:.1f} 秒，比 16 源组高 {lt['total_s']-n16['total_s']:.1f} 秒（描述性差异，不是同场景消融的因果收益）。平均纯收尾 {lt['tail_s']:.1f} 秒，占累计总耗时 {lt['pooled_tail_time_fraction']:.2%}；逐局比例再平均为 {lt['tail_fraction']:.2%}。",
        '',
        f"纯收尾中位数 {lt['tail_s_p50_p95'][0]:.1f} 秒，P95 为 {lt['tail_s_p50_p95'][1]:.1f} 秒。{sum(r['tail_s']>1e-6 for r in group)} 例存在纯收尾，{sum(r['tail_s']>3000 for r in group)} 例超过 3000 秒，{sum(r['tail_s']>6000 for r in group)} 例超过 6000 秒；因此均值掩盖了明显的长尾。",
        '',
        f"纯收尾平均成本：移动 {lt['tail_move_s']:.1f} 秒（{lt['tail_move_s']/lt['tail_s']:.2%}）、测量 {lt['tail_measure_s']:.1f} 秒、换频道 {lt['tail_switch_s']:.1f} 秒。这说明优化覆盖路线有价值，仅加速神经网络推理无法缩短这些虚拟动作成本。",
        '',
        '## 6000 秒后的测量是否基本没有价值',
        '',
        f"低于 16 源组，6000 秒后有 {lt['after_6000_measure_count']:,} 次测量，其中 {lt['after_6000_pooled_negative_rate']:.2%} 为 no_signal；{lt['after_6000_absent_channel_measures']:,} 次（占全部后段测量 {lt['after_6000_absent_channel_measures']/lt['after_6000_measure_count']:.2%}）发生在实际不存在源的频道。后者是事后真值分类，不是当时策略已知的事实。",
        '',
        f"但仍有 {lt['episodes_with_late_discovery']} / 2577 例（{lt['episodes_with_late_discovery']/2577:.2%}）在 6000 秒以后首次发现新的源，共 {sum(r['after6000_discovery_count'] for r in group)} 个；只有 {lt['all_cleared_by_6000']} 例（{lt['all_cleared_by_6000']/2577:.2%}）在 6000 秒前全部清除。直接按 6000 秒退出，会使其余 {2577-lt['all_cleared_by_6000']} 例在该时刻仍有未清除源。",
        '',
        f"6000 秒后的累计时间里，严格落在最后一次清除之后的部分占 {lt['after_6000_time_pure_tail_fraction']:.2%}。其余时间混合了覆盖、定位和清除，不能全算作有用时间，也不能全算作纯收尾。另有 {lt['after_6000_clear_failures']:,} 次清除失败、{lt['after_6000_clear_successes']:,} 次清除成功；‘测量大多无信号’这一比例本身遗漏了清除动作。",
        '',
        '## 哪类样例最符合“源早已处理完，却长时间搜空区域”',
        '',
        '| 场景类别（均为 N<16） | 样例数 | 平均总耗时 | 平均纯收尾 | 6000 秒后才发现新源的样例比例 |',
        '|---|---:|---:|---:|---:|',
    ]
    for d in ('area', 'edge', 'cluster', 'outward'):
        rr = [r for r in group if r['distribution'] == d]
        lines.append(f"| {d} | {len(rr)} | {np.mean([r['total_s'] for r in rr]):.1f} | {np.mean([r['tail_s'] for r in rr]):.1f} | {np.mean([r['after6000_discovery_count']>0 for r in rr]):.2%} |")
    lines += [
        '',
        '聚集场景（cluster）的纯收尾最重；向外定向场景（outward）则经常需要到后期才能发现源。当前 profile 同时绑定了分布与场强模式：area/smooth、edge/extreme、cluster/smooth、outward/zero，因此这里是联合场景分层，不能把全部差异只归因于空间分布，也不能直接视为官方出题概率。',
        '',
        '## 提供的官方日志：搜索还推迟了已知源的清除',
        '',
        '日志公开观测到并成功清除 14 个不同频道，以下按这 14 个源讨论；日志没有独立提供隐藏源数，不以观察到的数量冒充官方真值。',
        '',
        '| 里程碑 | 虚拟时间（秒） |',
        '|---|---:|',
        '| 这 14 个频道均已至少出现一次信号 | 413.00 |',
        '| 清除第 12 个源 | 4498.61 |',
        '| 清除第 13 个源（频道 8） | 6178.53 |',
        '| 清除第 14 个源（频道 3），随后退出 | 9236.07 |',
        '',
        f"6000 秒后的 65 次测量全部为 no_signal，且全部针对最终未发现源的 6 个频道。该时间段共 {official['after_6000_s']:.2f} 秒，按实际请求时间区间拆分，其中 {cover_late:.2f} 秒（{cover_late/official['after_6000_s']:.2%}）落在这些覆盖测量及其移动上，剩余时间属于两次清除及其移动。这比单看纯收尾 H=0 更能说明你指出的问题。",
        '',
        f"进一步用日志中的公开测量重建几何状态：频道 3 在 {ready[3]:.2f} 秒就已达到 CLEARABLE，频道 8 在 {ready[8]:.2f} 秒达到 CLEARABLE，却分别直到 9236.07 秒和 6178.53 秒才清除。这里确实存在可清除任务被覆盖任务延后的现象。证书就绪到清除的间隔包含服务其他源、移动及覆盖，并不全是可省耗时；本分析也未证明‘一旦可清除就立即过去’一定是总路线最优。",
        '',
        '## 机制与下一步优化方向',
        '',
        '匹配 checkpoint 的冻结控制器中，公开发现数量达到 16 时，可利用题目给出的数量上限，将其他未发现频道标为无源；少于 16 时，则要求未知频道在全部 31 个认证站点取得负观测。由于有 20 个频道，N=10…15 时，实际空频道全程测量次数逐例为 (20−N)×31，即 310、279、248、217、186、155 次。相应纯测量成本为 1550、1395、1240、1085、930、775 秒，尚未计换频和覆盖移动。',
        '',
        'Q4 单次 no_signal 不能直接排除整个圆盘，因为源有方向性。完整站点证书是当前实现的充分退出条件，并不代表理论上不存在更短的有效证书。16 源与低源数的耗时差异与这一机制一致；要量化其净因果代价，仍需保持清除完整性和退出证书有效的配对策略消融。',
        '',
        '建议首先优化有效证书所需的剩余覆盖路线、共享站点扫描和 CLEARABLE 与 COVER 的联合调度；之后研究能严格维护方向/位置可行域的自适应无源证书，减少必须访问的站点。不能仅凭连续无信号或经过 6000 秒便判定剩余源不存在。固定时限/概率提前退出若作为实验，必须单独报告漏源率与完成率。',
        '',
        '后续训练与验证应同时记录 F、C、T、H、可清除任务等待时间、空频道扫描量及清除失败数。只优化 H 可能通过推迟最后一个清除动作获得表面改善，必须同时比较总时间与完整清除率。这批 3000 样例已用于诊断；调参后应另取独立测试集验证，避免将对该批样例的适配当作泛化提升。',
        '',
        '## 产物与复核',
        '',
        '- `samples.csv` / `replay.jsonl`：3000 条逐样例分解。',
        '- `summary.json`：按源数、联合场景分层汇总。',
        '- `official_events.json` / `official_log_summary.json`：官方日志动作时间与汇总。',
        '- `additional_statistics.json`：公开观测重建的最早可清除时间及官方后段覆盖时间。',
        '- `manifest.json`：模型、原始样例和日志的 SHA256。',
        '- `tail_analysis.png` / `tail_analysis.pdf`：耗时分解、尾部箱线图、官方发现/清除曲线。箱线图未展示离群点，P95 见上文；纯收尾为零不代表没有穿插的无源确认成本。',
        '',
        '复现（输出目录须不存在）：',
        '',
        '```bash',
        './scripts/run_python.sh scripts/analyze_q4_absence_tail.py --output results/final-20260913/q4_absence_tail_new',
        './scripts/run_python.sh scripts/report_q4_absence_tail.py --input results/final-20260913/q4_absence_tail_new',
        '```',
    ]
    (dest / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(extra, ensure_ascii=False, indent=2))
    print(dest / 'report.md')


if __name__ == '__main__':
    main()
