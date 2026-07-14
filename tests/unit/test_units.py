"""Tests for unit conversion utilities."""

import pytest

from robotics_design_advisor.utils.units import UnitConverter, mm, cm, inch, ft


@pytest.fixture
def converter():
    return UnitConverter()


class TestUnitConverter:
    def test_mm_to_meters(self, converter):
        result = converter.to_meters(10.0, "mm")
        assert abs(result - 0.01) < 1e-9

    def test_cm_to_meters(self, converter):
        result = converter.to_meters(100.0, "cm")
        assert abs(result - 1.0) < 1e-9

    def test_inch_to_meters(self, converter):
        result = converter.to_meters(1.0, "inch")
        assert abs(result - 0.0254) < 1e-6

    def test_ft_to_meters(self, converter):
        result = converter.to_meters(1.0, "ft")
        assert abs(result - 0.3048) < 1e-6

    def test_m_to_meters(self, converter):
        result = converter.to_meters(1.0, "m")
        assert abs(result - 1.0) < 1e-9

    def test_meters_to_mm(self, converter):
        result = converter.from_meters(0.01, "mm")
        assert abs(result - 10.0) < 1e-9

    def test_meters_to_inch(self, converter):
        result = converter.from_meters(0.0254, "inch")
        assert abs(result - 1.0) < 1e-6


class TestConvenienceFunctions:
    def test_mm_function(self):
        result = mm(10.0)
        assert abs(result - 0.01) < 1e-9

    def test_cm_function(self):
        result = cm(100.0)
        assert abs(result - 1.0) < 1e-9

    def test_inch_function(self):
        result = inch(1.0)
        assert abs(result - 0.0254) < 1e-6

    def test_ft_function(self):
        result = ft(1.0)
        assert abs(result - 0.3048) < 1e-6
