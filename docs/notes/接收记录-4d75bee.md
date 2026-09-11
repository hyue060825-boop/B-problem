# hy 资产接收记录：4d75bee

按现状接收大规模训练资产及部署、评估入口，沿用 main 的目录。算法与训练缺陷由 hy 后续修复；接收资产不等于策略效果或部署能力已通过验证。

## 来源与整合

- 开发提交：`4d75bee81beaace2092f3812ede68d16d3dee353`；main 基点：`d6c7eb0f2fe0e1059db5c6a1b94d816e18dfc5f0`。
- 相对已接收的 `c457828`，新增 `cdb99b6`（部署与配对评估入口）、`4d75bee`（训练交付）两个提交。共变更 2896 个文件，其中训练资产 2892 个、新权重 38 个。
- `solution/`、`bsim/`、测试没有新增改动；main 原有源码、题面、论文和旧归档保留。本轮仅对两个新 Python 入口适配 `src/` 导入路径，并整理资产与说明。
- 执行前 fetch 发现 hy 又有 `9e10994`；按本轮约定固定接收至 `4d75bee`，该后续提交另行验收。前批历史与误操作说明仍见[c457828 接收记录](接收记录-c457828.md)。

| 内容 | main 中的位置 |
| --- | --- |
| 大规模训练完整快照 | [results/training/import-4d75bee/](../../results/training/import-4d75bee/README.md)，包含 12 份原配置和原 README，共 2905 个原始文件 |
| 权重部署、配对评估与启动包装 | `scripts/run_policy.py`、`scripts/evaluate_checkpoint.py`、`scripts/run_policy_local.sh` |
| 部署与评估用法 | [docs/simulator/local_deployment.md](../simulator/local_deployment.md) |
| 接收证据 | [results/validation/integration-4d75bee/](../../results/validation/integration-4d75bee/README.md) |

## 训练与结果状态

Q3 四路主训练均交付 256 次更新及 COMPLETE，四路续训均到第 512 次更新。Q4 四路初训因教师基线未全部完成而终止；四路 retry 的中途状态为第 154、157、154、157 次更新，尚未交付 COMPLETE。GPU7 retry 缺第 157 份逐更新回合文件，不能将其视为最终完整快照。

Q3 `q3_ext_gpu1/independent_test_32.json` 的 32 局中，教师与模型均完成；模型平均虚拟时间由 3671.736 s 降至 3347.881 s，平均配对差为 -323.856 s，约下降 8.82%。记录的近似 95% 区间为 [-475.560, -172.152] s。逐局值与汇总一致；本轮未复跑评估，尚未核查全部种子重叠或确认所用 checkpoint，结果限于自建研究场景。

四路 Q4 retry 最新交付验证均为第 128 次更新，教师和模型完成率分别为 21.875%、25%、25%、12.5%。GPU6 在完成率仅 25% 时仍有 `selection_pass=true`，不能据此判为可部署。

## 随资产保留的问题

| 项目 | 当前状态与影响 |
| --- | --- |
| Q4 结束、重复 COVER、筛选 | 本轮未改控制器和训练代码，前批问题仍在；未完成任务的时间差不能直接作为任务完成后的效率收益 |
| 宏动作预算与种子 | 训练配置的 `max_macros=1000` 仍未传入采样，实际为 400；多路种子有重叠，回合数不等于独立场景数 |
| 权重与源码追溯 | 新 Q3 续训和 Q4 retry 的独立 provenance 与 hy 当前源码匹配；较早主训练使用历史版本。38 份 checkpoint 内部 metadata 尚未逐一核对，旧小规模记录的源码缺口也未因此解决 |
| HTTP 部署 | 已实现加载权重、选择宏动作并经 RobotClient 请求；尚未端到端验证。剩余现实时间未递减，完整请求/响应未落盘，异常结束处理仍需完善 |
| 其他入口及论文 | 训练 CLI 返回状态、模型导出、Q2 夹具与图件、Q4 网格和论文表述等前批问题继续保留 |

本轮验证范围为原始资产完整性、main 内容保留、路径适配、入口和现有回归，详见[整合验证](../../results/validation/integration-4d75bee/README.md)。性能复跑、权重来源核查和官方演练随后分别留存；论文侧从 [handoff/](../../handoff/README.md) 获取材料，不将工程检查结论写成策略成绩。
