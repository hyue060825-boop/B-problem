# 可引用数据表

这些表格从已有原始记录复算，CSV 使用 UTF-8 BOM，便于 Excel 读取。字段保留英文以便脚本处理，含义如下。数值计算用完整精度，正文可按需要保留两至四位小数。

| 文件 | 内容与主要字段 |
| --- | --- |
| [q1_examples.csv](q1_examples.csv) | 两个人工算例；`diameter_m` 直径，`diameter_circle_covers` 覆盖判定，`mec_radius_m` 最小包围圆半径 |
| [q2_comparison.csv](q2_comparison.csv) | 最佳已评估点、沿示向线和固定侧翼；接收上界、采样后验半径、估计剩余时间、J |
| [q2_candidates.csv](q2_candidates.csv) | 每个已评估候选的坐标、接收保证与评分；不是连续全局搜索结果 |
| [q3_coverage_parameters.csv](q3_coverage_parameters.csv) | 不同六边形外圈半径的覆盖距离上界、裕量与证书；不是策略耗时实验 |
| [q34_summary.csv](q34_summary.csv) | 四组最新策略，每组 3000 局的完成数、总时间与每源时间分布 |
| [q34_paired.csv](q34_paired.csv) | 同场景新减旧的平均差、近似 95% 区间、降幅及更快/持平/更慢数量 |
| [q34_strata.csv](q34_strata.csv) | 按源数 N 或空间分布分组的配对统计；探索性分组比较 |
| [training_validation.csv](training_validation.csv) | Q3 联合 PPO 和 Q4 预算 PPO 的实际验证记录点、完成率和配对差 |
| [q4_grid.json](q4_grid.json) | 31 个站点、42 个三角形、重合处邻点及连续域核验结果 |
| [provenance.json](provenance.json) | 数据来源、输入与脚本哈希、生成环境及输出校验值 |

`mean_virtual_s` 是各局总虚拟耗时的均值；`mean_per_source_s` 是先算每局 T/C 再取均值；`weighted_per_source_s` 是所有局总时间除以总清除数。`mean_delta_virtual_s` 及区间单位为 s，`mean_delta_per_source_s` 及其区间单位为 s/源。所有差值都是新减旧，负值表示新模型耗时较少。

复算：`python scripts/build_handoff_assets.py --tables-only`。该命令更新表格的来源文件，不更新已有图件及图件来源；数据改变后需执行完整命令重绘。原始数据批次与局限见[数据清单](../../records/inventory/datasets.csv)和[实验说明](../shared/训练与评估.md)。

**文献启发补充 · LIT-Q2-01**：[4份新表与来源](LIT-Q2-01/README.md)包含实际补测、120场景配对及独立参数检查；由 `python scripts/build_q2_literature_assets.py` 生成，与上表旧Q2预测算例分别使用。
