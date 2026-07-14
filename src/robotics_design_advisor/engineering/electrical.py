"""Electrical engineering calculations for FTC/FRC robot design.

Pure functions — no side effects, no I/O.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path

from ._path_safety import safe_resolve
from .models import HubSpec, MotorSpec, PortAllocation, PowerBudget, WireGaugeResult

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent


def load_motor_specs(family_file: str = "motor_data/gobilda_yellow_jacket.json") -> list[MotorSpec]:
    """Load motor specs from a JSON file.

    Raises
    ------
    ValueError
        If the path escapes the data directory or the JSON is malformed.
    """
    path = safe_resolve(_DATA_DIR, family_file)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        raise FileNotFoundError(f"Motor data file not found: '{family_file}'") from None

    voltage = data.get("voltage_nominal", 12.0)
    variants = data.get("variants")
    if not isinstance(variants, list):
        raise ValueError(f"Motor data file '{family_file}' missing 'variants' list")

    return [
        MotorSpec(
            sku=v["sku"],
            name=v["name"],
            gear_ratio=v["gear_ratio"],
            free_speed_rpm=v["free_speed_rpm"],
            stall_torque_kg_cm=v["stall_torque_kg_cm"],
            stall_current_a=v["stall_current_a"],
            free_current_a=v["free_current_a"],
            encoder_ppr=v["encoder_ppr"],
            shaft_type=v["shaft_type"],
            weight_grams=v["weight_grams"],
            voltage_nominal=voltage,
        )
        for v in variants
    ]


def load_hub_spec(hub_file: str = "hub_data/rev_control_hub.json") -> HubSpec:
    """Load hub specs from a JSON file.

    Raises
    ------
    ValueError
        If the path escapes the data directory or the JSON is malformed.
    """
    path = safe_resolve(_DATA_DIR, hub_file)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        raise FileNotFoundError(f"Hub data file not found: '{hub_file}'") from None

    dims_raw = data.get("dimensions_mm", [101.6, 63.5, 25.4])
    if not isinstance(dims_raw, list) or len(dims_raw) != 3:
        raise ValueError(f"Hub '{hub_file}': dimensions_mm must be a list of 3 numbers")

    return HubSpec(
        name=data["name"],
        sku=data["sku"],
        weight_grams=data["weight_grams"],
        motor_ports=data["motor_ports"],
        motor_current_continuous_a=data["motor_current_continuous_a"],
        motor_current_max_a=data["motor_current_max_a"],
        servo_ports=data["servo_ports"],
        servo_current_total_a=data["servo_current_total_a"],
        encoder_ports=data["encoder_ports"],
        i2c_buses=data["i2c_buses"],
        digital_ports=data["digital_ports"],
        analog_ports=data["analog_ports"],
        has_imu=data.get("has_imu", False),
        dimensions_mm=tuple(dims_raw),
    )


def find_motor_by_sku(motors: Sequence[MotorSpec], sku: str) -> MotorSpec | None:
    """Find a motor by SKU in a list of specs."""
    for m in motors:
        if m.sku == sku:
            return m
    return None


def find_motor_by_ratio(motors: Sequence[MotorSpec], ratio: float, tolerance: float = 0.5) -> MotorSpec | None:
    """Find the motor closest to the given gear ratio."""
    best: MotorSpec | None = None
    best_diff = float("inf")
    for m in motors:
        diff = abs(m.gear_ratio - ratio)
        if diff < best_diff and diff <= tolerance:
            best = m
            best_diff = diff
    return best


# ---------------------------------------------------------------------------
# Power budget
# ---------------------------------------------------------------------------

def analyze_power_budget(
    motors: Sequence[tuple[MotorSpec, int]],
    hub: HubSpec | None = None,
) -> PowerBudget:
    """Analyse the electrical power budget for a set of motors.

    Parameters
    ----------
    motors : sequence of (MotorSpec, count) tuples
        Each motor type and how many are used.
    hub : HubSpec | None
        Hub to check against (uses REV defaults if None).
    """
    total_count = sum(count for _, count in motors)
    total_stall = sum(m.stall_current_a * count for m, count in motors)
    total_free = sum(m.free_current_a * count for m, count in motors)

    # Typical operating current is ~30% of stall for drive, ~20% for mechanisms
    typical = sum(
        (m.free_current_a + 0.25 * (m.stall_current_a - m.free_current_a)) * count
        for m, count in motors
    )

    fuse_limit = 20.0  # REV hub fuse rating
    if hub is not None:
        fuse_limit = hub.motor_current_max_a

    motor_ports_per_hub = 4 if hub is None else hub.motor_ports
    hub_count = math.ceil(total_count / motor_ports_per_hub) if total_count > 0 else 1

    warnings: list[str] = []
    within_budget = True

    if total_stall > fuse_limit * hub_count:
        warnings.append(
            f"Total stall current {total_stall:.1f}A exceeds "
            f"{fuse_limit * hub_count:.0f}A fuse capacity across {hub_count} hub(s). "
            "This is normal for multi-motor drivetrains — stall only occurs "
            "during hard impacts or when wheels are locked."
        )

    if typical > fuse_limit * hub_count * 0.8:
        warnings.append(
            f"Typical operating current {typical:.1f}A is close to "
            f"fuse limit — risk of brownout during heavy operation"
        )
        within_budget = False

    if total_count > 8:
        warnings.append(f"FTC allows maximum 8 DC motors, you have {total_count}")
        within_budget = False

    return PowerBudget(
        total_motors=total_count,
        total_stall_current_a=round(total_stall, 2),
        total_free_current_a=round(total_free, 2),
        typical_current_a=round(typical, 2),
        fuse_limit_a=fuse_limit,
        within_budget=within_budget,
        hub_count_needed=hub_count,
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Port allocation
# ---------------------------------------------------------------------------

def allocate_ports(
    motors: Sequence[tuple[str, str]],
    servos: Sequence[tuple[str, str]] = (),
    sensors: Sequence[tuple[str, str, str]] = (),
    hub: HubSpec | None = None,
) -> PortAllocation:
    """Allocate devices to hub ports.

    Parameters
    ----------
    motors : sequence of (device_name, purpose)
        e.g., [("motor_fl", "front_left_drive"), ...]
    servos : sequence of (device_name, purpose)
    sensors : sequence of (device_name, purpose, sensor_type)
        sensor_type: "encoder", "i2c", "digital", "analog"
    hub : HubSpec | None
    """
    motor_ports = 4 if hub is None else hub.motor_ports
    servo_ports = 6 if hub is None else hub.servo_ports

    assignments: list[tuple[str, str, str]] = []
    unassigned: list[str] = []
    hub_count = 1

    # Assign motors
    for i, (name, purpose) in enumerate(motors):
        hub_num = i // motor_ports + 1
        port = i % motor_ports
        hub_count = max(hub_count, hub_num)
        hub_label = "control_hub" if hub_num == 1 else f"expansion_hub_{hub_num - 1}"
        assignments.append((hub_label, f"motor_{port}", f"{name} ({purpose})"))

    # Assign servos
    for i, (name, purpose) in enumerate(servos):
        if i >= servo_ports * 2:  # max 2 hubs worth of servos
            unassigned.append(f"{name} ({purpose}) — no servo port available")
            continue
        hub_num = i // servo_ports + 1
        port = i % servo_ports
        hub_label = "control_hub" if hub_num == 1 else f"expansion_hub_{hub_num - 1}"
        assignments.append((hub_label, f"servo_{port}", f"{name} ({purpose})"))

    # Assign sensors
    sensor_port_limits: dict[str, int] = {
        "encoder": hub.encoder_ports if hub else 4,
        "i2c": hub.i2c_buses if hub else 4,
        "digital": hub.digital_ports if hub else 8,
        "analog": hub.analog_ports if hub else 4,
    }
    sensor_port_counters: dict[str, int] = {
        "encoder": 0, "i2c": 0, "digital": 0, "analog": 0,
    }
    for name, purpose, sensor_type in sensors:
        counter = sensor_port_counters.get(sensor_type, 0)
        limit = sensor_port_limits.get(sensor_type, 4)
        if counter >= limit:
            unassigned.append(f"{name} ({purpose}) — no {sensor_type} port available")
            continue
        assignments.append(
            ("control_hub", f"{sensor_type}_{counter}", f"{name} ({purpose})")
        )
        sensor_port_counters[sensor_type] = counter + 1

    warnings: list[str] = []
    if len(motors) > motor_ports * 2:
        warnings.append(
            f"Need {math.ceil(len(motors) / motor_ports)} hubs for {len(motors)} motors"
        )

    return PortAllocation(
        assignments=tuple(assignments),
        unassigned_devices=tuple(unassigned),
        hub_count=hub_count,
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Wire gauge
# ---------------------------------------------------------------------------

# AWG resistance per meter (approximate, for stranded copper at 20°C)
AWG_RESISTANCE_OHM_PER_M: dict[int, float] = {
    12: 0.00521,
    14: 0.00829,
    16: 0.01319,
    18: 0.02095,
    20: 0.03331,
    22: 0.05296,
}


def check_wire_gauge(
    current_a: float,
    length_mm: float,
    awg: int = 16,
    voltage: float = 12.0,
) -> WireGaugeResult:
    """Check voltage drop and adequacy for a wire gauge.

    Raises
    ------
    ValueError
        If the AWG is not in the supported table.
    """
    if awg not in AWG_RESISTANCE_OHM_PER_M:
        raise ValueError(
            f"Unsupported AWG {awg}. Supported: {sorted(AWG_RESISTANCE_OHM_PER_M.keys())}"
        )

    length_m = length_mm / 1000.0
    resistance = AWG_RESISTANCE_OHM_PER_M[awg]

    # Round trip (power + return)
    voltage_drop = 2 * current_a * resistance * length_m
    drop_pct = (voltage_drop / voltage) * 100.0

    adequate = drop_pct < 5.0

    recommendation = ""
    if not adequate:
        for test_awg in sorted(AWG_RESISTANCE_OHM_PER_M.keys()):
            test_drop = 2 * current_a * AWG_RESISTANCE_OHM_PER_M[test_awg] * length_m
            if (test_drop / voltage) * 100.0 < 5.0:
                recommendation = f"Use {test_awg} AWG or thicker"
                break

    return WireGaugeResult(
        awg=awg,
        voltage_drop_v=round(voltage_drop, 3),
        drop_pct=round(drop_pct, 1),
        adequate=adequate,
        recommendation=recommendation,
    )
