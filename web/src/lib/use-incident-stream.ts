"use client";

import { useEffect, useState } from "react";
import { useSWRConfig } from "swr";

import type { IncidentEvent } from "@/lib/api";
import { INCIDENTS_KEY_PREFIX } from "@/lib/hooks";

/**
 * Listens to the API's live incident feed (Server-Sent Events on `/api/stream`).
 *
 * `EventSource` is the browser's built-in SSE client: it keeps one HTTP request open, calls
 * our listener for each `event: incident` message, and reconnects by itself if the
 * connection drops. On every event we ask SWR to refetch all incident data, so lists and
 * detail pages update without a page reload. Mount this once (the app header does).
 */
export function useIncidentStream() {
  const { mutate } = useSWRConfig();
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<IncidentEvent | null>(null);

  useEffect(() => {
    const source = new EventSource("/api/stream"); // the session cookie is sent automatically
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // the browser retries on its own
    source.addEventListener("incident", (message) => {
      setLastEvent(JSON.parse(message.data) as IncidentEvent);
      // With only a key filter (no data argument), SWR keeps the current data on screen and
      // refetches in the background. Passing `undefined` as data would blank it instead.
      void mutate((key) => typeof key === "string" && key.startsWith(INCIDENTS_KEY_PREFIX));
    });
    return () => source.close();
  }, [mutate]);

  return { connected, lastEvent };
}
