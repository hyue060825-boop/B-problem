# Q4 优化审计记录

审计对象是当前工作区，而不是历史截图或历史报告。当前分支为 `hy_branch/b45c0d2`；参考提交为 `c4876b3`，工作区含本轮 Q4 belief、attention、DDP、证书工具和运行产物修改。

调用链核对结果：`TrainingEnv → Controller.legal_actions/execute → ReferenceKernel` 保持四接口和虚拟时钟；actor 只通过 `structural_features → structural_collate → StructuralCandidatePolicy` 接收公开历史。新模型使用 candidate-query channel/station attention 及 relation mask；旧 `normalized-public-v2` checkpoint 不可加载到新 schema。

安全边界：Q4 的单次 `no_signal` 不更新 certified feasible region；belief 只提供候选排序、概率代理和 probe 顺序；`CLEARABLE`、`ABSENT_CERTIFIED`、`EXIT` 仍由确定性几何证书产生。策略输入未包含真实源数量、位置、半径、类型、朝向、场景 seed 或最终清除标签。

基线：冻结推荐 `runs/q4_budget_20260912/train/best.pt`，SHA256 `2329eb4d12088ebccfdc459939aeb8d5ee67f9696b4b41b1385c3c158d4c0e4a`，特征 `normalized-public-v2`，源码与提交 `3ddb2d9` 对齐。新 structural Q4 仅作独立实验，未替换基线。

当前实现状态：目标和配对统计 TESTED；加权 belief/ESS/退化回退 TESTED；candidate cross-attention TESTED；8 卡 DDP 同步与分片 validation TESTED；K=30…23 GPU 搜索有界运行，K=30 被反例击穿；31 站有理四叉树证明 `PROVED_MATH`。连续域证明不表示 31 是理论最小站数。

实际结果：`runs/q4_belief_attention_20260912/medium3_8gpu` 完成 128 局 BC、两轮 DAgger、4 次 PPO；validation 64/64、test 128/128 完成，但学生比 teacher 慢约 412/406 秒每源，`selection_pass=false`。因此当前推荐仍是旧 31 站冻结系统。

主要未完成项：Q4 belief 的 GPU 常驻批量服务、跨环境合并 rollout、完整观测分支 EIG 和 K<31 可证明布局均未达到正式交付标准；这些状态保持 UNKNOWN/NOT_RUN，不以随机采样替代证明，也不启动无界长训。
