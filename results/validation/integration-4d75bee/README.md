# 4d75bee 接收与目录整合验证

hy 来源为 `4d75bee81beaace2092f3812ede68d16d3dee353`，main 基点为 `d6c7eb0f2fe0e1059db5c6a1b94d816e18dfc5f0`。按现状接收训练资产及部署、评估入口；本轮不修复算法问题，交付状态见[接收记录](../../../records/acceptance/接收记录-4d75bee.md)。

| 检查 | 结果与证据 |
| --- | --- |
| 原始训练资产 | 2905 个文件逐一核对 Git blob、SHA256 和文件权限，全部与 hy 一致，包含 38 份权重；[资产映射](资产映射.csv)还记录 4 个入口与说明文件，共 2909 项 |
| main 内容保留 | 426 个原文件内容及权限未变；9 个预期修改为 8 份当前说明和部署入口，见[preservation.json](preservation.json) |
| 路径适配 | 两个 Python 入口仅改变 `src/` 导入路径，Shell 入口与 hy 字节一致；`src/`、测试、日常配置及旧归档保留，见[path-adaptations.json](path-adaptations.json) |
| 回归测试 | **59 passed，69 subtests passed**，7.92 s；[日志](pytest.txt)、[命令及环境](pytest-run.json) |
| 新入口 | Python 语法、两个 `--help`、依赖导入及 Shell 语法通过，见[命令记录](commands.json)、[环境版本](environment.json) |
| Q3 交付记录复算 | 32 局的完成率、均值、配对差和近似置信区间与原汇总一致，见[independent-record-check.json](independent-record-check.json) |
| 训练状态与源码来源 | [交付摘要](delivery-summary.json)保留 16 路状态；[provenance 核对](provenance-review.json)来自接收前对同一 hy 提交的静态检查，不包含 checkpoint 内部 metadata |

首次在受限沙箱运行时，8 项 HTTP 测试因无法创建本机套接字失败，另有 51 项测试和 69 项子测试通过；[该次日志](pytest-sandbox-attempt.txt)和[命令](pytest-sandbox-attempt.json)保留。允许本机回环套接字后重跑相同测试，全部通过，未修改测试或算法。

验证使用本地现有 Python 3.13 / PyTorch 2.8 CPU 环境。只加载模块和帮助入口，没有加载执行本批权重、重新配对评估、运行训练或进行官方测试；文件校验不证明权重内部信息、部署行为和策略效果已通过验证。

复查从仓库根目录运行 `python -m pytest -q`；入口检查命令见 commands.json。后续 checkpoint 来源核查、性能复跑和官方演练分别新建运行目录，不覆盖这些接收证据。
