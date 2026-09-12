# 论文工作区

由论文手自行组织中文论文正文、图表、排版与提交材料。

建模及实验侧的写作资料见 [论文交付材料](../handoff/README.md)，原始题面见 [problem/](../problem/README.md)。

## 入口与当前状态

- [Overleaf 写作项目](https://www.overleaf.com/project/6aa35e81fca7345a83057613)（项目访问权限由 Overleaf 单独管理）。
- [main.tex](main.tex)：编译入口，选择 **XeLaTeX**；[main.pdf](main.pdf) 为 2026-09-12 本地重新编译的 26 页预览快照；本轮编译成功且无正文溢出。正文已按优秀论文写作经验补充问题重述、四问关系、假设依据、算法接口和结果解释，并使四问分别起页；同版源码已同步 Overleaf，在线编译为 26 页、0 错误、0 警告。
- 2026-09-12 算法核对版补充了 Q1 半平面交与覆盖证明、Q2 接收内近似与真实评分系数、Q3 条件化搜索教师及 SFT/DAgger/PPO 三阶段后训练，替换六张中文矢量图。训练规模与阶段回退结果移入实验设计；没有把训练成本写成在线成本。几何与 Q2 的 15 项回归测试通过。
- 2026-09-12 已按仓库最新实验方案更新正文：问题三冻结基线与 PPO 候选在 3000 个同场景试验中均全部完成，候选平均总耗时下降 0.43%，但冻结选模规则仍推荐基线；问题四修复终止与退出逻辑后，训练前模型与预算训练 best 在 3000 个同场景试验中均全部完成，best 平均总耗时下降 3.03%。联合批次 12000 条记录已通过配对、指标复算和训练测试种子隔离检查。问题四几何构造保持 42 个闭三角形、31 个检测点。灰色 `【】` 仍是正式测试成绩、参数灵敏度图、完整轨迹与退出证书图、AI 使用详情及完整程序附录等待填写项，不能视为已有结果。
- `sections/`：摘要、问题分析、假设、符号表、四问正文、检验、评价、AI 声明、参考文献和附录；论文手主要编辑这里。
- `figures/`：论文图片。建模侧先在 `handoff/` 交付图表出处和说明，再由论文手取用。
- `cumcm2026base.cls`、`cumcm2026.sty`：LaTeX 工作室 2026 排版底版；不要随正文反复改动。
- `AI_usage_details.tex`：单独编译的使用详情，最终文件名为 `AI工具使用详情.pdf`，放入支撑材料。内容须按真实使用情况填写。
- `QUALITY_REVIEW.md`：依据 2026 官方规范、全国评阅流程和 2025 年优秀论文写法整理的质量审查清单；提交前应逐项关闭其中的阻断项。

## GitHub 与 Overleaf 同步

当前使用源码快照同步，**尚未启用自动同步**。Overleaf 当前账号的 GitHub 入口会引导订阅；官方原生 Git/GitHub 同步为 Premium 功能。不要把 GitHub 推送成功理解为 Overleaf 已更新。

1. GitHub 保存团队版本：开始前 `git pull --ff-only`；论文手可按仓库协作约定直接提交自己维护的 `paper/`。
2. 若在 Overleaf 写作：先下载最新源文件，比较差异后更新本仓库 `paper/`，保留队友已提交内容，再提交推送。
3. 若在 GitHub/本地写作：先提交，再从仓库根目录导出仅含论文的包：

   ```bash
   git archive --format=zip --output=../B-problem-paper-Overleaf.zip HEAD:paper
   ```

   ZIP 根目录直接是 `main.tex`，不包含仓库其他目录。首次导入可用 Overleaf 的上传项目；更新当前项目时先下载其最新源码作比较，只上传本轮更改的文件。设置主文档 `main.tex`、编译器 XeLaTeX，编译成功后完成本次同步。
4. 同一轮只在一端修改，另一端先同步再继续。`main.pdf` 是快照，正文修改后需重新编译更新。

参考：[Overleaf GitHub 同步说明](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/github-synchronization)。当前已存在的 Overleaf 项目不能直接绑定已存在的 GitHub 仓库；将来启用原生同步时需按官方支持的导入流程处理。

## 本地编译

安装 TeX Live / MacTeX 后，在 `paper/` 中运行：

```bash
latexmk -xelatex main.tex
```

参考文献暂在 `sections/11_references.tex` 手动管理，正文使用 `\cite{标签}` 引用。附录需补齐全部完整可运行程序与实际支撑材料清单。

## 排版来源

[latexstudio/CUMCMThesis](https://github.com/latexstudio/CUMCMThesis)：类文件版本 2026/08/26 v2.9，配套样式版本 2026/08/23 v1.0。为区分旧模板，类文件名和 `ProvidesClass` 改为 `cumcm2026base`；其余上游内容保留。项目主文件采用数字章节编号。旧模板及其未使用的字体没有导入本目录。

[2026 官方格式规范](https://www.mcm.edu.cn/upload_cn/node/775/cQMeL0YY905244c8bd4b9af832f1699446d8385e.pdf)；[2026 AI 使用规定](https://www.mcm.edu.cn/html_cn/node/fef94648f2836ab6cc81586f4c38512b.html)。
