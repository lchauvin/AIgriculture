"""Shared pytest fixtures for AIgriculture tests."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pytest
import xarray as xr


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    """A throwaway directory for data caches."""
    d = tmp_path / "cache"
    d.mkdir()
    return d


def _make_synthetic_agera5(
    var_long_name: str,
    bbox: tuple[float, float, float, float],
    year: int,
    month: int,
    *,
    fill_value: float = 280.0,  # plausible temperature in K
) -> xr.Dataset:
    """Build a small synthetic AgERA5-like dataset for tests."""
    from calendar import monthrange

    days = monthrange(year, month)[1]
    minx, miny, maxx, maxy = bbox
    lats = np.arange(miny, maxy + 0.1, 0.1)
    lons = np.arange(minx, maxx + 0.1, 0.1)
    times = np.array(
        [np.datetime64(f"{year:04d}-{month:02d}-{d:02d}") for d in range(1, days + 1)]
    )
    rng = np.random.default_rng(seed=42)
    data = fill_value + rng.normal(0.0, 1.0, size=(len(times), len(lats), len(lons)))
    da = xr.DataArray(
        data.astype("float32"),
        coords={"time": times, "lat": lats, "lon": lons},
        dims=("time", "lat", "lon"),
        name=var_long_name,
    )
    return da.to_dataset()


class FakeCDSClient:
    """Pytest stand-in for ``cdsapi.Client`` that writes synthetic zip-wrapped
    NetCDFs matching the real AgERA5 delivery format."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], str]] = []

    def retrieve(self, dataset_id: str, request: dict[str, object], target: str) -> None:
        import zipfile
        from calendar import monthrange

        self.calls.append((dataset_id, dict(request), target))
        # ``area`` is [north, west, south, east]; reconstruct
        # (minx, miny, maxx, maxy).
        area = request["area"]
        bbox = (area[1], area[2], area[3], area[0])  # type: ignore[index]
        year = int(request["year"])  # type: ignore[arg-type]
        month = int(request["month"])  # type: ignore[arg-type]
        statistic = str(request.get("statistic", "raw"))
        long_name = f"AgERA5_{request['variable']}_{statistic}"

        # Build a synthetic month, then split into one NetCDF per day —
        # matching the real CDS delivery layout (a zip containing one .nc
        # per day, each with a single time step).
        monthly = _make_synthetic_agera5(
            var_long_name=long_name, bbox=bbox, year=year, month=month,
        )
        days = monthrange(year, month)[1]
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            paths: list[Path] = []
            for d in range(1, days + 1):
                day_ds = monthly.isel(time=[d - 1])
                p = tdp / f"agera5_{request['variable']}_{statistic}_{year:04d}{month:02d}{d:02d}.nc"
                day_ds.to_netcdf(p)
                paths.append(p)
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in paths:
                    zf.write(p, arcname=p.name)


@pytest.fixture
def fake_cds_client() -> FakeCDSClient:
    """A `cdsapi.Client`-compatible test double."""
    return FakeCDSClient()


@pytest.fixture
def quebec_bbox() -> tuple[float, float, float, float]:
    """A tiny Quebec-ish bounding box (for fast tests)."""
    return (-74.0, 45.0, -73.0, 46.0)


@pytest.fixture
def jan_2020() -> tuple[date, date]:
    return (date(2020, 1, 1), date(2020, 1, 31))
