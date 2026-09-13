# Q3/Q4 Structural Optimization Runbook

Use the repository launcher for every Python command so the `.venv` CUDA libraries precede system CUDA libraries:

```bash
cd /data5/hy/B-problem
scripts/run_python.sh -m pytest -q
```

CPU structural smoke:

```bash
scripts/run_python.sh scripts/q4_preflight.py --output runs/q34_structural_20260912/preflight_q4
```

Four-GPU synchronous smoke (one model/checkpoint, ranks 0-3):

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 scripts/run_torchrun.sh --standalone --nproc_per_node=4 scripts/train_ddp.py --config configs/q34_structural_q3_smoke.json
```

Use GPUs 4-7 for Q4 with `configs/q34_structural_q4_smoke.json`. `metrics.jsonl` records `world_size`, visible GPU IDs, optimizer state digest, and the parameter/Adam synchronization audit. Do not run Q3 and Q4 on overlapping GPU IDs.

Baseline hashes, non-overlapping train/validation/development/final seed ranges, and the test-selection rule are in `runs/q34_structural_20260912/manifest.json`. Final frozen tests must run once after validation checkpoint selection.
