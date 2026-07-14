"""Design advisor — generates competitive robot design variants.

Loads season knowledge from JSON, combines mechanism options across
design axes, and scores variants for uniqueness, complexity, and
competitiveness.

Pure functions — no side effects beyond reading season JSON files.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._path_safety import safe_resolve


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DesignVariant:
    """A single robot design variant."""
    name: str
    archetype_id: str
    drivetrain: str
    intake: str
    indexer: str
    scorer: str
    aiming: str
    endgame: str
    uniqueness_score: float   # 0-100, higher = more unusual
    complexity_score: float   # 0-100, higher = harder to build
    competitive_score: float  # 0-100, higher = more competitive
    motor_budget: int         # estimated DC motor count
    description: str
    pros: tuple[str, ...]
    cons: tuple[str, ...]


@dataclass(frozen=True)
class SeasonKnowledge:
    """Parsed season game knowledge."""
    competition: str
    season: str
    game_name: str
    game_elements: tuple[dict[str, Any], ...]
    scoring_zones: tuple[dict[str, Any], ...]
    mechanisms_needed: dict[str, Any]
    design_axes: dict[str, list[str]]
    cycle_targets: dict[str, int]


# ---------------------------------------------------------------------------
# Season loader
# ---------------------------------------------------------------------------

_SEASONS_DIR = Path(__file__).parent / "seasons"


def load_season(season_file: str) -> SeasonKnowledge:
    """Load season knowledge from a JSON file.

    Raises
    ------
    ValueError
        If the path escapes the seasons directory.
    """
    path = safe_resolve(_SEASONS_DIR, season_file)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        raise FileNotFoundError(f"Season file not found: '{season_file}'") from None

    return SeasonKnowledge(
        competition=data["competition"],
        season=data["season"],
        game_name=data["game_name"],
        game_elements=tuple(data.get("game_elements", [])),
        scoring_zones=tuple(data.get("scoring_zones", [])),
        mechanisms_needed=data.get("mechanisms_needed", {}),
        design_axes=data.get("design_axes", {}),
        cycle_targets=data.get("cycle_targets", {}),
    )


def list_seasons() -> list[str]:
    """List available season files."""
    return sorted(
        f.name
        for f in _SEASONS_DIR.glob("*.json")
        if not f.name.startswith("_")
    )


# ---------------------------------------------------------------------------
# Archetype definitions
# ---------------------------------------------------------------------------

_ARCHETYPES: list[dict[str, Any]] = [
    {
        "id": "V1",
        "name": "Speed Shooter",
        "drivetrain": "mecanum",
        "intake": "front_roller",
        "indexer": "belt_conveyor",
        "scorer": "dual_flywheel",
        "aiming": "fixed_angle_variable_speed",
        "endgame": "fast_park",
        "motor_budget": 8,
        "uniqueness": 25,
        "complexity": 55,
        "competitive": 80,
        "description": (
            "Fast mecanum drive with front roller intake feeding a belt conveyor "
            "to dual flywheels. Fixed aim angle, varies shot power by wheel speed. "
            "Prioritizes cycle speed over shot precision."
        ),
        "pros": (
            "Fast cycle time — belt feeds continuously",
            "Mecanum allows strafing to align quickly",
            "Well-understood design, many references available",
        ),
        "cons": (
            "Common design — low uniqueness at competition",
            "Fixed angle limits scoring flexibility",
            "High motor count leaves no spares",
        ),
    },
    {
        "id": "V2",
        "name": "Turret Sniper",
        "drivetrain": "mecanum",
        "intake": "front_roller",
        "indexer": "wheel_indexer",
        "scorer": "dual_flywheel",
        "aiming": "turret",
        "endgame": "simple_park",
        "motor_budget": 8,
        "uniqueness": 60,
        "complexity": 80,
        "competitive": 90,
        "description": (
            "Mecanum drive with turret-mounted dual flywheels. Can shoot while "
            "moving by tracking the goal with the turret. Wheel indexer meters "
            "one artifact at a time for consistent shots."
        ),
        "pros": (
            "Shoot while moving — highest cycle efficiency",
            "Turret tracks goal automatically",
            "Consistent single-element indexing",
        ),
        "cons": (
            "Turret adds significant complexity",
            "All 8 motors used — no room for error",
            "Turret weight raises CG",
        ),
    },
    {
        "id": "V3",
        "name": "Swerve Sniper",
        "drivetrain": "swerve",
        "intake": "front_roller",
        "indexer": "wheel_indexer",
        "scorer": "dual_flywheel",
        "aiming": "whole_robot_aim",
        "endgame": "simple_park",
        "motor_budget": 8,
        "uniqueness": 85,
        "complexity": 90,
        "competitive": 85,
        "description": (
            "Swerve drive eliminates turret need — whole robot rotates to aim. "
            "Dual flywheels with wheel indexer for consistent shots. "
            "Highest maneuverability on the field."
        ),
        "pros": (
            "Swerve is extremely rare in FTC — maximum uniqueness",
            "No turret needed — robot IS the turret",
            "Superior field positioning",
        ),
        "cons": (
            "Swerve is very complex to build and program",
            "Custom swerve modules may be needed",
            "High risk if swerve fails during match",
        ),
    },
    {
        "id": "V4",
        "name": "Hood Flexer",
        "drivetrain": "mecanum",
        "intake": "front_roller",
        "indexer": "direct_feed",
        "scorer": "single_flywheel_with_hood",
        "aiming": "adjustable_hood",
        "endgame": "fast_park",
        "motor_budget": 6,
        "uniqueness": 45,
        "complexity": 50,
        "competitive": 75,
        "description": (
            "Single flywheel with adjustable hood for angle control. "
            "Direct feed from intake — fewer parts, simpler build. "
            "Hood angle servo adjusts for distance."
        ),
        "pros": (
            "Fewer motors (6) — leaves room for extras",
            "Simple direct feed reduces jamming",
            "Adjustable hood handles multiple distances",
        ),
        "cons": (
            "Single flywheel less consistent than dual",
            "Slower cycle without belt/indexer",
            "Limited to one element at a time",
        ),
    },
    {
        "id": "V5",
        "name": "Placer Bot",
        "drivetrain": "mecanum",
        "intake": "claw_gripper",
        "indexer": "direct_feed",
        "scorer": "elevator_placer",
        "aiming": "pivot_hood",
        "endgame": "simple_park",
        "motor_budget": 7,
        "uniqueness": 55,
        "complexity": 60,
        "competitive": 70,
        "description": (
            "Elevator-based robot that places artifacts directly into goals. "
            "Claw gripper picks up one at a time, elevator lifts to goal height, "
            "pivot places accurately. Targets motif ramp for high points."
        ),
        "pros": (
            "Perfect accuracy — no missed shots",
            "Motif ramp scoring for 6 points each",
            "Moderate complexity",
        ),
        "cons": (
            "Slow cycle — one element at a time",
            "Must drive to goal each cycle",
            "Elevator extends height — CG concern",
        ),
    },
    {
        "id": "V6",
        "name": "Catapult Tank",
        "drivetrain": "differential",
        "intake": "dual_side_intake",
        "indexer": "carousel",
        "scorer": "catapult",
        "aiming": "whole_robot_aim",
        "endgame": "simple_park",
        "motor_budget": 7,
        "uniqueness": 70,
        "complexity": 55,
        "competitive": 65,
        "description": (
            "Differential drive for pushing power with dual side intakes. "
            "Carousel holds multiple artifacts, catapult launches them. "
            "Simple aim by rotating the whole robot."
        ),
        "pros": (
            "Dual intake collects from both sides",
            "Carousel stores 3-4 elements for burst scoring",
            "Differential drive is robust and simple",
        ),
        "cons": (
            "No strafing — slower field navigation",
            "Catapult less accurate than flywheel",
            "Burst fire then reload — inconsistent cycle",
        ),
    },
    {
        "id": "V7",
        "name": "Dual Intake Beast",
        "drivetrain": "mecanum",
        "intake": "dual_side_intake",
        "indexer": "belt_conveyor",
        "scorer": "dual_flywheel",
        "aiming": "pivot_hood",
        "endgame": "fast_park",
        "motor_budget": 8,
        "uniqueness": 50,
        "complexity": 70,
        "competitive": 85,
        "description": (
            "Mecanum drive with intakes on both sides for maximum collection. "
            "Belt conveyor feeds dual flywheels with pivot hood for angle. "
            "Never needs to turn around to collect."
        ),
        "pros": (
            "Collect from either side — fastest collection",
            "Belt conveyor for continuous feeding",
            "Pivot hood gives angle flexibility",
        ),
        "cons": (
            "All 8 motors used",
            "Complex dual intake mechanism",
            "Two intakes means more weight",
        ),
    },
    {
        "id": "V8",
        "name": "Modular Hybrid",
        "drivetrain": "H-drive",
        "intake": "over_body_intake",
        "indexer": "belt_conveyor",
        "scorer": "dual_flywheel",
        "aiming": "adjustable_hood",
        "endgame": "shared_zone_park",
        "motor_budget": 7,
        "uniqueness": 75,
        "complexity": 65,
        "competitive": 78,
        "description": (
            "H-drive (mecanum + extra strafe wheel) with over-body intake. "
            "Elements pass over the robot from back to front, feeding flywheels. "
            "Adjustable hood and shared zone endgame for bonus points."
        ),
        "pros": (
            "H-drive is uncommon — good uniqueness",
            "Over-body intake is space-efficient",
            "7 motors leaves one spare port",
        ),
        "cons": (
            "H-drive fifth wheel adds complexity",
            "Over-body path is longer — slightly slower feed",
            "Shared zone park requires coordination with partner",
        ),
    },
]


# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------

def _build_variant(a: dict[str, Any]) -> DesignVariant:
    return DesignVariant(
        name=a["name"],
        archetype_id=a["id"],
        drivetrain=a["drivetrain"],
        intake=a["intake"],
        indexer=a["indexer"],
        scorer=a["scorer"],
        aiming=a["aiming"],
        endgame=a["endgame"],
        uniqueness_score=float(a["uniqueness"]),
        complexity_score=float(a["complexity"]),
        competitive_score=float(a["competitive"]),
        motor_budget=a["motor_budget"],
        description=a["description"],
        pros=tuple(a["pros"]),
        cons=tuple(a["cons"]),
    )


# Pre-built lookup for O(1) access by ID
_ALL_ARCHETYPES: tuple[DesignVariant, ...] = tuple(_build_variant(a) for a in _ARCHETYPES)
_ARCHETYPE_MAP: dict[str, DesignVariant] = {v.archetype_id: v for v in _ALL_ARCHETYPES}


def get_archetypes() -> list[DesignVariant]:
    """Return all pre-defined competitive archetypes as DesignVariant objects."""
    return list(_ALL_ARCHETYPES)


def get_archetype_by_id(archetype_id: str) -> DesignVariant | None:
    """Find an archetype by its ID (e.g., 'V1', 'V2')."""
    return _ARCHETYPE_MAP.get(archetype_id)


def filter_variants(
    max_complexity: float = 100.0,
    min_competitive: float = 0.0,
    min_uniqueness: float = 0.0,
    max_motors: int = 8,
) -> list[DesignVariant]:
    """Filter archetypes by scoring thresholds."""
    return [
        v for v in _ALL_ARCHETYPES
        if v.complexity_score <= max_complexity
        and v.competitive_score >= min_competitive
        and v.uniqueness_score >= min_uniqueness
        and v.motor_budget <= max_motors
    ]


def rank_variants(
    variants: Sequence[DesignVariant],
    *,
    weight_uniqueness: float = 0.3,
    weight_competitive: float = 0.5,
    weight_complexity_penalty: float = 0.2,
) -> list[tuple[DesignVariant, float]]:
    """Rank variants by weighted composite score.

    Higher uniqueness and competitiveness are good.
    Higher complexity is penalized.

    Returns list of (variant, composite_score) sorted descending.
    """
    scored: list[tuple[DesignVariant, float]] = []
    for v in variants:
        composite = (
            weight_uniqueness * v.uniqueness_score
            + weight_competitive * v.competitive_score
            - weight_complexity_penalty * v.complexity_score
        )
        scored.append((v, round(composite, 1)))

    return sorted(scored, key=lambda x: x[1], reverse=True)


def recommend_for_season(
    season_file: str,
    *,
    max_complexity: float = 100.0,
    min_uniqueness: float = 0.0,
    top_n: int = 3,
) -> list[tuple[DesignVariant, float]]:
    """Recommend top design variants for a given season.

    Loads the season knowledge to validate that recommended mechanisms
    match available design axes.
    """
    season = load_season(season_file)
    axes = season.design_axes

    # Filter archetypes whose mechanisms exist in this season's axes
    valid: list[DesignVariant] = []
    for v in _ALL_ARCHETYPES:
        if (
            v.drivetrain in axes.get("drivetrain", [v.drivetrain])
            and v.intake in axes.get("intake", [v.intake])
            and v.indexer in axes.get("indexer", [v.indexer])
            and v.scorer in axes.get("scorer", [v.scorer])
            and v.aiming in axes.get("aiming", [v.aiming])
            and v.endgame in axes.get("endgame", [v.endgame])
        ):
            valid.append(v)

    # Apply filters
    filtered = [
        v for v in valid
        if v.complexity_score <= max_complexity
        and v.uniqueness_score >= min_uniqueness
    ]

    ranked = rank_variants(filtered)
    return ranked[:top_n]


def count_theoretical_combinations(season_file: str) -> int:
    """Count theoretical mechanism combinations for a season."""
    season = load_season(season_file)
    axes = season.design_axes
    total = 1
    for axis_options in axes.values():
        if axis_options:
            total *= len(axis_options)
    return total
