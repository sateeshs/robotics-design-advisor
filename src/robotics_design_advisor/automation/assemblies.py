"""Assembly operations mixin for SolidWorks COM automation.

Provides component insertion, mate management, and assembly tree inspection.
All position values are in **millimeters** at the public API boundary;
conversion to meters (SolidWorks internal) happens inside each method.

Requires the host class to provide:
- ``self._sw_app``: SolidWorks COM application object
- ``self.is_connected``: bool property
- ``self._result(success, message, error_code=0, data=None)``: result factory
"""

from __future__ import annotations

import enum
import logging
import math
from typing import Any

from ..parts.resolver import SkuNotFoundError, SkuResolver
from ._helpers import get_assembly_doc

logger = logging.getLogger(__name__)


class MateType(enum.IntEnum):
    """SolidWorks mate type constants (swMateType_e)."""
    COINCIDENT = 0
    CONCENTRIC = 1
    PERPENDICULAR = 2
    PARALLEL = 3
    TANGENT = 4
    DISTANCE = 5
    ANGLE = 6
    SYMMETRIC = 8
    WIDTH = 11
    LOCK = 16


class AssemblyOperations:
    """Mixin: assembly-level COM operations.

    Mixed into a host class that owns the SolidWorks connection.
    """

    # ------------------------------------------------------------------
    # Insert component
    # ------------------------------------------------------------------

    def insert_component(
        self,
        filepath: str,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> dict:
        """Insert a component into the active assembly.

        Parameters
        ----------
        filepath : str
            Absolute path to the part or sub-assembly file.
        position : tuple[float, float, float]
            (x, y, z) in **millimeters**.
        rotation : tuple[float, float, float]
            (rx, ry, rz) in **degrees** (currently unused by AddComponent5).
        """
        doc, err = get_assembly_doc(self)
        if err:
            return err

        # SolidWorks expects meters
        x_m = position[0] / 1000.0
        y_m = position[1] / 1000.0
        z_m = position[2] / 1000.0

        try:
            component = doc.AddComponent5(filepath, x_m, y_m, z_m, "")
        except Exception as exc:
            logger.error("AddComponent5 failed: %s", exc)
            return self._result(False, f"COM error inserting component: {exc}")  # type: ignore[attr-defined]

        if component is None:
            return self._result(  # type: ignore[attr-defined]
                False,
                f"Failed to insert component from '{filepath}'",
            )

        name = getattr(component, "Name2", "unknown")
        logger.info("Inserted component '%s' at (%.1f, %.1f, %.1f) mm", name, *position)

        return self._result(  # type: ignore[attr-defined]
            True,
            f"Component '{name}' inserted",
            data={"component_name": name, "filepath": filepath},
        )

    # ------------------------------------------------------------------
    # Insert by SKU (uses resolver)
    # ------------------------------------------------------------------

    def insert_library_part(
        self,
        sku: str,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        resolver_base_path: str = r"C:\goBILDA",
        resolver_category_map: dict[str, str] | None = None,
    ) -> dict:
        """Insert a goBILDA part by SKU.

        Resolves the SKU to a file path, then calls :meth:`insert_component`.
        """
        if resolver_category_map is None:
            resolver_category_map = _DEFAULT_GOBILDA_CATEGORIES

        resolver = SkuResolver(
            base_path=resolver_base_path,
            category_map=resolver_category_map,
        )

        try:
            filepath = resolver.resolve(sku)
        except (SkuNotFoundError, ValueError) as exc:
            return self._result(False, str(exc))  # type: ignore[attr-defined]

        result = self.insert_component(filepath, position, rotation)
        if result.get("data"):
            result = {**result, "data": {**result["data"], "sku": sku}}
        return result

    # ------------------------------------------------------------------
    # Mates
    # ------------------------------------------------------------------

    def add_mate(
        self,
        mate_type: MateType,
        entity1: str,
        entity2: str,
        value_mm: float = 0.0,
        angle_deg: float = 0.0,
    ) -> dict:
        """Add a mate constraint between two entities.

        Parameters
        ----------
        mate_type : MateType
            Type of mate (coincident, concentric, distance, etc.).
        entity1, entity2 : str
            Entity reference strings (e.g. ``"face1@channel-1"``).
        value_mm : float
            Distance value for distance mates, in mm.
        angle_deg : float
            Angle value for angle mates, in degrees.
        """
        doc, err = get_assembly_doc(self)
        if err:
            return err

        # Convert units for SolidWorks
        value_m = value_mm / 1000.0
        angle_rad = math.radians(angle_deg)

        try:
            mate_feature = doc.AddMate3(
                int(mate_type),  # mate type
                0,               # alignment (auto)
                False,           # flip
                value_m,         # distance/angle value
                value_m,         # min value (same for fixed)
                value_m,         # max value (same for fixed)
                angle_rad,       # angle value
                angle_rad,       # angle min
                angle_rad,       # angle max
                0,               # force to manifold
                1,               # error status return (placeholder)
            )
        except Exception as exc:
            logger.error("AddMate3 failed: %s", exc)
            return self._result(False, f"COM error adding mate: {exc}")  # type: ignore[attr-defined]

        if mate_feature is None:
            return self._result(  # type: ignore[attr-defined]
                False,
                f"Failed to add {mate_type.name} mate between '{entity1}' and '{entity2}'",
            )

        logger.info(
            "Added %s mate: %s ↔ %s", mate_type.name, entity1, entity2,
        )
        return self._result(  # type: ignore[attr-defined]
            True,
            f"{mate_type.name} mate added",
            data={
                "mate_type": mate_type.name,
                "entity1": entity1,
                "entity2": entity2,
            },
        )

    # ------------------------------------------------------------------
    # Assembly tree inspection
    # ------------------------------------------------------------------

    def get_assembly_tree(self) -> dict:
        """Return the assembly component tree as a JSON-serializable dict."""
        doc, err = get_assembly_doc(self)
        if err:
            return err

        config = doc.GetActiveConfiguration()
        root = config.GetRootComponent3(True)
        children = root.GetChildren() or []

        components = []
        for child in children:
            comp_info = {
                "name": getattr(child, "Name2", "unknown"),
                "path": child.GetPathName() if hasattr(child, "GetPathName") else "",
                "suppressed": bool(child.IsSuppressed()) if hasattr(child, "IsSuppressed") else False,
            }

            # Extract position from transform matrix if available
            transform = getattr(child, "Transform2", None)
            if transform is not None:
                arr = getattr(transform, "ArrayData", None)
                if arr and len(arr) >= 16:
                    comp_info["position_mm"] = (
                        round(arr[12] * 1000.0, 2),
                        round(arr[13] * 1000.0, 2),
                        round(arr[14] * 1000.0, 2),
                    )

            components.append(comp_info)

        return self._result(  # type: ignore[attr-defined]
            True,
            f"Assembly tree: {len(components)} component(s)",
            data={"components": components, "count": len(components)},
        )

    # ------------------------------------------------------------------
    # List mates
    # ------------------------------------------------------------------

    def list_mates(self) -> dict:
        """List all mates in the active assembly."""
        doc, err = get_assembly_doc(self)
        if err:
            return err

        mate_count = doc.GetMateCount() if hasattr(doc, "GetMateCount") else 0
        mates_raw = doc.GetMates() if hasattr(doc, "GetMates") else []

        mates = []
        for mate_obj in (mates_raw or []):
            mate_info: dict[str, Any] = {
                "name": getattr(mate_obj, "Name", "unknown"),
                "type": getattr(mate_obj, "Type", -1),
            }

            entity_count = (
                mate_obj.GetMateEntityCount()
                if hasattr(mate_obj, "GetMateEntityCount")
                else 0
            )

            entities = []
            for i in range(entity_count):
                try:
                    entity = mate_obj.MateEntity(i)
                    ref_comp = getattr(entity, "ReferenceComponent", None)
                    entities.append(getattr(ref_comp, "Name2", "unknown") if ref_comp else "unknown")
                except Exception as exc:
                    logger.warning("MateEntity(%d) failed: %s", i, exc)
                    entities.append("unknown")

            mate_info["entities"] = entities
            mates.append(mate_info)

        return self._result(  # type: ignore[attr-defined]
            True,
            f"Found {len(mates)} mate(s)",
            data={"mates": mates, "count": len(mates)},
        )


# ---------------------------------------------------------------------------
# Default goBILDA category map
# ---------------------------------------------------------------------------

_DEFAULT_GOBILDA_CATEGORIES: dict[str, str] = {
    "1120": "channel",
    "1121": "channel",
    "1100": "brackets",
    "1101": "brackets",
    "1301": "brackets",
    "2900": "wheels",
    "5202": "motors",
    "5201": "motors",
    "1310": "shafting",
    "1309": "shafting",
    "2800": "gears",
    "2801": "gears",
    "3400": "servos",
    "3200": "linear_motion",
    "3201": "linear_motion",
}
