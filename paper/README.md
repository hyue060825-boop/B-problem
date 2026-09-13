# 论文工作目录

入口 `main.tex`，使用 XeLaTeX 或 Tectonic 编译。论文按 `sections/` 拆分；`figures/` 保存绘图结果，`09b_conclusion.tex` 为结论，`AI_usage_details.tex` 为待据实填写的 AI 使用详情。

2026-09-13 更新：Q3/Q4 最终代码与结果以实验分支固定提交 `8ef9ef8` 为依据，核心证据在 `../results/final-8ef9ef8/`。源数对照图通过 `python3 scripts/build_final_paper_assets.py` 在仓库根目录生成。

论文以“在确保所有干扰源被清除的前提下优化耗时”为统一目标。Q3/Q4 最终模型在各 3000 个研究场景中均完成全部清除与合法退出，平均每源总虚拟时间分别为 255.99 s / 767.25 s，包含未知频道不存在证明。正文仅报告最终模型，Q3 有利布局作为有限候选实测参照。

审阅状态与正式提交前缺项见 `QUALITY_REVIEW.md`。本版不将研究测试冒充题面正式测试。
