"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import BboxControl from "@/app/components/BboxControl";
import ResultPanel from "@/app/components/ResultPanel";
import {
  ApiError,
  api,
  pollJob,
  type Bbox,
  type EnvelopeResult,
  type HealthResponse,
  type JobView,
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
const DEFAULT_YEARS = [2017, 2018, 2019];

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [bbox, setBbox] = useState<Bbox>(DEFAULT_BBOX);
  const [years, setYears] = useState<number[]>(DEFAULT_YEARS);
  const [job, setJob] = useState<JobView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCropId, setSelectedCropId] = useState<string | null>(null);
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
    job?.status === "pending" || job?.status === "running";

  const result: EnvelopeResult | null =
    job?.status === "succeeded" ? job.result : null;

  const selectedGrid = useMemo(() => {
    if (!result?.grids || !selectedCropId) return null;
    return result.grids.find((g) => g.crop_id === selectedCropId) ?? null;
  }, [result, selectedCropId]);

  // The bbox rectangle should always frame the *actual data extent*,
  // not the user's requested cell-center bbox. AgERA5 cells centered on
  // e.g. lat 45.0 paint from 44.95 to 45.05, so the heatmap spills
  // half a cell past the requested bbox edges. Once a result is in,
  // derive the cell-edge extent from any grid (all crops share the
  // same lat/lon coords). Before any result, fall back to the user's
  // requested bbox so the rectangle still tells them what they asked for.
  const displayBbox: Bbox = useMemo(() => {
    const grid = result?.grids?.[0];
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

    try {
      const accepted = await api.createEnvelope({
        bbox,
        historical_years: years,
        include_grids: true,
      });
      const initial: JobView = {
        job_id: accepted.job_id,
        status: "pending",
        created_at: new Date().toISOString(),
        started_at: null,
        completed_at: null,
        error: null,
        result: null,
      };
      setJob(initial);
      await pollJob(accepted.job_id, {
        signal: controller.signal,
        onUpdate: setJob,
      });
    } catch (e) {
      if ((e as DOMException).name === "AbortError") return;
      const msg =
        e instanceof ApiError
          ? `API error ${e.status}: ${e.message}`
          : (e as Error).message;
      setError(msg);
    }
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

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Region (EPSG:4326 bbox)
            </h2>
            <BboxControl bbox={bbox} onChange={setBbox} disabled={isRunning} />
            <p className="text-xs text-slate-500">
              Each side must be ≤ 5°. Default = southern Quebec.
            </p>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Historical years
            </h2>
            <YearsInput value={years} onChange={setYears} disabled={isRunning} />
          </section>

          <button
            type="button"
            onClick={handleAnalyze}
            disabled={isRunning || !health}
            className="rounded bg-emerald-600 px-4 py-2 font-medium text-emerald-50 transition enabled:hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            {isRunning ? "Analyzing…" : "Analyze"}
          </button>

          {error && (
            <div className="rounded border border-rose-700 bg-rose-950/50 p-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          {job && <JobStatusBar job={job} />}

          {result && (
            <ResultPanel
              result={result}
              selectedCropId={selectedCropId}
              onSelectCrop={setSelectedCropId}
            />
          )}
        </aside>

        <section className="relative flex-1">
          <MapView bbox={displayBbox} gridOverlay={selectedGrid} />
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

function YearsInput({
  value,
  onChange,
  disabled,
}: {
  value: number[];
  onChange: (years: number[]) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-col text-xs text-slate-400">
      <span className="mb-1 uppercase tracking-wider">comma-separated</span>
      <input
        type="text"
        disabled={disabled}
        defaultValue={value.join(", ")}
        onBlur={(e) => {
          const ys = e.target.value
            .split(",")
            .map((s) => parseInt(s.trim(), 10))
            .filter((n) => Number.isFinite(n));
          if (ys.length) onChange(ys);
        }}
        className="rounded border border-slate-600 bg-slate-900 px-2 py-1 font-mono text-sm text-slate-100 disabled:opacity-50"
      />
    </label>
  );
}

function JobStatusBar({ job }: { job: JobView }) {
  const tone =
    job.status === "succeeded"
      ? "border-emerald-800 bg-emerald-950/40 text-emerald-300"
      : job.status === "failed"
        ? "border-rose-800 bg-rose-950/40 text-rose-300"
        : "border-sky-800 bg-sky-950/40 text-sky-300";
  return (
    <div className={`rounded border px-3 py-2 text-xs ${tone}`}>
      <div className="font-mono">
        job {job.job_id.slice(0, 8)}… · status: {job.status}
      </div>
      {job.error && <div className="mt-1 whitespace-pre-wrap">{job.error}</div>}
    </div>
  );
}
