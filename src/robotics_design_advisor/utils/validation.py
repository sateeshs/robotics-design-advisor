"""Input validation for Robotics Design Advisor tool parameters.

Validates dimensions, names, enums, and paths before COM calls
to prevent cryptic SolidWorks errors.
"""

import re
from typing import Any

from ..constants import SwPlanes, SwEndConditions, SwMateTypes, SwDocumentTypes


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_dimension(value: Any, field: str, min_val: float = 0.001, max_val: float = 10000.0) -> float:
    """Validate a dimension value (mm). Must be positive and within range."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        raise ValidationError(field, f"Must be a number, got {type(value).__name__}")

    if val <= 0:
        raise ValidationError(field, f"Must be positive, got {val}")
    if val < min_val:
        raise ValidationError(field, f"Too small: {val}mm (min: {min_val}mm)")
    if val > max_val:
        raise ValidationError(field, f"Too large: {val}mm (max: {max_val}mm)")

    return val


def validate_name(value: Any, field: str, max_length: int = 255) -> str:
    """Validate a name string (document name, feature name, etc.)."""
    if not isinstance(value, str):
        raise ValidationError(field, f"Must be a string, got {type(value).__name__}")

    name = value.strip()
    if not name:
        raise ValidationError(field, "Cannot be empty")
    if len(name) > max_length:
        raise ValidationError(field, f"Too long: {len(name)} chars (max: {max_length})")

    # SolidWorks doesn't allow these in file/feature names
    invalid_chars = r'[<>:"/\\|?*]'
    if re.search(invalid_chars, name):
        raise ValidationError(field, f"Contains invalid characters: {invalid_chars}")

    return name


def validate_plane(value: Any) -> str:
    """Validate and normalize a plane name."""
    if not isinstance(value, str):
        raise ValidationError("plane", f"Must be a string, got {type(value).__name__}")

    plane = SwPlanes.get(value)
    if plane not in SwPlanes.all():
        valid = ", ".join(SwPlanes.all())
        raise ValidationError("plane", f"Unknown plane '{value}'. Valid: {valid}")

    return plane


def validate_position(value: Any, field: str = "position") -> tuple[float, float, float]:
    """Validate a 3D position [x, y, z]."""
    if not isinstance(value, (list, tuple)):
        raise ValidationError(field, f"Must be a list of 3 numbers, got {type(value).__name__}")

    if len(value) != 3:
        raise ValidationError(field, f"Must have exactly 3 values [x, y, z], got {len(value)}")

    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        raise ValidationError(field, "All values must be numbers")


def validate_sku(value: Any) -> str:
    """Validate a goBILDA SKU format (e.g., '1120-0001-0288')."""
    if not isinstance(value, str):
        raise ValidationError("sku", f"Must be a string, got {type(value).__name__}")

    sku = value.strip()
    if not sku:
        raise ValidationError("sku", "Cannot be empty")

    # goBILDA SKUs follow pattern: NNNN-NNNN-NNNN
    if not re.match(r"^\d{4}-\d{4}-\d{4}$", sku):
        raise ValidationError(
            "sku",
            f"Invalid SKU format '{sku}'. Expected: NNNN-NNNN-NNNN (e.g., 1120-0001-0288)",
        )

    return sku


def validate_mate_type(value: Any) -> int:
    """Validate and return a mate type enum value."""
    if isinstance(value, int):
        try:
            return int(SwMateTypes(value))
        except ValueError:
            pass

    if isinstance(value, str):
        mate_map = {
            "coincident": SwMateTypes.swMateCOINCIDENT,
            "concentric": SwMateTypes.swMateCONCENTRIC,
            "perpendicular": SwMateTypes.swMatePERPENDICULAR,
            "parallel": SwMateTypes.swMatePARALLEL,
            "tangent": SwMateTypes.swMateTANGENT,
            "distance": SwMateTypes.swMateDISTANCE,
            "angle": SwMateTypes.swMateANGLE,
            "lock": SwMateTypes.swMateLOCK,
            "width": SwMateTypes.swMateWIDTH,
        }
        result = mate_map.get(value.lower())
        if result is not None:
            return int(result)

    valid = "coincident, concentric, perpendicular, parallel, tangent, distance, angle, lock, width"
    raise ValidationError("mate_type", f"Unknown mate type '{value}'. Valid: {valid}")


def validate_end_condition(value: Any) -> int:
    """Validate and return an end condition enum value."""
    if isinstance(value, int):
        try:
            return int(SwEndConditions(value))
        except ValueError:
            pass

    if isinstance(value, str):
        condition_map = {
            "blind": SwEndConditions.swEndCondBlind,
            "through_all": SwEndConditions.swEndCondThroughAll,
            "through_all_both": SwEndConditions.swEndCondThroughAllBoth,
            "through_next": SwEndConditions.swEndCondThroughNext,
            "mid_plane": SwEndConditions.swEndCondMidPlane,
            "midplane": SwEndConditions.swEndCondMidPlane,
        }
        result = condition_map.get(value.lower())
        if result is not None:
            return int(result)

    valid = "blind, through_all, through_all_both, through_next, mid_plane"
    raise ValidationError("end_condition", f"Unknown end condition '{value}'. Valid: {valid}")
