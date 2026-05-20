# 03 — Methodology

> **Status:** v0.1 — drafted.

## Purpose

Define the modeling architecture AIgriculture will implement, justify it
against the alternatives, and specify the contract between the three
modeling tiers. This document drives ADR 0003 (primary crop model) and
the package layout under `backend/aigriculture/{suitability,crop_models,ml,uncertainty}/`.

## Why three tiers?

A literature survey of climate-driven crop suitability modeling identifies
three classes of approach, each with intrinsic limitations that the
others compensate for:

1. **Empirical / statistical models** (MaxEnt, Random Forest, XGBoost) —
   fast, interpretable, validate well on **in-sample** climates. Their
   structural assumption is **stationarity** of the climate-yield (or
   climate-presence) relationship. Under novel future climates, that
   assumption is questionable. Fitzgibbon et al. (2022) [@Fitzgibbon2022]
   showed MaxEnt outperforms Random Forest for corn suitability while
   sharing this stationarity weakness.

2. **Mechanistic / process-based models** (WOFOST, DSSAT, APSIM,
   AquaCrop) — capture phenology, water balance, nitrogen explicitly. They
   extrapolate to novel climates more credibly. Their weakness is **regional
   calibration cost** — default parameter sets carry the bias of the data
   they were calibrated on. AgMIP / GGCMI work [@Elliott2015GGCMI] documents
   model spreads of ±30–50% of the ensemble mean in some regions.

3. **Hybrid approaches** — process models bias-corrected against observed
   yields, or ML-emulators of process-model output. Yin et al. (2025,
   *Earth's Future*) showed that even the *choice of ensemble averaging
   method* injects ±10–20% uncertainty into projected yields.

The AgMIP / GGCMI consensus is that **ensembles outperform individuals**
and that combining mechanistic with statistical thinking is necessary for
credible projections. AIgriculture mirrors that consensus by structuring
the computation as three tiers that consume each other's outputs.

## Tier 1 — Climatic-envelope screening (GAEZ-style)

**Goal:** rapidly, for every species in the ECOCROP snapshot (~2,500
species), score climatic suitability under each scenario across the user's
selected region. The output is the **shortlist** of crops that warrant
the expensive Tier 2 process modeling.

**Inputs:**
- Future projections from CanDCS-M6 (primary) or NEX-GDDP-CMIP6 (global)
  or CHELSA-CMIP6 (1 km monthly bioclim), aggregated to the analysis
  resolution.
- ECOCROP per-species requirements: T<sub>min</sub>, T<sub>opt-low</sub>,
  T<sub>opt-high</sub>, T<sub>max</sub>; precipitation min / max; pH range;
  photoperiod; frost tolerance; latitude band; growing-degree-day target;
  cycle length.
- Per-region annual derived indicators (computed via `xclim`):
  growing-degree days (multiple base-temperature variants),
  frost-day count, mean precipitation by growing-season month,
  aridity index, length of frost-free period.
- Soil pH and texture from SoilGrids 2.0 (for the pH-range and
  texture-range filters).

**Algorithm (GAEZ-style):**

For each species s and grid cell g and scenario × time-window:

1. Compute monthly temperature suitability:
   - 0 below T<sub>min</sub> or above T<sub>max</sub>.
   - linear ramp from T<sub>min</sub> → T<sub>opt-low</sub>.
   - 1 in [T<sub>opt-low</sub>, T<sub>opt-high</sub>].
   - linear ramp from T<sub>opt-high</sub> → T<sub>max</sub>.
2. Compute precipitation suitability analogously over the species' rainfall
   range.
3. Combine T and P suitabilities multiplicatively (or via the GAEZ-style
   minimum operator — both are documented; the implementation must support
   either, configurable per crop).
4. Aggregate to a growing-season score weighted by the species' month-by-
   month requirements.
5. Mask by:
   - frost-day count > species frost-tolerance threshold,
   - growing-season length < cycle length,
   - latitude outside species' band,
   - soil pH outside species' range.
6. Discretize the continuous score into S1 / S2 / S3 / S4 / N classes
   following GAEZ conventions.

**Output of Tier 1:**
For each (scenario, time-window), a ranked list of species with
(continuous suitability score, discrete class, dominant limiting factor)
per cell, plus a region-aggregated ranking. The top **N = 10 to 30**
species feed Tier 2.

**Why GAEZ-style and not pure MaxEnt:**
- Transparent and decomposable — every prediction can be traced back to
  the limiting factor(s). Critical for the research-audience component.
- No training data required — works for crops with no historical presence
  in the region (the entire point of climate-shift recommendations).
- Calibrates against GAEZ v5 published rasters as a sanity check.

**Implementation location:** `backend/aigriculture/suitability/`.
- `envelope.py` — the scoring core.
- `gaez_classes.py` — class discretization.
- `limiting_factors.py` — explainability hooks.
- Configurable per-crop scoring profile loaded from
  `data/ecocrop_v2015_snapshot.db`.

## Tier 2 — Process-based yield projection (PCSE / WOFOST)

**Goal:** for the Tier 1 shortlist of top-N crops, produce gridded yield
projections (mean, variability, stress-year frequency) under the climate
ensemble. Process-based modeling buys us credible extrapolation to novel
climate combinations that the empirical Tier 3 cannot.

**Inputs:**
- For each ensemble member (GCM × SSP × time window): daily Tmin / Tmax /
  precipitation / solar radiation / vapor pressure (from CanDCS-M6 +
  AgERA5-derived radiation / vapor where CanDCS-M6 lacks those variables;
  CHELSA-W5E5 1 km daily forcing is a fallback / cross-check).
- Per-cell soil profile from SoilGrids 2.0 (texture, organic carbon,
  rooting depth, AWC) translated into PCSE soil parameter files.
- Per-crop WOFOST parameter file from
  `ajwdewit/WOFOST_crop_parameters` (default; potentially recalibrated for
  Quebec — see §C calibration gap in the crop knowledge base).
- Agromanagement: sowing date per crop per region (Sacks / GGCMI calendars
  refined against MAPAQ guides).

**Algorithm:**
- Run PCSE WOFOST 8.1 (with N dynamics) for each (cell × crop × ensemble
  member × year), under a "potential" or "water-limited" production
  scenario (configurable; we will default to water-limited for Quebec —
  irrigation is not the norm there).
- Aggregate per (region × crop × scenario × time window): mean yield,
  standard deviation across years, count of "low-yield" years (below 20th
  percentile of the same crop's historical distribution).

**Why WOFOST:**
- See ADR 0003 (to be written). Summary: Python-native, EUPL-licensed, 23
  crops including every Quebec staple, FAO lineage, the model behind the
  EU MARS operational system.

**Implementation location:** `backend/aigriculture/crop_models/`.
- `wofost_runner.py` — orchestrates PCSE runs.
- `soil_translator.py` — SoilGrids → PCSE soil file.
- `agromanagement.py` — sowing-date / management generation.
- `parameter_calibration.py` — Quebec-specific calibration of WOFOST
  parameters against StatCan FCRS yields (Phase 1 sub-task).

## Tier 3 — ML bias correction and skill estimation (XGBoost)

**Goal:** correct Tier 2 outputs against observed historical yields and
produce an independent skill estimate that does not rely on the process
model's structural assumptions.

**Inputs (training):**
- Features per (region × year): the same climate / soil / management
  features that Tier 2 sees, plus aggregate phenology indicators from
  Tier 1 (GDD, frost days, etc.) and Tier 2's simulated yield.
- Target: observed yield from StatCan FCRS Table 32-10-0359-01 (Quebec
  pilot) — extending later to USDA NASS / Eurostat / GDHY.

**Inputs (inference):**
- The same features computed for the user-selected region under each
  scenario × time-window.

**Algorithm:**
- `xgboost` regressor, `device=cuda` (RTX 4070 Ti available).
- Spatiotemporal cross-validation (leave-one-CAR-one-year out): random CV
  on temporally autocorrelated agricultural data overstates skill (see
  04-uncertainty-and-validation.md and the 2024 *Precision Agriculture*
  review).
- Output: a bias-corrected expected yield, plus a per-prediction skill
  estimate (RMSE on the spatiotemporal-CV residuals).
- Optional Phase 4: a small PyTorch MLP / transformer emulator of the
  Tier 2 process model, trained on a precomputed Tier 2 ensemble to allow
  the UI to respond instantly to user region selection without re-running
  WOFOST. 12 GB VRAM is sufficient for the model sizes we'd consider.

**Why XGBoost first and PyTorch later:**
- XGBoost: tabular, robust, easy to validate, GPU-accelerated; matches the
  feature volume we'll have for the Quebec MVP (single-digit Mrows).
- Deep models: overkill for tabular features but useful as emulators
  for compute-time reduction once Tier 2 is stable.

**Implementation location:** `backend/aigriculture/ml/`.

## Tier-to-tier contract (data flow)

```
       ┌────────────────────────────────────────────────────────┐
       │  CanDCS-M6 / AgERA5 / Daymet / SoilGrids / DEM / ACI   │
       └────────────────────────────────────────────────────────┘
                            │
                            ▼
          ┌─────────────────────────────────────┐
          │  aigriculture.climate.indicators    │
          │  (GDD, frost days, aridity, etc.    │
          │   computed via xclim)               │
          └─────────────────────────────────────┘
                            │
       ┌────────────────────┼────────────────────┐
       ▼                    ▼                    ▼
┌──────────────┐    ┌────────────────┐   ┌───────────────┐
│  Tier 1      │    │ Tier 2 input    │   │ Tier 3 input  │
│  envelope    │    │ assembly        │   │ feature build │
│  screening   │    │                 │   │               │
│              │    │                 │   │               │
│  Output:     │    │                 │   │               │
│  top-N crops │───▶│                 │   │               │
└──────────────┘    └────────────────┘   └───────────────┘
                            │                    │
                            ▼                    │
                    ┌────────────────┐           │
                    │  Tier 2        │           │
                    │  PCSE/WOFOST   │           │
                    │                │           │
                    │  Output:       │           │
                    │  ensemble      │           │
                    │  yield grids   │───────────┤
                    └────────────────┘           │
                                                 ▼
                                        ┌────────────────┐
                                        │  Tier 3        │
                                        │  XGBoost       │
                                        │  bias correct  │
                                        │                │
                                        │  Output:       │
                                        │  final ranked  │
                                        │  recommendation│
                                        │  + uncertainty │
                                        │  + skill score │
                                        └────────────────┘
```

**Inter-tier interfaces:**

- **Tier 1 → Tier 2:** a JSON / Parquet object containing:
  - `region`: GeoJSON polygon + region ID.
  - `scenario`: SSP code.
  - `time_window`: e.g., `2030-2040`.
  - `candidates`: ordered list of `{crop_id, ecocrop_score, dominant_limiter}`.
  - `tier1_diagnostics`: per-cell suitability grids for the candidates
    (Zarr path).

- **Tier 2 → Tier 3:** a Parquet table with:
  - Per `(region, year, scenario, gcm, crop)`: simulated yield, water-
    stress days, frost stress days, growing-degree days, etc.
  - Auxiliary: matching observed yield where available (for training).

- **Tier 3 → API:** ranked list of `{crop, expected_yield,
  uncertainty_band (10th–90th pct), skill_score, key_drivers}` plus
  visualization-ready Zarr grids.

## Computational budget

A rough estimate for one Quebec recommendation request:

- **Tier 1** — for ~2,500 species × 5 SSPs × 5 time windows × ~10,000
  10-km cells in a Quebec sub-region: ~12 GB of intermediate raster I/O
  but is **embarrassingly parallel** and arithmetic-cheap. ~30 s on a
  multi-core CPU with `dask`.
- **Tier 2** — for the top-N crops (say 20) × 5 SSPs × 5 GCMs × 30 years
  × 10,000 cells: ~500,000–3,000,000 WOFOST runs. At ~5 ms per run, that's
  ~1–4 hours wall-clock on a single CPU; **must** be either precomputed
  per region and cached, or parallelized via `dask` / a job queue. This is
  the budget driver and the reason the MVP architecture has a background-
  job system (`arq`).
- **Tier 3** — XGBoost training on the order of seconds; inference on the
  order of milliseconds per prediction; per-region precomputation is
  optional.

Phase 3 will therefore implement **on-demand Tier 1 + pre-computed Tier 2
tiles + on-demand Tier 3**.

## Cross-references

- ADR 0002 (climate data) — choice of CanDCS-M6 + NEX-GDDP-CMIP6
  cross-check; CHELSA-CMIP6 1 km for envelope screening.
- ADR 0003 (primary crop model) — choice of PCSE/WOFOST.
- ADR 0005 (scenarios + GCMs) — choice of SSP set and the ~5–7 GCM
  short-list.
- 04-uncertainty-and-validation.md — uncertainty propagation through the
  three tiers; hindcast harness.

## Verification checklist

- [ ] A Tier 1 envelope prototype runs for one Quebec polygon under one
      SSP, producing a sensible ranked list for the top-N species.
- [ ] A Tier 2 PCSE smoke test runs for one CAR × one crop × one year
      using AgERA5 historical data.
- [ ] A Tier 3 XGBoost end-to-end loop runs against StatCan FCRS Quebec
      yields and reports a spatiotemporal-CV skill metric.
- [ ] Tier 1 output broadly agrees with GAEZ v5 published suitability for
      maize / soybean / wheat in Quebec (within a class).
