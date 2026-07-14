"""Tests for input validation utilities."""

import pytest

from robotics_design_advisor.utils.validation import (
    ValidationError,
    validate_dimension,
    validate_end_condition,
    validate_mate_type,
    validate_name,
    validate_plane,
    validate_position,
    validate_sku,
)


class TestValidateDimension:
    def test_valid_dimension(self):
        assert validate_dimension(10.0, "depth") == 10.0

    def test_integer_input(self):
        assert validate_dimension(5, "depth") == 5.0

    def test_string_number(self):
        assert validate_dimension("25.5", "depth") == 25.5

    def test_negative_raises(self):
        with pytest.raises(ValidationError, match="Must be positive"):
            validate_dimension(-1, "depth")

    def test_zero_raises(self):
        with pytest.raises(ValidationError, match="Must be positive"):
            validate_dimension(0, "depth")

    def test_too_small_raises(self):
        with pytest.raises(ValidationError, match="Too small"):
            validate_dimension(0.0001, "depth")

    def test_too_large_raises(self):
        with pytest.raises(ValidationError, match="Too large"):
            validate_dimension(99999, "depth")

    def test_non_number_raises(self):
        with pytest.raises(ValidationError, match="Must be a number"):
            validate_dimension("abc", "depth")

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="Must be a number"):
            validate_dimension(None, "depth")


class TestValidateName:
    def test_valid_name(self):
        assert validate_name("MyPart", "name") == "MyPart"

    def test_strips_whitespace(self):
        assert validate_name("  MyPart  ", "name") == "MyPart"

    def test_empty_raises(self):
        with pytest.raises(ValidationError, match="Cannot be empty"):
            validate_name("", "name")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError, match="Cannot be empty"):
            validate_name("   ", "name")

    def test_invalid_chars_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_name("My<Part>", "name")

    def test_too_long_raises(self):
        with pytest.raises(ValidationError, match="Too long"):
            validate_name("a" * 300, "name")

    def test_non_string_raises(self):
        with pytest.raises(ValidationError, match="Must be a string"):
            validate_name(123, "name")


class TestValidatePlane:
    def test_front(self):
        assert validate_plane("front") == "Front Plane"

    def test_top(self):
        assert validate_plane("top") == "Top Plane"

    def test_right(self):
        assert validate_plane("right") == "Right Plane"

    def test_non_string_raises(self):
        with pytest.raises(ValidationError):
            validate_plane(42)


class TestValidatePosition:
    def test_valid_list(self):
        assert validate_position([1.0, 2.0, 3.0]) == (1.0, 2.0, 3.0)

    def test_valid_tuple(self):
        assert validate_position((0, 0, 0)) == (0.0, 0.0, 0.0)

    def test_integers(self):
        assert validate_position([1, 2, 3]) == (1.0, 2.0, 3.0)

    def test_wrong_length_raises(self):
        with pytest.raises(ValidationError, match="exactly 3"):
            validate_position([1, 2])

    def test_non_list_raises(self):
        with pytest.raises(ValidationError, match="list of 3"):
            validate_position("1,2,3")


class TestValidateSku:
    def test_valid_sku(self):
        assert validate_sku("1120-0001-0288") == "1120-0001-0288"

    def test_strips_whitespace(self):
        assert validate_sku("  1120-0001-0288  ") == "1120-0001-0288"

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError, match="Invalid SKU format"):
            validate_sku("1120-001-0288")

    def test_empty_raises(self):
        with pytest.raises(ValidationError, match="Cannot be empty"):
            validate_sku("")

    def test_non_string_raises(self):
        with pytest.raises(ValidationError, match="Must be a string"):
            validate_sku(1120)


class TestValidateMateType:
    def test_string_coincident(self):
        assert validate_mate_type("coincident") == 0

    def test_string_concentric(self):
        assert validate_mate_type("concentric") == 1

    def test_string_distance(self):
        assert validate_mate_type("distance") == 5

    def test_case_insensitive(self):
        assert validate_mate_type("COINCIDENT") == 0

    def test_integer_value(self):
        assert validate_mate_type(0) == 0

    def test_invalid_raises(self):
        with pytest.raises(ValidationError, match="Unknown mate type"):
            validate_mate_type("invalid_mate")


class TestValidateEndCondition:
    def test_string_blind(self):
        assert validate_end_condition("blind") == 0

    def test_string_through_all(self):
        assert validate_end_condition("through_all") == 1

    def test_string_midplane(self):
        assert validate_end_condition("midplane") == 6

    def test_integer_value(self):
        assert validate_end_condition(0) == 0

    def test_invalid_raises(self):
        with pytest.raises(ValidationError, match="Unknown end condition"):
            validate_end_condition("invalid_condition")
