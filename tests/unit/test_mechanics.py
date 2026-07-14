"""Tests for mechanical engineering calculations."""

import pytest

from robotics_design_advisor.engineering.models import MotorSpec, DrivetrainAnalysis, ArmAnalysis, CenterOfGravity, GearRatioResult
from robotics_design_advisor.engineering.mechanics import (
    calc_arm_torque,
    calc_center_of_gravity,
    calc_drivetrain_speed,
    calc_elevator_force,
    calc_gear_ratio_for_speed,
)


@pytest.fixture
def motor_1_to_1() -> MotorSpec:
    """High-speed 1:1 motor (6000 RPM, low torque)."""
    return MotorSpec(
        sku="5202-0002-0001",
        name="1:1 Ratio",
        gear_ratio=1.0,
        free_speed_rpm=6000.0,
        stall_torque_kg_cm=0.17,
        stall_current_a=9.2,
        free_current_a=0.25,
        encoder_ppr=28.0,
        shaft_type="6mm D-shaft",
        weight_grams=91.0,
        voltage_nominal=12.0,
    )


@pytest.fixture
def motor_19_2() -> MotorSpec:
    """Mid-range 19.2:1 motor (312 RPM, moderate torque)."""
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
        voltage_nominal=12.0,
    )


@pytest.fixture
def motor_50_9() -> MotorSpec:
    """High-torque 50.9:1 motor (117 RPM)."""
    return MotorSpec(
        sku="5202-0002-0051",
        name="50.9:1 Ratio",
        gear_ratio=50.9,
        free_speed_rpm=117.0,
        stall_torque_kg_cm=8.45,
        stall_current_a=9.2,
        free_current_a=0.25,
        encoder_ppr=1425.1,
        shaft_type="6mm D-shaft",
        weight_grams=128.0,
        voltage_nominal=12.0,
    )


# ---------------------------------------------------------------------------
# Drivetrain
# ---------------------------------------------------------------------------

class TestCalcDrivetrainSpeed:
    def test_returns_drivetrain_analysis(self, motor_19_2: MotorSpec) -> None:
        result = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0)
        assert isinstance(result, DrivetrainAnalysis)

    def test_free_speed_calculation(self, motor_19_2: MotorSpec) -> None:
        # 312 RPM, 96mm wheel, direct drive
        # circumference = pi * 0.096 = 0.30159 m
        # speed = 312 * 0.30159 / 60 = 1.568 m/s
        result = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0)
        assert abs(result.free_speed_m_s - 1.568) < 0.01

    def test_loaded_speed_is_80_pct_of_free(self, motor_19_2: MotorSpec) -> None:
        result = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0)
        expected_loaded = result.free_speed_m_s * 0.80
        assert abs(result.loaded_speed_m_s - expected_loaded) < 0.001

    def test_external_ratio_reduces_speed(self, motor_19_2: MotorSpec) -> None:
        direct = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0, external_ratio=1.0)
        geared = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0, external_ratio=2.0)
        assert geared.free_speed_m_s < direct.free_speed_m_s
        assert abs(geared.free_speed_m_s - direct.free_speed_m_s / 2.0) < 0.01

    def test_motor_count_affects_current(self, motor_19_2: MotorSpec) -> None:
        two = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0, motor_count=2)
        four = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0, motor_count=4)
        assert four.total_stall_current_a == pytest.approx(two.total_stall_current_a * 2, rel=0.01)
        assert four.total_motor_weight_grams == two.total_motor_weight_grams * 2

    def test_warns_when_too_fast(self, motor_1_to_1: MotorSpec) -> None:
        # 6000 RPM on 96mm wheel = very fast
        result = calc_drivetrain_speed(motor_1_to_1, wheel_diameter_mm=96.0)
        assert result.free_speed_m_s > 2.5
        assert any("very fast" in w for w in result.warnings)
        assert not result.recommended

    def test_warns_when_too_slow(self, motor_50_9: MotorSpec) -> None:
        # 117 RPM on small wheel with extra reduction
        result = calc_drivetrain_speed(motor_50_9, wheel_diameter_mm=50.0, external_ratio=3.0)
        assert result.free_speed_m_s < 0.5
        assert any("slow" in w for w in result.warnings)

    def test_recommended_speed_range(self, motor_19_2: MotorSpec) -> None:
        result = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0)
        # 1.568 m/s is in recommended range 0.8-2.2
        assert result.recommended

    def test_notes_include_gear_ratio(self, motor_19_2: MotorSpec) -> None:
        result = calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0, external_ratio=2.0)
        assert any("gear ratio" in n.lower() for n in result.notes)


# ---------------------------------------------------------------------------
# Gear ratio solver
# ---------------------------------------------------------------------------

class TestCalcGearRatioForSpeed:
    def test_returns_gear_ratio_result(self, motor_19_2: MotorSpec) -> None:
        result = calc_gear_ratio_for_speed(motor_19_2, wheel_diameter_mm=96.0, target_speed_m_s=1.5)
        assert isinstance(result, GearRatioResult)

    def test_achieves_target_speed(self, motor_19_2: MotorSpec) -> None:
        result = calc_gear_ratio_for_speed(motor_19_2, wheel_diameter_mm=96.0, target_speed_m_s=1.0)
        assert abs(result.actual_speed_m_s - 1.0) < 0.1

    def test_external_ratio_at_least_one(self, motor_19_2: MotorSpec) -> None:
        # Very high target speed should clamp ratio to 1.0
        result = calc_gear_ratio_for_speed(motor_19_2, wheel_diameter_mm=96.0, target_speed_m_s=100.0)
        assert result.external_ratio >= 1.0

    def test_zero_target_speed_returns_ratio_one(self, motor_19_2: MotorSpec) -> None:
        result = calc_gear_ratio_for_speed(motor_19_2, wheel_diameter_mm=96.0, target_speed_m_s=0.0)
        assert result.external_ratio == 1.0

    def test_total_ratio_is_product(self, motor_19_2: MotorSpec) -> None:
        result = calc_gear_ratio_for_speed(motor_19_2, wheel_diameter_mm=96.0, target_speed_m_s=1.0)
        expected = motor_19_2.gear_ratio * result.external_ratio
        assert abs(result.total_ratio - expected) < 0.1

    def test_current_estimate_reasonable(self, motor_19_2: MotorSpec) -> None:
        result = calc_gear_ratio_for_speed(motor_19_2, wheel_diameter_mm=96.0, target_speed_m_s=1.0)
        assert result.current_at_speed_a > motor_19_2.free_current_a
        assert result.current_at_speed_a < motor_19_2.stall_current_a


# ---------------------------------------------------------------------------
# Arm torque
# ---------------------------------------------------------------------------

class TestCalcArmTorque:
    def test_returns_arm_analysis(self, motor_50_9: MotorSpec) -> None:
        result = calc_arm_torque(motor_50_9, arm_length_mm=300.0, load_kg=0.5)
        assert isinstance(result, ArmAnalysis)

    def test_required_torque_at_horizontal(self, motor_50_9: MotorSpec) -> None:
        # 0.5 kg at 300mm (30 cm) = 15 kg·cm
        result = calc_arm_torque(motor_50_9, arm_length_mm=300.0, load_kg=0.5)
        assert result.required_torque_kg_cm == pytest.approx(15.0, rel=0.01)

    def test_usable_torque_is_50pct_stall(self, motor_50_9: MotorSpec) -> None:
        result = calc_arm_torque(motor_50_9, arm_length_mm=300.0, load_kg=0.5, external_ratio=2.0)
        expected = motor_50_9.stall_torque_kg_cm * 2.0 * 0.50
        assert result.available_torque_kg_cm == pytest.approx(expected, rel=0.01)

    def test_can_hold_light_load(self, motor_50_9: MotorSpec) -> None:
        # 8.45 kg·cm × 0.5 = 4.225 usable, 0.1 kg at 100mm = 1 kg·cm needed
        result = calc_arm_torque(motor_50_9, arm_length_mm=100.0, load_kg=0.1)
        assert result.can_hold

    def test_cannot_hold_excessive_load(self, motor_19_2: MotorSpec) -> None:
        # 3.2 kg·cm × 0.5 = 1.6 usable, 2 kg at 500mm = 100 kg·cm needed
        result = calc_arm_torque(motor_19_2, arm_length_mm=500.0, load_kg=2.0)
        assert not result.can_hold

    def test_warns_low_margin(self, motor_50_9: MotorSpec) -> None:
        # Arrange a load that barely fits
        # Usable = 8.45 * 0.5 = 4.225 kg·cm
        # 0.4 kg at 100mm (10cm) = 4.0 kg·cm → margin ~5.6%
        result = calc_arm_torque(motor_50_9, arm_length_mm=100.0, load_kg=0.4)
        assert result.torque_margin_pct < 20
        assert any("margin" in w.lower() for w in result.warnings)

    def test_external_ratio_multiplies_torque(self, motor_19_2: MotorSpec) -> None:
        r1 = calc_arm_torque(motor_19_2, arm_length_mm=200.0, load_kg=0.3, external_ratio=1.0)
        r5 = calc_arm_torque(motor_19_2, arm_length_mm=200.0, load_kg=0.3, external_ratio=5.0)
        assert r5.available_torque_kg_cm > r1.available_torque_kg_cm

    def test_warns_heavy_load_low_ratio(self, motor_50_9: MotorSpec) -> None:
        result = calc_arm_torque(motor_50_9, arm_length_mm=50.0, load_kg=1.5, external_ratio=1.0)
        assert any("higher gear ratio" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Elevator
# ---------------------------------------------------------------------------

class TestCalcElevatorForce:
    def test_returns_arm_analysis(self, motor_50_9: MotorSpec) -> None:
        result = calc_elevator_force(motor_50_9, spool_diameter_mm=30.0, load_kg=0.5)
        assert isinstance(result, ArmAnalysis)

    def test_required_torque_is_load_times_radius(self, motor_50_9: MotorSpec) -> None:
        # 30mm diameter → 15mm radius → 1.5 cm
        # 0.5 kg × 1.5 cm = 0.75 kg·cm
        result = calc_elevator_force(motor_50_9, spool_diameter_mm=30.0, load_kg=0.5)
        assert result.required_torque_kg_cm == pytest.approx(0.75, rel=0.01)

    def test_can_lift_light_load(self, motor_50_9: MotorSpec) -> None:
        result = calc_elevator_force(motor_50_9, spool_diameter_mm=30.0, load_kg=0.5)
        assert result.can_hold

    def test_cannot_lift_very_heavy_load(self, motor_19_2: MotorSpec) -> None:
        # Large spool, heavy load, no external ratio
        result = calc_elevator_force(motor_19_2, spool_diameter_mm=100.0, load_kg=5.0)
        # Required = 5 × 5cm = 25 kg·cm, available = 3.2 × 0.5 = 1.6
        assert not result.can_hold

    def test_external_ratio_helps(self, motor_19_2: MotorSpec) -> None:
        r1 = calc_elevator_force(motor_19_2, spool_diameter_mm=30.0, load_kg=1.0, external_ratio=1.0)
        r5 = calc_elevator_force(motor_19_2, spool_diameter_mm=30.0, load_kg=1.0, external_ratio=5.0)
        assert r5.torque_margin_pct > r1.torque_margin_pct


# ---------------------------------------------------------------------------
# Center of gravity
# ---------------------------------------------------------------------------

class TestCalcCenterOfGravity:
    def test_empty_components(self) -> None:
        result = calc_center_of_gravity([])
        assert isinstance(result, CenterOfGravity)
        assert result.total_mass_grams == 0

    def test_single_component(self) -> None:
        result = calc_center_of_gravity([(100.0, 50.0, 200.0, 500.0)])
        assert result.x_mm == pytest.approx(100.0, rel=0.01)
        assert result.y_mm == pytest.approx(50.0, rel=0.01)
        assert result.z_mm == pytest.approx(200.0, rel=0.01)
        assert result.total_mass_grams == pytest.approx(500.0, rel=0.01)

    def test_two_equal_masses_at_center(self) -> None:
        components = [
            (100.0, 50.0, 100.0, 500.0),
            (300.0, 50.0, 300.0, 500.0),
        ]
        result = calc_center_of_gravity(components)
        assert result.x_mm == pytest.approx(200.0, rel=0.01)
        assert result.z_mm == pytest.approx(200.0, rel=0.01)
        assert result.total_mass_grams == pytest.approx(1000.0, rel=0.01)

    def test_weighted_average(self) -> None:
        # Heavy mass at origin, light mass far away → CG near origin
        components = [
            (0.0, 0.0, 0.0, 900.0),
            (457.0, 0.0, 457.0, 100.0),
        ]
        result = calc_center_of_gravity(components)
        assert result.x_mm < 457.0 / 2  # closer to heavy mass
        assert result.x_mm == pytest.approx(45.7, rel=0.01)

    def test_within_footprint(self) -> None:
        components = [(228.5, 50.0, 228.5, 1000.0)]
        result = calc_center_of_gravity(components, footprint_mm=(457.0, 457.0))
        assert result.within_footprint

    def test_outside_footprint(self) -> None:
        components = [(500.0, 50.0, 500.0, 1000.0)]
        result = calc_center_of_gravity(components, footprint_mm=(457.0, 457.0))
        assert not result.within_footprint

    def test_offset_from_center(self) -> None:
        # Component exactly at center of footprint → offset 0
        components = [(228.5, 50.0, 228.5, 1000.0)]
        result = calc_center_of_gravity(components, footprint_mm=(457.0, 457.0))
        assert result.offset_from_center_mm == pytest.approx(0.0, abs=0.5)

    def test_zero_mass_returns_zero(self) -> None:
        components = [(100.0, 50.0, 100.0, 0.0)]
        result = calc_center_of_gravity(components)
        assert result.total_mass_grams == 0
        assert result.x_mm == 0
        assert result.y_mm == 0
        assert result.z_mm == 0
        assert result.within_footprint


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_drivetrain_zero_wheel_raises(self, motor_19_2: MotorSpec) -> None:
        with pytest.raises(ValueError, match="wheel_diameter_mm"):
            calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=0.0)

    def test_drivetrain_zero_ratio_raises(self, motor_19_2: MotorSpec) -> None:
        with pytest.raises(ValueError, match="external_ratio"):
            calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0, external_ratio=0.0)

    def test_drivetrain_zero_motors_raises(self, motor_19_2: MotorSpec) -> None:
        with pytest.raises(ValueError, match="motor_count"):
            calc_drivetrain_speed(motor_19_2, wheel_diameter_mm=96.0, motor_count=0)

    def test_arm_zero_length_raises(self, motor_50_9: MotorSpec) -> None:
        with pytest.raises(ValueError, match="arm_length_mm"):
            calc_arm_torque(motor_50_9, arm_length_mm=0.0, load_kg=0.5)

    def test_arm_negative_load_raises(self, motor_50_9: MotorSpec) -> None:
        with pytest.raises(ValueError, match="load_kg"):
            calc_arm_torque(motor_50_9, arm_length_mm=100.0, load_kg=-1.0)

    def test_elevator_zero_spool_raises(self, motor_50_9: MotorSpec) -> None:
        with pytest.raises(ValueError, match="spool_diameter_mm"):
            calc_elevator_force(motor_50_9, spool_diameter_mm=0.0, load_kg=0.5)

    def test_gear_ratio_zero_wheel_raises(self, motor_19_2: MotorSpec) -> None:
        with pytest.raises(ValueError, match="wheel_diameter_mm"):
            calc_gear_ratio_for_speed(motor_19_2, wheel_diameter_mm=0.0, target_speed_m_s=1.0)
