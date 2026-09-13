# 2026-09-13 完整最终交付

来源 `experiment_result@8ef9ef8` 的全部 `runs/` 按原实验目录名接收。这里包括最终权重、父模型、主实验、补充分析与少量探索结果；文件名 best/final 不自动等于最终选型。

- 方法和证据入口：[最终方案](../../handoff/shared/最终方案与实验说明.md)、[完整实验索引](../../handoff/shared/最终实验索引.md)。
- 最终权重：`q3_legacy_deadline_20260913/best.pt`、`q4_baseline_8gpu_1h_20260913/train/best.pt`；身份见[模型清单](../../records/inventory/models-final-20260913.json)。
- 主结果：`q34_deadline_test3000_20260913/` 的 Q3 配对；`q4_baseline_8gpu_1h_20260913/train/final_test.json` 的 Q4 配对。凌晨批次中 Q4 best 是当前父模型。
- 历史完整分卷：[history](../history/experiment_result-8ef9ef8/)，不是新的独立实验；可浏览副本与活动目录可能重复。
- 论文已引用的子集仍在 [final-8ef9ef8](../final-8ef9ef8/README.md)，保留路径和原表，不重复计为新证据。

原数据、训练配置、日志及代码快照保持字节；服务器绝对路径按[接收映射](../../records/acceptance/experiment_result-8ef9ef8/资产落位建议.csv)定位。新的运行和衍生分析放其他目录，不覆盖本批。
