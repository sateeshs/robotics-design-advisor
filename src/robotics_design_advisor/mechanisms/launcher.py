"""Launcher ballistics — flywheel RPM, catapult springs, launch angles.

Pure functions, no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.models import LauncherAnalysis
from robotics_design_advisor.mechanisms.motor_selection import KG_CM_TO_NMM, select_motor

GRAVITY = 9.80665
FLYWHEEL_EFFICIENCY = 0.60   # energy transfer: wheel → projectile
CATAPULT_EFFICIENCY = 0.70   # spring → projectile
DEFAULT_FLYWHEEL_DIAMETER_MM = 100.0
CATAPULT_ARM_LENGTH_M = 0.25  # typical FTC catapult arm


def calc_launch_velocity(
    distance_m: float,
    height_m: float,
    angle_deg: float,
) -> float:
    """Calculate required launch velocity for a projectile.

    Uses the range equation for projectile motion:
    v = sqrt( (g * d^2) / (d * sin(2*theta) - 2*h * cos^2(theta)) )

    Parameters
    ----------
    distance_m : float
        Horizontal distance to target (must be > 0).
    height_m : float
        Target height relative to launch point.
    angle_deg : float
        Launch angle in degrees (0 < angle < 90).
    """
    if distance_m <= 0:
        raise ValueError(f"distance_m must be positive, got {distance_m}")

    theta = math.radians(angle_deg)
    sin2t = math.sin(2.0 * theta)
    cos2t = math.cos(theta) ** 2

    denominator = distance_m * sin2t - 2.0 * height_m * cos2t
    if denominator <= 0:
        # Target unreachable at this angle — use near-vertical estimate
        denominator = 0.01

    v_squared = (GRAVITY * distance_m**2) / denominator
    return math.sqrt(max(0.0, v_squared))


def calc_optimal_angle(distance_m: float, height_m: float) -> float:
    """Find the launch angle that minimizes required velocity.

    Sweeps from 20-70 degrees in 1-degree increments.

    Parameters
    ----------
    distance_m : float
        Horizontal distance to target (must be > 0).
    height_m : float
        Target height relative to launch point.
    """
    if distance_m <= 0:
        raise ValueError(f"distance_m must be positive, got {distance_m}")

    best_angle = 45.0
    best_velocity = float("inf")

    for angle_int in range(20, 71):
        angle = float(angle_int)
        try:
            v = calc_launch_velocity(distance_m, height_m, angle)
        except ValueError:
            continue
        if v < best_velocity:
            best_velocity = v
            best_angle = angle

    return best_angle


def analyze_launcher(
    target_distance_m: float,
    target_height_m: float,
    projectile_mass_g: float,
    projectile_diameter_mm: float,
    launcher_type: str,
    motors: Sequence[MotorSpec],
    flywheel_diameter_mm: float = DEFAULT_FLYWHEEL_DIAMETER_MM,
) -> LauncherAnalysis:
    """Full launcher analysis — velocity, angle, motor/spring sizing.

    Parameters
    ----------
    target_distance_m : float
        Horizontal distance to target (must be > 0).
    target_height_m : float
        Target height relative to launch point.
    projectile_mass_g : float
        Projectile mass in grams (must be > 0).
    projectile_diameter_mm : float
        Projectile diameter in mm (must be > 0).
    launcher_type : str
        "flywheel" or "catapult".
    motors : sequence of MotorSpec
        Available motors for flywheel drive.
    flywheel_diameter_mm : float
        Flywheel wheel diameter (default 100mm).
    """
    if target_distance_m <= 0:
        raise ValueError(f"target_distance_m must be positive, got {target_distance_m}")
    if projectile_mass_g <= 0:
        raise ValueError(f"projectile_mass_g must be positive, got {projectile_mass_g}")
    if projectile_diameter_mm <= 0:
        raise ValueError(f"projectile_diameter_mm must be positive, got {projectile_diameter_mm}")

    mass_kg = projectile_mass_g / 1000.0
    angle = calc_optimal_angle(target_distance_m, target_height_m)
    velocity = calc_launch_velocity(target_distance_m, target_height_m, angle)
    energy = 0.5 * mass_kg * velocity**2

    notes: list[str] = []

    if launcher_type == "catapult":
        return _analyze_catapult(velocity, angle, energy, notes)

    return _analyze_flywheel(
        velocity, angle, energy, flywheel_diameter_mm, motors, notes
    )


def _analyze_catapult(
    velocity: float,
    angle: float,
    energy: float,
    notes: list[str],
) -> LauncherAnalysis:
    """Build a catapult LauncherAnalysis from computed ballistics."""
    spring_energy = energy / CATAPULT_EFFICIENCY
    # Estimate spring force: F = 2 * E / arm_deflection
    spring_force = 2.0 * spring_energy / CATAPULT_ARM_LENGTH_M

    notes.append(f"Catapult arm length assumed: {CATAPULT_ARM_LENGTH_M * 1000:.0f}mm")
    notes.append("Use surgical tubing or constant-force spring for energy storage.")

    return LauncherAnalysis(
        launch_velocity_ms=round(velocity, 2),
        launch_angle_deg=round(angle, 1),
        flywheel_rpm=0.0,
        flywheel_diameter_mm=0.0,
        motor_recommendation="N/A — spring-powered",
        spin_up_time_s=0.0,
        energy_per_shot_j=round(energy, 4),
        fire_rate_hz=round(1.0 / 1.5, 2),  # ~1.5s reload cycle
        catapult_spring_force_n=round(spring_force, 1),
        notes=tuple(notes),
    )


def _analyze_flywheel(
    velocity: float,
    angle: float,
    energy: float,
    flywheel_diameter_mm: float,
    motors: Sequence[MotorSpec],
    notes: list[str],
) -> LauncherAnalysis:
    """Build a flywheel LauncherAnalysis from computed ballistics."""
    # Surface speed must equal launch velocity adjusted for efficiency
    required_surface_speed = velocity / FLYWHEEL_EFFICIENCY
    # v = pi * d * RPM / 60  =>  RPM = 60 * v / (pi * d)
    flywheel_circumference_m = math.pi * flywheel_diameter_mm / 1000.0
    flywheel_rpm = (60.0 * required_surface_speed) / flywheel_circumference_m

    # Flywheel moment of inertia (solid cylinder): I = 0.5 * m * r^2
    flywheel_mass_kg = 0.15  # ~150g for a typical compliant wheel
    flywheel_radius_m = flywheel_diameter_mm / 2000.0
    inertia = 0.5 * flywheel_mass_kg * flywheel_radius_m**2

    # Required torque for 1-second spin-up
    target_spinup_s = 1.0
    angular_accel = (flywheel_rpm * 2.0 * math.pi / 60.0) / target_spinup_s
    required_torque_nmm = inertia * angular_accel * 1000.0  # N-m → N-mm

    motor_match = select_motor(
        required_torque_nmm, flywheel_rpm, tuple(motors), duty="intermittent"
    )

    # Actual spin-up time with selected motor
    motor_torque_nm = motor_match.output_torque_nmm / 1000.0
    if motor_torque_nm > 0:
        actual_spinup = (inertia * flywheel_rpm * 2.0 * math.pi / 60.0) / motor_torque_nm
    else:
        actual_spinup = float("inf")

    fire_rate = 1.0 / max(0.1, actual_spinup + 0.3)  # spin-up + feed time

    notes.append(f"Flywheel surface speed: {required_surface_speed:.1f} m/s")
    notes.append(f"Efficiency factor: {FLYWHEEL_EFFICIENCY:.0%} — use compliant wheels")
    if flywheel_rpm > 6000:
        notes.append("WARNING: RPM exceeds typical motor range — increase flywheel diameter")

    return LauncherAnalysis(
        launch_velocity_ms=round(velocity, 2),
        launch_angle_deg=round(angle, 1),
        flywheel_rpm=round(flywheel_rpm, 0),
        flywheel_diameter_mm=flywheel_diameter_mm,
        motor_recommendation=motor_match.motor_name,
        spin_up_time_s=round(actual_spinup, 2),
        energy_per_shot_j=round(energy, 4),
        fire_rate_hz=round(fire_rate, 2),
        catapult_spring_force_n=0.0,
        notes=tuple(notes),
    )
