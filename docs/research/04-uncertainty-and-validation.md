# 04 — Uncertainty and validation

> **Status:** stub. To be filled in during Phase 1.
>
> **Goal:** define how AIgriculture quantifies projection uncertainty and
> how the tool is retrospectively validated (the "set yourself back in
> time" requirement).

## Part A — Uncertainty quantification

Follow the Hawkins & Sutton (2009) framework [@HawkinsSutton2009]:

- **Internal variability.** Sample multiple decades / ensemble members.
- **Model uncertainty.** Minimum 5 GCMs from the CMIP6 ensemble.
- **Scenario uncertainty.** SSP1-2.6 / SSP2-4.5 / SSP5-8.5.

Report all three, visualize as fan charts, and surface which source
dominates at the requested projection horizon. Model uncertainty dominates
pre-2050 in most regions; scenario uncertainty dominates post-2070.

To be drafted:
- Specific GCM short-list (favor models with NEX-GDDP-CMIP6 *and* CHELSA
  coverage and Canadian-relevant performance).
- Aggregation strategy: ensemble mean + 10th/90th percentile bands; do not
  collapse to a single number in the UI.
- Communication of "this projection is dominated by {scenario / model /
  internal} uncertainty."

## Part B — Hindcast / retrospective validation

The user's specific requirement: "set yourself back in time, predict
forward, compare to what happened."

To be drafted:

1. **Baseline period.** Train on pre-1990 climate-yield relationships using
   data available at that time (early reanalysis, pre-CMIP3 projections
   where applicable).
2. **Prediction windows.** Project 1991–1995, 1996–2000, 2001–2005,
   2006–2010 and compare to observed crop area / yield.
3. **Validation datasets.**
   - **Quebec / Canada:** StatCan Census of Agriculture (1991, 1996, 2001,
     2006, 2011) + Field Crop Reporting Series. AAFC Annual Crop Inventory
     from 2009 onward.
   - **Europe:** Eurostat NUTS-2.
   - **US:** USDA NASS county.
   - **Global gridded:** GDHY [@IizumiSakai2020].
4. **Cross-validation strategy.** Spatiotemporal CV — leave-one-region-
   leave-one-year-out — not random CV. Random CV overstates skill on
   temporally autocorrelated agricultural data.
5. **Confounders.** Detrend, or run process models with fixed-cultivar
   assumptions, to separate climate signal from technological / cultivar /
   policy change. Reference Rezaei et al. 2018 [@Rezaei2018] for the
   ~50/50 phenology attribution finding; reference the 1992 CAP reform
   and successive US Farm Bills, and the 1996+ GMO adoption wave, as known
   structural breaks.
6. **Skill metrics.** RMSE and bias for yields; Brier score and ROC-AUC for
   discrete suitability classes; honest reporting of resolution mismatch
   (e.g., the StatCan Census is quinquennial).

## Cross-references

- ADR 0002 ratifies the primary climate-projection dataset.
- ADR 0003 ratifies the Tier 2 crop model.
- ADR 0005 (to be written) ratifies the scenario and GCM list.

## Verification checklist

- [ ] At least one full hindcast example produced for one Quebec crop,
      committed as a notebook report.
- [ ] Skill metrics reported with confidence intervals.
- [ ] An explicit comparison against MAPAQ's current regional crop
      recommendations included as a present-day sanity check.
