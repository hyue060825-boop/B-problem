---
spec_version: "1.0"
figure_id: "F001"
working_title: "Q3/Q4：几何约束下的在线控制"
status: "RENDERED"
outputs:
  source: "../F001-controller-workflow.svg"
  vector: "../F001-controller-workflow.pdf"
  preview: "../F001-controller-workflow.png"
---

# Scientific Figure Specification

# 1. Figure Identity
**Primary Archetype:** Workflow / Pipeline
**Secondary Archetype(s):** None

# 2. Scientific Purpose
## 2.1 Core Message
几何与频道状态生成合法动作，调度器选择动作，公开响应反馈更新状态。
## 2.2 Intended Reader Takeaway
公开响应与频道状态是理解本图的入口，结论以绑定来源为限。
## 2.3 Role in the Paper
为 Q1–Q4 的方法或实验说明提供可独立引用的中文图件。

# 3. Required Content
## 3.1 Must Show
- 公开响应与频道状态
- 可行域及几何证书
- 五类宏动作
- 规则或学习调度
- 串行 measure/clear/exit 与反馈
## 3.2 Exact Scientific Content
五类动作对应 COVER / LOCALIZE / CLEAR / PROBE_CLEAR / EXIT；串行接口为 measure / clear / exit。
## 3.3 Source Binding
- [src/solution/control/controller.py](../../../src/solution/control/controller.py)
- [src/solution/rl/environment.py](../../../src/solution/rl/environment.py)
- [scripts/run_policy.py](../../../scripts/run_policy.py)
## 3.4 Optional / Removable Content
可移除图内标题；保留轴、图例、单位和关键几何对象。
## 3.5 Assumptions / Open Questions
不画 Q2 choose_second 作为现有控制器调用；不让隐藏真值进入策略。

# 4. Scientific Structure & Relationships
## 4.1 Relationships
箭头表示数据流或执行顺序；EXIT 仅在全部频道已清除或已认证不存在时出现。

# 5. Figure Design
## 5.1 Reading Order
从左到右；图例与相邻对象或坐标轴共同阅读。
## 5.2 Composition
主流程沿节点连接展开，循环和待完成环节单独标明。
## 5.3 Primary Visual Anchor
公开响应与频道状态。
## 5.4 Information Hierarchy
### Primary
- 几何与频道状态生成合法动作，调度器选择动作，公开响应反馈更新状态。
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
不画 Q2 choose_second 作为现有控制器调用；不让隐藏真值进入策略。

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
