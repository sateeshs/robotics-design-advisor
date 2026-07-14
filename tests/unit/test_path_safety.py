"""Tests for path safety utilities."""

import pytest

from robotics_design_advisor.engineering.electrical import load_motor_specs, load_hub_spec
from robotics_design_advisor.engineering.design_advisor import load_season


class TestPathTraversal:
    def test_motor_loader_blocks_traversal(self) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            load_motor_specs("../../etc/passwd")

    def test_hub_loader_blocks_traversal(self) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            load_hub_spec("../../../etc/shadow")

    def test_season_loader_blocks_traversal(self) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            load_season("../../server.py")

    def test_valid_motor_path_works(self) -> None:
        motors = load_motor_specs("motor_data/gobilda_yellow_jacket.json")
        assert len(motors) > 0

    def test_valid_hub_path_works(self) -> None:
        hub = load_hub_spec("hub_data/rev_control_hub.json")
        assert hub.name == "REV Control Hub"

    def test_valid_season_path_works(self) -> None:
        season = load_season("ftc-2025-decode.json")
        assert season.game_name == "DECODE"

    def test_missing_file_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Motor data file not found"):
            load_motor_specs("motor_data/nonexistent.json")
