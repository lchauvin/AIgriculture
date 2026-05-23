"""Hindcast harness and skill reporting.

Backtests Tier 2 yields against observed Statistics Canada Field Crop
Reporting Series yields (``docs/research/04-uncertainty-and-validation``
Part B). See :mod:`aigriculture.validation.hindcast` for the entry point
:func:`run_hindcast` and :mod:`aigriculture.validation.statcan_fcrs` for the
observed-yield loader.
"""

from .hindcast import (
    HindcastMetrics,
    HindcastReport,
    StructuralBreak,
    YearPair,
    build_report,
    compute_metrics,
    format_report,
    predict_yields_by_year,
    run_hindcast,
)
from .statcan_fcrs import ObservedYieldSeries, StatCanFCRSSource

__all__ = [
    "HindcastMetrics",
    "HindcastReport",
    "ObservedYieldSeries",
    "StatCanFCRSSource",
    "StructuralBreak",
    "YearPair",
    "build_report",
    "compute_metrics",
    "format_report",
    "predict_yields_by_year",
    "run_hindcast",
]
