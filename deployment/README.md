# 最终模型部署

模型身份以 [完整清单](../records/inventory/models-final-20260913.json) 的 SHA-256 为准：

| 模型 | 仓库内权重 | 前缀 |
| --- | --- | --- |
| Q3 最终 | [best.pt](../results/final-20260913/q3_legacy_deadline_20260913/best.pt) | 51397bc8 |
| Q4 最终 | [best.pt](../results/final-20260913/q4_baseline_8gpu_1h_20260913/train/best.pt) | c8812ced |

`runtime_public_v2/` 保存与权重匹配的 44 个源码文件；`inference_fixtures.json` 提供两题各 13 个参考观测。`scripts/run_policy.py` 先校验代码、题号和特征，再载入模型。

在仓库根目录按 [README](../README.md) 安装后，先运行两题离线自检：

```bash
python scripts/run_policy.py --problem 3 --checkpoint results/final-20260913/q3_legacy_deadline_20260913/best.pt --robot-id LOCAL-CHECK --check-only
python scripts/run_policy.py --problem 4 --checkpoint results/final-20260913/q4_baseline_8gpu_1h_20260913/train/best.pt --robot-id LOCAL-CHECK --check-only
```

实际连接时去掉 `--check-only`，将 `--robot-id` 改为模拟器当前队号；默认地址 `http://127.0.0.1:2026`。每次日志另存于 `results/rehearsal/policy-logs/`，可用 `--log-dir` 指定新位置。只有明确选定并启动测试后才运行连接命令。

Windows 便携运行使用 [原始 ZIP](bundles/B-problem-paper-final.zip)，解压到独立新目录；包内 `models/q3_best.pt`、`models/q4_best.pt` 与上述权重相同。安装及操作见 [原部署说明](README_WINDOWS.md)。ZIP 与冻结代码保留交付时字节，不能只换一个 pt 文件。

另行导出本次适配入口的便携包：

```bash
python scripts/build_windows_policy_bundle.py --output .local/exports/final-policy-new
```

输出目录及同名 ZIP 必须不存在。前期研究模型的原 main 启动方式保留为 `scripts/run_policy_research.py`；最终模型使用本页入口。新配对评测、训练复现和证书验证见[复现说明](../docs/simulator/最终模型复现.md)。
