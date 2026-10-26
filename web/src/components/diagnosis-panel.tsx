"use client";

import { useState } from "react";

import { Skeleton } from "@/components/states";
import { ApiError, apiSend, type Diagnosis, type DiagnosisErrorKind } from "@/lib/api";
import { formatDateTime, METRIC_LABEL } from "@/lib/format";
import { useDiagnosis, useMe } from "@/lib/hooks";
import { can } from "@/lib/permissions";

const ERROR_TEXT: Record<DiagnosisErrorKind, string> = {
  not_configured: "AI diagnosis is turned off on this server (no API key is configured).",
  timeout: "The AI service did not answer in time.",
  rate_limited: "The AI service is rate limiting requests. Try again in a minute.",
  api_error: "The AI service returned an error.",
  invalid_output: "The AI's answer did not pass validation, so it is not shown.",
};

// Same bands as the confidence rules in the prompt (api/app/ai/prompt.py).
function confidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}

const APPROVAL_PREFIX = "Requires approval:";

/** The AI's suggestion for an incident. It is only ever advice: nothing here runs anything. */
export function DiagnosisPanel({ incidentId }: { incidentId: number }) {
  const me = useMe();
  const allowed = can(me.data, "viewDiagnosis");
  const diagnosis = useDiagnosis(incidentId, allowed);

  return (
    <section className="rounded-xl border border-line bg-surface p-4" aria-labelledby="ai-title">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <h2 id="ai-title" className="text-sm font-medium">
          AI diagnosis
        </h2>
        <span className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-2">
          AI-generated suggestion
        </span>
      </div>
      <p className="mb-4 text-xs text-ink-2">
        Suggested by a language model from this incident&apos;s data. It is never applied
        automatically: check it before acting.
      </p>
      {!me.data ? (
        <Skeleton className="h-24" />
      ) : !allowed ? (
        <p className="text-sm text-ink-2">AI diagnosis details are available to engineers.</p>
      ) : (
        <DiagnosisBody
          incidentId={incidentId}
          diagnosis={diagnosis.data}
          missing={diagnosis.error instanceof ApiError && diagnosis.error.status === 404}
          loadFailed={Boolean(diagnosis.error) && !diagnosis.data}
          onChanged={(updated) => void diagnosis.mutate(updated, { revalidate: false })}
        />
      )}
    </section>
  );
}

function DiagnosisBody(props: {
  incidentId: number;
  diagnosis: Diagnosis | undefined;
  missing: boolean;
  loadFailed: boolean;
  onChanged: (diagnosis: Diagnosis) => void;
}) {
  const { incidentId, diagnosis, missing, onChanged } = props;
  const [error, setError] = useState<string | null>(null);
  const base = `/incidents/${incidentId}/diagnosis`;

  async function send(request: () => Promise<Diagnosis>) {
    setError(null);
    try {
      onChanged(await request());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong.");
    }
  }
  const askAgain = () => void send(() => apiSend<Diagnosis>("POST", base));

  let body: React.ReactNode;
  if (missing) {
    body = (
      <div className="text-sm">
        <p className="text-ink-2">This incident has no diagnosis yet.</p>
        <SmallButton onClick={askAgain}>Run diagnosis</SmallButton>
      </div>
    );
  } else if (props.loadFailed) {
    body = <p className="text-sm text-ink-2">Could not load the diagnosis.</p>;
  } else if (!diagnosis) {
    body = <Skeleton className="h-24" />;
  } else if (diagnosis.status === "pending") {
    body = (
      <p className="text-sm text-ink-2" role="status">
        Diagnosing… this usually takes a few seconds and appears here by itself.
      </p>
    );
  } else if (diagnosis.status === "failed") {
    body = (
      <div className="text-sm">
        <p>{diagnosis.error ? ERROR_TEXT[diagnosis.error] : "The diagnosis failed."}</p>
        {diagnosis.error_detail && (
          <p className="mt-1 text-xs break-words text-muted">{diagnosis.error_detail}</p>
        )}
        <SmallButton onClick={askAgain}>Try again</SmallButton>
      </div>
    );
  } else {
    body = (
      <Result
        diagnosis={diagnosis}
        onVote={(helpful) =>
          void send(() => apiSend<Diagnosis>("PUT", `${base}/feedback`, { helpful }))
        }
        onAskAgain={askAgain}
      />
    );
  }

  return (
    <>
      {body}
      {error && (
        <p role="alert" className="mt-2 text-sm text-status-critical">
          {error}
        </p>
      )}
    </>
  );
}

function Result(props: {
  diagnosis: Diagnosis;
  onVote: (helpful: boolean) => void;
  onAskAgain: () => void;
}) {
  const { diagnosis } = props;
  const confidence = diagnosis.confidence ?? 0;
  const percent = Math.round(confidence * 100);

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="mb-1 text-xs font-medium text-muted">Probable cause</h3>
        <p className="text-base">{diagnosis.probable_cause}</p>
      </div>

      <div>
        <h3 className="mb-1 text-xs font-medium text-muted">Model confidence</h3>
        <div className="flex items-center gap-3">
          <div
            className="h-2 w-40 overflow-hidden rounded-full bg-line"
            role="meter"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-label="Model confidence"
          >
            <div className="h-full rounded-full bg-series-1" style={{ width: `${percent}%` }} />
          </div>
          <span className="tabular-nums">
            {percent}% · {confidenceLabel(confidence)}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted">
          The model&apos;s own estimate, not a measured probability.
        </p>
      </div>

      <div>
        <h3 className="mb-1 text-xs font-medium text-muted">Suggested next steps</h3>
        <ol className="list-decimal space-y-1 pl-5">
          {diagnosis.recommended_steps.map((step) =>
            step.startsWith(APPROVAL_PREFIX) ? (
              <li key={step}>
                <span className="mr-1 rounded bg-[color-mix(in_oklab,var(--status-warning)_22%,var(--surface))] px-1.5 py-0.5 text-xs font-medium">
                  Needs approval
                </span>
                {step.slice(APPROVAL_PREFIX.length).trim()}
              </li>
            ) : (
              <li key={step}>{step}</li>
            ),
          )}
        </ol>
      </div>

      <div>
        <h3 className="mb-1 text-xs font-medium text-muted">Evidence from the data</h3>
        <ul className="space-y-1">
          {diagnosis.evidence.map((item) => (
            <li key={item.observation}>
              <span className="font-medium">{METRIC_LABEL[item.metric]}:</span> {item.observation}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
        <span className="mr-1">Was this helpful?</span>
        <VoteButton active={diagnosis.feedback.mine === true} onClick={() => props.onVote(true)}>
          Yes · {diagnosis.feedback.helpful}
        </VoteButton>
        <VoteButton active={diagnosis.feedback.mine === false} onClick={() => props.onVote(false)}>
          No · {diagnosis.feedback.not_helpful}
        </VoteButton>
        <button
          type="button"
          onClick={props.onAskAgain}
          className="ml-auto text-xs text-ink-2 underline hover:text-ink"
        >
          Ask again
        </button>
      </div>
      <p className="text-xs text-muted">
        {diagnosis.model} · {diagnosis.latency_ms} ms
        {diagnosis.finished_at && ` · ${formatDateTime(diagnosis.finished_at)}`}
      </p>
    </div>
  );
}

function VoteButton(props: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={props.active}
      onClick={props.onClick}
      className={`rounded-md border px-2.5 py-1 tabular-nums ${props.active ? "border-ink font-medium" : "border-line text-ink-2 hover:text-ink"}`}
    >
      {props.children}
    </button>
  );
}

function SmallButton(props: { onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className="mt-3 rounded-md border border-line px-3 py-1.5 font-medium hover:bg-page"
    >
      {props.children}
    </button>
  );
}
