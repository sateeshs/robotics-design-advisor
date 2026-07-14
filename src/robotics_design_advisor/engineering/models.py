"""Data models for engineering analysis.

All models are frozen dataclasses for immutability.
"""

from dataclasses import dataclass
from typing import Literal


CheckStatus = Literal["PASS", "FAIL", "WARNING"]
CheckSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
Competition = Literal["FTC", "FRC"]


@dataclass(frozen=True)
class MotorSpec:
    """Electrical and mechanical specs for a motor."""
    sku: str
    name: str
    gear_ratio: float
    free_speed_rpm: float
    stall_torque_kg_cm: float
    stall_current_a: float
    free_current_a: float
    encoder_ppr: float
    shaft_type: str
    weight_grams: float
    voltage_nominal: float = 12.0


@dataclass(frozen=True)
class HubSpec:
    """Port and power specs for a control hub."""
    name: str
    sku: str
    weight_grams: float
    motor_ports: int
    motor_current_continuous_a: float
    motor_current_max_a: float
    servo_ports: int
    servo_current_total_a: float
    encoder_ports: int
    i2c_buses: int
    digital_ports: int
    analog_ports: int
    has_imu: bool
    dimensions_mm: tuple[float, float, float] = (101.6, 63.5, 25.4)


@dataclass(frozen=True)
class DrivetrainAnalysis:
    """Result of drivetrain engineering analysis."""
    free_speed_m_s: float
    loaded_speed_m_s: float
    total_stall_current_a: float
    total_free_current_a: float
    total_motor_weight_grams: float
    recommended: bool
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArmAnalysis:
    """Result of arm/elevator torque analysis."""
    required_torque_kg_cm: float
    available_torque_kg_cm: float
    torque_margin_pct: float
    can_hold: bool
    max_load_at_length_kg: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PowerBudget:
    """Electrical power budget analysis."""
    total_motors: int
    total_stall_current_a: float
    total_free_current_a: float
    typical_current_a: float
    fuse_limit_a: float
    within_budget: bool
    hub_count_needed: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortAllocation:
    """Hub port assignment map."""
    assignments: tuple[tuple[str, str, str], ...]  # (hub, port, device)
    unassigned_devices: tuple[str, ...] = ()
    hub_count: int = 1
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CenterOfGravity:
    """Center of gravity calculation result."""
    x_mm: float
    y_mm: float
    z_mm: float
    total_mass_grams: float
    within_footprint: bool
    offset_from_center_mm: float


@dataclass(frozen=True)
class GearRatioResult:
    """Gear ratio recommendation."""
    motor_sku: str
    motor_ratio: float
    external_ratio: float
    total_ratio: float
    actual_speed_m_s: float
    current_at_speed_a: float
    within_spec: bool


@dataclass(frozen=True)
class WireGaugeResult:
    """Wire gauge adequacy check result."""
    awg: int
    voltage_drop_v: float
    drop_pct: float
    adequate: bool
    recommendation: str


@dataclass(frozen=True)
class SafetyCheck:
    """Result of a single safety/compliance check."""
    rule_id: str
    rule_name: str
    status: CheckStatus
    actual_value: str
    limit_value: str
    message: str
    severity: CheckSeverity


@dataclass(frozen=True)
class InspectionReport:
    """Complete pre-inspection compliance report."""
    competition: Competition
    season: str
    checks: tuple[SafetyCheck, ...]
    passed: bool
    critical_failures: int
    warnings: int
    recommendations: tuple[str, ...] = ()


DrivetrainType = Literal[
    "mecanum", "swerve", "differential", "H-drive",
]
IntakeType = Literal[
    "front_roller", "dual_side_intake", "over_body_intake", "claw_gripper",
]
ScorerType = Literal[
    "dual_flywheel", "single_flywheel_with_hood", "catapult", "elevator_placer",
]
MotorApplication = Literal[
    "drivetrain", "arm", "elevator", "intake", "shooter", "turret",
]


@dataclass(frozen=True)
class DrivetrainChoice:
    """Recommended drivetrain configuration."""
    drivetrain_type: DrivetrainType
    motor_count: int
    rationale: str
    pros: tuple[str, ...]
    cons: tuple[str, ...]
    recommended_motor_skus: tuple[str, ...]


@dataclass(frozen=True)
class IntakeChoice:
    """Recommended intake configuration."""
    intake_type: IntakeType
    motor_count: int
    servo_count: int
    rationale: str
    pros: tuple[str, ...]
    cons: tuple[str, ...]


@dataclass(frozen=True)
class ScorerChoice:
    """Recommended scoring mechanism configuration."""
    scorer_type: ScorerType
    motor_count: int
    servo_count: int
    rationale: str
    pros: tuple[str, ...]
    cons: tuple[str, ...]


@dataclass(frozen=True)
class MotorRecommendation:
    """A ranked motor suggestion for a specific application."""
    sku: str
    name: str
    gear_ratio: float
    suitability_score: float  # 0-100
    rationale: str


@dataclass(frozen=True)
class ElectronicsPlacement:
    """Suggested placement for an electronic component."""
    component: str
    position_mm: tuple[float, float, float]
    mounting_face: str
    orientation: str
    rationale: str
    wire_routes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ElectronicsLayout:
    """Complete electronics layout for a robot."""
    placements: tuple[ElectronicsPlacement, ...]
    total_weight_grams: float
    cg_shift_mm: tuple[float, float, float]
    port_allocation: PortAllocation
    compliance_issues: tuple[str, ...] = ()
