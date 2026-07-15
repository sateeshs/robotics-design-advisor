"""Tests for hole detector — cylindrical hole detection and pattern clustering.

All CadQuery geometry is mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotics_design_advisor.step.analyzer import FaceInfo, StepAnalysis
from robotics_design_advisor.step.hole_detector import (
    DetectedHole,
    DetectedPattern,
    HoleDetection,
    detect,
    _cluster_into_pattern,
    _map_bolt_size,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analysis(faces: list[FaceInfo]) -> StepAnalysis:
    return StepAnalysis(
        bounding_box=(48.0, 48.0, 288.0),
        volume_mm3=42500.0,
        center_of_mass=(24.0, 24.0, 144.0),
        faces=tuple(faces),
    )


def _planar_face(
    face_id: str = "face_0",
    normal: tuple = (0, 1, 0),
    area: float = 1000.0,
    center: tuple = (24, 48, 144),
) -> FaceInfo:
    return FaceInfo(
        face_id=face_id,
        normal=normal,
        area_mm2=area,
        center=center,
        face_type="planar",
        outer_wire_edge_count=4,
    )


def _cylindrical_face(
    face_id: str = "face_1",
    center: tuple = (10, 48, 10),
    area: float = 26.4,  # pi * 4.2 * 2 (for M4 through 2mm plate)
) -> FaceInfo:
    return FaceInfo(
        face_id=face_id,
        normal=(0, 0, 1),  # axis direction
        area_mm2=area,
        center=center,
        face_type="cylindrical",
        outer_wire_edge_count=2,
    )


def _mock_shape_with_cylinders(
    cylinders: list[dict],
) -> MagicMock:
    """Build a mock CadQuery shape with cylindrical faces.

    Each cylinder dict: {radius_mm, center, length_mm}
    """
    shape = MagicMock()
    cq_faces = []

    for cyl in cylinders:
        face = MagicMock()
        face.geomType.return_value = "Cylinder"

        # Radius via the underlying geometry adapter
        geom = MagicMock()
        geom.Radius.return_value = cyl["radius_mm"]
        face.geomType.return_value = "Cylinder"
        face._geomAdaptor = MagicMock(return_value=geom)

        center_pt = MagicMock()
        center_pt.x, center_pt.y, center_pt.z = cyl["center"]
        face.Center.return_value = center_pt

        face.Area.return_value = (
            2 * 3.14159 * cyl["radius_mm"] * cyl.get("length_mm", 2.0)
        )

        cq_faces.append(face)

    shape.faces.return_value.vals.return_value = cq_faces
    return shape


# ---------------------------------------------------------------------------
# Tests: bolt size mapping
# ---------------------------------------------------------------------------

class TestBoltSizeMapping:
    def test_m4_hole(self) -> None:
        assert _map_bolt_size(4.2) == "M4"

    def test_m3_hole(self) -> None:
        assert _map_bolt_size(3.4) == "M3"

    def test_m25_hole(self) -> None:
        assert _map_bolt_size(2.6) == "M2.5"

    def test_m5_hole(self) -> None:
        assert _map_bolt_size(5.3) == "M5"

    def test_unknown_size(self) -> None:
        assert _map_bolt_size(7.0) == ""

    def test_exact_boundary_m4_low(self) -> None:
        assert _map_bolt_size(4.0) == "M4"

    def test_exact_boundary_m4_high(self) -> None:
        assert _map_bolt_size(4.3) == "M4"


# ---------------------------------------------------------------------------
# Tests: DetectedHole immutability
# ---------------------------------------------------------------------------

class TestDetectedHole:
    def test_frozen(self) -> None:
        h = DetectedHole(
            face_id="face_0",
            center=(10, 20, 30),
            diameter_mm=4.2,
            depth_mm=0,
            hole_type="through",
        )
        with pytest.raises(AttributeError):
            h.diameter_mm = 5.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: pattern clustering
# ---------------------------------------------------------------------------

class TestClusterIntoPattern:
    def test_4x4_grid_8mm_pitch(self) -> None:
        """Regular 4x4 grid with 8mm pitch should be detected."""
        holes = []
        for row in range(4):
            for col in range(4):
                holes.append(DetectedHole(
                    face_id="face_0",
                    center=(col * 8.0, 0.0, row * 8.0),
                    diameter_mm=4.2,
                    depth_mm=0,
                    hole_type="through",
                ))

        patterns = _cluster_into_pattern(holes, face_normal=(0, 1, 0))
        assert len(patterns) == 1
        p = patterns[0]
        assert p.count == 16
        assert abs(p.pitch_x_mm - 8.0) < 0.5
        assert abs(p.pitch_y_mm - 8.0) < 0.5
        assert p.grid == (4, 4)
        assert p.hole_diameter_mm == 4.2

    def test_single_row(self) -> None:
        """A single row of 6 holes should still detect pattern."""
        holes = [
            DetectedHole(
                face_id="face_0",
                center=(i * 8.0, 0.0, 0.0),
                diameter_mm=4.2,
                depth_mm=0,
                hole_type="through",
            )
            for i in range(6)
        ]
        patterns = _cluster_into_pattern(holes, face_normal=(0, 1, 0))
        assert len(patterns) == 1
        assert patterns[0].count == 6
        assert patterns[0].grid[0] == 6 or patterns[0].grid[1] == 6

    def test_too_few_holes(self) -> None:
        """Fewer than 4 holes should not form a pattern."""
        holes = [
            DetectedHole(
                face_id="face_0",
                center=(i * 8.0, 0.0, 0.0),
                diameter_mm=4.2,
                depth_mm=0,
                hole_type="through",
            )
            for i in range(3)
        ]
        patterns = _cluster_into_pattern(holes, face_normal=(0, 1, 0))
        assert len(patterns) == 0

    def test_irregular_spacing(self) -> None:
        """Holes with irregular spacing should not form a pattern."""
        holes = [
            DetectedHole(face_id="face_0", center=(0, 0, 0), diameter_mm=4.2, depth_mm=0, hole_type="through"),
            DetectedHole(face_id="face_0", center=(8, 0, 0), diameter_mm=4.2, depth_mm=0, hole_type="through"),
            DetectedHole(face_id="face_0", center=(20, 0, 0), diameter_mm=4.2, depth_mm=0, hole_type="through"),
            DetectedHole(face_id="face_0", center=(35, 0, 0), diameter_mm=4.2, depth_mm=0, hole_type="through"),
        ]
        patterns = _cluster_into_pattern(holes, face_normal=(0, 1, 0))
        assert len(patterns) == 0


# ---------------------------------------------------------------------------
# Tests: detect function
# ---------------------------------------------------------------------------

class TestDetect:
    def test_no_cylindrical_faces(self) -> None:
        """Shape with only planar faces should have no holes."""
        analysis = _make_analysis([_planar_face()])
        shape = MagicMock()
        shape.faces.return_value.vals.return_value = []

        result = detect(analysis, shape)

        assert isinstance(result, HoleDetection)
        assert len(result.holes) == 0
        assert len(result.patterns) == 0

    def test_detection_returns_frozen(self) -> None:
        """HoleDetection should be frozen."""
        result = HoleDetection(holes=(), patterns=())
        with pytest.raises(AttributeError):
            result.holes = ()  # type: ignore[misc]
