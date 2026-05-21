"use client";

import { useCallback } from "react";
import type { Bbox } from "@/app/lib/api";

interface BboxControlProps {
  bbox: Bbox;
  onChange: (bbox: Bbox) => void;
  disabled?: boolean;
}

/**
 * Four numeric inputs for the EPSG:4326 bbox. The Quebec MVP doesn't
 * need polygon drawing yet — a rectangle is enough — and numeric input
 * is reliable across screen readers and keyboard-only navigation,
 * which a draw-on-map UI is not.
 *
 * Constraints match the backend's EnvelopeRequest validator (each
 * side ≤ 5°, -180 ≤ minLon < maxLon ≤ 180, -90 ≤ minLat < maxLat ≤ 90).
 */
export default function BboxControl({ bbox, onChange, disabled }: BboxControlProps) {
  const [minLon, minLat, maxLon, maxLat] = bbox;

  const setField = useCallback(
    (idx: 0 | 1 | 2 | 3, value: number) => {
      const next: Bbox = [...bbox] as Bbox;
      next[idx] = value;
      onChange(next);
    },
    [bbox, onChange],
  );

  return (
    <fieldset disabled={disabled} className="grid grid-cols-2 gap-3">
      <label className="flex flex-col text-xs text-slate-400">
        <span className="mb-1 uppercase tracking-wider">min lon (°E)</span>
        <input
          type="number"
          step={0.1}
          value={minLon}
          onChange={(e) => setField(0, parseFloat(e.target.value))}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1 font-mono text-sm text-slate-100"
        />
      </label>
      <label className="flex flex-col text-xs text-slate-400">
        <span className="mb-1 uppercase tracking-wider">max lon (°E)</span>
        <input
          type="number"
          step={0.1}
          value={maxLon}
          onChange={(e) => setField(2, parseFloat(e.target.value))}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1 font-mono text-sm text-slate-100"
        />
      </label>
      <label className="flex flex-col text-xs text-slate-400">
        <span className="mb-1 uppercase tracking-wider">min lat (°N)</span>
        <input
          type="number"
          step={0.1}
          value={minLat}
          onChange={(e) => setField(1, parseFloat(e.target.value))}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1 font-mono text-sm text-slate-100"
        />
      </label>
      <label className="flex flex-col text-xs text-slate-400">
        <span className="mb-1 uppercase tracking-wider">max lat (°N)</span>
        <input
          type="number"
          step={0.1}
          value={maxLat}
          onChange={(e) => setField(3, parseFloat(e.target.value))}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1 font-mono text-sm text-slate-100"
        />
      </label>
    </fieldset>
  );
}
