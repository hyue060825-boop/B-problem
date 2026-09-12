# Q2 选点与实际补测实验

**文献启发补充 · LIT-Q2-01｜已实现并完成本地实验**

原选点器保留在 [q2.py](../../src/solution/planning/q2.py)，本次变体及实验入口为 [experiment_q2_literature.py](../../scripts/experiment_q2_literature.py)，配置为 [lit_q2_01.json](lit_q2_01.json)。方法、结果和写作边界见[独立交付](../../handoff/shared/文献启发与Q2改进说明.md)。

## 设计与冻结口径

| 阶段 | 场景种子 | 数量 | 用途 |
| --- | --- | ---: | --- |
| pilot | 412000—412007 | 8×4方法 | 检查一致性与运行成本，未据此修改默认评分参数 |
| evaluation | 413000—413119 | 120×4方法 | 冻结配置的独立配对评估 |
| sensitivity | 414000—414011 | 12×9配置 | 权重与离散化检查，未回选评估参数 |

主评估采用5种几何×4种误差×3种接收半径×2个实例的固定分层设计。每类几何24局、每类误差30局、每个半径40局。源位于半径1800 m目标圆内；首点与源间距大于5 m且不超过接收半径，首次direction由模拟器产生。五类为center、edge、rotated、wrap、short_range；后一类距离8—80 m。

误差0、+1°、-1°为常值场，smooth为 `FixedField(seed+917)`，同地点重复调用得到同一误差。示向度按本地half-up量化约定产生，几何实现使用1.01°保护角；不声称复制官方舍入或误差分布。单源使用test_fixture，不冒充Q3/Q4的10—16源实验。

对比沿示向线750 m、沿线750 m再左侧450 m、原choose_second默认搜索、本批几何候选。四者共用evaluate_point评分，预测后验来自公开可行域中的有限情景。原搜索约129点，新变体通常31点，候选预算不同，计算耗时另报。源坐标、半径和误差场均不传给select。

## 实际执行与统计

各方法在全新内核状态下从首检测点开始，执行两次检测，更新角域、near圆或全向no_signal排除区。评价端核对真实源包含关系，记录实际后验直径、面积和包围圆半径。

后续共用规则：证书安全则转清除，否则至多3次侧翼补测。以圆心沿最后示向度垂向偏移clip(0.45r,30,350) m，选择离当前位置较近的一侧。再由clear_cover生成一次清除点集合，依次访问最近剩余点，成功即停；最多2000次清除尝试。该规则用于隔离第二测点的影响，不等同于完整Q3/Q4控制器。

total_virtual_s含首测5秒，从已位于首检测点开始，不含Q3搜索到首点的路径。虚拟时间由ReferenceKernel.transition逐步计费，CPU选点时间另存selection_s。记录保留无法选点、无信号和清除预算失败标记，不按成功与否筛掉场景；若发现后验丢失真值等一致性错误，则停止整批处理，不静默忽略。

敏感性采用径向0.15—1等距3/5/9档及半径权重0/0.5/1，剩余时间权重固定1。主实验径向为0.15/0.3/0.5/0.75/1，5档并非同一网格；敏感性12局半径均为1000 m，仅含0/+1°/-1°场，结论据此限定。全配置保留，未按结果删选。

## 复现

安装仓库依赖后，从仓库根目录运行；原始输出目录必须不存在。

```bash
python scripts/experiment_q2_literature.py --phase pilot --output results/validation/q2-lit-new/pilot --workers 2
python scripts/experiment_q2_literature.py --phase evaluation --output results/validation/q2-lit-new/evaluation --workers 2
python scripts/experiment_q2_literature.py --phase sensitivity --output results/validation/q2-lit-new/sensitivity
python -m pytest tests/solution/test_q2.py tests/solution/test_q2_literature.py -q
```

有效单例为 [q2_example_lit.json](../../tests/fixtures/solution/q2_example_lit.json)，绑定源(900,30)和零误差，首次示向度1.91°：

```bash
python -m solution.cli solve-q2 --input tests/fixtures/solution/q2_example_lit.json --output results/validation/q2-lit-example-new
python scripts/build_q2_literature_assets.py
```

最后一条仅重绘已归档的LIT-Q2-01图表，不重跑策略。旧 [q2_example.json](../../tests/fixtures/solution/q2_example.json) 仍是人工评分算例；旧q2_source.json不作为本批依据。每批保存配置、场景、源码SHA-256、逐动作轨迹及输出哈希；墙钟统计随硬件与并发负载变化。
