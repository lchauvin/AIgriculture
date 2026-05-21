"""Tier 1 envelope job execution.

A single :func:`run_envelope_job` function that takes a job request,
runs the same data → indicators → envelope pipeline as
``backend/notebooks/exploratory/quebec_tier1_envelope.py``, and writes
the result back to the supplied :class:`JobStore`. The function is
synchronous; it runs inside whatever execution context the caller
provides (FastAPI's `BackgroundTasks`, a thread pool, an `arq` worker
once we deploy).

This is intentionally a thin wrapper. The hard work lives in the
domain modules; the runner exists only so the API can dispatch a job
without growing pipeline knowledge into its routes.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from uuid import UUID

import numpy as np
import xarray as xr

from ..data.agera5 import AgERA5Source
from ..data.candcs_m6 import CanDCSM6Source
from ..data.soilgrids import SoilGridsSource
from ..suitability import envelope as envelope_mod
from ..suitability import indicators as indicators_mod
from ..suitability import requirements as requirements_mod
from .jobs import JobStore
from .schemas import (
    CropEnvelopeScore,
    CropSuitabilityGrid,
    EnvelopeRequest,
    EnvelopeResult,
    FutureScenario,
    GAEZClass,
    HistoricalScenario,
    ProvenanceStamp,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AGERA5_CACHE = REPO_ROOT / "data" / "cache" / "agera5"


def run_envelope_job(
    job_id: UUID,
    store: JobStore,
    *,
    agera5_cache_dir: Path | None = None,
    catalogue_path: Path | None = None,
) -> None:
    """Execute the Tier 1 envelope pipeline and update the job store.

    Errors are caught and surfaced via :meth:`JobStore.mark_failed` so
    a runaway job can't crash the API process. The exception traceback
    is preserved in the error message for debugging.
    """
    store.mark_started(job_id)
    rec = store.get(job_id)
    if rec is None:
        return  # job got purged during dispatch — nothing more to do

    try:
        result = _compute_envelope(
            rec.request,
            agera5_cache_dir=agera5_cache_dir or DEFAULT_AGERA5_CACHE,
            catalogue_path=catalogue_path,
        )
    except Exception as exc:  # noqa: BLE001 — runner is the catch-all boundary
        import traceback

        msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        store.mark_failed(job_id, msg)
        return

    store.mark_succeeded(job_id, result)


def _compute_envelope(
    req: EnvelopeRequest,
    *,
    agera5_cache_dir: Path,
    catalogue_path: Path | None,
) -> EnvelopeResult:
    catalogue = requirements_mod.load_catalogue(catalogue_path)

    requested_ids = (
        set(req.crops) if req.crops is not None else {c.id for c in catalogue.crops}
    )
    crops = [c for c in catalogue.crops if c.id in requested_ids]
    missing = requested_ids - {c.id for c in crops}
    if missing:
        raise ValueError(
            f"Unknown crop id(s) {sorted(missing)!r}; available: "
            f"{[c.id for c in catalogue.crops]}"
        )

    # 1) Climate — branch on scenario kind.
    if isinstance(req.scenario, HistoricalScenario):
        ds, climate_prov = _load_historical(
            req.bbox, req.scenario, cache_dir=agera5_cache_dir
        )
    elif isinstance(req.scenario, FutureScenario):
        ds, climate_prov = _load_future(req.bbox, req.scenario)
    else:
        raise TypeError(f"Unknown scenario type {type(req.scenario).__name__}")

    # 2) SoilGrids topsoil pH on the climate grid.
    soil = SoilGridsSource()
    soil_ds = soil.load(
        bbox=req.bbox,
        variables=("phh2o",),
        depths=("0-5cm",),
    )
    ph_native = soil_ds["phh2o"].squeeze("depth", drop=True).rename({"x": "lon", "y": "lat"})
    if float(ph_native["lat"][0]) > float(ph_native["lat"][-1]):
        ph_native = ph_native.sortby("lat")
    soil_ph = ph_native.interp(
        lat=ds["lat"], lon=ds["lon"], kwargs={"fill_value": "extrapolate"},
    )

    # 3) Score every requested crop.
    crop_scores: list[CropEnvelopeScore] = []
    grids: list[CropSuitabilityGrid] | None = (
        [] if req.include_grids else None
    )
    for crop in crops:
        ind = indicators_mod.compute_all(
            ds, gdd_base_temperature_c=crop.gdd.base_temperature_c
        )
        sui = envelope_mod.score_crop(ind, crop, soil_ph=soil_ph)
        crop_scores.append(_summarize_crop(sui, crop))
        if grids is not None:
            grids.append(_grid_for_crop(sui, crop.id))

    # 4) Provenance.
    soil_prov = soil.provenance(bbox=req.bbox, time_range=None)
    prov: list[ProvenanceStamp] = [
        climate_prov,
        ProvenanceStamp(
            source=soil_prov.source_name,
            version=soil_prov.source_version,
            fingerprint=soil_prov.fingerprint(),
            license=soil_prov.license,
            citation_key=soil_prov.citation_key,
        ),
    ]

    return EnvelopeResult(
        bbox=req.bbox,
        scenario=req.scenario,
        crops=crop_scores,
        grids=grids,
        provenance=prov,
    )


# ---- climate loaders --------------------------------------------------------


def _load_historical(
    bbox: tuple[float, float, float, float],
    scenario: HistoricalScenario,
    *,
    cache_dir: Path,
) -> tuple[xr.Dataset, ProvenanceStamp]:
    """AgERA5 Apr-Sep × N years, concatenated. Same window as the Tier 1
    notebook so indicators are consistent."""
    agera5 = AgERA5Source(cache_dir=cache_dir)
    pieces = []
    for year in sorted(scenario.years):
        piece = agera5.load(
            bbox=bbox,
            time_range=(dt.date(year, 4, 1), dt.date(year, 9, 30)),
            variables=("t2m_min", "t2m_max", "precip"),
        )
        pieces.append(
            piece.rename({"t2m_min": "tasmin", "t2m_max": "tasmax", "precip": "pr"})
        )
    ds = xr.concat(pieces, dim="time")
    prov = agera5.provenance(
        bbox=bbox,
        time_range=(
            dt.date(min(scenario.years), 4, 1),
            dt.date(max(scenario.years), 9, 30),
        ),
        variables=("t2m_min", "t2m_max", "precip"),
    )
    return ds, ProvenanceStamp(
        source=prov.source_name,
        version=prov.source_version,
        fingerprint=prov.fingerprint(),
        license=prov.license,
        citation_key=prov.citation_key,
    )


def _load_future(
    bbox: tuple[float, float, float, float],
    scenario: FutureScenario,
) -> tuple[xr.Dataset, ProvenanceStamp]:
    """CanDCS-M6 OPeNDAP, single GCM × single SSP × year window, sliced
    to Apr-Sep so the indicator window matches the historical baseline.
    """
    candcs = CanDCSM6Source()
    ds = candcs.load(
        bbox=bbox,
        time_range=(
            dt.date(scenario.start_year, 1, 1),
            dt.date(scenario.end_year, 12, 31),
        ),
        gcms=(scenario.gcm,),
        ssps=(scenario.ssp,),
    ).isel(gcm=0, ssp=0, drop=True)
    # Slice to Apr-Sep (months 4-9) for like-for-like with historical.
    ds = ds.sel(time=ds["time.month"].isin([4, 5, 6, 7, 8, 9]))
    prov = candcs.provenance(
        bbox=bbox,
        time_range=(
            dt.date(scenario.start_year, 1, 1),
            dt.date(scenario.end_year, 12, 31),
        ),
        variables=("tasmin", "tasmax", "pr"),
    )
    return ds, ProvenanceStamp(
        source=prov.source_name,
        version=prov.source_version,
        fingerprint=prov.fingerprint(),
        license=prov.license,
        citation_key=prov.citation_key,
    )


def _grid_for_crop(
    sui: envelope_mod.CropSuitability,
    crop_id: str,
) -> CropSuitabilityGrid:
    """Pack a CropSuitability score grid into the wire schema."""
    score = sui.score
    lats = score["lat"].values
    lons = score["lon"].values
    d_lat = float(abs(lats[1] - lats[0])) if len(lats) > 1 else 0.1
    d_lon = float(abs(lons[1] - lons[0])) if len(lons) > 1 else 0.1
    # Ensure south→north ascending for the frontend.
    if lats[0] > lats[-1]:
        score = score.sortby("lat")
        lats = score["lat"].values
    raw = score.values
    # Replace NaN with None for JSON.
    score_grid: list[list[float | None]] = [
        [None if not np.isfinite(v) else float(v) for v in row]
        for row in raw
    ]
    return CropSuitabilityGrid(
        crop_id=crop_id,
        lats=[float(x) for x in lats],
        lons=[float(x) for x in lons],
        cell_size_deg=(d_lat, d_lon),
        score_grid=score_grid,
    )


def _summarize_crop(
    sui: envelope_mod.CropSuitability,
    crop: requirements_mod.CropRequirements,
) -> CropEnvelopeScore:
    envelope_score = float(sui.envelope_score.mean().values)
    preference_score = float(sui.preference_score.mean().values)
    combined_score = float(sui.score.mean().values)
    gaez_class = envelope_mod.classify_gaez(xr.DataArray(envelope_score)).item()

    # Modal limiting factor across cells.
    flat = sui.limiting_factor.values.flatten()
    flat = flat[flat != ""]
    modal_limit: str | None = None
    if len(flat):
        unique, counts = np.unique(flat, return_counts=True)
        modal_limit = str(unique[counts.argmax()])

    per_factor = {
        name: float(arr.mean().values) for name, arr in sui.per_factor.items()
    }

    return CropEnvelopeScore(
        crop_id=crop.id,
        scientific_name=crop.scientific_name,
        common_name_en=crop.common_name_en,
        common_name_fr=crop.common_name_fr,
        envelope_score=envelope_score,
        preference_score=preference_score,
        combined_score=combined_score,
        gaez_class=GAEZClass(gaez_class),
        limiting_factor=modal_limit,
        per_factor_envelope=per_factor,
    )


__all__ = ["run_envelope_job"]
