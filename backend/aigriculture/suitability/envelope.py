"""Tier 1 envelope scoring — GAEZ-style trapezoidal suitability.

Given a Dataset of climate + soil indicators and a ``CropRequirements``
spec, produce a continuous suitability score in [0, 1] per cell, plus
the dominant limiting factor for explainability.

Suitability is the **minimum** across the per-requirement scores
(Liebig's law of the minimum — the limiting factor sets the ceiling).
This is the GAEZ convention and is what the rest of the literature
benchmarks against.

We also discretize the continuous score into the standard FAO GAEZ
classes::

    score >= 0.80  → S1  (very suitable)
    score >= 0.55  → S2  (suitable)
    score >= 0.30  → S3  (moderately suitable)
    score >  0.00  → S4  (marginally suitable)
    score == 0     → N   (not suitable)

The class breakpoints are configurable but default to GAEZ v4.

For Tier 1 the score answers the question "is this crop in its
climatic envelope at all" — not "how much yield will it produce"; that
is Tier 2's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import xarray as xr

from .requirements import CropRequirements, Preference, TrapezoidBounds


# GAEZ-v4-style breakpoints for the discrete classes.
GAEZ_CLASS_BREAKPOINTS = {
    "S1": 0.80,
    "S2": 0.55,
    "S3": 0.30,
    "S4": 1e-6,  # strictly greater than zero
    "N":  0.0,
}
CLASS_ORDER = ("S1", "S2", "S3", "S4", "N")


def trapezoid(da: xr.DataArray, bounds: TrapezoidBounds) -> xr.DataArray:
    """Trapezoidal membership ∈ [0, 1].

    ::

        score
          1 |       _________
            |      /         \\
            |     /           \\
          0 |____/             \\____
                a   b         c  d
                |   |         |  |
              abs  opt       opt abs
              min  min       max max

    Out-of-range values score 0; on-plateau values score 1; linear ramps
    on either side.
    """
    a, b, c, d = bounds.absolute_min, bounds.optimal_min, bounds.optimal_max, bounds.absolute_max
    left_ramp = ((da - a) / (b - a)).clip(0, 1)
    right_ramp = ((d - da) / (d - c)).clip(0, 1) if d != c else xr.ones_like(da)
    # The minimum of the two ramps gives the trapezoid shape (0 outside,
    # 1 on the plateau, linear in between).
    score = xr.where(da.isnull(), np.nan, np.minimum(left_ramp, right_ramp))
    return score


def triangle(
    da: xr.DataArray,
    *,
    absolute_min: float,
    preferred: float,
    absolute_max: float,
) -> xr.DataArray:
    """Triangular preference ∈ [0, 1].

    ::

        score
          1 |       /\\
            |      /  \\
            |     /    \\
          0 |____/      \\____
                a   p      d
                |   |      |
              abs  pre    abs
              min  ferred max

    Peaks at ``preferred``; decays linearly to 0 at ``absolute_min`` and
    ``absolute_max``. Used alongside the trapezoidal envelope to
    discriminate among crops that all sit inside their envelopes — the
    triangle says "how close to peak performance is the cell", while
    the trapezoid says "does the cell sit inside the survival envelope
    at all".
    """
    if not (absolute_min <= preferred <= absolute_max):
        raise ValueError(
            f"preferred ({preferred}) must lie in [absolute_min, absolute_max] "
            f"= [{absolute_min}, {absolute_max}]"
        )
    left = (da - absolute_min) / max(preferred - absolute_min, 1e-9)
    right = (absolute_max - da) / max(absolute_max - preferred, 1e-9)
    raw = xr.where(da.isnull(), np.nan, np.minimum(left, right))
    return raw.clip(0, 1)


@dataclass(frozen=True, slots=True)
class CropSuitability:
    """Result of scoring one crop over one indicator field.

    The overall ``score`` is ``envelope_score × preference_score`` —
    the most useful default for ranking crops within a region:

    - ``envelope_score`` (trapezoidal, Liebig minimum across factors)
      answers *"is the cell inside the crop's survival envelope?"*.
      ``classify_gaez(envelope_score)`` gives the S1/S2/S3/S4/N class.
    - ``preference_score`` (triangular, geometric mean across factors)
      answers *"how close to peak performance is the cell within the
      envelope?"*. Discriminates among crops that all sit on the
      envelope plateau.

    Crops that lack a ``preference`` block in the YAML get a
    ``preference_score`` of 1.0 everywhere (no within-envelope
    differentiation), so the combined score falls back to the
    envelope semantics.
    """

    crop_id: str
    score: xr.DataArray
    envelope_score: xr.DataArray
    preference_score: xr.DataArray
    per_factor: dict[str, xr.DataArray]
    per_factor_preference: dict[str, xr.DataArray]
    limiting_factor: xr.DataArray


def score_crop(
    indicators: xr.Dataset,
    crop: CropRequirements,
    *,
    soil_ph: xr.DataArray | None = None,
) -> CropSuitability:
    """Score one crop against a Dataset of climate indicators.

    Parameters
    ----------
    indicators
        Output of ``aigriculture.suitability.indicators.compute_all``
        (or any Dataset with ``tmean_growing_c``, ``gdd``,
        ``annual_precip_mm``, ``growing_season_days``).
    crop
        A ``CropRequirements`` for the crop being scored. Must be one
        whose ``gdd.base_temperature_c`` matches the base used to
        compute ``indicators.gdd``.
    soil_ph
        Optional soil-pH DataArray (e.g. SoilGrids topsoil pH at the
        same grid as ``indicators``). When provided, contributes a pH
        sub-score factor; when omitted, the soil-pH constraint is
        skipped.

    Returns
    -------
    CropSuitability
    """
    per_factor: dict[str, xr.DataArray] = {}

    per_factor["temperature"] = trapezoid(
        indicators["tmean_growing_c"], crop.temperature.as_trapezoid()
    )
    per_factor["gdd"] = trapezoid(
        indicators["gdd"], crop.gdd.as_trapezoid()
    )
    per_factor["precipitation"] = trapezoid(
        indicators["annual_precip_mm"], crop.precipitation.as_trapezoid()
    )

    # Growing-season-length is a one-sided constraint: at least
    # ``cycle_min_days`` of frost-free growing season are required, with
    # increasing comfort up to a "plenty" threshold of 1.25× the
    # minimum. There's no upper kill in GAEZ for cycle length on the
    # frost-free-days side.
    cycle_min = crop.growing_season.cycle_min_days
    cycle_plenty = cycle_min * 1.25
    gs = indicators["growing_season_days"]
    per_factor["growing_season"] = xr.where(
        gs.isnull(),
        np.nan,
        ((gs - cycle_min) / max(cycle_plenty - cycle_min, 1e-6)).clip(0, 1),
    )

    if soil_ph is not None:
        per_factor["soil_ph"] = trapezoid(soil_ph, crop.soil.as_trapezoid())

    # Liebig minimum: the limiting factor sets the ceiling.
    factors = list(per_factor)
    stacked = xr.concat(
        [per_factor[f].expand_dims(factor=[f]) for f in factors],
        dim="factor",
    )
    score = stacked.min(dim="factor")

    limit_idx = stacked.argmin(dim="factor")
    factor_names = np.array(factors)
    limiting_factor = xr.DataArray(
        factor_names[limit_idx.values],
        coords=limit_idx.coords,
        dims=limit_idx.dims,
    )
    # Where every factor is NaN (no-data cell), the limit name is
    # meaningless — wipe it out so downstream UIs don't display a stale label.
    limiting_factor = limiting_factor.where(~score.isnull(), "")

    # ---- preference (triangular) -----------------------------------------
    per_factor_pref: dict[str, xr.DataArray] = {}
    if crop.preference is not None:
        per_factor_pref["temperature"] = triangle(
            indicators["tmean_growing_c"],
            absolute_min=crop.temperature.tmean_absolute_min_c,
            preferred=crop.preference.tmean_preferred_c,
            absolute_max=crop.temperature.tmean_absolute_max_c,
        )
        per_factor_pref["gdd"] = triangle(
            indicators["gdd"],
            absolute_min=crop.gdd.absolute_min,
            preferred=crop.preference.gdd_preferred,
            absolute_max=crop.gdd.absolute_max,
        )
        per_factor_pref["precipitation"] = triangle(
            indicators["annual_precip_mm"],
            absolute_min=crop.precipitation.annual_absolute_min_mm,
            preferred=crop.preference.annual_precip_preferred_mm,
            absolute_max=crop.precipitation.annual_absolute_max_mm,
        )
        if soil_ph is not None and crop.preference.ph_preferred is not None:
            per_factor_pref["soil_ph"] = triangle(
                soil_ph,
                absolute_min=crop.soil.ph_absolute_min,
                preferred=crop.preference.ph_preferred,
                absolute_max=crop.soil.ph_absolute_max,
            )
        # Geometric mean across factors keeps the score sensitive to any
        # single factor being far from its peak (no plateau-style
        # masking) while staying bounded in [0, 1].
        pref_stack = xr.concat(
            [per_factor_pref[f].expand_dims(factor=[f]) for f in per_factor_pref],
            dim="factor",
        )
        preference_score = pref_stack.prod(dim="factor") ** (1.0 / len(per_factor_pref))
    else:
        preference_score = xr.ones_like(score)

    combined = score * preference_score

    return CropSuitability(
        crop_id=crop.id,
        score=combined,
        envelope_score=score,
        preference_score=preference_score,
        per_factor=per_factor,
        per_factor_preference=per_factor_pref,
        limiting_factor=limiting_factor,
    )


def classify_gaez(
    score: xr.DataArray,
    breakpoints: dict[str, float] | None = None,
) -> xr.DataArray:
    """Bucket a continuous score ∈ [0, 1] into the FAO GAEZ S1/S2/S3/S4/N classes."""
    bp = breakpoints if breakpoints is not None else GAEZ_CLASS_BREAKPOINTS
    # Initialize as "N" (not suitable) and overwrite as we go.
    out = xr.full_like(score, "N", dtype=object)
    for cls in ("S4", "S3", "S2", "S1"):
        out = out.where(score < bp[cls], cls)
    out = out.where(~score.isnull(), "")
    return out


def rank_crops(
    indicators: xr.Dataset,
    crops: Iterable[CropRequirements],
    *,
    soil_ph: xr.DataArray | None = None,
) -> dict[str, CropSuitability]:
    """Score multiple crops; return a dict keyed by ``crop.id``."""
    return {
        crop.id: score_crop(indicators, crop, soil_ph=soil_ph)
        for crop in crops
    }


__all__ = [
    "CLASS_ORDER",
    "CropSuitability",
    "GAEZ_CLASS_BREAKPOINTS",
    "classify_gaez",
    "rank_crops",
    "score_crop",
    "trapezoid",
    "triangle",
]
