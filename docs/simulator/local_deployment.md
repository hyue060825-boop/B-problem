# 本机部署与评估

训练机提供 checkpoint，策略程序在测试电脑运行，经本机回环地址调用模拟器接口。`run_policy.py` 使用公开观测构造特征，不读取场景文件或隐藏真值；独立研究评估则由本地环境生成场景。

从仓库根目录、已安装 `.[rl]` 的 Python 环境执行。当前已接收部署代码、权重及研究评估入口，HTTP 部署尚待端到端验证；完整状态见[接收记录](../notes/接收记录-9e10994.md)。

## 研究场景配对评估

示例使用本批 Q3 续训权重，默认以 4 个进程在 CPU 上评估，不连接官方软件：

```bash
python scripts/evaluate_checkpoint.py \
  --problem 3 \
  --checkpoint results/training/import-4d75bee/large_20260911/q3_ext_gpu1/best.pt \
  --seed 900000 --episodes 32 \
  --output results/rehearsal/q3-4d75bee-eval-01.json
```

每次更换输出文件名；自定义父目录须先创建。指定新的种子范围不会自动证明它与训练、选模数据独立，使用前需核查重叠。归档中的 32 局评估是交付记录，尚未在本机复跑，也尚未确认对应 checkpoint 的内部信息。

## Q3 单策略批量评估

`evaluate_3000.py` 固定评估 Q3，不运行教师基线。以下示例对应本批 GPU2 续训权重；每次另取输出目录，避免覆盖旧结果：

```bash
python scripts/evaluate_3000.py \
  --checkpoint results/training/import-4d75bee/large_20260911/q3_ext_gpu2/best.pt \
  --episodes 3000 --seed 1200000 --workers 8 \
  --output results/rehearsal/q3-3000-eval-01
```

新输出包括逐局 JSON、汇总 JSON 和直方图。`mean_of_sample_per_source_times_s` 是各局 `T/C` 的算术平均；`source_weighted_mean_time_s` 是所有局总时间除以总清除数，两者分别报告。若有未完成局，须先报告完成率，不能只比较每源时间。

已交付的 [3000 局原件](../../results/validation/q3-3000-9e10994/README.md)为论文引用快照，包含未适配目录的原脚本副本；新实验使用上面的 `scripts/` 入口。该批与前述 GPU1 的 32 局配对测试使用不同权重，不合并解释为同一模型的性能提升。

## 本机 HTTP 部署

先在模拟器中准备相应会话，确认问题、监听端口与队号，再运行策略。以下以官方软件默认端口为例，将 `YOUR_ROBOT_ID` 替换为实际队号：

```bash
python scripts/run_policy.py \
  --problem 3 \
  --checkpoint results/training/import-4d75bee/large_20260911/q3_ext_gpu1/best.pt \
  --base-url http://127.0.0.1:2026 \
  --robot-id YOUR_ROBOT_ID
```

自建调试服务的端口按实际启动参数填写，例如 `20260`。程序不启动官方软件，只允许 `http://127.0.0.1:端口` 形式的回环地址；`--device` 默认为 `cpu`，可按环境选择 CUDA。必填参数为 `--checkpoint`，旧 `--policy` 参数已移除。

`scripts/run_policy_local.sh` 转调原训练机的 `run_python.sh`，依赖其 Python/CUDA 路径。其他机器使用上面的已激活环境入口。Q4 指定对应权重和 `--problem 4`；目前 retry 尚未交付完成记录，待修复并通过研究评估、官方演练后再用于正式测试。

## 当前边界

- 部署入口校验特征版本、研究 profile 和问题编号，但尚未验证这批权重的完整部署过程。`export_model.py` 仍待完善。
- Q3 批量评估入口目前仅检查 checkpoint 特征版本，尚未检查其问题编号和研究 profile；使用与 Q3 配置一致的权重，补强校验由 hy 后续处理。
- 剩余现实时间仅在进入会话时赋值，尚未随运行递减；宏动作预算耗尽、业务拒绝等异常处理仍需完善。
- 标准输出记录进入、宏动作和退出摘要，没有持久化完整请求/响应。退出后不要再次调用 `/exit` 查询原因。
- 研究 checkpoint 和本地评估不证明官方隐藏分布上的效果。正式测试前仍需先完成本地与官方演练验证。
