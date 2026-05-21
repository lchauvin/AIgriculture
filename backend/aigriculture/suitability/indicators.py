"""Climate indicators used by Tier 1 envelope screening.

Given a daily climate Dataset with ``tasmax`` (°C), ``tasmin`` (°C), and
``pr`` (mm/day), this module computes the per-cell aggregated indicators
Tier 1 scores against:

- ``tmean_growing_c``     — mean of (tasmin+tasmax)/2 across the
                            frost-free growing season (°C).
- ``gdd``                 — growing-degree days at a configurable
                            ``base_temperature_c`` over the growing
                            season (°C·days).
- ``annual_precip_mm``    — annual total precipitation (mm).
- ``growing_season_days`` — frost-free days per year (count).

For the AgERA5 + CanDCS-M6 path these are all available. AgERA5 ships
temperatures in Kelvin; CanDCS-M6 in °C. The functions below normalize
to °C if the ``units`` attribute is ``"K"``.

We compute everything via xarray ops so the result inherits the
chunking / lazy-evaluation of the input Dataset.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import xarray as xr

CELSIUS_PER_KELVIN_OFFSET: Final = 273.15


def _to_celsius(da: xr.DataArray) -> xr.DataArray:
    """Return ``da`` in °C, using the ``units`` attribute as the cue.

    Recognized inputs: ``K``, ``Kelvin``, ``°C`` / ``C`` / ``degC`` / ``celsius``.
    Anything else passes through unchanged with a metadata note.
    """
    units = (da.attrs.get("units") or "").strip().lower()
    if units in {"k", "kelvin"}:
        out = da - CELSIUS_PER_KELVIN_OFFSET
        out.attrs.update(da.attrs)
        out.attrs["units"] = "degC"
        out.attrs["units_converted_from"] = "K"
        return out
    return da


def daily_mean_temperature(ds: xr.Dataset) -> xr.DataArray:
    """Daily mean = (tasmin + tasmax) / 2 in °C."""
    tmax = _to_celsius(ds["tasmax"])
    tmin = _to_celsius(ds["tasmin"])
    tmean = (tmax + tmin) / 2.0
    tmean.attrs["units"] = "degC"
    tmean.name = "tmean"
    return tmean


def growing_degree_days(
    ds: xr.Dataset,
    *,
    base_temperature_c: float,
    only_frost_free: bool = True,
) -> xr.DataArray:
    """Sum of (Tmean − base, clipped at 0) over the year.

    Parameters
    ----------
    ds
        Dataset with ``tasmax`` and ``tasmin`` (any temperature units).
    base_temperature_c
        Crop-specific GDD base temperature.
    only_frost_free
        If True (default), days with ``tasmin < 0 °C`` are excluded from
        the sum — matches the standard agronomic interpretation that
        sub-zero nights interrupt active growth.

    Returns
    -------
    xr.DataArray (no ``time`` dimension) — annual-total °C·days if the
    input spans exactly one year; otherwise an average across the years
    in the input.
    """
    tmean = daily_mean_temperature(ds)
    excess = (tmean - base_temperature_c).clip(min=0.0)
    if only_frost_free:
        tmin_c = _to_celsius(ds["tasmin"])
        excess = excess.where(tmin_c >= 0.0, 0.0)
    annual = _resample_year_sum(excess)
    return annual.mean(dim="year") if "year" in annual.dims else annual


def growing_season_days(ds: xr.Dataset) -> xr.DataArray:
    """Frost-free days per year — count of days where ``tasmin >= 0 °C``."""
    tmin = _to_celsius(ds["tasmin"])
    frost_free = (tmin >= 0.0).astype("float32")
    annual = _resample_year_sum(frost_free)
    return annual.mean(dim="year") if "year" in annual.dims else annual


def mean_growing_season_temperature(ds: xr.Dataset) -> xr.DataArray:
    """Mean of daily Tmean across frost-free days, in °C.

    For cells with no frost-free days the result is ``NaN``.
    """
    tmean = daily_mean_temperature(ds)
    tmin = _to_celsius(ds["tasmin"])
    growing_mask = tmin >= 0.0
    tmean_in = tmean.where(growing_mask)
    annual = _resample_year_mean(tmean_in)
    out = annual.mean(dim="year") if "year" in annual.dims else annual
    out.attrs["units"] = "degC"
    return out


def annual_precipitation_mm(ds: xr.Dataset) -> xr.DataArray:
    """Annual-total precipitation (mm).

    Accepts ``pr`` in mm/day (CanDCS-M6 convention) or in kg/m²/s
    (CMIP6 standard); auto-converts the latter via the ``units`` attr.
    """
    pr = ds["pr"]
    units = (pr.attrs.get("units") or "").strip().lower()
    if units in {"kg m-2 s-1", "kg/m2/s", "kg m^-2 s^-1"}:
        pr_per_day = pr * 86400.0
    else:
        pr_per_day = pr  # assume mm/day / kg m-2 d-1
    annual = _resample_year_sum(pr_per_day)
    out = annual.mean(dim="year") if "year" in annual.dims else annual
    out.attrs["units"] = "mm"
    return out


def compute_all(
    ds: xr.Dataset,
    *,
    gdd_base_temperature_c: float,
) -> xr.Dataset:
    """Convenience: compute every indicator at once.

    Parameters
    ----------
    ds
        Daily climate Dataset.
    gdd_base_temperature_c
        Base T for the GDD calculation (varies per crop).
    """
    return xr.Dataset(
        {
            "tmean_growing_c": mean_growing_season_temperature(ds),
            "gdd": growing_degree_days(
                ds, base_temperature_c=gdd_base_temperature_c
            ),
            "annual_precip_mm": annual_precipitation_mm(ds),
            "growing_season_days": growing_season_days(ds),
        }
    )


# ---- internals --------------------------------------------------------------


def _resample_year_sum(da: xr.DataArray) -> xr.DataArray:
    """Annual total, indexed by ``year`` if the input spans >1 year."""
    yrs = np.unique(da["time"].dt.year.values)
    if len(yrs) == 1:
        return da.sum(dim="time", skipna=True)
    return da.groupby("time.year").sum(dim="time", skipna=True)


def _resample_year_mean(da: xr.DataArray) -> xr.DataArray:
    yrs = np.unique(da["time"].dt.year.values)
    if len(yrs) == 1:
        return da.mean(dim="time", skipna=True)
    return da.groupby("time.year").mean(dim="time", skipna=True)


__all__ = [
    "annual_precipitation_mm",
    "compute_all",
    "daily_mean_temperature",
    "growing_degree_days",
    "growing_season_days",
    "mean_growing_season_temperature",
]
