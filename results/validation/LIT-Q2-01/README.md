# LIT-Q2-01：Q2 实际补测实验

本批在 `main@a2d1e99` 基础上增加独立实验实现。Q3/Q4源码、权重与旧原始数据未改变。本地单源物理实验不代表官方演练或正式测试。

| 目录 | 内容 |
| --- | --- |
| [pilot](pilot/) | 8场景×4方法；检查阶段 |
| [evaluation](evaluation/) | 冻结参数的120场景×4方法，480条运行记录 |
| [sensitivity](sensitivity/) | 12个不同场景×9参数配置，108条运行记录 |
| [consistent-example](consistent-example/) | 首测1.91°与源(900,30)一致，原Q2入口产生的实际后验 |

前三批各保存 `cases.json`、`config.json`、`manifest.json`、`records.json`、`samples.csv`、`summary.json` 与 `outputs.sha256.json`。`records.json` 含初始/后验凸包、选点评分及逐步请求位置、返回观测和动作费用；真正可行集面积另见 `posterior_area_m2`。凸包图不保留集合中的孔。

`manifest.json` 绑定实际执行脚本及src文件SHA-256，`base_commit`是实验开始时的仓库提交，新增脚本以哈希为准。随机种子和生成器均在源码内可追溯。数据原件只读，复跑另建目录；[实验协议](../../../experiments/q2/README.md)、[结果交付](../../../handoff/shared/文献启发与Q2改进说明.md)、[整理表格](../../../handoff/tables/LIT-Q2-01/README.md)分别提供运行、解释和引用入口。
