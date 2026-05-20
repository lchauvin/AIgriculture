# 05 — Existing tools and prior work survey

> **Status:** v0.1 — drafted.

## Purpose

Know what already exists so we don't reinvent it; sharpen what AIgriculture
adds. This survey is the foundation for the "Why this project?"
paragraphs in the README and elsewhere.

## A — Tools and platforms

### A.1 FAO GAEZ Data Portal (v4 / v5)

- **What it is:** the canonical land-suitability product — pre-computed
  global suitability rasters for ~280 crop / management combinations
  under defined climate scenarios.
- **How AIgriculture differs:**
  - GAEZ outputs are **fixed-scenario, pre-computed rasters**; AIgriculture
    runs **on-demand for the user's polygon** under multiple SSPs with
    explicit uncertainty bands.
  - GAEZ surfaces **a single class per cell**; AIgriculture surfaces a
    distribution over the GCM ensemble and a "robustness" indicator.
  - GAEZ has **no hindcast**; AIgriculture's hindcast harness is a
    first-class feature.
  - GAEZ does **not bias-correct against observed yields**; AIgriculture's
    Tier 3 explicitly does.
- **Where we depend on it:** as a **reference / benchmark** for our Tier 1
  output and as the methodology source for the GAEZ-style envelope
  algorithm.

### A.2 CGIAR CCAFS Climate Analogues

- **What it is:** a methodology and tool for identifying "where today
  resembles your region's projected future climate," giving practitioners
  current-day analogue locations whose agronomic practices may inform
  future adaptation. Pugh et al. (2016) [@Pugh2016] is the canonical
  scientific reference.
- **How AIgriculture differs:**
  - Analogues are complementary rather than competitive. AIgriculture
    produces crop **recommendations**; CCAFS analogues produce
    **comparable-place insights**.
  - We may add a Phase 4 feature that surfaces analogue locations for
    a Quebec region's projected 2050 climate — a useful UX
    enhancement.
- **Status of the CCAFS tool:** the original CCAFS Climate Analogues web
  tool is intermittently available; verify before depending on it.
  Methodology, however, is documented and re-implementable.

### A.3 EU JRC Agri4Cast / MARS Bulletin

- **What it is:** the EU's operational crop-yield forecasting system. Uses
  WOFOST + remote sensing to produce monthly bulletins on European crop
  conditions (the **MARS Bulletin**) and short-term yield outlooks.
- **How AIgriculture differs:**
  - **Time horizon:** Agri4Cast is **near-real-time / current season**;
    AIgriculture projects **5–30 years**.
  - **Geography:** Agri4Cast is EU-focused; AIgriculture starts in Quebec.
  - **Audience:** Agri4Cast targets policy / commodity markets;
    AIgriculture targets a multi-audience portfolio.
- **What we borrow:** WOFOST itself is the same model that backs MARS,
  so AIgriculture's Tier 2 inherits a substantial operational pedigree.

### A.4 NASA Harvest / GEOGLAM Crop Monitor

- **What it is:** NASA Harvest (UMD) supports the GEOGLAM Crop Monitor —
  monthly global crop-condition bulletins coordinated by GEOGLAM and AMIS.
  Includes EO-derived crop-condition layers and an interactive Crop
  Monitor Exploring Tool (CMET).
- **How AIgriculture differs:** similar to Agri4Cast — Crop Monitor is
  **current-season nowcasting**, not multi-decadal projection.
- **What we borrow:** EO products (HLS, MODIS / VIIRS NDVI) and the
  community knowledge that helps interpret current-day satellite signals
  — feeds AIgriculture's Tier 3 features.

### A.5 ESA WorldCereal

- **What it is:** an ESA-funded global crop and irrigation mapping system
  producing 10 m global products for the year 2021 (and rolling), focused
  on maize and cereals (the Triticeae tribe — wheat / barley / rye —
  treated as a single class).
- **How AIgriculture differs:** WorldCereal is a **mapping** system (where
  things are grown); AIgriculture is a **recommendation** system (where
  things will grow well).
- **What we borrow:** WorldCereal layers can serve as alternate / cross-
  reference current-day crop maps complementing AAFC ACI / USDA CDL.
- **Citation:** the WorldCereal system paper is in *Earth System Science
  Data* 2023 (Van Tricht et al.) — to add to `CITATIONS.bib`.

### A.6 Commercial / current-season tools

For completeness, **mentioned only as context** (excluded from
AIgriculture's open-source dependency scope):

- **Climate FieldView** (Bayer / Climate LLC) — current-season precision-
  ag platform; commercial.
- **OneSoil** — commercial field-monitoring.
- **Granular** (Corteva).
- **The Climate Corporation** (now part of Bayer; original "Monsanto
  Climate" platform).

These tools are mostly current-season operational decision support, not
multi-decadal climate-adaptation projection.

## B — Recent academic projects (2022–2026)

A non-exhaustive selection of recent climate-adaptive crop suitability
work, useful both for methodology and for benchmarking AIgriculture's
outputs.

- **Fitzgibbon, Pisut & Fleisher (2022)** [@Fitzgibbon2022]
  — *Land* 11(9):1382. MaxEnt vs Random Forest for US corn under
  climate change; MaxEnt outperforms; reference for ML method choice.

- **Sgubin et al. (2023)** [@Sgubin2023] — *Global Change Biology*
  29(3):808–826. Non-linear loss of European wine regions under warming;
  the well-studied perennial-crop case study. Useful as a methodological
  template for any future perennial AIgriculture pilot.

- **Lobell & Di Tommaso (2025)** [@LobellDiTommaso2025] — *PNAS*
  122(20):e2502789122. A half-century retrospective showing North
  American agricultural regions warmed less than projected — a humbling
  reminder that models can be regionally biased and a direct caution
  for the Quebec MVP.

- **A recent 17-crop global suitability dataset** (Nature Scientific
  Data 2026) — provides 1 km global crop suitability for 17 crops under
  four SSPs and three future periods. A direct **external benchmark** for
  AIgriculture's Tier 1 output once published.

- **Sobie et al. (2024)** [@Sobie2024CanDCSM6] — *Geoscience Data Journal*
  11:806–824. The CanDCS-M6 dataset paper itself (our primary climate
  projection source).

- **A 2024 *Precision Agriculture* review** on common pitfalls in crop
  yield modeling — formalizes the spatiotemporal-CV recommendation we
  adopt in §4.

## C — Differentiation statement

In one paragraph: **AIgriculture is the only open-source, end-to-end,
user-region-selectable tool that combines (a) a GAEZ-style envelope
screen on the ECOCROP knowledge base for ~2,500 species, (b) a process-
based projection through PCSE/WOFOST on the CMIP6 ensemble (CanDCS-M6
for the Quebec MVP), (c) an XGBoost ML bias correction against historical
StatCan / Eurostat / USDA NASS yields, with Hawkins-Sutton uncertainty
decomposition and an explicit retrospective-hindcast harness exposed in
the user interface.**

What we are not:
- Not a current-season operational platform (Agri4Cast, NASA Harvest
  fill that role).
- Not a commercial precision-ag product.
- Not a single-shot academic study (we are reproducible, scriptable, and
  open).
- Not a fixed-scenario raster store (we are interactive and on-demand).

## D — Open questions

1. Is there an open-source upstream that already implements GAEZ-style
   envelope scoring in Python (so we don't re-implement)?
   - Initial search yields nothing comprehensive; will reverify when
     coding Tier 1 in Phase 2. Falling back to fresh implementation is
     fine and gives us full transparency.
2. Are there community-maintained ECOCROP CSV mirrors we should adopt?
   - `EcoCrop-ScrapeR` is R-based but produces a structured dump. We
     will likely implement a Python adapter rather than maintain another
     scraper.
3. Should we expose an "analogue" view (à la CCAFS) as a Phase 4 UI
   feature? Probably yes — it is a known-effective communication tool.

## Verification checklist

- [ ] Each referenced project's URL resolves.
- [ ] Each cited paper is in `CITATIONS.bib` with a verified DOI.
- [ ] The differentiation statement is reviewed by at least one domain
      expert (eventually) before public release.
