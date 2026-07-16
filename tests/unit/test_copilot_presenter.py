"""Tests for copilot display formatting — pure string functions."""

from unittest.mock import MagicMock

import pytest

from robotics_design_advisor.copilot.models import (
    CopilotState,
    DesignSummary,
    PartPlacement,
    SubsystemProposal,
    SubsystemResult,
)
from robotics_design_advisor.copilot.presenter import (
    format_progress,
    format_proposal,
    format_summary,
)
from robotics_design_advisor.solidworks.placement import Position


def _make_proposal() -> SubsystemProposal:
    pos = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)
    return SubsystemProposal(
        subsystem="drivetrain",
        parts=(
            PartPlacement(
                sku="5202-0002-0019",
                name="goBILDA Yellow Jacket Motor",
                step_path="/parts/5202-0002-0019.STEP",
                position=pos,
                quantity=4,
            ),
            PartPlacement(
                sku="3209-0001-0001",
                name="goBILDA Strafer Chassis Kit",
                step_path="/parts/3209-0001-0001.STEP",
                position=pos,
                quantity=1,
            ),
        ),
        rationale="Mecanum drivetrain with 4 motors for omni movement",
        estimated_cost_usd=379.95,
        estimated_weight_g=5420.0,
    )


class TestFormatProposal:
    def test_includes_subsystem_name(self):
        output = format_proposal(_make_proposal())
        assert "drivetrain" in output.lower() or "Drivetrain" in output

    def test_includes_part_skus(self):
        output = format_proposal(_make_proposal())
        assert "5202-0002-0019" in output
        assert "3209-0001-0001" in output

    def test_includes_cost(self):
        output = format_proposal(_make_proposal())
        assert "379.95" in output

    def test_includes_rationale(self):
        output = format_proposal(_make_proposal())
        assert "Mecanum" in output or "mecanum" in output


class TestFormatProgress:
    def test_shows_current_phase(self):
        state = CopilotState(
            current_phase=2,
            approved_subsystems=(
                SubsystemResult(subsystem="drivetrain", approved=True, component_names=(), notes=""),
                SubsystemResult(subsystem="intake", approved=True, component_names=(), notes=""),
            ),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        output = format_progress(state)
        assert "drivetrain" in output.lower()
        assert "scorer" in output.lower()

    def test_first_phase(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        output = format_progress(state)
        assert "drivetrain" in output.lower()

    def test_all_phases_complete(self):
        results = tuple(
            SubsystemResult(subsystem=s, approved=True, component_names=(), notes="")
            for s in ("drivetrain", "intake", "scorer", "endgame", "electronics")
        )
        state = CopilotState(
            current_phase=5,
            approved_subsystems=results,
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        output = format_progress(state)
        assert "complete" in output.lower() or "done" in output.lower()


class TestFormatSummary:
    def test_includes_totals(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=12,
            total_cost_usd=899.50,
            total_weight_g=8500.0,
            subsystems_completed=("drivetrain", "intake", "scorer"),
            subsystems_skipped=("endgame", "electronics"),
            warnings=("Weight approaching limit",),
        )
        output = format_summary(summary)
        assert "12" in output
        assert "899.50" in output or "899.5" in output
        assert "8500" in output

    def test_includes_warnings(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=5,
            total_cost_usd=100.0,
            total_weight_g=1000.0,
            subsystems_completed=("drivetrain",),
            subsystems_skipped=(),
            warnings=("Weight approaching limit",),
        )
        output = format_summary(summary)
        assert "Weight approaching limit" in output

    def test_includes_assembly_path(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=0,
            total_cost_usd=0.0,
            total_weight_g=0.0,
            subsystems_completed=(),
            subsystems_skipped=(),
            warnings=(),
        )
        output = format_summary(summary)
        assert "robot.SLDASM" in output
