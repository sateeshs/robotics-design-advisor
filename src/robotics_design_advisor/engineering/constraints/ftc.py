"""FTC competition rules and constraints.

Source: FIRST Tech Challenge Game Manual Part 1 (general robot rules).
These are structural/sizing/electrical limits — game-specific rules
live in season JSON files.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FTCConstraints:
    """FTC robot constraints (2024-2025 season rules, generally stable)."""

    # Size limits (mm)
    start_size_mm: tuple[float, float, float] = (457.2, 457.2, 457.2)  # 18"³
    max_width_mm: float = 508.0   # 20" expanded
    max_length_mm: float = 1066.8  # 42" expanded
    max_height_mm: float = 457.2  # 18" (no height expansion in most seasons)

    # Weight
    max_weight_kg: float = 19.05  # 42 lbs
    weight_includes_battery: bool = True

    # Motors
    max_dc_motors: int = 8
    max_servos: int = 12
    allowed_motor_brands: tuple[str, ...] = (
        "REV Robotics",
        "goBILDA",
        "TETRIX",
        "AndyMark NeveRest",
    )

    # Electrical
    max_battery_count: int = 1
    battery_type: str = "REV 12V Slim Battery"
    battery_voltage_nominal: float = 12.0
    max_hubs: int = 2  # 1 Control Hub + 1 Expansion Hub
    hub_fuse_a: float = 20.0

    # Safety
    max_voltage: float = 16.0
    requires_main_switch: bool = True
    requires_battery_retention: bool = True
    sharp_edge_prohibited: bool = True
    entanglement_check: bool = True

    # Competition
    competition: str = "FTC"


# Singleton for convenience
FTC_RULES = FTCConstraints()
