# Auth and real-time: how it works

## Login and sessions

- **No public sign-up.** Admins create accounts (`POST /users`). The seed script creates one demo user per role: `operator@`, `engineer@` and `admin@rackmind.local`, all with `SEED_PASSWORD`.
- **Login** (`POST /auth/login`):
  - Checks the Argon2 password hash. If the email is unknown, it still checks a dummy hash, so response times don't reveal which emails exist.
  - It answers the same "Wrong email or password" for every failure.
- **The session cookie:**
  - On success, the API sets `rackmind_session`, a JWT signed with `JWT_SECRET` that expires after `SESSION_MINUTES` (default 8 h).
  - The cookie is `HttpOnly`, so page scripts, including injected ones, can't read it.
  - It is `SameSite=Lax`, so other websites can't make the browser send it with their POSTs.
  - It is `Secure` when `COOKIE_SECURE=true` (set this in production, over HTTPS).
- **What the token holds:** only the user id. The role is read from the database on every request (`get_current_user` in `app/deps.py`), so changing a role or deactivating someone applies immediately.
- **Logout** deletes the cookie. A copied token stays valid until it expires, because JWTs are stateless. Making it invalid immediately would need a server-side denylist or sessions table.

## Permissions (enforced in the API)

- **Role guards:** `require_role(minimum)` builds a dependency that answers 403 below that role. Not logged in is 401. The shorthands `Operator`, `Engineer` and `Admin` are used as endpoint parameters.
- **The rules:**
  - Any logged-in user can read everything, acknowledge and comment.
  - An engineer can also resolve and assign.
  - An admin can also manage users (`/users`). `/users/directory` (names and roles only) is open to everyone.
- **Machines use a key, not a login.** The simulator sends `X-API-Key: INGEST_API_KEY`. Only that key can `POST /metrics`, and it can also read `/racks` and `/servers`. The key is compared with `hmac.compare_digest`, so timing doesn't leak it.
- **Self-protection:** an admin can't demote or deactivate their own account (409), so the last admin can't lock everyone out by mistake.
- **Tests:** `tests/test_permissions.py` runs every role against every sensitive endpoint, plus the logged-out case and the API-key case.

## Live updates (Redis pub/sub → SSE)

- **Publishing:** after each commit, the API (acknowledge, resolve, assign, comment) and the worker (opened, severity raised, recovered, relapsed) publish `{"action", "incident"}` on the Redis channel `incidents` (`app/services/events.py`). Publishing is best effort: the database stays the source of truth.
- **`GET /stream`** (any logged-in user) is a Server-Sent Events response, built with FastAPI's `EventSourceResponse`.
  - Each open connection subscribes to the channel and forwards every message as `event: incident`.
  - FastAPI adds a `: ping` every 15 s so proxies don't close idle connections.
  - The endpoint gives its DB connection back right after the auth check, because the request can stay open for hours.
- **SSE vs WebSockets:** SSE is one-way (server → browser), plain HTTP, sends cookies automatically and reconnects by itself. That is all a live feed needs.

## Web app

- **`src/proxy.ts`** (Next.js 16's name for middleware) redirects to `/login?next=…` when there is no session cookie. This is only an optimistic check: it can't verify the token. The API checks every request, and `apiGet`/`apiSend` send the user to login whenever the API answers 401.
- **`useIncidentStream`**
  - The app header opens one `EventSource('/api/stream')` for the whole app.
  - On each event, it asks SWR to refetch every `/incidents…` key, so lists, detail pages and the nav counter update without a reload.
  - When the detector opens an incident, it also shows a "New incident" toast.
- **Hidden actions:** `lib/permissions.ts` mirrors the API rules to hide buttons a role can't use: operators see no Resolve or Assign, and only admins see "Users". Hiding is only for convenience; the API decides.
- **Pages:**
  - `/login`
  - `/incidents`: Active / Resolved / All
  - `/incidents/[id]`: actions, comments, history
  - `/admin/users`: create, change role, deactivate

## Configuration

- In `.env`: `JWT_SECRET` (32+ random characters) and `INGEST_API_KEY` (16+). Both are required: the API refuses to start without them.
- Optional: `SESSION_MINUTES` and `COOKIE_SECURE`.
