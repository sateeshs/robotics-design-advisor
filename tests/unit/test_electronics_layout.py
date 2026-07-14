"""Tests for electronics layout engine."""

import pytest

from robotics_design_advisor.engineering.electrical import load_hub_spec
from robotics_design_advisor.engineering.electronics_layout import (
    DEFAULT_FOOTPRINT_MM,
    MIN_EMI_SEPARATION_MM,
    check_wire_clearances,
    generate_electronics_layout,
)
from robotics_design_advisor.engineering.models import (
    ElectronicsLayout,
    ElectronicsPlacement,
)


# ---------------------------------------------------------------------------
# Layout generation
# ---------------------------------------------------------------------------

class TestGenerateElectronicsLayout:
    def test_returns_electronics_layout(self) -> None:
        result = generate_electronics_layout()
        assert isinstance(result, ElectronicsLayout)

    def test_always_places_hub_battery_switch(self) -> None:
        result = generate_electronics_layout()
        components = {p.component for p in result.placements}
        assert "control_hub" in components
        assert "battery" in components
        assert "main_switch" in components

    def test_no_expansion_hub_with_few_motors(self) -> None:
        motors = [("fl", "drive"), ("fr", "drive")]
        result = generate_electronics_layout(motor_assignments=motors)
        components = {p.component for p in result.placements}
        assert "expansion_hub" not in components

    def test_adds_expansion_hub_when_needed(self) -> None:
        motors = [(f"m{i}", "drive") for i in range(5)]
        result = generate_electronics_layout(motor_assignments=motors)
        components = {p.component for p in result.placements}
        assert "expansion_hub" in components

    def test_total_weight_includes_hub_and_battery(self) -> None:
        result = generate_electronics_layout()
        # At minimum: control_hub (230) + battery (530) + switch (30) = 790
        assert result.total_weight_grams >= 790

    def test_weight_increases_with_expansion_hub(self) -> None:
        few = generate_electronics_layout(motor_assignments=[("m0", "d")])
        many = generate_electronics_layout(
            motor_assignments=[(f"m{i}", "d") for i in range(5)]
        )
        assert many.total_weight_grams > few.total_weight_grams

    def test_cg_shift_is_tuple_of_three(self) -> None:
        result = generate_electronics_layout()
        assert len(result.cg_shift_mm) == 3

    def test_port_allocation_included(self) -> None:
        motors = [("fl", "front_left"), ("fr", "front_right")]
        servos = [("claw", "grip")]
        result = generate_electronics_layout(
            motor_assignments=motors, servo_assignments=servos,
        )
        assert len(result.port_allocation.assignments) == 3

    def test_uses_provided_hub_spec(self) -> None:
        hub = load_hub_spec("hub_data/rev_control_hub.json")
        result = generate_electronics_layout(hub=hub)
        assert result.total_weight_grams >= hub.weight_grams

    def test_existing_components_affect_cg(self) -> None:
        # Heavy mass at corner should shift CG
        heavy_corner = [(0.0, 0.0, 0.0, 5000.0)]
        result = generate_electronics_layout(existing_components=heavy_corner)
        # CG should be shifted toward (0,0,0) corner
        assert result.cg_shift_mm[0] < 0  # left of center

    def test_compliance_issues_when_cg_outside(self) -> None:
        # Extreme off-center mass
        extreme = [(0.0, 0.0, 0.0, 50000.0)]
        result = generate_electronics_layout(
            existing_components=extreme,
            footprint_mm=(457.0, 457.0),
        )
        assert len(result.compliance_issues) > 0


# ---------------------------------------------------------------------------
# Placement details
# ---------------------------------------------------------------------------

class TestPlacementDetails:
    def test_hub_ports_face_up(self) -> None:
        result = generate_electronics_layout()
        hub = next(p for p in result.placements if p.component == "control_hub")
        assert hub.orientation == "ports_facing_up"

    def test_hub_centered_on_footprint(self) -> None:
        fp = (457.0, 457.0)
        result = generate_electronics_layout(footprint_mm=fp)
        hub = next(p for p in result.placements if p.component == "control_hub")
        center_x = fp[0] / 2.0
        center_z = fp[1] / 2.0
        assert abs(hub.position_mm[0] - center_x) < 1.0
        assert abs(hub.position_mm[2] - center_z) < 1.0

    def test_battery_low_mounted(self) -> None:
        result = generate_electronics_layout()
        batt = next(p for p in result.placements if p.component == "battery")
        assert batt.position_mm[1] < 50.0  # Y is height, should be low

    def test_battery_has_retention_warning(self) -> None:
        result = generate_electronics_layout()
        batt = next(p for p in result.placements if p.component == "battery")
        assert any("secured" in w.lower() for w in batt.warnings)

    def test_switch_on_side(self) -> None:
        result = generate_electronics_layout()
        sw = next(p for p in result.placements if p.component == "main_switch")
        assert sw.mounting_face == "side_panel"

    def test_all_placements_have_rationale(self) -> None:
        result = generate_electronics_layout()
        for p in result.placements:
            assert p.rationale, f"{p.component} missing rationale"

    def test_all_placements_have_wire_routes(self) -> None:
        result = generate_electronics_layout()
        for p in result.placements:
            assert len(p.wire_routes) > 0, f"{p.component} missing wire routes"


# ---------------------------------------------------------------------------
# Wire clearances
# ---------------------------------------------------------------------------

class TestCheckWireClearances:
    def test_no_warnings_for_default_layout(self) -> None:
        result = generate_electronics_layout()
        warnings = check_wire_clearances(result.placements)
        # Default layout should have adequate spacing
        assert warnings == []

    def test_warns_when_components_too_close(self) -> None:
        # Place hub and sensor at same spot
        close_placements = [
            ElectronicsPlacement(
                component="control_hub",
                position_mm=(100.0, 10.0, 100.0),
                mounting_face="baseplate",
                orientation="ports_up",
                rationale="test",
            ),
            ElectronicsPlacement(
                component="sensor_module",
                position_mm=(105.0, 10.0, 100.0),  # only 5mm away
                mounting_face="baseplate",
                orientation="flat",
                rationale="test",
            ),
        ]
        warnings = check_wire_clearances(close_placements)
        assert len(warnings) > 0
        assert any("separation" in w for w in warnings)

    def test_no_warning_between_two_hubs(self) -> None:
        # Hub-to-hub proximity is fine (they're daisy-chained)
        hub_placements = [
            ElectronicsPlacement(
                component="control_hub",
                position_mm=(100.0, 10.0, 100.0),
                mounting_face="baseplate",
                orientation="ports_up",
                rationale="test",
            ),
            ElectronicsPlacement(
                component="expansion_hub",
                position_mm=(105.0, 10.0, 100.0),
                mounting_face="baseplate",
                orientation="ports_up",
                rationale="test",
            ),
        ]
        warnings = check_wire_clearances(hub_placements)
        assert len(warnings) == 0
