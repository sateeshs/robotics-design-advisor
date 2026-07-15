"""Tests for motor selection by torque+speed requirement."""

import math
from pathlib import Path
from unittest.mock import patch

import pytest

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.motor_selection import (
    KG_CM_TO_NMM,
    load_motor_database,
    select_motor,
)


# --- Fixtures ---

def _make_motor(
    sku: str = "5202-0002-0051",
    name: str = "Yellow Jacket 50.9:1",
    gear_ratio: float = 50.9,
    free_speed_rpm: float = 117.0,
    stall_torque_kg_cm: float = 64.5,
    stall_current_a: float = 9.2,
    free_current_a: float = 0.25,
) -> MotorSpec:
    return MotorSpec(
        sku=sku,
        name=name,
        gear_ratio=gear_ratio,
        free_speed_rpm=free_speed_rpm,
        stall_torque_kg_cm=stall_torque_kg_cm,
        stall_current_a=stall_current_a,
        free_current_a=free_current_a,
        encoder_ppr=1425.1,
        shaft_type="6mm_D",
        weight_grams=470,
    )


SAMPLE_MOTORS = (
    _make_motor("5202-0002-0014", "YJ 13.7:1", 13.7, 435, 17.4, 9.2, 0.25),
    _make_motor("5202-0002-0019", "YJ 19.2:1", 19.2, 312, 24.3, 9.2, 0.25),
    _make_motor("5202-0002-0051", "YJ 50.9:1", 50.9, 117, 64.5, 9.2, 0.25),
    _make_motor("5202-0002-0071", "YJ 71.2:1", 71.2, 84, 90.2, 9.2, 0.25),
    _make_motor("5202-0002-0188", "YJ 188:1", 188.0, 30, 238.1, 9.2, 0.25),
)


class TestSelectMotor:
    def test_selects_motor_with_sufficient_torque(self):
        """A moderate torque need at moderate speed should pick ~50:1."""
        required_torque_nmm = 3000.0  # ~30 kg-cm
        required_rpm = 100.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.output_torque_nmm >= required_torque_nmm * 0.5  # usable torque
        assert result.torque_margin_pct >= 0.0

    def test_high_torque_selects_high_ratio(self):
        """Very high torque need should select the highest ratio motor."""
        required_torque_nmm = 10000.0
        required_rpm = 20.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.gear_ratio >= 71.2

    def test_high_speed_selects_low_ratio(self):
        """High speed need should select a low ratio motor."""
        required_torque_nmm = 500.0
        required_rpm = 300.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.gear_ratio <= 19.2

    def test_margin_above_zero_when_motor_sufficient(self):
        """When a motor can deliver, torque margin should be positive."""
        required_torque_nmm = 1000.0
        required_rpm = 80.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.torque_margin_pct > 0.0

    def test_returns_negative_margin_when_insufficient(self):
        """When no motor can deliver, best match has negative margin."""
        required_torque_nmm = 50000.0  # impossibly high
        required_rpm = 500.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.torque_margin_pct < 0.0

    def test_intermittent_duty_uses_higher_torque_fraction(self):
        result_cont = select_motor(3000.0, 100.0, SAMPLE_MOTORS, duty="continuous")
        result_int = select_motor(3000.0, 100.0, SAMPLE_MOTORS, duty="intermittent")
        # Intermittent allows using more of stall torque, so margin is higher
        assert result_int.torque_margin_pct >= result_cont.torque_margin_pct

    def test_empty_motors_raises(self):
        with pytest.raises(ValueError, match="No motors"):
            select_motor(1000.0, 100.0, ())

    def test_negative_torque_raises(self):
        with pytest.raises(ValueError, match="required_torque_nmm"):
            select_motor(-1.0, 100.0, SAMPLE_MOTORS)

    def test_negative_rpm_raises(self):
        with pytest.raises(ValueError, match="required_rpm"):
            select_motor(1000.0, -1.0, SAMPLE_MOTORS)


class TestLoadMotorDatabase:
    def test_loads_all_variants(self):
        motors = load_motor_database()
        assert len(motors) >= 8  # at least 8 Yellow Jacket variants in JSON
        assert all(isinstance(m, MotorSpec) for m in motors)

    def test_skus_are_unique(self):
        motors = load_motor_database()
        skus = [m.sku for m in motors]
        assert len(skus) == len(set(skus))

    def test_stall_torque_positive(self):
        motors = load_motor_database()
        assert all(m.stall_torque_kg_cm > 0 for m in motors)
