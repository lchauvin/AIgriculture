"""Tests for the SoilGrids 2.0 data source.

The ISRIC WebDAV service is real and reachable, but unit tests should not
depend on it. We inject a synthetic ``raster_opener`` that returns small
in-memory DataArrays — that exercises the depth-stacking, unit
conversion, and provenance code paths without any network I/O.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

import numpy as np
import pytest
import xarray as xr

from aigriculture.data.soilgrids import (
    ALL_DEPTHS,
    DEFAULT_PROPERTIES,
    SoilGridsSource,
)


def _fake_raster(
    bbox: tuple[float, float, float, float],
    *,
    fill_value: float,
    nrows: int = 4,
    ncols: int = 5,
) -> xr.DataArray:
    """Build a small EPSG:4326 raster shaped like ``_read_layer`` output."""
    minx, miny, maxx, maxy = bbox
    ys = np.linspace(maxy, miny, nrows, dtype=np.float32)
    xs = np.linspace(minx, maxx, ncols, dtype=np.float32)
    data = np.full((nrows, ncols), fill_value, dtype=np.float32)
    return xr.DataArray(
        data,
        coords={"y": ys, "x": xs},
        dims=("y", "x"),
    )


def make_opener(values_by_property: dict[str, float], bbox):
    """Return a ``raster_opener`` callable that hands back fixed values per
    property (extracted from the URL)."""

    def opener(url: str) -> xr.DataArray:
        for prop, value in values_by_property.items():
            if f"/{prop}/" in url:
                return _fake_raster(bbox, fill_value=value)
        raise AssertionError(f"unexpected SoilGrids URL: {url}")

    return opener


@pytest.fixture
def small_bbox() -> tuple[float, float, float, float]:
    # A tiny Quebec-ish window.
    return (-74.0, 45.0, -73.0, 46.0)


def test_returns_dataset_with_expected_variables(small_bbox):
    # SoilGrids stores rescaled integers; pick raw values whose factor-1 / 10
    # conversions land in plausible soil ranges.
    raw = {p: 300.0 for p in DEFAULT_PROPERTIES}
    src = SoilGridsSource(raster_opener=make_opener(raw, small_bbox))
    ds = src.load(bbox=small_bbox)

    assert set(ds.data_vars) == set(DEFAULT_PROPERTIES)
    # Every variable has a depth dimension of length 6 (all depths).
    for var in ds.data_vars:
        assert ds[var].sizes["depth"] == len(ALL_DEPTHS)


def test_depth_subset_returns_only_requested_depths(small_bbox):
    raw = {p: 300.0 for p in DEFAULT_PROPERTIES}
    src = SoilGridsSource(raster_opener=make_opener(raw, small_bbox))
    ds = src.load(bbox=small_bbox, depths=("0-5cm", "5-15cm"))
    assert ds["clay"].sizes["depth"] == 2
    np.testing.assert_array_equal(
        ds["depth"].values, np.array(["0-5cm", "5-15cm"]),
    )


def test_variable_subset(small_bbox):
    raw = {"clay": 300.0, "sand": 500.0, "phh2o": 65.0}
    src = SoilGridsSource(raster_opener=make_opener(raw, small_bbox))
    ds = src.load(bbox=small_bbox, variables=("clay", "phh2o"))
    assert set(ds.data_vars) == {"clay", "phh2o"}


def test_unknown_property_raises(small_bbox):
    src = SoilGridsSource(raster_opener=lambda _url: _fake_raster(small_bbox, fill_value=1.0))
    with pytest.raises(ValueError, match="Unknown SoilGrids properties"):
        src.load(bbox=small_bbox, variables=("not_a_property",))


def test_unknown_depth_raises(small_bbox):
    src = SoilGridsSource(raster_opener=lambda _url: _fake_raster(small_bbox, fill_value=1.0))
    with pytest.raises(ValueError, match="Unknown SoilGrids depths"):
        src.load(bbox=small_bbox, depths=("99-100cm",))


def test_units_applied_correctly(small_bbox):
    """Raw SoilGrids stores values rescaled by integer factors; the loader
    must apply the documented conversion before returning."""
    # clay: raw g/kg × 10 → %  (factor 0.1).
    # phh2o: raw pH × 10  → pH (factor 0.1).
    # bdod: raw cg/cm³ × 100 → g/cm³ (factor 0.01).
    raw = {"clay": 300.0, "phh2o": 65.0, "bdod": 150.0}
    src = SoilGridsSource(raster_opener=make_opener(raw, small_bbox))
    ds = src.load(
        bbox=small_bbox,
        variables=("clay", "phh2o", "bdod"),
        depths=("0-5cm",),
    )
    # clay 300 ×0.1 = 30 %.
    assert float(ds["clay"].mean()) == pytest.approx(30.0)
    assert ds["clay"].attrs["units"] == "%"
    # phh2o 65 ×0.1 = 6.5 pH units (typical garden soil).
    assert float(ds["phh2o"].mean()) == pytest.approx(6.5)
    assert ds["phh2o"].attrs["units"] == "pH"
    # bdod 150 ×0.01 = 1.5 g/cm³ (typical mineral soil).
    assert float(ds["bdod"].mean()) == pytest.approx(1.5)
    assert ds["bdod"].attrs["units"] == "g/cm3"


def test_static_source_accepts_none_time_range(small_bbox):
    raw = {p: 300.0 for p in DEFAULT_PROPERTIES}
    src = SoilGridsSource(raster_opener=make_opener(raw, small_bbox))
    # time_range omitted; load() must not raise.
    ds = src.load(bbox=small_bbox)
    assert ds.attrs["aigriculture.provenance"]
    assert src.is_static is True


def test_provenance_fingerprint_with_none_time(small_bbox):
    raw = {p: 300.0 for p in DEFAULT_PROPERTIES}
    src = SoilGridsSource(raster_opener=make_opener(raw, small_bbox))
    p1 = src.provenance(bbox=small_bbox, time_range=None)
    p2 = src.provenance(bbox=small_bbox, time_range=None)
    assert p1.fingerprint() == p2.fingerprint()
    # Different bbox → different fingerprint.
    p3 = src.provenance(bbox=(-75.0, 45.0, -73.0, 46.0), time_range=None)
    assert p3.fingerprint() != p1.fingerprint()


def test_vrt_url_pattern_matches_isric():
    src = SoilGridsSource()
    assert src._vrt_url("clay", "0-5cm", statistic="mean") == (
        "https://files.isric.org/soilgrids/latest/data/clay/clay_0-5cm_mean.vrt"
    )
