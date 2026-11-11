"""Unit tests for the pure detector: no database, just hand-made reading series.

Series are 5s readings with the simulator's noise; faults start at minute 30, so a full
baseline exists. Comments give the expected value of the last 30s at the judged moment.
"""

import pytest

from app.models import Metric, Severity
from app.services.detector import MIN_BASELINE_SAMPLES, check_threshold, evaluate, z_score
from tests.factories import ramp, series


def severities(readings: list[Metric]) -> dict[str, Severity]:
    return {finding.metric: finding.severity for finding in evaluate(readings)}


@pytest.mark.parametrize("seed", range(10))
def test_normal_noise_never_raises_a_finding(seed: int) -> None:
    readings = series(1, 60, seed=seed)

    # Judge the series at every minute of its second half, like the worker would.
    for end in range(len(readings) // 2, len(readings), 12):
        assert evaluate(readings[: end + 1]) == []


def test_overheat_is_caught_early_by_z_score_then_by_thresholds() -> None:
    heating = ramp("cpu_temp", per_minute=3, start_min=30)

    assert severities(series(1, 30.5, fault=heating)) == {}  # +1 C: within noise
    assert severities(series(1, 31.5, fault=heating)) == {"cpu_temp": Severity.INFO}  # +3.6 C
    assert severities(series(1, 39, fault=heating)) == {"cpu_temp": Severity.WARNING}  # 71 C
    assert severities(series(1, 43, fault=heating)) == {"cpu_temp": Severity.CRITICAL}  # 83 C


def test_memory_leak_is_flagged_before_any_fixed_limit() -> None:
    leak = ramp("memory_used_pct", per_minute=2.5, start_min=30)

    # ~54% and ~59%: far below the 85% limit, but unusual for this server (noise std 2%).
    assert severities(series(1, 34, fault=leak)) == {"memory_used_pct": Severity.INFO}
    assert severities(series(1, 36, fault=leak)) == {"memory_used_pct": Severity.WARNING}


def test_filling_disk_ends_critical() -> None:
    filling = ramp("disk_used_pct", per_minute=3, start_min=30)

    assert severities(series(1, 48, fault=filling)) == {"disk_used_pct": Severity.CRITICAL}  # 98%


def test_metrics_back_to_normal_give_no_findings() -> None:
    # Overheated from minute 15 to 25, then normal for 5 minutes. The baseline still holds
    # the hot readings, yet nothing is flagged: the z-score only looks upward.
    past_fault = ramp("cpu_temp", per_minute=3, start_min=15, end_min=25)

    assert severities(series(1, 30, fault=past_fault)) == {}


def test_short_history_uses_thresholds_only() -> None:
    # 2 minutes of data: too few readings for a baseline, so the network spike is not judged,
    # but the dangerous CPU temperature still is.
    spike = ramp("network_mbps", per_minute=2000, start_min=1.5)
    readings = series(1, 2, fault=spike, base={"cpu_temp": 85})

    assert len(readings) < MIN_BASELINE_SAMPLES
    assert severities(readings) == {"cpu_temp": Severity.CRITICAL}


def test_one_finding_per_metric_keeps_the_most_severe() -> None:
    # Far above normal (z-score says warning) and above 95% (threshold says critical).
    filling = ramp("disk_used_pct", per_minute=50, start_min=29)

    findings = evaluate(series(1, 30, fault=filling, base={"disk_used_pct": 80}))

    assert [(f.metric, f.severity) for f in findings] == [("disk_used_pct", Severity.CRITICAL)]


def test_z_score_uses_the_std_floor_for_flat_baselines() -> None:
    flat = [50.0] * MIN_BASELINE_SAMPLES

    assert z_score(51.0, flat, min_std=0.5) == 2.0  # std is 0: the 0.5 floor is used
    assert z_score(51.0, flat[:-1], min_std=0.5) is None  # one sample too few


@pytest.mark.parametrize(
    ("value", "expected"),
    [(69.9, None), (70, Severity.WARNING), (79.9, Severity.WARNING), (80, Severity.CRITICAL)],
)
def test_cpu_threshold_boundaries(value: float, expected: Severity | None) -> None:
    finding = check_threshold("cpu_temp", value)

    assert (finding.severity if finding else None) == expected


def test_metrics_without_thresholds_are_not_checked() -> None:
    assert check_threshold("power_w", 10_000) is None


def vps_series(minutes: float, cpu_usage_pct: float) -> list[Metric]:
    """Like a real VPS: no temperature or power sensor, CPU usage reported instead."""
    readings = series(1, minutes)
    for r in readings:
        r.cpu_temp = r.power_w = None
        r.cpu_usage_pct = cpu_usage_pct
    return readings


def test_metrics_a_server_does_not_report_are_skipped() -> None:
    assert evaluate(vps_series(60, cpu_usage_pct=20)) == []


def test_pinned_cpu_usage_is_critical_on_its_own() -> None:
    # Usage is judged by thresholds only (no z-score), so even a short history is enough.
    assert severities(vps_series(1, cpu_usage_pct=99)) == {"cpu_usage_pct": Severity.CRITICAL}
    assert severities(vps_series(1, cpu_usage_pct=92)) == {"cpu_usage_pct": Severity.WARNING}
    assert severities(vps_series(60, cpu_usage_pct=60)) == {}
