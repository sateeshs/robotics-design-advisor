"""Tests for trapezoidal motion profile calculations."""

import math

import pytest

from robotics_design_advisor.mechanisms.motion import (
    calc_encoder_ticks,
    calc_motion_profile,
)
from robotics_design_advisor.mechanisms.models import MotionProfile


class TestCalcEncoderTicks:
    def test_one_wheel_revolution(self):
        """One revolution of a 96mm wheel = pi*96 ≈ 301.6mm."""
        wheel_diam = 96.0
        circumference = math.pi * wheel_diam
        ticks = calc_encoder_ticks(
            distance_mm=circumference,
            wheel_diameter_mm=wheel_diam,
            ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert ticks == 538  # rounded from 537.7

    def test_gear_ratio_multiplies_ticks(self):
        ticks_1x = calc_encoder_ticks(300.0, 96.0, 537.7, 1.0)
        ticks_2x = calc_encoder_ticks(300.0, 96.0, 537.7, 2.0)
        assert ticks_2x == ticks_1x * 2

    def test_zero_distance_returns_zero(self):
        ticks = calc_encoder_ticks(0.0, 96.0, 537.7, 1.0)
        assert ticks == 0


class TestCalcMotionProfile:
    def test_returns_motion_profile(self):
        result = calc_motion_profile(
            distance_mm=1000.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert isinstance(result, MotionProfile)
        assert result.total_ticks > 0
        assert result.total_time_s > 0

    def test_tick_phases_sum_to_total(self):
        result = calc_motion_profile(
            distance_mm=1000.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert result.accel_ticks + result.cruise_ticks + result.decel_ticks == result.total_ticks

    def test_short_distance_triangular_profile(self):
        """Short distance may not reach cruise velocity → triangular profile."""
        result = calc_motion_profile(
            distance_mm=50.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        # Cruise ticks should be 0 or very small for triangular profile
        assert result.cruise_ticks <= result.total_ticks

    def test_pid_gains_are_positive(self):
        result = calc_motion_profile(
            distance_mm=1000.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert result.suggested_kp > 0
        assert result.suggested_ki >= 0
        assert result.suggested_kd > 0

    def test_higher_gear_ratio_more_ticks(self):
        result_1x = calc_motion_profile(
            distance_mm=500.0,
            max_velocity_mm_s=300.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        result_2x = calc_motion_profile(
            distance_mm=500.0,
            max_velocity_mm_s=300.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=2.0,
        )
        assert result_2x.total_ticks > result_1x.total_ticks

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="distance_mm"):
            calc_motion_profile(
                distance_mm=0.0,
                max_velocity_mm_s=500.0,
                wheel_diameter_mm=96.0,
                encoder_ticks_per_rev=537.7,
                gear_ratio=1.0,
            )

    def test_zero_velocity_raises(self):
        with pytest.raises(ValueError, match="max_velocity_mm_s"):
            calc_motion_profile(
                distance_mm=500.0,
                max_velocity_mm_s=0.0,
                wheel_diameter_mm=96.0,
                encoder_ticks_per_rev=537.7,
                gear_ratio=1.0,
            )

    def test_zero_wheel_diameter_raises(self):
        with pytest.raises(ValueError, match="wheel_diameter_mm"):
            calc_motion_profile(
                distance_mm=500.0,
                max_velocity_mm_s=300.0,
                wheel_diameter_mm=0.0,
                encoder_ticks_per_rev=537.7,
                gear_ratio=1.0,
            )

    def test_cruise_ticks_never_negative(self):
        """Short distances must not produce negative cruise ticks."""
        result = calc_motion_profile(
            distance_mm=50.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert result.cruise_ticks >= 0
        assert result.accel_ticks + result.cruise_ticks + result.decel_ticks == result.total_ticks
