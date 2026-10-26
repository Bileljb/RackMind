"""Synthetic telemetry for detector tests: a steady server with the simulator's noise levels."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from random import Random

from app.models import Metric

INTERVAL = timedelta(seconds=5)
# (typical value, noise std) per metric, the same noise as `simulator/rackmind_sim/readings.py`.
NORMAL = {
    "cpu_temp": (45.0, 1.0),
    "power_w": (300.0, 10.0),
    "disk_used_pct": (45.0, 0.1),
    "memory_used_pct": (45.0, 2.0),
    "network_mbps": (250.0, 30.0),
}

# A fault: given minutes since the series started, how much to add to each metric.
Fault = Callable[[float], dict[str, float]]


def no_fault(minute: float) -> dict[str, float]:
    return {}


def ramp(metric: str, per_minute: float, start_min: float, end_min: float = 1e9) -> Fault:
    """`metric` grows by `per_minute` from `start_min`, and is back to normal after `end_min`."""

    def offsets(minute: float) -> dict[str, float]:
        if start_min <= minute < end_min:
            return {metric: per_minute * (minute - start_min)}
        return {}

    return offsets


def series(
    server_id: int,
    minutes: float,
    *,
    fault: Fault = no_fault,
    base: dict[str, float] | None = None,
    end: datetime | None = None,
    seed: int = 0,
) -> list[Metric]:
    """Readings every 5s over `minutes`, oldest first, the last one at `end` (default: now).

    `base` overrides typical values, e.g. {"disk_used_pct": 80} for an almost full disk.
    """
    rng = Random(seed)
    end = end or datetime.now(UTC)
    count = int(minutes * 60 / INTERVAL.total_seconds())
    readings = []
    for i in range(count):
        minute = i * INTERVAL.total_seconds() / 60
        extra = fault(minute)
        values = {
            name: (base or {}).get(name, typical) + rng.gauss(0, noise) + extra.get(name, 0.0)
            for name, (typical, noise) in NORMAL.items()
        }
        timestamp = end - (count - 1 - i) * INTERVAL
        readings.append(Metric(server_id=server_id, timestamp=timestamp, **values))
    return readings
