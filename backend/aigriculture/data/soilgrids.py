"""SoilGrids 2.0 — ISRIC global digital soil mapping data source.

SoilGrids 2.0 is the primary continuous-grid soil dataset for AIgriculture
per ADR 0004. It supplies the seven Tier-2-essential properties (clay /
sand / silt / pH / soil organic carbon / bulk density / coarse fragments)
at six standard GlobalSoilMap depth intervals (0–5, 5–15, 15–30, 30–60,
60–100, 100–200 cm) at 250 m global resolution.

Citation: Poggio, L. et al. (2021). SoilGrids 2.0: producing soil
information for the globe with quantified spatial uncertainty. *SOIL*,
7, 217–240.

License: CC BY 4.0.

Access pattern
--------------
ISRIC hosts SoilGrids 2.0 as a set of global Cloud-Optimized GeoTIFFs
referenced by per-(property, depth, statistic) VRT mosaics on WebDAV:

    https://files.isric.org/soilgrids/latest/data/<prop>/<prop>_<depth>_<stat>.vrt

We access them via GDAL's ``/vsicurl/`` driver (no authentication
required, no rate limit publicly documented but the FAQ requests
"polite" access — no concurrent floods).

The native CRS is **Goode Homolosine on WGS 84** (``ESRI:54052``). We
reproject every load to ``EPSG:4326`` on the client so SoilGrids lines
up with AgERA5 and the rest of the pipeline.

Performance note
----------------
The native 250 m VRTs are large (multi-MB XML referencing thousands of
tiles); a full 7-property × 6-depth fetch for a 1° × 1° bbox can take
10–20 minutes on the first call. ISRIC also publishes a 1 km aggregated
single-COG tier at ``data_aggregated/1000m/<prop>/<prop>_<depth>_mean_1000.tif``
that is plenty for our 10 km climate-driver pipeline. Switching the
default to that tier is a planned optimization tracked separately.
"""

from __future__ import annotations

from typing import Sequence

import xarray as xr

from .base import (
    BBox,
    DataSource,
    TimeRange,
    validate_bbox,
    validate_time_range,
)

SOILGRIDS_BASE_URL = "https://files.isric.org/soilgrids/latest/data"
NATIVE_CRS = "ESRI:54052"  # Goode Homolosine on WGS 84
OUTPUT_CRS = "EPSG:4326"
SOURCE_URL = "https://www.isric.org/explore/soilgrids"
LICENSE = "CC-BY-4.0"
CITATION_KEY = "Poggio2021SoilGrids"

# Tier-2 essentials chosen per ADR 0003 / 02-crop-knowledge-base.md.
DEFAULT_PROPERTIES: tuple[str, ...] = (
    "clay",   # %  → SoilGrids stores g/kg ×10, see units below
    "sand",
    "silt",
    "phh2o",  # pH (H2O) ×10
    "soc",    # soil organic carbon, dg/kg
    "bdod",   # bulk density, cg/cm³
    "cfvo",   # coarse fragments, cm³/dm³
)

# Standard GlobalSoilMap depth intervals.
ALL_DEPTHS: tuple[str, ...] = (
    "0-5cm",
    "5-15cm",
    "15-30cm",
    "30-60cm",
    "60-100cm",
    "100-200cm",
)

# Reported units for each SoilGrids property (stored as integer rescaled
# values to keep COGs compact). The numeric raster value × conversion
# factor → SI / agronomic units the rest of the pipeline expects.
_UNITS: dict[str, tuple[str, float]] = {
    "clay":  ("%",    0.1),    # g/kg →  % (÷10)
    "sand":  ("%",    0.1),
    "silt":  ("%",    0.1),
    "phh2o": ("pH",   0.1),    # pH ×10
    "soc":   ("g/kg", 0.1),    # dg/kg → g/kg
    "bdod":  ("g/cm3", 0.01),  # cg/cm³ → g/cm³
    "cfvo":  ("%",    0.1),    # cm³/dm³ → %
}


class SoilGridsSource(DataSource):
    """SoilGrids 2.0 — global soil properties at 250 m, six depths.

    Parameters
    ----------
    base_url
        Override the default WebDAV root, mainly so tests can point at a
        local synthetic raster.
    raster_opener
        Optional ``callable(url: str) -> xarray.DataArray`` used in place of
        ``rioxarray.open_rasterio``. Lets tests inject a fake reader
        without a network call.
    """

    name = "soilgrids"
    version = "2.0"
    backend = "stream"
    source_url = SOURCE_URL
    license = LICENSE
    citation_key = CITATION_KEY
    is_static = True

    def __init__(
        self,
        base_url: str = SOILGRIDS_BASE_URL,
        raster_opener=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._opener = raster_opener

    # ---- DataSource interface ------------------------------------------------

    @property
    def variables(self) -> tuple[str, ...]:
        return DEFAULT_PROPERTIES

    @property
    def temporal_coverage(self):
        # Static layer; the closest meaningful answer is "applies always".
        # Encoded as the open interval `(date.min, None)` for consistency
        # with time-varying sources that return (start, None) for ongoing.
        from datetime import date

        return (date.min, None)

    @property
    def spatial_resolution_deg(self) -> float:
        # 250 m on the native Homolosine grid; ~0.00225° in the reprojected
        # EPSG:4326 grid at mid latitudes.
        return 0.00225

    @property
    def crs(self) -> str:
        # We expose the reprojected CRS by default; native is NATIVE_CRS.
        return OUTPUT_CRS

    def load(
        self,
        bbox: BBox,
        time_range: TimeRange | None = None,
        variables: Sequence[str] | None = None,
        *,
        depths: Sequence[str] | None = None,
    ) -> xr.Dataset:
        validate_bbox(bbox)
        validate_time_range(time_range)
        props = self._resolve_variables(variables)
        depth_list = self._resolve_depths(depths)

        property_arrays: dict[str, xr.DataArray] = {}
        for prop in props:
            depth_slabs: list[xr.DataArray] = []
            for depth in depth_list:
                url = self._vrt_url(prop, depth, statistic="mean")
                da = self._read_layer(url, bbox=bbox)
                da = self._apply_units(prop, da)
                da = da.expand_dims({"depth": [depth]})
                depth_slabs.append(da)
            stacked = (
                depth_slabs[0]
                if len(depth_slabs) == 1
                else xr.concat(depth_slabs, dim="depth")
            )
            property_arrays[prop] = stacked

        ds = xr.Dataset(property_arrays)
        ds.attrs["aigriculture.provenance"] = self.provenance(
            bbox=bbox, time_range=None, variables=props,
        ).fingerprint()
        ds.attrs["depths"] = tuple(depth_list)
        return ds

    # ---- internals -----------------------------------------------------------

    def _vrt_url(self, prop: str, depth: str, *, statistic: str) -> str:
        return f"{self.base_url}/{prop}/{prop}_{depth}_{statistic}.vrt"

    def _read_layer(self, url: str, *, bbox: BBox) -> xr.DataArray:
        """Open one SoilGrids COG/VRT, clip to ``bbox``, reproject to EPSG:4326.

        Tests inject a ``raster_opener`` that returns an already-projected,
        already-clipped DataArray; in that path we bypass the live network.
        """
        if self._opener is not None:
            return self._opener(url)

        import rioxarray as rxr  # noqa: PLC0415 — keep optional dep lazy

        vsicurl_url = f"/vsicurl/{url}"
        da = rxr.open_rasterio(vsicurl_url, masked=True)
        # Squeeze the single-band dimension SoilGrids COGs always carry.
        if "band" in da.dims and da.sizes["band"] == 1:
            da = da.isel(band=0).drop_vars("band", errors="ignore")
        # SoilGrids is in Homolosine. Project the requested EPSG:4326 bbox
        # into Homolosine, clip there, then reproject the clipped raster.
        from rasterio.warp import transform_bounds  # noqa: PLC0415

        h_bounds = transform_bounds(OUTPUT_CRS, NATIVE_CRS, *bbox, densify_pts=21)
        da = da.rio.clip_box(*h_bounds)
        da = da.rio.reproject(OUTPUT_CRS)
        return da

    def _apply_units(self, prop: str, da: xr.DataArray) -> xr.DataArray:
        units, factor = _UNITS.get(prop, ("", 1.0))
        out = da * factor
        out.attrs.update(da.attrs)
        out.attrs["units"] = units
        out.attrs["soilgrids_property"] = prop
        out.attrs["scale_factor_applied"] = factor
        return out

    def _resolve_variables(self, variables: Sequence[str] | None) -> list[str]:
        if variables is None:
            return list(DEFAULT_PROPERTIES)
        unknown = [v for v in variables if v not in DEFAULT_PROPERTIES]
        if unknown:
            raise ValueError(
                f"Unknown SoilGrids properties {unknown!r}; available: "
                f"{list(DEFAULT_PROPERTIES)}"
            )
        return list(variables)

    def _resolve_depths(self, depths: Sequence[str] | None) -> list[str]:
        if depths is None:
            return list(ALL_DEPTHS)
        unknown = [d for d in depths if d not in ALL_DEPTHS]
        if unknown:
            raise ValueError(
                f"Unknown SoilGrids depths {unknown!r}; available: {list(ALL_DEPTHS)}"
            )
        return list(depths)


__all__ = [
    "ALL_DEPTHS",
    "DEFAULT_PROPERTIES",
    "SoilGridsSource",
]
