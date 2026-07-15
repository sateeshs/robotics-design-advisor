"""Tests for STEP analyzer — core geometry extraction.

CadQuery objects are mocked so tests run without OCCT.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from robotics_design_advisor.step.analyzer import (
    FaceInfo,
    StepAnalysis,
    analyze,
    classify_face_type,
)


# ---------------------------------------------------------------------------
# Helpers: build mock CadQuery objects
# ---------------------------------------------------------------------------

def _mock_bounding_box(xlen: float, ylen: float, zlen: float) -> MagicMock:
    bb = MagicMock()
    bb.xlen = xlen
    bb.ylen = ylen
    bb.zlen = zlen
    return bb


def _mock_face(
    *,
    geom_type: str = "Plane",
    normal: tuple = (0.0, 1.0, 0.0),
    area: float = 100.0,
    center: tuple = (10.0, 20.0, 30.0),
) -> MagicMock:
    face = MagicMock()
    face.geomType.return_value = geom_type
    face.normalAt.return_value = MagicMock(x=normal[0], y=normal[1], z=normal[2])
    face.Area.return_value = area
    center_mock = MagicMock()
    center_mock.x = center[0]
    center_mock.y = center[1]
    center_mock.z = center[2]
    face.Center.return_value = center_mock
    return face


def _mock_shape(
    bb: MagicMock,
    volume: float,
    com: tuple,
    faces: list[MagicMock],
) -> MagicMock:
    shape = MagicMock()
    shape.val.return_value.BoundingBox.return_value = bb
    shape.val.return_value.Volume.return_value = volume
    com_mock = MagicMock()
    com_mock.x, com_mock.y, com_mock.z = com
    shape.val.return_value.Center.return_value = com_mock
    shape.faces.return_value.vals.return_value = faces
    return shape


# ---------------------------------------------------------------------------
# Tests: classify_face_type
# ---------------------------------------------------------------------------

class TestClassifyFaceType:
    def test_plane(self) -> None:
        assert classify_face_type("Plane") == "planar"

    def test_cylinder(self) -> None:
        assert classify_face_type("Cylinder") == "cylindrical"

    def test_cone(self) -> None:
        assert classify_face_type("Cone") == "conical"

    def test_sphere(self) -> None:
        assert classify_face_type("Sphere") == "other"

    def test_unknown(self) -> None:
        assert classify_face_type("BSplineSurface") == "other"


# ---------------------------------------------------------------------------
# Tests: FaceInfo immutability
# ---------------------------------------------------------------------------

class TestFaceInfo:
    def test_frozen(self) -> None:
        fi = FaceInfo(
            face_id="face_0",
            normal=(0.0, 1.0, 0.0),
            area_mm2=100.0,
            center=(10.0, 20.0, 30.0),
            face_type="planar",
            outer_wire_edge_count=4,
        )
        with pytest.raises(AttributeError):
            fi.face_id = "changed"  # type: ignore[misc]

    def test_fields(self) -> None:
        fi = FaceInfo(
            face_id="face_1",
            normal=(1.0, 0.0, 0.0),
            area_mm2=250.5,
            center=(5.0, 10.0, 15.0),
            face_type="cylindrical",
            outer_wire_edge_count=2,
        )
        assert fi.face_id == "face_1"
        assert fi.face_type == "cylindrical"
        assert fi.area_mm2 == 250.5


# ---------------------------------------------------------------------------
# Tests: StepAnalysis immutability
# ---------------------------------------------------------------------------

class TestStepAnalysis:
    def test_frozen(self) -> None:
        sa = StepAnalysis(
            bounding_box=(10.0, 20.0, 30.0),
            volume_mm3=5000.0,
            center_of_mass=(5.0, 10.0, 15.0),
            faces=(),
        )
        with pytest.raises(AttributeError):
            sa.volume_mm3 = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: analyze function
# ---------------------------------------------------------------------------

class TestAnalyze:
    @patch("robotics_design_advisor.step.analyzer.cq")
    def test_basic_analysis(self, mock_cq: MagicMock) -> None:
        """Verify analyze extracts bounding box, volume, COM, and faces."""
        faces = [
            _mock_face(geom_type="Plane", normal=(0, 1, 0), area=200.0, center=(5, 10, 15)),
            _mock_face(geom_type="Cylinder", normal=(0, 0, 1), area=50.0, center=(1, 2, 3)),
        ]
        bb = _mock_bounding_box(48.0, 48.0, 288.0)
        shape = _mock_shape(bb, volume=42500.0, com=(24.0, 24.0, 144.0), faces=faces)
        mock_cq.importers.importStep.return_value = shape

        result = analyze("/fake/path.STEP")

        assert isinstance(result, StepAnalysis)
        assert result.bounding_box == (48.0, 48.0, 288.0)
        assert result.volume_mm3 == 42500.0
        assert result.center_of_mass == (24.0, 24.0, 144.0)
        assert len(result.faces) == 2

    @patch("robotics_design_advisor.step.analyzer.cq")
    def test_face_extraction(self, mock_cq: MagicMock) -> None:
        """Verify face info is correctly extracted."""
        face = _mock_face(geom_type="Plane", normal=(0, -1, 0), area=13824.0, center=(24, 0, 144))
        bb = _mock_bounding_box(48.0, 48.0, 288.0)
        shape = _mock_shape(bb, volume=42500.0, com=(24, 24, 144), faces=[face])
        mock_cq.importers.importStep.return_value = shape

        result = analyze("/fake/path.STEP")

        fi = result.faces[0]
        assert fi.face_id == "face_0"
        assert fi.face_type == "planar"
        assert fi.normal == (0.0, -1.0, 0.0)
        assert fi.area_mm2 == 13824.0
        assert fi.center == (24.0, 0.0, 144.0)

    @patch("robotics_design_advisor.step.analyzer.cq")
    def test_cylindrical_face(self, mock_cq: MagicMock) -> None:
        """Cylindrical faces should have type 'cylindrical'."""
        face = _mock_face(geom_type="Cylinder", area=31.4, center=(10, 10, 5))
        bb = _mock_bounding_box(20, 20, 10)
        shape = _mock_shape(bb, volume=1000, com=(10, 10, 5), faces=[face])
        mock_cq.importers.importStep.return_value = shape

        result = analyze("/fake/path.STEP")
        assert result.faces[0].face_type == "cylindrical"

    @patch("robotics_design_advisor.step.analyzer.cq")
    def test_no_faces(self, mock_cq: MagicMock) -> None:
        """Shape with no faces should return empty faces tuple."""
        bb = _mock_bounding_box(10, 10, 10)
        shape = _mock_shape(bb, volume=1000, com=(5, 5, 5), faces=[])
        mock_cq.importers.importStep.return_value = shape

        result = analyze("/fake/path.STEP")
        assert result.faces == ()

    @patch("robotics_design_advisor.step.analyzer.cq")
    def test_returns_shape(self, mock_cq: MagicMock) -> None:
        """analyze should also return the loaded shape for downstream use."""
        bb = _mock_bounding_box(10, 10, 10)
        shape = _mock_shape(bb, volume=1000, com=(5, 5, 5), faces=[])
        mock_cq.importers.importStep.return_value = shape

        result, returned_shape = analyze("/fake/path.STEP", return_shape=True)
        assert returned_shape is shape
