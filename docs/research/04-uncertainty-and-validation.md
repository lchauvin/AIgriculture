# 04 — Uncertainty and validation

> **Status:** v0.1 — drafted.

## Purpose

Define how AIgriculture quantifies and communicates projection uncertainty,
and how the tool is **retrospectively validated** (the user's specific
"set yourself back in time" requirement).

## Part A — Uncertainty quantification

### A.1 The Hawkins & Sutton (2009) framework

Hawkins & Sutton (2009) [@HawkinsSutton2009] decompose projection
uncertainty into three additive sources:

- **Internal variability** — chaotic year-to-year fluctuations in the
  climate system; irreducible by improving models.
- **Model uncertainty** — disagreement among GCMs about the climate
  response to a given forcing; reducible in principle by better models.
- **Scenario uncertainty** — disagreement about the future emissions
  trajectory; reducible only by socioeconomic / political action.

The balance shifts with projection horizon:

- 2020 – 2040: internal variability dominates.
- 2040 – 2070: model uncertainty dominates.
- 2070 – 2100: scenario uncertainty dominates.

**AIgriculture must report all three and make their relative magnitudes
visible to the user.**

### A.2 Multi-model ensemble

- **Source:** CanDCS-M6 — 26 CMIP6 GCMs across SSP1-2.6 / SSP2-4.5 /
  SSP5-8.5, 24 GCMs for SSP3-7.0.
- **Operating ensemble for Quebec MVP:** start with **all 26** GCMs;
  collapse for visualization to ensemble mean + 10th / 90th percentile
  bands. For computational efficiency in Tier 2, sub-select **5–7 GCMs**
  that (i) span the equilibrium-climate-sensitivity range, (ii) appear
  in CanDCS-M6, NEX-GDDP-CMIP6, and ISIMIP3b (so cross-checks are
  apples-to-apples), and (iii) perform reasonably over the Canadian
  domain according to ECCC's published GCM-screening literature.
- **ADR 0005** (to be written) will ratify the GCM short-list.

### A.3 Multi-scenario set

Standard agricultural impact studies use a stress-test triplet plus one
"middle of the road":

- **SSP1-2.6** — strong mitigation, ~1.5–2 °C warming by 2100.
- **SSP2-4.5** — middle of the road, ~2.7 °C.
- **SSP5-8.5** — high-emissions stress test, ~4.4 °C.
- **SSP3-7.0** — added in 2024 to CanDCS-M6; include for ensemble
  completeness when available.

The UI presents these as **named scenarios** with plain-language framing
("strong mitigation" / "middle road" / "fossil-fuel-driven future") not
opaque codes.

### A.4 Propagating uncertainty through the three tiers

- **Tier 1** — runs once per (scenario × GCM × time window). The
  per-cell suitability score is therefore distributed across the GCM
  ensemble; we report ensemble mean class plus a "robustness" indicator
  (fraction of GCMs that agree on the discrete class).
- **Tier 2** — also runs per (scenario × GCM × time window) but with a
  finite PCSE / WOFOST stochastic spread baked in via inter-annual climate
  variability. Per-crop output is therefore a distribution over (GCM,
  year, scenario).
- **Tier 3** — adds the **bias-correction residual variance** estimated
  from the spatiotemporal-CV residuals as an independent (and often
  comparable in magnitude) source of uncertainty. The final
  recommendation's confidence interval is the convolution of the Tier 2
  ensemble spread and the Tier 3 residual.

### A.5 What we communicate

For each recommendation we surface:

- Median projected yield.
- An "uncertainty fan" (10th – 90th percentile band).
- A breakdown of which source (internal / model / scenario / bias-
  correction residual) dominates — directly answering "is this uncertainty
  reducible by better science, or do we just need to pick a policy
  scenario?"
- A robustness indicator: how many GCMs agree this crop's class shifts
  from S2 to S3 under SSP5-8.5 by 2050, for example.

---

## Part B — Hindcast / retrospective validation (the user's requirement)

The user's explicit ask: "set yourself back in time and verify your
predictions match what we observed today." This is **hindcasting**.

### B.1 Design

1. **Frozen baseline year**: 1990. Use only data that would have been
   available to a researcher in 1990:
   - Pre-1990 observed climate (ECCC AHCCD stations + reanalysis up to
     1990; for older periods, NCEP/NCAR reanalysis is acceptable).
   - The pre-CMIP3 / early-CMIP3-era projection set (where "future"
     projections existed; for some scenarios we use modern CMIP6
     historical runs as a proxy *with that limitation documented*).
   - WOFOST 8.1 with parameter values that are **not** post-1990-cultivar
     informed (use the default WOFOST parameter set with explicit
     documentation of its calibration year).
2. **Forward-project** to 1995, 2000, 2005, 2010 — and 2015 / 2020 once
   StatCan / AAFC ACI provide the validation data.
3. **Compare** against observed:
   - **Quebec FCRS** Table 32-10-0359-01 (annual provincial area / yield).
   - **Census of Agriculture** at the Census Agricultural Region level
     for 1991 / 1996 / 2001 / 2006 / 2011 / 2016 / 2021.
   - **AAFC ACI** annual gridded crop map from 2009 onward (for
     present-day crop-area sanity check).
   - **GDHY** gridded 0.5° yields 1981 – 2016 [@IizumiSakai2020] for the
     four covered crops.
4. **Skill metrics**:
   - For yields — RMSE, bias, R² against observed yields per region per
     year, plus per-decade summary.
   - For suitability classes — Brier score and ROC-AUC on
     observed-vs-predicted discrete class for the top-N crops.
   - Honesty: report skill against the *resolution-matched* observation
     (we cannot meaningfully validate field-level skill against a province-
     wide annual mean — flag that explicitly).

### B.2 Cross-validation strategy

Random K-fold cross-validation overstates skill on agricultural data due
to temporal and spatial autocorrelation (a 2024 *Precision Agriculture*
review formalized this). AIgriculture uses **spatiotemporal CV**:

- **Leave-one-year-out** (LOYO) — train on all years but year *y*,
  predict year *y*. Repeat for each year.
- **Leave-one-region-out** (LORO) — train on all CARs but CAR *r*,
  predict in *r*. Repeat for each CAR.
- **Leave-one-region-one-year-out** (LOROYO) — the most stringent;
  exclude region × year combinations to test generalization across both
  axes simultaneously.

We **always report the LOROYO skill** in addition to LOYO and LORO, and
make clear when the inferior LOYO or LORO would have flattered the model.

### B.3 Disentangling climate from non-climate change

Over 1990–2020, observed yields reflect climate, technology, and
cultivars. Rezaei et al. (2018) [@Rezaei2018] documented for German winter
wheat that **~50% of the phenology change** since 1950 is from cultivar
turnover, not climate. If AIgriculture ignores cultivar drift, it will
attribute climate-explainable yield gains to climate alone — overestimating
its own skill.

**Confounders to control for (Quebec context):**

1. **Cultivar improvement** — corn and soybean genetic gains have been
   ~1%/year in many regions; in cold/short-season Quebec the gain has
   sometimes been larger because new earlier-maturing hybrids open the
   region to crops that were previously borderline. Strategy: run Tier 2
   **with fixed (default) cultivar parameters**, then bias-correct the
   resulting yield trend out in Tier 3 — and document that the residual
   "explained-by-climate" share is what we report.
2. **Management** — fertilization, planting density, pesticides. Difficult
   to disentangle without farm-level records; we assume an aggregate
   linear trend and document it.
3. **Policy events** — CAP reform 1992 (Europe; less relevant for Quebec
   directly but relevant for European expansion), US Farm Bills,
   Canadian Wheat Board changes, supply-management policy. For Quebec,
   note any **major support-program changes** as known structural breaks.
4. **GMO adoption** — Bt corn (mid-1990s in Canada) and Roundup Ready
   soybean (late 1990s) changed effective yield potential. We do not
   attempt to model GMO impacts mechanistically; we flag them as
   structural-break years in the hindcast report.

### B.4 What "validation passed" means

A useful hindcast report communicates:

- **Time-resolved skill** — RMSE / R² per decade for each pilot crop.
- **Trend skill** — does the model recover the *direction* of yield
  trends? (More important than absolute level for climate-impact work.)
- **Geographic skill** — do CARs that experienced the largest climate
  shifts also show the largest model-vs-observation discrepancies (a
  sign that climate signal is real and detectable)?
- **Honest failure modes** — wherever the model under-/over-performs, name
  the suspected reason (cultivar, policy event, missing input).

The deliverable is an HTML / PDF report under
`backend/notebooks/exploratory/hindcast_quebec_<crop>.{ipynb,html}`.

### B.5 Sanity check against MAPAQ recommendations

Present-day expert baseline: do AIgriculture's MVP outputs broadly agree
with MAPAQ's published Quebec regional agronomic guides for which crops
are currently recommended in each Quebec region? Disagreement that
**MAPAQ is right and we are wrong** is a deal-breaker; disagreement that
**MAPAQ is current-day and we are projecting a near-future shift** is a
feature.

---

## Part C — Open questions for Phase 3

1. **Pre-1990 reanalysis for hindcast.** ERA5 starts in 1940 — sufficient.
   Pre-1990 daily AgERA5 covers from 1979. For periods before 1979, the
   choice is NCEP/NCAR or 20CRv3. Decide which.
2. **GCM "vintage" for hindcast.** Using current CMIP6 historical runs to
   represent a 1990 forecast is anachronistic but unavoidable. Document
   it and discuss the implications in the hindcast report.
3. **Cultivar-trend module.** Phase 4 work — explicitly modelling the
   yield-bump from cultivar improvements would let us attribute more
   cleanly. Until then we lean on Tier 3 ML to absorb the trend.

## Cross-references

- 03-methodology.md — the three-tier architecture this document validates.
- ADR 0005 — GCM short-list and scenario set.
- `aigriculture.validation` package — the hindcast harness.

## Verification checklist

- [ ] Hindcast harness runs end-to-end for one Quebec CAR × one crop ×
      one historical window (e.g., 1990 → 2000 for grain corn in CAR
      Montérégie).
- [ ] Per-decade RMSE, bias, R² reported.
- [ ] LOYO / LORO / LOROYO skill all computed and compared.
- [ ] Structural-break years (GMO adoption, major policy changes) flagged
      in the report.
- [ ] Each citation above resolves to a verified BibTeX entry.
