"""Grabber/intake physics — grip force, servo torque, grip type selection.

Pure functions, no I/O.
"""

from __future__ import annotations

from .models import GrabberAnalysis

GRAVITY_M_S2 = 9.80665
SAFETY_FACTOR = 2.0
DEFAULT_FRICTION = 0.5       # rubber on foam/plastic
ROLLER_FRICTION = 0.7        # compliant rubber rollers
JAW_OPENING_MARGIN_MM = 10.0
SERVO_CURRENT_PER_NMM = 0.8  # mA per N-mm holding torque (empirical estimate)

# Grip type selection based on game piece shape
_SHAPE_TO_GRIP: dict[str, str] = {
    "cube": "claw",
    "box": "claw",
    "sphere": "roller_intake",
    "ball": "roller_intake",
    "ring": "claw",
    "cylinder": "claw",
    "cone": "claw",
    "pixel": "roller_intake",
    "hexagon": "roller_intake",
}


def recommend_grip_type(piece_shape: str) -> str:
    """Recommend a grip type based on game piece shape.

    Returns "claw", "roller_intake", or "passive_funnel".
    """
    return _SHAPE_TO_GRIP.get(piece_shape.lower(), "claw")


def analyze_grabber(
    piece_weight_g: float,
    piece_dimensions_mm: tuple[float, ...],
    grip_type: str,
    jaw_length_mm: float,
    friction_coefficient: float | None = None,
) -> GrabberAnalysis:
    """Calculate grabber physics for a given game piece.

    Parameters
    ----------
    piece_weight_g : float
        Game piece mass in grams (must be > 0).
    piece_dimensions_mm : tuple of float
        Game piece dimensions (x, y, z) in mm.
    grip_type : str
        "claw", "roller_intake", or "passive_funnel".
    jaw_length_mm : float
        Lever arm from servo pivot to jaw tip in mm (must be > 0).
    friction_coefficient : float, optional
        Surface friction coefficient.  Defaults depend on grip type.
    """
    if piece_weight_g <= 0:
        raise ValueError(f"piece_weight_g must be positive, got {piece_weight_g}")
    if jaw_length_mm <= 0:
        raise ValueError(f"jaw_length_mm must be positive, got {jaw_length_mm}")

    weight_n = (piece_weight_g / 1000.0) * GRAVITY_M_S2
    largest_dim = max(piece_dimensions_mm)
    jaw_opening = largest_dim + JAW_OPENING_MARGIN_MM

    notes: list[str] = []

    if grip_type == "passive_funnel":
        return GrabberAnalysis(
            required_grip_force_n=0.0,
            required_torque_nmm=0.0,
            recommended_servo="None — passive geometry",
            jaw_opening_mm=round(jaw_opening, 1),
            grip_type="passive_funnel",
            hold_current_ma=0.0,
            notes=("Passive funnel — no motor or servo needed. Design guides to direct pieces.",),
        )

    if grip_type == "roller_intake":
        friction = friction_coefficient if friction_coefficient is not None else ROLLER_FRICTION
        grip_force = (weight_n * SAFETY_FACTOR) / friction
        torque = grip_force * jaw_length_mm
        notes.append("Roller intake — use compliant rubber wheels for grip.")
        notes.append("Ensure rollers spin inward to pull piece into robot.")
        servo_label = "goBILDA Speed Servo or DC motor"
    else:
        friction = friction_coefficient if friction_coefficient is not None else DEFAULT_FRICTION
        grip_force = (weight_n * SAFETY_FACTOR) / friction
        torque = grip_force * jaw_length_mm
        notes.append("Use rubber pads on jaw surfaces to increase friction.")
        if largest_dim > 100:
            notes.append("Large piece — consider parallel-jaw gripper for even contact.")
        servo_label = "goBILDA Torque Servo"

    # Round grip force first so torque is consistent with the stored value
    grip_force_rounded = round(grip_force, 3)
    torque_rounded = round(grip_force_rounded * jaw_length_mm, 3)
    hold_current = torque_rounded * SERVO_CURRENT_PER_NMM

    return GrabberAnalysis(
        required_grip_force_n=grip_force_rounded,
        required_torque_nmm=torque_rounded,
        recommended_servo=servo_label,
        jaw_opening_mm=round(jaw_opening, 1),
        grip_type=grip_type,
        hold_current_ma=round(hold_current, 1),
        notes=tuple(notes),
    )
