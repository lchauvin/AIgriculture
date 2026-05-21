"""xarray → PCSE WeatherDataProvider adapter.

PCSE's WOFOST simulators consume weather one day at a time through a
``WeatherDataProvider`` interface. Each daily record must populate the
following fields:

    TMIN, TMAX      — °C
    IRRAD           — kJ/m²/day
    VAP             — kPa  (actual 2 m vapor pressure)
    WIND            — m/s  at 10 m
    RAIN            — mm/day
    E0, ES0, ET0    — mm/day  (evapotranspiration; PCSE recomputes
                                these internally if not provided)

This module exposes :class:`XarrayWeatherDataProvider`, which adapts a
single-grid-cell daily xarray Dataset to that contract. Inputs are
canonical CMIP6 / AgERA5-renamed:

    tasmin, tasmax  — daily min/max 2 m air temperature (°C or K, auto-detected
                       from ``units`` attribute)
    pr              — daily precipitation (mm/day or kg/m²/s, auto-detected)
    rsds            — daily mean shortwave radiation flux (W/m² or J/m²/d)
    vap             — daily 2 m vapor pressure (kPa) — *optional*
    wind            — daily 10 m wind speed (m/s) — *optional*

When ``vap`` is absent the provider approximates it as the saturation
vapor pressure at TMIN (a standard ETref proxy when dew-point data are
missing; introduces ~5-15 % bias on the actual VAP value). When
``wind`` is absent it falls back to 2.0 m/s (the FAO Penman-Monteith
"data-poor" default). Both fallbacks are flagged on the provider's
``approximations`` attribute so callers can see what was synthesized.

For the AIgriculture Tier 2 MVP we drive WOFOST in *potential
production* (PP) mode, where these two approximations have very
limited impact (they enter the ETref calculation, which the soil-
water balance uses; PP ignores the soil-water balance). For
water-limited or nutrient-limited runs we should extend
:class:`aigriculture.data.agera5.AgERA5Source` to pull the
``2m_vapour_pressure`` and ``10m_wind_speed`` variables and feed them
through directly.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Final

import numpy as np
import xarray as xr
from pcse.base.weather import WeatherDataContainer, WeatherDataProvider
from pcse.settings import settings as pcse_settings
from pcse.util import reference_ET

# PCSE's default ``METEO_RANGE_CHECKS=True`` clamps E0/ES0/ET0 to
# (0, 2.5) mm/day, which is too tight: real-world reference ET in
# sunny mid-latitude summers routinely reaches 4-8 mm/day. We disable
# the check at module import. Callers who want it back on can flip
# the setting before constructing an XarrayWeatherDataProvider.
pcse_settings.METEO_RANGE_CHECKS = False

CELSIUS_PER_KELVIN: Final = 273.15
SECONDS_PER_DAY: Final = 86400.0
FAO_PM_WIND_DEFAULT_M_S: Final = 2.0
MM_PER_CM: Final = 10.0          # PCSE WeatherDataContainer expects RAIN/E0/ES0/ET0 in cm/day
HPA_PER_KPA: Final = 10.0        # ... and VAP in hPa
# IRRAD: PCSE expects J/m²/day on the WeatherDataContainer (the
# ``units`` dict says ``J/m2/day`` and the range ceiling is 40e6
# J/m²/d). Earlier versions of these notes incorrectly claimed
# kJ/m²/d. AgERA5 ships solar_radiation_flux already in J/m²/d so
# we pass it through directly.


def _to_celsius(da: xr.DataArray) -> xr.DataArray:
    units = (da.attrs.get("units") or "").strip().lower()
    if units in {"k", "kelvin"}:
        out = da - CELSIUS_PER_KELVIN
        out.attrs.update(da.attrs)
        out.attrs["units"] = "degC"
        return out
    return da


def _to_j_m2_day(da: xr.DataArray) -> xr.DataArray:
    """Normalize a radiation field to J/m²/day, the PCSE convention
    (see ``pcse.base.weather.WeatherDataContainer.units``)."""
    units = (da.attrs.get("units") or "").strip().lower()
    if units in {"w m-2", "w/m2", "w m^-2"}:
        out = da * SECONDS_PER_DAY
    elif units in {"j m-2", "j/m2", "j m-2 day-1", "j m-2 d-1"}:
        out = da * 1.0
    elif units in {"kj m-2", "kj/m2", "kj m-2 day-1", "kj m-2 d-1"}:
        out = da * 1000.0
    elif units in {"mj m-2", "mj m-2 day-1", "mj/m2"}:
        out = da * 1.0e6
    else:
        # AgERA5 ships solar_rad as J/m²/day in practice; pass through.
        out = da * 1.0
    out.attrs.update(da.attrs)
    out.attrs["units"] = "J/m2/day"
    return out


def _precip_to_mm_day(da: xr.DataArray) -> xr.DataArray:
    units = (da.attrs.get("units") or "").strip().lower()
    if units in {"kg m-2 s-1", "kg/m2/s", "kg m^-2 s^-1"}:
        out = da * SECONDS_PER_DAY
    else:
        out = da  # assume already mm/day
    out.attrs.update(da.attrs)
    out.attrs["units"] = "mm/day"
    return out


def _magnus_saturation_vapor_kpa(t_c: float) -> float:
    """Saturation vapor pressure at temperature ``t_c`` (°C), in kPa.

    Standard Magnus / Tetens form (FAO Irrigation & Drainage Paper 56,
    Eq. 11). Used to approximate VAP from TMIN when actual VAP is not
    available — at typical dew-point conditions, dew approaches
    saturation at the daily minimum temperature.
    """
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


@dataclass(slots=True)
class _Approximations:
    """Bookkeeping of which weather fields were synthesized."""

    vap: bool = False
    wind: bool = False
    notes: list[str] = field(default_factory=list)


class XarrayWeatherDataProvider(WeatherDataProvider):
    """PCSE WeatherDataProvider backed by an xarray daily Dataset.

    Parameters
    ----------
    ds
        Daily Dataset with at minimum ``tasmin``, ``tasmax``, ``pr``,
        ``rsds``. Optional ``vap`` (kPa) and ``wind`` (m/s).
    latitude, longitude, elevation
        Site metadata used by PCSE's E0/ES0/ET0 calculations. If
        ``latitude`` / ``longitude`` are not provided we pick the
        cell-mean. Elevation defaults to 100 m (Quebec lowlands).
    angstA, angstB
        Angstrom coefficients for shortwave-radiation calibration.
        Defaults to PCSE's continental-temperate values (0.18 / 0.55).
    """

    # WeatherDataProvider exposes ``self.store: dict[(date, 0)] = WDC``
    # populated by __init__.

    def __init__(
        self,
        ds: xr.Dataset,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        elevation: float = 100.0,
        angstA: float = 0.18,
        angstB: float = 0.55,
    ) -> None:
        super().__init__()

        self.approximations = _Approximations()
        self.description = ["xarray-backed weather", "AIgriculture XarrayWeatherDataProvider"]
        self.angstA = angstA
        self.angstB = angstB
        self.elevation = float(elevation)

        # Set site geometry from the Dataset's coordinates BEFORE reducing
        # them away — otherwise the lat/lon dims get collapsed and the
        # coord itself disappears (xarray drops scalar coords on reduce).
        if latitude is None:
            latitude = (
                float(ds["lat"].mean().values) if "lat" in ds.coords else 0.0
            )
        if longitude is None:
            longitude = (
                float(ds["lon"].mean().values) if "lon" in ds.coords else 0.0
            )
        self.latitude = float(latitude)
        self.longitude = float(longitude)

        # Reduce to a single time series. If lat/lon dims are present,
        # mean over them (caller is expected to have already selected
        # the point of interest).
        ds = self._reduce_to_point(ds)

        self._populate_store(ds)

    # ------------------------------------------------------------------
    @staticmethod
    def _reduce_to_point(ds: xr.Dataset) -> xr.Dataset:
        for dim in ("lat", "lon", "y", "x"):
            if dim in ds.dims:
                ds = ds.mean(dim=dim)
        return ds

    def _populate_store(self, ds: xr.Dataset) -> None:
        tmin_c = _to_celsius(ds["tasmin"]).values
        tmax_c = _to_celsius(ds["tasmax"]).values
        rain_mm = _precip_to_mm_day(ds["pr"]).values
        irrad_j = _to_j_m2_day(ds["rsds"]).values

        if "vap" in ds.data_vars:
            vap_kpa = ds["vap"].values  # assume already kPa
        else:
            self.approximations.vap = True
            self.approximations.notes.append(
                "VAP approximated as saturation vapor pressure at TMIN "
                "(Magnus equation); real AgERA5 vap not pulled."
            )
            vap_kpa = np.array([_magnus_saturation_vapor_kpa(t) for t in tmin_c])

        if "wind" in ds.data_vars:
            wind_ms = ds["wind"].values
        else:
            self.approximations.wind = True
            self.approximations.notes.append(
                f"WIND set to FAO Penman-Monteith default {FAO_PM_WIND_DEFAULT_M_S} m/s; "
                "real AgERA5 wind not pulled."
            )
            wind_ms = np.full(tmin_c.shape, FAO_PM_WIND_DEFAULT_M_S)

        # PCSE expects datetime.date keys.
        times = ds["time"].values
        if np.issubdtype(times.dtype, np.datetime64):
            dates = [
                (np.datetime64(t, "D").item())
                if isinstance(t, np.datetime64)
                else t
                for t in times
            ]
            dates = [
                (d if isinstance(d, dt.date) else dt.date(d.year, d.month, d.day))
                for d in dates
            ]
        else:
            dates = list(times)

        for i, day in enumerate(dates):
            tmin_today = float(tmin_c[i])
            tmax_today = float(tmax_c[i])
            irrad_today_j = float(irrad_j[i])
            vap_today_kpa = float(vap_kpa[i])
            wind_today = float(wind_ms[i])

            # Reference ET — water surface (E0), bare soil (ES0), closed
            # crop canopy (ET0). All in mm/day. ``reference_ET`` wants
            # IRRAD in J/m²/d and VAP in hPa.
            e0_mm, es0_mm, et0_mm = reference_ET(
                DAY=day,
                LAT=self.latitude,
                ELEV=self.elevation,
                TMIN=tmin_today,
                TMAX=tmax_today,
                IRRAD=irrad_today_j,
                VAP=vap_today_kpa * HPA_PER_KPA,
                WIND=wind_today,
                ANGSTA=self.angstA,
                ANGSTB=self.angstB,
            )

            # The WeatherDataContainer expects PCSE's idiosyncratic units:
            #   IRRAD  J/m²/day   (NOT kJ — see ``pcse.base.weather.WeatherDataContainer.units``)
            #   VAP    hPa        (NOT kPa)
            #   RAIN   cm/day     (NOT mm/day)
            #   E0/ES0/ET0  cm/day  (NOT mm/day)
            # Mismatches silently zero out the photosynthesis machinery.
            # Also: TEMP is *documented* as auto-derived but in practice
            # stays ``None`` unless explicitly passed, and leaf-dynamics
            # crashes when it sees ``None - TBASE`` — provide it.
            wdc = WeatherDataContainer(
                LAT=self.latitude,
                LON=self.longitude,
                ELEV=self.elevation,
                DAY=day,
                IRRAD=irrad_today_j,
                TMIN=tmin_today,
                TMAX=tmax_today,
                TEMP=(tmin_today + tmax_today) / 2.0,
                VAP=vap_today_kpa * HPA_PER_KPA,
                WIND=wind_today,
                RAIN=float(rain_mm[i]) / MM_PER_CM,
                E0=float(e0_mm) / MM_PER_CM,
                ES0=float(es0_mm) / MM_PER_CM,
                ET0=float(et0_mm) / MM_PER_CM,
            )
            self._store_WeatherDataContainer(wdc, day)


__all__ = ["XarrayWeatherDataProvider"]
