import type { IncidentStatus, Severity } from "@/lib/api";

// Like the temperature badges: color sits on the icon only and a text label always goes
// with it, so severity never depends on color alone.
const SEVERITY_ICON: Record<Severity, string> = {
  info: "text-muted",
  warning: "text-status-warning",
  critical: "text-status-critical",
};

const SEVERITY_LABEL: Record<Severity, string> = {
  info: "Info",
  warning: "Warning",
  critical: "Critical",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <svg viewBox="0 0 16 16" className={`size-3.5 ${SEVERITY_ICON[severity]}`} aria-hidden="true">
        {severity === "info" ? (
          <circle cx="8" cy="8" r="5" fill="currentColor" />
        ) : (
          <>
            <path d="M8 1.5 15 14H1z" fill="currentColor" />
            <path
              d="M8 6v4M8 11.5v.5"
              stroke="var(--surface)"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </>
        )}
      </svg>
      {SEVERITY_LABEL[severity]}
    </span>
  );
}

const STATUS_STYLE: Record<IncidentStatus, string> = {
  open: "border-ink text-ink",
  acknowledged: "border-line text-ink-2",
  resolved: "border-line text-muted",
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLE[status]}`}
    >
      {status}
    </span>
  );
}

/** Shown while the detector sees normal metrics again on an unresolved incident. */
export function RecoveryChip() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_oklab,var(--status-good)_14%,var(--surface))] px-2 py-0.5 text-xs text-ink">
      <span className="size-1.5 rounded-full bg-status-good" aria-hidden="true" />
      Back to normal
    </span>
  );
}
