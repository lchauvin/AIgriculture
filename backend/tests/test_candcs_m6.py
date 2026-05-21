"""Tests for the CanDCS-M6 PAVICS / OPeNDAP data source.

PAVICS THREDDS is real and reachable, but unit tests inject a synthetic
``dataset_opener`` so they're fast and offline. Each opener call records
the URL it was given, which lets us assert that the loader builds the
right OPeNDAP path per (GCM × SSP).
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

import numpy as np
import pytest
import xarray as xr

from aigriculture.data.candcs_m6 import (
    CanDCSM6Source,
    DEFAULT_SSPS,
    DEFAULT_VARIABLES,
    GCM_REGISTRY,
)


def _make_synthetic_candcs(
    bbox: tuple[float, float, float, float],
    *,
    start: str = "2040-01-01",
    end: str = "2042-12-31",
    fill: dict[str, float] | None = None,
) -> xr.Dataset:
    """Build a small synthetic CanDCS-M6-like dataset."""
    times = np.arange(
        np.datetime64(start), np.datetime64(end) + np.timedelta64(1, "D"),
        np.timedelta64(1, "D"),
    )
    minx, miny, maxx, maxy = bbox
    lats = np.arange(miny - 0.5, maxy + 0.5 + 1.0 / 12, 1.0 / 12)
    lons = np.arange(minx - 0.5, maxx + 0.5 + 1.0 / 12, 1.0 / 12)
    fill = fill or {"tasmax": 290.0, "tasmin": 280.0, "pr": 2e-5}
    coords = {"time": times, "lat": lats, "lon": lons}
    shape = (len(times), len(lats), len(lons))
    data_vars = {
        name: (("time", "lat", "lon"), np.full(shape, val, dtype="float32"))
        for name, val in fill.items()
    }
    return xr.Dataset(data_vars, coords=coords)


def make_recording_opener(bbox, **kwargs):
    """Return a (calls, opener) pair: the opener serves a synthetic
    dataset and records every URL it was given."""
    calls: list[str] = []

    def opener(url: str) -> xr.Dataset:
        calls.append(url)
        return _make_synthetic_candcs(bbox, **kwargs)

    return calls, opener


@pytest.fixture
def small_bbox() -> tuple[float, float, float, float]:
    return (-74.0, 45.0, -73.0, 46.0)


def test_opendap_url_pattern_matches_pavics(small_bbox):
    src = CanDCSM6Source()
    url = src._opendap_url("CanESM5", "ssp245")
    assert url == (
        "https://pavics.ouranos.ca/thredds/dodsC/datasets/"
        "simulations/bias_adjusted/cmip6/pcic/CanDCS-M6/"
        "day_MBCn+PCIC-Blend_CanESM5_historical+ssp245_r1i1p2f1_gn"
        "_19500101-21001231.ncml"
    )


def test_load_one_gcm_one_ssp(small_bbox):
    calls, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2040, 1, 1), date(2040, 12, 31)),
        gcms=("CanESM5",),
        ssps=("ssp245",),
        variables=("tasmax",),
    )
    assert list(ds.data_vars) == ["tasmax"]
    assert ds.sizes["gcm"] == 1
    assert ds.sizes["ssp"] == 1
    assert ds.sizes["time"] == 366  # 2040 is a leap year
    assert len(calls) == 1
    assert "CanESM5_historical+ssp245" in calls[0]


def test_load_multiple_gcms_and_ssps(small_bbox):
    calls, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2040, 1, 1), date(2040, 12, 31)),
        gcms=("CanESM5", "MPI-ESM1-2-LR"),
        ssps=("ssp126", "ssp585"),
        variables=("tasmax",),
    )
    assert ds.sizes["gcm"] == 2
    assert ds.sizes["ssp"] == 2
    # The dataset coordinates carry the GCM and SSP labels.
    assert list(ds["gcm"].values) == ["CanESM5", "MPI-ESM1-2-LR"]
    assert list(ds["ssp"].values) == ["ssp126", "ssp585"]
    # 2 GCMs × 2 SSPs = 4 OPeNDAP opens.
    assert len(calls) == 4


def test_default_gcms_and_ssps_match_adr_0005(small_bbox):
    """The defaults should be the ADR 0005 short-list."""
    calls, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    src.load(
        bbox=small_bbox,
        time_range=(date(2040, 1, 1), date(2040, 1, 31)),
        variables=("tasmax",),
    )
    # 5 GCMs × 3 SSPs by default → 15 opens.
    assert len(calls) == 5 * 3


def test_unknown_gcm_raises(small_bbox):
    _, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    with pytest.raises(ValueError, match="GCM_REGISTRY"):
        src.load(
            bbox=small_bbox,
            time_range=(date(2040, 1, 1), date(2040, 12, 31)),
            gcms=("FAKE-GCM",),
        )


def test_unknown_ssp_raises(small_bbox):
    _, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    with pytest.raises(ValueError, match="Unknown SSPs"):
        src.load(
            bbox=small_bbox,
            time_range=(date(2040, 1, 1), date(2040, 12, 31)),
            ssps=("ssp999",),
        )


def test_unknown_variable_raises(small_bbox):
    _, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    with pytest.raises(ValueError, match="Unknown CanDCS-M6 variables"):
        src.load(
            bbox=small_bbox,
            time_range=(date(2040, 1, 1), date(2040, 12, 31)),
            variables=("not_a_variable",),
        )


def test_requires_time_range(small_bbox):
    _, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    with pytest.raises(ValueError, match="time-varying"):
        src.load(bbox=small_bbox, time_range=None)


def test_bbox_subset_applied(small_bbox):
    """The synthetic opener returns a wider bbox; load() should clip it."""
    calls, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2040, 1, 1), date(2040, 1, 5)),
        gcms=("CanESM5",),
        ssps=("ssp245",),
        variables=("tasmax",),
    )
    # The synthetic data spans [miny-0.5, maxy+0.5] but the .sel() should
    # have clipped to [miny, maxy].
    assert ds["lat"].min().item() >= small_bbox[1] - 0.05  # tolerate edge step
    assert ds["lat"].max().item() <= small_bbox[3] + 0.05


def test_time_subset_applied(small_bbox):
    _, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2040, 6, 1), date(2040, 6, 30)),
        gcms=("CanESM5",),
        ssps=("ssp245",),
        variables=("tasmax",),
    )
    assert ds.sizes["time"] == 30


def test_descending_lat_axis_handled_correctly(small_bbox):
    """Some PAVICS files may publish lat north→south; the subset code should
    auto-flip the slice direction."""

    def opener(url: str) -> xr.Dataset:
        ds = _make_synthetic_candcs(small_bbox)
        # Reverse the lat axis to simulate north-down ordering.
        return ds.isel(lat=slice(None, None, -1))

    src = CanDCSM6Source(dataset_opener=opener)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2040, 1, 1), date(2040, 1, 5)),
        gcms=("CanESM5",),
        ssps=("ssp245",),
        variables=("tasmax",),
    )
    assert ds.sizes["lat"] > 0


def test_provenance_records_variables_and_streaming(small_bbox):
    _, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    p = src.provenance(
        bbox=small_bbox,
        time_range=(date(2040, 1, 1), date(2040, 12, 31)),
        variables=("tasmax", "tasmin"),
    )
    assert p.variables == ("tasmax", "tasmin")
    assert p.backend == "stream"
    assert p.citation_key == "Sobie2024CanDCSM6"


def test_gcm_registry_includes_adr_0005_shortlist():
    """Defends against accidental removal of the ADR 0005 short-list."""
    required = {"CanESM5", "MPI-ESM1-2-LR", "MIROC6", "GFDL-ESM4", "EC-Earth3"}
    assert required.issubset(set(GCM_REGISTRY)), (
        f"GCM_REGISTRY missing {required - set(GCM_REGISTRY)!r}"
    )


def test_returned_dataset_carries_gcm_and_ssp_attrs(small_bbox):
    _, opener = make_recording_opener(small_bbox)
    src = CanDCSM6Source(dataset_opener=opener)
    ds = src.load(
        bbox=small_bbox,
        time_range=(date(2040, 1, 1), date(2040, 1, 5)),
        gcms=("CanESM5",),
        ssps=("ssp245",),
        variables=("tasmax",),
    )
    assert ds.attrs["gcms"] == ("CanESM5",)
    assert ds.attrs["ssps"] == ("ssp245",)
