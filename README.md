# 牛波一项目

2026 国赛 B 题三人协作仓库：两人负责建模、编程与实验，一人负责中文论文。比赛周期三天，优先完成可验证的模型、可复现的结果与可用于写作的材料。

## 从这里开始

1. 阅读 [题面与附件](problem/README.md)，结合 [题目阅读](docs/notes/题目阅读.md) 统一理解；后续建模、编程、实验和论文写作时回查，确保与题意一致。
2. 建模路线见 [总体方案](docs/model/总体方案.md)；编程与联调先按下方步骤安装，再看 [模拟器说明](docs/simulator/README.md)。
3. 建模与实验侧将可用于写作的材料放入 [handoff/](handoff/README.md)；论文手从该索引取用材料，在 [paper/](paper/README.md) 内组织论文。
4. 开工与提交参考 [GitHub 协作速查](github-guidance.md)。使用 Codex 时从本仓库目录启动，项目约定见 [AGENTS.md](AGENTS.md)。

## 当前进展

| 内容 | 状态与入口 |
| --- | --- |
| 四问建模 | [总体方案](docs/model/总体方案.md)已有候选推导与实现路线；Q1 几何、Q2 选点、Q3/Q4 搜索清除算法仍待实现和实验验证 |
| 本地模拟器 | 已有物理规则、HTTP 服务、客户端、回放与调试网页，可用于规则验证和联调；兼容边界见 [模拟器说明](docs/simulator/README.md) |
| 工程验证 | [整合验证记录](results/validation/integration-20260911-4f12388/README.md)包含 39 项通过的回归测试、原件校验、计时回放与内核对比；尚无完整策略的效果验证 |
| 论文与交付 | [paper/](paper/README.md)已有论文框架与排版文件，由论文手维护；[handoff/](handoff/README.md)尚待整理可用的模型、实验结论和图表 |

接下来先实现并验证确定性求解闭环；学习调度是可选路线，目前没有训练流程。候选推导和本地测试通过的结论，仍需结合题面与策略实验核实后用于论文。

## 目录

以下列出当前主要目录，后续随实现增补：

```text
B-problem/
├── problem/                 # 原始题面与文件校验值
│   └── 附件/                # 官方附件原件
├── docs/
│   ├── model/               # 数学推导、假设、符号与模型说明
│   ├── notes/               # 题目阅读、讨论与待解问题
│   └── simulator/           # 模拟器用法、规则依据与兼容范围
├── src/
│   └── bsim/                # 本地模拟器、客户端、策略接口与调试网页
├── scripts/                 # 实验、结果处理与绘图入口，待实现
├── tests/
│   ├── simulator/           # 物理规则、计时、协议与网页接口回归
│   └── fixtures/            # 固定测试输入；模拟器样例在 simulator/ 下
├── experiments/             # 实验配置与分析代码，待实现
│   ├── q1/
│   ├── q2/
│   ├── q3/
│   └── q4/
├── results/
│   ├── validation/          # 工程验证与历史导入记录
│   ├── rehearsal/           # 本地策略评估与官方演练，分别标注
│   ├── formal/              # 正式测试原始记录，不覆盖或删除
│   ├── figures/             # 生成的图
│   └── tables/              # 生成的表
├── handoff/                 # 建模与实验侧交给论文手的材料
├── paper/                   # 论文手维护；main.tex 为编译入口
│   ├── sections/            # 论文各章节
│   └── figures/             # 论文采用的图片
└── .agents/
    └── skills/              # 共享绘图与写作技能
```

结果留存见 [结果说明](results/README.md)，共享技能见 [使用说明](.agents/skills/README.md)。

文档优先中文。协作说明保持简短，模型推导和实验记录保留复现与核对所需信息；同一内容优先链接引用。

`handoff/` 先按问题写文档，引用具体模型和实验记录。空目录中的 `.gitkeep` 在加入实际文件后可移除。

## 运行环境

项目要求 Python 3.9+，整合验证使用 Python 3.13。模拟器运行只使用标准库。从仓库根目录首次安装：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m bsim audit-rules
python -m bsim validate-fixtures --profile fixture_conformance
```

Windows 使用 `python` 创建环境，并在 PowerShell 中运行 `.venv\Scripts\Activate.ps1` 激活。后续开新终端时重新激活即可；可编辑安装后，源码修改直接生效，依赖配置变化时重新安装。换克隆或工作区时重新创建各自的环境。安装构建需要 setuptools，具体要求见 [pyproject.toml](pyproject.toml)。

启动本地网页：

```bash
python -m bsim web --port 8765 --robot-port 20260
```

打开终端打印的完整链接。网页用于固定场景下的手动调试；接入算法、回放和完整验证命令见 [模拟器说明](docs/simulator/README.md)。
