# Q4 原最佳基线：八卡同步续训一小时

训练目录：`runs/q4_baseline_8gpu_1h_20260913`。

起点为 `runs/q4_legacy_deadline_20260913/best.pt`（SHA256 e8a525f78d176d9073372394b324bd585f4445fbf9cd1515141c483f38d5bd90），已复制到本次运行的 parent/best.pt。使用原始规划和 31 站点退出证书，没有启用 B/C/D 规划干预。

八张 RTX 4090，NCCL DDP 同步更新一套模型和 Adam 状态；几何模拟器与轨迹采样使用 32 个 CPU worker。每轮 256 个随机完整场景，PPO 两个 epoch，全局 minibatch 512，学习率 1e-5。八卡执行 4 轮 smoke（含续训恢复），逐卡参数及 Adam 状态完全一致；教师与基线门槛通过后才开始正式训练。

2026-09-13 10:10:32 +08:00 启动正式训练进程。训练预算为 3600 秒（包含期间验证和保存），预计约 11:11 结束更新；完成当前更新并保存后自动进行配对测试。测试与进程清理另需时间。

训练种子起点 1810000000；验证 1820000000 起共 512 场景；独立测试 1830000000 起共 3000 场景。每 40 轮验证；仅通过完成率、配对收益和延迟门槛的候选保存为本次 best.pt。若没有通过门槛的新 best，最后测试 latest.pt 供诊断，推荐模型仍保留原基线。

运行在 tmux 会话 `q4_baseline_8gpu_1h_20260913`。进程监督记录 supervisor.json，正式训练日志 train.console.log，实时统计 train/status.json 与 train/metrics.jsonl。训练快照 train/latest.pt，验证通过的新最优 train/best.pt（可能不存在），最终配对结果 train/final_test.json。每 5 轮及退出时保存，首轮也保存。原 best 不覆盖。

查看日志：

```bash
tail -f /data5/hy/B-problem/runs/q4_baseline_8gpu_1h_20260913/train.console.log
```

当前文件记录启动配置，不把启动训练写成训练完成；实际状态以 supervisor.json 和 train/status.json 为准。
