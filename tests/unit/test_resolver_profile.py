"""Tests for SkuResolver.resolve_with_profile."""

import json

import pytest

from robotics_design_advisor.parts.resolver import SkuResolver, SkuNotFoundError


class TestResolveWithProfile:
    def test_returns_path_and_profile(self, tmp_path):
        profile_dir = tmp_path / "profiles"
        profile_dir.mkdir()
        profile = {"sku": "1101-0001-0008", "category": "structure/beam"}
        (profile_dir / "1101-0001-0008.json").write_text(json.dumps(profile))

        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(profile_dir),
        )
        path, prof = resolver.resolve_with_profile("1101-0001-0008")
        assert path == "/parts/beams/1101-0001-0008.step"
        assert prof["sku"] == "1101-0001-0008"

    def test_returns_none_profile_when_not_cached(self, tmp_path):
        profile_dir = tmp_path / "profiles"
        profile_dir.mkdir()

        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(profile_dir),
        )
        path, prof = resolver.resolve_with_profile("1101-0001-0008")
        assert path == "/parts/beams/1101-0001-0008.step"
        assert prof is None

    def test_returns_none_profile_when_no_profiles_dir(self):
        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
        )
        path, prof = resolver.resolve_with_profile("1101-0001-0008")
        assert path == "/parts/beams/1101-0001-0008.step"
        assert prof is None

    def test_invalid_sku_raises(self, tmp_path):
        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(tmp_path),
        )
        with pytest.raises(ValueError):
            resolver.resolve_with_profile("")

    def test_unknown_prefix_raises(self, tmp_path):
        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(tmp_path),
        )
        with pytest.raises(SkuNotFoundError):
            resolver.resolve_with_profile("9999-0001-0001")
