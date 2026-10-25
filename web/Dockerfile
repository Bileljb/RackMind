# Development image for the dashboard. Production image comes in Phase 7.
FROM node:24-alpine

WORKDIR /app

# Install dependencies first so Docker caches this layer until package*.json changes.
# `npm install` rather than `npm ci`: a lockfile written on Windows can miss optional
# Linux-only packages, which makes `npm ci` refuse to run. Versions still come from the lock.
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 3000
# --hostname 0.0.0.0: listen on all interfaces so the port is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
