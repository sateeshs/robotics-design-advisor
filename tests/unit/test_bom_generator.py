"""Tests for bill of materials generation."""

import pytest

from robotics_design_advisor.engineering.bom_generator import generate_bom
from robotics_design_advisor.engineering.models import BillOfMaterials, BOMItem


class TestGenerateBom:
    def test_returns_bill_of_materials(self):
        bom = generate_bom(
            archetype_name="Speed Shooter",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=True,
            constraints={},
        )
        assert isinstance(bom, BillOfMaterials)

    def test_includes_motors(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=0,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        motor_items = [i for i in bom.items if "motor" in i.name.lower() or "motor" in i.category.lower()]
        total_motors = sum(i.quantity for i in motor_items)
        assert total_motors >= 4

    def test_includes_servos(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=3,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        servo_items = [i for i in bom.items if "servo" in i.name.lower()]
        total_servos = sum(i.quantity for i in servo_items)
        assert total_servos >= 3

    def test_includes_control_hub(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=0,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        hub_items = [i for i in bom.items if "hub" in i.name.lower() or "hub" in i.category.lower()]
        assert len(hub_items) >= 1

    def test_lift_adds_linear_slide(self):
        bom_with = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=1,
            has_lift=True,
            has_launcher=False,
            constraints={},
        )
        bom_without = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=1,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        assert len(bom_with.items) > len(bom_without.items)

    def test_total_cost_positive(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        assert bom.total_cost_usd > 0

    def test_total_cost_matches_items(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        expected = sum(i.unit_price_usd * i.quantity for i in bom.items)
        assert abs(bom.total_cost_usd - expected) < 0.01

    def test_warns_on_motor_limit(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=10,
            servo_count=0,
            has_lift=False,
            has_launcher=False,
            constraints={"max_motors": 8},
        )
        assert any("motor" in w.lower() for w in bom.warnings)

    def test_warns_on_weight_limit(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=8,
            servo_count=12,
            has_lift=True,
            has_launcher=True,
            constraints={"weight_limit_g": 100},
        )
        assert any("weight" in w.lower() for w in bom.warnings)

    def test_subsystem_breakdown_present(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        assert len(bom.subsystem_breakdown) > 0

    def test_all_items_have_sku(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=True,
            has_launcher=True,
            constraints={},
        )
        for item in bom.items:
            assert item.sku != ""
            assert item.name != ""
            assert item.quantity > 0
            assert item.unit_price_usd >= 0
