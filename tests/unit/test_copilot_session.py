"""Tests for copilot session engine — COM adapter mocked."""

from unittest.mock import MagicMock, patch

import pytest

from robotics_design_advisor.copilot.models import (
    CopilotState,
    DesignSummary,
    SUBSYSTEM_ORDER,
    SubsystemProposal,
    SubsystemResult,
)
from robotics_design_advisor.copilot.session import (
    approve_subsystem,
    finish_session,
    propose_subsystem,
    skip_subsystem,
    start_session,
)
from robotics_design_advisor.engineering.models import (
    BillOfMaterials,
    BOMItem,
    DesignSynthesis,
    ScoringStrategy,
)
from robotics_design_advisor.solidworks.assembly import AssemblyDoc, ComponentRef
from robotics_design_advisor.solidworks.connection import SolidWorksSession
from robotics_design_advisor.solidworks.placement import Position


def _make_mock_synthesis() -> DesignSynthesis:
    strategy = ScoringStrategy(
        name="test",
        expected_auto_points=10,
        expected_teleop_points=30,
        expected_endgame_points=5,
        total_expected_points=45,
        required_mechanisms=("drivetrain", "grabber"),
        difficulty="intermediate",
        rationale="test",
    )
    motor_item = BOMItem(
        sku="5202-0002-0019",
        name="goBILDA Motor",
        quantity=4,
        unit_price_usd=19.99,
        category="motion",
        subsystem="drivetrain",
        notes="",
    )
    hub_item = BOMItem(
        sku="REV-31-1595",
        name="REV Control Hub",
        quantity=1,
        unit_price_usd=249.99,
        category="electronics",
        subsystem="electronics",
        notes="",
    )
    bom = BillOfMaterials(
        items=(motor_item, hub_item),
        total_cost_usd=329.95,
        total_weight_g=1170.0,
        warnings=(),
        subsystem_breakdown={},
    )
    return DesignSynthesis(
        season="INTO THE DEEP",
        competition="FTC",
        strategy=strategy,
        archetype_name="Test Bot",
        bom=bom,
        mechanism_notes=("test note",),
        autonomous_notes=("auto note",),
        warnings=(),
    )


def _make_mock_session() -> SolidWorksSession:
    return SolidWorksSession(app=MagicMock(), active_doc=None)


class TestStartSession:
    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_returns_initial_state(self, mock_create_asm, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        sw_session = _make_mock_session()
        state = start_session(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
            sw_session=sw_session,
            save_path="/tmp/robot.SLDASM",
        )
        assert isinstance(state, CopilotState)
        assert state.current_phase == 0
        assert len(state.approved_subsystems) == 0

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_stores_design_synthesis(self, mock_create_asm, mock_synth):
        synthesis = _make_mock_synthesis()
        mock_synth.return_value = synthesis
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        state = start_session(
            "ftc-2024-into-the-deep.json", "intermediate",
            _make_mock_session(), "/tmp/robot.SLDASM",
        )
        assert state.design_synthesis.season == "INTO THE DEEP"

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_single_subsystem_session(self, mock_create_asm, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        state = start_session(
            "ftc-2024-into-the-deep.json", "intermediate",
            _make_mock_session(), "/tmp/robot.SLDASM",
            subsystems=("drivetrain",),
        )
        assert state.target_subsystems == ("drivetrain",)
        assert len(state.target_subsystems) == 1

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    def test_existing_assembly_reuse(self, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        existing_asm = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        state = start_session(
            "ftc-2024-into-the-deep.json", "intermediate",
            _make_mock_session(), "/tmp/ignored.SLDASM",
            existing_assembly=existing_asm,
        )
        assert state.assembly_ref is existing_asm

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_invalid_subsystem_raises(self, mock_create_asm, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        with pytest.raises(ValueError, match="subsystem"):
            start_session(
                "ftc-2024-into-the-deep.json", "intermediate",
                _make_mock_session(), "/tmp/robot.SLDASM",
                subsystems=("nonexistent",),
            )


class TestProposeSubsystem:
    def test_returns_proposal_for_current_phase(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )

        new_state, proposal = propose_subsystem(state)
        assert isinstance(proposal, SubsystemProposal)
        assert proposal.subsystem == "drivetrain"

    def test_drivetrain_gets_motor_parts(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )

        _, proposal = propose_subsystem(state)
        skus = {p.sku for p in proposal.parts}
        assert "5202-0002-0019" in skus

    def test_raises_when_all_phases_done(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        results = tuple(
            SubsystemResult(subsystem=s, approved=True, component_names=(), notes="")
            for s in SUBSYSTEM_ORDER
        )
        state = CopilotState(
            current_phase=5,
            approved_subsystems=results,
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        with pytest.raises(ValueError, match="complete"):
            propose_subsystem(state)

    def test_single_subsystem_mode(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
            target_subsystems=("electronics",),
        )
        _, proposal = propose_subsystem(state)
        assert proposal.subsystem == "electronics"


class TestApproveSubsystem:
    def test_advances_phase(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        asm.com_ref.AddComponent5.return_value = MagicMock()

        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        _, proposal = propose_subsystem(state)
        new_state, result = approve_subsystem(state, proposal)

        assert new_state.current_phase == 1
        assert result.approved is True
        assert result.subsystem == "drivetrain"
        assert len(new_state.approved_subsystems) == 1

    def test_inserts_components(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        mock_comp = MagicMock()
        asm.com_ref.AddComponent5.return_value = mock_comp

        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        _, proposal = propose_subsystem(state)
        _, result = approve_subsystem(state, proposal)
        assert len(result.component_names) > 0


class TestSkipSubsystem:
    def test_advances_phase_without_inserting(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        new_state = skip_subsystem(state)
        assert new_state.current_phase == 1
        assert len(new_state.approved_subsystems) == 1
        assert new_state.approved_subsystems[0].approved is False

    def test_raises_when_all_phases_done(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=5,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        with pytest.raises(ValueError, match="complete"):
            skip_subsystem(state)


class TestFinishSession:
    def test_returns_design_summary(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        results = (
            SubsystemResult(subsystem="drivetrain", approved=True, component_names=("m1",), notes=""),
            SubsystemResult(subsystem="intake", approved=False, component_names=(), notes="skipped"),
        )
        state = CopilotState(
            current_phase=2,
            approved_subsystems=results,
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        summary = finish_session(state)
        assert isinstance(summary, DesignSummary)
        assert summary.assembly_path == "/tmp/robot.SLDASM"
        assert "drivetrain" in summary.subsystems_completed
        assert "intake" in summary.subsystems_skipped

    def test_calls_save(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        finish_session(state)
        asm.com_ref.Save.assert_called_once()
