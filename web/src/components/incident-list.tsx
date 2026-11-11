"use client";

import Link from "next/link";
import { useState } from "react";

import { RecoveryChip, SeverityBadge, StatusBadge } from "@/components/incident-badges";
import { ErrorPanel, Skeleton } from "@/components/states";
import type { IncidentStatus, Source } from "@/lib/api";
import { formatDateTime, personName } from "@/lib/format";
import { useDirectory, useIncidents, useServers } from "@/lib/hooks";
import { MODE_SOURCE, useMode } from "@/lib/mode";

const VIEWS: { label: string; statuses: IncidentStatus[] }[] = [
  { label: "Active", statuses: ["open", "acknowledged"] },
  { label: "Resolved", statuses: ["resolved"] },
  { label: "All", statuses: [] },
];

export function IncidentList() {
  const mode = useMode();
  if (mode === null) return <Skeleton className="h-64" />;
  return <IncidentListFor key={mode} source={MODE_SOURCE[mode]} />;
}

/** Only incidents of the current mode's servers: real ones in Live, simulated in Simulation. */
function IncidentListFor({ source }: { source: Source }) {
  const [view, setView] = useState(VIEWS[0]);
  const incidents = useIncidents(view.statuses, source);
  const servers = useServers();
  const directory = useDirectory();

  const hostname = (serverId: number) =>
    servers.data?.find((s) => s.id === serverId)?.hostname ?? `#${serverId}`;

  return (
    <>
      <div
        role="group"
        aria-label="Which incidents"
        className="mb-4 inline-flex rounded-md border border-line bg-surface p-0.5 text-sm"
      >
        {VIEWS.map((option) => (
          <button
            key={option.label}
            type="button"
            aria-pressed={view === option}
            onClick={() => setView(option)}
            className={`rounded px-3 py-1 ${view === option ? "bg-page font-medium text-ink" : "text-ink-2 hover:text-ink"}`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {incidents.error && !incidents.data ? (
        <ErrorPanel message="Could not load incidents." onRetry={() => void incidents.mutate()} />
      ) : !incidents.data ? (
        <Skeleton className="h-64" />
      ) : incidents.data.length === 0 ? (
        <p className="rounded-lg border border-line bg-surface p-6 text-sm text-ink-2">
          No {view.label.toLowerCase()} incidents.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Severity</th>
                <th className="px-4 py-2 font-medium">Incident</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Server</th>
                <th className="px-4 py-2 font-medium">Assignee</th>
                <th className="px-4 py-2 font-medium">Opened</th>
              </tr>
            </thead>
            <tbody>
              {incidents.data.map((incident) => (
                <tr key={incident.id} className="border-t border-line">
                  <td className="px-4 py-2.5">
                    <SeverityBadge severity={incident.severity} />
                  </td>
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/incidents/${incident.id}`}
                      className="font-medium hover:underline"
                    >
                      {incident.title}
                    </Link>
                    {incident.recovery_suggested && (
                      <span className="ml-2">
                        <RecoveryChip />
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={incident.status} />
                  </td>
                  <td className="px-4 py-2.5 text-ink-2">{hostname(incident.server_id)}</td>
                  <td className="px-4 py-2.5 text-ink-2">
                    {incident.assignee_id === null
                      ? "—"
                      : personName(directory.data, incident.assignee_id)}
                  </td>
                  <td className="px-4 py-2.5 text-ink-2 tabular-nums">
                    {formatDateTime(incident.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
