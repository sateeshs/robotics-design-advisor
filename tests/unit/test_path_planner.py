"""Tests for path planning and time budgeting."""

import math

import pytest

from robotics_design_advisor.autonomous.models import PlannedPath, Pose
from robotics_design_advisor.autonomous.path_planner import (
    TURN_SPEED_DEG_S,
    check_time_budget,
    plan_path,
)


class TestPlanPath:
    def test_single_segment_straight(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        path = plan_path(start, (end,), max_speed_mm_s=500.0)
        assert isinstance(path, PlannedPath)
        assert len(path.segments) >= 1
        assert path.total_distance_mm > 0
        assert path.total_time_s > 0

    def test_total_distance_matches_straight_line(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=3000.0, y_mm=4000.0, heading_deg=0.0)
        path = plan_path(start, (end,), max_speed_mm_s=1000.0)
        # Distance should be at least the straight-line 5000mm
        assert path.total_distance_mm >= 4999.0

    def test_multi_waypoint_path(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        w1 = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        w2 = Pose(x_mm=1000.0, y_mm=1000.0, heading_deg=90.0)
        path = plan_path(start, (w1, w2), max_speed_mm_s=500.0)
        assert len(path.waypoints) == 3  # start + 2 waypoints
        assert path.total_time_s > 0

    def test_turn_segment_included_when_heading_changes(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=90.0)
        path = plan_path(start, (end,), max_speed_mm_s=500.0)
        segment_types = [s.segment_type for s in path.segments]
        assert "turn" in segment_types

    def test_time_includes_acceleration(self):
        """With trapezoidal profile, time > distance/speed."""
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=2000.0, y_mm=0.0, heading_deg=0.0)
        path = plan_path(start, (end,), max_speed_mm_s=1000.0, max_accel_mm_s2=500.0)
        min_time = 2000.0 / 1000.0  # 2s at constant speed
        assert path.total_time_s > min_time

    def test_empty_waypoints_raises(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        with pytest.raises(ValueError, match="waypoints"):
            plan_path(start, (), max_speed_mm_s=500.0)

    def test_zero_speed_raises(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        with pytest.raises(ValueError, match="max_speed_mm_s"):
            plan_path(start, (end,), max_speed_mm_s=0.0)


class TestCheckTimeBudget:
    def test_ftc_within_budget(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=500.0, y_mm=0.0, heading_deg=0.0)
        path = plan_path(start, (end,), max_speed_mm_s=500.0)
        within, margin = check_time_budget(path, "FTC")
        assert within is True
        assert margin > 0

    def test_frc_within_budget(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=500.0, y_mm=0.0, heading_deg=0.0)
        path = plan_path(start, (end,), max_speed_mm_s=1000.0)
        within, margin = check_time_budget(path, "FRC")
        assert within is True
        assert margin > 0

    def test_over_budget_returns_false(self):
        # Very long path that will exceed 30s FTC auto
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        waypoints = tuple(
            Pose(x_mm=float(i * 3000), y_mm=0.0, heading_deg=0.0)
            for i in range(1, 20)
        )
        path = plan_path(start, waypoints, max_speed_mm_s=500.0)
        within, margin = check_time_budget(path, "FTC")
        assert within is False
        assert margin < 0

    def test_invalid_competition_raises(self):
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        end = Pose(x_mm=500.0, y_mm=0.0, heading_deg=0.0)
        path = plan_path(start, (end,), max_speed_mm_s=500.0)
        with pytest.raises(ValueError, match="competition"):
            check_time_budget(path, "VEX")
