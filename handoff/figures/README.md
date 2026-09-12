# 中文图件

每张图提供 PDF、SVG 和 PNG，配套规格位于 `specs/`。优先取 PDF 插入论文；SVG 可编辑，PNG 用于预览。内部 ID 不等于论文章节图号。

| ID | 主题 | 文件 | 规格 |
| --- | --- | --- | --- |
| F001 | 几何约束下的在线控制 | [PDF](F001-controller-workflow.pdf) · [SVG](F001-controller-workflow.svg) · [PNG](F001-controller-workflow.png) | [规格](specs/F001-controller-workflow.md) |
| F002 | Q1 直径圆反例 | [PDF](F002-q1-diameter-circle.pdf) · [SVG](F002-q1-diameter-circle.svg) · [PNG](F002-q1-diameter-circle.png) | [规格](specs/F002-q1-diameter-circle.md) |
| F003 | Q2 保证接收区域与候选 | [PDF](F003-q2-candidates.pdf) · [SVG](F003-q2-candidates.svg) · [PNG](F003-q2-candidates.png) | [规格](specs/F003-q2-candidates.md) |
| F004 | Q3 七站覆盖 | [PDF](F004-q3-coverage.pdf) · [SVG](F004-q3-coverage.svg) · [PNG](F004-q3-coverage.png) | [规格](specs/F004-q3-coverage.md) |
| F005 | Q4 网格与定向发现 | [PDF](F005-q4-directional-coverage.pdf) · [SVG](F005-q4-directional-coverage.svg) · [PNG](F005-q4-directional-coverage.png) | [规格](specs/F005-q4-directional-coverage.md) |
| F006 | Q3/Q4 每局 T/C 分布 | [PDF](F006-q34-per-source-ecdf.pdf) · [SVG](F006-q34-per-source-ecdf.svg) · [PNG](F006-q34-per-source-ecdf.png) | [规格](specs/F006-q34-per-source-ecdf.md) |
| F007 | 按源数分组的配对差 | [PDF](F007-q34-paired-by-count.pdf) · [SVG](F007-q34-paired-by-count.svg) · [PNG](F007-q34-paired-by-count.png) | [规格](specs/F007-q34-paired-by-count.md) |
| F008 | 训练期间验证变化 | [PDF](F008-q34-validation-progress.pdf) · [SVG](F008-q34-validation-progress.svg) · [PNG](F008-q34-validation-progress.png) | [规格](specs/F008-q34-validation-progress.md) |
| F009 | 训练、选模与配对评估 | [PDF](F009-training-evaluation-workflow.pdf) · [SVG](F009-training-evaluation-workflow.svg) · [PNG](F009-training-evaluation-workflow.png) | [规格](specs/F009-training-evaluation-workflow.md) |

## 图注与引用边界

- **F001**：公开历史更新可行域和频道状态，几何证书约束合法动作，规则或学习调度选择动作并串行执行。当前补测采用侧翼启发式，图中没有接入 Q2 完整选点器。
- **F002**：由合法测向角域构成的等边三角形，直径为 40 m，而最小包围圆半径为 23.094 m；直径圆不能覆盖整个定位区域。数据为人工算例。
- **F003**：人工首次观测下的保证接收内近似与已评估候选点；颜色表示有限情景评分 J，星号表示最佳已评估点。图中没有第二次实际观测后验，也没有对未评估位置插值。
- **F004**：目标圆半径 1800 m，中心与半径 1135 m 六边形顶点共七站，保守接收半径 999.98 m。几何距离上界约 994.81 m；图不表示实际最优路线。
- **F005**：边长 995 m 的网格包含 42 个相交三角形、31 个站点。右侧展示普通非重合位置的闭发射半平面发现依据；重合情形由六个邻点补证。右图为数学示意。
- **F006**：最新 Q3/Q4 各 3000 个配对研究场景的每局 T/C 经验累积分布。四组全部完成；均值降幅约 0.40%、2.75%，不等同于总时间降幅或官方成绩。
- **F007**：按源数 N 分组的新减旧总虚拟耗时差，误差条为配对差均值的近似 95% 区间。分组为探索性分析，没有作多重检验校正。
- **F008**：固定验证集上相对各自对照的总耗时差；圆点是实际验证记录，连线仅辅助阅读，阴影为近似 95% 区间。Q3/Q4 轮次与对照不同；这些记录用于选模，不能称独立测试。
- **F009**：Q3 搜索辅助微调与 Q4 修复后训练分别生成模型，经验证选模与冻结后进行配对评估。虚线官方环节表示当前尚待补充的仓库证据，不表示已经执行。

## 重绘与使用

从仓库根目录运行 `python scripts/build_handoff_assets.py`。数据和绘图脚本只依赖仓库内原件，来源及输出哈希见 [provenance.json](provenance.json)。需要项目基础 Python 依赖、中文字体（文泉驿正黑或 Noto Sans CJK SC）和 `rsvg-convert`（librsvg）；所有输出均已在本机生成。

本批使用用户提供的 `figure-design-skills/scientific-figure-spec`，按七节 FigureSpec 记录科学信息与设计边界，使用原生 SVG 绘制流程图、Matplotlib 绘制数值和几何图。规格结构已检查，导出图已查看；状态为 `RENDERED`，供论文手选择采用，不标为已获最终接受。

当前没有有效数据支持 Q2 实际补测前后图、Q2 参数灵敏度图或官方场景轨迹，因此本批不生成这些图。未来补齐记录后另增图件，不覆盖对应的原始实验数据。
