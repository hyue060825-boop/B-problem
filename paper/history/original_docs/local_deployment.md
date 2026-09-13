# 本机部署

最新 Q3 / Q4 部署说明见 [Windows 部署说明](../deployment/README_WINDOWS.md)。

`python scripts/build_windows_policy_bundle.py` 导出包含匹配运行代码、两题 best 权重和离线参考观测的独立包。已生成：`dist/B-problem-windows-20260913.zip`。

新版 `scripts/run_policy.py` 支持 Q3 / Q4 的 `normalized-public-v2` checkpoint，固定从 `deployment/runtime_public_v2/` 加载匹配源码，并按权重 provenance 校验。当前开发中的新版 controller、14 维候选和 v5 attention 不可直接接到这两份旧谱系权重。

Windows 使用 Python 3.11 和 CPU PyTorch，无需复制 Linux `.venv`、训练数据或连接训练服务器。具体安装、自检和两题运行命令见上述说明。

HTTP 200、`/enter accepted=false` 是官方拒绝进入，不是权重维度错误。核对当前登录队号、是否已经成功进入本局；程序无法从该响应中推断具体原因。协议依据：附件2 §6.3。新版启动程序仅发送三个规范字段，保存逐请求和响应日志，明确拒绝后停止。
