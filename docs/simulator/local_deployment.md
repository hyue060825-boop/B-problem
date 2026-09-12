# 本机部署与评估

从仓库根目录、已安装 `.[rl,test]` 的 Python 环境执行。当前接收至 `3ddb2d9`；四份评估权重已在本机加载并各完成 2 局，Q3/Q4 各通过一次自建 HTTP 部署。完整状态见[接收记录](../notes/接收记录-3ddb2d9.md)。这些验证不调用官方软件。

## 最新 Q3/Q4 配对评估

入口固定比较本批四份权重：Q3 PPO 候选与冻结原模型、Q4 五小时训练 best 与训练前模型。先做少量场景检查，输出目录必须不存在：

```bash
python scripts/evaluate_latest_pair.py \
  --episodes 2 --workers 2 \
  --output results/rehearsal/q34-paired-01
```

完整复跑用 `--episodes 3000`，按机器资源设置 `--workers`；默认 Q3/Q4 种子分别从 310000000、320000000 开始，与[本批报告](../../results/training/import-3ddb2d9/runs/q34_3000_test_20260912/report.md)一致。改进策略后应另选未使用的测试集，不能反复用原测试集选模。

需要将单个模型与规则教师配对比较时：

```bash
python scripts/evaluate_checkpoint.py \
  --problem 3 \
  --checkpoint results/training/import-3ddb2d9/runs/q3_joint_20260912/ppo_candidate.pt \
  --seed 330000000 --episodes 32 \
  --output results/rehearsal/q3-teacher-paired-01.json
```

确认输出父目录存在。该入口的对照是规则教师，与最新四模型报告中的“冻结原模型”不同，分别引用。

## 本机 HTTP 部署

先在模拟器准备对应会话，再填写实际队号、问题与监听端口。以下端口仅为示例：

```bash
python scripts/run_policy.py \
  --problem 3 \
  --checkpoint results/training/import-3ddb2d9/runs/q3_joint_20260912/ppo_candidate.pt \
  --base-url http://127.0.0.1:2026 \
  --robot-id YOUR_ROBOT_ID
```

Q4 改为 `--problem 4`，权重使用 `results/training/import-3ddb2d9/runs/q4_budget_20260912/train/best.pt`。Q3 候选尚不替代此前稳健选模推荐；冻结原模型为同一 Q3 目录中的 `baseline.pt`。先用官方演练核对效果，再决定正式策略。

`run_policy.py` 使用公开观测，不读取隐藏真值；只连接本机回环 HTTP，`--device` 默认 `cpu`。进入后按单调时钟更新现实预算，加载时检查问题、特征、研究 profile 和关键源码。完整请求/响应尚未持久化，标准输出为进入、宏动作及退出摘要；异常处理仍需完善。

独立检查 Q3 的自建 HTTP 闭环可运行以下命令，它会新建临时端口，不连接现有服务：

```bash
python scripts/check_q3_local_http.py \
  --checkpoint results/training/import-3ddb2d9/runs/q3_joint_20260912/ppo_candidate.pt \
  --output results/rehearsal/q3-http-01
```

该检查使用当前 Python 启动部署子进程。训练机的 `run_python.sh`、`run_policy_local.sh` 依赖其 `.venv` 和 CUDA 库路径，其他环境使用上面的 `python` 入口。

## 历史权重与结果

`evaluate_3000.py` 支持 `--problem 3/4` 的单策略批量评估，但仍仅检查特征版本，不校验完整源码、profile 或问题编号；当前优先使用上述配对入口。旧批次结果按原源码、权重和实验口径保留，不据此推断修复后的表现。

main 的源码哈希校验同时识别旧 `solution/`、`bsim/` 和新 `src/` 路径；目录搬迁不放宽文件内容检查。旧权重若与当前关键代码不符，会被正常拒绝。确需研究旧权重接新控制器的行为时，`evaluate_checkpoint.py --allow-code-mismatch` 仅用于显式诊断，并另存结果；部署不提供静默绕过。

`mean_i(T_i/C_i)` 是每局总虚拟时间先除以清除数再平均，`sum(T_i)/sum(C_i)` 是按清除数加权，两者不能混用。先报告完成率，再比较耗时；研究分布、官方演练与正式成绩分别记录。
