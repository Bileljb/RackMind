import type { IncidentMetric, MetricField, UserBrief } from "@/lib/api";

export const METRIC_LABEL: Record<MetricField, string> = {
  cpu_temp: "CPU temperature",
  power_w: "Power draw",
  cpu_usage_pct: "CPU usage",
  disk_used_pct: "Disk used",
  memory_used_pct: "Memory used",
  network_mbps: "Network",
};

/** "26 Oct, 09:14" in the viewer's locale and time zone. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** A user's name from the directory; `null` means the system (the detector) did it. */
export function personName(directory: UserBrief[] | undefined, id: number | null): string {
  if (id === null) return "Detector";
  return directory?.find((u) => u.id === id)?.full_name ?? `User #${id}`;
}

/** What an incident is about: a metric's name, or "Not reporting" for a silent server. */
export const INCIDENT_METRIC_LABEL: Record<IncidentMetric, string> = {
  ...METRIC_LABEL,
  heartbeat: "Not reporting",
};

/** "just now", "40 s ago", "3 min ago", "2 h ago", "5 days ago". */
export function formatAgo(iso: string, now: number): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds} s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86_400)} days ago`;
}
