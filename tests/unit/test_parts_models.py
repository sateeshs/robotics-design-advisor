"""Tests for part profile data models."""

import pytest

from robotics_design_advisor.parts.models import (
    BoundingBox,
    CatalogEntry,
    CategorySummary,
    ConnectionPoint,
    Geometry,
    HolePattern,
    MateSuggestion,
    MountingFace,
    PartProfile,
)


class TestBoundingBox:
    def test_create_with_defaults(self) -> None:
        bb = BoundingBox(x=48.0, y=48.0, z=288.0)
        assert bb.x == 48.0
        assert bb.y == 48.0
        assert bb.z == 288.0
        assert bb.unit == "mm"

    def test_immutable(self) -> None:
        bb = BoundingBox(x=10.0, y=20.0, z=30.0)
        with pytest.raises(AttributeError):
            bb.x = 99.0  # type: ignore[misc]


class TestGeometry:
    def test_create(self) -> None:
        geo = Geometry(
            bounding_box=BoundingBox(x=48.0, y=48.0, z=288.0),
            volume_cm3=42.5,
            mass_grams=115.0,
            center_of_mass=(24.0, 24.0, 144.0),
        )
        assert geo.volume_cm3 == 42.5
        assert geo.mass_grams == 115.0
        assert geo.center_of_mass == (24.0, 24.0, 144.0)


class TestHolePattern:
    def test_create(self) -> None:
        hp = HolePattern(
            pattern_id="pattern_0",
            face_ref="face_top",
            hole_diameter_mm=4.2,
            hole_type="through",
            pitch_x_mm=8.0,
            pitch_y_mm=8.0,
            grid=(6, 36),
            bolt_size="M4",
            count=216,
        )
        assert hp.pitch_x_mm == 8.0
        assert hp.bolt_size == "M4"
        assert hp.count == 216
        assert hp.grid == (6, 36)


class TestMountingFace:
    def test_defaults(self) -> None:
        mf = MountingFace(
            face_id="face_top",
            normal=(0.0, 1.0, 0.0),
            area_mm2=13824.0,
            center=(24.0, 48.0, 144.0),
        )
        assert mf.face_type == "planar"
        assert mf.has_holes is False
        assert mf.hole_pattern_ref == ""

    def test_with_holes(self) -> None:
        mf = MountingFace(
            face_id="face_top",
            normal=(0.0, 1.0, 0.0),
            area_mm2=13824.0,
            center=(24.0, 48.0, 144.0),
            has_holes=True,
            hole_pattern_ref="pattern_0",
        )
        assert mf.has_holes is True
        assert mf.hole_pattern_ref == "pattern_0"


class TestConnectionPoint:
    def test_bolt_hole_grid(self) -> None:
        cp = ConnectionPoint(
            connection_type="bolt_hole_grid",
            compatible_with=("M4_bolt", "gobilda_8mm_pattern"),
            face_ref="face_top",
            pattern_ref="pattern_0",
        )
        assert cp.connection_type == "bolt_hole_grid"
        assert "gobilda_8mm_pattern" in cp.compatible_with

    def test_shaft_bore(self) -> None:
        cp = ConnectionPoint(
            connection_type="shaft_bore",
            compatible_with=("REX_8mm_shaft",),
            diameter_mm=8.0,
            profile="D_bore",
            location=(24.0, 24.0, 0.0),
        )
        assert cp.diameter_mm == 8.0
        assert cp.profile == "D_bore"


class TestPartProfile:
    def test_full_profile(self) -> None:
        profile = PartProfile(
            sku="1120-0001-0288",
            name="U-Channel 288mm",
            category="structure/channel",
            source_file="channel/1120-0001-0288.step",
            geometry=Geometry(
                bounding_box=BoundingBox(x=48.0, y=48.0, z=288.0),
                volume_cm3=42.5,
                mass_grams=115.0,
                center_of_mass=(24.0, 24.0, 144.0),
            ),
            mounting_faces=(
                MountingFace(
                    face_id="face_top",
                    normal=(0.0, 1.0, 0.0),
                    area_mm2=13824.0,
                    center=(24.0, 48.0, 144.0),
                    has_holes=True,
                    hole_pattern_ref="pattern_0",
                ),
            ),
            hole_patterns=(
                HolePattern(
                    pattern_id="pattern_0",
                    face_ref="face_top",
                    hole_diameter_mm=4.2,
                    hole_type="through",
                    pitch_x_mm=8.0,
                    pitch_y_mm=8.0,
                    grid=(6, 36),
                    bolt_size="M4",
                    count=216,
                ),
            ),
            connection_points=(
                ConnectionPoint(
                    connection_type="bolt_hole_grid",
                    compatible_with=("M4_bolt", "gobilda_8mm_pattern"),
                    face_ref="face_top",
                    pattern_ref="pattern_0",
                ),
            ),
            compatible_with=("gobilda_8mm_pattern", "M4_socket_head"),
            can_mate_with=("brackets", "plates", "motors"),
        )
        assert profile.sku == "1120-0001-0288"
        assert profile.schema_version == 1
        assert len(profile.mounting_faces) == 1
        assert len(profile.hole_patterns) == 1
        assert len(profile.connection_points) == 1

    def test_immutable(self) -> None:
        profile = PartProfile(
            sku="1120-0001-0288",
            name="U-Channel",
            category="structure/channel",
            source_file="channel/1120-0001-0288.step",
            geometry=Geometry(
                bounding_box=BoundingBox(x=48.0, y=48.0, z=288.0),
                volume_cm3=42.5,
                mass_grams=115.0,
                center_of_mass=(24.0, 24.0, 144.0),
            ),
            mounting_faces=(),
            hole_patterns=(),
            connection_points=(),
            compatible_with=(),
            can_mate_with=(),
        )
        with pytest.raises(AttributeError):
            profile.sku = "9999"  # type: ignore[misc]


class TestCatalogEntry:
    def test_create(self) -> None:
        entry = CatalogEntry(
            sku="1120-0001-0288",
            name="U-Channel 288mm",
            category="structure/channel",
            bounding_box=BoundingBox(x=48.0, y=48.0, z=288.0),
            mass_grams=115.0,
            hole_count=216,
            bolt_size="M4",
            compatible_with=("gobilda_8mm_pattern",),
        )
        assert entry.sku == "1120-0001-0288"
        assert entry.mass_grams == 115.0


class TestCategorySummary:
    def test_create(self) -> None:
        cs = CategorySummary(
            category="structure/channel",
            part_count=35,
            description="U-channels and C-channels",
        )
        assert cs.part_count == 35

    def test_default_description(self) -> None:
        cs = CategorySummary(category="motion/motor", part_count=18)
        assert cs.description == ""


class TestMateSuggestion:
    def test_create(self) -> None:
        ms = MateSuggestion(
            mate_type="concentric",
            part_a_ref="shaft_bore_center",
            part_b_ref="shaft_bore",
            confidence=0.9,
            rationale="Both parts have matching 8mm D-bore shaft connections",
        )
        assert ms.mate_type == "concentric"
        assert ms.confidence == 0.9
        assert ms.value_mm == 0.0

    def test_distance_mate(self) -> None:
        ms = MateSuggestion(
            mate_type="distance",
            part_a_ref="face_end",
            part_b_ref="wheel_inner",
            confidence=0.7,
            rationale="Offset needed for wheel clearance",
            value_mm=5.0,
        )
        assert ms.value_mm == 5.0
