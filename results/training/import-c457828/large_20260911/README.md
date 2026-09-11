# 大规模研究训练配置

这些配置用于自建 LOCAL-RESEARCH 分布，不代表官方隐藏测试分布。

- `configs/g0.json` 至 `g3.json`：Q3，GPU 0–3，各 256 次 PPO 更新，每次 64 局。
- `configs/g4.json` 至 `g7.json`：Q4，GPU 4–7，各 256 次 PPO 更新，每次 64 局。
- `configs/q3ext0.json` 至 `q3ext3.json`：从 Q3 第 256 次更新的 checkpoint 续训至第 512 次，每次 128 局。

从仓库根目录启动单路：

```bash
scripts/run_python.sh scripts/start_training.py --config runs/large_20260911/configs/g0.json
```

续训配置依赖服务器上对应的 `q3_gpu*/latest.pt`。本次代码同步包含配置；该目录的大规模训练权重、逐局结果和运行日志仍保留在服务器上，未随本次提交上传。不要向正在运行的同一路输出目录启动第二个写入进程。

## 当前实现限制

Q4 当前允许教师完成率低于 100% 时继续研究训练；这只是放宽启动门槛，不表示控制器已经修复。最近站点重复覆盖可能无法提供新信息，失败回合仍计入失败。已有小样本验证不能证明当前 Q4 的大规模效果。

配置中的 `max_macros` 尚未传入 `run_training` 的各处采样调用，实际采样仍使用 `collect` 的默认值 400；配置值 1000 不代表实际已生效。

训练、验证种子按区间偏移生成，多路之间未保证完全去重，局数不等于独立场景数。独立测试集评估结果应单独记录，不能用训练期间验证替代。

同步前验证：`scripts/run_python.sh -m pytest -q`，49 passed，15 subtests passed。该结果是代码回归检查，不是模型质量验收。
