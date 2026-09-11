# 本机部署

训练服务器只导出 checkpoint；策略程序在测试电脑运行，并通过本机回环地址调用四个接口。策略程序不读取场景文件或隐藏真值。

Q3 示例：

```bash
scripts/run_policy_local.sh \
  --problem 3 \
  --checkpoint runs/large_20260911/q3_ext_gpu1/best.pt \
  --base-url http://127.0.0.1:2026 \
  --robot-id <参赛队号>
```

Q4 使用对应的 `best.pt`，且 `--problem 4`。只有在 Q4 训练完成并通过独立配对评估后才替换 checkpoint。

正式运行前在官方软件中确认它已监听 `127.0.0.1:2026`、参赛队号正确、问题编号正确。程序不会自动启动官方模拟器，也不会连接非回环地址。

训练 checkpoint 是研究分布产物，不代表官方隐藏分布已经验证。接口结束后不要再调用 `/exit` 查询原因。
