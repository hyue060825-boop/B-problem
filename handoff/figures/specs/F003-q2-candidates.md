---
spec_version: "1.0"
figure_id: "F003"
working_title: "Q2：保证接收区域与候选点评分"
status: "RENDERED"
outputs:
  source: "../../../scripts/build_handoff_assets.py"
  vector: "../F003-q2-candidates.pdf"
  preview: "../F003-q2-candidates.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Results / Diagnostics
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
先保证再次接收，再在有限候选点中权衡移动和估计定位代价。
## 2.2 Intended Reader Takeaway
首次观测可行域是理解本图的入口，结论以绑定来源为限。
## 2.3 Role in the Paper
为 Q1–Q4 的方法或实验说明提供可独立引用的中文图件。

# 3. Required Content
## 3.1 Must Show
- 首次观测可行域
- 保证接收内近似
- 实际候选点及 J 值
- 最佳已评估点与 J≤最小值+10 s 的候选
## 3.2 Exact Scientific Content
坐标与 J 从 result.json 读取；最佳点约 (735.90,262.92) m；高质量候选阈值为最小 J 加 10 s。
## 3.3 Source Binding
- [results/validation/import-c457828/artifacts/q2/example/input.json](../../../results/validation/import-c457828/artifacts/q2/example/input.json)
- [results/validation/import-c457828/artifacts/q2/example/result.json](../../../results/validation/import-c457828/artifacts/q2/example/result.json)
- [src/solution/planning/q2.py](../../../src/solution/planning/q2.py)
## 3.4 Optional / Removable Content
可移除图内标题；保留轴、图例、单位和关键几何对象。
## 3.5 Assumptions / Open Questions
不画虚构的第二次观测后验；不插值成未经评估的连续热力面。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
候选位于保证接收区域中，颜色只编码有限情景的综合评分。

# 5. Figure Design
## 5.1 Reading Order
从左到右；图例与相邻对象或坐标轴共同阅读。
## 5.2 Composition
单面板横向展示接收区域：横轴为北向 y，纵轴为东向 x；交换全部几何对象与散点的显示坐标，保持等比例，原始物理坐标和评分不变。使用 cividis_r 色标及底部图例。
## 5.3 Primary Visual Anchor
首次观测可行域。
## 5.4 Information Hierarchy
### Primary
- 先保证再次接收，再在有限候选点中权衡移动和估计定位代价。
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
不画虚构的第二次观测后验；不插值成未经评估的连续热力面。

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
