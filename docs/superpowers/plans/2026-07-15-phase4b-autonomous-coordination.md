# Phase 4B: Autonomous Coordination Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python autonomous coordination layer that plans field paths, validates timing budgets, coordinates subsystem actions via state machines, and recommends sensors for FTC/FRC robots.

**Architecture:** New `autonomous/` package under `src/robotics_design_advisor/` with frozen dataclass models and pure calculation functions. `field.py` defines coordinate systems and zones for FTC/FRC fields. `path_planner.py` calculates point-to-point distances, turn times, and time budgets. `state_machine.py` validates action sequences with parallel/sequential coordination rules. `sensors.py` recommends sensors for autonomous tasks.

**Tech Stack:** Python 3.10+, pytest, pure math (no external dependencies)

## Global Constraints

- All dataclasses are `frozen=True` with `tuple` for sequences (immutability)
- All calculation functions are pure — no I/O, no side effects
- Units: mm for length, degrees for heading, seconds for time
- FTC field: 3658×3658 mm (144"×144"), auto period 30s
- FRC field: 16459×8229 mm (54'1"×27'), auto period 15s
- Functions must validate inputs and raise `ValueError` for invalid arguments
- Follow existing codebase patterns (`engineering/models.py`, `mechanisms/models.py`)
- Target: 80%+ test coverage

---

## File Structure

```
src/robotics_design_advisor/autonomous/
├── __init__.py              # Package exports
├── models.py                # Frozen dataclasses: Pose, Zone, FieldConfig, PathSegment,
│                            #   PlannedPath, Action, AutonomousRoutine, SensorRecommendation
├── field.py                 # FTC/FRC field configs, zone lookup, pose utilities
├── path_planner.py          # Point-to-point paths, turn time, time budgets, heading optimization
├── state_machine.py         # Validate action sequences, parallel/sequential rules, time budget checks
└── sensors.py               # Sensor recommendations per autonomous task

tests/unit/
├── test_autonomous_models.py
├── test_field.py
├── test_path_planner.py
├── test_state_machine.py
└── test_sensors.py
```

---

### Task 1: Autonomous Models

**Files:**
- Create: `src/robotics_design_advisor/autonomous/__init__.py`
- Create: `src/robotics_design_advisor/autonomous/models.py`
- Test: `tests/unit/test_autonomous_models.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Pose`, `Zone`, `FieldConfig`, `PathSegment`, `PlannedPath`, `Action`, `AutonomousRoutine`, `SensorRecommendation` — imported by all other autonomous modules

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_autonomous_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_autonomous_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'robotics_design_advisor.autonomous'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/autonomous/__init__.py
"""Autonomous coordination layer for FTC/FRC robot design."""
```

```python
# src/robotics_design_advisor/autonomous/models.py
"""Frozen dataclasses for autonomous coordination.

All models are immutable. Sequences use tuple, not list.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pose:
    """A 2D position with heading on the field."""
    x_mm: float
    y_mm: float
    heading_deg: float  # 0 = facing positive X


@dataclass(frozen=True)
class Zone:
    """A named region on the field."""
    name: str
    center: Pose
    radius_mm: float
    zone_type: str  # "scoring" | "pickup" | "parking" | "human_player"


@dataclass(frozen=True)
class FieldConfig:
    """Field dimensions, alliance, zones, and legal starting positions."""
    width_mm: float
    length_mm: float
    alliance: str  # "red" | "blue"
    zones: tuple[Zone, ...]
    starting_positions: tuple[Pose, ...]


@dataclass(frozen=True)
class PathSegment:
    """One segment of a planned path."""
    start: Pose
    end: Pose
    distance_mm: float
    estimated_time_s: float
    segment_type: str  # "drive" | "turn" | "strafe" | "spline"


@dataclass(frozen=True)
class PlannedPath:
    """A complete planned path with segments and timing."""
    segments: tuple[PathSegment, ...]
    total_distance_mm: float
    total_time_s: float
    waypoints: tuple[Pose, ...]


@dataclass(frozen=True)
class Action:
    """A single action in an autonomous routine."""
    name: str
    subsystem: str  # "drivetrain" | "arm" | "grabber" | "launcher"
    duration_s: float
    parameters: dict  # subsystem-specific params
    wait_for: str  # "" | "sensor_trigger" | "encoder_target" | "timer"
    parallel_with: str  # name of action that can run simultaneously, or ""


@dataclass(frozen=True)
class AutonomousRoutine:
    """A validated autonomous routine with timing and scoring estimate."""
    name: str
    competition: str  # "FTC" | "FRC"
    actions: tuple[Action, ...]
    total_time_s: float
    time_margin_s: float
    scoring_potential: int


@dataclass(frozen=True)
class SensorRecommendation:
    """A sensor recommendation for an autonomous task."""
    task: str
    sensor_type: str  # "distance_tof" | "color" | "imu" | "encoder" | "camera"
    sensor_name: str
    mounting_location: str
    rationale: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_autonomous_models.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/autonomous/__init__.py src/robotics_design_advisor/autonomous/models.py tests/unit/test_autonomous_models.py
git commit -m "feat(autonomous): add frozen dataclass models for field, paths, actions, sensors"
```

---

### Task 2: Field Configuration

**Files:**
- Create: `src/robotics_design_advisor/autonomous/field.py`
- Test: `tests/unit/test_field.py`

**Interfaces:**
- Consumes: `Pose`, `Zone`, `FieldConfig` from `autonomous/models.py`
- Produces: `ftc_field(alliance) -> FieldConfig`, `frc_field(alliance) -> FieldConfig`, `distance_between(a: Pose, b: Pose) -> float`, `angle_between(a: Pose, b: Pose) -> float`, `find_zone(field: FieldConfig, name: str) -> Zone | None`, `is_in_zone(pose: Pose, zone: Zone) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_field.py
"""Tests for field configuration and pose utilities."""

import math

import pytest

from robotics_design_advisor.autonomous.field import (
    FTC_AUTO_PERIOD_S,
    FRC_AUTO_PERIOD_S,
    angle_between,
    distance_between,
    find_zone,
    frc_field,
    ftc_field,
    is_in_zone,
)
from robotics_design_advisor.autonomous.models import FieldConfig, Pose, Zone


class TestFtcField:
    def test_dimensions(self):
        field = ftc_field("red")
        assert field.width_mm == 3658.0
        assert field.length_mm == 3658.0

    def test_alliance(self):
        assert ftc_field("red").alliance == "red"
        assert ftc_field("blue").alliance == "blue"

    def test_has_zones(self):
        field = ftc_field("red")
        assert len(field.zones) > 0

    def test_has_starting_positions(self):
        field = ftc_field("red")
        assert len(field.starting_positions) > 0

    def test_invalid_alliance_raises(self):
        with pytest.raises(ValueError, match="alliance"):
            ftc_field("green")


class TestFrcField:
    def test_dimensions(self):
        field = frc_field("red")
        assert field.width_mm == 16459.0
        assert field.length_mm == 8229.0

    def test_has_zones(self):
        field = frc_field("blue")
        assert len(field.zones) > 0


class TestDistanceBetween:
    def test_same_point(self):
        p = Pose(x_mm=100.0, y_mm=200.0, heading_deg=0.0)
        assert distance_between(p, p) == 0.0

    def test_horizontal(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        assert distance_between(a, b) == 1000.0

    def test_diagonal(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=3000.0, y_mm=4000.0, heading_deg=0.0)
        assert distance_between(a, b) == 5000.0  # 3-4-5 triangle


class TestAngleBetween:
    def test_east(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        assert abs(angle_between(a, b) - 0.0) < 0.1

    def test_north(self):
        a = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=0.0, y_mm=1000.0, heading_deg=0.0)
        assert abs(angle_between(a, b) - 90.0) < 0.1

    def test_west(self):
        a = Pose(x_mm=1000.0, y_mm=0.0, heading_deg=0.0)
        b = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        assert abs(angle_between(a, b) - 180.0) < 0.1

    def test_same_point_returns_zero(self):
        p = Pose(x_mm=100.0, y_mm=200.0, heading_deg=0.0)
        assert angle_between(p, p) == 0.0


class TestFindZone:
    def test_finds_existing_zone(self):
        field = ftc_field("red")
        zone = find_zone(field, field.zones[0].name)
        assert zone is not None
        assert zone.name == field.zones[0].name

    def test_returns_none_for_missing(self):
        field = ftc_field("red")
        assert find_zone(field, "nonexistent_zone") is None


class TestIsInZone:
    def test_center_is_in_zone(self):
        center = Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0)
        zone = Zone(name="test", center=center, radius_mm=300.0, zone_type="scoring")
        assert is_in_zone(center, zone) is True

    def test_outside_radius(self):
        center = Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0)
        zone = Zone(name="test", center=center, radius_mm=300.0, zone_type="scoring")
        far = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        assert is_in_zone(far, zone) is False

    def test_on_boundary(self):
        center = Pose(x_mm=0.0, y_mm=0.0, heading_deg=0.0)
        zone = Zone(name="test", center=center, radius_mm=500.0, zone_type="scoring")
        edge = Pose(x_mm=500.0, y_mm=0.0, heading_deg=0.0)
        assert is_in_zone(edge, zone) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_field.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/autonomous/field.py
"""Field coordinate system, zone definitions, and pose utilities.

Covers FTC (144"×144") and FRC (54'1"×27') fields.
Pure functions, no I/O.
"""

from __future__ import annotations

import math

from .models import FieldConfig, Pose, Zone

# Auto period durations
FTC_AUTO_PERIOD_S = 30.0
FRC_AUTO_PERIOD_S = 15.0

# Field dimensions in mm
_FTC_WIDTH_MM = 3658.0   # 144 inches
_FTC_LENGTH_MM = 3658.0  # 144 inches (square field)
_FRC_WIDTH_MM = 16459.0  # 54'1"
_FRC_LENGTH_MM = 8229.0  # 27'

_VALID_ALLIANCES = {"red", "blue"}


def ftc_field(alliance: str) -> FieldConfig:
    """Create a standard FTC field configuration.

    Parameters
    ----------
    alliance : str
        "red" or "blue".
    """
    if alliance not in _VALID_ALLIANCES:
        raise ValueError(f"alliance must be 'red' or 'blue', got '{alliance}'")

    zones = (
        Zone(name="net_zone",
             center=Pose(x_mm=600.0, y_mm=600.0, heading_deg=0.0),
             radius_mm=300.0, zone_type="scoring"),
        Zone(name="observation_zone",
             center=Pose(x_mm=3058.0, y_mm=600.0, heading_deg=0.0),
             radius_mm=300.0, zone_type="pickup"),
        Zone(name="high_basket",
             center=Pose(x_mm=300.0, y_mm=300.0, heading_deg=0.0),
             radius_mm=200.0, zone_type="scoring"),
        Zone(name="parking",
             center=Pose(x_mm=3058.0, y_mm=3058.0, heading_deg=0.0),
             radius_mm=300.0, zone_type="parking"),
    )

    if alliance == "red":
        starts = (
            Pose(x_mm=300.0, y_mm=1829.0, heading_deg=0.0),
            Pose(x_mm=300.0, y_mm=2743.0, heading_deg=0.0),
        )
    else:
        starts = (
            Pose(x_mm=3358.0, y_mm=1829.0, heading_deg=180.0),
            Pose(x_mm=3358.0, y_mm=2743.0, heading_deg=180.0),
        )

    return FieldConfig(
        width_mm=_FTC_WIDTH_MM,
        length_mm=_FTC_LENGTH_MM,
        alliance=alliance,
        zones=zones,
        starting_positions=starts,
    )


def frc_field(alliance: str) -> FieldConfig:
    """Create a standard FRC field configuration.

    Parameters
    ----------
    alliance : str
        "red" or "blue".
    """
    if alliance not in _VALID_ALLIANCES:
        raise ValueError(f"alliance must be 'red' or 'blue', got '{alliance}'")

    zones = (
        Zone(name="speaker",
             center=Pose(x_mm=600.0, y_mm=4114.0, heading_deg=0.0),
             radius_mm=500.0, zone_type="scoring"),
        Zone(name="amp",
             center=Pose(x_mm=1800.0, y_mm=7800.0, heading_deg=0.0),
             radius_mm=400.0, zone_type="scoring"),
        Zone(name="source",
             center=Pose(x_mm=15000.0, y_mm=1000.0, heading_deg=0.0),
             radius_mm=600.0, zone_type="pickup"),
    )

    if alliance == "red":
        starts = (
            Pose(x_mm=1000.0, y_mm=4114.0, heading_deg=0.0),
            Pose(x_mm=1000.0, y_mm=5500.0, heading_deg=0.0),
            Pose(x_mm=1000.0, y_mm=6500.0, heading_deg=0.0),
        )
    else:
        starts = (
            Pose(x_mm=15459.0, y_mm=4114.0, heading_deg=180.0),
            Pose(x_mm=15459.0, y_mm=5500.0, heading_deg=180.0),
            Pose(x_mm=15459.0, y_mm=6500.0, heading_deg=180.0),
        )

    return FieldConfig(
        width_mm=_FRC_WIDTH_MM,
        length_mm=_FRC_LENGTH_MM,
        alliance=alliance,
        zones=zones,
        starting_positions=starts,
    )


def distance_between(a: Pose, b: Pose) -> float:
    """Euclidean distance between two poses in mm."""
    dx = b.x_mm - a.x_mm
    dy = b.y_mm - a.y_mm
    return math.sqrt(dx * dx + dy * dy)


def angle_between(a: Pose, b: Pose) -> float:
    """Bearing from pose a to pose b in degrees (0 = east, 90 = north).

    Returns 0.0 if a and b are the same point.
    """
    dx = b.x_mm - a.x_mm
    dy = b.y_mm - a.y_mm
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.degrees(math.atan2(dy, dx)) % 360.0


def find_zone(field: FieldConfig, name: str) -> Zone | None:
    """Find a zone by name in the field configuration."""
    for zone in field.zones:
        if zone.name == name:
            return zone
    return None


def is_in_zone(pose: Pose, zone: Zone) -> bool:
    """Check if a pose is within a zone's radius."""
    dist = distance_between(pose, zone.center)
    return dist <= zone.radius_mm
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_field.py -v`
Expected: 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/autonomous/field.py tests/unit/test_field.py
git commit -m "feat(autonomous): add FTC/FRC field configs, pose utilities, zone lookup"
```

---

### Task 3: Path Planner

**Files:**
- Create: `src/robotics_design_advisor/autonomous/path_planner.py`
- Test: `tests/unit/test_path_planner.py`

**Interfaces:**
- Consumes: `Pose`, `PathSegment`, `PlannedPath` from `models.py`, `distance_between` and `angle_between` from `field.py`, `FTC_AUTO_PERIOD_S` and `FRC_AUTO_PERIOD_S` from `field.py`
- Produces: `plan_path(start: Pose, waypoints: tuple[Pose, ...], max_speed_mm_s: float, max_accel_mm_s2: float) -> PlannedPath`, `check_time_budget(path: PlannedPath, competition: str) -> tuple[bool, float]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_path_planner.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_path_planner.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/autonomous/path_planner.py
"""Path planning — point-to-point paths with time budgets.

Plans paths between waypoints using trapezoidal velocity profiles
and validates against FTC/FRC autonomous period time limits.
Pure functions, no I/O.
"""

from __future__ import annotations

import math

from .field import (
    FTC_AUTO_PERIOD_S,
    FRC_AUTO_PERIOD_S,
    angle_between,
    distance_between,
)
from .models import PathSegment, PlannedPath, Pose

TURN_SPEED_DEG_S = 180.0  # typical FTC robot: 180 deg/s turn rate
DEFAULT_ACCEL_MM_S2 = 1000.0  # reasonable FTC drivetrain acceleration

_COMPETITION_PERIODS: dict[str, float] = {
    "FTC": FTC_AUTO_PERIOD_S,
    "FRC": FRC_AUTO_PERIOD_S,
}


def _normalize_angle(deg: float) -> float:
    """Normalize angle to [-180, 180]."""
    deg = deg % 360.0
    if deg > 180.0:
        deg -= 360.0
    return deg


def _calc_drive_time(
    distance_mm: float,
    max_speed_mm_s: float,
    max_accel_mm_s2: float,
) -> float:
    """Calculate drive time using trapezoidal velocity profile."""
    if distance_mm <= 0:
        return 0.0

    accel_time = max_speed_mm_s / max_accel_mm_s2
    accel_distance = 0.5 * max_accel_mm_s2 * accel_time**2

    if 2 * accel_distance >= distance_mm:
        # Triangular profile
        return 2.0 * math.sqrt(distance_mm / max_accel_mm_s2)

    cruise_distance = distance_mm - 2 * accel_distance
    cruise_time = cruise_distance / max_speed_mm_s
    return 2 * accel_time + cruise_time


def plan_path(
    start: Pose,
    waypoints: tuple[Pose, ...],
    max_speed_mm_s: float,
    max_accel_mm_s2: float = DEFAULT_ACCEL_MM_S2,
) -> PlannedPath:
    """Plan a path through a sequence of waypoints.

    Generates drive and turn segments between consecutive waypoints.
    Uses trapezoidal velocity profile for drive time estimates.

    Parameters
    ----------
    start : Pose
        Starting position and heading.
    waypoints : tuple of Pose
        Sequence of target poses (must have at least one).
    max_speed_mm_s : float
        Maximum drive speed in mm/s (must be > 0).
    max_accel_mm_s2 : float
        Maximum acceleration in mm/s^2.
    """
    if not waypoints:
        raise ValueError("waypoints must not be empty")
    if max_speed_mm_s <= 0:
        raise ValueError(f"max_speed_mm_s must be positive, got {max_speed_mm_s}")
    if max_accel_mm_s2 <= 0:
        raise ValueError(f"max_accel_mm_s2 must be positive, got {max_accel_mm_s2}")

    segments: list[PathSegment] = []
    all_waypoints = [start] + list(waypoints)
    current = start
    current_heading = start.heading_deg

    for target in waypoints:
        dist = distance_between(current, target)

        # Turn segment: rotate to face target
        if dist > 0.1:  # skip turn for negligible distance
            target_bearing = angle_between(current, target)
            turn_delta = abs(_normalize_angle(target_bearing - current_heading))

            if turn_delta > 1.0:  # skip tiny turns
                turn_time = turn_delta / TURN_SPEED_DEG_S
                turn_end = Pose(
                    x_mm=current.x_mm,
                    y_mm=current.y_mm,
                    heading_deg=target_bearing,
                )
                segments.append(PathSegment(
                    start=current,
                    end=turn_end,
                    distance_mm=0.0,
                    estimated_time_s=round(turn_time, 3),
                    segment_type="turn",
                ))
                current_heading = target_bearing

        # Drive segment
        if dist > 0.1:
            drive_time = _calc_drive_time(dist, max_speed_mm_s, max_accel_mm_s2)
            drive_end = Pose(
                x_mm=target.x_mm,
                y_mm=target.y_mm,
                heading_deg=current_heading,
            )
            segments.append(PathSegment(
                start=current,
                end=drive_end,
                distance_mm=round(dist, 1),
                estimated_time_s=round(drive_time, 3),
                segment_type="drive",
            ))

        # Final heading adjustment if target has different heading
        final_heading_delta = abs(_normalize_angle(target.heading_deg - current_heading))
        if final_heading_delta > 1.0:
            turn_time = final_heading_delta / TURN_SPEED_DEG_S
            segments.append(PathSegment(
                start=Pose(x_mm=target.x_mm, y_mm=target.y_mm, heading_deg=current_heading),
                end=target,
                distance_mm=0.0,
                estimated_time_s=round(turn_time, 3),
                segment_type="turn",
            ))
            current_heading = target.heading_deg

        current = target
        current_heading = target.heading_deg

    total_dist = sum(s.distance_mm for s in segments)
    total_time = sum(s.estimated_time_s for s in segments)

    return PlannedPath(
        segments=tuple(segments),
        total_distance_mm=round(total_dist, 1),
        total_time_s=round(total_time, 3),
        waypoints=tuple(all_waypoints),
    )


def check_time_budget(
    path: PlannedPath,
    competition: str,
) -> tuple[bool, float]:
    """Check if a path fits within the auto period.

    Parameters
    ----------
    path : PlannedPath
        The planned path to validate.
    competition : str
        "FTC" or "FRC".

    Returns
    -------
    (within_budget, margin_s) : tuple[bool, float]
        Whether the path fits, and the time margin in seconds.
    """
    if competition not in _COMPETITION_PERIODS:
        raise ValueError(
            f"competition must be one of {sorted(_COMPETITION_PERIODS)}, got '{competition}'"
        )

    period = _COMPETITION_PERIODS[competition]
    margin = period - path.total_time_s
    return margin >= 0, round(margin, 3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_path_planner.py -v`
Expected: 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/autonomous/path_planner.py tests/unit/test_path_planner.py
git commit -m "feat(autonomous): add path planner — waypoint paths, turn segments, time budgets"
```

---

### Task 4: State Machine

**Files:**
- Create: `src/robotics_design_advisor/autonomous/state_machine.py`
- Test: `tests/unit/test_state_machine.py`

**Interfaces:**
- Consumes: `Action`, `AutonomousRoutine` from `models.py`, `FTC_AUTO_PERIOD_S`, `FRC_AUTO_PERIOD_S` from `field.py`
- Produces: `build_routine(name, competition, actions) -> AutonomousRoutine`, `validate_routine(routine) -> tuple[bool, tuple[str, ...]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_state_machine.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_state_machine.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/autonomous/state_machine.py
"""State machine — autonomous routine building and validation.

Validates action sequences for subsystem conflicts, timing budgets,
and parallel action rules. Pure functions, no I/O.
"""

from __future__ import annotations

from .field import FTC_AUTO_PERIOD_S, FRC_AUTO_PERIOD_S
from .models import Action, AutonomousRoutine

_COMPETITION_PERIODS: dict[str, float] = {
    "FTC": FTC_AUTO_PERIOD_S,
    "FRC": FRC_AUTO_PERIOD_S,
}


def _calc_total_time(actions: tuple[Action, ...]) -> float:
    """Calculate total time accounting for parallel actions.

    Parallel actions overlap: max(a, b) instead of a + b.
    """
    action_names = {a.name for a in actions}
    parallel_targets = {a.parallel_with for a in actions if a.parallel_with}
    consumed: set[str] = set()
    total = 0.0

    for action in actions:
        if action.name in consumed:
            continue

        # Find all actions parallel with this one
        parallel_group = [action]
        for other in actions:
            if other.parallel_with == action.name and other.name not in consumed:
                parallel_group.append(other)
                consumed.add(other.name)

        consumed.add(action.name)

        # If this action is parallel with another, it was already counted
        if action.parallel_with and action.parallel_with in action_names:
            continue

        group_time = max(a.duration_s for a in parallel_group)
        total += group_time

    return round(total, 3)


def build_routine(
    name: str,
    competition: str,
    actions: tuple[Action, ...],
    scoring_potential: int = 0,
) -> AutonomousRoutine:
    """Build an autonomous routine from a sequence of actions.

    Parameters
    ----------
    name : str
        Routine name (e.g. "2+0 basket auto").
    competition : str
        "FTC" or "FRC".
    actions : tuple of Action
        Ordered sequence of actions.
    scoring_potential : int
        Estimated points scored.
    """
    if not actions:
        raise ValueError("actions must not be empty")
    if competition not in _COMPETITION_PERIODS:
        raise ValueError(
            f"competition must be one of {sorted(_COMPETITION_PERIODS)}, got '{competition}'"
        )

    total_time = _calc_total_time(actions)
    period = _COMPETITION_PERIODS[competition]
    margin = round(period - total_time, 3)

    return AutonomousRoutine(
        name=name,
        competition=competition,
        actions=actions,
        total_time_s=total_time,
        time_margin_s=margin,
        scoring_potential=scoring_potential,
    )


def validate_routine(routine: AutonomousRoutine) -> tuple[bool, tuple[str, ...]]:
    """Validate an autonomous routine for conflicts and timing.

    Returns
    -------
    (valid, warnings) : tuple[bool, tuple[str, ...]]
        Whether the routine is valid, and any warning messages.
    """
    warnings: list[str] = []
    action_names = {a.name for a in routine.actions}

    # Check time budget
    period = _COMPETITION_PERIODS.get(routine.competition, 30.0)
    if routine.total_time_s > period:
        warnings.append(
            f"Total time {routine.total_time_s:.1f}s exceeds "
            f"{routine.competition} auto period ({period:.0f}s)"
        )

    for action in routine.actions:
        # Negative duration
        if action.duration_s < 0:
            warnings.append(
                f"Action '{action.name}' has negative duration ({action.duration_s}s)"
            )

        # Parallel reference check
        if action.parallel_with:
            if action.parallel_with not in action_names:
                warnings.append(
                    f"Action '{action.name}' references parallel action "
                    f"'{action.parallel_with}' which does not exist"
                )
            else:
                # Same-subsystem conflict check
                for other in routine.actions:
                    if other.name == action.parallel_with:
                        if other.subsystem == action.subsystem:
                            warnings.append(
                                f"Subsystem conflict: '{action.name}' and "
                                f"'{other.name}' both use '{action.subsystem}' "
                                f"but are marked as parallel"
                            )
                        break

    valid = len(warnings) == 0
    return valid, tuple(warnings)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_state_machine.py -v`
Expected: 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/autonomous/state_machine.py tests/unit/test_state_machine.py
git commit -m "feat(autonomous): add state machine — routine building, parallel actions, validation"
```

---

### Task 5: Sensor Recommendations

**Files:**
- Create: `src/robotics_design_advisor/autonomous/sensors.py`
- Test: `tests/unit/test_sensors.py`

**Interfaces:**
- Consumes: `SensorRecommendation` from `models.py`
- Produces: `recommend_sensors(tasks: tuple[str, ...]) -> tuple[SensorRecommendation, ...]`, `SENSOR_DATABASE: dict[str, SensorRecommendation]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_sensors.py
"""Tests for sensor recommendation engine."""

import pytest

from robotics_design_advisor.autonomous.models import SensorRecommendation
from robotics_design_advisor.autonomous.sensors import (
    SENSOR_DATABASE,
    recommend_sensors,
)


class TestSensorDatabase:
    def test_has_standard_tasks(self):
        expected_tasks = [
            "piece_detection",
            "distance_to_wall",
            "field_position",
            "heading",
            "line_detection",
            "target_alignment",
        ]
        for task in expected_tasks:
            assert task in SENSOR_DATABASE, f"Missing task: {task}"

    def test_all_entries_are_sensor_recommendations(self):
        for task, rec in SENSOR_DATABASE.items():
            assert isinstance(rec, SensorRecommendation)
            assert rec.task == task

    def test_sensor_fields_non_empty(self):
        for task, rec in SENSOR_DATABASE.items():
            assert rec.sensor_type, f"{task}: sensor_type is empty"
            assert rec.sensor_name, f"{task}: sensor_name is empty"
            assert rec.mounting_location, f"{task}: mounting_location is empty"
            assert rec.rationale, f"{task}: rationale is empty"


class TestRecommendSensors:
    def test_single_task(self):
        result = recommend_sensors(("piece_detection",))
        assert len(result) == 1
        assert result[0].task == "piece_detection"

    def test_multiple_tasks(self):
        result = recommend_sensors(("piece_detection", "heading", "distance_to_wall"))
        assert len(result) == 3
        tasks = {r.task for r in result}
        assert tasks == {"piece_detection", "heading", "distance_to_wall"}

    def test_all_results_are_sensor_recommendations(self):
        result = recommend_sensors(("piece_detection", "field_position"))
        assert all(isinstance(r, SensorRecommendation) for r in result)

    def test_unknown_task_skipped(self):
        result = recommend_sensors(("piece_detection", "teleportation"))
        assert len(result) == 1
        assert result[0].task == "piece_detection"

    def test_empty_tasks_returns_empty(self):
        result = recommend_sensors(())
        assert len(result) == 0
        assert isinstance(result, tuple)

    def test_all_known_tasks(self):
        all_tasks = tuple(SENSOR_DATABASE.keys())
        result = recommend_sensors(all_tasks)
        assert len(result) == len(all_tasks)

    def test_duplicate_tasks_deduplicated(self):
        result = recommend_sensors(("heading", "heading", "heading"))
        assert len(result) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_sensors.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/autonomous/sensors.py
"""Sensor recommendations for autonomous tasks.

Maps common FTC/FRC autonomous tasks to recommended sensors with
mounting locations and rationale. Pure functions, no I/O.
"""

from __future__ import annotations

from .models import SensorRecommendation

SENSOR_DATABASE: dict[str, SensorRecommendation] = {
    "piece_detection": SensorRecommendation(
        task="piece_detection",
        sensor_type="distance_tof",
        sensor_name="REV 2m Distance Sensor (Time of Flight)",
        mounting_location="claw_interior",
        rationale="Detects game piece presence in grabber via short-range distance reading. "
                  "Beam break alternative: mount across jaw opening.",
    ),
    "distance_to_wall": SensorRecommendation(
        task="distance_to_wall",
        sensor_type="distance_tof",
        sensor_name="REV 2m Distance Sensor",
        mounting_location="front_bumper",
        rationale="Measures distance to field walls for positioning. "
                  "Mount facing forward for approach control.",
    ),
    "field_position": SensorRecommendation(
        task="field_position",
        sensor_type="encoder",
        sensor_name="Dead wheel odometry (3x REV Through Bore Encoder)",
        mounting_location="chassis_underside",
        rationale="Three dead wheels (2 parallel + 1 perpendicular) track X/Y position. "
                  "Fuse with IMU heading for full field localization.",
    ),
    "heading": SensorRecommendation(
        task="heading",
        sensor_type="imu",
        sensor_name="REV Control Hub Built-in IMU (BNO055/BHI260AP)",
        mounting_location="chassis_center",
        rationale="Built into REV Control/Expansion Hub — no extra wiring. "
                  "Provides heading for turn control and odometry fusion.",
    ),
    "line_detection": SensorRecommendation(
        task="line_detection",
        sensor_type="color",
        sensor_name="REV Color Sensor V3",
        mounting_location="chassis_underside_front",
        rationale="Downward-facing color sensor detects field lines and tape. "
                  "Use for autonomous alignment at scoring positions.",
    ),
    "target_alignment": SensorRecommendation(
        task="target_alignment",
        sensor_type="camera",
        sensor_name="Logitech C270 or C920 + AprilTag pipeline",
        mounting_location="robot_front_upper",
        rationale="Webcam with AprilTag detection for target alignment. "
                  "Use EOCV or Limelight for processing. Mount high for clear sightlines.",
    ),
}


def recommend_sensors(
    tasks: tuple[str, ...],
) -> tuple[SensorRecommendation, ...]:
    """Recommend sensors for the given autonomous tasks.

    Unknown tasks are silently skipped. Duplicate tasks are deduplicated.

    Parameters
    ----------
    tasks : tuple of str
        Task names to get sensor recommendations for.
    """
    seen: set[str] = set()
    results: list[SensorRecommendation] = []
    for task in tasks:
        if task in SENSOR_DATABASE and task not in seen:
            results.append(SENSOR_DATABASE[task])
            seen.add(task)
    return tuple(results)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_sensors.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/autonomous/sensors.py tests/unit/test_sensors.py
git commit -m "feat(autonomous): add sensor recommendations — task-to-sensor mapping for FTC/FRC"
```

---

## Summary

| Task | Module | Tests | Capability |
|------|--------|-------|-----------|
| 1 | `models.py` | 10 | Frozen dataclasses for poses, zones, paths, actions, sensors |
| 2 | `field.py` | 16 | FTC/FRC field configs, pose math, zone lookup |
| 3 | `path_planner.py` | 11 | Waypoint paths, turn segments, time budgets |
| 4 | `state_machine.py` | 12 | Routine building, parallel actions, validation rules |
| 5 | `sensors.py` | 10 | Sensor recommendations per autonomous task |
| **Total** | **6 files** | **~59** | |
