# 实验结果

- `validation/`：模型算例、工程验证、历史评估证据与接收记录；论文已引用的归档保留原路径。
- `training/`：研究训练的配置、日志、权重和逐局记录；历史交付与新实验分目录保存。
- `rehearsal/`：演练及本地策略评估，每次运行使用独立目录。
- `formal/`：正式测试，每次运行独立归档；保留原始日志及其文件名，不覆盖或删除。
- `figures/`、`tables/`：生成的图表，关联对应运行和生成脚本。

已有记录：[早期模拟器导入](validation/import-b192804/README.md)、[早期整合验证](validation/integration-20260911-4f12388/README.md)、[hy 报告和算例](validation/import-c457828/README.md)、[前批研究训练](training/import-c457828/README.md)、[大规模训练交付](training/import-4d75bee/README.md)、[Q3 四路选模验证](validation/q3-large-4d75bee/summary.json)、[Q3 3000 局评估](validation/q3-3000-9e10994/README.md)、[本次接收验证](validation/integration-9e10994/README.md)。当前已有自建分布研究结果，质量与复现问题见[接收记录](../docs/notes/接收记录-9e10994.md)；尚未交付官方演练或正式成绩。

运行目录可用 `q3-20260911-143000-baseline` 等唯一名称。每次重要运行记录：

- 问题编号、运行类型与时间；正式测试另记案例编码。
- 代码 commit、运行命令、配置与随机种子（适用时）。若代码含未提交改动，额外保存补丁或代码快照，不能仅记旧 commit。
- 原始输出、清除数量、定位清除总时间与程序运行时间；已知目标总数时再计算清除比例，注明指标单位与口径。
- 主要结论、失败原因和待核实事项。记录可用简短 Markdown 或结构化文件，按需要选择。

分析修正另存，保留原始事实。供论文采用的结果及图表在 `handoff/` 中链接到具体版本；交付副本时注明来源。
