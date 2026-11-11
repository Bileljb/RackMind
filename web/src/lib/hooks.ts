"use client";

import useSWR, { type SWRConfiguration } from "swr";

import {
  apiGet,
  type Diagnosis,
  type Incident,
  type IncidentDetail,
  type IncidentStatus,
  type Metric,
  type Rack,
  type Server,
  type SimulationStatus,
  type Source,
  type User,
  type UserBrief,
} from "@/lib/api";

export const POLL_INTERVAL_MS = 5000;

// Live data: refetch every 5s. SWR keeps showing the previous data while refetching, and
// pauses polling while the tab is hidden.
const live: SWRConfiguration = { refreshInterval: POLL_INTERVAL_MS };

// Inventory (racks, servers) rarely changes: fetch once per page visit.
const stable: SWRConfiguration = { revalidateOnFocus: false };

// Incidents are pushed by the live stream (see use-incident-stream.ts), which refetches
// them the moment they change. The slow poll is only a safety net if the stream drops.
const pushed: SWRConfiguration = { refreshInterval: 30_000 };

/** Every SWR key that holds incident data starts with this, so the stream can refresh them. */
export const INCIDENTS_KEY_PREFIX = "/incidents";

/** `?source=agent` (Live mode) or `?source=simulated` (Simulation mode); "" for both. */
function sourceParam(source: Source | undefined): string {
  return source ? `source=${source}` : "";
}

function withQuery(path: string, ...params: string[]): string {
  const query = params.filter(Boolean).join("&");
  return query ? `${path}?${query}` : path;
}

export function useRacks(source?: Source) {
  return useSWR<Rack[]>(withQuery("/racks", sourceParam(source)), apiGet, stable);
}

export function useServers(source?: Source) {
  return useSWR<Server[]>(withQuery("/servers", sourceParam(source)), apiGet, stable);
}

export function useServer(serverId: number) {
  return useSWR<Server>(`/servers/${serverId}`, apiGet, stable);
}

export function useLatestMetrics(source?: Source) {
  return useSWR<Metric[]>(withQuery("/metrics/latest", sourceParam(source)), apiGet, live);
}

export const SIMULATION_STATUS_KEY = "/simulation/status";

/** Whether the simulator is running. Polled only while `enabled` (in Simulation mode). */
export function useSimulationStatus(enabled: boolean) {
  return useSWR<SimulationStatus>(enabled ? SIMULATION_STATUS_KEY : null, apiGet, live);
}

/**
 * Readings of one server over the last `minutes`. The key holds the window size, not the
 * timestamps: `start` is computed when each request is sent, so the window slides forward
 * on every poll without changing the key (a changing key would restart the request).
 */
export function useMetricHistory(serverId: number, minutes: number) {
  return useSWR<Metric[]>(
    [`/servers/${serverId}/metrics`, minutes],
    ([path, windowMinutes]: [string, number]) => {
      const start = new Date(Date.now() - windowMinutes * 60_000).toISOString();
      return apiGet<Metric[]>(`${path}?start=${encodeURIComponent(start)}`);
    },
    live,
  );
}

/** The logged-in user. `error.status === 401` means logged out (apiGet redirects to login). */
export function useMe() {
  return useSWR<User>("/auth/me", apiGet, stable);
}

/** Names and roles of all users, to show "Assigned to Jane" instead of an id. */
export function useDirectory() {
  return useSWR<UserBrief[]>("/users/directory", apiGet, stable);
}

/** Admin only: full accounts, for the user management page. */
export function useUsers() {
  return useSWR<User[]>("/users", apiGet);
}

/** Incidents, newest first. An empty `statuses` list means every status. */
export function useIncidents(statuses: IncidentStatus[] = [], source?: Source) {
  const statusParams = statuses.map((s) => `status=${s}`);
  const key = withQuery(INCIDENTS_KEY_PREFIX, "limit=200", sourceParam(source), ...statusParams);
  return useSWR<Incident[]>(key, apiGet, pushed);
}

export function useIncident(incidentId: number) {
  return useSWR<IncidentDetail>(`${INCIDENTS_KEY_PREFIX}/${incidentId}`, apiGet, pushed);
}

/**
 * The incident's AI diagnosis. Only requested when `enabled` (engineers and admins): other
 * roles would get 403. Its key starts with `/incidents`, so live events refresh it too.
 */
export function useDiagnosis(incidentId: number, enabled: boolean) {
  return useSWR<Diagnosis>(
    enabled ? `${INCIDENTS_KEY_PREFIX}/${incidentId}/diagnosis` : null,
    apiGet,
    pushed,
  );
}
