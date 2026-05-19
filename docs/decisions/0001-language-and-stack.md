# ADR 0001 — Language and stack

- **Status:** accepted
- **Date:** 2026-05-19

## Context

AIgriculture is a geospatial, climate-aware modeling tool with a public web
interface. The dominant technical demands are:

1. **Geospatial / climate-science data manipulation** — read NetCDF / GeoTIFF /
   Zarr, manipulate multidimensional arrays, run process-based crop models.
2. **Machine learning** — gradient-boosted trees (Tier 3 bias correction) and
   optional deep models (process-model emulators, EO-based classifiers) on a
   single workstation GPU.
3. **A modern interactive map UI** — polygon drawing, vector / raster tile
   rendering, uncertainty visualizations.
4. **Background jobs** — projection computations can take seconds to minutes
   per region; the UI must remain responsive.
5. **Single-author maintainability** — the chosen languages and frameworks
   must have minimal cross-cutting friction.

## Decision

- **Backend in Python 3.11+** (Python is the lingua franca of geospatial /
  climate / ML communities; every dataset we care about has a first-party or
  community Python loader).
- **Frontend in TypeScript on Next.js 14 (App Router).** Map rendering via
  MapLibre GL JS through `react-map-gl`. Charts via Recharts (with Visx as a
  fallback for bespoke fan charts).
- **Build/deps:** `uv` for Python (fast, modern); `npm` (or `pnpm`) for the
  frontend. `pyproject.toml` declares the package; optional-dependency groups
  separate heavy scientific stacks from the bare install.
- **API:** FastAPI + Pydantic v2, served by `uvicorn` in dev, hardened for
  production later.
- **Persistence:** PostGIS for vector data and crop metadata; Zarr (local
  disk under ~300 GB per dataset, otherwise STAC-streamed) for gridded
  climate / EO data; Parquet for tabular yields.
- **Background work:** `arq` (small, Redis-based) for now; revisit if we
  need richer scheduling.

## Consequences

- **Pros:** maximal ecosystem coverage (every climate / EO / crop-model
  library is Python-first); excellent ML tooling; widely-known frontend
  framework; the data layer scales from notebook to production without
  changing the abstraction.
- **Cons:** two languages to maintain; Python type-safety is weaker than
  TypeScript's, partially mitigated by `mypy --strict`; the frontend toolchain
  is heavier than e.g. plain Leaflet + vanilla JS would be.

## Alternatives considered

- **Streamlit / Dash full-Python stack.** Quicker to a demo, but limited
  control over map interactions and bundling; awkward for production-quality
  UX. Rejected for the multi-audience polish target.
- **R / R Shiny.** Strong climate-science ecosystem (raster, terra, sf), but
  weaker on web app deployment and ML compared with Python. Rejected.
- **Julia.** Excellent numerical performance, growing climate stack, but
  smaller ecosystem and steeper hiring story (even for "future me"). Rejected.
- **Plain HTML + Leaflet for frontend.** Considered as a minimal alternative;
  rejected because the planned uncertainty / fan-chart visualizations are
  awkward without a component framework, and the user explicitly wants a
  professional-grade UI.

## References

- [PCSE / WOFOST documentation](https://pcse.readthedocs.io/)
- [xarray documentation](https://docs.xarray.dev/)
- [Microsoft Planetary Computer STAC API](https://planetarycomputer.microsoft.com/docs/concepts/stac/)
- [MapLibre GL JS](https://maplibre.org/)
