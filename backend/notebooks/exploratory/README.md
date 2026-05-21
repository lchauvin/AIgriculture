# Exploratory notebooks

Quick, throwaway investigations of data and methodology. **Not load-bearing.**
Whenever a notebook discovers something worth keeping, the insight is
promoted into:

- a research document under `docs/research/`,
- production code under `backend/aigriculture/`,
- and at least one test under `backend/tests/`.

## Format

We use the **percent (`# %%`) script format** rather than committing
`.ipynb` files:

- Each `# %%` block is a cell.
- Each `# %% [markdown]` block is a markdown cell.
- The file is plain Python — `git diff` shows real diffs, not JSON blobs.
- It opens cell-by-cell in VS Code, PyCharm, and (via `jupytext`)
  JupyterLab.

Convert to `.ipynb` on demand:

```bash
.venv/bin/jupytext --to ipynb quebec_gdd_smoke_test.py
```

## Running

These scripts are runnable end-to-end:

```bash
.venv/bin/python backend/notebooks/exploratory/quebec_gdd_smoke_test.py
```

Notebooks that hit live external services (the CDS API, Earth Engine,
etc.) require credentials. Each notebook documents its prerequisites at
the top.

## Listing

| File | Purpose | External deps |
|------|---------|----------------|
| `quebec_gdd_smoke_test.py` | First end-to-end exercise of the data layer — pulls AgERA5 for a Quebec sub-region and computes GDD via xclim. | Copernicus CDS API (`~/.cdsapirc`). |
| `quebec_soil_smoke_test.py` | Streams SoilGrids 2.0 Tier-2 essential properties (clay, sand, silt, pH, SOC, bulk density, coarse fragments) at six depths for a Quebec subset; prints per-(property, depth) summaries; plots the topsoil-clay map. | ISRIC public WebDAV (no auth). |
| `quebec_aci_smoke_test.py` | Streams one year of AAFC Annual Crop Inventory for a Quebec subset via Earth Engine; prints land-cover class histogram and maps the result. | Earth Engine (`earthengine authenticate` once, `AIGRICULTURE_EE_PROJECT` env var set to your GCP project ID). |
| `quebec_candcs_m6_smoke_test.py` | Lazy OPeNDAP load from PAVICS for a one-month CanDCS-M6 slice (CanESM5 × SSP2-4.5 × July 2050) over a Quebec subset; prints tasmax/tasmin/pr summaries; maps mid-century July monthly-mean Tmax. | PAVICS THREDDS (no auth). |
