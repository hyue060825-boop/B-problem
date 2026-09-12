# 标准多卡同步训练

`scripts/train_ddp.py` 使用 PyTorch `DistributedDataParallel`。每个进程绑定一张 GPU，持有相同的 `CandidatePolicy` 副本。2026-09-12 修复后的 Q4 使用物理 GPU 4–7；GPU 0–3 留给 Q3。

每轮各 rank 使用不同随机种子采样本地回合；BC、DAgger、PPO 反向传播通过 NCCL 同步梯度。只有 rank 0 写入统一的 `latest.pt`、`best.pt` 和验证结果。各卡执行同样次数的 Adam 更新：较短的数据分片用零权重样本补齐，并按全局真实样本数加权。每阶段/轮次对参数和 Adam 全部状态计算 SHA256，跨卡不一致立即报错。旧版 `DDP.join()` 无法保证 Adam 状态一致，已经移除。

启动本次 Q4（输出目录必须是新的）：

```bash
CUDA_VISIBLE_DEVICES=4,5,6,7 scripts/run_torchrun.sh \
  --standalone --nnodes=1 --nproc-per-node=4 \
  scripts/train_ddp.py --config runs/q4_repaired_20260912/train_config.json
```

本次从头执行 BC 128 局、DAgger 2 × 128 局、PPO 100 × 128 局。episode 配置是全局数量，不是每卡数量。采样由每卡 4 个 CPU worker 完成，梯度更新由 4 张 GPU 同步完成；采样期间 GPU 利用率较低属于当前实现的运行方式。

BC、DAgger 完成率必须达到 100% 才继续；验证集教师和学生均须 100% 完成且学生平均虚拟耗时更低，才可入选 best。训练、验证、测试随机种子分别隔离，详见输出的 `seed_manifest.json`。最终先按验证集冻结模型，再做一次独立 3000 局教师/学生配对测试。旧权重与修复后的控制器组合只能显式作为诊断测评，不能沿用旧报告。运行中禁止修改训练源码，检测到源码摘要变化会停训。

回归命令：`CUDA_VISIBLE_DEVICES='' scripts/run_python.sh -m pytest -q`。`tests/test_ddp_updates.py` 用不等长分片验证各卡 Adam 状态一致，并在双精度下与单进程全局批次更新对照，避免 softmax 公共偏置的单精度舍入被 Adam 放大而干扰算法等价检查。实际 CUDA smoke 使用正常单精度并进行跨卡精确状态摘要检查。

多卡同步训练和此前 `large_20260911` 的独立多路训练是两种不同实验；模型选择应在同步训练完成后用统一独立测试集评估。
