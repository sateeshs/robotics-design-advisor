"""Tests for launcher ballistics calculations."""

import math

import pytest

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.launcher import (
    GRAVITY,
    FLYWHEEL_EFFICIENCY,
    calc_launch_velocity,
    calc_optimal_angle,
    analyze_launcher,
)
from robotics_design_advisor.mechanisms.models import LauncherAnalysis


def _make_motor(ratio: float = 5.2, rpm: float = 1150, torque: float = 6.6) -> MotorSpec:
    return MotorSpec(
        sku=f"5202-test-{ratio}",
        name=f"Test {ratio}:1",
        gear_ratio=ratio,
        free_speed_rpm=rpm,
        stall_torque_kg_cm=torque,
        stall_current_a=9.2,
        free_current_a=0.25,
        encoder_ppr=145.1,
        shaft_type="6mm_D",
        weight_grams=310,
    )


SAMPLE_MOTORS = (_make_motor(3.7, 1620, 4.7), _make_motor(5.2, 1150, 6.6))


class TestCalcLaunchVelocity:
    def test_flat_launch(self):
        """Launching at 45deg to hit 3m distance, 0m height."""
        v = calc_launch_velocity(distance_m=3.0, height_m=0.0, angle_deg=45.0)
        # v = sqrt(g * d / sin(2*45)) = sqrt(9.81 * 3 / 1) ≈ 5.42
        expected = math.sqrt(GRAVITY * 3.0)
        assert abs(v - expected) < 0.1

    def test_elevated_target_needs_more_velocity(self):
        v_flat = calc_launch_velocity(3.0, 0.0, 45.0)
        v_high = calc_launch_velocity(3.0, 1.0, 45.0)
        assert v_high > v_flat

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="distance_m"):
            calc_launch_velocity(0.0, 0.0, 45.0)


class TestCalcOptimalAngle:
    def test_flat_target_near_45(self):
        """For a flat target, optimal angle is near 45 degrees."""
        angle = calc_optimal_angle(3.0, 0.0)
        assert 40.0 <= angle <= 50.0

    def test_elevated_target_higher_angle(self):
        """Elevated targets require a steeper trajectory to clear height."""
        angle_flat = calc_optimal_angle(3.0, 0.0)
        angle_high = calc_optimal_angle(3.0, 2.0)
        # Shooting at a target that is nearly as high as it is far
        # requires a steeper angle to minimize required velocity.
        assert angle_high >= angle_flat


class TestAnalyzeLauncher:
    def test_flywheel_returns_analysis(self):
        result = analyze_launcher(
            target_distance_m=3.0,
            target_height_m=1.0,
            projectile_mass_g=28.0,
            projectile_diameter_mm=38.0,
            launcher_type="flywheel",
            motors=SAMPLE_MOTORS,
        )
        assert isinstance(result, LauncherAnalysis)
        assert result.launch_velocity_ms > 0
        assert result.flywheel_rpm > 0
        assert result.flywheel_diameter_mm > 0

    def test_catapult_returns_spring_force(self):
        result = analyze_launcher(
            target_distance_m=2.0,
            target_height_m=0.5,
            projectile_mass_g=50.0,
            projectile_diameter_mm=60.0,
            launcher_type="catapult",
            motors=SAMPLE_MOTORS,
        )
        assert result.catapult_spring_force_n > 0
        assert result.flywheel_rpm == 0.0

    def test_energy_per_shot_positive(self):
        result = analyze_launcher(
            target_distance_m=3.0,
            target_height_m=0.0,
            projectile_mass_g=28.0,
            projectile_diameter_mm=38.0,
            launcher_type="flywheel",
            motors=SAMPLE_MOTORS,
        )
        # E = 0.5 * m * v^2
        expected_energy = 0.5 * 0.028 * result.launch_velocity_ms ** 2
        assert abs(result.energy_per_shot_j - expected_energy) < 0.01

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="target_distance_m"):
            analyze_launcher(
                target_distance_m=0.0,
                target_height_m=0.0,
                projectile_mass_g=28.0,
                projectile_diameter_mm=38.0,
                launcher_type="flywheel",
                motors=SAMPLE_MOTORS,
            )

    def test_negative_mass_raises(self):
        with pytest.raises(ValueError, match="projectile_mass_g"):
            analyze_launcher(
                target_distance_m=3.0,
                target_height_m=0.0,
                projectile_mass_g=-1.0,
                projectile_diameter_mm=38.0,
                launcher_type="flywheel",
                motors=SAMPLE_MOTORS,
            )
