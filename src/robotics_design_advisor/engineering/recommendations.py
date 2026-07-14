"""Mechanism recommendation engine for FTC/FRC robot design.

Maps game requirements (speed, accuracy, range) to specific mechanism
types and motor selections.  Pure functions — no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import (
    DrivetrainChoice,
    IntakeChoice,
    MotorRecommendation,
    MotorSpec,
    ScorerChoice,
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_0_1(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


# ---------------------------------------------------------------------------
# Drivetrain recommendations
# ---------------------------------------------------------------------------

_DRIVETRAIN_SPECS: dict[str, dict] = {
    "mecanum": {
        "motor_count": 4,
        "agility_score": 0.9,
        "push_score": 0.3,
        "speed_score": 0.8,
        "pros": (
            "Omnidirectional movement — strafe without turning",
            "Well-understood, many resources available",
            "Good balance of speed and maneuverability",
        ),
        "cons": (
            "Lower traction than differential — weak pushing",
            "Uses 4 motors for drivetrain alone",
            "Mecanum wheels are heavier than standard wheels",
        ),
        "motor_ratios": (19.2, 13.7),
    },
    "differential": {
        "motor_count": 4,
        "agility_score": 0.4,
        "push_score": 0.9,
        "speed_score": 0.7,
        "pros": (
            "Maximum traction for pushing and climbing",
            "Simple, robust, easy to maintain",
            "Lower cost — standard wheels",
        ),
        "cons": (
            "Cannot strafe — must turn to change direction",
            "Slower cycle time when alignment is needed",
            "Less agile in tight spaces",
        ),
        "motor_ratios": (19.2, 13.7),
    },
    "swerve": {
        "motor_count": 4,
        "agility_score": 1.0,
        "push_score": 0.4,
        "speed_score": 0.6,
        "pros": (
            "Ultimate agility — translate and rotate independently",
            "High traction with full omnidirectional movement",
            "Very rare in FTC — maximum uniqueness",
        ),
        "cons": (
            "Extremely complex to build and program",
            "Requires 4 additional steering servos or motors",
            "High risk — hard to debug at competition",
        ),
        "motor_ratios": (13.7, 19.2),
    },
    "H-drive": {
        "motor_count": 5,
        "agility_score": 0.7,
        "push_score": 0.5,
        "speed_score": 0.7,
        "pros": (
            "Strafing capability with simpler build than mecanum",
            "Better traction than mecanum for forward/reverse",
            "Uncommon design — good uniqueness",
        ),
        "cons": (
            "Uses 5 motors — leaves only 3 for mechanisms",
            "Fifth wheel placement is critical for balance",
            "Limited strafe speed compared to mecanum",
        ),
        "motor_ratios": (19.2, 13.7),
    },
}

# SKUs for common drivetrain motor ratios
_RATIO_TO_SKU: dict[float, str] = {
    3.7: "5202-0002-0003",
    5.2: "5202-0002-0005",
    13.7: "5202-0002-0014",
    19.2: "5202-0002-0019",
    26.9: "5202-0002-0027",
    50.9: "5202-0002-0051",
    71.2: "5202-0002-0071",
    99.5: "5202-0002-0100",
    139.0: "5202-0002-0139",
    188.0: "5202-0002-0188",
    435.0: "5202-0002-0435",
}


def recommend_drivetrain(
    speed_priority: float,
    push_priority: float,
    agility: float,
) -> DrivetrainChoice:
    """Recommend a drivetrain type based on design priorities.

    Parameters
    ----------
    speed_priority : float
        How important top speed is (0.0–1.0).
    push_priority : float
        How important pushing power is (0.0–1.0).
    agility : float
        How important omnidirectional movement is (0.0–1.0).
    """
    _validate_0_1(speed_priority, "speed_priority")
    _validate_0_1(push_priority, "push_priority")
    _validate_0_1(agility, "agility")

    best_type = "mecanum"
    best_score = -1.0

    for dt_type, spec in _DRIVETRAIN_SPECS.items():
        score = (
            speed_priority * spec["speed_score"]
            + push_priority * spec["push_score"]
            + agility * spec["agility_score"]
        )
        if score > best_score:
            best_score = score
            best_type = dt_type

    spec = _DRIVETRAIN_SPECS[best_type]
    motor_skus = tuple(
        _RATIO_TO_SKU[r] for r in spec["motor_ratios"] if r in _RATIO_TO_SKU
    )

    return DrivetrainChoice(
        drivetrain_type=best_type,
        motor_count=spec["motor_count"],
        rationale=(
            f"Selected {best_type} based on priorities: "
            f"speed={speed_priority:.1f}, push={push_priority:.1f}, agility={agility:.1f}. "
            f"Composite score: {best_score:.2f}."
        ),
        pros=spec["pros"],
        cons=spec["cons"],
        recommended_motor_skus=motor_skus,
    )


# ---------------------------------------------------------------------------
# Intake recommendations
# ---------------------------------------------------------------------------

_INTAKE_SPECS: dict[str, dict] = {
    "front_roller": {
        "motor_count": 1,
        "servo_count": 0,
        "speed_score": 0.8,
        "size_max_mm": 150.0,
        "shape_affinity": ("sphere", "cylinder"),
        "pros": (
            "Fast continuous intake — good cycle time",
            "Simple single-motor design",
            "Works well with round game elements",
        ),
        "cons": (
            "Struggles with large or irregular shapes",
            "Elements can bounce out if speed is wrong",
            "Only collects from front",
        ),
    },
    "dual_side_intake": {
        "motor_count": 2,
        "servo_count": 0,
        "speed_score": 0.9,
        "size_max_mm": 180.0,
        "shape_affinity": ("sphere", "cylinder", "cube"),
        "pros": (
            "Collect from both sides — fastest collection",
            "Can grab while driving past elements",
            "Handles wider range of element sizes",
        ),
        "cons": (
            "Uses 2 motors — higher motor budget",
            "More complex mechanism",
            "Wider robot footprint",
        ),
    },
    "over_body_intake": {
        "motor_count": 1,
        "servo_count": 0,
        "speed_score": 0.6,
        "size_max_mm": 140.0,
        "shape_affinity": ("sphere",),
        "pros": (
            "Space-efficient — elements travel over robot",
            "Natural path to rear-mounted scorer",
            "Single motor keeps budget low",
        ),
        "cons": (
            "Longer element path — slower feeding",
            "Only works with round elements",
            "Height constraint from over-body path",
        ),
    },
    "claw_gripper": {
        "motor_count": 0,
        "servo_count": 1,
        "speed_score": 0.3,
        "size_max_mm": 300.0,
        "shape_affinity": ("cube", "cylinder", "irregular"),
        "pros": (
            "Handles large, irregular, or delicate elements",
            "Uses servo — no motor budget impact",
            "Precise placement possible",
        ),
        "cons": (
            "Slowest intake — one element at a time",
            "Must align carefully before grabbing",
            "Grip force limits element weight",
        ),
    },
}


def recommend_intake(
    element_size_mm: float,
    element_shape: str,
    intake_speed: float,
) -> IntakeChoice:
    """Recommend an intake mechanism.

    Parameters
    ----------
    element_size_mm : float
        Approximate diameter or width of the game element in mm.
    element_shape : str
        Shape category: "sphere", "cube", "cylinder", "irregular".
    intake_speed : float
        How important intake speed is (0.0–1.0).
    """
    _validate_positive(element_size_mm, "element_size_mm")
    _validate_0_1(intake_speed, "intake_speed")

    best_type = "front_roller"
    best_score = -1.0

    for intake_type, spec in _INTAKE_SPECS.items():
        # Base: speed affinity
        score = intake_speed * spec["speed_score"]

        # Bonus for shape match
        if element_shape in spec["shape_affinity"]:
            score += 0.3

        # Bonus for simpler mechanism when element is small (< 120mm)
        if element_size_mm < 120.0 and spec["motor_count"] + spec["servo_count"] <= 1:
            score += 0.15

        # Penalty if element is too large for this intake
        if element_size_mm > spec["size_max_mm"]:
            score -= 0.5

        if score > best_score:
            best_score = score
            best_type = intake_type

    spec = _INTAKE_SPECS[best_type]

    return IntakeChoice(
        intake_type=best_type,
        motor_count=spec["motor_count"],
        servo_count=spec["servo_count"],
        rationale=(
            f"Selected {best_type} for {element_shape} elements "
            f"({element_size_mm:.0f}mm), speed priority {intake_speed:.1f}."
        ),
        pros=spec["pros"],
        cons=spec["cons"],
    )


# ---------------------------------------------------------------------------
# Scorer recommendations
# ---------------------------------------------------------------------------

_SCORER_SPECS: dict[str, dict] = {
    "dual_flywheel": {
        "motor_count": 2,
        "servo_count": 0,
        "range_score": 0.9,
        "accuracy_score": 0.7,
        "rate_score": 0.9,
        "min_range_mm": 500.0,
        "pros": (
            "High fire rate — continuous feeding possible",
            "Good range and consistency",
            "Adjustable speed for distance control",
        ),
        "cons": (
            "Uses 2 motors for scorer alone",
            "Spin-up time before first shot",
            "Requires consistent element feeding",
        ),
    },
    "single_flywheel_with_hood": {
        "motor_count": 1,
        "servo_count": 1,
        "range_score": 0.7,
        "accuracy_score": 0.8,
        "rate_score": 0.6,
        "min_range_mm": 300.0,
        "pros": (
            "Only 1 motor — saves motor budget",
            "Hood servo adjusts angle for range",
            "Simpler than dual flywheel",
        ),
        "cons": (
            "Lower fire rate than dual flywheel",
            "Single wheel gives less spin stability",
            "Hood mechanism adds complexity",
        ),
    },
    "catapult": {
        "motor_count": 1,
        "servo_count": 0,
        "range_score": 0.6,
        "accuracy_score": 0.4,
        "rate_score": 0.7,
        "min_range_mm": 500.0,
        "pros": (
            "Simple mechanism — single motor",
            "Can launch multiple elements at once",
            "No spin-up time needed",
        ),
        "cons": (
            "Less accurate than flywheel",
            "Fixed trajectory harder to adjust",
            "Reload cycle between launches",
        ),
    },
    "elevator_placer": {
        "motor_count": 1,
        "servo_count": 1,
        "range_score": 0.1,
        "accuracy_score": 1.0,
        "rate_score": 0.3,
        "min_range_mm": 0.0,
        "pros": (
            "Perfect accuracy — direct placement",
            "No missed shots possible",
            "Can score in high goals precisely",
        ),
        "cons": (
            "Must drive to goal every cycle",
            "Slowest scoring rate",
            "Elevator extends height — CG concern",
        ),
    },
}


def recommend_scorer(
    range_mm: float,
    accuracy: float,
    rate: float,
) -> ScorerChoice:
    """Recommend a scoring mechanism.

    Parameters
    ----------
    range_mm : float
        Required scoring distance in mm (0 = direct placement).
    accuracy : float
        How important scoring accuracy is (0.0–1.0).
    rate : float
        How important scoring rate is (0.0–1.0).
    """
    if range_mm < 0:
        raise ValueError(f"range_mm must be non-negative, got {range_mm}")
    _validate_0_1(accuracy, "accuracy")
    _validate_0_1(rate, "rate")

    best_type = "dual_flywheel"
    best_score = -1.0

    for scorer_type, spec in _SCORER_SPECS.items():
        score = (
            0.3 * spec["range_score"]
            + accuracy * spec["accuracy_score"]
            + rate * spec["rate_score"]
        )

        # Penalize ranged scorers for short-range tasks
        if range_mm < 500.0 and spec["min_range_mm"] >= 500.0:
            score -= 0.5

        # Bonus for placement at short range (where direct placement excels)
        if range_mm < 500.0 and scorer_type == "elevator_placer":
            score += 0.3

        # Penalize placement for long-range tasks
        if range_mm > 1000.0 and scorer_type == "elevator_placer":
            score -= 0.8

        if score > best_score:
            best_score = score
            best_type = scorer_type

    spec = _SCORER_SPECS[best_type]

    return ScorerChoice(
        scorer_type=best_type,
        motor_count=spec["motor_count"],
        servo_count=spec["servo_count"],
        rationale=(
            f"Selected {best_type} for {range_mm:.0f}mm range, "
            f"accuracy={accuracy:.1f}, rate={rate:.1f}."
        ),
        pros=spec["pros"],
        cons=spec["cons"],
    )


# ---------------------------------------------------------------------------
# Motor suggestions per application
# ---------------------------------------------------------------------------

# Ideal gear ratio ranges per application type
_APPLICATION_RATIO_RANGES: dict[str, tuple[float, float, float]] = {
    # (ideal_low, ideal_center, ideal_high)
    "drivetrain": (13.0, 19.2, 27.0),
    "arm": (50.0, 100.0, 188.0),
    "elevator": (20.0, 50.0, 100.0),
    "intake": (3.0, 5.2, 19.2),
    "shooter": (1.0, 3.7, 5.2),
    "turret": (50.0, 71.2, 139.0),
}


def suggest_motor_for_application(
    motors: Sequence[MotorSpec],
    application: str,
    top_n: int = 5,
) -> list[MotorRecommendation]:
    """Rank motors by suitability for a specific application.

    Parameters
    ----------
    motors : sequence of MotorSpec
        Available motors to choose from.
    application : str
        One of: "drivetrain", "arm", "elevator", "intake", "shooter", "turret".
    top_n : int
        Maximum number of recommendations to return.
    """
    valid_apps = set(_APPLICATION_RATIO_RANGES.keys())
    if application not in valid_apps:
        raise ValueError(
            f"Unknown application '{application}'. Valid: {sorted(valid_apps)}"
        )

    if not motors:
        return []

    low, center, high = _APPLICATION_RATIO_RANGES[application]
    results: list[MotorRecommendation] = []

    for motor in motors:
        ratio = motor.gear_ratio

        # Score based on how close the ratio is to the ideal range
        if low <= ratio <= high:
            # Within ideal range — score based on distance from center
            distance = abs(ratio - center) / (high - low)
            score = 100.0 - (distance * 30.0)
        elif ratio < low:
            # Below range — penalize proportionally
            distance = (low - ratio) / low
            score = max(0.0, 70.0 - distance * 100.0)
        else:
            # Above range — penalize proportionally
            distance = (ratio - high) / high
            score = max(0.0, 70.0 - distance * 100.0)

        score = round(min(100.0, max(0.0, score)), 1)

        rationale = _build_motor_rationale(motor, application, score)

        results.append(MotorRecommendation(
            sku=motor.sku,
            name=motor.name,
            gear_ratio=motor.gear_ratio,
            suitability_score=score,
            rationale=rationale,
        ))

    results.sort(key=lambda r: r.suitability_score, reverse=True)
    return results[:top_n]


def _build_motor_rationale(motor: MotorSpec, application: str, score: float) -> str:
    """Build a human-readable rationale for a motor recommendation."""
    if score >= 80:
        fit = "Excellent fit"
    elif score >= 60:
        fit = "Good fit"
    elif score >= 40:
        fit = "Acceptable"
    else:
        fit = "Poor fit"

    return (
        f"{fit} for {application}: {motor.gear_ratio}:1 ratio gives "
        f"{motor.free_speed_rpm:.0f} RPM free speed, "
        f"{motor.stall_torque_kg_cm:.1f} kg·cm stall torque."
    )
