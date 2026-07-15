"""Tests for the full design synthesis pipeline."""

import pytest

from robotics_design_advisor.engineering.design_synthesizer import (
    synthesize_design,
)
from robotics_design_advisor.engineering.models import (
    BillOfMaterials,
    DesignSynthesis,
    ScoringStrategy,
)


class TestSynthesizeDesign:
    def test_returns_design_synthesis(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert isinstance(result, DesignSynthesis)

    def test_has_season_info(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert result.season == "INTO THE DEEP"
        assert result.competition == "FTC"

    def test_has_strategy(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert isinstance(result.strategy, ScoringStrategy)
        assert result.strategy.total_expected_points > 0

    def test_has_archetype(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert result.archetype_name != ""

    def test_has_bom(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert isinstance(result.bom, BillOfMaterials)
        assert result.bom.total_cost_usd > 0
        assert len(result.bom.items) > 0

    def test_has_mechanism_notes(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert len(result.mechanism_notes) > 0

    def test_has_autonomous_notes(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert len(result.autonomous_notes) > 0

    def test_specific_archetype(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
            archetype_id="V5",
        )
        assert result.archetype_name == "Placer Bot"

    def test_beginner_level(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="beginner",
        )
        assert isinstance(result, DesignSynthesis)
        assert result.strategy.difficulty in ("beginner", "intermediate")

    def test_advanced_level(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="advanced",
        )
        assert isinstance(result, DesignSynthesis)

    def test_invalid_team_level_raises(self):
        with pytest.raises(ValueError, match="team_level"):
            synthesize_design(
                season_file="ftc-2024-into-the-deep.json",
                team_level="expert",
            )

    def test_invalid_archetype_raises(self):
        with pytest.raises(ValueError, match="archetype"):
            synthesize_design(
                season_file="ftc-2024-into-the-deep.json",
                team_level="intermediate",
                archetype_id="V99",
            )

    def test_missing_season_raises(self):
        with pytest.raises(FileNotFoundError):
            synthesize_design(
                season_file="nonexistent.json",
                team_level="intermediate",
            )

    def test_fallback_when_no_archetypes_match(self, monkeypatch):
        from robotics_design_advisor.engineering import design_synthesizer

        monkeypatch.setattr(
            design_synthesizer, "recommend_for_season", lambda *a, **kw: []
        )
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert result.archetype_name == "Custom"
        assert any("no matching archetype" in w.lower() for w in result.warnings)
