"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { NavLink } from "@/components/nav-link";
import { apiSend, type IncidentEvent } from "@/lib/api";
import { useIncidents, useMe } from "@/lib/hooks";
import { can } from "@/lib/permissions";
import { useIncidentStream } from "@/lib/use-incident-stream";

/**
 * Top bar: brand, navigation, live-feed status and the user menu. It also owns the app's one
 * live incident connection, so every page gets live updates.
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
  const active = useIncidents(["open", "acknowledged"]);
  const { connected, lastEvent } = useIncidentStream();
  const activeCount = active.data?.length;

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
        <LiveDot connected={connected} />
        {me.data && (
          <span className="hidden text-ink-2 sm:inline">
            {me.data.full_name} · <span className="capitalize">{me.data.role}</span>
          </span>
        )}
        <LogoutButton />
      </div>
      <NewIncidentToast event={lastEvent} />
    </>
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

/** "New incident" popup when the detector opens one, wherever the user is in the app. */
function NewIncidentToast({ event }: { event: IncidentEvent | null }) {
  const [visible, setVisible] = useState<IncidentEvent | null>(null);

  useEffect(() => {
    if (event?.action !== "incident.opened") return;
    const show = setTimeout(() => setVisible(event), 0);
    const hide = setTimeout(() => setVisible(null), TOAST_MS);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, [event]);

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
