"""Tests for the AAFC ACI Earth Engine data source.

We never hit the live Earth Engine service in unit tests. Instead we inject
an ``image_fetcher`` that writes a small synthetic GeoTIFF, then exercise
the cache, multi-year concat, year-range clipping, and error paths.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from aigriculture.data.aafc_aci import (
    AAFCACISource,
    COVERAGE_END_KNOWN,
    LEGEND,
    _years_in_range,
    aci_label,
)


def _write_synthetic_aci_tiff(
    path: Path,
    bbox: tuple[float, float, float, float],
    *,
    fill_value: int,
    nrows: int = 6,
    ncols: int = 8,
) -> None:
    """Write a tiny EPSG:4326 single-band uint8 GeoTIFF over ``bbox``."""
    minx, miny, maxx, maxy = bbox
    res_x = (maxx - minx) / ncols
    res_y = (maxy - miny) / nrows
    transform = from_origin(minx, maxy, res_x, res_y)
    data = np.full((nrows, ncols), fill_value, dtype=np.uint8)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=ncols,
        height=nrows,
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as ds:
        ds.write(data, 1)


@pytest.fixture
def small_bbox() -> tuple[float, float, float, float]:
    return (-74.0, 45.0, -73.0, 46.0)


@pytest.fixture
def fake_fetcher(small_bbox):
    """A fetcher that writes a synthetic ACI raster with year-encoded values."""
    calls: list[tuple[int, tuple, Path]] = []

    def fetcher(year: int, bbox, dest: Path) -> None:
        calls.append((year, bbox, dest))
        # encode the year as the pixel value so tests can assert which year
        # produced which raster.
        _write_synthetic_aci_tiff(dest, bbox, fill_value=year - 2000)

    fetcher.calls = calls  # type: ignore[attr-defined]
    return fetcher


def test_year_iteration_inclusive():
    assert _years_in_range((date(2015, 1, 1), date(2017, 12, 31))) == [2015, 2016, 2017]
    assert _years_in_range((date(2015, 6, 1), date(2015, 8, 31))) == [2015]


def test_year_iteration_clipped_to_coverage():
    assert _years_in_range((date(2005, 1, 1), date(2011, 12, 31))) == [2009, 2010, 2011]
    assert _years_in_range(
        (date(2024, 1, 1), date(2030, 12, 31))
    ) == [2024]


def test_load_single_year_returns_dataset(tmp_path: Path, fake_fetcher, small_bbox):
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2020, 1, 1), date(2020, 12, 31)),
    )
    assert list(ds.data_vars) == ["landcover"]
    assert ds.sizes["time"] == 1
    np.testing.assert_array_equal(
        ds["time"].values,
        np.array([np.datetime64("2020-01-01")]),
    )
    # The synthetic fetcher writes (year - 2000) as the pixel value.
    assert float(ds["landcover"].mean()) == pytest.approx(20.0)


def test_load_multiple_years_concatenates(tmp_path: Path, fake_fetcher, small_bbox):
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2018, 1, 1), date(2020, 12, 31)),
    )
    assert ds.sizes["time"] == 3
    np.testing.assert_array_equal(
        ds["time"].values,
        np.array([f"{y}-01-01" for y in (2018, 2019, 2020)], dtype="datetime64"),
    )
    # The mean across years and pixels should reflect (18 + 19 + 20) / 3.
    assert float(ds["landcover"].mean()) == pytest.approx(19.0)


def test_load_is_idempotent(tmp_path: Path, fake_fetcher, small_bbox):
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    src.load(bbox=small_bbox, time_range=(date(2020, 1, 1), date(2020, 12, 31)))
    first_count = len(fake_fetcher.calls)

    src.load(bbox=small_bbox, time_range=(date(2020, 1, 1), date(2020, 12, 31)))
    second_count = len(fake_fetcher.calls)

    assert second_count == first_count  # cached TIFF reused


def test_load_clips_time_range_to_coverage(tmp_path: Path, fake_fetcher, small_bbox):
    """Years before 2009 and after the latest known year should be dropped."""
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2007, 1, 1), date(2010, 12, 31)),
    )
    assert ds.sizes["time"] == 2  # 2009, 2010
    years_seen = {call[0] for call in fake_fetcher.calls}
    assert years_seen == {2009, 2010}


def test_load_requires_time_range(tmp_path: Path, fake_fetcher, small_bbox):
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    with pytest.raises(ValueError, match="time-varying"):
        src.load(bbox=small_bbox, time_range=None)


def test_load_empty_year_range_raises(tmp_path: Path, fake_fetcher, small_bbox):
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    with pytest.raises(ValueError, match="no full calendar year"):
        src.load(
            bbox=small_bbox,
            time_range=(date(2005, 1, 1), date(2007, 12, 31)),
        )


def test_unknown_variable_raises(tmp_path: Path, fake_fetcher, small_bbox):
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    with pytest.raises(ValueError, match="only the 'landcover' band"):
        src.load(
            bbox=small_bbox,
            time_range=(date(2020, 1, 1), date(2020, 12, 31)),
            variables=("not_a_band",),
        )


def test_ee_initialize_requires_project(tmp_path: Path, small_bbox):
    """If no fetcher is injected, EE initialization needs a project ID."""
    src = AAFCACISource(cache_dir=tmp_path)  # no fetcher, no ee_project
    with pytest.raises(RuntimeError, match="Earth Engine project"):
        src.load(
            bbox=small_bbox,
            time_range=(date(2020, 1, 1), date(2020, 12, 31)),
        )


def test_provenance_records_landcover(tmp_path: Path, fake_fetcher, small_bbox):
    src = AAFCACISource(cache_dir=tmp_path, image_fetcher=fake_fetcher)
    p = src.provenance(
        bbox=small_bbox,
        time_range=(date(2020, 1, 1), date(2020, 12, 31)),
    )
    assert p.variables == ("landcover",)
    assert p.backend == "stream"


def test_coverage_end_known_is_a_real_year():
    """Guard against accidental future-dating of the coverage constant."""
    assert COVERAGE_END_KNOWN.year >= 2024


def test_legend_contains_quebec_staples():
    """Codes Quebec MVP cares about most must be present and named correctly."""
    expected = {
        20:  "Water",
        34:  "Urban and Developed",
        122: "Pasture and Forages",
        146: "Spring Wheat",
        147: "Corn for Grain",
        153: "Canola and Rapeseed",
        158: "Soybeans",
        210: "Coniferous",
        220: "Broadleaf",
        230: "Mixedwood",
    }
    for code, name in expected.items():
        assert LEGEND[code] == name, f"legend code {code}: {LEGEND[code]!r} != {name!r}"


def test_aci_label_unknown_code_returns_fallback():
    label = aci_label(99999)
    assert label.startswith("Unknown")
    assert "99999" in label


def test_aci_label_known_code():
    assert aci_label(147) == "Corn for Grain"
    assert aci_label(158) == "Soybeans"
