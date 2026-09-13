# 最终实验表

主表为 `final_main_results.csv`，源数分组为 `final_by_source_count.csv`，配对区间为 `paired_effects.csv`；均从逐局记录复算，证据路径指向 main 完整批次。Q3 父模型行来源已修正为 baseline 文件，配对表分别列出两侧来源。

`training_data_accounting.csv` 区分入选 best 之前与整段训练；`validation_curves.csv` 属于选模验证。其余表沿用原补充分析数值，分别标注 q3_final、q3_parent、q4_parent；不能合并成最终模型的同一批实验。

运行 `python scripts/build_final_handoff_assets.py` 更新本目录及输入清单，不修改论文或原始数据。交付时的原表见[来源副本](../../../records/acceptance/experiment_result-8ef9ef8/source-adapted/paper/tables/)，图与原始证据见[实验索引](../../shared/最终实验索引.md)。
