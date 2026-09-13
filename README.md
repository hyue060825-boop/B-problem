# 牛波一项目

2026 国赛 B 题三人协作仓库。hyue060825-boop 的最终模型、代码和实验来自 `experiment_result@8ef9ef8`；验收负责人整合到 `main`，与 Iloverice-wang 维护结果、交付与中文论文。

## 从这里开始

1. [题面与附件](problem/README.md)和[题目阅读](docs/notes/题目阅读.md)：建模、实验、写作时回查题意。
2. [Q1](handoff/q1/README.md)、[Q2](handoff/q2/README.md)、[Q3](handoff/q3/README.md)、[Q4](handoff/q4/README.md)：每题方法、实现、结果与引用边界。
3. [最终方案与实验说明](handoff/shared/最终方案与实验说明.md)、[最终实验索引](handoff/shared/最终实验索引.md)：最终选型、训练谱系、补充分析、失败与中断记录。
4. [部署与自检](deployment/README.md)、[最终模型复现](docs/simulator/最终模型复现.md)：指定权重、配套代码、运行和复算命令。
5. [图件](handoff/figures/README.md)、[表格](handoff/tables/README.md)、[版本记录](records/versions.md)：写作资产及来源。

## 最终状态

| 内容 | 状态与证据 |
| --- | --- |
| Q1/Q2 | 几何求解、保证接收区域和选点算法；另保留 main 的两篇文献与 [LIT-Q2-01 实际补测实验](handoff/shared/文献启发与Q2改进说明.md) |
| Q3 | 七站覆盖、侧翼定位、清除证书与候选动作网络；最终权重 `51397bc8…` |
| Q4 | 31 站定向覆盖、完整负观测认证和 16 源上界；最终权重 `c8812ced…` |
| 主实验 | 两题各 3000/3000 完成，清除源数 38961/39086；平均整局 3255.759/9685.100 s，平均逐局 T/N 为 255.989/767.252 s/源，见[主表](handoff/tables/final-20260913/final_main_results.csv) |
| 补充实验 | 按源数、无源尾段、规划对照、空场景、有限布局搜索和精确覆盖证书；逐项标注最终/父模型 |
| 论文 | main@910df44 已引用最终主结果；[论文入口](paper/README.md)及[写作证据快照](results/final-8ef9ef8/README.md)保留原路径 |

主结果来自自建研究分布，时间包含完成搜索和不存在确认。Q4 相对父模型的配对均值略降，但 95% 区间跨零。提供的一份官方 Q4 交互日志属于父模型；各次正式成绩与加密导出尚未包含在本次 Git 交付中。

## 目录

```text
B-problem/
├── problem/                    # 原题、附件和校验值
├── docs/
│   ├── model/                  # 总体推导与实现索引
│   ├── notes/                  # 题意阅读与提取材料
│   ├── references/             # 文献来源与适用边界
│   └── simulator/              # 模拟器、部署与复现说明
├── src/
│   ├── bsim/                   # 研究模拟器、协议、回放和网页
│   └── solution/               # 几何、覆盖、控制、学习与搜索
├── deployment/
│   ├── runtime_public_v2/      # 与最终权重匹配的冻结代码
│   └── bundles/                # 原始便携 ZIP
├── scripts/                    # 训练、测评、部署、复算与核验入口
├── tests/
│   ├── simulator/
│   ├── solution/
│   └── fixtures/               # 固定输入
├── experiments/
│   ├── q1/、q2/                # Q2 含 LIT-Q2-01
│   └── q3/、q4/                # 配置及 Q4 精确证书、规划实验工具
├── results/
│   ├── final-20260913/         # 本次完整交付：最终/父模型与活跃实验
│   ├── history/                # 完整历史分卷与浏览副本
│   ├── final-8ef9ef8/          # 论文已引用的固定证据子集，保留路径
│   ├── training/、validation/  # 前期交付、训练和工程验证
│   ├── rehearsal/、official/   # 新运行；已交付的官方单例另记类型
│   └── formal/                # 正式原始导出，不覆盖或删除
├── records/
│   ├── acceptance/            # 接收、映射、来源与核验
│   ├── inventory/             # 数据、权重与图件清单
│   ├── protocols/             # 历史方案与提示词
│   └── improvements/          # 文献启发等方法改进记录
├── handoff/
│   ├── q1/、q2/、q3/、q4/     # 每题写作依据
│   ├── shared/                # 最终方案、实验索引和共同约定
│   └── figures/、tables/      # 按批次保存图表与来源
├── paper/                      # 论文手维护，main.tex 为入口
└── .agents/skills/             # 共享绘图与写作技能
```

原始数据、配置、代码快照和 provenance 按接收时字节保存；旧路径从[逐文件映射](records/acceptance/experiment_result-8ef9ef8/资产落位建议.csv)查找。当前说明指向完整交付，论文快照保留为稳定引用。历史文件中的 best/final 名称按[模型身份清单](records/inventory/models-final-20260913.json)解释。

## 环境与运行

Python 3.11+，从仓库根目录安装：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[rl,test]'
python -m bsim audit-rules
python -m bsim validate-fixtures --profile fixture_conformance
python -m pytest -q
```

原部署环境为 Python 3.11、CPU PyTorch 2.5.1；便携包依赖和 Windows 用法见[部署说明](deployment/README.md)。研究代码位于 `src/`，最终运行入口自动加载配套冻结运行时，不关闭源码校验。

```bash
python scripts/run_policy.py --problem 3 --checkpoint results/final-20260913/q3_legacy_deadline_20260913/best.pt --robot-id LOCAL-CHECK --check-only
python scripts/run_policy.py --problem 4 --checkpoint results/final-20260913/q4_baseline_8gpu_1h_20260913/train/best.pt --robot-id LOCAL-CHECK --check-only
python scripts/build_final_handoff_assets.py
python scripts/verify_final_assets.py
```

上述自检不连接模拟器；复算只更新 handoff 衍生表和来源清单，保留原图及原数据。前期 F001–F009 和 LIT-Q2-01 图表仍分别用 `build_handoff_assets.py`、`build_q2_literature_assets.py` 生成。[GitHub 速查](github-guidance.md)与 [AGENTS.md](AGENTS.md)说明协作约定。
