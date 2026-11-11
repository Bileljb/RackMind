"use client";

import Link from "next/link";

import { BandBadge, BandIcon } from "@/components/band-badge";
import { ErrorPanel, LiveIndicator, Skeleton, StaleBanner } from "@/components/states";
import type { Metric, Rack, Server, Source } from "@/lib/api";
import {
  BAND_LABEL,
  bandOf,
  CPU_USAGE,
  formatScaled,
  scaleCaption,
  scaleFor,
  STALE_AFTER_MS,
  TEMPERATURE,
  type Band,
} from "@/lib/bands";
import { formatAgo } from "@/lib/format";
import {
  POLL_INTERVAL_MS,
  useLatestMetrics,
  useRacks,
  useServers,
  useSimulationStatus,
} from "@/lib/hooks";
import { MODE_SOURCE, setMode, useMode } from "@/lib/mode";
import { useNow } from "@/lib/use-now";

const BANDS_IN_LEGEND: Band[] = ["normal", "warm", "hot", "critical", "stale"];

// Background tint per band: a light wash of the status color behind ink-colored text.
const CELL_TINT: Record<Band, string> = {
  normal: "bg-surface",
  warm: "bg-[color-mix(in_oklab,var(--status-warning)_18%,var(--surface))]",
  hot: "bg-[color-mix(in_oklab,var(--status-serious)_22%,var(--surface))]",
  critical: "bg-[color-mix(in_oklab,var(--status-critical)_24%,var(--surface))]",
  stale: "bg-page",
};

/** The dashboard for the current mode: real servers in Live, the demo data center in Simulation. */
export function RackGrid() {
  const mode = useMode();
  if (mode === null) return <RackGridSkeleton />;
  // `key`: switching modes starts from a clean state instead of showing the other mode's data.
  return <RackGridFor key={mode} source={MODE_SOURCE[mode]} />;
}

function RackGridFor({ source }: { source: Source }) {
  const racks = useRacks(source);
  const servers = useServers(source);
  const latest = useLatestMetrics(source);
  const now = useNow(POLL_INTERVAL_MS);
  const simulation = source === "simulated";

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
  if (!simulation && servers.data.length === 0) return <NoRealServers />;

  const inventory = servers.data;
  const byServer = new Map((latest.data ?? []).map((m) => [m.server_id, m]));
  const newest = (latest.data ?? []).reduce<string | undefined>(
    (max, m) => (max === undefined || m.timestamp > max ? m.timestamp : max),
    undefined,
  );
  const fresh =
    newest !== undefined && now !== null && now - new Date(newest).getTime() <= STALE_AFTER_MS;
  const scales = new Set(inventory.map((server) => scaleFor(byServer.get(server.id))));

  return (
    <div>
      {simulation && <SimulationBanner receiving={fresh} />}
      <StaleBanner show={Boolean(latest.error)} />
      <Summary
        servers={inventory}
        bandOf={(server) => bandOf(byServer.get(server.id), now)}
        newest={newest}
        live={!latest.error}
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {racks.data.map((rack) => (
          <RackColumn
            key={rack.id}
            rack={rack}
            servers={inventory.filter((s) => s.rack_id === rack.id)}
            byServer={byServer}
            now={now}
          />
        ))}
      </div>
      <Legend captions={[TEMPERATURE, CPU_USAGE].filter((s) => scales.has(s)).map(scaleCaption)} />
    </div>
  );
}

/** What Simulation mode is, and whether the simulator has started sending yet. */
function SimulationBanner({ receiving }: { receiving: boolean }) {
  const status = useSimulationStatus(true);
  const starting = !receiving || status.data?.active === false;
  return (
    <div
      role="status"
      className="mb-4 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink-2"
    >
      <p className="font-medium text-ink">
        Simulation mode{starting ? ": starting the simulation…" : ": demo data"}
      </p>
      <p className="mt-1">
        You are exploring a simulated data center. Faults are injected on a schedule: a CPU spike
        within a minute, then a memory leak, an overheating rack and a filling disk. Open an
        incident to see how it was detected and what the AI suggests. The simulation runs only while
        someone is in this mode.
      </p>
    </div>
  );
}

function NoRealServers() {
  return (
    <div className="rounded-lg border border-line bg-surface p-6 text-sm">
      <h2 className="font-medium">No real servers connected yet</h2>
      <p className="mt-1 text-ink-2">To monitor a Linux machine:</p>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-ink-2">
        <li>
          Register it on the API:{" "}
          <code className="rounded bg-page px-1.5 py-0.5 text-xs">
            docker compose exec api python -m app.add_server web-01 --group Production
          </code>
        </li>
        <li>
          Run <code className="rounded bg-page px-1.5 py-0.5 text-xs">rackmind_agent.py</code> on
          the machine with the server id it printed (see{" "}
          <code className="rounded bg-page px-1.5 py-0.5 text-xs">docs/modules/agent.md</code>).
        </li>
        <li>Reload this page: the server appears within seconds.</li>
      </ol>
      <button
        type="button"
        onClick={() => setMode("simulation", "live")}
        className="mt-4 rounded-md border border-line px-3 py-1.5 font-medium hover:bg-page"
      >
        Explore Simulation mode meanwhile
      </button>
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
  bandOf: (server: Server) => Band;
  newest: string | undefined;
  live: boolean;
}) {
  const counts = new Map<Band, number>();
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
  now,
}: {
  rack: Rack;
  servers: Server[];
  byServer: Map<number, Metric>;
  now: number | null;
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
            <ServerCell server={server} metric={byServer.get(server.id)} now={now} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ServerCell({
  server,
  metric,
  now,
}: {
  server: Server;
  metric: Metric | undefined;
  now: number | null;
}) {
  const band = bandOf(metric, now);
  const value = band === "stale" || !metric ? "—" : formatScaled(metric);
  // A real server that went quiet: say since when, it's the first thing an operator asks.
  const lastSeen =
    band === "stale" && server.source === "agent" && metric && now !== null
      ? `last seen ${formatAgo(metric.timestamp, now)}`
      : null;
  return (
    <Link
      href={`/servers/${server.id}`}
      title={`${server.hostname}: ${lastSeen ?? value}, ${BAND_LABEL[band]}`}
      className={`flex items-center gap-3 rounded-md px-2 py-2 ring-1 ring-ring transition hover:ring-2 hover:ring-axis focus-visible:outline-2 focus-visible:outline-series-1 ${CELL_TINT[band]}`}
    >
      <span className="w-7 text-xs text-muted tabular-nums">U{server.rack_unit}</span>
      <span className="min-w-0 flex-1 truncate text-sm">{server.hostname}</span>
      <span className="text-sm font-medium tabular-nums">
        {lastSeen ? <span className="text-xs font-normal text-ink-2">{lastSeen}</span> : value}
      </span>
      <BandIcon band={band} />
    </Link>
  );
}

function Legend({ captions }: { captions: string[] }) {
  return (
    <div className="mt-4">
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {BANDS_IN_LEGEND.map((band) => (
          <BandBadge key={band} band={band} />
        ))}
      </div>
      {captions.map((caption) => (
        <p key={caption} className="mt-1 text-xs text-muted">
          {caption}
        </p>
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
