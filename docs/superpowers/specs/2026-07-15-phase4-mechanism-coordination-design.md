# Phase 4: Mechanism Intelligence & Autonomous Coordination — Design Spec

## Purpose

Give Claude the physics, planning, and game knowledge to design complete
robot subsystems — not just pick parts, but answer "what motor?", "how fast?",
"what path?", and "how do all subsystems coordinate in autonomous mode?"

Phase 4 has three sub-phases that build on each other:

```
4A: Mechanism Physics Engine
    "What torque does the grabber need? What RPM for the launcher?"
        │
        ▼
4B: Autonomous Coordination Layer
    "Drive 2m forward, turn 90°, extend arm, grab, retract, drive back"
        │
        ▼
4C: Season-Aware Design Advisor
    "For INTO THE DEEP 2025, here's your full robot: BOM + auto routine + code skeleton"
```

---

## Phase 4A: Mechanism Physics Engine

### Purpose

Calculate the physics behind each robot mechanism so Claude can recommend
motors, servos, gear ratios, and validate that a design will actually work
before the team builds it.

### Package: `src/robotics_design_advisor/mechanisms/`

| Module | Responsibility |
|--------|---------------|
| `__init__.py` | Package exports |
| `grabber.py` | Claw/intake torque, grip force, servo selection, compliance |
| `launcher.py` | Flywheel ballistics, catapult spring force, launch angle optimization |
| `lift.py` | Elevator force, 4-bar arm torque curve, motor+gear ratio selection |
| `motion.py` | Distance↔encoder ticks, velocity profiles, acceleration, PID starting points |
| `models.py` | Frozen dataclasses for all mechanism types |
| `motor_selection.py` | Given a torque+speed requirement, recommend goBILDA motor + gear ratio |

### Module Details

#### grabber.py

**Inputs:** game piece weight (g), dimensions (mm), grip type (claw/roller/passive)

**Outputs:** `GrabberAnalysis`

```python
@dataclass(frozen=True)
class GrabberAnalysis:
    required_grip_force_n: float     # force to hold piece (weight × safety factor × friction)
    required_torque_nmm: float       # servo torque at jaw tip
    recommended_servo: str           # e.g. "goBILDA Torque Servo" or "REV SRS"
    jaw_opening_mm: float            # minimum opening for game piece
    grip_type: str                   # "claw" | "roller_intake" | "passive_funnel"
    hold_current_ma: float           # servo holding current estimate
    notes: list[str]                 # design tips
```

**Key physics:**
- Grip force = (piece_weight × gravity × safety_factor) / friction_coefficient
- Servo torque = grip_force × jaw_length (lever arm)
- Roller intake: friction_force = normal_force × rubber_coefficient
- Passive funnel: no motor needed, geometry-only design

**Grip type selection rules:**
- Cube/box → claw (parallel grip or pivot)
- Ball/sphere → roller intake (continuous feed) or funnel
- Ring/cylinder → hook + passive capture
- Cone (FTC 2023 style) → claw with compliance
- Pixel/hexagon → roller + guide rails

#### launcher.py

**Inputs:** target distance (m), target height (m), projectile mass (g),
projectile diameter (mm), launcher type (flywheel/catapult/linear_punch)

**Outputs:** `LauncherAnalysis`

```python
@dataclass(frozen=True)
class LauncherAnalysis:
    launch_velocity_ms: float        # required exit velocity
    launch_angle_deg: float          # optimal angle for distance + height
    flywheel_rpm: float              # if flywheel type
    flywheel_diameter_mm: float      # wheel size
    motor_recommendation: str        # motor + gear ratio
    spin_up_time_s: float            # time to reach launch RPM
    energy_per_shot_j: float         # kinetic energy
    fire_rate_hz: float              # max shots per second
    catapult_spring_force_n: float   # if catapult type
    notes: list[str]
```

**Key physics:**
- Projectile: v = sqrt((g × d²) / (d × sin(2θ) - 2h × cos²(θ)))
- Flywheel: surface_speed = π × diameter × RPM / 60
- Energy transfer efficiency: ~50-70% for compliant wheels
- Spin-up: τ = I × α (moment of inertia × angular acceleration)
- Catapult: E_spring = 0.5 × k × x², E_kinetic = 0.5 × m × v²

#### lift.py

**Inputs:** payload mass (g), max height (mm), lift type (elevator/4bar/arm),
number of stages (for elevator)

**Outputs:** `LiftAnalysis`

```python
@dataclass(frozen=True)
class LiftAnalysis:
    required_force_n: float          # continuous lifting force
    peak_force_n: float              # acceleration + payload
    required_torque_nmm: float       # at motor shaft after gearing
    motor_recommendation: str        # motor + gear ratio
    gear_ratio: float                # recommended ratio
    max_speed_mm_s: float            # lift speed at recommended ratio
    time_to_max_height_s: float      # full extension time
    counterbalance_force_n: float    # spring/elastic counterbalance suggestion
    spool_diameter_mm: float         # for string/belt elevator
    notes: list[str]
```

**Key physics:**
- Elevator: F = (m_payload + m_carriage) × g × stages × friction_factor
- 4-bar arm: τ = m × g × L × cos(θ) (varies with angle)
- Counterbalance: constant-force spring matches gravity torque curve
- Spool: torque = force × spool_radius, speed = angular_vel × spool_radius
- Continuous duty: motor must sustain load without overheating

**Lift type guidance:**
- Elevator: best for vertical-only, high reach, multiple stages
- 4-bar: best for arc motion, combined reach + rotation
- Single arm: simplest, limited height, good for light payloads
- Cascade: highest reach-to-stow ratio

#### motion.py

**Inputs:** distance (mm), max velocity (mm/s), wheel diameter (mm),
encoder ticks per revolution, gear ratio

**Outputs:** `MotionProfile`

```python
@dataclass(frozen=True)
class MotionProfile:
    total_ticks: int                 # encoder ticks for distance
    cruise_velocity_tps: float       # ticks per second at max speed
    accel_ticks: int                 # ticks during acceleration phase
    decel_ticks: int                 # ticks during deceleration phase
    cruise_ticks: int                # ticks at constant speed
    total_time_s: float              # total move time
    accel_time_s: float              # acceleration phase duration
    suggested_kp: float              # PID proportional gain starting point
    suggested_ki: float              # PID integral gain starting point
    suggested_kd: float              # PID derivative gain starting point
    notes: list[str]
```

**Key physics:**
- Ticks = (distance / (π × wheel_diameter)) × ticks_per_rev × gear_ratio
- Trapezoidal profile: accel phase → cruise phase → decel phase
- Accel time = v_max / acceleration
- Total time = accel_time + cruise_time + decel_time
- PID starting points: Kp based on motor characteristics, Kd = Kp × 0.1

#### motor_selection.py

**Inputs:** required torque (N·mm), required speed (RPM), duty cycle (continuous/intermittent)

**Outputs:** `MotorRecommendation`

```python
@dataclass(frozen=True)
class MotorRecommendation:
    motor_name: str                  # e.g. "goBILDA 5202 Series Yellow Jacket"
    motor_sku: str                   # goBILDA SKU
    base_rpm: float                  # motor free speed
    stall_torque_nmm: float          # motor stall torque
    gear_ratio: float                # recommended gear ratio
    output_rpm: float                # after gearing
    output_torque_nmm: float         # after gearing
    torque_margin_pct: float         # how much headroom (should be >20%)
    current_draw_a: float            # estimated operating current
    notes: list[str]
```

**Motor database:**
Uses existing `engineering/motor_data/gobilda_yellow_jacket.json` for specs.
Yellow Jacket planetary ratios: 3.7:1, 5.2:1, 13.7:1, 19.2:1, 26.9:1, 50.9:1, 71.2:1, 188.2:1

---

## Phase 4B: Autonomous Coordination Layer

### Purpose

Plan and validate autonomous routines — field positioning, path planning,
and state machine coordination across all subsystems.

### Package: `src/robotics_design_advisor/autonomous/`

| Module | Responsibility |
|--------|---------------|
| `__init__.py` | Package exports |
| `field.py` | Field coordinate system, zone definitions, starting positions |
| `path_planner.py` | Waypoint sequences, spline paths, distance/time estimates |
| `state_machine.py` | Action sequences with timing, transitions, sensor triggers |
| `sensors.py` | Sensor recommendations per task (which sensor for which job) |
| `models.py` | Frozen dataclasses for field, paths, states |

#### field.py

**Covers both FTC and FRC fields:**

```python
@dataclass(frozen=True)
class FieldConfig:
    width_mm: float              # FTC: 3658 (144"), FRC: 16459 (54'1")
    length_mm: float             # FTC: 3658 (144"), FRC: 8229 (27')
    alliance: str                # "red" | "blue"
    zones: tuple[Zone, ...]      # scoring zones, pickup zones, parking
    starting_positions: tuple[Pose, ...]  # legal starting positions

@dataclass(frozen=True)
class Pose:
    x_mm: float
    y_mm: float
    heading_deg: float           # 0 = facing positive X

@dataclass(frozen=True)
class Zone:
    name: str                    # "net_zone", "high_basket", "observation"
    center: Pose
    radius_mm: float             # allowable positioning tolerance
    zone_type: str               # "scoring" | "pickup" | "parking" | "human_player"
```

#### path_planner.py

**Inputs:** start Pose, sequence of target Poses, robot constraints (max speed, max accel)

**Outputs:** `PlannedPath`

```python
@dataclass(frozen=True)
class PathSegment:
    start: Pose
    end: Pose
    distance_mm: float
    estimated_time_s: float
    segment_type: str            # "drive" | "turn" | "strafe" | "spline"

@dataclass(frozen=True)
class PlannedPath:
    segments: tuple[PathSegment, ...]
    total_distance_mm: float
    total_time_s: float
    waypoints: tuple[Pose, ...]
```

**Key logic:**
- Point-to-point: straight-line distance + turn time
- Spline paths: cubic Hermite or Bezier curves for smooth motion
- Time budgeting: FTC auto = 30s, FRC auto = 15s — every segment must fit
- Heading optimization: minimize total rotation

#### state_machine.py

**Defines autonomous routines as action sequences:**

```python
@dataclass(frozen=True)
class Action:
    name: str                    # "drive_to_basket", "extend_arm", "open_claw"
    subsystem: str               # "drivetrain" | "arm" | "grabber" | "launcher"
    duration_s: float            # estimated time
    parameters: dict             # subsystem-specific params
    wait_for: str                # "" | "sensor_trigger" | "encoder_target" | "timer"
    parallel_with: str           # action that can run simultaneously

@dataclass(frozen=True)
class AutonomousRoutine:
    name: str                    # "2+0 basket auto", "5 specimen auto"
    competition: str             # "FTC" | "FRC"
    actions: tuple[Action, ...]
    total_time_s: float
    time_margin_s: float         # buffer before auto period ends
    scoring_potential: int       # estimated points scored
```

**Coordination rules:**
- Parallel actions on different subsystems (drive + arm raise)
- Sequential actions on same subsystem (can't grab while arm moving)
- Sensor gates: wait for beam break before closing claw
- Safety interlocks: don't open grabber while arm is stowed
- Time budgets: warn if total exceeds auto period

#### sensors.py

**Recommends sensors for each autonomous task:**

```python
@dataclass(frozen=True)
class SensorRecommendation:
    task: str                    # "piece_detection", "distance_to_wall", "field_position"
    sensor_type: str             # "distance_tof", "color", "imu", "encoder", "camera"
    sensor_name: str             # specific product name
    mounting_location: str       # "front_bumper", "claw_interior", "chassis_center"
    rationale: str
```

**Sensor selection rules:**

| Task | Primary sensor | Backup |
|------|---------------|--------|
| Piece in grabber? | Beam break / distance ToF | Color sensor |
| Distance to wall | REV 2m distance sensor | Ultrasonic |
| Field position | Dead wheel odometry + IMU | AprilTag camera |
| Heading | IMU (REV hub built-in) | Dual odometry |
| Line detection | REV color sensor (downward) | — |
| Target alignment | Webcam + AprilTag | Distance sensors |

---

## Phase 4C: Season-Aware Design Advisor

### Purpose

Tie everything together: load a specific FTC/FRC season's game data,
analyze the game, and generate a complete robot design recommendation
including BOM, mechanism specs, auto routines, and code skeleton.

### Package: extends `src/robotics_design_advisor/engineering/`

| Module | Responsibility |
|--------|---------------|
| `game_analyzer.py` | Parse season game manual data, identify scoring actions, prioritize strategies |
| `bom_generator.py` | Given a validated design → complete bill of materials with quantities + costs |
| `design_synthesizer.py` | Orchestrate: game analysis → archetype selection → mechanism sizing → BOM → auto routine |

#### game_analyzer.py

**Inputs:** season JSON (extends existing `seasons/` data)

**Enhanced season schema:**

```json
{
  "season": "INTO THE DEEP",
  "year": "2024-2025",
  "competition": "FTC",
  "game_pieces": [
    {
      "name": "sample",
      "type": "cube",
      "weight_g": 28,
      "dimensions_mm": [38, 38, 38],
      "material": "foam",
      "friction_coefficient": 0.7
    },
    {
      "name": "specimen",
      "type": "clip",
      "weight_g": 35,
      "dimensions_mm": [50, 30, 80],
      "grip_method": "hook_and_clip"
    }
  ],
  "scoring_actions": [
    {
      "name": "net_zone_sample",
      "points": 2,
      "mechanism": "grabber",
      "target_location": {"x": 600, "y": 600, "z": 0},
      "difficulty": "easy",
      "cycle_time_s": 8
    },
    {
      "name": "high_basket_sample",
      "points": 8,
      "mechanism": "lift+grabber",
      "target_location": {"x": 300, "y": 300, "z": 1060},
      "difficulty": "hard",
      "cycle_time_s": 15
    },
    {
      "name": "high_chamber_specimen",
      "points": 10,
      "mechanism": "arm+grabber",
      "target_location": {"x": 1829, "y": 0, "z": 660},
      "difficulty": "medium",
      "cycle_time_s": 12
    }
  ],
  "field": {
    "width_mm": 3658,
    "length_mm": 3658,
    "zones": [
      {"name": "net_zone", "center": [600, 600], "radius_mm": 300, "type": "scoring"},
      {"name": "observation_zone", "center": [3058, 600], "radius_mm": 300, "type": "pickup"}
    ]
  },
  "endgame": [
    {"name": "level_1_ascent", "points": 3, "mechanism": "passive"},
    {"name": "level_2_ascent", "points": 15, "mechanism": "active_hang"},
    {"name": "level_3_ascent", "points": 30, "mechanism": "active_hang+pull"}
  ],
  "constraints": {
    "auto_period_s": 30,
    "teleop_period_s": 120,
    "endgame_period_s": 30,
    "max_pieces_preloaded": 1
  }
}
```

**Output:** `GameAnalysis` with prioritized strategies

```python
@dataclass(frozen=True)
class ScoringStrategy:
    name: str                     # "high_basket_focused", "specimen_speed"
    expected_auto_points: int
    expected_teleop_points: int
    expected_endgame_points: int
    total_expected_points: int
    required_mechanisms: tuple[str, ...]  # ("elevator", "grabber", "drivetrain")
    difficulty: str               # "beginner" | "intermediate" | "advanced"
    rationale: str

@dataclass(frozen=True)
class GameAnalysis:
    season: str
    strategies: tuple[ScoringStrategy, ...]
    recommended_strategy: str     # name of best strategy for team level
    game_pieces: tuple[dict, ...]
    field_config: dict
```

#### bom_generator.py

**Inputs:** validated design (archetype + mechanism analyses)

**Outputs:** `BillOfMaterials`

```python
@dataclass(frozen=True)
class BOMItem:
    sku: str
    name: str
    quantity: int
    unit_price_usd: float
    category: str                 # "structure", "motion", "electronics", "hardware"
    subsystem: str                # "drivetrain", "arm", "grabber", "electronics"
    notes: str

@dataclass(frozen=True)
class BillOfMaterials:
    items: tuple[BOMItem, ...]
    total_cost_usd: float
    total_weight_g: float
    warnings: tuple[str, ...]     # "Over 18" height limit", "8 motor limit"
    subsystem_breakdown: dict     # subsystem → (cost, weight, part_count)
```

#### design_synthesizer.py

**The orchestrator — ties all of Phase 4 together:**

```
User: "Design a competitive FTC robot for INTO THE DEEP"
                    │
                    ▼
            ┌──────────────┐
            │ game_analyzer │  Analyze season, prioritize strategies
            └──────┬───────┘
                   │ recommended strategy + game pieces
                   ▼
            ┌──────────────┐
            │design_advisor│  Select archetype, apply constraints (Phase 2)
            └──────┬───────┘
                   │ archetype + base design
                   ▼
         ┌─────────────────┐
         │ mechanism sizing │  grabber + launcher + lift + motion (Phase 4A)
         └────────┬────────┘
                  │ mechanism analyses with motor selections
                  ▼
         ┌────────────────┐
         │ path_planner + │  Auto routine + sensor plan (Phase 4B)
         │ state_machine  │
         └────────┬───────┘
                  │ autonomous routine
                  ▼
         ┌────────────────┐
         │ bom_generator  │  Full parts list with costs
         └────────┬───────┘
                  │
                  ▼
            ┌───────────┐
            │  Output:   │
            │  - BOM     │
            │  - Mech specs
            │  - Auto routine
            │  - Warnings │
            └───────────┘
```

---

## Implementation Order

1. **Phase 4A** — Mechanism Physics Engine (implement first)
   - `mechanisms/models.py`
   - `mechanisms/grabber.py` + tests
   - `mechanisms/launcher.py` + tests
   - `mechanisms/lift.py` + tests
   - `mechanisms/motion.py` + tests
   - `mechanisms/motor_selection.py` + tests

2. **Phase 4B** — Autonomous Coordination Layer
   - `autonomous/models.py`
   - `autonomous/field.py` + tests
   - `autonomous/path_planner.py` + tests
   - `autonomous/state_machine.py` + tests
   - `autonomous/sensors.py` + tests

3. **Phase 4C** — Season-Aware Design Advisor
   - Enhanced season JSON schema
   - `engineering/game_analyzer.py` + tests
   - `engineering/bom_generator.py` + tests
   - `engineering/design_synthesizer.py` + tests

## Testing Strategy

- All mechanism calculators: unit tests with known physics problems
- Path planner: test time budgets against FTC/FRC auto periods
- State machine: test parallel action validation, safety interlocks
- Integration: full pipeline from season JSON → BOM for INTO THE DEEP 2025

## Dependencies

No new external dependencies — all physics is pure Python math.
Uses existing motor data from Phase 2.
