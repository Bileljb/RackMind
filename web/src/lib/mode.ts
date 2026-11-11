"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useSWRConfig } from "swr";

import { apiSend, type Source } from "@/lib/api";
import { SIMULATION_STATUS_KEY, useServers } from "@/lib/hooks";

/**
 * Live mode shows real servers (agents); Simulation mode shows the simulated data center, and
 * keeps the simulator running while the user is in it.
 *
 * The choice is per browser (localStorage), not per account: one person exploring the demo
 * changes nothing for anyone else. A link with `?mode=simulation` opens straight in the demo.
 */
export type Mode = "live" | "simulation";

export const MODE_SOURCE: Record<Mode, Source> = { live: "agent", simulation: "simulated" };

const STORAGE_KEY = "rackmind.mode";
// Browsers refresh the API's 90s lease this often (see api/app/services/simulation.py).
const KEEPALIVE_MS = 30_000;

function isMode(value: string | null): value is Mode {
  return value === "live" || value === "simulation";
}

// A tiny store outside React: every component using `useMode` reads the same value and
// re-renders when it changes. `undefined` = not read from the URL / storage yet.
let chosen: Mode | null | undefined;
const listeners = new Set<() => void>();

function readChosen(): Mode | null {
  if (chosen === undefined) {
    const fromUrl = new URLSearchParams(window.location.search).get("mode");
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      // storage blocked (private mode, strict settings): fall back to the default
    }
    chosen = isMode(fromUrl) ? fromUrl : isMode(stored) ? stored : null;
  }
  return chosen;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Switch modes. `current` is what the user saw (it may be the default, never stored). */
export function setMode(mode: Mode, current: Mode | null) {
  const leavingSimulation = current === "simulation" && mode === "live";
  chosen = mode;
  try {
    window.localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // not remembered across visits, but still applied now
  }
  // Drop `?mode=` from the address bar, so a reload keeps the mode just picked.
  const url = new URL(window.location.href);
  if (url.searchParams.has("mode")) {
    url.searchParams.delete("mode");
    window.history.replaceState(window.history.state, "", url);
  }
  listeners.forEach((listener) => listener());
  // Stop the simulator now instead of waiting for the lease to expire. If someone else is
  // still in Simulation mode, their next keepalive starts it again.
  if (leavingSimulation) void apiSend("DELETE", "/simulation/keepalive").catch(() => {});
}

/**
 * The current mode, or null while it is still being decided (before the first render in the
 * browser, or while checking whether any real server exists).
 * Default when the user never chose: Live if a real server exists, otherwise Simulation, so
 * a fresh install opens on something to look at.
 */
export function useMode(): Mode | null {
  const picked = useSyncExternalStore(subscribe, readChosen, () => null);
  const agents = useServers("agent");
  if (picked) return picked;
  if (!agents.data) return null;
  return agents.data.length > 0 ? "live" : "simulation";
}

/**
 * While this browser is in Simulation mode, keep the simulator running: tell the API now,
 * then every 30s. Closing the tab stops the refreshes and the simulation ends by itself.
 * Mount once (the app header does).
 */
export function useSimulationKeepalive(mode: Mode | null) {
  const { mutate } = useSWRConfig();

  useEffect(() => {
    if (mode !== "simulation") return;
    const keepAlive = () =>
      apiSend("POST", "/simulation/keepalive")
        .then(() => mutate(SIMULATION_STATUS_KEY))
        .catch(() => {}); // the status poll shows "Paused" if this keeps failing
    void keepAlive();
    const timer = setInterval(() => void keepAlive(), KEEPALIVE_MS);
    return () => clearInterval(timer);
  }, [mode, mutate]);
}
