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
    # Use the recommended strategy, but for beginner/intermediate levels
    # prefer a strategy whose difficulty doesn't exceed the team level.
    _level_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    team_order = _level_order[team_level]

    # Find the recommended strategy first
    recommended = next(
        (s for s in analysis.strategies if s.name == analysis.recommended_strategy),
        analysis.strategies[0] if analysis.strategies else None,
    )

    # If the recommended strategy is harder than the team level, find a better fit
    strategy = recommended
    if recommended is not None:
        rec_order = _level_order.get(recommended.difficulty, 2)
        if rec_order > team_order:
            # Pick the highest-scoring strategy at or below team level
            candidates = [
                s for s in analysis.strategies
                if _level_order.get(s.difficulty, 2) <= team_order
            ]
            if candidates:
                strategy = max(candidates, key=lambda s: s.total_expected_points)

    if strategy is None:
        raise ValueError("No strategies generated for this season")

    has_lift = any(m in ("elevator", "lift", "arm") for m in strategy.required_mechanisms)
    has_launcher = (
        any(m in ("launcher", "shooter") for m in strategy.required_mechanisms)
        or "flywheel" in scorer_type
    )

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
