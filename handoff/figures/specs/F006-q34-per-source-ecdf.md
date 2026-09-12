---
spec_version: "1.0"
figure_id: "F006"
working_title: "Q3/Q4：每源耗时的经验分布"
status: "RENDERED"
outputs:
  source: "../../../scripts/build_handoff_assets.py"
  vector: "../F006-q34-per-source-ecdf.pdf"
  preview: "../F006-q34-per-source-ecdf.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Results / Diagnostics
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
在各 3000 个配对研究场景中比较当前候选与各自对照的每局 T/C 分布。
## 2.2 Intended Reader Takeaway
Q3 与 Q4 各 3000 个配对场景是理解本图的入口，结论以绑定来源为限。
## 2.3 Role in the Paper
为 Q1–Q4 的方法或实验说明提供可独立引用的中文图件。

# 3. Required Content
## 3.1 Must Show
- Q3 与 Q4 各 3000 个配对场景
- 四组均完成
- 经验累积分布
- 每局 T/C，单位 s/源
## 3.2 Exact Scientific Content
每组 3000 局全部完成；每局先计算 T/C，均值降幅 Q3 约 0.40%、Q4 约 2.75%。
## 3.3 Source Binding
- [results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q3_baseline_samples.json](../../../results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q3_baseline_samples.json)
- [results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q3_candidate_samples.json](../../../results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q3_candidate_samples.json)
- [results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q4_baseline_samples.json](../../../results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q4_baseline_samples.json)
- [results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q4_best_samples.json](../../../results/training/import-3ddb2d9/runs/q34_3000_test_20260912/q4_best_samples.json)
## 3.4 Optional / Removable Content
可移除图内标题；保留轴、图例、单位和关键几何对象。
## 3.5 Assumptions / Open Questions
不将自建分布写成官方成绩；不把总时间降幅标作 T/C 降幅。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
同一问题内比较模型，两个问题使用不同耗时横轴；曲线越靠左表示耗时越小。

# 5. Figure Design
## 5.1 Reading Order
从左到右；图例与相邻对象或坐标轴共同阅读。
## 5.2 Composition
数据面板使用明确坐标或等比例几何坐标；多面板分别解释同一问题的不同层面。
## 5.3 Primary Visual Anchor
Q3 与 Q4 各 3000 个配对场景。
## 5.4 Information Hierarchy
### Primary
- 在各 3000 个配对研究场景中比较当前候选与各自对照的每局 T/C 分布。
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
不将自建分布写成官方成绩；不把总时间降幅标作 T/C 降幅。

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
