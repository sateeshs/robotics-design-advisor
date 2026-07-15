"""Lift/elevator/arm physics — force, torque, counterbalance, spool sizing.

Pure functions, no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.models import LiftAnalysis
from robotics_design_advisor.mechanisms.motor_selection import KG_CM_TO_NMM, select_motor

GRAVITY = 9.80665
FRICTION_FACTOR = 1.15         # 15% friction overhead for linear slides
DEFAULT_CARRIAGE_MASS_G = 150  # typical slide carriage mass
DEFAULT_SPOOL_DIAMETER_MM = 30.0
ACCEL_FACTOR = 1.5             # peak force = 1.5x continuous (for acceleration)

VALID_LIFT_TYPES = {"elevator", "four_bar", "arm", "cascade"}


def analyze_lift(
    payload_mass_g: float,
    max_height_mm: float,
    lift_type: str,
    motors: Sequence[MotorSpec],
    stages: int = 1,
    carriage_mass_g: float = DEFAULT_CARRIAGE_MASS_G,
    spool_diameter_mm: float = DEFAULT_SPOOL_DIAMETER_MM,
) -> LiftAnalysis:
    """Full lift analysis — force, torque, motor selection, timing.

    Parameters
    ----------
    payload_mass_g : float
        Payload mass in grams (must be > 0).
    max_height_mm : float
        Maximum lift height in mm (must be > 0).
    lift_type : str
        "elevator", "four_bar", "arm", or "cascade".
    motors : sequence of MotorSpec
        Available motors.
    stages : int
        Number of elevator stages (only for elevator/cascade).
    carriage_mass_g : float
        Carriage/slide mass in grams.
    spool_diameter_mm : float
        Spool diameter for string/belt elevator.
    """
    if payload_mass_g <= 0:
        raise ValueError(f"payload_mass_g must be positive, got {payload_mass_g}")
    if max_height_mm <= 0:
        raise ValueError(f"max_height_mm must be positive, got {max_height_mm}")
    if lift_type not in VALID_LIFT_TYPES:
        raise ValueError(
            f"lift_type must be one of {sorted(VALID_LIFT_TYPES)}, got '{lift_type}'"
        )

    payload_kg = payload_mass_g / 1000.0
    carriage_kg = carriage_mass_g / 1000.0
    total_mass_kg = payload_kg + carriage_kg
    notes: list[str] = []

    if lift_type in ("elevator", "cascade"):
        # Elevator: F = (m_payload + m_carriage) * g * stages * friction_factor
        stage_multiplier = max(1, stages)
        required_force = total_mass_kg * GRAVITY * stage_multiplier * FRICTION_FACTOR
        peak_force = required_force * ACCEL_FACTOR

        # Torque at spool: T = F * spool_radius
        spool_radius_mm = spool_diameter_mm / 2.0
        required_torque = required_force * spool_radius_mm  # N-mm

        # Counterbalance: match ~80% of gravity force with constant-force spring
        counterbalance = total_mass_kg * GRAVITY * 0.8

        # Motor selection based on torque at spool
        motor_match = select_motor(required_torque, 100.0, tuple(motors))

        # Lift speed: v = angular_velocity * spool_radius
        motor_rpm = motor_match.output_rpm
        angular_vel_rad_s = motor_rpm * 2.0 * math.pi / 60.0
        spool_radius_m = spool_radius_mm / 1000.0
        speed_mm_s = angular_vel_rad_s * spool_radius_m * 1000.0

        time_to_height = max_height_mm / speed_mm_s if speed_mm_s > 0 else float("inf")

        if stages > 1:
            notes.append(f"{stages}-stage elevator: {stage_multiplier}x force multiplier")
        notes.append(f"Spool diameter: {spool_diameter_mm:.0f}mm")
        if counterbalance > 0:
            notes.append(f"Counterbalance with {counterbalance:.1f}N constant-force spring")

        actual_spool = spool_diameter_mm

    elif lift_type == "four_bar":
        # 4-bar arm: torque = m * g * L * cos(theta) — worst case at horizontal
        arm_length_mm = max_height_mm  # arm reach ≈ max height
        arm_length_m = arm_length_mm / 1000.0
        required_torque_nm = total_mass_kg * GRAVITY * arm_length_m  # at horizontal
        required_torque = required_torque_nm * 1000.0  # N-mm
        required_force = total_mass_kg * GRAVITY
        peak_force = required_force * ACCEL_FACTOR

        counterbalance = total_mass_kg * GRAVITY * 0.7

        motor_match = select_motor(required_torque, 60.0, tuple(motors))

        # Speed estimate: 90 degrees in a reasonable time
        motor_rpm = motor_match.output_rpm
        time_per_rev_s = 60.0 / motor_rpm if motor_rpm > 0 else float("inf")
        time_to_height = time_per_rev_s * 0.25  # quarter turn
        speed_mm_s = max_height_mm / time_to_height if time_to_height > 0 else 0.0

        notes.append("4-bar linkage — torque varies with angle (worst at horizontal)")
        notes.append(f"Counterbalance with {counterbalance:.1f}N spring at pivot")
        actual_spool = 0.0

    else:  # "arm"
        arm_length_mm = max_height_mm
        arm_length_m = arm_length_mm / 1000.0
        required_torque_nm = total_mass_kg * GRAVITY * arm_length_m
        required_torque = required_torque_nm * 1000.0
        required_force = total_mass_kg * GRAVITY
        peak_force = required_force * ACCEL_FACTOR
        counterbalance = total_mass_kg * GRAVITY * 0.5

        motor_match = select_motor(required_torque, 40.0, tuple(motors))

        motor_rpm = motor_match.output_rpm
        time_per_rev_s = 60.0 / motor_rpm if motor_rpm > 0 else float("inf")
        time_to_height = time_per_rev_s * 0.25
        speed_mm_s = max_height_mm / time_to_height if time_to_height > 0 else 0.0

        notes.append("Simple arm — keep payload light for best performance")
        actual_spool = 0.0

    return LiftAnalysis(
        required_force_n=round(required_force, 2),
        peak_force_n=round(peak_force, 2),
        required_torque_nmm=round(required_torque, 1),
        motor_recommendation=motor_match.motor_name,
        gear_ratio=motor_match.gear_ratio,
        max_speed_mm_s=round(speed_mm_s, 1),
        time_to_max_height_s=round(time_to_height, 2),
        counterbalance_force_n=round(counterbalance, 2),
        spool_diameter_mm=actual_spool,
        lift_type=lift_type,
        notes=tuple(notes),
    )
