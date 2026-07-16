"""Approximate part placement within robot envelope.

Distributes parts evenly within subsystem-specific zones
of a 457x457x457mm FTC robot envelope. Pure functions — no
SolidWorks dependency.

Designed for upgrade: when profile-driven mating is added,
replace calculate_position logic without changing callers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """3D position and rotation for a part."""
    x: float  # mm
    y: float  # mm
    z: float  # mm
    rx: float  # degrees
    ry: float  # degrees
    rz: float  # degrees


# Zone format: ((x_min, y_min, z_min), (x_max, y_max, z_max))
# Within a 457 x 457 x 457 mm FTC robot envelope
SUBSYSTEM_ZONES: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "drivetrain":  ((0.0,   0.0,   0.0),  (457.0, 457.0, 50.0)),
    "intake":      ((300.0, 50.0,  50.0),  (457.0, 400.0, 200.0)),
    "scorer":      ((100.0, 50.0,  200.0), (350.0, 400.0, 400.0)),
    "endgame":     ((0.0,   50.0,  200.0), (150.0, 400.0, 400.0)),
    "electronics": ((0.0,   50.0,  50.0),  (200.0, 400.0, 200.0)),
}


def calculate_position(
    subsystem: str,
    part_index: int,
    part_count: int,
) -> Position:
    """Calculate approximate position for a part within its subsystem zone.

    Parts are distributed evenly along the x-axis of the subsystem zone.

    Parameters
    ----------
    subsystem : str
        One of: drivetrain, intake, scorer, endgame, electronics.
    part_index : int
        Zero-based index of this part within the subsystem.
    part_count : int
        Total number of parts in this subsystem.

    Raises
    ------
    ValueError
        If subsystem is unknown, part_index < 0, part_count < 1,
        or part_index >= part_count.
    """
    if subsystem not in SUBSYSTEM_ZONES:
        raise ValueError(
            f"Unknown subsystem '{subsystem}'. "
            f"Valid: {sorted(SUBSYSTEM_ZONES.keys())}"
        )
    if part_count < 1:
        raise ValueError(f"part_count must be >= 1, got {part_count}")
    if part_index < 0 or part_index >= part_count:
        raise ValueError(
            f"part_index must be 0..{part_count - 1}, got {part_index}"
        )

    (x_min, y_min, z_min), (x_max, y_max, z_max) = SUBSYSTEM_ZONES[subsystem]

    # Distribute along x-axis within the zone
    if part_count == 1:
        x = (x_min + x_max) / 2
    else:
        x = x_min + (x_max - x_min) * part_index / (part_count - 1)

    # Center in y and z
    y = (y_min + y_max) / 2
    z = (z_min + z_max) / 2

    return Position(
        x=round(x, 2),
        y=round(y, 2),
        z=round(z, 2),
        rx=0.0,
        ry=0.0,
        rz=0.0,
    )
