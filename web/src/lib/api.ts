// Types mirror the backend's Pydantic response schemas (api/app/schemas/). Keep them in sync.

/** `RackOut` */
export type Rack = {
  id: number;
  name: string;
  location: string;
};

/** `ServerOut` */
export type Server = {
  id: number;
  rack_id: number;
  hostname: string;
  rack_unit: number; // vertical slot, U1 at the bottom
};

/** `MetricOut` */
export type Metric = {
  id: number;
  server_id: number;
  timestamp: string; // ISO 8601 with timezone, e.g. "2026-10-25T08:30:09Z"
  cpu_temp: number; // degrees Celsius
  power_w: number;
  disk_used_pct: number;
  memory_used_pct: number;
  network_mbps: number;
};

/** The numeric fields of a Metric, i.e. what can be charted. */
export type MetricField = Exclude<keyof Metric, "id" | "server_id" | "timestamp">;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** GET a backend path through the Next.js proxy (`/api/...`, see next.config.ts). */
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}
