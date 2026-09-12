---
spec_version: "1.0"
figure_id: "F011"
working_title: "Q2精度与总耗时的配对评估"
status: "RENDERED"
outputs:
  source: "../../../scripts/build_q2_literature_assets.py"
  vector: "../F011-q2-paired-evaluation.pdf"
  preview: "../F011-q2-paired-evaluation.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Results / Diagnostics
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
几何候选减少平均总耗时，但第二次观测精度存在代价。
## 2.2 Intended Reader Takeaway
依据实际观测比较几何精度与执行成本。
## 2.3 Role in the Paper
Q2补充实验；LIT-Q2-01。

# 3. Required Content
## 3.1 Must Show
- 四方法后验半径ECDF、120对耗时和等值线。
## 3.2 Exact Scientific Content
- 数据以对应批次记录为准；m为米，s为秒；当前Q2与几何候选分别标识。
## 3.3 Source Binding
- [原始批次](../../../results/validation/LIT-Q2-01/README.md)
- [整理表格](../../tables/LIT-Q2-01/README.md)
## 3.4 Optional / Removable Content
标题可并入论文图注。
## 3.5 Assumptions / Open Questions
本地单源研究；固定空间误差场，不代表官方成绩。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
每个散点连接相同场景的两种策略结果，后续规则一致。

# 5. Figure Design
## 5.1 Reading Order
左到右。
## 5.2 Composition
横向双面板，共享字体与语义颜色；轴和图例就近标注。
## 5.3 Primary Visual Anchor
各方法实际数据之间的比较。
## 5.4 Information Hierarchy
### Primary
- 几何候选减少平均总耗时，但第二次观测精度存在代价。
### Secondary
- 单位、案例数和方法图例。
### Supporting
- 来源和适用边界见图注。
## 5.5 Simplification & Redundancy
不增加装饰图标或未经观测的数据点。

# 6. Visual & Content Constraints
## 6.1 Visual Semantics
当前Q2蓝色，几何候选橙色；用文字及线型同时区分。
## 6.2 Required Figure Labels
横纵轴带单位，配对差说明新减旧。
## 6.3 Must Not Imply / Avoid
不将总耗时改善写成每局改善或定位精度提高；不混同官方结果。

# 7. References & Rendering Requirements
## 7.1 References
来源为绑定实验记录；文献只作方法背景，见[文献说明](../../../docs/references/README.md)。
## 7.2 Cross-Figure Consistency
与F001—F009保持中文和单位口径一致。
## 7.3 Rendering Requirements
**Intended Use:** 中文论文Q2补充实验。
**Target Size / Aspect Ratio:** 通栏约18 cm；双面板。
**Preferred Backend:** Python / Matplotlib
**Required Outputs:** PDF、SVG、PNG、生成代码及SHA-256。
