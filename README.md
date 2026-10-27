# Rackmind

**AI-assisted data center monitoring and incident management.**

Rackmind watches a (simulated) data center, notices when a server starts misbehaving, opens an incident, and asks an LLM for a probable cause and next steps, while people stay in charge of every decision.

<!-- CI badge, once the repo is on GitHub:
[![CI](https://github.com/<user>/rackmind/actions/workflows/ci.yml/badge.svg)](https://github.com/<user>/rackmind/actions/workflows/ci.yml)
-->

<!-- Demo: add a screenshot or GIF here, e.g. docs/demo.gif, and link the 2-minute video. -->
> 📽️ **Demo video:** _coming soon_  ·  🌐 **Live demo:** _coming soon_

---

## What it does

- **Live rack view.** Four racks × five servers, each reporting CPU temperature, power, disk, memory and network every 5 seconds. Each server has its own charts with selectable time ranges.
- **Anomaly detection.** A background worker checks every batch of readings against fixed safety limits *and* each server's own recent normal (a rolling z-score), and opens **one** incident per affected server, never duplicates.
- **Incident workflow.** Incidents go `open → acknowledged → resolved`, with assignment, comments, a full audit history, and a "looks recovered" hint when readings return to normal. Nothing is ever closed automatically.
- **AI diagnosis.** Each new incident gets a structured diagnosis from an LLM: probable cause, confidence, recommended steps and the evidence behind them. The answer is schema-validated before anyone sees it; the AI **only suggests** and never acts on infrastructure.
- **Real-time updates.** New incidents, status changes and diagnoses appear in every open browser instantly (Server-Sent Events over Redis pub/sub), with a "New incident" toast.
- **Role-based access.** Operators, engineers and admins see and can do different things. The API enforces every rule; the UI just hides what you can't use.
- **Fault injection.** The simulator can overheat a rack, fill a disk or leak memory on a schedule, so the whole pipeline can be demonstrated end to end.

## Architecture

```mermaid
flowchart LR
    sim["Simulator<br/>(telemetry + faults)"] -- "POST /metrics/batch<br/>X-API-Key" --> api
    subgraph backend["Backend (Python)"]
        api["FastAPI<br/>REST + SSE"]
        worker["ARQ worker<br/>detector + AI diagnosis"]
    end
    api -- "save readings" --> pg[("PostgreSQL")]
    api -- "queue detect job" --> redis[("Redis<br/>queue + pub/sub")]
    redis -- "jobs" --> worker
    worker -- "incidents, diagnoses" --> pg
    worker -- "diagnose" --> llm["Groq LLM<br/>(structured output)"]
    worker -- "publish events" --> redis
    redis -- "subscribe" --> api
    browser["Browser"] -- "HTTPS" --> caddy["Caddy<br/>(prod only)"] --> web["Next.js<br/>dashboard"]
    web -- "/api/* proxy<br/>+ SSE stream" --> api
```

**The flow, step by step**

1. The **simulator** sends 20 readings every 5 s to `POST /metrics/batch`, authenticated with a machine API key.
2. The **API** validates them (Pydantic), writes them in one `INSERT`, queues a `detect_anomalies` job in Redis, and responds immediately. Ingestion never waits on detection.
3. The **worker** runs the detector. If a server looks wrong, it opens an incident (or raises the severity of the existing one) and queues a diagnosis job.
4. The worker builds a compact context (metrics around the incident, rack neighbours, similar past incidents), calls the **LLM** with a strict JSON schema, validates the answer again, and stores it, or stores *why* it failed.
5. Every change is published on Redis; each open **`/stream`** connection forwards it to the browser, which refetches what changed.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12, fully async), Pydantic v2 |
| Database | PostgreSQL 17, SQLAlchemy 2.0 (async) + Alembic migrations |
| Background jobs | Redis + ARQ |
| Real-time | Server-Sent Events, Redis pub/sub |
| Auth | JWT in an `HttpOnly` cookie, Argon2 password hashes, role-based access control |
| AI | Groq API (`openai/gpt-oss-120b` by default), strict structured outputs, validated with Pydantic |
| Frontend | Next.js 16 (App Router, Cache Components), TypeScript, Tailwind CSS v4, SWR, Recharts |
| Quality | pytest + httpx, ruff, mypy (strict), eslint, prettier |
| Infra | Docker Compose, Caddy (automatic HTTPS), GitHub Actions |

## Quick start

You need **Docker** (with Compose). Then, from the repo root:

```bash
cp .env.example .env
docker compose up --build
```

That starts Postgres, Redis, the API, the worker, the simulator and the dashboard, applies migrations and seeds demo data.

- Dashboard: **http://localhost:3000**
- API docs (Swagger): **http://localhost:8000/docs**

**Demo accounts** (password = `SEED_PASSWORD` in `.env`, `change-me` by default):

| Email | Role |
|---|---|
| `operator@rackmind.local` | operator |
| `engineer@rackmind.local` | engineer |
| `admin@rackmind.local` | admin |

**See an incident happen.** The example `.env` schedules three faults (`SIM_FAULTS`): rack R02 overheats, `r03-srv02` leaks memory, and `r01-srv03` fills its disk. The detector needs a few minutes of normal readings to learn each server's baseline, so the first incidents appear roughly **8 minutes** after start. Restart the schedule any time with `docker compose restart simulator`.

**AI diagnosis is optional.** Put a free key from [console.groq.com](https://console.groq.com/keys) in `GROQ_API_KEY`. Without one, everything else works, and incidents say the AI is not configured.

## Roles

| | Operator | Engineer | Admin |
|---|:-:|:-:|:-:|
| View dashboard, servers, incidents | ✅ | ✅ | ✅ |
| Acknowledge and comment | ✅ | ✅ | ✅ |
| Resolve and assign incidents | | ✅ | ✅ |
| Read, retry and rate AI diagnoses | | ✅ | ✅ |
| Manage users | | | ✅ |

## How the interesting parts work

### Anomaly detection
The detector (`api/app/services/detector.py`) is a set of pure functions, easy to test without a database. For each metric it compares the **mean of the last 30 s** (to smooth out noise) against two rules and keeps the more severe result:

- **Fixed thresholds**: dangerous on any server (e.g. CPU ≥ 70 °C warning, ≥ 80 °C critical; disk/memory ≥ 85 % / ≥ 95 %).
- **Rolling z-score**: how far the recent mean is from *this server's* baseline (its readings from 30 to 5 minutes ago). The 5-minute gap keeps a slow drift from hiding inside its own baseline; a per-metric floor on the standard deviation stops perfectly steady metrics from turning tiny wobbles into alarms; only *upward* deviations count, so recovery doesn't trigger a false alarm.

**No duplicates:** a partial unique index in Postgres allows at most one active incident per server, and inserts use `ON CONFLICT DO NOTHING`, so two concurrent jobs can't both open one. New findings only raise an incident's severity, never lower it.

### AI diagnosis, safely
- **Context, not raw data.** About 1,800 raw readings are summarised into per-minute averages plus baseline statistics (~3.5k characters), along with rack neighbours (shared cause, or one machine?), the detector's reasons, and up to five similar resolved incidents with their comments.
- **Two layers of validation.** The JSON Schema of the response model is sent to Groq in strict mode, then Pydantic validates the answer again before it is stored. Malformed output is stored as `invalid_output` and never shown.
- **Graceful failure.** Timeouts, rate limits and API errors are retried with backoff, then stored as a named failure state. The incident works the same either way, and an engineer can ask again.
- **Suggest, never act.** No code path touches infrastructure. Risky steps must start with "Requires approval:", the UI labels the panel as AI-generated, and human-written text (titles, comments) is passed as data, never instructions, to resist prompt injection.

### Real-time
The API and worker publish `{action, incident}` on a Redis channel after each commit. `GET /stream` is a Server-Sent Events endpoint: it checks the session, **releases its database connection** (the request may stay open for hours), then forwards each message. The browser keeps one `EventSource` for the whole app and asks SWR to refetch only the incident data that changed.

### Auth
Login sets a signed JWT in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` in production). The token holds only the user id; the role is read from the database on every request, so a role change or deactivation applies immediately. The browser only ever talks to the Next.js origin, which proxies `/api/*` to FastAPI: no CORS, and cookies just work.

## Decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| **Async FastAPI** | Most work is waiting on Postgres, Redis or the LLM; async serves many of those at once on one process. | Every library on the request path must be async-aware (asyncpg, async SQLAlchemy). |
| **Detection in a worker, not in the request** | Ingestion stays fast and keeps working if detection is slow or broken. | Incidents appear a moment after the data, and a queue (Redis) is one more moving part. |
| **Thresholds + z-score** instead of ML | Explainable ("72 °C, 6σ above this server's normal"), no training data needed, easy to test. | The z-score slowly accepts long anomalies as normal, and assumes roughly Gaussian noise. |
| **SSE** instead of WebSockets | Updates only flow server → browser; SSE is plain HTTP, sends cookies, reconnects on its own. | One-way only; each tab holds an open connection. |
| **JWT in an HttpOnly cookie** | Scripts (including injected ones) can't read it; no token handling in the frontend. | Logout can't revoke a copied token before it expires (no server-side session list). |
| **Permissions enforced in the API** | The UI can be bypassed; the API can't. One permission matrix test covers every role × endpoint. | Rules are mirrored in the frontend just to hide buttons, so both must stay in sync. |
| **LLM output in a strict schema** | The UI can rely on its shape, and bad output fails loudly instead of rendering nonsense. | Fewer models support strict structured outputs; the model is configurable via `GROQ_MODEL`. |
| **Plain PostgreSQL** for metrics | One database to run and back up; a `(server_id, timestamp)` index covers every query here. | No automatic downsampling or retention; TimescaleDB would be the next step at real volumes. |

## Limits

- **The data is simulated.** Real hardware would report through SNMP, IPMI/Redfish or an agent, at much higher volume, and would need retention and downsampling.
- A rack-wide fault opens one incident **per server**; nothing correlates them into one rack-level incident yet.
- The AI only sees metrics, not logs or hardware events, so its causes stay fairly generic. Its confidence is the model's own estimate, not a measured probability.
- Each new incident costs one LLM call.

## Testing and CI

```bash
docker compose exec api pytest          # 196 tests: detector, deduplication, incident lifecycle,
                                        # permission matrix, AI failure handling (mocked LLM), SSE…
docker compose exec simulator pytest    # fault math
docker compose exec api ruff check . && docker compose exec api mypy
cd web && npm run lint && npm run typecheck
```

Backend tests run against a separate `<db>_test` database, and each test is rolled back, so dev data is never touched. The LLM is replaced by a fake client: no network, no cost.

**GitHub Actions** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs lint, format check, type-check and tests for the API (against a real Postgres), the simulator and the web app (including a production `next build`) on every push.

## Deployment

```bash
cp .env.example .env    # real secrets, plus DOMAIN=your.domain
docker compose -f docker-compose.prod.yml up -d --build
```

The production stack builds slim, non-root images without hot reload, keeps Postgres/Redis/API private to the Docker network, and puts **Caddy** in front for automatic HTTPS. Details in [`docs/modules/deployment.md`](docs/modules/deployment.md).

## Project structure

```
api/              FastAPI app, worker, migrations, tests
  app/routers/    HTTP endpoints (metrics, racks, servers, incidents, auth, users, stream, diagnosis)
  app/services/   business logic: detector, incidents, events, diagnosis
  app/ai/         LLM client, prompt, context builder, response schema
  app/workers/    ARQ worker (detection + diagnosis jobs)
web/              Next.js dashboard
simulator/        telemetry generator with fault injection
docs/modules/     short "how it works" notes per module
docker-compose.yml        local development (hot reload)
docker-compose.prod.yml   production (Caddy + HTTPS)
```

Each module has a short write-up: [foundation](docs/modules/foundation.md) · [pipeline](docs/modules/pipeline.md) · [dashboard](docs/modules/dashboard.md) · [detection](docs/modules/detection.md) · [auth & real-time](docs/modules/auth-and-realtime.md) · [AI diagnosis](docs/modules/ai-diagnosis.md) · [deployment](docs/modules/deployment.md)

## Roadmap

- Group related incidents (e.g. a rack-wide overheat) into one parent incident
- Editable detection rules per server or metric from the UI
- Metric retention and downsampling (TimescaleDB continuous aggregates)
- Feed logs and hardware events into the AI context
- Notifications (email / Slack) for critical incidents
- Server-side session revocation
