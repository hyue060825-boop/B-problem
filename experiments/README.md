# 实验入口

配置放 `q1/`–`q4/`，运行输出放 `results/`。当前接收至 hy 的 `9e10994`，训练参数和算法按原状态保留；[接收状态与已知问题](../docs/notes/接收记录-9e10994.md)持续记录，算法修复由 hy 后续交付。

| 配置 | 用途 | 输出 |
| --- | --- | --- |
| `q3/large_20260911/g0.json`–`g3.json` | Q3 四路独立训练，GPU 0–3 | `results/training/large_20260911/q3_gpu*/` |
| `q4/large_20260911/g4.json`–`g7.json` | Q4 四路独立训练，GPU 4–7 | `results/training/large_20260911/q4_gpu*_retry/` |
| `q3/large_20260911/q3ext0.json`–`q3ext3.json` | Q3 续训 | 依赖上述 Q3 输出中的 `latest.pt`，写入 `q3_ext_gpu*/` |
| [research_not_authorized.json](research_not_authorized.json) | 原有阻断示例 | 不是可直接训练的完整配置 |

12 份日常配置只适配了 `output` 和 `resume` 的目录，其他值与交付一致。[本批训练归档](../results/training/import-4d75bee/README.md)已包含对应大规模权重、原配置和日志；Q3 主训练与续训均已交付 COMPLETE，Q4 retry 尚未完成。

归档权重没有复制到上表的活动输出路径。需要从交付断点续训时，另建实验配置，将 `resume` 指向归档中相应的 `latest.pt`，并为 `output` 设置新目录；不要覆盖原始交付，也不要用旧小规模权重替代对应断点。

安装学习依赖、准备对应 GPU，并为新实验设置独立输出目录后，从仓库根目录运行单路：

```bash
python scripts/start_training.py --config experiments/q3/large_20260911/g0.json
```

`scripts/run_python.sh` 是原训练机的 Python 3.11/CUDA 环境入口；其他环境使用已激活虚拟环境的 `python`。`smoke_training.py` 输出到 `results/training/smoke_20260911/`，启动新一轮前另设目录；不要覆盖已有实验。

当前 Q4 结束与筛选问题未修复，配置的 `max_macros=1000` 仍未传入采样，实际为 400。多路场景种子有重叠，回合数与独立场景数需分别记录。`train_bc.py`、`train_dagger.py`、`train_ppo.py` 的返回状态，以及 `export_model.py` 的导出功能仍待完善。

`evaluate_checkpoint.py` 用于教师与模型配对评估；`evaluate_3000.py` 用于指定权重的 Q3 单策略批量评估，可设置种子、局数和进程数。后者新增结果放 `results/rehearsal/`，已交付的 3000 局原件保留在[论文引用目录](../results/validation/q3-3000-9e10994/README.md)，不要从该目录的原始脚本副本启动新实验。

`run_policy.py` 已提供本机 HTTP 部署入口，改用必填参数 `--checkpoint`，原 `--policy` 参数已移除。三个入口的用法和当前限制见[本机部署与评估](../docs/simulator/local_deployment.md)。

Q1/Q2 人工输入在 [tests/fixtures/solution/](../tests/fixtures/solution/)，命令见根 README。新运行注明源码版本、配置、种子、环境与原始输出；选模验证与独立测试分开记录。
