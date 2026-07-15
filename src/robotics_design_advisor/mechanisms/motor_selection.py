"""Motor selection engine — match torque+speed requirements to goBILDA motors.

Loads the Yellow Jacket motor database and scores each motor variant
against a given torque and speed requirement. Pure functions except
for ``load_motor_database`` which reads the JSON file once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.models import MotorMatch

# 1 kg-cm = 98.0665 N-mm
KG_CM_TO_NMM = 98.0665

# Fraction of stall torque considered safe for continuous vs intermittent duty
_DUTY_FACTORS: dict[str, float] = {
    "continuous": 0.50,
    "intermittent": 0.70,
}

_MOTOR_DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "engineering"
    / "motor_data"
    / "gobilda_yellow_jacket.json"
)


def load_motor_database(path: Path | None = None) -> tuple[MotorSpec, ...]:
    """Load goBILDA Yellow Jacket motor specs from JSON.

    Parameters
    ----------
    path : Path, optional
        Override path to the motor JSON file.  Defaults to the bundled
        ``gobilda_yellow_jacket.json``.
    """
    data_path = path or _MOTOR_DATA_PATH
    with open(data_path) as f:
        data = json.load(f)

    motors: list[MotorSpec] = []
    for v in data["variants"]:
        motors.append(
            MotorSpec(
                sku=v["sku"],
                name=v["name"],
                gear_ratio=v["gear_ratio"],
                free_speed_rpm=v["free_speed_rpm"],
                stall_torque_kg_cm=v["stall_torque_kg_cm"],
                stall_current_a=v["stall_current_a"],
                free_current_a=v["free_current_a"],
                encoder_ppr=v["encoder_ppr"],
                shaft_type=v["shaft_type"],
                weight_grams=v["weight_grams"],
                voltage_nominal=data.get("voltage_nominal", 12.0),
            )
        )
    return tuple(motors)


def select_motor(
    required_torque_nmm: float,
    required_rpm: float,
    motors: tuple[MotorSpec, ...] | list[MotorSpec],
    duty: Literal["continuous", "intermittent"] = "continuous",
) -> MotorMatch:
    """Find the best motor for a torque + speed requirement.

    Scores each motor by how well its usable torque and free speed
    match the requirement.  Returns the single best match.

    Parameters
    ----------
    required_torque_nmm : float
        Required output torque in N-mm (must be >= 0).
    required_rpm : float
        Required output speed in RPM (must be >= 0).
    motors : sequence of MotorSpec
        Available motors to choose from.
    duty : "continuous" | "intermittent"
        Duty cycle — intermittent allows using a higher fraction of stall torque.
    """
    if required_torque_nmm < 0:
        raise ValueError(
            f"required_torque_nmm must be non-negative, got {required_torque_nmm}"
        )
    if required_rpm < 0:
        raise ValueError(
            f"required_rpm must be non-negative, got {required_rpm}"
        )
    if not motors:
        raise ValueError("No motors provided")

    duty_factor = _DUTY_FACTORS.get(duty, 0.50)
    best_score = float("-inf")
    best_match: MotorMatch | None = None

    for motor in motors:
        stall_torque_nmm = motor.stall_torque_kg_cm * KG_CM_TO_NMM
        usable_torque_nmm = stall_torque_nmm * duty_factor

        torque_margin_pct = (
            ((usable_torque_nmm - required_torque_nmm) / required_torque_nmm * 100.0)
            if required_torque_nmm > 0
            else 999.0
        )

        # Speed score: how well the motor's free RPM matches required RPM
        speed_ratio = motor.free_speed_rpm / required_rpm if required_rpm > 0 else 10.0
        if speed_ratio >= 1.0:
            speed_score = 1.0 - min(1.0, (speed_ratio - 1.0) / 5.0)
        else:
            speed_score = speed_ratio - 1.0  # negative if too slow

        # Torque score: positive margin is good, penalize excess heavily
        if torque_margin_pct >= 0:
            torque_score = 1.0 - min(1.0, torque_margin_pct / 500.0)
        else:
            torque_score = torque_margin_pct / 100.0  # negative, severe penalty

        # Combined score — torque is weighted 2x because stalling is worse than being slow
        score = torque_score * 2.0 + speed_score

        # Estimate operating current (linear interpolation on motor curve)
        load_fraction = (
            min(1.0, required_torque_nmm / stall_torque_nmm)
            if stall_torque_nmm > 0
            else 1.0
        )
        current_draw = (
            motor.free_current_a
            + load_fraction * (motor.stall_current_a - motor.free_current_a)
        )

        notes: list[str] = []
        if torque_margin_pct < 20.0:
            notes.append(
                f"Low torque margin ({torque_margin_pct:.0f}%) — risk of stalling"
            )
        if motor.free_speed_rpm < required_rpm:
            notes.append(
                f"Motor free speed ({motor.free_speed_rpm:.0f} RPM) below"
                f" required ({required_rpm:.0f} RPM)"
            )

        match = MotorMatch(
            motor_name=motor.name,
            motor_sku=motor.sku,
            base_rpm=motor.free_speed_rpm,
            stall_torque_nmm=round(stall_torque_nmm, 1),
            gear_ratio=motor.gear_ratio,
            output_rpm=motor.free_speed_rpm,
            output_torque_nmm=round(usable_torque_nmm, 1),
            torque_margin_pct=round(torque_margin_pct, 1),
            current_draw_a=round(current_draw, 2),
            notes=tuple(notes),
        )

        if score > best_score:
            best_score = score
            best_match = match

    if best_match is None:
        raise RuntimeError("Internal error: motor loop produced no result")
    return best_match
