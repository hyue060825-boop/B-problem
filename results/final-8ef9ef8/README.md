# 最终论文证据快照（2026-09-13）

来源：GitHub `hyue060825-boop/B-problem` 的 `experiment_result`，固定提交 `8ef9ef87d8c5413e85e02d18a99eee083da8d66f`。本目录只导入论文所需的固定材料；全部历史、分卷档案及额外诊断保留在该提交中，不把实验分支的不同目录结构覆盖到主分支。

- `final-runtime.zip`：冻结的 solution、bsim、scripts、tests、部署说明和两份最终权重。解压到独立目录运行，勿与主分支 `src/` 混用。
- `paper/model_registry.json`：模型与权重身份。Q3 最终 `51397bc8…`，Q4 最终 `c8812ced…`。
- `runs/`：Q3 最终/父模型逐局记录、Q4 最终配对记录及辅助实验摘要。
- `paper/tables/`：实验分支原始导出，保持不改。
- `sha256.json`：导入时 37 个原始文件的 SHA-256 清单；新增 README、复算和核验输出不属于原始文件清单。
- `paper_recalculation.json`：在主分支独立复算的均值、完成率、配对区间和权重校验。
- `release_verification.json`：固定实验分支的发布材料核验输出；完整原始缓存不在本机时，不能声称本机已检验该缓存全部内容。

## 复算

在主仓库运行 `python3 scripts/build_final_paper_assets.py`。脚本逐局核验完成率、清除数等于真实源数、虚拟计时分解和配对场景身份，复算并绘制 `paper/figures/F013-complete-search-comparison.pdf`。

## 解释边界

Q3/Q4 各 3000 局均完成，38961/39086 个源全部清除。时间包含不存在证明。主结果均为研究测试，不冒充官方正式三次测试。
Q4 布局搜索、尾部分析、规划消融及单份官方日志来自父模型，不能归到最终模型。每个 N 的 704 个布局候选是有限搜索；最快观察值不是全局最优或理论下界，低于该值不能据此断言遗漏。16 源可利用数量上限结束未知频道覆盖，仍须清除所有发现源。

## 参数构造链补充

[继承链证据](lineage/README.md) 恢复 SFT 与 DAgger 的真实角色：最终 Q3 包含 SFT 继承；DAgger 第二轮已执行但当轮选模回退到第一轮 SFT。不能根据末段仅运行 PPO 删除前期方法。
