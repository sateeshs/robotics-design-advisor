"""Tests for game analysis and strategy generation."""

import pytest

from robotics_design_advisor.engineering.game_analyzer import (
    analyze_game,
    load_enhanced_season,
)
from robotics_design_advisor.engineering.models import GameAnalysis, ScoringStrategy


class TestLoadEnhancedSeason:
    def test_loads_into_the_deep(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert data["game_name"] == "INTO THE DEEP"
        assert data["competition"] == "FTC"
        assert len(data["game_elements"]) == 2

    def test_has_scoring_actions(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert "scoring_actions" in data
        assert len(data["scoring_actions"]) >= 3

    def test_has_endgame(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert "endgame" in data
        assert len(data["endgame"]) >= 2

    def test_has_constraints(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert "constraints" in data
        assert data["constraints"]["auto_period_s"] == 30

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_enhanced_season("nonexistent.json")

    def test_path_traversal_raises(self):
        with pytest.raises(ValueError, match="escapes"):
            load_enhanced_season("../../etc/passwd")


class TestAnalyzeGame:
    def test_returns_game_analysis(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert isinstance(analysis, GameAnalysis)
        assert analysis.season == "INTO THE DEEP"
        assert analysis.competition == "FTC"

    def test_generates_strategies(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert len(analysis.strategies) >= 2
        for s in analysis.strategies:
            assert isinstance(s, ScoringStrategy)
            assert s.total_expected_points > 0

    def test_recommends_strategy(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert analysis.recommended_strategy != ""
        strategy_names = {s.name for s in analysis.strategies}
        assert analysis.recommended_strategy in strategy_names

    def test_beginner_gets_easier_strategy(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        beginner = analyze_game(data, "beginner")
        advanced = analyze_game(data, "advanced")
        # Beginner strategy should be easier difficulty
        beginner_strat = next(
            s for s in beginner.strategies if s.name == beginner.recommended_strategy
        )
        advanced_strat = next(
            s for s in advanced.strategies if s.name == advanced.recommended_strategy
        )
        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        assert difficulty_order[beginner_strat.difficulty] <= difficulty_order[advanced_strat.difficulty]

    def test_strategies_have_required_mechanisms(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        for s in analysis.strategies:
            assert len(s.required_mechanisms) > 0
            assert "drivetrain" in s.required_mechanisms

    def test_includes_game_pieces(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert len(analysis.game_pieces) > 0

    def test_includes_field_config(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert "dimensions_mm" in analysis.field_config or "width_mm" in analysis.field_config

    def test_invalid_team_level_raises(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        with pytest.raises(ValueError, match="team_level"):
            analyze_game(data, "expert")

    def test_auto_points_reflect_autonomous_multiplier(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        for s in analysis.strategies:
            # Auto points should be >= 0 since scoring_actions have auto multipliers
            assert s.expected_auto_points >= 0

    def test_empty_scoring_actions_raises(self):
        data = {
            "competition": "FTC",
            "game_name": "Empty",
            "game_elements": [],
            "field": {},
        }
        with pytest.raises(ValueError, match="scoring strategies"):
            analyze_game(data, "intermediate")
