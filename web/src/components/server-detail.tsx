"use client";

import Link from "next/link";
import { useState } from "react";

import { BandBadge } from "@/components/band-badge";
import { MetricChart, type MetricSpec } from "@/components/metric-chart";
import { ErrorPanel, LiveIndicator, Skeleton, StaleBanner } from "@/components/states";
import { ApiError, type Metric } from "@/lib/api";
import { POLL_INTERVAL_MS, useMetricHistory, useRacks, useServer } from "@/lib/hooks";
import { tempBand } from "@/lib/temperature";
import { useNow } from "@/lib/use-now";

const METRICS: MetricSpec[] = [
  { field: "cpu_temp", title: "CPU temperature", unit: "°C" },
  { field: "power_w", title: "Power draw", unit: "W" },
  { field: "memory_used_pct", title: "Memory used", unit: "%", domain: [0, 100] },
  { field: "disk_used_pct", title: "Disk used", unit: "%", domain: [0, 100] },
  { field: "network_mbps", title: "Network", unit: "Mbps" },
];

const RANGES = [
  { minutes: 15, label: "15m" },
  { minutes: 60, label: "1h" },
  { minutes: 360, label: "6h" },
  { minutes: 1440, label: "24h" },
];

const TABLE_ROWS = 12; // one minute of readings

export function ServerDetail({ serverId }: { serverId: number }) {
  const [minutes, setMinutes] = useState(60);
  const server = useServer(serverId);
  const racks = useRacks();
  const history = useMetricHistory(serverId, minutes);
  const now = useNow(POLL_INTERVAL_MS);

  if (server.error instanceof ApiError && server.error.status === 404) {
    return <NotFound />;
  }
  if (server.error) {
    return (
      <ErrorPanel message="Could not load this server." onRetry={() => void server.mutate()} />
    );
  }

  const rack = racks.data?.find((r) => r.id === server.data?.rack_id);
  const metrics = history.data ?? [];
  const latest = metrics.at(-1);

  return (
    <>
      <BackLink />
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          {server.data ? (
            <h1 className="text-xl font-semibold">{server.data.hostname}</h1>
          ) : (
            <Skeleton className="h-7 w-40" />
          )}
          <p className="mt-1 flex flex-wrap items-center gap-x-3 text-sm text-ink-2">
            {rack && server.data && (
              <span>
                Rack {rack.name} · U{server.data.rack_unit} · {rack.location}
              </span>
            )}
            {history.data && (
              <BandBadge band={tempBand(latest?.cpu_temp, latest?.timestamp, now)} />
            )}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <LiveIndicator latest={latest?.timestamp} live={!history.error} />
          <RangePicker value={minutes} onChange={setMinutes} />
        </div>
      </header>

      <StaleBanner show={Boolean(history.error && history.data)} />
      {history.error && !history.data ? (
        <ErrorPanel
          message="Could not load metric history."
          onRetry={() => void history.mutate()}
        />
      ) : !history.data ? (
        <ChartsSkeleton />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {METRICS.map((spec) => (
              <MetricChart key={spec.field} spec={spec} metrics={metrics} />
            ))}
          </div>
          <RecentReadings metrics={metrics} />
        </>
      )}
    </>
  );
}

function RangePicker({ value, onChange }: { value: number; onChange: (minutes: number) => void }) {
  return (
    <div
      role="group"
      aria-label="Time range"
      className="flex rounded-md border border-line bg-surface p-0.5 text-sm"
    >
      {RANGES.map((range) => (
        <button
          key={range.minutes}
          type="button"
          aria-pressed={value === range.minutes}
          onClick={() => onChange(range.minutes)}
          className={`rounded px-2.5 py-1 ${value === range.minutes ? "bg-page font-medium text-ink" : "text-ink-2 hover:text-ink"}`}
        >
          {range.label}
        </button>
      ))}
    </div>
  );
}

/** The same data as the charts, as text: readable without hovering, and by screen readers. */
function RecentReadings({ metrics }: { metrics: Metric[] }) {
  const rows = metrics.slice(-TABLE_ROWS).reverse();
  if (rows.length === 0) return null;
  return (
    <details className="mt-6 rounded-xl border border-line bg-surface">
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
        Latest readings (table)
      </summary>
      <div className="overflow-x-auto">
        <table className="w-full text-sm tabular-nums">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Time</th>
              {METRICS.map((spec) => (
                <th key={spec.field} className="px-4 py-2 text-right font-medium">
                  {spec.title} ({spec.unit})
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id} className="border-t border-line">
                <td className="px-4 py-2 text-ink-2">
                  {new Date(m.timestamp).toLocaleTimeString()}
                </td>
                {METRICS.map((spec) => (
                  <td key={spec.field} className="px-4 py-2 text-right">
                    {m[spec.field].toFixed(1)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function BackLink() {
  return (
    <Link href="/" className="mb-4 inline-block text-sm text-ink-2 hover:text-ink">
      ← All racks
    </Link>
  );
}

function NotFound() {
  return (
    <>
      <BackLink />
      <div className="rounded-lg border border-line bg-surface p-6 text-sm">
        <h1 className="font-medium">Server not found</h1>
        <p className="mt-1 text-ink-2">
          There is no server with this id. Pick one from the rack grid.
        </p>
      </div>
    </>
  );
}

function ChartsSkeleton() {
  return (
    <div
      className="grid grid-cols-1 gap-4 lg:grid-cols-2"
      aria-busy="true"
      aria-label="Loading charts"
    >
      {METRICS.map((spec) => (
        <Skeleton key={spec.field} className="h-60" />
      ))}
    </div>
  );
}
