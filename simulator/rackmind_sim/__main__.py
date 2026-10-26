"""Entry point: `python -m rackmind_sim`. Sends one batch of readings per interval, forever."""

import asyncio
import contextlib
import logging
import random
from dataclasses import asdict
from datetime import UTC, datetime

import httpx

from rackmind_sim.config import Config, parse_config
from rackmind_sim.faults import Fault, apply_faults
from rackmind_sim.readings import Reading, ServerInfo, make_baseline, normal_reading

STARTUP_RETRY_DELAY_S = 3.0

log = logging.getLogger("rackmind_sim")


async def fetch_servers(client: httpx.AsyncClient) -> list[ServerInfo]:
    racks = (await client.get("/racks")).raise_for_status().json()
    servers = (await client.get("/servers")).raise_for_status().json()
    rack_names = {rack["id"]: rack["name"] for rack in racks}
    return [ServerInfo(s["id"], s["hostname"], rack_names[s["rack_id"]]) for s in servers]


async def wait_for_servers(client: httpx.AsyncClient) -> list[ServerInfo]:
    """The API may still be starting (migrations, seed): retry until it answers."""
    while True:
        try:
            return await fetch_servers(client)
        except httpx.HTTPError as error:
            log.warning("API not ready (%s), retrying in %ss", error, STARTUP_RETRY_DELAY_S)
            await asyncio.sleep(STARTUP_RETRY_DELAY_S)


def check_fault_targets(faults: list[Fault], servers: list[ServerInfo]) -> None:
    """Fail fast on a typo like `overheat:R09`, instead of silently injecting nothing."""
    for fault in faults:
        if not any(fault.affects(server) for server in servers):
            raise SystemExit(f"Fault {fault}: no server matches target {fault.target!r}")


def to_payload(reading: Reading, timestamp: datetime) -> dict[str, object]:
    return {**asdict(reading), "timestamp": timestamp.isoformat()}


def build_batch(
    servers: list[ServerInfo],
    baselines: dict[int, Reading],
    faults: list[Fault],
    elapsed_s: float,
    rng: random.Random,
) -> list[dict[str, object]]:
    """One reading per server, all stamped with the same time."""
    now = datetime.now(UTC)
    batch = []
    for server in servers:
        reading = normal_reading(baselines[server.id], rng)
        reading = apply_faults(reading, server, faults, elapsed_s)
        batch.append(to_payload(reading, now))
    return batch


async def run(config: Config) -> None:
    rng = random.Random(config.seed)
    headers = {"X-API-Key": config.api_key}
    async with httpx.AsyncClient(base_url=config.api_url, headers=headers, timeout=10) as client:
        servers = await wait_for_servers(client)
        if not servers:
            raise SystemExit("The API has no servers. Run the seed script first.")
        check_fault_targets(config.faults, servers)
        baselines = {server.id: make_baseline(server.id) for server in servers}
        for fault in config.faults:
            log.info("Scheduled %s at +%ss for %ss", fault, fault.start_s, fault.duration_s)

        loop = asyncio.get_running_loop()
        started = loop.time()
        while True:
            tick = loop.time()
            elapsed_s = tick - started
            payload = build_batch(servers, baselines, config.faults, elapsed_s, rng)
            active = [str(f) for f in config.faults if f.is_active(elapsed_s)] or ["none"]
            try:
                (await client.post("/metrics/batch", json=payload)).raise_for_status()
                log.info("Sent %d readings (active faults: %s)", len(payload), ", ".join(active))
            except httpx.HTTPError as error:
                # Keep going: a short API outage should not kill the simulator.
                log.error("Failed to send readings: %s", error)
            await asyncio.sleep(max(0.0, config.interval_s - (loop.time() - tick)))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # we already log each batch ourselves
    with contextlib.suppress(KeyboardInterrupt):  # Ctrl+C exits quietly
        asyncio.run(run(parse_config()))


if __name__ == "__main__":
    main()
