"""Tests for grabber/intake physics calculations."""

import math

import pytest

from robotics_design_advisor.mechanisms.grabber import (
    GRAVITY_M_S2,
    SAFETY_FACTOR,
    analyze_grabber,
    recommend_grip_type,
)
from robotics_design_advisor.mechanisms.models import GrabberAnalysis


class TestAnalyzeGrabber:
    def test_claw_grip_force(self):
        """Grip force = (weight_N * safety_factor) / friction_coefficient."""
        result = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
        )
        assert isinstance(result, GrabberAnalysis)
        weight_n = 0.1 * GRAVITY_M_S2  # 100g in N
        expected_grip = weight_n * SAFETY_FACTOR / 0.5  # default friction
        assert abs(result.required_grip_force_n - expected_grip) < 0.01

    def test_servo_torque_equals_force_times_lever(self):
        result = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
        )
        expected_torque = result.required_grip_force_n * 80.0
        assert abs(result.required_torque_nmm - expected_torque) < 0.01

    def test_jaw_opening_is_largest_dimension_plus_margin(self):
        result = analyze_grabber(
            piece_weight_g=50.0,
            piece_dimensions_mm=(38.0, 50.0, 25.0),
            grip_type="claw",
            jaw_length_mm=60.0,
        )
        # Jaw opening should accommodate largest dimension + 10mm margin
        assert result.jaw_opening_mm >= 50.0

    def test_roller_intake_uses_rubber_friction(self):
        result = analyze_grabber(
            piece_weight_g=28.0,
            piece_dimensions_mm=(38.0, 38.0, 38.0),
            grip_type="roller_intake",
            jaw_length_mm=60.0,
        )
        assert result.grip_type == "roller_intake"
        assert result.required_grip_force_n > 0

    def test_passive_funnel_zero_torque(self):
        result = analyze_grabber(
            piece_weight_g=28.0,
            piece_dimensions_mm=(38.0, 38.0, 38.0),
            grip_type="passive_funnel",
            jaw_length_mm=60.0,
        )
        assert result.required_torque_nmm == 0.0
        assert result.hold_current_ma == 0.0

    def test_custom_friction_coefficient(self):
        result_low = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
            friction_coefficient=0.3,
        )
        result_high = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
            friction_coefficient=0.8,
        )
        # Lower friction needs more grip force
        assert result_low.required_grip_force_n > result_high.required_grip_force_n

    def test_zero_weight_raises(self):
        with pytest.raises(ValueError, match="piece_weight_g"):
            analyze_grabber(
                piece_weight_g=0.0,
                piece_dimensions_mm=(50.0, 50.0, 50.0),
                grip_type="claw",
                jaw_length_mm=80.0,
            )

    def test_negative_jaw_length_raises(self):
        with pytest.raises(ValueError, match="jaw_length_mm"):
            analyze_grabber(
                piece_weight_g=50.0,
                piece_dimensions_mm=(50.0, 50.0, 50.0),
                grip_type="claw",
                jaw_length_mm=-10.0,
            )


class TestRecommendGripType:
    def test_cube_recommends_claw(self):
        assert recommend_grip_type("cube") == "claw"

    def test_sphere_recommends_roller(self):
        assert recommend_grip_type("sphere") == "roller_intake"

    def test_ring_recommends_hook(self):
        assert recommend_grip_type("ring") == "claw"

    def test_unknown_defaults_to_claw(self):
        assert recommend_grip_type("alien_artifact") == "claw"
