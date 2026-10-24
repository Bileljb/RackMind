# Rackmind: Project Plan for Claude Code

> AI-assisted data center monitoring and incident management platform.
> Showcase project, built to be deployed and presented as a portfolio piece.
> **Deadline: Dec 31, 2026** (start: Oct 24, 2026).

---

## 1. Project Overview

Rackmind simulates a data center (racks, servers, sensors), ingests telemetry, detects anomalies, opens incidents, and uses an LLM to suggest a probable cause and remediation steps. Operators and engineers handle incidents through a role-based workflow.

**Core flow**

```
Simulator -> FastAPI ingestion -> PostgreSQL
                                     |
                         Detector worker (Redis queue)
                                     |
                              Incident created
                                     |
                         AI worker (LLM diagnosis)
                                     |
          Next.js dashboard <- SSE live feed <- API
```

**Roles**
- `operator`: views dashboard, acknowledges incidents, comments.
- `engineer`: everything an operator can do, plus resolves incidents, edits detection rules, sees AI diagnosis details.
- `admin`: everything, plus user management.

---

## 2. Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12), async, Pydantic v2 |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic |
| Database | PostgreSQL (TimescaleDB optional, only if time allows) |
| Queue / workers | Redis + ARQ (or Celery) |
| Frontend | Next.js (App Router) + TypeScript + Tailwind CSS |
| Real-time | Server-Sent Events (SSE), Redis pub/sub |
| Auth | JWT (httpOnly cookies), RBAC |
| AI | Groq API (`groq` Python SDK), JSON output validated with Pydantic; model name configurable via env |
| Tests | pytest + httpx (backend), basic component/e2e checks (frontend) |
| Lint / format | ruff, mypy (backend); eslint, prettier (frontend) |
| Infra | Docker Compose, GitHub Actions, AWS (EC2, optionally RDS and S3) |

---

## 3. Repository Structure

```
rackmind/
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/          # config (Pydantic settings), security, db session
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── routers/       # metrics, racks, servers, incidents, auth, users, stream
│   │   ├── services/      # business logic (incidents, detection, ai)
│   │   ├── workers/       # detector and AI worker tasks
│   │   └── deps.py        # dependency injection (db, current user, role guards)
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── web/                   # Next.js app
├── simulator/             # telemetry + fault injection
├── docs/                  # architecture diagram, decisions, module notes
├── docker-compose.yml
├── .github/workflows/
├── RACKMIND_PLAN.md
└── README.md
```

---

## 4. Rules for Claude Code (READ FIRST)

The owner is a full stack developer (React, Node/Express/TypeScript, PostgreSQL/Prisma, JWT). He is **new to FastAPI, Next.js, queues, SSE, Docker, AWS and LLM integration**. He delegates heavy code to you but must **understand all of it**. Work in teaching mode:

1. **Work one checklist item at a time.** Do not jump ahead or generate several phases at once.
2. **Before writing code**, state in 2-4 lines what you are about to build and why.
3. **After writing code**, explain each new file briefly (purpose, key functions, how it connects to the rest). Use plain language.
4. **Introduce new concepts simply** (e.g. async, dependency injection, queues, SSE) with a small example before applying them.
5. **Do NOT write these for the owner. Guide him and review his code instead:**
   - the anomaly detection logic (Phase 4)
   - the LLM prompt and response schema (Phase 6)
6. **Write a short "how it works" note** in `docs/modules/<module>.md` after each module (5-10 lines).
7. **Quality bar:** type hints everywhere, small functions, no dead code, meaningful names, tests for business logic, no secrets in git (use `.env` + `.env.example`).
8. **Never run destructive commands** (dropping DBs, deleting volumes, force-pushing) without asking.
9. **Commit after each completed checklist group** with a clear message (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
10. If something in this plan is unclear or a better option exists, **say so and ask** before deviating.
11. The AI feature only **suggests**; it never executes actions on infrastructure.

---

## 5. Phases and Checklists

### Phase 1: Foundation (Oct 24 - Nov 3)

**Learn:** Linux CLI basics, Docker Compose, FastAPI project structure, Pydantic settings, SQLAlchemy 2.0 async, Alembic.

- [x] Initialize git repo, `.gitignore`, `.env.example`
- [x] Create folder structure from section 3
- [x] Set up `api/` with `pyproject.toml`, ruff, mypy, pytest config
- [x] Pydantic settings class reading from environment
- [ ] `docker-compose.yml` with Postgres, Redis, and the API (hot reload)
- [ ] Async DB session setup + dependency (`get_db`)
- [ ] SQLAlchemy models: `User`, `Rack`, `Server`, `Metric`, `Incident`, `Comment`, `AuditLog`
- [ ] Alembic initial migration
- [ ] Seed script: 4 racks, 20 servers, 3 users (one per role)
- [ ] `GET /health` endpoint + first pytest test
- [ ] `docs/modules/foundation.md` note

**Done when:** `docker compose up` starts everything, migrations run, seed data is present, health test passes.

---

### Phase 2: Data pipeline (Nov 4 - Nov 13)

**Learn:** async Python, Pydantic validation, httpx, pytest fixtures.

- [ ] Metric schema: server_id, timestamp, cpu_temp, power_w, disk_used_pct, memory_used_pct, network_mbps
- [ ] `POST /metrics` ingestion (single and batch), validated with Pydantic
- [ ] Read endpoints: list racks, list servers, latest metrics per server, metric history with time range
- [ ] Index on `(server_id, timestamp)`
- [ ] Simulator service: emits normal readings with noise every 5s for all servers
- [ ] Fault injector with 3 faults: overheating rack, disk filling/failing, memory leak
- [ ] Configurable fault schedule (CLI flags or env)
- [ ] Tests: ingestion validation, read endpoints
- [ ] `docs/modules/pipeline.md` note

**Done when:** running the simulator fills the DB and faults are visible in the stored data.

---

### Phase 3: Dashboard (Nov 14 - Nov 23)

**Learn:** nextjs.org/learn (App Router, server vs client components, route handlers, data fetching).

- [ ] Next.js + TypeScript + Tailwind setup, add `web` to Docker Compose
- [ ] Typed API client (types matching backend schemas)
- [ ] Layout and navigation
- [ ] Rack grid / heatmap colored by temperature
- [ ] Server detail page with metric charts (Recharts)
- [ ] Polling every 5s for fresh data
- [ ] Loading and error states
- [ ] `docs/modules/dashboard.md` note

**Done when:** you can start the simulator and watch a fault appear on the dashboard.

---

### Phase 4: Detection and incidents (Nov 24 - Dec 3)

**Learn:** task queues (ARQ/Celery + Redis), rolling mean and standard deviation, z-score.

> The owner writes the detection logic. Claude Code explains concepts, scaffolds the worker, and reviews.

- [ ] Worker setup (ARQ/Celery) + Docker Compose service
- [ ] Enqueue a detection job when metrics arrive (or on a schedule)
- [ ] Detection v1: fixed thresholds per metric (**owner writes**)
- [ ] Detection v2: rolling baseline + z-score (**owner writes**)
- [ ] Severity levels (info, warning, critical)
- [ ] Incident creation with **deduplication** (one ongoing fault = one incident)
- [ ] Auto-resolve suggestion when metrics return to normal
- [ ] Incident lifecycle: `open -> acknowledged -> resolved`
- [ ] Assignment, comments, audit log entries on every state change
- [ ] Incident endpoints (list with filters, detail, transitions, comments)
- [ ] Unit tests for detector (normal data, each fault type, deduplication)
- [ ] `docs/modules/detection.md` note

**Done when:** one injected fault creates exactly one incident, which moves through the full lifecycle.

---

### Phase 5: Real-time and auth (Dec 4 - Dec 13)

**Learn:** SSE, Redis pub/sub, JWT with httpOnly cookies, Next.js middleware, RBAC.

- [ ] Registration disabled for public, admin creates users
- [ ] Login/logout, password hashing, JWT in httpOnly cookie
- [ ] Role guard dependencies in FastAPI (`require_role(...)`)
- [ ] Enforce permissions on all endpoints (API first)
- [ ] Redis pub/sub publishing on new incident / state change
- [ ] `GET /stream` SSE endpoint, authenticated
- [ ] Next.js: login page, middleware protecting routes, `EventSource` live incident feed
- [ ] UI hides actions the role cannot perform
- [ ] Admin user management page
- [ ] Permission tests (each role vs each sensitive endpoint)
- [ ] `docs/modules/auth-and-realtime.md` note

**Done when:** each role can do only what it should, and incidents appear live without refreshing.

---

### Phase 6: AI diagnosis (Dec 14 - Dec 20)

**Learn:** Groq API basics (chat completions, JSON mode / structured outputs, rate limits), Pydantic validation of LLM responses, prompt design.

> The owner writes the prompt and the response schema. Claude Code scaffolds the integration and reviews.

- [ ] Groq client wrapper with timeout, retries with backoff (handle 429 rate limits), `GROQ_API_KEY` and `GROQ_MODEL` from env (add both to `.env.example`; check the Groq docs for current model names and structured-output support)
- [ ] Response schema (Pydantic): `probable_cause`, `confidence` (0-1), `recommended_steps[]`, `evidence[]` (**owner designs**)
- [ ] Prompt: recent metrics window (e.g. last 30 min), incident info, similar past incidents (**owner writes**)
- [ ] AI worker job triggered when an incident is created
- [ ] Validate output with Pydantic; handle invalid JSON, timeouts, API errors (store failure state)
- [ ] Store diagnosis with the incident
- [ ] UI: diagnosis panel on the incident page with confidence and evidence shown
- [ ] "Was this helpful?" feedback button stored in DB
- [ ] Clear UI label that suggestions are AI-generated and never auto-executed
- [ ] Tests with a mocked LLM client (valid, invalid, timeout)
- [ ] `docs/modules/ai-diagnosis.md` note

**Done when:** a new incident automatically gets a validated diagnosis, and failures degrade gracefully.

---

### Phase 7: Ship (Dec 21 - Dec 31)

**Learn:** GitHub Actions, AWS basics (EC2, security groups, IAM, optionally RDS and S3), HTTPS basics.

- [ ] GitHub Actions: lint + tests on every push
- [ ] Production Docker Compose / images (no dev flags, no hot reload)
- [ ] Launch EC2 instance, configure security groups, SSH key access
- [ ] Deploy with Docker Compose, environment variables via `.env` on the server
- [ ] Domain or public URL, HTTPS (reverse proxy such as Caddy or Nginx)
- [ ] Optional: move Postgres to RDS, backups to S3
- [ ] Demo seed data and a demo user per role
- [ ] README: overview, screenshot/GIF, architecture diagram, setup in one command, decisions and trade-offs, limits (simulated data), roadmap
- [ ] 2-minute demo video (fault injected, incident appears live, AI diagnosis, role difference)
- [ ] Portfolio page for Rackmind (description, links, video, repo)
- [ ] Share the project publicly (pin the repo on GitHub, post on LinkedIn with the demo video)
- [ ] Final pass: remove dead code, check no secrets in git history

**Done when:** live URL works, one-command local setup works, README and video are finished, and the project is shared publicly.

---

## 6. Priorities if Behind Schedule

Cut in this order:
1. TimescaleDB, RDS, S3
2. Extra fault types (keep at least 2)
3. Admin user management UI (keep roles in the API)
4. Frontend polish

**Never cut:** deployment, tests on detector and permissions, the demo video, the README.

---

## 7. Definition of Done (Whole Project)

- [ ] Live deployed URL
- [ ] `docker compose up` runs everything locally
- [ ] Tests for detector, permissions, and AI failure handling pass in CI
- [ ] Architecture diagram and "decisions and trade-offs" section in README
- [ ] 2-minute demo video
- [ ] Portfolio page published
- [ ] Owner can explain every module, the async design, DB session handling, the detector, and how LLM output is validated
- [ ] Project shared publicly (GitHub pin, LinkedIn post with demo video)

---

## 8. Interview Prep Notes (Owner)

Be ready to answer:
- Why async FastAPI, and how do dependency injection and DB sessions work here?
- How does the detector avoid duplicate incidents?
- Why z-score, and what are its weaknesses?
- How do you handle bad or slow LLM output, and why does the AI only suggest?
- How are permissions enforced, and why on the API first?
- What would change with real hardware telemetry (SNMP/IPMI, volume, retention)?
