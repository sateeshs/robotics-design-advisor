"""Electronics placement engine for FTC/FRC robot design.

Suggests optimal positions for hubs, batteries, and sensors based on
mechanical constraints, CG impact, and wiring best practices.

Pure functions — no side effects, no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .electrical import allocate_ports
from .mechanics import calc_center_of_gravity
from .models import (
    ElectronicsLayout,
    ElectronicsPlacement,
    HubSpec,
)


# ---------------------------------------------------------------------------
# Placement rules
# ---------------------------------------------------------------------------

# Minimum separation between motor/power wires and data/signal wires (mm)
MIN_EMI_SEPARATION_MM = 25.0

# Default FTC robot footprint (mm)
DEFAULT_FOOTPRINT_MM = (457.0, 457.0)  # 18" × 18"

# Component weight estimates (grams) when not provided
_DEFAULT_WEIGHTS: dict[str, float] = {
    "control_hub": 230.0,
    "expansion_hub": 200.0,
    "battery": 530.0,  # REV 12V Slim Battery
    "power_distribution": 50.0,
    "switch": 30.0,
}


def _place_control_hub(
    footprint_mm: tuple[float, float],
    hub: HubSpec | None = None,
) -> ElectronicsPlacement:
    """Place the control hub centered and low for optimal CG."""
    center_x = footprint_mm[0] / 2.0
    center_z = footprint_mm[1] / 2.0

    hub_dims = hub.dimensions_mm if hub else (101.6, 63.5, 25.4)

    position = (center_x, hub_dims[2] / 2.0 + 5.0, center_z)

    return ElectronicsPlacement(
        component="control_hub",
        position_mm=position,
        mounting_face="top_of_baseplate",
        orientation="ports_facing_up",
        rationale=(
            "Centered for minimal CG offset. Low mounting reduces "
            "tipping risk. Ports up for easy cable access."
        ),
        wire_routes=(
            "Motor wires route along chassis rails to hub",
            f"Keep signal wires >{MIN_EMI_SEPARATION_MM}mm from motor wires",
        ),
        warnings=(),
    )


def _place_expansion_hub(
    footprint_mm: tuple[float, float],
    hub: HubSpec | None = None,
) -> ElectronicsPlacement:
    """Place expansion hub adjacent to control hub."""
    center_x = footprint_mm[0] / 2.0
    center_z = footprint_mm[1] / 2.0

    hub_dims = hub.dimensions_mm if hub else (101.6, 63.5, 25.4)

    offset_x = hub_dims[0] + 10.0  # 10mm gap between hubs
    position = (center_x + offset_x / 2.0, hub_dims[2] / 2.0 + 5.0, center_z)

    return ElectronicsPlacement(
        component="expansion_hub",
        position_mm=position,
        mounting_face="top_of_baseplate",
        orientation="ports_facing_up",
        rationale=(
            "Adjacent to control hub for short XT30 daisy-chain. "
            "Same height for consistent CG."
        ),
        wire_routes=(
            "XT30 power cable from control hub (keep short)",
            "USB or UART data cable to control hub",
        ),
        warnings=(),
    )


def _place_battery(
    footprint_mm: tuple[float, float],
) -> ElectronicsPlacement:
    """Place battery low and centered for optimal CG."""
    center_x = footprint_mm[0] / 2.0
    center_z = footprint_mm[1] / 2.0

    return ElectronicsPlacement(
        component="battery",
        position_mm=(center_x, 25.0, center_z - 60.0),
        mounting_face="baseplate",
        orientation="terminals_accessible",
        rationale=(
            "Low center placement minimizes CG height. "
            "Offset slightly toward rear for front mechanism clearance. "
            "Must be secured with Velcro strap or bracket (FTC rule)."
        ),
        wire_routes=(
            "XT30 power cable to control hub main power input",
            "Route power cable along chassis rail, secured with zip ties",
        ),
        warnings=(
            "Battery MUST be secured — loose batteries are an inspection failure",
            "Ensure battery is accessible for quick swap between matches",
        ),
    )


def _place_main_switch(
    footprint_mm: tuple[float, float],
) -> ElectronicsPlacement:
    """Place main power switch for easy access."""
    return ElectronicsPlacement(
        component="main_switch",
        position_mm=(footprint_mm[0] - 30.0, 50.0, footprint_mm[1] / 2.0),
        mounting_face="side_panel",
        orientation="toggle_accessible",
        rationale=(
            "Side-mounted for referee and team access. "
            "Must be reachable without removing any covers."
        ),
        wire_routes=(
            "Inline with battery-to-hub power cable",
        ),
        warnings=(
            "Switch must be clearly labeled and easy to operate",
        ),
    )


# ---------------------------------------------------------------------------
# Layout engine
# ---------------------------------------------------------------------------

def generate_electronics_layout(
    motor_assignments: Sequence[tuple[str, str]] = (),
    servo_assignments: Sequence[tuple[str, str]] = (),
    sensor_assignments: Sequence[tuple[str, str, str]] = (),
    hub: HubSpec | None = None,
    expansion_hub: HubSpec | None = None,
    footprint_mm: tuple[float, float] = DEFAULT_FOOTPRINT_MM,
    existing_components: Sequence[tuple[float, float, float, float]] = (),
) -> ElectronicsLayout:
    """Generate a complete electronics layout for the robot.

    Parameters
    ----------
    motor_assignments : sequence of (name, purpose)
    servo_assignments : sequence of (name, purpose)
    sensor_assignments : sequence of (name, purpose, type)
    hub : HubSpec | None
        Control hub spec (uses defaults if None).
    expansion_hub : HubSpec | None
        Expansion hub spec if needed.
    footprint_mm : (width, depth)
        Robot footprint.
    existing_components : sequence of (x, y, z, mass_grams)
        Already-placed mechanical components for CG calculation.
    """
    placements: list[ElectronicsPlacement] = []
    compliance_issues: list[str] = []

    # Place control hub
    ctrl_placement = _place_control_hub(footprint_mm, hub)
    placements.append(ctrl_placement)

    # Determine if expansion hub needed
    motor_ports = 4 if hub is None else hub.motor_ports
    needs_expansion = len(motor_assignments) > motor_ports

    if needs_expansion:
        exp_placement = _place_expansion_hub(footprint_mm, expansion_hub)
        placements.append(exp_placement)

    # Place battery
    batt_placement = _place_battery(footprint_mm)
    placements.append(batt_placement)

    # Place main switch
    switch_placement = _place_main_switch(footprint_mm)
    placements.append(switch_placement)

    # Calculate total electronics weight
    ctrl_weight = hub.weight_grams if hub else _DEFAULT_WEIGHTS["control_hub"]
    total_weight = ctrl_weight + _DEFAULT_WEIGHTS["battery"] + _DEFAULT_WEIGHTS["switch"]
    if needs_expansion:
        exp_weight = expansion_hub.weight_grams if expansion_hub else _DEFAULT_WEIGHTS["expansion_hub"]
        total_weight += exp_weight

    # Calculate CG shift from electronics
    electronics_cg_components: list[tuple[float, float, float, float]] = []
    component_weights = {
        "control_hub": ctrl_weight,
        "battery": _DEFAULT_WEIGHTS["battery"],
        "main_switch": _DEFAULT_WEIGHTS["switch"],
    }
    if needs_expansion:
        component_weights["expansion_hub"] = (
            expansion_hub.weight_grams if expansion_hub else _DEFAULT_WEIGHTS["expansion_hub"]
        )

    for p in placements:
        w = component_weights.get(p.component, 50.0)
        electronics_cg_components.append((*p.position_mm, w))

    # Combine with existing mechanical components
    all_components = list(existing_components) + electronics_cg_components
    cg = calc_center_of_gravity(all_components, footprint_mm)

    center_x = footprint_mm[0] / 2.0
    center_z = footprint_mm[1] / 2.0
    cg_shift = (
        round(cg.x_mm - center_x, 1),
        round(cg.y_mm, 1),
        round(cg.z_mm - center_z, 1),
    )

    # Compliance checks
    if not cg.within_footprint:
        compliance_issues.append(
            "Center of gravity falls outside robot footprint — "
            "redistribute weight or adjust electronics placement"
        )

    if cg.offset_from_center_mm > footprint_mm[0] * 0.25:
        compliance_issues.append(
            f"CG offset {cg.offset_from_center_mm:.0f}mm from center — "
            "robot may pull to one side during driving"
        )

    # Port allocation
    port_alloc = allocate_ports(
        motors=motor_assignments,
        servos=servo_assignments,
        sensors=sensor_assignments,
        hub=hub,
    )

    return ElectronicsLayout(
        placements=tuple(placements),
        total_weight_grams=round(total_weight, 1),
        cg_shift_mm=cg_shift,
        port_allocation=port_alloc,
        compliance_issues=tuple(compliance_issues),
    )


def check_wire_clearances(
    placements: Sequence[ElectronicsPlacement],
) -> list[str]:
    """Check for EMI clearance issues between placed components.

    Returns a list of warning strings.
    """
    warnings: list[str] = []

    hub_components = {"control_hub", "expansion_hub"}

    for hub_p in placements:
        if hub_p.component not in hub_components:
            continue
        for sig_p in placements:
            if sig_p.component in hub_components:
                continue
            dist = math.sqrt(
                sum(
                    (a - b) ** 2
                    for a, b in zip(hub_p.position_mm, sig_p.position_mm, strict=True)
                )
            )
            if dist < MIN_EMI_SEPARATION_MM:
                warnings.append(
                    f"{sig_p.component} is only {dist:.0f}mm from {hub_p.component} — "
                    f"maintain >{MIN_EMI_SEPARATION_MM:.0f}mm separation for signal integrity"
                )

    return warnings
