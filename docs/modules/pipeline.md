# Data pipeline: how it works

- **Flow:** `simulator` (20 readings every 5s, only in Simulation mode) and `rackmind-agent` on real servers -> `POST /metrics/batch` -> `metrics` table -> read endpoints.
- **Validation** lives in `app/schemas/metric.py` (`MetricIn`). Pydantic rejects bad values with a 422 before any DB work: percentages outside 0-100, negative power/network, CPU temp outside -20..150 C, timestamps without a timezone, or more than 5 minutes in the future. `cpu_temp`, `power_w` and `cpu_usage_pct` are optional: real servers rarely have temperature or power sensors. Unknown `server_id`s are checked in `app/services/metrics.py` and also give a 422 that lists them.
- **Batches are all-or-nothing:** one invalid reading rejects the whole batch. A batch has 1 to 1000 readings and is written with a single `INSERT` (one DB round trip).
- **Endpoints:** `GET /racks?source=`, `GET /servers?rack_id=&source=`, `GET /metrics/latest?rack_id=&source=` (newest reading per server), and `GET /servers/{id}/metrics?start=&end=` (oldest first, `[start, end)`, last hour by default, 24h max).
- **Index** `ix_metrics_server_id_timestamp` on `(server_id, timestamp)` serves both "time range of one server" and "newest reading of one server". `latest` uses a `LATERAL` join: one quick index lookup per server instead of scanning the whole table.
- **Simulator** (`simulator/rackmind_sim/`): each server gets a random baseline (`readings.py`) plus Gaussian noise every tick. Faults (`faults.py`) are time windows that push values further from normal the longer they run, then stop, so readings go back to normal:
  - `overheat:<rack>`: +3 C/min, capped at +40 C, with power rising alongside it.
  - `disk_fill:<host>`: +3 %/min, capped at 100%.
  - `memory_leak:<host>`: +2.5 %/min, capped at 99.5%.
  - `cpu_spike:<host>`: CPU usage pinned at 99% at once (and +12 °C): a critical incident within a minute, for demos.
- **Fault schedule:** `--fault kind:target:start_s:duration_s` (repeatable), or `SIM_FAULTS` in `.env` (comma-separated). Times count from when the simulation starts (see `simulation-mode.md`). A target that matches no server stops the simulator at startup.
- **Tests:** `docker compose exec api pytest` runs against a separate `<db>_test` database. Each test's changes are rolled back. `docker compose exec simulator pytest` tests the fault math.
