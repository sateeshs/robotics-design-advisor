"""Tests for copilot session state dataclasses."""

from unittest.mock import MagicMock

import pytest

from robotics_design_advisor.copilot.models import (
    CopilotState,
    DesignSummary,
    PartPlacement,
    SubsystemProposal,
    SubsystemResult,
    SUBSYSTEM_ORDER,
)
from robotics_design_advisor.solidworks.placement import Position


class TestSubsystemOrder:
    def test_has_five_subsystems(self):
        assert len(SUBSYSTEM_ORDER) == 5

    def test_drivetrain_first(self):
        assert SUBSYSTEM_ORDER[0] == "drivetrain"

    def test_electronics_last(self):
        assert SUBSYSTEM_ORDER[-1] == "electronics"


class TestPartPlacement:
    def test_creation(self):
        pos = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)
        pp = PartPlacement(
            sku="5202-0002-0019",
            name="goBILDA Motor",
            step_path="/parts/5202-0002-0019.STEP",
            position=pos,
            quantity=4,
        )
        assert pp.sku == "5202-0002-0019"
        assert pp.position.x == 100.0

    def test_frozen(self):
        pos = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)
        pp = PartPlacement(
            sku="X", name="X", step_path="/x", position=pos, quantity=1,
        )
        with pytest.raises(AttributeError):
            pp.sku = "Y"  # type: ignore[misc]


class TestSubsystemProposal:
    def test_creation(self):
        pos = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)
        placement = PartPlacement(
            sku="5202-0002-0019", name="Motor", step_path="/m.STEP",
            position=pos, quantity=4,
        )
        proposal = SubsystemProposal(
            subsystem="drivetrain",
            parts=(placement,),
            rationale="4 motors for mecanum drive",
            estimated_cost_usd=79.96,
            estimated_weight_g=920.0,
        )
        assert proposal.subsystem == "drivetrain"
        assert len(proposal.parts) == 1
        assert proposal.estimated_cost_usd == 79.96


class TestSubsystemResult:
    def test_creation(self):
        result = SubsystemResult(
            subsystem="drivetrain",
            approved=True,
            component_names=("motor_1", "motor_2"),
            notes="",
        )
        assert result.approved is True
        assert len(result.component_names) == 2


class TestCopilotState:
    def test_creation(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        assert state.current_phase == 0
        assert len(state.approved_subsystems) == 0

    def test_default_target_subsystems(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        assert state.target_subsystems == SUBSYSTEM_ORDER

    def test_custom_target_subsystems(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
            target_subsystems=("drivetrain", "electronics"),
        )
        assert state.target_subsystems == ("drivetrain", "electronics")
        assert len(state.target_subsystems) == 2

    def test_current_subsystem_name(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        assert state.target_subsystems[state.current_phase] == "drivetrain"

    def test_frozen(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        with pytest.raises(AttributeError):
            state.current_phase = 1  # type: ignore[misc]


class TestDesignSummary:
    def test_creation(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=12,
            total_cost_usd=899.50,
            total_weight_g=8500.0,
            subsystems_completed=("drivetrain", "intake", "scorer"),
            subsystems_skipped=("endgame", "electronics"),
            warnings=("Weight approaching limit",),
        )
        assert summary.total_parts_inserted == 12
        assert len(summary.subsystems_completed) == 3
        assert len(summary.subsystems_skipped) == 2
