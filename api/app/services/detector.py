"""Anomaly detector: decides from one server's recent readings whether something is wrong.

Pure functions, no database, so they are easy to unit test with hand-made readings.
Two kinds of rule look at every metric, and the more severe result wins:

- Fixed thresholds (v1): values that are dangerous on any server, e.g. CPU at 80 C.
- Rolling z-score (v2): values that are unusual *for this server*, compared with its own
  last 30 minutes. It catches a drift early, long before a fixed limit is reached.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from statistics import fmean, pstdev

from app.models import Metric, Severity

METRIC_NAMES = (
    "cpu_temp",
    "power_w",
    "cpu_usage_pct",
    "disk_used_pct",
    "memory_used_pct",
    "network_mbps",
)


@dataclass(frozen=True)
class Threshold:
    warning: float
    critical: float


# CPU limits match the dashboard's "hot" and "critical" bands. Power and network have no
# limit that fits every server (their normal level differs per machine): only the z-score
# watches them. CPU usage: a server pinned near 100% for 30s can't keep up with its work.
THRESHOLDS = {
    "cpu_temp": Threshold(warning=70, critical=80),
    "cpu_usage_pct": Threshold(warning=90, critical=98),
    "disk_used_pct": Threshold(warning=85, critical=95),
    "memory_used_pct": Threshold(warning=85, critical=95),
}

# Rules judge the mean of the last 30s (about 6 readings), not a single reading: averaging
# shrinks sensor noise, so one random spike can't open an incident.
RECENT_WINDOW = timedelta(seconds=30)
# The baseline ("normal for this server") is the 30 min before now, minus the last 5 min.
# The gap keeps the start of a slow drift out of the baseline it is compared against.
BASELINE_WINDOW = timedelta(minutes=30)
BASELINE_GAP = timedelta(minutes=5)
# Callers must load at least this much history for the baseline to be complete.
LOOKBACK = BASELINE_WINDOW
# Below this many baseline readings (~2.5 min) the mean and spread are not trustworthy yet.
MIN_BASELINE_SAMPLES = 30
# Floor for the standard deviation. A very steady metric (std near 0) would otherwise turn
# a tiny wobble into a huge z-score. Values are in each metric's unit.
# Only these metrics get a z-score. CPU usage is left out: it is bursty by nature (a cron job,
# a deploy), so "unusual for this server" would fire constantly; its threshold is enough.
MIN_STD = {
    "cpu_temp": 0.5,
    "power_w": 5.0,
    "disk_used_pct": 0.5,
    "memory_used_pct": 1.0,
    "network_mbps": 10.0,
}
Z_INFO = 3.0
Z_WARNING = 6.0


@dataclass(frozen=True)
class Finding:
    """One anomalous metric: how bad it is and why, in words a person can check."""

    metric: str
    severity: Severity
    value: float  # mean of the recent readings
    reason: str


def check_threshold(metric: str, value: float) -> Finding | None:
    limits = THRESHOLDS.get(metric)
    if limits is None:
        return None
    if value >= limits.critical:
        severity, limit = Severity.CRITICAL, limits.critical
    elif value >= limits.warning:
        severity, limit = Severity.WARNING, limits.warning
    else:
        return None
    return Finding(metric, severity, value, f"{value:.1f} is above the {severity} limit {limit:g}")


def z_score(value: float, baseline: Sequence[float], min_std: float) -> float | None:
    """How many standard deviations `value` is above the baseline mean.

    Example: baseline mean 45, std 1, value 48 -> z = 3. None if the baseline is too short.
    """
    if len(baseline) < MIN_BASELINE_SAMPLES:
        return None
    return (value - fmean(baseline)) / max(pstdev(baseline), min_std)


def check_z_score(metric: str, value: float, baseline: Sequence[float]) -> Finding | None:
    """Flag values far *above* normal only.

    Upward only on purpose: right after a fault ends, the baseline still holds the high fault
    values, so a normal reading would look "far below normal" and raise a false alarm.
    """
    min_std = MIN_STD.get(metric)
    if min_std is None:
        return None
    z = z_score(value, baseline, min_std)
    if z is None or z < Z_INFO:
        return None
    severity = Severity.WARNING if z >= Z_WARNING else Severity.INFO
    return Finding(metric, severity, value, f"{z:.1f} standard deviations above its recent normal")


def evaluate(readings: Sequence[Metric]) -> list[Finding]:
    """Findings for one server, judged as of its newest reading. `readings`: oldest first.

    Returns at most one finding per metric (the most severe), and [] when all looks normal.
    Metrics the server doesn't report (None, e.g. temperature on a VPS) are skipped.
    """
    if not readings:
        return []
    now = readings[-1].timestamp
    recent = [r for r in readings if r.timestamp > now - RECENT_WINDOW]
    baseline = [r for r in readings if now - BASELINE_WINDOW <= r.timestamp <= now - BASELINE_GAP]

    findings = []
    for metric in METRIC_NAMES:
        recent_values = _values(recent, metric)
        if not recent_values:
            continue
        value = fmean(recent_values)
        history = _values(baseline, metric)
        candidates = [check_threshold(metric, value), check_z_score(metric, value, history)]
        if found := [c for c in candidates if c is not None]:
            findings.append(max(found, key=lambda finding: finding.severity.rank))
    return findings


def _values(readings: Sequence[Metric], metric: str) -> list[float]:
    """The metric's values in these readings, leaving out the ones that weren't reported."""
    return [value for r in readings if (value := getattr(r, metric)) is not None]
