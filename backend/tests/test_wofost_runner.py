"""Tests for the Tier 2 PCSE/WOFOST wrapper.

Unit tests exercise the wrapper's logic (unit conversion, agromanagement
construction, yield conversion) against synthetic inputs without touching
PCSE's simulator. One integration-style test injects a fake PCSE model
class so we can verify the wrapper composes inputs and unpacks outputs
correctly, while still keeping the test fast and deterministic.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pytest
import xarray as xr

from aigriculture.crop_models import weather as weather_mod
from aigriculture.crop_models import wofost_runner
from aigriculture.crop_models.weather import (
    FAO_PM_WIND_DEFAULT_M_S,
    XarrayWeatherDataProvider,
    _magnus_saturation_vapor_kpa,
)


# ---- helpers ---------------------------------------------------------------


def _synthetic_daily_climate(
    *,
    n_days: int = 30,
    tasmin_c: float = 10.0,
    tasmax_c: float = 25.0,
    pr_mm_day: float = 3.0,
    rsds_j_m2_day: float = 18_000_000.0,  # ≈ 18 MJ/m²/d, summer mid-latitude
    lat: float = 45.5,
    lon: float = -73.5,
    start: str = "2018-05-01",
) -> xr.Dataset:
    times = np.arange(
        np.datetime64(start),
        np.datetime64(start) + np.timedelta64(n_days, "D"),
        np.timedelta64(1, "D"),
    )

    def _field(value: float):
        return ("time",), np.full(n_days, value, dtype="float32")

    ds = xr.Dataset(
        {
            "tasmin": _field(tasmin_c),
            "tasmax": _field(tasmax_c),
            "pr": _field(pr_mm_day),
            "rsds": _field(rsds_j_m2_day),
        },
        coords={"time": times, "lat": lat, "lon": lon},
    )
    ds["tasmin"].attrs["units"] = "degC"
    ds["tasmax"].attrs["units"] = "degC"
    ds["pr"].attrs["units"] = "mm/day"
    ds["rsds"].attrs["units"] = "J m-2 d-1"
    return ds


# ---- weather translator ----------------------------------------------------


def test_magnus_at_known_temperatures():
    """Magnus equation: 0 °C → 0.611 kPa; 20 °C → 2.34 kPa."""
    assert _magnus_saturation_vapor_kpa(0.0) == pytest.approx(0.6108, rel=1e-3)
    assert _magnus_saturation_vapor_kpa(20.0) == pytest.approx(2.339, rel=1e-2)
    # Strictly increasing with T.
    assert (
        _magnus_saturation_vapor_kpa(-10.0)
        < _magnus_saturation_vapor_kpa(0.0)
        < _magnus_saturation_vapor_kpa(20.0)
        < _magnus_saturation_vapor_kpa(35.0)
    )


def test_weather_provider_populates_store():
    ds = _synthetic_daily_climate(n_days=10)
    wp = XarrayWeatherDataProvider(ds)
    assert wp.first_date == dt.date(2018, 5, 1)
    assert wp.last_date == dt.date(2018, 5, 10)
    assert wp.latitude == pytest.approx(45.5)
    assert wp.longitude == pytest.approx(-73.5)


def test_weather_provider_unit_conversion():
    """Verify each input unit is normalized to PCSE's expected units in
    the populated WeatherDataContainer (IRRAD: J/m²/d; VAP: hPa;
    RAIN/E0/ES0/ET0: cm/day; TEMP: derived as (TMIN+TMAX)/2)."""
    ds = _synthetic_daily_climate(n_days=5)
    # Re-encode in non-default units to exercise every converter.
    ds["tasmin"] = ds["tasmin"] + 273.15
    ds["tasmin"].attrs["units"] = "K"
    ds["tasmax"] = ds["tasmax"] + 273.15
    ds["tasmax"].attrs["units"] = "K"
    ds["pr"] = ds["pr"] / 86400.0
    ds["pr"].attrs["units"] = "kg m-2 s-1"
    ds["rsds"] = ds["rsds"] / 1.0e6
    ds["rsds"].attrs["units"] = "MJ m-2 day-1"

    wp = XarrayWeatherDataProvider(ds)
    rec = wp(dt.date(2018, 5, 1))
    assert rec.TMIN == pytest.approx(10.0)
    assert rec.TMAX == pytest.approx(25.0)
    # 3 mm/day → 0.3 cm/day
    assert rec.RAIN == pytest.approx(0.3)
    # 18 MJ/m²/d → 18e6 J/m²/d
    assert rec.IRRAD == pytest.approx(18_000_000.0, rel=1e-3)
    # Mean temperature must be present (PCSE's optional but
    # leaf-dynamics-required ``TEMP``).
    assert rec.TEMP == pytest.approx((10.0 + 25.0) / 2)


def test_weather_provider_synthesizes_vap_and_wind_when_missing():
    ds = _synthetic_daily_climate(n_days=5, tasmin_c=12.0)
    wp = XarrayWeatherDataProvider(ds)
    rec = wp(dt.date(2018, 5, 1))
    # PCSE WeatherDataContainer stores VAP in hPa; our Magnus output is
    # in kPa, so the stored value is 10× the kPa estimate.
    expected_vap_hpa = _magnus_saturation_vapor_kpa(12.0) * 10.0
    assert rec.VAP == pytest.approx(expected_vap_hpa, rel=1e-6)
    assert rec.WIND == pytest.approx(FAO_PM_WIND_DEFAULT_M_S)
    assert wp.approximations.vap is True
    assert wp.approximations.wind is True
    assert len(wp.approximations.notes) == 2


def test_weather_provider_uses_real_vap_and_wind_when_present():
    ds = _synthetic_daily_climate(n_days=5)
    # vap stored on the input ds is in kPa; the provider converts to hPa
    # for the WeatherDataContainer.
    ds["vap"] = (("time",), np.full(5, 1.5, dtype="float32"))
    ds["wind"] = (("time",), np.full(5, 4.0, dtype="float32"))
    wp = XarrayWeatherDataProvider(ds)
    rec = wp(dt.date(2018, 5, 1))
    assert rec.VAP == pytest.approx(15.0)  # 1.5 kPa × 10 = 15 hPa
    assert rec.WIND == pytest.approx(4.0)
    assert wp.approximations.vap is False
    assert wp.approximations.wind is False


def test_weather_provider_reduces_lat_lon_dims():
    """A multi-cell Dataset gets reduced to a single point via cell-mean."""
    times = np.arange(
        np.datetime64("2018-05-01"),
        np.datetime64("2018-05-06"),
        np.timedelta64(1, "D"),
    )
    lats = np.array([45.0, 45.5, 46.0])
    lons = np.array([-74.0, -73.5, -73.0])
    shape = (len(times), len(lats), len(lons))
    ds = xr.Dataset(
        {
            "tasmin": (("time", "lat", "lon"), np.full(shape, 10.0, dtype="float32")),
            "tasmax": (("time", "lat", "lon"), np.full(shape, 25.0, dtype="float32")),
            "pr": (("time", "lat", "lon"), np.full(shape, 3.0, dtype="float32")),
            "rsds": (("time", "lat", "lon"), np.full(shape, 1.8e7, dtype="float32")),
        },
        coords={"time": times, "lat": lats, "lon": lons},
    )
    for v in ("tasmin", "tasmax"):
        ds[v].attrs["units"] = "degC"
    ds["pr"].attrs["units"] = "mm/day"
    ds["rsds"].attrs["units"] = "J m-2 d-1"

    wp = XarrayWeatherDataProvider(ds)
    # Mean latitude / longitude across the grid.
    assert wp.latitude == pytest.approx(45.5)
    assert wp.longitude == pytest.approx(-73.5)


# ---- agromanagement --------------------------------------------------------


def test_build_agromanagement_structure():
    agro = wofost_runner.build_agromanagement(
        campaign_start=dt.date(2018, 4, 1),
        crop_name="maize",
        variety_name="Grain_maize_201",
        emergence=dt.date(2018, 5, 15),
        harvest=dt.date(2018, 10, 15),
        max_duration_days=180,
    )
    assert isinstance(agro, list) and len(agro) == 1
    assert dt.date(2018, 4, 1) in agro[0]
    cal = agro[0][dt.date(2018, 4, 1)]["CropCalendar"]
    assert cal["crop_name"] == "maize"
    assert cal["variety_name"] == "Grain_maize_201"
    assert cal["crop_start_date"] == dt.date(2018, 5, 15)
    assert cal["crop_start_type"] == "emergence"
    assert cal["crop_end_date"] == dt.date(2018, 10, 15)
    assert cal["crop_end_type"] == "maturity"
    assert cal["max_duration"] == 180
    assert agro[0][dt.date(2018, 4, 1)]["TimedEvents"] is None
    assert agro[0][dt.date(2018, 4, 1)]["StateEvents"] is None


# ---- yield conversion ------------------------------------------------------


def test_yield_t_ha_conversion():
    # WOFOST TWSO is in kg/ha grain dry matter; the FAO 14 % moisture
    # standard adjusts upward by 1/(1-0.14) ≈ 1.163. So 8000 kg/ha DM
    # → ≈ 9.30 t/ha at 14 % moisture.
    assert wofost_runner._yield_t_ha(0.0) == 0.0
    assert wofost_runner._yield_t_ha(8000.0) == pytest.approx(
        8000.0 * wofost_runner.DRY_MATTER_TO_GRAIN_FACTOR / 1000.0
    )
    # Quick sanity: 10 t/ha DM should round to about 11.6 t/ha at 14 % moisture.
    assert wofost_runner._yield_t_ha(10_000.0) == pytest.approx(11.6, rel=1e-2)


# ---- end-to-end (mocked PCSE) ---------------------------------------------


class _FakeSummary(dict):
    """Stand-in for PCSE's summary dict."""


class _FakeWofost:
    last_init: dict | None = None

    def __init__(self, paramprov, weather, agro):
        type(self).last_init = {"paramprov": paramprov, "weather": weather, "agro": agro}

    def run_till_terminate(self):  # noqa: D401
        """Stub — would run integration; tests verify state after."""

    def get_summary_output(self):
        return [
            _FakeSummary(
                TWSO=8500.0,
                TAGP=19_000.0,
                LAIMAX=5.5,
                DOE=dt.date(2018, 5, 15),
                DOA=dt.date(2018, 7, 25),
                DOM=dt.date(2018, 9, 20),
            )
        ]


def test_run_wofost_pp_composes_inputs_and_returns_summary():
    ds = _synthetic_daily_climate(n_days=180, start="2018-04-01")
    result = wofost_runner.run_wofost_pp(
        weather_ds=ds,
        crop_name="maize",
        variety_name="Grain_maize_201",
        campaign_start=dt.date(2018, 4, 1),
        emergence=dt.date(2018, 5, 15),
        harvest=dt.date(2018, 10, 15),
        pcse_model=_FakeWofost,
    )
    assert result.twso_kg_ha_dm == 8500.0
    assert result.yield_t_ha == pytest.approx(
        8500.0 * wofost_runner.DRY_MATTER_TO_GRAIN_FACTOR / 1000.0
    )
    assert result.lai_max == 5.5
    assert result.doe == dt.date(2018, 5, 15)
    assert result.doa == dt.date(2018, 7, 25)
    assert result.dom == dt.date(2018, 9, 20)
    # VAP and WIND were synthesized — should be flagged.
    assert any("VAP" in note for note in result.weather_approximations)
    assert any("WIND" in note for note in result.weather_approximations)
    # And the FakeWofost should have been wired to a real ParameterProvider /
    # WeatherDataProvider / agromanagement.
    init = _FakeWofost.last_init
    assert init is not None
    assert init["agro"][0][dt.date(2018, 4, 1)]["CropCalendar"]["variety_name"] == "Grain_maize_201"
    assert init["weather"].first_date == dt.date(2018, 4, 1)
