"""Tests for field configuration and pose utilities."""

import math

import pytest

from robotics_design_advisor.autonomous.field import (
    FTC_AUTO_PERIOD_S,
    FRC_AUTO_PERIOD_S,
    angle_between,
    distance_between,
    find_zone,
    frc_field,
    ftc_field,
    is_in_zone,
)
from robotics_design_advisor.autonomous.models import FieldConfig, Pose, Zone


class TestFtcField:
    def test_dimensions(self):
        field = ftc_field("red")
        assert field.width_mm == 3658.0
        assert field.length_mm == 3658.0

    def test_alliance(self):
        assert ftc_field("red").alliance == "red"
        assert ftc_field("blue").alliance == "blue"

    def test_has_zones(self):
        field = ftc_field("red")
        assert len(field.zones) > 0

    def test_has_starting_positions(self):
        field = ftc_field("red")
        assert len(field.starting_positions) > 0

    def test_invalid_alliance_raises(self):
        with pytest.raises(ValueError, match="alliance"):
            ftc_field("green")


class TestFrcField:
    def test_dimensions(self):
        field = frc_field("red")
        assert field.width_mm == 16459.0
        assert field.length_mm == 8229.0

    def test_has_zones(self):
        field = frc_field("blue")
        assert len(field.zones) > 0

    def test_alliance(self):
        assert frc_field("red").alliance == "red"
        assert frc_field("blue").alliance == "blue"

    def test_invalid_alliance_raises(self):
        with pytest.raises(ValueError, match="alliance"):
            frc_field("green")


class TestDistanceBetween:
    def test_same_point(self):
        p = Pose(x_mm=100.0, y_mm=200.0, heading_deg=0.0)
        assert distance_between(p, p) == 0.0

    def test_horizontal(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        assert distance_between(a, b) == 1000.0

    def test_diagonal(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=3000.0, y_mm=4000.0, heading_deg=0.0)
        assert distance_between(a, b) == 5000.0  # 3-4-5 triangle


class TestAngleBetween:
    def test_east(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        assert abs(angle_between(a, b) - 0.0) < 0.1

    def test_north(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=0.0, y_mm=1000.0, heading_deg=0.0)
        assert abs(angle_between(a, b) - 90.0) < 0.1

    def test_west(self):
        a = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        assert abs(angle_between(a, b) - 180.0) < 0.1

    def test_same_point_returns_zero(self):
        p = Pose(x_mm=100.0, y_mm=200.0, heading_deg=0.0)
        assert angle_between(p, p) == 0.0


class TestFindZone:
    def test_finds_existing_zone(self):
        field = ftc_field("red")
        zone = find_zone(field, field.zones[0].name)
        assert zone is not None
        assert zone.name == field.zones[0].name

    def test_returns_none_for_missing(self):
        field = ftc_field("red")
        assert find_zone(field, "nonexistent_zone") is None


class TestIsInZone:
    def test_center_is_in_zone(self):
        center = Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0)
        zone = Zone(name="test", center=center, radius_mm=300.0, zone_type="scoring")
        assert is_in_zone(center, zone) is True

    def test_outside_radius(self):
        center = Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0)
        zone = Zone(name="test", center=center, radius_mm=300.0, zone_type="scoring")
        far = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        assert is_in_zone(far, zone) is False

    def test_on_boundary(self):
        center = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        zone = Zone(name="test", center=center, radius_mm=500.0, zone_type="scoring")
        edge = Pose(x_mm=500.0, y_mm=0.0, heading_deg=0.0)
        assert is_in_zone(edge, zone) is True
