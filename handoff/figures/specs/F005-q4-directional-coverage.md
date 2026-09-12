---
spec_version: "1.0"
figure_id: "F005"
working_title: "Q4：三角网格与定向发现依据"
status: "RENDERED"
outputs:
  source: "../../../scripts/build_handoff_assets.py"
  vector: "../F005-q4-directional-coverage.pdf"
  preview: "../F005-q4-directional-coverage.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Mechanism
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
覆盖目标圆的三角网格中，每个普通内部点在任意闭发射半平面内至少有一个三角形顶点。
## 2.2 Intended Reader Takeaway
42 个三角形、31 个站点是理解本图的入口，结论以绑定来源为限。
## 2.3 Role in the Paper
为 Q1–Q4 的方法或实验说明提供可独立引用的中文图件。

# 3. Required Content
## 3.1 Must Show
- 42 个三角形、31 个站点
- 网格边长 995 m
- 目标圆半径 1800 m
- 半平面与三角形内部点的凸组合示意
## 3.2 Exact Scientific Content
网格边长 995 m；42 个三角形、31 个站点；半平面边界包含在可见区域中。
## 3.3 Source Binding
- [src/solution/coverage/certificates.py](../../../src/solution/coverage/certificates.py)
- [handoff/tables/q4_grid.json](../../../handoff/tables/q4_grid.json)
## 3.4 Optional / Removable Content
可移除图内标题；保留轴、图例、单位和关键几何对象。
## 3.5 Assumptions / Open Questions
右侧为数学示意，不是已运行的干扰源场景；不能把一次无信号当圆盘排除。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
左侧展示完整网格，右侧解释非重合位置的局部发现依据；重合位置由六邻点补证。

# 5. Figure Design
## 5.1 Reading Order
从左到右；图例与相邻对象或坐标轴共同阅读。
## 5.2 Composition
数据面板使用明确坐标或等比例几何坐标；多面板分别解释同一问题的不同层面。
## 5.3 Primary Visual Anchor
42 个三角形、31 个站点。
## 5.4 Information Hierarchy
### Primary
- 覆盖目标圆的三角网格中，每个普通内部点在任意闭发射半平面内至少有一个三角形顶点。
### Secondary
- 单位、图例和比较关系。
### Supporting
- 图注中的数据来源和适用范围。
## 5.5 Simplification & Redundancy
不使用装饰图标、虚构数据点或额外插值；完整数值与出处由表格及清单承载。

# 6. Visual & Content Constraints
## 6.1 Visual Semantics
蓝色表示对照/公开输入，橙色表示候选/动作选择，青色表示几何范围；颜色同时由线型、标签或图例解释。
## 6.2 Required Figure Labels
采用中文对象名称；几何坐标标注 m，耗时标注 s 或 s/源，统计差值说明新减旧；相关数值按 3.2 保留。
## 6.3 Must Not Imply / Avoid
右侧为数学示意，不是已运行的干扰源场景；不能把一次无信号当圆盘排除。

# 7. References & Rendering Requirements
## 7.1 References
使用绑定的仓库数据和实现，不复制旧图的排版或使用论文目录作为数据源。
## 7.2 Cross-Figure Consistency
中文说明、米与秒单位、统一字体和颜色；统计差值均为新减旧。
## 7.3 Rendering Requirements
**Intended Use:** 中文论文方法与实验图，供论文手选用。
**Target Size / Aspect Ratio:** 通栏约 17–18 cm；单幅几何图可按可读性缩放。
**Preferred Backend:** Python / Matplotlib
**Required Outputs:** SVG、PDF、PNG，以及重绘代码和输入哈希。
