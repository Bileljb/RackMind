# Targets: `dev` (next dev, source mounted by Compose) and `prod` (built, minimal image).
FROM node:24-alpine AS deps

WORKDIR /app

# Install dependencies first so Docker caches this layer until package*.json changes.
# `npm install` rather than `npm ci`: a lockfile written on Windows can miss optional
# Linux-only packages, which makes `npm ci` refuse to run. Versions still come from the lock.
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund


# ---------- dev ----------
FROM deps AS dev
COPY . .
EXPOSE 3000
# --hostname 0.0.0.0: listen on all interfaces so the port is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]


# ---------- build: `next build` with output "standalone" ----------
FROM deps AS build
# The /api/* rewrite target is read from next.config.ts at BUILD time and baked into the
# output, so the API address must be known here, not only when the container starts.
ARG API_URL=http://api:8000
ENV API_URL=$API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY . .
# public/ may be empty, and git doesn't keep empty folders: make sure it exists for the copy below.
RUN mkdir -p public && npm run build


# ---------- prod: only the traced server files, no node_modules install, no source ----------
FROM node:24-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
# `standalone` holds server.js plus the node_modules it needs; static assets are copied
# next to it so server.js can serve them (see Next.js docs: next.config output).
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
