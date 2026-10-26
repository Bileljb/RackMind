import { UserAdmin } from "@/components/user-admin";

export default function UsersPage() {
  return (
    <>
      <h1 className="mb-1 text-xl font-semibold">Users</h1>
      <p className="mb-6 text-sm text-ink-2">
        Create accounts, change roles, and deactivate people who should no longer have access.
      </p>
      <UserAdmin />
    </>
  );
}
