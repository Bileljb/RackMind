"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { NavLink } from "@/components/nav-link";
import { apiSend, type IncidentEvent } from "@/lib/api";
import { useIncidents, useMe, useServers } from "@/lib/hooks";
import { MODE_SOURCE, setMode, useMode, useSimulationKeepalive, type Mode } from "@/lib/mode";
import { can } from "@/lib/permissions";
import { useIncidentStream } from "@/lib/use-incident-stream";

/**
 * Top bar: brand, navigation, Live / Simulation switch, live-feed status and the user menu.
 * It also owns the app's one live incident connection (so every page gets live updates) and
 * the simulation keepalive (so the simulator runs while this browser is in Simulation mode).
 * The path is only known per request, hence <Suspense> (the shell shows the bare brand).
 */
export function AppHeader() {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-6 px-4">
        <span className="text-base font-semibold tracking-tight">Rackmind</span>
        <Suspense>
          <HeaderForPath />
        </Suspense>
      </div>
    </header>
  );
}

function HeaderForPath() {
  // The login page has no session: no menu, and no stream (it would only get 401s).
  return usePathname() === "/login" ? null : <SignedInHeader />;
}

function SignedInHeader() {
  const me = useMe();
  const mode = useMode();
  const source = mode ? MODE_SOURCE[mode] : undefined;
  const active = useIncidents(["open", "acknowledged"], source);
  const { connected, lastEvent } = useIncidentStream();
  useSimulationKeepalive(mode);
  const activeCount = mode ? active.data?.length : undefined;

  return (
    <>
      <nav className="flex gap-1 text-sm">
        <NavLink href="/">Racks</NavLink>
        <NavLink href="/incidents">
          Incidents
          {activeCount ? (
            <span className="ml-1.5 rounded-full bg-ink px-1.5 py-0.5 text-xs text-surface tabular-nums">
              {activeCount}
            </span>
          ) : null}
        </NavLink>
        {can(me.data, "manageUsers") && <NavLink href="/admin/users">Users</NavLink>}
      </nav>
      <div className="ml-auto flex items-center gap-4 text-sm">
        <ModeSwitch mode={mode} />
        <LiveDot connected={connected} />
        {me.data && (
          <span className="hidden text-ink-2 sm:inline">
            {me.data.full_name} · <span className="capitalize">{me.data.role}</span>
          </span>
        )}
        <LogoutButton />
      </div>
      <NewIncidentToast event={lastEvent} mode={mode} />
    </>
  );
}

const MODES: { mode: Mode; label: string }[] = [
  { mode: "live", label: "Live" },
  { mode: "simulation", label: "Simulation" },
];

/** Real servers or the demo data center. Switching to Simulation starts the simulator. */
function ModeSwitch({ mode }: { mode: Mode | null }) {
  return (
    <div
      role="group"
      aria-label="Data shown"
      className="flex rounded-md border border-line bg-surface p-0.5 text-sm"
    >
      {MODES.map((option) => (
        <button
          key={option.mode}
          type="button"
          aria-pressed={mode === option.mode}
          onClick={() => setMode(option.mode, mode)}
          className={`rounded px-2.5 py-1 ${mode === option.mode ? "bg-page font-medium text-ink" : "text-ink-2 hover:text-ink"}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function LiveDot({ connected }: { connected: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2" role="status">
      <span
        className={`size-2 rounded-full ${connected ? "bg-status-good" : "bg-muted"}`}
        aria-hidden="true"
      />
      {connected ? "Live" : "Reconnecting…"}
    </span>
  );
}

function LogoutButton() {
  async function logout() {
    await apiSend("POST", "/auth/logout");
    // A full page load on purpose, not router.push: it drops every cached response of the
    // previous session, so the next person on this browser sees none of it.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/login");
  }
  return (
    <button
      type="button"
      onClick={() => void logout()}
      className="rounded-md border border-line px-3 py-1.5 hover:bg-page"
    >
      Log out
    </button>
  );
}

const TOAST_MS = 8000;

/**
 * "New incident" popup when the detector opens one, wherever the user is in the app. Only for
 * the current mode: a demo incident must not pop up over real servers, nor the reverse.
 */
function NewIncidentToast({ event, mode }: { event: IncidentEvent | null; mode: Mode | null }) {
  const [visible, setVisible] = useState<IncidentEvent | null>(null);
  const servers = useServers(mode ? MODE_SOURCE[mode] : undefined);
  const inMode = servers.data?.some((s) => s.id === event?.incident.server_id) ?? false;

  useEffect(() => {
    if (event?.action !== "incident.opened" || !inMode) return;
    const show = setTimeout(() => setVisible(event), 0);
    const hide = setTimeout(() => setVisible(null), TOAST_MS);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, [event, inMode]);

  if (!visible) return null;
  return (
    <div
      role="status"
      className="fixed right-4 bottom-4 z-10 max-w-sm rounded-lg border border-line bg-surface p-4 text-sm shadow-lg"
    >
      <p className="font-medium">New incident</p>
      <Link
        href={`/incidents/${visible.incident.id}`}
        onClick={() => setVisible(null)}
        className="mt-1 block text-ink-2 underline hover:text-ink"
      >
        {visible.incident.title}
      </Link>
    </div>
  );
}
