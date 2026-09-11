# 规则证据矩阵

规则原件见[题面与附件](../../problem/README.md)，版本由[校验清单](../../problem/SHA256SUMS)确定。代码位于 `src/bsim/`，测试位于 `tests/simulator/`。下表只说明对应断言覆盖的公开规则，不表示隐藏生成过程一致。EXPLICIT 为明示规则，DERIVED 为推论，UNSPECIFIED 为未充分定义。


| 编号 | 规则文本 | 原文件和位置 | 级别 | 代码位置 | 测试编号（tests中的方法名） | 未决事项 |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | 源位于原点圆心1800米圆域，东x北y | B题第1页；附件2 §1.1 | EXPLICIT | scenarios.Source | Physics.test_scenario_constraints | 隐藏位置分布G01 |
| R02 | 10—16个源，频道1—20，每频道至多一个 | B题第1—2页；附件2 §1.3 | EXPLICIT | scenarios.Scenario | Physics.test_scenario_constraints | 具体联合分布G01 |
| R03 | 问题3全向；问题4两类并存 | B题第1—2页问题3/4 | EXPLICIT | scenarios.Scenario | Physics.test_scenario_constraints | 类型数量分布G01 |
| R04 | 接收半径各自固定，1000—1500米，闭边界 | 附件2 §2.1—2.2 | EXPLICIT | reference.within/visible | Physics.test_omni_thresholds / test_all_cardinal_halfplane_boundaries | 浮点比较G06 |
| R05 | 定向源有效半平面总180度，含边界 | B题第2页附录1(3)；附件2 §2.2 | EXPLICIT | reference.visible | Physics.test_direction_and_clear / test_all_cardinal_halfplane_boundaries | 重合及任意旋转临界点G06 |
| R06 | 非重合点可用u·(p-g)≥0判断 | 同R05，由cos夹角在±90度非负推导 | DERIVED | reference.visible | Physics.test_direction_and_clear | 三角函数浮点边界G06 |
| R07 | 可接收且距离≤5时near且无角度 | B题第3页附录2(9)；附件2 §2.4、§7 | EXPLICIT | reference.observe | Physics.test_omni_thresholds / test_direction_and_clear | 定向重合G06 |
| R08 | 不存在、已清除、距离超限、覆盖外均no_signal | 附件2 §2.2、§7.3 | EXPLICIT | reference.observe | Physics.test_omni_thresholds / test_direction_and_clear | 无 |
| R09 | 方向从检测点指向源；东0逆时针，[0,360) | 附件2 §1.2、§7.3 | EXPLICIT | reference.observe | Physics.test_omni_thresholds / test_error_endpoints_quantization_and_return | 量化顺序G04 |
| R10 | 同地点误差固定，范围[-1,+1]度 | B题第2页附录2(1)；附件2 §2.3 | EXPLICIT | noise.ErrorField/FixtureNoise | Physics.test_error_endpoints_quantization_and_return | G02/G03；仅TEST场固定性通过 |
| R11 | 示向度保留两位小数，归一化 | 附件2 §2.3 | EXPLICIT | noise.Numerics.angle | Physics.test_error_endpoints_quantization_and_return | G04，具体舍入仅夹具 |
| R12 | 清除仅看指定未清除源距离≤20，不受朝向影响 | B题第3页附录2(8)；附件2 §8.2 | EXPLICIT | reference.transition | Physics.test_direction_and_clear | 浮点边界G06 |
| R13 | 同源只能清除一次 | 附件2 §8.2 | EXPLICIT | reference.State/transition | Physics.test_direction_and_clear | 无 |
| R14 | 狗可出圆，分量有限且绝对值≤2000000 | 附件2 §1.1、§7.4 | EXPLICIT | protocol.validate | Protocol.test_json_invalids | 无 |
| R15 | 初始(0,0)、频道1，enter不增虚拟时间 | 附件1 §1、§2.1；附件2 §1.4、§6 | EXPLICIT | reference.State/session.request | Protocol.test_official_timing_example | 无 |
| R16 | 移动距离/5秒，无移动独立指令 | B题第3页附录2(6)；附件2 §3、§4.2 | EXPLICIT | reference.transition | Protocol.test_official_timing_example / ClockClient.test_noninteger_movement_microseconds | 微秒取整G05 |
| R17 | measure固定5秒，仅频道改变另加1秒 | 附件2 §4.3 | EXPLICIT | reference.transition | Protocol.test_official_timing_example | 无 |
| R18 | clear成功5秒、失败3秒，不改变测向频道 | 附件2 §4.4、§8 | EXPLICIT | reference.transition | Protocol.test_official_timing_example / Physics.test_direction_and_clear | 无 |
| R19 | exit任意位置，0秒，user_exit | 附件1 §2.4；附件2 §9 | EXPLICIT | session.request | Protocol.test_official_timing_example / Http.test_http_reference_exact_and_closed | 结束发送/缓存G08 |
| R20 | accepted=false仅公共字段，virtual_time_s=0，不生效 | 附件2 §4.1、§5.2 | EXPLICIT | session.rejection/client | Protocol.test_idempotence_and_rejections / ClockClient.test_client_lost_response_and_pending | 无 |
| R21 | 内部微秒累计，响应JSON number最多6位小数 | 附件2 §4.1 | EXPLICIT | reference.State/noise.movement_us/session | ClockClient.test_noninteger_movement_microseconds | 舍入实现G05 |
| R22 | 数据准备后倒计时5秒，窗口25分钟，enter后最多20分钟 | 附件1 §2.5；附件2 §4.5 | EXPLICIT | session.prepare/data_ready/deadline | ClockClient.test_lifecycle_and_late_enter / CLI.test_separate_server_and_socket_lifecycle | 精确时钟取样未官方实测 |
| R23 | 剩余完整秒数取两截止较早者，0—1200 | 附件2 §4.5、§6.2，“完整秒数”向下取整 | DERIVED | session.request | ClockClient.test_lifecycle_and_late_enter | 亚秒边界实测未做 |
| R24 | 虚拟上限360000秒，登记在截止前的动作可完成 | 附件2 §4.5 | EXPLICIT | session.request/refresh | ClockClient.test_registered_action_finishes_and_virtual_crossing / Http.test_incomplete_body_past_deadline_does_not_execute | 传输细节G08 |
| R25 | 倒计时/结束接口关闭，无JSON断开正常 | 附件1 §4.4—4.5；附件2 §1.5、§5.3 | EXPLICIT | http_server/client/session | CLI.test_separate_server_and_socket_lifecycle / Http.test_http_reference_exact_and_closed | G08 |
| R26 | 仅POST，4精确路径，无斜线/查询串 | 附件2 §3、§5.1 | EXPLICIT | protocol.validate/http_server.Handler | Protocol.test_headers_paths_identifiers_size_depth / Http.test_wire_errors_and_retries | 畸形HTTP解析优先级G07 |
| R27 | JSON媒体类型，仅charset=utf-8；encoding缺省或identity | 附件2 §5.1 | EXPLICIT | protocol.validate | Protocol.test_headers_paths_identifiers_size_depth | 大小写/参数细节G07 |
| R28 | 无BOM UTF-8对象，无重复键，≤65536字节、≤16层 | 附件2 §5.1 | EXPLICIT | protocol.validate/depth/pairs | Protocol.test_json_invalids / test_headers_paths_identifiers_size_depth / Validation.test_deep_json_is_rejected_without_recursion_error / Http.test_deep_json_returns_public_400_over_http | 深度计数约定G07 |
| R29 | channel允许整数值1.0，不允许1.5和布尔 | 附件2 §5.1；JSON布尔与数值类型不同 | EXPLICIT | protocol.validate/finite | Protocol.test_json_invalids | 无 |
| R30 | robot_id逐字节匹配，1—64字节；request_id 1—128字节，无控制/格式字符 | 附件2 §5.1、§6.3 | EXPLICIT | protocol.identifier/validate | Protocol.test_headers_paths_identifiers_size_depth / test_idempotence_and_rejections | 特殊Unicode边缘未穷举 |
| R31 | 未声明字段，包括position子字段，200 false | 附件2 §5.1、§7.4 | EXPLICIT | protocol.validate | Protocol.test_headers_paths_identifiers_size_depth | 复合错误顺序G07 |
| R32 | 400/404/405/409/413/415/429/500的含义 | 附件2 §5.3 | EXPLICIT | protocol/session/http_server | Protocol.test_json_invalids / test_headers_paths_identifiers_size_depth / test_state_and_capacity / Physics.test_atomic_failure_and_missing_profiles | 429阈值仅注入；异常传输未穷举 |
| R33 | 相同ID相同请求原响应重放，不重复计费，保留时间戳 | 附件2 §5.3 | EXPLICIT | session.cache/client | Protocol.test_idempotence_and_rejections / ClockClient.test_client_lost_response_and_pending | JSON等价G07、关闭后重放G08 |
| R34 | 同ID不同动作或不同新动作并发409 | 附件2 §5.3 | EXPLICIT | session.condition/http_server.delivery_active | Protocol.test_concurrent_actions / test_idempotence_and_rejections | 同ID执行中策略G07 |
| R35 | 结构/未知字段/身份不匹配不占用ID | 附件2 §5.3 | EXPLICIT | session.request | Protocol.test_idempotence_and_rejections | 其他业务拒绝占用策略G07 |
| R36 | 不因测量虚拟5秒而现实等待；正常合法串行无速率上限 | 附件2 §1.4、§5.3 | EXPLICIT | session/http_server | CLI.test_separate_server_and_socket_lifecycle | 保护阈值G07 |
| R37 | 总源数等真值不通过机器人接口返回 | B题第3—4页；附件2 §1.3、§2.1、§5—9 | EXPLICIT | client.public_response/env/evaluation | ClockClient.test_response_leakage_and_history / Equivalence.test_batch_reference_and_fast_session | 同用户恶意进程沙箱不在本实现内 |
| R38 | 默认回环127.0.0.1:2026，可改端口 | 附件2 §1.5 | EXPLICIT | http_server.LocalServer/CLI | Http各项 / CLI.test_separate_server_and_socket_lifecycle | IPv6未实现 |
| R39 | 演练不限次数；正式每问3次，中止占机会 | B题第3—4页；附件1 §4.3、§4.5 | EXPLICIT | 文档范围限制，不模拟正式机会 | NOT_RUN：未启动官方运行 | G09 |
| R40 | 官方编码、加密日志、上传不等同客户端明文轨迹 | 附件1 §4.6 | EXPLICIT | evaluation的LOCAL标记 | Equivalence.test_replay_and_observable_audit | G09 |
| G01—G09 | 隐藏过程、数值及异常协议细节未充分定义 | 详见official_gaps.md每行检索范围 | UNSPECIFIED | profiles/OfficialGenerator/OfficialError/Numerics | CLI.test_profile_block_and_replay_cli / Physics.test_atomic_failure_and_missing_profiles | BLOCKED，不能记PASS |

实现扩展（管理端reset、BatchEnv、Policy契约、LOCAL标签、场景文件格式）来自本阶段开发要求，不标注为官方接口。快速内核是工程实现选择，测试见Equivalence，不作为官方算法或随机模型证据。

响应必填字段、数值和枚举由 `Validation.test_required_response_fields_and_numeric_ranges` 等验证；异常响应后的幂等恢复、完整/局部轨迹区分和来源审计也在 `test_validation.py` 中覆盖。可观测轨迹通过不证明隐藏真值或全部清除。
