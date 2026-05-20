"""Quebec AAFC ACI smoke test.

Third end-to-end exercise of the data layer:

1. Use ``aigriculture.data.aafc_aci.AAFCACISource`` to fetch one year of
   AAFC Annual Crop Inventory via Earth Engine for a small Quebec bbox.
2. Print the histogram of land-cover class codes (which classes are
   present + how many pixels of each).
3. Map the result; cache the GeoTIFF for re-runs.
4. Stamp the provenance fingerprint.

Run end-to-end as a script:

    .venv/bin/python backend/notebooks/exploratory/quebec_aci_smoke_test.py

Prerequisites:

- A Google Cloud project ID and Earth Engine activation. The script reads
  the project ID from the ``AIGRICULTURE_EE_PROJECT`` env var. You can
  either ``export AIGRICULTURE_EE_PROJECT=your-project-id`` in the shell
  or drop ``AIGRICULTURE_EE_PROJECT=your-project-id`` into a ``.env`` file
  at the project root — ``python-dotenv`` is loaded at import time so
  either works.
- ``earthengine authenticate`` run once interactively to write
  ``~/.config/earthengine/credentials``.
"""

# %% [markdown]
# # Quebec AAFC Annual Crop Inventory smoke test
#
# Streams one year of ACI for the Quebec sub-region and writes a
# class-code histogram + a map.

# %%
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv

from aigriculture.data.aafc_aci import AAFCACISource

# Load a project-root `.env` if present. Idempotent; harmless when absent.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# %% [markdown]
# ## Configuration

# %%
REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / "data" / "cache" / "aafc_aci"

# Same southern-Quebec sub-region as the AgERA5 and SoilGrids smoke tests.
QUEBEC_BBOX = (-74.0, 45.0, -73.0, 46.0)
TIME_RANGE = (date(2020, 1, 1), date(2020, 12, 31))  # one year

EE_PROJECT = os.environ.get("AIGRICULTURE_EE_PROJECT")
if not EE_PROJECT:
    raise SystemExit(
        "AIGRICULTURE_EE_PROJECT env var not set. "
        "Set it to your Google Cloud project ID with Earth Engine enabled, "
        "e.g. `export AIGRICULTURE_EE_PROJECT=my-ee-project`."
    )

print(f"cache dir : {CACHE_DIR}")
print(f"bbox      : {QUEBEC_BBOX}")
print(f"year      : {TIME_RANGE[0].year}")
print(f"EE project: {EE_PROJECT}")

# %% [markdown]
# ## Load ACI for 2020
#
# First call downloads a ~MB-sized GeoTIFF via Earth Engine's
# ``getDownloadURL``. Subsequent calls reuse the cached file.

# %%
source = AAFCACISource(cache_dir=CACHE_DIR, ee_project=EE_PROJECT)
ds = source.load(bbox=QUEBEC_BBOX, time_range=TIME_RANGE)
print(ds)

# %% [markdown]
# ## Class-code histogram
#
# ACI codes (subset relevant to Quebec, full legend on the EE catalog):
# - 20  Water
# - 30  Exposed Land / Barren
# - 34  Urban
# - 50  Shrubland
# - 110 Grassland
# - 122 Pasture
# - 130 Too Wet to Be Seeded
# - 140 Fallow / Idle
# - 145 Forage
# - 146 Mixed Forage / Hay
# - 153 Corn
# - 155 Soybean
# - 158 Wheat / Spring Wheat
# - 160 Barley
# - 162 Canola
# - 230 Wetland
# - 200/210/220 Forest types
# - 50/51 etc.

# %%
arr = ds["landcover"].isel(time=0).values.astype("int64")
arr = arr[arr != 0]  # mask out 0 / nodata
codes, counts = np.unique(arr, return_counts=True)
total = counts.sum()
print(f"\nUnique classes: {len(codes)}, total valid pixels: {total:,}")
print(f"\n{'code':>5}  {'count':>10}  {'pct':>6}")
for c, n in sorted(zip(codes, counts), key=lambda kv: -kv[1])[:20]:
    print(f"  {int(c):>3}  {int(n):>10,}  {100 * n / total:>5.2f}%")

# %% [markdown]
# ## Plot the land-cover map

# %%
fig, ax = plt.subplots(figsize=(8, 6))
ds["landcover"].isel(time=0).plot.pcolormesh(
    ax=ax, cmap="tab20", cbar_kwargs={"label": "ACI class code"},
)
ax.set_title(f"Quebec — AAFC ACI {TIME_RANGE[0].year}")
ax.set_xlabel("Longitude (°E)")
ax.set_ylabel("Latitude (°N)")
out_png = Path(__file__).with_suffix(".png")
fig.savefig(out_png, dpi=120, bbox_inches="tight")
print(f"saved: {out_png}")

# %% [markdown]
# ## Provenance

# %%
prov = source.provenance(bbox=QUEBEC_BBOX, time_range=TIME_RANGE)
print(f"source       : {prov.source_name} v{prov.source_version}")
print(f"backend      : {prov.backend}")
print(f"license      : {prov.license}")
print(f"citation key : {prov.citation_key}")
print(f"fingerprint  : {prov.fingerprint()}")
