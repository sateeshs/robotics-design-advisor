"""Field coordinate system, zone definitions, and pose utilities.

Covers FTC (144"×144") and FRC (54'1"×27') fields.
Pure functions, no I/O.
"""

from __future__ import annotations

import math

from .models import FieldConfig, Pose, Zone

# Auto period durations
FTC_AUTO_PERIOD_S = 30.0
FRC_AUTO_PERIOD_S = 15.0

# Field dimensions in mm
_FTC_WIDTH_MM = 3658.0   # 144 inches
_FTC_LENGTH_MM = 3658.0  # 144 inches (square field)
_FRC_WIDTH_MM = 16459.0  # 54'1"
_FRC_LENGTH_MM = 8229.0  # 27'

_VALID_ALLIANCES = {"red", "blue"}


def ftc_field(alliance: str) -> FieldConfig:
    """Create a standard FTC field configuration.

    Parameters
    ----------
    alliance : str
        "red" or "blue".
    """
    if alliance not in _VALID_ALLIANCES:
        raise ValueError(f"alliance must be 'red' or 'blue', got '{alliance}'")

    zones = (
        Zone(name="net_zone",
             center=Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0),
             radius_mm=300.0, zone_type="scoring"),
        Zone(name="observation_zone",
             center=Pose(x_mm=3058.0, y_mm=600.0, heading_deg=0.0),
             radius_mm=300.0, zone_type="pickup"),
        Zone(name="high_basket",
             center=Pose(x_mm=300.0, y_mm=300.0, heading_deg=0.0),
             radius_mm=200.0, zone_type="scoring"),
        Zone(name="parking",
             center=Pose(x_mm=3058.0, y_mm=3058.0, heading_deg=0.0),
             radius_mm=300.0, zone_type="parking"),
    )

    if alliance == "red":
        starts = (
            Pose(x_mm=300.0, y_mm=1829.0, heading_deg=0.0),
            Pose(x_mm=300.0, y_mm=2743.0, heading_deg=0.0),
        )
    else:
        starts = (
            Pose(x_mm=3358.0, y_mm=1829.0, heading_deg=180.0),
            Pose(x_mm=3358.0, y_mm=2743.0, heading_deg=180.0),
        )

    return FieldConfig(
        width_mm=_FTC_WIDTH_MM,
        length_mm=_FTC_LENGTH_MM,
        alliance=alliance,
        zones=zones,
        starting_positions=starts,
    )


def frc_field(alliance: str) -> FieldConfig:
    """Create a standard FRC field configuration.

    Parameters
    ----------
    alliance : str
        "red" or "blue".
    """
    if alliance not in _VALID_ALLIANCES:
        raise ValueError(f"alliance must be 'red' or 'blue', got '{alliance}'")

    zones = (
        Zone(name="speaker",
             center=Pose(x_mm=600.0, y_mm=4114.0, heading_deg=0.0),
             radius_mm=500.0, zone_type="scoring"),
        Zone(name="amp",
             center=Pose(x_mm=1800.0, y_mm=7800.0, heading_deg=0.0),
             radius_mm=400.0, zone_type="scoring"),
        Zone(name="source",
             center=Pose(x_mm=15000.0, y_mm=1000.0, heading_deg=0.0),
             radius_mm=600.0, zone_type="pickup"),
    )

    if alliance == "red":
        starts = (
            Pose(x_mm=1000.0, y_mm=4114.0, heading_deg=0.0),
            Pose(x_mm=1000.0, y_mm=5500.0, heading_deg=0.0),
            Pose(x_mm=1000.0, y_mm=6500.0, heading_deg=0.0),
        )
    else:
        starts = (
            Pose(x_mm=15459.0, y_mm=4114.0, heading_deg=180.0),
            Pose(x_mm=15459.0, y_mm=5500.0, heading_deg=180.0),
            Pose(x_mm=15459.0, y_mm=6500.0, heading_deg=180.0),
        )

    return FieldConfig(
        width_mm=_FRC_WIDTH_MM,
        length_mm=_FRC_LENGTH_MM,
        alliance=alliance,
        zones=zones,
        starting_positions=starts,
    )


def distance_between(a: Pose, b: Pose) -> float:
    """Euclidean distance between two poses in mm."""
    dx = b.x_mm - a.x_mm
    dy = b.y_mm - a.y_mm
    return math.sqrt(dx * dx + dy * dy)


def angle_between(a: Pose, b: Pose) -> float:
    """Bearing from pose a to pose b in degrees (0 = east, 90 = north).

    Returns 0.0 if a and b are the same point.
    """
    dx = b.x_mm - a.x_mm
    dy = b.y_mm - a.y_mm
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.degrees(math.atan2(dy, dx)) % 360.0


def find_zone(field: FieldConfig, name: str) -> Zone | None:
    """Find a zone by name in the field configuration."""
    for zone in field.zones:
        if zone.name == name:
            return zone
    return None


def is_in_zone(pose: Pose, zone: Zone) -> bool:
    """Check if a pose is within a zone's radius."""
    dist = distance_between(pose, zone.center)
    return dist <= zone.radius_mm
