"use client";

import { useState, type FormEvent } from "react";

import { ErrorPanel, Skeleton } from "@/components/states";
import { ApiError, apiSend, ROLES, type Role, type User } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useMe, useUsers } from "@/lib/hooks";
import { can } from "@/lib/permissions";

export function UserAdmin() {
  const me = useMe();
  if (!me.data) return <Skeleton className="h-64" />;
  // The proxy only knows "logged in", not the role, so non-admins can reach this URL.
  // Say so plainly; the API would refuse every request here with 403 anyway.
  if (!can(me.data, "manageUsers")) {
    return (
      <p className="rounded-lg border border-line bg-surface p-6 text-sm">
        Only administrators can manage users.
      </p>
    );
  }
  return <UserTable me={me.data} />;
}

function UserTable({ me }: { me: User }) {
  const users = useUsers();
  const [error, setError] = useState<string | null>(null);

  async function update(user: User, changes: Partial<Pick<User, "role" | "is_active">>) {
    setError(null);
    try {
      await apiSend("PATCH", `/users/${user.id}`, changes);
      await users.mutate();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not update the user.");
    }
  }

  if (users.error && !users.data) {
    return <ErrorPanel message="Could not load users." onRetry={() => void users.mutate()} />;
  }
  if (!users.data) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-6">
      {error && (
        <p role="alert" className="text-sm text-status-critical">
          {error}
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Email</th>
              <th className="px-4 py-2 font-medium">Role</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {users.data.map((user) => {
              const isMe = user.id === me.id; // can't demote or deactivate yourself
              return (
                <tr key={user.id} className="border-t border-line">
                  <td className="px-4 py-2.5 font-medium">
                    {user.full_name}
                    {isMe && <span className="ml-1 text-xs text-muted">(you)</span>}
                  </td>
                  <td className="px-4 py-2.5 text-ink-2">{user.email}</td>
                  <td className="px-4 py-2.5">
                    <select
                      aria-label={`Role of ${user.full_name}`}
                      value={user.role}
                      disabled={isMe}
                      onChange={(event) => void update(user, { role: event.target.value as Role })}
                      className="rounded-md border border-line bg-page px-2 py-1 capitalize"
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      type="button"
                      disabled={isMe}
                      onClick={() => void update(user, { is_active: !user.is_active })}
                      className="rounded-md border border-line px-2.5 py-1 hover:bg-page disabled:opacity-50"
                    >
                      {user.is_active ? "Active · deactivate" : "Inactive · reactivate"}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 text-ink-2 tabular-nums">
                    {formatDateTime(user.created_at)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <CreateUserForm onCreated={() => void users.mutate()} />
    </div>
  );
}

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiSend("POST", "/users", data);
      form.reset();
      setError(null);
      onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create the user.");
    }
  }

  return (
    <form
      onSubmit={(event) => void onSubmit(event)}
      className="rounded-xl border border-line bg-surface p-4 text-sm"
    >
      <h2 className="mb-3 font-medium">New user</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Input label="Full name" name="full_name" type="text" />
        <Input label="Email" name="email" type="email" />
        <Input label="Temporary password" name="password" type="password" minLength={10} />
        <label className="block">
          <span className="mb-1 block text-ink-2">Role</span>
          <select
            name="role"
            defaultValue="operator"
            className="w-full rounded-md border border-line bg-page px-2 py-2 capitalize"
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-status-critical">
          {error}
        </p>
      )}
      <button type="submit" className="mt-4 rounded-md bg-ink px-3 py-2 font-medium text-surface">
        Create user
      </button>
    </form>
  );
}

function Input(props: { label: string; name: string; type: string; minLength?: number }) {
  return (
    <label className="block">
      <span className="mb-1 block text-ink-2">{props.label}</span>
      <input
        name={props.name}
        type={props.type}
        minLength={props.minLength}
        required
        autoComplete="off"
        className="w-full rounded-md border border-line bg-page px-3 py-2"
      />
    </label>
  );
}
