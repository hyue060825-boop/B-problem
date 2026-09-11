# 本地模拟器

提供公开物理规则、四个 HTTP 接口、会话计时、确定性夹具、回放、CPU 内核对比和调试网页。当前可用于规则验证与客户端联调；完整求解器、随机研究场景生成、训练器和 GPU 后端尚未实现。

先按[仓库说明](../../README.md)完成可编辑安装。以下命令在仓库根目录、已激活的环境中执行。

已有测试的结果与适用范围见[整合验证记录](../../results/validation/integration-20260911-4f12388/README.md)。下方 `.local/` 输出用于临时调试；需要留存的验证或策略实验按[结果说明](../../results/README.md)归档。

## 验证与回放

```bash
python -m bsim audit-rules
python -m bsim validate-fixtures --profile fixture_conformance
python -m bsim replay --fixture tests/fixtures/simulator/timing.json --trace tests/fixtures/simulator/timing.trace.json --output .local/timing-replay.json
python -m bsim audit-trace --trace .local/timing-replay.json
python -m bsim compare-kernels --profile fixture_conformance --steps 10000
```

原件校验直接读取 `problem/SHA256SUMS`；`--sources` 可指定另一份包含该清单的题面目录。计时例应为 `0,105,111,194,199,199` 秒；单源、零误差是测试输入，不能据此评价搜索效果。

`audit-trace` 检查字段、请求顺序、重复 ID 和可观测计时：发现冲突为 `FAIL`；缺少进入、结束或动作确认时为 `INCOMPLETE`；覆盖完整且检查通过才为 `PASS`。PASS 不证明全部源已清除，也不证明与官方隐藏场景一致。两种非 PASS 状态均返回退出码 1。

```bash
python -m bsim benchmark --device cpu --num-envs 64 --steps 128
python -m bsim compare-traces --left .local/timing-replay.json --right results/validation/import-b192804/docs/timing_replay.json --include-real-time
```

性能测试仅包含 CPU 物理状态转移，不包含 HTTP、策略计算与训练。轨迹比较要求相同请求 ID 和确定性输入；默认忽略现实响应时间戳。

## 网页与动作服务

```bash
python -m bsim web --port 8765 --robot-port 20260
```

打开终端给出的完整管理链接，选择场景、开始会话，倒计时 5 秒后点击“进入”。可手动检测、清除，也可连接外部策略。地图展示轨迹和示向线，支持点击选点、缩放及导出动作记录。管理端真值视图默认关闭。

管理网页与机器人动作端口独立，均只监听本机回环地址。管理链接包含每次启动生成的密钥，留在本地管理端。新建会话会替换旧会话的内存记录，需要保留时先导出；导出只含已接受动作，不含拒绝、网络异常或真值。

也可直接启动动作服务，在另一个终端运行通信示例：

```bash
# 终端一，等待倒计时结束
python -m bsim serve --profile fixture_conformance --fixture tests/fixtures/simulator/timing.json --port 20260
# 终端二
python -m bsim smoke-client --url http://127.0.0.1:20260 --output .local/client-trace.json
```

示例执行六步计时动作后退出，不具有搜索能力。问题 4 展示夹具为 `tests/fixtures/simulator/visual_mixed.json`，包含手工指定的 10 个混合源。

## 接入策略

实现 `bsim.strategy.Policy.choose(public_history)`，返回 `(path, position, channel)`，由 `RobotClient` 串行发送动作。只向策略提供公开请求/响应历史；管理端的场景、误差、真实源数和评价对象单独使用。

网络失败会复用原始字节与 ID 重试。失败耗尽或响应格式异常时保留 pending，使用 `retry_pending()` 恢复；确认响应合法前不更新客户端时钟。当前运行器只提供基础循环，后续求解器需补运行预算、异常恢复和持久化日志。

源码使用仓库内的夹具与测试，当前面向完整源码仓库运行。`fixture_conformance` 可用；`strict_official`、`compatible_research` 和 CUDA 后端尚不可用，对应命令退出码为 2。

详细依据见[规则矩阵](rules_matrix.md)、[兼容范围](compatibility.md)、[官方信息缺口](official_gaps.md)。历史交付记录见[原始导入](../../results/validation/import-b192804/README.md)。
