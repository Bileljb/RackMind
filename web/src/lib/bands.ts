// Display-only bands for the rack grid. These do NOT create incidents: anomaly detection is
// a separate backend job, with its own limits.

import type { Metric } from "@/lib/api";

export type Band = "normal" | "warm" | "hot" | "critical" | "stale";

/** The metric a server is colored by, and where its bands start. */
export type Scale = {
  field: "cpu_temp" | "cpu_usage_pct";
  label: string;
  unit: string;
  warm: number;
  hot: number;
  critical: number;
};

export const TEMPERATURE: Scale = {
  field: "cpu_temp",
  label: "CPU temperature",
  unit: "°C",
  warm: 60,
  hot: 70,
  critical: 80,
};

// Hot and critical match the detector's CPU usage limits (90% / 98%).
export const CPU_USAGE: Scale = {
  field: "cpu_usage_pct",
  label: "CPU usage",
  unit: "%",
  warm: 70,
  hot: 90,
  critical: 98,
};

// Servers report every 5s; no reading for 30s means the data can't be trusted.
export const STALE_AFTER_MS = 30_000;

/** Temperature when the server has a sensor (simulated racks), CPU usage otherwise (VPSes). */
export function scaleFor(metric: Metric | undefined): Scale {
  return metric?.cpu_temp == null ? CPU_USAGE : TEMPERATURE;
}

export function bandOf(
  metric: Metric | undefined,
  now: number | null, // null: clock not read yet, so skip the staleness check
): Band {
  const value = metric?.[scaleFor(metric).field];
  if (metric === undefined || value == null) return "stale";
  if (now !== null && now - new Date(metric.timestamp).getTime() > STALE_AFTER_MS) return "stale";
  const scale = scaleFor(metric);
  if (value >= scale.critical) return "critical";
  if (value >= scale.hot) return "hot";
  if (value >= scale.warm) return "warm";
  return "normal";
}

/** "45.2 °C" or "12.0 %", the value a server is colored by. */
export function formatScaled(metric: Metric): string {
  const scale = scaleFor(metric);
  const value = metric[scale.field];
  return value == null ? "—" : `${value.toFixed(1)} ${scale.unit}`;
}

export const BAND_LABEL: Record<Band, string> = {
  normal: "Normal",
  warm: "Warm",
  hot: "Hot",
  critical: "Critical",
  stale: "No recent data",
};

/** "CPU temperature: warm ≥ 60, hot ≥ 70, critical ≥ 80 °C" */
export function scaleCaption(scale: Scale): string {
  return `${scale.label}: warm ≥ ${scale.warm}, hot ≥ ${scale.hot}, critical ≥ ${scale.critical} ${scale.unit}`;
}
