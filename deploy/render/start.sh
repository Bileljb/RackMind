#!/bin/sh
# Runs the whole backend in one container (Render free plan): migrations and seed once,
# then the worker and the simulator in the background, and the API in the foreground.
# Render sends traffic to $PORT and restarts the container if the API exits.
set -e
PORT="${PORT:-8000}"

alembic upgrade head
python -m app.seed

# Background processes are restarted if they crash; the container's life follows the API.
keep_running() {
  while true; do
    "$@" || echo "$1 exited with status $?, restarting in 5 s" >&2
    sleep 5
  done
}

keep_running arq app.workers.main.WorkerSettings --custom-log-dict app.workers.main.LOG_CONFIG &

# The simulator posts to the API inside this container, with the same ingest key.
export SIM_API_URL="http://localhost:$PORT" SIM_API_KEY="$INGEST_API_KEY"
keep_running python -m rackmind_sim &

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips='*'
