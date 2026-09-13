# Q3 / Q4 旧最佳模型四卡微调（2026-09-13）

两任务分别使用 GPU 0–3 和 4–7，四 rank 同步优化各自一个模型。旧运行源码全部与父 checkpoint provenance 匹配，保留 normalized-public-v2 的 11 维候选特征。Q4 旧最佳是 CandidatePolicy，不是 StructuralCandidatePolicy；此前对话中的结构化续训说明有误。

Q3 父 update=1599，Q4 父 update=3499。恢复 Adam 状态，但明确用新采样随机流启动四卡子谱系；不声称与原八卡运行逐位相同。Q3 lr=5e-6，Q4 lr=1e-5。每轮全局 128 场景，每卡 32；每卡 minibatch 64，无梯度累积，PPO epochs=2。运行源码及旧 reward 保持一致，本轮只改变微调学习率与资源分片，验证选模改用配对 T/N。

Q3 启动前的当前工作区加载尝试失败，没有有效续训结果。最终改用 /tmp/B-problem-q3legacy、train_deadline_ddp.py，严格通过旧 runtime 哈希校验。Q3 约 01:03 启动，因此实际剩余训练窗口约六小时，不是六个半小时。

Q4 smoke 完成 2×16 场景，同步和 Adam 检查通过。独立 64 局开发配对完成均为 64/64，旧模型 815.536，新模型 818.477 秒/源，差 +2.941，95% CI 半宽 6.080。无明确提升证据；正式实验从原冻结 best 开始，smoke 权重不替代父模型。

## 停止与产物

每轮原子保存 latest，验证集优于父模型才保存 best。07:00 停止启动新轮；每个任务独立 supervisor 在 07:08 TERM，仅针对自己创建的进程组，07:09 KILL 兜底。最终 3000 配对终测未安排自动运行，避免越过用户截止时间。原生产推荐不覆盖。

日志位于 runs/q3_legacy_deadline_20260913 和 runs/q4_legacy_deadline_20260913；tmux 会话 q3_deadline_4gpu、q4_deadline_4gpu。supervisor.json 保存自己的 PID、命令与 deadline。配置位于 configs/q3_legacy_deadline_4gpu.json 与 configs/q4_legacy_deadline_4gpu.json。

启动入口（截止后拒绝运行）：

    python scripts/run_until_deadline.py --problem 3
    python scripts/run_until_deadline.py --problem 4

本轮参数更新在 CUDA；rollout 使用旧 CPU reference 和 worker 池，不将 GPU 使用描述为全流程 GPU 模拟。
