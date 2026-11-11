from datetime import UTC, datetime

import pytest

from rackmind_agent import NetworkSample, build_reading, load_config, network_mbps

REQUIRED = {"RACKMIND_URL": "http://api/", "RACKMIND_KEY": "k", "RACKMIND_SERVER_ID": "21"}


def test_network_rate_is_bits_per_second_between_samples() -> None:
    before = NetworkSample(total_bytes=1_000_000, at=100.0)
    after = NetworkSample(total_bytes=13_500_000, at=105.0)  # 12.5 MB in 5s

    assert network_mbps(before, after) == pytest.approx(20.0)


def test_network_counter_reset_is_not_negative() -> None:
    before = NetworkSample(total_bytes=9_000_000, at=100.0)
    after = NetworkSample(total_bytes=1_000, at=105.0)  # interface restarted

    assert network_mbps(before, after) >= 0


def test_network_rate_without_elapsed_time_is_zero() -> None:
    sample = NetworkSample(total_bytes=5, at=100.0)

    assert network_mbps(sample, sample) == 0.0


def test_reading_matches_the_api_shape() -> None:
    now = datetime(2026, 11, 11, 10, 0, tzinfo=UTC)

    reading = build_reading(
        21,
        now,
        cpu_usage_pct=12.345,
        memory_used_pct=40.0,
        disk_used_pct=55.55,
        network_mbps=1.23456,
        cpu_temp=None,
    )

    assert reading == {
        "server_id": 21,
        "timestamp": "2026-11-11T10:00:00+00:00",
        "cpu_usage_pct": 12.3,
        "memory_used_pct": 40.0,
        "disk_used_pct": 55.5,
        "network_mbps": 1.235,
        "cpu_temp": None,  # no sensor: the API accepts a reading without it
    }


def test_config_defaults_and_trailing_slash() -> None:
    config = load_config(REQUIRED)

    assert config.url == "http://api"
    assert (config.server_id, config.interval_s, config.disk_path) == (21, 5.0, "/")


@pytest.mark.parametrize(
    "env",
    [
        {k: v for k, v in REQUIRED.items() if k != "RACKMIND_KEY"},
        {**REQUIRED, "RACKMIND_SERVER_ID": "web-01"},
    ],
)
def test_bad_config_exits_with_a_message(env: dict[str, str]) -> None:
    with pytest.raises(SystemExit):
        load_config(env)
