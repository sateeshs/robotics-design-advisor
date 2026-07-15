"""Tests for connection classifier — classifies holes into connection types."""

from __future__ import annotations

import pytest

from robotics_design_advisor.step.analyzer import FaceInfo, StepAnalysis
from robotics_design_advisor.step.hole_detector import (
    DetectedHole,
    DetectedPattern,
    HoleDetection,
)
from robotics_design_advisor.step.connection_classifier import (
    ClassificationResult,
    classify,
    _classify_pattern,
    _classify_single_hole,
    _infer_can_mate_with,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analysis(faces: tuple[FaceInfo, ...] = ()) -> StepAnalysis:
    return StepAnalysis(
        bounding_box=(48.0, 48.0, 288.0),
        volume_mm3=42500.0,
        center_of_mass=(24.0, 24.0, 144.0),
        faces=faces,
    )


def _make_pattern(
    *,
    diameter: float = 4.2,
    pitch_x: float = 8.0,
    pitch_y: float = 8.0,
    grid: tuple[int, int] = (6, 6),
    count: int = 36,
    face_ref: str = "face_0",
) -> DetectedPattern:
    return DetectedPattern(
        pattern_id="pattern_0",
        face_ref=face_ref,
        holes=(),
        hole_diameter_mm=diameter,
        pitch_x_mm=pitch_x,
        pitch_y_mm=pitch_y,
        grid=grid,
        count=count,
    )


def _make_hole(
    *,
    diameter: float = 8.0,
    center: tuple = (24, 24, 0),
    face_id: str = "face_0",
) -> DetectedHole:
    return DetectedHole(
        face_id=face_id,
        center=center,
        diameter_mm=diameter,
        depth_mm=0,
        hole_type="through",
    )


# ---------------------------------------------------------------------------
# Tests: pattern classification
# ---------------------------------------------------------------------------

class TestClassifyPattern:
    def test_gobilda_8mm_m4_pattern(self) -> None:
        """4.2mm holes at 8mm pitch → gobilda_8mm_pattern + M4_bolt."""
        pattern = _make_pattern(diameter=4.2, pitch_x=8.0, pitch_y=8.0)
        conn, tags = _classify_pattern(pattern)

        assert conn.connection_type == "bolt_hole_grid"
        assert "gobilda_8mm_pattern" in conn.compatible_with
        assert "M4_bolt" in conn.compatible_with

    def test_m4_non_gobilda_pitch(self) -> None:
        """4.2mm holes at non-8mm pitch → M4_bolt but not gobilda pattern."""
        pattern = _make_pattern(diameter=4.2, pitch_x=10.0, pitch_y=10.0)
        conn, tags = _classify_pattern(pattern)

        assert conn.connection_type == "bolt_hole_grid"
        assert "M4_bolt" in conn.compatible_with
        assert "gobilda_8mm_pattern" not in conn.compatible_with

    def test_m3_gobilda_pattern(self) -> None:
        """3.4mm holes at 8mm pitch → gobilda_8mm_pattern + M3_bolt."""
        pattern = _make_pattern(diameter=3.4, pitch_x=8.0, pitch_y=8.0)
        conn, tags = _classify_pattern(pattern)

        assert "gobilda_8mm_pattern" in conn.compatible_with
        assert "M3_bolt" in conn.compatible_with

    def test_pattern_face_ref(self) -> None:
        """Connection should reference the pattern's face and pattern ID."""
        pattern = _make_pattern(face_ref="face_top")
        conn, _ = _classify_pattern(pattern)
        assert conn.face_ref == "face_top"
        assert conn.pattern_ref == "pattern_0"


# ---------------------------------------------------------------------------
# Tests: single hole classification
# ---------------------------------------------------------------------------

class TestClassifySingleHole:
    def test_8mm_shaft_bore(self) -> None:
        """8mm hole → shaft_bore with REX_8mm_shaft."""
        hole = _make_hole(diameter=8.0)
        conn, tags = _classify_single_hole(hole)

        assert conn.connection_type == "shaft_bore"
        assert "REX_8mm_shaft" in conn.compatible_with

    def test_6mm_shaft_bore(self) -> None:
        """6mm hole → shaft_bore."""
        hole = _make_hole(diameter=6.0)
        conn, tags = _classify_single_hole(hole)

        assert conn.connection_type == "shaft_bore"
        assert "6mm_shaft" in conn.compatible_with

    def test_5mm_pin_hole(self) -> None:
        """5mm hole → pin_hole."""
        hole = _make_hole(diameter=5.0)
        conn, tags = _classify_single_hole(hole)

        assert conn.connection_type == "pin_hole"
        assert "5mm_pin" in conn.compatible_with

    def test_location_preserved(self) -> None:
        """Connection should preserve the hole's center location."""
        hole = _make_hole(center=(10, 20, 30))
        conn, _ = _classify_single_hole(hole)
        assert conn.location == (10, 20, 30)


# ---------------------------------------------------------------------------
# Tests: can_mate_with inference
# ---------------------------------------------------------------------------

class TestInferCanMateWith:
    def test_bolt_grid_mates(self) -> None:
        types = {"bolt_hole_grid"}
        mates = _infer_can_mate_with(types)
        assert "brackets" in mates
        assert "plates" in mates
        assert "channels" in mates

    def test_shaft_bore_mates(self) -> None:
        types = {"shaft_bore"}
        mates = _infer_can_mate_with(types)
        assert "shafts" in mates
        assert "hubs" in mates
        assert "wheels" in mates

    def test_motor_mount_mates(self) -> None:
        types = {"motor_mount_pattern"}
        mates = _infer_can_mate_with(types)
        assert "motors" in mates

    def test_combined(self) -> None:
        types = {"bolt_hole_grid", "shaft_bore"}
        mates = _infer_can_mate_with(types)
        assert "brackets" in mates
        assert "shafts" in mates


# ---------------------------------------------------------------------------
# Tests: classify (full pipeline)
# ---------------------------------------------------------------------------

class TestClassify:
    def test_with_pattern_and_hole(self) -> None:
        """Full classification with a pattern and an isolated hole."""
        pattern = _make_pattern(diameter=4.2, pitch_x=8.0, pitch_y=8.0)
        hole = _make_hole(diameter=8.0)

        detection = HoleDetection(
            holes=(hole,),
            patterns=(pattern,),
        )
        analysis = _make_analysis()
        result = classify(analysis, detection)

        assert isinstance(result, ClassificationResult)
        assert len(result.connection_points) >= 2
        assert "gobilda_8mm_pattern" in result.compatible_with
        assert "REX_8mm_shaft" in result.compatible_with
        assert len(result.can_mate_with) > 0

    def test_empty_detection(self) -> None:
        """No holes → empty result."""
        detection = HoleDetection(holes=(), patterns=())
        analysis = _make_analysis()
        result = classify(analysis, detection)

        assert len(result.connection_points) == 0
        assert len(result.compatible_with) == 0

    def test_result_frozen(self) -> None:
        result = ClassificationResult(
            connection_points=(),
            compatible_with=(),
            can_mate_with=(),
        )
        with pytest.raises(AttributeError):
            result.compatible_with = ()  # type: ignore[misc]
