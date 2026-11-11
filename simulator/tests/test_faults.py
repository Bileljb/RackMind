import pytest

from rackmind_sim.faults import Fault, FaultKind, apply_faults, parse_fault
from rackmind_sim.readings import Reading, ServerInfo

SERVER = ServerInfo(id=1, hostname="r01-srv01", rack_name="R01")
OTHER_RACK_SERVER = ServerInfo(id=6, hostname="r02-srv01", rack_name="R02")
NORMAL = Reading(
    server_id=1,
    cpu_temp=45,
    power_w=300,
    cpu_usage_pct=20,
    disk_used_pct=50,
    memory_used_pct=40,
    network_mbps=200,
)


def test_parse_fault_reads_all_parts() -> None:
    assert parse_fault("overheat:R01:60:600") == Fault(FaultKind.OVERHEAT, "R01", 60, 600)


@pytest.mark.parametrize(
    "spec",
    ["overheat:R01:60", "explode:R01:60:600", "overheat:R01:soon:600", "overheat:R01:60:0"],
)
def test_parse_fault_rejects_bad_specs(spec: str) -> None:
    with pytest.raises(ValueError):
        parse_fault(spec)


def test_fault_only_active_inside_its_window() -> None:
    fault = Fault(FaultKind.DISK_FILL, "r01-srv01", start_s=60, duration_s=120)

    assert not fault.is_active(59)
    assert fault.is_active(60)
    assert fault.is_active(179)
    assert not fault.is_active(180)


def test_overheat_raises_temp_and_power_of_its_rack_only() -> None:
    faults = [Fault(FaultKind.OVERHEAT, "R01", start_s=0, duration_s=3600)]
    ten_minutes = 600

    hot = apply_faults(NORMAL, SERVER, faults, ten_minutes)
    untouched = apply_faults(NORMAL, OTHER_RACK_SERVER, faults, ten_minutes)

    assert hot.cpu_temp == pytest.approx(75)  # 45 + 3 C/min * 10 min
    assert hot.power_w > NORMAL.power_w
    assert hot.cpu_usage_pct > NORMAL.cpu_usage_pct  # throttling keeps the CPU busier
    assert untouched == NORMAL


def test_overheat_is_capped() -> None:
    faults = [Fault(FaultKind.OVERHEAT, "R01", start_s=0, duration_s=36000)]

    assert apply_faults(NORMAL, SERVER, faults, 5 * 3600).cpu_temp == pytest.approx(85)


def test_disk_fill_stops_at_100_pct() -> None:
    faults = [Fault(FaultKind.DISK_FILL, "r01-srv01", start_s=0, duration_s=3600)]

    assert apply_faults(NORMAL, SERVER, faults, 600).disk_used_pct == pytest.approx(80)
    assert apply_faults(NORMAL, SERVER, faults, 3000).disk_used_pct == 100


def test_memory_leak_grows_then_plateaus() -> None:
    faults = [Fault(FaultKind.MEMORY_LEAK, "r01-srv01", start_s=0, duration_s=36000)]

    assert apply_faults(NORMAL, SERVER, faults, 600).memory_used_pct == pytest.approx(65)
    assert apply_faults(NORMAL, SERVER, faults, 6000).memory_used_pct == 99.5


def test_readings_return_to_normal_after_fault_ends() -> None:
    faults = [Fault(FaultKind.MEMORY_LEAK, "r01-srv01", start_s=0, duration_s=60)]

    assert apply_faults(NORMAL, SERVER, faults, 61) == NORMAL


def test_cpu_spike_pins_cpu_usage_of_its_server_only() -> None:
    faults = [Fault(FaultKind.CPU_SPIKE, "r01-srv01", start_s=0, duration_s=60)]

    spiked = apply_faults(NORMAL, SERVER, faults, 1)

    assert spiked.cpu_usage_pct == 99
    assert spiked.cpu_temp > NORMAL.cpu_temp
    assert apply_faults(NORMAL, OTHER_RACK_SERVER, faults, 1) == NORMAL
