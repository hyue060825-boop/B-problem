# 论文复现说明

以根目录 `README.md` 和 `paper/model_registry.json` 为模型身份入口。本分支不自动启动训练。

## 已有结果的精确复算

```bash
python scripts/build_paper_catalog.py
python scripts/verify_paper_release.py
python -m pytest -q
python scripts/verify_q4_certificate_exact.py runs/q4_optimization_20260912/layout31_proof.json
```

`build_paper_catalog.py` 从最终逐局数据重新计算均值、P95、源数分层和配对区间，生成PNG/PDF与UTF-8 CSV。配对95%区间采用均值±1.96×样本标准差/√n，并非bootstrap。训练表分别统计整段运行与保存best之前的数据；只计当前续训段，不含继承父权重之前的历史训练。

`verify_paper_release.py` 检查模型、运行源码、数据表输入、分卷哈希、原实验覆盖和论文入口链接。有服务器原始cache时再核对所有25984原件；克隆到其他电脑没有cache时明确记录该项未执行。整理时已经逐成员验证全部压缩包；单次解包还会重复验证成员内容。

## 冻结最终模型的新评测

```bash
python scripts/evaluate_final_pair.py --output cache/new_final_pair --episodes 3000 --workers 16 --q3-seed 1930000000 --q4-seed 1940000000
```

Q3对照 `q3_gpu8_extended_20260912/ppo/best.pt`；Q4对照 `q4_legacy_deadline_20260913/best.pt`。默认场景是自建研究分布。输出目录必须不存在；新评测不能覆盖归档主结果。保留现实剩余时间特征，且运行硬件/负载影响该特征，因此不能保证重新跑每个虚拟耗时都逐位相同。旧 Q4 主评测在rank内先父模型后候选；新入口交替顺序，协议差异必须披露。

`evaluate_deadline_pair.py` 保留凌晨实验的模型组合（其中Q4是父基线对更早budget模型），不能拿它当最终Q4评测入口。`search_q3_layout_extremes.py` 对应最终Q3；Q4补充分析入口默认对应父基线，使用前查其参数和报告。

## 复现训练方案

最终Q3原配置：`runs/q3_legacy_deadline_20260913/config.json`；最终Q4：`runs/q4_baseline_8gpu_1h_20260913/train/config.json`。原文件中的绝对路径、截止时间和结果不改动。另存一份新配置，改成新输出路径、本机父权重路径和将来的截止时间，再调用：

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 python -m torch.distributed.run --standalone --nproc_per_node=4 scripts/train_legacy_deadline_ddp.py --config NEW_Q3_CONFIG.json
```

Q4用8个rank与原Q4配置。`launch_q4_baseline_8gpu_hour.py --output NEW_DIRECTORY` 则完整保留八卡一小时、smoke和自动配对测试流程，从e8a5父模型开始。长训练前按原流程完成smoke与恢复smoke。父模型、优化器、随机种子和DDP一致性检查均需保留；新日期不应继续使用旧绝对deadline。

研究模拟器与几何rollout主要在CPU，GPU用于网络前后向与DDP。原 GPU 搜索/其他架构尝试的源码、标签和实验日志在 `paper/history/`，不混入当前最终运行时。

## 查阅历史原件

```bash
python scripts/extract_experiment_archive.py paper/history/runs/q3_gpu8_extended_20260912/archive_manifest.json cache/q3_gpu8_evidence
```

所有分卷按清单顺序拼接并校验；原相对路径在解包目录内保留。旧模型权重不随历史证据重复上传，必要对照权重在 `runs/`，其余原权重在服务器cache。历史文档里的链接/绝对路径保留原样，跨机器阅读从新实验索引进入。
