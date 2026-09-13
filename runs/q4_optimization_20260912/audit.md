# Q4 optimization execution audit

HEAD `c4876b3ffdd2d2dcd172c2547203cc4fa5c00192`, branch `hy_branch/b45c0d2`.
The workspace contained pre-existing modified and untracked run outputs; they were preserved.

Eight RTX 4090 devices are visible (24,209 MiB free each). The repository virtualenv cannot import torch because `libcusparse.so.12` requires missing/incompatible `libnvJitLink.so.12`; GPU training and GPU certificate search are therefore NOT_RUN and no GPU result is claimed.

Implemented in `solution/rl/environment.py`:

- Per-episode objective reward is now `-ΔT/(100*N)` with N held privately by the trainer environment.
- The selected candidate's belief reception probability is captured before execution and emitted in metrics, replacing the zero placeholder.

The existing structural policy has a Transformer over channels and gather/concat candidate context; it is recorded as a baseline architecture pending a true candidate-query cross-attention implementation. Existing certificate code is a Shapely/grid helper and is not an exact continuous-domain proof; certificate compression remains NOT_RUN.

The CUDA loader issue was resolved for this workspace by prepending the venv `nvidia/nvjitlink/lib` and `nvidia/cusparse/lib` directories to `LD_LIBRARY_PATH`. Torch 2.5.1+cu124 now sees all 8 GPUs; a 4096×4096 CUDA matmul smoke passed. `tests/test_q4_repair.py` passes: 92 tests.

A one episode, one update single GPU PPO smoke completed in 7.4 s with 100% completion. Validation delta was 0; sealed test delta was +139.55 s, so the candidate was not selected. A standalone exact certificate verifier was added; certificate compression remains NOT_RUN because no explicit witness artifact exists.

Exported `layout31.json` from the existing 31-station triangular grid. The independent verifier correctly returned UNKNOWN because no explicit witness cells were supplied. GPU falsification sampled 157,137 points inside the source disk (requested 200,000), found no sampled point with fewer than 7 nearby stations; this is empirical only and does not establish a certificate.
