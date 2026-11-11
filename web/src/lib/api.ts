// Types mirror the backend's Pydantic response schemas (api/app/schemas/). Keep them in sync.

/** `RackOut` */
export type Rack = {
  id: number;
  name: string;
  location: string;
};

/** Where a server's readings come from: the simulator, or rackmind-agent on a real machine. */
export type Source = "simulated" | "agent";

/** `ServerOut` */
export type Server = {
  id: number;
  rack_id: number;
  hostname: string;
  rack_unit: number; // vertical slot, U1 at the bottom
  source: Source;
};

/** `MetricOut` */
export type Metric = {
  id: number;
  server_id: number;
  timestamp: string; // ISO 8601 with timezone, e.g. "2026-10-25T08:30:09Z"
  // null: the server has no sensor for it (most real servers report neither)
  cpu_temp: number | null; // degrees Celsius
  power_w: number | null;
  cpu_usage_pct: number | null; // null on simulated readings from before it existed
  disk_used_pct: number;
  memory_used_pct: number;
  network_mbps: number;
};

/** The numeric fields of a Metric, i.e. what can be charted. */
export type MetricField = Exclude<keyof Metric, "id" | "server_id" | "timestamp">;

/** What opened an incident: a metric, or `heartbeat` when a real server stopped reporting. */
export type IncidentMetric = MetricField | "heartbeat";

/** `Role`, lowest to highest. Each role can do everything the roles before it can. */
export const ROLES = ["operator", "engineer", "admin"] as const;
export type Role = (typeof ROLES)[number];

/** `UserOut` */
export type User = {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
};

/** `UserBrief`: what any logged-in user sees about colleagues (from `/users/directory`). */
export type UserBrief = Pick<User, "id" | "full_name" | "role" | "is_active">;

export type Severity = "info" | "warning" | "critical";
export type IncidentStatus = "open" | "acknowledged" | "resolved";

/** `IncidentOut` */
export type Incident = {
  id: number;
  server_id: number;
  title: string;
  metric_name: IncidentMetric;
  severity: Severity;
  status: IncidentStatus;
  assignee_id: number | null;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  recovered_at: string | null; // when metrics looked normal again (cleared if not anymore)
  recovery_suggested: boolean;
};

/** `CommentOut` */
export type Comment = {
  id: number;
  author_id: number;
  body: string;
  created_at: string;
};

/** `AuditEventOut`: one line of an incident's history. */
export type AuditEvent = {
  id: number;
  actor_id: number | null; // null: done by the system (detector)
  action: string; // e.g. "incident.acknowledged"
  details: Record<string, unknown>;
  created_at: string;
};

/** `IncidentDetail` */
export type IncidentDetail = {
  incident: Incident;
  comments: Comment[];
  history: AuditEvent[];
};

export type DiagnosisStatus = "pending" | "succeeded" | "failed";
export type DiagnosisErrorKind =
  "not_configured" | "timeout" | "rate_limited" | "api_error" | "invalid_output";

/** `DiagnosisOut`: the AI's suggestion for one incident (engineers and admins only). */
export type Diagnosis = {
  status: DiagnosisStatus;
  model: string | null;
  probable_cause: string | null;
  confidence: number | null; // 0-1
  recommended_steps: string[];
  evidence: { metric: MetricField; observation: string }[];
  error: DiagnosisErrorKind | null;
  error_detail: string | null;
  latency_ms: number | null;
  created_at: string;
  finished_at: string | null;
  feedback: { helpful: number; not_helpful: number; mine: boolean | null };
};

/** `SimulationStatus`: is anyone in Simulation mode (so the simulator is running)? */
export type SimulationStatus = { active: boolean };

/** `IncidentEvent`: what the live stream (`/stream`) sends when an incident changes. */
export type IncidentEvent = {
  action: string;
  incident: Incident;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/**
 * Not logged in (or the session expired): go to the login page, then come back here.
 * The proxy (src/proxy.ts) only checks that a cookie exists; the API is what decides.
 */
function redirectToLogin() {
  const { pathname, search } = window.location;
  if (pathname === "/login") return;
  // Outside React (no router here), and a full load clears data cached for the old session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(pathname + search)}`);
}

/** FastAPI puts a readable message in `detail` (a string, or a list for validation errors). */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return "Some fields are not valid.";
  } catch {
    // not JSON: fall through
  }
  return `Request failed (${response.status})`;
}

async function handle<T>(response: Response): Promise<T> {
  if (response.status === 401) redirectToLogin();
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * GET a backend path through the Next.js proxy (`/api/...`, see next.config.ts).
 * The session cookie is sent automatically: same origin, and JavaScript never touches it.
 */
export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(`/api${path}`));
}

/** POST / PUT / PATCH / DELETE, with an optional JSON body. Throws `ApiError` on failure. */
export async function apiSend<T>(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(response);
}
