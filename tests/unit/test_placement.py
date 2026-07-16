"""Tests for approximate part placement within robot envelope."""

import pytest

from robotics_design_advisor.solidworks.placement import (
    SUBSYSTEM_ZONES,
    Position,
    calculate_position,
)


class TestPosition:
    def test_creation(self):
        p = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)
        assert p.x == 100.0
        assert p.z == 25.0

    def test_frozen(self):
        p = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)
        with pytest.raises(AttributeError):
            p.x = 1.0  # type: ignore[misc]


class TestSubsystemZones:
    def test_all_subsystems_defined(self):
        expected = {"drivetrain", "intake", "scorer", "endgame", "electronics"}
        assert set(SUBSYSTEM_ZONES.keys()) == expected

    def test_zones_within_robot_envelope(self):
        # FTC robot envelope: 457 x 457 x 457 mm
        for name, (min_corner, max_corner) in SUBSYSTEM_ZONES.items():
            assert min_corner[0] >= 0, f"{name} x_min below 0"
            assert min_corner[1] >= 0, f"{name} y_min below 0"
            assert min_corner[2] >= 0, f"{name} z_min below 0"
            assert max_corner[0] <= 457, f"{name} x_max exceeds 457"
            assert max_corner[1] <= 457, f"{name} y_max exceeds 457"
            assert max_corner[2] <= 457, f"{name} z_max exceeds 457"

    def test_zones_have_positive_volume(self):
        for name, (min_corner, max_corner) in SUBSYSTEM_ZONES.items():
            for i in range(3):
                assert max_corner[i] > min_corner[i], f"{name} axis {i} has zero volume"


class TestCalculatePosition:
    def test_single_part(self):
        pos = calculate_position("drivetrain", 0, 1)
        assert isinstance(pos, Position)
        zone_min, zone_max = SUBSYSTEM_ZONES["drivetrain"]
        assert zone_min[0] <= pos.x <= zone_max[0]
        assert zone_min[1] <= pos.y <= zone_max[1]
        assert zone_min[2] <= pos.z <= zone_max[2]

    def test_multiple_parts_distributed(self):
        positions = [calculate_position("intake", i, 4) for i in range(4)]
        # All positions should be distinct
        coords = [(p.x, p.y, p.z) for p in positions]
        assert len(set(coords)) == 4

    def test_parts_within_zone(self):
        for subsystem in SUBSYSTEM_ZONES:
            for i in range(3):
                pos = calculate_position(subsystem, i, 3)
                zone_min, zone_max = SUBSYSTEM_ZONES[subsystem]
                assert zone_min[0] <= pos.x <= zone_max[0], f"{subsystem}[{i}] x out of zone"
                assert zone_min[1] <= pos.y <= zone_max[1], f"{subsystem}[{i}] y out of zone"
                assert zone_min[2] <= pos.z <= zone_max[2], f"{subsystem}[{i}] z out of zone"

    def test_invalid_subsystem_raises(self):
        with pytest.raises(ValueError, match="subsystem"):
            calculate_position("nonexistent", 0, 1)

    def test_invalid_index_raises(self):
        with pytest.raises(ValueError, match="part_index"):
            calculate_position("drivetrain", -1, 1)

    def test_invalid_count_raises(self):
        with pytest.raises(ValueError, match="part_count"):
            calculate_position("drivetrain", 0, 0)

    def test_index_exceeds_count_raises(self):
        with pytest.raises(ValueError, match="part_index"):
            calculate_position("drivetrain", 5, 3)

    def test_default_rotation_is_zero(self):
        pos = calculate_position("electronics", 0, 1)
        assert pos.rx == 0.0
        assert pos.ry == 0.0
        assert pos.rz == 0.0
