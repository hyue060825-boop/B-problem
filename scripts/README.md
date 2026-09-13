# 脚本入口

| 用途 | 入口 |
| --- | --- |
| 最终部署、自检、便携包 | `run_policy.py`、`build_windows_policy_bundle.py` |
| 最终表格复算、资产核验 | `build_final_handoff_assets.py`、`verify_final_assets.py` |
| 新配对评测 | `evaluate_final_pair.py`；显式指定新种子与新输出目录 |
| 最终续训流程 | `train_legacy_deadline_ddp.py`、`launch_q4_baseline_8gpu_hour.py` |
| 精确覆盖证书 | `build_q4_witness_certificate.py`、`verify_q4_certificate_exact.py` |
| Q4 父模型补充分析 | `analyze_q4_absence_tail.py`、`evaluate_q4_planning_ablation.py`、`evaluate_q4_empty_arena.py` |
| 有限布局搜索 | `search_q3_layout_extremes.py` 使用最终 Q3；`search_q4_layout_extremes.py` 使用父 Q4 |
| 原始结果再分析 | `report_*`、`plot_q4_last_clear_comparison.py`，先看 `--help`，写入新工作目录 |
| 前期研究与 Q2 文献实验 | 既有训练、评估入口；`experiment_q2_literature.py`、`build_q2_literature_assets.py` |

运行命令见[最终复现](../docs/simulator/最终模型复现.md)。`evaluate_deadline_pair.py` 保留旧阶段组合，不是最终 Q4；原 main 的研究部署入口保留为 `run_policy_research.py`。论文手的 `build_final_paper_assets.py` 会写入 `paper/`，实验侧交付使用 `build_final_handoff_assets.py`。

所有入口保持原方法和计算过程，适配只涉及路径、运行时选择和输出保护。历史一次性整理脚本在 `records/acceptance/experiment_result-8ef9ef8/` 及历史压缩档案中，只作来源记录。
