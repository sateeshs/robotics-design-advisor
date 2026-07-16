"""Display formatting for copilot proposals, progress, and summaries.

Pure functions — no I/O, no side effects. Output is plain text
suitable for terminal, chat, or MCP tool responses.
"""

from __future__ import annotations

from .models import (
    CopilotState,
    DesignSummary,
    SubsystemProposal,
    SUBSYSTEM_ORDER,
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
        cost = part.quantity * _estimate_unit_price(part.sku)
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
    approved_names = {r.subsystem for r in state.approved_subsystems}

    for i, subsystem in enumerate(state.target_subsystems):
        if subsystem in approved_names:
            parts.append(f"{subsystem} [done]")
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


def _estimate_unit_price(sku: str) -> float:
    """Rough price estimate from SKU prefix. Internal helper."""
    prefix = sku.split("-")[0] if "-" in sku else sku[:4]
    # Very rough mapping — real prices come from BOM
    estimates: dict[str, float] = {
        "5202": 19.99,
        "2000": 24.99,
        "3209": 299.99,
        "REV": 249.99,
    }
    return estimates.get(prefix, 10.0)
