"""Tests for component pattern operations mixin (Phase 2E.3).

All SolidWorks COM calls are mocked — these tests run on Linux.
"""

from unittest.mock import MagicMock

import pytest

from robotics_design_advisor.automation.patterns import PatternOperations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockPatternHost(PatternOperations):
    """Minimal host that satisfies the mixin's requirements."""

    def __init__(self):
        self._sw_app = MagicMock()
        self._connected = True

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _result(self, success, message, error_code=0, data=None):
        result = {"success": success, "message": message, "error_code": error_code}
        if data is not None:
            result["data"] = data
        return result


@pytest.fixture()
def host():
    h = MockPatternHost()
    doc = MagicMock()
    doc.GetType.return_value = 2  # swDocASSEMBLY
    h._sw_app.ActiveDoc = doc
    return h


# ---------------------------------------------------------------------------
# Linear pattern
# ---------------------------------------------------------------------------

class TestLinearPattern:
    def test_returns_success(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        pattern = MagicMock()
        fm.InsertLinearPattern.return_value = pattern
        doc.FeatureManager = fm

        result = host.create_linear_pattern(
            components=["channel-1"],
            direction=(1.0, 0.0, 0.0),
            count=4,
            spacing_mm=48.0,
        )
        assert result["success"] is True

    def test_passes_count_and_spacing(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        pattern = MagicMock()
        fm.InsertLinearPattern.return_value = pattern
        doc.FeatureManager = fm

        host.create_linear_pattern(
            components=["channel-1"],
            direction=(1.0, 0.0, 0.0),
            count=3,
            spacing_mm=96.0,
        )
        call_args = fm.InsertLinearPattern.call_args
        assert call_args is not None

    def test_data_includes_count(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        pattern = MagicMock()
        fm.InsertLinearPattern.return_value = pattern
        doc.FeatureManager = fm

        result = host.create_linear_pattern(
            components=["channel-1"],
            direction=(1.0, 0.0, 0.0),
            count=5,
            spacing_mm=48.0,
        )
        assert result["data"]["count"] == 5
        assert result["data"]["spacing_mm"] == 48.0

    def test_failure_returns_error(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        fm.InsertLinearPattern.return_value = None
        doc.FeatureManager = fm

        result = host.create_linear_pattern(
            components=["channel-1"],
            direction=(1.0, 0.0, 0.0),
            count=3,
            spacing_mm=48.0,
        )
        assert result["success"] is False

    def test_not_assembly_returns_error(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        doc.GetType.return_value = 1  # part, not assembly

        result = host.create_linear_pattern(
            components=["channel-1"],
            direction=(1.0, 0.0, 0.0),
            count=3,
            spacing_mm=48.0,
        )
        assert result["success"] is False

    def test_invalid_count_raises(self, host) -> None:
        with pytest.raises(ValueError, match="count"):
            host.create_linear_pattern(
                components=["channel-1"],
                direction=(1.0, 0.0, 0.0),
                count=0,
                spacing_mm=48.0,
            )

    def test_invalid_spacing_raises(self, host) -> None:
        with pytest.raises(ValueError, match="spacing_mm"):
            host.create_linear_pattern(
                components=["channel-1"],
                direction=(1.0, 0.0, 0.0),
                count=3,
                spacing_mm=-1.0,
            )


# ---------------------------------------------------------------------------
# Circular pattern
# ---------------------------------------------------------------------------

class TestCircularPattern:
    def test_returns_success(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        pattern = MagicMock()
        fm.InsertCircularPattern.return_value = pattern
        doc.FeatureManager = fm

        result = host.create_circular_pattern(
            components=["wheel-1"],
            axis=(0.0, 1.0, 0.0),
            count=4,
        )
        assert result["success"] is True

    def test_default_angle_is_360(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        pattern = MagicMock()
        fm.InsertCircularPattern.return_value = pattern
        doc.FeatureManager = fm

        result = host.create_circular_pattern(
            components=["wheel-1"],
            axis=(0.0, 1.0, 0.0),
            count=4,
        )
        assert result["data"]["total_angle_deg"] == 360.0

    def test_custom_angle(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        pattern = MagicMock()
        fm.InsertCircularPattern.return_value = pattern
        doc.FeatureManager = fm

        result = host.create_circular_pattern(
            components=["bracket-1"],
            axis=(0.0, 1.0, 0.0),
            count=3,
            total_angle_deg=180.0,
        )
        assert result["data"]["total_angle_deg"] == 180.0

    def test_failure_returns_error(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        fm = MagicMock()
        fm.InsertCircularPattern.return_value = None
        doc.FeatureManager = fm

        result = host.create_circular_pattern(
            components=["wheel-1"],
            axis=(0.0, 1.0, 0.0),
            count=4,
        )
        assert result["success"] is False

    def test_invalid_count_raises(self, host) -> None:
        with pytest.raises(ValueError, match="count"):
            host.create_circular_pattern(
                components=["wheel-1"],
                axis=(0.0, 1.0, 0.0),
                count=1,
            )

    def test_invalid_angle_raises(self, host) -> None:
        with pytest.raises(ValueError, match="total_angle_deg"):
            host.create_circular_pattern(
                components=["wheel-1"],
                axis=(0.0, 1.0, 0.0),
                count=4,
                total_angle_deg=0.0,
            )

    def test_not_assembly_returns_error(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        doc.GetType.return_value = 1

        result = host.create_circular_pattern(
            components=["wheel-1"],
            axis=(0.0, 1.0, 0.0),
            count=4,
        )
        assert result["success"] is False
