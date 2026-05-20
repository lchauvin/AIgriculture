"""Tests for the AgERA5 data source.

Uses the `fake_cds_client` fixture from conftest so no real CDS connection
is required.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from aigriculture.data.agera5 import AgERA5Source, _days_in_month, _month_iter


def test_month_iter_single_month():
    assert _month_iter(date(2020, 1, 1), date(2020, 1, 31)) == [(2020, 1)]


def test_month_iter_year_spanning():
    months = _month_iter(date(2019, 11, 1), date(2020, 2, 28))
    assert months == [(2019, 11), (2019, 12), (2020, 1), (2020, 2)]


def test_days_in_month_handles_leap_year():
    assert _days_in_month(2020, 2) == 29
    assert _days_in_month(2021, 2) == 28


def test_load_one_month_returns_dataset(
    tmp_cache_dir: Path,
    fake_cds_client,
    quebec_bbox,
    jan_2020,
):
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)
    ds = src.load(bbox=quebec_bbox, time_range=jan_2020, variables=("t2m_mean",))

    # Variable was renamed from CDS long-name to our public name.
    assert "t2m_mean" in ds.data_vars
    # Exactly 31 days in January 2020.
    assert ds.sizes["time"] == 31
    # Provenance fingerprint stamped on the Dataset.
    assert "aigriculture.provenance" in ds.attrs


def test_load_is_idempotent(
    tmp_cache_dir: Path,
    fake_cds_client,
    quebec_bbox,
    jan_2020,
):
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)

    src.load(bbox=quebec_bbox, time_range=jan_2020, variables=("t2m_mean",))
    first_call_count = len(fake_cds_client.calls)

    src.load(bbox=quebec_bbox, time_range=jan_2020, variables=("t2m_mean",))
    second_call_count = len(fake_cds_client.calls)

    # Second load reuses the cached NetCDF — no new CDS retrieval.
    assert second_call_count == first_call_count


def test_load_two_variables_pulls_two_files(
    tmp_cache_dir: Path,
    fake_cds_client,
    quebec_bbox,
    jan_2020,
):
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)
    src.load(
        bbox=quebec_bbox,
        time_range=jan_2020,
        variables=("t2m_mean", "precip"),
    )

    # One month × two variables == two CDS calls.
    assert len(fake_cds_client.calls) == 2
    requested_vars = {call[1]["variable"] for call in fake_cds_client.calls}
    assert requested_vars == {"2m_temperature", "precipitation_flux"}


def test_unknown_variable_raises(tmp_cache_dir: Path, fake_cds_client, quebec_bbox, jan_2020):
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)
    with pytest.raises(ValueError, match="Unknown AgERA5 variables"):
        src.load(bbox=quebec_bbox, time_range=jan_2020, variables=("not_a_variable",))


def test_bbox_makes_it_into_cds_area(
    tmp_cache_dir: Path,
    fake_cds_client,
    jan_2020,
):
    """CDS expects ``area = [north, west, south, east]`` — verify the mapping."""
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)
    bbox = (-74.5, 45.5, -73.5, 46.5)
    src.load(bbox=bbox, time_range=jan_2020, variables=("t2m_mean",))

    sent_area = fake_cds_client.calls[0][1]["area"]
    assert sent_area == [46.5, -74.5, 45.5, -73.5]  # N, W, S, E


def test_multi_variable_load_returns_named_dataset(
    tmp_cache_dir: Path,
    fake_cds_client,
    quebec_bbox,
    jan_2020,
):
    """Two variables should produce a Dataset with two correctly named
    data variables (regardless of the CDS internal naming)."""
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)
    ds = src.load(
        bbox=quebec_bbox,
        time_range=jan_2020,
        variables=("t2m_min", "t2m_max"),
    )
    assert set(ds.data_vars) == {"t2m_min", "t2m_max"}
    assert ds.sizes["time"] == 31


def test_multi_month_load_concatenates_time(
    tmp_cache_dir: Path,
    fake_cds_client,
    quebec_bbox,
):
    """A time range spanning two months should produce a single
    contiguous time axis."""
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)
    ds = src.load(
        bbox=quebec_bbox,
        time_range=(date(2020, 1, 15), date(2020, 2, 14)),
        variables=("t2m_mean",),
    )
    assert ds.sizes["time"] == 31  # Jan 15..31 + Feb 1..14
    # Dates are monotonically increasing.
    times = ds["time"].values
    assert (times[1:] > times[:-1]).all()


def test_returned_data_is_numeric(
    tmp_cache_dir: Path,
    fake_cds_client,
    quebec_bbox,
    jan_2020,
):
    src = AgERA5Source(cache_dir=tmp_cache_dir, api_client=fake_cds_client)
    ds = src.load(bbox=quebec_bbox, time_range=jan_2020, variables=("t2m_mean",))
    arr = ds["t2m_mean"].values
    assert np.isfinite(arr).all()
    # synthetic data centered at 280 K, σ=1 — sanity check the mean.
    assert 275.0 < float(arr.mean()) < 285.0
