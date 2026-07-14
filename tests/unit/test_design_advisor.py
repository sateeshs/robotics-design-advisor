"""Tests for design advisor and variant generation."""

import pytest

from robotics_design_advisor.engineering.design_advisor import (
    DesignVariant,
    SeasonKnowledge,
    count_theoretical_combinations,
    filter_variants,
    get_archetype_by_id,
    get_archetypes,
    list_seasons,
    load_season,
    rank_variants,
    recommend_for_season,
)


# ---------------------------------------------------------------------------
# Season loading
# ---------------------------------------------------------------------------

class TestLoadSeason:
    def test_loads_decode(self) -> None:
        season = load_season("ftc-2025-decode.json")
        assert isinstance(season, SeasonKnowledge)
        assert season.game_name == "DECODE"
        assert season.competition == "FTC"

    def test_has_game_elements(self) -> None:
        season = load_season("ftc-2025-decode.json")
        assert len(season.game_elements) > 0
        assert season.game_elements[0]["name"] == "artifact"

    def test_has_scoring_zones(self) -> None:
        season = load_season("ftc-2025-decode.json")
        assert len(season.scoring_zones) >= 2
        zone_names = {z["name"] for z in season.scoring_zones}
        assert "low_goal" in zone_names
        assert "high_goal" in zone_names

    def test_has_design_axes(self) -> None:
        season = load_season("ftc-2025-decode.json")
        assert "drivetrain" in season.design_axes
        assert "scorer" in season.design_axes
        assert len(season.design_axes["drivetrain"]) >= 2

    def test_has_cycle_targets(self) -> None:
        season = load_season("ftc-2025-decode.json")
        assert season.cycle_targets["top_team_cycles"] == 20


class TestListSeasons:
    def test_includes_decode(self) -> None:
        seasons = list_seasons()
        assert "ftc-2025-decode.json" in seasons

    def test_excludes_template(self) -> None:
        seasons = list_seasons()
        assert "_template.json" not in seasons


# ---------------------------------------------------------------------------
# Archetypes
# ---------------------------------------------------------------------------

class TestGetArchetypes:
    def test_returns_eight_archetypes(self) -> None:
        archetypes = get_archetypes()
        assert len(archetypes) == 8

    def test_all_are_design_variants(self) -> None:
        for v in get_archetypes():
            assert isinstance(v, DesignVariant)

    def test_ids_are_v1_through_v8(self) -> None:
        ids = {v.archetype_id for v in get_archetypes()}
        assert ids == {"V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"}

    def test_all_have_descriptions(self) -> None:
        for v in get_archetypes():
            assert v.description
            assert v.pros
            assert v.cons

    def test_scores_in_valid_range(self) -> None:
        for v in get_archetypes():
            assert 0 <= v.uniqueness_score <= 100
            assert 0 <= v.complexity_score <= 100
            assert 0 <= v.competitive_score <= 100

    def test_motor_budget_within_ftc_limit(self) -> None:
        for v in get_archetypes():
            assert v.motor_budget <= 8


class TestGetArchetypeById:
    def test_finds_v1(self) -> None:
        v = get_archetype_by_id("V1")
        assert v is not None
        assert v.name == "Speed Shooter"

    def test_finds_v3(self) -> None:
        v = get_archetype_by_id("V3")
        assert v is not None
        assert v.name == "Swerve Sniper"

    def test_returns_none_for_invalid(self) -> None:
        assert get_archetype_by_id("V99") is None


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestFilterVariants:
    def test_no_filter_returns_all(self) -> None:
        result = filter_variants()
        assert len(result) == 8

    def test_filter_by_complexity(self) -> None:
        result = filter_variants(max_complexity=60)
        for v in result:
            assert v.complexity_score <= 60

    def test_filter_by_competitiveness(self) -> None:
        result = filter_variants(min_competitive=80)
        for v in result:
            assert v.competitive_score >= 80

    def test_filter_by_uniqueness(self) -> None:
        result = filter_variants(min_uniqueness=70)
        for v in result:
            assert v.uniqueness_score >= 70

    def test_filter_by_motors(self) -> None:
        result = filter_variants(max_motors=6)
        for v in result:
            assert v.motor_budget <= 6

    def test_combined_filters_reduce_count(self) -> None:
        all_variants = filter_variants()
        strict = filter_variants(max_complexity=60, min_competitive=75, min_uniqueness=40)
        assert len(strict) <= len(all_variants)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

class TestRankVariants:
    def test_returns_sorted_descending(self) -> None:
        ranked = rank_variants(get_archetypes())
        scores = [s for _, s in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_returns_all_variants(self) -> None:
        ranked = rank_variants(get_archetypes())
        assert len(ranked) == 8

    def test_high_uniqueness_weight_favors_unique(self) -> None:
        ranked = rank_variants(
            get_archetypes(),
            weight_uniqueness=0.8,
            weight_competitive=0.1,
            weight_complexity_penalty=0.1,
        )
        top = ranked[0][0]
        assert top.uniqueness_score >= 70

    def test_high_competitive_weight_favors_competitive(self) -> None:
        ranked = rank_variants(
            get_archetypes(),
            weight_uniqueness=0.1,
            weight_competitive=0.8,
            weight_complexity_penalty=0.1,
        )
        top = ranked[0][0]
        assert top.competitive_score >= 80


# ---------------------------------------------------------------------------
# Season recommendations
# ---------------------------------------------------------------------------

class TestRecommendForSeason:
    def test_returns_top_n(self) -> None:
        result = recommend_for_season("ftc-2025-decode.json", top_n=3)
        assert len(result) <= 3

    def test_returns_design_variants(self) -> None:
        result = recommend_for_season("ftc-2025-decode.json")
        for variant, score in result:
            assert isinstance(variant, DesignVariant)
            assert isinstance(score, float)

    def test_respects_uniqueness_filter(self) -> None:
        result = recommend_for_season(
            "ftc-2025-decode.json", min_uniqueness=60,
        )
        for variant, _ in result:
            assert variant.uniqueness_score >= 60

    def test_respects_complexity_filter(self) -> None:
        result = recommend_for_season(
            "ftc-2025-decode.json", max_complexity=60,
        )
        for variant, _ in result:
            assert variant.complexity_score <= 60


class TestCountCombinations:
    def test_decode_combinations(self) -> None:
        count = count_theoretical_combinations("ftc-2025-decode.json")
        # 4 drivetrains × 4 intakes × 4 indexers × 4 scorers × 5 aimers × 3 endgames
        assert count == 4 * 4 * 4 * 4 * 5 * 3  # 3840
