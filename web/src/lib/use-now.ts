"use client";

import { useEffect, useState } from "react";

/**
 * The current time in ms, refreshed every `intervalMs`, so "is this reading stale?" follows
 * the clock. It is null until the component runs in the browser: reading the clock during
 * render would freeze the build-time value into the prerendered HTML.
 */
export function useNow(intervalMs: number): number | null {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    const first = setTimeout(tick, 0);
    const timer = setInterval(tick, intervalMs);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [intervalMs]);
  return now;
}
