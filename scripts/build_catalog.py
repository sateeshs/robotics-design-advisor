#!/usr/bin/env python
"""Build catalog.json and categories.json from profile JSON files.

Usage:
    python scripts/build_catalog.py \
        --profiles-dir ./profiles/gobilda \
        --output-dir ./profiles/gobilda
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("build-catalog")


def _load_profiles(profiles_dir: Path) -> list[dict]:
    """Load all profile JSON files from a directory tree."""
    profiles = []
    for json_path in sorted(profiles_dir.rglob("*.json")):
        if json_path.name.startswith("_"):
            continue
        if json_path.name in ("catalog.json", "categories.json"):
            continue

        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping %s: %s", json_path, exc)
            continue

        if "sku" in data and "category" in data:
            profiles.append(data)

    return profiles


def _build_catalog_entry(profile: dict) -> dict:
    """Convert a full profile to a catalog entry."""
    geo = profile.get("geometry", {})
    bb = geo.get("bounding_box", {})

    hole_count = sum(hp.get("count", 0) for hp in profile.get("hole_patterns", []))
    bolt_size = ""
    for hp in profile.get("hole_patterns", []):
        if hp.get("bolt_size"):
            bolt_size = hp["bolt_size"]
            break

    return {
        "sku": profile["sku"],
        "name": profile["name"],
        "category": profile["category"],
        "bounding_box": {
            "x": bb.get("x", 0),
            "y": bb.get("y", 0),
            "z": bb.get("z", 0),
            "unit": bb.get("unit", "mm"),
        },
        "mass_grams": geo.get("mass_grams", 0),
        "hole_count": hole_count,
        "bolt_size": bolt_size,
        "compatible_with": profile.get("compatible_with", []),
    }


def _build_categories(profiles: list[dict]) -> list[dict]:
    """Build category summaries from profiles."""
    counts: dict[str, int] = defaultdict(int)
    for p in profiles:
        counts[p["category"]] += 1

    return sorted(
        [{"category": cat, "part_count": count, "description": ""} for cat, count in counts.items()],
        key=lambda c: c["category"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build catalog index from profiles")
    parser.add_argument("--profiles-dir", required=True, help="Directory containing profile JSONs")
    parser.add_argument("--output-dir", required=True, help="Output directory for catalog/categories")
    args = parser.parse_args()

    profiles_dir = Path(args.profiles_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profiles = _load_profiles(profiles_dir)
    logger.info("Loaded %d profiles", len(profiles))

    if not profiles:
        logger.warning("No profiles found in %s", profiles_dir)
        return

    # Build catalog
    catalog = [_build_catalog_entry(p) for p in profiles]
    catalog_path = output_dir / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    logger.info("Wrote catalog: %s (%d entries)", catalog_path, len(catalog))

    # Build categories
    categories = _build_categories(profiles)
    categories_path = output_dir / "categories.json"
    with open(categories_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2)
    logger.info("Wrote categories: %s (%d categories)", categories_path, len(categories))


if __name__ == "__main__":
    main()
