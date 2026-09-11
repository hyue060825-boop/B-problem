# 本地模拟器交付验收报告

本阶段已在现有 `B-problem` 仓库完成可运行的独立LOCAL模拟器，未等待最终求解算法。规则、场景、误差、策略和评价分别成模块；策略仅经四类动作与公开响应交互。**公开规则的已测范围通过，完整官方复刻仍受G01—G09阻断。** 未登录官方软件、未启动演练或正式测试、未进行模型训练。

验证日期：2026-09-11。源码环境：macOS 26.4 arm64、Python 3.9.6、10个逻辑CPU。运行和测试仅依赖Python标准库；读取官方PDF使用的临时阅读工具不属于项目运行依赖。官方源文件清单及哈希在 `rules/source_manifest.json`，实测核对在 `docs/source_audit.json`。

## 验收状态

| 范围 | 状态 | 实际证据 | 结论限制 |
| --- | --- | --- | --- |
| 官方材料完整读取与哈希 | PASS | 三份原文件SHA256均匹配；Word表格和公式已读取；source_audit.json | 搭建提示词属于开发任务说明，不当作官方物理证据 |
| 源格式、公开数量/类型/位置/频道约束 | PASS | Physics.test_scenario_constraints | 不是官方生成器，场景联合分布BLOCKED |
| 全向/定向普通点接收、near/no_signal/direction | PASS | Physics中的阈值、方向和轴向边界夹具 | 非轴向浮点临界点及重合官方语义仍BLOCKED |
| ≤20米清除、背面清除、重复清除、清除后无信号 | PASS | Physics.test_direction_and_clear | 在所列精确/邻域夹具范围内 |
| 官方整数时间示例 | PASS | timing_replay.json：0、105、111、194、199、199秒 | 示例依据附件2 §10；零误差/单源不是官方生成事实 |
| 常用请求校验、四接口响应、拒绝不变状态 | PASS | Protocol/Http测试；400/404/405/409/413/415和200 false | 异常HTTP解析、复合错误优先级尚无官方实测 |
| 幂等原响应重放、原ID重试、并发拒绝 | PASS | 时间戳保持、同动作只计费一次、并发409、丢响应重试夹具 | 原字节比较/同ID合并/业务拒绝ID占用属于LOCAL约定G07 |
| 429容量保护及内部错误500原子性 | PASS | 管理端注入容量阈值、G06未定义动作500且无状态提交 | 仅TEST故障注入，不知道官方容量/保护阈值 |
| 现实窗口、晚enter、截止后不执行、登记动作可完成 | PASS | 注入时钟夹具；未完整请求跨现实截止的HTTP夹具 | 不实际等待20/25分钟；准确时钟取样及边缘舍入未官方对照 |
| 虚拟跨限时、手工中止、exit计时 | PASS | 359999→360004秒动作完成后终止；abort/exit测试 | 关闭时缓存投递关系G08仍未决 |
| 独立进程HTTP及监听生命周期 | PASS | CLI.test_separate_server_and_socket_lifecycle：真实5秒倒计时，六步HTTP，exit关闭端口 | 仅本机Python服务，不是官方软件 |
| 固定误差场接口、数值量化配置、误差表重放 | PASS | ±1/0、换频道离开再回、查询顺序、舍入临界和不同TEST舍入模式 | 仅显式TEST常值/表，官方G02—G05未解决 |
| 参考内核与CPU快速内核等价 | PASS | kernel_comparison.json：10000步、48个边界、0差异；另有5000步回归 | 场景为有限TEST输入；共享误差/角度/计时策略的一致性不是官方证据 |
| 批量会话、参考会话及HTTP语义 | PASS | Equivalence.test_batch_reference_and_fast_session、Http.test_http_reference_exact_and_closed逐步响应和状态相等 | CPU批处理，无CUDA实现；无大规模训练 |
| 重放、差异与公开轨迹核对工具 | PASS | 确定夹具逐步重放、扰动差异检出、trace_audit.json | 未在官方采集轨迹上运行；无法推断隐藏随机过程 |
| actor输入字段及不同真值相同历史 | PASS | 字段白名单、禁用额外真值字段、同公开响应相同输入、独立进程HTTP | 无OS沙箱；不能声称防御恶意同用户进程读取文件 |
| CPU有限夹具性能测量 | PASS | benchmark_cpu.json，64环境×128步 | 仅物理步，不是端到端训练吞吐 |
| 官方软件逐行为实测 | NOT_RUN | 0局、0请求 | 本阶段没有自动启动任何官方运行 |
| CUDA/八卡服务器/Windows部署 | NOT_RUN | 未连接GPU服务器；CUDA后端未实现，命令明确退出2 | 未声称GPU加速、跨平台实测或服务器吞吐 |
| 官方完整随机生成器及误差场 | BLOCKED | OfficialGenerator/OfficialError失败接口及G01—G03报告 | 不能声称官方同分布 |
| 官方角度、微秒及重合细节 | BLOCKED | 必填TEST数值配置，strict启动明确拒绝 | G04—G06待官方依据 |
| 官方完整异常协议和结束投递 | BLOCKED | G07—G08文档，常用路径已实现 | 无完整协议测试套件 |
| 官方身份、编码、加密日志和成绩上传 | BLOCKED | G09；LOCAL标签和明文记录 | 不实现官方成绩系统替代 |
| 满足当前官方一致性要求的大规模训练 | BLOCKED | strict_official退出2，无静默回退 | 同时遵守本阶段不训练的明确范围 |

## 可复现结果

`python3 -m bsim validate-fixtures --profile fixture_conformance`：26个测试方法通过，原始输出保存在 `docs/test_results.txt`。每个方法可能包含多个边界子案例。它们包括已知规则断言和自定夹具约定的断言，不能把26个测试通过解释为G01—G09通过。当前执行的断言无FAIL；未测试/被阻断范围如上表分别列明。

独立命令 `compare-kernels --steps 10000`：10000步动作以及48个阈值相邻浮点对比均无差异。使用的确定性测试种子只是可复现测试输入，不能对应官方案例编号。所有大规模训练入口仍未启用。

本机一次短时CPU测量（64环境、每环境128步，共8192次物理转移）：

| 内核 | 总耗时 | 物理转移/秒 |
| --- | ---: | ---: |
| ReferenceKernel | 0.133172秒 | 61514 |
| FastKernel | 0.068093秒 | 120305 |

这是单源夹具、单进程CPU循环，不含HTTP、策略搜索、信念更新、网络传输和训练。快速路径保留高精度移动计时并对距离边界回退；本次约1.96倍结果不代表所有场景的稳定加速。没有测试GPU，未承诺八卡训练吞吐。

## 交付清单与替换方式

- 源码：`bsim/`，包含参考/快速内核、场景/噪声接口、协议/会话/时钟、服务端/客户端、策略契约、批量管理接口、评价及CLI。
- 夹具：`fixtures/timing.json`和`fixtures/timing.trace.json`；其余边界夹具在可重置测试中明确定义。
- 验证：`tests/`，包括物理、通信、时钟、客户端、等价、信息字段与独立进程CLI测试。
- 审计：`rules/source_manifest.json`、`docs/rules_matrix.md`、`docs/official_gaps.md`。
- 使用及边界：根目录 `README.md`、`docs/compatibility.md`、`requirements.lock`。
- 实测记录：`docs/test_results.txt`、`docs/source_audit.json`、`docs/timing_replay.json`、`docs/kernel_comparison.json`、`docs/benchmark_cpu.json`、`docs/trace_audit.json`。

后续确定性算法、搜索规划器和模型只替换 `Policy.choose(public_history)`；无需改动仿真内核。训练接入前继续保持评价真值与actor输入分离。现阶段没有求解策略、PPO训练器、CUDA内核或官方随机生成实现，文档和命令不会把它们描述为已完成。

要解除官方一致性阻断，需要官方场景联合生成说明、固定误差场及地点键、角度/时间量化与边界参考样例。现有可确认模块、测试工具和策略契约可立即使用，不必等待这些信息或最终求解算法。

## 可视化网页版补充交付

后续已完成本地可视化网页，新增 `python3 -m bsim web` 命令。包含运行控制、地图轨迹、手动四类动作、计时反馈、已接受动作列表、LOCAL导出和默认关闭的管理端真值视图。网页与机器人接口使用独立端口，未改变机器人观测字段。

最新回归共29项测试通过（此前26项加3项网页管理测试）。浏览器实际验证了开始/倒计时、六步演示至199秒、真值开关、刷新、地图点击坐标和中止确认，未发现控制台error/warn。运行说明见README，可视化模块逐项PASS/NOT_RUN及限制见 [网页验收记录](web_dashboard_report.md)。官方软件/CUDA仍未实测，G01—G09未因增加网页而解除。
