# 标准多卡同步训练

`scripts/train_ddp.py` 使用 PyTorch `DistributedDataParallel`。一次训练运行由 `torchrun --nproc-per-node=8` 启动 8 个进程，每个进程绑定一张 GPU，持有相同的 `CandidatePolicy` 副本。

每轮各 rank 使用不同随机种子采样本地回合；BC/PPO 反向传播通过 NCCL 同步梯度，更新后 8 个副本参数一致。只有 rank 0 写入统一的 `latest.pt`、`best.pt` 和验证结果。`DDP.join()` 处理随机场景导致的局部 batch 数差异。

启动 Q3：

```bash
scripts/run_torchrun.sh --standalone --nnodes=1 --nproc-per-node=8 \
  scripts/train_ddp.py --config runs/ddp_20260911/q3_config.json
```

Q4 使用 `runs/ddp_20260911/q4_config.json`，应在 Q3 运行结束后启动，或使用另一台完整的 8 卡节点。Q3 和 Q4 不能在同一组 GPU 上同时运行，否则会互相争抢显存和计算资源。

多卡同步训练和此前 `large_20260911` 的独立多路训练是两种不同实验；模型选择应在同步训练完成后用统一独立测试集评估。
