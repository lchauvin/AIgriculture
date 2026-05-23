"""Tests for the hindcast harness.

The pure scoring path (metric math, report assembly, structural-break
flagging) and the StatCan CSV parser are covered without network or PCSE.
The heavy WOFOST + AgERA5 prediction path is exercised by the live smoke
script (``backend/notebooks/exploratory/quebec_hindcast_corn.py``), not here.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from aigriculture.validation import statcan_fcrs
from aigriculture.validation.hindcast import (
    KNOWN_BREAKS,
    build_report,
    compute_metrics,
    format_report,
)
from aigriculture.validation.statcan_fcrs import ObservedYieldSeries, StatCanFCRSSource


# ---- compute_metrics -------------------------------------------------------


def test_compute_metrics_perfect_match():
    matched = [(2017, 9.0, 9.0), (2018, 10.0, 10.0), (2019, 11.0, 11.0)]
    m = compute_metrics(matched)
    assert m.n == 3
    assert m.rmse == pytest.approx(0.0)
    assert m.mae == pytest.approx(0.0)
    assert m.bias == pytest.approx(0.0)
    assert m.r2 == pytest.approx(1.0)
    assert m.pearson_r == pytest.approx(1.0)
    # Both trends rise 1 t/ha/yr → agree.
    assert m.predicted_trend_t_ha_per_yr == pytest.approx(1.0)
    assert m.observed_trend_t_ha_per_yr == pytest.approx(1.0)
    assert m.trend_direction_agrees is True


def test_compute_metrics_constant_positive_bias():
    # Model over-predicts by a constant 2 t/ha — the potential-production case.
    matched = [(2017, 11.0, 9.0), (2018, 12.0, 10.0), (2019, 13.0, 11.0)]
    m = compute_metrics(matched)
    assert m.bias == pytest.approx(2.0)
    assert m.mae == pytest.approx(2.0)
    assert m.rmse == pytest.approx(2.0)
    # Perfectly correlated (constant offset) but R² (NSE) is badly negative:
    # SS_res = 3*4 = 12, SS_tot = 2 (var of 9,10,11) ⇒ 1 - 12/2 = -5.
    assert m.pearson_r == pytest.approx(1.0)
    assert m.r2 == pytest.approx(-5.0)


def test_compute_metrics_known_rmse_bias():
    matched = [(2000, 8.0, 10.0), (2001, 12.0, 10.0)]  # diffs -2, +2
    m = compute_metrics(matched)
    assert m.bias == pytest.approx(0.0)
    assert m.rmse == pytest.approx(2.0)
    assert m.mae == pytest.approx(2.0)


def test_compute_metrics_opposing_trends_disagree():
    # Predicted rises, observed falls.
    matched = [(2000, 8.0, 11.0), (2001, 9.0, 10.0), (2002, 10.0, 9.0)]
    m = compute_metrics(matched)
    assert m.predicted_trend_t_ha_per_yr is not None
    assert m.observed_trend_t_ha_per_yr is not None
    assert m.predicted_trend_t_ha_per_yr > 0
    assert m.observed_trend_t_ha_per_yr < 0
    assert m.trend_direction_agrees is False


def test_compute_metrics_empty():
    m = compute_metrics([])
    assert m.n == 0
    assert m.rmse is None
    assert m.r2 is None
    assert m.trend_direction_agrees is None


def test_compute_metrics_single_point():
    m = compute_metrics([(2018, 10.0, 9.0)])
    assert m.n == 1
    assert m.bias == pytest.approx(1.0)
    assert m.rmse == pytest.approx(1.0)
    # Trends and R² need ≥2 points / observed spread.
    assert m.r2 is None
    assert m.predicted_trend_t_ha_per_yr is None
    assert m.trend_direction_agrees is None


# ---- build_report ----------------------------------------------------------


def _obs(by_year: dict[int, float]) -> ObservedYieldSeries:
    return ObservedYieldSeries(
        crop_label="Corn for grain",
        geo="Quebec",
        unit="t/ha",
        by_year=by_year,
        source="test",
        table_id="32-10-0359-01",
        license="test",
        citation_key="StatCanFCRS2026",
    )


def test_build_report_aligns_and_handles_gaps():
    predicted = {2017: 10.8, 2018: 10.5}  # 2019 prediction missing
    observed = _obs({2017: 10.0, 2018: 9.44, 2019: 8.88})
    report = build_report(
        "corn_grain", "Quebec", predicted, observed, [2017, 2018, 2019],
        cultivar="maize/Grain_maize_203",
    )
    assert [p.year for p in report.pairs] == [2017, 2018, 2019]
    # 2019 has observed but no predicted → present as a pair, excluded from metrics.
    p2019 = next(p for p in report.pairs if p.year == 2019)
    assert p2019.predicted_t_ha is None
    assert p2019.observed_t_ha == pytest.approx(8.88)
    assert p2019.residual is None
    assert report.matched_years() == [2017, 2018]
    assert report.metrics.n == 2
    assert report.metrics.bias is not None and report.metrics.bias > 0
    assert report.cultivar == "maize/Grain_maize_203"


def test_build_report_flags_structural_breaks_in_window():
    predicted = {1995: 7.0, 1996: 7.2, 2000: 7.5}
    observed = _obs({1995: 6.5, 1996: 6.6, 2000: 6.9})
    report = build_report("corn_grain", "Quebec", predicted, observed, [1995, 1996, 2000])
    break_years = {b.year for b in report.structural_breaks}
    assert 1996 in break_years  # Bt corn, corn-relevant, inside window


def test_build_report_excludes_breaks_outside_window_and_other_crops():
    predicted = {2017: 10.8, 2018: 10.5, 2019: 10.2}
    observed = _obs({2017: 10.0, 2018: 9.44, 2019: 8.88})
    report = build_report("corn_grain", "Quebec", predicted, observed, [2017, 2018, 2019])
    # No corn break falls in 2017–2019; the soybean break must never appear here.
    assert report.structural_breaks == ()


def test_known_breaks_are_crop_tagged():
    # Each break must declare which crops it applies to (used for filtering).
    assert all(b.crops for b in KNOWN_BREAKS)
    corn_breaks = [b for b in KNOWN_BREAKS if "corn_grain" in b.crops]
    assert any(b.year == 1996 for b in corn_breaks)


def test_format_report_runs():
    predicted = {2017: 10.8, 2018: 10.5}
    observed = _obs({2017: 10.0, 2018: 9.44})
    report = build_report(
        "corn_grain", "Quebec", predicted, observed, [2017, 2018],
        cultivar="maize/Grain_maize_203", notes=("test note",),
    )
    text = format_report(report)
    assert "Hindcast — corn_grain / Quebec" in text
    assert "RMSE" in text
    assert "2017" in text


# ---- StatCan CSV parser ----------------------------------------------------


# A tiny fixture mirroring the real 32-10-0359-01 column layout. Includes
# rows that must be filtered out: a non-yield disposition, another province,
# and another crop.
FIXTURE_CSV = (
    '"REF_DATE","GEO","DGUID","Harvest disposition","Type of crop","UOM",'
    '"UOM_ID","SCALAR_FACTOR","SCALAR_ID","VECTOR","COORDINATE","VALUE",'
    '"STATUS","SYMBOL","TERMINATED","DECIMALS"\n'
    '"2017","Quebec","x","Average yield (kilograms per hectare)","Corn for grain",'
    '"Kilograms per hectare","193","units","0","v1","1","10000","","","","0"\n'
    '"2018","Quebec","x","Average yield (kilograms per hectare)","Corn for grain",'
    '"Kilograms per hectare","193","units","0","v1","1","9441","","","","0"\n'
    # Wrong disposition (area, not yield) — must be excluded.
    '"2018","Quebec","x","Seeded area (hectares)","Corn for grain",'
    '"Hectares","100","units","0","v9","1","400000","","","","0"\n'
    # Wrong province — must be excluded.
    '"2018","Ontario","x","Average yield (kilograms per hectare)","Corn for grain",'
    '"Kilograms per hectare","193","units","0","v2","1","11000","","","","0"\n'
    # Wrong crop — must be excluded.
    '"2018","Quebec","x","Average yield (kilograms per hectare)","Soybeans",'
    '"Kilograms per hectare","193","units","0","v3","1","3000","","","","0"\n'
)


def _seed_fixture(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / statcan_fcrs.CSV_NAME).write_text(FIXTURE_CSV, encoding="utf-8")


def test_statcan_parser_filters_and_converts(tmp_path: Path):
    cache_dir = tmp_path / "statcan"
    _seed_fixture(cache_dir)
    src = StatCanFCRSSource(cache_dir=cache_dir)
    series = src.load_yield_t_ha("Corn for grain", geo="Quebec")
    # kg/ha → t/ha, only the two Quebec corn yield rows survive.
    assert series.by_year == {2017: pytest.approx(10.0), 2018: pytest.approx(9.441)}
    assert series.unit == "t/ha"
    assert series.years() == [2017, 2018]
    assert series.citation_key == "StatCanFCRS2026"


def test_statcan_parser_raises_on_unknown_label(tmp_path: Path):
    cache_dir = tmp_path / "statcan"
    _seed_fixture(cache_dir)
    src = StatCanFCRSSource(cache_dir=cache_dir)
    with pytest.raises(ValueError, match="No StatCan yield rows"):
        src.load_yield_t_ha("Triticale", geo="Quebec")


def test_statcan_no_download_when_cached(tmp_path: Path, monkeypatch):
    cache_dir = tmp_path / "statcan"
    _seed_fixture(cache_dir)

    def _boom(*args, **kwargs):
        raise AssertionError("should not download when CSV is cached")

    monkeypatch.setattr(statcan_fcrs, "urlopen", _boom)
    src = StatCanFCRSSource(cache_dir=cache_dir)
    series = src.load_yield_t_ha("Corn for grain", geo="Quebec")
    assert math.isclose(series.by_year[2017], 10.0)
