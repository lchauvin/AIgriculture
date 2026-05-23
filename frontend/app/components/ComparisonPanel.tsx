"use client";

import type {
  CropEnvelopeScore,
  EnvelopeResult,
  ProvenanceStamp,
} from "@/app/lib/api";
import {
  GaezBadge,
  ProvenanceList,
  describeScenario,
} from "@/app/components/ResultPanel";

export type OverlaySide = "A" | "B";

interface ComparisonPanelProps {
  resultA: EnvelopeResult;
  resultB: EnvelopeResult;
  selectedCropId: string | null;
  onSelectCrop: (cropId: string | null) => void;
  overlaySide: OverlaySide;
  onOverlaySideChange: (side: OverlaySide) => void;
}

/**
 * Side-by-side view of two scenarios over the same region. Scenario A is
 * the baseline (typically historical present); B is the comparison
 * (typically a future SSP projection). Rows keep A's combined-score order
 * (the backend already sorts each result desc) and surface the per-crop
 * shift (Δ = B − A). Clicking a row overlays that crop's grid on the map
 * for whichever side the overlay toggle selects.
 */
export default function ComparisonPanel({
  resultA,
  resultB,
  selectedCropId,
  onSelectCrop,
  overlaySide,
  onOverlaySideChange,
}: ComparisonPanelProps) {
  const bById = new Map(resultB.crops.map((c) => [c.crop_id, c]));
  const rows = resultA.crops.map((a) => ({ a, b: bById.get(a.crop_id) ?? null }));
  const mergedProvenance = dedupeProvenance([
    ...resultA.provenance,
    ...resultB.provenance,
  ]);

  return (
    <div className="flex flex-col gap-3">
      <header>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          A → B comparison
        </h2>
        <dl className="mt-1 space-y-0.5 text-xs">
          <div>
            <span className="font-semibold text-sky-400">A</span>{" "}
            <span className="text-slate-400">
              {describeScenario(resultA.scenario)}
            </span>
          </div>
          <div>
            <span className="font-semibold text-amber-400">B</span>{" "}
            <span className="text-slate-400">
              {describeScenario(resultB.scenario)}
            </span>
          </div>
        </dl>
        <p className="mt-1 text-xs text-slate-500">
          Δ is the change in combined score (B − A). Click a crop to overlay
          its per-cell suitability for the selected side.
        </p>
      </header>

      <OverlayToggle
        side={overlaySide}
        onChange={onOverlaySideChange}
        labelA={describeScenario(resultA.scenario)}
        labelB={describeScenario(resultB.scenario)}
      />

      <table className="w-full table-auto border-collapse text-sm">
        <thead className="text-xs uppercase tracking-wider text-slate-400">
          <tr className="border-b border-slate-700">
            <th className="py-2 text-left">crop</th>
            <th className="py-2 text-right text-sky-400">A</th>
            <th className="py-2 text-right text-amber-400">B</th>
            <th className="py-2 text-right">Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ a, b }) => (
            <ComparisonRow
              key={a.crop_id}
              a={a}
              b={b}
              selected={a.crop_id === selectedCropId}
              onToggle={() =>
                onSelectCrop(a.crop_id === selectedCropId ? null : a.crop_id)
              }
            />
          ))}
        </tbody>
      </table>

      <ProvenanceList stamps={mergedProvenance} />
    </div>
  );
}

function ComparisonRow({
  a,
  b,
  selected,
  onToggle,
}: {
  a: CropEnvelopeScore;
  b: CropEnvelopeScore | null;
  selected: boolean;
  onToggle: () => void;
}) {
  const delta = b ? b.combined_score - a.combined_score : null;
  return (
    <tr
      onClick={onToggle}
      className={`cursor-pointer border-b border-slate-800 transition ${
        selected ? "bg-slate-700/60" : "hover:bg-slate-800/60"
      }`}
    >
      <td className="py-2">
        <div className="font-medium text-slate-100">{a.common_name_en}</div>
        <div className="text-xs italic text-slate-500">
          {a.scientific_name}
          {a.common_name_fr ? ` · ${a.common_name_fr}` : ""}
        </div>
      </td>
      <ScoreCell crop={a} />
      <ScoreCell crop={b} />
      <td className="py-2 text-right">
        <DeltaCell d={delta} />
      </td>
    </tr>
  );
}

function ScoreCell({ crop }: { crop: CropEnvelopeScore | null }) {
  if (!crop) {
    return <td className="py-2 text-right text-slate-500">—</td>;
  }
  return (
    <td className="py-2 text-right">
      <div className="font-mono text-slate-100">
        {crop.combined_score.toFixed(2)}
      </div>
      <div className="mt-0.5">
        <GaezBadge cls={crop.gaez_class} />
      </div>
    </td>
  );
}

// Anything within ±EPS reads as "no meaningful change" — keeps tiny
// numerical wobble from being rendered as a confident up/down arrow.
const DELTA_EPS = 0.02;

function DeltaCell({ d }: { d: number | null }) {
  if (d === null) return <span className="text-slate-500">—</span>;
  const tone =
    d > DELTA_EPS
      ? "text-emerald-400"
      : d < -DELTA_EPS
        ? "text-rose-400"
        : "text-slate-400";
  const arrow = d > DELTA_EPS ? "▲" : d < -DELTA_EPS ? "▼" : "→";
  const sign = d > 0 ? "+" : "";
  return (
    <span className={`font-mono ${tone}`}>
      {arrow} {sign}
      {d.toFixed(2)}
    </span>
  );
}

function OverlayToggle({
  side,
  onChange,
  labelA,
  labelB,
}: {
  side: OverlaySide;
  onChange: (side: OverlaySide) => void;
  labelA: string;
  labelB: string;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-slate-400">Map overlay:</span>
      <div className="flex rounded border border-slate-600 p-0.5">
        <button
          type="button"
          title={labelA}
          onClick={() => onChange("A")}
          className={`rounded px-2 py-0.5 transition ${
            side === "A"
              ? "bg-sky-700 text-sky-50"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          A
        </button>
        <button
          type="button"
          title={labelB}
          onClick={() => onChange("B")}
          className={`rounded px-2 py-0.5 transition ${
            side === "B"
              ? "bg-amber-700 text-amber-50"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          B
        </button>
      </div>
    </div>
  );
}

function dedupeProvenance(stamps: ProvenanceStamp[]): ProvenanceStamp[] {
  const seen = new Set<string>();
  const out: ProvenanceStamp[] = [];
  for (const s of stamps) {
    if (seen.has(s.fingerprint)) continue;
    seen.add(s.fingerprint);
    out.push(s);
  }
  return out;
}
