"""Motion profiles — encoder ticks, trapezoidal velocity, PID starting points.

Pure functions, no I/O.
"""

from __future__ import annotations

import math

from .models import MotionProfile

DEFAULT_ACCELERATION_MM_S2 = 1000.0  # reasonable default for FTC drivetrains


def calc_encoder_ticks(
    distance_mm: float,
    wheel_diameter_mm: float,
    ticks_per_rev: float,
    gear_ratio: float,
) -> int:
    """Convert a linear distance to encoder ticks.

    ticks = (distance / wheel_circumference) * ticks_per_rev * gear_ratio
    """
    if distance_mm == 0:
        return 0
    circumference = math.pi * wheel_diameter_mm
    revolutions = distance_mm / circumference
    return round(revolutions * ticks_per_rev * gear_ratio)


def calc_motion_profile(
    distance_mm: float,
    max_velocity_mm_s: float,
    wheel_diameter_mm: float,
    encoder_ticks_per_rev: float,
    gear_ratio: float,
    acceleration_mm_s2: float = DEFAULT_ACCELERATION_MM_S2,
) -> MotionProfile:
    """Calculate a trapezoidal motion profile with encoder tick breakdowns.

    Parameters
    ----------
    distance_mm : float
        Target travel distance (must be > 0).
    max_velocity_mm_s : float
        Maximum cruise velocity (must be > 0).
    wheel_diameter_mm : float
        Drive wheel outer diameter (must be > 0).
    encoder_ticks_per_rev : float
        Encoder resolution (ticks per motor shaft revolution).
    gear_ratio : float
        External gear ratio (motor-to-wheel).
    acceleration_mm_s2 : float
        Acceleration rate (default 1000 mm/s^2).
    """
    if distance_mm <= 0:
        raise ValueError(f"distance_mm must be positive, got {distance_mm}")
    if max_velocity_mm_s <= 0:
        raise ValueError(f"max_velocity_mm_s must be positive, got {max_velocity_mm_s}")
    if wheel_diameter_mm <= 0:
        raise ValueError(f"wheel_diameter_mm must be positive, got {wheel_diameter_mm}")
    if acceleration_mm_s2 <= 0:
        raise ValueError(f"acceleration_mm_s2 must be positive, got {acceleration_mm_s2}")

    # Time and distance to accelerate to max velocity
    accel_time = max_velocity_mm_s / acceleration_mm_s2
    accel_distance = 0.5 * acceleration_mm_s2 * accel_time**2

    # Deceleration mirrors acceleration
    decel_time = accel_time
    decel_distance = accel_distance

    # Check if we can reach cruise velocity (triangular vs trapezoidal)
    if accel_distance + decel_distance >= distance_mm:
        # Triangular profile — never reaches full cruise speed
        # d = 2 * (0.5 * a * t^2)  =>  t = sqrt(d / a)
        half_time = math.sqrt(distance_mm / acceleration_mm_s2)
        accel_time = half_time
        decel_time = half_time
        accel_distance = distance_mm / 2.0
        decel_distance = distance_mm / 2.0
        cruise_distance = 0.0
        cruise_time = 0.0
        actual_max_v = acceleration_mm_s2 * half_time
    else:
        cruise_distance = distance_mm - accel_distance - decel_distance
        cruise_time = cruise_distance / max_velocity_mm_s
        actual_max_v = max_velocity_mm_s

    total_time = accel_time + cruise_time + decel_time

    # Convert distances to ticks — cruise_ticks computed last to absorb rounding
    total_ticks = calc_encoder_ticks(distance_mm, wheel_diameter_mm, encoder_ticks_per_rev, gear_ratio)
    accel_ticks = calc_encoder_ticks(accel_distance, wheel_diameter_mm, encoder_ticks_per_rev, gear_ratio)
    decel_ticks = calc_encoder_ticks(decel_distance, wheel_diameter_mm, encoder_ticks_per_rev, gear_ratio)
    cruise_ticks = total_ticks - accel_ticks - decel_ticks

    # Cruise velocity in ticks per second
    circumference = math.pi * wheel_diameter_mm
    ticks_per_mm = (encoder_ticks_per_rev * gear_ratio) / circumference
    cruise_velocity_tps = actual_max_v * ticks_per_mm

    # PID starting points (heuristic for FTC motor controllers)
    kp = 10.0 / total_ticks if total_ticks > 0 else 0.01
    ki = 0.0  # start with zero integral
    kd = kp * 0.1  # derivative = 10% of proportional

    notes: list[str] = []
    if cruise_ticks <= 0:
        notes.append("Triangular profile — distance too short to reach cruise velocity")
    notes.append(f"Peak velocity: {actual_max_v:.0f} mm/s")
    notes.append(f"Acceleration: {acceleration_mm_s2:.0f} mm/s^2")
    notes.append("PID gains are starting points — tune on actual robot")

    return MotionProfile(
        total_ticks=total_ticks,
        cruise_velocity_tps=round(cruise_velocity_tps, 1),
        accel_ticks=accel_ticks,
        decel_ticks=decel_ticks,
        cruise_ticks=cruise_ticks,
        total_time_s=round(total_time, 3),
        accel_time_s=round(accel_time, 3),
        suggested_kp=round(kp, 6),
        suggested_ki=ki,
        suggested_kd=round(kd, 6),
        notes=tuple(notes),
    )
