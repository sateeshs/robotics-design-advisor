"""Connection classifier — maps detected holes/patterns to connection types.

Uses goBILDA domain knowledge to classify hole patterns as bolt grids,
shaft bores, motor mounts, etc., and assigns compatibility tags.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .analyzer import StepAnalysis
from .hole_detector import (
    DetectedHole,
    DetectedPattern,
    HoleDetection,
    _map_bolt_size,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — goBILDA domain knowledge
# ---------------------------------------------------------------------------

_GOBILDA_PITCH_MM = 8.0
_PITCH_TOLERANCE = 0.5

# Shaft bore classifications: (min_dia, max_dia, tags)
_SHAFT_BORES = [
    (7.8, 8.2, ("REX_8mm_shaft",)),
    (5.8, 6.2, ("6mm_shaft",)),
]

# Pin hole classifications
_PIN_HOLES = [
    (4.8, 5.2, ("5mm_pin",)),
    (2.9, 3.1, ("3mm_pin",)),
]

# Mate inference from connection types
_MATE_MAP: dict[str, tuple[str, ...]] = {
    "bolt_hole_grid": ("brackets", "plates", "channels", "motors", "servos"),
    "shaft_bore": ("shafts", "hubs", "wheels"),
    "motor_mount_pattern": ("motors",),
    "pin_hole": ("pins", "axles"),
    "bearing_seat": ("bearings",),
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConnectionInfo:
    """A classified connection point."""
    connection_type: str
    compatible_with: tuple[str, ...]
    face_ref: str = ""
    pattern_ref: str = ""
    diameter_mm: float = 0.0
    profile: str = ""
    location: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class ClassificationResult:
    """Full classification output."""
    connection_points: tuple[ConnectionInfo, ...]
    compatible_with: tuple[str, ...]
    can_mate_with: tuple[str, ...]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(
    analysis: StepAnalysis,
    detection: HoleDetection,
) -> ClassificationResult:
    """Classify detected holes and patterns into connection types.

    Parameters
    ----------
    analysis : StepAnalysis
        Geometry analysis of the part.
    detection : HoleDetection
        Detected holes and patterns.

    Returns
    -------
    ClassificationResult
        Connection points, compatibility tags, and mate suggestions.
    """
    connections: list[ConnectionInfo] = []
    all_tags: set[str] = set()
    connection_types: set[str] = set()

    # Classify patterns
    pattern_hole_ids: set[int] = set()
    for pattern in detection.patterns:
        # Track which holes are in patterns so we don't double-classify
        for h in pattern.holes:
            pattern_hole_ids.add(id(h))

        conn, tags = _classify_pattern(pattern)
        connections.append(conn)
        all_tags.update(tags)
        connection_types.add(conn.connection_type)

    # Classify isolated holes (not part of any pattern)
    for hole in detection.holes:
        if id(hole) in pattern_hole_ids:
            continue
        conn, tags = _classify_single_hole(hole)
        connections.append(conn)
        all_tags.update(tags)
        connection_types.add(conn.connection_type)

    can_mate = _infer_can_mate_with(connection_types)

    return ClassificationResult(
        connection_points=tuple(connections),
        compatible_with=tuple(sorted(all_tags)),
        can_mate_with=tuple(sorted(can_mate)),
    )


# ---------------------------------------------------------------------------
# Pattern classification
# ---------------------------------------------------------------------------

def _classify_pattern(
    pattern: DetectedPattern,
) -> tuple[ConnectionInfo, set[str]]:
    """Classify a hole pattern as a connection type."""
    tags: set[str] = set()
    bolt = _map_bolt_size(pattern.hole_diameter_mm)

    if bolt:
        tags.add(f"{bolt}_bolt")

    # Check for goBILDA 8mm pitch
    is_gobilda = (
        abs(pattern.pitch_x_mm - _GOBILDA_PITCH_MM) < _PITCH_TOLERANCE
        or abs(pattern.pitch_y_mm - _GOBILDA_PITCH_MM) < _PITCH_TOLERANCE
    )
    if is_gobilda:
        tags.add("gobilda_8mm_pattern")

    conn = ConnectionInfo(
        connection_type="bolt_hole_grid",
        compatible_with=tuple(sorted(tags)),
        face_ref=pattern.face_ref,
        pattern_ref=pattern.pattern_id,
        diameter_mm=pattern.hole_diameter_mm,
    )

    return conn, tags


# ---------------------------------------------------------------------------
# Single hole classification
# ---------------------------------------------------------------------------

def _classify_single_hole(
    hole: DetectedHole,
) -> tuple[ConnectionInfo, set[str]]:
    """Classify an isolated hole."""
    tags: set[str] = set()

    # Check shaft bore sizes
    for min_d, max_d, bore_tags in _SHAFT_BORES:
        if min_d <= hole.diameter_mm <= max_d:
            tags.update(bore_tags)
            conn = ConnectionInfo(
                connection_type="shaft_bore",
                compatible_with=tuple(sorted(tags)),
                face_ref=hole.face_id,
                diameter_mm=hole.diameter_mm,
                location=hole.center,
            )
            return conn, tags

    # Check pin hole sizes
    for min_d, max_d, pin_tags in _PIN_HOLES:
        if min_d <= hole.diameter_mm <= max_d:
            tags.update(pin_tags)
            conn = ConnectionInfo(
                connection_type="pin_hole",
                compatible_with=tuple(sorted(tags)),
                face_ref=hole.face_id,
                diameter_mm=hole.diameter_mm,
                location=hole.center,
            )
            return conn, tags

    # Generic bolt hole
    bolt = _map_bolt_size(hole.diameter_mm)
    if bolt:
        tags.add(f"{bolt}_bolt")

    conn = ConnectionInfo(
        connection_type="bolt_hole_grid",
        compatible_with=tuple(sorted(tags)),
        face_ref=hole.face_id,
        diameter_mm=hole.diameter_mm,
        location=hole.center,
    )
    return conn, tags


# ---------------------------------------------------------------------------
# Mate inference
# ---------------------------------------------------------------------------

def _infer_can_mate_with(connection_types: set[str]) -> set[str]:
    """Infer what part categories this part can mate with."""
    mates: set[str] = set()
    for ct in connection_types:
        mates.update(_MATE_MAP.get(ct, ()))
    return mates
