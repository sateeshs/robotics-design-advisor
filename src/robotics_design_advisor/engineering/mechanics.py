"""Mechanical engineering calculations for FTC/FRC robot design.

Pure functions — no side effects, no I/O.  All inputs are primitive types
or frozen dataclasses from ``models.py``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import (
    ArmAnalysis,
    CenterOfGravity,
    DrivetrainAnalysis,
    GearRatioResult,
    MotorSpec,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRAVITY_M_S2 = 9.80665
KG_CM_TO_N_M = 0.0980665  # 1 kg·cm ≈ 0.098 N·m
LOADED_SPEED_FACTOR = 0.80  # Empirical: ~80% of free speed under normal driving
USABLE_TORQUE_FACTOR = 0.50  # Continuous safe torque: 50% of stall avoids overheating
STALL_FRACTION_AT_SPEED = 0.20  # Current fraction above free at ~80% free speed


# ---------------------------------------------------------------------------
# Drivetrain
# ---------------------------------------------------------------------------

def calc_drivetrain_speed(
    motor: MotorSpec,
    wheel_diameter_mm: float,
    external_ratio: float = 1.0,
    motor_count: int = 4,
) -> DrivetrainAnalysis:
    """Analyse a drivetrain given motor, wheel, and gearing.

    Parameters
    ----------
    motor : MotorSpec
        Motor driving the wheels.
    wheel_diameter_mm : float
        Wheel outer diameter in mm (must be > 0).
    external_ratio : float
        Additional gear reduction *after* the motor gearbox (must be > 0).
        1.0 means direct from motor output to wheel.
    motor_count : int
        Number of drive motors (typically 2 or 4).
    """
    if wheel_diameter_mm <= 0:
        raise ValueError(f"wheel_diameter_mm must be positive, got {wheel_diameter_mm}")
    if external_ratio <= 0:
        raise ValueError(f"external_ratio must be positive, got {external_ratio}")
    if motor_count <= 0:
        raise ValueError(f"motor_count must be positive, got {motor_count}")

    wheel_circumference_m = math.pi * wheel_diameter_mm / 1000.0

    output_rpm = motor.free_speed_rpm / external_ratio
    free_speed_m_s = (output_rpm * wheel_circumference_m) / 60.0

    loaded_speed_m_s = free_speed_m_s * LOADED_SPEED_FACTOR

    total_stall = motor.stall_current_a * motor_count
    total_free = motor.free_current_a * motor_count
    total_weight = motor.weight_grams * motor_count

    warnings: list[str] = []
    if free_speed_m_s > 2.5:
        warnings.append(
            f"Free speed {free_speed_m_s:.1f} m/s is very fast — "
            "consider higher gear ratio for controllability"
        )
    if free_speed_m_s < 0.5:
        warnings.append(
            f"Free speed {free_speed_m_s:.1f} m/s is slow — "
            "consider lower gear ratio"
        )

    recommended = 0.8 <= free_speed_m_s <= 2.2

    notes: list[str] = []
    notes.append(f"External gear ratio: {external_ratio:.1f}:1")
    notes.append(f"Output RPM at wheel: {output_rpm:.0f}")

    return DrivetrainAnalysis(
        free_speed_m_s=round(free_speed_m_s, 3),
        loaded_speed_m_s=round(loaded_speed_m_s, 3),
        total_stall_current_a=round(total_stall, 2),
        total_free_current_a=round(total_free, 2),
        total_motor_weight_grams=total_weight,
        recommended=recommended,
        warnings=tuple(warnings),
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Gear ratio solver
# ---------------------------------------------------------------------------

def calc_gear_ratio_for_speed(
    motor: MotorSpec,
    wheel_diameter_mm: float,
    target_speed_m_s: float,
) -> GearRatioResult:
    """Find the external gear ratio needed to hit a target drivetrain speed.

    Returns the ratio and the resulting actual speed.
    """
    if wheel_diameter_mm <= 0:
        raise ValueError(f"wheel_diameter_mm must be positive, got {wheel_diameter_mm}")

    wheel_circumference_m = math.pi * wheel_diameter_mm / 1000.0

    if target_speed_m_s <= 0:
        external_ratio = 1.0
    else:
        external_ratio = (
            motor.free_speed_rpm * wheel_circumference_m
        ) / (60.0 * target_speed_m_s)

    external_ratio = max(1.0, round(external_ratio, 2))

    actual_speed = (
        (motor.free_speed_rpm / external_ratio) * wheel_circumference_m
    ) / 60.0

    current_at_speed = motor.free_current_a + STALL_FRACTION_AT_SPEED * (
        motor.stall_current_a - motor.free_current_a
    )

    return GearRatioResult(
        motor_sku=motor.sku,
        motor_ratio=motor.gear_ratio,
        external_ratio=external_ratio,
        total_ratio=round(motor.gear_ratio * external_ratio, 2),
        actual_speed_m_s=round(actual_speed, 3),
        current_at_speed_a=round(current_at_speed, 2),
        within_spec=True,
    )


# ---------------------------------------------------------------------------
# Arm / elevator torque
# ---------------------------------------------------------------------------

def calc_arm_torque(
    motor: MotorSpec,
    arm_length_mm: float,
    load_kg: float,
    external_ratio: float = 1.0,
) -> ArmAnalysis:
    """Check whether a motor can hold a load at the end of an arm.

    The worst case is arm horizontal (cos 0° = 1).

    Parameters
    ----------
    motor : MotorSpec
        Motor driving the arm joint.
    arm_length_mm : float
        Distance from pivot to load in mm (must be > 0).
    load_kg : float
        Mass at the end of the arm in kg (must be >= 0).
    external_ratio : float
        Additional gear reduction after motor gearbox (must be > 0).
    """
    if arm_length_mm <= 0:
        raise ValueError(f"arm_length_mm must be positive, got {arm_length_mm}")
    if load_kg < 0:
        raise ValueError(f"load_kg must be non-negative, got {load_kg}")
    if external_ratio <= 0:
        raise ValueError(f"external_ratio must be positive, got {external_ratio}")

    arm_length_cm = arm_length_mm / 10.0
    required_torque = load_kg * arm_length_cm  # kg·cm at horizontal

    available_torque = motor.stall_torque_kg_cm * external_ratio
    usable_torque = available_torque * USABLE_TORQUE_FACTOR

    margin = ((usable_torque - required_torque) / required_torque * 100.0
              if required_torque > 0 else 999.0)

    can_hold = usable_torque >= required_torque

    max_load = usable_torque / arm_length_cm

    warnings: list[str] = []
    if margin < 20:
        warnings.append(
            f"Torque margin only {margin:.0f}% — arm may stall under load"
        )
    if external_ratio < 2.0 and load_kg > 1.0:
        warnings.append(
            "Consider higher gear ratio for heavy arm loads"
        )

    return ArmAnalysis(
        required_torque_kg_cm=round(required_torque, 2),
        available_torque_kg_cm=round(usable_torque, 2),
        torque_margin_pct=round(margin, 1),
        can_hold=can_hold,
        max_load_at_length_kg=round(max_load, 2),
        warnings=tuple(warnings),
    )


def calc_elevator_force(
    motor: MotorSpec,
    spool_diameter_mm: float,
    load_kg: float,
    external_ratio: float = 1.0,
) -> ArmAnalysis:
    """Check whether a motor can lift a load via spool/pulley.

    Elevator force = (motor_torque × gear_ratio) / spool_radius.
    Load force = mass × gravity.
    """
    if spool_diameter_mm <= 0:
        raise ValueError(f"spool_diameter_mm must be positive, got {spool_diameter_mm}")
    if load_kg < 0:
        raise ValueError(f"load_kg must be non-negative, got {load_kg}")
    if external_ratio <= 0:
        raise ValueError(f"external_ratio must be positive, got {external_ratio}")

    spool_radius_cm = spool_diameter_mm / 20.0  # mm → cm, then ÷ 2

    available_torque = motor.stall_torque_kg_cm * external_ratio * USABLE_TORQUE_FACTOR
    required_torque = load_kg * spool_radius_cm

    margin = ((available_torque - required_torque) / required_torque * 100.0
              if required_torque > 0 else 999.0)

    can_hold = available_torque >= required_torque
    max_load = available_torque / spool_radius_cm

    warnings: list[str] = []
    if margin < 20:
        warnings.append(
            f"Elevator torque margin only {margin:.0f}% — may stall under load"
        )

    return ArmAnalysis(
        required_torque_kg_cm=round(required_torque, 2),
        available_torque_kg_cm=round(available_torque, 2),
        torque_margin_pct=round(margin, 1),
        can_hold=can_hold,
        max_load_at_length_kg=round(max_load, 2),
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Center of gravity
# ---------------------------------------------------------------------------

def calc_center_of_gravity(
    components: Sequence[tuple[float, float, float, float]],
    footprint_mm: tuple[float, float] = (457.0, 457.0),
) -> CenterOfGravity:
    """Compute the combined center of gravity.

    Parameters
    ----------
    components : sequence of (x_mm, y_mm, z_mm, mass_grams) tuples
        Position and mass of each component.
        x = width axis, y = height axis, z = depth axis.
    footprint_mm : (width, depth)
        Robot footprint for checking CG containment (plan view: x, z).
    """
    if not components:
        return CenterOfGravity(0, 0, 0, 0, True, 0)

    total_mass = sum(c[3] for c in components)
    if total_mass <= 0:
        return CenterOfGravity(0, 0, 0, 0, True, 0)

    cx = sum(c[0] * c[3] for c in components) / total_mass
    cy = sum(c[1] * c[3] for c in components) / total_mass
    cz = sum(c[2] * c[3] for c in components) / total_mass

    center_x = footprint_mm[0] / 2.0
    center_z = footprint_mm[1] / 2.0

    # Plan-view offset: x and z axes form the ground plane
    offset = math.sqrt((cx - center_x) ** 2 + (cz - center_z) ** 2)
    within = (0 <= cx <= footprint_mm[0]) and (0 <= cz <= footprint_mm[1])

    return CenterOfGravity(
        x_mm=round(cx, 1),
        y_mm=round(cy, 1),
        z_mm=round(cz, 1),
        total_mass_grams=round(total_mass, 1),
        within_footprint=within,
        offset_from_center_mm=round(offset, 1),
    )
