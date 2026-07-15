"""Profile builder — orchestrates STEP analysis into PartProfile JSON.

Runs the full pipeline: analyze → detect holes → classify connections,
then assembles the result into the JSON schema consumed by the
Parts Intelligence MCP server.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .analyzer import StepAnalysis, analyze
from .connection_classifier import ClassificationResult, classify
from .hole_detector import HoleDetection, detect, _map_bolt_size

logger = logging.getLogger(__name__)

# Aluminum 6061-T6 density (most goBILDA parts are aluminum)
ALUMINUM_DENSITY_G_CM3 = 2.7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_profile(
    step_path: str,
    sku: str,
    name: str,
    category: str,
) -> dict:
    """Analyze a STEP file and build a PartProfile-compatible dict.

    Parameters
    ----------
    step_path : str
        Path to the STEP file.
    sku : str
        Part SKU (e.g. "1120-0001-0288").
    name : str
        Human-readable part name.
    category : str
        Part category (e.g. "structure/channel").

    Returns
    -------
    dict
        JSON-serializable profile matching the PartProfile schema.
    """
    analysis, shape = analyze(step_path, return_shape=True)
    detection = detect(analysis, shape)
    classification = classify(analysis, detection)

    return _assemble_profile(
        sku=sku,
        name=name,
        category=category,
        analysis=analysis,
        detection=detection,
        classification=classification,
    )


def write_profile(profile: dict, output_dir: str) -> Path:
    """Write a profile dict to a JSON file.

    Creates ``{output_dir}/{category}/{sku}.json``.

    Returns
    -------
    Path
        The path to the written file.
    """
    category = profile["category"]
    sku = profile["sku"]

    out_path = Path(output_dir)
    for segment in category.split("/"):
        out_path = out_path / segment

    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{sku}.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    logger.info("Wrote profile: %s", file_path)
    return file_path


# ---------------------------------------------------------------------------
# Internal — profile assembly
# ---------------------------------------------------------------------------

def _assemble_profile(
    *,
    sku: str,
    name: str,
    category: str,
    analysis: StepAnalysis,
    detection: HoleDetection,
    classification: ClassificationResult,
) -> dict:
    """Assemble all analysis results into a profile dict."""
    volume_cm3 = round(analysis.volume_mm3 / 1000.0, 2)
    mass_grams = round(volume_cm3 * ALUMINUM_DENSITY_G_CM3, 1)

    # Build geometry section
    geometry = {
        "bounding_box": {
            "x": round(analysis.bounding_box[0], 2),
            "y": round(analysis.bounding_box[1], 2),
            "z": round(analysis.bounding_box[2], 2),
            "unit": "mm",
        },
        "volume_cm3": volume_cm3,
        "mass_grams": mass_grams,
        "center_of_mass": [
            round(analysis.center_of_mass[0], 2),
            round(analysis.center_of_mass[1], 2),
            round(analysis.center_of_mass[2], 2),
        ],
    }

    # Build hole patterns
    hole_patterns = []
    pattern_face_map: dict[str, str] = {}  # face_id → pattern_id

    for p in detection.patterns:
        bolt_size = _map_bolt_size(p.hole_diameter_mm)
        hole_patterns.append({
            "pattern_id": p.pattern_id,
            "face_ref": p.face_ref,
            "hole_diameter_mm": p.hole_diameter_mm,
            "hole_type": "through",
            "pitch_x_mm": p.pitch_x_mm,
            "pitch_y_mm": p.pitch_y_mm,
            "grid": list(p.grid),
            "bolt_size": bolt_size,
            "count": p.count,
        })
        pattern_face_map[p.face_ref] = p.pattern_id

    # Build mounting faces (planar faces that have hole patterns)
    mounting_faces = []
    for fi in analysis.faces:
        if fi.face_type != "planar":
            continue
        has_pattern = fi.face_id in pattern_face_map
        if not has_pattern:
            # Only include large planar faces as mounting faces
            if fi.area_mm2 < 100.0:
                continue
        mounting_faces.append({
            "face_id": fi.face_id,
            "normal": list(fi.normal),
            "area_mm2": round(fi.area_mm2, 2),
            "center": list(fi.center),
            "face_type": fi.face_type,
            "has_holes": has_pattern,
            "hole_pattern_ref": pattern_face_map.get(fi.face_id, ""),
        })

    # Build connection points
    connection_points = []
    for cp in classification.connection_points:
        point: dict = {
            "connection_type": cp.connection_type,
            "compatible_with": list(cp.compatible_with),
        }
        if cp.face_ref:
            point["face_ref"] = cp.face_ref
        if cp.pattern_ref:
            point["pattern_ref"] = cp.pattern_ref
        if cp.diameter_mm > 0:
            point["diameter_mm"] = cp.diameter_mm
        if cp.profile:
            point["profile"] = cp.profile
        if any(v != 0.0 for v in cp.location):
            point["location"] = list(cp.location)
        connection_points.append(point)

    source_file = f"{category}/{sku}.STEP"

    return {
        "sku": sku,
        "name": name,
        "category": category,
        "source_file": source_file,
        "schema_version": 1,
        "geometry": geometry,
        "mounting_faces": mounting_faces,
        "hole_patterns": hole_patterns,
        "connection_points": connection_points,
        "compatible_with": list(classification.compatible_with),
        "can_mate_with": list(classification.can_mate_with),
    }
