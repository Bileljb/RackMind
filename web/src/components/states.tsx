// Shared loading / error UI so every page handles these states the same way.

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-line ${className}`} aria-hidden="true" />;
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-line bg-surface p-6 text-sm">
      <p className="font-medium">{message}</p>
      <p className="mt-1 text-ink-2">Check that the API is running (`docker compose ps`).</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-md border border-line px-3 py-1.5 font-medium hover:bg-page"
        >
          Try again
        </button>
      )}
    </div>
  );
}

/**
 * Shown above live data when a refresh failed: we keep the last good data on screen,
 * but say clearly that it is not live anymore.
 */
export function StaleBanner({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <p
      role="status"
      className="mb-4 rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink-2"
    >
      Live updates paused: the API is not answering. Showing the last data received, retrying every
      5s.
    </p>
  );
}

/** Pulsing dot + time of the newest reading, so the user can see polling is alive. */
export function LiveIndicator({ latest, live }: { latest: string | undefined; live: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-ink-2">
      <span className="relative flex size-2">
        {live && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-status-good opacity-60" />
        )}
        <span
          className={`relative inline-flex size-2 rounded-full ${live ? "bg-status-good" : "bg-muted"}`}
        />
      </span>
      {latest ? `Latest reading ${new Date(latest).toLocaleTimeString()}` : "Waiting for readings…"}
      {!live && " · paused"}
    </span>
  );
}
