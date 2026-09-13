# Q3/Q4 Structural Optimization Implementation

Date: 2026-09-12. This report records the implemented public-information controller changes.

The frozen baselines are copied under `runs/q34_structural_20260912/baselines` with SHA256 recorded in `runs/q34_structural_20260912/manifest.json`. New experiment seeds are disjoint from every prior evaluation range.

Implemented changes:

- `safe_point()` is used for certified CLEAR candidates and rechecked with `certificate(point)` before execution.
- Exact same-channel, same-coordinate active LOCALIZE measurements are rejected and counted.
- `ProbePlan` fixes probe points and order; candidate position, cost, logs, and execution use that immutable plan.
- `PROBE_STEP` executes one certified cover point and returns for re-planning. `FULL_PROBE_FALLBACK` retains the complete finite cover.
- `plan_open_route()` provides deterministic nearest-neighbor, open-path 2-opt ordering and insertion detour diagnostics.
- Coverage distinguishes physical station visits from per-channel certificate progress and offers conservative scan sets.
- `normalized-public-v3-structural` adds candidate channel/station indices, scan masks, station tokens, and public channel geometry. `StructuralCandidatePolicy` gathers the bound tokens and mask representation explicitly.
- `Q4DirectionalBelief` models no-signal as the disjunction of out-of-radius and directional back-side explanations. It is advisory only and never changes Q4 safety certificates; the certified 31-station fallback remains active.
- Checkpoints now carry explicit model/feature versions; mismatches are rejected. Legacy v2 fixtures remain usable only through the compatibility `CandidatePolicy` path.

The Q4 cumulative directional certificate was not connected online because a continuous proof and boundary audit are not yet complete.

All strategy inputs are derived from accepted public responses. Scenario truth is used only by evaluation metrics and never enters actor/controller decisions.
