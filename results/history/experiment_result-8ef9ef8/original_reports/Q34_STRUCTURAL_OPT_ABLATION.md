# Q3/Q4 Structural Optimization Ablation

The run is staged. E0 is the frozen baseline recorded in `Q34_STRUCTURAL_OPT_BASELINE_AUDIT.md`. E1 (safe point, exact dedup, ProbePlan), E2 (short probe), E3 (open route), and E4-E7 (feature binding, station tokens, Q4 planning belief, adaptive scan sets) are implemented in the current source and passed focused unit tests.

Current evidence:

- Focused controller, Q4 repair, search schema, and DDP synchronization tests: passed.
- Full repository test suite: passed under `scripts/run_python.sh -m pytest -q`.
- Q3 teacher smoke on two isolated seeds: 2/2 complete; virtual times 3708.76 s and 4423.86 s.
- Q4 representative teacher smoke (N=10, area, zero error): complete, 9876.25 s virtual time, 60 macros.
- Four-GPU Q3 DDP smoke reached BC with 100% baseline completion (16/16), 741 macros, and `parameter_and_optimizer_sync=true`; it was stopped before PPO because the old CPU teacher rollout took over two minutes per small campaign and this source does not yet use the structural v3 trainer.

No final checkpoint is selected from these diagnostics. A paired 3000-scenario final comparison is pending structural v3 training and isolated validation.
