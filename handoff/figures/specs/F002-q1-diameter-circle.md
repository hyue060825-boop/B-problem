---
spec_version: "1.0"
figure_id: "F002"
working_title: "Q1：直径圆与最小包围圆"
status: "RENDERED"
outputs:
  source: "../../../scripts/build_handoff_assets.py"
  vector: "../F002-q1-diameter-circle.pdf"
  preview: "../F002-q1-diameter-circle.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Comparison
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
合法测向交会区域的直径圆不一定覆盖整个区域。
## 2.2 Intended Reader Takeaway
等边三角形可行域是理解本图的入口，结论以绑定来源为限。
## 2.3 Role in the Paper
为 Q1–Q4 的方法或实验说明提供可独立引用的中文图件。

# 3. Required Content
## 3.1 Must Show
- 等边三角形可行域
- 直径圆与最小包围圆
- 直径 40.00 m、最小包围圆半径 23.094 m
## 3.2 Exact Scientific Content
直径 40.00 m；最小包围圆半径 23.094 m；同一组三角形顶点用于两个圆的比较。
## 3.3 Source Binding
- [results/validation/import-c457828/artifacts/q1/triangle/result.json](../../../results/validation/import-c457828/artifacts/q1/triangle/result.json)
- [results/validation/import-c457828/artifacts/q1/triangle/input.json](../../../results/validation/import-c457828/artifacts/q1/triangle/input.json)
## 3.4 Optional / Removable Content
可移除图内标题；保留轴、图例、单位和关键几何对象。
## 3.5 Assumptions / Open Questions
人工算例不是官方测试；两圆不是两种测量误差分布。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
两个圆与同一个可行域作几何覆盖比较。

# 5. Figure Design
## 5.1 Reading Order
从左到右；图例与相邻对象或坐标轴共同阅读。
## 5.2 Composition
数据面板使用明确坐标或等比例几何坐标；多面板分别解释同一问题的不同层面。
## 5.3 Primary Visual Anchor
等边三角形可行域。
## 5.4 Information Hierarchy
### Primary
- 合法测向交会区域的直径圆不一定覆盖整个区域。
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
人工算例不是官方测试；两圆不是两种测量误差分布。

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
