"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HealthResponse = {
  status: string;
  service: string;
  version: string;
  now: string;
};

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/health`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<HealthResponse>;
      })
      .then(setHealth)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="min-h-screen p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-slate-100">AIgriculture</h1>
        <p className="mt-1 text-slate-400">
          Climate-adaptive crop recommendation — select a region, see which
          crops fit its climate today and under future warming.
        </p>
      </header>

      <section className="rounded-lg border border-slate-700 bg-slate-800 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Backend connection
        </h2>
        {error ? (
          <p className="text-red-400">
            ✖ couldn&apos;t reach{" "}
            <code className="font-mono text-xs">{API_URL}</code>: {error}
          </p>
        ) : health ? (
          <p className="text-green-400">
            ✔ <code className="font-mono text-xs">{health.service}</code> v
            {health.version} reachable at{" "}
            <code className="font-mono text-xs">{API_URL}</code>
          </p>
        ) : (
          <p className="text-slate-400">checking…</p>
        )}
      </section>

      <section className="mt-8 rounded-lg border border-slate-700 bg-slate-800 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Next
        </h2>
        <p className="text-slate-300">
          Map of Quebec, polygon-draw, and crop-result panel land in the next
          commit. This page exists so we can verify the Next.js ↔ FastAPI wiring
          before introducing MapLibre.
        </p>
      </section>
    </main>
  );
}
