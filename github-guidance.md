# GitHub 协作速查

- hyue060825-boop 的最终交付在 `experiment_result`；旧 `hy_branch/b45c0d2` 不再作为接收入口。
- 验收负责人整合实验资产到 `main`，与 Iloverice-wang 维护结果及论文。`paper/` 由论文手组织，建模实验侧在 `handoff/` 交付。
- 开工先检查工作区，再同步目标分支；不要在运行训练的源码目录中途切换版本。

```bash
git status
git fetch origin main experiment_result
git switch main
git merge --ff-only origin/main
```

本地已有独立提交时，先查看双方增量再合并；不要用 reset 丢弃工作。验收固定来源提交，按 main 目录接收代码与数据，记录来源、配置、权重和验证，更新当前导航。大批资产可在临时整合分支审阅后合入 main，少量独立修改可直接提交。

```bash
git diff
git add -- 本次修改的文件路径
git diff --cached --stat
git commit -m "说明本次完成的工作"
git push origin main
```

推送前再次核对远端。禁止强推 main，不重写共享历史；原始实验记录不覆盖，同一论文文件避免同时编辑。历史方案与提示词留在 `records/protocols/`，不作为当前规则。
