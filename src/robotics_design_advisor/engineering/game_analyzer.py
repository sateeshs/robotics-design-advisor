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
        best_endgame = (
            max(endgame, key=lambda e: e["points"])
            if endgame
            else {"points": 0, "mechanism": "passive", "name": "none"}
        )
        endgame_pts = best_endgame["points"]

        mechanisms_set = set()
        mechanisms_set.add("drivetrain")
        mech_str = best_action.get("mechanism", "")
        for m in mech_str.split("+"):
            if m.strip():
                mechanisms_set.add(m.strip())
        if best_endgame.get("mechanism", "passive") not in ("passive", "none"):
            mechanisms_set.add("hang_mechanism")

        difficulty = _DIFFICULTY_TO_LEVEL.get(
            best_action.get("difficulty", "medium"), "intermediate"
        )

        strategies.append(
            ScoringStrategy(
                name=f"{best_action['name']}_focused",
                expected_auto_points=auto_pts,
                expected_teleop_points=teleop_pts,
                expected_endgame_points=endgame_pts,
                total_expected_points=auto_pts + teleop_pts + endgame_pts,
                required_mechanisms=tuple(sorted(mechanisms_set)),
                difficulty="advanced" if difficulty == "advanced" else "intermediate",
                rationale=f"Focus on {best_action['name']} ({best_action['points']} pts each) "
                f"with {best_endgame.get('name', 'no')} endgame",
            )
        )

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
        easy_endgame = (
            min(endgame, key=lambda e: e["points"])
            if endgame
            else {"points": 0, "name": "none"}
        )
        endgame_pts = easy_endgame["points"]

        mechanisms_set = {"drivetrain"}
        for m in action.get("mechanism", "").split("+"):
            if m.strip():
                mechanisms_set.add(m.strip())

        strategies.append(
            ScoringStrategy(
                name=f"{action['name']}_easy",
                expected_auto_points=auto_pts,
                expected_teleop_points=teleop_pts,
                expected_endgame_points=endgame_pts,
                total_expected_points=auto_pts + teleop_pts + endgame_pts,
                required_mechanisms=tuple(sorted(mechanisms_set)),
                difficulty="beginner",
                rationale=f"Simple {action['name']} strategy for beginners, "
                f"easy cycles with {easy_endgame.get('name', 'no')} endgame",
            )
        )

    # Strategy: Balanced — mix of medium-difficulty actions
    medium_actions = [a for a in scoring_actions if a.get("difficulty") == "medium"]
    if medium_actions:
        action = medium_actions[0]
        cycle_time = action.get("cycle_time_s", 10)
        auto_cycles = min(2, int(auto_period / cycle_time))
        teleop_cycles = int(teleop_period / cycle_time)
        auto_pts = auto_cycles * action["points"] * 2
        teleop_pts = teleop_cycles * action["points"]

        mid_endgame = (
            sorted(endgame, key=lambda e: e["points"])[len(endgame) // 2]
            if endgame
            else {"points": 0, "name": "none"}
        )
        endgame_pts = mid_endgame["points"]

        mechanisms_set = {"drivetrain"}
        for m in action.get("mechanism", "").split("+"):
            if m.strip():
                mechanisms_set.add(m.strip())

        strategies.append(
            ScoringStrategy(
                name=f"{action['name']}_balanced",
                expected_auto_points=auto_pts,
                expected_teleop_points=teleop_pts,
                expected_endgame_points=endgame_pts,
                total_expected_points=auto_pts + teleop_pts + endgame_pts,
                required_mechanisms=tuple(sorted(mechanisms_set)),
                difficulty="intermediate",
                rationale=f"Balanced {action['name']} strategy, "
                f"medium complexity with {mid_endgame.get('name', 'no')} endgame",
            )
        )

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

    Raises
    ------
    ValueError
        If team_level is not valid.
    """
    if team_level not in _VALID_TEAM_LEVELS:
        raise ValueError(
            f"team_level must be one of {sorted(_VALID_TEAM_LEVELS)}, got '{team_level}'"
        )

    strategies = _build_strategies(season_data)

    if not strategies:
        raise ValueError(
            "No scoring strategies could be generated — "
            "season data may be missing 'scoring_actions'"
        )

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
