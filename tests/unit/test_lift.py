"""Tests for lift/elevator/arm physics calculations."""

import math

import pytest

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.lift import (
    GRAVITY,
    FRICTION_FACTOR,
    analyze_lift,
)
from robotics_design_advisor.mechanisms.models import LiftAnalysis


def _make_motor(ratio: float = 50.9, rpm: float = 117, torque: float = 64.5) -> MotorSpec:
    return MotorSpec(
        sku=f"5202-test-{ratio}",
        name=f"Test {ratio}:1",
        gear_ratio=ratio,
        free_speed_rpm=rpm,
        stall_torque_kg_cm=torque,
        stall_current_a=9.2,
        free_current_a=0.25,
        encoder_ppr=1425.1,
        shaft_type="6mm_D",
        weight_grams=470,
    )


SAMPLE_MOTORS = (
    _make_motor(19.2, 312, 24.3),
    _make_motor(50.9, 117, 64.5),
    _make_motor(71.2, 84, 90.2),
    _make_motor(188.0, 30, 238.1),
)


class TestAnalyzeLift:
    def test_elevator_returns_analysis(self):
        result = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=600.0,
            lift_type="elevator",
            motors=SAMPLE_MOTORS,
        )
        assert isinstance(result, LiftAnalysis)
        assert result.lift_type == "elevator"
        assert result.required_force_n > 0
        assert result.spool_diameter_mm > 0

    def test_elevator_force_includes_gravity_and_friction(self):
        result = analyze_lift(
            payload_mass_g=1000.0,
            max_height_mm=800.0,
            lift_type="elevator",
            stages=1,
            carriage_mass_g=200.0,
            motors=SAMPLE_MOTORS,
        )
        total_mass_kg = (1000.0 + 200.0) / 1000.0
        min_force = total_mass_kg * GRAVITY * FRICTION_FACTOR
        assert result.required_force_n >= min_force * 0.99

    def test_two_stage_doubles_force(self):
        result_1 = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=400.0,
            lift_type="elevator",
            stages=1,
            motors=SAMPLE_MOTORS,
        )
        result_2 = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=800.0,
            lift_type="elevator",
            stages=2,
            motors=SAMPLE_MOTORS,
        )
        # 2-stage needs more force due to stage multiplier
        assert result_2.required_force_n > result_1.required_force_n

    def test_four_bar_returns_analysis(self):
        result = analyze_lift(
            payload_mass_g=300.0,
            max_height_mm=500.0,
            lift_type="four_bar",
            motors=SAMPLE_MOTORS,
        )
        assert result.lift_type == "four_bar"
        assert result.required_torque_nmm > 0

    def test_arm_returns_analysis(self):
        result = analyze_lift(
            payload_mass_g=200.0,
            max_height_mm=400.0,
            lift_type="arm",
            motors=SAMPLE_MOTORS,
        )
        assert result.lift_type == "arm"

    def test_counterbalance_reduces_peak_force(self):
        result = analyze_lift(
            payload_mass_g=1000.0,
            max_height_mm=800.0,
            lift_type="elevator",
            motors=SAMPLE_MOTORS,
        )
        # Counterbalance should be positive (offsetting gravity)
        assert result.counterbalance_force_n > 0

    def test_time_to_height_positive(self):
        result = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=600.0,
            lift_type="elevator",
            motors=SAMPLE_MOTORS,
        )
        assert result.time_to_max_height_s > 0

    def test_zero_payload_raises(self):
        with pytest.raises(ValueError, match="payload_mass_g"):
            analyze_lift(
                payload_mass_g=0.0,
                max_height_mm=600.0,
                lift_type="elevator",
                motors=SAMPLE_MOTORS,
            )

    def test_zero_height_raises(self):
        with pytest.raises(ValueError, match="max_height_mm"):
            analyze_lift(
                payload_mass_g=500.0,
                max_height_mm=0.0,
                lift_type="elevator",
                motors=SAMPLE_MOTORS,
            )

    def test_invalid_lift_type_raises(self):
        with pytest.raises(ValueError, match="lift_type"):
            analyze_lift(
                payload_mass_g=500.0,
                max_height_mm=600.0,
                lift_type="teleporter",
                motors=SAMPLE_MOTORS,
            )
