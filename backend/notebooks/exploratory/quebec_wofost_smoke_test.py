"""Quebec WOFOST smoke test — single-point grain corn for 2018.

The first AIgriculture Tier 2 run. Pulls AgERA5 daily weather for a
representative Montérégie point (Saint-Hyacinthe area, deep in Quebec
corn country) for the full April – October corn-growing window of 2018,
runs WOFOST 7.2 in potential-production mode against PCSE's
Grain_maize_201 cultivar (~2500 CHU, mid-MG Quebec corn), and reports
yield + phenology.

Comparison reference (StatCan Field Crop Reporting Series, Table
32-10-0359-01):
    Quebec corn for grain, 2018: ~9.4 t/ha province-wide.

Expected WOFOST PP yield for southern Quebec: 11 – 14 t/ha. The "yield
gap" between WOFOST PP and StatCan-observed is normal — WOFOST PP
assumes unlimited water and nutrients, no weeds, no pests. Tier 3
(ML bias correction) closes the gap.

Run end-to-end:

    .venv/bin/python backend/notebooks/exploratory/quebec_wofost_smoke_test.py

Prerequisites:
- ``~/.cdsapirc`` configured (AgERA5).
- Apr-Sep cache from the GDD smoke test is reused; October 2018 will
  be downloaded on first run (~90 seconds).
"""

# %% [markdown]
# # Quebec WOFOST smoke test
#
# Single point in Montérégie × Grain_maize_201 × 2018.

# %%
from __future__ import annotations

import datetime as dt
from pathlib import Path

import xarray as xr

from aigriculture.crop_models import wofost_runner
from aigriculture.data.agera5 import AgERA5Source

# %% [markdown]
# ## Configuration

# %%
REPO_ROOT = Path(__file__).resolve().parents[3]
AGERA5_CACHE = REPO_ROOT / "data" / "cache" / "agera5"

# Same bbox as the Tier 1 envelope notebook — reuses the existing cache.
QUEBEC_BBOX = (-74.0, 45.0, -72.5, 46.0)

# Representative Montérégie corn-country point: ~Saint-Hyacinthe.
POINT_LAT = 45.5
POINT_LON = -73.5
ELEVATION_M = 30.0  # St-Lawrence valley low elevation

YEAR = 2018
CAMPAIGN_START = dt.date(YEAR, 4, 1)
EMERGENCE = dt.date(YEAR, 5, 15)
HARVEST = dt.date(YEAR, 10, 31)

print(f"bbox          : {QUEBEC_BBOX}")
print(f"point (lat,lon): ({POINT_LAT}, {POINT_LON})")
print(f"year          : {YEAR}")
print(f"emergence     : {EMERGENCE}")
print(f"harvest       : {HARVEST}")

# %% [markdown]
# ## Pull AgERA5 daily weather for Apr–Oct 2018
#
# The existing GDD-smoke-test cache covers Apr–Sep; October needs a
# fresh download (~90 s). We pull Tmin, Tmax, and precip for use as
# WOFOST inputs, plus solar radiation (rsds equivalent). The runner
# will Magnus-approximate VAP and FAO-default WIND for this MVP.

# %%
print("\nPulling AgERA5 (will reuse cache where available)...")
agera5 = AgERA5Source(cache_dir=AGERA5_CACHE)
ds = agera5.load(
    bbox=QUEBEC_BBOX,
    time_range=(CAMPAIGN_START, HARVEST),
    variables=("t2m_min", "t2m_max", "precip", "solar_rad"),
)
# Rename to the canonical CMIP6 names the WOFOST runner expects.
ds = ds.rename({"t2m_min": "tasmin", "t2m_max": "tasmax", "precip": "pr", "solar_rad": "rsds"})
# AgERA5 ships temperatures in Kelvin, precip in mm/day, radiation in J/m²/d.
# (The WOFOST weather translator handles unit conversion via the `units`
# attribute.)
for v in ("tasmin", "tasmax"):
    ds[v].attrs.setdefault("units", "K")
ds["pr"].attrs.setdefault("units", "mm/day")
ds["rsds"].attrs.setdefault("units", "J m-2 d-1")

print(f"loaded: time={ds.sizes['time']} days, lat={ds.sizes['lat']}, lon={ds.sizes['lon']}")

# %% [markdown]
# ## Select the Montérégie point

# %%
point_ds = ds.sel(lat=POINT_LAT, lon=POINT_LON, method="nearest")
print(f"\nSelected cell:  lat={float(point_ds.lat):.2f}, lon={float(point_ds.lon):.2f}")
print(f"  Tmin range   : {float(point_ds['tasmin'].min())-273.15:.1f} → "
      f"{float(point_ds['tasmin'].max())-273.15:.1f} °C")
print(f"  Tmax range   : {float(point_ds['tasmax'].min())-273.15:.1f} → "
      f"{float(point_ds['tasmax'].max())-273.15:.1f} °C")
print(f"  precip total : {float(point_ds['pr'].sum()):.0f} mm over the window")
print(f"  rsds mean    : {float(point_ds['rsds'].mean())/1e6:.1f} MJ/m²/day")

# %% [markdown]
# ## Run WOFOST 7.2 PP

# %%
print("\nRunning WOFOST 7.2 PP, Grain_maize_201...")
result = wofost_runner.run_wofost_pp(
    weather_ds=point_ds,
    crop_name="maize",
    variety_name="Grain_maize_201",
    campaign_start=CAMPAIGN_START,
    emergence=EMERGENCE,
    harvest=HARVEST,
    latitude=POINT_LAT,
    longitude=POINT_LON,
    elevation=ELEVATION_M,
)

# %% [markdown]
# ## Results

# %%
print("\n=== WOFOST 7.2 PP, Quebec Montérégie, 2018, Grain_maize_201 ===")
print(f"  yield (t/ha @14% moisture)  : {result.yield_t_ha:7.2f}")
print(f"  TWSO (kg/ha dry matter)     : {result.twso_kg_ha_dm:7.0f}")
print(f"  TAGP (above-ground biomass) : {result.tagp_kg_ha:7.0f}  kg/ha")
print(f"  LAI max                     : {result.lai_max:7.2f}")
print(f"  emergence (DOE)             : {result.doe}")
print(f"  anthesis  (DOA)             : {result.doa}")
print(f"  maturity  (DOM)             : {result.dom}")
if result.weather_approximations:
    print()
    print("Weather field approximations:")
    for n in result.weather_approximations:
        print(f"  - {n}")

# %% [markdown]
# ## Yield-gap check
#
# WOFOST PP gives the *potential* yield under unlimited water, no
# nutrient stress, no pest/weed competition. Real Quebec corn yields
# capture the yield gap from those constraints.

# %%
STATCAN_QUEBEC_CORN_2018_T_HA = 9.4  # FCRS Table 32-10-0359-01 ballpark
gap_pct = (result.yield_t_ha - STATCAN_QUEBEC_CORN_2018_T_HA) / STATCAN_QUEBEC_CORN_2018_T_HA * 100
print(f"\nStatCan Quebec corn 2018 (FCRS, t/ha @14% moisture, provincial): {STATCAN_QUEBEC_CORN_2018_T_HA:.1f}")
print(f"WOFOST PP yield gap                                              : {gap_pct:+.1f}%")
print(
    "\nA WOFOST-PP-to-observed gap of +20% to +50% is typical for "
    "well-managed temperate-zone corn (Lobell & Cassman literature)."
)
