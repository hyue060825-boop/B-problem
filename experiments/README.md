# 实验入口

配置放 `q1/`–`q4/`，输出放 `results/`。当前接收至 hy 的 `3ddb2d9`，包含 Q4 控制及同步 DDP 修复；[接收记录](../records/acceptance/接收记录-3ddb2d9.md)区分当前实现、交付记录与本机验证。

| 配置 | 用途 | 默认新输出 |
| --- | --- | --- |
| [q3/joint_20260912.json](q3/joint_20260912.json) | Q3 搜索标签、四卡 SFT/DAgger/PPO | `results/training/q3_joint_new/` |
| [q4/repaired_20260912.json](q4/repaired_20260912.json) | 修复后从头 BC/DAgger/PPO，同步 DDP | `results/training/q4_repaired_new/` |
| [q4/budget_20260912.json](q4/budget_20260912.json) | 从已交付 Q4 权重开始，按现实时间预算微调 | `results/training/q4_budget_new/` |
| `q3/large_20260911/`、`q4/large_20260911/` | 旧独立多路训练及续训 | 原活动输出；运行前另设目录 |
| [research_not_authorized.json](research_not_authorized.json) | 原有阻断示例 | 不是完整训练配置 |

前三份配置只调整输出及 checkpoint 路径，原参数快照保存在[本批交付](../results/training/import-3ddb2d9/README.md)。每轮另设输出目录，不能指向归档；种子区间和选模集、测试集的独立性由具体实验核对。

在具备 CUDA、NCCL 的训练环境中，从已激活虚拟环境运行 Q4（GPU 编号按实际分配设置）：

```bash
CUDA_VISIBLE_DEVICES=4,5,6,7 python -m torch.distributed.run \
  --standalone --nnodes=1 --nproc-per-node=4 \
  scripts/train_ddp.py --config experiments/q4/repaired_20260912.json
```

预算微调将脚本换成 `scripts/train_budget_ddp.py`，配置换成 `experiments/q4/budget_20260912.json`。同步机制见[多卡说明](../docs/simulator/ddp_training.md)。旧 `large_20260911` 是独立多路训练，不与同一个模型的同步 DDP 混称。

Q3 先用 `python scripts/prepare_q3_joint.py --output results/training/q3_joint_new` 准备基线、种子清单和配置，再用 `generate_q3_labels.py` 生成标签、`train_q3_joint.py` 执行各阶段。准备脚本使用已交付 GPU2 原权重，扫描 `results/` 中历史种子；还会生成 `experiments/q3/joint-generated.json`。完整标签和部分中间权重尚未交付，不能直接照抄原报告中的服务器续训命令；原流程见[Q3 实验报告](../results/training/import-3ddb2d9/reports/Q3搜索教师与专家迭代实验报告.MD)。准备步骤需要训练机的 `nvidia-smi`。

训练入口使用严格源码校验；旧权重与当前控制器不符时，不直接续训。`q4_preflight.py` 的历史权重诊断还缺少旧 DDP checkpoint，当前不能完整复跑。单路 `start_training.py`、`train_bc.py`、`train_dagger.py`、`train_ppo.py` 继续保留，具体阶段行为按实现确认；`export_model.py` 仍待完善。

新模型评估、原模型配对和 HTTP 部署命令见[本机部署与评估](../docs/simulator/local_deployment.md)。Q1/Q2 人工输入在 [tests/fixtures/solution/](../tests/fixtures/solution/)。记录源码版本、配置、种子、依赖和原始输出，选模验证与独立测试分开解释。
