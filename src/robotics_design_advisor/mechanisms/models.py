"""Frozen dataclasses for mechanism physics calculations.

All models are immutable. Sequences use tuple, not list.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GrabberAnalysis:
    """Result of grabber/intake physics analysis."""

    required_grip_force_n: float
    required_torque_nmm: float
    recommended_servo: str
    jaw_opening_mm: float
    grip_type: str  # "claw" | "roller_intake" | "passive_funnel"
    hold_current_ma: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class LauncherAnalysis:
    """Result of launcher ballistics analysis."""

    launch_velocity_ms: float
    launch_angle_deg: float
    flywheel_rpm: float
    flywheel_diameter_mm: float
    motor_recommendation: str
    spin_up_time_s: float
    energy_per_shot_j: float
    fire_rate_hz: float
    catapult_spring_force_n: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class LiftAnalysis:
    """Result of lift/elevator/arm physics analysis."""

    required_force_n: float
    peak_force_n: float
    required_torque_nmm: float
    motor_recommendation: str
    gear_ratio: float
    max_speed_mm_s: float
    time_to_max_height_s: float
    counterbalance_force_n: float
    spool_diameter_mm: float
    lift_type: str  # "elevator" | "four_bar" | "arm" | "cascade"
    notes: tuple[str, ...]


@dataclass(frozen=True)
class MotionProfile:
    """Trapezoidal motion profile with encoder tick calculations."""

    total_ticks: int
    cruise_velocity_tps: float  # ticks per second
    accel_ticks: int
    decel_ticks: int
    cruise_ticks: int
    total_time_s: float
    accel_time_s: float
    suggested_kp: float
    suggested_ki: float
    suggested_kd: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class MotorMatch:
    """A motor matched to a specific torque+speed requirement."""

    motor_name: str
    motor_sku: str
    base_rpm: float
    stall_torque_nmm: float
    gear_ratio: float
    output_rpm: float
    output_torque_nmm: float
    torque_margin_pct: float
    current_draw_a: float
    notes: tuple[str, ...]
