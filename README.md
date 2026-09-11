# 牛波一项目

2026 国赛 B 题三人协作仓库，比赛周期三天。hyue060825-boop 在 `hy_branch/b45c0d2` 完成 Q1–Q4 建模、编程与实验；由验收负责人整合到 `main`，再与 Iloverice-wang 整理资产、验证结果和完成中文论文。

## 从这里开始

1. 阅读[题面与附件](problem/README.md)和[题目阅读](docs/notes/题目阅读.md)，后续建模、实验、写作时回查题意。
2. 先看[总体方案](docs/model/总体方案.md)与[实现索引](docs/model/实现索引.md)，区分候选推导、已实现算法和待验证结论。
3. 本次接收状态与遗留问题见[接收记录](docs/notes/接收记录-4d75bee.md)；论文手从 [handoff/](handoff/README.md) 取用材料，在 [paper/](paper/README.md) 组织正文。
4. 协作流程见 [GitHub 速查](github-guidance.md)，项目约定见 [AGENTS.md](AGENTS.md)，共享技能见[使用说明](.agents/skills/README.md)。

## 当前进展

已接收 hy 分支截至 `4d75bee` 的资产，包含此前 `c457828` 和 `ef52a6b` 引入的内容；源码、配置与历史结果已按下列目录整理。

| 内容 | 状态与入口 |
| --- | --- |
| Q1/Q2 | 已有几何求解、选点算法、人工算例和图件；Q2 部分夹具、图件与参数说明仍待完善，见[实现索引](docs/model/实现索引.md) |
| Q3/Q4 | 已有覆盖、定位与清除控制器；本轮未改算法，Q4 结束逻辑尚待 hy 修复 |
| 研究训练 | 已接收大规模日志、逐局结果和 38 份新权重；Q3 主训练及续训已交付 COMPLETE，Q4 retry 为中途快照，见[训练归档](results/training/import-4d75bee/README.md) |
| 部署与评估 | 已有 checkpoint 部署和配对评估入口；部署尚待端到端验证，用法见[本机部署](docs/simulator/local_deployment.md) |
| 本地模拟器 | `src/bsim/` 保留物理规则、HTTP 服务、客户端、回放和网页；用法与兼容范围见[模拟器说明](docs/simulator/README.md) |
| 验证与论文 | 工程验证、策略质量和官方成绩分别记录；[本次整合验证](results/validation/integration-4d75bee/README.md)与[交付索引](handoff/README.md)提供证据入口 |

自建模拟器用于批量研究训练和可重复实验；随后用官方演练验证、迭代，再进行正式测试。Q3 新交付的 32 局评估记录中，教师和模型均完成全部任务，模型平均虚拟时间下降约 8.82%；尚未在本机复跑，不代表官方成绩。

## 目录

```text
B-problem/
├── problem/                    # 原始题面、附件与校验值
│   └── 附件/
├── docs/
│   ├── model/                  # 总体方案、实现与推导索引
│   ├── notes/                  # 题目阅读、接收记录；extracted/ 为题面提取材料
│   └── simulator/              # 本地模拟器说明与兼容范围
├── src/
│   ├── bsim/                   # 模拟器、客户端、研究场景与调试网页
│   └── solution/               # geometry、planning、coverage、control、rl、evaluation
├── scripts/                    # 覆盖验证、训练、checkpoint 评估与本机部署入口
├── tests/
│   ├── simulator/              # 物理、协议、计时、客户端与网页回归
│   ├── solution/               # 几何、选点、覆盖与学习组件测试
│   └── fixtures/               # simulator/ 与 solution/ 固定输入
├── experiments/
│   ├── q1/                     # 后续按实验需要补充
│   ├── q2/
│   ├── q3/                     # large_20260911/：主训练及续训配置
│   └── q4/                     # large_20260911/：主训练配置
├── results/
│   ├── validation/             # 原始报告、算例图件、工程验证与接收证据
│   ├── training/               # 历史权重、训练记录；新训练单独建目录
│   ├── rehearsal/              # 本地策略评估与官方演练，分别标注
│   ├── formal/                 # 正式原始结果，不覆盖或删除
│   ├── figures/                # 后续生成的图
│   └── tables/                 # 后续生成的表
├── handoff/                    # 提供给论文手的材料与状态索引
├── paper/                      # 论文手维护，main.tex 为入口
│   ├── sections/
│   └── figures/
└── .agents/skills/             # 共享绘图与写作技能
```

日常实现和配置使用新目录；`results/**/import-*` 保存原始交付记录，旧路径按[前批映射](results/validation/integration-c457828/资产映射.csv)或[本批映射](results/validation/integration-4d75bee/资产映射.csv)查找。历史 provenance 不改写，新运行另存输出。

## 运行环境与入口

项目要求 Python 3.11+。从仓库根目录安装基础建模与模拟器环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m bsim audit-rules
python -m bsim validate-fixtures --profile fixture_conformance
```

学习模块及全量测试还需 PyTorch 和 pytest，可安装 `python -m pip install -e '.[rl,test]'`。模拟器核心本身使用标准库，整个项目的建模环境还包括 NumPy、SciPy、Shapely 等，依赖见 [pyproject.toml](pyproject.toml)。Windows 使用 `python` 创建环境，在 PowerShell 中运行 `.venv\Scripts\Activate.ps1`。

运行几何算例与覆盖检查，输出目录每次另取名称：

```bash
python -m solution.cli solve-q1 --input tests/fixtures/solution/q1_triangle.json --output results/figures/q1-example
python -m solution.cli solve-q2 --input tests/fixtures/solution/q2_example.json --output results/figures/q2-example
python scripts/validate_coverage.py --problem 4
python -m pytest -q
```

启动调试网页：`python -m bsim web --port 8765 --robot-port 20260`，打开终端打印的完整链接。训练配置和已知入口限制见[实验说明](experiments/README.md)；结果留存见[结果说明](results/README.md)。
