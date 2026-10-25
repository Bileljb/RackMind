// Display-only temperature bands for the rack grid. These do NOT create incidents:
// anomaly detection is a separate backend job (Phase 4).

export type TempBand = "normal" | "warm" | "hot" | "critical" | "stale";

export const WARM_C = 60;
export const HOT_C = 70;
export const CRITICAL_C = 80;
// The simulator reports every 5s; no reading for 30s means the data can't be trusted.
export const STALE_AFTER_MS = 30_000;

export function tempBand(
  cpuTemp: number | undefined,
  timestamp: string | undefined,
  now: number | null, // null: clock not read yet, so skip the staleness check
): TempBand {
  if (cpuTemp === undefined || timestamp === undefined) return "stale";
  if (now !== null && now - new Date(timestamp).getTime() > STALE_AFTER_MS) return "stale";
  if (cpuTemp >= CRITICAL_C) return "critical";
  if (cpuTemp >= HOT_C) return "hot";
  if (cpuTemp >= WARM_C) return "warm";
  return "normal";
}

export const BAND_LABEL: Record<TempBand, string> = {
  normal: "Normal",
  warm: `Warm ≥ ${WARM_C} °C`,
  hot: `Hot ≥ ${HOT_C} °C`,
  critical: `Critical ≥ ${CRITICAL_C} °C`,
  stale: "No recent data",
};
