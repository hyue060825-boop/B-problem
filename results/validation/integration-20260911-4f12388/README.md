# 资产整合验证

代码提交：`4f12388560937378ab1b18f89d036f73740410e6`。运行环境与输入文件哈希见 [run.json](run.json)。

- [39 项回归](tests.txt)全部通过，包含深层 JSON、完整响应校验、异常响应后的幂等恢复、局部轨迹判定、HTTP 及网页管理 API。
- [三份原件校验](sources.json)通过；[保留项检查](preservation.json)通过。
- [附件计时回放](replay.json)和[公开轨迹审计](trace-audit.json)通过，累计为 0、105、111、194、199、199 秒。
- [10,000 步内核对比](kernel-comparison.json)及 48 个距离边界无差异。
- [历史计时轨迹比较](trace-comparison.json)无差异。
- [构建检查](package-check.json)确认网页 HTML、CSS、JavaScript 已包含在安装包中；演示数据仍依赖完整仓库。

原始输入和运行命令记录在 run.json，脚本捕获的输出保存为本目录各文件。复现入口见[模拟器说明](../../../docs/simulator/README.md)。

本次未运行官方演练、训练或浏览器视觉验收。测试通过说明已列案例成立，不代表完整求解器、官方隐藏场景一致性或全部清除已得到验证。
