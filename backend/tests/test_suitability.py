"""Tests for the Tier 1 suitability stack.

Three modules under test:
- aigriculture.suitability.requirements
- aigriculture.suitability.indicators
- aigriculture.suitability.envelope

Each test uses small deterministic inputs so the expected values are
inspectable by hand.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from aigriculture.suitability import envelope, indicators, requirements


# ---- requirements -----------------------------------------------------------


def test_default_quebec_catalogue_loads():
    cat = requirements.load_catalogue()
    ids = {c.id for c in cat.crops}
    assert ids == {"corn_grain", "soybean", "spring_wheat", "canola"}
    assert cat.schema_version == 1


def test_corn_temperature_window_quebec_tuned():
    """The corn temperature window is Quebec-tuned (lower tmean_optimal_min
    than ECOCROP's tropical baseline); see the YAML's cultivar-calibration
    notes."""
    cat = requirements.load_catalogue()
    corn = cat.by_id("corn_grain")
    assert corn.scientific_name == "Zea mays"
    assert corn.ecoport_code == 2175
    t = corn.temperature
    assert t.tmean_absolute_min_c == 10.0    # ECOCROP TMIN preserved
    assert t.tmean_optimal_min_c == 14.0     # Quebec-tuned; ECOCROP 18.0
    assert t.tmean_optimal_max_c == 33.0     # ECOCROP TOPMX preserved
    assert t.tmean_absolute_max_c == 47.0    # ECOCROP TMAX preserved


def test_corn_gdd_window_quebec_tuned():
    """Corn GDD bounds cover the Quebec MG range *plus* cultivar
    adaptation under warming (broad optimal range; absolute_max in
    the heat-stress regime, not at the cultivar-window edge)."""
    cat = requirements.load_catalogue()
    corn = cat.by_id("corn_grain")
    g = corn.gdd
    assert g.base_temperature_c == 10.0
    assert g.absolute_min == 700      # earliest Quebec MG with margin
    assert g.optimal_min == 1000      # mid-MG Quebec optimum
    assert g.optimal_max == 2700      # spans MG range + cultivar adaptation
    assert g.absolute_max == 3500     # heat-stress regime


def test_unknown_crop_raises():
    cat = requirements.load_catalogue()
    with pytest.raises(KeyError, match="not_a_crop"):
        cat.by_id("not_a_crop")


def test_trapezoid_bounds_validate_ordering(tmp_path: Path):
    """A YAML with absolute_min >= optimal_min must fail at load time."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        """
schema_version: 1
crops:
  - id: broken
    scientific_name: Brokenus brokenii
    common_name_en: Broken
    ecoport_code: 0
    temperature:
      tmean_absolute_min_c: 20.0
      tmean_optimal_min_c: 18.0   # < absolute_min — should fail
      tmean_optimal_max_c: 25.0
      tmean_absolute_max_c: 35.0
    gdd:
      base_temperature_c: 10.0
      absolute_min: 1000
      optimal_min: 1500
      optimal_max: 2000
      absolute_max: 3000
    precipitation:
      annual_absolute_min_mm: 100
      annual_optimal_min_mm: 200
      annual_optimal_max_mm: 800
      annual_absolute_max_mm: 1500
    soil:
      ph_absolute_min: 5.0
      ph_optimal_min: 6.0
      ph_optimal_max: 7.0
      ph_absolute_max: 8.0
    growing_season:
      cycle_min_days: 90
      cycle_max_days: 200
    frost:
      kill_temperature_c: 0.0
    citations: []
"""
    )
    with pytest.raises(ValueError):
        requirements.load_catalogue(bad)


# ---- indicators -------------------------------------------------------------


def _make_synthetic_climate(
    *,
    tasmax_c: float = 25.0,
    tasmin_c: float = 12.0,
    pr_mm_day: float = 3.0,
    days: int = 365,
    nlat: int = 2,
    nlon: int = 3,
) -> xr.Dataset:
    """Build a uniform daily climate Dataset."""
    times = np.arange(
        np.datetime64("2020-01-01"),
        np.datetime64("2020-01-01") + np.timedelta64(days, "D"),
        np.timedelta64(1, "D"),
    )
    lats = np.linspace(45.0, 46.0, nlat)
    lons = np.linspace(-74.0, -73.0, nlon)
    shape = (len(times), nlat, nlon)

    def _full(x):
        return (("time", "lat", "lon"), np.full(shape, x, dtype="float32"))

    ds = xr.Dataset(
        {
            "tasmax": _full(tasmax_c),
            "tasmin": _full(tasmin_c),
            "pr": _full(pr_mm_day),
        },
        coords={"time": times, "lat": lats, "lon": lons},
    )
    ds["tasmax"].attrs["units"] = "degC"
    ds["tasmin"].attrs["units"] = "degC"
    ds["pr"].attrs["units"] = "mm/day"
    return ds


def test_daily_mean_temperature_uniform_field():
    ds = _make_synthetic_climate(tasmax_c=30.0, tasmin_c=10.0)
    tmean = indicators.daily_mean_temperature(ds)
    np.testing.assert_allclose(tmean.values, 20.0)


def test_kelvin_input_is_converted_to_celsius():
    ds = _make_synthetic_climate()
    # Re-stamp as Kelvin and shift values up by 273.15.
    ds["tasmin"] = ds["tasmin"] + 273.15
    ds["tasmax"] = ds["tasmax"] + 273.15
    ds["tasmin"].attrs["units"] = "K"
    ds["tasmax"].attrs["units"] = "K"
    tmean = indicators.daily_mean_temperature(ds)
    # Mean of (25, 12) = 18.5 °C.
    np.testing.assert_allclose(tmean.values, (25.0 + 12.0) / 2)


def test_gdd_base_10_one_year():
    """Uniform Tmean = 18.5 °C every day for a non-leap year (365 days)."""
    ds = _make_synthetic_climate(tasmax_c=25.0, tasmin_c=12.0, days=365)
    gdd = indicators.growing_degree_days(ds, base_temperature_c=10.0)
    # Daily excess = 18.5 − 10 = 8.5; annual = 8.5 × 365 = 3102.5.
    np.testing.assert_allclose(float(gdd.values.mean()), 8.5 * 365)


def test_growing_season_days_all_frost_free():
    """tasmin always 12 °C; growing season = 365 days."""
    ds = _make_synthetic_climate(tasmin_c=12.0, days=365)
    gs = indicators.growing_season_days(ds)
    np.testing.assert_allclose(float(gs.values.mean()), 365)


def test_growing_season_days_excludes_subzero():
    """Set tasmin = −5 °C for first 60 days; the rest frost-free."""
    ds = _make_synthetic_climate(tasmin_c=12.0, days=365)
    ds["tasmin"].values[:60] = -5.0
    gs = indicators.growing_season_days(ds)
    np.testing.assert_allclose(float(gs.values.mean()), 365 - 60)


def test_annual_precipitation_mm_per_day_input():
    ds = _make_synthetic_climate(pr_mm_day=2.0, days=365)
    p = indicators.annual_precipitation_mm(ds)
    np.testing.assert_allclose(float(p.values.mean()), 730.0)


def test_annual_precipitation_kg_m2_s_input_is_converted():
    """A pr in CMIP6 SI units (kg/m²/s) should auto-scale to mm/day."""
    ds = _make_synthetic_climate(pr_mm_day=2.0 / 86400.0, days=365)
    ds["pr"].attrs["units"] = "kg m-2 s-1"
    p = indicators.annual_precipitation_mm(ds)
    np.testing.assert_allclose(float(p.values.mean()), 730.0)


def test_compute_all_returns_expected_variables():
    ds = _make_synthetic_climate()
    out = indicators.compute_all(ds, gdd_base_temperature_c=10.0)
    assert set(out.data_vars) == {
        "tmean_growing_c", "gdd", "annual_precip_mm", "growing_season_days",
    }


# ---- envelope ---------------------------------------------------------------


def test_trapezoid_at_known_points():
    bounds = requirements.TrapezoidBounds(
        absolute_min=0.0, optimal_min=10.0,
        optimal_max=20.0, absolute_max=30.0,
    )
    x = xr.DataArray(np.array([-1.0, 0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 31.0]))
    score = envelope.trapezoid(x, bounds)
    expected = [0.0, 0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0, 0.0]
    np.testing.assert_allclose(score.values, expected)


def test_score_crop_perfect_conditions_for_corn():
    """Hand-pick indicators in the optimal window for corn → score == 1."""
    cat = requirements.load_catalogue()
    corn = cat.by_id("corn_grain")
    ind = xr.Dataset(
        {
            "tmean_growing_c": xr.DataArray([[22.0]], dims=("y", "x")),
            "gdd": xr.DataArray([[1200.0]], dims=("y", "x")),
            "annual_precip_mm": xr.DataArray([[800.0]], dims=("y", "x")),
            "growing_season_days": xr.DataArray([[200.0]], dims=("y", "x")),
        }
    )
    res = envelope.score_crop(ind, corn)
    assert float(res.score.values[0, 0]) == pytest.approx(1.0)


def test_score_crop_outside_temperature_window_zero():
    """Push tmean above absolute_max → score is 0; limiting factor is temperature."""
    cat = requirements.load_catalogue()
    corn = cat.by_id("corn_grain")
    ind = xr.Dataset(
        {
            "tmean_growing_c": xr.DataArray([[60.0]], dims=("y", "x")),  # too hot
            "gdd": xr.DataArray([[2200.0]], dims=("y", "x")),
            "annual_precip_mm": xr.DataArray([[800.0]], dims=("y", "x")),
            "growing_season_days": xr.DataArray([[200.0]], dims=("y", "x")),
        }
    )
    res = envelope.score_crop(ind, corn)
    assert float(res.score.values[0, 0]) == 0.0
    assert str(res.limiting_factor.values[0, 0]) == "temperature"


def test_score_crop_includes_soil_ph_when_provided():
    cat = requirements.load_catalogue()
    corn = cat.by_id("corn_grain")
    ind = xr.Dataset(
        {
            "tmean_growing_c": xr.DataArray([[22.0]], dims=("y", "x")),
            "gdd": xr.DataArray([[1200.0]], dims=("y", "x")),
            "annual_precip_mm": xr.DataArray([[800.0]], dims=("y", "x")),
            "growing_season_days": xr.DataArray([[200.0]], dims=("y", "x")),
        }
    )
    bad_ph = xr.DataArray([[3.0]], dims=("y", "x"))  # way below corn's absolute_min 4.5
    res = envelope.score_crop(ind, corn, soil_ph=bad_ph)
    assert float(res.score.values[0, 0]) == 0.0
    assert str(res.limiting_factor.values[0, 0]) == "soil_ph"


def test_classify_gaez_breakpoints():
    score = xr.DataArray([0.0, 0.10, 0.40, 0.70, 0.90, np.nan])
    cls = envelope.classify_gaez(score)
    assert list(cls.values[:-1]) == ["N", "S4", "S3", "S2", "S1"]
    # NaN cells get empty string.
    assert cls.values[-1] == ""


def test_rank_crops_returns_all():
    cat = requirements.load_catalogue()
    ind = xr.Dataset(
        {
            "tmean_growing_c": xr.DataArray([[22.0]], dims=("y", "x")),
            "gdd": xr.DataArray([[1200.0]], dims=("y", "x")),
            "annual_precip_mm": xr.DataArray([[800.0]], dims=("y", "x")),
            "growing_season_days": xr.DataArray([[200.0]], dims=("y", "x")),
        }
    )
    results = envelope.rank_crops(ind, cat.crops)
    assert set(results) == {"corn_grain", "soybean", "spring_wheat", "canola"}
    # Each result is a CropSuitability with a single score scalar.
    for r in results.values():
        assert r.score.shape == (1, 1)
