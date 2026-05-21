"""Thin xarray-friendly wrapper around PCSE / WOFOST 7.2.

Per ADR 0003, PCSE/WOFOST is AIgriculture's primary Tier 2 process
model. This module composes the four PCSE inputs (weather, crop, soil,
site) plus an agromanagement spec into a single function call returning
a flat result dict.

For the Tier 2 MVP we drive **potential production** (``Wofost72_PP``)
— no water or nutrient stress. That isolates the climate × cultivar
signal from soil-water uncertainty (a Phase-2 separate calibration
step). When we move to water-limited mode we'll add a soil-translator
that maps SoilGrids properties to PCSE soil parameters via a
pedotransfer function.

Example
-------
    >>> from aigriculture.crop_models import wofost_runner
    >>> result = wofost_runner.run_wofost_pp(
    ...     weather_ds=daily_climate_ds,
    ...     crop_name="maize",
    ...     variety_name="Grain_maize_201",
    ...     campaign_start=dt.date(2018, 4, 1),
    ...     emergence=dt.date(2018, 5, 15),
    ...     harvest=dt.date(2018, 10, 15),
    ... )
    >>> result["yield_t_ha"]    # grain dry matter at 14% moisture
    9.84
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Mapping

import xarray as xr

from .weather import XarrayWeatherDataProvider

DRY_MATTER_TO_GRAIN_FACTOR = 1.16  # ÷1000 then × this → t/ha grain @14% moisture
# (1 / (1 - 0.14) ≈ 1.163; the 14% moisture standard is the FAO grain-market reference.)

# Atmospheric CO₂ concentration (ppm) — must be set for Wofost72 assimilation
# to produce non-zero biomass. The CO2AMAXTB lookup is *zero* at the
# PCSE-default sentinel (-99 ppm), which is the silent footgun that
# leaves the canopy frozen at the initial LAIEM. We set 415 ppm as the
# default — global atmospheric CO₂ averaged 414.7 ppm for 2021 (NOAA
# Mauna Loa). Override per simulation year if you care.
DEFAULT_CO2_PPM: float = 415.0


def _yield_t_ha(twso_kg_ha_dm: float) -> float:
    """Convert TWSO (Total Weight Storage Organs, kg/ha dry matter) to
    grain yield in t/ha at the FAO 14 % moisture standard."""
    return twso_kg_ha_dm * DRY_MATTER_TO_GRAIN_FACTOR / 1000.0


@dataclass(slots=True, frozen=True)
class WofostRunResult:
    """Compact summary of one Wofost72_PP run.

    Attributes
    ----------
    yield_t_ha
        Grain yield at 14 % moisture (t/ha). Comparable directly to
        StatCan FCRS / USDA NASS reported yields.
    twso_kg_ha_dm
        Total weight of storage organs (PCSE's raw ``TWSO``) — grain dry
        matter, kg/ha.
    tagp_kg_ha
        Total above-ground production (grain + leaves + stems) kg/ha
        dry matter.
    lai_max
        Maximum leaf-area-index reached during the season.
    doe, doa, dom
        Dates of emergence / anthesis / physiological maturity. ``None``
        when the simulation did not reach that phase before terminating.
    weather_approximations
        Notes about any synthesized weather fields (e.g. VAP estimated
        from TMIN). Empty when all inputs were real.
    raw_summary
        The complete PCSE summary dict for downstream introspection.
    """

    yield_t_ha: float
    twso_kg_ha_dm: float
    tagp_kg_ha: float
    lai_max: float
    doe: dt.date | None
    doa: dt.date | None
    dom: dt.date | None
    weather_approximations: tuple[str, ...]
    raw_summary: dict


def run_wofost_pp(
    weather_ds: xr.Dataset,
    *,
    crop_name: str,
    variety_name: str,
    campaign_start: dt.date,
    emergence: dt.date,
    harvest: dt.date,
    latitude: float | None = None,
    longitude: float | None = None,
    elevation: float = 100.0,
    site_wav: float = 10.0,
    co2_ppm: float = DEFAULT_CO2_PPM,
    max_duration_days: int = 200,
    pcse_model: Any = None,
    weather_provider: WeatherDataProvider | None = None,  # type: ignore[name-defined]
) -> WofostRunResult:
    """Run Wofost72_PP for one site-year and return a summary.

    Parameters
    ----------
    weather_ds
        Daily climate Dataset with ``tasmin``, ``tasmax``, ``pr``,
        ``rsds`` (and optional ``vap`` / ``wind``). Use
        :class:`XarrayWeatherDataProvider` directly via ``weather_provider``
        if you want full control.
    crop_name, variety_name
        Selectors for ``pcse.input.YAMLCropDataProvider``. Available
        crops are listed in
        :file:`docs/research/02-crop-knowledge-base.md` §B.1 and in
        the ``reference_pcse_quirks`` memory note.
    campaign_start, emergence, harvest
        Agromanagement dates. ``campaign_start`` is when PCSE begins
        the integration; ``emergence`` is when the crop is initialized;
        ``harvest`` is the latest allowed termination date.
    latitude / longitude / elevation
        Site metadata for ETref calculations. If omitted, ``latitude``
        / ``longitude`` come from the Dataset's mean coordinates.
    site_wav
        Initial available soil water (mm). 10 mm is the
        ``WOFOST72SiteDataProvider`` default and is a safe choice for
        potential-production runs (where it isn't used).
    pcse_model
        Optional PCSE model class override (defaults to
        ``pcse.models.Wofost72_PP``). Tests inject a dummy model.
    weather_provider
        Optional pre-built ``WeatherDataProvider`` to use instead of
        constructing one from ``weather_ds``.
    """
    # Lazy imports — pcse is heavy and we want this module importable
    # without pulling it in for unrelated tests.
    from pcse.base import ParameterProvider  # noqa: PLC0415
    from pcse.input import (  # noqa: PLC0415
        DummySoilDataProvider,
        WOFOST72SiteDataProvider,
        YAMLCropDataProvider,
    )

    if pcse_model is None:
        from pcse.models import Wofost72_PP  # noqa: PLC0415

        pcse_model = Wofost72_PP

    cropd = YAMLCropDataProvider()
    cropd.set_active_crop(crop_name, variety_name)
    soild = DummySoilDataProvider()
    sited = WOFOST72SiteDataProvider(WAV=site_wav)
    paramprov = ParameterProvider(cropdata=cropd, soildata=soild, sitedata=sited)
    # CO₂ is read by the assimilation module from the merged parameter
    # provider. WOFOST72SiteDataProvider does not expose it, and the
    # cropdata YAMLs leave it as the sentinel -99, which the CO2AMAXTB
    # lookup interprets as "zero atmosphere" and zeroes out assimilation.
    # We inject it through PCSE's override mechanism.
    paramprov.set_override("CO2", co2_ppm, check=False)

    if weather_provider is None:
        weather_provider = XarrayWeatherDataProvider(
            weather_ds,
            latitude=latitude,
            longitude=longitude,
            elevation=elevation,
        )

    agro = build_agromanagement(
        campaign_start=campaign_start,
        crop_name=crop_name,
        variety_name=variety_name,
        emergence=emergence,
        harvest=harvest,
        max_duration_days=max_duration_days,
    )

    sim = pcse_model(paramprov, weather_provider, agro)
    sim.run_till_terminate()
    summary_list = sim.get_summary_output()
    if not summary_list:
        raise RuntimeError(
            f"PCSE returned an empty summary for "
            f"{crop_name}/{variety_name} {campaign_start}–{harvest}"
        )
    summary = summary_list[0]

    twso = float(summary.get("TWSO") or 0.0)
    notes = getattr(weather_provider, "approximations", None)
    notes_tuple: tuple[str, ...] = tuple(notes.notes) if notes is not None else ()

    return WofostRunResult(
        yield_t_ha=_yield_t_ha(twso),
        twso_kg_ha_dm=twso,
        tagp_kg_ha=float(summary.get("TAGP") or 0.0),
        lai_max=float(summary.get("LAIMAX") or 0.0),
        doe=summary.get("DOE"),
        doa=summary.get("DOA"),
        dom=summary.get("DOM"),
        weather_approximations=notes_tuple,
        raw_summary=dict(summary),
    )


def build_agromanagement(
    *,
    campaign_start: dt.date,
    crop_name: str,
    variety_name: str,
    emergence: dt.date,
    harvest: dt.date,
    max_duration_days: int = 200,
) -> list[dict]:
    """Build PCSE's nested agromanagement-dict for one campaign.

    PCSE accepts a list of ``{date: {CropCalendar: ..., TimedEvents:
    ..., StateEvents: ...}}`` dicts. For a single-campaign run we
    return a list with one entry.
    """
    return [
        {
            campaign_start: {
                "CropCalendar": {
                    "crop_name": crop_name,
                    "variety_name": variety_name,
                    "crop_start_date": emergence,
                    "crop_start_type": "emergence",
                    "crop_end_date": harvest,
                    "crop_end_type": "maturity",
                    "max_duration": max_duration_days,
                },
                "TimedEvents": None,
                "StateEvents": None,
            }
        }
    ]


__all__ = [
    "WofostRunResult",
    "build_agromanagement",
    "run_wofost_pp",
]
