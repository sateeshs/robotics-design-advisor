"""FRC competition rules and constraints.

Source: FIRST Robotics Competition Game Manual (general robot rules).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FRCConstraints:
    """FRC robot constraints (general rules, stable across seasons)."""

    # Size limits (mm)
    max_frame_perimeter_mm: float = 3048.0  # 120" perimeter
    max_height_mm: float = 1371.6  # 4'6" = 54"
    max_height_extended_mm: float = 1981.2  # varies by season, ~78"

    # Weight
    max_weight_kg: float = 56.7  # 125 lbs with bumpers
    max_weight_no_bumpers_kg: float = 52.16  # 115 lbs without bumpers
    weight_includes_battery: bool = True
    weight_includes_bumpers: bool = True

    # Motors — FRC allows more motor types and counts
    max_motor_power_budget: str = "circuit-based"  # No fixed motor count
    max_cim_equivalent: int = 6  # Legacy rule, modern is PDP-based
    allowed_motor_types: tuple[str, ...] = (
        "CIM",
        "Mini CIM",
        "NEO",
        "NEO 550",
        "Falcon 500",
        "Kraken X60",
        "REV Vortex",
    )

    # Electrical
    max_battery_count: int = 1
    battery_type: str = "12V 18Ah SLA"
    battery_voltage_nominal: float = 12.0
    main_breaker_a: float = 120.0
    max_40a_breaker_slots: int = 6
    max_30a_breaker_slots: int = 10
    max_20a_breaker_slots: int = 10

    # Safety
    max_voltage: float = 16.0
    requires_main_breaker: bool = True
    requires_battery_retention: bool = True
    sharp_edge_prohibited: bool = True
    bumpers_required: bool = True
    bumper_height_min_mm: float = 88.9   # 3.5"
    bumper_height_max_mm: float = 190.5  # 7.5" from floor

    # Pneumatics (optional)
    max_pneumatic_pressure_psi: float = 120.0
    max_working_pressure_psi: float = 60.0

    # Competition
    competition: str = "FRC"


# Singleton for convenience
FRC_RULES = FRCConstraints()
