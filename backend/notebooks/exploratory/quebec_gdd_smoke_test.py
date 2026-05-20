"""Quebec growing-degree-days smoke test.

First end-to-end exercise of the AIgriculture data layer:

1. Use `aigriculture.data.agera5.AgERA5Source` to fetch one month of
   AgERA5 daily Tmin / Tmax / Tmean for a small Quebec bounding box.
2. Compute growing-degree days (GDD, base 10 °C) using `xclim`.
3. Plot the resulting map and write it to `.png` next to this script.
4. Print the provenance fingerprint that downstream computations can
   stamp against.

Run interactively (cell-by-cell in VS Code / JupyterLab via jupytext) or
end-to-end as a script:

    .venv/bin/python backend/notebooks/exploratory/quebec_gdd_smoke_test.py

Requires:
- A working ``~/.cdsapirc`` (see the project README / CDS setup notes).
- The CDS dataset ``sis-agrometeorological-indicators`` accepted on your
  CDS account (one-time terms-of-use click on the dataset page).
"""

# %% [markdown]
# # Quebec GDD smoke test
#
# Pulls one month of AgERA5 for a small Quebec polygon and computes
# growing-degree days. Cache lives at ``data/cache/agera5/`` under the
# project root.

# %%
from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import xarray as xr
import xclim.indices as xci

from aigriculture.data.agera5 import AgERA5Source

# %% [markdown]
# ## Configuration
#
# A tiny Quebec sub-region (around Montréal–Drummondville) for a quick
# pull. Pick a larger bbox once the live CDS path is validated.

# %%
REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / "data" / "cache" / "agera5"

QUEBEC_BBOX = (-74.0, 45.0, -71.5, 46.5)  # (minx, miny, maxx, maxy) in EPSG:4326
TIME_RANGE = (date(2020, 5, 1), date(2020, 5, 31))  # May 2020, growing season start

print(f"cache dir: {CACHE_DIR}")
print(f"bbox    : {QUEBEC_BBOX}")
print(f"period  : {TIME_RANGE[0]} → {TIME_RANGE[1]}")

# %% [markdown]
# ## Load AgERA5
#
# Defaults to the real CDS API client; the first call writes a NetCDF per
# (variable, month) into the cache directory. Subsequent calls are
# idempotent.

# %%
source = AgERA5Source(cache_dir=CACHE_DIR)
ds = source.load(
    bbox=QUEBEC_BBOX,
    time_range=TIME_RANGE,
    variables=("t2m_min", "t2m_max", "t2m_mean"),
)
print(ds)

# %% [markdown]
# ## Compute growing-degree days
#
# `xclim` expects temperatures in Kelvin (AgERA5 default) and emits the
# result in °C·days. Base 10 °C is the canonical maize / soybean GDD base.

# %%
gdd = xci.growing_degree_days(
    tas=ds["t2m_mean"],
    thresh="10.0 degC",
)
gdd_map = gdd.sum(dim="time")
print(f"GDD May 2020 (base 10 °C):")
print(f"  min: {float(gdd_map.min()):.1f} °C·d")
print(f"  max: {float(gdd_map.max()):.1f} °C·d")
print(f"  mean: {float(gdd_map.mean()):.1f} °C·d")

# %% [markdown]
# ## Plot

# %%
fig, ax = plt.subplots(figsize=(8, 6))
gdd_map.plot.pcolormesh(ax=ax, cmap="YlOrRd")
ax.set_title("Quebec — GDD (base 10 °C), May 2020 (AgERA5)")
ax.set_xlabel("Longitude (°E)")
ax.set_ylabel("Latitude (°N)")
out_png = Path(__file__).with_suffix(".png")
fig.savefig(out_png, dpi=120, bbox_inches="tight")
print(f"saved: {out_png}")

# %% [markdown]
# ## Provenance fingerprint
#
# Stamping every derived computation with the input provenance fingerprint
# is how AIgriculture stays reproducible. The fingerprint is stable across
# wall-clock time and machines: same (source, version, bbox, time_range,
# variables) → same hex string.

# %%
prov = source.provenance(
    bbox=QUEBEC_BBOX,
    time_range=TIME_RANGE,
    variables=("t2m_min", "t2m_max", "t2m_mean"),
)
print(f"source       : {prov.source_name} v{prov.source_version}")
print(f"backend      : {prov.backend}")
print(f"license      : {prov.license}")
print(f"citation key : {prov.citation_key}")
print(f"fingerprint  : {prov.fingerprint()}")
