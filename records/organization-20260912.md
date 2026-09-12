# 仓库资产整理：2026-09-12

基准为 `main@4e2cf9f`，算法来源至 hy `3ddb2d9`。本次整理面向题意、建模、实验和写作交付，未改变算法或历史实验结论。

## 目录与材料

- 四份 `docs/notes/接收记录-*.md` 迁至 `records/acceptance/`，更新相对链接；版本入口为 `records/versions.md`。历史验证原件保持在 `results/validation/`，通过版本记录访问。
- `handoff/q1/`–`q4/` 各自整理题意、建模过程、当前实现、实验与结果、复现入口和图表；`shared/` 统一记号、训练过程、统计口径及历史批次边界。
- `handoff/figures/` 提供 9 张中文图，每张均有 PDF、SVG、PNG 和七节 FigureSpec；`handoff/tables/` 提供 8 份整理 CSV、Q4 网格及来源记录。
- `records/inventory/` 清点 15 类主要数据资产、58 份权重，以及全部工作文件与图件；清单排除 `paper/` 和清单自身。
- 更新根 README、模型与模拟器说明，补 Q1/Q2 实验入口；完整候选推导与当前实际方法分别指引。

绘图采用用户提供的 `projects/skills/group-resource/materials/skills/figure-design-skills/scientific-figure-spec`。流程图以原生 SVG 绘制，数值与几何图以 Python/Matplotlib 生成；重绘依赖和输入哈希随交付保存。图件状态为 `RENDERED`，没有代替论文手作最终采用决定。

## 验证

- 重新汇总最新 12000 条评估记录，检查场景配对、C=N、逐局指标与四份权重哈希；原记录不变，未重跑训练或完整评估。
- 9 份 FigureSpec 严格结构检查通过。PNG 和实际 PDF 栅格化导出均已查看，修正网格裁切、标注和缺字符号；9 份 SVG 可解析，PDF 可正常导出。
- 表格单独复算得到相同的 8 份 CSV，不改变既有图件与图件 provenance；图与表分别记录来源。
- `paper/` 的 32 个原文件、题面 5 个文件、`src/` 49 个文件和 `tests/` 27 个文件逐字节一致。`results/` 只调整 9 份导航 README；其余 3598 个原文件保持原路径和内容，包括所有权重、原始数据和图件。
- 新生成的 CSV 统一使用 LF 换行，SVG 清除行末空格；9 张 PNG 内容不变，暂存内容与工作区哈希一致。
- 活动文档链接、来源与导出哈希、脚本语法和 Git 暂存差异检查的结果见[核验摘要](inventory/organization-check.json)。本次不涉及算法变更，未重复执行已有全量回归。

Q2 的实际第二观测、参数灵敏度和官方运行数据仍未齐备，已在各题说明中列出；本批只使用已有证据生成相应图表。
