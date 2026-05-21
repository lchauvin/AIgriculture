"""Quebec CanDCS-M6 smoke test.

Fourth end-to-end exercise of the data layer — and the first that pulls
**future** climate projections:

1. Use ``aigriculture.data.candcs_m6.CanDCSM6Source`` to stream the
   PAVICS-hosted CanDCS-M6 daily output for one GCM × one SSP × one
   month over a Quebec sub-region.
2. Print summary stats (tasmax / tasmin / pr).
3. Plot the mid-century July Tmax map.
4. Stamp the provenance fingerprint.

Run end-to-end as a script:

    .venv/bin/python backend/notebooks/exploratory/quebec_candcs_m6_smoke_test.py

No credentials required; PAVICS OPeNDAP is open.
"""

# %% [markdown]
# # Quebec CanDCS-M6 smoke test
#
# A one-month CanESM5 SSP2-4.5 slice over southern Quebec to validate
# the OPeNDAP path end-to-end.

# %%
from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt

from aigriculture.data.candcs_m6 import CanDCSM6Source

# %% [markdown]
# ## Configuration

# %%
REPO_ROOT = Path(__file__).resolve().parents[3]

QUEBEC_BBOX = (-74.0, 45.0, -73.0, 46.0)
# Mid-century, peak growing season: a month where we expect Tmax well
# above 25 °C and intermittent precipitation.
TIME_RANGE = (date(2050, 7, 1), date(2050, 7, 31))
GCM = "CanESM5"
SSP = "ssp245"

print(f"bbox        : {QUEBEC_BBOX}")
print(f"time range  : {TIME_RANGE[0]} → {TIME_RANGE[1]}")
print(f"GCM × SSP   : {GCM} × {SSP}")

# %% [markdown]
# ## Load CanDCS-M6
#
# PAVICS OPeNDAP — lazy, no local cache. ``xarray.open_dataset`` retrieves
# only metadata, then ``.sel(...)`` pulls the windowed bytes for the bbox
# and time range.

# %%
source = CanDCSM6Source()
ds = source.load(
    bbox=QUEBEC_BBOX,
    time_range=TIME_RANGE,
    gcms=(GCM,),
    ssps=(SSP,),
    # All three variables: daily max / min temperature + precipitation.
)
print(ds)

# %% [markdown]
# ## Summary statistics
#
# Plausibility check for July 2050 over southern Quebec under SSP2-4.5
# from CanESM5:
#
# - **tasmax**: 20 – 40 °C is the plausible range; mean around 28 – 33 °C.
# - **tasmin**: 10 – 22 °C; mean around 15 – 20 °C.
# - **pr**: 0 – 50 mm/day per cell on any given day; monthly-mean around
#   1 – 4 mm/day (Quebec gets ~80–100 mm in July climatologically).

# %%
for var in ("tasmax", "tasmin", "pr"):
    da = ds[var].isel(gcm=0, ssp=0)
    units = da.attrs.get("units", "?")
    print(f"\n{var} [{units}]:")
    print(f"  min  = {float(da.min()):8.3f}")
    print(f"  mean = {float(da.mean()):8.3f}")
    print(f"  max  = {float(da.max()):8.3f}")

# %% [markdown]
# ## Map: monthly-mean tasmax

# %%
fig, ax = plt.subplots(figsize=(8, 6))
ds["tasmax"].isel(gcm=0, ssp=0).mean(dim="time").plot.pcolormesh(
    ax=ax,
    cmap="hot_r",
    cbar_kwargs={"label": "Tmax monthly mean (°C)"},
)
ax.set_title(f"Quebec — CanDCS-M6 / {GCM} / {SSP} — July {TIME_RANGE[0].year} Tmax")
ax.set_xlabel("Longitude (°E)")
ax.set_ylabel("Latitude (°N)")
out_png = Path(__file__).with_suffix(".png")
fig.savefig(out_png, dpi=120, bbox_inches="tight")
print(f"\nsaved: {out_png}")

# %% [markdown]
# ## Provenance

# %%
prov = source.provenance(
    bbox=QUEBEC_BBOX,
    time_range=TIME_RANGE,
    variables=("tasmax", "tasmin", "pr"),
)
print(f"source       : {prov.source_name} v{prov.source_version}")
print(f"backend      : {prov.backend}")
print(f"license      : {prov.license}")
print(f"citation key : {prov.citation_key}")
print(f"fingerprint  : {prov.fingerprint()}")
