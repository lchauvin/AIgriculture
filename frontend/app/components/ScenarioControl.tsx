"use client";

import {
  AVAILABLE_GCMS,
  AVAILABLE_SSPS,
  type FutureScenario,
  type HistoricalScenario,
  type Scenario,
  type Ssp,
} from "@/app/lib/api";

interface ScenarioControlProps {
  scenario: Scenario;
  onChange: (scenario: Scenario) => void;
  disabled?: boolean;
}

const DEFAULT_HISTORICAL: HistoricalScenario = {
  kind: "historical",
  years: [2017, 2018, 2019],
};

const DEFAULT_FUTURE: FutureScenario = {
  kind: "future",
  gcm: "CanESM5",
  ssp: "ssp245",
  start_year: 2049,
  end_year: 2051,
};

const INPUT_CLASS =
  "rounded border border-slate-600 bg-slate-900 px-2 py-1 font-mono text-sm text-slate-100 disabled:opacity-50";

export default function ScenarioControl({
  scenario,
  onChange,
  disabled,
}: ScenarioControlProps) {
  return (
    <div className="flex flex-col gap-3">
      {/* Tab toggle: historical vs future. */}
      <div className="flex rounded border border-slate-600 p-0.5 text-sm">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(DEFAULT_HISTORICAL)}
          className={`flex-1 rounded px-3 py-1 transition ${
            scenario.kind === "historical"
              ? "bg-slate-600 text-slate-100"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Historical
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(DEFAULT_FUTURE)}
          className={`flex-1 rounded px-3 py-1 transition ${
            scenario.kind === "future"
              ? "bg-slate-600 text-slate-100"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Future
        </button>
      </div>

      {scenario.kind === "historical" ? (
        <HistoricalInputs
          scenario={scenario}
          onChange={onChange}
          disabled={disabled}
        />
      ) : (
        <FutureInputs
          scenario={scenario}
          onChange={onChange}
          disabled={disabled}
        />
      )}
    </div>
  );
}

function HistoricalInputs({
  scenario,
  onChange,
  disabled,
}: {
  scenario: HistoricalScenario;
  onChange: (s: Scenario) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-col text-xs text-slate-400">
      <span className="mb-1 uppercase tracking-wider">years (comma-separated)</span>
      <input
        type="text"
        disabled={disabled}
        defaultValue={scenario.years.join(", ")}
        onBlur={(e) => {
          const ys = e.target.value
            .split(",")
            .map((s) => parseInt(s.trim(), 10))
            .filter((n) => Number.isFinite(n));
          if (ys.length) onChange({ kind: "historical", years: ys });
        }}
        className={INPUT_CLASS}
      />
      <span className="mt-1 text-slate-500">AgERA5 reanalysis, 1979–present.</span>
    </label>
  );
}

function FutureInputs({
  scenario,
  onChange,
  disabled,
}: {
  scenario: FutureScenario;
  onChange: (s: Scenario) => void;
  disabled?: boolean;
}) {
  const set = (patch: Partial<FutureScenario>) =>
    onChange({ ...scenario, ...patch });

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col text-xs text-slate-400">
        <span className="mb-1 uppercase tracking-wider">climate model (GCM)</span>
        <select
          disabled={disabled}
          value={scenario.gcm}
          onChange={(e) => set({ gcm: e.target.value })}
          className={INPUT_CLASS}
        >
          {AVAILABLE_GCMS.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col text-xs text-slate-400">
        <span className="mb-1 uppercase tracking-wider">emissions pathway (SSP)</span>
        <select
          disabled={disabled}
          value={scenario.ssp}
          onChange={(e) => set({ ssp: e.target.value as Ssp })}
          className={INPUT_CLASS}
        >
          {AVAILABLE_SSPS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col text-xs text-slate-400">
          <span className="mb-1 uppercase tracking-wider">start year</span>
          <input
            type="number"
            disabled={disabled}
            min={2015}
            max={2100}
            value={scenario.start_year}
            onChange={(e) => set({ start_year: parseInt(e.target.value, 10) })}
            className={INPUT_CLASS}
          />
        </label>
        <label className="flex flex-col text-xs text-slate-400">
          <span className="mb-1 uppercase tracking-wider">end year</span>
          <input
            type="number"
            disabled={disabled}
            min={2015}
            max={2100}
            value={scenario.end_year}
            onChange={(e) => set({ end_year: parseInt(e.target.value, 10) })}
            className={INPUT_CLASS}
          />
        </label>
      </div>

      <p className="text-xs text-amber-400/80">
        CanDCS-M6 projections stream from PAVICS — a multi-year future query
        can take ~1 minute.
      </p>
    </div>
  );
}
