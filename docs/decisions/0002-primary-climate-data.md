# ADR 0002 — Primary climate data sources

- **Status:** accepted
- **Date:** 2026-05-19

## Context

AIgriculture needs (i) **historical observed climate** for Tier 2 / Tier 3
training and hindcast validation, and (ii) **future climate projections**
for the recommendation. For the Quebec MVP we have several viable options
catalogued in `docs/research/01-data-catalogue.md` §2 and §3.

The choice has to balance: (a) spatial resolution adequate for agricultural
impact (≥ 10 km), (b) cadence adequate for crop modeling (daily), (c)
Canadian-tuned bias correction, (d) multivariate consistency between
temperature and precipitation, (e) open license, (f) Python-friendly
access.

## Decision

### Historical observed climate (training + hindcast)

- **Primary daily driver:** **AgERA5** (Copernicus CDS,
  `10.24381/cds.6c68c9bb`) — 0.1°, daily, 1979 – present, agriculture-
  tailored variable set, CC BY 4.0.
- **High-resolution cross-check:** **Daymet v4** (ORNL DAAC) — 1 km daily
  over North America from 1980; cached locally for Quebec.
- **Station ground truth for hindcast:** **ECCC AHCCD** — daily and
  monthly homogenized observations at Canadian stations under Open
  Government Licence — Canada.
- **Long-term anomaly reference:** **CanGRD** — 50 km gridded anomalies
  from 1900 (southern Canada) / 1948 (all Canada).

### Future projections (recommendation)

- **Primary:** **CanDCS-M6** (Sobie et al. 2024,
  `10.1002/gdj3.257`) — daily, ~6–10 km, 26 CMIP6 GCMs × 4 SSPs
  (SSP1-2.6 / SSP2-4.5 / SSP3-7.0 / SSP5-8.5), MBCn multivariate bias
  correction. Canadian-tuned and multivariate-consistent.
- **Independent cross-check:** **NEX-GDDP-CMIP6** (NASA Ames) — 0.25°,
  daily, BCSD-style bias correction. Streams from AWS Open Data.
- **High-resolution envelope inputs:** **CHELSA-CMIP6** monthly +
  bioclimatic variables at 1 km, for Tier 1 climatic-envelope scoring.
- **GGCMI / ISIMIP3b** stays in reserve for any cross-validation that
  requires alignment with the GGCMI ensemble.

## Consequences

- The Quebec MVP gets the most accurate Canadian-tuned projections
  available; the multivariate MBCn approach preserves T × P joint
  behaviour critical for crop modeling.
- The cross-check against NEX-GDDP-CMIP6 lets us flag any case where
  CanDCS-M6 disagrees substantially with the broader CMIP6 community.
- We assume the burden of obtaining variables (solar radiation, vapor
  pressure) that CanDCS-M6 does not directly downscale: we use AgERA5
  for these in the historical period and a delta-method projection for
  the future period (well-documented technique in the literature).

## Alternatives considered

- **NEX-GDDP-CMIP6 as primary** — globally consistent, BCSD-style; rejected
  for the MVP because its 0.25° resolution is coarser than CanDCS-M6 and
  it is not multivariate-consistent. Kept as cross-check.
- **CHELSA-CMIP6 as primary** — finest resolution (1 km), but monthly
  cadence is insufficient for daily-cadence crop modeling without
  re-disaggregation. Use only for Tier 1 monthly envelope work.
- **EURO/NA-CORDEX** — dynamically downscaled; physically richer but
  smaller GCM coverage and not Canadian-tuned. Save for Phase 4
  cross-validation.
- **ISIMIP3b as primary** — 0.5° resolution insufficient and limited to
  three SSPs. Use only if we explicitly want GGCMI-comparable outputs.

## References

- `docs/research/01-data-catalogue.md` §§2 and 3
- Sobie et al. (2024) *Geosci. Data J.* 11:806–824 — `[@Sobie2024CanDCSM6]`
- Lange (2019) *Geosci. Model Dev.* 12:3055–3070 — `[@Lange2019]`
