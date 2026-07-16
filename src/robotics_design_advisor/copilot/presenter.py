"""Display formatting for copilot proposals, progress, and summaries.

Pure functions — no I/O, no side effects. Output is plain text
suitable for terminal, chat, or MCP tool responses.
"""

from __future__ import annotations

from .models import (
    CopilotState,
    DesignSummary,
    SubsystemProposal,
)


def format_proposal(proposal: SubsystemProposal) -> str:
    """Format a subsystem proposal for display.

    Shows parts list with SKUs, quantities, costs, and rationale.
    """
    lines: list[str] = []
    lines.append(f"=== {proposal.subsystem.upper()} ===")
    lines.append("")
    lines.append(f"Rationale: {proposal.rationale}")
    lines.append("")
    lines.append("Parts:")
    for part in proposal.parts:
        lines.append(
            f"  - {part.name} (SKU: {part.sku}) x{part.quantity}"
        )
    lines.append("")
    lines.append(f"Estimated cost: ${proposal.estimated_cost_usd:.2f}")
    lines.append(f"Estimated weight: {proposal.estimated_weight_g:.0f}g")
    return "\n".join(lines)


def format_progress(state: CopilotState) -> str:
    """Show build progress across target subsystems."""
    parts: list[str] = []
    approved_names = {r.subsystem for r in state.approved_subsystems if r.approved}
    skipped_names = {r.subsystem for r in state.approved_subsystems if not r.approved}

    for i, subsystem in enumerate(state.target_subsystems):
        if subsystem in approved_names:
            parts.append(f"{subsystem} [done]")
        elif subsystem in skipped_names:
            parts.append(f"{subsystem} [skipped]")
        elif i == state.current_phase:
            parts.append(f"{subsystem} [current]")
        else:
            parts.append(subsystem)

    progress_line = " | ".join(parts)

    if state.current_phase >= len(state.target_subsystems):
        return f"Build complete: {progress_line}"

    return f"Progress: {progress_line}"


def format_summary(summary: DesignSummary) -> str:
    """Format the final design summary."""
    lines: list[str] = []
    lines.append("=== DESIGN SUMMARY ===")
    lines.append("")
    lines.append(f"Assembly: {summary.assembly_path}")
    lines.append(f"Parts inserted: {summary.total_parts_inserted}")
    lines.append(f"Total cost: ${summary.total_cost_usd:.2f}")
    lines.append(f"Total weight: {summary.total_weight_g:.0f}g")
    lines.append("")

    if summary.subsystems_completed:
        lines.append(f"Completed: {', '.join(summary.subsystems_completed)}")
    if summary.subsystems_skipped:
        lines.append(f"Skipped: {', '.join(summary.subsystems_skipped)}")

    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in summary.warnings:
            lines.append(f"  ! {w}")

    return "\n".join(lines)


