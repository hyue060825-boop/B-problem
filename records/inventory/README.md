# 资产清点

清点范围为 `paper/` 之外的仓库工作资产，不扫描虚拟环境、忽略文件或权重内部张量。这里保存路径与来源；用于写作的整理表格在 [handoff/tables/](../../handoff/tables/README.md)。

| 文件 | 用途 |
| --- | --- |
| [datasets.csv](datasets.csv) | 按问题和实验目的整理的主要数据批次，含用途与限制 |
| [files.csv](files.csv) | 文件路径、类别、大小、SHA-256；排除清单自身，避免循环校验 |
| [checkpoints.csv](checkpoints.csv) | 全部 58 份权重的路径、哈希和使用角色；明确最新四份配对权重 |
| [figures.csv](figures.csv) | 历史结果图与本批中文图件，保留各自版本 |
| [summary.json](summary.json) | 按目录汇总的数量和体积 |

从仓库根目录运行 `python scripts/inventory_assets.py` 更新工作区清单。清单包含尚未提交的整理成果，以每个文件的哈希记录实际内容；提交后可按需要再次刷新。

数据目录中的历史 `pid`、日志与失败快照只作来源记录，不代表当前本机运行状态。不同权重、验证集、独立评估与官方测试分别解释，不能因文件都在 `results/` 中就合并统计。
