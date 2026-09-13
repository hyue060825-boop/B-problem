# B-problem：论文实验与最终模型

`experiment_result` 是论文材料整理分支。先读 **[论文写作指导说明书](paper/论文写作指导说明书.md)**，再查 [全部实验索引](paper/EXPERIMENT_INDEX.md) 和 [图表索引](paper/FIGURE_INDEX.md)。

| 题目 | 用户指定的最终 checkpoint | SHA256 前缀 |
|---|---|---|
| Q3 | [best.pt](runs/q3_legacy_deadline_20260913/best.pt) | `51397bc8` |
| Q4 | [best.pt](runs/q4_baseline_8gpu_1h_20260913/train/best.pt) | `c8812ced` |

两题使用 `CandidatePolicy / normalized-public-v2`，运行代码与权重来源一致。最终 Q4 的独立测试均值略优于父基线，但配对区间跨零；无源尾段、空场景、四组对照和 Q4 极端布局使用父基线，具体归属见 [模型清单](paper/model_registry.json)。

| 目录 | 内容 |
|---|---|
| `paper/` | 中文写作指南、数据表、图表、原始方案、官方单例日志、证据清单 |
| `paper/history/` | 全部历史实验的逐局数据/标签/日志分卷及可浏览报告图表，含失败与阴性结果 |
| `runs/` | 展开的最终训练谱系、主评测与相关补充实验；保留少量必要对照权重 |
| `solution/`、`bsim/` | 匹配最终权重的策略、几何和研究模拟器 |
| `scripts/`、`tests/` | 最终版本训练、分析、部署、复核入口与相应测试 |
| `artifacts/`、`reports/` | Q1/Q2算例和直接相关主报告；其他原报告在历史区 |
| `deployment/` | 冻结运行时、CPU参考输出、Windows部署说明 |
| `cache/` | 仅服务器本地保存原工作区及不用的权重；不进入Git分支 |

## 复核与生成论文图表

Python 3.11；先安装适合本机的 PyTorch（服务器记录版本2.5.1），然后：

```bash
python -m pip install -r requirements-paper.txt
python -m pip install -e .
python scripts/build_paper_catalog.py
python scripts/verify_paper_release.py
python -m pytest -q
```

已有服务器虚拟环境可用 `./scripts/run_python.sh` 代替 `python`。图表生成仅重算已有数据，不重新训练或访问官方接口。[复现说明](docs/REPRODUCING.md) 区分原始复核与新实验。

## Windows 使用

按 [部署说明](deployment/README_WINDOWS.md) 安装依赖。运行 `python scripts/build_windows_policy_bundle.py` 可生成两份最终权重配套的独立部署ZIP；输出目录已存在时会拒绝覆盖。连接官方程序之前先运行 `--check-only`。

## 原始数据保全

原工作区25984个文件全部原样移至服务器 `cache/original_workspace_20260913/` 并核对SHA256。所有历史实验的非模型数据也以可校验分卷纳入本分支；旧模型及冗余源码大包仍留本地cache。[原始清单](paper/provenance/original_inventory.json) 可用于逐文件找回。解包仅写入新目录，不覆盖当前代码。

整理后验证：195项测试、15个子测试通过；模型/源码、分卷和全部原件校验通过。详见 [验证结果](paper/provenance/release_verification.json) 与 [检查记录](paper/provenance/checks/README.md)。

新增补充实验：[最终Q4的10–16源各1000局评测](runs/q4_final_best_counts_20260913/evaluation/report.md)，7000/7000完成，六张分布图（PNG/PDF）及逐局数据已归档。
