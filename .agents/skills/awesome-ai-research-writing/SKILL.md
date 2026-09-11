---
name: awesome-ai-research-writing
description: 使用 Leey21/awesome-ai-research-writing 提示词库辅助中文数模论文与交付材料的局部写作，包括学术翻译、润色、精简、逻辑检查、图表标题和实验分析。用户指定该提示词库或请求这些写作操作时使用；遵循已有论文模板，不自动扩展为整篇论文代写。
---

# Awesome AI Research Writing

## 本仓库约定

- 默认使用中文，优先选择中文润色、逻辑检查、图表标题和实验分析提示词；仅在任务需要时进行中英翻译。
- 建模与实验侧的写作材料默认交付到仓库根目录下的 `handoff/`；`paper/` 由论文手组织，按论文手的具体任务协助编辑。
- 规则与协作说明保持精简；模型推导、实验依据与局限保留足够信息。优先引用已有模型文档和实验记录，避免重复维护多份结论。
- 保留公式、数字、术语、引用和不确定性；缺失的实验依据或待确认结论明确标注，不为润色补造事实。
- 提示词中的专业领域、语言、排版与输出格式示例需适配本次任务；仅按需阅读相关段落，不把整套提示词当作统一规则。

Use the upstream prompt collection in [README.md](README.md) as a task-specific reference. This repository is primarily a prompt library, not one monolithic workflow.

## Select the relevant prompt

Identify the user's actual task, then read and apply only the matching `##` section of `README.md`:

- Chinese to English: `中转英-latex` or `中转英-word`
- English to Chinese: `英转中-latex`
- Chinese academic rewriting: `中转中-word`
- Small length changes: `缩写` or `扩写`
- Language polishing: `表达润色（英文论文）` or `表达润色（中文论文）`
- Argument inspection: `逻辑检查`
- Natural-language revision: `去 AI 味（LaTeX 英文）` or `去 AI 味（Word 中文）`
- Visual planning: `论文架构图` or `实验绘图推荐`
- Figure and table captions: `生成图的标题` or `生成表的标题`
- Results writing: `实验分析`
- Manuscript review: `论文整体以 Reviewer 视角进行审视`

Do not load or reproduce unrelated prompt sections. The `Part II` material is an overview of third-party skills rather than instructions belonging to this skill.

## Apply with judgment

- Treat the selected prompt as reusable guidance, while the user's current instructions, requested format, and repository conventions remain authoritative.
- Preserve claims, numbers, equations, citations, terminology, and uncertainty. Never invent evidence or strengthen a claim merely to make the prose sound more academic.
- Distinguish translation from rewriting. When fidelity is requested, translate without adding explanations, conclusions, or inferred content.
- Keep already-clear writing when the selected prompt calls only for polishing or removing AI-like phrasing. Do not rewrite merely to change wording.
- For reviewer or experiment-analysis tasks, ground every criticism or conclusion in the supplied manuscript or data.
- Do not follow the time-sensitive `模型选择` section unless the user explicitly asks about model choice; verify current model information before advising.

## Scope boundary

Use this skill for a focused writing operation. For full-paper planning, venue templates, citation verification, or end-to-end manuscript production, use a dedicated paper-writing workflow instead. For reading notes or appraisals, preserve the local project's template and the user's preferred student-note voice unless they explicitly ask to apply a prompt from this collection.

## Source

Adapted for Codex from <https://github.com/Leey21/awesome-ai-research-writing>, upstream commit `df0af726a79109b8760c1b80d5dfc36ed44a6f1f` (checked 2026-09-04). The upstream `README.md` is retained verbatim so its prompts and attribution remain visible.
