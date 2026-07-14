"""Tests for tiered parts query engine."""

from pathlib import Path

import pytest

from robotics_design_advisor.parts.query import (
    PartsCatalog,
    ProfileNotFoundError,
)


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_profiles"


@pytest.fixture()
def catalog() -> PartsCatalog:
    return PartsCatalog(FIXTURES_DIR)


class TestCatalogLoading:
    def test_loads_all_fixture_parts(self, catalog: PartsCatalog) -> None:
        assert catalog.part_count == 5

    def test_empty_directory(self, tmp_path: Path) -> None:
        cat = PartsCatalog(tmp_path)
        assert cat.part_count == 0

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        cat = PartsCatalog(tmp_path / "nope")
        assert cat.part_count == 0

    def test_skips_underscore_files(self, tmp_path: Path) -> None:
        (tmp_path / "_template.json").write_text('{"sku":"X","name":"X","category":"x"}')
        cat = PartsCatalog(tmp_path)
        assert cat.part_count == 0

    def test_skips_malformed_json(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("not json{{{")
        cat = PartsCatalog(tmp_path)
        assert cat.part_count == 0

    def test_skips_missing_required_fields(self, tmp_path: Path) -> None:
        (tmp_path / "partial.json").write_text('{"sku":"1120-0001-0001"}')
        cat = PartsCatalog(tmp_path)
        assert cat.part_count == 0


class TestListCategories:
    def test_returns_all_categories(self, catalog: PartsCatalog) -> None:
        cats = catalog.list_categories()
        names = [c.category for c in cats]
        assert "structure/channel" in names
        assert "motion/motor" in names
        assert "motion/wheel" in names
        assert "motion/shaft" in names

    def test_categories_sorted(self, catalog: PartsCatalog) -> None:
        cats = catalog.list_categories()
        names = [c.category for c in cats]
        assert names == sorted(names)

    def test_channel_count(self, catalog: PartsCatalog) -> None:
        cats = catalog.list_categories()
        channel = next(c for c in cats if c.category == "structure/channel")
        assert channel.part_count == 2


class TestSearch:
    def test_search_by_name(self, catalog: PartsCatalog) -> None:
        results = catalog.search("mecanum")
        assert len(results) == 1
        assert results[0].sku == "2900-0005-0002"

    def test_search_by_sku(self, catalog: PartsCatalog) -> None:
        results = catalog.search("1120-0001-0288")
        assert len(results) == 1
        assert results[0].name == "U-Channel 288mm"

    def test_search_case_insensitive(self, catalog: PartsCatalog) -> None:
        results = catalog.search("U-CHANNEL")
        assert len(results) == 2

    def test_search_multi_word(self, catalog: PartsCatalog) -> None:
        results = catalog.search("channel 288")
        assert len(results) == 1
        assert results[0].sku == "1120-0001-0288"

    def test_search_by_category(self, catalog: PartsCatalog) -> None:
        results = catalog.search(category="structure/channel")
        assert len(results) == 2
        assert all(r.category == "structure/channel" for r in results)

    def test_search_no_results(self, catalog: PartsCatalog) -> None:
        results = catalog.search("nonexistent part xyz")
        assert results == []

    def test_search_empty_query_returns_all(self, catalog: PartsCatalog) -> None:
        results = catalog.search(max_results=100)
        assert len(results) == 5

    def test_search_max_results(self, catalog: PartsCatalog) -> None:
        results = catalog.search(max_results=2)
        assert len(results) == 2

    def test_search_by_min_length(self, catalog: PartsCatalog) -> None:
        results = catalog.search(min_length_mm=400)
        skus = {r.sku for r in results}
        assert "1120-0001-0432" in skus  # 432mm
        assert "1310-0016-4008" in skus  # 400mm
        assert "1120-0001-0288" not in skus

    def test_search_by_max_length(self, catalog: PartsCatalog) -> None:
        results = catalog.search(max_length_mm=100)
        skus = {r.sku for r in results}
        assert "2900-0005-0002" in skus  # 96mm
        assert "1120-0001-0288" not in skus  # 288mm

    def test_search_by_compatible_tag(self, catalog: PartsCatalog) -> None:
        results = catalog.search(compatible_with="REX_8mm_shaft")
        skus = {r.sku for r in results}
        assert "1120-0001-0288" in skus  # channel with shaft bore
        assert "2900-0005-0002" in skus  # wheel with shaft bore
        assert "1310-0016-4008" in skus  # shaft
        assert "5202-0002-0019" not in skus  # motor has 6mm, not REX 8mm

    def test_search_combined_filters(self, catalog: PartsCatalog) -> None:
        results = catalog.search(
            "channel",
            category="structure/channel",
            min_length_mm=300,
        )
        assert len(results) == 1
        assert results[0].sku == "1120-0001-0432"


class TestFindCompatible:
    def test_find_by_tag(self, catalog: PartsCatalog) -> None:
        results = catalog.find_compatible("gobilda_8mm_pattern")
        skus = {r.sku for r in results}
        assert "1120-0001-0288" in skus
        assert "1120-0001-0432" in skus

    def test_find_with_category_filter(self, catalog: PartsCatalog) -> None:
        results = catalog.find_compatible(
            "REX_8mm_shaft", category="motion/wheel",
        )
        assert len(results) == 1
        assert results[0].sku == "2900-0005-0002"

    def test_find_no_matches(self, catalog: PartsCatalog) -> None:
        results = catalog.find_compatible("nonexistent_tag")
        assert results == []


class TestGetProfile:
    def test_get_existing_profile(self, catalog: PartsCatalog) -> None:
        profile = catalog.get_profile("1120-0001-0288")
        assert profile.sku == "1120-0001-0288"
        assert profile.name == "U-Channel 288mm"
        assert profile.geometry.mass_grams == 115
        assert len(profile.mounting_faces) == 2
        assert len(profile.hole_patterns) == 2
        assert len(profile.connection_points) == 2
        assert "gobilda_8mm_pattern" in profile.compatible_with

    def test_get_motor_profile(self, catalog: PartsCatalog) -> None:
        profile = catalog.get_profile("5202-0002-0019")
        assert profile.category == "motion/motor"
        assert profile.geometry.bounding_box.z == 102

    def test_get_nonexistent_raises(self, catalog: PartsCatalog) -> None:
        with pytest.raises(ProfileNotFoundError, match="9999"):
            catalog.get_profile("9999-0000-0000")

    def test_profile_immutable(self, catalog: PartsCatalog) -> None:
        profile = catalog.get_profile("1120-0001-0288")
        with pytest.raises(AttributeError):
            profile.sku = "changed"  # type: ignore[misc]

    def test_profile_schema_version(self, catalog: PartsCatalog) -> None:
        profile = catalog.get_profile("1120-0001-0288")
        assert profile.schema_version == 1

    def test_shaft_profile_has_no_mounting_faces(self, catalog: PartsCatalog) -> None:
        profile = catalog.get_profile("1310-0016-4008")
        assert len(profile.mounting_faces) == 0
        assert len(profile.hole_patterns) == 0
        assert len(profile.connection_points) == 1


class TestCatalogEntryFields:
    def test_entry_has_bounding_box(self, catalog: PartsCatalog) -> None:
        results = catalog.search("1120-0001-0288")
        entry = results[0]
        assert entry.bounding_box.x == 48
        assert entry.bounding_box.z == 288

    def test_entry_has_mass(self, catalog: PartsCatalog) -> None:
        results = catalog.search("1120-0001-0288")
        assert results[0].mass_grams == 115

    def test_entry_has_hole_count(self, catalog: PartsCatalog) -> None:
        results = catalog.search("1120-0001-0288")
        assert results[0].hole_count == 432  # 216 top + 216 bottom

    def test_entry_has_bolt_size(self, catalog: PartsCatalog) -> None:
        results = catalog.search("1120-0001-0288")
        assert results[0].bolt_size == "M4"
