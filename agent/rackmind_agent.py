"""rackmind-agent: sends this machine's metrics to Rackmind every few seconds.

    RACKMIND_URL=https://rackmind.example.com/api \
    RACKMIND_KEY=<INGEST_API_KEY> \
    RACKMIND_SERVER_ID=21 \
    python rackmind_agent.py

Get the server id from `python -m app.add_server <hostname> --group <group>` on the API.
Metrics: CPU usage, memory, disk (one filesystem), network traffic, and CPU temperature when
the machine exposes a sensor (most VPSes don't; the API accepts readings without it).
If the API can't be reached, the reading is dropped and the next one is tried 5s later:
Rackmind's heartbeat notices the gap if it lasts longer than a minute.
"""

import contextlib
import logging
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import psutil

log = logging.getLogger("rackmind_agent")

# Sensor groups that hold the CPU package temperature on common hardware (Intel, AMD, Pi).
CPU_SENSORS = ("coretemp", "k10temp", "cpu_thermal", "zenpower")


@dataclass(frozen=True)
class Config:
    url: str  # API base URL, e.g. https://rackmind.example.com/api
    key: str  # the API's INGEST_API_KEY, sent as X-API-Key
    server_id: int
    interval_s: float
    disk_path: str  # filesystem whose usage is reported


def load_config(env: Mapping[str, str]) -> Config:
    """Read settings from environment variables. Exits with a clear message if one is missing."""
    missing = [
        name for name in ("RACKMIND_URL", "RACKMIND_KEY", "RACKMIND_SERVER_ID") if not env.get(name)
    ]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")
    try:
        server_id = int(env["RACKMIND_SERVER_ID"])
        interval_s = float(env.get("RACKMIND_INTERVAL", "5"))
    except ValueError as error:
        raise SystemExit(f"Invalid setting: {error}") from None
    return Config(
        url=env["RACKMIND_URL"].rstrip("/"),
        key=env["RACKMIND_KEY"],
        server_id=server_id,
        interval_s=interval_s,
        disk_path=env.get("RACKMIND_DISK_PATH", "/"),
    )


@dataclass(frozen=True)
class NetworkSample:
    """Total bytes sent + received since boot, and when they were read (monotonic seconds)."""

    total_bytes: int
    at: float


def network_mbps(previous: NetworkSample, current: NetworkSample) -> float:
    """Average traffic between two samples, in megabits per second.

    The OS only gives running totals, so the rate is the difference over the time between.
    Example: 12.5 MB more after 5s -> 12_500_000 * 8 / 5 / 1e6 = 20 Mbit/s.
    """
    seconds = current.at - previous.at
    if seconds <= 0:
        return 0.0
    # A counter that went down was reset (interface restarted): count from zero, not negative.
    transferred = max(0, current.total_bytes - previous.total_bytes)
    return transferred * 8 / seconds / 1_000_000


def sample_network() -> NetworkSample:
    counters = psutil.net_io_counters()
    return NetworkSample(counters.bytes_sent + counters.bytes_recv, time.monotonic())


def cpu_temperature() -> float | None:
    """The CPU temperature in Celsius, or None if this machine has no readable sensor."""
    read_sensors = getattr(psutil, "sensors_temperatures", None)  # Linux and FreeBSD only
    sensors = read_sensors() if read_sensors else {}
    for name in CPU_SENSORS:
        if sensors.get(name):
            return float(sensors[name][0].current)
    return None


def build_reading(
    server_id: int,
    timestamp: datetime,
    *,
    cpu_usage_pct: float,
    memory_used_pct: float,
    disk_used_pct: float,
    network_mbps: float,
    cpu_temp: float | None,
) -> dict[str, object]:
    """One reading in the shape `POST /metrics/batch` expects (the API's `MetricIn`)."""
    return {
        "server_id": server_id,
        "timestamp": timestamp.isoformat(),
        "cpu_usage_pct": round(cpu_usage_pct, 1),
        "memory_used_pct": round(memory_used_pct, 1),
        "disk_used_pct": round(disk_used_pct, 1),
        "network_mbps": round(network_mbps, 3),
        "cpu_temp": round(cpu_temp, 1) if cpu_temp is not None else None,
    }


def collect(config: Config, previous: NetworkSample) -> tuple[dict[str, object], NetworkSample]:
    """Read every metric now. Returns the reading and the network sample for next time."""
    current = sample_network()
    reading = build_reading(
        config.server_id,
        datetime.now(UTC),
        cpu_usage_pct=psutil.cpu_percent(),  # since the previous call: one interval's average
        memory_used_pct=psutil.virtual_memory().percent,
        disk_used_pct=psutil.disk_usage(config.disk_path).percent,
        network_mbps=network_mbps(previous, current),
        cpu_temp=cpu_temperature(),
    )
    return reading, current


def send(client: httpx.Client, reading: dict[str, object]) -> None:
    try:
        response = client.post("/metrics/batch", json=[reading])
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        # 401: wrong key. 422: unknown server id, or this machine's clock is far off.
        log.error(
            "API refused the reading (%s): %s", error.response.status_code, error.response.text
        )
    except httpx.HTTPError as error:
        log.warning("Could not reach the API, will try again next interval: %s", error)


def run(config: Config) -> None:
    psutil.cpu_percent()  # the first call has nothing to compare with: start the clock now
    network = sample_network()
    headers = {"X-API-Key": config.key}
    with httpx.Client(base_url=config.url, headers=headers, timeout=10) as client:
        log.info(
            "Sending metrics for server %s to %s every %ss",
            config.server_id,
            config.url,
            config.interval_s,
        )
        next_at = time.monotonic()
        while True:
            # A fixed cadence: wait first, so CPU usage is averaged over a full interval.
            next_at += config.interval_s
            time.sleep(max(0.0, next_at - time.monotonic()))
            reading, network = collect(config, network)
            send(client, reading)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    with contextlib.suppress(KeyboardInterrupt):  # Ctrl+C exits quietly
        run(load_config(os.environ))


if __name__ == "__main__":
    main()
