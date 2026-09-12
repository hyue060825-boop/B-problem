# 测向定位文献与本题对应

**文献启发补充 · LIT-Q2-01**。以下是本次补充的方法来源；不追溯宣称既有实现直接出自这些论文。引用条目见 [references.bib](references.bib)，本批结果与写作建议见[独立交付说明](../../handoff/shared/文献启发与Q2改进说明.md)。

## [L1] 谨慎贪心主动定位

Joshua Vander Hook, Pratap Tokekar, Volkan Isler. *Cautious Greedy Strategy for Bearing-based Active Localization: Experiments and Theoretical Analysis*. ICRA, 2012. DOI：[10.1109/ICRA.2012.6225244](https://doi.org/10.1109/ICRA.2012.6225244)。[作者条目](https://tokekar.com/vanderhook2012cautious.html)、[会议原文](https://tokekar.com/pubs/vanderhook2012cautious.pdf)。

原文 §II–IV 将移动和测量时间共同计入代价，以高斯先验和 EKF 表示位置不确定性，针对有180°歧义的传感器设计谨慎约束和侧向选点。时间性能分析依赖该估计模型及风险假设，不是本题有界误差条件下的保证。

本次借鉴“针对主要不确定方向补测、同时考虑行动成本”的思想。实现使用可行域最远点对方向，而非协方差特征向量；它是本题的几何改造，不是论文算法复现。原地重复测量不能按独立高斯样本积累精度：本题误差场在同位置保持固定。

## [L2] 有界误差下的测向传感器布设与选择

Pratap Tokekar, Volkan Isler. *Sensor Placement and Selection for Bearing Sensors with Bounded Uncertainty*. ICRA, 2013. DOI：[10.1109/ICRA.2013.6630920](https://doi.org/10.1109/ICRA.2013.6630920)。[作者条目](https://tokekar.com/tokekar2013asensor.html)、[会议原文](https://tokekar.com/pubs/tokekar2013asensor.pdf)。

原文 §III 用角域交表示有界误差下的位置集合，以位置和允许测量的最坏情况定义直径、面积不确定性；§V 分析三角网格及局部传感器选择。其环境是无可见性约束的方形区域，优化固定传感器数量与定位质量。

这为本题的几何不确定性指标提供相关依据。我们的有限情景评分只是采样估计，不能据此继承连续最坏情况保证。Q4 的圆形区域、有限接收距离和未知发射半平面需要另外证明；七站、31站和20 m清除条件均以本题推导与代码为准。

## 引用与使用边界

| 位置 | 可以引用 | 仍由本题负责 |
| --- | --- | --- |
| Q1 | [L2] 角域交与直径、面积指标 | 直径圆覆盖判断、最小包围圆及反例 |
| Q2 | [L1] 代价与选点方向；[L2] 几何质量及最坏情况口径 | 保证接收集合、候选离散化、参数与实际观测实验 |
| Q3 | [L1] 补测效率的设计动机 | 频道搜索、无遗漏退出与多目标总耗时 |
| Q4 | [L2] 网格分析的相关背景 | 定向可见性、发现与定位的区别、部署验证 |

Q2 的 `shape` 名称表示本批几何候选变体。现有 Q3/Q4 控制器没有因此改变；不将新试验的成绩归入既有3000场景结果，也不把文献中的近似比或竞争比赋予本仓库方法。
