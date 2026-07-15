"""Hole detection and pattern clustering for STEP geometry.

Finds cylindrical holes in a CadQuery shape, measures diameters,
and clusters regularly-spaced holes into grid patterns.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .analyzer import FaceInfo, StepAnalysis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hole diameter range to consider (mm)
_MIN_HOLE_DIA = 1.5
_MAX_HOLE_DIA = 12.0

# Minimum holes to form a pattern
_MIN_PATTERN_HOLES = 4

# Tolerance for pitch regularity (mm)
_PITCH_TOLERANCE = 0.5

# Bolt size mapping: (min_diameter_mm, max_diameter_mm) → bolt_size
_BOLT_SIZES = [
    (2.5, 2.7, "M2.5"),
    (3.2, 3.5, "M3"),
    (4.0, 4.3, "M4"),
    (5.0, 5.5, "M5"),
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DetectedHole:
    """A single cylindrical hole detected in the geometry."""
    face_id: str
    center: tuple[float, float, float]
    diameter_mm: float
    depth_mm: float
    hole_type: str  # "through" | "blind"


@dataclass(frozen=True)
class DetectedPattern:
    """A regular grid pattern of holes on a face."""
    pattern_id: str
    face_ref: str
    holes: tuple[DetectedHole, ...]
    hole_diameter_mm: float
    pitch_x_mm: float
    pitch_y_mm: float
    grid: tuple[int, int]
    count: int


@dataclass(frozen=True)
class HoleDetection:
    """Complete hole detection results."""
    holes: tuple[DetectedHole, ...]
    patterns: tuple[DetectedPattern, ...]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect(analysis: StepAnalysis, shape: Any) -> HoleDetection:
    """Detect holes and patterns in a shape.

    Parameters
    ----------
    analysis : StepAnalysis
        Previously computed geometry analysis.
    shape : CadQuery Workplane
        The loaded CadQuery shape for direct face access.
    """
    cq_faces = shape.faces().vals()
    holes = _find_cylindrical_holes(cq_faces, analysis)

    if not holes:
        return HoleDetection(holes=(), patterns=())

    # Group holes by parent face and diameter, then try pattern detection
    patterns = _detect_patterns(holes, analysis)

    return HoleDetection(
        holes=tuple(holes),
        patterns=tuple(patterns),
    )


# ---------------------------------------------------------------------------
# Bolt size mapping
# ---------------------------------------------------------------------------

def _map_bolt_size(diameter_mm: float) -> str:
    """Map a hole diameter to a standard bolt size."""
    for min_d, max_d, bolt in _BOLT_SIZES:
        if min_d <= diameter_mm <= max_d:
            return bolt
    return ""


# ---------------------------------------------------------------------------
# Hole finding
# ---------------------------------------------------------------------------

def _find_cylindrical_holes(
    cq_faces: list[Any],
    analysis: StepAnalysis,
) -> list[DetectedHole]:
    """Find cylindrical faces that represent holes."""
    holes: list[DetectedHole] = []

    for i, face in enumerate(cq_faces):
        try:
            geom_type = face.geomType()
        except Exception:
            continue

        if geom_type != "Cylinder":
            continue

        try:
            radius = face.radius()
        except Exception:
            continue

        diameter = radius * 2.0
        if diameter < _MIN_HOLE_DIA or diameter > _MAX_HOLE_DIA:
            continue

        center_pt = face.Center()
        center = (center_pt.x, center_pt.y, center_pt.z)

        # Find nearest planar face to assign as parent
        parent_face_id = _find_nearest_planar_face(center, analysis.faces)

        holes.append(DetectedHole(
            face_id=parent_face_id,
            center=center,
            diameter_mm=round(diameter, 2),
            depth_mm=0,  # Assume through-hole for now
            hole_type="through",
        ))

    return holes


def _find_nearest_planar_face(
    point: tuple[float, float, float],
    faces: tuple[FaceInfo, ...],
) -> str:
    """Find the nearest planar face to a point."""
    best_id = "face_0"
    best_dist = float("inf")

    for fi in faces:
        if fi.face_type != "planar":
            continue
        dist = math.dist(point, fi.center)
        if dist < best_dist:
            best_dist = dist
            best_id = fi.face_id

    return best_id


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def _detect_patterns(
    holes: list[DetectedHole],
    analysis: StepAnalysis,
) -> list[DetectedPattern]:
    """Group holes by face+diameter and detect grid patterns."""
    # Group by (face_id, diameter)
    groups: dict[tuple[str, float], list[DetectedHole]] = defaultdict(list)
    for h in holes:
        key = (h.face_id, h.diameter_mm)
        groups[key].append(h)

    patterns: list[DetectedPattern] = []
    pattern_counter = 0

    face_normals: dict[str, tuple[float, float, float]] = {
        fi.face_id: fi.normal for fi in analysis.faces
    }

    for (face_id, diameter), group in groups.items():
        if len(group) < _MIN_PATTERN_HOLES:
            continue

        normal = face_normals.get(face_id, (0, 1, 0))
        found = _cluster_into_pattern(group, face_normal=normal)

        for p_data in found:
            patterns.append(DetectedPattern(
                pattern_id=f"pattern_{pattern_counter}",
                face_ref=face_id,
                holes=tuple(p_data.holes),
                hole_diameter_mm=diameter,
                pitch_x_mm=p_data.pitch_x_mm,
                pitch_y_mm=p_data.pitch_y_mm,
                grid=p_data.grid,
                count=p_data.count,
            ))
            pattern_counter += 1

    return patterns


def _cluster_into_pattern(
    holes: list[DetectedHole],
    *,
    face_normal: tuple[float, float, float],
) -> list[DetectedPattern]:
    """Try to find a regular grid pattern in a set of same-diameter holes.

    Projects hole centers onto a 2D plane perpendicular to the face normal,
    finds dominant spacings, and verifies grid regularity.
    """
    if len(holes) < _MIN_PATTERN_HOLES:
        return []

    # Build a coordinate system on the face plane
    u_axis, v_axis = _make_plane_axes(face_normal)

    # Project hole centers onto 2D
    coords_2d = []
    for h in holes:
        u = h.center[0] * u_axis[0] + h.center[1] * u_axis[1] + h.center[2] * u_axis[2]
        v = h.center[0] * v_axis[0] + h.center[1] * v_axis[1] + h.center[2] * v_axis[2]
        coords_2d.append((u, v))

    # Find dominant pitch in each axis
    pitch_u = _find_dominant_pitch([c[0] for c in coords_2d])
    pitch_v = _find_dominant_pitch([c[1] for c in coords_2d])

    if pitch_u is None and pitch_v is None:
        return []

    # For single-row patterns, one pitch may be None
    if pitch_u is None:
        pitch_u = 0.0
    if pitch_v is None:
        pitch_v = 0.0

    # Count grid dimensions
    u_values = sorted(set(round(c[0] / max(pitch_u, 0.1)) for c in coords_2d)) if pitch_u > 0.1 else [0]
    v_values = sorted(set(round(c[1] / max(pitch_v, 0.1)) for c in coords_2d)) if pitch_v > 0.1 else [0]

    grid_u = len(u_values)
    grid_v = len(v_values)

    # Verify the pattern accounts for most holes
    expected = grid_u * grid_v
    if expected < _MIN_PATTERN_HOLES:
        return []

    actual = len(holes)
    if actual < expected * 0.7:
        return []

    # Use the larger pitch as x, smaller as y (or vice versa)
    px = max(pitch_u, pitch_v)
    py = min(pitch_u, pitch_v) if min(pitch_u, pitch_v) > 0.1 else px
    gx = max(grid_u, grid_v)
    gy = min(grid_u, grid_v) if min(grid_u, grid_v) > 0 else 1

    return [DetectedPattern(
        pattern_id="",  # Assigned by caller
        face_ref=holes[0].face_id,
        holes=tuple(holes),
        hole_diameter_mm=holes[0].diameter_mm,
        pitch_x_mm=round(px, 2),
        pitch_y_mm=round(py, 2),
        grid=(gx, gy),
        count=actual,
    )]


def _make_plane_axes(
    normal: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Create two orthogonal axes on the plane defined by normal."""
    nx, ny, nz = normal

    # Pick a vector not parallel to normal
    if abs(nx) < 0.9:
        ref = (1.0, 0.0, 0.0)
    else:
        ref = (0.0, 1.0, 0.0)

    # u = ref × normal (cross product)
    u = (
        ref[1] * nz - ref[2] * ny,
        ref[2] * nx - ref[0] * nz,
        ref[0] * ny - ref[1] * nx,
    )
    mag = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
    if mag < 1e-10:
        return (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    u = (u[0] / mag, u[1] / mag, u[2] / mag)

    # v = normal × u
    v = (
        ny * u[2] - nz * u[1],
        nz * u[0] - nx * u[2],
        nx * u[1] - ny * u[0],
    )

    return u, v


def _find_dominant_pitch(values: list[float]) -> float | None:
    """Find the most common spacing between sorted values.

    Returns None if no regular spacing is found.
    """
    if len(values) < 2:
        return None

    sorted_vals = sorted(values)
    spacings: list[float] = []
    for i in range(1, len(sorted_vals)):
        s = sorted_vals[i] - sorted_vals[i - 1]
        if s > 0.5:  # Skip near-zero spacings
            spacings.append(s)

    if not spacings:
        return None

    # Find the most frequent spacing (within tolerance)
    spacing_groups: dict[float, int] = {}
    for s in spacings:
        matched = False
        for ref in spacing_groups:
            if abs(s - ref) < _PITCH_TOLERANCE:
                spacing_groups[ref] += 1
                matched = True
                break
        if not matched:
            spacing_groups[s] = 1

    if not spacing_groups:
        return None

    # Dominant spacing must account for majority of gaps
    best_spacing = max(spacing_groups, key=spacing_groups.get)  # type: ignore[arg-type]
    best_count = spacing_groups[best_spacing]

    if best_count < len(spacings) * 0.5:
        return None

    return best_spacing
