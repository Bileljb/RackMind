import { ROLES, type Role, type User } from "@/lib/api";

/**
 * Which actions each role may take, mirroring the API's `require_role(...)` rules
 * (api/app/routers/). Used only to hide buttons: the API enforces the real rules, so a
 * mismatch here shows a button that fails with 403, it never grants anything.
 */
const MINIMUM_ROLE = {
  acknowledge: "operator",
  comment: "operator",
  resolve: "engineer",
  assign: "engineer",
  manageUsers: "admin",
} satisfies Record<string, Role>;

export type Action = keyof typeof MINIMUM_ROLE;

export function can(user: User | undefined, action: Action): boolean {
  if (!user) return false;
  return ROLES.indexOf(user.role) >= ROLES.indexOf(MINIMUM_ROLE[action]);
}
