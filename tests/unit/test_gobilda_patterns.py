"""Tests for goBILDA pattern constants."""

from robotics_design_advisor.parts import gobilda_patterns as gp


class TestPitchConstants:
    def test_standard_pitch(self) -> None:
        assert gp.PITCH_MM == 8.0

    def test_half_pitch(self) -> None:
        assert gp.HALF_PITCH_MM == gp.PITCH_MM / 2


class TestM4Constants:
    def test_clearance_larger_than_thread(self) -> None:
        assert gp.M4_CLEARANCE_HOLE_MM > gp.M4_THREAD_DIAMETER_MM

    def test_close_fit_between_thread_and_clearance(self) -> None:
        assert gp.M4_THREAD_DIAMETER_MM < gp.M4_CLOSE_FIT_HOLE_MM < gp.M4_CLEARANCE_HOLE_MM

    def test_tap_drill_smaller_than_thread(self) -> None:
        assert gp.M4_TAP_DRILL_MM < gp.M4_THREAD_DIAMETER_MM

    def test_nut_width_matches_socket_head(self) -> None:
        # M4 nut and socket head are both 7mm across
        assert gp.M4_NUT_WIDTH_MM == gp.M4_SOCKET_HEAD_DIAMETER_MM


class TestRexShaft:
    def test_shaft_and_bore_match(self) -> None:
        assert gp.REX_SHAFT_DIAMETER_MM == gp.REX_SHAFT_BORE_MM

    def test_d_bore_flat_depth_positive(self) -> None:
        assert gp.REX_D_BORE_FLAT_DEPTH_MM > 0


class TestChannelDimensions:
    def test_square_cross_section(self) -> None:
        assert gp.CHANNEL_WIDTH_MM == gp.CHANNEL_HEIGHT_MM

    def test_wall_thickness_positive(self) -> None:
        assert gp.CHANNEL_WALL_THICKNESS_MM > 0

    def test_standard_lengths_sorted(self) -> None:
        lengths = gp.CHANNEL_STANDARD_LENGTHS_MM
        assert lengths == tuple(sorted(lengths))

    def test_lengths_are_multiples_of_pitch(self) -> None:
        for length in gp.CHANNEL_STANDARD_LENGTHS_MM:
            assert length % gp.PITCH_MM == 0, f"{length}mm is not a multiple of {gp.PITCH_MM}mm"

    def test_shortest_length_equals_width(self) -> None:
        assert gp.CHANNEL_STANDARD_LENGTHS_MM[0] == gp.CHANNEL_WIDTH_MM


class TestMotorMount:
    def test_bolt_count(self) -> None:
        assert gp.YELLOW_JACKET_BOLT_COUNT == 4

    def test_shaft_smaller_than_pilot(self) -> None:
        assert gp.YELLOW_JACKET_SHAFT_DIAMETER_MM < gp.YELLOW_JACKET_PILOT_DIAMETER_MM


class TestTags:
    def test_all_tags_populated(self) -> None:
        assert len(gp.ALL_TAGS) >= 5

    def test_all_tags_are_strings(self) -> None:
        for tag in gp.ALL_TAGS:
            assert isinstance(tag, str)

    def test_individual_tags_in_all_tags(self) -> None:
        assert gp.TAG_GOBILDA_8MM_PATTERN in gp.ALL_TAGS
        assert gp.TAG_M4_BOLT in gp.ALL_TAGS
        assert gp.TAG_REX_8MM_SHAFT in gp.ALL_TAGS
        assert gp.TAG_YELLOW_JACKET_MOUNT in gp.ALL_TAGS


class TestSkuCategoryMap:
    def test_channel_prefix(self) -> None:
        assert gp.SKU_CATEGORY_MAP["1120"] == "structure/channel"

    def test_motor_prefix(self) -> None:
        assert gp.SKU_CATEGORY_MAP["5202"] == "motion/motor"

    def test_all_categories_have_slash(self) -> None:
        for prefix, category in gp.SKU_CATEGORY_MAP.items():
            assert "/" in category, f"Category '{category}' for prefix '{prefix}' missing slash"
