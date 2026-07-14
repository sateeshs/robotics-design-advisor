"""Safety and compliance inspection checker.

Validates a robot design against FTC or FRC competition rules and
returns a structured inspection report.

Pure functions — no side effects, no I/O.
"""

from __future__ import annotations

from .constraints.frc import FRC_RULES, FRCConstraints
from .constraints.ftc import FTC_RULES, FTCConstraints
from .models import Competition, InspectionReport, SafetyCheck


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_size_ftc(
    width_mm: float,
    depth_mm: float,
    height_mm: float,
    expanded: bool = False,
    rules: FTCConstraints = FTC_RULES,
) -> list[SafetyCheck]:
    """Check robot dimensions against FTC size limits."""
    checks: list[SafetyCheck] = []

    if expanded:
        checks.append(SafetyCheck(
            rule_id="FTC-R101",
            rule_name="Expanded width limit",
            status="PASS" if width_mm <= rules.max_width_mm else "FAIL",
            actual_value=f"{width_mm:.1f}mm",
            limit_value=f"{rules.max_width_mm:.1f}mm",
            message=(
                f"Width {width_mm:.1f}mm {'within' if width_mm <= rules.max_width_mm else 'exceeds'} "
                f"{rules.max_width_mm:.1f}mm expanded limit"
            ),
            severity="CRITICAL",
        ))
        checks.append(SafetyCheck(
            rule_id="FTC-R102",
            rule_name="Expanded length limit",
            status="PASS" if depth_mm <= rules.max_length_mm else "FAIL",
            actual_value=f"{depth_mm:.1f}mm",
            limit_value=f"{rules.max_length_mm:.1f}mm",
            message=(
                f"Length {depth_mm:.1f}mm {'within' if depth_mm <= rules.max_length_mm else 'exceeds'} "
                f"{rules.max_length_mm:.1f}mm expanded limit"
            ),
            severity="CRITICAL",
        ))
    else:
        for dim_name, dim_val, limit in [
            ("Width", width_mm, rules.start_size_mm[0]),
            ("Depth", depth_mm, rules.start_size_mm[1]),
            ("Height", height_mm, rules.start_size_mm[2]),
        ]:
            checks.append(SafetyCheck(
                rule_id="FTC-R100",
                rule_name=f"Starting {dim_name.lower()} limit",
                status="PASS" if dim_val <= limit else "FAIL",
                actual_value=f"{dim_val:.1f}mm",
                limit_value=f"{limit:.1f}mm",
                message=(
                    f"{dim_name} {dim_val:.1f}mm {'within' if dim_val <= limit else 'exceeds'} "
                    f"{limit:.1f}mm starting limit"
                ),
                severity="CRITICAL",
            ))

    return checks


def _check_size_frc(
    frame_perimeter_mm: float,
    height_mm: float,
    rules: FRCConstraints = FRC_RULES,
) -> list[SafetyCheck]:
    """Check robot dimensions against FRC size limits."""
    return [
        SafetyCheck(
            rule_id="FRC-R201",
            rule_name="Frame perimeter limit",
            status="PASS" if frame_perimeter_mm <= rules.max_frame_perimeter_mm else "FAIL",
            actual_value=f"{frame_perimeter_mm:.1f}mm",
            limit_value=f"{rules.max_frame_perimeter_mm:.1f}mm",
            message=(
                f"Frame perimeter {frame_perimeter_mm:.1f}mm "
                f"{'within' if frame_perimeter_mm <= rules.max_frame_perimeter_mm else 'exceeds'} "
                f"{rules.max_frame_perimeter_mm:.1f}mm limit"
            ),
            severity="CRITICAL",
        ),
        SafetyCheck(
            rule_id="FRC-R202",
            rule_name="Height limit",
            status="PASS" if height_mm <= rules.max_height_mm else "FAIL",
            actual_value=f"{height_mm:.1f}mm",
            limit_value=f"{rules.max_height_mm:.1f}mm",
            message=(
                f"Height {height_mm:.1f}mm "
                f"{'within' if height_mm <= rules.max_height_mm else 'exceeds'} "
                f"{rules.max_height_mm:.1f}mm limit"
            ),
            severity="CRITICAL",
        ),
    ]


def _check_weight(
    weight_kg: float,
    competition: Competition,
) -> SafetyCheck:
    """Check robot weight against competition limit."""
    if competition == "FTC":
        limit = FTC_RULES.max_weight_kg
        rule_id = "FTC-W100"
    else:
        limit = FRC_RULES.max_weight_no_bumpers_kg
        rule_id = "FRC-W200"

    return SafetyCheck(
        rule_id=rule_id,
        rule_name="Weight limit",
        status="PASS" if weight_kg <= limit else "FAIL",
        actual_value=f"{weight_kg:.2f}kg",
        limit_value=f"{limit:.2f}kg",
        message=(
            f"Robot weight {weight_kg:.2f}kg "
            f"{'within' if weight_kg <= limit else 'exceeds'} "
            f"{limit:.2f}kg limit"
        ),
        severity="CRITICAL",
    )


def _check_motor_count(
    dc_motor_count: int,
    servo_count: int,
    competition: Competition,
) -> list[SafetyCheck]:
    """Check motor and servo counts."""
    checks: list[SafetyCheck] = []

    if competition == "FTC":
        checks.append(SafetyCheck(
            rule_id="FTC-M100",
            rule_name="DC motor limit",
            status="PASS" if dc_motor_count <= FTC_RULES.max_dc_motors else "FAIL",
            actual_value=str(dc_motor_count),
            limit_value=str(FTC_RULES.max_dc_motors),
            message=(
                f"{dc_motor_count} DC motors "
                f"{'within' if dc_motor_count <= FTC_RULES.max_dc_motors else 'exceeds'} "
                f"limit of {FTC_RULES.max_dc_motors}"
            ),
            severity="CRITICAL",
        ))
        checks.append(SafetyCheck(
            rule_id="FTC-M101",
            rule_name="Servo limit",
            status="PASS" if servo_count <= FTC_RULES.max_servos else "FAIL",
            actual_value=str(servo_count),
            limit_value=str(FTC_RULES.max_servos),
            message=(
                f"{servo_count} servos "
                f"{'within' if servo_count <= FTC_RULES.max_servos else 'exceeds'} "
                f"limit of {FTC_RULES.max_servos}"
            ),
            severity="CRITICAL",
        ))

    return checks


def _check_electrical(
    battery_count: int,
    has_main_switch: bool,
    has_battery_retention: bool,
    competition: Competition,
) -> list[SafetyCheck]:
    """Check electrical safety requirements."""
    checks: list[SafetyCheck] = []
    max_batteries = FTC_RULES.max_battery_count if competition == "FTC" else FRC_RULES.max_battery_count

    checks.append(SafetyCheck(
        rule_id=f"{competition}-E100",
        rule_name="Battery count",
        status="PASS" if battery_count <= max_batteries else "FAIL",
        actual_value=str(battery_count),
        limit_value=str(max_batteries),
        message=f"{battery_count} battery(ies) — limit is {max_batteries}",
        severity="CRITICAL",
    ))

    if competition == "FTC":
        checks.append(SafetyCheck(
            rule_id="FTC-E101",
            rule_name="Main power switch",
            status="PASS" if has_main_switch else "FAIL",
            actual_value="present" if has_main_switch else "missing",
            limit_value="required",
            message="Main power switch " + ("present" if has_main_switch else "MISSING — required for inspection"),
            severity="CRITICAL",
        ))

    checks.append(SafetyCheck(
        rule_id=f"{competition}-E102",
        rule_name="Battery retention",
        status="PASS" if has_battery_retention else "FAIL",
        actual_value="secured" if has_battery_retention else "unsecured",
        limit_value="required",
        message="Battery " + ("properly secured" if has_battery_retention else "NOT SECURED — inspection failure"),
        severity="CRITICAL",
    ))

    return checks


def _check_safety_hazards(
    has_sharp_edges: bool,
    has_entanglement_risk: bool,
    has_pinch_points: bool,
    wires_secured: bool,
) -> list[SafetyCheck]:
    """Check physical safety hazards."""
    checks: list[SafetyCheck] = []

    checks.append(SafetyCheck(
        rule_id="SAFETY-S100",
        rule_name="Sharp edges (paper test)",
        status="FAIL" if has_sharp_edges else "PASS",
        actual_value="present" if has_sharp_edges else "none",
        limit_value="none allowed",
        message=(
            "Sharp edges detected — must pass paper test (paper should not be cut)"
            if has_sharp_edges
            else "No sharp edges — passes paper test"
        ),
        severity="CRITICAL" if has_sharp_edges else "LOW",
    ))

    checks.append(SafetyCheck(
        rule_id="SAFETY-S101",
        rule_name="Entanglement hazards",
        status="FAIL" if has_entanglement_risk else "PASS",
        actual_value="present" if has_entanglement_risk else "none",
        limit_value="none allowed",
        message=(
            "Entanglement hazards found — exposed gears, chains, or strings"
            if has_entanglement_risk
            else "No entanglement hazards"
        ),
        severity="HIGH" if has_entanglement_risk else "LOW",
    ))

    checks.append(SafetyCheck(
        rule_id="SAFETY-S102",
        rule_name="Pinch points",
        status="WARNING" if has_pinch_points else "PASS",
        actual_value="present" if has_pinch_points else "none",
        limit_value="minimize",
        message=(
            "Pinch points found — consider adding guards"
            if has_pinch_points
            else "No pinch points"
        ),
        severity="MEDIUM" if has_pinch_points else "LOW",
    ))

    checks.append(SafetyCheck(
        rule_id="SAFETY-S103",
        rule_name="Wire management",
        status="PASS" if wires_secured else "FAIL",
        actual_value="secured" if wires_secured else "loose",
        limit_value="secured",
        message=(
            "All wires properly secured"
            if wires_secured
            else "Loose wires — must be zip-tied and routed safely"
        ),
        severity="HIGH" if not wires_secured else "LOW",
    ))

    return checks


# ---------------------------------------------------------------------------
# Full inspection
# ---------------------------------------------------------------------------

def run_inspection(
    competition: Competition = "FTC",
    season: str = "2025-2026",
    *,
    # Dimensions
    width_mm: float = 400.0,
    depth_mm: float = 400.0,
    height_mm: float = 400.0,
    expanded: bool = False,
    frame_perimeter_mm: float | None = None,
    # Weight
    weight_kg: float = 10.0,
    # Motors
    dc_motor_count: int = 4,
    servo_count: int = 2,
    # Electrical
    battery_count: int = 1,
    has_main_switch: bool = True,
    has_battery_retention: bool = True,
    # Safety
    has_sharp_edges: bool = False,
    has_entanglement_risk: bool = False,
    has_pinch_points: bool = False,
    wires_secured: bool = True,
) -> InspectionReport:
    """Run a complete pre-inspection compliance check.

    Parameters
    ----------
    competition : "FTC" or "FRC"
    season : season identifier
    All other parameters describe the robot's current state.
    """
    all_checks: list[SafetyCheck] = []

    # Size checks
    if competition == "FTC":
        all_checks.extend(
            _check_size_ftc(width_mm, depth_mm, height_mm, expanded=expanded)
        )
    else:
        perim = frame_perimeter_mm if frame_perimeter_mm is not None else 2 * (width_mm + depth_mm)
        all_checks.extend(_check_size_frc(perim, height_mm))

    # Weight
    all_checks.append(_check_weight(weight_kg, competition))

    # Motors
    all_checks.extend(_check_motor_count(dc_motor_count, servo_count, competition))

    # Electrical
    all_checks.extend(_check_electrical(
        battery_count, has_main_switch, has_battery_retention, competition,
    ))

    # Safety hazards
    all_checks.extend(_check_safety_hazards(
        has_sharp_edges, has_entanglement_risk, has_pinch_points, wires_secured,
    ))

    # Aggregate results
    critical_failures = sum(
        1 for c in all_checks if c.status == "FAIL" and c.severity == "CRITICAL"
    )
    warning_count = sum(
        1 for c in all_checks if c.status in ("WARNING", "FAIL") and c.severity != "CRITICAL"
    )
    passed = critical_failures == 0

    recommendations: list[str] = []
    if not passed:
        recommendations.append("Fix all CRITICAL failures before attending inspection")
    if warning_count > 0:
        recommendations.append("Review WARNING items — inspectors may flag these")
    if competition == "FTC" and weight_kg > FTC_RULES.max_weight_kg * 0.9:
        recommendations.append(
            f"Weight {weight_kg:.1f}kg is close to {FTC_RULES.max_weight_kg:.1f}kg limit — "
            "leave margin for field additions"
        )

    return InspectionReport(
        competition=competition,
        season=season,
        checks=tuple(all_checks),
        passed=passed,
        critical_failures=critical_failures,
        warnings=warning_count,
        recommendations=tuple(recommendations),
    )
