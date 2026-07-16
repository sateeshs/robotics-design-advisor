"""Copilot session engine — orchestrates interactive design flow.

Each function takes state in, returns new state out (immutable).
Side effects (SolidWorks COM calls) only happen in approve_subsystem
and finish_session.
"""

from __future__ import annotations

from .models import (
    CopilotState,
    DesignSummary,
    PartPlacement,
    SubsystemProposal,
    SubsystemResult,
    SUBSYSTEM_ORDER,
)
from ..engineering.design_synthesizer import synthesize_design
from ..engineering.models import BOMItem, DesignSynthesis
from ..solidworks.assembly import (
    AssemblyDoc,
    create_assembly,
    insert_component,
    save_assembly,
)
from ..solidworks.connection import SolidWorksSession
from ..solidworks.placement import calculate_position


def start_session(
    season_file: str,
    team_level: str,
    sw_session: SolidWorksSession,
    save_path: str,
    subsystems: tuple[str, ...] | None = None,
    existing_assembly: AssemblyDoc | None = None,
) -> CopilotState:
    """Start a new design copilot session.

    Generates a DesignSynthesis and creates (or reuses) a SolidWorks assembly.
    Supports both full builds (all subsystems) and independent subsystem work.

    Parameters
    ----------
    season_file : str
        Enhanced season JSON filename.
    team_level : str
        "beginner", "intermediate", or "advanced".
    sw_session : SolidWorksSession
        Active SolidWorks COM session.
    save_path : str
        File path for the new assembly (ignored if existing_assembly given).
    subsystems : tuple[str, ...] | None
        Which subsystems to process. None means all (SUBSYSTEM_ORDER).
        Pass a subset like ("drivetrain",) for independent work.
    existing_assembly : AssemblyDoc | None
        If provided, add to this assembly instead of creating a new one.
        Enables incremental builds — work on subsystems independently
        and integrate them into the same assembly.
    """
    synthesis = synthesize_design(season_file, team_level)

    target: tuple[str, ...] = subsystems if subsystems is not None else SUBSYSTEM_ORDER

    # Validate requested subsystems before any COM calls
    valid = set(SUBSYSTEM_ORDER)
    for s in target:
        if s not in valid:
            raise ValueError(
                f"Unknown subsystem '{s}'. Valid: {sorted(valid)}"
            )

    if existing_assembly is not None:
        assembly = existing_assembly
    else:
        assembly = create_assembly(sw_session, synthesis.archetype_name, save_path)

    return CopilotState(
        current_phase=0,
        approved_subsystems=(),
        assembly_ref=assembly,
        design_synthesis=synthesis,
        session=sw_session,
        target_subsystems=target,
    )


def _filter_bom_by_subsystem(
    bom_items: tuple[BOMItem, ...],
    subsystem: str,
) -> tuple[BOMItem, ...]:
    """Filter BOM items belonging to a specific subsystem."""
    return tuple(item for item in bom_items if item.subsystem == subsystem)


def propose_subsystem(
    state: CopilotState,
) -> tuple[CopilotState, SubsystemProposal]:
    """Generate a proposal for the current subsystem.

    Raises
    ------
    ValueError
        If all target subsystems have been processed.
    """
    if state.current_phase >= len(state.target_subsystems):
        raise ValueError("All subsystems complete — call finish_session instead")

    subsystem = state.target_subsystems[state.current_phase]
    synthesis: DesignSynthesis = state.design_synthesis

    # Filter BOM items for this subsystem
    subsystem_items = _filter_bom_by_subsystem(synthesis.bom.items, subsystem)

    # Build placements with approximate positions
    placements: list[PartPlacement] = []
    total_parts = len(subsystem_items)
    for i, item in enumerate(subsystem_items):
        position = calculate_position(
            subsystem,
            i,
            max(total_parts, 1),
        )
        placements.append(PartPlacement(
            sku=item.sku,
            name=item.name,
            step_path=f"{item.sku}.STEP",  # resolved at insertion time
            position=position,
            quantity=item.quantity,
        ))

    # Calculate subsystem totals
    cost = sum(item.unit_price_usd * item.quantity for item in subsystem_items)
    weight = sum(100.0 * item.quantity for item in subsystem_items)  # rough estimate

    proposal = SubsystemProposal(
        subsystem=subsystem,
        parts=tuple(placements),
        rationale=f"{synthesis.archetype_name}: {subsystem} components",
        estimated_cost_usd=round(cost, 2),
        estimated_weight_g=round(weight, 1),
    )

    return (state, proposal)


def approve_subsystem(
    state: CopilotState,
    proposal: SubsystemProposal,
) -> tuple[CopilotState, SubsystemResult]:
    """Approve a proposal and insert parts into SolidWorks.

    This function inserts components via COM.
    """
    component_names: list[str] = []

    for placement in proposal.parts:
        for i in range(placement.quantity):
            position = calculate_position(
                proposal.subsystem,
                min(i, max(len(proposal.parts) - 1, 0)),
                max(len(proposal.parts), 1),
            )
            comp = insert_component(
                state.session,
                state.assembly_ref,
                placement.step_path,
                position,
            )
            component_names.append(comp.name)

    result = SubsystemResult(
        subsystem=proposal.subsystem,
        approved=True,
        component_names=tuple(component_names),
        notes="",
    )

    new_state = CopilotState(
        current_phase=state.current_phase + 1,
        approved_subsystems=state.approved_subsystems + (result,),
        assembly_ref=state.assembly_ref,
        design_synthesis=state.design_synthesis,
        session=state.session,
        target_subsystems=state.target_subsystems,
    )

    return (new_state, result)


def skip_subsystem(state: CopilotState) -> CopilotState:
    """Skip the current subsystem without inserting anything."""
    if state.current_phase >= len(state.target_subsystems):
        raise ValueError("All subsystems complete — cannot skip")

    subsystem = state.target_subsystems[state.current_phase]
    result = SubsystemResult(
        subsystem=subsystem,
        approved=False,
        component_names=(),
        notes="skipped",
    )

    return CopilotState(
        current_phase=state.current_phase + 1,
        approved_subsystems=state.approved_subsystems + (result,),
        assembly_ref=state.assembly_ref,
        design_synthesis=state.design_synthesis,
        session=state.session,
        target_subsystems=state.target_subsystems,
    )


def finish_session(state: CopilotState) -> DesignSummary:
    """Finalize the session — save assembly and return summary."""
    save_assembly(state.session, state.assembly_ref)

    completed = tuple(
        r.subsystem for r in state.approved_subsystems if r.approved
    )
    skipped = tuple(
        r.subsystem for r in state.approved_subsystems if not r.approved
    )
    total_parts = sum(
        len(r.component_names) for r in state.approved_subsystems if r.approved
    )

    synthesis: DesignSynthesis = state.design_synthesis

    return DesignSummary(
        assembly_path=state.assembly_ref.save_path,
        total_parts_inserted=total_parts,
        total_cost_usd=synthesis.bom.total_cost_usd,
        total_weight_g=synthesis.bom.total_weight_g,
        subsystems_completed=completed,
        subsystems_skipped=skipped,
        warnings=synthesis.warnings,
    )
