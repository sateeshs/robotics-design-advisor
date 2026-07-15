"""Bill of materials generator for FTC/FRC robot designs.

Given design parameters (motor count, servo count, mechanisms needed),
generates a complete BOM with part SKUs, quantities, costs, and warnings.
Pure functions except for data constants.
"""

from __future__ import annotations

from typing import Any

from .models import BillOfMaterials, BOMItem

# --- Part catalog (representative goBILDA / REV prices) ---

_MOTOR_ITEM = BOMItem(
    sku="5202-0002-0019",
    name="goBILDA Yellow Jacket 19.2:1 Motor",
    quantity=1,
    unit_price_usd=19.99,
    category="motion",
    subsystem="drivetrain",
    notes="DC motor for drivetrain or mechanism",
)

_SERVO_ITEM = BOMItem(
    sku="2000-0025-0002",
    name="goBILDA Dual Mode Servo (25-2)",
    quantity=1,
    unit_price_usd=24.99,
    category="motion",
    subsystem="mechanism",
    notes="Standard servo for claw, pivot, or other",
)

_CONTROL_HUB = BOMItem(
    sku="REV-31-1595",
    name="REV Control Hub",
    quantity=1,
    unit_price_usd=249.99,
    category="electronics",
    subsystem="electronics",
    notes="Primary control hub with IMU",
)

_EXPANSION_HUB = BOMItem(
    sku="REV-31-1153",
    name="REV Expansion Hub",
    quantity=1,
    unit_price_usd=199.99,
    category="electronics",
    subsystem="electronics",
    notes="Additional hub for >4 motors or >6 servos",
)

_BATTERY = BOMItem(
    sku="REV-31-1302",
    name="REV 12V Slim Battery",
    quantity=1,
    unit_price_usd=59.99,
    category="electronics",
    subsystem="electronics",
    notes="Competition battery",
)

_CHASSIS_KIT = BOMItem(
    sku="3209-0001-0001",
    name="goBILDA Strafer Chassis Kit",
    quantity=1,
    unit_price_usd=299.99,
    category="structure",
    subsystem="drivetrain",
    notes="Base chassis with mecanum wheels and channel",
)

_LINEAR_SLIDE = BOMItem(
    sku="3418-0014-0200",
    name="goBILDA Low-Profile Linear Slide (200mm)",
    quantity=2,
    unit_price_usd=17.99,
    category="structure",
    subsystem="lift",
    notes="Linear slide pair for elevator mechanism",
)

_SLIDE_BELT = BOMItem(
    sku="3416-0014-0120",
    name="goBILDA GT2 Timing Belt + Pulleys",
    quantity=1,
    unit_price_usd=12.99,
    category="motion",
    subsystem="lift",
    notes="Belt drive for elevator actuation",
)

_FLYWHEEL = BOMItem(
    sku="3411-0014-0096",
    name="goBILDA 96mm Compliant Wheel (pair)",
    quantity=1,
    unit_price_usd=8.99,
    category="motion",
    subsystem="launcher",
    notes="Compliant wheels for flywheel launcher",
)

_LAUNCHER_MOTOR = BOMItem(
    sku="5202-0002-0005",
    name="goBILDA Yellow Jacket 5.2:1 Motor",
    quantity=2,
    unit_price_usd=19.99,
    category="motion",
    subsystem="launcher",
    notes="High-speed motors for flywheel launcher",
)

_HARDWARE_KIT = BOMItem(
    sku="2800-0004-0001",
    name="goBILDA Hardware Assortment",
    quantity=1,
    unit_price_usd=24.99,
    category="hardware",
    subsystem="general",
    notes="M4 bolts, nuts, standoffs, spacers",
)

_WIRING_KIT = BOMItem(
    sku="REV-31-1387",
    name="REV Wiring Kit (JST-VH + XT30)",
    quantity=1,
    unit_price_usd=14.99,
    category="electronics",
    subsystem="electronics",
    notes="Motor and power cables",
)

# Approximate weight per item category (grams)
_WEIGHT_MAP: dict[str, float] = {
    "goBILDA Yellow Jacket 19.2:1 Motor": 230.0,
    "goBILDA Yellow Jacket 5.2:1 Motor": 230.0,
    "goBILDA Dual Mode Servo (25-2)": 60.0,
    "REV Control Hub": 250.0,
    "REV Expansion Hub": 230.0,
    "REV 12V Slim Battery": 530.0,
    "goBILDA Strafer Chassis Kit": 4500.0,
    "goBILDA Low-Profile Linear Slide (200mm)": 180.0,
    "goBILDA GT2 Timing Belt + Pulleys": 50.0,
    "goBILDA 96mm Compliant Wheel (pair)": 120.0,
    "goBILDA Hardware Assortment": 200.0,
    "REV Wiring Kit (JST-VH + XT30)": 80.0,
}


def _item_with_quantity(template: BOMItem, quantity: int, subsystem: str = "") -> BOMItem:
    """Create a BOMItem from a template with updated quantity and optional subsystem."""
    return BOMItem(
        sku=template.sku,
        name=template.name,
        quantity=quantity,
        unit_price_usd=template.unit_price_usd,
        category=template.category,
        subsystem=subsystem if subsystem else template.subsystem,
        notes=template.notes,
    )


def generate_bom(
    archetype_name: str,
    motor_count: int,
    servo_count: int,
    has_lift: bool,
    has_launcher: bool,
    constraints: dict[str, Any],
) -> BillOfMaterials:
    """Generate a bill of materials for a robot design.

    Parameters
    ----------
    archetype_name : str
        Name of the design archetype.
    motor_count : int
        Total number of DC motors needed.
    servo_count : int
        Total number of servos needed.
    has_lift : bool
        Whether the design includes an elevator/lift.
    has_launcher : bool
        Whether the design includes a flywheel launcher.
    constraints : dict
        Optional constraint limits (max_motors, weight_limit_g, etc.).
    """
    items: list[BOMItem] = []

    # Chassis
    items.append(_CHASSIS_KIT)

    # Motors
    if motor_count > 0:
        items.append(_item_with_quantity(_MOTOR_ITEM, motor_count))

    # Servos
    if servo_count > 0:
        items.append(_item_with_quantity(_SERVO_ITEM, servo_count, "mechanism"))

    # Electronics
    items.append(_CONTROL_HUB)
    if motor_count > 4 or servo_count > 6:
        items.append(_EXPANSION_HUB)
    items.append(_BATTERY)
    items.append(_WIRING_KIT)

    # Lift mechanism
    if has_lift:
        items.append(_LINEAR_SLIDE)
        items.append(_SLIDE_BELT)

    # Launcher mechanism
    if has_launcher:
        items.append(_FLYWHEEL)
        items.append(_LAUNCHER_MOTOR)

    # Hardware
    items.append(_HARDWARE_KIT)

    # Calculate totals
    total_cost = sum(i.unit_price_usd * i.quantity for i in items)
    total_weight = sum(
        _WEIGHT_MAP.get(i.name, 100.0) * i.quantity
        for i in items
    )

    # Subsystem breakdown
    breakdown: dict[str, tuple[float, float, int]] = {}
    for item in items:
        cost = item.unit_price_usd * item.quantity
        weight = _WEIGHT_MAP.get(item.name, 100.0) * item.quantity
        if item.subsystem in breakdown:
            prev = breakdown[item.subsystem]
            breakdown[item.subsystem] = (
                round(prev[0] + cost, 2),
                round(prev[1] + weight, 1),
                prev[2] + 1,
            )
        else:
            breakdown[item.subsystem] = (round(cost, 2), round(weight, 1), 1)

    # Warnings
    warnings: list[str] = []
    max_motors = constraints.get("max_motors", 8)
    if motor_count > max_motors:
        warnings.append(
            f"Motor count ({motor_count}) exceeds limit ({max_motors})"
        )

    weight_limit = constraints.get("weight_limit_g")
    if weight_limit is not None and total_weight > weight_limit:
        warnings.append(
            f"Estimated weight ({total_weight:.0f}g) exceeds limit ({weight_limit}g)"
        )

    return BillOfMaterials(
        items=tuple(items),
        total_cost_usd=round(total_cost, 2),
        total_weight_g=round(total_weight, 1),
        warnings=tuple(warnings),
        subsystem_breakdown=breakdown,
    )
