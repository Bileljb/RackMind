# Simulation mode: how it works

- **Two modes, switched in the header:** **Live** shows real servers (`servers.source = 'agent'`), **Simulation** shows the 20 seeded servers (`'simulated'`). Every read the dashboard makes passes `?source=` (`GET /racks`, `/servers`, `/metrics/latest`, `/incidents`), so each mode only ever sees its own servers and incidents. Both kinds of data live in the same tables; nothing is copied.
- **The mode is per browser**, not per account (`web/src/lib/mode.ts`): kept in `localStorage`, readable from the URL (`/?mode=simulation` opens the demo directly). With no choice yet, the app opens in Live if any real server exists, otherwise in Simulation, so a fresh install shows something.
- **The simulator only runs while someone is in Simulation mode.** It is a lease in Redis (`app/services/simulation.py`):
  1. Entering Simulation mode sends `POST /simulation/keepalive`, which sets the key `simulation:active` with a 90 s expiry. The browser repeats it every 30 s.
  2. Before each 5 s cycle the simulator asks `GET /simulation/status` (with its API key) and sleeps while the answer is `{"active": false}`.
  3. Switching back to Live sends `DELETE /simulation/keepalive`: the simulator stops on its next cycle. Closing the tab simply stops the refreshes, and the key expires within 90 s.
- **Why a lease and not a count of viewers:** nothing has to notice that a tab closed or crashed; the expiry handles it. Several people in Simulation mode just refresh the same key, and they share one simulated data center.
- **Each start replays the demo:** the fault schedule (`SIM_FAULTS`, default in `docker-compose.yml`) counts from when the simulation starts. The default is a CPU spike on `r02-srv03` at +20 s (a critical incident within about a minute), then a memory leak, an overheating rack R04 and a filling disk.
- **Cost:** while nobody watches the demo it produces no readings, detection jobs or AI diagnoses, which keeps the Groq free-tier quota for real incidents.
- **Live events:** the incident stream (`/stream`) still carries every event. The "new incident" toast only shows incidents on the current mode's servers, and lists refetch with their own `?source=` filter.
- **Known limit:** an unresolved simulated incident blocks new ones on the same server (one active incident per server), so a server that still has an old demo incident only gets its severity raised. Resolve old demo incidents to see the scenario open fresh ones.
- **Tests:** `api/tests/test_simulation.py` (lease, stop, simulator key), `test_read_endpoints.py` and `test_incidents.py` (`source` filters), `simulator/tests/test_status.py` (paused when inactive or when the API fails).
