# 01 — Open data catalogue

> **Status:** stub. To be filled in during Phase 1.
>
> **Goal:** for every dataset under consideration, capture: provider,
> what it provides, spatial resolution, temporal resolution + coverage,
> access method (API / STAC / Earth Engine / direct download), license,
> known caveats, citation (BibTeX key in `CITATIONS.bib`), and the
> decision on whether to access it via cloud-streaming or local Zarr
> cache (see [ADR 0004](../decisions/0004-compute-and-storage.md) once
> written).

## Sections to write

### 1. Satellite / Earth Observation
- Copernicus Sentinel-1, -2, -3
- Landsat 7 / 8 / 9
- MODIS Terra / Aqua (MOD13 NDVI/EVI; MOD15 LAI/FPAR)
- VIIRS
- Harmonized Landsat-Sentinel-2 (HLS, NASA)
- Copernicus Global Land Service vegetation products

### 2. Historical climate / reanalysis
- ERA5, ERA5-Land
- **AgERA5** — primary candidate for historical training data
- CHIRPS
- GPM IMERG
- PRISM (US)
- E-OBS (Europe)
- Daymet (North America)
- **ECCC AHCCD** — Adjusted and Homogenized Canadian Climate Data
- **CanGRD** — gridded historical climate, ECCC

### 3. Climate projections
- CMIP6 (via ESGF + Pangeo Zarr)
- **NEX-GDDP-CMIP6** (NASA)
- **CHELSA-CMIP6** (ETH)
- **ISIMIP3b**
- **EURO-CORDEX**, **NA-CORDEX**
- **NRCan / CCCS** Canadian downscaled CMIP6 — primary for Quebec MVP

For each projection product: list the GCMs available, the SSPs available,
the bias-correction method (BCSD vs ISIMIP3BASD vs other), and the spatial
resolution of the *final* downscaled grid.

### 4. Soil
- SoilGrids 2.0 (ISRIC)
- European Soil Database / LUCAS
- SSURGO / STATSGO2 (USDA)
- **AAFC Soil Landscapes of Canada (SLC)** — Quebec MVP
- HWSD v2 (FAO)

### 5. Topography
- Copernicus DEM GLO-30
- SRTM, ASTER GDEM

### 6. Land cover & crop maps (validation and masking)
- ESA WorldCover
- USDA Cropland Data Layer (CDL)
- **AAFC Annual Crop Inventory (ACI)** — Quebec MVP
- CORINE Land Cover
- EuroCrops / Sen4AgriNet

### 7. Historical crop production statistics (hindcast validation)
- FAOSTAT
- GDHY (Iizumi & Sakai 2020) — already in `CITATIONS.bib`
- USDA NASS QuickStats
- Eurostat (NUTS-2 regional)
- **StatCan Census of Agriculture + Field Crop Reporting Series** — Quebec MVP
- **ISQ + MAPAQ** — Quebec-specific

## Per-entry template

```markdown
### {Dataset name}

- **Provider:**
- **What it provides:**
- **Spatial resolution:**
- **Temporal resolution / coverage:**
- **Access method:** [API / STAC / Earth Engine / direct download / etc.]
- **License:**
- **Caveats:**
- **Citation:** [@BibKey]
- **Backend choice:** [stream from STAC / local Zarr cache] — see ADR 0004
- **Estimated size for Quebec subset / global subset:**
```

## Verification checklist (per entry)

- [ ] Provider URL resolves and lists current dataset version.
- [ ] License confirmed on the official source (not paraphrased).
- [ ] Resolution and coverage numbers match the source documentation.
- [ ] A BibTeX entry exists in `CITATIONS.bib`.
- [ ] Access path tested in a notebook in `backend/notebooks/exploratory/`.
