# Q3 source-count evaluation preflight

The requested final model is `runs/q3_gpu8_extended_20260912/ppo/best.pt`,
SHA256 `8cc3a1621334640e6010d8d8fc2cc91a7d47a879573bd54b55fa45a990a56e71`.
The earlier answer pointing to `runs/q3_current_best_eval_20260912/current_best.pt`
was incorrect: that is the intermediate 3289.21 s/episode checkpoint.
The final model's original report records 3276.6193848973335 s/episode.

Source was exported from Git HEAD `9bf8830` into `source/`. Before evaluation,
every solution/bsim file in the model's provenance was checked against SHA256.
All matched. The current working controller/features were not used or modified.

Four original final-test scenes were replayed with identical virtual times:

| Seed | Original seconds | Replayed seconds |
|---|---:|---:|
| 419000000 | 3625.380345 | 3625.380345 |
| 419000001 | 4042.182589 | 4042.182589 |
| 419000002 | 1297.283130 | 1297.283130 |
| 419000003 | 3698.075516 | 3698.075516 |

Fixed-count smoke: N=10, seed=710000000 completed at 2792.472584 s;
N=16, seed=710060000 completed at 3053.215264 s.
These smoke scenes use the same frozen model and are rerun in the final dataset;
no model fitting, selection or tuning occurred.

Full evaluation: 1000 fresh seeds per N=10..16 (7000 episodes), fixed public
research distribution. N is used only in the simulator generator, not policy
inputs. Six figures cover all seven strata: five single panels for N=10..14
and a two-panel figure for N=15 and N=16. Results are LOCAL-RESEARCH.
