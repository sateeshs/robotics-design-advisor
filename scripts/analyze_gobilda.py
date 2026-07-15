#!/usr/bin/env python
"""Batch-process goBILDA STEP files into JSON part profiles.

Usage:
    python scripts/analyze_gobilda.py \
        --input-dir /path/to/STEP/files \
        --output-dir ./profiles/gobilda \
        --workers 4
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Add src to path for script execution
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from robotics_design_advisor.step.profile_builder import build_profile, write_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("analyze-gobilda")

# SKU pattern: digits and hyphens (e.g., 1101-0001-0008)
_SKU_RE = re.compile(r"^(\d{4}-\d{4}-\d{4})")

# Default SKU category map location
_DEFAULT_SKU_MAP = Path(__file__).resolve().parent.parent / "src" / "robotics_design_advisor" / "step" / "sku_categories.json"


def _extract_sku(filename: str) -> str | None:
    """Extract SKU from a filename like '1101-0001-0008.STEP'."""
    match = _SKU_RE.match(filename)
    return match.group(1) if match else None


def _load_sku_map(path: Path) -> dict[str, str]:
    """Load SKU prefix → category mapping."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve_category(sku: str, sku_map: dict[str, str]) -> str:
    """Look up category for a SKU prefix."""
    prefix = sku.split("-")[0] if "-" in sku else sku[:4]
    return sku_map.get(prefix, "uncategorized")


def _make_name(sku: str, category: str) -> str:
    """Generate a human-readable name from SKU and category."""
    cat_parts = category.split("/")
    part_type = cat_parts[-1].replace("_", " ").title() if cat_parts else "Part"
    return f"{part_type} {sku}"


def _process_one(
    step_path: str,
    sku: str,
    name: str,
    category: str,
    output_dir: str,
) -> tuple[str, bool, str]:
    """Process a single STEP file. Returns (sku, success, message)."""
    try:
        profile = build_profile(
            step_path=step_path,
            sku=sku,
            name=name,
            category=category,
        )
        write_profile(profile, output_dir)
        return sku, True, "ok"
    except Exception as e:
        return sku, False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-process goBILDA STEP files")
    parser.add_argument("--input-dir", required=True, help="Directory containing .STEP files")
    parser.add_argument("--output-dir", required=True, help="Output directory for JSON profiles")
    parser.add_argument("--sku-map", default=str(_DEFAULT_SKU_MAP), help="SKU category map JSON")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (default 1)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    sku_map = _load_sku_map(Path(args.sku_map))
    logger.info("Loaded %d SKU prefix mappings", len(sku_map))

    # Find all STEP files
    step_files: list[tuple[Path, str]] = []
    for ext in ("*.STEP", "*.step", "*.stp", "*.STP"):
        for p in sorted(input_dir.glob(ext)):
            sku = _extract_sku(p.stem)
            if sku:
                step_files.append((p, sku))
            else:
                logger.warning("Skipping non-SKU filename: %s", p.name)

    logger.info("Found %d STEP files to process", len(step_files))

    if not step_files:
        logger.warning("No STEP files found in %s", input_dir)
        return

    # Process
    start = time.monotonic()
    success_count = 0
    fail_count = 0

    if args.workers <= 1:
        # Sequential processing
        for i, (path, sku) in enumerate(step_files, 1):
            category = _resolve_category(sku, sku_map)
            name = _make_name(sku, category)
            sku_result, ok, msg = _process_one(
                str(path), sku, name, category, args.output_dir
            )
            if ok:
                success_count += 1
            else:
                fail_count += 1
                logger.warning("FAILED %s: %s", sku_result, msg)

            if i % 10 == 0 or i == len(step_files):
                elapsed = time.monotonic() - start
                logger.info("Progress: %d/%d (%.1fs)", i, len(step_files), elapsed)
    else:
        # Parallel processing
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for path, sku in step_files:
                category = _resolve_category(sku, sku_map)
                name = _make_name(sku, category)
                fut = executor.submit(
                    _process_one, str(path), sku, name, category, args.output_dir
                )
                futures[fut] = sku

            done = 0
            for fut in as_completed(futures):
                done += 1
                sku_result, ok, msg = fut.result()
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    logger.warning("FAILED %s: %s", sku_result, msg)

                if done % 10 == 0 or done == len(step_files):
                    elapsed = time.monotonic() - start
                    logger.info("Progress: %d/%d (%.1fs)", done, len(step_files), elapsed)

    elapsed = time.monotonic() - start
    logger.info(
        "Done: %d success, %d failed out of %d in %.1fs",
        success_count, fail_count, len(step_files), elapsed,
    )


if __name__ == "__main__":
    main()
