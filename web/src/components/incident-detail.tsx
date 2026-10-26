"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { RecoveryChip, SeverityBadge, StatusBadge } from "@/components/incident-badges";
import { ErrorPanel, Skeleton } from "@/components/states";
import {
  ApiError,
  apiSend,
  type AuditEvent,
  type Comment,
  type Incident,
  type UserBrief,
} from "@/lib/api";
import { formatDateTime, METRIC_LABEL, personName } from "@/lib/format";
import { useDirectory, useIncident, useMe, useServers } from "@/lib/hooks";
import { can } from "@/lib/permissions";

export function IncidentDetailView({ incidentId }: { incidentId: number }) {
  const detail = useIncident(incidentId);
  const directory = useDirectory();
  const servers = useServers();

  if (detail.error instanceof ApiError && detail.error.status === 404) {
    return <Missing />;
  }
  if (detail.error && !detail.data) {
    return (
      <ErrorPanel message="Could not load this incident." onRetry={() => void detail.mutate()} />
    );
  }
  if (!detail.data) return <Skeleton className="h-96" />;

  const { incident, comments, history } = detail.data;
  const server = servers.data?.find((s) => s.id === incident.server_id);
  // After any action, refetch. (The live stream would also do it, a moment later.)
  const refresh = () => void detail.mutate();

  return (
    <>
      <BackLink />
      <header className="mb-6">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
          {incident.recovery_suggested && <RecoveryChip />}
        </div>
        <h1 className="text-xl font-semibold">{incident.title}</h1>
        <p className="mt-1 text-sm text-ink-2">
          {server ? (
            <Link href={`/servers/${server.id}`} className="underline hover:text-ink">
              {server.hostname}
            </Link>
          ) : (
            `Server #${incident.server_id}`
          )}{" "}
          · {METRIC_LABEL[incident.metric_name]} · opened {formatDateTime(incident.created_at)}
        </p>
      </header>

      {incident.recovery_suggested && incident.recovered_at && (
        <p
          role="status"
          className="mb-6 rounded-md border border-line bg-surface px-4 py-3 text-sm text-ink-2"
        >
          Metrics have looked normal since {formatDateTime(incident.recovered_at)}. Consider
          resolving this incident once the cause is understood.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Comments
            incidentId={incident.id}
            comments={comments}
            directory={directory.data}
            onAdded={refresh}
          />
          <History events={history} directory={directory.data} />
        </div>
        <Actions incident={incident} directory={directory.data} onChanged={refresh} />
      </div>
    </>
  );
}

/** Buttons appear only for roles allowed to use them (the API checks again anyway). */
function Actions(props: {
  incident: Incident;
  directory: UserBrief[] | undefined;
  onChanged: () => void;
}) {
  const { incident, directory, onChanged } = props;
  const me = useMe();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const base = `/incidents/${incident.id}`;
  const showAcknowledge = incident.status === "open" && can(me.data, "acknowledge");
  const showResolve = incident.status === "acknowledged" && can(me.data, "resolve");
  const showAssign = incident.status !== "resolved" && can(me.data, "assign");
  const assignees = directory?.filter((u) => u.is_active && u.role !== "operator") ?? [];

  return (
    <aside className="h-fit space-y-4 rounded-xl border border-line bg-surface p-4 text-sm">
      <h2 className="font-medium">Actions</h2>
      <dl className="space-y-1 text-ink-2">
        <div>
          <dt className="inline">Assignee: </dt>
          <dd className="inline text-ink">
            {incident.assignee_id === null ? "nobody" : personName(directory, incident.assignee_id)}
          </dd>
        </div>
        {incident.acknowledged_at && (
          <div>Acknowledged {formatDateTime(incident.acknowledged_at)}</div>
        )}
        {incident.resolved_at && <div>Resolved {formatDateTime(incident.resolved_at)}</div>}
      </dl>

      {showAcknowledge && (
        <ActionButton
          disabled={busy}
          onClick={() => run(() => apiSend("POST", `${base}/acknowledge`))}
        >
          Acknowledge
        </ActionButton>
      )}
      {showResolve && (
        <ActionButton disabled={busy} onClick={() => run(() => apiSend("POST", `${base}/resolve`))}>
          Resolve
        </ActionButton>
      )}
      {incident.status === "acknowledged" && !can(me.data, "resolve") && (
        <p className="text-ink-2">An engineer will resolve this incident.</p>
      )}
      {showAssign && (
        <label className="block">
          <span className="mb-1 block text-ink-2">Assign to</span>
          <select
            value={incident.assignee_id ?? ""}
            disabled={busy}
            onChange={(event) => {
              const value = event.target.value;
              void run(() =>
                apiSend("PUT", `${base}/assignee`, { assignee_id: value ? Number(value) : null }),
              );
            }}
            className="w-full rounded-md border border-line bg-page px-2 py-1.5"
          >
            <option value="">Nobody</option>
            {assignees.map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name} ({user.role})
              </option>
            ))}
          </select>
        </label>
      )}
      {error && (
        <p role="alert" className="text-status-critical">
          {error}
        </p>
      )}
    </aside>
  );
}

function ActionButton(props: { disabled: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      disabled={props.disabled}
      onClick={props.onClick}
      className="w-full rounded-md bg-ink px-3 py-2 font-medium text-surface disabled:opacity-60"
    >
      {props.children}
    </button>
  );
}

function Comments(props: {
  incidentId: number;
  comments: Comment[];
  directory: UserBrief[] | undefined;
  onAdded: () => void;
}) {
  const me = useMe();
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form).get("body");
    try {
      await apiSend("POST", `/incidents/${props.incidentId}/comments`, { body });
      form.reset();
      setError(null);
      props.onAdded();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not post the comment.");
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-4">
      <h2 className="mb-3 text-sm font-medium">Comments</h2>
      {props.comments.length === 0 ? (
        <p className="text-sm text-ink-2">No comments yet.</p>
      ) : (
        <ul className="space-y-3 text-sm">
          {props.comments.map((comment) => (
            <li key={comment.id}>
              <p className="text-xs text-muted">
                {personName(props.directory, comment.author_id)} ·{" "}
                {formatDateTime(comment.created_at)}
              </p>
              <p className="whitespace-pre-wrap">{comment.body}</p>
            </li>
          ))}
        </ul>
      )}
      {can(me.data, "comment") && (
        <form onSubmit={(event) => void onSubmit(event)} className="mt-4 space-y-2">
          <label htmlFor="comment-body" className="sr-only">
            Add a comment
          </label>
          <textarea
            id="comment-body"
            name="body"
            required
            maxLength={5000}
            rows={3}
            placeholder="What did you find or do?"
            className="w-full rounded-md border border-line bg-page px-3 py-2 text-sm"
          />
          {error && (
            <p role="alert" className="text-sm text-status-critical">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="rounded-md border border-line px-3 py-1.5 text-sm font-medium hover:bg-page"
          >
            Add comment
          </button>
        </form>
      )}
    </section>
  );
}

/** "incident.severity_raised" -> "Severity raised" */
function actionLabel(action: string): string {
  const words = action.replace(/^incident\./, "").replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

type Finding = { metric: keyof typeof METRIC_LABEL; reason: string };

/** The detector's explanation: one `reason` when severity rose, a `findings` list when opened. */
function eventReasons(event: AuditEvent): string[] {
  const { reason, findings } = event.details;
  if (typeof reason === "string") return [reason];
  if (Array.isArray(findings)) {
    return (findings as Finding[]).map((f) => `${METRIC_LABEL[f.metric]}: ${f.reason}`);
  }
  return [];
}

function History({
  events,
  directory,
}: {
  events: AuditEvent[];
  directory: UserBrief[] | undefined;
}) {
  return (
    <section className="rounded-xl border border-line bg-surface p-4">
      <h2 className="mb-3 text-sm font-medium">History</h2>
      <ol className="space-y-2 text-sm">
        {events.map((event) => (
          <li key={event.id} className="flex flex-wrap gap-x-2">
            <span className="text-muted tabular-nums">{formatDateTime(event.created_at)}</span>
            <span className="font-medium">{actionLabel(event.action)}</span>
            <span className="text-ink-2">by {personName(directory, event.actor_id)}</span>
            {eventReasons(event).map((reason) => (
              <span key={reason} className="w-full text-ink-2">
                {reason}
              </span>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}

function BackLink() {
  return (
    <Link href="/incidents" className="mb-4 inline-block text-sm text-ink-2 hover:text-ink">
      ← All incidents
    </Link>
  );
}

function Missing() {
  return (
    <>
      <BackLink />
      <div className="rounded-lg border border-line bg-surface p-6 text-sm">
        <h1 className="font-medium">Incident not found</h1>
      </div>
    </>
  );
}
