# 牛波一项目

三人协作仓库：两人负责建模、编程与实验，一人负责中文论文。比赛周期三天，优先完成可验证的模型、可复现的结果与可用于写作的材料。

## 从这里开始

1. 阅读 [题面与附件](problem/README.md)，结合 [题目阅读](docs/notes/题目阅读.md) 统一理解；后续建模、编程、实验和论文写作时回查，确保与题意一致。
2. 开工与提交参考 [GitHub 协作速查](github-guidance.md)。使用 Codex 时从本仓库目录启动，项目约定见 [AGENTS.md](AGENTS.md)。
3. 建模与实验侧将可用于写作的材料放入 [handoff/](handoff/README.md)；论文手从该索引取用材料，在 [paper/](paper/README.md) 内组织论文。
4. 当前建模路线见[总体方案](docs/model/总体方案.md)，本地联调从[模拟器说明](docs/simulator/README.md)开始。

## 目录

| 路径 | 用途 |
| --- | --- |
| `problem/` | 原始题面、附件与文件校验值 |
| `docs/model/` | 数学推导、假设、符号与模型说明 |
| `docs/notes/` | 讨论、待解问题与方案选择记录 |
| `docs/simulator/` | 本地模拟器使用、规则依据与兼容范围 |
| `src/` | 可复用算法与模拟器交互代码 |
| `scripts/` | 运行实验、处理结果与绘图的入口 |
| `tests/` | 几何边界、算法正确性、接口等必要验证 |
| `experiments/q1/` 至 `q4/` | 各问题的实验配置与分析代码；原始运行输出放 `results/` |
| `results/` | 演练与正式测试记录，以及生成的图表 |
| `handoff/` | 经整理的论文交付材料，注明依据与待确认事项 |
| `paper/` | 论文手维护的正文、排版及提交材料 |
| `.agents/skills/` | 共享绘图与写作技能，见 [使用说明](.agents/skills/README.md) |

文档优先中文。协作说明保持简短，模型推导和实验记录保留复现与核对所需信息；同一内容优先链接引用。

上述分类按实际工作调整。当前模拟器在 `src/bsim/`，对应测试和夹具在 `tests/simulator/`、`tests/fixtures/simulator/`。其他算法随实现增加；`handoff/` 先按问题写文档。空目录中的 `.gitkeep` 在加入实际文件后可移除。

## 运行环境

Python 3.9+，模拟器运行只使用标准库。从仓库根目录安装：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m bsim audit-rules
python -m bsim validate-fixtures --profile fixture_conformance
```

Windows PowerShell 使用 `.venv\Scripts\Activate.ps1` 激活环境。可编辑安装后，源码修改直接生效；换克隆或工作区时使用各自环境。安装构建需要 setuptools，具体要求见 `pyproject.toml`。

启动本地网页：

```bash
python -m bsim web --port 8765 --robot-port 20260
```

打开终端打印的完整链接。更多命令与策略接入见[模拟器说明](docs/simulator/README.md)。当前已有本地规则验证工具，Q3/Q4 完整求解器和学习训练流程尚未实现；验证记录见 [results/](results/README.md)。
