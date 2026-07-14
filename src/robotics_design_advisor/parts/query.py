"""Tiered search engine for goBILDA part profiles.

Loads part profiles from a directory tree and exposes three tiers:

- **Tier 1**: Category summaries (list_categories) — ~2 KB in memory.
- **Tier 2**: Catalog entries (search) — lightweight search results.
- **Tier 3**: Full profiles (get_profile) — loaded per-part on demand.

All data is read-only after construction.  The catalog is an in-memory
index built once at load time from the JSON profile files on disk.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import (
    BoundingBox,
    CatalogEntry,
    CategorySummary,
    ConnectionPoint,
    Geometry,
    HolePattern,
    MountingFace,
    PartProfile,
)

logger = logging.getLogger(__name__)


class ProfileNotFoundError(Exception):
    """Raised when a requested SKU has no profile on disk."""


class PartsCatalog:
    """In-memory index over goBILDA part profiles.

    Parameters
    ----------
    profiles_dir : str | Path
        Root directory containing ``{category}/{sku}.json`` files.
    """

    def __init__(self, profiles_dir: str | Path) -> None:
        self._profiles_dir = Path(profiles_dir)
        self._catalog: dict[str, CatalogEntry] = {}
        self._categories: dict[str, int] = {}
        self._load_catalog()

    # ------------------------------------------------------------------
    # Tier 1 — categories
    # ------------------------------------------------------------------

    def list_categories(self) -> list[CategorySummary]:
        """Return Tier 1 category summaries sorted by name."""
        return sorted(
            (
                CategorySummary(category=cat, part_count=count)
                for cat, count in self._categories.items()
            ),
            key=lambda c: c.category,
        )

    # ------------------------------------------------------------------
    # Tier 2 — search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        *,
        category: str | None = None,
        min_length_mm: float | None = None,
        max_length_mm: float | None = None,
        compatible_with: str | None = None,
        max_results: int = 20,
    ) -> list[CatalogEntry]:
        """Search the catalog by keyword, category, size, or tag.

        Parameters
        ----------
        query : str
            Free-text search against SKU and name (case-insensitive).
        category : str, optional
            Filter to a specific category (e.g. ``"structure/channel"``).
        min_length_mm, max_length_mm : float, optional
            Filter by the longest bounding-box dimension.
        compatible_with : str, optional
            Filter to parts that carry this compatibility tag.
        max_results : int
            Cap on returned results (default 20).
        """
        query_lower = query.lower()
        results: list[CatalogEntry] = []

        for entry in self._catalog.values():
            if category and entry.category != category:
                continue

            if query_lower:
                haystack = f"{entry.sku} {entry.name}".lower()
                if not all(term in haystack for term in query_lower.split()):
                    continue

            longest = max(entry.bounding_box.x, entry.bounding_box.y, entry.bounding_box.z)
            if min_length_mm is not None and longest < min_length_mm:
                continue
            if max_length_mm is not None and longest > max_length_mm:
                continue

            if compatible_with and compatible_with not in entry.compatible_with:
                continue

            results.append(entry)
            if len(results) >= max_results:
                break

        return results

    # ------------------------------------------------------------------
    # Tier 2 — find compatible
    # ------------------------------------------------------------------

    def find_compatible(
        self,
        tag: str,
        *,
        category: str | None = None,
        max_results: int = 20,
    ) -> list[CatalogEntry]:
        """Find parts that carry a specific compatibility tag.

        Parameters
        ----------
        tag : str
            Compatibility tag to search for (e.g. ``"REX_8mm_shaft"``).
        category : str, optional
            Restrict to a single category.
        max_results : int
            Cap on results.
        """
        return self.search(compatible_with=tag, category=category, max_results=max_results)

    # ------------------------------------------------------------------
    # Tier 3 — full profile
    # ------------------------------------------------------------------

    def get_profile(self, sku: str) -> PartProfile:
        """Load the full Tier 3 profile for a specific SKU.

        Reads from disk each time — profiles are not cached in memory
        to keep the catalog lightweight.

        Raises
        ------
        ProfileNotFoundError
            If no profile file exists for the SKU.
        """
        entry = self._catalog.get(sku)
        if entry is None:
            raise ProfileNotFoundError(f"No profile for SKU '{sku}'")

        path = self._find_profile_path(sku, entry.category)
        if path is None:
            raise ProfileNotFoundError(f"Profile file missing for SKU '{sku}'")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return _parse_profile(data)

    # ------------------------------------------------------------------
    # Catalog size
    # ------------------------------------------------------------------

    @property
    def part_count(self) -> int:
        """Total number of indexed parts."""
        return len(self._catalog)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_catalog(self) -> None:
        """Walk the profiles directory and build the in-memory index."""
        if not self._profiles_dir.is_dir():
            logger.warning("Profiles directory does not exist: %s", self._profiles_dir)
            return

        for json_path in sorted(self._profiles_dir.rglob("*.json")):
            if json_path.name.startswith("_"):
                continue

            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Skipping %s: %s", json_path, exc)
                continue

            entry = _parse_catalog_entry(data)
            if entry is None:
                continue

            self._catalog[entry.sku] = entry
            self._categories[entry.category] = self._categories.get(entry.category, 0) + 1

        logger.info(
            "Loaded %d parts across %d categories",
            len(self._catalog),
            len(self._categories),
        )

    def _find_profile_path(self, sku: str, category: str) -> Path | None:
        """Locate the JSON file for a SKU within the profiles directory."""
        # Category path segments: "structure/channel" → structure/channel/
        cat_dir = self._profiles_dir
        for segment in category.split("/"):
            cat_dir = cat_dir / segment

        candidate = cat_dir / f"{sku}.json"
        if candidate.is_file():
            return candidate

        # Fallback: search all subdirectories
        for p in self._profiles_dir.rglob(f"{sku}.json"):
            return p

        return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_catalog_entry(data: dict[str, Any]) -> CatalogEntry | None:
    """Extract a lightweight CatalogEntry from raw JSON."""
    sku = data.get("sku")
    name = data.get("name")
    category = data.get("category")
    if not sku or not name or not category:
        return None

    geo = data.get("geometry", {})
    bb_raw = geo.get("bounding_box", {})
    bb = BoundingBox(
        x=float(bb_raw.get("x", 0)),
        y=float(bb_raw.get("y", 0)),
        z=float(bb_raw.get("z", 0)),
        unit=bb_raw.get("unit", "mm"),
    )

    # Aggregate hole count
    hole_count = 0
    bolt_size = ""
    for hp in data.get("hole_patterns", []):
        hole_count += hp.get("count", 0)
        if not bolt_size:
            bolt_size = hp.get("bolt_size", "")

    return CatalogEntry(
        sku=sku,
        name=name,
        category=category,
        bounding_box=bb,
        mass_grams=float(geo.get("mass_grams", 0)),
        hole_count=hole_count,
        bolt_size=bolt_size,
        compatible_with=tuple(data.get("compatible_with", [])),
    )


def _parse_profile(data: dict[str, Any]) -> PartProfile:
    """Parse a full PartProfile from raw JSON."""
    geo_raw = data["geometry"]
    bb_raw = geo_raw["bounding_box"]

    geometry = Geometry(
        bounding_box=BoundingBox(
            x=float(bb_raw["x"]),
            y=float(bb_raw["y"]),
            z=float(bb_raw["z"]),
            unit=bb_raw.get("unit", "mm"),
        ),
        volume_cm3=float(geo_raw["volume_cm3"]),
        mass_grams=float(geo_raw["mass_grams"]),
        center_of_mass=tuple(geo_raw["center_of_mass"]),
    )

    mounting_faces = tuple(
        MountingFace(
            face_id=mf["face_id"],
            normal=tuple(mf["normal"]),
            area_mm2=float(mf["area_mm2"]),
            center=tuple(mf["center"]),
            face_type=mf.get("face_type", "planar"),
            has_holes=mf.get("has_holes", False),
            hole_pattern_ref=mf.get("hole_pattern_ref", ""),
        )
        for mf in data.get("mounting_faces", [])
    )

    hole_patterns = tuple(
        HolePattern(
            pattern_id=hp["pattern_id"],
            face_ref=hp["face_ref"],
            hole_diameter_mm=float(hp["hole_diameter_mm"]),
            hole_type=hp["hole_type"],
            pitch_x_mm=float(hp["pitch_x_mm"]),
            pitch_y_mm=float(hp["pitch_y_mm"]),
            grid=tuple(hp["grid"]),
            bolt_size=hp["bolt_size"],
            count=int(hp["count"]),
        )
        for hp in data.get("hole_patterns", [])
    )

    connection_points = tuple(
        ConnectionPoint(
            connection_type=cp["connection_type"],
            compatible_with=tuple(cp.get("compatible_with", [])),
            face_ref=cp.get("face_ref", ""),
            pattern_ref=cp.get("pattern_ref", ""),
            diameter_mm=float(cp.get("diameter_mm", 0)),
            profile=cp.get("profile", ""),
            location=tuple(cp.get("location", (0, 0, 0))),
        )
        for cp in data.get("connection_points", [])
    )

    return PartProfile(
        sku=data["sku"],
        name=data["name"],
        category=data["category"],
        source_file=data["source_file"],
        geometry=geometry,
        mounting_faces=mounting_faces,
        hole_patterns=hole_patterns,
        connection_points=connection_points,
        compatible_with=tuple(data.get("compatible_with", [])),
        can_mate_with=tuple(data.get("can_mate_with", [])),
        schema_version=data.get("schema_version", 1),
    )
