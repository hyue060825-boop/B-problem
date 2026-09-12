# GitHub 协作速查

三人、三天竞赛，以可追溯交付和及时同步为主。命令行、编辑器或 GitHub Desktop 均可。

## 分工与分支

- **hyue060825-boop**：在 `hy_branch/b45c0d2` 完成 Q1–Q4 建模、编程、实验和后续修复，提交到该分支。
- **验收负责人**：审阅 hy 的交付，整理资产并合入 `main`，说明当前能力和遗留问题。
- **验收负责人、Iloverice-wang**：维护 `main`，组织验证、交接与论文；`paper/` 由论文手统筹，建模材料放 `handoff/`。

hy 不直接向 `main` 交付开发提交。已知问题可随当前资产接收，修复由 hy 后续更新；接收记录与质量验证分别说明。

## hy 日常提交

切换前检查工作区，已有修改先提交或妥善暂存。开工时同步开发分支：

```bash
git status
git fetch origin
git switch hy_branch/b45c0d2
git pull --ff-only origin hy_branch/b45c0d2
```

完成一批工作后检查差异，按文件暂存，明确推送目标：

```bash
git diff
git add -- 本次修改的文件路径
git diff --cached
git commit -m "feat: 完成一批模型与实验"
git push origin HEAD:hy_branch/b45c0d2
```

交付说明写清提交号、入口、配置、结果及已知问题。不要在正在训练的同一份源码中途切换版本。

## 验收与 main 维护

1. 验收负责人 fetch 后固定 hy 的提交，核对原始记录与 main 上队友的更新。
2. 整合源码、配置和结果，保留原始训练记录；只做已授权的改动，补相称的验证和交付索引；接收记录写入 `records/acceptance/`，版本入口更新 `records/versions.md`。
3. 审阅后提交到 `main`。需要队友看差异时使用 PR；少量文档或论文手独立维护的文件可直接提交，提交前先同步。
4. 整合推送后 hy 在开发分支执行 `git fetch origin`、`git merge origin/main`，接续新的目录和接口。`hy_branch/b45c0d2` 保留使用。

禁止强推 `main`，也不为整理误操作提交而重写共享历史。冲突时保留双方工作，推送被拒绝时先核对远端更新。同一论文文件避免多人同时编辑；向论文手交付时更新 [handoff/README.md](handoff/README.md)。

本指南参考 AgenticFinLab 的协作材料，已按本队分工简化。
