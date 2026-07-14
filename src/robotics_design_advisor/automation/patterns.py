"""Component pattern operations mixin for SolidWorks COM automation.

Provides linear and circular component patterns for assembly automation.

Requires the host class to provide:
- ``self._sw_app``: SolidWorks COM application object
- ``self.is_connected``: bool property
- ``self._result(success, message, error_code=0, data=None)``: result factory
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence

from ._helpers import get_assembly_doc

logger = logging.getLogger(__name__)


class PatternOperations:
    """Mixin: linear and circular component patterns."""

    # ------------------------------------------------------------------
    # Linear pattern
    # ------------------------------------------------------------------

    def create_linear_pattern(
        self,
        components: Sequence[str],
        direction: tuple[float, float, float],
        count: int,
        spacing_mm: float,
    ) -> dict:
        """Create a linear pattern of components.

        Parameters
        ----------
        components : sequence of str
            Component names to pattern.
        direction : tuple[float, float, float]
            Direction vector (x, y, z) — does not need to be normalized.
        count : int
            Total number of instances (including original). Must be >= 2.
        spacing_mm : float
            Distance between instances in mm. Must be > 0.
        """
        if count < 2:
            raise ValueError(f"count must be >= 2, got {count}")
        if spacing_mm <= 0:
            raise ValueError(f"spacing_mm must be positive, got {spacing_mm}")

        doc, err = get_assembly_doc(self)
        if err:
            return err

        spacing_m = spacing_mm / 1000.0
        fm = doc.FeatureManager

        try:
            pattern = fm.InsertLinearPattern(
                count,          # D1 count
                spacing_m,      # D1 spacing (meters)
                1,              # D2 count (single direction)
                0.0,            # D2 spacing
                True,           # seed only
                direction[0],   # D1 direction X
                direction[1],   # D1 direction Y
                direction[2],   # D1 direction Z
            )
        except Exception as exc:
            logger.error("InsertLinearPattern failed: %s", exc)
            return self._result(False, f"COM error creating linear pattern: {exc}")  # type: ignore[attr-defined]

        if pattern is None:
            return self._result(  # type: ignore[attr-defined]
                False,
                f"Failed to create linear pattern for {components}",
            )

        logger.info(
            "Created linear pattern: %d instances, %.1f mm spacing",
            count, spacing_mm,
        )
        return self._result(  # type: ignore[attr-defined]
            True,
            f"Linear pattern created: {count} instances at {spacing_mm}mm spacing",
            data={
                "pattern_type": "linear",
                "components": list(components),
                "count": count,
                "spacing_mm": spacing_mm,
                "direction": direction,
            },
        )

    # ------------------------------------------------------------------
    # Circular pattern
    # ------------------------------------------------------------------

    def create_circular_pattern(
        self,
        components: Sequence[str],
        axis: tuple[float, float, float],
        count: int,
        total_angle_deg: float = 360.0,
    ) -> dict:
        """Create a circular pattern of components.

        Parameters
        ----------
        components : sequence of str
            Component names to pattern.
        axis : tuple[float, float, float]
            Rotation axis vector (x, y, z).
        count : int
            Total number of instances (including original). Must be >= 2.
        total_angle_deg : float
            Total angle span in degrees (default 360 for full circle).
        """
        if count < 2:
            raise ValueError(f"count must be >= 2, got {count}")
        if total_angle_deg <= 0.0:
            raise ValueError(f"total_angle_deg must be positive, got {total_angle_deg}")

        doc, err = get_assembly_doc(self)
        if err:
            return err

        total_angle_rad = math.radians(total_angle_deg)
        fm = doc.FeatureManager

        try:
            pattern = fm.InsertCircularPattern(
                count,            # instance count
                total_angle_rad,  # total angle
                True,             # equal spacing
                axis[0],          # axis X
                axis[1],          # axis Y
                axis[2],          # axis Z
            )
        except Exception as exc:
            logger.error("InsertCircularPattern failed: %s", exc)
            return self._result(False, f"COM error creating circular pattern: {exc}")  # type: ignore[attr-defined]

        if pattern is None:
            return self._result(  # type: ignore[attr-defined]
                False,
                f"Failed to create circular pattern for {components}",
            )

        logger.info(
            "Created circular pattern: %d instances, %.1f° total",
            count, total_angle_deg,
        )
        return self._result(  # type: ignore[attr-defined]
            True,
            f"Circular pattern created: {count} instances over {total_angle_deg}°",
            data={
                "pattern_type": "circular",
                "components": list(components),
                "count": count,
                "total_angle_deg": total_angle_deg,
                "axis": axis,
            },
        )
