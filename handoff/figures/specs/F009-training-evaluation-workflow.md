---
spec_version: "1.0"
figure_id: "F009"
working_title: "研究训练、验证与交付流程"
status: "RENDERED"
outputs:
  source: "../F009-training-evaluation-workflow.svg"
  vector: "../F009-training-evaluation-workflow.pdf"
  preview: "../F009-training-evaluation-workflow.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Workflow / Pipeline
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
模型训练、固定验证集选模和训练后的配对评估各自承担不同证据角色。
## 2.2 Intended Reader Takeaway
自建研究场景是理解本图的入口，结论以绑定来源为限。
## 2.3 Role in the Paper
为 Q1–Q4 的方法或实验说明提供可独立引用的中文图件。

# 3. Required Content
## 3.1 Must Show
- 自建研究场景
- Q3 搜索标签与 SFT/DAgger/PPO
- Q4 修复后 BC/DAgger/PPO 与预算训练
- 验证选模与冻结权重
- 3000 个配对场景评估
- 官方演练待执行
## 3.2 Exact Scientific Content
Q3 为 SFT/DAgger/PPO，Q4 为 BC/DAgger/PPO 及预算训练；每题最新配对场景 3000 个。
## 3.3 Source Binding
- [results/training/import-3ddb2d9/runs/q3_joint_20260912/config.json](../../../results/training/import-3ddb2d9/runs/q3_joint_20260912/config.json)
- [results/training/import-3ddb2d9/runs/q3_joint_20260912/frozen_selection.json](../../../results/training/import-3ddb2d9/runs/q3_joint_20260912/frozen_selection.json)
- [results/training/import-3ddb2d9/runs/q4_budget_20260912/train/status.json](../../../results/training/import-3ddb2d9/runs/q4_budget_20260912/train/status.json)
- [results/training/import-3ddb2d9/runs/q34_3000_test_20260912/manifest.json](../../../results/training/import-3ddb2d9/runs/q34_3000_test_20260912/manifest.json)
## 3.4 Optional / Removable Content
可移除图内标题；保留轴、图例、单位和关键几何对象。
## 3.5 Assumptions / Open Questions
不把历史八路独立训练画成同步 DDP；不把官方测试画成已经完成。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
Q3 与 Q4 是并行研究路线，汇入验证和冻结；官方环节使用虚线表示待形成仓库证据。

# 5. Figure Design
## 5.1 Reading Order
从左到右；图例与相邻对象或坐标轴共同阅读。
## 5.2 Composition
主流程沿节点连接展开，循环和待完成环节单独标明。
## 5.3 Primary Visual Anchor
自建研究场景。
## 5.4 Information Hierarchy
### Primary
- 模型训练、固定验证集选模和训练后的配对评估各自承担不同证据角色。
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
不把历史八路独立训练画成同步 DDP；不把官方测试画成已经完成。

# 7. References & Rendering Requirements
## 7.1 References
使用绑定的仓库数据和实现，不复制旧图的排版或使用论文目录作为数据源。
## 7.2 Cross-Figure Consistency
中文说明、米与秒单位、统一字体和颜色；统计差值均为新减旧。
## 7.3 Rendering Requirements
**Intended Use:** 中文论文方法与实验图，供论文手选用。
**Target Size / Aspect Ratio:** 通栏约 17–18 cm；单幅几何图可按可读性缩放。
**Preferred Backend:** SVG / rsvg-convert
**Required Outputs:** SVG、PDF、PNG，以及重绘代码和输入哈希。
