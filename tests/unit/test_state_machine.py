"""Tests for autonomous routine state machine validation."""

import pytest

from robotics_design_advisor.autonomous.models import Action, AutonomousRoutine
from robotics_design_advisor.autonomous.state_machine import (
    build_routine,
    validate_routine,
)


def _action(
    name: str = "test",
    subsystem: str = "drivetrain",
    duration: float = 1.0,
    wait_for: str = "",
    parallel_with: str = "",
) -> Action:
    return Action(
        name=name,
        subsystem=subsystem,
        duration_s=duration,
        parameters={},
        wait_for=wait_for,
        parallel_with=parallel_with,
    )


class TestBuildRoutine:
    def test_creates_routine(self):
        actions = (_action("drive", "drivetrain", 3.0), _action("grab", "grabber", 1.0))
        routine = build_routine("test_auto", "FTC", actions)
        assert isinstance(routine, AutonomousRoutine)
        assert routine.name == "test_auto"
        assert routine.competition == "FTC"
        assert len(routine.actions) == 2

    def test_total_time_sums_sequential_actions(self):
        actions = (_action("a1", "drivetrain", 3.0), _action("a2", "grabber", 2.0))
        routine = build_routine("test", "FTC", actions)
        assert routine.total_time_s == 5.0

    def test_parallel_actions_use_max_duration(self):
        a1 = _action("drive", "drivetrain", 3.0)
        a2 = _action("raise_arm", "arm", 2.0, parallel_with="drive")
        routine = build_routine("test", "FTC", (a1, a2))
        # Parallel: max(3.0, 2.0) = 3.0, not 5.0
        assert routine.total_time_s == 3.0

    def test_time_margin_ftc(self):
        actions = (_action("drive", "drivetrain", 5.0),)
        routine = build_routine("test", "FTC", actions)
        assert routine.time_margin_s == 25.0  # 30 - 5

    def test_time_margin_frc(self):
        actions = (_action("drive", "drivetrain", 5.0),)
        routine = build_routine("test", "FRC", actions)
        assert routine.time_margin_s == 10.0  # 15 - 5

    def test_empty_actions_raises(self):
        with pytest.raises(ValueError, match="actions"):
            build_routine("test", "FTC", ())

    def test_invalid_competition_raises(self):
        with pytest.raises(ValueError, match="competition"):
            build_routine("test", "VEX", (_action(),))


class TestValidateRoutine:
    def test_valid_routine_passes(self):
        actions = (_action("drive", "drivetrain", 3.0), _action("grab", "grabber", 1.0))
        routine = build_routine("test", "FTC", actions)
        valid, warnings = validate_routine(routine)
        assert valid is True
        assert len(warnings) == 0

    def test_over_time_budget_warns(self):
        # 35s > FTC 30s limit
        actions = (_action("long_drive", "drivetrain", 35.0),)
        routine = build_routine("test", "FTC", actions)
        valid, warnings = validate_routine(routine)
        assert valid is False
        any_time_warning = any("time" in w.lower() or "exceed" in w.lower() for w in warnings)
        assert any_time_warning

    def test_same_subsystem_parallel_warns(self):
        a1 = _action("drive_forward", "drivetrain", 3.0)
        a2 = _action("drive_back", "drivetrain", 2.0, parallel_with="drive_forward")
        routine = build_routine("test", "FTC", (a1, a2))
        valid, warnings = validate_routine(routine)
        any_conflict = any("subsystem" in w.lower() or "conflict" in w.lower() for w in warnings)
        assert any_conflict

    def test_parallel_ref_missing_warns(self):
        a1 = _action("grab", "grabber", 1.0, parallel_with="nonexistent")
        routine = build_routine("test", "FTC", (a1,))
        valid, warnings = validate_routine(routine)
        any_ref_warning = any("nonexistent" in w for w in warnings)
        assert any_ref_warning

    def test_negative_duration_warns(self):
        a1 = _action("bad", "drivetrain", -1.0)
        routine = build_routine("test", "FTC", (a1,))
        valid, warnings = validate_routine(routine)
        assert valid is False
        any_dur_warning = any("duration" in w.lower() for w in warnings)
        assert any_dur_warning
