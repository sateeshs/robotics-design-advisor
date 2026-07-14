"""Tests for SKU → STEP path resolver (Phase 2E.1)."""

import pytest

from robotics_design_advisor.parts.resolver import (
    SkuResolver,
    SkuNotFoundError,
)


@pytest.fixture()
def resolver():
    return SkuResolver(
        base_path=r"C:\goBILDA",
        category_map={
            "1120": "channel",
            "1121": "channel",
            "1301": "brackets",
            "2900": "wheels",
            "5202": "motors",
            "1310": "shafting",
        },
    )


class TestSkuResolver:
    def test_resolves_channel_sku(self, resolver) -> None:
        path = resolver.resolve("1120-0001-0288")
        assert path == r"C:\goBILDA\channel\1120-0001-0288.step"

    def test_resolves_motor_sku(self, resolver) -> None:
        path = resolver.resolve("5202-0002-0019")
        assert path == r"C:\goBILDA\motors\5202-0002-0019.step"

    def test_resolves_wheel_sku(self, resolver) -> None:
        path = resolver.resolve("2900-0005-0002")
        assert path == r"C:\goBILDA\wheels\2900-0005-0002.step"

    def test_resolves_shaft_sku(self, resolver) -> None:
        path = resolver.resolve("1310-0016-4008")
        assert path == r"C:\goBILDA\shafting\1310-0016-4008.step"

    def test_unknown_category_prefix_raises(self, resolver) -> None:
        with pytest.raises(SkuNotFoundError, match="9999-0001-0001"):
            resolver.resolve("9999-0001-0001")

    def test_empty_sku_raises(self, resolver) -> None:
        with pytest.raises(ValueError, match="SKU must not be empty"):
            resolver.resolve("")

    def test_sku_with_path_traversal_raises(self, resolver) -> None:
        with pytest.raises(ValueError, match="Invalid SKU"):
            resolver.resolve("../etc/passwd")

    def test_sku_with_slashes_raises(self, resolver) -> None:
        with pytest.raises(ValueError, match="Invalid SKU"):
            resolver.resolve("1120/0001/0288")

    def test_custom_extension(self) -> None:
        resolver = SkuResolver(
            base_path=r"D:\Parts",
            category_map={"1120": "channel"},
            extension=".sldprt",
        )
        path = resolver.resolve("1120-0001-0288")
        assert path == r"D:\Parts\channel\1120-0001-0288.sldprt"

    def test_forward_slash_base_path(self) -> None:
        resolver = SkuResolver(
            base_path="/home/user/parts",
            category_map={"1120": "channel"},
        )
        path = resolver.resolve("1120-0001-0288")
        assert path == "/home/user/parts/channel/1120-0001-0288.step"

    def test_get_category(self, resolver) -> None:
        assert resolver.get_category("1120-0001-0288") == "channel"
        assert resolver.get_category("5202-0002-0019") == "motors"

    def test_get_category_unknown_returns_none(self, resolver) -> None:
        assert resolver.get_category("9999-0001-0001") is None

    def test_list_categories(self, resolver) -> None:
        categories = resolver.list_categories()
        assert "channel" in categories
        assert "motors" in categories
        assert len(categories) == 5  # channel, brackets, wheels, motors, shafting (1120+1121 both map to channel)


class TestSkuValidation:
    def test_valid_sku_format(self, resolver) -> None:
        # Should not raise
        resolver.resolve("1120-0001-0288")

    def test_sku_with_backslash_raises(self, resolver) -> None:
        with pytest.raises(ValueError, match="Invalid SKU"):
            resolver.resolve("1120\\0001\\0288")

    def test_sku_with_null_byte_raises(self, resolver) -> None:
        with pytest.raises(ValueError, match="Invalid SKU"):
            resolver.resolve("1120-0001\x00-0288")

    def test_short_sku_raises(self, resolver) -> None:
        with pytest.raises(ValueError, match="SKU too short"):
            resolver.resolve("AB1")
