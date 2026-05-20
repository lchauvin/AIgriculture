# ADR 0005 — Uncertainty quantification and SSP / GCM ensemble

- **Status:** accepted
- **Date:** 2026-05-19

## Context

AIgriculture must report projection uncertainty in a way that is both
scientifically credible and understandable to a non-specialist audience.
Without explicit uncertainty, climate projections degenerate into spurious
precision and undermine the tool's value. See
`docs/research/04-uncertainty-and-validation.md` for the methodology.

## Decision

### Uncertainty framework

Adopt the **Hawkins & Sutton (2009) decomposition** [@HawkinsSutton2009]
into internal variability, model uncertainty, and scenario uncertainty.
Report all three; explicitly identify which dominates at the requested
horizon.

### Standard SSP set

For every recommendation request, AIgriculture runs:

- **SSP1-2.6** — strong mitigation (~1.5–2 °C by 2100).
- **SSP2-4.5** — middle of the road (~2.7 °C).
- **SSP5-8.5** — high-emissions stress test (~4.4 °C).
- **SSP3-7.0** — added in 2024 to CanDCS-M6; included when available.

These match the IPCC AR6 "core" SSP scenarios used in the agricultural
impact literature.

### GCM short-list (provisional — to be ratified before Phase 3 code)

A short-list of **5–7 CMIP6 GCMs** balances ensemble breadth and
computational tractability. Criteria:

1. Present in **CanDCS-M6**, **NEX-GDDP-CMIP6**, **and ISIMIP3b** (so
   cross-checks are apples-to-apples).
2. Span the equilibrium-climate-sensitivity (ECS) range from the CMIP6
   "low" (~2.5 °C) to "high" (~5 °C) family — including at least one of
   the "hot-model" cluster that ECCC researchers commonly include with
   appropriate weighting.
3. Reasonable performance over the Canadian domain (no obvious cold-bias
   pathologies that would dominate hindcast errors).

**Initial candidate set** (to be locked in during Phase 1 implementation
of the climate ingestion layer):

- CanESM5 (Canadian — natural fit).
- MPI-ESM1-2-LR.
- MIROC6.
- NorESM2-MM.
- GFDL-ESM4.
- EC-Earth3.
- UKESM1-0-LL (hot-model cluster representative).

The final list — including the choice of `r{i}i1p1f1` ensemble members —
will be appended to this ADR before any Tier 2 production runs.

### Communication in the UI

- **Default view:** ensemble mean + 10th-90th percentile fan chart, with
  a panel labeling the dominant uncertainty source.
- **Drill-down:** per-GCM lines on demand; per-SSP comparison view.
- **No single-scenario point estimates** anywhere in the UI.

## Consequences

- A Quebec recommendation request runs **7 GCMs × 4 SSPs × 5 time
  windows** = up to 140 ensemble members per crop in Tier 2; mitigated by
  per-region precomputation.
- Storage budget for the per-region ensemble fits within the local Zarr
  cache plan (ADR 0004).
- The UI must be designed so the multi-dimensional ensemble doesn't feel
  overwhelming to a non-specialist. Defer to UX work in Phase 3.

## Alternatives considered

- **Single SSP (e.g., SSP2-4.5).** Cheaper, but single-scenario
  projections are scientifically misleading. Rejected.
- **Full CanDCS-M6 ensemble (26 GCMs).** Most rigorous; rejected for the
  MVP on computational grounds (`26 × 4 × 5 = 520` members per crop per
  region). We will, however, run the full ensemble for the **Tier 1
  envelope** screen (cheap) and the short-list for **Tier 2 process
  modeling**.
- **2 ° / 1.5 ° / 3 ° target-warming framing** (à la the IPCC SR1.5
  framework). Useful for policy framing; we report the warming level the
  SSP/scenario produces by 2100 alongside the SSP label for context.

## Verification

- Hindcast uncertainty bands cover observed yields with the nominal
  frequency (e.g., 80% of observed Quebec yield years fall inside the
  10th–90th band) — a calibration check on the ensemble itself.
- Hawkins-Sutton diagnostic plot generated for at least one Quebec crop
  before sign-off.

## References

- `docs/research/04-uncertainty-and-validation.md` Part A.
- Hawkins & Sutton (2009) `[@HawkinsSutton2009]`.
