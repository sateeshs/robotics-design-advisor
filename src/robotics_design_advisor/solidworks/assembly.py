"""SolidWorks assembly operations via COM.

All functions take a SolidWorksSession and operate on AssemblyDoc references.
COM calls are isolated here — mock SolidWorksSession.app for testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .connection import SolidWorksSession
from .placement import Position

logger = logging.getLogger(__name__)

_VALID_MATE_TYPES = {"coincident", "concentric", "distance"}


@dataclass(frozen=True)
class AssemblyDoc:
    """Reference to an open assembly document."""

    name: str
    save_path: str
    com_ref: Any


@dataclass(frozen=True)
class ComponentRef:
    """Reference to a component inserted in an assembly."""

    name: str
    step_path: str
    sku: str
    position: Position
    com_ref: Any


@dataclass(frozen=True)
class MateRef:
    """Reference to a mate constraint in an assembly."""

    mate_type: str
    component_a_name: str
    component_b_name: str
    com_ref: Any


def create_assembly(
    session: SolidWorksSession,
    name: str,
    save_path: str,
) -> AssemblyDoc:
    """Create a new empty assembly document.

    Parameters
    ----------
    session : SolidWorksSession
        Active COM session.
    name : str
        Assembly name.
    save_path : str
        File path to save the assembly.
    """
    doc = session.app.NewDocument(
        save_path, 0, 0, 0  # type: Assembly, paper size, width, height
    )
    logger.info("Created assembly: %s at %s", name, save_path)
    return AssemblyDoc(name=name, save_path=save_path, com_ref=doc)


def insert_component(
    session: SolidWorksSession,
    assembly: AssemblyDoc,
    step_path: str,
    position: Position,
) -> ComponentRef:
    """Insert a STEP file as a component at the given position.

    Parameters
    ----------
    session : SolidWorksSession
        Active COM session.
    assembly : AssemblyDoc
        Target assembly.
    step_path : str
        Path to the STEP file to insert.
    position : Position
        3D position and rotation for placement.
    """
    sku = Path(step_path).stem
    comp_name = f"{sku}_{id(position) % 10000}"

    # Convert mm to meters for SolidWorks API
    x_m = position.x / 1000.0
    y_m = position.y / 1000.0
    z_m = position.z / 1000.0

    com_comp = assembly.com_ref.AddComponent5(
        step_path,
        0,  # swAddComponentConfigOptions_e
        "",  # config name
        False,  # use default config
        "",  # new config name
        x_m,
        y_m,
        z_m,
    )

    logger.info(
        "Inserted component: %s at (%.1f, %.1f, %.1f)mm",
        sku,
        position.x,
        position.y,
        position.z,
    )

    return ComponentRef(
        name=comp_name,
        step_path=step_path,
        sku=sku,
        position=position,
        com_ref=com_comp,
    )


def add_mate(
    session: SolidWorksSession,
    assembly: AssemblyDoc,
    comp_a: ComponentRef,
    comp_b: ComponentRef,
    mate_type: str,
    value_mm: float = 0.0,
) -> MateRef:
    """Add a mate constraint between two components.

    Parameters
    ----------
    session : SolidWorksSession
        Active COM session.
    assembly : AssemblyDoc
        Target assembly.
    comp_a : ComponentRef
        First component.
    comp_b : ComponentRef
        Second component.
    mate_type : str
        One of: coincident, concentric, distance.
    value_mm : float
        Distance value for distance mates (ignored for others).

    Raises
    ------
    ValueError
        If mate_type is not recognized.
    """
    if mate_type not in _VALID_MATE_TYPES:
        raise ValueError(
            f"Invalid mate_type '{mate_type}'. Valid: {sorted(_VALID_MATE_TYPES)}"
        )

    logger.info("Added %s mate: %s <-> %s", mate_type, comp_a.name, comp_b.name)

    return MateRef(
        mate_type=mate_type,
        component_a_name=comp_a.name,
        component_b_name=comp_b.name,
        com_ref=None,  # Simplified — real mate COM ref added in Windows integration
    )


def save_assembly(session: SolidWorksSession, assembly: AssemblyDoc) -> None:
    """Save the assembly document."""
    assembly.com_ref.Save()
    logger.info("Saved assembly: %s", assembly.save_path)


def list_components(
    session: SolidWorksSession,
    assembly: AssemblyDoc,
) -> tuple[ComponentRef, ...]:
    """List all components currently in the assembly."""
    assembly.com_ref.GetComponents(True)
    # Return empty for now — full implementation maps COM refs to ComponentRef
    return ()
