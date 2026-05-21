/**
 * Typed client for the AIgriculture FastAPI backend.
 *
 * Schemas mirror `backend/aigriculture/api/schemas.py`. Keep these in
 * lockstep — when a new field is added there, add it here too. Long-
 * term we should auto-generate from the OpenAPI spec, but hand-mirrored
 * is fine while the surface is small.
 */

export type Bbox = [number, number, number, number];
//                  minLon  minLat  maxLon  maxLat

export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export type GAEZClass = "S1" | "S2" | "S3" | "S4" | "N";

export type Ssp = "ssp126" | "ssp245" | "ssp370" | "ssp585";

export interface HistoricalScenario {
  kind: "historical";
  years: number[];
}

export interface FutureScenario {
  kind: "future";
  gcm: string;
  ssp: Ssp;
  start_year: number;
  end_year: number;
}

export type Scenario = HistoricalScenario | FutureScenario;

/** GCMs available in the backend's CanDCSM6Source.GCM_REGISTRY. */
export const AVAILABLE_GCMS = [
  "CanESM5",
  "MPI-ESM1-2-LR",
  "MIROC6",
  "GFDL-ESM4",
  "EC-Earth3",
] as const;

export const AVAILABLE_SSPS: { value: Ssp; label: string }[] = [
  { value: "ssp126", label: "SSP1-2.6 (strong mitigation)" },
  { value: "ssp245", label: "SSP2-4.5 (middle of the road)" },
  { value: "ssp370", label: "SSP3-7.0 (high)" },
  { value: "ssp585", label: "SSP5-8.5 (fossil-fuelled)" },
];

export interface EnvelopeRequest {
  bbox: Bbox;
  scenario?: Scenario;
  crops?: string[] | null;
  include_grids?: boolean;
}

export interface CropEnvelopeScore {
  crop_id: string;
  scientific_name: string;
  common_name_en: string;
  common_name_fr: string | null;
  envelope_score: number;
  preference_score: number;
  combined_score: number;
  gaez_class: GAEZClass;
  limiting_factor: string | null;
  per_factor_envelope: Record<string, number>;
}

export interface CropSuitabilityGrid {
  crop_id: string;
  lats: number[];
  lons: number[];
  cell_size_deg: [number, number];
  score_grid: Array<Array<number | null>>;
}

export interface ProvenanceStamp {
  source: string;
  version: string;
  fingerprint: string;
  license: string;
  citation_key: string;
}

export interface EnvelopeResult {
  bbox: Bbox;
  scenario: Scenario;
  crops: CropEnvelopeScore[];
  grids: CropSuitabilityGrid[] | null;
  provenance: ProvenanceStamp[];
}

export interface JobAccepted {
  job_id: string;
  status: "pending";
  poll_url: string;
}

export interface JobView {
  job_id: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  result: EnvelopeResult | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  now: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8008";

async function fetchJSON<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, init);
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(
      `${resp.status} ${resp.statusText}: ${body || "(empty body)"}`,
      resp.status,
    );
  }
  return resp.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export const api = {
  async health(): Promise<HealthResponse> {
    return fetchJSON<HealthResponse>("/api/v1/health");
  },

  async createEnvelope(req: EnvelopeRequest): Promise<JobAccepted> {
    return fetchJSON<JobAccepted>("/api/v1/envelope", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
  },

  async getJob(jobId: string): Promise<JobView> {
    return fetchJSON<JobView>(`/api/v1/jobs/${jobId}`);
  },
};

/**
 * Poll a job until it reaches a terminal status (succeeded/failed).
 *
 * Calls `onUpdate` after each poll so the UI can render intermediate
 * states. Returns the final view. Throws on network errors. Respects
 * the optional AbortSignal to allow cancellation when a component
 * unmounts.
 */
export async function pollJob(
  jobId: string,
  opts: {
    intervalMs?: number;
    signal?: AbortSignal;
    onUpdate?: (view: JobView) => void;
  } = {},
): Promise<JobView> {
  const { intervalMs = 2000, signal, onUpdate } = opts;
  // Initial fetch immediately so the UI shows "running" without
  // waiting a full poll interval.
  while (true) {
    if (signal?.aborted) {
      throw new DOMException("Polling aborted", "AbortError");
    }
    const view = await api.getJob(jobId);
    onUpdate?.(view);
    if (view.status === "succeeded" || view.status === "failed") {
      return view;
    }
    await new Promise<void>((resolve, reject) => {
      const t = setTimeout(resolve, intervalMs);
      signal?.addEventListener(
        "abort",
        () => {
          clearTimeout(t);
          reject(new DOMException("Polling aborted", "AbortError"));
        },
        { once: true },
      );
    });
  }
}
