# 脚本入口

- 论文图表与审计：`build_paper_catalog.py`、`verify_paper_release.py`、`extract_experiment_archive.py`。
- 最终推理与打包：`run_policy.py`、`build_windows_policy_bundle.py`、`check_q3_local_http.py`。
- 最终Q4固定源数评测：`evaluate_q4_source_counts.py`，10–16源各1000局、六张分布图。
- 最终模型新配对评测：`evaluate_final_pair.py`。`evaluate_deadline_pair.py`用于历史凌晨模型组合。
- 同架构补充分析：`analyze/report_q4_absence_tail.py`、`evaluate/report_q4_planning_ablation.py`、`plot_q4_last_clear_comparison.py`、`evaluate_q4_empty_arena.py`、`search/report_q3_layout_extremes.py`、`search/report_q4_layout_extremes.py`。
- 覆盖证明：`verify_q4_certificate_exact.py`、`build_q4_witness_certificate.py`、`validate_coverage.py`。
- 最终训练入口：`train_legacy_deadline_ddp.py`、`launch_q4_baseline_8gpu_hour.py`，使用已归档训练配置的新副本；不要复用旧输出目录和截止时间。
- `organize_paper_branch.py` 是本次一次性迁移记录，已有cache时会拒绝重跑；不要用它整理新克隆。

斜线合写的 `analyze/report_...` 表示两份独立脚本的名称前缀。各脚本以 `--help` 或源码参数为准。其他早期训练入口与所有原脚本在 `paper/history/workspace/scripts/` 压缩包中；部分兼容版本单列于 `paper/history/legacy_entrypoints/`。
