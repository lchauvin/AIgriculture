# Brief — codebase review and validation assessment (2026-09-06)

## Goal
Audit the AIgriculture codebase (backend, frontend, tests, tooling, docs) for
correctness, bugs, performance, test coverage, scientific soundness of the
suitability/hindcast logic, maturity, and critical missing features. Assess
whether a retrospective backtest ("data up to year X → predict viable crops
for year Y → confirm against observations") can be run, and run it if the
environment permits. Deliver a written report.

## Constraints given
- Review only; no source changes were requested.
- Do not read `.env` for secrets/ports.

## What exists (established by exploration)
- ~1,570 statements of production Python: `data/` (AgERA5, CanDCS-M6,
  SoilGrids, AAFC ACI loaders), `suitability/` (Tier 1 envelope),
  `crop_models/` (Tier 2 WOFOST-PP), `validation/` (hindcast harness +
  StatCan parser), `api/` (FastAPI, in-memory jobs). `climate/`, `ml/`,
  `uncertainty/` are empty stubs.
- Next.js 14 single-page frontend; builds, lints and type-checks clean.
- 128 pytest tests, all passing, 87 % line coverage; all external I/O mocked.
- Local data: StatCan 32100359 CSV (60 MB), one AAFC ACI 2020 tile.
  `data/cache/agera5/` is empty. No CDS / Earth Engine credentials present.

## Out of scope
- Fixing defects (would be a separate run with its own plan).
- Downloading climate data (needs credentials the machine does not have).

## Open questions (for the human)
- Whether to obtain CDS credentials and run the proposed backtest.
- Whether to schedule a fix run for the blocker/major defects.

## Size and trigger
**S — mode: none.** Deliverable is a report (docs), not code. No source
files change, no contract changes. Fan-out used only for read-only
exploration (3 explore agents, one re-dispatched after an API-credit failure).

## Task table
| ID | Area | Depends on | Acceptance |
|----|------|-----------|------------|
| T1 | docs | — | Baseline established: tests, lint, type-check, build results recorded |
| T2 | docs | T1 | Three exploration reports returned (data/crop-model; suitability/validation/API; frontend/tests/tooling/docs) |
| T3 | docs | T2 | `docs/reviews/2026-09-06-code-review.md` written with findings, severity, backtest design, maturity, gaps |
