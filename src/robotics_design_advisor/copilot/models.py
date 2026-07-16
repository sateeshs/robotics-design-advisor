"""Session state dataclasses for the design copilot.

All models are frozen for immutability. State transitions
return new instances rather than mutating existing ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..solidworks.placement import Position

# Build order: chassis first, mechanisms next, wiring last
SUBSYSTEM_ORDER: tuple[str, ...] = (
    "drivetrain",
    "intake",
    "scorer",
    "endgame",
    "electronics",
)


@dataclass(frozen=True)
class PartPlacement:
    """A BOM part resolved to a STEP path with a target position."""

    sku: str
    name: str
    step_path: str
    position: Position
    quantity: int


@dataclass(frozen=True)
class SubsystemProposal:
    """A recommended set of parts for one subsystem."""

    subsystem: str
    parts: tuple[PartPlacement, ...]
    rationale: str
    estimated_cost_usd: float
    estimated_weight_g: float


@dataclass(frozen=True)
class SubsystemResult:
    """Outcome of a subsystem approval/skip."""

    subsystem: str
    approved: bool
    component_names: tuple[str, ...]  # names of inserted components
    notes: str


@dataclass(frozen=True)
class CopilotState:
    """Immutable copilot session state.

    current_phase is an index into target_subsystems.
    target_subsystems defaults to SUBSYSTEM_ORDER but can be a
    subset for independent subsystem work.
    """

    current_phase: int  # index into target_subsystems
    approved_subsystems: tuple[SubsystemResult, ...]
    assembly_ref: Any  # AssemblyDoc
    design_synthesis: Any  # DesignSynthesis
    session: Any  # SolidWorksSession
    target_subsystems: tuple[str, ...] = SUBSYSTEM_ORDER  # which subsystems to process


@dataclass(frozen=True)
class DesignSummary:
    """Final output after all subsystems are processed."""

    assembly_path: str
    total_parts_inserted: int
    total_cost_usd: float
    total_weight_g: float
    subsystems_completed: tuple[str, ...]
    subsystems_skipped: tuple[str, ...]
    warnings: tuple[str, ...]
