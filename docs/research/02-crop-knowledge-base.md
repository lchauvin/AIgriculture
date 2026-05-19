# 02 — Crop knowledge base

> **Status:** stub. To be filled in during Phase 1.
>
> **Goal:** catalogue (a) crop-trait databases — the "what does crop X
> need?" layer — and (b) process-based crop models — the "given climate X
> and soil Y, what yield does crop Z give?" layer. Conclude with a
> decision matrix selecting the primary model(s).

## Part A — Crop trait / requirement databases

To document, with access notes:

- **FAO ECOCROP** — ~2,500 species, but officially discontinued ~2015.
  Access via `gaez.fao.org/pages/ecocrop` and `ecocrop.apps.fao.org`.
  Document available variables (min/max temperature, precipitation, pH,
  photoperiod, salinity, latitude/altitude, soil texture, etc.).
- **FAO GAEZ v4 / v5** — publishes suitability rasters; also publishes
  underlying crop parameters. Useful both as a reference dataset *and* as
  a benchmark for our own model.
- **Sacks et al. 2010 crop calendar** — planting/harvest windows.
- **GGCMI crop calendars** — harmonized for GGCMI intercomparison.
- **USDA PLANTS database** + **USDA Plant Hardiness Zones**.
- **TRY Plant Trait Database**.
- **GBIF**, **GENESYS-PGR / EURISCO**.

Deliverable: a versioned local snapshot of ECOCROP (consider the existing
`EcoCrop-ScrapeR` workflow on GitHub) loaded into a small SQLite or DuckDB
table the rest of the pipeline can query.

## Part B — Process-based crop models

| Model | Language | License | Python integration | Regional calibration (EU / NA / Quebec) | Crop coverage |
|-------|----------|---------|--------------------|-----------------------------------------|---------------|
| **PCSE / WOFOST** | Python | EUPL / open | Native (PyPI `pcse`) | EU-strong | ~10 staple crops |
| DSSAT | Fortran / C | mixed | `pyDSSAT`, `DSSATTools`, etc. | US-strong | ~30 crops |
| APSIM Next Gen | C# | LGPL-like | scriptable | AU / temperate | many |
| AquaCrop | Fortran / Pascal | FAO non-commercial | `aquacrop-ospy` | water-stress driven | major crops |
| STICS | Fortran | INRAE | weak | FR-strong | many |

Cells to be verified during Phase 1.

## Part C — Recommendation

PCSE/WOFOST as the **primary** Tier 2 model. Rationale (to be expanded with
citations):

- Python-native — fits the rest of the stack.
- FAO-lineage — credible.
- Open and well-documented.
- EU calibration set; Quebec parameter availability is a question to assess
  during Phase 1 (a calibration plan against StatCan + ISQ yields will be
  proposed if needed).

DSSAT and APSIM remain on standby for crops not covered by WOFOST and for
ensemble cross-checks once the MVP is up.

## Verification checklist

- [ ] Each database's URL resolves, license is confirmed on source.
- [ ] Each model's repository / website is reachable; license confirmed.
- [ ] For PCSE/WOFOST: at least one minimal end-to-end run executed in a
      notebook (`backend/notebooks/exploratory/`) on synthetic AgERA5 data
      for one Quebec point.
- [ ] BibTeX entries added to `CITATIONS.bib` for each cited source.
