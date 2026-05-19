# Architecture Decision Records

Architecture Decision Records (ADRs) are short, dated, immutable documents
that capture a single architectural choice and the reasoning behind it.
Format and process are described in [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](0001-language-and-stack.md) | Language and stack — Python + Next.js | accepted |
| 0002 | Primary climate-projection dataset | _to be written_ |
| 0003 | Primary crop model — PCSE/WOFOST | _to be written_ |
| 0004 | Compute and storage — hybrid STAC + local Zarr (<~300 GB) | _to be written_ |
| 0005 | Scenarios and GCM ensemble | _to be written_ |
| [0006](0006-license.md) | License — MIT | accepted |
| 0007 | GPU and ML stack — RTX 4070 Ti budget | _to be written_ |

ADRs are append-only. If a decision is revisited, write a new ADR that
supersedes the old one (and update the old one's status to
`superseded by ADR XXXX`).
