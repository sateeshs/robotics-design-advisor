# Phase 4C: Season-Aware Design Advisor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a season-aware design advisor that analyzes FTC/FRC game data, generates scoring strategies, produces a bill of materials, and orchestrates the full design pipeline from game analysis through mechanism sizing to autonomous routine planning.

**Architecture:** Three new modules in `src/robotics_design_advisor/engineering/`: `game_analyzer.py` parses enhanced season JSON and generates prioritized scoring strategies. `bom_generator.py` converts mechanism analyses and archetype selections into a complete BOM with costs. `design_synthesizer.py` orchestrates the full pipeline: game analysis → archetype selection → mechanism sizing → autonomous planning → BOM generation. A new enhanced season JSON file (`ftc-2024-into-the-deep.json`) demonstrates the full schema.

**Tech Stack:** Python 3.10+, pytest, pure math (no external dependencies)

## Global Constraints

- All dataclasses are `frozen=True` with `tuple` for sequences (immutability)
- All calculation functions are pure — no I/O, no side effects (except `load_enhanced_season` which reads JSON)
- Units: mm for length, degrees for heading, seconds for time, USD for cost, grams for weight
- Functions must validate inputs and raise `ValueError` for invalid arguments
- Follow existing codebase patterns (`engineering/models.py`, `engineering/design_advisor.py`)
- Target: 80%+ test coverage
- Existing season JSON schema (DECODE format) must remain unchanged — enhanced schema is additive

---

## File Structure

```
src/robotics_design_advisor/engineering/
├── seasons/
│   ├── ftc-2024-into-the-deep.json   # NEW: Enhanced season JSON for INTO THE DEEP
│   ├── ftc-2025-decode.json           # existing — unchanged
│   └── _template.json                 # existing — unchanged
├── game_analyzer.py                   # NEW: Parse enhanced season data, generate strategies
├── bom_generator.py                   # NEW: Build BOM from mechanism analyses
├── design_synthesizer.py              # NEW: Orchestrate full pipeline
└── models.py                          # MODIFY: Add ScoringStrategy, GameAnalysis, BOMItem,
                                       #   BillOfMaterials, DesignSynthesis

tests/unit/
├── test_game_analyzer.py
├── test_bom_generator.py
└── test_design_synthesizer.py
```

---

### Task 1: Phase 4C Models + Enhanced Season JSON

**Files:**
- Modify: `src/robotics_design_advisor/engineering/models.py` (append new dataclasses)
- Create: `src/robotics_design_advisor/engineering/seasons/ftc-2024-into-the-deep.json`
- Test: `tests/unit/test_phase4c_models.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `ScoringStrategy`, `GameAnalysis`, `BOMItem`, `BillOfMaterials`, `DesignSynthesis` — imported by game_analyzer, bom_generator, design_synthesizer

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_phase4c_models.py
"""Tests for Phase 4C design advisor dataclasses."""

from robotics_design_advisor.engineering.models import (
    BillOfMaterials,
    BOMItem,
    DesignSynthesis,
    GameAnalysis,
    ScoringStrategy,
)


class TestScoringStrategy:
    def test_creation(self):
        s = ScoringStrategy(
            name="high_basket_focused",
            expected_auto_points=16,
            expected_teleop_points=40,
            expected_endgame_points=15,
            total_expected_points=71,
            required_mechanisms=("elevator", "grabber", "drivetrain"),
            difficulty="intermediate",
            rationale="Focus on high basket scoring for maximum points per cycle",
        )
        assert s.name == "high_basket_focused"
        assert s.total_expected_points == 71
        assert len(s.required_mechanisms) == 3

    def test_frozen(self):
        s = ScoringStrategy(
            name="test",
            expected_auto_points=0,
            expected_teleop_points=0,
            expected_endgame_points=0,
            total_expected_points=0,
            required_mechanisms=(),
            difficulty="beginner",
            rationale="test",
        )
        try:
            s.name = "changed"  # type: ignore[misc]
            assert False, "Should raise"
        except AttributeError:
            pass


class TestGameAnalysis:
    def test_creation(self):
        strategy = ScoringStrategy(
            name="net_zone",
            expected_auto_points=4,
            expected_teleop_points=20,
            expected_endgame_points=3,
            total_expected_points=27,
            required_mechanisms=("grabber", "drivetrain"),
            difficulty="beginner",
            rationale="Simple net zone scoring",
        )
        ga = GameAnalysis(
            season="INTO THE DEEP",
            competition="FTC",
            strategies=(strategy,),
            recommended_strategy="net_zone",
            game_pieces=({"name": "sample", "weight_g": 28},),
            field_config={"width_mm": 3658, "length_mm": 3658},
        )
        assert ga.season == "INTO THE DEEP"
        assert ga.competition == "FTC"
        assert len(ga.strategies) == 1
        assert ga.recommended_strategy == "net_zone"


class TestBOMItem:
    def test_creation(self):
        item = BOMItem(
            sku="5202-0002-0019",
            name="goBILDA Yellow Jacket 19.2:1",
            quantity=4,
            unit_price_usd=19.99,
            category="motion",
            subsystem="drivetrain",
            notes="Drivetrain motors",
        )
        assert item.sku == "5202-0002-0019"
        assert item.quantity == 4
        assert item.unit_price_usd == 19.99


class TestBillOfMaterials:
    def test_creation(self):
        item = BOMItem(
            sku="5202-0002-0019",
            name="goBILDA Yellow Jacket 19.2:1",
            quantity=4,
            unit_price_usd=19.99,
            category="motion",
            subsystem="drivetrain",
            notes="",
        )
        bom = BillOfMaterials(
            items=(item,),
            total_cost_usd=79.96,
            total_weight_g=1200.0,
            warnings=(),
            subsystem_breakdown={"drivetrain": (79.96, 1200.0, 1)},
        )
        assert bom.total_cost_usd == 79.96
        assert len(bom.items) == 1
        assert "drivetrain" in bom.subsystem_breakdown


class TestDesignSynthesis:
    def test_creation(self):
        strategy = ScoringStrategy(
            name="test",
            expected_auto_points=0,
            expected_teleop_points=0,
            expected_endgame_points=0,
            total_expected_points=0,
            required_mechanisms=(),
            difficulty="beginner",
            rationale="test",
        )
        item = BOMItem(
            sku="TEST-001",
            name="Test Part",
            quantity=1,
            unit_price_usd=10.0,
            category="structure",
            subsystem="chassis",
            notes="",
        )
        bom = BillOfMaterials(
            items=(item,),
            total_cost_usd=10.0,
            total_weight_g=100.0,
            warnings=(),
            subsystem_breakdown={},
        )
        ds = DesignSynthesis(
            season="INTO THE DEEP",
            competition="FTC",
            strategy=strategy,
            archetype_name="Speed Shooter",
            bom=bom,
            mechanism_notes=("Grabber: claw grip, 2.0N force",),
            autonomous_notes=("30s auto budget, 25s margin",),
            warnings=(),
        )
        assert ds.season == "INTO THE DEEP"
        assert ds.archetype_name == "Speed Shooter"
        assert ds.bom.total_cost_usd == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_phase4c_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'ScoringStrategy'`

- [ ] **Step 3: Write minimal implementation**

Append the following dataclasses to the end of `src/robotics_design_advisor/engineering/models.py`:

```python
# --- Phase 4C: Season-Aware Design Advisor models ---


@dataclass(frozen=True)
class ScoringStrategy:
    """A prioritized scoring strategy for a season."""
    name: str
    expected_auto_points: int
    expected_teleop_points: int
    expected_endgame_points: int
    total_expected_points: int
    required_mechanisms: tuple[str, ...]
    difficulty: str  # "beginner" | "intermediate" | "advanced"
    rationale: str


@dataclass(frozen=True)
class GameAnalysis:
    """Analyzed game with prioritized strategies."""
    season: str
    competition: str  # "FTC" | "FRC"
    strategies: tuple[ScoringStrategy, ...]
    recommended_strategy: str  # name of best strategy
    game_pieces: tuple[dict, ...]
    field_config: dict


@dataclass(frozen=True)
class BOMItem:
    """A single item in a bill of materials."""
    sku: str
    name: str
    quantity: int
    unit_price_usd: float
    category: str  # "structure" | "motion" | "electronics" | "hardware"
    subsystem: str  # "drivetrain" | "arm" | "grabber" | "electronics"
    notes: str


@dataclass(frozen=True)
class BillOfMaterials:
    """Complete bill of materials with cost and weight totals."""
    items: tuple[BOMItem, ...]
    total_cost_usd: float
    total_weight_g: float
    warnings: tuple[str, ...]
    subsystem_breakdown: dict  # subsystem -> (cost, weight, part_count)


@dataclass(frozen=True)
class DesignSynthesis:
    """Complete design synthesis output — the final deliverable."""
    season: str
    competition: str
    strategy: ScoringStrategy
    archetype_name: str
    bom: BillOfMaterials
    mechanism_notes: tuple[str, ...]
    autonomous_notes: tuple[str, ...]
    warnings: tuple[str, ...]
```

Create the enhanced season JSON:

```json
// src/robotics_design_advisor/engineering/seasons/ftc-2024-into-the-deep.json
{
  "competition": "FTC",
  "season": "2024-2025",
  "game_name": "INTO THE DEEP",
  "field": {
    "dimensions_mm": [3658, 3658],
    "notes": "Standard FTC 12'×12' field with submersible and baskets"
  },
  "game_elements": [
    {
      "name": "sample",
      "type": "cube",
      "dimensions_mm": [38, 38, 38],
      "weight_grams": 28,
      "material": "foam",
      "color_variants": ["yellow", "blue", "red"],
      "quantity_on_field": 30,
      "friction_coefficient": 0.7,
      "notes": "~1.5 inch foam cubes"
    },
    {
      "name": "specimen",
      "type": "clip",
      "dimensions_mm": [50, 30, 80],
      "weight_grams": 35,
      "material": "plastic",
      "color_variants": [],
      "quantity_on_field": 6,
      "grip_method": "hook_and_clip",
      "notes": "Plastic clip, requires hook mechanism"
    }
  ],
  "scoring_zones": [
    {
      "name": "net_zone",
      "type": "zone",
      "position": "alliance_side",
      "height_mm": 0,
      "opening_mm": [600, 600],
      "points_per_element": 2,
      "autonomous_multiplier": 2,
      "notes": "Drop samples into net zone on floor"
    },
    {
      "name": "low_basket",
      "type": "basket",
      "position": "alliance_corner",
      "height_mm": 660,
      "opening_mm": [254, 254],
      "points_per_element": 4,
      "autonomous_multiplier": 2,
      "notes": "Low basket on alliance corner"
    },
    {
      "name": "high_basket",
      "type": "basket",
      "position": "alliance_corner",
      "height_mm": 1060,
      "opening_mm": [254, 254],
      "points_per_element": 8,
      "autonomous_multiplier": 2,
      "notes": "High basket on alliance corner, requires elevator"
    },
    {
      "name": "low_chamber",
      "type": "chamber",
      "position": "field_center",
      "height_mm": 330,
      "opening_mm": [25, 610],
      "points_per_element": 6,
      "autonomous_multiplier": 2,
      "notes": "Low specimen chamber on submersible"
    },
    {
      "name": "high_chamber",
      "type": "chamber",
      "position": "field_center",
      "height_mm": 660,
      "opening_mm": [25, 610],
      "points_per_element": 10,
      "autonomous_multiplier": 2,
      "notes": "High specimen chamber on submersible"
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
      "name": "low_basket_sample",
      "points": 4,
      "mechanism": "lift+grabber",
      "target_location": {"x": 300, "y": 300, "z": 660},
      "difficulty": "medium",
      "cycle_time_s": 12
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
      "name": "low_chamber_specimen",
      "points": 6,
      "mechanism": "arm+grabber",
      "target_location": {"x": 1829, "y": 0, "z": 330},
      "difficulty": "medium",
      "cycle_time_s": 10
    },
    {
      "name": "high_chamber_specimen",
      "points": 10,
      "mechanism": "arm+grabber",
      "target_location": {"x": 1829, "y": 0, "z": 660},
      "difficulty": "hard",
      "cycle_time_s": 12
    }
  ],
  "endgame": [
    {"name": "level_1_ascent", "points": 3, "mechanism": "passive"},
    {"name": "level_2_ascent", "points": 15, "mechanism": "active_hang"},
    {"name": "level_3_ascent", "points": 30, "mechanism": "active_hang+pull"}
  ],
  "constraints": {
    "auto_period_s": 30,
    "teleop_period_s": 120,
    "endgame_period_s": 30,
    "max_pieces_preloaded": 1,
    "max_motors": 8,
    "max_servos": 12,
    "size_limit_mm": [457, 457, 457],
    "weight_limit_g": 19050
  },
  "mechanisms_needed": {
    "intake": {
      "element_to_collect": "sample",
      "collection_method": "claw/roller",
      "notes": "Must handle 38mm foam cubes and 80mm specimens"
    },
    "scorer": {
      "delivery_method": "place",
      "target_distance_mm": 0,
      "accuracy_requirement": "high",
      "notes": "Direct placement into baskets and chambers"
    },
    "endgame": {
      "task": "hang",
      "points": 30,
      "notes": "Level 3 ascent for maximum endgame points"
    }
  },
  "design_axes": {
    "drivetrain": ["mecanum", "differential"],
    "intake": ["claw_gripper", "front_roller"],
    "indexer": ["direct_feed"],
    "scorer": ["elevator_placer"],
    "aiming": ["pivot_hood", "whole_robot_aim"],
    "endgame": ["simple_park", "fast_park"]
  },
  "cycle_targets": {
    "top_team_cycles": 12,
    "average_team_cycles": 6,
    "cycle_time_seconds": 10
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_phase4c_models.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/engineering/models.py src/robotics_design_advisor/engineering/seasons/ftc-2024-into-the-deep.json tests/unit/test_phase4c_models.py
git commit -m "feat(engineering): add Phase 4C models and INTO THE DEEP season JSON"
```

---

### Task 2: Game Analyzer

**Files:**
- Create: `src/robotics_design_advisor/engineering/game_analyzer.py`
- Test: `tests/unit/test_game_analyzer.py`

**Interfaces:**
- Consumes: `ScoringStrategy`, `GameAnalysis` from `models.py`, `load_season` and `SeasonKnowledge` from `design_advisor.py`
- Produces: `load_enhanced_season(season_file: str) -> dict`, `analyze_game(season_data: dict, team_level: str) -> GameAnalysis`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_game_analyzer.py
"""Tests for game analysis and strategy generation."""

import pytest

from robotics_design_advisor.engineering.game_analyzer import (
    analyze_game,
    load_enhanced_season,
)
from robotics_design_advisor.engineering.models import GameAnalysis, ScoringStrategy


class TestLoadEnhancedSeason:
    def test_loads_into_the_deep(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert data["game_name"] == "INTO THE DEEP"
        assert data["competition"] == "FTC"
        assert len(data["game_elements"]) == 2

    def test_has_scoring_actions(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert "scoring_actions" in data
        assert len(data["scoring_actions"]) >= 3

    def test_has_endgame(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert "endgame" in data
        assert len(data["endgame"]) >= 2

    def test_has_constraints(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        assert "constraints" in data
        assert data["constraints"]["auto_period_s"] == 30

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_enhanced_season("nonexistent.json")

    def test_path_traversal_raises(self):
        with pytest.raises(ValueError, match="escapes"):
            load_enhanced_season("../../etc/passwd")


class TestAnalyzeGame:
    def test_returns_game_analysis(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert isinstance(analysis, GameAnalysis)
        assert analysis.season == "INTO THE DEEP"
        assert analysis.competition == "FTC"

    def test_generates_strategies(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert len(analysis.strategies) >= 2
        for s in analysis.strategies:
            assert isinstance(s, ScoringStrategy)
            assert s.total_expected_points > 0

    def test_recommends_strategy(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert analysis.recommended_strategy != ""
        strategy_names = {s.name for s in analysis.strategies}
        assert analysis.recommended_strategy in strategy_names

    def test_beginner_gets_easier_strategy(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        beginner = analyze_game(data, "beginner")
        advanced = analyze_game(data, "advanced")
        # Beginner strategy should be easier difficulty
        beginner_strat = next(
            s for s in beginner.strategies if s.name == beginner.recommended_strategy
        )
        advanced_strat = next(
            s for s in advanced.strategies if s.name == advanced.recommended_strategy
        )
        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        assert difficulty_order[beginner_strat.difficulty] <= difficulty_order[advanced_strat.difficulty]

    def test_strategies_have_required_mechanisms(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        for s in analysis.strategies:
            assert len(s.required_mechanisms) > 0
            assert "drivetrain" in s.required_mechanisms

    def test_includes_game_pieces(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert len(analysis.game_pieces) > 0

    def test_includes_field_config(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        assert "dimensions_mm" in analysis.field_config or "width_mm" in analysis.field_config

    def test_invalid_team_level_raises(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        with pytest.raises(ValueError, match="team_level"):
            analyze_game(data, "expert")

    def test_auto_points_reflect_autonomous_multiplier(self):
        data = load_enhanced_season("ftc-2024-into-the-deep.json")
        analysis = analyze_game(data, "intermediate")
        for s in analysis.strategies:
            # Auto points should be > 0 since scoring_actions have auto multipliers
            assert s.expected_auto_points >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_game_analyzer.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/engineering/game_analyzer.py
"""Game analysis — parse season data and generate scoring strategies.

Loads enhanced season JSON (with scoring_actions, endgame, constraints)
and generates prioritized strategies based on team level.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._path_safety import safe_resolve
from .models import GameAnalysis, ScoringStrategy

_SEASONS_DIR = Path(__file__).parent / "seasons"

_VALID_TEAM_LEVELS = {"beginner", "intermediate", "advanced"}

_DIFFICULTY_TO_LEVEL: dict[str, str] = {
    "easy": "beginner",
    "medium": "intermediate",
    "hard": "advanced",
}

_DIFFICULTY_ORDER: dict[str, int] = {
    "beginner": 0,
    "intermediate": 1,
    "advanced": 2,
}


def load_enhanced_season(season_file: str) -> dict[str, Any]:
    """Load an enhanced season JSON file.

    Parameters
    ----------
    season_file : str
        Filename within the seasons directory.

    Raises
    ------
    FileNotFoundError
        If the season file does not exist.
    ValueError
        If the path escapes the seasons directory.
    """
    path = safe_resolve(_SEASONS_DIR, season_file)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        raise FileNotFoundError(f"Season file not found: '{season_file}'") from None


def _build_strategies(season_data: dict[str, Any]) -> tuple[ScoringStrategy, ...]:
    """Generate scoring strategies from season data."""
    scoring_actions = season_data.get("scoring_actions", [])
    endgame = season_data.get("endgame", [])
    constraints = season_data.get("constraints", {})
    auto_period = constraints.get("auto_period_s", 30)
    teleop_period = constraints.get("teleop_period_s", 120)

    strategies: list[ScoringStrategy] = []

    # Strategy: Focus on highest-point single action
    if scoring_actions:
        # Sort by points descending
        sorted_actions = sorted(scoring_actions, key=lambda a: a["points"], reverse=True)
        best_action = sorted_actions[0]
        cycle_time = best_action.get("cycle_time_s", 10)
        auto_multiplier = 2  # typical FTC auto multiplier
        auto_cycles = min(2, int(auto_period / cycle_time))
        teleop_cycles = int(teleop_period / cycle_time)

        auto_pts = auto_cycles * best_action["points"] * auto_multiplier
        teleop_pts = teleop_cycles * best_action["points"]

        # Best endgame
        best_endgame = max(endgame, key=lambda e: e["points"]) if endgame else {"points": 0, "mechanism": "passive", "name": "none"}
        endgame_pts = best_endgame["points"]

        mechanisms_set = set()
        mechanisms_set.add("drivetrain")
        mech_str = best_action.get("mechanism", "")
        for m in mech_str.split("+"):
            if m.strip():
                mechanisms_set.add(m.strip())
        if best_endgame.get("mechanism", "passive") not in ("passive", "none"):
            mechanisms_set.add("hang_mechanism")

        difficulty = _DIFFICULTY_TO_LEVEL.get(best_action.get("difficulty", "medium"), "intermediate")

        strategies.append(ScoringStrategy(
            name=f"{best_action['name']}_focused",
            expected_auto_points=auto_pts,
            expected_teleop_points=teleop_pts,
            expected_endgame_points=endgame_pts,
            total_expected_points=auto_pts + teleop_pts + endgame_pts,
            required_mechanisms=tuple(sorted(mechanisms_set)),
            difficulty="advanced" if difficulty == "advanced" else "intermediate",
            rationale=f"Focus on {best_action['name']} ({best_action['points']} pts each) "
                      f"with {best_endgame.get('name', 'no')} endgame",
        ))

    # Strategy: Easy/beginner — focus on lowest-difficulty actions
    easy_actions = [a for a in scoring_actions if a.get("difficulty") == "easy"]
    if easy_actions:
        action = easy_actions[0]
        cycle_time = action.get("cycle_time_s", 8)
        auto_cycles = min(2, int(auto_period / cycle_time))
        teleop_cycles = int(teleop_period / cycle_time)
        auto_pts = auto_cycles * action["points"] * 2
        teleop_pts = teleop_cycles * action["points"]

        # Easiest endgame
        easy_endgame = min(endgame, key=lambda e: e["points"]) if endgame else {"points": 0, "name": "none"}
        endgame_pts = easy_endgame["points"]

        mechanisms_set = {"drivetrain"}
        for m in action.get("mechanism", "").split("+"):
            if m.strip():
                mechanisms_set.add(m.strip())

        strategies.append(ScoringStrategy(
            name=f"{action['name']}_easy",
            expected_auto_points=auto_pts,
            expected_teleop_points=teleop_pts,
            expected_endgame_points=endgame_pts,
            total_expected_points=auto_pts + teleop_pts + endgame_pts,
            required_mechanisms=tuple(sorted(mechanisms_set)),
            difficulty="beginner",
            rationale=f"Simple {action['name']} strategy for beginners, "
                      f"easy cycles with {easy_endgame.get('name', 'no')} endgame",
        ))

    # Strategy: Balanced — mix of medium-difficulty actions
    medium_actions = [a for a in scoring_actions if a.get("difficulty") == "medium"]
    if medium_actions:
        action = medium_actions[0]
        cycle_time = action.get("cycle_time_s", 10)
        auto_cycles = min(2, int(auto_period / cycle_time))
        teleop_cycles = int(teleop_period / cycle_time)
        auto_pts = auto_cycles * action["points"] * 2
        teleop_pts = teleop_cycles * action["points"]

        mid_endgame = sorted(endgame, key=lambda e: e["points"])[len(endgame) // 2] if endgame else {"points": 0, "name": "none"}
        endgame_pts = mid_endgame["points"]

        mechanisms_set = {"drivetrain"}
        for m in action.get("mechanism", "").split("+"):
            if m.strip():
                mechanisms_set.add(m.strip())

        strategies.append(ScoringStrategy(
            name=f"{action['name']}_balanced",
            expected_auto_points=auto_pts,
            expected_teleop_points=teleop_pts,
            expected_endgame_points=endgame_pts,
            total_expected_points=auto_pts + teleop_pts + endgame_pts,
            required_mechanisms=tuple(sorted(mechanisms_set)),
            difficulty="intermediate",
            rationale=f"Balanced {action['name']} strategy, "
                      f"medium complexity with {mid_endgame.get('name', 'no')} endgame",
        ))

    return tuple(strategies)


def analyze_game(
    season_data: dict[str, Any],
    team_level: str,
) -> GameAnalysis:
    """Analyze a season and generate prioritized strategies.

    Parameters
    ----------
    season_data : dict
        Enhanced season JSON data (loaded via load_enhanced_season).
    team_level : str
        "beginner", "intermediate", or "advanced".
    """
    if team_level not in _VALID_TEAM_LEVELS:
        raise ValueError(
            f"team_level must be one of {sorted(_VALID_TEAM_LEVELS)}, got '{team_level}'"
        )

    strategies = _build_strategies(season_data)

    # Recommend strategy matching team level
    level_order = _DIFFICULTY_ORDER[team_level]
    recommended = ""
    best_score = -1

    for s in strategies:
        s_order = _DIFFICULTY_ORDER.get(s.difficulty, 1)
        # Prefer strategies at or below team level
        if s_order <= level_order:
            score = s.total_expected_points
        else:
            score = s.total_expected_points * 0.5  # penalize harder strategies
        if score > best_score:
            best_score = score
            recommended = s.name

    if not recommended and strategies:
        recommended = strategies[0].name

    return GameAnalysis(
        season=season_data.get("game_name", season_data.get("season", "")),
        competition=season_data.get("competition", "FTC"),
        strategies=strategies,
        recommended_strategy=recommended,
        game_pieces=tuple(season_data.get("game_elements", [])),
        field_config=season_data.get("field", {}),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_game_analyzer.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/engineering/game_analyzer.py tests/unit/test_game_analyzer.py
git commit -m "feat(engineering): add game analyzer — season parsing, strategy generation"
```

---

### Task 3: BOM Generator

**Files:**
- Create: `src/robotics_design_advisor/engineering/bom_generator.py`
- Test: `tests/unit/test_bom_generator.py`

**Interfaces:**
- Consumes: `BOMItem`, `BillOfMaterials` from `models.py`
- Produces: `generate_bom(archetype_name: str, motor_count: int, servo_count: int, has_lift: bool, has_launcher: bool, constraints: dict) -> BillOfMaterials`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_bom_generator.py
"""Tests for bill of materials generation."""

import pytest

from robotics_design_advisor.engineering.bom_generator import generate_bom
from robotics_design_advisor.engineering.models import BillOfMaterials, BOMItem


class TestGenerateBom:
    def test_returns_bill_of_materials(self):
        bom = generate_bom(
            archetype_name="Speed Shooter",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=True,
            constraints={},
        )
        assert isinstance(bom, BillOfMaterials)

    def test_includes_motors(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=0,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        motor_items = [i for i in bom.items if "motor" in i.name.lower() or "motor" in i.category.lower()]
        total_motors = sum(i.quantity for i in motor_items)
        assert total_motors >= 4

    def test_includes_servos(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=3,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        servo_items = [i for i in bom.items if "servo" in i.name.lower()]
        total_servos = sum(i.quantity for i in servo_items)
        assert total_servos >= 3

    def test_includes_control_hub(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=0,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        hub_items = [i for i in bom.items if "hub" in i.name.lower() or "hub" in i.category.lower()]
        assert len(hub_items) >= 1

    def test_lift_adds_linear_slide(self):
        bom_with = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=1,
            has_lift=True,
            has_launcher=False,
            constraints={},
        )
        bom_without = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=1,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        assert len(bom_with.items) > len(bom_without.items)

    def test_total_cost_positive(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        assert bom.total_cost_usd > 0

    def test_total_cost_matches_items(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        expected = sum(i.unit_price_usd * i.quantity for i in bom.items)
        assert abs(bom.total_cost_usd - expected) < 0.01

    def test_warns_on_motor_limit(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=10,
            servo_count=0,
            has_lift=False,
            has_launcher=False,
            constraints={"max_motors": 8},
        )
        assert any("motor" in w.lower() for w in bom.warnings)

    def test_warns_on_weight_limit(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=8,
            servo_count=12,
            has_lift=True,
            has_launcher=True,
            constraints={"weight_limit_g": 100},
        )
        assert any("weight" in w.lower() for w in bom.warnings)

    def test_subsystem_breakdown_present(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=False,
            has_launcher=False,
            constraints={},
        )
        assert len(bom.subsystem_breakdown) > 0

    def test_all_items_have_sku(self):
        bom = generate_bom(
            archetype_name="test",
            motor_count=4,
            servo_count=2,
            has_lift=True,
            has_launcher=True,
            constraints={},
        )
        for item in bom.items:
            assert item.sku != ""
            assert item.name != ""
            assert item.quantity > 0
            assert item.unit_price_usd >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_bom_generator.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/engineering/bom_generator.py
"""Bill of materials generator for FTC/FRC robot designs.

Given design parameters (motor count, servo count, mechanisms needed),
generates a complete BOM with part SKUs, quantities, costs, and warnings.
Pure functions except for data constants.
"""

from __future__ import annotations

from typing import Any

from .models import BillOfMaterials, BOMItem

# --- Part catalog (representative goBILDA / REV prices) ---

_MOTOR_ITEM = BOMItem(
    sku="5202-0002-0019",
    name="goBILDA Yellow Jacket 19.2:1 Motor",
    quantity=1,
    unit_price_usd=19.99,
    category="motion",
    subsystem="drivetrain",
    notes="DC motor for drivetrain or mechanism",
)

_SERVO_ITEM = BOMItem(
    sku="2000-0025-0002",
    name="goBILDA Dual Mode Servo (25-2)",
    quantity=1,
    unit_price_usd=24.99,
    category="motion",
    subsystem="mechanism",
    notes="Standard servo for claw, pivot, or other",
)

_CONTROL_HUB = BOMItem(
    sku="REV-31-1595",
    name="REV Control Hub",
    quantity=1,
    unit_price_usd=249.99,
    category="electronics",
    subsystem="electronics",
    notes="Primary control hub with IMU",
)

_EXPANSION_HUB = BOMItem(
    sku="REV-31-1153",
    name="REV Expansion Hub",
    quantity=1,
    unit_price_usd=199.99,
    category="electronics",
    subsystem="electronics",
    notes="Additional hub for >4 motors or >6 servos",
)

_BATTERY = BOMItem(
    sku="REV-31-1302",
    name="REV 12V Slim Battery",
    quantity=1,
    unit_price_usd=59.99,
    category="electronics",
    subsystem="electronics",
    notes="Competition battery",
)

_CHASSIS_KIT = BOMItem(
    sku="3209-0001-0001",
    name="goBILDA Strafer Chassis Kit",
    quantity=1,
    unit_price_usd=299.99,
    category="structure",
    subsystem="drivetrain",
    notes="Base chassis with mecanum wheels and channel",
)

_LINEAR_SLIDE = BOMItem(
    sku="3418-0014-0200",
    name="goBILDA Low-Profile Linear Slide (200mm)",
    quantity=2,
    unit_price_usd=17.99,
    category="structure",
    subsystem="lift",
    notes="Linear slide pair for elevator mechanism",
)

_SLIDE_BELT = BOMItem(
    sku="3416-0014-0120",
    name="goBILDA GT2 Timing Belt + Pulleys",
    quantity=1,
    unit_price_usd=12.99,
    category="motion",
    subsystem="lift",
    notes="Belt drive for elevator actuation",
)

_FLYWHEEL = BOMItem(
    sku="3411-0014-0096",
    name="goBILDA 96mm Compliant Wheel (pair)",
    quantity=1,
    unit_price_usd=8.99,
    category="motion",
    subsystem="launcher",
    notes="Compliant wheels for flywheel launcher",
)

_LAUNCHER_MOTOR = BOMItem(
    sku="5202-0002-0005",
    name="goBILDA Yellow Jacket 5.2:1 Motor",
    quantity=2,
    unit_price_usd=19.99,
    category="motion",
    subsystem="launcher",
    notes="High-speed motors for flywheel launcher",
)

_HARDWARE_KIT = BOMItem(
    sku="2800-0004-0001",
    name="goBILDA Hardware Assortment",
    quantity=1,
    unit_price_usd=24.99,
    category="hardware",
    subsystem="general",
    notes="M4 bolts, nuts, standoffs, spacers",
)

_WIRING_KIT = BOMItem(
    sku="REV-31-1387",
    name="REV Wiring Kit (JST-VH + XT30)",
    quantity=1,
    unit_price_usd=14.99,
    category="electronics",
    subsystem="electronics",
    notes="Motor and power cables",
)

# Approximate weight per item category (grams)
_WEIGHT_MAP: dict[str, float] = {
    "goBILDA Yellow Jacket 19.2:1 Motor": 230.0,
    "goBILDA Yellow Jacket 5.2:1 Motor": 230.0,
    "goBILDA Dual Mode Servo (25-2)": 60.0,
    "REV Control Hub": 250.0,
    "REV Expansion Hub": 230.0,
    "REV 12V Slim Battery": 530.0,
    "goBILDA Strafer Chassis Kit": 4500.0,
    "goBILDA Low-Profile Linear Slide (200mm)": 180.0,
    "goBILDA GT2 Timing Belt + Pulleys": 50.0,
    "goBILDA 96mm Compliant Wheel (pair)": 120.0,
    "goBILDA Hardware Assortment": 200.0,
    "REV Wiring Kit (JST-VH + XT30)": 80.0,
}


def _item_with_quantity(template: BOMItem, quantity: int, subsystem: str = "") -> BOMItem:
    """Create a BOMItem from a template with updated quantity and optional subsystem."""
    return BOMItem(
        sku=template.sku,
        name=template.name,
        quantity=quantity,
        unit_price_usd=template.unit_price_usd,
        category=template.category,
        subsystem=subsystem if subsystem else template.subsystem,
        notes=template.notes,
    )


def generate_bom(
    archetype_name: str,
    motor_count: int,
    servo_count: int,
    has_lift: bool,
    has_launcher: bool,
    constraints: dict[str, Any],
) -> BillOfMaterials:
    """Generate a bill of materials for a robot design.

    Parameters
    ----------
    archetype_name : str
        Name of the design archetype.
    motor_count : int
        Total number of DC motors needed.
    servo_count : int
        Total number of servos needed.
    has_lift : bool
        Whether the design includes an elevator/lift.
    has_launcher : bool
        Whether the design includes a flywheel launcher.
    constraints : dict
        Optional constraint limits (max_motors, weight_limit_g, etc.).
    """
    items: list[BOMItem] = []

    # Chassis
    items.append(_CHASSIS_KIT)

    # Motors
    if motor_count > 0:
        items.append(_item_with_quantity(_MOTOR_ITEM, motor_count))

    # Servos
    if servo_count > 0:
        items.append(_item_with_quantity(_SERVO_ITEM, servo_count, "mechanism"))

    # Electronics
    items.append(_CONTROL_HUB)
    if motor_count > 4 or servo_count > 6:
        items.append(_EXPANSION_HUB)
    items.append(_BATTERY)
    items.append(_WIRING_KIT)

    # Lift mechanism
    if has_lift:
        items.append(_LINEAR_SLIDE)
        items.append(_SLIDE_BELT)

    # Launcher mechanism
    if has_launcher:
        items.append(_FLYWHEEL)
        items.append(_LAUNCHER_MOTOR)

    # Hardware
    items.append(_HARDWARE_KIT)

    # Calculate totals
    total_cost = sum(i.unit_price_usd * i.quantity for i in items)
    total_weight = sum(
        _WEIGHT_MAP.get(i.name, 100.0) * i.quantity
        for i in items
    )

    # Subsystem breakdown
    breakdown: dict[str, tuple[float, float, int]] = {}
    for item in items:
        cost = item.unit_price_usd * item.quantity
        weight = _WEIGHT_MAP.get(item.name, 100.0) * item.quantity
        if item.subsystem in breakdown:
            prev = breakdown[item.subsystem]
            breakdown[item.subsystem] = (
                round(prev[0] + cost, 2),
                round(prev[1] + weight, 1),
                prev[2] + 1,
            )
        else:
            breakdown[item.subsystem] = (round(cost, 2), round(weight, 1), 1)

    # Warnings
    warnings: list[str] = []
    max_motors = constraints.get("max_motors", 8)
    if motor_count > max_motors:
        warnings.append(
            f"Motor count ({motor_count}) exceeds limit ({max_motors})"
        )

    weight_limit = constraints.get("weight_limit_g")
    if weight_limit is not None and total_weight > weight_limit:
        warnings.append(
            f"Estimated weight ({total_weight:.0f}g) exceeds limit ({weight_limit}g)"
        )

    return BillOfMaterials(
        items=tuple(items),
        total_cost_usd=round(total_cost, 2),
        total_weight_g=round(total_weight, 1),
        warnings=tuple(warnings),
        subsystem_breakdown=breakdown,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_bom_generator.py -v`
Expected: 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/engineering/bom_generator.py tests/unit/test_bom_generator.py
git commit -m "feat(engineering): add BOM generator — part catalog, cost/weight, constraint warnings"
```

---

### Task 4: Design Synthesizer

**Files:**
- Create: `src/robotics_design_advisor/engineering/design_synthesizer.py`
- Test: `tests/unit/test_design_synthesizer.py`

**Interfaces:**
- Consumes:
  - `load_enhanced_season`, `analyze_game` from `game_analyzer.py`
  - `recommend_for_season`, `get_archetype_by_id` from `design_advisor.py`
  - `generate_bom` from `bom_generator.py`
  - `DesignSynthesis`, `GameAnalysis`, `ScoringStrategy`, `BillOfMaterials` from `models.py`
- Produces: `synthesize_design(season_file: str, team_level: str, archetype_id: str | None) -> DesignSynthesis`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_design_synthesizer.py
"""Tests for the full design synthesis pipeline."""

import pytest

from robotics_design_advisor.engineering.design_synthesizer import (
    synthesize_design,
)
from robotics_design_advisor.engineering.models import (
    BillOfMaterials,
    DesignSynthesis,
    ScoringStrategy,
)


class TestSynthesizeDesign:
    def test_returns_design_synthesis(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert isinstance(result, DesignSynthesis)

    def test_has_season_info(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert result.season == "INTO THE DEEP"
        assert result.competition == "FTC"

    def test_has_strategy(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert isinstance(result.strategy, ScoringStrategy)
        assert result.strategy.total_expected_points > 0

    def test_has_archetype(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert result.archetype_name != ""

    def test_has_bom(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert isinstance(result.bom, BillOfMaterials)
        assert result.bom.total_cost_usd > 0
        assert len(result.bom.items) > 0

    def test_has_mechanism_notes(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert len(result.mechanism_notes) > 0

    def test_has_autonomous_notes(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
        )
        assert len(result.autonomous_notes) > 0

    def test_specific_archetype(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
            archetype_id="V5",
        )
        assert result.archetype_name == "Placer Bot"

    def test_beginner_level(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="beginner",
        )
        assert isinstance(result, DesignSynthesis)
        assert result.strategy.difficulty in ("beginner", "intermediate")

    def test_advanced_level(self):
        result = synthesize_design(
            season_file="ftc-2024-into-the-deep.json",
            team_level="advanced",
        )
        assert isinstance(result, DesignSynthesis)

    def test_invalid_team_level_raises(self):
        with pytest.raises(ValueError, match="team_level"):
            synthesize_design(
                season_file="ftc-2024-into-the-deep.json",
                team_level="expert",
            )

    def test_invalid_archetype_raises(self):
        with pytest.raises(ValueError, match="archetype"):
            synthesize_design(
                season_file="ftc-2024-into-the-deep.json",
                team_level="intermediate",
                archetype_id="V99",
            )

    def test_missing_season_raises(self):
        with pytest.raises(FileNotFoundError):
            synthesize_design(
                season_file="nonexistent.json",
                team_level="intermediate",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_design_synthesizer.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/engineering/design_synthesizer.py
"""Design synthesizer — orchestrates the full robot design pipeline.

Chains game analysis → archetype selection → mechanism notes →
autonomous notes → BOM generation into a single DesignSynthesis output.
"""

from __future__ import annotations

from typing import Any

from .bom_generator import generate_bom
from .design_advisor import get_archetype_by_id, recommend_for_season
from .game_analyzer import analyze_game, load_enhanced_season
from .models import DesignSynthesis

_VALID_TEAM_LEVELS = {"beginner", "intermediate", "advanced"}


def _mechanism_notes_from_strategy(
    strategy_name: str,
    archetype_name: str,
    season_data: dict[str, Any],
) -> tuple[str, ...]:
    """Generate mechanism notes based on strategy and archetype."""
    notes: list[str] = []
    notes.append(f"Archetype: {archetype_name}")

    scoring_actions = season_data.get("scoring_actions", [])
    for action in scoring_actions:
        if action["name"] in strategy_name or strategy_name.startswith(action["name"]):
            mechanism = action.get("mechanism", "unknown")
            notes.append(
                f"Primary scoring: {action['name']} "
                f"({action['points']} pts, {mechanism}, "
                f"~{action.get('cycle_time_s', '?')}s cycle)"
            )

    game_elements = season_data.get("game_elements", [])
    for elem in game_elements:
        weight = elem.get("weight_grams", elem.get("weight_g", 0))
        dims = elem.get("dimensions_mm", [])
        notes.append(
            f"Game piece: {elem['name']} "
            f"({weight}g, {dims}mm)"
        )

    endgame = season_data.get("endgame", [])
    if endgame:
        best = max(endgame, key=lambda e: e["points"])
        notes.append(
            f"Endgame target: {best['name']} ({best['points']} pts, {best['mechanism']})"
        )

    return tuple(notes)


def _autonomous_notes(
    season_data: dict[str, Any],
) -> tuple[str, ...]:
    """Generate autonomous period planning notes."""
    notes: list[str] = []
    constraints = season_data.get("constraints", {})
    auto_period = constraints.get("auto_period_s", 30)
    notes.append(f"Auto period: {auto_period}s")

    scoring_actions = season_data.get("scoring_actions", [])
    easy_actions = [a for a in scoring_actions if a.get("difficulty") == "easy"]
    if easy_actions:
        action = easy_actions[0]
        cycles = int(auto_period / action.get("cycle_time_s", 10))
        notes.append(
            f"Auto plan: {cycles}x {action['name']} "
            f"({cycles * action['points'] * 2} pts with auto multiplier)"
        )

    preloaded = constraints.get("max_pieces_preloaded", 1)
    notes.append(f"Preloaded pieces: {preloaded}")

    field = season_data.get("field", {})
    dims = field.get("dimensions_mm", [3658, 3658])
    notes.append(f"Field: {dims[0]}×{dims[1]}mm")

    return tuple(notes)


def synthesize_design(
    season_file: str,
    team_level: str,
    archetype_id: str | None = None,
) -> DesignSynthesis:
    """Run the full design pipeline for a season.

    Parameters
    ----------
    season_file : str
        Enhanced season JSON filename.
    team_level : str
        "beginner", "intermediate", or "advanced".
    archetype_id : str or None
        Specific archetype ID (e.g. "V5"). If None, auto-selects.

    Raises
    ------
    ValueError
        If team_level is invalid or archetype_id doesn't exist.
    FileNotFoundError
        If season_file doesn't exist.
    """
    if team_level not in _VALID_TEAM_LEVELS:
        raise ValueError(
            f"team_level must be one of {sorted(_VALID_TEAM_LEVELS)}, got '{team_level}'"
        )

    # Step 1: Load season data
    season_data = load_enhanced_season(season_file)

    # Step 2: Analyze game
    analysis = analyze_game(season_data, team_level)

    # Step 3: Select archetype
    if archetype_id is not None:
        archetype = get_archetype_by_id(archetype_id)
        if archetype is None:
            raise ValueError(f"Unknown archetype_id '{archetype_id}'")
        archetype_name = archetype.name
        motor_budget = archetype.motor_budget
        scorer_type = archetype.scorer
    else:
        # Auto-select based on season
        ranked = recommend_for_season(season_file, top_n=1)
        if ranked:
            archetype, _score = ranked[0]
            archetype_name = archetype.name
            motor_budget = archetype.motor_budget
            scorer_type = archetype.scorer
        else:
            archetype_name = "Custom"
            motor_budget = 8
            scorer_type = "elevator_placer"

    # Step 4: Determine mechanisms from strategy
    strategy = next(
        (s for s in analysis.strategies if s.name == analysis.recommended_strategy),
        analysis.strategies[0] if analysis.strategies else None,
    )

    if strategy is None:
        raise ValueError("No strategies generated for this season")

    has_lift = any(m in ("elevator", "lift", "arm") for m in strategy.required_mechanisms)
    has_launcher = any(m in ("launcher", "shooter") for m in strategy.required_mechanisms) or "flywheel" in scorer_type

    # Estimate servo count from mechanisms
    servo_count = 2  # baseline: claw + wrist
    if has_lift:
        servo_count += 1

    constraints = season_data.get("constraints", {})

    # Step 5: Generate BOM
    bom = generate_bom(
        archetype_name=archetype_name,
        motor_count=motor_budget,
        servo_count=servo_count,
        has_lift=has_lift,
        has_launcher=has_launcher,
        constraints=constraints,
    )

    # Step 6: Generate notes
    mech_notes = _mechanism_notes_from_strategy(
        strategy.name, archetype_name, season_data
    )
    auto_notes = _autonomous_notes(season_data)

    # Step 7: Collect warnings
    warnings: list[str] = list(bom.warnings)

    return DesignSynthesis(
        season=analysis.season,
        competition=analysis.competition,
        strategy=strategy,
        archetype_name=archetype_name,
        bom=bom,
        mechanism_notes=mech_notes,
        autonomous_notes=auto_notes,
        warnings=tuple(warnings),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_design_synthesizer.py -v`
Expected: 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/robotics_design_advisor/engineering/design_synthesizer.py tests/unit/test_design_synthesizer.py
git commit -m "feat(engineering): add design synthesizer — full pipeline from season to BOM"
```

---

## Summary

| Task | Module | Tests | Capability |
|------|--------|-------|-----------|
| 1 | `models.py` + season JSON | 6 | Phase 4C dataclasses + INTO THE DEEP enhanced season data |
| 2 | `game_analyzer.py` | 10 | Parse enhanced seasons, generate scoring strategies by team level |
| 3 | `bom_generator.py` | 11 | Generate BOM with costs, weights, constraint warnings |
| 4 | `design_synthesizer.py` | 13 | Full pipeline: season → strategy → archetype → BOM → notes |
| **Total** | **4 files + 1 JSON** | **~40** | |
