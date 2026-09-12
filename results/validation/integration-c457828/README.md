# c457828 接收与目录整合验证

来源为 `hy_branch/b45c0d2@c457828`，main 基点为 `b4e307f`。本次按现状接收，算法与训练缺陷留待 hy 修复；分工、误入 main 的提交及遗留问题见[接收记录](../../../records/acceptance/接收记录-c457828.md)。

## 检查结果

| 检查 | 结果与证据 |
| --- | --- |
| 来源与迁移 | 315 个来源文件全部有去向，286 个内容一致；[资产映射](资产映射.csv)逐项记录 Git blob |
| 原件及队友改动 | 225 个来源原始资产、85 个 main 保护文件内容未变，见[preservation.json](preservation.json) |
| 实现边界 | 9 个源码文件只有预期路径适配；12 份日常配置只改变 output/resume 路径，见[path-adaptations.json](path-adaptations.json) |
| 安装与导入 | src 布局可编辑安装成功，bsim、solution 均从当前仓库 src 导入，见[环境记录](environment.json) |
| 全量回归 | **59 passed，69 subtests passed**，9.08 s；[日志](pytest.txt)、[命令](pytest-run.json) |
| 命令行入口 | Q1/Q2 算例、Q3/Q4 覆盖检查、题面校验、训练帮助入口通过，见[commands.json](commands.json) |
| 算例数值 | Q1 输出与原记录一致，Q2 最佳评分差约 9.89e-12，见[numeric-comparison.json](numeric-comparison.json) |

测试包含 main 原有模拟器回归和 hy 算法测试；没有通过修改断言或算法来消除已知问题。安装验证复用本地验收依赖，未启动 GPU 训练、官方演练或正式测试。

## 数据入口

- [q1/](q1/)、[q2/](q2/)：新目录下重新执行人工算例的输出，provenance 使用当前 src 路径。
- [coverage-q3-stdout.txt](coverage-q3-stdout.txt)、[coverage-q4-stdout.txt](coverage-q4-stdout.txt)：覆盖入口输出。
- [review/](review/)：此前对原 c457828 的 49 项回归、Q4 结束检查、旧权重配对评估与配置检查，原样保留；不与上面的整合后回归混计。
- [历史报告和图件](../import-c457828/README.md)、[历史训练](../../training/import-c457828/README.md)：hy 原始交付。

常规复查从仓库根目录执行 `python -m pytest -q`；其他本次命令见 commands.json。历史检查针对记录中的固定提交，后续更新另建验证目录，避免覆盖证据。
