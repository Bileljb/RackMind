"use client";

import Link from "next/link";

import { BandBadge, BandIcon } from "@/components/band-badge";
import { ErrorPanel, LiveIndicator, Skeleton, StaleBanner } from "@/components/states";
import type { Metric, Rack, Server } from "@/lib/api";
import { POLL_INTERVAL_MS, useLatestMetrics, useRacks, useServers } from "@/lib/hooks";
import { BAND_LABEL, tempBand, type TempBand } from "@/lib/temperature";
import { useNow } from "@/lib/use-now";

const BANDS_IN_LEGEND: TempBand[] = ["normal", "warm", "hot", "critical", "stale"];

// Background tint per band: a light wash of the status color behind ink-colored text.
const CELL_TINT: Record<TempBand, string> = {
  normal: "bg-surface",
  warm: "bg-[color-mix(in_oklab,var(--status-warning)_18%,var(--surface))]",
  hot: "bg-[color-mix(in_oklab,var(--status-serious)_22%,var(--surface))]",
  critical: "bg-[color-mix(in_oklab,var(--status-critical)_24%,var(--surface))]",
  stale: "bg-page",
};

export function RackGrid() {
  const racks = useRacks();
  const servers = useServers();
  const latest = useLatestMetrics();
  const now = useNow(POLL_INTERVAL_MS);

  const firstError = racks.error ?? servers.error;
  if (firstError) {
    return (
      <ErrorPanel
        message="Could not load the rack inventory."
        onRetry={() => {
          void racks.mutate();
          void servers.mutate();
        }}
      />
    );
  }
  if (!racks.data || !servers.data || (!latest.data && !latest.error)) {
    return <RackGridSkeleton />;
  }

  const inventory = servers.data;
  const byServer = new Map((latest.data ?? []).map((m) => [m.server_id, m]));
  const bandOf = (server: Server) => {
    const metric = byServer.get(server.id);
    return tempBand(metric?.cpu_temp, metric?.timestamp, now);
  };
  const newest = (latest.data ?? []).reduce<string | undefined>(
    (max, m) => (max === undefined || m.timestamp > max ? m.timestamp : max),
    undefined,
  );

  return (
    <div>
      <StaleBanner show={Boolean(latest.error)} />
      <Summary servers={inventory} bandOf={bandOf} newest={newest} live={!latest.error} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {racks.data.map((rack) => (
          <RackColumn
            key={rack.id}
            rack={rack}
            servers={inventory.filter((s) => s.rack_id === rack.id)}
            byServer={byServer}
            bandOf={bandOf}
          />
        ))}
      </div>
      <Legend />
    </div>
  );
}

function Summary({
  servers,
  bandOf,
  newest,
  live,
}: {
  servers: Server[];
  bandOf: (server: Server) => TempBand;
  newest: string | undefined;
  live: boolean;
}) {
  const counts = new Map<TempBand, number>();
  for (const server of servers) {
    const band = bandOf(server);
    counts.set(band, (counts.get(band) ?? 0) + 1);
  }
  const shown = BANDS_IN_LEGEND.filter((band) => counts.has(band));
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2">
        {shown.map((band) => (
          <span key={band} className="inline-flex items-center gap-1.5">
            <BandIcon band={band} />
            <span className="font-semibold text-ink">{counts.get(band)}</span> {BAND_LABEL[band]}
          </span>
        ))}
      </p>
      <LiveIndicator latest={newest} live={live} />
    </div>
  );
}

function RackColumn({
  rack,
  servers,
  byServer,
  bandOf,
}: {
  rack: Rack;
  servers: Server[];
  byServer: Map<number, Metric>;
  bandOf: (server: Server) => TempBand;
}) {
  // Highest slot first, like looking at a real rack (U1 is at the bottom).
  const topDown = [...servers].sort((a, b) => b.rack_unit - a.rack_unit);
  return (
    <section
      className="rounded-xl border border-line bg-surface p-3"
      aria-label={`Rack ${rack.name}`}
    >
      <h2 className="mb-3 flex items-baseline justify-between px-1">
        <span className="font-semibold">{rack.name}</span>
        <span className="text-xs text-muted">{rack.location}</span>
      </h2>
      <ul className="flex flex-col gap-0.5">
        {topDown.map((server) => (
          <li key={server.id}>
            <ServerCell server={server} metric={byServer.get(server.id)} band={bandOf(server)} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ServerCell({
  server,
  metric,
  band,
}: {
  server: Server;
  metric: Metric | undefined;
  band: TempBand;
}) {
  const temp = band === "stale" || !metric ? "—" : `${metric.cpu_temp.toFixed(1)} °C`;
  return (
    <Link
      href={`/servers/${server.id}`}
      title={`${server.hostname}: ${temp}, ${BAND_LABEL[band]}`}
      className={`flex items-center gap-3 rounded-md px-2 py-2 ring-1 ring-ring transition hover:ring-2 hover:ring-axis focus-visible:outline-2 focus-visible:outline-series-1 ${CELL_TINT[band]}`}
    >
      <span className="w-7 text-xs text-muted tabular-nums">U{server.rack_unit}</span>
      <span className="min-w-0 flex-1 truncate text-sm">{server.hostname}</span>
      <span className="text-sm font-medium tabular-nums">{temp}</span>
      <BandIcon band={band} />
    </Link>
  );
}

function Legend() {
  return (
    <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
      {BANDS_IN_LEGEND.map((band) => (
        <BandBadge key={band} band={band} />
      ))}
    </div>
  );
}

function RackGridSkeleton() {
  return (
    <div
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      aria-busy="true"
      aria-label="Loading racks"
    >
      {Array.from({ length: 4 }, (_, i) => (
        <Skeleton key={i} className="h-72" />
      ))}
    </div>
  );
}
