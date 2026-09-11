# 实验入口

配置放 `q1/`–`q4/`，运行输出放 `results/`。当前接收的是 hy 的 c457828，训练参数和算法按原状态保留；[已知问题](../docs/notes/接收记录-c457828.md)由 hy 后续修复。

| 配置 | 用途 | 输出 |
| --- | --- | --- |
| `q3/large_20260911/g0.json`–`g3.json` | Q3 四路独立训练，GPU 0–3 | `results/training/large_20260911/q3_gpu*/` |
| `q4/large_20260911/g4.json`–`g7.json` | Q4 四路独立训练，GPU 4–7 | `results/training/large_20260911/q4_gpu*_retry/` |
| `q3/large_20260911/q3ext0.json`–`q3ext3.json` | Q3 续训 | 依赖上述 Q3 输出中的 `latest.pt`，写入 `q3_ext_gpu*/` |
| [research_not_authorized.json](research_not_authorized.json) | 原有阻断示例 | 不是可直接训练的完整配置 |

12 份配置只适配了 `output` 和 `resume` 的目录，其他值与交付一致。[原配置及说明](../results/training/import-c457828/large_20260911/README.md)原样保留。续训权重尚未交付，不能用旧小规模权重冒充对应断点。

安装学习依赖、准备对应 GPU，并为新实验设置独立输出目录后，从仓库根目录运行单路：

```bash
python scripts/start_training.py --config experiments/q3/large_20260911/g0.json
```

`scripts/run_python.sh` 是原训练机的 Python 3.11/CUDA 环境入口；其他环境使用已激活虚拟环境的 `python`。`smoke_training.py` 输出到 `results/training/smoke_20260911/`，启动新一轮前另设目录；不要覆盖已有实验。

当前 Q4 结束与筛选问题未修复，配置的 `max_macros=1000` 仍未传入采样，实际为 400。多路场景种子有重叠，回合数与独立场景数需分别记录。`train_bc.py`、`train_dagger.py`、`train_ppo.py` 的返回状态，及 `run_policy.py`、`export_model.py` 的部署功能仍待完善。

Q1/Q2 人工输入在 [tests/fixtures/solution/](../tests/fixtures/solution/)，命令见根 README。新运行注明源码版本、配置、种子、环境与原始输出；选模验证与独立测试分开记录。
