"""Tests for Parts Intelligence MCP server tool handlers.

Tests call the tool handler functions directly (no MCP transport).
"""

from pathlib import Path

import pytest

import parts_server
from robotics_design_advisor.parts.query import PartsCatalog


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_profiles"


@pytest.fixture(autouse=True)
def _load_catalog():
    """Load the test catalog before each test."""
    parts_server._catalog = PartsCatalog(FIXTURES_DIR)
    yield
    parts_server._catalog = None


# ---------------------------------------------------------------------------
# search_parts
# ---------------------------------------------------------------------------

class TestSearchParts:
    def test_search_by_name(self) -> None:
        results = parts_server.search_parts("mecanum")
        assert len(results) == 1
        assert results[0]["sku"] == "2900-0005-0002"

    def test_search_by_sku(self) -> None:
        results = parts_server.search_parts("1120-0001-0288")
        assert len(results) == 1
        assert results[0]["name"] == "U-Channel 288mm"

    def test_search_by_category(self) -> None:
        results = parts_server.search_parts(category="structure/channel")
        assert len(results) == 2
        assert all(r["category"] == "structure/channel" for r in results)

    def test_search_empty_returns_all(self) -> None:
        results = parts_server.search_parts(max_results=100)
        assert len(results) == 5

    def test_search_no_match(self) -> None:
        results = parts_server.search_parts("nonexistent xyz")
        assert results == []

    def test_search_min_length(self) -> None:
        results = parts_server.search_parts(min_length_mm=400)
        skus = {r["sku"] for r in results}
        assert "1120-0001-0432" in skus
        assert "1120-0001-0288" not in skus

    def test_search_max_length(self) -> None:
        results = parts_server.search_parts(max_length_mm=100)
        skus = {r["sku"] for r in results}
        assert "2900-0005-0002" in skus
        assert "1120-0001-0288" not in skus

    def test_search_max_results(self) -> None:
        results = parts_server.search_parts(max_results=2)
        assert len(results) == 2

    def test_search_zero_min_length_ignored(self) -> None:
        results = parts_server.search_parts(min_length_mm=0.0, max_results=100)
        assert len(results) == 5

    def test_search_zero_max_length_ignored(self) -> None:
        results = parts_server.search_parts(max_length_mm=0.0, max_results=100)
        assert len(results) == 5

    def test_search_empty_category_ignored(self) -> None:
        results = parts_server.search_parts(category="", max_results=100)
        assert len(results) == 5

    def test_result_has_required_fields(self) -> None:
        results = parts_server.search_parts("channel")
        entry = results[0]
        assert "sku" in entry
        assert "name" in entry
        assert "category" in entry
        assert "bounding_box" in entry
        assert "mass_grams" in entry


# ---------------------------------------------------------------------------
# get_part_profile
# ---------------------------------------------------------------------------

class TestGetPartProfile:
    def test_get_existing(self) -> None:
        profile = parts_server.get_part_profile("1120-0001-0288")
        assert profile["sku"] == "1120-0001-0288"
        assert profile["name"] == "U-Channel 288mm"
        assert profile["geometry"]["mass_grams"] == 115
        assert len(profile["mounting_faces"]) == 2
        assert len(profile["hole_patterns"]) == 2

    def test_get_motor(self) -> None:
        profile = parts_server.get_part_profile("5202-0002-0019")
        assert profile["category"] == "motion/motor"
        assert "connection_points" in profile

    def test_get_nonexistent_returns_error(self) -> None:
        result = parts_server.get_part_profile("9999-0000-0000")
        assert "error" in result

    def test_profile_has_connection_points(self) -> None:
        profile = parts_server.get_part_profile("1120-0001-0288")
        cps = profile["connection_points"]
        assert len(cps) == 2
        types = {cp["connection_type"] for cp in cps}
        assert "bolt_hole_grid" in types
        assert "shaft_bore" in types

    def test_profile_has_compatible_with(self) -> None:
        profile = parts_server.get_part_profile("1120-0001-0288")
        assert "gobilda_8mm_pattern" in profile["compatible_with"]


# ---------------------------------------------------------------------------
# find_compatible_parts
# ---------------------------------------------------------------------------

class TestFindCompatibleParts:
    def test_find_by_tag(self) -> None:
        results = parts_server.find_compatible_parts("gobilda_8mm_pattern")
        skus = {r["sku"] for r in results}
        assert "1120-0001-0288" in skus
        assert "1120-0001-0432" in skus

    def test_find_shaft_compatible(self) -> None:
        results = parts_server.find_compatible_parts("REX_8mm_shaft")
        skus = {r["sku"] for r in results}
        assert "2900-0005-0002" in skus  # wheel
        assert "1310-0016-4008" in skus  # shaft
        assert "1120-0001-0288" in skus  # channel

    def test_find_with_category(self) -> None:
        results = parts_server.find_compatible_parts(
            "REX_8mm_shaft", category="motion/wheel",
        )
        assert len(results) == 1
        assert results[0]["sku"] == "2900-0005-0002"

    def test_find_no_match(self) -> None:
        results = parts_server.find_compatible_parts("nonexistent_tag")
        assert results == []

    def test_empty_category_ignored(self) -> None:
        results = parts_server.find_compatible_parts("M4_bolt", category="")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# list_categories
# ---------------------------------------------------------------------------

class TestListCategories:
    def test_returns_all_categories(self) -> None:
        cats = parts_server.list_categories()
        names = {c["category"] for c in cats}
        assert "structure/channel" in names
        assert "motion/motor" in names
        assert "motion/wheel" in names
        assert "motion/shaft" in names

    def test_categories_have_counts(self) -> None:
        cats = parts_server.list_categories()
        channel = next(c for c in cats if c["category"] == "structure/channel")
        assert channel["part_count"] == 2

    def test_categories_are_dicts(self) -> None:
        cats = parts_server.list_categories()
        for c in cats:
            assert isinstance(c, dict)
            assert "category" in c
            assert "part_count" in c


# ---------------------------------------------------------------------------
# suggest_mates
# ---------------------------------------------------------------------------

class TestSuggestMates:
    def test_wheel_to_shaft(self) -> None:
        results = parts_server.suggest_mates("2900-0005-0002", "1310-0016-4008")
        assert len(results) >= 1
        assert results[0]["mate_type"] == "concentric"
        assert results[0]["confidence"] >= 0.9

    def test_channel_to_channel(self) -> None:
        results = parts_server.suggest_mates("1120-0001-0288", "1120-0001-0432")
        assert len(results) >= 1
        mate_types = {r["mate_type"] for r in results}
        assert "coincident" in mate_types

    def test_nonexistent_sku_a_returns_error(self) -> None:
        result = parts_server.suggest_mates("9999-0000-0000", "1120-0001-0288")
        assert isinstance(result, dict)
        assert "error" in result

    def test_nonexistent_sku_b_returns_error(self) -> None:
        result = parts_server.suggest_mates("1120-0001-0288", "9999-0000-0000")
        assert isinstance(result, dict)
        assert "error" in result

    def test_suggestions_have_required_fields(self) -> None:
        results = parts_server.suggest_mates("2900-0005-0002", "1310-0016-4008")
        for s in results:
            assert "mate_type" in s
            assert "part_a_ref" in s
            assert "part_b_ref" in s
            assert "confidence" in s
            assert "rationale" in s

    def test_motor_to_channel(self) -> None:
        results = parts_server.suggest_mates("5202-0002-0019", "1120-0001-0288")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Server initialization
# ---------------------------------------------------------------------------

class TestServerInit:
    def test_catalog_not_loaded_raises(self) -> None:
        parts_server._catalog = None
        with pytest.raises(RuntimeError, match="not initialized"):
            parts_server._get_catalog()

    def test_mcp_server_name(self) -> None:
        assert parts_server.mcp.name == "parts-intelligence"
