"""Quebec Tier 1 envelope demo — historical vs mid-century future.

The first AIgriculture computation that **answers the project's actual
question**: which crops are climatically suitable for a Quebec region
today vs under 2050s SSP2-4.5 warming?

Pipeline:
1. Pull historical (AgERA5) and future (CanDCS-M6 / CanESM5 / ssp245)
   daily climate for a Quebec sub-region.
2. Compute climate indicators per crop (GDD with crop-specific base T,
   growing-season length, mean growing-season temperature, annual
   precip).
3. Score every Quebec staple (corn, soybean, spring wheat, canola)
   against the trapezoidal envelope from data/crops/quebec_staples.yaml.
4. Plot per-crop suitability maps for present vs future.

Run end-to-end:

    .venv/bin/python backend/notebooks/exploratory/quebec_tier1_envelope.py

Prerequisites:

- AgERA5 cache from the GDD smoke test (or another AgERA5 pull).
  ``data/cache/agera5/`` is reused.
- ``~/.cdsapirc`` configured (AgERA5).
- No EE credentials needed (CanDCS-M6 streams from PAVICS).
"""

# %% [markdown]
# # Quebec Tier 1 envelope — present vs 2050s
#
# The whole stack in one script: data layer → indicators → envelope
# scoring → maps.

# %%
from __future__ import annotations

from datetime import date
from pathlib import Path

import contextily as cx
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from aigriculture.data.agera5 import AgERA5Source
from aigriculture.data.candcs_m6 import CanDCSM6Source
from aigriculture.data.soilgrids import SoilGridsSource
from aigriculture.suitability import envelope, indicators, requirements

# %% [markdown]
# ## Configuration

# %%
REPO_ROOT = Path(__file__).resolve().parents[3]
AGERA5_CACHE = REPO_ROOT / "data" / "cache" / "agera5"

# A 1.5° × 1° window covering southern Quebec — large enough to show a
# climatic gradient north→south.
QUEBEC_BBOX = (-74.0, 45.0, -72.5, 46.0)

# Historical baseline period — use a 3-year sample for speed; in
# production a 30-year window is the climatological convention.
HISTORICAL_YEARS = (2017, 2018, 2019)

# Mid-century future window under SSP2-4.5 / CanESM5.
FUTURE_TIME_RANGE = (date(2049, 1, 1), date(2051, 12, 31))
FUTURE_GCM = "CanESM5"
FUTURE_SSP = "ssp245"

print(f"bbox            : {QUEBEC_BBOX}")
print(f"historical years: {HISTORICAL_YEARS}")
print(f"future window   : {FUTURE_TIME_RANGE[0]} → {FUTURE_TIME_RANGE[1]}")
print(f"future GCM × SSP: {FUTURE_GCM} × {FUTURE_SSP}")

# %% [markdown]
# ## Load the crop catalogue

# %%
catalogue = requirements.load_catalogue()
print(f"\nLoaded {len(catalogue.crops)} crops:")
for c in catalogue.crops:
    print(
        f"  {c.id:>14s}  {c.scientific_name:25s}  "
        f"GDD (base {c.gdd.base_temperature_c:.0f} °C): "
        f"{c.gdd.optimal_min:.0f}–{c.gdd.optimal_max:.0f}"
    )


# %% [markdown]
# ## Helper: per-crop indicators
#
# GDD is base-T-dependent, so each crop's indicators need to be
# recomputed with its own GDD base T. Everything else (Tmean, precip,
# growing-season days) is shared.

# %%
def indicators_for_crop(ds: xr.Dataset, crop) -> xr.Dataset:
    return indicators.compute_all(
        ds, gdd_base_temperature_c=crop.gdd.base_temperature_c
    )


# %% [markdown]
# ## Pull AgERA5 historical climate

# %%
agera5 = AgERA5Source(cache_dir=AGERA5_CACHE)
hist_pieces = []
for year in HISTORICAL_YEARS:
    print(f"  AgERA5 {year} (growing season)...")
    ds = agera5.load(
        bbox=QUEBEC_BBOX,
        # April-September: cover the Quebec growing season.
        # Using a partial year keeps the CDS quota low; for production
        # we'd ingest the full annual window.
        time_range=(date(year, 4, 1), date(year, 9, 30)),
        variables=("t2m_min", "t2m_max", "precip"),
    )
    # Rename AgERA5 fields to the suitability module's expected names.
    ds = ds.rename({"t2m_min": "tasmin", "t2m_max": "tasmax", "precip": "pr"})
    hist_pieces.append(ds)

hist_ds = xr.concat(hist_pieces, dim="time")
print(f"\nHistorical Dataset: time={hist_ds.sizes['time']} days, "
      f"lat={hist_ds.sizes['lat']}, lon={hist_ds.sizes['lon']}")

# %% [markdown]
# ## Pull CanDCS-M6 future climate
#
# Lazy OPeNDAP — only the bytes for the bbox + time window get
# transferred. We then slice down to the same April–September window
# the historical AgERA5 pull covers, so historical and future
# indicators integrate over equivalent calendar windows. (Otherwise
# the full-year future GDD looks artificially inflated compared with
# the Apr–Sep historical sum.)

# %%
print(f"\nCanDCS-M6 {FUTURE_GCM} {FUTURE_SSP} {FUTURE_TIME_RANGE[0]}–{FUTURE_TIME_RANGE[1]} ...")
candcs = CanDCSM6Source()
future_ds = candcs.load(
    bbox=QUEBEC_BBOX,
    time_range=FUTURE_TIME_RANGE,
    gcms=(FUTURE_GCM,),
    ssps=(FUTURE_SSP,),
).isel(gcm=0, ssp=0, drop=True)
# Slice to Apr–Sep to match the AgERA5 historical window.
future_ds = future_ds.sel(time=future_ds["time.month"].isin([4, 5, 6, 7, 8, 9]))
print(f"Future Dataset (Apr–Sep slice): time={future_ds.sizes['time']} days, "
      f"lat={future_ds.sizes['lat']}, lon={future_ds.sizes['lon']}")


# %% [markdown]
# ## Load SoilGrids 2.0 topsoil pH and align to the climate grids
#
# pH(H₂O) at 0–5 cm is the relevant horizon for crop establishment.
# SoilGrids streams at ~250 m via ISRIC's WebDAV VRT (CRS converted to
# EPSG:4326 by the loader); we then interpolate linearly down to each
# climate grid (AgERA5 0.1° historical, CanDCS-M6 1/12° future) using
# xarray's ``interp``. pH is a smooth continuous field at agricultural
# scales, so linear interpolation is well-justified.

# %%
print("\nSoilGrids 2.0 topsoil (0–5cm) pH...")
soil = SoilGridsSource()
soil_ds = soil.load(
    bbox=QUEBEC_BBOX,
    variables=("phh2o",),
    depths=("0-5cm",),
)
ph_native = soil_ds["phh2o"].squeeze("depth", drop=True)
# rioxarray uses x/y; rename to lon/lat for alignment with climate data
# and ensure latitude is south→north ascending.
ph_native = ph_native.rename({"x": "lon", "y": "lat"})
if float(ph_native["lat"][0]) > float(ph_native["lat"][-1]):
    ph_native = ph_native.sortby("lat")
print(
    f"SoilGrids pH grid: {ph_native.sizes['lat']} × {ph_native.sizes['lon']} cells, "
    f"range {float(ph_native.min()):.2f} – {float(ph_native.max()):.2f}"
)


def align_ph_to(climate_dataset: xr.Dataset) -> xr.DataArray:
    """Linearly interpolate native-grid SoilGrids pH onto a climate
    dataset's lat/lon grid."""
    return ph_native.interp(
        lat=climate_dataset["lat"], lon=climate_dataset["lon"],
        kwargs={"fill_value": "extrapolate"},
    )


hist_ph = align_ph_to(hist_ds)
future_ph = align_ph_to(future_ds)
print(
    f"After interp to climate grids: "
    f"historical (AgERA5) {hist_ph.shape}, "
    f"future (CanDCS-M6) {future_ph.shape}"
)


# %% [markdown]
# ## Score every crop, past + future

# %%
def score_all_crops(
    ds: xr.Dataset,
    label: str,
    *,
    soil_ph: xr.DataArray,
) -> dict[str, envelope.CropSuitability]:
    print(f"\n--- scoring {label} ---")
    print(
        f"  {'crop':>14s}  {'envel':>6}  {'pref':>6}  {'combo':>6}  "
        f"{'class':>5}  {'limiting':>14s}  per-factor envelope (T/GDD/Pr/GS/pH)"
    )
    results = {}
    for crop in catalogue.crops:
        ind = indicators_for_crop(ds, crop)
        sui = envelope.score_crop(ind, crop, soil_ph=soil_ph)
        results[crop.id] = sui

        env = float(sui.envelope_score.mean().values)
        pref = float(sui.preference_score.mean().values)
        combo = float(sui.score.mean().values)
        cls = envelope.classify_gaez(xr.DataArray(env)).item()

        flat = sui.limiting_factor.values.flatten()
        flat = flat[flat != ""]
        if len(flat):
            unique, counts = np.unique(flat, return_counts=True)
            modal_limit = unique[counts.argmax()]
        else:
            modal_limit = "—"

        per = {k: float(v.mean().values) for k, v in sui.per_factor.items()}
        per_str = (
            f"T={per.get('temperature', 0):.2f} "
            f"GDD={per.get('gdd', 0):.2f} "
            f"Pr={per.get('precipitation', 0):.2f} "
            f"GS={per.get('growing_season', 0):.2f} "
            f"pH={per.get('soil_ph', 0):.2f}"
        )
        print(
            f"  {crop.id:>14s}  {env:>6.3f}  {pref:>6.3f}  {combo:>6.3f}  "
            f"{cls:>5}  {modal_limit:>14s}  {per_str}"
        )
    return results

hist_scores = score_all_crops(hist_ds, "historical (AgERA5)", soil_ph=hist_ph)
future_scores = score_all_crops(
    future_ds, f"future ({FUTURE_GCM} {FUTURE_SSP})", soil_ph=future_ph,
)


# %% [markdown]
# ## Plot a 4-crop × 2-period suitability grid, on Esri World Imagery
#
# `contextily` fetches Web-Mercator basemap tiles and reprojects them to
# our axes' CRS (EPSG:4326). Tiles are cached locally after first use, so
# subsequent runs are fast. Suitability data overlays at α=0.55 so the
# underlying landscape (rivers, urban areas, agricultural lots) shows
# through.
#
# Axis limits are computed from the **actual cell-edge extent** of each
# row's data (AgERA5 is 0.1°, CanDCS-M6 is 1/12°), so the basemap
# exactly matches the heatmap rather than extending past it.


def cell_edge_extent(da: xr.DataArray) -> tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) of the cell *edges* given coords
    at cell centers."""
    lats = da["lat"].values
    lons = da["lon"].values
    dlat = float(abs(lats[1] - lats[0])) if len(lats) > 1 else 0.1
    dlon = float(abs(lons[1] - lons[0])) if len(lons) > 1 else 0.1
    return (
        float(lons.min()) - dlon / 2,
        float(lats.min()) - dlat / 2,
        float(lons.max()) + dlon / 2,
        float(lats.max()) + dlat / 2,
    )


# %%
fig, axes = plt.subplots(
    nrows=2, ncols=len(catalogue.crops),
    figsize=(5 * len(catalogue.crops), 4.5 * 2),
    # sharex/sharey OFF so each row can use its own data-derived extent
    # (AgERA5 0.1° row and CanDCS-M6 1/12° row have different cell
    # alignments; forcing a shared extent reintroduces the heatmap-vs-
    # basemap gap the user spotted in the previous render).
)

# One extent per row, computed from the row's first crop suitability.
hist_extent = cell_edge_extent(next(iter(hist_scores.values())).score)
future_extent = cell_edge_extent(next(iter(future_scores.values())).score)
row_extents = (hist_extent, future_extent)

for col, crop in enumerate(catalogue.crops):
    for row, (period, results) in enumerate(
        [("Historical", hist_scores), (f"{FUTURE_GCM} {FUTURE_SSP} 2050", future_scores)]
    ):
        ax = axes[row, col]
        sui = results[crop.id]
        im = sui.score.plot.pcolormesh(
            ax=ax, vmin=0, vmax=1, cmap="RdYlGn",
            alpha=0.55,
            add_colorbar=False,
        )
        ext = row_extents[row]
        ax.set_xlim(ext[0], ext[2])
        ax.set_ylim(ext[1], ext[3])
        cx.add_basemap(
            ax,
            crs="EPSG:4326",
            source=cx.providers.Esri.WorldImagery,
            zoom=9,
        )
        ax.set_title(f"{crop.common_name_en}\n{period}", fontsize=11)
        ax.set_xlabel("")
        ax.set_ylabel("")

# Single shared colorbar at the right.
cbar = fig.colorbar(
    im, ax=axes.ravel().tolist(),
    orientation="vertical",
    shrink=0.6,
    pad=0.02,
    label="Suitability score (0 = N / unsuitable; 1 = S1 / very suitable)",
)

fig.suptitle(
    f"Quebec Tier 1 envelope — bbox {QUEBEC_BBOX} — basemap © Esri WorldImagery",
    fontsize=12,
)
out_png = Path(__file__).with_suffix(".png")
fig.savefig(out_png, dpi=120, bbox_inches="tight")
print(f"\nsaved: {out_png}")
