"""Core STEP geometry extraction.

Loads a STEP file via CadQuery and extracts bounding box, volume,
center of mass, and face information (normals, areas, centers, types).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, overload

import cadquery as cq

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

_FACE_TYPE_MAP = {
    "Plane": "planar",
    "Cylinder": "cylindrical",
    "Cone": "conical",
}


@dataclass(frozen=True)
class FaceInfo:
    """Geometric information about a single face."""
    face_id: str
    normal: tuple[float, float, float]
    area_mm2: float
    center: tuple[float, float, float]
    face_type: str  # "planar" | "cylindrical" | "conical" | "other"
    outer_wire_edge_count: int


@dataclass(frozen=True)
class StepAnalysis:
    """Result of analyzing a STEP file's geometry."""
    bounding_box: tuple[float, float, float]  # (x, y, z) in mm
    volume_mm3: float
    center_of_mass: tuple[float, float, float]
    faces: tuple[FaceInfo, ...]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_face_type(geom_type: str) -> str:
    """Map a CadQuery geomType string to our face type label."""
    return _FACE_TYPE_MAP.get(geom_type, "other")


def analyze(
    step_path: str,
    *,
    return_shape: bool = False,
) -> StepAnalysis | tuple[StepAnalysis, Any]:
    """Analyze a STEP file and extract geometry summary.

    Parameters
    ----------
    step_path : str
        Path to a ``.STEP`` or ``.stp`` file.
    return_shape : bool
        If True, also return the loaded CadQuery Workplane for downstream use
        (hole detection needs the shape object).

    Returns
    -------
    StepAnalysis
        Geometry summary.  If ``return_shape`` is True, returns
        ``(StepAnalysis, shape)`` instead.
    """
    logger.debug("Loading STEP: %s", step_path)
    shape = cq.importers.importStep(step_path)

    solid = shape.val()
    bb = solid.BoundingBox()
    bounding_box = (bb.xlen, bb.ylen, bb.zlen)
    volume_mm3 = solid.Volume()
    com = solid.Center()
    center_of_mass = (com.x, com.y, com.z)

    cq_faces = shape.faces().vals()
    faces = tuple(_extract_face(i, f) for i, f in enumerate(cq_faces))

    analysis = StepAnalysis(
        bounding_box=bounding_box,
        volume_mm3=volume_mm3,
        center_of_mass=center_of_mass,
        faces=faces,
    )

    if return_shape:
        return analysis, shape
    return analysis


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _extract_face(index: int, face: Any) -> FaceInfo:
    """Extract geometry info from a single CadQuery face."""
    geom_type = face.geomType()
    face_type = classify_face_type(geom_type)

    normal_vec = face.normalAt()
    normal = (normal_vec.x, normal_vec.y, normal_vec.z)

    area_mm2 = face.Area()

    center_pt = face.Center()
    center = (center_pt.x, center_pt.y, center_pt.z)

    # Count edges on outer wire for pattern heuristics
    try:
        outer_wire = face.outerWire()
        edge_count = len(outer_wire.Edges())
    except Exception:
        edge_count = 0

    return FaceInfo(
        face_id=f"face_{index}",
        normal=normal,
        area_mm2=area_mm2,
        center=center,
        face_type=face_type,
        outer_wire_edge_count=edge_count,
    )
