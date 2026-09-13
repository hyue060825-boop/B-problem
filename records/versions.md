# 版本索引

当前完整交付来源为 `experiment_result@8ef9ef8`，在 main@910df44 上整合。核心算法、main 协议修复和 LIT-Q2-01 保留，最终权重通过冻结运行时部署。见[完整接收记录](acceptance/接收记录-8ef9ef8-完整资产.md)。

| 来源 / 阶段 | main 整合提交 | 主要资产 | 接收与验证 |
| --- | --- | --- | --- |
| 早期本地模拟器与方案 | `4f12388` | `src/bsim/`、题意与总体建模路线 | [验证](../results/validation/integration-20260911-4f12388/README.md) |
| hy `c457828`，含此前几何与策略更新 | `63cf14d` | Q1/Q2、覆盖控制、首批训练及算例 | [接收](acceptance/接收记录-c457828.md) · [验证与映射](../results/validation/integration-c457828/README.md) |
| hy `4d75bee` | `bb5f4d4` | 独立多路训练、续训权重、部署评估入口 | [接收](acceptance/接收记录-4d75bee.md) · [验证与映射](../results/validation/integration-4d75bee/README.md) |
| hy `9e10994` | `0343831` | Q3 旧版 3000 局单策略评估 | [接收](acceptance/接收记录-9e10994.md) · [验证与映射](../results/validation/integration-9e10994/README.md) |
| hy `3ddb2d9`，含 `ffea626`、`0720358` | `4e2cf9f` | Q4 修复、同步 DDP、Q3 搜索、最新四模型配对记录 | [接收](acceptance/接收记录-3ddb2d9.md) · [验证与映射](../results/validation/integration-3ddb2d9/README.md) |

Git 提交保留完整变更历史。旧记录中的缺陷、完成率和“待补充”描述针对当时版本；当前使用方式以 [实现索引](../docs/model/实现索引.md)及[写作交付](../handoff/README.md)为准。

| 后续批次 | 基准 | 内容 | 记录 |
| --- | --- | --- | --- |
| LIT-Q2-01 | a2d1e99；提交见Git历史 | 文献依据、Q2几何候选及实际补测；Q3/Q4仅补方案 | [改进记录](improvements/LIT-Q2-01.md) |

## 2026-09-13 最终论文证据同步

接收固定实验提交 `8ef9ef8`，更新论文及 Overleaf，详见 [接收记录](acceptance/接收记录-8ef9ef8-论文.md)。最终逐局结果和可运行源码、权重固定在 `results/final-8ef9ef8/`，原算法目录及历史结果保留。

## 最终完整资产整合

在论文证据同步基础上补齐所有来源文件、实验档案、父模型和部署包，更新每题交付与复现入口。资产去向见[实际映射](acceptance/experiment_result-8ef9ef8/asset-map-main.json)，本机验证见[整合验证](../results/validation/integration-8ef9ef8/README.md)。本地合并保留 main 与 experiment_result 双亲，未推送远端。

推送前另接收远端 `1e48a64`、`8f0efba`：补齐 Q3 参数继承证据、调整论文最终模型展示范围。合并无冲突，论文与其证据子集以 `8f0efba` 核对，完整实验整合基准仍保留 `910df44`。

上传期间另接收 `725353b` 的 Q1/Q2 论文与实际补测图修订，完整保留论文手提交；当前保护基准相应更新。
