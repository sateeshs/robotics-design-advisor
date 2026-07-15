"""Path planning — point-to-point paths with time budgets.

Plans paths between waypoints using trapezoidal velocity profiles
and validates against FTC/FRC autonomous period time limits.
Pure functions, no I/O.
"""

from __future__ import annotations

import math

from .field import (
    FTC_AUTO_PERIOD_S,
    FRC_AUTO_PERIOD_S,
    angle_between,
    distance_between,
)
from .models import PathSegment, PlannedPath, Pose

TURN_SPEED_DEG_S = 180.0  # typical FTC robot: 180 deg/s turn rate
DEFAULT_ACCEL_MM_S2 = 1000.0  # reasonable FTC drivetrain acceleration

_COMPETITION_PERIODS: dict[str, float] = {
    "FTC": FTC_AUTO_PERIOD_S,
    "FRC": FRC_AUTO_PERIOD_S,
}


def _normalize_angle(deg: float) -> float:
    """Normalize angle to [-180, 180]."""
    deg = deg % 360.0
    if deg > 180.0:
        deg -= 360.0
    return deg


def _calc_drive_time(
    distance_mm: float,
    max_speed_mm_s: float,
    max_accel_mm_s2: float,
) -> float:
    """Calculate drive time using trapezoidal velocity profile."""
    if distance_mm <= 0:
        return 0.0

    accel_time = max_speed_mm_s / max_accel_mm_s2
    accel_distance = 0.5 * max_accel_mm_s2 * accel_time**2

    if 2 * accel_distance >= distance_mm:
        # Triangular profile
        return 2.0 * math.sqrt(distance_mm / max_accel_mm_s2)

    cruise_distance = distance_mm - 2 * accel_distance
    cruise_time = cruise_distance / max_speed_mm_s
    return 2 * accel_time + cruise_time


def plan_path(
    start: Pose,
    waypoints: tuple[Pose, ...],
    max_speed_mm_s: float,
    max_accel_mm_s2: float = DEFAULT_ACCEL_MM_S2,
) -> PlannedPath:
    """Plan a path through a sequence of waypoints.

    Generates drive and turn segments between consecutive waypoints.
    Uses trapezoidal velocity profile for drive time estimates.

    Parameters
    ----------
    start : Pose
        Starting position and heading.
    waypoints : tuple of Pose
        Sequence of target poses (must have at least one).
    max_speed_mm_s : float
        Maximum drive speed in mm/s (must be > 0).
    max_accel_mm_s2 : float
        Maximum acceleration in mm/s^2.
    """
    if not waypoints:
        raise ValueError("waypoints must not be empty")
    if max_speed_mm_s <= 0:
        raise ValueError(f"max_speed_mm_s must be positive, got {max_speed_mm_s}")
    if max_accel_mm_s2 <= 0:
        raise ValueError(f"max_accel_mm_s2 must be positive, got {max_accel_mm_s2}")

    segments: list[PathSegment] = []
    all_waypoints = [start] + list(waypoints)
    current = start
    current_heading = start.heading_deg

    for target in waypoints:
        dist = distance_between(current, target)

        # Turn segment: rotate to face target
        if dist > 0.1:  # skip turn for negligible distance
            target_bearing = angle_between(current, target)
            turn_delta = abs(_normalize_angle(target_bearing - current_heading))

            if turn_delta > 1.0:  # skip tiny turns
                turn_time = turn_delta / TURN_SPEED_DEG_S
                turn_end = Pose(
                    x_mm=current.x_mm,
                    y_mm=current.y_mm,
                    heading_deg=target_bearing,
                )
                segments.append(PathSegment(
                    start=current,
                    end=turn_end,
                    distance_mm=0.0,
                    estimated_time_s=round(turn_time, 3),
                    segment_type="turn",
                ))
                current_heading = target_bearing

        # Drive segment
        if dist > 0.1:
            drive_time = _calc_drive_time(dist, max_speed_mm_s, max_accel_mm_s2)
            drive_end = Pose(
                x_mm=target.x_mm,
                y_mm=target.y_mm,
                heading_deg=current_heading,
            )
            segments.append(PathSegment(
                start=current,
                end=drive_end,
                distance_mm=round(dist, 1),
                estimated_time_s=round(drive_time, 3),
                segment_type="drive",
            ))

        # Final heading adjustment if target has different heading
        final_heading_delta = abs(_normalize_angle(target.heading_deg - current_heading))
        if final_heading_delta > 1.0:
            turn_time = final_heading_delta / TURN_SPEED_DEG_S
            segments.append(PathSegment(
                start=Pose(x_mm=target.x_mm, y_mm=target.y_mm, heading_deg=current_heading),
                end=target,
                distance_mm=0.0,
                estimated_time_s=round(turn_time, 3),
                segment_type="turn",
            ))
            current_heading = target.heading_deg

        current = target
        current_heading = target.heading_deg

    total_dist = sum(s.distance_mm for s in segments)
    total_time = sum(s.estimated_time_s for s in segments)

    return PlannedPath(
        segments=tuple(segments),
        total_distance_mm=round(total_dist, 1),
        total_time_s=round(total_time, 3),
        waypoints=tuple(all_waypoints),
    )


def check_time_budget(
    path: PlannedPath,
    competition: str,
) -> tuple[bool, float]:
    """Check if a path fits within the auto period.

    Parameters
    ----------
    path : PlannedPath
        The planned path to validate.
    competition : str
        "FTC" or "FRC".

    Returns
    -------
    (within_budget, margin_s) : tuple[bool, float]
        Whether the path fits, and the time margin in seconds.
    """
    if competition not in _COMPETITION_PERIODS:
        raise ValueError(
            f"competition must be one of {sorted(_COMPETITION_PERIODS)}, got '{competition}'"
        )

    period = _COMPETITION_PERIODS[competition]
    margin = period - path.total_time_s
    return margin >= 0, round(margin, 3)
