# Phase 4A: Mechanism Physics Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build pure-Python physics calculators for FTC/FRC robot mechanisms (grabber, launcher, lift, motion profiles) so Claude can recommend motors, validate designs, and compute real engineering parameters.

**Architecture:** New `mechanisms/` package under `src/robotics_design_advisor/` with frozen dataclass models and pure calculation functions. Each module takes primitive inputs (mass, distance, speed) and returns frozen dataclass results with physics calculations, motor recommendations, and design notes. Motor selection loads the existing `gobilda_yellow_jacket.json` database.

**Tech Stack:** Python 3.10+, pytest, pure math (no external dependencies)

## Global Constraints

- All dataclasses are `frozen=True` with `tuple` for sequences (immutability)
- All calculation functions are pure — no I/O, no side effects
- Units: mm for length, grams for mass, N for force, N-mm for torque, RPM for speed
- Motor data sourced from `src/robotics_design_advisor/engineering/motor_data/gobilda_yellow_jacket.json`
- Existing `engineering/models.py` already has `MotorSpec`, `MotorRecommendation`, `ArmAnalysis` — reuse, don't duplicate
- Existing `engineering/mechanics.py` has `calc_arm_torque`, `calc_elevator_force` — Phase 4A extends with richer outputs
- Constants: `GRAVITY_M_S2 = 9.80665` (already in `mechanics.py`)
- Functions must validate inputs and raise `ValueError` for invalid arguments
- Target: 80%+ test coverage

---

## File Structure

```
src/robotics_design_advisor/mechanisms/
├── __init__.py              # Package exports
├── models.py                # Frozen dataclasses: GrabberAnalysis, LauncherAnalysis,
│                            #   LiftAnalysis, MotionProfile, MotorMatch
├── motor_selection.py       # Load motor DB, find best motor+ratio for torque+speed requirement
├── grabber.py               # Grip force, servo torque, grip type selection
├── launcher.py              # Flywheel ballistics, catapult spring force, launch angles
├── lift.py                  # Elevator force, 4-bar arm torque, counterbalance, spool sizing
└── motion.py                # Encoder ticks, trapezoidal velocity profiles, PID starting points

tests/unit/
├── test_mechanism_models.py
├── test_motor_selection.py
├── test_grabber.py
├── test_launcher.py
├── test_lift.py
└── test_motion.py
```

---

### Task 1: Mechanism Models

**Files:**
- Create: `src/robotics_design_advisor/mechanisms/__init__.py`
- Create: `src/robotics_design_advisor/mechanisms/models.py`
- Test: `tests/unit/test_mechanism_models.py`

**Interfaces:**
- Consumes: nothing
- Produces: `GrabberAnalysis`, `LauncherAnalysis`, `LiftAnalysis`, `MotionProfile`, `MotorMatch` — imported by all other mechanism modules

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mechanism_models.py
"""Tests for mechanism physics dataclasses."""

from robotics_design_advisor.mechanisms.models import (
    GrabberAnalysis,
    LauncherAnalysis,
    LiftAnalysis,
    MotionProfile,
    MotorMatch,
)


class TestGrabberAnalysis:
    def test_creation(self):
        g = GrabberAnalysis(
            required_grip_force_n=5.0,
            required_torque_nmm=250.0,
            recommended_servo="goBILDA Torque Servo",
            jaw_opening_mm=45.0,
            grip_type="claw",
            hold_current_ma=200.0,
            notes=("Use rubber pads for grip.",),
        )
        assert g.required_grip_force_n == 5.0
        assert g.grip_type == "claw"
        assert len(g.notes) == 1

    def test_frozen(self):
        g = GrabberAnalysis(
            required_grip_force_n=5.0,
            required_torque_nmm=250.0,
            recommended_servo="goBILDA Torque Servo",
            jaw_opening_mm=45.0,
            grip_type="claw",
            hold_current_ma=200.0,
            notes=(),
        )
        try:
            g.grip_type = "roller_intake"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestLauncherAnalysis:
    def test_creation(self):
        la = LauncherAnalysis(
            launch_velocity_ms=5.0,
            launch_angle_deg=45.0,
            flywheel_rpm=3000.0,
            flywheel_diameter_mm=100.0,
            motor_recommendation="Yellow Jacket 5.2:1",
            spin_up_time_s=0.8,
            energy_per_shot_j=0.35,
            fire_rate_hz=2.0,
            catapult_spring_force_n=0.0,
            notes=(),
        )
        assert la.launch_velocity_ms == 5.0
        assert la.flywheel_rpm == 3000.0


class TestLiftAnalysis:
    def test_creation(self):
        li = LiftAnalysis(
            required_force_n=20.0,
            peak_force_n=30.0,
            required_torque_nmm=500.0,
            motor_recommendation="Yellow Jacket 50.9:1",
            gear_ratio=50.9,
            max_speed_mm_s=150.0,
            time_to_max_height_s=3.0,
            counterbalance_force_n=10.0,
            spool_diameter_mm=30.0,
            lift_type="elevator",
            notes=(),
        )
        assert li.required_force_n == 20.0
        assert li.lift_type == "elevator"


class TestMotionProfile:
    def test_creation(self):
        mp = MotionProfile(
            total_ticks=1000,
            cruise_velocity_tps=500.0,
            accel_ticks=200,
            decel_ticks=200,
            cruise_ticks=600,
            total_time_s=2.5,
            accel_time_s=0.5,
            suggested_kp=0.01,
            suggested_ki=0.0,
            suggested_kd=0.001,
            notes=(),
        )
        assert mp.total_ticks == 1000
        assert mp.accel_ticks + mp.decel_ticks + mp.cruise_ticks == mp.total_ticks


class TestMotorMatch:
    def test_creation(self):
        mm = MotorMatch(
            motor_name="Yellow Jacket 50.9:1",
            motor_sku="5202-0002-0051",
            base_rpm=117.0,
            stall_torque_nmm=6326.0,
            gear_ratio=50.9,
            output_rpm=117.0,
            output_torque_nmm=6326.0,
            torque_margin_pct=35.0,
            current_draw_a=3.0,
            notes=(),
        )
        assert mm.motor_sku == "5202-0002-0051"
        assert mm.torque_margin_pct == 35.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_mechanism_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'robotics_design_advisor.mechanisms'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/mechanisms/__init__.py
"""Mechanism physics engine for FTC/FRC robot design."""
```

```python
# src/robotics_design_advisor/mechanisms/models.py
"""Frozen dataclasses for mechanism physics calculations.

All models are immutable. Sequences use tuple, not list.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GrabberAnalysis:
    """Result of grabber/intake physics analysis."""
    required_grip_force_n: float
    required_torque_nmm: float
    recommended_servo: str
    jaw_opening_mm: float
    grip_type: str          # "claw" | "roller_intake" | "passive_funnel"
    hold_current_ma: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class LauncherAnalysis:
    """Result of launcher ballistics analysis."""
    launch_velocity_ms: float
    launch_angle_deg: float
    flywheel_rpm: float
    flywheel_diameter_mm: float
    motor_recommendation: str
    spin_up_time_s: float
    energy_per_shot_j: float
    fire_rate_hz: float
    catapult_spring_force_n: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class LiftAnalysis:
    """Result of lift/elevator/arm physics analysis."""
    required_force_n: float
    peak_force_n: float
    required_torque_nmm: float
    motor_recommendation: str
    gear_ratio: float
    max_speed_mm_s: float
    time_to_max_height_s: float
    counterbalance_force_n: float
    spool_diameter_mm: float
    lift_type: str          # "elevator" | "four_bar" | "arm" | "cascade"
    notes: tuple[str, ...]


@dataclass(frozen=True)
class MotionProfile:
    """Trapezoidal motion profile with encoder tick calculations."""
    total_ticks: int
    cruise_velocity_tps: float   # ticks per second
    accel_ticks: int
    decel_ticks: int
    cruise_ticks: int
    total_time_s: float
    accel_time_s: float
    suggested_kp: float
    suggested_ki: float
    suggested_kd: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class MotorMatch:
    """A motor matched to a specific torque+speed requirement."""
    motor_name: str
    motor_sku: str
    base_rpm: float
    stall_torque_nmm: float
    gear_ratio: float
    output_rpm: float
    output_torque_nmm: float
    torque_margin_pct: float
    current_draw_a: float
    notes: tuple[str, ...]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_mechanism_models.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/mechanisms/__init__.py src/robotics_design_advisor/mechanisms/models.py tests/unit/test_mechanism_models.py
git commit -m "feat(mechanisms): add frozen dataclass models for grabber, launcher, lift, motion, motor"
```

---

### Task 2: Motor Selection

**Files:**
- Create: `src/robotics_design_advisor/mechanisms/motor_selection.py`
- Test: `tests/unit/test_motor_selection.py`

**Interfaces:**
- Consumes: `MotorMatch` from `mechanisms/models.py`, `MotorSpec` from `engineering/models.py`, motor JSON from `engineering/motor_data/gobilda_yellow_jacket.json`
- Produces: `load_motor_database() -> tuple[MotorSpec, ...]`, `select_motor(required_torque_nmm, required_rpm, motors, duty) -> MotorMatch`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_motor_selection.py
"""Tests for motor selection by torque+speed requirement."""

import math
from pathlib import Path
from unittest.mock import patch

import pytest

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.motor_selection import (
    KG_CM_TO_NMM,
    load_motor_database,
    select_motor,
)


# --- Fixtures ---

def _make_motor(
    sku: str = "5202-0002-0051",
    name: str = "Yellow Jacket 50.9:1",
    gear_ratio: float = 50.9,
    free_speed_rpm: float = 117.0,
    stall_torque_kg_cm: float = 64.5,
    stall_current_a: float = 9.2,
    free_current_a: float = 0.25,
) -> MotorSpec:
    return MotorSpec(
        sku=sku,
        name=name,
        gear_ratio=gear_ratio,
        free_speed_rpm=free_speed_rpm,
        stall_torque_kg_cm=stall_torque_kg_cm,
        stall_current_a=stall_current_a,
        free_current_a=free_current_a,
        encoder_ppr=1425.1,
        shaft_type="6mm_D",
        weight_grams=470,
    )


SAMPLE_MOTORS = (
    _make_motor("5202-0002-0014", "YJ 13.7:1", 13.7, 435, 17.4, 9.2, 0.25),
    _make_motor("5202-0002-0019", "YJ 19.2:1", 19.2, 312, 24.3, 9.2, 0.25),
    _make_motor("5202-0002-0051", "YJ 50.9:1", 50.9, 117, 64.5, 9.2, 0.25),
    _make_motor("5202-0002-0071", "YJ 71.2:1", 71.2, 84, 90.2, 9.2, 0.25),
    _make_motor("5202-0002-0188", "YJ 188:1", 188.0, 30, 238.1, 9.2, 0.25),
)


class TestSelectMotor:
    def test_selects_motor_with_sufficient_torque(self):
        """A moderate torque need at moderate speed should pick ~50:1."""
        required_torque_nmm = 3000.0  # ~30 kg-cm
        required_rpm = 100.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.output_torque_nmm >= required_torque_nmm * 0.5  # usable torque
        assert result.torque_margin_pct >= 0.0

    def test_high_torque_selects_high_ratio(self):
        """Very high torque need should select the highest ratio motor."""
        required_torque_nmm = 10000.0
        required_rpm = 20.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.gear_ratio >= 71.2

    def test_high_speed_selects_low_ratio(self):
        """High speed need should select a low ratio motor."""
        required_torque_nmm = 500.0
        required_rpm = 300.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.gear_ratio <= 19.2

    def test_margin_above_zero_when_motor_sufficient(self):
        """When a motor can deliver, torque margin should be positive."""
        required_torque_nmm = 1000.0
        required_rpm = 80.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.torque_margin_pct > 0.0

    def test_returns_negative_margin_when_insufficient(self):
        """When no motor can deliver, best match has negative margin."""
        required_torque_nmm = 50000.0  # impossibly high
        required_rpm = 500.0
        result = select_motor(required_torque_nmm, required_rpm, SAMPLE_MOTORS)
        assert result.torque_margin_pct < 0.0

    def test_intermittent_duty_uses_higher_torque_fraction(self):
        result_cont = select_motor(3000.0, 100.0, SAMPLE_MOTORS, duty="continuous")
        result_int = select_motor(3000.0, 100.0, SAMPLE_MOTORS, duty="intermittent")
        # Intermittent allows using more of stall torque, so margin is higher
        assert result_int.torque_margin_pct >= result_cont.torque_margin_pct

    def test_empty_motors_raises(self):
        with pytest.raises(ValueError, match="No motors"):
            select_motor(1000.0, 100.0, ())

    def test_negative_torque_raises(self):
        with pytest.raises(ValueError, match="required_torque_nmm"):
            select_motor(-1.0, 100.0, SAMPLE_MOTORS)

    def test_negative_rpm_raises(self):
        with pytest.raises(ValueError, match="required_rpm"):
            select_motor(1000.0, -1.0, SAMPLE_MOTORS)


class TestLoadMotorDatabase:
    def test_loads_all_variants(self):
        motors = load_motor_database()
        assert len(motors) >= 8  # at least 8 Yellow Jacket variants in JSON
        assert all(isinstance(m, MotorSpec) for m in motors)

    def test_skus_are_unique(self):
        motors = load_motor_database()
        skus = [m.sku for m in motors]
        assert len(skus) == len(set(skus))

    def test_stall_torque_positive(self):
        motors = load_motor_database()
        assert all(m.stall_torque_kg_cm > 0 for m in motors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_motor_selection.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_motor_database' from 'robotics_design_advisor.mechanisms.motor_selection'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/mechanisms/motor_selection.py
"""Motor selection engine — match torque+speed requirements to goBILDA motors.

Loads the Yellow Jacket motor database and scores each motor variant
against a given torque and speed requirement. Pure functions except
for ``load_motor_database`` which reads the JSON file once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.models import MotorMatch

# 1 kg-cm = 98.0665 N-mm
KG_CM_TO_NMM = 98.0665

# Fraction of stall torque considered safe for continuous vs intermittent duty
_DUTY_FACTORS: dict[str, float] = {
    "continuous": 0.50,
    "intermittent": 0.70,
}

_MOTOR_DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "engineering"
    / "motor_data"
    / "gobilda_yellow_jacket.json"
)


def load_motor_database(path: Path | None = None) -> tuple[MotorSpec, ...]:
    """Load goBILDA Yellow Jacket motor specs from JSON.

    Parameters
    ----------
    path : Path, optional
        Override path to the motor JSON file.  Defaults to the bundled
        ``gobilda_yellow_jacket.json``.
    """
    data_path = path or _MOTOR_DATA_PATH
    with open(data_path) as f:
        data = json.load(f)

    motors: list[MotorSpec] = []
    for v in data["variants"]:
        motors.append(
            MotorSpec(
                sku=v["sku"],
                name=v["name"],
                gear_ratio=v["gear_ratio"],
                free_speed_rpm=v["free_speed_rpm"],
                stall_torque_kg_cm=v["stall_torque_kg_cm"],
                stall_current_a=v["stall_current_a"],
                free_current_a=v["free_current_a"],
                encoder_ppr=v["encoder_ppr"],
                shaft_type=v["shaft_type"],
                weight_grams=v["weight_grams"],
                voltage_nominal=data.get("voltage_nominal", 12.0),
            )
        )
    return tuple(motors)


def select_motor(
    required_torque_nmm: float,
    required_rpm: float,
    motors: tuple[MotorSpec, ...] | list[MotorSpec],
    duty: Literal["continuous", "intermittent"] = "continuous",
) -> MotorMatch:
    """Find the best motor for a torque + speed requirement.

    Scores each motor by how well its usable torque and free speed
    match the requirement.  Returns the single best match.

    Parameters
    ----------
    required_torque_nmm : float
        Required output torque in N-mm (must be > 0).
    required_rpm : float
        Required output speed in RPM (must be >= 0).
    motors : sequence of MotorSpec
        Available motors to choose from.
    duty : "continuous" | "intermittent"
        Duty cycle — intermittent allows using a higher fraction of stall torque.
    """
    if required_torque_nmm < 0:
        raise ValueError(f"required_torque_nmm must be non-negative, got {required_torque_nmm}")
    if required_rpm < 0:
        raise ValueError(f"required_rpm must be non-negative, got {required_rpm}")
    if not motors:
        raise ValueError("No motors provided")

    duty_factor = _DUTY_FACTORS.get(duty, 0.50)
    best_score = float("-inf")
    best_match: MotorMatch | None = None

    for motor in motors:
        stall_torque_nmm = motor.stall_torque_kg_cm * KG_CM_TO_NMM
        usable_torque_nmm = stall_torque_nmm * duty_factor

        torque_margin_pct = (
            ((usable_torque_nmm - required_torque_nmm) / required_torque_nmm * 100.0)
            if required_torque_nmm > 0
            else 999.0
        )

        # Speed score: how well the motor's free RPM matches required RPM
        speed_ratio = motor.free_speed_rpm / required_rpm if required_rpm > 0 else 10.0
        if speed_ratio >= 1.0:
            speed_score = 1.0 - min(1.0, (speed_ratio - 1.0) / 5.0)
        else:
            speed_score = speed_ratio - 1.0  # negative if too slow

        # Torque score: positive margin is good, penalize excess heavily
        if torque_margin_pct >= 0:
            torque_score = 1.0 - min(1.0, torque_margin_pct / 500.0)
        else:
            torque_score = torque_margin_pct / 100.0  # negative, severe penalty

        # Combined score — torque is weighted 2x because stalling is worse than being slow
        score = torque_score * 2.0 + speed_score

        # Estimate operating current (linear interpolation on motor curve)
        load_fraction = min(1.0, required_torque_nmm / stall_torque_nmm) if stall_torque_nmm > 0 else 1.0
        current_draw = motor.free_current_a + load_fraction * (motor.stall_current_a - motor.free_current_a)

        notes: list[str] = []
        if torque_margin_pct < 20.0:
            notes.append(f"Low torque margin ({torque_margin_pct:.0f}%) — risk of stalling")
        if motor.free_speed_rpm < required_rpm:
            notes.append(
                f"Motor free speed ({motor.free_speed_rpm:.0f} RPM) below required ({required_rpm:.0f} RPM)"
            )

        match = MotorMatch(
            motor_name=motor.name,
            motor_sku=motor.sku,
            base_rpm=motor.free_speed_rpm,
            stall_torque_nmm=round(stall_torque_nmm, 1),
            gear_ratio=motor.gear_ratio,
            output_rpm=motor.free_speed_rpm,
            output_torque_nmm=round(usable_torque_nmm, 1),
            torque_margin_pct=round(torque_margin_pct, 1),
            current_draw_a=round(current_draw, 2),
            notes=tuple(notes),
        )

        if score > best_score:
            best_score = score
            best_match = match

    assert best_match is not None  # guaranteed by non-empty motors check
    return best_match
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_motor_selection.py -v`
Expected: 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/mechanisms/motor_selection.py tests/unit/test_motor_selection.py
git commit -m "feat(mechanisms): add motor selection engine — match torque+speed to Yellow Jacket motors"
```

---

### Task 3: Grabber Physics

**Files:**
- Create: `src/robotics_design_advisor/mechanisms/grabber.py`
- Test: `tests/unit/test_grabber.py`

**Interfaces:**
- Consumes: `GrabberAnalysis` from `mechanisms/models.py`
- Produces: `analyze_grabber(piece_weight_g, piece_dimensions_mm, grip_type, jaw_length_mm, friction_coefficient) -> GrabberAnalysis`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_grabber.py
"""Tests for grabber/intake physics calculations."""

import math

import pytest

from robotics_design_advisor.mechanisms.grabber import (
    GRAVITY_M_S2,
    SAFETY_FACTOR,
    analyze_grabber,
    recommend_grip_type,
)
from robotics_design_advisor.mechanisms.models import GrabberAnalysis


class TestAnalyzeGrabber:
    def test_claw_grip_force(self):
        """Grip force = (weight_N * safety_factor) / friction_coefficient."""
        result = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
        )
        assert isinstance(result, GrabberAnalysis)
        weight_n = 0.1 * GRAVITY_M_S2  # 100g in N
        expected_grip = weight_n * SAFETY_FACTOR / 0.5  # default friction
        assert abs(result.required_grip_force_n - expected_grip) < 0.01

    def test_servo_torque_equals_force_times_lever(self):
        result = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
        )
        expected_torque = result.required_grip_force_n * 80.0
        assert abs(result.required_torque_nmm - expected_torque) < 0.01

    def test_jaw_opening_is_largest_dimension_plus_margin(self):
        result = analyze_grabber(
            piece_weight_g=50.0,
            piece_dimensions_mm=(38.0, 50.0, 25.0),
            grip_type="claw",
            jaw_length_mm=60.0,
        )
        # Jaw opening should accommodate largest dimension + 10mm margin
        assert result.jaw_opening_mm >= 50.0

    def test_roller_intake_uses_rubber_friction(self):
        result = analyze_grabber(
            piece_weight_g=28.0,
            piece_dimensions_mm=(38.0, 38.0, 38.0),
            grip_type="roller_intake",
            jaw_length_mm=60.0,
        )
        assert result.grip_type == "roller_intake"
        assert result.required_grip_force_n > 0

    def test_passive_funnel_zero_torque(self):
        result = analyze_grabber(
            piece_weight_g=28.0,
            piece_dimensions_mm=(38.0, 38.0, 38.0),
            grip_type="passive_funnel",
            jaw_length_mm=60.0,
        )
        assert result.required_torque_nmm == 0.0
        assert result.hold_current_ma == 0.0

    def test_custom_friction_coefficient(self):
        result_low = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
            friction_coefficient=0.3,
        )
        result_high = analyze_grabber(
            piece_weight_g=100.0,
            piece_dimensions_mm=(50.0, 50.0, 50.0),
            grip_type="claw",
            jaw_length_mm=80.0,
            friction_coefficient=0.8,
        )
        # Lower friction needs more grip force
        assert result_low.required_grip_force_n > result_high.required_grip_force_n

    def test_zero_weight_raises(self):
        with pytest.raises(ValueError, match="piece_weight_g"):
            analyze_grabber(
                piece_weight_g=0.0,
                piece_dimensions_mm=(50.0, 50.0, 50.0),
                grip_type="claw",
                jaw_length_mm=80.0,
            )

    def test_negative_jaw_length_raises(self):
        with pytest.raises(ValueError, match="jaw_length_mm"):
            analyze_grabber(
                piece_weight_g=50.0,
                piece_dimensions_mm=(50.0, 50.0, 50.0),
                grip_type="claw",
                jaw_length_mm=-10.0,
            )


class TestRecommendGripType:
    def test_cube_recommends_claw(self):
        assert recommend_grip_type("cube") == "claw"

    def test_sphere_recommends_roller(self):
        assert recommend_grip_type("sphere") == "roller_intake"

    def test_ring_recommends_hook(self):
        assert recommend_grip_type("ring") == "claw"

    def test_unknown_defaults_to_claw(self):
        assert recommend_grip_type("alien_artifact") == "claw"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_grabber.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/mechanisms/grabber.py
"""Grabber/intake physics — grip force, servo torque, grip type selection.

Pure functions, no I/O.
"""

from __future__ import annotations

from .models import GrabberAnalysis

GRAVITY_M_S2 = 9.80665
SAFETY_FACTOR = 2.0
DEFAULT_FRICTION = 0.5       # rubber on foam/plastic
ROLLER_FRICTION = 0.7        # compliant rubber rollers
JAW_OPENING_MARGIN_MM = 10.0
SERVO_CURRENT_PER_NMM = 0.8  # mA per N-mm holding torque (empirical estimate)

# Grip type selection based on game piece shape
_SHAPE_TO_GRIP: dict[str, str] = {
    "cube": "claw",
    "box": "claw",
    "sphere": "roller_intake",
    "ball": "roller_intake",
    "ring": "claw",
    "cylinder": "claw",
    "cone": "claw",
    "pixel": "roller_intake",
    "hexagon": "roller_intake",
}


def recommend_grip_type(piece_shape: str) -> str:
    """Recommend a grip type based on game piece shape.

    Returns "claw", "roller_intake", or "passive_funnel".
    """
    return _SHAPE_TO_GRIP.get(piece_shape.lower(), "claw")


def analyze_grabber(
    piece_weight_g: float,
    piece_dimensions_mm: tuple[float, ...],
    grip_type: str,
    jaw_length_mm: float,
    friction_coefficient: float | None = None,
) -> GrabberAnalysis:
    """Calculate grabber physics for a given game piece.

    Parameters
    ----------
    piece_weight_g : float
        Game piece mass in grams (must be > 0).
    piece_dimensions_mm : tuple of float
        Game piece dimensions (x, y, z) in mm.
    grip_type : str
        "claw", "roller_intake", or "passive_funnel".
    jaw_length_mm : float
        Lever arm from servo pivot to jaw tip in mm (must be > 0).
    friction_coefficient : float, optional
        Surface friction coefficient.  Defaults depend on grip type.
    """
    if piece_weight_g <= 0:
        raise ValueError(f"piece_weight_g must be positive, got {piece_weight_g}")
    if jaw_length_mm <= 0:
        raise ValueError(f"jaw_length_mm must be positive, got {jaw_length_mm}")

    weight_n = (piece_weight_g / 1000.0) * GRAVITY_M_S2
    largest_dim = max(piece_dimensions_mm)
    jaw_opening = largest_dim + JAW_OPENING_MARGIN_MM

    notes: list[str] = []

    if grip_type == "passive_funnel":
        return GrabberAnalysis(
            required_grip_force_n=0.0,
            required_torque_nmm=0.0,
            recommended_servo="None — passive geometry",
            jaw_opening_mm=round(jaw_opening, 1),
            grip_type="passive_funnel",
            hold_current_ma=0.0,
            notes=("Passive funnel — no motor or servo needed. Design guides to direct pieces.",),
        )

    if grip_type == "roller_intake":
        friction = friction_coefficient if friction_coefficient is not None else ROLLER_FRICTION
        grip_force = (weight_n * SAFETY_FACTOR) / friction
        torque = grip_force * jaw_length_mm
        notes.append("Roller intake — use compliant rubber wheels for grip.")
        notes.append("Ensure rollers spin inward to pull piece into robot.")
        servo_label = "goBILDA Speed Servo or DC motor"
    else:
        friction = friction_coefficient if friction_coefficient is not None else DEFAULT_FRICTION
        grip_force = (weight_n * SAFETY_FACTOR) / friction
        torque = grip_force * jaw_length_mm
        notes.append("Use rubber pads on jaw surfaces to increase friction.")
        if largest_dim > 100:
            notes.append("Large piece — consider parallel-jaw gripper for even contact.")
        servo_label = "goBILDA Torque Servo"

    hold_current = torque * SERVO_CURRENT_PER_NMM

    return GrabberAnalysis(
        required_grip_force_n=round(grip_force, 3),
        required_torque_nmm=round(torque, 3),
        recommended_servo=servo_label,
        jaw_opening_mm=round(jaw_opening, 1),
        grip_type=grip_type,
        hold_current_ma=round(hold_current, 1),
        notes=tuple(notes),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_grabber.py -v`
Expected: 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/mechanisms/grabber.py tests/unit/test_grabber.py
git commit -m "feat(mechanisms): add grabber physics — grip force, servo torque, grip type selection"
```

---

### Task 4: Launcher Ballistics

**Files:**
- Create: `src/robotics_design_advisor/mechanisms/launcher.py`
- Test: `tests/unit/test_launcher.py`

**Interfaces:**
- Consumes: `LauncherAnalysis` from `mechanisms/models.py`, `select_motor` from `motor_selection.py`, `MotorSpec` from `engineering/models.py`
- Produces: `analyze_launcher(target_distance_m, target_height_m, projectile_mass_g, projectile_diameter_mm, launcher_type, motors) -> LauncherAnalysis`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_launcher.py
"""Tests for launcher ballistics calculations."""

import math

import pytest

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.launcher import (
    GRAVITY,
    FLYWHEEL_EFFICIENCY,
    calc_launch_velocity,
    calc_optimal_angle,
    analyze_launcher,
)
from robotics_design_advisor.mechanisms.models import LauncherAnalysis


def _make_motor(ratio: float = 5.2, rpm: float = 1150, torque: float = 6.6) -> MotorSpec:
    return MotorSpec(
        sku=f"5202-test-{ratio}",
        name=f"Test {ratio}:1",
        gear_ratio=ratio,
        free_speed_rpm=rpm,
        stall_torque_kg_cm=torque,
        stall_current_a=9.2,
        free_current_a=0.25,
        encoder_ppr=145.1,
        shaft_type="6mm_D",
        weight_grams=310,
    )


SAMPLE_MOTORS = (_make_motor(3.7, 1620, 4.7), _make_motor(5.2, 1150, 6.6))


class TestCalcLaunchVelocity:
    def test_flat_launch(self):
        """Launching at 45deg to hit 3m distance, 0m height."""
        v = calc_launch_velocity(distance_m=3.0, height_m=0.0, angle_deg=45.0)
        # v = sqrt(g * d / sin(2*45)) = sqrt(9.81 * 3 / 1) ≈ 5.42
        expected = math.sqrt(GRAVITY * 3.0)
        assert abs(v - expected) < 0.1

    def test_elevated_target_needs_more_velocity(self):
        v_flat = calc_launch_velocity(3.0, 0.0, 45.0)
        v_high = calc_launch_velocity(3.0, 1.0, 45.0)
        assert v_high > v_flat

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="distance_m"):
            calc_launch_velocity(0.0, 0.0, 45.0)


class TestCalcOptimalAngle:
    def test_flat_target_near_45(self):
        """For a flat target, optimal angle is near 45 degrees."""
        angle = calc_optimal_angle(3.0, 0.0)
        assert 40.0 <= angle <= 50.0

    def test_elevated_target_lower_angle(self):
        """Elevated targets need a more direct trajectory."""
        angle_flat = calc_optimal_angle(3.0, 0.0)
        angle_high = calc_optimal_angle(3.0, 2.0)
        # High target should use a lower or similar angle
        assert angle_high <= angle_flat + 5.0


class TestAnalyzeLauncher:
    def test_flywheel_returns_analysis(self):
        result = analyze_launcher(
            target_distance_m=3.0,
            target_height_m=1.0,
            projectile_mass_g=28.0,
            projectile_diameter_mm=38.0,
            launcher_type="flywheel",
            motors=SAMPLE_MOTORS,
        )
        assert isinstance(result, LauncherAnalysis)
        assert result.launch_velocity_ms > 0
        assert result.flywheel_rpm > 0
        assert result.flywheel_diameter_mm > 0

    def test_catapult_returns_spring_force(self):
        result = analyze_launcher(
            target_distance_m=2.0,
            target_height_m=0.5,
            projectile_mass_g=50.0,
            projectile_diameter_mm=60.0,
            launcher_type="catapult",
            motors=SAMPLE_MOTORS,
        )
        assert result.catapult_spring_force_n > 0
        assert result.flywheel_rpm == 0.0

    def test_energy_per_shot_positive(self):
        result = analyze_launcher(
            target_distance_m=3.0,
            target_height_m=0.0,
            projectile_mass_g=28.0,
            projectile_diameter_mm=38.0,
            launcher_type="flywheel",
            motors=SAMPLE_MOTORS,
        )
        # E = 0.5 * m * v^2
        expected_energy = 0.5 * 0.028 * result.launch_velocity_ms ** 2
        assert abs(result.energy_per_shot_j - expected_energy) < 0.01

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="target_distance_m"):
            analyze_launcher(
                target_distance_m=0.0,
                target_height_m=0.0,
                projectile_mass_g=28.0,
                projectile_diameter_mm=38.0,
                launcher_type="flywheel",
                motors=SAMPLE_MOTORS,
            )

    def test_negative_mass_raises(self):
        with pytest.raises(ValueError, match="projectile_mass_g"):
            analyze_launcher(
                target_distance_m=3.0,
                target_height_m=0.0,
                projectile_mass_g=-1.0,
                projectile_diameter_mm=38.0,
                launcher_type="flywheel",
                motors=SAMPLE_MOTORS,
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_launcher.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/mechanisms/launcher.py
"""Launcher ballistics — flywheel RPM, catapult springs, launch angles.

Pure functions, no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.models import LauncherAnalysis
from robotics_design_advisor.mechanisms.motor_selection import KG_CM_TO_NMM, select_motor

GRAVITY = 9.80665
FLYWHEEL_EFFICIENCY = 0.60   # energy transfer: wheel → projectile
CATAPULT_EFFICIENCY = 0.70   # spring → projectile
DEFAULT_FLYWHEEL_DIAMETER_MM = 100.0
CATAPULT_ARM_LENGTH_M = 0.25  # typical FTC catapult arm


def calc_launch_velocity(
    distance_m: float,
    height_m: float,
    angle_deg: float,
) -> float:
    """Calculate required launch velocity for a projectile.

    Uses the range equation for projectile motion:
    v = sqrt( (g * d^2) / (d * sin(2*theta) - 2*h * cos^2(theta)) )

    Parameters
    ----------
    distance_m : float
        Horizontal distance to target (must be > 0).
    height_m : float
        Target height relative to launch point.
    angle_deg : float
        Launch angle in degrees (0 < angle < 90).
    """
    if distance_m <= 0:
        raise ValueError(f"distance_m must be positive, got {distance_m}")

    theta = math.radians(angle_deg)
    sin2t = math.sin(2.0 * theta)
    cos2t = math.cos(theta) ** 2

    denominator = distance_m * sin2t - 2.0 * height_m * cos2t
    if denominator <= 0:
        # Target unreachable at this angle — use near-vertical estimate
        denominator = 0.01

    v_squared = (GRAVITY * distance_m**2) / denominator
    return math.sqrt(max(0.0, v_squared))


def calc_optimal_angle(distance_m: float, height_m: float) -> float:
    """Find the launch angle that minimizes required velocity.

    Sweeps from 20-70 degrees in 1-degree increments.
    """
    if distance_m <= 0:
        raise ValueError(f"distance_m must be positive, got {distance_m}")

    best_angle = 45.0
    best_velocity = float("inf")

    for angle_int in range(20, 71):
        angle = float(angle_int)
        try:
            v = calc_launch_velocity(distance_m, height_m, angle)
        except ValueError:
            continue
        if v < best_velocity:
            best_velocity = v
            best_angle = angle

    return best_angle


def analyze_launcher(
    target_distance_m: float,
    target_height_m: float,
    projectile_mass_g: float,
    projectile_diameter_mm: float,
    launcher_type: str,
    motors: Sequence[MotorSpec],
    flywheel_diameter_mm: float = DEFAULT_FLYWHEEL_DIAMETER_MM,
) -> LauncherAnalysis:
    """Full launcher analysis — velocity, angle, motor/spring sizing.

    Parameters
    ----------
    target_distance_m : float
        Horizontal distance to target (must be > 0).
    target_height_m : float
        Target height relative to launch point.
    projectile_mass_g : float
        Projectile mass in grams (must be > 0).
    projectile_diameter_mm : float
        Projectile diameter in mm (must be > 0).
    launcher_type : str
        "flywheel" or "catapult".
    motors : sequence of MotorSpec
        Available motors for flywheel drive.
    flywheel_diameter_mm : float
        Flywheel wheel diameter (default 100mm).
    """
    if target_distance_m <= 0:
        raise ValueError(f"target_distance_m must be positive, got {target_distance_m}")
    if projectile_mass_g <= 0:
        raise ValueError(f"projectile_mass_g must be positive, got {projectile_mass_g}")
    if projectile_diameter_mm <= 0:
        raise ValueError(f"projectile_diameter_mm must be positive, got {projectile_diameter_mm}")

    mass_kg = projectile_mass_g / 1000.0
    angle = calc_optimal_angle(target_distance_m, target_height_m)
    velocity = calc_launch_velocity(target_distance_m, target_height_m, angle)
    energy = 0.5 * mass_kg * velocity**2

    notes: list[str] = []

    if launcher_type == "catapult":
        # Spring energy must deliver kinetic energy accounting for losses
        spring_energy = energy / CATAPULT_EFFICIENCY
        # E_spring = 0.5 * k * x^2 — estimate spring force as F = 2 * E / x
        # Assume arm deflection ~ arm length
        spring_force = 2.0 * spring_energy / CATAPULT_ARM_LENGTH_M

        notes.append(f"Catapult arm length assumed: {CATAPULT_ARM_LENGTH_M * 1000:.0f}mm")
        notes.append("Use surgical tubing or constant-force spring for energy storage.")

        motor_rec = "N/A — spring-powered"

        return LauncherAnalysis(
            launch_velocity_ms=round(velocity, 2),
            launch_angle_deg=round(angle, 1),
            flywheel_rpm=0.0,
            flywheel_diameter_mm=0.0,
            motor_recommendation=motor_rec,
            spin_up_time_s=0.0,
            energy_per_shot_j=round(energy, 4),
            fire_rate_hz=round(1.0 / 1.5, 2),  # ~1.5s reload cycle
            catapult_spring_force_n=round(spring_force, 1),
            notes=tuple(notes),
        )

    # Flywheel calculation
    # Surface speed must equal launch velocity (adjusted for efficiency)
    required_surface_speed = velocity / FLYWHEEL_EFFICIENCY
    # v = pi * d * RPM / 60  =>  RPM = 60 * v / (pi * d)
    flywheel_circumference_m = math.pi * flywheel_diameter_mm / 1000.0
    flywheel_rpm = (60.0 * required_surface_speed) / flywheel_circumference_m

    # Motor needs to spin at flywheel RPM (direct drive assumed)
    # Torque needed for spin-up: T = I * alpha
    # Flywheel moment of inertia (solid cylinder): I = 0.5 * m * r^2
    flywheel_mass_kg = 0.15  # ~150g for a typical compliant wheel
    flywheel_radius_m = flywheel_diameter_mm / 2000.0
    inertia = 0.5 * flywheel_mass_kg * flywheel_radius_m**2

    # Target spin-up time ~ 1 second
    target_spinup_s = 1.0
    angular_accel = (flywheel_rpm * 2.0 * math.pi / 60.0) / target_spinup_s
    required_torque_nmm = inertia * angular_accel * 1000.0  # N-m → N-mm

    motor_match = select_motor(required_torque_nmm, flywheel_rpm, tuple(motors), duty="intermittent")

    # Actual spin-up time with selected motor
    motor_torque_nm = motor_match.output_torque_nmm / 1000.0
    if motor_torque_nm > 0:
        actual_spinup = (inertia * flywheel_rpm * 2.0 * math.pi / 60.0) / motor_torque_nm
    else:
        actual_spinup = float("inf")

    fire_rate = 1.0 / max(0.1, actual_spinup + 0.3)  # spin-up + feed time

    notes.append(f"Flywheel surface speed: {required_surface_speed:.1f} m/s")
    notes.append(f"Efficiency factor: {FLYWHEEL_EFFICIENCY:.0%} — use compliant wheels")
    if flywheel_rpm > 6000:
        notes.append("WARNING: RPM exceeds typical motor range — increase flywheel diameter")

    return LauncherAnalysis(
        launch_velocity_ms=round(velocity, 2),
        launch_angle_deg=round(angle, 1),
        flywheel_rpm=round(flywheel_rpm, 0),
        flywheel_diameter_mm=flywheel_diameter_mm,
        motor_recommendation=motor_match.motor_name,
        spin_up_time_s=round(actual_spinup, 2),
        energy_per_shot_j=round(energy, 4),
        fire_rate_hz=round(fire_rate, 2),
        catapult_spring_force_n=0.0,
        notes=tuple(notes),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_launcher.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/mechanisms/launcher.py tests/unit/test_launcher.py
git commit -m "feat(mechanisms): add launcher ballistics — flywheel RPM, catapult springs, optimal angles"
```

---

### Task 5: Lift Physics

**Files:**
- Create: `src/robotics_design_advisor/mechanisms/lift.py`
- Test: `tests/unit/test_lift.py`

**Interfaces:**
- Consumes: `LiftAnalysis` from `mechanisms/models.py`, `select_motor` from `motor_selection.py`, `MotorSpec` from `engineering/models.py`
- Produces: `analyze_lift(payload_mass_g, max_height_mm, lift_type, stages, carriage_mass_g, motors) -> LiftAnalysis`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_lift.py
"""Tests for lift/elevator/arm physics calculations."""

import math

import pytest

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.lift import (
    GRAVITY,
    FRICTION_FACTOR,
    analyze_lift,
)
from robotics_design_advisor.mechanisms.models import LiftAnalysis


def _make_motor(ratio: float = 50.9, rpm: float = 117, torque: float = 64.5) -> MotorSpec:
    return MotorSpec(
        sku=f"5202-test-{ratio}",
        name=f"Test {ratio}:1",
        gear_ratio=ratio,
        free_speed_rpm=rpm,
        stall_torque_kg_cm=torque,
        stall_current_a=9.2,
        free_current_a=0.25,
        encoder_ppr=1425.1,
        shaft_type="6mm_D",
        weight_grams=470,
    )


SAMPLE_MOTORS = (
    _make_motor(19.2, 312, 24.3),
    _make_motor(50.9, 117, 64.5),
    _make_motor(71.2, 84, 90.2),
    _make_motor(188.0, 30, 238.1),
)


class TestAnalyzeLift:
    def test_elevator_returns_analysis(self):
        result = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=600.0,
            lift_type="elevator",
            motors=SAMPLE_MOTORS,
        )
        assert isinstance(result, LiftAnalysis)
        assert result.lift_type == "elevator"
        assert result.required_force_n > 0
        assert result.spool_diameter_mm > 0

    def test_elevator_force_includes_gravity_and_friction(self):
        result = analyze_lift(
            payload_mass_g=1000.0,
            max_height_mm=800.0,
            lift_type="elevator",
            stages=1,
            carriage_mass_g=200.0,
            motors=SAMPLE_MOTORS,
        )
        total_mass_kg = (1000.0 + 200.0) / 1000.0
        min_force = total_mass_kg * GRAVITY * FRICTION_FACTOR
        assert result.required_force_n >= min_force * 0.99

    def test_two_stage_doubles_force(self):
        result_1 = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=400.0,
            lift_type="elevator",
            stages=1,
            motors=SAMPLE_MOTORS,
        )
        result_2 = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=800.0,
            lift_type="elevator",
            stages=2,
            motors=SAMPLE_MOTORS,
        )
        # 2-stage needs more force due to stage multiplier
        assert result_2.required_force_n > result_1.required_force_n

    def test_four_bar_returns_analysis(self):
        result = analyze_lift(
            payload_mass_g=300.0,
            max_height_mm=500.0,
            lift_type="four_bar",
            motors=SAMPLE_MOTORS,
        )
        assert result.lift_type == "four_bar"
        assert result.required_torque_nmm > 0

    def test_arm_returns_analysis(self):
        result = analyze_lift(
            payload_mass_g=200.0,
            max_height_mm=400.0,
            lift_type="arm",
            motors=SAMPLE_MOTORS,
        )
        assert result.lift_type == "arm"

    def test_counterbalance_reduces_peak_force(self):
        result = analyze_lift(
            payload_mass_g=1000.0,
            max_height_mm=800.0,
            lift_type="elevator",
            motors=SAMPLE_MOTORS,
        )
        # Counterbalance should be positive (offsetting gravity)
        assert result.counterbalance_force_n > 0

    def test_time_to_height_positive(self):
        result = analyze_lift(
            payload_mass_g=500.0,
            max_height_mm=600.0,
            lift_type="elevator",
            motors=SAMPLE_MOTORS,
        )
        assert result.time_to_max_height_s > 0

    def test_zero_payload_raises(self):
        with pytest.raises(ValueError, match="payload_mass_g"):
            analyze_lift(
                payload_mass_g=0.0,
                max_height_mm=600.0,
                lift_type="elevator",
                motors=SAMPLE_MOTORS,
            )

    def test_zero_height_raises(self):
        with pytest.raises(ValueError, match="max_height_mm"):
            analyze_lift(
                payload_mass_g=500.0,
                max_height_mm=0.0,
                lift_type="elevator",
                motors=SAMPLE_MOTORS,
            )

    def test_invalid_lift_type_raises(self):
        with pytest.raises(ValueError, match="lift_type"):
            analyze_lift(
                payload_mass_g=500.0,
                max_height_mm=600.0,
                lift_type="teleporter",
                motors=SAMPLE_MOTORS,
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_lift.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/mechanisms/lift.py
"""Lift/elevator/arm physics — force, torque, counterbalance, spool sizing.

Pure functions, no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from robotics_design_advisor.engineering.models import MotorSpec
from robotics_design_advisor.mechanisms.models import LiftAnalysis
from robotics_design_advisor.mechanisms.motor_selection import KG_CM_TO_NMM, select_motor

GRAVITY = 9.80665
FRICTION_FACTOR = 1.15         # 15% friction overhead for linear slides
DEFAULT_CARRIAGE_MASS_G = 150  # typical slide carriage mass
DEFAULT_SPOOL_DIAMETER_MM = 30.0
ACCEL_FACTOR = 1.5             # peak force = 1.5x continuous (for acceleration)

VALID_LIFT_TYPES = {"elevator", "four_bar", "arm", "cascade"}


def analyze_lift(
    payload_mass_g: float,
    max_height_mm: float,
    lift_type: str,
    motors: Sequence[MotorSpec],
    stages: int = 1,
    carriage_mass_g: float = DEFAULT_CARRIAGE_MASS_G,
    spool_diameter_mm: float = DEFAULT_SPOOL_DIAMETER_MM,
) -> LiftAnalysis:
    """Full lift analysis — force, torque, motor selection, timing.

    Parameters
    ----------
    payload_mass_g : float
        Payload mass in grams (must be > 0).
    max_height_mm : float
        Maximum lift height in mm (must be > 0).
    lift_type : str
        "elevator", "four_bar", "arm", or "cascade".
    motors : sequence of MotorSpec
        Available motors.
    stages : int
        Number of elevator stages (only for elevator/cascade).
    carriage_mass_g : float
        Carriage/slide mass in grams.
    spool_diameter_mm : float
        Spool diameter for string/belt elevator.
    """
    if payload_mass_g <= 0:
        raise ValueError(f"payload_mass_g must be positive, got {payload_mass_g}")
    if max_height_mm <= 0:
        raise ValueError(f"max_height_mm must be positive, got {max_height_mm}")
    if lift_type not in VALID_LIFT_TYPES:
        raise ValueError(
            f"lift_type must be one of {sorted(VALID_LIFT_TYPES)}, got '{lift_type}'"
        )

    payload_kg = payload_mass_g / 1000.0
    carriage_kg = carriage_mass_g / 1000.0
    total_mass_kg = payload_kg + carriage_kg
    notes: list[str] = []

    if lift_type in ("elevator", "cascade"):
        # Elevator: F = (m_payload + m_carriage) * g * stages * friction_factor
        stage_multiplier = max(1, stages)
        required_force = total_mass_kg * GRAVITY * stage_multiplier * FRICTION_FACTOR
        peak_force = required_force * ACCEL_FACTOR

        # Torque at spool: T = F * spool_radius
        spool_radius_mm = spool_diameter_mm / 2.0
        required_torque = required_force * spool_radius_mm  # N-mm

        # Counterbalance: match ~80% of gravity force with constant-force spring
        counterbalance = total_mass_kg * GRAVITY * 0.8

        # Motor selection based on torque at spool
        motor_match = select_motor(required_torque, 100.0, tuple(motors))

        # Lift speed: v = angular_velocity * spool_radius
        motor_rpm = motor_match.output_rpm
        angular_vel_rad_s = motor_rpm * 2.0 * math.pi / 60.0
        spool_radius_m = spool_radius_mm / 1000.0
        speed_mm_s = angular_vel_rad_s * spool_radius_m * 1000.0

        time_to_height = max_height_mm / speed_mm_s if speed_mm_s > 0 else float("inf")

        if stages > 1:
            notes.append(f"{stages}-stage elevator: {stage_multiplier}x force multiplier")
        notes.append(f"Spool diameter: {spool_diameter_mm:.0f}mm")
        if counterbalance > 0:
            notes.append(f"Counterbalance with {counterbalance:.1f}N constant-force spring")

        actual_spool = spool_diameter_mm

    elif lift_type == "four_bar":
        # 4-bar arm: torque = m * g * L * cos(theta) — worst case at horizontal
        arm_length_mm = max_height_mm  # arm reach ≈ max height
        arm_length_m = arm_length_mm / 1000.0
        required_torque_nm = total_mass_kg * GRAVITY * arm_length_m  # at horizontal
        required_torque = required_torque_nm * 1000.0  # N-mm
        required_force = total_mass_kg * GRAVITY
        peak_force = required_force * ACCEL_FACTOR

        counterbalance = total_mass_kg * GRAVITY * 0.7

        motor_match = select_motor(required_torque, 60.0, tuple(motors))

        # Speed estimate: 90 degrees in a reasonable time
        motor_rpm = motor_match.output_rpm
        time_per_rev_s = 60.0 / motor_rpm if motor_rpm > 0 else float("inf")
        time_to_height = time_per_rev_s * 0.25  # quarter turn
        speed_mm_s = max_height_mm / time_to_height if time_to_height > 0 else 0

        notes.append("4-bar linkage — torque varies with angle (worst at horizontal)")
        notes.append(f"Counterbalance with {counterbalance:.1f}N spring at pivot")
        actual_spool = 0.0

    else:  # "arm"
        arm_length_mm = max_height_mm
        arm_length_m = arm_length_mm / 1000.0
        required_torque_nm = total_mass_kg * GRAVITY * arm_length_m
        required_torque = required_torque_nm * 1000.0
        required_force = total_mass_kg * GRAVITY
        peak_force = required_force * ACCEL_FACTOR
        counterbalance = total_mass_kg * GRAVITY * 0.5

        motor_match = select_motor(required_torque, 40.0, tuple(motors))

        motor_rpm = motor_match.output_rpm
        time_per_rev_s = 60.0 / motor_rpm if motor_rpm > 0 else float("inf")
        time_to_height = time_per_rev_s * 0.25
        speed_mm_s = max_height_mm / time_to_height if time_to_height > 0 else 0

        notes.append("Simple arm — keep payload light for best performance")
        actual_spool = 0.0

    return LiftAnalysis(
        required_force_n=round(required_force, 2),
        peak_force_n=round(peak_force, 2),
        required_torque_nmm=round(required_torque, 1),
        motor_recommendation=motor_match.motor_name,
        gear_ratio=motor_match.gear_ratio,
        max_speed_mm_s=round(speed_mm_s, 1),
        time_to_max_height_s=round(time_to_height, 2),
        counterbalance_force_n=round(counterbalance, 2),
        spool_diameter_mm=actual_spool,
        lift_type=lift_type,
        notes=tuple(notes),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_lift.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/mechanisms/lift.py tests/unit/test_lift.py
git commit -m "feat(mechanisms): add lift physics — elevator force, 4-bar torque, counterbalance, spool sizing"
```

---

### Task 6: Motion Profiles

**Files:**
- Create: `src/robotics_design_advisor/mechanisms/motion.py`
- Test: `tests/unit/test_motion.py`

**Interfaces:**
- Consumes: `MotionProfile` from `mechanisms/models.py`
- Produces: `calc_motion_profile(distance_mm, max_velocity_mm_s, wheel_diameter_mm, encoder_ticks_per_rev, gear_ratio, acceleration_mm_s2) -> MotionProfile`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_motion.py
"""Tests for trapezoidal motion profile calculations."""

import math

import pytest

from robotics_design_advisor.mechanisms.motion import (
    calc_encoder_ticks,
    calc_motion_profile,
)
from robotics_design_advisor.mechanisms.models import MotionProfile


class TestCalcEncoderTicks:
    def test_one_wheel_revolution(self):
        """One revolution of a 96mm wheel = pi*96 ≈ 301.6mm."""
        wheel_diam = 96.0
        circumference = math.pi * wheel_diam
        ticks = calc_encoder_ticks(
            distance_mm=circumference,
            wheel_diameter_mm=wheel_diam,
            ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert ticks == 538  # rounded from 537.7

    def test_gear_ratio_multiplies_ticks(self):
        ticks_1x = calc_encoder_ticks(300.0, 96.0, 537.7, 1.0)
        ticks_2x = calc_encoder_ticks(300.0, 96.0, 537.7, 2.0)
        assert ticks_2x == ticks_1x * 2

    def test_zero_distance_returns_zero(self):
        ticks = calc_encoder_ticks(0.0, 96.0, 537.7, 1.0)
        assert ticks == 0


class TestCalcMotionProfile:
    def test_returns_motion_profile(self):
        result = calc_motion_profile(
            distance_mm=1000.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert isinstance(result, MotionProfile)
        assert result.total_ticks > 0
        assert result.total_time_s > 0

    def test_tick_phases_sum_to_total(self):
        result = calc_motion_profile(
            distance_mm=1000.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert result.accel_ticks + result.cruise_ticks + result.decel_ticks == result.total_ticks

    def test_short_distance_triangular_profile(self):
        """Short distance may not reach cruise velocity → triangular profile."""
        result = calc_motion_profile(
            distance_mm=50.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        # Cruise ticks should be 0 or very small for triangular profile
        assert result.cruise_ticks <= result.total_ticks

    def test_pid_gains_are_positive(self):
        result = calc_motion_profile(
            distance_mm=1000.0,
            max_velocity_mm_s=500.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        assert result.suggested_kp > 0
        assert result.suggested_ki >= 0
        assert result.suggested_kd > 0

    def test_higher_gear_ratio_more_ticks(self):
        result_1x = calc_motion_profile(
            distance_mm=500.0,
            max_velocity_mm_s=300.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=1.0,
        )
        result_2x = calc_motion_profile(
            distance_mm=500.0,
            max_velocity_mm_s=300.0,
            wheel_diameter_mm=96.0,
            encoder_ticks_per_rev=537.7,
            gear_ratio=2.0,
        )
        assert result_2x.total_ticks > result_1x.total_ticks

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="distance_mm"):
            calc_motion_profile(
                distance_mm=0.0,
                max_velocity_mm_s=500.0,
                wheel_diameter_mm=96.0,
                encoder_ticks_per_rev=537.7,
                gear_ratio=1.0,
            )

    def test_zero_velocity_raises(self):
        with pytest.raises(ValueError, match="max_velocity_mm_s"):
            calc_motion_profile(
                distance_mm=500.0,
                max_velocity_mm_s=0.0,
                wheel_diameter_mm=96.0,
                encoder_ticks_per_rev=537.7,
                gear_ratio=1.0,
            )

    def test_zero_wheel_diameter_raises(self):
        with pytest.raises(ValueError, match="wheel_diameter_mm"):
            calc_motion_profile(
                distance_mm=500.0,
                max_velocity_mm_s=300.0,
                wheel_diameter_mm=0.0,
                encoder_ticks_per_rev=537.7,
                gear_ratio=1.0,
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_motion.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/mechanisms/motion.py
"""Motion profiles — encoder ticks, trapezoidal velocity, PID starting points.

Pure functions, no I/O.
"""

from __future__ import annotations

import math

from .models import MotionProfile

DEFAULT_ACCELERATION_MM_S2 = 1000.0  # reasonable default for FTC drivetrains


def calc_encoder_ticks(
    distance_mm: float,
    wheel_diameter_mm: float,
    ticks_per_rev: float,
    gear_ratio: float,
) -> int:
    """Convert a linear distance to encoder ticks.

    ticks = (distance / wheel_circumference) * ticks_per_rev * gear_ratio
    """
    if distance_mm == 0:
        return 0
    circumference = math.pi * wheel_diameter_mm
    revolutions = distance_mm / circumference
    return round(revolutions * ticks_per_rev * gear_ratio)


def calc_motion_profile(
    distance_mm: float,
    max_velocity_mm_s: float,
    wheel_diameter_mm: float,
    encoder_ticks_per_rev: float,
    gear_ratio: float,
    acceleration_mm_s2: float = DEFAULT_ACCELERATION_MM_S2,
) -> MotionProfile:
    """Calculate a trapezoidal motion profile with encoder tick breakdowns.

    Parameters
    ----------
    distance_mm : float
        Target travel distance (must be > 0).
    max_velocity_mm_s : float
        Maximum cruise velocity (must be > 0).
    wheel_diameter_mm : float
        Drive wheel outer diameter (must be > 0).
    encoder_ticks_per_rev : float
        Encoder resolution (ticks per motor shaft revolution).
    gear_ratio : float
        External gear ratio (motor-to-wheel).
    acceleration_mm_s2 : float
        Acceleration rate (default 1000 mm/s^2).
    """
    if distance_mm <= 0:
        raise ValueError(f"distance_mm must be positive, got {distance_mm}")
    if max_velocity_mm_s <= 0:
        raise ValueError(f"max_velocity_mm_s must be positive, got {max_velocity_mm_s}")
    if wheel_diameter_mm <= 0:
        raise ValueError(f"wheel_diameter_mm must be positive, got {wheel_diameter_mm}")
    if acceleration_mm_s2 <= 0:
        raise ValueError(f"acceleration_mm_s2 must be positive, got {acceleration_mm_s2}")

    # Time and distance to accelerate to max velocity
    accel_time = max_velocity_mm_s / acceleration_mm_s2
    accel_distance = 0.5 * acceleration_mm_s2 * accel_time**2

    # Deceleration mirrors acceleration
    decel_time = accel_time
    decel_distance = accel_distance

    # Check if we can reach cruise velocity (triangular vs trapezoidal)
    if accel_distance + decel_distance >= distance_mm:
        # Triangular profile — never reaches full cruise speed
        # d = 2 * (0.5 * a * t^2)  =>  t = sqrt(d / a)
        half_time = math.sqrt(distance_mm / acceleration_mm_s2)
        accel_time = half_time
        decel_time = half_time
        accel_distance = distance_mm / 2.0
        decel_distance = distance_mm / 2.0
        cruise_distance = 0.0
        cruise_time = 0.0
        actual_max_v = acceleration_mm_s2 * half_time
    else:
        cruise_distance = distance_mm - accel_distance - decel_distance
        cruise_time = cruise_distance / max_velocity_mm_s
        actual_max_v = max_velocity_mm_s

    total_time = accel_time + cruise_time + decel_time

    # Convert distances to ticks
    total_ticks = calc_encoder_ticks(distance_mm, wheel_diameter_mm, encoder_ticks_per_rev, gear_ratio)
    accel_ticks = calc_encoder_ticks(accel_distance, wheel_diameter_mm, encoder_ticks_per_rev, gear_ratio)
    decel_ticks = calc_encoder_ticks(decel_distance, wheel_diameter_mm, encoder_ticks_per_rev, gear_ratio)
    cruise_ticks = total_ticks - accel_ticks - decel_ticks

    # Cruise velocity in ticks per second
    circumference = math.pi * wheel_diameter_mm
    ticks_per_mm = (encoder_ticks_per_rev * gear_ratio) / circumference
    cruise_velocity_tps = actual_max_v * ticks_per_mm

    # PID starting points (heuristic for FTC motor controllers)
    # Kp: small proportional gain based on total ticks
    kp = 10.0 / total_ticks if total_ticks > 0 else 0.01
    ki = 0.0  # start with zero integral
    kd = kp * 0.1  # derivative = 10% of proportional

    notes: list[str] = []
    if cruise_ticks <= 0:
        notes.append("Triangular profile — distance too short to reach cruise velocity")
    notes.append(f"Peak velocity: {actual_max_v:.0f} mm/s")
    notes.append(f"Acceleration: {acceleration_mm_s2:.0f} mm/s^2")
    notes.append("PID gains are starting points — tune on actual robot")

    return MotionProfile(
        total_ticks=total_ticks,
        cruise_velocity_tps=round(cruise_velocity_tps, 1),
        accel_ticks=accel_ticks,
        decel_ticks=decel_ticks,
        cruise_ticks=cruise_ticks,
        total_time_s=round(total_time, 3),
        accel_time_s=round(accel_time, 3),
        suggested_kp=round(kp, 6),
        suggested_ki=ki,
        suggested_kd=round(kd, 6),
        notes=tuple(notes),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_motion.py -v`
Expected: 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/mechanisms/motion.py tests/unit/test_motion.py
git commit -m "feat(mechanisms): add motion profiles — encoder ticks, trapezoidal velocity, PID starting points"
```

---

## Summary

| Task | Module | Tests | Physics |
|------|--------|-------|---------|
| 1 | `models.py` | 6 | Frozen dataclasses for all mechanism outputs |
| 2 | `motor_selection.py` | 12 | Load motor DB, score by torque+speed, select best match |
| 3 | `grabber.py` | 11 | Grip force, servo torque, grip type recommendation |
| 4 | `launcher.py` | 10 | Ballistics, flywheel RPM, catapult springs, optimal angles |
| 5 | `lift.py` | 10 | Elevator force, 4-bar torque, counterbalance, spool sizing |
| 6 | `motion.py` | 11 | Encoder ticks, trapezoidal profiles, PID starting points |
| **Total** | **7 files** | **~60** | |
