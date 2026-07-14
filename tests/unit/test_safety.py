"""Tests for safety and compliance inspection."""

import pytest

from robotics_design_advisor.engineering.models import InspectionReport, SafetyCheck
from robotics_design_advisor.engineering.safety import run_inspection


# ---------------------------------------------------------------------------
# FTC inspection
# ---------------------------------------------------------------------------

class TestFTCInspection:
    def test_returns_inspection_report(self) -> None:
        result = run_inspection(competition="FTC")
        assert isinstance(result, InspectionReport)

    def test_compliant_robot_passes(self) -> None:
        result = run_inspection(
            competition="FTC",
            width_mm=400.0, depth_mm=400.0, height_mm=400.0,
            weight_kg=10.0, dc_motor_count=4, servo_count=2,
            battery_count=1, has_main_switch=True,
            has_battery_retention=True, wires_secured=True,
        )
        assert result.passed
        assert result.critical_failures == 0

    def test_oversized_robot_fails(self) -> None:
        result = run_inspection(
            competition="FTC",
            width_mm=500.0, depth_mm=500.0, height_mm=500.0,
        )
        assert not result.passed
        assert result.critical_failures > 0
        failed_ids = [c.rule_id for c in result.checks if c.status == "FAIL"]
        assert any("FTC-R100" in rid for rid in failed_ids)

    def test_too_many_motors_fails(self) -> None:
        result = run_inspection(competition="FTC", dc_motor_count=10)
        assert not result.passed
        failed = [c for c in result.checks if c.status == "FAIL" and "motor" in c.rule_name.lower()]
        assert len(failed) > 0

    def test_too_many_servos_fails(self) -> None:
        result = run_inspection(competition="FTC", servo_count=14)
        assert not result.passed

    def test_overweight_fails(self) -> None:
        result = run_inspection(competition="FTC", weight_kg=25.0)
        assert not result.passed

    def test_no_main_switch_fails(self) -> None:
        result = run_inspection(competition="FTC", has_main_switch=False)
        assert not result.passed
        switch_checks = [c for c in result.checks if "switch" in c.rule_name.lower()]
        assert any(c.status == "FAIL" for c in switch_checks)

    def test_unsecured_battery_fails(self) -> None:
        result = run_inspection(competition="FTC", has_battery_retention=False)
        assert not result.passed

    def test_sharp_edges_fail(self) -> None:
        result = run_inspection(competition="FTC", has_sharp_edges=True)
        assert not result.passed

    def test_loose_wires_fail(self) -> None:
        result = run_inspection(competition="FTC", wires_secured=False)
        # Loose wires are HIGH severity (not CRITICAL), so robot may still "pass"
        # but should have warnings
        wire_checks = [c for c in result.checks if "wire" in c.rule_name.lower()]
        assert any(c.status == "FAIL" for c in wire_checks)

    def test_expanded_size_check(self) -> None:
        result = run_inspection(
            competition="FTC",
            width_mm=480.0, depth_mm=800.0, height_mm=400.0,
            expanded=True,
        )
        # 480 < 508 and 800 < 1066.8 → should pass expanded
        assert result.passed

    def test_expanded_too_wide_fails(self) -> None:
        result = run_inspection(
            competition="FTC",
            width_mm=600.0, depth_mm=800.0, height_mm=400.0,
            expanded=True,
        )
        assert not result.passed

    def test_weight_warning_near_limit(self) -> None:
        # 90% of 19.05 = 17.145
        result = run_inspection(competition="FTC", weight_kg=17.5)
        assert any("close to" in r for r in result.recommendations)


# ---------------------------------------------------------------------------
# FRC inspection
# ---------------------------------------------------------------------------

class TestFRCInspection:
    def test_returns_inspection_report(self) -> None:
        result = run_inspection(competition="FRC")
        assert isinstance(result, InspectionReport)

    def test_compliant_frc_robot_passes(self) -> None:
        result = run_inspection(
            competition="FRC",
            width_mm=700.0, depth_mm=700.0, height_mm=1000.0,
            weight_kg=50.0,
        )
        assert result.passed

    def test_perimeter_exceeds_limit(self) -> None:
        result = run_inspection(
            competition="FRC",
            frame_perimeter_mm=3200.0,
            height_mm=1000.0,
        )
        assert not result.passed

    def test_height_exceeds_limit(self) -> None:
        result = run_inspection(
            competition="FRC",
            width_mm=700.0, depth_mm=700.0,
            height_mm=1500.0,
        )
        assert not result.passed

    def test_frc_auto_perimeter_from_dimensions(self) -> None:
        # width=700, depth=700 → perimeter = 2800 < 3048
        result = run_inspection(
            competition="FRC",
            width_mm=700.0, depth_mm=700.0, height_mm=1000.0,
            weight_kg=50.0,
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Safety hazards (competition-agnostic)
# ---------------------------------------------------------------------------

class TestSafetyHazards:
    def test_entanglement_is_high_severity(self) -> None:
        result = run_inspection(competition="FTC", has_entanglement_risk=True)
        entangle = [c for c in result.checks if "entanglement" in c.rule_name.lower()]
        assert len(entangle) == 1
        assert entangle[0].severity == "HIGH"

    def test_pinch_points_are_warning(self) -> None:
        result = run_inspection(competition="FTC", has_pinch_points=True)
        pinch = [c for c in result.checks if "pinch" in c.rule_name.lower()]
        assert len(pinch) == 1
        assert pinch[0].status == "WARNING"

    def test_all_checks_have_required_fields(self) -> None:
        result = run_inspection(competition="FTC")
        for check in result.checks:
            assert check.rule_id
            assert check.rule_name
            assert check.status in ("PASS", "FAIL", "WARNING")
            assert check.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")

    def test_recommendations_on_failure(self) -> None:
        result = run_inspection(competition="FTC", width_mm=500.0)
        assert len(result.recommendations) > 0
        assert any("CRITICAL" in r for r in result.recommendations)
