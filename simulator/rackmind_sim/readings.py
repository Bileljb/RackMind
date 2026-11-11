"""Normal (healthy) telemetry: one stable baseline per server, plus random noise per reading."""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerInfo:
    id: int
    hostname: str
    rack_name: str


@dataclass(frozen=True)
class Reading:
    """Sensor values of one server at one instant (the timestamp is added when sending)."""

    server_id: int
    cpu_temp: float
    power_w: float
    cpu_usage_pct: float
    disk_used_pct: float
    memory_used_pct: float
    network_mbps: float


def make_baseline(server_id: int) -> Reading:
    """Pick the typical values of one server, so servers differ from each other.

    Derived from the server id only, so they are the same after every simulator restart, like
    a real machine. Random values per start would look like every server suddenly changing,
    and the detector (rightly) opens incidents for that.
    """
    rng = random.Random(f"baseline-{server_id}")
    return Reading(
        server_id=server_id,
        cpu_temp=rng.uniform(40, 50),
        power_w=rng.uniform(250, 350),
        cpu_usage_pct=rng.uniform(10, 35),
        disk_used_pct=rng.uniform(30, 60),
        memory_used_pct=rng.uniform(35, 55),
        network_mbps=rng.uniform(100, 400),
    )


def normal_reading(baseline: Reading, rng: random.Random) -> Reading:
    """The baseline plus small random noise (Gaussian), like a real sensor jittering."""
    return Reading(
        server_id=baseline.server_id,
        cpu_temp=baseline.cpu_temp + rng.gauss(0, 1.0),
        power_w=max(0.0, baseline.power_w + rng.gauss(0, 10)),
        cpu_usage_pct=clamp_pct(baseline.cpu_usage_pct + rng.gauss(0, 4.0)),
        disk_used_pct=clamp_pct(baseline.disk_used_pct + rng.gauss(0, 0.1)),
        memory_used_pct=clamp_pct(baseline.memory_used_pct + rng.gauss(0, 2.0)),
        network_mbps=max(0.0, baseline.network_mbps + rng.gauss(0, 30)),
    )


def clamp_pct(value: float) -> float:
    return min(100.0, max(0.0, value))
