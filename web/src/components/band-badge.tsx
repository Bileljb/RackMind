import { BAND_LABEL, type TempBand } from "@/lib/temperature";

// Status color lives on the icon only; the text stays in ink so it is always readable,
// and the label means the state never depends on color alone.
const ICON_COLOR: Record<TempBand, string> = {
  normal: "text-status-good",
  warm: "text-status-warning",
  hot: "text-status-serious",
  critical: "text-status-critical",
  stale: "text-muted",
};

export function BandIcon({ band }: { band: TempBand }) {
  const className = `size-3.5 shrink-0 ${ICON_COLOR[band]}`;
  if (band === "normal") {
    return (
      <svg viewBox="0 0 16 16" className={className} aria-hidden="true">
        <circle cx="8" cy="8" r="5" fill="currentColor" />
      </svg>
    );
  }
  if (band === "stale") {
    return (
      <svg viewBox="0 0 16 16" className={className} aria-hidden="true">
        <circle
          cx="8"
          cy="8"
          r="5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeDasharray="3 2"
        />
      </svg>
    );
  }
  // Warning triangle for warm / hot / critical.
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true">
      <path d="M8 1.5 15 14H1z" fill="currentColor" />
      <path d="M8 6v4M8 11.5v.5" stroke="var(--surface)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function BandBadge({ band }: { band: TempBand }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
      <BandIcon band={band} />
      {BAND_LABEL[band]}
    </span>
  );
}
