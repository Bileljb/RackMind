"""Fault injection: time windows during which some servers' readings drift away from normal.

A fault is written `kind:target:start_s:duration_s`, e.g. `overheat:R02:60:600` means
"rack R02 starts overheating 60s after the simulator starts, for 10 minutes".
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from rackmind_sim.readings import Reading, ServerInfo, clamp_pct

# How fast each fault gets worse, per minute since the fault started.
OVERHEAT_DEGREES_PER_MIN = 3.0
OVERHEAT_MAX_EXTRA_DEGREES = 40.0
FAN_WATTS_PER_DEGREE = 3.0  # hotter servers spin their fans harder and draw more power
DISK_FILL_PCT_PER_MIN = 3.0
MEMORY_LEAK_PCT_PER_MIN = 2.5
MEMORY_LEAK_CEILING_PCT = 99.5


class FaultKind(StrEnum):
    OVERHEAT = "overheat"  # target: a rack name, every server in it heats up
    DISK_FILL = "disk_fill"  # target: a hostname
    MEMORY_LEAK = "memory_leak"  # target: a hostname


@dataclass(frozen=True)
class Fault:
    kind: FaultKind
    target: str
    start_s: float
    duration_s: float

    def __str__(self) -> str:
        return f"{self.kind}:{self.target}"

    def affects(self, server: ServerInfo) -> bool:
        if self.kind is FaultKind.OVERHEAT:
            return server.rack_name == self.target
        return server.hostname == self.target

    def is_active(self, elapsed_s: float) -> bool:
        return self.start_s <= elapsed_s < self.start_s + self.duration_s

    def apply(self, reading: Reading, elapsed_s: float) -> Reading:
        """Return the reading as distorted by this fault, `elapsed_s` into the simulation."""
        minutes_in = (elapsed_s - self.start_s) / 60
        match self.kind:
            case FaultKind.OVERHEAT:
                extra = min(minutes_in * OVERHEAT_DEGREES_PER_MIN, OVERHEAT_MAX_EXTRA_DEGREES)
                return replace(
                    reading,
                    cpu_temp=reading.cpu_temp + extra,
                    power_w=reading.power_w + extra * FAN_WATTS_PER_DEGREE,
                )
            case FaultKind.DISK_FILL:
                filled = reading.disk_used_pct + minutes_in * DISK_FILL_PCT_PER_MIN
                return replace(reading, disk_used_pct=clamp_pct(filled))
            case FaultKind.MEMORY_LEAK:
                leaked = reading.memory_used_pct + minutes_in * MEMORY_LEAK_PCT_PER_MIN
                return replace(reading, memory_used_pct=min(leaked, MEMORY_LEAK_CEILING_PCT))


def parse_fault(spec: str) -> Fault:
    """Parse `kind:target:start_s:duration_s`. Raises ValueError with a readable message."""
    parts = spec.strip().split(":")
    if len(parts) != 4:
        raise ValueError(f"fault {spec!r} must look like kind:target:start_s:duration_s")
    kind, target, start, duration = parts
    try:
        fault_kind = FaultKind(kind)
    except ValueError:
        choices = ", ".join(FaultKind)
        raise ValueError(f"unknown fault kind {kind!r} (choose from: {choices})") from None
    try:
        start_s, duration_s = float(start), float(duration)
    except ValueError:
        raise ValueError(f"fault {spec!r}: start_s and duration_s must be numbers") from None
    if start_s < 0 or duration_s <= 0:
        raise ValueError(f"fault {spec!r}: start must be >= 0 and duration > 0")
    return Fault(fault_kind, target, start_s, duration_s)


def apply_faults(
    reading: Reading, server: ServerInfo, faults: list[Fault], elapsed_s: float
) -> Reading:
    for fault in faults:
        if fault.affects(server) and fault.is_active(elapsed_s):
            reading = fault.apply(reading, elapsed_s)
    return reading
