# 02 — Crop knowledge base

> **Status:** v0.1 — drafted with verified primary sources.

## Purpose

For AIgriculture to recommend crops, it needs two layers of crop
knowledge:

- **Part A — Crop trait / requirement databases:** "what does crop X
  need?" (temperature window, precipitation requirement, frost tolerance,
  soil pH, photoperiod, etc.).
- **Part B — Process-based crop models:** "given climate X and soil Y,
  what yield does crop Z give?" (mechanistic simulators that account for
  phenology, water balance, nutrients).

This document catalogues both layers, scores the candidates, and concludes
with concrete recommendations for the Quebec MVP.

---

## Part A — Crop trait & requirement databases

### A.1 FAO ECOCROP

- **Provider:** Food and Agriculture Organization of the UN, originally
  developed in the 1990s.
- **What it provides:** environmental-requirement records for ~2,568 plant
  species, including (per species): minimum / optimal / maximum
  temperature, annual precipitation, soil pH range, light intensity,
  Köppen climate, photoperiod sensitivity, latitude range, altitude range,
  salinity tolerance, soil texture preferences, soil depth.
- **Status:** **officially discontinued ~2015** but remains accessible —
  the database has not been formally maintained in over a decade. We treat
  the parameter set as a frozen baseline.
- **Access:**
  - FAO GAEZ Data Portal: `https://gaez.fao.org/pages/ecocrop`
  - FAO ECOCROP application: `https://ecocrop.apps.fao.org/`
  - There is no native CSV download. Community scrapers exist; the most
    referenced is `EcoCrop-ScrapeR` (R-based).
- **License:** FAO terms of use (verify per use; FAO data is generally
  CC BY-NC-SA or CC BY 3.0 IGO).
- **Backend choice:** **scrape once → versioned local SQLite or DuckDB**
  snapshot under `data/ecocrop_v2015_snapshot.db` (or similar). Treat as
  immutable.
- **Caveats:**
  - Frozen at ~2015 parameters; does not reflect modern breeding,
    drought-tolerant cultivars, or recent agronomic research.
  - Quality varies by species — staple crops are well-characterized;
    minor species have sparser records.
  - Some parameters are categorical, not continuous — design Tier 1 to
    handle both.
- **Verified:**
  - https://gaez.fao.org/pages/ecocrop
- **Role in AIgriculture:** the **primary input to Tier 1** (GAEZ-style
  climatic envelope screening) for all ~2,500 species.

### A.2 FAO GAEZ v4 / v5

- **Provider:** FAO + IIASA (Global Agro-Ecological Zoning project).
- **What it provides:** the canonical land-suitability product, combining
  climate, soil, and terrain to compute crop-specific suitability classes
  globally. The GAEZ v4 portal hosts pre-computed suitability rasters for
  ~280 crop / management combinations; v5 (released 2022) refreshes the
  methodology and inputs to CMIP6.
- **Suitability classes:** S1 (very suitable), S2 (suitable), S3
  (moderately suitable), S4 (marginally suitable), N (not suitable).
- **Inputs:** climate (precipitation, temperature, growing-degree days,
  wind, sunshine, humidity), soil (seven qualities), terrain (slope /
  aspect), and crop-specific thermal / water requirements.
- **License:** open access through the GAEZ Data Portal; FAO data terms.
- **Access:** `https://gaez.fao.org/` (portal + rasters + technical
  documentation).
- **Backend choice:** **download v5 suitability rasters for the Quebec
  bounding box** (small) for direct benchmarking. We do not depend on
  GAEZ at runtime — it is our **reference product** for Tier 1
  validation.
- **Role in AIgriculture:** **(i) reference / benchmark** (does our Tier 1
  output broadly agree with GAEZ for the same crops under similar
  scenarios?), **(ii) methodology source** for the climatic-envelope
  algorithm we will re-implement in `aigriculture.suitability`.
- **Verified:**
  - https://gaez.fao.org/

### A.3 Crop calendars

- **Sacks et al. (2010) crop calendar** — planting and harvest dates for
  19 major crops worldwide, on a 5-arc-minute grid. The de-facto standard
  for climate-impact studies for over a decade. To add to `CITATIONS.bib`.
- **GGCMI Phase 1 crop calendars** — harmonized planting / maturity for
  the GGCMI intercomparison; an updated set for Phase 3 is in use.
- **MIRCA2000** (Portmann et al. 2010) — monthly irrigated and rainfed
  growing areas; complements Sacks for irrigation-aware modeling. To add
  to `CITATIONS.bib`.

**For Quebec MVP:** consult Sacks et al. for the global view; verify
against **AAFC ACI year-by-year** and **MAPAQ regional agronomic guides**
for the Quebec-specific planting / harvest windows.

### A.4 USDA PLANTS + Plant Hardiness Zones

- **USDA PLANTS Database** — comprehensive North American plant species
  records (~80,000 species/taxa) including some agronomic notes; primary
  use here is cross-checking species names against ECOCROP.
- **USDA Plant Hardiness Zone Map (2023 release)** — defines 13 zones (1a
  – 13b) by average annual minimum temperature; mostly relevant for
  perennials / horticulture. **Note: Canada has its own
  AAFC Plant Hardiness Zones for Canada (most recent: 2023 update).**
- **Backend choice:** stream / reference only; not a primary data layer.
- **Role in AIgriculture:** plausibility check for perennial /
  horticultural recommendations (will this fruit tree survive a Quebec
  winter?).

### A.5 TRY Plant Trait Database

- **Provider:** Max Planck Institute for Biogeochemistry consortium.
- **What it provides:** the largest open plant-trait database — millions
  of trait observations for >280,000 species. Useful for non-traditional
  agroforestry / cover-crop recommendations and for filling ECOCROP gaps.
- **License:** access by request; trait-by-trait open / restricted status.
- **Status:** **investigate during Phase 4** — overkill for the Quebec MVP
  staple crops.

### A.6 GBIF, GENESYS-PGR, EURISCO

- **GBIF** — global biodiversity occurrences; useful for **observed**
  distribution of cultivated and wild species (a "where does this plant
  actually grow today" reality check).
- **GENESYS-PGR** — international plant-genetic-resources accession portal.
- **EURISCO** — European plant-genetic-resources catalogue.
- **Status:** advanced / future use; not part of the MVP.

---

## Part B — Process-based crop models

### B.1 PCSE / WOFOST (primary candidate)

- **Provider:** Wageningen University (`pcse` on PyPI; led by Allard de
  Wit).
- **What it is:** **the Python Crop Simulation Environment** — a Python
  framework implementing WOFOST, LINGRA, LINTUL3 and related crop
  growth models. Used in operational EU crop yield forecasting (MARS).
- **Crop models included:**
  - WOFOST 7.2, 7.3 (released with PCSE 6.0), **8.1** (full crop N
    dynamics, released with PCSE 6.0).
  - LINGRA (grassland production).
  - LINTUL3 (simplified light-use-efficiency model).
- **Crops with WOFOST parameter files** (`ajwdewit/WOFOST_crop_parameters`):
  **23 crops total** — barley, cassava, chickpea, cotton, cowpea, fababean,
  groundnut, **maize**, millet, mungbean, pigeonpea, **potato**, **rapeseed**,
  rice, seed onion, sorghum, **soybean**, **sugarbeet**, sugarcane,
  sunflower, sweetpotato, tobacco, **wheat**. **Every Quebec-relevant
  staple crop is included.**
- **Language:** Python (3.6+); current version PCSE 6.0.
- **License:** **European Union Public License (EUPL)** — copyleft-style
  but considered "weak copyleft" and compatible with most uses.
- **Access:** `pip install pcse`; source at `https://github.com/ajwdewit/pcse`.
- **Verified:**
  - https://pcse.readthedocs.io/en/stable/
  - https://github.com/ajwdewit/WOFOST_crop_parameters

### B.2 DSSAT

- **Provider:** DSSAT Foundation, ICASA, with USA / international partners.
- **What it is:** Decision Support System for Agrotechnology Transfer — a
  long-established suite of crop models (CERES, CROPGRO, CSM) used in over
  198 countries.
- **Crops:** 45+ crops; particularly strong on US row crops and tropical
  crops.
- **Language:** Fortran (closed historical architecture; recent Cropping
  System Model (CSM) reframe).
- **License:** free; DSSAT now describes itself as open-source though the
  exact license per release should be verified at integration time.
- **Current version:** **4.8.5** (released 1 December 2024).
- **Python integration:** no first-party Python wrapper documented on the
  DSSAT site at the time of writing (2026-05). Community wrappers (e.g.,
  `pyDSSAT`, `DSSATTools`) exist but vary in maintenance status.
- **Regional calibration:** strong US presence (CRAFT tool, regional
  forecasting); ICASA Data Standards Version 2.0 for calibration.
- **Status in AIgriculture:** **secondary** — keep for crops not covered by
  WOFOST and for ensemble cross-checks (Phase 4).
- **Verified:**
  - https://dssat.net/

### B.3 APSIM Next Generation

- **Provider:** APSIM Initiative (Australia-led international consortium).
- **What it is:** the Agricultural Production Systems Simulator, "Next
  Generation" rewrite — strong in soil-water-nitrogen-crop interactions
  and management; widely used in Australia, increasingly elsewhere.
- **Crops:** many — wheat, barley, canola, maize, soybean, sorghum, rice,
  cotton, sugarcane, pasture systems.
- **Language:** C# / .NET (open-source).
- **License:** the ApsimX core is open source; **commercial use requires a
  paid license** (a hard caveat — re-check before any production use, as
  it conflicts with our open-source-only constraint for the production
  product).
- **Python integration:** the community Python wrapper
  **apsimNGpy** (Apache-2.0; built on Pythonnet) provides reproducible,
  scriptable access.
- **Status in AIgriculture:** **investigate license carefully** before
  integration. Strong scientific value but the commercial-use license
  question must be resolved.
- **Verified:**
  - https://github.com/APSIMInitiative/ApsimX
  - https://github.com/MAGALA-RICHARD/apsimNGpy

### B.4 AquaCrop (FAO) + AquaCrop-OSPy

- **AquaCrop (FAO):** water-driven crop model focused on yield response to
  water; designed for water-limited contexts. Current version **7.1.1**.
  Standalone executables (Windows / Linux / Mac).
- **AquaCrop-OSPy:** open-source Python implementation by Foster et al.
  (Univ. Manchester) tracking FAO AquaCrop 7.1; **Apache-2.0**; current
  version **3.0.12** (October 2025). Citation: Foster et al. (2022)
  *Agricultural Water Management* 254:106976 — to add to `CITATIONS.bib`.
- **Crops:** AquaCrop default calibrations include maize, wheat, soybean,
  sunflower, rice, sugar beet, cotton, sorghum and a few others.
  AquaCrop-OSPy mirrors most v7.1 features but is not the official FAO
  implementation.
- **Status in AIgriculture:** **complement** to WOFOST — especially for
  water-limited / drought-stress projections; lighter input requirements.
- **Verified:**
  - https://www.fao.org/aquacrop/en/
  - https://github.com/aquacropos/aquacrop

### B.5 STICS (INRAE)

- **Provider:** INRAE (France).
- **Strengths:** well-calibrated for French / European crops and
  cropping systems; long heritage.
- **Language:** Fortran; weak Python integration in the open-source
  community.
- **Status:** **not selected** for Quebec MVP — Python integration cost
  outweighs benefits given WOFOST + DSSAT already cover our needs.

### B.6 GGCMI / ISIMIP ensemble (alignment target)

- **What it is:** the AgMIP Global Gridded Crop Model Intercomparison —
  not a model, but the **protocol** under which 12–15 global gridded crop
  models run on harmonized inputs [@Elliott2015GGCMI].
- **Why it matters:** if we drive WOFOST with ISIMIP3b forcings and follow
  GGCMI protocols, our outputs become comparable with the published
  GGCMI ensemble. This grants AIgriculture immediate scientific
  legitimacy.

### Decision matrix (process-based models)

Scoring (1–5; 5 = best fit for AIgriculture's needs):

| Model | Python | License (open) | Regional calibration (EU + NA) | Crop coverage | Quebec relevance | Total |
|-------|:------:|:--------------:|:------------------------------:|:-------------:|:----------------:|:-----:|
| **PCSE / WOFOST** | 5 | 5 (EUPL) | 4 (EU-strong; NA acceptable) | 4 (23 crops, all Quebec staples) | 5 | **23** |
| DSSAT | 2 (community) | 4 (free; license details vary) | 5 (US-strong) | 5 (45+ crops) | 4 | 20 |
| APSIM Next Gen | 4 (apsimNGpy) | 2 (commercial-use cost concern) | 3 | 4 | 3 | 16 |
| AquaCrop-OSPy | 4 | 5 (Apache-2.0) | 3 (water-limited focus) | 3 | 3 | 18 |
| STICS | 1 | 3 | 3 (FR-strong) | 4 | 2 | 13 |

**Winner: PCSE / WOFOST.**

---

## Part C — Quebec MVP crop short-list

Quebec's principal field crops (StatCan FCRS 2024) by area / production:

- **Corn (maïs-grain)** — 3.6 Mt production (2024), yield 162.1 bu/ac.
- **Soybean (soja)** — 1.4 Mt production (2024), yield 49.6 bu/ac.
- **Wheat (blé, mostly spring)** — significant but smaller area than corn
  / soy.
- **Barley (orge)** — relatively small in Quebec compared to Prairies.
- **Canola / rapeseed (canola / colza)** — Quebec area modest but
  expanding northward — a strong climate-shift candidate.
- **Hay / forage** — large area but not a "field crop" in the FCRS sense
  and not in WOFOST's parameter set; defer to Phase 4.

**Cross-referencing against the WOFOST parameter list** (23 crops, see
B.1) — corn, soybean, wheat, barley, canola/rapeseed, sugarbeet, potato
are all available.

### Recommended pilot crops for Phase 3 (4 crops)

1. **Corn / grain maize** — highest economic value in Quebec; strong
   northward suitability shift in literature; WOFOST `maize`.
2. **Soybean** — second-largest crop; well-studied climate sensitivity;
   WOFOST `soybean`.
3. **Spring wheat** — provincial-level FCRS data available back decades;
   classical climate-impact reference crop; WOFOST `wheat`.
4. **Canola (rapeseed)** — emerging crop on the Quebec northern frontier;
   most interesting "is this going to be viable in 2040?" question;
   WOFOST `rapeseed`.

**Sequence:** start with **corn** as the calibration crop (best
data, simplest hindcast), then add soybean, wheat, canola.

### Calibration gap (open question for Phase 1 → 3)

WOFOST's default parameter sets are calibrated against European cultivars
and management. Quebec cultivars differ:

- Shorter-day-length-adapted lines.
- Cold-tolerance breeding (especially soybean / corn).
- Different sowing / harvest windows than European baselines.

**Phase 1 task** (to be split into a follow-up Phase 1 sub-deliverable):
take each pilot crop's WOFOST default parameter file, run it driven by
historical AgERA5 / Daymet for representative Quebec Census Agricultural
Regions, and compare simulated yields against StatCan FCRS observed
yields. Compute bias and the parameter sensitivities that drive it. From
that diagnostic decide whether to (a) accept the default with a
post-hoc bias correction in Tier 3, or (b) recalibrate one or two key
parameters (`TBASE`, `TSUM1/TSUM2`, `KDIF`, `EFF`, etc.).

---

## Verification checklist

- [ ] ECOCROP snapshot generated as a versioned local database, with
      provenance metadata.
- [ ] GAEZ v5 Quebec-region suitability raster downloaded for at least
      maize, wheat, soybean for baseline comparison.
- [ ] PCSE installed and a smoke test (one Quebec CAR, one crop, one year)
      executed in a notebook in `backend/notebooks/exploratory/`.
- [ ] WOFOST default parameter files vs Quebec historical yields:
      bias-and-sensitivity diagnostic produced.
- [ ] DSSAT availability check (license, install) — if used in Phase 4.
- [ ] APSIM commercial-use license question resolved before any integration
      work.
- [ ] Every new claim above cites a BibTeX entry in `CITATIONS.bib`.
