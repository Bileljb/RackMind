# Deployment and CI: how it works

- **Two Compose files, one set of Dockerfiles.** Each Dockerfile has a `dev` and a `prod` target (multi-stage build). `docker-compose.yml` builds `dev`: test tools installed, source mounted, hot reload. `docker-compose.prod.yml` builds `prod`: runtime dependencies only, code baked into the image, non-root user, `restart: unless-stopped`. The prod file sets its own project name (`rackmind-prod`), so its containers and database volume never mix with the dev ones on the same machine.
- **API image (`prod`):** on start it runs `alembic upgrade head`, then the seed script (skipped if data exists), then uvicorn with no `--reload`. `--proxy-headers` makes it trust the `X-Forwarded-*` headers sent by the proxy in front. The worker uses the same image with the ARQ command (no `--watch`).
- **Web image (`prod`):** `next build` with `output: "standalone"` writes a small `server.js` plus only the `node_modules` files it actually uses, so the final image holds no source and no full install. The `/api/*` rewrite target is read at **build** time, so `API_URL` is a build argument (`http://api:8000`).
- **Caddy** (`Caddyfile`) is the only service with open ports (80, 443).
  - It gets and renews a Let's Encrypt certificate for `DOMAIN` by itself, and redirects HTTP to HTTPS.
  - It forwards everything to the Next.js server, which proxies `/api/*` to FastAPI. Postgres, Redis and the API are reachable only inside the Compose network.
  - It compresses responses, except `/api/stream`: compressing Server-Sent Events would hold them in a buffer. For the same reason Next's own gzip is turned off (`compress: false`).
- **Cookies:** prod sets `COOKIE_SECURE=true` by default, so the session cookie is only sent over HTTPS.
- **Deploy on a server** (for example an EC2 instance with Docker installed, ports 22/80/443 open in its security group):
  ```bash
  git clone <repo> && cd rackmind
  cp .env.example .env   # real secrets, DOMAIN=your.domain
  docker compose -f docker-compose.prod.yml up -d --build
  ```
  Update with `git pull`, then the same `up -d --build`. Migrations run on start.
- **Try it locally:** the same command with no `DOMAIN` serves `https://localhost` using Caddy's own local certificate. The browser warns about it, because that certificate isn't trusted outside the container.
- **CI** (`.github/workflows/ci.yml`) runs three jobs in parallel on every push and pull request:
  - `api`: ruff (lint and format), mypy, and pytest against a Postgres service container. Redis is faked in the tests.
  - `simulator`: ruff, mypy, pytest.
  - `web`: eslint, prettier, `tsc`, and `next build`. The build catches Cache Components mistakes that type-checking misses.
