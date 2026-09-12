# 大规模训练交付：4d75bee

来源为 `hy_branch/b45c0d2@4d75bee81beaace2092f3812ede68d16d3dee353`。`large_20260911/` 保存原分支同名目录的完整快照，共 2905 个文件、38 份权重，其中 2892 个文件是相对前批 `c457828` 的新增交付。

| 目录 | 交付状态 | 权重 |
| --- | --- | --- |
| `q3_gpu0`–`q3_gpu3` | 四路均 COMPLETE，各 256 次 PPO 更新 | 每路 BC、DAgger、best、latest |
| `q3_ext_gpu0`–`q3_ext_gpu3` | 四路均 COMPLETE，续训至第 512 次更新 | GPU0 仅 latest；GPU1–3 各有 best、latest |
| `q4_gpu4`–`q4_gpu7` | 教师基线未全部完成，均以 FATAL 终止 | 无 |
| `q4_gpu4_retry`–`q4_gpu7_retry` | 状态分别为第 154、157、154、157 次更新，目标 256；尚无 COMPLETE | GPU4–6 各有 BC、DAgger、best、latest；GPU7 缺 best |
| `configs/`、`logs/` | 12 份原始配置、16 路启动日志及历史 pid | pid 不代表当前本机进程 |

Q4 GPU7 retry 的状态写第 157 次更新，但逐更新回合文件仅有 156 份；这是中途交付快照。Q3 GPU0 续训未产出新 best，与继承旧最佳评分后未选出新 best 的记录相符，不补造文件。

[Q3 独立测试记录](large_20260911/q3_ext_gpu1/independent_test_32.json)包含 seed=900000–900031 的 32 局：教师与模型均完成，平均虚拟时间分别为 3671.736 s、3347.881 s，平均配对差 -323.856 s，约下降 8.82%。逐局值与汇总已核对；本机复跑、所用权重与种子独立性仍待核查，不能作为官方成绩。

原始配置、provenance、日志、失败与逐局记录、权重保持原字节；内部 `runs/` 路径和原 README 的“尚未上传”是交付原文，不作为当前使用说明。原始文件来源及校验值见[资产映射](../../validation/integration-4d75bee/资产映射.csv)。

日常训练配置放 [experiments/](../../../experiments/README.md)，部署或评估显式指定这里的权重。续训另建配置，从所需 `latest.pt` 读取，输出到新目录，不覆盖归档。前批交付仍保存在 [import-c457828/](../import-c457828/README.md)；遗留问题见[本批接收记录](../../../records/acceptance/接收记录-4d75bee.md)。
