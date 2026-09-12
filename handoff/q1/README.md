# Q1：交会定位区域的直径与覆盖圆

题目要求给出交会定位多边形的直径算法，并判断以区域直径为直径的圆能否覆盖整个区域。可直接采用的结论是：**直径圆不总能覆盖定位区域，必须另作覆盖判定。**

## 建模过程

检测点为 `s_i`，示向度为 `theta_i`，误差界为 `epsilon=1°`。令

$$
u_i^-=(\cos(\theta_i-\epsilon),\sin(\theta_i-\epsilon)),\quad
u_i^+=(\cos(\theta_i+\epsilon),\sin(\theta_i+\epsilon)).
$$

以二维叉积记方向约束：`[u_i^-,x-s_i]≥0`、`[u_i^+,x-s_i]≤0`。两半平面形成前向角域，多次观测取交得到 `P`。Q1 的角域交与在线任务另加的距离、目标圆约束应分开说明。

对有界凸多边形，最远点对位于顶点，采用旋转卡壳计算直径 `D=max ||v_i-v_j||`。若最远点对为 A、B，任何半径为 D/2 且覆盖二者的圆，其圆心只能是中点 m；因此检查所有顶点到 m 的距离是否不超过 D/2，即可回答直径圆覆盖问题。

三次合法测向角域可交成边长 40 m 的等边三角形。其直径为 40 m，最小包围圆半径为 `40/√3≈23.094 m`，大于 20 m，构成反例。这同时说明在线清除不能仅依据直径不超过 40 m，而应核验整个可信可行域能被清除圆覆盖。

## 编程方案

实现集中在 [geometry/core.py](../../src/solution/geometry/core.py)：半平面交主线使用排序与双端队列，配合线性规划识别可行性和无界情况；退化情况回退处理。结果区分空集、点、线段、多边形、无界集合。直径采用旋转卡壳，最小包围圆采用随机增量构造。

排序半平面交主算法为 O(n log n)，旋转卡壳为 O(h)；完整实现还包括 LP 诊断及退化回退，不能把所有输入下的程序成本一概写为前者。测试保留 O(h²) 枚举直径和独立凸优化核对最小包围圆。

## 算例、结果与复现

| 人工算例 | 区域 | 直径 / m | 直径圆覆盖 | 最小包围圆半径 / m |
| --- | --- | ---: | --- | ---: |
| 两次对称交会 | 四边形 | 34.9208 | 是 | 17.4604 |
| 三扇形反例 | 等边三角形 | 40.0000 | 否 | 23.0940 |

输入和输出见[原始算例](../../results/validation/import-c457828/artifacts/q1/)，原推导见[问题一报告](../../results/validation/import-c457828/reports/问题1_结果报告.MD)。整理表格为 [q1_examples.csv](../tables/q1_examples.csv)，中文图为 [F002：直径圆反例](../figures/F002-q1-diameter-circle.pdf)。

从仓库根目录复现，输出另取新目录：

```bash
python -m solution.cli solve-q1 --input tests/fixtures/solution/q1_triangle.json --output results/validation/q1-triangle-new
python -m solution.cli solve-q1 --input tests/fixtures/solution/q1_crossing.json --output results/validation/q1-crossing-new
python -m pytest tests/solution/test_geometry.py -q
```

这些是解释数学结论的人工输入，不是官方场景成绩。当前算例支持几何构造与程序对应；有限边界测试不等于所有浮点退化输入的证明。进一步推导可查[总体方案](../../docs/model/总体方案.md)。
