# LIT-Q2-01：文献启发与 Q2 实验补充

基准：`main@a2d1e99d8a700af3b6a7c918c375a84d8196d942`。本批按审核通过的计划实施，提交历史以Git记录为准。写作交付见[独立说明](../../handoff/shared/文献启发与Q2改进说明.md)。

## 本批变化

- `docs/references/`：两篇ICRA论文的来源、BibTeX、方法对应与适用边界。
- `scripts/experiment_q2_literature.py`、`experiments/q2/`：新增几何候选变体、实际观测与统一后续清除实验。复用src原选点和几何函数，未改动src源码。
- `tests/fixtures/solution/q2_*_lit.json`：新增一致夹具；`tests/solution/test_q2_literature.py`覆盖首测一致性、接收保证、实际计费、固定误差及5/20/1000 m边界。
- `results/validation/LIT-Q2-01/`：32条试运行、480条配对评估、108条参数检查及一致单例。配置在主评估前固定，未按结果删选方法或参数。
- `handoff/`：独立交付说明、4份整理表和F010—F012三张中文图，均绑定原始记录；原始数据保留；旧图表仅刷新生成来源与导出元数据，视觉内容不变。
- `docs/model/总体方案.md` §6.5、§10.7、§15.1及各题handoff：原文就地补充，使用“文献启发补充 · LIT-Q2-01”标记；Q3/Q4明确为待验证接入方案。

原计划中的独立小批敏感性采用等距径向档位，而主实验保留预先定义的非等距5档；文档、表格和F012明确该区别及其12场景分布限制。本批没有根据敏感性结果改变主评估参数。

## 结果与验收

主评估四方法各120/120完成；几何候选较当前Q2平均少5.74 s，但后验半径增加3.68 m。保留原选点器，新变体作为有明确局限的实验资产；Q3/Q4不借用本批收益改写已有成绩。

验证命令与证据：

```bash
python -m pytest tests/solution/test_q2.py tests/solution/test_q2_literature.py -q
python scripts/verify_q2_literature.py
python scripts/build_q2_literature_assets.py
```

数据核验同时检查种子配对、JSON/CSV一致、源码与输出哈希，以独立距离计费、GEOS最小包围圆和枚举直径交叉核对实际指标。图件检查PNG、SVG解析、PDF导出与中文字体；验证摘要见 [LIT-Q2-01-validation.json](LIT-Q2-01-validation.json)。

本次未重训或运行官方测试，paper保持原样。原始题面、src、旧测试、权重及历史实验输出按基准逐字节检查；只更新导航、方案、交付文档和资产清单。新实验与已有Q3/Q4 HTTP部署、3000场景评估分别解释。

## 提交前整理

统一根README的有效Q2算例与两套图表重绘入口；绘图脚本按实际生成文件登记来源，避免跨批次收录。复算核对原8份CSV、网格、SVG和PNG内容不变，新批图表逐字节不变；两份原生流程图PDF仅有导出元数据变化，栅格化内容另行核对。
