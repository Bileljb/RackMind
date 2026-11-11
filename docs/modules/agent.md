# Agent (real servers): how it works

- **What it is:** `agent/rackmind_agent.py`, one Python file using `psutil`. Every 5 s it reads CPU usage, memory used, disk used (one filesystem, `/` by default), network traffic in Mbit/s (the difference between two counter readings) and the CPU temperature when the machine has a sensor (most VPSes don't), then posts one reading to `POST /metrics/batch`.
- **Register the server first**, on the machine running the API:

  ```bash
  docker compose exec api python -m app.add_server web-01 --group Production
  # Added web-01 to Production. Agent setting: RACKMIND_SERVER_ID=21
  ```

  The group (a `racks` row) is created on first use and becomes a column on the Live dashboard. The server gets `source = 'agent'`.
- **Try it locally** (any machine with Python 3.12+, against the dev stack):

  ```bash
  pip install httpx psutil
  RACKMIND_URL=http://localhost:8000 RACKMIND_KEY=<INGEST_API_KEY> RACKMIND_SERVER_ID=21 \
    python agent/rackmind_agent.py
  ```

- **Install on a Linux server** as a systemd service (`agent/rackmind-agent.service`):

  ```bash
  sudo mkdir -p /opt/rackmind-agent && sudo cp rackmind_agent.py /opt/rackmind-agent/
  sudo python3 -m venv /opt/rackmind-agent/venv
  sudo /opt/rackmind-agent/venv/bin/pip install httpx psutil
  sudo nano /etc/rackmind-agent.env      # the three RACKMIND_* lines above
  sudo chmod 600 /etc/rackmind-agent.env # the key is a secret
  sudo cp rackmind-agent.service /etc/systemd/system/
  sudo systemctl daemon-reload && sudo systemctl enable --now rackmind-agent
  journalctl -u rackmind-agent -f        # logs
  ```

  `RACKMIND_URL` is the API base: `https://<domain>/api` in production (through Caddy and Next.js), `http://<host>:8000` against the dev stack. Optional: `RACKMIND_INTERVAL` (seconds) and `RACKMIND_DISK_PATH`.
- **Update:** copy the new file over and `systemctl restart rackmind-agent`. **Uninstall:** `systemctl disable --now rackmind-agent`, then remove the unit, `/opt/rackmind-agent` and `/etc/rackmind-agent.env`.
- **Errors:** a 401 means a wrong key; a 422 means an unknown server id or a machine clock more than 5 minutes ahead. If the API is unreachable the reading is dropped and the next one is tried 5 s later. A gap longer than the heartbeat limit opens a "not reporting" incident (see `detection.md`).
- **Known limitations (deliberate, for a portfolio scope):**
  - **Shared key:** agents use the same `INGEST_API_KEY` as the simulator, so any agent could post readings for any server. Per-server tokens (hashed, revocable) are the production fix.
  - **No buffering:** readings taken while the API is down are lost, not sent later.
  - **No install script or package:** the steps above are manual.
- **Tests:** `agent/tests/test_agent.py` (network rate maths, counter reset, payload shape, config errors). `api/tests/test_add_server.py` covers the registration command.
