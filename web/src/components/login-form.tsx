"use client";

import { useState, type FormEvent } from "react";

import { ApiError, apiSend, type User } from "@/lib/api";

/** Only same-site paths: `?next=https://evil.example` must not send the user elsewhere. */
function safeNextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  return next?.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function LoginForm() {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      // On success the API sets the httpOnly session cookie; we never see the token.
      await apiSend<User>("POST", "/auth/login", {
        email: form.get("email"),
        password: form.get("password"),
      });
      window.location.assign(safeNextPath()); // full load, so every page starts fresh
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not reach the server.");
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={(event) => void onSubmit(event)}
      className="space-y-4 rounded-lg border border-line bg-surface p-6"
    >
      <Field label="Email" name="email" type="email" autoComplete="username" />
      <Field label="Password" name="password" type="password" autoComplete="current-password" />
      {error && (
        <p role="alert" className="text-sm text-status-critical">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-md bg-ink px-3 py-2 text-sm font-medium text-surface disabled:opacity-60"
      >
        {submitting ? "Logging in…" : "Log in"}
      </button>
    </form>
  );
}

function Field(props: { label: string; name: string; type: string; autoComplete: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{props.label}</span>
      <input
        name={props.name}
        type={props.type}
        autoComplete={props.autoComplete}
        required
        className="w-full rounded-md border border-line bg-page px-3 py-2"
      />
    </label>
  );
}
