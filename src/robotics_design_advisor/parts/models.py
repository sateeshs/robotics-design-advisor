"""Data models for part profiles and catalog entries.

All models are frozen dataclasses for immutability.
These represent the semantic metadata extracted from STEP geometry
by the analysis pipeline (Phase 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MateTypeHint = Literal[
    "coincident", "concentric", "distance", "tangent", "parallel",
]
HoleType = Literal["through", "blind", "counterbore", "countersink"]
ConnectionType = Literal[
    "bolt_hole_grid", "shaft_bore", "motor_mount_pattern",
    "bearing_seat", "servo_mount", "pin_hole",
]


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding box in millimeters."""
    x: float
    y: float
    z: float
    unit: str = "mm"


@dataclass(frozen=True)
class Geometry:
    """Summarized geometry for a part."""
    bounding_box: BoundingBox
    volume_cm3: float
    mass_grams: float
    center_of_mass: tuple[float, float, float]


@dataclass(frozen=True)
class HolePattern:
    """A regular pattern of holes on a face."""
    pattern_id: str
    face_ref: str
    hole_diameter_mm: float
    hole_type: HoleType
    pitch_x_mm: float
    pitch_y_mm: float
    grid: tuple[int, int]
    bolt_size: str
    count: int


@dataclass(frozen=True)
class MountingFace:
    """A planar face suitable for mounting."""
    face_id: str
    normal: tuple[float, float, float]
    area_mm2: float
    center: tuple[float, float, float]
    face_type: str = "planar"
    has_holes: bool = False
    hole_pattern_ref: str = ""


@dataclass(frozen=True)
class ConnectionPoint:
    """A connection feature on a part."""
    connection_type: ConnectionType
    compatible_with: tuple[str, ...]
    face_ref: str = ""
    pattern_ref: str = ""
    diameter_mm: float = 0.0
    profile: str = ""
    location: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class PartProfile:
    """Complete semantic profile for a single part.

    This is the Tier 3 data — full detail loaded per-part.
    """
    sku: str
    name: str
    category: str
    source_file: str
    geometry: Geometry
    mounting_faces: tuple[MountingFace, ...]
    hole_patterns: tuple[HolePattern, ...]
    connection_points: tuple[ConnectionPoint, ...]
    compatible_with: tuple[str, ...]
    can_mate_with: tuple[str, ...]
    schema_version: int = 1


@dataclass(frozen=True)
class CatalogEntry:
    """Abbreviated part info for the Tier 2 catalog index.

    Lighter than a full PartProfile — used for search results
    before the caller requests the full profile.
    """
    sku: str
    name: str
    category: str
    bounding_box: BoundingBox
    mass_grams: float
    hole_count: int
    bolt_size: str
    compatible_with: tuple[str, ...]


@dataclass(frozen=True)
class CategorySummary:
    """Tier 1 category index entry."""
    category: str
    part_count: int
    description: str = ""


@dataclass(frozen=True)
class MateSuggestion:
    """A suggested mate between two parts."""
    mate_type: MateTypeHint
    part_a_ref: str
    part_b_ref: str
    confidence: float  # 0.0-1.0
    rationale: str
    value_mm: float = 0.0
