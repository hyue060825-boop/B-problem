# Q3 搜索监督与策略参数继承链

原件来自固定实验提交 8ef9ef8 的 `paper/history/runs/*/readable/`，子目录保留运行标识。本目录新增核验不修改原档案。

1. `q3_joint_20260912` 完成 SFT 第一轮和 DAgger 第二轮；`dagger_round2/status.json` 为 COMPLETE。
2. `ppo_start_selection.json` 明确选择 `sft_round1/checkpoint_0004.pt`。DAgger 四个检查点验证均值 +4.00～+8.19 s，均未通过选模。
3. `frozen_selection.json` 中 PPO 候选 SHA 为 a924b601…，与扩展阶段 `run_manifest.json` 的 baseline_sha256 一致。
4. 扩展阶段 `ppo_initial_selection.json` 与 `ppo_config.json` 均指向 `sft_gpu/checkpoint_0004.pt`；其 PPO/best.pt 为最终 Q3 的直接父模型，最终配置已在上一层 runs 中归档。

因此，最终 Q3 包含 SFT 继承；DAgger 确已运行但该第二轮权重未直接进入已归档最终继承链。不能把“不在在线前向流程执行”误写为“离线训练没有使用”。Q4 的独立父模型链不得无证据套用 Q3 的这一链条。
