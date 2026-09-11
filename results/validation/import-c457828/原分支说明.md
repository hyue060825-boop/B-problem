# B-problem

已实现独立的LOCAL模拟器：公开物理规则、四个HTTP接口、会话与时钟、确定性夹具、重放和CPU批量路径。官方隐藏场景分布、误差场及部分数值约定仍缺依据，完整官方模式会明确阻断。没有启动官方演练/正式测试，也没有开展训练。

详细交付状态见 [验收报告](docs/conformance_report.md)，规则依据见 [规则矩阵](docs/rules_matrix.md)，缺失资料见 [官方缺口](docs/official_gaps.md)，替换策略与数值约定见 [架构和兼容范围](docs/compatibility.md)。

## 快速验证

在本目录运行，需Python 3.9+，只使用标准库，依赖说明见 `requirements.lock`。

```bash
python3 -m bsim audit-rules --sources ..
python3 -m bsim validate-fixtures --profile fixture_conformance
python3 -m bsim replay --fixture fixtures/timing.json --trace fixtures/timing.trace.json
python3 -m bsim compare-kernels --profile fixture_conformance --steps 10000
python3 -m bsim benchmark --device cpu --num-envs 64 --steps 128
```

官方计时夹具预期累计秒数为 `0,105,111,194,199,199`。输出中的LOCAL标记表示本地记录，不是官方案例编码或加密日志。

## 本地HTTP运行

为避免误连官方默认端口，示例使用20260。以下命令只启动本地夹具，不调用官方软件；客户端命令需要明确指定URL。

终端一：

```bash
python3 -m bsim serve --profile fixture_conformance --fixture fixtures/timing.json --host 127.0.0.1 --port 20260
```

等待5秒倒计时后，终端二：

```bash
python3 -m bsim smoke-client --url http://127.0.0.1:20260 --output .local/client-trace.json
python3 -m bsim audit-trace --trace .local/client-trace.json
```

`exit`之后服务退出。每次新测试创建新的本地服务；不存在机器人reset接口。

以下命令**预期阻断**，退出码2，不会静默转为研究场景：

```bash
python3 -m bsim serve --profile strict_official
python3 -m bsim benchmark --device cuda --num-envs 256
```

前者缺官方依据；后者没有实现CUDA后端。`compatible_research`也尚未启用。用户后续授权研究目标后仍需明确假设并实现，不能只切换名称。

## 重放与比较

```bash
python3 -m bsim replay --fixture fixtures/timing.json --trace fixtures/timing.trace.json --output .local/replay.json
python3 -m bsim compare-traces --left .local/replay.json --right docs/timing_replay.json --include-real-time
python3 -m bsim audit-trace --trace .local/replay.json
```

夹具trace的每一步可携带 `advance_s` 推进管理端注入时钟，`expected_status`及`expected`指定断言，`abort:true`用于中止夹具。真实HTTP客户端轨迹的时间戳不要求与注入时间戳相同，默认比较忽略响应现实时间戳。官方软件没有可控隐藏真值时，只用 `audit-trace` 检查可观察不变量，不能声称逐场景等价。

## 接入后续策略

策略实现 `bsim.strategy.Policy.choose(public_history)`，返回 `(path, position, channel)`，通过 `RobotClient` 串行动作。模型输入只能来自client的请求/响应历史和最近一次有效虚拟时钟。采集/评估端单独持有场景和Session；不要把真值对象或夹具路径传给策略。

`BatchEnv`是管理端接口，用于将来接入学习系统的多个独立本地会话；其返回仍然只有公开响应和连接断开事实。参考内核、快速内核与HTTP使用同一动作语义。当前仅开展有限夹具验证及性能测量，没有训练模型，也没有实现最终搜索算法。

## 可视化网页版

在本目录执行：

```bash
python3 -m bsim web --port 8765 --robot-port 20260
```

打开终端打印的完整管理链接（含`#token=...`）。网页地址是 `127.0.0.1:8765`，动作接口单独使用 `127.0.0.1:20260`。管理密钥每次启动重新生成，仅保存在当前浏览器标签页会话中；不要把管理链接传给策略程序。

操作顺序：选择本地夹具 → 开始本地会话 → 等待5秒倒计时 → 点击“进入” → 手动检测/清除，或连接独立策略。也可在接口就绪后直接点击“运行六步计时演示”，自动执行enter、四个动作和exit。

地图显示目标圆、机器狗、移动轨迹、检测点、清除成功点及可选示向线；点击地图可填写动作坐标，支持缩放和适应轨迹。右侧独立的“管理端调试视图”默认关闭，开启后才请求并绘制源位置、朝向和接收范围。此信息不进入机器人动作响应。

顶部显示虚拟时间、现实剩余时间、已成功清除数和当前位置；底部列出最近1000个已接受动作。导出可取得本会话全部已接受动作的LOCAL JSON记录，供 `audit-trace` 检查。拒绝动作在操作反馈中提示，不进入已接受动作表。相同ID重放不重复计入。

提供两个确定夹具：

- 混合源展示夹具：手工指定的问题4场景，满足公开范围约束，零误差为明确TEST输入。
- 官方计时示例夹具：保留附件六步计时预期，单源与零误差仅是本地测试输入。

网页不提供官方登录、正式测试、成绩上传、随机场景生成或模型训练。新建会话会替换内存中的旧会话，需保留记录时先导出；结束当前会话不会关闭管理网页。停止整个网页服务请在启动终端按Ctrl+C。详细验证见 `docs/web_dashboard_report.md`。
