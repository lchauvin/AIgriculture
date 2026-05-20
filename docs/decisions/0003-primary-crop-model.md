# ADR 0003 — Primary crop model (Tier 2)

- **Status:** accepted
- **Date:** 2026-05-19

## Context

Tier 2 of the AIgriculture pipeline runs a process-based crop model under
ensemble climate forcings to produce yield projections. The choice
between WOFOST (PCSE), DSSAT, APSIM Next Generation, AquaCrop, and STICS
is documented in `docs/research/02-crop-knowledge-base.md` §B.

Requirements:
- Open source (or free with no commercial-use restriction).
- Python-native or Python-wrapped without heavy native dependencies.
- Parameter sets for **every Quebec MVP pilot crop** (corn, soybean,
  spring wheat, canola).
- Reasonable computational cost (we anticipate ~1–3 M runs for a Quebec
  recommendation request).
- Documented scientific pedigree.

## Decision

**Use PCSE / WOFOST as the primary Tier 2 model.**

- Library: `pcse` (PyPI), current version **6.0**, implementing
  **WOFOST 8.1** with full crop N dynamics (plus WOFOST 7.3 for legacy
  comparability).
- Parameter sets: `ajwdewit/WOFOST_crop_parameters` (23 crops; every
  Quebec staple included).
- License: European Union Public License (EUPL). Compatible with our MIT-
  licensed code (EUPL is a "weak copyleft" that we satisfy by linking
  unmodified PCSE as a dependency).
- Production scenario: **water-limited** by default for Quebec (irrigation
  is not the norm in Quebec for the pilot crops).
- Soil: SoilGrids 2.0 properties translated to PCSE soil parameters via
  `aigriculture.crop_models.soil_translator`.

**Reserves for ensemble cross-checking and crops outside WOFOST:**

- **DSSAT 4.8.5** — community Python wrapper (`pyDSSAT`, `DSSATTools`);
  add when expanding beyond Quebec staples (Phase 4).
- **AquaCrop-OSPy v3.0.x** (Apache-2.0) — for water-stress-driven
  modeling and as a Tier 2 cross-check for crops where water is the
  primary limiter.

**Not selected:**

- **APSIM Next Generation** — the apsimNGpy wrapper is excellent
  technically, but the APSIM core's commercial-use license terms are
  unclear at the time of writing and conflict with our open-source-only
  constraint until resolved. Re-evaluate in Phase 4.
- **STICS** — weak Python integration outweighs the regional benefits.

## Consequences

- We accept that WOFOST default parameter sets are calibrated against
  European cultivars; a **Quebec calibration sub-task** is planned for
  Phase 1 / Phase 3 (compare WOFOST defaults to StatCan FCRS observed
  yields; document bias; recalibrate or bias-correct in Tier 3 as
  appropriate).
- We accept that water-limited production is the default; irrigation
  expansion in Quebec (currently small) is a Phase 4 consideration.

## Verification

- Smoke test: PCSE WOFOST run for one Quebec Census Agricultural Region ×
  grain corn × 1990 driven by AgERA5; sensible yield (cf. StatCan FCRS).
- Bias diagnostic: compare WOFOST default output to StatCan FCRS for the
  four pilot crops over 1990–2020.

## References

- `docs/research/02-crop-knowledge-base.md` §B and the decision matrix.
- `https://pcse.readthedocs.io/en/stable/`
- `https://github.com/ajwdewit/WOFOST_crop_parameters`
