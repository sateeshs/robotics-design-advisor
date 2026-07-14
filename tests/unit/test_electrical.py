"""Tests for electrical engineering calculations."""

import pytest

from robotics_design_advisor.engineering.electrical import (
    allocate_ports,
    analyze_power_budget,
    check_wire_gauge,
    find_motor_by_ratio,
    find_motor_by_sku,
    load_hub_spec,
    load_motor_specs,
)
from robotics_design_advisor.engineering.models import (
    HubSpec,
    MotorSpec,
    PortAllocation,
    PowerBudget,
    WireGaugeResult,
)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

class TestLoadMotorSpecs:
    def test_loads_gobilda_yellow_jacket(self) -> None:
        motors = load_motor_specs()
        assert len(motors) > 0
        assert all(isinstance(m, MotorSpec) for m in motors)

    def test_all_have_required_fields(self) -> None:
        motors = load_motor_specs()
        for m in motors:
            assert m.sku
            assert m.name
            assert m.gear_ratio > 0
            assert m.free_speed_rpm > 0
            assert m.stall_torque_kg_cm > 0
            assert m.weight_grams > 0

    def test_ratios_are_sorted_ascending(self) -> None:
        motors = load_motor_specs()
        ratios = [m.gear_ratio for m in motors]
        assert ratios == sorted(ratios)

    def test_higher_ratio_means_lower_speed(self) -> None:
        motors = load_motor_specs()
        for i in range(len(motors) - 1):
            if motors[i].gear_ratio < motors[i + 1].gear_ratio:
                assert motors[i].free_speed_rpm >= motors[i + 1].free_speed_rpm


class TestLoadHubSpec:
    def test_loads_control_hub(self) -> None:
        hub = load_hub_spec("hub_data/rev_control_hub.json")
        assert isinstance(hub, HubSpec)
        assert hub.name == "REV Control Hub"

    def test_loads_expansion_hub(self) -> None:
        hub = load_hub_spec("hub_data/rev_expansion_hub.json")
        assert isinstance(hub, HubSpec)
        assert hub.name == "REV Expansion Hub"

    def test_control_hub_has_imu(self) -> None:
        hub = load_hub_spec("hub_data/rev_control_hub.json")
        assert hub.has_imu

    def test_expansion_hub_no_imu(self) -> None:
        hub = load_hub_spec("hub_data/rev_expansion_hub.json")
        assert not hub.has_imu

    def test_hub_port_counts(self) -> None:
        hub = load_hub_spec("hub_data/rev_control_hub.json")
        assert hub.motor_ports == 4
        assert hub.servo_ports == 6
        assert hub.encoder_ports == 4
        assert hub.i2c_buses == 4


# ---------------------------------------------------------------------------
# Motor finders
# ---------------------------------------------------------------------------

class TestFindMotorBySku:
    def test_finds_existing_sku(self) -> None:
        motors = load_motor_specs()
        found = find_motor_by_sku(motors, motors[0].sku)
        assert found is not None
        assert found.sku == motors[0].sku

    def test_returns_none_for_missing_sku(self) -> None:
        motors = load_motor_specs()
        assert find_motor_by_sku(motors, "NONEXISTENT-999") is None


class TestFindMotorByRatio:
    def test_finds_closest_ratio(self) -> None:
        motors = load_motor_specs()
        found = find_motor_by_ratio(motors, 19.0)
        assert found is not None
        assert abs(found.gear_ratio - 19.2) < 1.0

    def test_returns_none_when_no_match(self) -> None:
        motors = load_motor_specs()
        # Tolerance 0.5, ask for ratio 999
        assert find_motor_by_ratio(motors, 999.0, tolerance=0.5) is None


# ---------------------------------------------------------------------------
# Power budget
# ---------------------------------------------------------------------------

@pytest.fixture
def drive_motor() -> MotorSpec:
    return MotorSpec(
        sku="5202-0002-0019",
        name="19.2:1 Ratio",
        gear_ratio=19.2,
        free_speed_rpm=312.0,
        stall_torque_kg_cm=3.2,
        stall_current_a=9.2,
        free_current_a=0.25,
        encoder_ppr=537.7,
        shaft_type="6mm D-shaft",
        weight_grams=116.0,
    )


class TestAnalyzePowerBudget:
    def test_returns_power_budget(self, drive_motor: MotorSpec) -> None:
        result = analyze_power_budget([(drive_motor, 4)])
        assert isinstance(result, PowerBudget)

    def test_total_motors_count(self, drive_motor: MotorSpec) -> None:
        result = analyze_power_budget([(drive_motor, 4)])
        assert result.total_motors == 4

    def test_stall_current_sums(self, drive_motor: MotorSpec) -> None:
        result = analyze_power_budget([(drive_motor, 4)])
        assert result.total_stall_current_a == pytest.approx(9.2 * 4, rel=0.01)

    def test_free_current_sums(self, drive_motor: MotorSpec) -> None:
        result = analyze_power_budget([(drive_motor, 4)])
        assert result.total_free_current_a == pytest.approx(0.25 * 4, rel=0.01)

    def test_typical_between_free_and_stall(self, drive_motor: MotorSpec) -> None:
        result = analyze_power_budget([(drive_motor, 4)])
        assert result.typical_current_a > result.total_free_current_a
        assert result.typical_current_a < result.total_stall_current_a

    def test_four_motors_within_budget(self, drive_motor: MotorSpec) -> None:
        result = analyze_power_budget([(drive_motor, 4)])
        assert result.within_budget

    def test_nine_motors_exceeds_ftc_limit(self, drive_motor: MotorSpec) -> None:
        result = analyze_power_budget([(drive_motor, 9)])
        assert not result.within_budget
        assert any("8 DC motors" in w for w in result.warnings)

    def test_hub_count_for_many_motors(self, drive_motor: MotorSpec) -> None:
        # 8 motors → need 2 hubs (4 ports each)
        result = analyze_power_budget([(drive_motor, 8)])
        assert result.hub_count_needed == 2

    def test_hub_override(self, drive_motor: MotorSpec) -> None:
        hub = load_hub_spec("hub_data/rev_control_hub.json")
        result = analyze_power_budget([(drive_motor, 4)], hub=hub)
        assert result.fuse_limit_a == hub.motor_current_max_a


# ---------------------------------------------------------------------------
# Port allocation
# ---------------------------------------------------------------------------

class TestAllocatePorts:
    def test_returns_port_allocation(self) -> None:
        result = allocate_ports(
            motors=[("fl", "front_left"), ("fr", "front_right")],
        )
        assert isinstance(result, PortAllocation)

    def test_assigns_motors_to_ports(self) -> None:
        result = allocate_ports(
            motors=[("fl", "front_left"), ("fr", "front_right"),
                    ("bl", "back_left"), ("br", "back_right")],
        )
        assert len(result.assignments) == 4
        ports_used = [a[1] for a in result.assignments]
        assert "motor_0" in ports_used
        assert "motor_3" in ports_used

    def test_assigns_servos(self) -> None:
        result = allocate_ports(
            motors=[],
            servos=[("claw", "claw_open_close"), ("arm", "arm_rotate")],
        )
        servo_assignments = [a for a in result.assignments if "servo" in a[1]]
        assert len(servo_assignments) == 2

    def test_assigns_sensors(self) -> None:
        result = allocate_ports(
            motors=[],
            sensors=[("color", "detect_game_piece", "i2c"),
                     ("limit", "arm_stop", "digital")],
        )
        assert len(result.assignments) == 2
        types = [a[1] for a in result.assignments]
        assert any("i2c" in t for t in types)
        assert any("digital" in t for t in types)

    def test_overflow_warns(self) -> None:
        motors = [(f"motor_{i}", f"purpose_{i}") for i in range(10)]
        result = allocate_ports(motors=motors)
        assert any("hubs" in w.lower() for w in result.warnings)

    def test_hub_count_increments(self) -> None:
        # 5 motors → need 2 hubs
        motors = [(f"m{i}", f"p{i}") for i in range(5)]
        result = allocate_ports(motors=motors)
        assert result.hub_count == 2


# ---------------------------------------------------------------------------
# Wire gauge
# ---------------------------------------------------------------------------

class TestCheckWireGauge:
    def test_returns_wire_gauge_result(self) -> None:
        result = check_wire_gauge(current_a=5.0, length_mm=500.0)
        assert isinstance(result, WireGaugeResult)

    def test_short_wire_adequate(self) -> None:
        result = check_wire_gauge(current_a=5.0, length_mm=200.0, awg=16)
        assert result.adequate

    def test_long_wire_high_current_inadequate(self) -> None:
        result = check_wire_gauge(current_a=10.0, length_mm=3000.0, awg=22)
        assert not result.adequate
        assert result.recommendation  # non-empty string

    def test_voltage_drop_increases_with_length(self) -> None:
        short = check_wire_gauge(current_a=5.0, length_mm=200.0, awg=16)
        long_wire = check_wire_gauge(current_a=5.0, length_mm=2000.0, awg=16)
        assert long_wire.voltage_drop_v > short.voltage_drop_v

    def test_thicker_wire_lower_drop(self) -> None:
        thin = check_wire_gauge(current_a=5.0, length_mm=1000.0, awg=22)
        thick = check_wire_gauge(current_a=5.0, length_mm=1000.0, awg=12)
        assert thick.voltage_drop_v < thin.voltage_drop_v

    def test_drop_percentage_calculation(self) -> None:
        from robotics_design_advisor.engineering.electrical import AWG_RESISTANCE_OHM_PER_M
        result = check_wire_gauge(current_a=5.0, length_mm=1000.0, awg=16, voltage=12.0)
        expected_drop = 2 * 5.0 * AWG_RESISTANCE_OHM_PER_M[16] * 1.0
        expected_pct = (expected_drop / 12.0) * 100.0
        assert result.drop_pct == pytest.approx(expected_pct, rel=0.01)

    def test_unsupported_awg_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported AWG"):
            check_wire_gauge(current_a=5.0, length_mm=500.0, awg=10)

    def test_sensor_port_overflow_goes_to_unassigned(self) -> None:
        # 5 i2c sensors when hub only has 4 buses
        sensors = [(f"s{i}", f"sensor_{i}", "i2c") for i in range(5)]
        result = allocate_ports(motors=[], sensors=sensors)
        assert len(result.unassigned_devices) == 1
