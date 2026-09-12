# 版本索引

当前算法基准为 `main@4e2cf9f`，已接收 hy 至 `3ddb2d9`。a2d1e99完成资产整理；LIT-Q2-01在其基础上新增独立Q2实验，src算法和历史数据不变。

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
