import type { MetricField, UserBrief } from "@/lib/api";

export const METRIC_LABEL: Record<MetricField, string> = {
  cpu_temp: "CPU temperature",
  power_w: "Power draw",
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
