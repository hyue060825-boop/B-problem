# Q4 优化执行报告（2026-09-12）

本报告按 `Q4优化方案.MD` 的模型阶段、证书阶段顺序记录实际完成项。所有模拟器成绩均来自 `LOCAL-RESEARCH` 研究分布，不能当作官方模拟器成绩。

## 基线与约束

- 分支：`hy_branch/b45c0d2`；执行起点：`c4876b3ffdd2d2dcd172c2547203cc4fa5c00192`。
- 冻结推荐仍是 `runs/q4_budget_20260912/train/best.pt`，SHA256 `2329eb4d12088ebccfdc459939aeb8d5ee67f9696b4b41b1385c3c158d4c0e4a`。
- 该权重是 `normalized-public-v2`，训练时源码与提交 `3ddb2d9` 对应；没有把旧权重套在新特征或新 controller 上。
- Q4 单次 `no_signal` 不会修改安全可行域；只有 31 个证书站完整覆盖或公开 16 源上界逻辑才能退出。训练策略不接收真实 N、源坐标、半径、类型、朝向或 seed。

## 已实现并验证

1. 训练目标统一为每局 `-ΔT/(100*N)`，失败惩罚独立保留；配对选模使用 `T/N`，失败局不因时间较短而获选。
2. Q4 belief 改为公开历史条件化的加权粒子，默认 128 个粒子，提供 valid、ESS、age、degenerate、接收概率、near 概率、方向统计等字段；belief 只用于排序和规划。
3. `StructuralCandidatePolicy` 升级为 candidate-query cross-attention：candidate 对公开 scan mask 的 channel token 做 attention，绑定 station 使用对应 station token，未绑定动作使用 null token，station padding 不进入 critic pooling。
4. LOCALIZE 增加公开 belief 排序的多尺度候选；COVER 对已知频道按 belief 信息量排序；PROBE 保留有限完整 cover，并在连续失败后强制 fallback，防止无进展循环。
5. DDP 保留全局优势统计、等步更新、参数与 Adam 状态摘要审计；validation/test 已改为八个 rank 分片配对评测。
6. GPU 反例入口使用完整 1800m 源域、float64、角间隙判据；独立 CPU `Fraction` 四叉树 witness verifier 可拒绝篡改证书。

专项回归：

```
tests/test_q4_repair.py                  94 passed（完整矩阵；修复前置 mock 后）
tests/test_q4_attention.py               5 passed
tests/test_q4_belief.py                   4 passed
tests/test_q4_exact_certificate.py        6 passed
tests/test_ddp_updates.py                 2 passed（与上述组合运行）
```

最后一组组合运行结果为 `16 passed`；关键专项测试和精确证书测试均通过。运行环境为 Torch 2.5.1+cu124、8×RTX 4090。

## 训练与评估

8 卡 smoke 记录在 `runs/q4_belief_attention_20260912/smoke3_8gpu`：32 局 BC、16 局 DAgger、1 次 PPO，所有 rank 的状态摘要一致；validation 2/8、test 4/8，候选未准入。首次 smoke 的 DAgger 门槛已修正为保留失败轨迹、交给教师重标注，而不是在采样阶段丢弃。

中等训练记录在 `runs/q4_belief_attention_20260912/medium3_8gpu`：

- 128 局 BC 完成率 100%；两轮 DAgger 分别为 67.19% 和 100%，失败轨迹成功被重标注。
- 4 次同步 PPO 更新，每轮 64 局均完成；参数/Adam 摘要每次一致，loss、KL、熵、clip fraction 均有限。
- validation：64/64 完成，学生平均 `T/N=1256.34s/source`，teacher `844.01s/source`；配对差 `+412.33s/source`，近似 95% CI 半宽 `37.63s`。
- 独立 test：128/128 完成，学生平均 `T/N=1227.93s/source`，teacher `822.38s/source`；配对差 `+405.54s/source`，近似 95% CI 半宽 `29.80s`。
- `selection_pass=false`，目录中没有 `best.pt`；原冻结推荐不变。

新增 GPU 搜索 smoke：K=30 候选在独立攻击的首个 250,000 点分块中被确认反例；K=29…23 也均在 200,000 点搜索面板上出现违规。搜索结果只作为经验反例，未被当成连续域证明。

## 31 站连续域证书

`runs/q4_optimization_20260912/layout31_proof.json` 使用有理四叉树、`R_cert=999m` 构造 2224 个叶子（2152 个 witness、72 个 OUTSIDE）及 13 个重合 guard。独立验证命令：

```
scripts/run_python.sh scripts/verify_q4_certificate_exact.py \
  runs/q4_optimization_20260912/layout31_proof.json
```

输出 `PROVED_MATH`，使用 `fractions.Fraction`，不读取搜索器的 claimed PASS。该证明覆盖当前 31 站布局的连续源域和重合 guard 语义；它不证明 31 是理论最小站数，也不证明任意压缩布局安全。当前 K<31 没有已证明布局，正式系统继续保留 31 站回退。

## 复现入口与限制

Q4 v4/v5 配置和脚本位于 `configs/`、`scripts/`；8 卡启动示例：

```
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 scripts/run_python.sh \
  -m torch.distributed.run --standalone --nproc_per_node=8 \
  scripts/train_ddp.py --config configs/q4_belief_attention_8gpu_medium3.json
```

端到端训练的主要瓶颈仍是 CPU reference 环境、路线和 belief 候选构建；PPO 反向本身只占很小部分。GPU 搜索和策略更新已实际使用 CUDA，但不能据 GPU 利用率推断整体环境加速。新 attention 模型当前没有性能收益，不能替换冻结推荐；下一步应在独立开发集优化 probe 长尾和路线成本，再重新进行 validation/test，而不是继续盲目增加 PPO 轮数。
