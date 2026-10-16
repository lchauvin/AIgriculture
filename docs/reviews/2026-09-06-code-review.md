# AIgriculture — Code Review, Validation Assessment and Maturity Report

**Date:** 2026-09-06
**Scope:** `backend/`, `frontend/`, `backend/tests/`, tooling, `docs/`, local data cache.
**Method:** baseline runs (pytest, ruff, mypy, `next build`/`tsc`/`next lint`) plus three
independent read-only code explorations, with claims spot-checked by executing snippets
against the real code and the real StatCan CSV. No source file was modified.

---

## 0. Executive summary

The project is a **working Tier-1/Tier-2 MVP for a single Quebec bbox**, not the
three-tier, uncertainty-aware system the README and ADRs describe. The code that exists
is generally clean, well-documented and unit-tested at the function level (128 tests,
87 % line coverage), and the frontend builds cleanly. However:

1. **Two scoring defects materially bias every result today** (Apr–Sep precipitation
   scored against *annual* thresholds; duplicate years double GDD/precip).
2. **No-data handling is wrong end to end** — NaN cells become score 0 / class "N" and
   pollute region means; a NaN factor is silently *ignored* rather than propagated.
3. **The real-data pipeline (`api/runner.py`, `validation/hindcast.py`) has zero test
   coverage**; every test mocks the network and the runner.
4. **The requested backtest cannot be run from this checkout.** The AgERA5 cache is
   empty, no CDS/Earth-Engine credentials exist on the machine, and the hindcast that
   *is* implemented is a same-year yield comparison, not a temporal hold-out.
5. **Everything the project calls its differentiator — multi-GCM ensembles,
   Hawkins–Sutton uncertainty, ML bias correction, water-limited WOFOST — is
   unimplemented** (`climate/`, `ml/`, `uncertainty/` are one-line stubs).
6. **Docs are badly out of date** (README says "no application code yet"; every ADR is
   contradicted by the code somewhere; research docs still marked "Stub").

**Maturity: early prototype (TRL 3–4).** Suitable for demonstrating the concept on one
bbox with pre-downloaded data; not suitable for producing recommendations anyone should
act on, and not yet validated against any observation.

---

## 1. Baseline (what was run)

| Check | Result |
|---|---|
| `uv sync --all-extras` (Python 3.12.12) | OK |
| `uv run pytest -q` | **128 passed**, 0 failed; 87 % line coverage |
| `uv run ruff check backend/aigriculture` | **130 errors** (50 auto-fixable); 244 incl. tests |
| `uv run ruff format --check` | 24 of 47 files would be reformatted |
| `uv run mypy backend/aigriculture` | **Unusable** — `python_version = "3.11"` in `pyproject.toml` while venv deps use 3.12 syntax (zarr); with `--python-version 3.12` mypy 2.1.0 hits an internal error |
| `next build` / `tsc --noEmit` / `next lint` | All pass (Next 14.2.35). Note: `node_modules/.bin` lacks Windows `.cmd` shims, so `npm run …` fails on this machine until `npm ci` is re-run |
| CI / pre-commit / Dockerfile / Makefile | None exist |
| `project-dashboard.json` (required by `D:\Python\AGENTS.md` for projects exposing servers) | **Missing** — FastAPI on 8008, Next dev on 3232 |
| git | Repo flagged "dubious ownership" (owned by Administrators); needs `git config --global --add safe.directory …` |

Data actually present locally: `data/cache/statcan/32100359.csv` (390 k rows, 1908–2026,
Quebec included), one AAFC ACI tile for 2020 over (−74, 45, −73, 46). `data/cache/agera5/`
is **empty**. No `~/.cdsapirc`, no `CDSAPI_*` env vars, no Earth Engine credentials.

---

## 2. Defects

Severity: **blocker** = wrong results for normal inputs; **major** = wrong results or
unsafe behaviour under realistic conditions; **minor** = quality/robustness.

### 2.1 Scientific / scoring correctness

| # | Sev | Location | Finding |
|---|---|---|---|
| S1 | **blocker** | `api/runner.py:191`, `:233`; `data/crops/quebec_staples.yaml` `annual_*_mm` | Climate is loaded for **Apr–Sep only**, but `annual_precipitation_mm` is scored against **annual** ECOCROP thresholds (500–750 mm optimum). Verified: uniform 3 mm/day Apr–Sep → 549 mm → corn precipitation factor 0.745 and `limiting_factor = "precipitation"` in humid Quebec. Precipitation becomes the artificial limiter for every crop. |
| S2 | **blocker** | `api/runner.py:188`, `:305` | `sorted(scenario.years)` does not dedupe. `years=[2018, 2018]` concatenates the same days twice → GDD and precipitation **doubled** (verified 2745 vs 1372.5), WOFOST run twice. Schema allows duplicates. |
| S3 | **major** | `suitability/indicators.py:167-168`; `envelope.py:220` | `sum(skipna=True)` turns an all-NaN cell (ocean, outside coverage) into `gdd=0, precip=0, gs_days=0` → envelope 0, class "N", limiting factor "gdd". The `where(~isnull)` guard is dead code. Verified: 3 valid cells at 0.745 + 1 NaN cell → region mean 0.559. No-data is rendered as "unsuitable". |
| S4 | **major** | `suitability/envelope.py:209`, `:257` | `min(dim="factor")` / `prod()` use default `skipna=True`: a cell with `soil_ph = NaN` scores 1.0 with the soil constraint silently dropped (verified). |
| S5 | **major** | `suitability/envelope.py:288-298` | `rank_crops` scores all crops against a single indicator set, i.e. **one GDD base temperature** for corn (10), wheat (0), canola (5). `score_crop`'s docstring forbids this; `test_rank_crops_returns_all` codifies the misuse. Runner and notebook avoid it by calling `compute_all` per crop. |
| S6 | **major** | `crop_models/wofost_runner.py:198-206` | `summary.get("TWSO") or 0.0` turns `None` (crop never reached storage-organ growth) into a **valid 0 t/ha** that is averaged into region yields. |
| S7 | **major** | `crop_models/wofost_runner.py:49`, `:169` | CO₂ fixed at 415 ppm for every simulation year → spurious CO₂ fertilisation in 1990s hindcasts (≈355 ppm). |
| S8 | **major** | `data/aafc_aci.py:272-348` | `LEGEND` is wrong for ~30 of 76 codes when diffed against the official EE catalogue (e.g. 177 is Potatoes, labelled Tomatoes; 60/85/121/159–199 mostly wrong). The four staple codes happen to be right, so tests do not catch it. Potatoes — a major Quebec crop — are absent. |
| S9 | **major** | `crop_models/weather.py:177-186` | If the dataset has `y/x` dims (anything from rioxarray) and `latitude` is not passed, site latitude silently defaults to **0°** → wrong day length, Angot radiation, ET0. |
| S10 | **major** | `crop_models/weather.py:61` | Import-time global side effect: `pcse_settings.METEO_RANGE_CHECKS = False` for the whole process, disabling *all* PCSE range checks, not just E0/ES0/ET0. Combined with no finiteness check (`:204-207`, `:245-250`), NaN weather flows into WOFOST silently. |
| S11 | **major** | `crop_models/weather.py:75-110` | Unknown/missing `units` attr passes through unconverted: Kelvin without attr becomes 280 °C; `"W/m^2"` (not in the accepted set) is treated as J m⁻² d⁻¹ → 86 400× too small radiation. The whole AgERA5 path depends on attrs surviving xarray ops. |
| S12 | minor | `suitability/indicators.py:59-98` | GDD has no upper cap and zeroes any day with Tmin < 0 (non-standard McMaster–Wilhelm; mismatches the CHU-based calibration comments in the YAML). `growing_season_days` is a *count* of Tmin ≥ 0 days (max 183 in the window), not frost-free-period length; factor is ≈1.0 everywhere → non-discriminating. |
| S13 | minor | `suitability/requirements.py`, `envelope.py:191-198` | `frost.kill_temperature_c`, `reduced_growth_temperature_c`, `growing_season.cycle_max_days`, `photoperiod`, `aci_code` are loaded and **never consumed**. Frost is hard-coded at 0 °C; canola's −6 °C tolerance has no effect. |
| S14 | minor | `suitability/requirements.py:78,107,138,171` | Validators are non-strict (`abs_min == opt_min` allowed); `as_trapezoid()` then raises at **score** time, contradicting the "validated at load" docstring. |
| S15 | minor | `api/runner.py:348` | GAEZ class is derived from the **mean** of a min-based score, not from the per-cell class distribution/robustness that `04-uncertainty` §A.4 specifies. |
| S16 | minor | `api/runner.py:118-123` | SoilGrids 250 m pH is point-sampled (`interp`, `fill_value="extrapolate"`) onto the 10 km climate grid — aliasing inside the footprint, fabricated values outside. Should be a block mean. |
| S17 | minor | `crop_models/wofost_runner.py:40,52-55` | `DRY_MATTER_TO_GRAIN_FACTOR = 1.16` (14 % moisture) applied to all crops; canola market moisture is 8.5–10 %, soybean 13 % → ~5 % structural bias. |
| S18 | minor | `data/candcs_m6.py:177-189` | GCMs concatenated along `gcm` with no calendar check. CMIP6 GCMs mix `noleap` and `proleptic_gregorian`; if PAVICS preserves them, `concat` either raises or silently outer-joins with NaN days. Unverified against the live catalogue; no guard. |

### 2.2 API / runtime safety

| # | Sev | Location | Finding |
|---|---|---|---|
| A1 | **major** | `api/runner.py:73-76`; `api/routes/jobs.py:31` | Full Python traceback (with absolute filesystem paths) is stored in `JobView.error` and returned verbatim to clients; the frontend renders it. |
| A2 | **major** | `api/schemas.py:59-63` | `HistoricalScenario.years` has no max length, no min/max year (AgERA5 starts 1979), no dedupe → one request can trigger hundreds of CDS downloads (`years=[1979..2025]` → 846 CDS requests). |
| A3 | **major** | `api/routes/envelope.py:41`; `data/agera5.py:159-160,248` | Jobs run via `BackgroundTasks` on the 40-thread anyio pool with no concurrency cap or queue. Two jobs with the same bbox/year race on `fp.exists()` → both download and write the same NetCDF → corrupt cache / `PermissionError` on Windows. `arq` is a declared dependency but unused. |
| A4 | **major** | `api/jobs.py` | In-memory dict: no TTL, eviction, size cap, persistence or job timeout. Results with grids are MBs each → unbounded memory. A job `running` when the process dies stays `running` forever; the frontend polls it every 2 s forever. |
| A5 | **major** | `api/runner.py:112-117`; `data/soilgrids.py` | SoilGrids native 250 m VRT is streamed from ISRIC on **every job**, never cached (module docstring itself warns 10–20 min). Every job, including "historical", needs network. |
| A6 | **major** | `data/agera5.py:246-250,337`; `data/aafc_aci.py:252-261` | Partial download/write leaves a truncated file; `fp.exists()` then skips re-fetch → **poisoned cache** surfacing later as an opaque HDF error. Should write to temp + rename. |
| A7 | minor | `data/base.py:59-72` | `Provenance.fingerprint()` omits source-specific selectors (`gcms`, `ssps`, `depths`) → different data selections hash identically. AgERA5 cache filename omits `version`; bbox rounded to 2 dp collides. |
| A8 | minor | `api/runner.py:306-317, 329-331` | In the yield path, the AgERA5 load is outside the `try` (aborts whole job) while WOFOST failures are swallowed with no note in the result. |
| A9 | minor | `api/schemas.py:138-144`; `runner.py:90-99` | `crops=()` yields a zero-crop job that still downloads climate + soil; unknown crop or GCM surfaces as a failed job with traceback rather than a 422. |
| A10 | minor | `data/agera5.py:172`, `candcs_m6.py:250`, `soilgrids.py:205` | Dataset/raster handles never closed (28 NetCDF, 15 OPeNDAP, 42 GDAL handles per load); on Windows these lock cache files. |
| A11 | minor | `crop_models/wofost_runner.py:111` | `F821 Undefined name WeatherDataProvider` in an annotation. No runtime crash (PEP 563), but `typing.get_type_hints()` raises `NameError`, mypy sees `Any`, and `ruff check` fails → lint-gate blocker. |
| A12 | minor | `validation/statcan_fcrs.py:87,105` | `urlopen` without timeout; 60 MB CSV re-parsed on every call. |

### 2.3 Frontend

| # | Sev | Location | Finding |
|---|---|---|---|
| F1 | major | `app/lib/api.ts:184-202` | Stale-poll race: abort is checked only *before* `getJob`; a late response writes the old job's view over the new job's. If the signal is already aborted when the sleep promise is built, the promise never settles. Abort listeners accumulate per iteration. |
| F2 | major | `app/lib/api.ts:172-204` | Polling has no max attempts/timeout — combined with A4, a stuck job polls forever. |
| F3 | minor | `app/page.tsx:162-165` | Compare mode: if side A fails, side B keeps polling and controls stay disabled until B finishes. |
| F4 | minor | `BboxControl.tsx:41-71`; `ScenarioControl.tsx:171,183` | `parseFloat("")`/`parseInt("")` → NaN into state → NaN coordinates sent to MapLibre. No client-side check of min<max, ≤5° side, ≤30-yr window. |
| F5 | minor | `ScenarioControl.tsx:101` | Uncontrolled `defaultValue` for historical years desyncs from state on mode reset; `onBlur`-only commit. |
| F6 | minor | `api.ts:35-48` | GCM/SSP lists hand-mirror `GCM_REGISTRY`; no OpenAPI codegen. Zero-crop / null-grid / one-side-failed empty states not handled. |

Frontend↔backend field types otherwise **match** (`Bbox`, `JobView`, `EnvelopeResult`, etc.).

---

## 3. Performance

- **CDS N+1**: one CDS request per (variable × month × bbox) — 28 sequential queued requests per site-year; CDS accepts multi-month requests. Default first request on a fresh cache (3 years × 6 months × 3 vars = 54 requests) runs for a very long time with status `running` and no progress signal.
- **Redundant graph execution**: `_summarize_crop` computes `.mean()` on 3 score arrays and every factor array separately; plus `limit_idx.values` (`envelope.py:214`) forces an eager compute mid-pipeline; plus `_grid_for_crop`. Roughly 8–10 full dask graph executions per crop, each re-reading the monthly NetCDFs. One `.load()` on the indicators would fix it.
- `compute_all` is recomputed per crop though only GDD depends on the crop.
- `_compute_yields` re-opens the AgERA5 Apr–Oct slice per crop × year.
- AAFC ACI loaded with `masked=True` → uint8 classes become float32 with NaN (4× memory, 55 MB per year-tile) and `aci_label(int(NaN))` raises.
- No local cache for CanDCS-M6 (OPeNDAP each job) or SoilGrids; the 1 km SoilGrids tier is not used.
- `YAMLCropDataProvider()` re-unpickles the crop DB on every WOFOST call.

---

## 4. Validation / backtest assessment

### 4.1 What the code does today

`validation/hindcast.py::run_hindcast` is a **same-year simulation-vs-observation**
check: for each year, load AgERA5 Apr–Oct for the bbox → bbox-mean weather →
WOFOST-7.2 potential production → compare to StatCan Quebec provincial yield for the
same year. Metrics: n, RMSE, MAE, bias, NSE, Pearson r, OLS trend slopes, trend-sign
agreement, flags for known structural breaks (Bt corn 1996, RR soy 1997).

It is **not** the "train on ≤1980, predict 1990, confirm" design requested, and not the
frozen-baseline forward projection described in `docs/research/04-uncertainty-and-validation.md`
§B.1 (the doc's v0.2 status block acknowledges the substitution). There is nothing fitted,
so there is no hold-out. Only `corn_grain` is mapped to a StatCan label; soybean and canola
have WOFOST cultivars and StatCan series (`Soybeans` 1986–2025, `Canola (rapeseed)`
1996–2025) but cannot be hindcast. **There is no envelope-vs-observed-cropland (ACI)
validation anywhere** — `aci_code` in the YAML is inert.

### 4.2 Can it run now?

**No.** `data/cache/agera5/` is empty (the notebook `quebec_hindcast_corn.py:26-27`
claims 2018 is "fully present in the committed cache" — it is not). No CDS credentials
exist on this machine. Without them every year lands in `failures` and the report has
n = 0. The harness "runs" but proves nothing. StatCan parsing does work against the real
CSV (verified: Quebec corn 2018 = 9.441 t/ha, matching the doc).

### 4.3 What a real backtest of the *recommendation* would look like

The user's framing — "does the crop the tool would have recommended actually become
viable?" — is a test of the **Tier-1 envelope ranking**, not of WOFOST yield. A feasible
design with the data sources already integrated:

1. **Baseline period.** Compute the envelope per crop from AgERA5 (available 1979→) for a
   climate normal, e.g. 1981–1990, over a bbox or over Quebec's agricultural
   regions.
2. **Target period.** Compare the ranking/GAEZ class against observations 1991–2000:
   - *Provincial* (available now, no download): StatCan seeded/harvested area and yield
     per crop 1908–2025. Test: crops classified S1/S2 in the baseline should show
     non-trivial and growing seeded area in the target decade; crops classed S4/N should
     not. The soybean expansion in Quebec (area ≈0 before 1986, large by 2000s) and the
     northward march of grain corn are the natural positive cases; spring wheat's decline
     is a negative case.
   - *Spatial* (needs Earth Engine): AAFC ACI exists only from **2009**, so a spatial
     "predict 1990 cropland" is impossible; the earliest spatial test is baseline
     1991–2000 → observed cropland 2009–2020 (Brier / ROC-AUC of class vs presence).
3. **Temporal skill.** Repeat with a sliding baseline (1981–1990 → 1991–2000 → 2001–2010
   → 2011–2020) and check that *changes* in suitability rank predict *changes* in area
   share. That is the honest test of a climate-driven recommendation.
4. **Yield tier.** Keep the existing WOFOST hindcast as a secondary check, but with a
   year-appropriate CO₂ and with soybean/canola mapped.

**Prerequisites** (none met today): CDS credentials + ~40 site-years of AgERA5
(≈ 40 × 6 × 3 = 720 CDS requests with the current loader; ≈ 120 with a multi-month
request refactor); Earth Engine project for the spatial variant; fixing S1–S4 first,
otherwise the baseline itself is biased.

**What can be done offline right now** (no credentials): a StatCan-only descriptive
study of Quebec area/yield trends per catalogue crop, to establish the observation side
of the backtest and the expected sign of each test. That is preparatory, not validation.

---

## 5. Test coverage

- 128 tests, 87 % lines, **no test touches the network** (good). Loaders, indicators,
  envelope math, schemas, job store (incl. 100-thread concurrency) are well covered.
- **Zero coverage** of the real pipeline: `runner.py` is at 28 % — `_compute_envelope`,
  `_load_historical`, `_load_future`, `_compute_yields`, `_summarize_crop`,
  `_grid_for_crop` are untested; `predict_yields_by_year` and `run_hindcast` are
  untested. API tests patch the runner out. This is exactly where S1–S3 live.
- Tests are mostly plumbing/arithmetic. A few are scientifically meaningful (corn at
  preference optimum → 1.0; 60 °C → 0; NSE vs Pearson under constant bias). Absent: a
  known Quebec bbox with realistic climate ranking corn/soy S1/S2; a warming scenario
  shifting scores plausibly; any test of the Apr–Sep window semantics.
- `test_rank_crops_returns_all` encodes a scientific misuse (S5).
- `test_aafc_aci` only checks the four staple legend codes, so S8 is invisible.
- `.pyc` files under `notebooks/__pycache__` show notebooks were once collected by pytest
  under Python 3.11.

---

## 6. Documentation and process drift

- **README.md:10-11** — "Phase 1 — Research. No application code yet." False; 20+
  commits titled Phase 2/3. Points to a plan file outside the repo. Promises
  Recharts/Visx fan charts that are not in `package.json`.
- **docs/research/README.md** — all five deliverables marked "Stub"; they are 144–1063
  lines with no TODOs.
- **ADRs contradicted by code** (no superseding ADR, contrary to `CONTRIBUTING.md:15-16`):

  | ADR | Says | Code |
  |---|---|---|
  | 0001, 0004 | PostGIS; `arq` workers | No DB anywhere; in-memory dict; `BackgroundTasks` |
  | 0004 | Zarr caches for all sources; `scripts/` with checksums | NetCDF cache for AgERA5 only; CanDCS/SoilGrids uncached; `scripts/` empty |
  | 0005 | Every request runs 3–4 SSPs, ≥5 GCMs, ensemble fan, "no single-scenario point estimates anywhere in the UI" | API accepts one GCM × one SSP; UI shows point estimates + A/B compare; `uncertainty/` empty |
  | 0005 | 7 candidate GCMs, final list to be appended | 5 GCMs, ADR never amended |
  | 0003 | Water-limited WOFOST 8.1 default; `soil_translator` | `Wofost72_PP` only; module absent |
  | 0002 | Daymet, AHCCD, CanGRD, NEX-GDDP, CHELSA cross-checks | None |
  | 03-methodology | ~2,500 ECOCROP species; monthly weighting; xclim | 4 YAML crops; season aggregates; xclim unused |

- **CONTRIBUTING.md** commitments not honoured: ruff/format before commit (130/244
  errors, 24 unformatted files), `mypy --strict` (unrunnable), CLI scripts under
  `scripts/` (empty), "main always passes CI" (no CI), loader-test rule (true for
  loaders, false for runner).
- **frontend/README.md** layout diagram shows `components/`, `lib/`, `public/` at
  `frontend/` root; actual paths are `app/components/`, `app/lib/`; `public/` absent.

---

## 7. Maturity assessment

| Dimension | Level | Evidence |
|---|---|---|
| Architecture | Prototype | Clear module boundaries and a good `DataSource` ABC, but three of seven packages are empty and the API bypasses the designed job/storage layer. |
| Scientific correctness | Not yet trustworthy | S1–S4 bias every result; frost/photoperiod/cycle-max unused; GDD non-standard; CO₂ fixed; no ensemble. |
| Validation | None achieved | Harness exists but cannot run from this checkout; design does not test the recommendation; no spatial validation. |
| Data engineering | Fragile | Cache poisoning, no versioning in cache keys, write races, no cache for 2 of 4 sources, N+1 remote requests. |
| API robustness | Dev-only | Traceback leak, unbounded inputs, unbounded memory, no job lifecycle. |
| Frontend | Solid MVP | Builds/lints/types clean; polling race and no empty states. |
| Tests | Good unit hygiene, hollow integration | 87 % lines but 0 % of the real-data path. |
| Tooling/process | Weak | No CI, no pre-commit config, mypy broken, lint red, no Docker, no dashboard manifest. |
| Documentation | Stale and over-promising | See §6. |

Overall: **TRL 3–4 / early prototype.** The foundations (loaders, envelope math, WOFOST
adapter, StatCan parser) are a reasonable base; the gap to the stated goal is in
validation, uncertainty, and operational robustness, not in more UI.

---

## 8. Critical missing features (ordered by impact on the stated goal)

1. **Multi-GCM / multi-SSP ensemble with uncertainty** — the core differentiator (ADR
   0005). Loader already returns `(ssp, gcm, …)` dims; the runner throws them away
   (`.isel(gcm=0, ssp=0)`). No Hawkins–Sutton decomposition, no fan chart.
2. **A recommendation backtest** as in §4.3 — without it the tool has no demonstrated
   skill. Needs the StatCan area series (present), AgERA5 history (credentials), and
   ideally ACI 2009→ (Earth Engine).
3. **Correct precipitation/water logic** — either annual precipitation from a full-year
   load, or growing-season thresholds recalibrated; longer term, water-limited WOFOST
   (`Wofost72_WLP_FD`) with SoilGrids-derived hydraulic parameters (ADR 0003).
4. **No-data semantics** — NaN must propagate to score/class/limiting factor and be
   excluded from region means; the frontend needs a "no data" colour.
5. **Frost / kill temperature, photoperiod, cycle-length** actually consumed by the
   envelope; GDD with an upper cap (or CHU for corn) and a proper frost-free-period
   length.
6. **Year-appropriate CO₂ and crop-specific moisture** in WOFOST; soybean/canola/wheat
   in the hindcast.
7. **Job lifecycle**: queue with concurrency cap, TTL/eviction, timeout, persistence
   (Redis/`arq` or SQLite), sanitised errors.
8. **Caching layer**: Zarr or NetCDF cache for CanDCS-M6 and SoilGrids (1 km tier),
   multi-month CDS requests, atomic writes, version/selector in cache keys.
9. **Broader crop catalogue** (potatoes, barley, oats, forages, blueberries are Quebec
   staples with StatCan/ACI series) — 4 crops cannot produce a meaningful "which crops
   become favourable" answer.
10. **Regional granularity**: Quebec agricultural regions (CAR/MRC polygons) instead of a
    free bbox, so results can be joined to StatCan/Census geographies for validation.
11. **CI, pre-commit, mypy fix, `project-dashboard.json`, README/ADR refresh.**

---

## 9. Recommended next steps

**Fix run (size M, backend):** S1, S2, S3, S4, S6, A1, A2, A6, A11, plus a regression
test for `_compute_envelope` with a synthetic Apr–Sep dataset. These are small, sharply
bounded changes that remove the known biases before any validation is attempted.

**Validation run (needs human input):** obtain CDS API credentials (free registration),
decide the bbox/regions and decades, then implement the §4.3 backtest as a CLI under
`scripts/` with the StatCan area-share comparison. Expect hours of CDS queue time for the
first download; refactor `agera5.py` to multi-month requests first.

**Housekeeping (size S, infra/docs):** ruff `--fix`, format, `python_version = "3.12"`
for mypy, add CI + pre-commit, add `project-dashboard.json` (ports 8008/3232), rewrite
README status, amend or supersede ADRs 0001/0003/0004/0005, unmark research docs as
"Stub".

---

## Appendix A — StatCan 32100359 facts for Quebec (verified against the local CSV)

- Crop labels relevant to the catalogue: `Corn for grain` (yield 1908–2025),
  `Wheat, spring` (1908–2025), `Soybeans` (1986–2025), `Canola (rapeseed)` (1996–2025).
  45 labels in total incl. `Corn for silage`, `Barley`, `Oats`, `Tame hay`.
- Dispositions: average yield (kg/ha, bu/ac), seeded area, harvested area (null for
  ~half the years), production (t, bu), farm price (to 2017), total farm value (to 1984).
- Quebec corn: 2018 = 9 441 kg/ha; 2024 = 10 176; 2025 = 8 855.
- `CROP_STATCAN_LABEL` must use `Canola (rapeseed)`, not `Canola`.

## Appendix B — Files reviewed

`backend/aigriculture/**/*.py` (all 27 modules), `backend/tests/*.py` (10 files),
`backend/notebooks/exploratory/*.py`, `frontend/app/**`, `frontend/package.json`,
`next.config.mjs`, `tsconfig.json`, `pyproject.toml`, `.gitignore`, `README.md`,
`CONTRIBUTING.md`, `docs/decisions/*.md`, `docs/research/*.md`,
`data/crops/quebec_staples.yaml`, `data/cache/statcan/32100359.csv` (queried).
`.env` and `.env.local` were not opened.
