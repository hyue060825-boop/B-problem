# Q4 3000 局诊断测试

使用 `runs/large_20260911/q4_gpu6_retry/best.pt` 在自建 `LOCAL-RESEARCH` 分布上运行 3000 个独立随机场景。该 checkpoint 未通过正式模型选择门槛，本目录结果只用于诊断，不能作为官方测评依据。

每局定义 `t_i = virtual_time_s / cleared_sources`，然后计算 `sum(t_i) / 3000`：

- 完成率：411 / 3000 = **13.7%**
- 每局平均每源时间的平均值：**2176.546 s/source**
- 按总时间和总清除源数加权：**1959.670 s/source**
- 中位数：2176.423 s/source
- P05 / P95：478.681 / 3829.869 s/source
- 总清除源数：35,363

大量局面在 400 个宏动作预算内未完成，说明当前 Q4 策略不能进入正式部署测评阶段。`samples.json` 保存逐局结果，`summary.json` 保存聚合统计，`per_source_time_distribution.png` 为分布图。
