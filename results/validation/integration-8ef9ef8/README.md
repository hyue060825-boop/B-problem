# 最终资产本机整合验证

执行基准 `main@910df44`，来源 `experiment_result@8ef9ef8`。此目录只记录接收与工程验证，不替代最终 3000 场景主结果，也不属于官方成绩。

| 检查 | 结果与证据 |
| --- | --- |
| 完整回归 | 209 通过、2 CUDA 跳过，69 个子测试通过；[JUnit](pytest.xml) |
| 入口导入和参数 | 16 个新分析、报告、训练及证书入口的 `--help` 通过；[记录](entry-help-checks.json) |
| 新配对入口 | Q3/Q4 最终与父模型各 2 局，共 8 局全部完成；[输出](final-pair-smoke/summary.json) |
| 便携包 | 新输出目录打包成功；两题各 13 个参考状态自检通过；[记录](bundle-check.json) |
| 输出保护 | 两题布局报告拒绝在归档目录重生成；[记录](archival-output-guards.json) |
| 资产、原件及链接 | [最终核验](asset-verification.json)核对全部来源映射、模型、运行时、分卷、主结果和当前导航 |
| Git 字节一致性 | [暂存核验](git-index-verification.json)确认接收文件未被行尾转换改变 |

完整回归命令：

```bash
python -m pytest -q
python scripts/evaluate_final_pair.py --output results/validation/integration-8ef9ef8/final-pair-smoke --episodes 2 --workers 1 --q3-seed 1950000000 --q4-seed 1960000000
python scripts/verify_final_assets.py --deep-archives --output .local/verification-new.json
```

上述 smoke 目录现已归档，复跑必须另取输出名。两题各用 1950000000–1950000001、1960000000–1960000001；样本量很小，只验证配套运行代码、权重载入、数据输出和退出，不用于方法比较或选模。

本机 Python 3.13、CPU PyTorch 2.8；无 CUDA。HTTP 与 CPU 多进程测试使用本机临时端口，未连接官方软件；未重跑多 GPU 长训、原生 Windows 或官方隐藏场景。原部署环境为 Python 3.11、CPU PyTorch 2.5.1。
