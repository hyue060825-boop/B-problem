---
name: academic-plotting
description: 为数学建模竞赛与学术论文绘制或修改实验图表、流程图和示意图，兼顾数据可复现、结构准确与图形可编辑性。根据图形需求和用户选择使用合适工具；普通图片、网页界面和整篇论文排版不属于此技能范围。
license: MIT
metadata:
  version: 1.0.0
  author: Orchestra Research
  tags: '["Academic Writing","Visualization","Matplotlib","Seaborn","Plotting","Figures","Diagrams","NeurIPS","ICML","ICLR","LaTeX"]'
---

# Academic Plotting — 竞赛绘图

## 本仓库约定

- 面向中文数模论文，图题、图例、坐标说明和交付说明默认使用中文；符号、单位与模型文档保持一致，检查中文字体能正确显示。
- 数值图表使用实际数据和可复现绘图代码；流程图与示意图准确表达模型关系。沿用用户选择的绘图工具。
- 图表默认输出到仓库根目录下的 `results/figures/`，通过 `handoff/` 提供图意、结论、数据来源和复现入口；具体任务指定其他路径时按任务执行。
- `paper/` 由论文手组织维护。本技能可协助论文手处理其指定的图表任务；建模与实验侧的日常交付使用 `handoff/`。
- 下文及参考资料保留原技能的技术指导。ML 会议的版式和示例只作参考，实际输出以本队中文论文及用户要求为准。

本副本基于本机 `academic-plotting` 技能适配，保留原作者、许可元数据及参考资料。

Create the scientific figure requested by the user. Separate factual content,
rendering requirements, and aesthetic choices. Planning-only requests need a
specification or recommendation, not an image-generation call.

## Select the Rendering Workflow

| Figure requirement | Preferred capability |
|---|---|
| Quantitative or empirical comparison | Reproducible data-driven plotting code |
| Exact architecture, workflow, or text-heavy diagram | Editable vector or deterministic, specification-driven renderer |
| Conceptual or illustrative visual | Suitable image-generation backend available in the environment |
| Explicitly specified backend | Use it when permitted and able to meet the required output contract |

Examples include matplotlib for data, SVG/PDF, TikZ, Draw.io or other editable
renderers for structure, and available image-generation tools for illustrations.
No provider is a universal prerequisite.

Use the current environment's execution rules for the selected backend. Reuse
existing authorization; do not silently change a requested backend or relax
editability requirements. Optional dependencies do not block other workflows.

---

## Capabilities and Fallbacks

| Route | Required capability for that route | Optional tools / fallback |
|---|---|---|
| Quantitative figure | Accurate source data and reproducible rendering | matplotlib/numpy or an available equivalent; seaborn/scipy only for the selected recipe |
| Exact diagram | Renderer meeting structure and editability requirements | SVG, TikZ, Draw.io, Mermaid or another suitable renderer |
| Generative illustration | An available, authorized image backend | Provider-specific SDKs only for the selected backend |
| Gemini SDK | Authorized Gemini route and its SDK/configured client | See the optional Gemini reference; other routes do not depend on it |

Do not install packages, activate services, change accounts, or inspect/output
credentials to satisfy this Skill. Reuse authorized capabilities. If a required
capability is missing, pause only that dependent step and continue supported
work. Do not silently replace a user-required backend or editable output.
Optional specialist Skills and LaTeX font rendering do not block figure planning
or other available rendering paths.

## Step 0: Context Analysis & Extraction

Capture a lightweight FigureSpec from the supplied context:

- purpose and supported scientific takeaway;
- data source and transformations, or required entities and relationships;
- exact labels, units, and directionality;
- final display size, output format, and editability/reproducibility needs;
- user-specified backend and style, if any;
- factual and visual acceptance criteria.

Reuse a specification already supplied by the user. Do not ask for confirmation
of routine layout choices. Ask only about missing facts or decisions that change
scientific content, required output, or execution authority; continue independent
work. Never invent measured values, missing modules, or relationships.

The following inputs can supply the specification:

| Input Type | Example | What to Extract |
|-----------|---------|-----------------|
| Full paper / section draft | "Here's our method section..." | System components, their relationships, data flow |
| Description paragraph | "Our system has three layers that..." | Key entities, hierarchy, connections |
| Raw results / data table | "MMLU: 85.2, HumanEval: 72.1..." | Metrics, methods, comparison structure |
| CSV / JSON data | Experiment log files | Variables, trends, grouping dimensions |
| Vague request | "Make a figure for the overview" | Read surrounding paper context to infer content |

### Extraction Workflow

**For diagrams** (research context → architecture figure):

1. **Read the provided context** — paper section, abstract, or description paragraph
2. **Identify visual entities** — What are the main components/modules/stages?
   - Look for: nouns that represent system parts, named modules, layers, stages
   - Count them: if >8 top-level entities, consider grouping into sections
3. **Identify relationships** — How do components connect?
   - Look for: verbs describing data flow ("sends to", "queries", "feeds into")
   - Classify: data flow (solid arrow), control flow (gray), error path (dashed red)
4. **Determine layout pattern**:
   - Sequential pipeline → left-to-right flow
   - Layered architecture → horizontal bands stacked vertically
   - Hub-and-spoke → central node with radiating connections
   - Hierarchical → top-down tree
5. **Assign colors** — One accent color per logical group/layer
6. **Write every label exactly** — Extract exact terminology from the paper text

**For data charts** (results → figure):

1. **Read the provided data** — table, paragraph with numbers, CSV, or JSON
2. **Identify dimensions**:
   - What is being compared? (methods, models, configurations) → categorical axis
   - What is the metric? (accuracy, loss, latency, F1) → value axis
   - Is there a time/step dimension? → line plot
   - Are there multiple metrics? → multi-panel or grouped bars
3. **Choose chart type** automatically using this priority:
   - Has a step/time axis → **line plot**
   - Comparing N methods on M benchmarks → **grouped bar chart**
   - Single ranking → **horizontal bar** (leaderboard)
   - Correlation between two continuous variables → **scatter plot**
   - Square matrix of values → **heatmap**
   - Proportional breakdown → **stacked bar** (avoid pie charts)
4. **Determine figure sizing** — Single column vs full width based on data density
5. **Apply a justified highlight** — Highlight a method only when identified by the user/context; otherwise keep methods comparably readable

### Auto-Detection Examples

**Context → Diagram**: "Our system has a Planner, Executor, and Verifier. Planner sends plans to Executor, Executor returns results to Verifier, Verifier feeds back to Planner on failure."
→ 3 entities, cycle layout, dashed feedback arrow → **Workflow 1 (precise diagram)**

**Data → Chart**: "GPT-4: MMLU 86.4, HumanEval 67.0. Ours: 88.1, 71.2. Llama-3: 79.3, 62.1."
→ 3 methods × 2 benchmarks → **Workflow 2 (grouped bar)**, highlight "Ours" in coral

---

## Workflow 1: Scientific Diagrams and Conceptual Illustrations

1. Extract or reuse the FigureSpec.
2. For exact structure, select an editable or specification-driven renderer.
   For a conceptual illustration, select a suitable available image backend.
3. Preserve required components, relationships, labels, and scientific meaning.
   Choose routine layout and styling within the user's constraints.
4. Produce an initial candidate and apply [QA and Iteration](#qa-and-iteration).
5. Deliver the passing artifact and the appropriate editable source or provenance.

Read [references/diagram-generation.md](references/diagram-generation.md) for
prompt and layout examples. Read [references/gemini-backend.md](references/gemini-backend.md)
only when Gemini is explicitly selected or contextually required.

A generative renderer must not reconstruct measured data. If a selected backend
cannot satisfy required structural precision or editability, continue specification
work and resolve that output constraint before finalizing.

### Style Recipes

Read the optional [visual styles and palettes](references/diagram-generation.md#visual-styles) when choosing a diagram style. They do not change the FigureSpec or renderer policy.

---

## Workflow 2: Data-Driven Charts (matplotlib/seaborn)

For any figure with numerical data, axes, or quantitative comparisons.

### Checklist

- [ ] **Extract from context**: Parse results/data, identify methods, metrics, and comparison structure
- [ ] **Auto-select chart type** based on data dimensions (see decision guide below)
- [ ] Prepare data (CSV, dict, or inline arrays)
- [ ] Apply publication styling (fonts, colors, sizes)
- [ ] Highlight a method only when identified by the user/context, while keeping baselines distinguishable
- [ ] Export the requested publication format under [Figure Output Policy](#figure-output-policy); add a raster preview when useful
- [ ] Check whether the output is vector, raster, or mixed
- [ ] Verify font compatibility for the selected manuscript/output when applicable
- [ ] Deliver reproducible plotting code using the project's naming conventions

### Chart Type Decision Guide

| Data Pattern | Best Chart | Notes |
|-------------|------------|-------|
| Trend over time/steps | Line plot | Training curves, scaling laws |
| Comparing categories | Grouped bar chart | Model comparisons, ablations |
| Distribution | Violin / box plot | Score distributions across methods |
| Correlation | Scatter plot | Embedding analysis, metric correlation |
| Grid of values | Heatmap | Attention maps, confusion matrices |
| Part of whole | Stacked bar (not pie) | Prefer stacked bar over pie in ML papers |
| Many methods, one metric | Horizontal bar | Leaderboard-style comparisons |

### Plotting Recipes

See [data-visualization.md](references/data-visualization.md) for setup, palettes,
supported SD bands, value labels, and the nine chart patterns. Select only the
relevant pattern and adapt it to the supplied data and required output.

---

## Figure Output Policy

Resolve output requirements in this order: explicit user requirement, target
venue requirement, scientific figure type, then editability/reproducibility.
If explicit requirements conflict or cannot be met, disclose the conflict and
resolve the dependent output decision; do not silently claim venue compliance.

Prefer vector output for quantitative plots, line art, structural diagrams, and
text-heavy or editable figures. Suitable raster is acceptable for photographs,
generated illustrations, image-like scientific outputs, and venue-approved
high-resolution images. Preserve editable source or plotting code when required.

A PDF or SVG may contain raster or mixed content. Embedding a raster image does
not make it vector. Verify the actual representation, final display dimensions,
and effective raster resolution; changing DPI metadata alone does not add detail.
Export the required deliverables; a PNG preview is optional unless requested.

## Publication Style Reference

Read [style-guide.md](references/style-guide.md) for venue dimension examples,
LaTeX integration, fonts, and accessibility checks. Verify the selected
venue/year/template and actual display size rather than treating historical
dimensions as universal requirements.

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Fonts look wrong in LaTeX | Match available fonts; use LaTeX rendering only when its toolchain is available and appropriate |
| Figure too large for column | Check venue width limits, use `figsize` in inches |
| Colors indistinguishable in print | Use colorblind-safe palette + different line styles/markers |
| Generated labels are wrong | Identify the exact label defect, correct it, then recheck scientific QA |
| Generated style misses the specification | Adjust the selected style without changing scientific content |
| Blurry figures in PDF | Inspect embedded content; export vector where suitable or adequate raster detail at final display size |
| Legend overlaps data | Use `bbox_to_anchor`, `loc="upper left"`, or external legend |
| Too many tick labels | Use `ax.xaxis.set_major_locator(MaxNLocator(5))` |

## When to Use vs Alternatives

| Need | This Skill | Alternative |
|------|-----------|-------------|
| Architecture diagrams | Editable/specification-driven rendering | Select TikZ, Draw.io, SVG or Mermaid as appropriate |
| Data charts | matplotlib/seaborn | Plotly (interactive), R/ggplot2 (statistics-heavy) |
| Full paper writing | Use with `ml-paper-writing` | — |
| Poster figures | Larger fonts, wider | `latex-posters` when available; whole-poster layout uses its own workflow |
| Presentation figures | Larger text, fewer details | PowerPoint/Keynote export |

---

## QA and Iteration

Check every final candidate against the FigureSpec:

- Scientific content: data, components, relationships, directionality, and claims.
- Completeness: required labels, units, legends, nodes, edges, and panels.
- Readability: text, contrast, routing, overlaps, and clipping at final display size.
- Output: usable file, required format, effective raster resolution, and required
  editable source or reproducible code.

Scientific correctness and required completeness are hard gates. Aesthetic
quality cannot compensate for an incorrect label, value, or connection.

If the candidate passes, finish. If it fails, identify the concrete defect,
make a targeted correction or retry, and recheck the affected requirements
plus any properties the correction could have disturbed.

Do not generate a fixed number of candidates. Additional variants require a user
request or a concrete comparison need. Stop retrying when a candidate passes,
a required permission/capability is unavailable, or no justified repair path remains
within the authorized scope and budget. In the latter cases, report the unresolved
defect and do not label the artifact final or publication-ready.

## Completion and Provenance

Deliver the requested passing artifact, its location, and relevant QA status.
Provide plotting code and data provenance for quantitative figures, editable
source for diagrams when required, and prompts/backend/nonsecret parameters
for generated illustrations.

Use existing project naming conventions (for example, figures/gen_fig_<name>.py
and figures/fig_<name>.<format>). Preview-only requests do not require project
integration. Keep candidates when needed for comparison or diagnosis, not to
satisfy a fixed count. Saving a generation prompt or script does not guarantee
deterministic reproduction of a generated image.
