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
