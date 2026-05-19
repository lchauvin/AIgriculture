# 03 — Methodology

> **Status:** stub. To be filled in during Phase 1.
>
> **Goal:** present the chosen modeling architecture and justify it against
> the alternatives.

## Three-tier architecture (recommended)

1. **Tier 1 — Climatic-envelope screening.**
   For every species in our ECOCROP snapshot, compute monthly climatic
   suitability against the species' temperature / precipitation / GDD /
   frost-day / aridity requirements under each future climate scenario.
   Output: discrete suitability classes (S1–S4, N) following the FAO GAEZ
   convention. Scales to all ~2,500 species; fast; transparent.

2. **Tier 2 — Process-based yield projection.**
   For the top-N crops surfaced by Tier 1 (and the crops historically
   important in the region), run PCSE/WOFOST under an ensemble of CMIP6
   climate forcings (≥ 5 GCMs × {SSP1-2.6, SSP2-4.5, SSP5-8.5}). Output:
   projected mean yield, yield variability, and stress-year frequency.

3. **Tier 3 — ML bias correction & skill check.**
   Train an XGBoost regressor on historical {climate features} → {observed
   yield} using StatCan / Eurostat / USDA NASS yields. Use it to:
   - bias-correct Tier 2 outputs,
   - and provide an independent skill estimate.

## Sections to write

- The three classes of model evaluated (empirical, mechanistic, hybrid) and
  why a hybrid is justified. Cite Fitzgibbon et al. 2022 [@Fitzgibbon2022]
  on MaxEnt vs Random Forest, and the AgMIP / GGCMI consensus that
  ensembles outperform individuals [@Elliott2015GGCMI].
- The FAO GAEZ methodology in detail — since Tier 1 is a re-implementation
  of GAEZ-style suitability, we owe the reader a clear description of what
  GAEZ does and where our implementation differs.
- How Tiers communicate: what features Tier 1 hands to Tier 2 (shortlist of
  crops + bounding region), and what Tier 2 hands to Tier 3 (gridded yield
  projections + uncertainty estimates).
- Computational budget per region per scenario (one ensemble run, then how
  many runs aggregate to a tile).

## Verification checklist

- [ ] Each cited paper is in `CITATIONS.bib` and verified.
- [ ] A minimal Tier-1 prototype runs in a notebook for one Quebec polygon
      against AgERA5 historical data, producing a sensible suitability
      ranking.
- [ ] An ADR exists (`docs/decisions/0003-primary-crop-model.md`) that
      ratifies the Tier 2 model choice.
