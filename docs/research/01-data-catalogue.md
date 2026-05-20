# 01 — Open data catalogue

> **Status:** v0.1 complete (all seven sections drafted with verified
> primary sources). Pending refinements during Phase 1: a few minor
> citation gaps marked inline (CHIRPS Funk 2015, E-OBS Cornes 2018,
> AgERA5 author list, LUCAS Orgiazzi 2018, Sobie 2024 already added,
> EuroCropsML Reuß 2025, EU-27 harmonized 2025). Use of CHELSA-CMIP6
> URL needs reverification at code time.

## Purpose

For every dataset under consideration by AIgriculture, capture the provider,
what it provides, spatial / temporal resolution, coverage period, access
method, license, known caveats, and primary citation. The catalogue
underpins ADRs 0002 (primary climate-projection dataset), 0004 (compute
and storage backend), and 0005 (scenarios and GCM ensemble), and is the
single source of truth for what data the implementation depends on.

## Conventions

- **Backend choice** (per dataset) is one of:
  - **Stream** — accessed via STAC / Earth Engine / direct cloud-optimized
    reads with no local copy.
  - **Local Zarr** — downloaded once (subset to the relevant
    bounding box / time window) and cached on disk as Zarr. Threshold: per
    [the user's storage preference](../../README.md), prefer local when a
    dataset (subset) is below ~300 GB and re-read often.
  - **Hybrid** — small derived products cached locally; raw archive
    streamed.
- **Citation** is the BibTeX key in [`../../CITATIONS.bib`](../../CITATIONS.bib).
  Every entry below has at least one verified primary-source URL inline
  (used during Phase 1 to confirm the facts on this page).

---

## §1 Satellite imagery / Earth observation

### 1.1 Copernicus Sentinel-1 (SAR)

- **Provider:** ESA / European Commission (Copernicus Programme).
- **What it provides:** C-band Synthetic Aperture Radar imagery — all-weather,
  day-and-night surface observations. Key for soil-moisture proxies, crop
  structure / biomass change, flood mapping, and complementing optical EO
  through cloud cover.
- **Imaging modes:**
  - **IW** (Interferometric Wide, default for land) — 250 km swath, ~5 × 20 m
    spatial resolution.
  - **EW** (Extra Wide) — 400 km swath, coarser resolution, maritime / ice.
  - **SM** (Stripmap) — narrow swath, higher resolution.
  - **WV** (Wave) — specialized ocean.
- **Revisit time:** currently 12 days (single-satellite scenario), restoring
  to 6 days once Sentinel-1C (launched 5 December 2024) becomes operational
  after a commissioning phase expected to end May 2025.
- **Mission history:** Sentinel-1A operational from April 2014; Sentinel-1B
  ended July 2022 after an instrument failure; Sentinel-1C launched Dec 2024.
- **Products:** Level-0 (raw), Level-1 GRD (Ground Range Detected,
  amplitude), Level-1 SLC (Single Look Complex, phase + amplitude),
  Level-2 OCN (ocean).
- **Access:**
  - ESA Copernicus Data Space — OData + STAC catalogue:
    `https://documentation.dataspace.copernicus.eu/`
  - AWS Open Data Registry (Sentinel-1 RTC / GRD).
  - Microsoft Planetary Computer (Sentinel-1 GRD + RTC, STAC).
  - Google Earth Engine.
- **License:** free and open, Copernicus data policy.
- **Backend choice:** **stream** (STAC against MPC or AWS); on-the-fly
  preprocessing rather than local archive.
- **Caveats:** speckle requires careful filtering; backscatter varies with
  soil moisture *and* vegetation structure *and* surface roughness — the
  signal is not easily decomposable without ancillary models.
- **Verified:**
  - https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel1.html

### 1.2 Copernicus Sentinel-2 (multispectral optical)

- **Provider:** ESA / European Commission (Copernicus Programme).
- **What it provides:** 13-band multispectral optical imagery (visible →
  SWIR). The workhorse for crop classification, vegetation indices, and
  field-level monitoring in our scope.
- **Spatial resolution by band group:**
  - 10 m: B02 (blue), B03 (green), B04 (red), B08 (NIR).
  - 20 m: B05, B06, B07, B08A, B11, B12.
  - 60 m: B01, B09, B10.
- **Constellation history:** Sentinel-2A launched 2015; Sentinel-2B added;
  Sentinel-2C launched 5 September 2024 and operationally replaced
  Sentinel-2A on 21 January 2025.
- **Revisit time:** ~10 days single-satellite at equator; **5 days** in
  constellation (2–3 days at mid-latitudes — relevant for Quebec).
- **Products:**
  - **Level-1C** — Top-of-Atmosphere reflectance (global, since 2015).
  - **Level-2A** — Surface reflectance (atmospherically corrected, ARD).
  - **Level-3** — quarterly cloud-filtered mosaics at 10 m.
- **Access:** Copernicus Data Space (OData + STAC), Sentinel Hub, AWS Open
  Data, Microsoft Planetary Computer, Google Earth Engine.
- **License:** free and open, Copernicus data policy.
- **Backend choice:** **stream** (STAC; the Quebec subset for a single year
  at 10 m would be in the multi-hundred-GB range — keep cloud-streamed).
- **Caveats:** clouds are the dominant limitation in Quebec; cloud-mask
  quality varies by L2A processor version (use the most recent baseline).
- **Verified:**
  - https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html

### 1.3 Copernicus Sentinel-3 (OLCI / SLSTR)

- **Provider:** ESA / European Commission (Copernicus Programme).
- **What it provides:** moderate-resolution ocean + land colour (OLCI) and
  surface temperature (SLSTR). For AIgriculture, OLCI provides the data
  source feeding the **Copernicus Global Land Service NDVI 300 m V2**
  product (see §1.7); SLSTR provides land surface temperature at 500 m – 1 km.
- **Instruments and resolutions:**
  - **OLCI** — 300 m, < 2 day revisit.
  - **SLSTR** — 500 m to 1 km, < 4 day revisit, includes LST.
  - **SRAL** — radar altimeter, 28 day repeat (not directly relevant).
- **Coverage:** global since March 2016.
- **License:** free and open, Copernicus data policy.
- **Backend choice:** **stream** for OLCI / SLSTR L2 products via STAC.
- **Caveats:** lower spatial resolution than Sentinel-2 — useful for
  regional / national aggregations, not field-level.
- **Verified:**
  - https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel3.html

### 1.4 Landsat 7, 8, 9

- **Provider:** NASA + USGS.
- **What it provides:** the longest continuous global moderate-resolution
  optical EO record. Indispensable for any pre-2015 historical analysis
  (Sentinel-2 only starts in 2015), including hindcast validation.
- **Satellites:**
  - **Landsat 7 (ETM+)** — launched April 1999. Scan Line Corrector failed
    May 2003, leaving permanent gaps in post-SLC-off scenes.
  - **Landsat 8 (OLI / TIRS)** — launched February 2013.
  - **Landsat 9 (OLI-2 / TIRS-2)** — launched September 2021.
- **Spatial resolution:**
  - OLI / OLI-2 multispectral: 30 m.
  - Panchromatic band: 15 m.
  - Thermal (TIRS / TIRS-2): native 100 m, resampled to 30 m.
- **Revisit time:** 16 days single-satellite; **8 days** Landsat 8 + 9
  combined.
- **Products:** Landsat Collection 2 Level-1 + Level-2 (surface reflectance,
  surface temperature) for L4 – L9.
- **Access:** USGS EarthExplorer, USGS / EROS STAC, AWS Open Data,
  Microsoft Planetary Computer, Google Earth Engine.
- **License:** USGS no-cost open data policy since 2008.
- **Backend choice:** **stream** (STAC).
- **Caveats:** Landsat 7 SLC-off gaps; thermal-band stripe artefacts on
  some scenes; cloud cover dominant in Quebec winters.
- **Verified:**
  - https://www.usgs.gov/landsat-missions/landsat-collection-2
  - https://www.usgs.gov/faqs/what-are-band-designations-landsat-satellites

### 1.5 MODIS MOD13Q1 v6.1 (vegetation indices)

- **Provider:** NASA / LP DAAC.
- **What it provides:** Terra MODIS 16-day vegetation indices (NDVI and
  EVI) on a sinusoidal grid. Long uninterrupted record useful for
  multi-decade trend and hindcast work.
- **Spatial resolution:** 250 m.
- **Temporal resolution:** 16-day composite.
- **Coverage:** 18 February 2000 – present (global).
- **Companion product:** MYD13Q1 (Aqua, since 2002) — phase-shifted; the
  two combined give ~8-day effective compositing.
- **DOI:** `10.5067/MODIS/MOD13Q1.061`.
- **Citation:** Didan, K. (2021). *MODIS/Terra Vegetation Indices 16-Day L3
  Global 250m SIN Grid V061* [Data set]. NASA Land Processes DAAC.
- **Format:** HDF-EOS2; ~92 MB per granule.
- **Access:** NASA Earthdata, LP DAAC Cloud (S3), MPC / GEE.
- **License:** openly shared under EOSDIS Data Use and Citation Guidance.
- **Backend choice:** **stream** for the Quebec subset; consider local Zarr
  cache for derived crop-region time-series.
- **Verified:**
  - https://www.earthdata.nasa.gov/data/catalog/lpcloud-mod13q1-061

### 1.6 VIIRS VNP13A1 (vegetation indices)

- **Provider:** NASA / LP DAAC; instrument on Suomi-NPP and JPSS-1.
- **What it provides:** VIIRS 16-day composite NDVI, EVI, and EVI-2 — the
  designated MODIS continuity product as MODIS Terra/Aqua approach end of
  life.
- **Spatial resolution:** 500 m.
- **Temporal resolution:** 16-day composite.
- **Coverage:** 17 January 2012 – 8 June 2024 (V1.001, deprecated 8 April
  2025). **Use V002** (current) going forward.
- **Platform:** Suomi NPP.
- **DOI (V001, deprecated):** `10.5067/VIIRS/VNP13A1.001`.
- **License:** openly shared under EOSDIS Data Use and Citation Guidance.
- **Backend choice:** **stream**.
- **Caveats:** V001 → V002 migration pending; verify which version is
  available on the chosen STAC catalog at implementation time. Coarser than
  MODIS MOD13Q1 (500 m vs 250 m) — use only when MODIS continuity matters
  past 2024–2025.
- **Verified:**
  - https://www.earthdata.nasa.gov/data/catalog/lpcloud-vnp13a1-001

### 1.7 Harmonized Landsat Sentinel-2 (HLS)

- **Provider:** NASA Goddard / LP DAAC.
- **What it provides:** harmonized 30 m analysis-ready surface reflectance
  blending Landsat 8/9 (HLSL30) and Sentinel-2 A/B/C (HLSS30). Effectively
  collapses Landsat's 16-day repeat and Sentinel-2's 5-day repeat into a
  single virtual constellation.
- **Spatial resolution:** 30 m.
- **Temporal resolution:** < 1.4 days globally on average, < 1.9 days in
  the tropics.
- **Coverage:** Landsat 8 from 2013, Sentinel-2 from 2015; global land
  excluding Antarctica. Extended to present with Sentinel-2C (2024+).
- **Products:** HLSL30, HLSS30; HLS-VI (vegetation indices) introduced
  February 2025; HLS-LL (low latency) anticipated early 2027.
- **Access:** NASA Earthdata, LP DAAC, MPC.
- **License:** modified Copernicus Sentinel data under ESA licensing terms
  (free, open, attribution).
- **Backend choice:** **stream** — HLS is the recommended optical EO source
  for Tier 1 / Tier 3 phenology features.
- **Verified:**
  - https://hls.gsfc.nasa.gov/

### 1.8 Copernicus Global Land Service NDVI 300 m V2

- **Provider:** EEA / European Commission, Copernicus Land Monitoring
  Service.
- **What it provides:** 10-daily global NDVI at 300 m, derived from
  Sentinel-3 OLCI observations — designed for vegetation-trend continuity
  with the earlier PROBA-V era V1 (2014–2020).
- **Spatial resolution:** 300 m.
- **Temporal resolution:** 10-day composites.
- **Coverage:** V2: July 2020 – present (Sentinel-3 era). V1: 2014–2020
  (PROBA-V era). For continuous trend work pre-2014, fall back to
  MOD13Q1 / VNP13A1.
- **Access:** Copernicus Land Monitoring Service portal + Wekeo /
  CDS-Toolbox.
- **License:** Copernicus data policy (free + open).
- **Backend choice:** **stream**.
- **Verified:**
  - https://land.copernicus.eu/en/products/vegetation/normalised-difference-vegetation-index-v2-0-300m
  - https://land.copernicus.eu/global/content/release-300m-ndvi-version-2-based-sentinel-3-observations

### §1 Summary

| Source | Resolution | Revisit | Coverage | Primary use in AIgriculture |
|--------|-----------|---------|----------|------------------------------|
| Sentinel-1 (SAR) | 5–20 m (IW) | 12 d → 6 d (S1C) | 2014 – present | Cloud-immune backscatter, soil moisture, biomass. |
| Sentinel-2 (optical) | 10 / 20 / 60 m | 5 d | 2015 – present | Field-level vegetation indices, crop classification. |
| Sentinel-3 (OLCI/SLSTR) | 300 m / 500 m | < 2 d / < 4 d | 2016 – present | LST, large-region vegetation. |
| Landsat 7/8/9 | 30 m | 16 d / 8 d (L8+9) | 1999 – present | Pre-Sentinel record for hindcast. |
| MOD13Q1 v6.1 | 250 m | 16 d | 2000 – present | Long-term NDVI/EVI trend. |
| VNP13A1 | 500 m | 16 d | 2012 – present | MODIS continuity post-Terra/Aqua. |
| HLS (L30/S30) | 30 m | ~1.4 d | 2013 – present | Recommended Tier 1/Tier 3 optical features. |
| CGLS NDVI 300 m V2 | 300 m | 10 d | 2020 – present (V2) | Region-scale vegetation trend. |

---

## §2 Historical climate / reanalysis

### 2.1 ERA5 (Copernicus reanalysis, single levels)

- **Provider:** ECMWF / Copernicus Climate Change Service (C3S).
- **What it provides:** the flagship global reanalysis. Hundreds of
  atmospheric, ocean-wave, and land-surface variables on a regular grid;
  the most widely cited modern reanalysis for climate-impact work.
- **Spatial resolution:** 0.25° × 0.25° (~28 km at the equator) for the
  reanalysis; uncertainty estimates available at 0.5° from a 10-member
  ensemble at 3-hour intervals.
- **Temporal resolution:** hourly.
- **Coverage:** 1940 – present, updated daily with ~5-day latency.
- **License:** **CC BY 4.0**.
- **DOI:** `10.24381/cds.adbb2d47`.
- **Access:** Copernicus CDS API (`cdsapi`), CDS web interface, also
  mirrored on AWS Open Data and Google Earth Engine.
- **Backend choice:** **stream** for most use cases; consider a regional
  Zarr cache for Quebec subsets at hourly resolution if used heavily
  (rough estimate: a single year of hourly 2 m T + precipitation for the
  Quebec bounding box ≈ a few GB; full multi-decade with many variables
  ≪ 300 GB).
- **Verified:**
  - https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels

### 2.2 ERA5-Land

- **Provider:** ECMWF / C3S.
- **What it provides:** ERA5 forced offline at higher resolution over
  land surfaces, with refined topography. Land-surface variables: skin
  temperature, soil temperature and moisture at four layers (0–7, 7–28,
  28–100, 100–289 cm), runoff, snow, etc.
- **Spatial resolution:** 0.1° × 0.1° (~9 km).
- **Temporal resolution:** hourly.
- **Coverage:** January 1950 – present.
- **License:** **CC BY 4.0**.
- **DOI:** `10.24381/cds.e2161bac`.
- **Access:** Copernicus CDS API.
- **Backend choice:** **stream**; cache derived monthly aggregates locally.
- **Verified:**
  - https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land

### 2.3 AgERA5 (Agrometeorological indicators)

- **Provider:** ECMWF / C3S, derived from ERA5 with topographic correction.
- **What it provides:** an **agriculture-tailored** daily product with 16+
  variables ready for crop modeling — 2 m air & dew-point temperature,
  precipitation (with liquid / solid fractions), solar radiation, 10 m wind
  speed, relative humidity, vapor pressure, Penman-Monteith reference ET,
  vapor pressure deficit, snow metrics. **The recommended historical driver
  for Tier 2 (PCSE / WOFOST) runs.**
- **Spatial resolution:** 0.1° × 0.1° (~9 km).
- **Temporal resolution:** daily (aggregated to local time zones).
- **Coverage:** 1979 – present, updated daily.
- **File format:** NetCDF-4, CF Metadata Convention v1.7.
- **License:** **CC BY 4.0**.
- **DOI:** `10.24381/cds.6c68c9bb`.
- **Access:** Copernicus CDS API.
- **Backend choice:** **local Zarr cache** for the Quebec / eastern Canada
  bounding box — small enough (< 50 GB for the full 1979 – present record)
  to keep on disk; we will read it on every PCSE run.
- **Verified:**
  - https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators

### 2.4 CHIRPS (precipitation)

- **Provider:** UC Santa Barbara Climate Hazards Center (CHC) + USGS / USAID.
- **What it provides:** quasi-global daily / pentad / monthly precipitation
  built from satellite IR observations, rain-gauge calibration, and the
  CHPclim background climatology. Strong in data-sparse regions.
- **Spatial resolution:** 0.05° (~5.5 km).
- **Temporal resolutions:** daily, pentad (5-day), monthly.
- **Coverage:** 1981 – near-present.
- **Geographic extent:** 50°S – 50°N (all longitudes). **NB: Northern Quebec
  is partially outside the 50°N cap — verify per-pixel coverage for the
  region of interest.**
- **License:** effectively public domain (Creative Commons CC0).
- **Citation:** Funk et al. (2015), *Scientific Data*, "The climate hazards
  infrared precipitation with stations" — to be added to `CITATIONS.bib`
  during Phase 1.
- **Backend choice:** **stream**; local cache only if used heavily.
- **Verified:**
  - https://www.chc.ucsb.edu/data/chirps

### 2.5 PRISM (US conterminous)

- **Provider:** PRISM Climate Group, NACSE at Oregon State University.
- **What it provides:** high-resolution gridded historical weather for the
  conterminous US.
- **Spatial resolution:** **4 km** (free) and **800 m** (some products).
- **Temporal resolutions:** daily (1981 – present), monthly (1895 – present),
  annual (1895 – present), and 30-year normals.
- **Variables:** Tmin, Tmax, Tmean, precipitation, dew point, solar
  irradiance (sloped surface).
- **License:** free for public use; terms at https://prism.oregonstate.edu/terms
- **Backend choice:** **stream**; we will need this only when we expand to
  the US (Phase 4).
- **Caveats:** US conterminous only — no Alaska, no Canada.
- **Verified:**
  - https://prism.oregonstate.edu/

### 2.6 E-OBS (Europe gridded observations)

- **Provider:** Royal Netherlands Meteorological Institute (KNMI) + ECA&D
  + Copernicus Climate Change Service (C3S).
- **What it provides:** daily gridded observed weather for Europe based on
  the ECA&D station network. Variables: TG (mean T), TN, TX, RR
  (precipitation), PP (sea-level pressure), HU (RH), FG (wind speed), QQ
  (global radiation).
- **Spatial resolution:** **0.1°** and 0.25° regular grids available.
- **Temporal resolution:** daily.
- **Coverage:** January 1950 – present.
- **Citation:** Cornes et al. (2018), *J. Geophys. Res. Atmospheres* — to be
  added to `CITATIONS.bib`.
- **License:** ECA&D data policy — **strictly non-commercial research and
  education use**; scientific publications must be available without
  commercial delays. Compatible with AIgriculture's open-source / research
  scope but not with future commercial re-distribution.
- **Access:** ECA&D direct download, KNMI Data Platform, Copernicus CDS.
- **Backend choice:** **stream** when expanding to Europe (Phase 4);
  consider local Zarr for the EURO pilot region.
- **Verified:**
  - https://cds.climate.copernicus.eu/datasets/insitu-gridded-observations-europe
  - https://confluence.ecmwf.int/display/CKB/E-OBS+daily+gridded+observations+for+Europe+from+1950+to+present:+Product+user+guide

### 2.7 Daymet (North America)

- **Provider:** ORNL DAAC, Daymet team at Oak Ridge.
- **What it provides:** the highest-resolution open daily weather grid for
  North America: minimum and maximum temperature, precipitation, vapor
  pressure, shortwave radiation, snow water equivalent, and day length.
- **Spatial resolution:** **1 km × 1 km**.
- **Temporal resolution:** daily.
- **Coverage:** continental North America + Hawaii from 1980; Puerto Rico
  from 1950; extends through the end of the most recent full calendar year.
- **Current version:** **Daymet v4** (released 15 December 2020).
- **Access:** ORNL DAAC THREDDS, NetCDF subset, RESTful single-pixel
  extraction API, full bulk download.
- **License:** open data (NASA Earthdata); attribution requested.
- **Backend choice:** **local Zarr cache** for the Quebec / eastern Canada
  subset — the high resolution makes per-province caching cost-effective
  and fast for repeat reads (the regional subset is < 100 GB).
- **Verified:**
  - https://daymet.ornl.gov/

### 2.8 ECCC AHCCD — Adjusted and Homogenized Canadian Climate Data

- **Provider:** Environment and Climate Change Canada (ECCC), Canadian
  Centre for Climate Services.
- **What it provides:** station-level homogenized historical climate
  observations for Canada. For AIgriculture this is the most reliable
  ground-truth for **hindcast validation** in Quebec.
- **Variables:**
  - Daily max / min / mean surface air temperature — > 330 stations.
  - Daily rainfall / snowfall / total precipitation — > 460 stations.
  - Monthly / seasonal / annual mean hourly wind speed — 156 stations.
  - Monthly / seasonal / annual mean sea-level + station pressure — 626
    stations.
- **Spatial extent:** stations across Canada (point data).
- **Temporal extent:** daily back to early-to-mid 20th century at many
  stations; precise per-station coverage in the technical documentation.
- **License:** **Open Government Licence — Canada**.
- **Access:**
  - GeoMet OGC API: `https://api.weather.gc.ca/collections/ahccd-annual`
    (and the daily T&P collection).
  - Open Government Portal: `open.canada.ca` (datasets
    `d6813de6-…` for daily T&P, `9c4ebc00-…` for the master AHCCD entry).
- **Backend choice:** **local cache** as Parquet (point time series — small).
- **Verified:**
  - https://api.weather.gc.ca/collections/ahccd-annual?lang=en
  - https://open.canada.ca/data/en/dataset/d6813de6-b20a-46cc-8990-01862ae15c5f
  - https://www.canada.ca/en/environment-climate-change/services/climate-change/science-research-data/climate-trends-variability/adjusted-homogenized-canadian-data.html

### 2.9 CanGRD — Canadian Gridded Climate Anomalies

- **Provider:** ECCC.
- **What it provides:** gridded monthly / seasonal / annual temperature and
  precipitation **anomalies** over Canada, interpolated from AHCCD
  stations. Useful as a long-term spatial reference of how the climate of
  Quebec has changed since the early 20th century — the *signal* without
  having to manage all the stations directly.
- **Spatial resolution:** **50 km**.
- **Temporal resolution:** monthly, seasonal, annual.
- **Coverage:** 1948 – previous full calendar year (all of Canada);
  southern Canada from 1900. Baseline reference period: 1961–1990.
- **License:** Open Government Licence — Canada.
- **Access:** ECCC MSC Open Data; Open Government Portal datasets
  `3d4b68a5-…`, `e55959c6-…`, `e61aea77-…`.
- **Backend choice:** **local cache** (small).
- **Caveats:** Anomaly product; not absolute values. 50 km coarser than
  Daymet's 1 km; complementary use, not redundant.
- **Verified:**
  - https://open.canada.ca/data/en/dataset/3d4b68a5-13bc-48bb-ad10-801128aa6604
  - https://eccc-msc.github.io/open-data/msc-data/climate_cangrd/readme_cangrd-datamart_en/

### §2 Summary and recommendation

| Source | Resolution | Cadence | Coverage | Role |
|--------|-----------|---------|----------|------|
| ERA5 | 0.25° | hourly | 1940 – present | Global reanalysis baseline. |
| ERA5-Land | 0.1° | hourly | 1950 – present | Higher-resolution land surface. |
| **AgERA5** | 0.1° | **daily** | 1979 – present | **Primary historical driver for Tier 2 (WOFOST).** |
| CHIRPS | 0.05° | daily | 1981 – present (50°S–50°N) | Independent precipitation. |
| PRISM | 4 km / 800 m | daily / monthly | 1895 – present (CONUS) | Phase 4 US expansion. |
| E-OBS | 0.1° | daily | 1950 – present (Europe) | Phase 4 EU expansion. |
| Daymet v4 | 1 km | daily | 1980 – present (NA) | **High-res driver for Quebec MVP.** |
| **AHCCD** | stations | daily | early-20C – present (Canada) | **Hindcast ground truth.** |
| CanGRD | 50 km | monthly | 1900 / 1948 – present | Long-term anomaly reference. |

**Recommendation for the Quebec MVP:**
- **Driver for crop models:** AgERA5 (primary) + Daymet v4 (high-res
  cross-check).
- **Hindcast validation:** AHCCD stations + CanGRD anomalies.
- Reserve ERA5 / ERA5-Land for diagnostics that need finer-than-daily
  cadence or non-agro variables.

---
## §3 Climate projections

Climate-change scenarios for AIgriculture come from the **CMIP6** ensemble.
Raw CMIP6 output is at ~100–250 km resolution — too coarse for agricultural
impact at field / regional scale. We therefore use **downscaled, bias-
corrected derivatives**. For the Quebec MVP the leading candidate is
**CanDCS-M6** (Canadian-tuned). Globally, NEX-GDDP-CMIP6 and CHELSA-CMIP6
are the standard reference products and serve as cross-checks and as the
expansion path for North America and Europe.

### 3.1 CMIP6 raw output via ESGF

- **Provider:** WCRP CMIP Panel; data distributed via the Earth System Grid
  Federation (ESGF) and mirrors.
- **What it provides:** the raw GCM ensemble — > 100 models from
  ~50 modelling centres, including historical and future SSP simulations.
- **Spatial resolution:** native model grids, typically ~100 km (atmosphere)
  / ~1° (ocean); varies by model.
- **Temporal resolution:** mostly monthly and daily; some sub-daily.
- **SSPs:** SSP1-1.9, SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP4-3.4, SSP4-6.0,
  SSP5-3.4OS, SSP5-8.5 — though not every model runs every scenario.
- **License:** majority **CC BY 4.0**; a minority **CC BY-NC** or
  **CC BY-NC-SA**. License is per-model; must be checked per use.
- **Access:** ESGF Metagrid (`https://metagrid.esgf-west.org/search/cmip6/`),
  Pangeo CMIP6 Zarr cloud catalogue (`gs://cmip6` / `s3://esgf-world`),
  Google Cloud CMIP6 archive.
- **Backend choice:** **stream** via Pangeo Zarr — best ergonomics for
  ensemble work. Raw CMIP6 is rarely used directly; we will use it mostly
  to build / validate the downscaled products and to access variables that
  derived products don't expose.
- **Caveats:** very large archive (PB-scale globally); license is
  per-model and must be tracked.

### 3.2 NEX-GDDP-CMIP6

- **Provider:** NASA Ames Earth Exchange.
- **What it provides:** the global downscaled, bias-corrected daily CMIP6
  product. Standard reference for global impact studies; widely cited.
- **Spatial resolution:** **0.25°** (~25 km).
- **Temporal resolution:** daily.
- **Coverage:** 1950 – 2100 (historical + projections).
- **Bias-correction method:** Bias Correction and Spatial Disaggregation
  (BCSD-like, NASA Ames implementation).
- **Variables:** at minimum Tmin, Tmax, precipitation; expanded variable set
  in the latest releases.
- **GCMs / SSPs:** "Tier 1" SSPs (SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5);
  GCM list per dataset — confirm via the technical note at the start of
  any production run.
- **Geographic extent:** 90°N – 60°S, all longitudes.
- **Archive size:** ~38 TB total.
- **License:** US public-sector data; free with attribution.
- **Access:**
  - AWS Open Data: `s3://nex-gddp-cmip6`.
  - NASA NCCS THREDDS:
    `https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/catalog.html`.
  - Google Earth Engine: `NASA/GDDP-CMIP6`.
- **Backend choice:** **stream from AWS / Earth Engine**; never download
  the whole archive. For Quebec, stream the bounding-box subset and
  optionally cache a per-GCM × per-SSP daily Zarr (a few GB each).
- **Verified:**
  - https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6

### 3.3 CHELSA-CMIP6

- **Provider:** Swiss Federal Research Institute WSL, ETH Zürich
  (CHELSA-Climate group).
- **What it provides:** 1 km global downscaled CMIP6 — the highest spatial
  resolution of the widely-used CMIP6 downscaled products. Built by
  topographic downscaling using the CHELSA V2.1 algorithm (trend-
  preserving, delta change method).
- **Spatial resolution:** **30 arc-seconds (~1 km)**.
- **Temporal resolution:** monthly (climatologies) and derived bioclimatic
  variables (BIO01–BIO19).
- **Coverage:** historical + three future periods (2011–2040, 2041–2070,
  2071–2100).
- **Bias-correction method:** trend-preserving bias correction before
  downscaling; delta change for projections.
- **GCMs / SSPs:** a selected subset of CMIP6 models × SSPs (not the full
  ensemble — chosen for spread). Exact list at the project page.
- **Companion product:** **CHELSA-W5E5** — daily 1 km historical forcing
  (T, P, downwelling shortwave) for impact studies (1979 – present).
- **Python tooling:** the `chelsa-cmip6` PyPI package can regenerate any
  region's bioclimatic variables programmatically.
- **License:** CC BY 4.0.
- **Access:** `https://chelsa-climate.org/`, EnviDat archives.
- **Backend choice:** **local cache** of the Quebec bounding-box monthly
  rasters — small (few GB) and re-used heavily by Tier 1 envelope screening.
- **Caveats:** monthly cadence is the *normal* CHELSA-CMIP6 product —
  daily-resolution future projections require CHELSA-W5E5 (historical)
  combined with the GCM delta separately.
- **Verified:**
  - https://chelsa-climate.org/cmip6/ (search-result corroboration; the
    canonical page was 404 at the time of writing; reverify before code
    development)

### 3.4 ISIMIP3b

- **Provider:** Inter-Sectoral Impact Model Intercomparison Project (PIK).
- **What it provides:** the standard impact-modelling input archive,
  bias-corrected CMIP6 driving the official global crop / hydrology / fish /
  forest impact model intercomparison. **If we run PCSE/WOFOST in a way
  that should be comparable to GGCMI Phase 3 outputs, ISIMIP3b is the right
  forcing.**
- **Spatial resolution:** 0.5° (~50 km).
- **Temporal resolution:** daily.
- **Coverage:** pre-industrial control, historical, and three SSPs
  (SSP1-RCP2.6, SSP3-RCP7.0, SSP5-RCP8.5).
- **Bias-correction method:** ISIMIP3BASD (Lange 2019) [@Lange2019] — the
  trend-preserving quantile-mapping method, corrected toward
  W5E5 observations.
- **License:** CC BY 4.0.
- **Access:** ISIMIP data portal + ESGF mirror.
- **Backend choice:** **stream**; small enough to local-cache the Quebec
  bounding box if used heavily.
- **Verified:**
  - https://www.isimip.org/protocol/3/

### 3.5 CanDCS-M6 — Canadian Downscaled Climate Scenarios (Multivariate) CMIP6

- **Provider:** Pacific Climate Impacts Consortium (PCIC) + Canadian Centre
  for Climate Services (CCCS) + Environment and Climate Change Canada.
- **What it provides:** **the Canadian-tuned downscaled CMIP6 product.**
  Daily downscaled Tmin / Tmax / precipitation plus 30+ derived climate
  indices, with explicit preservation of multivariate relationships between
  variables (essential for crop modeling, where T × P joint behaviour
  matters).
- **Spatial resolution:** **~6 × 10 km** (Canada-wide).
- **Temporal resolution:** daily.
- **Coverage:** historical 1971–2000; future 2041–2070 (mid-century) and
  2071–2100 (late-century). The companion **CanDCS-U6** (univariate,
  BCCAQv2) extends through 1950–2014 + 2015–2100.
- **Bias-correction method:** **n-dimensional Multivariate Bias Correction
  (MBCn)**, building on BCCAQv2 / QDM.
- **GCMs:** **26 CMIP6 models** for SSP1-2.6, SSP2-4.5, SSP5-8.5; **24
  models** for SSP3-7.0.
- **SSPs:** SSP1-2.6, SSP2-4.5, SSP3-7.0 (added in 2024), SSP5-8.5.
- **Citation:** Sobie, S. R., Ouali, D., Curry, C. L., & Zwiers, F. W.
  (2024). Multivariate Canadian Downscaled Climate Scenarios for CMIP6
  (CanDCS-M6). *Geoscience Data Journal* **11**: 806–824.
  DOI: `10.1002/gdj3.257`.
- **Access:** `climatedata.ca` (maps + downloads), `pavics.ouranos.ca`
  (U6 predecessor), CCCS data portal.
- **License:** Open Government Licence — Canada (confirm per dataset).
- **Backend choice:** **local Zarr** for the Quebec bounding box for the
  full 26-GCM × 4-SSP ensemble — easily under 300 GB and re-read on every
  recommendation request.
- **Verified:**
  - https://climatedata.ca/resource/intro-to-candcs-m6/
  - https://rmets.onlinelibrary.wiley.com/doi/10.1002/gdj3.257

### 3.6 EURO-CORDEX & NA-CORDEX (dynamical regional downscaling)

- **Provider:** WCRP CORDEX, regional domains.
- **What it provides:** **dynamically** downscaled regional climate model
  (RCM) output — captures local terrain, mesoscale effects, and physical
  processes that statistical downscaling can miss.
- **EURO-CORDEX:** 11 km (EUR-11) and 44 km (EUR-44) grids, multiple
  RCM × GCM combinations, RCP2.6 / 4.5 / 8.5 originally (CMIP5-driven);
  CMIP6-driven ensembles are emerging in 2024–2025.
- **NA-CORDEX:** **0.22° (~25 km) and 0.44° (~50 km)** over North America,
  multiple RCM × GCM combinations, 1950 – 2100.
- **License:** "Freely available under the Terms of Use"; cite Mearns et
  al. (2017) for NA-CORDEX, DOI `10.5065/D6SJ1JCH`.
- **Access:** ESGF, NSF NCAR Geodata Science Exchange (GDEX), AWS Open Data
  for Zarr versions.
- **Backend choice:** **stream**; consider for Phase 4 expansion when
  multi-region dynamical projections matter. For Quebec MVP, prefer CanDCS-M6
  for daily ensemble work; reserve NA-CORDEX as a dynamical cross-check.
- **Verified:**
  - https://na-cordex.org/
  - https://www.euro-cordex.net/ (corroborated by search-result summaries)

### §3 Summary and recommendation

| Source | Resolution | Cadence | GCMs / SSPs | Bias correction | Primary use |
|--------|-----------|---------|-------------|------------------|-------------|
| CMIP6 (ESGF + Pangeo) | ~100 km | mostly daily / monthly | full ensemble | none | reference / fallback variables |
| **NEX-GDDP-CMIP6** | 0.25° | daily | "Tier 1" SSPs | BCSD-like | global cross-check |
| **CHELSA-CMIP6** | 1 km | monthly + bioclim | subset of GCMs | trend-preserving + delta | Tier 1 high-resolution envelope |
| **ISIMIP3b** | 0.5° | daily | 3 SSPs | ISIMIP3BASD (Lange 2019) | GGCMI alignment |
| **CanDCS-M6** | ~6–10 km | daily | 26 (24) GCMs × 4 SSPs | MBCn (multivariate) | **Quebec MVP primary** |
| EURO-CORDEX / NA-CORDEX | 11–50 km | daily | RCM × GCM | none / per-product | dynamical cross-check |

**Recommendation for Quebec MVP (ADR 0002):**
- **Primary:** CanDCS-M6 daily Tmin / Tmax / precipitation + indices
  (multivariate, Canadian-tuned, 26 GCMs × 4 SSPs).
- **Cross-check:** NEX-GDDP-CMIP6 (independent BCSD-style downscaling).
- **High-resolution envelope:** CHELSA-CMIP6 1 km monthly bioclimatic
  variables for Tier 1 screening.
- **Standard SSP set:** SSP1-2.6, SSP2-4.5, SSP5-8.5. Optionally add
  SSP3-7.0 once stable in CanDCS-M6.
- **GCM short-list (provisional):** select ~5–7 GCMs that (i) appear in
  CanDCS-M6, NEX-GDDP-CMIP6, *and* ISIMIP3b, (ii) span the equilibrium-
  climate-sensitivity range, and (iii) perform well over the Canadian
  domain per existing literature. The exact list will be ratified in ADR
  0005.

---
## §4 Soil

Soil is one of the four inputs (climate, soil, terrain, management) that
the GAEZ methodology and process-based crop models depend on. AIgriculture
needs at minimum: texture (sand / silt / clay), pH, soil organic carbon,
bulk density, and rooting depth, at multiple depths, for every grid cell.

### 4.1 SoilGrids 2.0 (ISRIC)

- **Provider:** ISRIC — World Soil Information.
- **What it provides:** the global digital soil mapping reference.
  Machine-learning predictive maps of 14 soil properties at six standard
  GlobalSoilMap depth intervals (0–5, 5–15, 15–30, 30–60, 60–100,
  100–200 cm), with per-pixel uncertainty.
- **Spatial resolution:** **250 m**.
- **Properties:** pH (H2O), soil organic carbon content, bulk density,
  coarse fragments, sand %, silt %, clay %, cation exchange capacity, total
  nitrogen, soil organic carbon density and stock, plus a few derived
  variables (USDA classes, WRB classes).
- **Coverage:** global.
- **License:** **CC BY 4.0**.
- **Access:**
  - WebDAV / Cloud-Optimized GeoTIFF: `https://files.isric.org/soilgrids/latest/data/`
  - WCS / WMS endpoints (legacy; intermittent).
  - REST API (note: ISRIC documents intermittent issues; verify at run time).
  - Available on Microsoft Planetary Computer STAC collection.
- **Backend choice:** **local cache** of the Quebec / eastern Canada
  bounding box (small — single-digit GB for the depth/property set we
  need); also keep the COG-on-MPC streaming path as a fallback.
- **Verified:**
  - https://www.isric.org/explore/soilgrids

### 4.2 LUCAS Soil (Europe)

- **Provider:** EU Joint Research Centre (JRC), European Soil Data Centre
  (ESDAC).
- **What it provides:** the largest harmonized open soil dataset for
  Europe. Topsoil (0–20 cm) physico-chemical measurements from ~19,000
  points sampled in a single co-ordinated campaign (~April–October 2018).
- **Variables:** texture, organic carbon, pH, nitrogen, P, K, CEC, plus
  spectral and metals analyses. The 2022 follow-up campaign is in
  preparation.
- **License:** open access via ESDAC (registration required for downloads;
  research-friendly terms).
- **Citation:** Orgiazzi, A. et al. (2018). LUCAS Soil, the largest
  expandable soil dataset for Europe: a review. *European Journal of Soil
  Science* — to add to `CITATIONS.bib`.
- **Backend choice:** **local cache** as Parquet (point measurements —
  small). Phase 4 (Europe expansion).
- **Verified:**
  - https://esdac.jrc.ec.europa.eu/content/lucas-2018-topsoil-data

### 4.3 SSURGO / STATSGO2 / gNATSGO (US)

- **Provider:** USDA Natural Resources Conservation Service (NRCS).
- **What it provides:** detailed soil survey for the US.
  - **SSURGO** — typically 1:24,000 scale; the most detailed product.
  - **STATSGO2** — 1:250,000 scale; complete national coverage including
    areas not yet mapped in SSURGO.
  - **gNATSGO** — pre-rasterized national product blending SSURGO + STATSGO2
    at 10 m grid; the recommended single-product choice for analysis.
- **Variables:** very rich — particle-size fractions, organic matter, bulk
  density, AWC, pH, salinity, drainage class, hydric rating, etc.
- **License:** US government work, public domain.
- **Access:** Web Soil Survey, USDA Geospatial Data Gateway, the
  **gNATSGO** raster on Microsoft Planetary Computer (STAC).
- **Backend choice:** **stream** from MPC; cache derived properties for US
  pilot regions when we expand (Phase 4).
- **Caveats:** access endpoint had a transient timeout during research —
  reverify before use.

### 4.4 AAFC Soil Landscapes of Canada (SLC) v3.2

- **Provider:** Agriculture and Agri-Food Canada (AAFC), Canadian Soil
  Information Service (CanSIS), via the National Soil Database (NSDB).
- **What it provides:** **the primary soil dataset for Quebec MVP.** GIS
  polygon coverage of Canada at 1:1,000,000 compilation scale, attributing
  each polygon with one or more soil-landscape components, plus surface
  form, slope, water-table depth, permafrost, lakes, and component-level
  soil properties.
- **Scale:** 1:1,000,000 (polygon — *not* gridded). Coarser than SoilGrids
  but Canadian-specific and grounded in Canadian soil-survey practice.
- **Current version:** **3.2** (2011).
- **License:** Open Government Licence — Canada (verify per dataset on
  download).
- **Access:** CanSIS National Soil Database via
  `https://sis.agr.gc.ca/cansis/nsdb/slc/index.html`; bulk download.
- **Backend choice:** **local cache** as GeoPackage; small. Use *in
  conjunction* with SoilGrids — SLC gives the Canadian-validated polygon
  description; SoilGrids fills in continuous grid where the SLC component
  data are categorical.
- **Verified:**
  - https://sis.agr.gc.ca/cansis/nsdb/slc/index.html

### 4.5 HWSD v2.0 (FAO Harmonized World Soil Database)

- **Provider:** FAO / IIASA.
- **What it provides:** global harmonized soil database at 30 arc-second
  (~1 km) resolution. Useful as a sanity-check global product and the
  legacy input for many earlier impact studies.
- **Spatial resolution:** ~1 km (30 arc-seconds).
- **Depth layers:** seven layers (0–20, 20–40, 40–60, 60–80, 80–100,
  100–150, 150–200 cm).
- **Variables:** texture (USDA class), effective CEC, total N, C/N,
  aluminium saturation, bulk density, rootable depth, available water
  capacity (AWC), with error estimates.
- **License:** FAO licence terms — verify per use; some FAO products are
  CC BY-NC-SA.
- **Access:** FAO Soils Portal; .mdb + raster + technical documentation.
- **Backend choice:** **stream / one-time download**; secondary to
  SoilGrids 2.0 (newer, ML-based, openly licensed) but useful for
  cross-product comparison.
- **Verified:**
  - https://www.fao.org/soils-portal/data-hub/soil-maps-and-databases/harmonized-world-soil-database-v20/en/

### §4 Summary and recommendation

| Source | Resolution | Depth | Coverage | License | Role |
|--------|-----------|-------|----------|---------|------|
| **SoilGrids 2.0** | 250 m grid | 6 layers to 2 m | Global | CC BY 4.0 | **Primary continuous grid.** |
| LUCAS Soil 2018 | points | 0–20 cm | Europe | open (ESDAC) | EU pilot, ground truth. |
| SSURGO / gNATSGO | 10 m grid (gNATSGO) | many | US | public domain | US pilot. |
| **SLC v3.2 (AAFC)** | polygons (1:1M) | per component | Canada | OGL-Canada | **Quebec MVP polygon layer.** |
| HWSD v2.0 | ~1 km | 7 layers to 2 m | Global | FAO terms | Cross-product check. |

**Recommendation:** SoilGrids 2.0 is the primary continuous-grid soil
source; SLC v3.2 supplements it with Canadian-validated polygon
attributes for the Quebec MVP. HWSD v2 stays in reserve.

---
## §5 Topography

Topography feeds three things: (i) downscaling of climate variables to
finer grids, (ii) slope / aspect adjustments in suitability scoring, and
(iii) hydrological masking of inarable terrain.

### 5.1 Copernicus DEM GLO-30

- **Provider:** ESA / Copernicus (data from DLR TanDEM-X mission, processed
  by Airbus DS).
- **What it provides:** the **recommended primary DEM**. A 30 m global
  Digital Surface Model derived from TanDEM-X — the most recent and most
  accurate open global DEM.
- **Spatial resolution:** 30 m (GLO-30); GLO-90 alternative at 90 m.
- **Vertical accuracy:** Global RMSE **1.68 m** (validated against ICESat GLAS).
- **Coverage:** global. (A small number of country tiles remain restricted;
  Canada is included.)
- **License:** free for general public use under Copernicus terms;
  © DLR and Airbus DS, distributed by ESA / EU.
- **Access:**
  - AWS Open Data S3: `s3://copernicus-dem-30m/` (Cloud-Optimized GeoTIFFs).
  - Copernicus Data Space.
  - OpenTopography.
  - Microsoft Planetary Computer STAC.
  - Google Earth Engine: `COPERNICUS/DEM/GLO30`.
- **Backend choice:** **stream** via STAC; cache the Quebec tiles locally
  (small, < 5 GB).
- **Verified:**
  - https://registry.opendata.aws/copernicus-dem/
  - https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

### 5.2 SRTM v3 (NASA / USGS)

- **Provider:** NASA JPL + USGS LP DAAC.
- **What it provides:** the original global open-DEM standard. SRTM-V3
  (also called "SRTM Plus") is void-filled using ASTER GDEM, GMTED 2010
  and the US NED.
- **Spatial resolution:** 30 m globally (US 1 arc-second; global 3 arc-second
  in earlier releases — V3 expanded 1 arc-second to global).
- **Coverage:** 60°N – 56°S. **Quebec coverage: only the southern portion
  below 60°N — northern Quebec is outside SRTM.** Use Copernicus DEM
  there.
- **License:** open distribution.
- **Access:** USGS Earthdata, AWS Open Data, Google Earth Engine.
- **Backend choice:** secondary to Copernicus DEM; useful only when a
  matching SRTM-era product is needed for historical reproducibility.
- **Verified:**
  - https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003

### 5.3 ASTER GDEM v3

- **Provider:** NASA / METI (Japan).
- **What it provides:** stereo-derived global DEM at 1 arc-second. Used
  primarily as a void-fill for SRTM and as a high-latitude alternative.
- **Coverage:** 83°N – 83°S (covers all of Quebec including the far north).
- **Status:** **secondary** for AIgriculture — Copernicus DEM GLO-30 is
  newer and more accurate. Mention only as a cross-product check at
  northern latitudes where SRTM is missing.
- **Caveats:** known artefacts in mountainous and forested terrain.

### §5 Recommendation

**Copernicus DEM GLO-30** as the primary global DEM. SRTM v3 for
historical / SRTM-era benchmarking; ASTER GDEM v3 as a northern-latitude
fallback in the rare cases the Copernicus product has gaps.

---
## §6 Land cover & crop maps

These datasets answer two questions: (i) **where can crops grow at all**
(land cover) and (ii) **what is currently grown where** (crop-specific
maps), the latter being indispensable for present-day calibration and
hindcast comparison.

### 6.1 ESA WorldCover

- **Provider:** ESA WorldCover consortium (VITO, Brockmann Consult, CS,
  Wageningen University, GAMMA, IIASA).
- **What it provides:** the first 10 m global land-cover product
  generated annually from a Sentinel-1 + Sentinel-2 fusion.
- **Spatial resolution:** **10 m**.
- **Classes:** 11 standard land-cover classes (cropland, tree cover, etc.).
- **Available years:** **2020** (V100) and **2021** (V200).
- **License:** CC BY 4.0.
- **Access:** AWS Open Data (STAC), Microsoft Planetary Computer, Google
  Earth Engine, ESA WorldCover viewer.
- **Backend choice:** **stream**.
- **Verified:**
  - https://esa-worldcover.org/en

### 6.2 USDA Cropland Data Layer (CDL)

- **Provider:** USDA NASS.
- **What it provides:** annual crop-specific raster for the US — the gold
  standard for US crop maps.
- **Spatial resolution:** **30 m historically; 10 m starting with the
  2024 CDL (released 2025)**; a 30 m resampled version remains for
  historical continuity.
- **Classes:** **133 map categories**.
- **Coverage:** conterminous US + Hawaii (HCDL added 2025). National
  coverage from 2008; some states earlier; the program traces to 1971.
- **Cadence:** annual.
- **License:** US government work — public domain (NASS does not require
  registration for the published CDL).
- **Access:** CroplandCROS web app, USDA NASS National Download, CDL
  Viewer on Earth Engine.
- **Backend choice:** **stream** (Phase 4 US expansion).
- **Verified:**
  - https://www.nass.usda.gov/Research_and_Science/Cropland/SARS1a.php

### 6.3 AAFC Annual Crop Inventory (ACI)

- **Provider:** Agriculture and Agri-Food Canada (AAFC), Earth Observation
  Team.
- **What it provides:** **the Canadian counterpart to the US CDL — primary
  current-day crop map for the Quebec MVP.** Annual national crop-type
  classification from optical (Landsat / AWiFS / DMC / now Sentinel-2)
  and radar (RADARSAT-2) imagery.
- **Spatial resolution:** **30 m** (56 m in the first two years 2009–2010).
- **Coverage start:** **2009** (gradual extension to all provinces by
  2011).
- **Geographic extent:** Canada (with caveats — the historical extent
  expanded from Prairies to all provinces over 2009–2011).
- **Classes:** ~72 classes, including specific crop types, water, urban,
  forest.
- **Reported accuracy:** overall ≥ 85%.
- **License:** **Open Government Licence — Canada (OGL-Canada-2.0)**.
- **Access:**
  - Open Government Portal:
    `https://open.canada.ca/data/en/dataset/ba2645d5-4458-414d-b196-6303ac06c1c9`.
  - AAFC interactive map: `https://agriculture.canada.ca/atlas/aci`.
  - Google Earth Engine: `AAFC/ACI`.
- **Backend choice:** **stream from Earth Engine + cache Quebec annual
  rasters locally** — small (a few GB per year for Quebec at 30 m).
- **Verified:**
  - https://developers.google.com/earth-engine/datasets/catalog/AAFC_ACI
  - https://open.canada.ca/data/en/dataset/ba2645d5-4458-414d-b196-6303ac06c1c9
- **ISO 19131 spec:** https://agriculture.canada.ca/atlas/data_donnees/annualCropInventory/supportdocument_documentdesupport/en/ISO%2019131_AAFC_Annual_Crop_Inventory_Data_Product_Specifications.pdf

### 6.4 CORINE Land Cover

- **Provider:** European Environment Agency (EEA), Copernicus Land
  Monitoring Service.
- **What it provides:** harmonized European land-cover at 44 thematic
  classes (Level 3).
- **Update cycle:** every 6 years — 1990, 2000, 2006, 2012, 2018; the next
  in the cycle is 2024.
- **Geographic extent:** EEA-39 (most of Europe; coverage details per
  release).
- **Minimum mapping unit:** 25 ha for land cover; 5 ha for land-cover
  *change*.
- **License:** open and free; Copernicus terms.
- **Access:** Copernicus Land Monitoring Service portal; Wekeo.
- **Backend choice:** **stream** (Phase 4 EU expansion).
- **Caveats:** coarser MMU than WorldCover; not field-level. Use
  WorldCover (10 m) for the cropland mask; use CORINE for European policy
  /-context views.
- **Verified:**
  - https://land.copernicus.eu/en/products/corine-land-cover

### 6.5 EuroCrops / EuroCropsML / Sen4AgriNet

- **Provider:** academic / industry community (`dida-do/eurocropsml`,
  EuroCrops project).
- **What it provides:** harmonized European farmer-declaration crop labels
  (LPIS-derived) joined to Sentinel-2 time series at the parcel level. Up
  to **176 crop classes**, **706,683 labeled parcels** in
  EuroCropsML (2025).
- **License:** open on Zenodo (CC BY).
- **Citation:** Reuß et al. (2025), *Scientific Data*, "The EuroCropsML
  time series benchmark dataset for few-shot crop type classification in
  Europe" — to add to `CITATIONS.bib`.
- **Access:** Zenodo + GitHub `dida-do/eurocropsml`.
- **Backend choice:** **local** for ML / model training when we expand to
  Europe.
- **Caveats:** parcel-level — different format from raster crop maps;
  pairs well with Sentinel-2 features for ML.
- **Verified:**
  - https://www.nature.com/articles/s41597-025-04952-7
  - https://github.com/dida-do/eurocropsml

### §6 Summary and recommendation

| Source | Resolution | Cadence | Coverage | Role |
|--------|-----------|---------|----------|------|
| ESA WorldCover | 10 m | 2020, 2021 | global | Cropland mask (any region). |
| USDA CDL | 30 m → 10 m | annual | US + HI | US pilot crop map. |
| **AAFC ACI** | 30 m | annual since 2009 | Canada | **Quebec MVP current-day crop map.** |
| CORINE | 25 ha MMU | 6-yearly | Europe | EU context / change product. |
| EuroCrops(ML) | parcel-level | 2021 (and others) | EU | EU ML training set. |

**Recommendation:** ESA WorldCover (10 m, latest year) as the cropland
mask for *any* region. **AAFC ACI as the current-day crop map for the
Quebec MVP** — also our reference for present-day model sanity-checks (does
our model recommend what's currently grown?).

---
## §7 Historical crop production statistics

These are the ground-truth datasets for the **hindcast harness**. Each
covers crop area, production, and yield, but at different spatial and
temporal granularities, with different known confounders, and under
different licenses.

### 7.1 FAOSTAT (global national-level)

- **Provider:** FAO Statistics Division.
- **What it provides:** the global reference for national agricultural
  statistics — area harvested, yield, production for ~170 commodities
  across ~245 countries.
- **Geographic granularity:** national (sub-national only via member
  states' own datasets, not standardized here).
- **Temporal coverage:** **1961 – present**.
- **License:** CC BY 4.0 (FAOSTAT data policy; verify per dataset).
- **Access:** FAOSTAT web portal + bulk download + the `faostat` R / Python
  packages.
- **Backend choice:** **local cache** (small — a few hundred MB for the
  full crops time series).
- **Caveats:** quality varies by country / era; reported yields blend
  irrigated and rainfed where applicable.
- **Verified:**
  - https://www.fao.org/faostat/en/#data/QCL

### 7.2 GDHY — Global Dataset of Historical Yields (Iizumi & Sakai 2020)

- **Provider:** Iizumi & Sakai (NIAES) — Scientific Data 2020 [@IizumiSakai2020].
- **What it provides:** **gridded** yield estimates for **maize, rice,
  wheat, soybean** at 0.5° grid, 1981–2016, hybridizing FAOSTAT national
  yields with satellite-derived productivity to disaggregate spatially.
- **Spatial resolution:** **0.5°** grid.
- **Temporal coverage:** 1981 – 2016.
- **License:** CC BY 4.0 (Scientific Data); also archived on PANGAEA.
- **Access:** PANGAEA dataset; v1.3 aligned to v1.2 for time-series
  continuity.
- **Backend choice:** **local cache** (~10s of MB per crop).
- **Caveats:** depends on FAOSTAT national totals (so inherits FAOSTAT's
  national-quality variation) and on remote-sensing inputs (so degrades in
  the pre-satellite era and on cloud-prone regions).

### 7.3 USDA NASS QuickStats

- **Provider:** USDA NASS.
- **What it provides:** **the highest-quality sub-national agricultural
  statistics in the world** — county-, agricultural-district-, watershed-,
  and state-level data for hundreds of commodities. Including area, yield,
  production, prices, sales, demographics.
- **Geographic granularity:** national, state, **county**, agricultural
  district, watershed, zip code, multi-state.
- **Temporal coverage:** **1850 – 2026** (per-commodity coverage varies);
  modern crop area/yield/production typically reliable from the 1920s
  onward, more so from the 1960s.
- **License:** US government work — public domain.
- **Access:** QuickStats web interface + REST API (`api.nass.usda.gov`)
  + bulk download.
- **Backend choice:** **local cache** as Parquet (Phase 4 US expansion).
- **Verified:**
  - https://quickstats.nass.usda.gov/

### 7.4 Eurostat regional crop statistics

- **Provider:** Eurostat.
- **What it provides:** harmonized European crop area / production / yield
  statistics from EU-27 (and some EFTA) member states.
- **Geographic granularity:** **NUTS-2** (regional, sub-national);
  partial NUTS-3.
- **Temporal coverage:** ~1970s – present (per-member-state coverage
  varies).
- **Key dataset codes:** `apro_cpsh1`, `apro_cpshr` (and related).
- **License:** Eurostat data policy — CC BY 4.0.
- **Access:** Eurostat web tables + bulk JSON / TSV + the `eurostat` Python
  package.
- **Companion dataset:** a 2025 *Scientific Data* harmonized EU-27 crop
  statistics dataset (Nature Scientific Data 2025; to add to
  `CITATIONS.bib`) consolidates 2017–2021 area + production at NUTS-2
  for reproducibility.
- **Backend choice:** **local cache** (small).
- **Caveats:** the EU Common Agricultural Policy (CAP) reform of 1992 and
  successive reforms create structural breaks; document these in the
  hindcast harness.

### 7.5 Statistics Canada Census of Agriculture + Field Crop Reporting Series

- **Provider:** Statistics Canada.
- **Two complementary datasets:**
  - **Census of Agriculture** — comprehensive farm-level enumeration,
    **every 5 years** (most recent: 2021; next: 2026). Census Agricultural
    Regions (CARs) granularity.
  - **Field Crop Reporting Series (FCRS)** — annual area / yield /
    production for principal field crops, provincial granularity, with
    intra-season releases (March, June, September, November). Since 2017,
    the September release is replaced by model-based estimates from
    satellite imagery — an interesting precedent for AIgriculture's own
    methodology.
- **Geographic granularity:** national, provincial, Census Agricultural
  Region (CAR), Small Area Data Regions.
- **Key tables:** `32-10-0359-01` (annual areas, yield, production at
  national + provincial scale), `32-10-0002-01` (Small Area Data Regions),
  and others.
- **License:** **Statistics Canada Open Licence** (CC BY-equivalent).
- **Access:** `www150.statcan.gc.ca` tables (CSV / JSON / API), the
  StatCan Web Data Service (WDS) REST API.
- **Backend choice:** **local cache** as Parquet.
- **Verified:**
  - https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210035901
  - https://www.statcan.gc.ca/en/survey/agriculture/3401
- **Concrete Quebec sanity check (2024):** corn (grain) Quebec production
  3.6 Mt (+7.9% yoy), yield 162.1 bu/ac; soybean 1.4 Mt (+9.3% yoy), yield
  49.6 bu/ac. These are the kinds of numbers we should be able to
  back-test against.

### 7.6 ISQ + MAPAQ (Quebec)

- **Provider:** Institut de la statistique du Québec (ISQ); Ministère de
  l'Agriculture, des Pêcheries et de l'Alimentation du Québec (MAPAQ).
- **What it provides:** Quebec-specific agricultural statistics, regional
  agronomic guides, and current crop recommendations by Quebec region.
- **Use in AIgriculture:**
  - ISQ — additional historical depth and Quebec-specific aggregations
    beyond StatCan.
  - MAPAQ — **present-day expert baseline.** If our model says "grow X in
    region Y" and MAPAQ's published guide says X is unsuitable for Y, that
    is a red flag. This is the practitioner sanity check at the end of the
    Quebec MVP.
- **License:** Quebec government open data (verify per dataset).
- **Access:** ISQ data portal (`statistique.quebec.ca`); MAPAQ agronomic
  guides as PDFs.

### 7.7 Financière agricole du Québec (potential calibration source)

- **Provider:** La Financière agricole du Québec.
- **What it provides (potentially):** crop-insurance-based yield data —
  potentially the most accurate field-level Quebec yields, but access is
  not generally open. Worth investigating whether anonymized aggregate
  data are available for research.
- **Status:** **investigate during Phase 1 / Phase 3 implementation.**

### §7 Summary and recommendation

| Source | Granularity | Cadence | Coverage | Role |
|--------|-------------|---------|----------|------|
| FAOSTAT | national | annual | 1961 – present (global) | Global hindcast baseline. |
| GDHY (Iizumi & Sakai 2020) | 0.5° grid | annual | 1981 – 2016 (global, 4 crops) | Gridded yield ground truth. |
| USDA NASS QuickStats | county / state | annual | from 1850 (varies) | US hindcast (Phase 4). |
| Eurostat (apro\_cpsh\*) | NUTS-2 | annual | ~1970s – present | EU hindcast (Phase 4). |
| **StatCan Field Crop Reporting Series** | province | annual | mid-20C – present | **Quebec MVP annual ground truth.** |
| **StatCan Census of Agriculture** | CAR / Small Area Regions | 5-yearly | 1996, 2001, ..., 2021 | **Quebec MVP fine-scale ground truth.** |
| ISQ / MAPAQ | Quebec regional | varies | varies | Quebec context + practitioner baseline. |

**Recommendation for Quebec MVP:**
- **Primary annual ground truth:** StatCan Table `32-10-0359-01` (FCRS,
  provincial) for 1976–present, plus the Small Area Data Regions table
  `32-10-0002-01` where available.
- **Quinquennial cross-check:** Census of Agriculture 1996 / 2001 / 2006 /
  2011 / 2016 / 2021 for hindcast year-pair comparisons.
- **Global / external cross-check:** FAOSTAT national Canada-wide; GDHY
  gridded 0.5° for the 1981–2016 maize / soybean / wheat overlap.
- **Present-day expert baseline:** MAPAQ regional crop suitability guides.

---

---

## Cross-section summary — Quebec MVP "shopping list"

A condensed view of which datasets the Quebec MVP will actually pull at
runtime, with the planned storage backend per dataset:

| Layer | Dataset | Backend | Estimated Quebec-subset size |
|-------|---------|---------|------------------------------|
| Optical EO | HLS (L30 / S30) | stream | n/a — on-demand |
| SAR EO | Sentinel-1 GRD (MPC) | stream | n/a — on-demand |
| Reference NDVI | MOD13Q1 v6.1 | stream | n/a — on-demand |
| Historical climate | AgERA5 (CDS) | **local Zarr** | < 50 GB (1979 – present) |
| Historical climate (HR) | Daymet v4 | **local Zarr** | < 100 GB |
| Long-term anomalies | CanGRD | **local** (small) | < 1 GB |
| Station observations | ECCC AHCCD | **local Parquet** | < 1 GB |
| Future projections | CanDCS-M6 (26 GCM × 4 SSP) | **local Zarr** | < 100 GB |
| Future projections (xc) | NEX-GDDP-CMIP6 (subset) | stream / cache | n/a |
| Bioclimatic envelope | CHELSA-CMIP6 (1 km monthly) | **local** | < 10 GB |
| Soil (continuous) | SoilGrids 2.0 | **local COG/Zarr** | < 10 GB |
| Soil (polygon) | AAFC SLC v3.2 | **local GeoPackage** | < 1 GB |
| DEM | Copernicus DEM GLO-30 | **local** (Quebec tiles) | < 5 GB |
| Land cover | ESA WorldCover (2021) | stream | n/a |
| Crop map | AAFC ACI (annual) | stream + cache | < 5 GB per year |
| Yield ground truth | StatCan FCRS + Census | **local Parquet** | < 1 GB |
| External cross-check | FAOSTAT, GDHY | **local Parquet** | < 1 GB |

**Total estimated local storage budget for Quebec MVP: ~250 GB** — under
the user's ~300 GB local-vs-cloud threshold, which justifies keeping the
heavy climate / projection / soil layers as local Zarr stores.

---

## Verification checklist (per entry)

- [ ] Provider URL resolves and lists the current dataset version.
- [ ] License confirmed on the official source (not paraphrased).
- [ ] Resolution and coverage numbers match the source documentation.
- [ ] A BibTeX entry exists in `CITATIONS.bib` where the dataset will be
      cited from a `docs/research/*.md` document or written into the code.
- [ ] Access path tested in a notebook in `backend/notebooks/exploratory/`.
