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
from ..data.soilgrids import SoilGridsSource
from ..suitability import envelope as envelope_mod
from ..suitability import indicators as indicators_mod
from ..suitability import requirements as requirements_mod
from .jobs import JobStore
from .schemas import (
    CropEnvelopeScore,
    EnvelopeRequest,
    EnvelopeResult,
    GAEZClass,
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

    # 1) AgERA5 historical — same April-September window the Tier 1
    #    notebook uses (full year increases AgERA5 quota for negligible
    #    Tier 1 signal — winter doesn't move the score). One pull per
    #    year, concatenated.
    agera5 = AgERA5Source(cache_dir=agera5_cache_dir)
    hist_pieces = []
    for year in sorted(req.historical_years):
        piece = agera5.load(
            bbox=req.bbox,
            time_range=(dt.date(year, 4, 1), dt.date(year, 9, 30)),
            variables=("t2m_min", "t2m_max", "precip"),
        )
        hist_pieces.append(
            piece.rename({"t2m_min": "tasmin", "t2m_max": "tasmax", "precip": "pr"})
        )
    ds = xr.concat(hist_pieces, dim="time")

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
    for crop in crops:
        ind = indicators_mod.compute_all(
            ds, gdd_base_temperature_c=crop.gdd.base_temperature_c
        )
        sui = envelope_mod.score_crop(ind, crop, soil_ph=soil_ph)
        crop_scores.append(_summarize_crop(sui, crop))

    # 4) Provenance — record what we consumed.
    prov: list[ProvenanceStamp] = []
    agera5_prov = agera5.provenance(
        bbox=req.bbox,
        time_range=(
            dt.date(min(req.historical_years), 4, 1),
            dt.date(max(req.historical_years), 9, 30),
        ),
        variables=("t2m_min", "t2m_max", "precip"),
    )
    prov.append(
        ProvenanceStamp(
            source=agera5_prov.source_name,
            version=agera5_prov.source_version,
            fingerprint=agera5_prov.fingerprint(),
            license=agera5_prov.license,
            citation_key=agera5_prov.citation_key,
        )
    )
    soil_prov = soil.provenance(bbox=req.bbox, time_range=None)
    prov.append(
        ProvenanceStamp(
            source=soil_prov.source_name,
            version=soil_prov.source_version,
            fingerprint=soil_prov.fingerprint(),
            license=soil_prov.license,
            citation_key=soil_prov.citation_key,
        )
    )

    return EnvelopeResult(
        bbox=req.bbox,
        historical_years=tuple(sorted(req.historical_years)),
        crops=crop_scores,
        provenance=prov,
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
