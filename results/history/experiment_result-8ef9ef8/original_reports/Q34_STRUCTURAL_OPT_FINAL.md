# Q3/Q4 Structural Optimization Final Status

This is an interim engineering status for 2026-09-12. The structural controller and public-information feature changes are implemented and regression tested. The required long four-GPU v3 training and isolated 3000-scenario paired comparison have not yet completed, so no new checkpoint is recommended.

Frozen recommendations remain:

- Q3: `runs/q34_structural_20260912/baselines/q3_best_v2.pt` (SHA256 `8cc3a1621334640e6010d8d8fc2cc91a7d47a879573bd54b55fa45a990a56e71`).
- Q4: `runs/q34_structural_20260912/baselines/q4_best_v2.pt` (SHA256 `2329eb4d12088ebccfdc459939aeb8d5ee67f9696b4b41b1385c3c158d4c0e4a`).

Safety boundaries are preserved: Q4 single no-signal does not exclude a disk, incomplete coverage cannot certify absence, and certified clear failures terminate the episode. The cumulative directional certificate remains research-only and disconnected. All reported simulator results are LOCAL-RESEARCH diagnostics, not official simulator scores.

## 2026-09-12 结构化 DDP 复验

- Q3 四卡结构 smoke：`runs/q34_structural_20260912/q3/ddp_structural_smoke`，world_size=4，参数与 Adam 状态同步通过，BC/验证/测试完成率均为 1.0；验证 paired delta +693.66 s，未生成 best，不能替代冻结基线。
- Q4 首次四卡 smoke 因 `max_macros=80` 导致 1/4 教师回合预算耗尽；提高到 160 后 BC 完成率 4/4，但 rollout 在验证前已运行约 9 分钟且 GPU 利用率接近 0，已停止。该结果属于性能瓶颈记录，不是数值崩溃。
- 结构化入口现已真正使用 `StructuralCandidatePolicy`、v3 structural features、显式 channel/station gather 与 scan mask，并在 checkpoint 中记录 structural feature version。
- 在完成 GPU 搜索/rollout 加速前，不启动长时间 Q3/Q4 正式训练，也不把上述 smoke checkpoint 选为 best。
