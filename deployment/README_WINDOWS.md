# Windows 本地部署：论文最终 Q3 / Q4

Q3：`q3_legacy_deadline_20260913/best.pt`（51397bc8）；Q4：`q4_baseline_8gpu_1h_20260913/train/best.pt`（c8812ced）。Q4 已更新为用户指定的一小时续训 best；历史官方日志使用的是其父基线。

将整个 ZIP 解压到一个新文件夹，例如 `D:\B-problem-local`。不要与旧代码目录混合，不必复制服务器虚拟环境或完整训练 runs。

## 文件

- `scripts/run_policy.py`：Q3/Q4 共用启动程序。
- `deployment/runtime_public_v2/`：与两份权重完全匹配的策略、特征、几何和通信代码。保持整个目录及 manifest.json。
- `deployment/inference_fixtures.json`：26 组公开观测及服务器参考输出，用于本地自检。
- `models/q3_best.pt`、`models/q4_best.pt`：本轮验证集选出的 best，已在新 3000 局配对测评中验证。
- `requirements-windows.txt`：依赖；`bundle_manifest.json`：逐文件哈希和原始权重来源。

权重与本包内的 11 维 normalized-public-v2 特征绑定。不要换成开发分支的 14 维或 v5 controller。包内保留原 checkpoint 以保持哈希可追溯；使用可信来源的权重。

## 安装（PowerShell，Python 3.11 64 位）

在解压后的文件夹中打开 PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r .\requirements-windows.txt
```

不需要激活虚拟环境，不需要 CUDA 或 Linux 的 run_python.sh。若 `py -3.11` 不存在，先安装 Python 3.11 64 位。CPU 推理即可。

## 先做离线自检

```powershell
.\.venv\Scripts\python.exe .\scripts\run_policy.py --problem 3 --checkpoint .\models\q3_best.pt --robot-id 202619002320 --check-only
.\.venv\Scripts\python.exe .\scripts\run_policy.py --problem 4 --checkpoint .\models\q4_best.pt --robot-id 202619002320 --check-only
```

应看到 `MODEL_READY`、`PARITY_CHECK`、`CHECK_ONLY_OK`。每题 13 个参考状态，容差 atol=rtol=1e-4；若近似平局导致动作差异，会记录 near_tied_choices。该操作不发送 /enter，不消耗官方测试。服务器已验证 CPU 路径；Windows 原生依赖和本机性能由此步骤核验。

## 连接官方模拟器

1. 在官方软件登录，确认界面中的参赛队号。下列 `202619002320` 必须与当前登录队号逐字一致。
2. 在官方软件选择对应问题和测试样例，开始测试，等待五秒倒计时结束、接口就绪。
3. 只启动对应的一条命令。一个官方测试会话只运行一个策略程序；Q3、Q4 分别新开测试。

Q3：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_policy.py --problem 3 --checkpoint .\models\q3_best.pt --base-url http://127.0.0.1:2026 --robot-id 202619002320
```

Q4：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_policy.py --problem 4 --checkpoint .\models\q4_best.pt --base-url http://127.0.0.1:2026 --robot-id 202619002320
```

程序按官方 /enter 返回的现实剩余时间执行，串行调用 /measure、/clear、/exit。固定误差意味着不能把同地点重复测量当作独立信息。Q4 保留匹配权重的 31 站覆盖及退出条件；无需独立启动服务器或连接训练服务器。

## `/enter accepted=false` 的含义

截图是 `HTTP 200` 但 `accepted=false`，说明模拟器收到请求但拒绝进入。这个响应发生在模型动作选择之前，不能据此判断模型权重错误。官方附件2 §6.3 列出：arena_id 不为 default、robot_id 与登录队号不一致、包含未知字段、重复 /enter。

新程序固定只发送 arena_id=default、robot_id、唯一 request_id 三个字段，检查队号中的空白/不可见字符，并记录实际请求和原始响应。若依然被拒绝：

- 对照官方界面的当前登录队号，不能用其他账号/旧队号。
- 若本局已有程序成功进入，关闭其他策略进程，并在官方软件中结束旧局、重新开始新测试后再运行。不要对已经进入的同一局不断重跑脚本。
- 尚未开放接口通常会表现为连接失败；等待倒计时结束和就绪提示。

官方该拒绝响应没有原因字段，程序无法替你确定是哪一种，也不能强制重置或绕过。不要另行用 HTTP 工具测试 /enter：成功进入后再启动策略会造成重复进入。

每次运行在 `logs/q3_*.jsonl` 或 `logs/q4_*.jsonl` 保存启动信息、逐请求、响应及错误。网络超时只以相同 request_id 和请求字节重试，明确拒绝后不会不停发送新的 /enter。若需要排查，提供该次日志和官方界面的题号、队号及测试状态；无需提供账号密码。

## 验证范围

服务器完成两题端到端本地 HTTP 模拟器测试，全部清除并正常退出；测试了错误队号、重复进入、权重题号不符和离线自检。未在此服务器启动 Windows 官方软件。3000 场景成绩为研究模拟器结果，官方效果需本机实测。
