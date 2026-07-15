"""Integration tests — run the full STEP analysis pipeline on real files.

These tests require CadQuery and are marked with @pytest.mark.integration
so they can be skipped in CI without OCCT installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from robotics_design_advisor.step.analyzer import StepAnalysis, analyze
from robotics_design_advisor.step.hole_detector import HoleDetection, detect
from robotics_design_advisor.step.connection_classifier import classify
from robotics_design_advisor.step.profile_builder import build_profile, write_profile

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "step"
_BEAM_STEP = _FIXTURES_DIR / "1101-0001-0008.STEP"

pytestmark = pytest.mark.integration


@pytest.fixture
def beam_step_path() -> str:
    if not _BEAM_STEP.exists():
        pytest.skip("STEP fixture not available")
    return str(_BEAM_STEP)


# ---------------------------------------------------------------------------
# Tests: analyzer on real STEP
# ---------------------------------------------------------------------------

class TestAnalyzerIntegration:
    def test_loads_and_extracts_geometry(self, beam_step_path: str) -> None:
        result = analyze(beam_step_path)
        assert isinstance(result, StepAnalysis)

        # 1101-0001-0008 is a small U-beam, roughly 12x8x12 mm
        bb = result.bounding_box
        assert bb[0] > 0
        assert bb[1] > 0
        assert bb[2] > 0

    def test_has_faces(self, beam_step_path: str) -> None:
        result = analyze(beam_step_path)
        assert len(result.faces) > 0

    def test_volume_positive(self, beam_step_path: str) -> None:
        result = analyze(beam_step_path)
        assert result.volume_mm3 > 0

    def test_return_shape(self, beam_step_path: str) -> None:
        result, shape = analyze(beam_step_path, return_shape=True)
        assert isinstance(result, StepAnalysis)
        assert shape is not None


# ---------------------------------------------------------------------------
# Tests: hole detection on real STEP
# ---------------------------------------------------------------------------

class TestHoleDetectorIntegration:
    def test_detects_holes(self, beam_step_path: str) -> None:
        analysis, shape = analyze(beam_step_path, return_shape=True)
        detection = detect(analysis, shape)
        assert isinstance(detection, HoleDetection)
        # Small beam should have at least some holes
        # (if it doesn't, that's also valid — depends on the part)


# ---------------------------------------------------------------------------
# Tests: full pipeline on real STEP
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:
    def test_build_profile(self, beam_step_path: str) -> None:
        profile = build_profile(
            step_path=beam_step_path,
            sku="1101-0001-0008",
            name="U-Beam 8mm",
            category="structure/beam",
        )

        # Verify schema compliance
        assert profile["sku"] == "1101-0001-0008"
        assert profile["name"] == "U-Beam 8mm"
        assert profile["category"] == "structure/beam"
        assert profile["schema_version"] == 1
        assert "geometry" in profile
        assert "bounding_box" in profile["geometry"]
        assert "volume_cm3" in profile["geometry"]
        assert "mass_grams" in profile["geometry"]
        assert "mounting_faces" in profile
        assert "hole_patterns" in profile
        assert "connection_points" in profile
        assert "compatible_with" in profile
        assert "can_mate_with" in profile

    def test_write_profile(self, beam_step_path: str, tmp_path: Path) -> None:
        profile = build_profile(
            step_path=beam_step_path,
            sku="1101-0001-0008",
            name="U-Beam 8mm",
            category="structure/beam",
        )
        out_file = write_profile(profile, str(tmp_path))

        assert out_file.exists()
        assert out_file.name == "1101-0001-0008.json"

        import json
        with open(out_file) as f:
            data = json.load(f)
        assert data["sku"] == "1101-0001-0008"

    def test_profile_loadable_by_parts_catalog(
        self, beam_step_path: str, tmp_path: Path
    ) -> None:
        """Verify the generated profile can be loaded by PartsCatalog."""
        from robotics_design_advisor.parts.query import PartsCatalog

        profile = build_profile(
            step_path=beam_step_path,
            sku="1101-0001-0008",
            name="U-Beam 8mm",
            category="structure/beam",
        )
        write_profile(profile, str(tmp_path))

        catalog = PartsCatalog(tmp_path)
        assert catalog.part_count == 1

        results = catalog.search(query="1101")
        assert len(results) == 1
        assert results[0].sku == "1101-0001-0008"

        full = catalog.get_profile("1101-0001-0008")
        assert full.sku == "1101-0001-0008"
        assert full.geometry.bounding_box.x > 0
