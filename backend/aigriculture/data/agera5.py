"""AgERA5 — Copernicus C3S Agrometeorological Indicators data source.

AgERA5 is ERA5-derived, agriculture-tailored daily forcing at 0.1° (~10 km),
1979 – present. It is the primary historical climate driver for AIgriculture's
Tier 2 (PCSE / WOFOST) per ADR 0002.

Dataset DOI: 10.24381/cds.6c68c9bb
Catalogue:   https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators
License:     CC BY 4.0

Authentication
--------------
The Copernicus Climate Data Store API (``cdsapi``) reads credentials from
``~/.cdsapirc``. Generating an API key requires a free CDS account. We do
*not* embed credentials in code; ``cdsapi`` will raise a clear error if the
file is missing.

Caching
-------
Downloads are written month-by-month to a local NetCDF cache, then opened as
a single chunked dataset via ``xarray.open_mfdataset``. A subsequent call with
the same ``(bbox, variables, time_range)`` is idempotent — the loader skips
any NetCDF already on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

import xarray as xr

from .base import (
    BBox,
    DataSource,
    Provenance,
    TimeRange,
    validate_bbox,
    validate_time_range,
)

DATASET_ID = "sis-agrometeorological-indicators"
GRID_DEG = 0.1
CRS = "EPSG:4326"
SOURCE_URL = "https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators"
LICENSE = "CC-BY-4.0"
CITATION_KEY = "BoogaardAgERA5"


# The AgERA5 catalogue exposes variables that the user requests jointly with a
# `statistic` (24h min/mean/max for temperature, 24h flux for precipitation,
# etc.). To keep the AIgriculture-facing API simple, we expose pre-bundled
# (variable, statistic, output-name) tuples; the user asks for the
# output-name and the loader handles the joint CDS call.
@dataclass(frozen=True, slots=True)
class _VarSpec:
    """Mapping from an AIgriculture-facing variable name to its CDS request."""

    out_name: str          # what we return as a Dataset variable
    cds_variable: str      # CDS API ``variable`` value
    cds_statistic: str     # CDS API ``statistic`` value


# Minimal Tier-2-ready bundle. Extend in Phase 3 if/when more variables are
# needed (solar radiation, RH at multiple hours, etc.).
_VARS: dict[str, _VarSpec] = {
    "t2m_min": _VarSpec("t2m_min", "2m_temperature", "24_hour_minimum"),
    "t2m_max": _VarSpec("t2m_max", "2m_temperature", "24_hour_maximum"),
    "t2m_mean": _VarSpec("t2m_mean", "2m_temperature", "24_hour_mean"),
    "precip": _VarSpec("precip", "precipitation_flux", "24_hour_mean"),
    "solar_rad": _VarSpec("solar_rad", "solar_radiation_flux", "24_hour_mean"),
}


class AgERA5Source(DataSource):
    """Local-Zarr AgERA5 source backed by a NetCDF download cache.

    Parameters
    ----------
    cache_dir
        Where to keep the NetCDF month-chunks. Anything cached here can be
        deleted; the loader will re-download as needed.
    api_client
        Optional pre-built ``cdsapi.Client`` instance — used in tests so the
        loader can be exercised without a real CDS connection. If omitted,
        a default client is created on first use.
    """

    name = "agera5"
    version = "1.1"  # CDS dataset version
    backend = "local"
    source_url = SOURCE_URL
    license = LICENSE
    citation_key = CITATION_KEY

    def __init__(
        self,
        cache_dir: str | Path,
        api_client: object | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = api_client

    # ---- DataSource interface ------------------------------------------------

    @property
    def variables(self) -> tuple[str, ...]:
        return tuple(_VARS.keys())

    @property
    def temporal_coverage(self) -> tuple[date, date | None]:
        # The dataset is daily from 1979-01-01 to "present", with an
        # operational lag of a few weeks.
        return (date(1979, 1, 1), None)

    @property
    def spatial_resolution_deg(self) -> float:
        return GRID_DEG

    @property
    def crs(self) -> str:
        return CRS

    def load(
        self,
        bbox: BBox,
        time_range: TimeRange,
        variables: Sequence[str] | None = None,
    ) -> xr.Dataset:
        validate_bbox(bbox)
        validate_time_range(time_range)
        var_keys = self._resolve_variables(variables)

        files: list[Path] = []
        for year, month in _month_iter(*time_range):
            for key in var_keys:
                spec = _VARS[key]
                fp = self._cache_path(spec, year, month, bbox)
                if not fp.exists():
                    self._download_month(spec, year, month, bbox, fp)
                files.append(fp)

        ds = xr.open_mfdataset(files, combine="by_coords", chunks={"time": 30})
        ds = ds.sel(
            time=slice(time_range[0].isoformat(), time_range[1].isoformat()),
        )
        # Rename CDS variables to our public names. AgERA5 NetCDFs name the
        # variable after the CDS ``variable`` field (e.g. ``Temperature_Air_2m_Mean_24h``);
        # the exact name is statistic-dependent. We rename by position.
        ds = self._normalize_variable_names(ds, var_keys)
        # Attach provenance as a global attribute for traceability.
        ds.attrs["aigriculture.provenance"] = self.provenance(
            bbox=bbox,
            time_range=time_range,
            variables=var_keys,
        ).fingerprint()
        return ds

    # ---- internals -----------------------------------------------------------

    def _resolve_variables(self, variables: Sequence[str] | None) -> list[str]:
        if variables is None:
            return list(_VARS)
        unknown = [v for v in variables if v not in _VARS]
        if unknown:
            raise ValueError(
                f"Unknown AgERA5 variables {unknown!r}; available: {list(_VARS)}"
            )
        return list(variables)

    def _cache_path(self, spec: _VarSpec, year: int, month: int, bbox: BBox) -> Path:
        # bbox is in the filename so different regions don't collide.
        bbox_tag = "_".join(f"{x:+.2f}" for x in bbox).replace("+", "p").replace("-", "m")
        fname = f"agera5_{spec.out_name}_{year:04d}{month:02d}_{bbox_tag}.nc"
        return self.cache_dir / fname

    def _download_month(
        self,
        spec: _VarSpec,
        year: int,
        month: int,
        bbox: BBox,
        out: Path,
    ) -> None:
        client = self._get_client()
        minx, miny, maxx, maxy = bbox
        # CDS expects area as [north, west, south, east].
        area = [maxy, minx, miny, maxx]
        days = [f"{d:02d}" for d in range(1, _days_in_month(year, month) + 1)]
        request = {
            "format": "netcdf",
            "variable": spec.cds_variable,
            "statistic": spec.cds_statistic,
            "year": f"{year:04d}",
            "month": f"{month:02d}",
            "day": days,
            "area": area,
            "version": self.version,
        }
        client.retrieve(DATASET_ID, request, str(out))  # type: ignore[attr-defined]

    def _get_client(self) -> object:
        if self._client is not None:
            return self._client
        # Lazy import — `cdsapi` is an optional dependency.
        import cdsapi  # noqa: PLC0415

        self._client = cdsapi.Client()
        return self._client

    @staticmethod
    def _normalize_variable_names(ds: xr.Dataset, requested: Sequence[str]) -> xr.Dataset:
        """Best-effort rename of CDS-named variables to AgERA5Source out-names.

        AgERA5 NetCDFs include long, statistic-specific variable names. When
        the file contains exactly one data variable, we rename it to the
        requested out-name. When there are several we leave them untouched
        and trust downstream selection via ``ds[var_name]``.
        """
        data_vars = [v for v in ds.data_vars]
        if len(data_vars) == 1 and len(requested) == 1:
            return ds.rename({data_vars[0]: requested[0]})
        return ds


# ---- helpers ----------------------------------------------------------------


def _days_in_month(year: int, month: int) -> int:
    from calendar import monthrange

    return monthrange(year, month)[1]


def _month_iter(start: date, end: date) -> list[tuple[int, int]]:
    """Yield ``(year, month)`` tuples covering ``[start, end]`` inclusive."""
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


__all__ = ["AgERA5Source", "DATASET_ID", "GRID_DEG"]
