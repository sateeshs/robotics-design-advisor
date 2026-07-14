"""Tests for configuration management."""

import json

import pytest

from robotics_design_advisor.config import RoboticsConfig


class TestRoboticsConfig:
    def test_default_values(self):
        config = RoboticsConfig()

        assert config.default_unit == "mm"
        assert config.log_level == "INFO"
        assert config.startup_timeout == 120
        assert config.server_port == 8585

    def test_invalid_unit_defaults_to_mm(self):
        config = RoboticsConfig(default_unit="cubits")

        assert config.default_unit == "mm"

    def test_invalid_log_level_defaults_to_info(self):
        config = RoboticsConfig(log_level="VERBOSE")

        assert config.log_level == "INFO"

    def test_load_from_json(self, tmp_path):
        config_data = {
            "default_unit": "inch",
            "server_port": 9090,
            "gobilda_steps_path": "C:\\goBILDA",
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data))

        config = RoboticsConfig.load(str(config_path))

        assert config.default_unit == "inch"
        assert config.server_port == 9090
        assert config.gobilda_steps_path == "C:\\goBILDA"

    def test_load_missing_file_returns_defaults(self, tmp_path):
        config = RoboticsConfig.load(str(tmp_path / "nonexistent.json"))

        assert config.default_unit == "mm"

    def test_save_and_load_roundtrip(self, tmp_path):
        config = RoboticsConfig(
            default_unit="inch",
            server_port=9090,
            server_api_key="test-key",
        )
        config_path = str(tmp_path / "config.json")
        config.save(config_path)

        loaded = RoboticsConfig.load(config_path)

        assert loaded.default_unit == "inch"
        assert loaded.server_port == 9090
        assert loaded.server_api_key == "test-key"

    def test_to_dict(self):
        config = RoboticsConfig()
        d = config.to_dict()

        assert isinstance(d, dict)
        assert d["default_unit"] == "mm"
        assert "server_port" in d

    def test_update(self):
        config = RoboticsConfig()
        config.update(default_unit="cm", server_port=7777)

        assert config.default_unit == "cm"
        assert config.server_port == 7777

    def test_update_unknown_key_ignored(self):
        config = RoboticsConfig()
        config.update(nonexistent_key="value")
        # Should not raise, just log a warning

    def test_get_log_level_int(self):
        config = RoboticsConfig(log_level="DEBUG")

        import logging
        assert config.get_log_level_int() == logging.DEBUG


class TestConfigNewFields:
    """Test the new fields added for Phase 1."""

    def test_server_fields_defaults(self):
        config = RoboticsConfig()

        assert config.server_host == "0.0.0.0"
        assert config.server_port == 8585
        assert config.server_api_key == ""

    def test_gobilda_fields_defaults(self):
        config = RoboticsConfig()

        assert config.gobilda_steps_path == ""
        assert config.gobilda_profiles_path == ""

    def test_output_path_default(self):
        config = RoboticsConfig()

        assert config.output_path == ""
