# Architecture Decision Records

Architecture Decision Records (ADRs) are short, dated, immutable documents
that capture a single architectural choice and the reasoning behind it.
Format and process are described in [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](0001-language-and-stack.md) | Language and stack — Python + Next.js | accepted |
| [0002](0002-primary-climate-data.md) | Primary climate data — AgERA5 + Daymet + CanDCS-M6 | accepted |
| [0003](0003-primary-crop-model.md) | Primary crop model — PCSE/WOFOST | accepted |
| [0004](0004-compute-and-storage.md) | Compute and storage — hybrid STAC + local Zarr (< 300 GB) | accepted |
| [0005](0005-uncertainty-and-scenarios.md) | Uncertainty + SSP / GCM ensemble | accepted |
| [0006](0006-license.md) | License — MIT | accepted |
| [0007](0007-gpu-and-ml-stack.md) | GPU and ML stack — RTX 4070 Ti budget | accepted |

ADRs are append-only. If a decision is revisited, write a new ADR that
supersedes the old one (and update the old one's status to
`superseded by ADR XXXX`).
