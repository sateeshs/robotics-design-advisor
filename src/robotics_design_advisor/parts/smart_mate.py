"""Profile-based mate suggestions between two parts.

Analyzes connection points and compatibility tags from two part
profiles to suggest valid SolidWorks mate constraints.

Pure functions — no I/O, no COM calls.
"""

from __future__ import annotations

from .models import ConnectionPoint, MateSuggestion, PartProfile


def suggest_mates(
    profile_a: PartProfile,
    profile_b: PartProfile,
) -> list[MateSuggestion]:
    """Suggest mate constraints between two parts based on their profiles.

    Matches connection points by overlapping compatibility tags, then
    infers the appropriate mate type from connection geometry.

    Returns suggestions sorted by confidence (highest first).
    """
    suggestions: list[MateSuggestion] = []

    for cp_a in profile_a.connection_points:
        for cp_b in profile_b.connection_points:
            suggestion = _try_match(cp_a, cp_b, profile_a.sku, profile_b.sku)
            if suggestion is not None:
                suggestions.append(suggestion)

    # Deduplicate by (mate_type, part_a_ref, part_b_ref)
    seen: set[tuple[str, str, str]] = set()
    unique: list[MateSuggestion] = []
    for s in suggestions:
        key = (s.mate_type, s.part_a_ref, s.part_b_ref)
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return sorted(unique, key=lambda s: s.confidence, reverse=True)


def _try_match(
    cp_a: ConnectionPoint,
    cp_b: ConnectionPoint,
    sku_a: str,
    sku_b: str,
) -> MateSuggestion | None:
    """Try to match two connection points and return a mate suggestion."""
    tags_a = set(cp_a.compatible_with)
    tags_b = set(cp_b.compatible_with)
    overlap = tags_a & tags_b

    if not overlap:
        return None

    mate_type, confidence, rationale = _infer_mate(cp_a, cp_b, overlap)

    a_ref = cp_a.pattern_ref or cp_a.face_ref or cp_a.connection_type
    b_ref = cp_b.pattern_ref or cp_b.face_ref or cp_b.connection_type

    return MateSuggestion(
        mate_type=mate_type,
        part_a_ref=f"{a_ref}@{sku_a}",
        part_b_ref=f"{b_ref}@{sku_b}",
        confidence=confidence,
        rationale=rationale,
    )


def _infer_mate(
    cp_a: ConnectionPoint,
    cp_b: ConnectionPoint,
    overlap: set[str],
) -> tuple[str, float, str]:
    """Infer mate type, confidence, and rationale from connection points."""

    # Shaft bore ↔ shaft bore → concentric
    if cp_a.connection_type == "shaft_bore" and cp_b.connection_type == "shaft_bore":
        if cp_a.diameter_mm == cp_b.diameter_mm and cp_a.diameter_mm > 0:
            return (
                "concentric",
                0.95,
                f"Both parts have matching {cp_a.diameter_mm}mm "
                f"{cp_a.profile or 'round'} shaft connections",
            )
        return (
            "concentric",
            0.7,
            f"Both parts have shaft bores ({cp_a.diameter_mm}mm / {cp_b.diameter_mm}mm) — "
            "verify diameter compatibility",
        )

    # Bolt hole grid ↔ bolt hole grid → coincident
    if (
        cp_a.connection_type == "bolt_hole_grid"
        and cp_b.connection_type == "bolt_hole_grid"
    ):
        return (
            "coincident",
            0.9,
            f"Matching bolt hole patterns via {', '.join(sorted(overlap))}",
        )

    # Motor mount ↔ bolt hole grid → coincident
    if _one_is(cp_a, cp_b, "motor_mount_pattern", "bolt_hole_grid"):
        return (
            "coincident",
            0.85,
            "Motor mount pattern aligns with bolt hole grid",
        )

    # Bolt hole grid ↔ shaft bore → distance (offset needed)
    if _one_is(cp_a, cp_b, "bolt_hole_grid", "shaft_bore"):
        return (
            "distance",
            0.6,
            "Bolt grid and shaft bore on different parts — likely needs offset mate",
        )

    # Generic overlap fallback
    return (
        "coincident",
        0.5,
        f"Compatible via shared tags: {', '.join(sorted(overlap))}",
    )


def _one_is(
    cp_a: ConnectionPoint,
    cp_b: ConnectionPoint,
    type_1: str,
    type_2: str,
) -> bool:
    """Check if the two connection points are one of each type (in either order)."""
    types = {cp_a.connection_type, cp_b.connection_type}
    return types == {type_1, type_2}
