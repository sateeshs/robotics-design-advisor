"""Tests for autonomous coordination dataclasses."""

import math

from robotics_design_advisor.autonomous.models import (
    Action,
    AutonomousRoutine,
    FieldConfig,
    PathSegment,
    PlannedPath,
    Pose,
    SensorRecommendation,
    Zone,
)


class TestPose:
    def test_creation(self):
        p = Pose(x_mm=1000.0, y_mm=500.0, heading_deg=90.0)
        assert p.x_mm == 1000.0
        assert p.y_mm == 500.0
        assert p.heading_deg == 90.0

    def test_frozen(self):
        p = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        try:
            p.x_mm = 100.0  # type: ignore[misc]
            assert False, "Should raise"
        except AttributeError:
            pass


class TestZone:
    def test_creation(self):
        center = Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0)
        z = Zone(name="net_zone", center=center, radius_mm=300.0, zone_type="scoring")
        assert z.name == "net_zone"
        assert z.zone_type == "scoring"
        assert z.radius_mm == 300.0


class TestFieldConfig:
    def test_creation(self):
        center = Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0)
        zone = Zone(name="net_zone", center=center, radius_mm=300.0, zone_type="scoring")
        start = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        fc = FieldConfig(
            width_mm=3658.0,
            length_mm=3658.0,
            alliance="red",
            zones=(zone,),
            starting_positions=(start,),
        )
        assert fc.width_mm == 3658.0
        assert fc.alliance == "red"
        assert len(fc.zones) == 1


class TestPathSegment:
    def test_creation(self):
        s = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        e = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        seg = PathSegment(start=s, end=e, distance_mm=1000.0, estimated_time_s=2.0, segment_type="drive")
        assert seg.distance_mm == 1000.0
        assert seg.segment_type == "drive"


class TestPlannedPath:
    def test_creation(self):
        s = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        e = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        seg = PathSegment(start=s, end=e, distance_mm=1000.0, estimated_time_s=2.0, segment_type="drive")
        path = PlannedPath(
            segments=(seg,),
            total_distance_mm=1000.0,
            total_time_s=2.0,
            waypoints=(s, e),
        )
        assert path.total_distance_mm == 1000.0
        assert len(path.segments) == 1


class TestAction:
    def test_creation(self):
        a = Action(
            name="drive_to_basket",
            subsystem="drivetrain",
            duration_s=3.0,
            parameters={"target_x_mm": 600.0, "target_y_mm": 600.0},
            wait_for="",
            parallel_with="",
        )
        assert a.name == "drive_to_basket"
        assert a.subsystem == "drivetrain"
        assert a.duration_s == 3.0

    def test_frozen(self):
        a = Action(
            name="test",
            subsystem="drivetrain",
            duration_s=1.0,
            parameters={},
            wait_for="",
            parallel_with="",
        )
        try:
            a.name = "changed"  # type: ignore[misc]
            assert False, "Should raise"
        except AttributeError:
            pass


class TestAutonomousRoutine:
    def test_creation(self):
        a1 = Action(name="drive", subsystem="drivetrain", duration_s=3.0,
                     parameters={}, wait_for="", parallel_with="")
        a2 = Action(name="grab", subsystem="grabber", duration_s=1.0,
                     parameters={}, wait_for="sensor_trigger", parallel_with="")
        routine = AutonomousRoutine(
            name="2+0 basket auto",
            competition="FTC",
            actions=(a1, a2),
            total_time_s=4.0,
            time_margin_s=26.0,
            scoring_potential=16,
        )
        assert routine.name == "2+0 basket auto"
        assert routine.competition == "FTC"
        assert len(routine.actions) == 2
        assert routine.time_margin_s == 26.0


class TestSensorRecommendation:
    def test_creation(self):
        sr = SensorRecommendation(
            task="piece_detection",
            sensor_type="distance_tof",
            sensor_name="REV 2m Distance Sensor",
            mounting_location="claw_interior",
            rationale="Detects game piece presence in grabber",
        )
        assert sr.task == "piece_detection"
        assert sr.sensor_type == "distance_tof"
