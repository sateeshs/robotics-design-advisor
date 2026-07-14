"""Tests for smart mate suggestions."""

from pathlib import Path

import pytest

from robotics_design_advisor.parts.query import PartsCatalog
from robotics_design_advisor.parts.smart_mate import suggest_mates


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_profiles"


@pytest.fixture()
def catalog() -> PartsCatalog:
    return PartsCatalog(FIXTURES_DIR)


@pytest.fixture()
def channel_profile(catalog: PartsCatalog):
    return catalog.get_profile("1120-0001-0288")


@pytest.fixture()
def motor_profile(catalog: PartsCatalog):
    return catalog.get_profile("5202-0002-0019")


@pytest.fixture()
def wheel_profile(catalog: PartsCatalog):
    return catalog.get_profile("2900-0005-0002")


@pytest.fixture()
def shaft_profile(catalog: PartsCatalog):
    return catalog.get_profile("1310-0016-4008")


class TestShaftMates:
    def test_wheel_to_shaft_concentric(self, wheel_profile, shaft_profile) -> None:
        suggestions = suggest_mates(wheel_profile, shaft_profile)
        concentric = [s for s in suggestions if s.mate_type == "concentric"]
        assert len(concentric) >= 1
        assert concentric[0].confidence >= 0.9

    def test_channel_to_shaft_concentric(self, channel_profile, shaft_profile) -> None:
        suggestions = suggest_mates(channel_profile, shaft_profile)
        concentric = [s for s in suggestions if s.mate_type == "concentric"]
        assert len(concentric) >= 1

    def test_shaft_mate_mentions_diameter(self, wheel_profile, shaft_profile) -> None:
        suggestions = suggest_mates(wheel_profile, shaft_profile)
        concentric = [s for s in suggestions if s.mate_type == "concentric"]
        assert any("8" in s.rationale for s in concentric)


class TestBoltPatternMates:
    def test_channel_to_channel_coincident(self, channel_profile) -> None:
        suggestions = suggest_mates(channel_profile, channel_profile)
        coincident = [s for s in suggestions if s.mate_type == "coincident"]
        assert len(coincident) >= 1
        assert coincident[0].confidence >= 0.85

    def test_channel_to_wheel_bolt_match(self, channel_profile, wheel_profile) -> None:
        suggestions = suggest_mates(channel_profile, wheel_profile)
        bolt_mates = [s for s in suggestions if "bolt" in s.rationale.lower() or "M4" in s.rationale]
        # Both have M4_bolt tag on their bolt hole grids
        assert len(bolt_mates) >= 1


class TestMotorMates:
    def test_motor_to_channel_has_suggestions(self, motor_profile, channel_profile) -> None:
        suggestions = suggest_mates(motor_profile, channel_profile)
        assert len(suggestions) >= 1

    def test_motor_mount_coincident(self, motor_profile, channel_profile) -> None:
        suggestions = suggest_mates(motor_profile, channel_profile)
        # Motor has motor_mount_pattern with M4_bolt, channel has bolt_hole_grid with M4_bolt
        bolt_mates = [s for s in suggestions if s.confidence >= 0.5]
        assert len(bolt_mates) >= 1


class TestNoMates:
    def test_motor_to_shaft_limited(self, motor_profile, shaft_profile) -> None:
        # Motor has 6mm D-shaft, shaft has REX 8mm — different tags, no overlap
        suggestions = suggest_mates(motor_profile, shaft_profile)
        # Should have no concentric mate (different shaft diameters/tags)
        concentric = [s for s in suggestions if s.mate_type == "concentric"]
        assert len(concentric) == 0


class TestSuggestionProperties:
    def test_sorted_by_confidence(self, channel_profile, wheel_profile) -> None:
        suggestions = suggest_mates(channel_profile, wheel_profile)
        if len(suggestions) >= 2:
            confidences = [s.confidence for s in suggestions]
            assert confidences == sorted(confidences, reverse=True)

    def test_all_have_rationale(self, channel_profile, shaft_profile) -> None:
        suggestions = suggest_mates(channel_profile, shaft_profile)
        for s in suggestions:
            assert s.rationale
            assert len(s.rationale) > 10

    def test_all_have_refs(self, wheel_profile, shaft_profile) -> None:
        suggestions = suggest_mates(wheel_profile, shaft_profile)
        for s in suggestions:
            assert "@" in s.part_a_ref
            assert "@" in s.part_b_ref

    def test_confidence_in_range(self, channel_profile, wheel_profile) -> None:
        suggestions = suggest_mates(channel_profile, wheel_profile)
        for s in suggestions:
            assert 0.0 <= s.confidence <= 1.0

    def test_no_duplicate_suggestions(self, channel_profile) -> None:
        suggestions = suggest_mates(channel_profile, channel_profile)
        keys = [(s.mate_type, s.part_a_ref, s.part_b_ref) for s in suggestions]
        assert len(keys) == len(set(keys))


class TestSymmetry:
    def test_same_count_both_directions(self, channel_profile, wheel_profile) -> None:
        ab = suggest_mates(channel_profile, wheel_profile)
        ba = suggest_mates(wheel_profile, channel_profile)
        assert len(ab) == len(ba)

    def test_same_mate_types_both_directions(self, wheel_profile, shaft_profile) -> None:
        ab = suggest_mates(wheel_profile, shaft_profile)
        ba = suggest_mates(shaft_profile, wheel_profile)
        types_ab = sorted(s.mate_type for s in ab)
        types_ba = sorted(s.mate_type for s in ba)
        assert types_ab == types_ba
