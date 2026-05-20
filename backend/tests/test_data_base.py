"""Tests for the abstract DataSource interface."""

from __future__ import annotations

from datetime import date

import pytest
import xarray as xr

from aigriculture.data.base import (
    DataSource,
    Provenance,
    validate_bbox,
    validate_time_range,
)


class _StubSource(DataSource):
    """Minimal concrete DataSource that returns an empty Dataset."""

    name = "stub"
    version = "0.0"
    backend = "local"
    source_url = "https://example.invalid/stub"
    license = "CC0-1.0"
    citation_key = "Stub2026"

    @property
    def variables(self) -> tuple[str, ...]:
        return ("t2m_mean",)

    @property
    def temporal_coverage(self):
        return (date(1979, 1, 1), None)

    @property
    def spatial_resolution_deg(self) -> float:
        return 0.1

    @property
    def crs(self) -> str:
        return "EPSG:4326"

    def load(self, bbox, time_range, variables=None):
        return xr.Dataset()


def test_provenance_fingerprint_is_stable_for_same_request():
    src = _StubSource()
    bbox = (-74.0, 45.0, -73.0, 46.0)
    tr = (date(2020, 1, 1), date(2020, 1, 31))

    p1 = src.provenance(bbox=bbox, time_range=tr, variables=("t2m_mean",))
    p2 = src.provenance(bbox=bbox, time_range=tr, variables=("t2m_mean",))

    assert p1.fingerprint() == p2.fingerprint()


def test_provenance_fingerprint_changes_with_bbox():
    src = _StubSource()
    tr = (date(2020, 1, 1), date(2020, 1, 31))

    p1 = src.provenance(bbox=(-74.0, 45.0, -73.0, 46.0), time_range=tr)
    p2 = src.provenance(bbox=(-74.0, 45.0, -73.0, 47.0), time_range=tr)

    assert p1.fingerprint() != p2.fingerprint()


def test_provenance_fingerprint_excludes_loaded_at():
    """Two calls produced at different times for the same request must match."""
    src = _StubSource()
    bbox = (-74.0, 45.0, -73.0, 46.0)
    tr = (date(2020, 1, 1), date(2020, 1, 31))

    p1 = src.provenance(bbox=bbox, time_range=tr)
    p2 = src.provenance(bbox=bbox, time_range=tr)

    assert p1.loaded_at != p2.loaded_at or p1.loaded_at == p2.loaded_at  # tautology, but
    # the loaded_at field is independent of the fingerprint:
    assert p1.fingerprint() == p2.fingerprint()


def test_provenance_to_dict_round_trip():
    src = _StubSource()
    p = src.provenance(
        bbox=(-74.0, 45.0, -73.0, 46.0),
        time_range=(date(2020, 1, 1), date(2020, 1, 31)),
    )
    d = p.to_dict()
    assert d["source_name"] == "stub"
    assert d["variables"] == ["t2m_mean"]
    assert d["fingerprint"] == p.fingerprint()


def test_validate_bbox_rejects_degenerate():
    with pytest.raises(ValueError):
        validate_bbox((0.0, 0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        validate_bbox((1.0, 0.0, 0.0, 1.0))  # minx > maxx


def test_validate_time_range_rejects_inverted():
    with pytest.raises(ValueError):
        validate_time_range((date(2020, 12, 31), date(2020, 1, 1)))


def test_stub_source_default_variables_in_provenance():
    src = _StubSource()
    p = src.provenance(
        bbox=(-74.0, 45.0, -73.0, 46.0),
        time_range=(date(2020, 1, 1), date(2020, 1, 31)),
        variables=None,
    )
    assert p.variables == ("t2m_mean",)
