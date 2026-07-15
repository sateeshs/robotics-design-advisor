"""Tests for profile builder — orchestrates analysis and writes JSON profiles."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from robotics_design_advisor.step.analyzer import FaceInfo, StepAnalysis
from robotics_design_advisor.step.hole_detector import (
    DetectedHole,
    DetectedPattern,
    HoleDetection,
)
from robotics_design_advisor.step.connection_classifier import (
    ClassificationResult,
    ConnectionInfo,
)
from robotics_design_advisor.step.profile_builder import (
    build_profile,
    write_profile,
    ALUMINUM_DENSITY_G_CM3,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_analysis() -> StepAnalysis:
    return StepAnalysis(
        bounding_box=(48.0, 48.0, 288.0),
        volume_mm3=42500.0,
        center_of_mass=(24.0, 24.0, 144.0),
        faces=(
            FaceInfo(
                face_id="face_0",
                normal=(0.0, 1.0, 0.0),
                area_mm2=13824.0,
                center=(24.0, 48.0, 144.0),
                face_type="planar",
                outer_wire_edge_count=4,
            ),
        ),
    )


@pytest.fixture
def mock_detection() -> HoleDetection:
    return HoleDetection(
        holes=(
            DetectedHole(
                face_id="face_0",
                center=(8, 48, 8),
                diameter_mm=4.2,
                depth_mm=0,
                hole_type="through",
            ),
        ),
        patterns=(
            DetectedPattern(
                pattern_id="pattern_0",
                face_ref="face_0",
                holes=(),
                hole_diameter_mm=4.2,
                pitch_x_mm=8.0,
                pitch_y_mm=8.0,
                grid=(6, 36),
                count=216,
            ),
        ),
    )


@pytest.fixture
def mock_classification() -> ClassificationResult:
    return ClassificationResult(
        connection_points=(
            ConnectionInfo(
                connection_type="bolt_hole_grid",
                compatible_with=("M4_bolt", "gobilda_8mm_pattern"),
                face_ref="face_0",
                pattern_ref="pattern_0",
                diameter_mm=4.2,
            ),
        ),
        compatible_with=("M4_bolt", "gobilda_8mm_pattern"),
        can_mate_with=("brackets", "channels", "plates"),
    )


# ---------------------------------------------------------------------------
# Tests: build_profile
# ---------------------------------------------------------------------------

class TestBuildProfile:
    @patch("robotics_design_advisor.step.profile_builder.classify")
    @patch("robotics_design_advisor.step.profile_builder.detect")
    @patch("robotics_design_advisor.step.profile_builder.analyze")
    def test_produces_valid_profile(
        self,
        mock_analyze: MagicMock,
        mock_detect: MagicMock,
        mock_classify: MagicMock,
        mock_analysis: StepAnalysis,
        mock_detection: HoleDetection,
        mock_classification: ClassificationResult,
    ) -> None:
        shape = MagicMock()
        mock_analyze.return_value = (mock_analysis, shape)
        mock_detect.return_value = mock_detection
        mock_classify.return_value = mock_classification

        profile = build_profile(
            step_path="/fake/1120-0001-0288.STEP",
            sku="1120-0001-0288",
            name="U-Channel 288mm",
            category="structure/channel",
        )

        assert profile["sku"] == "1120-0001-0288"
        assert profile["name"] == "U-Channel 288mm"
        assert profile["category"] == "structure/channel"
        assert profile["source_file"] == "structure/channel/1120-0001-0288.STEP"
        assert profile["schema_version"] == 1

    @patch("robotics_design_advisor.step.profile_builder.classify")
    @patch("robotics_design_advisor.step.profile_builder.detect")
    @patch("robotics_design_advisor.step.profile_builder.analyze")
    def test_geometry_conversion(
        self,
        mock_analyze: MagicMock,
        mock_detect: MagicMock,
        mock_classify: MagicMock,
        mock_analysis: StepAnalysis,
        mock_detection: HoleDetection,
        mock_classification: ClassificationResult,
    ) -> None:
        shape = MagicMock()
        mock_analyze.return_value = (mock_analysis, shape)
        mock_detect.return_value = mock_detection
        mock_classify.return_value = mock_classification

        profile = build_profile(
            step_path="/fake/path.STEP",
            sku="1120-0001-0288",
            name="U-Channel",
            category="structure/channel",
        )

        geo = profile["geometry"]
        assert geo["bounding_box"]["x"] == 48.0
        assert geo["bounding_box"]["y"] == 48.0
        assert geo["bounding_box"]["z"] == 288.0
        assert geo["bounding_box"]["unit"] == "mm"

        # Volume: 42500 mm³ = 42.5 cm³
        assert abs(geo["volume_cm3"] - 42.5) < 0.1

        # Mass: 42.5 cm³ × 2.7 g/cm³ = 114.75 g
        expected_mass = 42.5 * ALUMINUM_DENSITY_G_CM3
        assert abs(geo["mass_grams"] - expected_mass) < 1.0

    @patch("robotics_design_advisor.step.profile_builder.classify")
    @patch("robotics_design_advisor.step.profile_builder.detect")
    @patch("robotics_design_advisor.step.profile_builder.analyze")
    def test_mounting_faces(
        self,
        mock_analyze: MagicMock,
        mock_detect: MagicMock,
        mock_classify: MagicMock,
        mock_analysis: StepAnalysis,
        mock_detection: HoleDetection,
        mock_classification: ClassificationResult,
    ) -> None:
        shape = MagicMock()
        mock_analyze.return_value = (mock_analysis, shape)
        mock_detect.return_value = mock_detection
        mock_classify.return_value = mock_classification

        profile = build_profile(
            step_path="/fake/path.STEP",
            sku="1120-0001-0288",
            name="U-Channel",
            category="structure/channel",
        )

        # face_0 has a pattern → should become a mounting face
        mf = profile["mounting_faces"]
        assert len(mf) >= 1
        assert mf[0]["face_id"] == "face_0"
        assert mf[0]["has_holes"] is True
        assert mf[0]["hole_pattern_ref"] == "pattern_0"

    @patch("robotics_design_advisor.step.profile_builder.classify")
    @patch("robotics_design_advisor.step.profile_builder.detect")
    @patch("robotics_design_advisor.step.profile_builder.analyze")
    def test_hole_patterns(
        self,
        mock_analyze: MagicMock,
        mock_detect: MagicMock,
        mock_classify: MagicMock,
        mock_analysis: StepAnalysis,
        mock_detection: HoleDetection,
        mock_classification: ClassificationResult,
    ) -> None:
        shape = MagicMock()
        mock_analyze.return_value = (mock_analysis, shape)
        mock_detect.return_value = mock_detection
        mock_classify.return_value = mock_classification

        profile = build_profile(
            step_path="/fake/path.STEP",
            sku="test",
            name="Test",
            category="test",
        )

        hp = profile["hole_patterns"]
        assert len(hp) == 1
        assert hp[0]["pattern_id"] == "pattern_0"
        assert hp[0]["hole_diameter_mm"] == 4.2
        assert hp[0]["pitch_x_mm"] == 8.0
        assert hp[0]["bolt_size"] == "M4"
        assert hp[0]["count"] == 216


# ---------------------------------------------------------------------------
# Tests: write_profile
# ---------------------------------------------------------------------------

class TestWriteProfile:
    def test_writes_json(self, tmp_path: Path) -> None:
        profile = {
            "sku": "1101-0001-0008",
            "name": "U-Beam 8mm",
            "category": "structure/beam",
        }
        output_dir = tmp_path / "profiles"
        write_profile(profile, str(output_dir))

        expected = output_dir / "structure" / "beam" / "1101-0001-0008.json"
        assert expected.exists()

        data = json.loads(expected.read_text())
        assert data["sku"] == "1101-0001-0008"

    def test_creates_subdirectories(self, tmp_path: Path) -> None:
        profile = {"sku": "5202-0002-0019", "name": "Motor", "category": "motion/motor"}
        output_dir = tmp_path / "profiles"
        write_profile(profile, str(output_dir))

        expected = output_dir / "motion" / "motor" / "5202-0002-0019.json"
        assert expected.exists()
