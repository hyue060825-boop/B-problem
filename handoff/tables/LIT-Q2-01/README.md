# LIT-Q2-01 数据表

**本批新增｜实际观测与执行结果**。完整解释见[独立交付](../../shared/文献启发与Q2改进说明.md)。

| 文件 | 含义 |
| --- | --- |
| [summary.csv](summary.csv) | 四方法各120场景；完成数、实际后验均值、耗时与计算成本 |
| [paired.csv](paired.csv) | 各方法减当前Q2；配对均值差与95%区间半宽；better表示该指标数值更小 |
| [samples.csv](samples.csv) | 480条逐局指标；posterior_contains_truth是评价端核验，不能作为策略输入 |
| [sensitivity.csv](sensitivity.csv) | 9参数配置，每配置12场景；独立小批，不与120场景直接混合 |
| [provenance.json](provenance.json) | 原始输入、生成脚本及4表/3图/3规格的SHA-256 |

`posterior_radius_m`、`posterior_diameter_m`、`posterior_area_m2`来自实际第二次观测；`predicted_radius_m`、`predicted_J_s`是事先的有限情景估计。`clear_ready`表示当时可行域通过半径19.98 m的保护证书，并不等于实际源已被清除。`completed`只在清除返回success后成立。

`total_virtual_s`含首次5秒及完整后续动作；`second_action_s`仅第二次移动和检测；`selection_s`是本机选点墙钟时间。主实验比较约129或31候选，并非相同候选数量下的方向消融。敏感性5档等距网格也不等于主实验的非等距5档。

重绘复算：`python scripts/build_q2_literature_assets.py`，不会改变原始记录。旧Q2预测算例表保留在上级目录，不能称其为本次真实补测结果。
