# 牛波一项目

2026 国赛 B 题三人协作仓库，比赛周期三天。hyue060825-boop 在 `hy_branch/b45c0d2` 完成 Q1–Q4 建模、编程与实验；由验收负责人整合到 `main`，再与 Iloverice-wang 整理资产、验证结果和完成中文论文。

## 从这里开始

1. 阅读[题面与附件](problem/README.md)和[题目阅读](docs/notes/题目阅读.md)，后续建模、实验、写作时回查题意。
2. 从[实现索引](docs/model/实现索引.md)查看当前算法；[总体方案](docs/model/总体方案.md)保留完整候选推导，说明导航见 [docs/](docs/README.md)。
3. 按 [Q1](handoff/q1/README.md)、[Q2](handoff/q2/README.md)、[Q3](handoff/q3/README.md)、[Q4](handoff/q4/README.md) 阅读当前方法、代码与实验；[handoff/](handoff/README.md) 集中提供中文图表和写作依据。
4. [records/](records/README.md) 保存接收、版本与资产清点，当前边界见[接收记录](records/acceptance/接收记录-3ddb2d9.md)。
5. 协作流程见 [GitHub 速查](github-guidance.md)，项目约定见 [AGENTS.md](AGENTS.md)，共享技能见[使用说明](.agents/skills/README.md)。

## 当前进展

已接收 hy 分支截至 `3ddb2d9` 的资产，包含 Q4 控制修复、同步多卡训练、Q3 搜索与最新配对评估；保留 main 的论文和历史结果，源码、配置及新交付沿用下列目录。

| 内容 | 状态与入口 |
| --- | --- |
| Q1/Q2 | 已有几何求解及选点算法；LIT-Q2-01新增Q2一致夹具、120场景实际补测和参数检查，见[实现索引](docs/model/实现索引.md) |
| Q3/Q4 | 已有覆盖、定位与清除控制器；已接收 Q4 不存在认证和退出修复，新增 Q3 搜索教师与 GPU 搜索 |
| 研究训练 | 已接收同步 DDP、Q3 联合微调及 Q4 预算训练，本批含 10 份权重；见[最新交付](results/training/import-3ddb2d9/README.md)，旧批次单独保留 |
| Q3/Q4 配对评估 | 四组各 3000 局记录均完成；Q3 候选、Q4 best 相对本批对照平均每局少 14.32 s、308.35 s，见[最新报告](results/training/import-3ddb2d9/runs/q34_3000_test_20260912/report.md) |
| 部署与评估 | 已实跑四模型共 8 局评估及 Q3/Q4 各一次自建 HTTP 部署；关键源码校验兼容目录迁移，用法见[本机部署](docs/simulator/local_deployment.md) |
| 本地模拟器 | `src/bsim/` 保留物理规则、HTTP 服务、客户端、回放和网页；用法与兼容范围见[模拟器说明](docs/simulator/README.md) |
| 验证与论文 | 工程验证、策略质量和官方成绩分别记录；[本次整合验证](results/validation/integration-3ddb2d9/README.md)与[交付索引](handoff/README.md)提供证据入口 |

自建模拟器用于批量研究训练和可重复实验；随后用官方演练验证、迭代，再进行正式测试。Q3 的 32 局配对测试、四路选模验证和 3000 局单策略评估使用的权重及统计口径不同，按[交付索引](handoff/README.md)分别引用；本轮复核交付记录并做少量场景运行验证，未重跑完整Q3/Q4测评；Q2另增LIT-Q2-01本地实验，均不代表官方成绩。

## 目录

```text
B-problem/
├── problem/                    # 原始题面、附件与校验值
│   └── 附件/
├── docs/
│   ├── model/                  # 总体方案、实现与推导索引
│   ├── notes/                  # 题目阅读；extracted/ 为题面提取材料
│   ├── references/             # 两篇ICRA文献及本题适用边界
│   └── simulator/              # 本地模拟器说明与兼容范围
├── src/
│   ├── bsim/                   # 模拟器、客户端、研究场景与调试网页
│   └── solution/               # geometry、planning、coverage、control、rl、evaluation、search
├── scripts/                    # 训练、评估、部署、图表生成与资产清点
├── tests/
│   ├── simulator/              # 物理、协议、计时、客户端与网页回归
│   ├── solution/               # 几何、选点、覆盖与学习组件测试
│   └── fixtures/               # simulator/ 与 solution/ 固定输入
├── experiments/
│   ├── q1/                     # 后续按实验需要补充
│   ├── q2/                     # lit_q2_01.json：实际补测与参数实验
│   ├── q3/                     # large_20260911/、joint_20260912.json
│   └── q4/                     # large_20260911/、repaired_20260912.json、budget_20260912.json
├── results/
│   ├── validation/             # 原始报告、算例图件、工程验证与接收证据
│   ├── training/               # 历史权重、训练记录；新训练单独建目录
│   ├── rehearsal/              # 本地策略评估与官方演练，分别标注
│   ├── formal/                 # 正式原始结果，不覆盖或删除
│   ├── figures/                # 后续生成的图
│   └── tables/                 # 后续生成的表
├── records/                    # 版本、接收和整理记录
│   ├── acceptance/
│   ├── improvements/           # 方法改进与验证记录
│   └── inventory/              # 数据批次、文件、权重与图件清单
├── handoff/                    # 提供给论文手的当前方法与实验依据
│   ├── q1/、q2/、q3/、q4/       # 每题模型、实现、结果和图表入口
│   ├── shared/                  # 共同约定、训练过程与统计口径
│   ├── figures/                 # 中文 PDF / SVG / PNG 及设计规格
│   └── tables/                  # 整理 CSV、网格和来源校验
├── paper/                      # 论文手维护，main.tex 为入口
│   ├── sections/
│   └── figures/
└── .agents/skills/             # 共享绘图与写作技能
```

日常实现和配置使用新目录；原始交付记录的旧路径按 [c457828 映射](results/validation/integration-c457828/资产映射.csv)、[4d75bee 映射](results/validation/integration-4d75bee/资产映射.csv)或[9e10994 映射](results/validation/integration-9e10994/资产映射.csv)查找。本轮增量见[3ddb2d9 映射表](results/validation/integration-3ddb2d9/asset-map.csv)。论文已引用的结果归档保留其路径；历史 provenance 不改写，新运行另存输出。

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
python -m solution.cli solve-q2 --input tests/fixtures/solution/q2_example_lit.json --output results/validation/q2-example-new
python scripts/validate_coverage.py --problem 4
python -m pytest -q
```

启动调试网页：`python -m bsim web --port 8765 --robot-port 20260`，打开终端打印的完整链接。训练配置和已知入口限制见[实验说明](experiments/README.md)；结果留存见[结果说明](results/README.md)。

## 整理数据与重绘图表

```bash
python scripts/build_handoff_assets.py
python scripts/build_q2_literature_assets.py
python scripts/inventory_assets.py
```

前两条命令分别生成F001—F009及原批表格、LIT-Q2-01的F010—F012及补充表格，不运行策略或训练。需要中文字体，原批流程图导出还使用 `rsvg-convert`；原批只复算表格可加 `--tables-only`。最后一条更新 `paper/` 之外的资产清单。各脚本只登记自身生成文件的来源；原始实验数据按既有批次保留。

**文献启发补充 · LIT-Q2-01**：[独立交付说明](handoff/shared/文献启发与Q2改进说明.md)集中说明Q2新增方法与实验、Q3/Q4方案补充及写作边界；[实验入口](experiments/q2/README.md)提供复现命令，[文献来源](docs/references/README.md)提供引用信息。
