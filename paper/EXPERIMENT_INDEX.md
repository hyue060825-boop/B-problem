# 实验与证据索引

入口：[论文写作指导说明书](论文写作指导说明书.md) · [模型身份](model_registry.json) · [图表索引](FIGURE_INDEX.md) · [统计表](tables/)

正文数据见下表前四项。旧版、失败、中断与阴性结果也全部归档；名称中的 best/final 不代表本分支最终选型。计划材料本身不证明实验完成。

## 正文与附录快速入口

| 材料 | 模型/用途 |
|---|---|
| [report.md](../runs/q34_deadline_test3000_20260913/report.md) | 最终Q3；Q4行属于父基线 |
| [report.md](../runs/q4_baseline_8gpu_1h_20260913/evaluation/report.md) | 最终Q4与父模型配对 |
| [final_main_results.csv](tables/final_main_results.csv) | 两份最终权重主表 |
| [training_data_accounting.csv](tables/training_data_accounting.csv) | 整段训练和入选best之前的数据量 |
| [report.md](../runs/q3_layout_extremes_20260913_v2/report.md) | 最终Q3构造极端布局 |
| [tail_analysis.png](../runs/q4_absence_tail_analysis_20260913_v2/tail_analysis.png) | Q4父基线尾段图 |
| [q4_planning_ablation_20260913](../runs/q4_planning_ablation_20260913) | Q4父基线四组对照及3000局A/C曲线 |
| [q4_empty_arena_20260913](../runs/q4_empty_arena_20260913) | Q4父基线空场景 |
| [q4_layout_extremes_20260913](../runs/q4_layout_extremes_20260913) | Q4父基线极端布局 |
| [logQ4.jsonl](official_logs/logQ4.jsonl) | Q4父基线官方单例；非批量官方测试 |
| [protocols](protocols) | 所有用户提供的原方案与优化提示词 |
| [original_reports](history/original_reports) | 原始报告（标题和结论保留写作时语境） |
| [original_docs](history/original_docs) | 原始设计/运行说明 |
| [artifacts](../artifacts) | Q1/Q2输入、结果、图形与来源 |
| [report.md](../runs/q4_final_best_counts_20260913/evaluation/report.md) | 新增：最终Q4 c8812ced，10–16源各1000局；六张分布图 |

## 所有历史实验目录

| 原目录 | 证据归属 | 原始证据文件数 | 可浏览报告和图 | 完整压缩档案 |
|---|---|---:|---|---|
| `runs/ddp_20260911` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 13 | [浏览](history/runs/ddp_20260911/readable) | [校验清单及分卷](history/runs/ddp_20260911/archive_manifest.json) |
| `runs/large_20260911` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 3270 | [浏览](history/runs/large_20260911/readable) | [校验清单及分卷](history/runs/large_20260911/archive_manifest.json) |
| `runs/legacy_deadline_20260913` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 3 | [浏览](history/runs/legacy_deadline_20260913/readable) | [校验清单及分卷](history/runs/legacy_deadline_20260913/archive_manifest.json) |
| `runs/q34_3000_test_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 17 | [浏览](history/runs/q34_3000_test_20260912/readable) | [校验清单及分卷](history/runs/q34_3000_test_20260912/archive_manifest.json) |
| `runs/q34_deadline_test3000_20260913` | 正文：最终Q3；该目录Q4行是父基线 | 19 | [浏览](history/runs/q34_deadline_test3000_20260913/readable) | [校验清单及分卷](history/runs/q34_deadline_test3000_20260913/archive_manifest.json) |
| `runs/q34_structural_20260912` | 历史不同架构：结构化优化、DDP、瓶颈与对照 | 347 | [浏览](history/runs/q34_structural_20260912/readable) | [校验清单及分卷](history/runs/q34_structural_20260912/archive_manifest.json) |
| `runs/q3_3000_test_20260911` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 4 | [浏览](history/runs/q3_3000_test_20260911/readable) | [校验清单及分卷](history/runs/q3_3000_test_20260911/archive_manifest.json) |
| `runs/q3_best_finetune_20260913` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 2 | 见压缩包 | [校验清单及分卷](history/runs/q3_best_finetune_20260913/archive_manifest.json) |
| `runs/q3_current_best_eval_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 8 | [浏览](history/runs/q3_current_best_eval_20260912/readable) | [校验清单及分卷](history/runs/q3_current_best_eval_20260912/archive_manifest.json) |
| `runs/q3_final_best_counts_20260912` | 附录：Q3父模型8cc3，10–16源每组1000局 | 74 | [浏览](history/runs/q3_final_best_counts_20260912/readable) | [校验清单及分卷](history/runs/q3_final_best_counts_20260912/archive_manifest.json) |
| `runs/q3_gpu8_extended_20260912` | Q3父模型训练、GPU搜索与独立评估 | 2690 | [浏览](history/runs/q3_gpu8_extended_20260912/readable) | [校验清单及分卷](history/runs/q3_gpu8_extended_20260912/archive_manifest.json) |
| `runs/q3_gpu8_extended_source_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 79 | [浏览](history/runs/q3_gpu8_extended_source_20260912/readable) | [校验清单及分卷](history/runs/q3_gpu8_extended_source_20260912/archive_manifest.json) |
| `runs/q3_gpu8_smoke_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 137 | [浏览](history/runs/q3_gpu8_smoke_20260912/readable) | [校验清单及分卷](history/runs/q3_gpu8_smoke_20260912/archive_manifest.json) |
| `runs/q3_gpu_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 57 | [浏览](history/runs/q3_gpu_20260912/readable) | [校验清单及分卷](history/runs/q3_gpu_20260912/archive_manifest.json) |
| `runs/q3_joint_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 2179 | [浏览](history/runs/q3_joint_20260912/readable) | [校验清单及分卷](history/runs/q3_joint_20260912/archive_manifest.json) |
| `runs/q3_layout_extremes_20260913` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 4 | [浏览](history/runs/q3_layout_extremes_20260913/readable) | [校验清单及分卷](history/runs/q3_layout_extremes_20260913/archive_manifest.json) |
| `runs/q3_layout_extremes_20260913_v2` | 附录：最终Q3主动搜索极端布局 | 36 | [浏览](history/runs/q3_layout_extremes_20260913_v2/readable) | [校验清单及分卷](history/runs/q3_layout_extremes_20260913_v2/archive_manifest.json) |
| `runs/q3_legacy_deadline_20260913` | 最终Q3训练谱系 | 6668 | [浏览](history/runs/q3_legacy_deadline_20260913/readable) | [校验清单及分卷](history/runs/q3_legacy_deadline_20260913/archive_manifest.json) |
| `runs/q3_ppo_20260911` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 76 | [浏览](history/runs/q3_ppo_20260911/readable) | [校验清单及分卷](history/runs/q3_ppo_20260911/archive_manifest.json) |
| `runs/q4_3000_test_20260911` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 4 | [浏览](history/runs/q4_3000_test_20260911/readable) | [校验清单及分卷](history/runs/q4_3000_test_20260911/archive_manifest.json) |
| `runs/q4_absence_tail_analysis_20260913` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 8 | [浏览](history/runs/q4_absence_tail_analysis_20260913/readable) | [校验清单及分卷](history/runs/q4_absence_tail_analysis_20260913/archive_manifest.json) |
| `runs/q4_absence_tail_analysis_20260913_v2` | 附录：Q4父基线3000局无源尾段复放 | 10 | [浏览](history/runs/q4_absence_tail_analysis_20260913_v2/readable) | [校验清单及分卷](history/runs/q4_absence_tail_analysis_20260913_v2/archive_manifest.json) |
| `runs/q4_baseline_8gpu_1h_20260913` | 最终Q4训练与3000局配对主结果 | 781 | [浏览](history/runs/q4_baseline_8gpu_1h_20260913/readable) | [校验清单及分卷](history/runs/q4_baseline_8gpu_1h_20260913/archive_manifest.json) |
| `runs/q4_belief_attention_20260912` | 历史不同架构：信念注意力尝试，不是最终方法 | 57 | [浏览](history/runs/q4_belief_attention_20260912/readable) | [校验清单及分卷](history/runs/q4_belief_attention_20260912/archive_manifest.json) |
| `runs/q4_budget_20260912` | 更早Q4基线训练与验证 | 3931 | [浏览](history/runs/q4_budget_20260912/readable) | [校验清单及分卷](history/runs/q4_budget_20260912/archive_manifest.json) |
| `runs/q4_certificate_search_20260912` | 附录：几何证书/缩减布局反例，独立工具 | 20 | [浏览](history/runs/q4_certificate_search_20260912/readable) | [校验清单及分卷](history/runs/q4_certificate_search_20260912/archive_manifest.json) |
| `runs/q4_closed_loop_20260913` | 历史闭环优化尝试，不是最终方法 | 65 | [浏览](history/runs/q4_closed_loop_20260913/readable) | [校验清单及分卷](history/runs/q4_closed_loop_20260913/archive_manifest.json) |
| `runs/q4_continue_paired_3000_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 10 | [浏览](history/runs/q4_continue_paired_3000_20260912/readable) | [校验清单及分卷](history/runs/q4_continue_paired_3000_20260912/archive_manifest.json) |
| `runs/q4_continue_paired_smoke_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 9 | [浏览](history/runs/q4_continue_paired_smoke_20260912/readable) | [校验清单及分卷](history/runs/q4_continue_paired_smoke_20260912/archive_manifest.json) |
| `runs/q4_empty_arena_20260913` | 附录：Q4父基线零源诊断（不属常规分布） | 5 | [浏览](history/runs/q4_empty_arena_20260913/readable) | [校验清单及分卷](history/runs/q4_empty_arena_20260913/archive_manifest.json) |
| `runs/q4_layout_extremes_20260913` | 附录：Q4父基线主动搜索极端布局 | 36 | [浏览](history/runs/q4_layout_extremes_20260913/readable) | [校验清单及分卷](history/runs/q4_layout_extremes_20260913/archive_manifest.json) |
| `runs/q4_legacy_deadline_20260913` | Q4父基线；补充实验的重要参照 | 4279 | [浏览](history/runs/q4_legacy_deadline_20260913/readable) | [校验清单及分卷](history/runs/q4_legacy_deadline_20260913/archive_manifest.json) |
| `runs/q4_legacy_deadline_smoke_20260913` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 10 | [浏览](history/runs/q4_legacy_deadline_smoke_20260913/readable) | [校验清单及分卷](history/runs/q4_legacy_deadline_smoke_20260913/archive_manifest.json) |
| `runs/q4_old_new_paired_20260912_v2` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 2 | [浏览](history/runs/q4_old_new_paired_20260912_v2/readable) | [校验清单及分卷](history/runs/q4_old_new_paired_20260912_v2/archive_manifest.json) |
| `runs/q4_optimization_20260912` | 附录：精确覆盖证明与探索证据 | 32 | [浏览](history/runs/q4_optimization_20260912/readable) | [校验清单及分卷](history/runs/q4_optimization_20260912/archive_manifest.json) |
| `runs/q4_planning_ablation_20260913` | 附录：Q4父基线A/B/C/D负结果与最后清除曲线 | 26 | [浏览](history/runs/q4_planning_ablation_20260913/readable) | [校验清单及分卷](history/runs/q4_planning_ablation_20260913/archive_manifest.json) |
| `runs/q4_ppo_20260911` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 76 | [浏览](history/runs/q4_ppo_20260911/readable) | [校验清单及分卷](history/runs/q4_ppo_20260911/archive_manifest.json) |
| `runs/q4_repaired_20260912` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 145 | [浏览](history/runs/q4_repaired_20260912/readable) | [校验清单及分卷](history/runs/q4_repaired_20260912/archive_manifest.json) |
| `runs/smoke_20260911` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 6 | 见压缩包 | [校验清单及分卷](history/runs/smoke_20260911/archive_manifest.json) |
| `workspace/scripts` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 54 | 见压缩包 | [校验清单及分卷](history/workspace/scripts/archive_manifest.json) |
| `workspace/tests` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 25 | 见压缩包 | [校验清单及分卷](history/workspace/tests/archive_manifest.json) |
| `workspace/solution` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 34 | 见压缩包 | [校验清单及分卷](history/workspace/solution/archive_manifest.json) |
| `workspace/bsim` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 21 | 见压缩包 | [校验清单及分卷](history/workspace/bsim/archive_manifest.json) |
| `workspace/configs` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 29 | 见压缩包 | [校验清单及分卷](history/workspace/configs/archive_manifest.json) |
| `workspace/reports` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 39 | 见压缩包 | [校验清单及分卷](history/workspace/reports/archive_manifest.json) |
| `workspace/docs` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 18 | 见压缩包 | [校验清单及分卷](history/workspace/docs/archive_manifest.json) |
| `workspace/logs` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 1 | 见压缩包 | [校验清单及分卷](history/workspace/logs/archive_manifest.json) |
| `workspace/experiments` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 1 | 见压缩包 | [校验清单及分卷](history/workspace/experiments/archive_manifest.json) |
| `workspace/run_logs` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 18 | 见压缩包 | [校验清单及分卷](history/workspace/run_logs/archive_manifest.json) |
| `workspace/external_logs` | 历史探索/复现实验；以该档案配置、状态和报告为准，不冒充最终权重结果 | 10 | 见压缩包 | [校验清单及分卷](history/workspace/external_logs/archive_manifest.json) |

## 解包复核

分卷均小于40 MiB。压缩包保留原相对路径，逐文件SHA256在清单中。用新目录解包，不覆盖当前代码：

```bash
python scripts/extract_experiment_archive.py paper/history/runs/q4_planning_ablation_20260913/archive_manifest.json cache/replay_ablation
```

压缩包包含逐局样本、日志、训练标签张量及原脚本；不用的模型权重只存本地cache。完整原件25984项均有原始SHA256。历史报告可能引用本地cache中的旧权重，不能将其当成独立部署包。
