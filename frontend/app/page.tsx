"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import BboxControl from "@/app/components/BboxControl";
import ComparisonPanel, {
  type OverlaySide,
} from "@/app/components/ComparisonPanel";
import ResultPanel from "@/app/components/ResultPanel";
import ScenarioControl from "@/app/components/ScenarioControl";
import {
  ApiError,
  api,
  pollJob,
  type Bbox,
  type EnvelopeResult,
  type HealthResponse,
  type JobView,
  type Scenario,
} from "@/app/lib/api";

// MapLibre needs browser globals; load it client-only with no SSR.
const MapView = dynamic(() => import("@/app/components/MapView"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-500">
      loading map…
    </div>
  ),
});

const DEFAULT_BBOX: Bbox = [-74.0, 45.0, -72.5, 46.0];
const DEFAULT_SCENARIO: Scenario = {
  kind: "historical",
  years: [2017, 2018, 2019],
};
// Default comparison side (B) — a mid-century middle-of-the-road future,
// so the out-of-the-box compare run shows present vs ~2050.
const DEFAULT_SCENARIO_B: Scenario = {
  kind: "future",
  gcm: "CanESM5",
  ssp: "ssp245",
  start_year: 2049,
  end_year: 2051,
};

type Mode = "single" | "compare";

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [bbox, setBbox] = useState<Bbox>(DEFAULT_BBOX);
  const [mode, setMode] = useState<Mode>("single");
  const [scenario, setScenario] = useState<Scenario>(DEFAULT_SCENARIO);
  const [scenarioB, setScenarioB] = useState<Scenario>(DEFAULT_SCENARIO_B);
  const [includeYield, setIncludeYield] = useState(false);
  const [job, setJob] = useState<JobView | null>(null);
  const [jobB, setJobB] = useState<JobView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCropId, setSelectedCropId] = useState<string | null>(null);
  const [overlaySide, setOverlaySide] = useState<OverlaySide>("B");
  const pollAbort = useRef<AbortController | null>(null);

  // Health check on mount so the user knows up-front whether the
  // backend is reachable.
  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  // Cancel any in-flight polling when the component unmounts.
  useEffect(() => {
    return () => pollAbort.current?.abort();
  }, []);

  const isRunning =
    isJobRunning(job) || (mode === "compare" && isJobRunning(jobB));

  const resultA: EnvelopeResult | null =
    job?.status === "succeeded" ? job.result : null;
  const resultB: EnvelopeResult | null =
    jobB?.status === "succeeded" ? jobB.result : null;
  // Single-mode rendering (map extent, ResultPanel) keys off scenario A.
  const result = resultA;

  // In compare mode the map overlays one side at a time; in single mode
  // it's always scenario A.
  const overlayResult =
    mode === "compare" && overlaySide === "B" ? resultB : resultA;

  const selectedGrid = useMemo(() => {
    if (!overlayResult?.grids || !selectedCropId) return null;
    return overlayResult.grids.find((g) => g.crop_id === selectedCropId) ?? null;
  }, [overlayResult, selectedCropId]);

  // The bbox rectangle should frame the *actual data extent* when the
  // current bbox state matches whatever the result was computed for —
  // AgERA5 cells centered on e.g. lat 45.0 paint from 44.95 to 45.05,
  // so the heatmap spills half a cell past the requested bbox edges.
  // Once the user starts editing the bbox (by dragging on the map or
  // by typing new numbers) we fall back to their live bbox so the
  // rectangle tracks the drag instead of staying glued to the stale
  // grid extent.
  const displayBbox: Bbox = useMemo(() => {
    if (!result) return bbox;
    if (!bboxesApproxEqual(result.bbox, bbox)) return bbox;
    const grid = result.grids?.[0];
    if (!grid) return bbox;
    const [dLat, dLon] = grid.cell_size_deg;
    return [
      grid.lons[0] - dLon / 2,
      grid.lats[0] - dLat / 2,
      grid.lons[grid.lons.length - 1] + dLon / 2,
      grid.lats[grid.lats.length - 1] + dLat / 2,
    ];
  }, [result, bbox]);

  async function handleAnalyze() {
    setError(null);
    setSelectedCropId(null);
    pollAbort.current?.abort();
    const controller = new AbortController();
    pollAbort.current = controller;

    // Create + poll one envelope job, streaming updates into `setView`.
    // Yield (Tier 2 / WOFOST) is single-mode + historical only.
    const runOne = async (
      scn: Scenario,
      setView: (j: JobView) => void,
    ): Promise<void> => {
      const accepted = await api.createEnvelope({
        bbox,
        scenario: scn,
        include_grids: true,
        include_yield:
          mode === "single" && includeYield && scn.kind === "historical",
      });
      setView({
        job_id: accepted.job_id,
        status: "pending",
        created_at: new Date().toISOString(),
        started_at: null,
        completed_at: null,
        error: null,
        result: null,
      });
      await pollJob(accepted.job_id, {
        signal: controller.signal,
        onUpdate: setView,
      });
    };

    try {
      if (mode === "single") {
        setJobB(null);
        await runOne(scenario, setJob);
      } else {
        // Run both scenarios concurrently over the same region.
        await Promise.all([
          runOne(scenario, setJob),
          runOne(scenarioB, setJobB),
        ]);
      }
    } catch (e) {
      if ((e as DOMException).name === "AbortError") return;
      const msg =
        e instanceof ApiError
          ? `API error ${e.status}: ${e.message}`
          : (e as Error).message;
      setError(msg);
    }
  }

  function switchMode(next: Mode) {
    if (next === mode) return;
    setMode(next);
    setSelectedCropId(null);
  }

  return (
    <main className="flex h-screen flex-col">
      <header className="border-b border-slate-700 bg-slate-900 px-6 py-4">
        <h1 className="text-xl font-bold text-slate-100">AIgriculture</h1>
        <p className="text-xs text-slate-400">
          Climate-adaptive crop recommendation — Tier 1 envelope over Quebec.
        </p>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          // CSS-native horizontal resize handle (corner of the aside).
          // ``minWidth`` keeps the form usable; ``maxWidth`` keeps the
          // map visible. MapLibre's ResizeObserver picks up the change
          // and re-fits the canvas automatically.
          style={{
            resize: "horizontal",
            overflow: "auto",
            width: 420,
            minWidth: 320,
            maxWidth: 720,
          }}
          className="flex flex-col gap-5 border-r border-slate-700 bg-slate-900 p-6"
        >
          <ConnectionBadge health={health} error={healthError} />

          <ModeToggle mode={mode} onChange={switchMode} disabled={isRunning} />

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Region (EPSG:4326 bbox)
            </h2>
            <BboxControl bbox={bbox} onChange={setBbox} disabled={isRunning} />
            <p className="text-xs text-slate-500">
              Each side must be ≤ 5°. Default = southern Quebec.
              {mode === "compare" && " Both scenarios share this region."}
            </p>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              {mode === "compare" ? (
                <>
                  Scenario <span className="text-sky-400">A</span> (baseline)
                </>
              ) : (
                "Scenario"
              )}
            </h2>
            <ScenarioControl
              scenario={scenario}
              onChange={setScenario}
              disabled={isRunning}
            />
          </section>

          {mode === "compare" && (
            <section className="flex flex-col gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                Scenario <span className="text-amber-400">B</span> (comparison)
              </h2>
              <ScenarioControl
                scenario={scenarioB}
                onChange={setScenarioB}
                disabled={isRunning}
              />
            </section>
          )}

          {mode === "single" && (
            <section className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={includeYield}
                  disabled={isRunning || scenario.kind !== "historical"}
                  onChange={(e) => setIncludeYield(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-900"
                />
                Estimate yield (Tier 2 / WOFOST)
              </label>
              <p className="text-xs text-slate-500">
                {scenario.kind === "historical"
                  ? "Runs the process-based crop model per crop. Adds a few seconds; spring wheat is unsupported in WOFOST."
                  : "Yield is historical-only — WOFOST needs solar radiation, which the CanDCS-M6 projections don't carry."}
              </p>
            </section>
          )}

          <button
            type="button"
            onClick={handleAnalyze}
            disabled={isRunning || !health}
            className="rounded bg-emerald-600 px-4 py-2 font-medium text-emerald-50 transition enabled:hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            {isRunning
              ? mode === "compare"
                ? "Comparing…"
                : "Analyzing…"
              : mode === "compare"
                ? "Compare"
                : "Analyze"}
          </button>

          {error && (
            <div className="rounded border border-rose-700 bg-rose-950/50 p-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          {mode === "single" ? (
            <>
              {job && <JobStatusBar job={job} />}
              {result && (
                <ResultPanel
                  result={result}
                  selectedCropId={selectedCropId}
                  onSelectCrop={setSelectedCropId}
                />
              )}
            </>
          ) : (
            <>
              {job && <JobStatusBar job={job} label="A" />}
              {jobB && <JobStatusBar job={jobB} label="B" />}
              {resultA && resultB && (
                <ComparisonPanel
                  resultA={resultA}
                  resultB={resultB}
                  selectedCropId={selectedCropId}
                  onSelectCrop={setSelectedCropId}
                  overlaySide={overlaySide}
                  onOverlaySideChange={setOverlaySide}
                />
              )}
            </>
          )}
        </aside>

        <section className="relative flex-1">
          <MapView
            bbox={displayBbox}
            gridOverlay={selectedGrid}
            // Interactive only when not running. Edits flow through
            // setBbox, which auto-syncs the sidebar inputs.
            onBboxChange={isRunning ? undefined : setBbox}
          />
        </section>
      </div>
    </main>
  );
}

// ---- subcomponents ---------------------------------------------------------

function ConnectionBadge({
  health,
  error,
}: {
  health: HealthResponse | null;
  error: string | null;
}) {
  if (error) {
    return (
      <div className="rounded border border-rose-700 bg-rose-950/50 px-3 py-2 text-xs text-rose-200">
        Backend unreachable: {error}
      </div>
    );
  }
  if (health) {
    return (
      <div className="rounded border border-emerald-800 bg-emerald-950/40 px-3 py-2 text-xs text-emerald-300">
        ✔ {health.service} v{health.version} reachable
      </div>
    );
  }
  return (
    <div className="rounded border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-400">
      Checking backend…
    </div>
  );
}

function bboxesApproxEqual(a: Bbox, b: Bbox, eps = 1e-6): boolean {
  for (let i = 0; i < 4; i++) {
    if (Math.abs(a[i] - b[i]) > eps) return false;
  }
  return true;
}

function isJobRunning(job: JobView | null): boolean {
  return job?.status === "pending" || job?.status === "running";
}

function ModeToggle({
  mode,
  onChange,
  disabled,
}: {
  mode: Mode;
  onChange: (mode: Mode) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex rounded border border-slate-600 p-0.5 text-sm">
      {(["single", "compare"] as const).map((m) => (
        <button
          key={m}
          type="button"
          disabled={disabled}
          onClick={() => onChange(m)}
          className={`flex-1 rounded px-3 py-1 capitalize transition ${
            mode === m
              ? "bg-slate-600 text-slate-100"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          {m === "single" ? "Single" : "Compare A/B"}
        </button>
      ))}
    </div>
  );
}

function JobStatusBar({ job, label }: { job: JobView; label?: string }) {
  const tone =
    job.status === "succeeded"
      ? "border-emerald-800 bg-emerald-950/40 text-emerald-300"
      : job.status === "failed"
        ? "border-rose-800 bg-rose-950/40 text-rose-300"
        : "border-sky-800 bg-sky-950/40 text-sky-300";
  return (
    <div className={`rounded border px-3 py-2 text-xs ${tone}`}>
      <div className="font-mono">
        {label ? `${label}: ` : ""}job {job.job_id.slice(0, 8)}… · status:{" "}
        {job.status}
      </div>
      {job.error && <div className="mt-1 whitespace-pre-wrap">{job.error}</div>}
    </div>
  );
}
