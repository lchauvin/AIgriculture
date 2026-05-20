# ADR 0007 — GPU and ML stack

- **Status:** accepted
- **Date:** 2026-05-19

## Context

The user has an **NVIDIA RTX 4070 Ti (12 GB VRAM)** available locally and
is willing to use it for ML training and inference. AIgriculture's ML
needs sit in Tier 3 (bias correction) and in optional Phase 4 work
(process-model emulators, EO-feature deep models). We need to commit to a
stack that uses this GPU well and stays inside the 12 GB VRAM budget.

## Decision

### Primary ML library: `xgboost` (GPU)

- For Tier 3 bias correction, the feature volume is tabular and on the
  order of low-millions of rows (region × year × crop × scenario × GCM).
- Use `xgboost` with `device="cuda"` and `tree_method="hist"`. This
  comfortably fits within 12 GB VRAM for our problem size.
- Cross-validation: spatiotemporal (see ADR 0005, §B.2 of
  04-uncertainty-and-validation.md).

### Secondary: `scikit-learn` + `lightgbm`

- `scikit-learn` for baselines and pipeline-management — CPU.
- `lightgbm` (with GPU support) as an XGBoost cross-check; not load-bearing.

### Phase 4 deep models: PyTorch

- Reserved for:
  - **Process-model emulators.** Train a small MLP / Transformer on the
    pre-computed Tier 2 (PCSE/WOFOST) ensemble so the UI can respond at
    interactive latency without re-running WOFOST. The target model size
    is small (< 50 MB) and will fit easily.
  - **EO-feature models** for crop classification (cross-checks against
    AAFC ACI) — Phase 4 if needed.
- Install: `torch` with the matching CUDA 12.x build (`uv pip install
  torch --index-url ...`).
- Use **mixed precision** (`torch.cuda.amp`) by default when training, to
  stretch the 12 GB budget on image-based workloads.

### Other GPU-accelerated tools (optional)

- `cupy` for any explicit GPU NumPy work.
- RAPIDS (`cudf`, `cuml`) — investigate but **not required** for the MVP.

## VRAM budget guidance

- Always report VRAM peak (`nvidia-smi` snapshots) when adding a new model.
- For any deep model, prefer:
  - Mixed precision (`torch.cuda.amp`).
  - Gradient checkpointing for large transformer training.
  - Batch sizes set so peak VRAM stays under 10 GB (leaving headroom).
- If a model truly cannot fit, document why and either (i) reduce model
  size or (ii) train on CPU at lower iteration count and accept the
  slower turnaround.

## Reproducibility and pinning

- Pin `xgboost`, `torch`, `cupy`, and `cuda-toolkit` versions in
  `pyproject.toml`'s `ml` extra.
- Document the CUDA driver / toolkit / Python combo in a top-level
  `docs/architecture/cuda-env.md` (to be written when the first ML code
  lands).

## Consequences

- The MVP's heavy lifting fits in 12 GB. We have a clear escalation path
  if Phase 4 needs more — multi-GPU rental on a Spot instance, or
  CPU-only fallbacks — but we do not pre-optimize for it.
- We commit to CUDA-based ML; if the workstation changes (e.g., to an AMD
  GPU), expect a small but non-trivial rework.

## Alternatives considered

- **CPU-only.** Would slow XGBoost training noticeably; PyTorch deep
  models infeasible. Rejected given a GPU is available.
- **JAX.** Excellent on the workstation but a smaller ecosystem and
  steeper onboarding cost for collaborators. Reserved for Phase 4
  experimentation.
- **RAPIDS as primary.** Strong on tabular ML but immature for our
  geospatial pre-processing needs. Optional.

## Verification

- `nvidia-smi`, `python -c "import torch; print(torch.cuda.is_available())"`,
  and `python -c "import xgboost as xgb; xgb.DeviceQuantileDMatrix"`
  all succeed in the project's dev environment.
- First XGBoost run produces a reproducible (`random_state` pinned)
  baseline against StatCan FCRS Quebec corn yields.
