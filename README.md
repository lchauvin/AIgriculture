# AIgriculture

> A climate-adaptive crop recommendation tool: select a region in Europe or
> North America and get a ranked, uncertainty-aware list of crops likely to
> thrive there over the next 5–10 years, accounting for climate-change
> projections from the CMIP6 ensemble.

## Status

**Phase 1 — Research.** No application code yet; this repository currently
holds documentation, Architecture Decision Records, and citation infrastructure.
The full plan lives in `~/.claude/plans/i-want-to-start-partitioned-newt.md`.

## What it does (target functionality)

1. **Region selection.** A user draws a polygon on a map of Europe or North
   America (the MVP focuses on Quebec / eastern Canada).
2. **Data ingestion.** Open Earth-observation, climate-reanalysis, climate-
   projection, soil, topography, and historical crop-yield data are pulled
   from cloud STAC catalogs or local Zarr caches.
3. **Three-tier modeling.**
   - **Tier 1 — Climatic-envelope screening.** GAEZ-style monthly suitability
     computed against FAO ECOCROP requirements for ~2,500 species.
   - **Tier 2 — Process-based yield projection.** PCSE/WOFOST run on a
     short-list of crops under an ensemble of CMIP6 climate forcings.
   - **Tier 3 — ML bias correction.** XGBoost trained on historical
     Statistics Canada / Eurostat / USDA NASS yields cross-checks and
     corrects Tier 2 outputs.
4. **Uncertainty quantification.** Hawkins & Sutton (2009) decomposition into
   internal, model, and scenario uncertainty. Standard scenarios:
   SSP1-2.6, SSP2-4.5, SSP5-8.5; ≥ 5 GCMs.
5. **Retrospective validation.** A hindcast harness lets the tool be
   "set back in time" (train on pre-1990 data, predict 1990–2010, compare
   against observed yields and AAFC crop inventories).

## Stack

- **Backend** — Python 3.11+, FastAPI, `xarray` / `rioxarray` / `dask` /
  `zarr`, `pcse` (WOFOST), `xgboost`, `pystac-client`, `stackstac`, `xclim`,
  `cdsapi`. GPU-accelerated where helpful (RTX 4070 Ti, 12 GB VRAM).
- **Frontend** — Next.js 14 (App Router), `react-map-gl` + MapLibre GL JS,
  Recharts / Visx for uncertainty fan charts.
- **Data** — PostGIS for vector + metadata; Zarr for gridded data (local
  when under ~300 GB per dataset, otherwise streamed from STAC).
- **License** — MIT (see [`LICENSE`](LICENSE)).

## Documentation

- [`docs/research/`](docs/research) — Phase 1 deliverables.
  - `01-data-catalogue.md` — every dataset under consideration, with
    resolution / coverage / access / license / citation.
  - `02-crop-knowledge-base.md` — crop-trait databases and process-based
    crop models.
  - `03-methodology.md` — three-tier modeling architecture and why.
  - `04-uncertainty-and-validation.md` — Hawkins-Sutton, hindcast plan.
  - `05-existing-tools-survey.md` — what already exists (FAO GAEZ, CCAFS,
    JRC MARS, etc.) and how AIgriculture differs.
- [`docs/decisions/`](docs/decisions) — Architecture Decision Records.
- [`CITATIONS.bib`](CITATIONS.bib) — BibTeX entries underpinning every claim
  in the research docs. Cite-and-verify discipline: no source, no claim.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The core disciplines:

1. **Research before code.** Implementation follows from documented design
   and cited evidence, not the other way around.
2. **Cite and verify.** Every factual claim in `docs/research/*.md` resolves
   to a primary source in `CITATIONS.bib`. URLs are tested; DOIs resolve.
3. **Open source, free tier only.** No paid APIs or proprietary datasets.

## Acknowledgements

Built atop the open-data ecosystems of Copernicus / ESA, NASA, USGS, ECCC,
NRCan, ISRIC, the FAO, AAFC, Statistics Canada, Eurostat, USDA NASS, ISIMIP,
the AgMIP community, and the broader scientific Python and PyData stacks.
