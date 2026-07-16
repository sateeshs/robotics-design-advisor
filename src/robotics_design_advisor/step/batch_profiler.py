"""Batch STEP profiler — analyze all STEP files and cache results.

Scans directories for .STEP files, runs each through profile_builder,
writes individual JSON profiles, and generates a catalog index.
Idempotent: skips files that already have cached profiles.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .profile_builder import build_profile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FailureRecord:
    """A STEP file that failed analysis."""
    sku: str
    step_path: str
    error: str


@dataclass(frozen=True)
class BatchResult:
    """Summary of a batch profiling run."""
    profiled: int
    skipped: int
    failed: int
    index_path: str
    failures: tuple[FailureRecord, ...]


def extract_sku_from_filename(filename: str) -> str:
    """Extract SKU from a STEP filename.

    Examples: '1101-0001-0008.STEP' -> '1101-0001-0008'
    """
    name = Path(filename).stem
    return name


def _build_single_profile(
    step_path: str,
    sku: str,
    category: str,
) -> dict[str, Any]:
    """Build a profile for one STEP file. Separated for monkeypatching."""
    return build_profile(
        step_path=step_path,
        sku=sku,
        name=sku,  # use SKU as name — enrichment happens separately
        category=category,
    )


def build_index(profiles_dir: str) -> dict[str, Any]:
    """Build a catalog index from cached profile JSON files.

    Parameters
    ----------
    profiles_dir : str
        Directory containing individual profile JSON files.

    Returns
    -------
    dict
        Mapping of SKU to metadata (category, bounding_box, mass_grams, profile_path).
    """
    index: dict[str, Any] = {}
    profiles_path = Path(profiles_dir)

    for json_file in profiles_path.glob("*.json"):
        if json_file.name.startswith("_"):
            continue  # skip _index.json, _failures.json
        try:
            profile = json.loads(json_file.read_text(encoding="utf-8"))
            sku = profile.get("sku", json_file.stem)
            geometry = profile.get("geometry", {})
            index[sku] = {
                "category": profile.get("category", ""),
                "bounding_box": geometry.get("bounding_box", {}),
                "mass_grams": geometry.get("mass_grams", 0.0),
                "profile_path": str(json_file),
            }
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Skipping malformed profile %s: %s", json_file, exc)

    return index


def run_batch(
    step_dirs: tuple[str, ...],
    output_dir: str,
    sku_categories: dict[str, str],
) -> BatchResult:
    """Run batch profiling on all STEP files in the given directories.

    Parameters
    ----------
    step_dirs : tuple[str, ...]
        Directories to scan for .STEP files.
    output_dir : str
        Directory to write profile JSON files and index.
    sku_categories : dict[str, str]
        Maps SKU prefix (first 4 digits) to category string.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    profiled = 0
    skipped = 0
    failures: list[FailureRecord] = []

    # Collect all STEP files
    step_files: list[Path] = []
    for dir_str in step_dirs:
        dir_path = Path(dir_str)
        if dir_path.is_dir():
            step_files.extend(dir_path.glob("*.STEP"))
            step_files.extend(dir_path.glob("*.step"))

    for step_file in sorted(step_files):
        sku = extract_sku_from_filename(step_file.name)

        # Check if already cached
        cached_path = output_path / f"{sku}.json"
        if cached_path.exists():
            logger.debug("Skipping already cached: %s", sku)
            skipped += 1
            continue

        # Look up category from prefix
        prefix = sku.split("-")[0] if "-" in sku else sku[:4]
        category = sku_categories.get(prefix, "unknown")

        try:
            profile = _build_single_profile(
                step_path=str(step_file),
                sku=sku,
                category=category,
            )
            # Write profile directly as flat JSON (not in category subdirs)
            cached_path.write_text(
                json.dumps(profile, indent=2),
                encoding="utf-8",
            )
            profiled += 1
            logger.info("Profiled: %s (%d/%d)", sku, profiled, len(step_files))
        except Exception as exc:
            logger.warning("Failed to profile %s: %s", sku, exc)
            failures.append(FailureRecord(
                sku=sku,
                step_path=str(step_file),
                error=str(exc),
            ))

    # Build and write index
    index = build_index(str(output_path))
    index_path = output_path / "_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    # Write failures log
    if failures:
        failures_path = output_path / "_failures.json"
        failures_data = [
            {"sku": f.sku, "step_path": f.step_path, "error": f.error}
            for f in failures
        ]
        failures_path.write_text(json.dumps(failures_data, indent=2), encoding="utf-8")

    return BatchResult(
        profiled=profiled,
        skipped=skipped,
        failed=len(failures),
        index_path=str(index_path),
        failures=tuple(failures),
    )
