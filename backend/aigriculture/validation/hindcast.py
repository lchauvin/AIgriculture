"""Hindcast harness — backtest Tier 2 yields against observed StatCan yields.

**Approach** (``docs/research/04-uncertainty-and-validation`` Part B): an
*observed-climate backtest*. For each year we drive WOFOST potential
production with the **observed AgERA5 weather** of that growing season and
compare the predicted yield to the StatCan Field Crop Reporting Series
provincial yield for the same year. This isolates the crop model's skill
given (near-)perfect weather.

It deliberately does **not** test climate-*projection* skill — using today's
CMIP6 historical runs to "forecast" 1995 is anachronistic (doc Part C). That
is a Phase-4 concern.

**Expected bias.** Potential production carries no water / nutrient / pest
stress, so predicted yields sit *above* observed farm yields. We report that
bias rather than correcting it; Tier 3 (ML bias-correction) will absorb the
trend later. The harness's job is to quantify and characterise the gap, not
to hide it.

The orchestration splits into three pieces so the scoring logic is unit-
testable without network or PCSE:

- :func:`predict_yields_by_year` — heavy: AgERA5 + WOFOST per year.
- :class:`StatCanFCRSSource` (sibling module) — observed yields.
- :func:`build_report` / :func:`compute_metrics` — pure functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from ..suitability import requirements as requirements_mod
from .statcan_fcrs import ObservedYieldSeries, StatCanFCRSSource

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AGERA5_CACHE = REPO_ROOT / "data" / "cache" / "agera5"

# Map an AIgriculture crop id → the StatCan ``Type of crop`` label. Extend as
# crops gain a WOFOST mapping and a corresponding StatCan series.
CROP_STATCAN_LABEL: dict[str, str] = {
    "corn_grain": "Corn for grain",
}


@dataclass(frozen=True, slots=True)
class StructuralBreak:
    """A non-climate discontinuity that confounds the climate signal.

    These annotate the report (doc B.3); the model does **not** adjust for
    them. ``approximate`` flags years we only know to within a few seasons
    (e.g. trait-adoption ramps rather than a single switch-over).
    """

    year: int
    label: str
    crops: tuple[str, ...]
    approximate: bool = False


# Known Quebec-relevant breaks. Sourced from doc B.3, which itself flags the
# trait-adoption years as approximate ("mid-/late-1990s").
KNOWN_BREAKS: tuple[StructuralBreak, ...] = (
    StructuralBreak(
        1996, "Bt (insect-resistant) corn commercialization in Canada",
        crops=("corn_grain",), approximate=True,
    ),
    StructuralBreak(
        1997, "Roundup Ready soybean adoption begins in Canada",
        crops=("soybean",), approximate=True,
    ),
)


@dataclass(frozen=True, slots=True)
class YearPair:
    """Predicted vs observed yield for one calendar year (t/ha)."""

    year: int
    predicted_t_ha: float | None
    observed_t_ha: float | None

    @property
    def residual(self) -> float | None:
        """predicted − observed (None unless both present)."""
        if self.predicted_t_ha is None or self.observed_t_ha is None:
            return None
        return self.predicted_t_ha - self.observed_t_ha


@dataclass(frozen=True, slots=True)
class HindcastMetrics:
    """Skill summary over the years where both predicted and observed exist.

    ``r2`` is the coefficient of determination (a.k.a. Nash–Sutcliffe
    efficiency): ``1 − SS_res/SS_tot``. It can go negative when a strongly
    biased model does worse than predicting the observed mean — which is an
    honest and likely outcome for unbiased potential-production yields.
    """

    n: int
    rmse: float | None
    mae: float | None
    bias: float | None  # mean(pred − obs); positive ⇒ model over-predicts
    r2: float | None
    pearson_r: float | None
    predicted_trend_t_ha_per_yr: float | None
    observed_trend_t_ha_per_yr: float | None
    trend_direction_agrees: bool | None


@dataclass(frozen=True, slots=True)
class HindcastReport:
    crop_id: str
    geo: str
    cultivar: str | None
    pairs: tuple[YearPair, ...]
    metrics: HindcastMetrics
    structural_breaks: tuple[StructuralBreak, ...]
    observed_source: str
    observed_table_id: str
    observed_license: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def matched_years(self) -> list[int]:
        return [p.year for p in self.pairs if p.residual is not None]


# ---- pure scoring -----------------------------------------------------------


def _slope_per_year(years: Sequence[int], values: Sequence[float]) -> float | None:
    """Least-squares slope (value units per year). None if < 2 points or the
    years have no spread."""
    n = len(years)
    if n < 2:
        return None
    mean_x = sum(years) / n
    mean_y = sum(values) / n
    sxx = sum((x - mean_x) ** 2 for x in years)
    if sxx == 0:
        return None
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(years, values))
    return sxy / sxx


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def compute_metrics(matched: Sequence[tuple[int, float, float]]) -> HindcastMetrics:
    """Compute skill metrics from ``(year, predicted, observed)`` triples.

    ``matched`` must contain only years where both values are present.
    """
    n = len(matched)
    if n == 0:
        return HindcastMetrics(
            n=0, rmse=None, mae=None, bias=None, r2=None, pearson_r=None,
            predicted_trend_t_ha_per_yr=None, observed_trend_t_ha_per_yr=None,
            trend_direction_agrees=None,
        )

    years = [m[0] for m in matched]
    pred = [m[1] for m in matched]
    obs = [m[2] for m in matched]
    diffs = [p - o for p, o in zip(pred, obs)]

    bias = sum(diffs) / n
    mae = sum(abs(d) for d in diffs) / n
    rmse = math.sqrt(sum(d * d for d in diffs) / n)

    mean_obs = sum(obs) / n
    ss_tot = sum((o - mean_obs) ** 2 for o in obs)
    ss_res = sum(d * d for d in diffs)
    r2 = (1.0 - ss_res / ss_tot) if (n >= 2 and ss_tot > 0) else None

    pred_trend = _slope_per_year(years, pred)
    obs_trend = _slope_per_year(years, obs)
    direction_agrees: bool | None = None
    if pred_trend is not None and obs_trend is not None:
        # Treat a flat trend (|slope| below a tiny threshold) as sign 0 so we
        # don't claim agreement/disagreement on numerical noise.
        eps = 1e-6
        sp = 0 if abs(pred_trend) < eps else (1 if pred_trend > 0 else -1)
        so = 0 if abs(obs_trend) < eps else (1 if obs_trend > 0 else -1)
        direction_agrees = sp == so

    return HindcastMetrics(
        n=n,
        rmse=rmse,
        mae=mae,
        bias=bias,
        r2=r2,
        pearson_r=_pearson(pred, obs),
        predicted_trend_t_ha_per_yr=pred_trend,
        observed_trend_t_ha_per_yr=obs_trend,
        trend_direction_agrees=direction_agrees,
    )


def build_report(
    crop_id: str,
    geo: str,
    predicted: dict[int, float],
    observed: ObservedYieldSeries,
    requested_years: Iterable[int],
    *,
    cultivar: str | None = None,
    notes: Sequence[str] = (),
) -> HindcastReport:
    """Assemble a :class:`HindcastReport` from predicted + observed yields.

    Pure: no network, no PCSE. ``requested_years`` defines the row set; a
    year with a missing predicted or observed value still appears as a pair
    (with ``None``) but is excluded from the metrics.
    """
    years = sorted(set(requested_years))
    pairs = tuple(
        YearPair(
            year=y,
            predicted_t_ha=predicted.get(y),
            observed_t_ha=observed.by_year.get(y),
        )
        for y in years
    )
    matched = [
        (p.year, p.predicted_t_ha, p.observed_t_ha)
        for p in pairs
        if p.predicted_t_ha is not None and p.observed_t_ha is not None
    ]
    metrics = compute_metrics(matched)

    lo, hi = (years[0], years[-1]) if years else (0, -1)
    breaks = tuple(
        b for b in KNOWN_BREAKS if crop_id in b.crops and lo <= b.year <= hi
    )

    return HindcastReport(
        crop_id=crop_id,
        geo=geo,
        cultivar=cultivar,
        pairs=pairs,
        metrics=metrics,
        structural_breaks=breaks,
        observed_source=observed.source,
        observed_table_id=observed.table_id,
        observed_license=observed.license,
        notes=tuple(notes),
    )


# ---- heavy prediction path --------------------------------------------------


def predict_yields_by_year(
    crop: requirements_mod.CropRequirements,
    years: Iterable[int],
    *,
    bbox: tuple[float, float, float, float],
    cache_dir: Path | None = None,
) -> tuple[dict[int, float], str, list[tuple[int, str]]]:
    """Run WOFOST PP on observed AgERA5 for each year (region-centre site).

    Returns ``(yields_by_year, cultivar, failures)`` where ``failures`` lists
    ``(year, message)`` for years that errored (a bad year is skipped, not
    fatal). Mirrors the API runner's yield path but keeps per-year results
    instead of averaging. Requires the crop to carry a ``wofost`` mapping.
    """
    if crop.wofost is None:
        raise ValueError(
            f"Crop {crop.id!r} has no WOFOST mapping; cannot hindcast yield."
        )
    # Heavy imports kept local so the pure scoring path stays light.
    from ..crop_models import wofost_runner
    from ..data.agera5 import AgERA5Source

    agera5 = AgERA5Source(cache_dir=cache_dir or DEFAULT_AGERA5_CACHE)
    wf = crop.wofost
    lat_c = (bbox[1] + bbox[3]) / 2.0
    lon_c = (bbox[0] + bbox[2]) / 2.0

    out: dict[int, float] = {}
    failures: list[tuple[int, str]] = []
    for year in sorted(set(years)):
        try:
            ds = agera5.load(
                bbox=bbox,
                time_range=(date(year, 4, 1), date(year, 10, 31)),
                variables=("t2m_min", "t2m_max", "precip", "solar_rad"),
            ).rename(
                {
                    "t2m_min": "tasmin",
                    "t2m_max": "tasmax",
                    "precip": "pr",
                    "solar_rad": "rsds",
                }
            )
            result = wofost_runner.run_wofost_pp(
                weather_ds=ds,
                crop_name=wf.crop_name,
                variety_name=wf.variety_name,
                campaign_start=date(year, 4, 1),
                emergence=date(year, wf.emergence_month, wf.emergence_day),
                harvest=date(year, wf.harvest_month, wf.harvest_day),
                latitude=lat_c,
                longitude=lon_c,
            )
            out[year] = result.yield_t_ha
        except Exception as exc:  # noqa: BLE001 — record and continue
            failures.append((year, f"{type(exc).__name__}: {exc}"))
            continue

    return out, f"{wf.crop_name}/{wf.variety_name}", failures


def run_hindcast(
    crop_id: str,
    *,
    years: Iterable[int],
    bbox: tuple[float, float, float, float],
    geo: str = "Quebec",
    agera5_cache_dir: Path | None = None,
    statcan_cache_dir: Path | None = None,
    catalogue_path: Path | None = None,
) -> HindcastReport:
    """End-to-end hindcast for one crop × region × year span.

    Heavy: pulls AgERA5, runs WOFOST per year, and reads the StatCan table.
    """
    years = sorted(set(years))
    catalogue = requirements_mod.load_catalogue(catalogue_path)
    crop = catalogue.by_id(crop_id)

    if crop_id not in CROP_STATCAN_LABEL:
        raise ValueError(
            f"No StatCan crop label registered for {crop_id!r}; add it to "
            f"CROP_STATCAN_LABEL."
        )

    predicted, cultivar, failures = predict_yields_by_year(
        crop, years, bbox=bbox, cache_dir=agera5_cache_dir
    )

    observed = StatCanFCRSSource(statcan_cache_dir).load_yield_t_ha(
        CROP_STATCAN_LABEL[crop_id], geo=geo
    )

    notes = [
        "WOFOST potential production (no water/nutrient/pest stress) — a "
        "positive bias vs observed farm yields is expected, not a model error.",
        "StatCan yields are reported at the market moisture standard; WOFOST "
        "yields are converted to 14% moisture. Treat sub-decimal agreement "
        "cautiously.",
        "Predicted yields use region-centre weather, compared against a "
        "province-wide observed mean — a resolution mismatch (doc B.1).",
    ]
    for year, msg in failures:
        notes.append(f"WOFOST failed for {year}: {msg}")

    return build_report(
        crop_id,
        geo,
        predicted,
        observed,
        years,
        cultivar=cultivar,
        notes=notes,
    )


# ---- text rendering ---------------------------------------------------------


def _fmt(x: float | None, prec: int = 2) -> str:
    return "—" if x is None else f"{x:.{prec}f}"


def format_report(report: HindcastReport) -> str:
    """Render a plain-text summary suitable for a notebook / CLI."""
    m = report.metrics
    lines: list[str] = []
    lines.append(
        f"Hindcast — {report.crop_id} / {report.geo}"
        + (f" [{report.cultivar}]" if report.cultivar else "")
    )
    lines.append(f"Observed: {report.observed_source} ({report.observed_table_id})")
    lines.append("")
    lines.append(f"  {'year':>6}  {'pred':>8}  {'obs':>8}  {'resid':>8}")
    for p in report.pairs:
        lines.append(
            f"  {p.year:>6}  {_fmt(p.predicted_t_ha):>8}  "
            f"{_fmt(p.observed_t_ha):>8}  {_fmt(p.residual):>8}"
        )
    lines.append("")
    lines.append(f"  n matched      : {m.n}")
    lines.append(f"  RMSE  (t/ha)   : {_fmt(m.rmse)}")
    lines.append(f"  MAE   (t/ha)   : {_fmt(m.mae)}")
    lines.append(f"  bias  (t/ha)   : {_fmt(m.bias)}  (+ = model over-predicts)")
    lines.append(f"  R²  (NSE)      : {_fmt(m.r2)}")
    lines.append(f"  Pearson r      : {_fmt(m.pearson_r)}")
    lines.append(
        f"  trend pred/obs : {_fmt(m.predicted_trend_t_ha_per_yr, 3)} / "
        f"{_fmt(m.observed_trend_t_ha_per_yr, 3)} t/ha/yr"
        f"  (dir agrees: {m.trend_direction_agrees})"
    )
    if report.structural_breaks:
        lines.append("")
        lines.append("  structural breaks in window:")
        for b in report.structural_breaks:
            approx = " (approx.)" if b.approximate else ""
            lines.append(f"    {b.year}{approx}: {b.label}")
    if report.notes:
        lines.append("")
        lines.append("  notes:")
        for note in report.notes:
            lines.append(f"    - {note}")
    return "\n".join(lines)


__all__ = [
    "CROP_STATCAN_LABEL",
    "HindcastMetrics",
    "HindcastReport",
    "KNOWN_BREAKS",
    "StructuralBreak",
    "YearPair",
    "build_report",
    "compute_metrics",
    "format_report",
    "predict_yields_by_year",
    "run_hindcast",
]
