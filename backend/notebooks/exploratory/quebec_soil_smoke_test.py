"""Quebec soil-properties smoke test.

Second end-to-end exercise of the AIgriculture data layer:

1. Use ``aigriculture.data.soilgrids.SoilGridsSource`` to fetch the
   Tier-2 essential soil properties for a small Quebec bounding box.
2. Print summary statistics per (property, depth) — these are good
   sanity checks against published Champlain-Sea-clay regional values.
3. Plot the topsoil (0–5 cm) clay map and write to ``.png``.
4. Stamp the provenance fingerprint.

Run end-to-end as a script:

    .venv/bin/python backend/notebooks/exploratory/quebec_soil_smoke_test.py

Hits the live ISRIC WebDAV via GDAL's ``/vsicurl/``. No credentials
required.
"""

# %% [markdown]
# # Quebec soil-properties smoke test
#
# Streams a small Quebec subset of SoilGrids 2.0, reprojects from
# Homolosine to EPSG:4326, and prints per-depth summaries.

# %%
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from aigriculture.data.soilgrids import (
    ALL_DEPTHS,
    DEFAULT_PROPERTIES,
    SoilGridsSource,
)

# %% [markdown]
# ## Configuration

# %%
REPO_ROOT = Path(__file__).resolve().parents[3]

# A 1° × 1° window over the Montréal–Sherbrooke area. Larger than the
# AgERA5 GDD demo so we sample varied soils (Champlain clays in the
# St-Lawrence valley vs sandier glacial outwash to the south).
QUEBEC_BBOX = (-74.0, 45.0, -73.0, 46.0)

print(f"bbox    : {QUEBEC_BBOX}")
print(f"props   : {DEFAULT_PROPERTIES}")
print(f"depths  : {ALL_DEPTHS}")

# %% [markdown]
# ## Load SoilGrids
#
# ``SoilGridsSource`` streams the ISRIC global VRTs via ``/vsicurl/``. No
# local cache — each request hits the live service.

# %%
source = SoilGridsSource()
ds = source.load(bbox=QUEBEC_BBOX)
print(ds)

# %% [markdown]
# ## Per-(property, depth) summaries
#
# Plausibility against published Quebec values:
#
# - **clay** (St-Lawrence valley topsoil): 25–50 % is normal — Champlain
#   Sea legacy.
# - **sand**: complementary; 5–40 % typical.
# - **phh2o** (topsoil): 5.5–7.0 across most of southern Quebec.
# - **soc** (topsoil): 15–60 g/kg in well-drained agricultural soils.
# - **bdod**: 1.1–1.6 g/cm³ for mineral topsoils.

# %%
for prop in DEFAULT_PROPERTIES:
    print(f"\n{prop} ({ds[prop].attrs.get('units')}):")
    for depth in ALL_DEPTHS:
        da_d = ds[prop].sel(depth=depth)
        # Some pixels at the bbox edges may be NaN; ignore them in summaries.
        valid = da_d.where(~da_d.isnull())
        print(
            f"  {depth:>10s}  "
            f"min={float(valid.min()):6.2f}  "
            f"mean={float(valid.mean()):6.2f}  "
            f"max={float(valid.max()):6.2f}"
        )

# %% [markdown]
# ## Plot topsoil clay (0–5 cm)

# %%
fig, ax = plt.subplots(figsize=(8, 6))
ds["clay"].sel(depth="0-5cm").plot.pcolormesh(
    ax=ax, cmap="YlOrBr", cbar_kwargs={"label": "Clay (%)"},
)
ax.set_title("Quebec — SoilGrids 2.0 topsoil clay (0–5 cm)")
ax.set_xlabel("Longitude (°E)")
ax.set_ylabel("Latitude (°N)")
out_png = Path(__file__).with_suffix(".png")
fig.savefig(out_png, dpi=120, bbox_inches="tight")
print(f"saved: {out_png}")

# %% [markdown]
# ## Provenance

# %%
prov = source.provenance(bbox=QUEBEC_BBOX, time_range=None)
print(f"source       : {prov.source_name} v{prov.source_version}")
print(f"backend      : {prov.backend}")
print(f"license      : {prov.license}")
print(f"citation key : {prov.citation_key}")
print(f"fingerprint  : {prov.fingerprint()}")
