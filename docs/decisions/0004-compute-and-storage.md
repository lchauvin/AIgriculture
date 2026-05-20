# ADR 0004 — Compute and storage architecture

- **Status:** accepted
- **Date:** 2026-05-19

## Context

AIgriculture must access several TB of climate, EO, and ancillary data
spanning historical records to multi-decadal future projections. The user
has stated preferences: open-source data sources only; willing to host
data locally if the per-dataset subset is < ~300 GB and cheaper than
recurrent cloud egress; willing to use the local RTX 4070 Ti (12 GB) for
ML inference and training.

For each dataset we have a choice between **stream from a STAC / Earth-
Engine / cloud catalog** and **download once into a local Zarr cache**.

## Decision

### Strategy: hybrid, per-dataset

The `aigriculture.data` package exposes a backend-agnostic interface;
each dataset registers as either `streaming` or `local` per the
classification in `docs/research/01-data-catalogue.md`.

### Per-dataset backend choices (Quebec MVP)

**Streamed** (no local copy):
- Sentinel-1 GRD via Microsoft Planetary Computer STAC.
- Sentinel-2 L2A via MPC STAC.
- Landsat 7/8/9 Collection 2 via MPC STAC.
- HLS (L30 / S30) via NASA Earthdata Cloud + MPC.
- MOD13Q1 v6.1 + VNP13A1 via NASA Earthdata Cloud.
- ESA WorldCover via AWS / MPC.
- AAFC ACI via Earth Engine (with annual Quebec rasters cached locally).
- Copernicus DEM GLO-30 via AWS Open Data (Quebec tiles cached locally).

**Local Zarr cache**:
- **AgERA5** subset for Quebec (1979 – present) — < 50 GB.
- **Daymet v4** subset for Quebec (1980 – present, 1 km) — < 100 GB.
- **CanDCS-M6** for Quebec (26 GCMs × 4 SSPs × daily Tmin/Tmax/Pr) —
  < 100 GB.
- **CHELSA-CMIP6** Quebec monthly + bioclim — < 10 GB.
- **SoilGrids 2.0** Quebec subset — < 10 GB.
- **CanGRD**, **AHCCD station Parquet**, **AAFC SLC** GeoPackage — < 2 GB
  combined.
- **StatCan FCRS / Census of Agriculture / FAOSTAT / GDHY** Parquet — < 1
  GB combined.

**Total local-storage budget for Quebec MVP: ~250 GB** — comfortably
under the user's 300 GB threshold.

### Storage formats

- **Gridded climate / soil / EO:** Zarr stores with `dask`-friendly
  chunking; CRS preserved through `rioxarray`.
- **Vector and tabular:** PostgreSQL + PostGIS for vector regions and crop
  metadata; Parquet (pyarrow) for purely tabular yields / FCRS.
- **Derived intermediate products:** local Zarr under `data/cache/` (all
  gitignored).

### Compute

- All numerical work runs **locally on the workstation**. The RTX 4070 Ti
  (12 GB) is used for:
  - **XGBoost** Tier 3 training/inference (`device="cuda"`).
  - Any future PyTorch model (process-model emulators; EO-feature deep
    models).
- Long-running background jobs (Tier 2 ensembles) are queued via **`arq`**
  (Redis-backed) and processed by a local worker.
- The frontend (Next.js) runs in dev locally; deployment target is
  deferred to Phase 4.

### Cloud usage

- **No paid cloud services** in the MVP — confirmed by ADR 0006-style
  open-source/free-tier constraint.
- **Free cloud access via STAC** (MPC, AWS Open Data, NASA Earthdata
  Cloud, Earth Engine) is used liberally for the streamed datasets.
- Earth Engine requires a free account; honour the rate / quota limits.

## Consequences

- Storage cost is local disk only; we accept that responsibility (the user
  has the disk).
- We pay full compute on the workstation. The dominant cost is Tier 2
  ensembles (~1–4 h per region); the MVP architecture mitigates this with
  pre-computed regional tiles + on-demand recompute via the job queue.
- We can iterate quickly because most data are local; cloud-streamed
  layers are only accessed when their value justifies the latency.

## Alternatives considered

- **Pure cloud-native (no local download).** Cheaper to set up but slower
  on repeat reads and pays cloud-egress fees if we ever leave the
  free-tier providers. Rejected.
- **All-local mirror.** Would balloon past 300 GB once Sentinel /
  Landsat / ERA5 are pulled in. Rejected.
- **Earth Engine as the single compute platform.** Free for research but
  ties us to Google's environment, limits library choice (no PCSE), and
  makes the project less self-hostable. Rejected.

## Verification

- Backend abstraction has unit tests against fixtures.
- For each dataset listed as `local`, a download script + checksum manifest
  exists under `scripts/`.
- A storage-budget check (`du -sh data/`) is part of CI smoke tests.

## References

- `docs/research/01-data-catalogue.md` — per-dataset stream/local rationale.
- User preference: `~/.claude/projects/-home-whiteshadow-code-AIgriculture/memory/feedback_local_storage_threshold.md`
