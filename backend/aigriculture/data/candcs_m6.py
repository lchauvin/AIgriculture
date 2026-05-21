"""CanDCS-M6 — Canadian Downscaled Climate Scenarios (Multivariate, CMIP6).

Primary future-climate projection source for the Quebec MVP per ADR 0002.
Statistically downscaled CMIP6 daily Tmin / Tmax / precipitation at 1/12°
(~8 km) over Canada, 1950 – 2100, multivariate-bias-corrected with the
MBCn-PCIC-Blend method (Sobie et al. 2024) [@Sobie2024CanDCSM6].

Access pattern
--------------
The daily files are served by the **PAVICS THREDDS** catalogue (Ouranos
+ CRIM):

    https://pavics.ouranos.ca/thredds/catalog/datasets/simulations/bias_adjusted/cmip6/pcic/CanDCS-M6/

Each file is an NcML aggregation of the underlying yearly NetCDFs. The
filename pattern is::

    day_MBCn+PCIC-Blend_<GCM>_historical+ssp<NNN>_<ENS>_<GRID>_19500101-21001231.ncml

where ``<ENS>`` is the CMIP6 ensemble-member ID (e.g. ``r1i1p1f1``) and
``<GRID>`` is the grid label (``gn`` / ``gr`` / ``gr1`` — varies per GCM).
We open each file lazily via OPeNDAP::

    https://pavics.ouranos.ca/thredds/dodsC/datasets/simulations/bias_adjusted/cmip6/pcic/CanDCS-M6/<filename>

so an xarray ``open_dataset`` never has to download anything past the
metadata header. Subsequent ``.sel(time=slice(...), lat=slice(...),
lon=slice(...))`` pulls only the bytes needed.

License: Open Government Licence – Canada.

Units
-----
PCIC stores CanDCS-M6 in user-friendly units rather than raw CMIP6:

- ``tasmax`` and ``tasmin``: **degrees Celsius** (CMIP6 standard is Kelvin).
- ``pr``: **kg m⁻² day⁻¹** (== mm/day; CMIP6 standard is kg m⁻² s⁻¹).

The loader passes values through unmodified. The ``units`` attribute on
each variable carries the canonical string; downstream code (climate
indicators, crop models) should respect it explicitly rather than
assume.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Iterable, Sequence

import xarray as xr

from .base import (
    BBox,
    DataSource,
    TimeRange,
    validate_bbox,
    validate_time_range,
)

PAVICS_OPENDAP_BASE = (
    "https://pavics.ouranos.ca/thredds/dodsC/datasets/"
    "simulations/bias_adjusted/cmip6/pcic/CanDCS-M6"
)
NATIVE_RESOLUTION_DEG = 1.0 / 12.0  # ~8 km
CRS = "EPSG:4326"
SOURCE_URL = "https://pavics.ouranos.ca/thredds/catalog/datasets/simulations/bias_adjusted/cmip6/pcic/CanDCS-M6/catalog.html"
LICENSE = "OGL-Canada-2.0"
CITATION_KEY = "Sobie2024CanDCSM6"

# Coverage spans the joint historical-plus-future archive.
COVERAGE_START = date(1950, 1, 1)
COVERAGE_END = date(2100, 12, 31)
HISTORICAL_END = date(2014, 12, 31)  # for documentation; SSPs begin 2015.

# GCM registry — each value is (ensemble member, grid label) as appears in
# the PAVICS filename. Confirmed against the live catalogue 2026-05.
# Aligned with the provisional ADR 0005 short-list; extend in Phase 4 to
# the full 27-GCM set when needed.
GCM_REGISTRY: dict[str, tuple[str, str]] = {
    "CanESM5":       ("r1i1p2f1", "gn"),
    "MPI-ESM1-2-LR": ("r1i1p1f1", "gn"),
    "MIROC6":        ("r1i1p1f1", "gn"),
    "GFDL-ESM4":     ("r1i1p1f1", "gr1"),
    "EC-Earth3":     ("r4i1p1f1", "gr"),
}

# Default SSPs per ADR 0005. SSP3-7.0 is published for a subset of GCMs
# in CanDCS-M6; opt in explicitly with ``ssps=("ssp370",)`` when wanted.
DEFAULT_SSPS: tuple[str, ...] = ("ssp126", "ssp245", "ssp585")

DEFAULT_VARIABLES: tuple[str, ...] = ("tasmax", "tasmin", "pr")

DateRangeTag = "19500101-21001231"

# Injection point for tests: ``(opendap_url) -> xarray.Dataset``.
DatasetOpener = Callable[[str], xr.Dataset]


class CanDCSM6Source(DataSource):
    """Streaming OPeNDAP loader over the PAVICS CanDCS-M6 archive."""

    name = "candcs_m6"
    # PCIC's MBCn-Blend daily release on PAVICS, dated by Sobie et al.
    # 2024. Bump if PCIC publishes a versioned re-release.
    version = "PCIC-MBCn-Blend-2024"
    backend = "stream"
    is_static = False
    source_url = SOURCE_URL
    license = LICENSE
    citation_key = CITATION_KEY

    def __init__(
        self,
        *,
        base_url: str = PAVICS_OPENDAP_BASE,
        dataset_opener: DatasetOpener | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._opener = dataset_opener

    # ---- DataSource interface ------------------------------------------------

    @property
    def variables(self) -> tuple[str, ...]:
        return DEFAULT_VARIABLES

    @property
    def temporal_coverage(self) -> tuple[date, date | None]:
        return (COVERAGE_START, COVERAGE_END)

    @property
    def spatial_resolution_deg(self) -> float:
        return NATIVE_RESOLUTION_DEG

    @property
    def crs(self) -> str:
        return CRS

    def load(
        self,
        bbox: BBox,
        time_range: TimeRange | None = None,
        variables: Sequence[str] | None = None,
        *,
        gcms: Sequence[str] | None = None,
        ssps: Sequence[str] | None = None,
    ) -> xr.Dataset:
        validate_bbox(bbox)
        validate_time_range(time_range)
        if time_range is None:
            raise ValueError(
                "CanDCS-M6 is time-varying; pass a time_range covering the "
                "historical and/or future window you want."
            )
        vars_ = self._resolve_variables(variables)
        gcm_list = self._resolve_gcms(gcms)
        ssp_list = self._resolve_ssps(ssps)

        # Build a sparse 4-axis (gcm × ssp × variable × per-file) of
        # subsetted DataArrays, then assemble into a Dataset.
        gcm_arrays: dict[str, dict[str, dict[str, xr.DataArray]]] = {}
        for gcm in gcm_list:
            gcm_arrays[gcm] = {}
            for ssp in ssp_list:
                url = self._opendap_url(gcm, ssp)
                ds = self._open(url)
                ds = self._subset(ds, bbox=bbox, time_range=time_range)
                gcm_arrays[gcm][ssp] = {v: ds[v] for v in vars_}

        # Assemble: for each variable, stack across (gcm, ssp). We expand
        # along new dims rather than xr.concat to give callers clean
        # (gcm, ssp, time, lat, lon) shape.
        out_vars: dict[str, xr.DataArray] = {}
        for var in vars_:
            per_ssp_stacks = []
            for ssp in ssp_list:
                per_gcm = [
                    gcm_arrays[g][ssp][var].expand_dims(gcm=[g])
                    for g in gcm_list
                ]
                stacked = (
                    per_gcm[0] if len(per_gcm) == 1
                    else xr.concat(per_gcm, dim="gcm")
                )
                per_ssp_stacks.append(stacked.expand_dims(ssp=[ssp]))
            combined = (
                per_ssp_stacks[0] if len(per_ssp_stacks) == 1
                else xr.concat(per_ssp_stacks, dim="ssp")
            )
            out_vars[var] = combined

        ds = xr.Dataset(out_vars)
        ds.attrs["aigriculture.provenance"] = self.provenance(
            bbox=bbox, time_range=time_range, variables=vars_,
        ).fingerprint()
        ds.attrs["gcms"] = tuple(gcm_list)
        ds.attrs["ssps"] = tuple(ssp_list)
        return ds

    # ---- internals -----------------------------------------------------------

    def _resolve_variables(self, variables: Sequence[str] | None) -> list[str]:
        if variables is None:
            return list(DEFAULT_VARIABLES)
        unknown = [v for v in variables if v not in DEFAULT_VARIABLES]
        if unknown:
            raise ValueError(
                f"Unknown CanDCS-M6 variables {unknown!r}; available: "
                f"{list(DEFAULT_VARIABLES)}"
            )
        return list(variables)

    def _resolve_gcms(self, gcms: Sequence[str] | None) -> list[str]:
        if gcms is None:
            return list(GCM_REGISTRY)
        unknown = [g for g in gcms if g not in GCM_REGISTRY]
        if unknown:
            raise ValueError(
                f"GCM(s) {unknown!r} not in the AIgriculture CanDCS-M6 "
                f"registry. Known GCMs: {list(GCM_REGISTRY)}. To add a GCM, "
                f"extend GCM_REGISTRY with its (ensemble_member, grid_label) "
                f"as it appears on the PAVICS catalogue."
            )
        return list(gcms)

    def _resolve_ssps(self, ssps: Sequence[str] | None) -> list[str]:
        if ssps is None:
            return list(DEFAULT_SSPS)
        allowed = {"ssp126", "ssp245", "ssp370", "ssp585"}
        unknown = [s for s in ssps if s not in allowed]
        if unknown:
            raise ValueError(
                f"Unknown SSPs {unknown!r}; allowed: {sorted(allowed)}."
            )
        return list(ssps)

    def _opendap_url(self, gcm: str, ssp: str) -> str:
        ens, grid = GCM_REGISTRY[gcm]
        filename = (
            f"day_MBCn+PCIC-Blend_{gcm}_historical+{ssp}"
            f"_{ens}_{grid}_{DateRangeTag}.ncml"
        )
        return f"{self.base_url}/{filename}"

    def _open(self, url: str) -> xr.Dataset:
        if self._opener is not None:
            return self._opener(url)
        # Open lazily; ``decode_times=True`` is the default and matters for
        # the time-slice path below.
        return xr.open_dataset(url, chunks={"time": 365})

    @staticmethod
    def _subset(
        ds: xr.Dataset,
        *,
        bbox: BBox,
        time_range: TimeRange,
    ) -> xr.Dataset:
        minx, miny, maxx, maxy = bbox
        # CanDCS-M6 NetCDFs use ``lat`` (south→north ascending) and ``lon``
        # (-180..180). Defensive: pick the slice direction matching the
        # coordinate ordering on the actual file.
        lat = ds["lat"]
        lat_slice = (
            slice(miny, maxy)
            if float(lat[0]) < float(lat[-1])
            else slice(maxy, miny)
        )
        lon = ds["lon"]
        lon_slice = (
            slice(minx, maxx)
            if float(lon[0]) < float(lon[-1])
            else slice(maxx, minx)
        )
        return ds.sel(
            lat=lat_slice,
            lon=lon_slice,
            time=slice(time_range[0].isoformat(), time_range[1].isoformat()),
        )


__all__ = [
    "CanDCSM6Source",
    "COVERAGE_END",
    "COVERAGE_START",
    "DEFAULT_SSPS",
    "DEFAULT_VARIABLES",
    "GCM_REGISTRY",
    "HISTORICAL_END",
]
