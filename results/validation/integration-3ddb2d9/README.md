# 3ddb2d9 整合验证

接收来源：`3ddb2d9e914de17f1d2cce8d8f7cf9f4bd423e45`。原件与本机验证分开存放；此目录不代表官方演练或正式成绩。

| 检查 | 证据与结果 |
| --- | --- |
| 资产与统计 | [asset-check.json](asset-check.json)、[asset-map.csv](asset-map.csv)：373 个接收路径；339 份原件逐字节一致，3277 份 main 原有题面、论文及结果文件保持不变；12000 局记录均值、种子配对和四份权重哈希吻合 |
| 回归 | [pytest.txt](pytest.txt)：184 passed、2 skipped、69 subtests passed；跳过项需要真实 CUDA |
| 目录与权重校验 | [checkpoint-layout-test.txt](checkpoint-layout-test.txt)：新增 1 项测试通过；新旧路径均可加载，缺失、错误或相互矛盾的关键源码哈希仍拒绝 |
| 入口 | [entry-check.json](entry-check.json)：本轮 17 个 Python 入口的语法及 `--help`、1 个 shell 入口的语法检查 |
| 配对入口实跑 | [smoke-paired/summary.json](smoke-paired/summary.json)：四份权重各 2 局，共 8 局均完成；仅作运行验证，不据此判断性能优劣 |
| Q3 HTTP 部署 | [http-q3/summary.json](http-q3/summary.json)：新建自建模拟器回环服务，10/10 个源清除并退出，预算递减 |
| Q4 HTTP 部署 | [http-q4/summary.json](http-q4/summary.json)：新建自建模拟器回环服务，13/13 个源清除并退出，预算递减 |

使用 Python 3.13.13、PyTorch 2.8.0+cpu；OpenMP、OpenBLAS、MKL 线程数均为 1。命令及权重来源见各 JSON；入口运行方式见[部署说明](../../../docs/simulator/local_deployment.md)。HTTP 原始 stdout/stderr 保存在对应目录的 `client.log`；原始交付与本机少量场景的墙钟耗时可能不同。

本次未执行完整训练、真实多卡/CUDA 验证、12000 局重新测评或官方模拟器测试。接收边界见[接收记录](../../../records/acceptance/接收记录-3ddb2d9.md)。
