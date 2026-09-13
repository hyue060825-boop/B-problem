# Q3/Q4 Structural Optimization Baseline Audit

Date: 2026-09-12. Branch: `hy_branch/b45c0d2`. Audited HEAD: `9bf8830f17b5863d4d8334691c18788ebd1a6e56`; the prompt's `3ddb2d9` review baseline has since gained only the Q3 eight-GPU search/training pipeline. Existing modified historical run files under `runs/large_20260911` are preserved and excluded from this work.

## Execution path

`TrainingEnv` creates a LOCAL-RESEARCH `Session` backed by the exact `ReferenceKernel`. The controller obtains only `/enter`, `/measure`, `/clear`, and `/exit` public responses. `Controller.legal_actions()` creates macro candidates; `features()` turns the public controller state and those candidates into actor inputs; `CandidatePolicy` selects a candidate; `Controller.execute()` expands it into primitive HTTP-equivalent requests. Evaluation truth is used only by `TrainingEnv.metrics()` for completion and reporting.

DDP training creates one rank per GPU, collects disjoint seed shards, globally normalizes PPO advantages, synchronizes gradients for each optimizer step, audits model plus Adam state, and allows only rank 0 to save one checkpoint lineage. Validation seeds select `best.pt`; frozen test seeds are evaluated only after selection. Search uses frozen policy replicas without optimizers and its hypotheses are conditioned only on serialized public history.

## Current controller and candidate space

Both problems use channel states `UNKNOWN -> LOCALIZING/CLEARABLE -> CLEARED`, with `ABSENT_CERTIFIED` for public absence proofs. Q3 uses a certified seven-station omni skeleton and may apply 1000 m negative exclusion after a source is discovered. Q4 retains a continuous-domain 31-station directional certificate and never turns an isolated Q4 `no_signal` into a position exclusion.

The current candidates are: up to the three nearest unvisited `COVER` stations, fixed two-sided `LOCALIZE` points while `localizations < 3`, certified `CLEAR` at the MEC center, monolithic `PROBE_CLEAR`, and certified `EXIT`. COVER scans one hard-coded channel set and marks the physical station visited globally. A near observation immediately invokes a certified same-position clear.

## Current actor input

Feature version is `normalized-public-v2`: 10 global values, 20 channel rows of 9 values, and one 11-value row per candidate. The policy encodes all channel rows with a Transformer and averages them. Every candidate receives the same channel mean. A candidate does not gather its own channel token, a COVER candidate has no exact 20-channel scan mask, and remaining stations have no tokens. Absolute channel ID is embedded in global/candidate scalars, so permutation equivariance is not guaranteed.

## Safety boundary

`CLEARABLE`, certified CLEAR, `ABSENT_CERTIFIED`, and EXIT come only from deterministic geometric state. Planning/search hypotheses do not modify those certificates. Q4 requires valid `no_signal` observations at every certified grid station for a still-unknown channel, or the public upper bound of 16 discovered channels, before absence. A certified clear failure raises and terminates the episode. Hidden source count, coordinates, radius, type, heading, scenario seed, and final-clear truth are absent from controller and actor inputs.

## Frozen baselines

The current Q3 recommendation is `runs/q3_gpu8_extended_20260912/ppo/best.pt`, SHA256 `8cc3a1621334640e6010d8d8fc2cc91a7d47a879573bd54b55fa45a990a56e71`. Its independent 3000-run comparison completed 3000/3000 at 3276.62 mean virtual seconds and 256.69 mean seconds/source.

The current Q4 recommendation is `runs/q4_budget_20260912/train/best.pt`, SHA256 `2329eb4d12088ebccfdc459939aeb8d5ee67f9696b4b41b1385c3c158d4c0e4a`. Its independent 3000-run comparison completed 3000/3000 at 9879.05 mean virtual seconds and 784.35 mean seconds/source on the most recent fresh set.

## Confirmed structural gaps

1. Certified clear candidates use the MEC center even though `safe_point(current)` can preserve safety with less travel.
2. Exact same-channel, same-coordinate LOCALIZE candidates are not suppressed.
3. PROBE_CLEAR advertises `cover[0]` and an original-order cost, then execution greedily reorders all points. Candidate, feature, cost, and actual primitive sequence therefore disagree.
4. A probe is a long indivisible macro. The actor cannot replan after a failed clear updates the feasible region.
5. Coverage planning exposes only three locally nearest stations and has no open-route or insertion cost.
6. Physical station visit and per-channel certificate progress are conflated. Partial scan sets cannot be represented safely.
7. The v2 actor cannot bind actions to channel/station tokens or exact scan sets.
8. Q4 has no public-history directional planning belief. Its safety behavior is conservative and correct, but planning cannot distinguish radius from back-side no-signal explanations.
9. `clear_cover()` is certified but mostly axis-aligned and its point order is not route optimized.
10. The existing search teacher is Q3-only. Q4 cannot reuse its omni assumptions or tensor kernel.
11. Existing research scenarios pair some spatial and error-field strata by seed modulo; they do not provide the fully crossed structural stress matrix requested for final reporting.

The implementation sequence for this run follows the prompt: deterministic waste and action-plan consistency, short probe replanning, open route/insertion, v3 feature binding, Q4 planning belief and scan sets, then ablation, smoke, four-GPU-per-problem training, and new frozen paired tests. The 31-station Q4 safety certificate remains available as fallback throughout. Cumulative directional certification will not be connected online unless a continuous proof and boundary tests pass.
