"use client";

import type { CropEnvelopeScore, EnvelopeResult } from "@/app/lib/api";

interface ResultPanelProps {
  result: EnvelopeResult;
  selectedCropId: string | null;
  onSelectCrop: (cropId: string | null) => void;
}

/**
 * Sorted crop table. Click a row to toggle its per-cell grid overlay
 * on the map. The selected row is highlighted; clicking it again clears
 * the selection.
 */
export default function ResultPanel({
  result,
  selectedCropId,
  onSelectCrop,
}: ResultPanelProps) {
  return (
    <div className="flex flex-col gap-3">
      <header>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Tier 1 envelope — {result.historical_years.join(", ")} historical
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Click a crop to overlay its per-cell suitability on the map. The
          ranking is by combined score (envelope × preference).
        </p>
      </header>

      <table className="w-full table-auto border-collapse text-sm">
        <thead className="text-xs uppercase tracking-wider text-slate-400">
          <tr className="border-b border-slate-700">
            <th className="py-2 text-left">crop</th>
            <th className="py-2 text-right">combined</th>
            <th className="py-2 text-right">envelope</th>
            <th className="py-2 text-right">preference</th>
            <th className="py-2 text-left">class</th>
            <th className="py-2 text-left">limited by</th>
          </tr>
        </thead>
        <tbody>
          {result.crops.map((c) => (
            <CropRow
              key={c.crop_id}
              crop={c}
              selected={c.crop_id === selectedCropId}
              onToggle={() =>
                onSelectCrop(c.crop_id === selectedCropId ? null : c.crop_id)
              }
            />
          ))}
        </tbody>
      </table>

      <ProvenanceList result={result} />
    </div>
  );
}

function CropRow({
  crop,
  selected,
  onToggle,
}: {
  crop: CropEnvelopeScore;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <tr
      onClick={onToggle}
      className={`cursor-pointer border-b border-slate-800 transition ${
        selected ? "bg-slate-700/60" : "hover:bg-slate-800/60"
      }`}
    >
      <td className="py-2">
        <div className="font-medium text-slate-100">{crop.common_name_en}</div>
        <div className="text-xs italic text-slate-500">
          {crop.scientific_name}
          {crop.common_name_fr ? ` · ${crop.common_name_fr}` : ""}
        </div>
      </td>
      <td className="py-2 text-right font-mono text-slate-100">
        {crop.combined_score.toFixed(2)}
      </td>
      <td className="py-2 text-right font-mono text-slate-300">
        {crop.envelope_score.toFixed(2)}
      </td>
      <td className="py-2 text-right font-mono text-slate-300">
        {crop.preference_score.toFixed(2)}
      </td>
      <td className="py-2">
        <GaezBadge cls={crop.gaez_class} />
      </td>
      <td className="py-2 text-xs text-slate-400">
        {crop.limiting_factor ?? "—"}
      </td>
    </tr>
  );
}

const GAEZ_COLOR: Record<string, string> = {
  S1: "bg-emerald-600 text-emerald-50",
  S2: "bg-lime-600 text-lime-50",
  S3: "bg-amber-600 text-amber-50",
  S4: "bg-orange-700 text-orange-50",
  N: "bg-rose-800 text-rose-50",
};

function GaezBadge({ cls }: { cls: string }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
        GAEZ_COLOR[cls] ?? "bg-slate-600 text-slate-50"
      }`}
    >
      {cls}
    </span>
  );
}

function ProvenanceList({ result }: { result: EnvelopeResult }) {
  if (!result.provenance.length) return null;
  return (
    <details className="text-xs text-slate-500">
      <summary className="cursor-pointer text-slate-400 hover:text-slate-200">
        Provenance — {result.provenance.length} source
        {result.provenance.length === 1 ? "" : "s"}
      </summary>
      <ul className="mt-2 space-y-1 font-mono">
        {result.provenance.map((p) => (
          <li key={p.fingerprint}>
            <span className="text-slate-300">{p.source}</span>{" "}
            <span className="text-slate-500">v{p.version}</span>{" "}
            <span className="text-slate-500">[{p.license}]</span>{" "}
            <span className="text-slate-600">
              fp:{p.fingerprint.slice(0, 12)}…
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
