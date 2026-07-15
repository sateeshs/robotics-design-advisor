"""Frozen dataclasses for autonomous coordination.

All models are immutable. Sequences use tuple, not list.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pose:
    """A 2D position with heading on the field."""
    x_mm: float
    y_mm: float
    heading_deg: float  # 0 = facing positive X


@dataclass(frozen=True)
class Zone:
    """A named region on the field."""
    name: str
    center: Pose
    radius_mm: float
    zone_type: str  # "scoring" | "pickup" | "parking" | "human_player"


@dataclass(frozen=True)
class FieldConfig:
    """Field dimensions, alliance, zones, and legal starting positions."""
    width_mm: float
    length_mm: float
    alliance: str  # "red" | "blue"
    zones: tuple[Zone, ...]
    starting_positions: tuple[Pose, ...]


@dataclass(frozen=True)
class PathSegment:
    """One segment of a planned path."""
    start: Pose
    end: Pose
    distance_mm: float
    estimated_time_s: float
    segment_type: str  # "drive" | "turn" | "strafe" | "spline"


@dataclass(frozen=True)
class PlannedPath:
    """A complete planned path with segments and timing."""
    segments: tuple[PathSegment, ...]
    total_distance_mm: float
    total_time_s: float
    waypoints: tuple[Pose, ...]


@dataclass(frozen=True)
class Action:
    """A single action in an autonomous routine."""
    name: str
    subsystem: str  # "drivetrain" | "arm" | "grabber" | "launcher"
    duration_s: float
    parameters: dict  # subsystem-specific params
    wait_for: str  # "" | "sensor_trigger" | "encoder_target" | "timer"
    parallel_with: str  # name of action that can run simultaneously, or ""


@dataclass(frozen=True)
class AutonomousRoutine:
    """A validated autonomous routine with timing and scoring estimate."""
    name: str
    competition: str  # "FTC" | "FRC"
    actions: tuple[Action, ...]
    total_time_s: float
    time_margin_s: float
    scoring_potential: int


@dataclass(frozen=True)
class SensorRecommendation:
    """A sensor recommendation for an autonomous task."""
    task: str
    sensor_type: str  # "distance_tof" | "color" | "imu" | "encoder" | "camera"
    sensor_name: str
    mounting_location: str
    rationale: str
