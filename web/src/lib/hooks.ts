"use client";

import useSWR, { type SWRConfiguration } from "swr";

import { apiGet, type Metric, type Rack, type Server } from "@/lib/api";

export const POLL_INTERVAL_MS = 5000;

// Live data: refetch every 5s. SWR keeps showing the previous data while refetching, and
// pauses polling while the tab is hidden.
const live: SWRConfiguration = { refreshInterval: POLL_INTERVAL_MS };

// Inventory (racks, servers) rarely changes: fetch once per page visit.
const stable: SWRConfiguration = { revalidateOnFocus: false };

export function useRacks() {
  return useSWR<Rack[]>("/racks", apiGet, stable);
}

export function useServers() {
  return useSWR<Server[]>("/servers", apiGet, stable);
}

export function useServer(serverId: number) {
  return useSWR<Server>(`/servers/${serverId}`, apiGet, stable);
}

export function useLatestMetrics() {
  return useSWR<Metric[]>("/metrics/latest", apiGet, live);
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
