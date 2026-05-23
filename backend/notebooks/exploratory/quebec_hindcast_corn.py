# %% [markdown]
# # Quebec grain-corn hindcast — observed-climate backtest
#
# First end-to-end run of the hindcast harness
# (`aigriculture.validation.hindcast`). For each year we drive WOFOST
# potential production with observed AgERA5 weather and compare the
# predicted yield to the Statistics Canada Field Crop Reporting Series
# provincial yield (Table 32-10-0359-01).
#
# **Method:** observed-climate backtest, *not* a climate-projection
# forecast (see `docs/research/04-uncertainty-and-validation.md` Part B/C).
#
# **Expected result:** WOFOST PP carries no water/nutrient/pest stress, so
# predicted yields sit *above* observed farm yields — a positive bias we
# report rather than correct (Tier 3 will absorb it later).
#
# ## Prerequisites
# - Copernicus CDS API (`~/.cdsapirc`) — only if the requested years are
#   not already in `data/cache/agera5`.
# - StatCan bulk CSV — downloaded automatically to `data/cache/statcan`
#   on first run (~5 MB), then cached.
#
# ## Years
# Pass years on the command line, e.g.
# `python quebec_hindcast_corn.py 2010 2011 ... 2019`.
# Defaults to **2018 only** — the year fully present in the committed
# AgERA5 cache, so the script runs offline as a wiring proof. A real skill
# assessment (RMSE / R² / trend) needs ~10+ years, which means fetching the
# missing AgERA5 months from the CDS first.

# %%
from __future__ import annotations

import sys

from aigriculture.validation.hindcast import format_report, run_hindcast

# Southern-Quebec (Montérégie) box — matches the committed AgERA5 cache and
# the Tier 2 / Tier 1 smoke tests.
BBOX = (-74.0, 45.0, -72.5, 46.0)

DEFAULT_YEARS = [2018]


# %%
def main(years: list[int]) -> None:
    print(f"Hindcasting grain corn over {BBOX} for years {years} …\n")
    report = run_hindcast("corn_grain", years=years, bbox=BBOX, geo="Quebec")
    print(format_report(report))

    if report.metrics.n < 5:
        print(
            "\n[!] Fewer than 5 matched years — RMSE/R²/trend are not yet "
            "meaningful. This run proves the harness end-to-end; pull more "
            "AgERA5 years for a real skill assessment."
        )


# %%
if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]]
    main(args or DEFAULT_YEARS)
