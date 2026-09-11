# 模拟器原始交付记录

来源提交：`b19280495fd788c3eaf40c7256fb31feb0d7bbe0`。本目录保存该提交中的历史验收报告、原始测试输出、性能结果和文件清单，内容保持原样。

- `docs/conformance_report.md`、`docs/web_dashboard_report.md`：交付时的范围与验证说明。
- `docs/*.json`、`docs/test_results.txt`：原环境输出；CPU 性能来自 macOS，不能替代当前机器测量。
- `rules/`：当时的来源及构建哈希；包含未随仓库提供的开发提示词来源记录。
- `requirements.lock`：当时的两行环境说明，未锁定第三方依赖。

报告和清单中的旧路径相对于来源提交的仓库根目录，保留它们便于对照 Git 历史。当前目录、运行方式及能力以[模拟器说明](../../../docs/simulator/README.md)为准；当前官方原件校验读取 `problem/SHA256SUMS`。新的验证另建运行目录。
