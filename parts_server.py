"""Parts Intelligence MCP Server.

A STDIO MCP server that exposes goBILDA part search, profile lookup,
compatibility filtering, and smart mate suggestions as tools callable
by Claude Code.

Usage:
    python parts_server.py --profiles-dir ./profiles/gobilda

Claude Code config (~/.claude/mcp_servers.json):
    {
      "parts-intelligence": {
        "type": "stdio",
        "command": "python",
        "args": ["/path/to/parts_server.py", "--profiles-dir", "/path/to/profiles"]
      }
    }
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from robotics_design_advisor.parts.models import (
    CatalogEntry,
    CategorySummary,
    MateSuggestion,
    PartProfile,
)
from robotics_design_advisor.parts.query import PartsCatalog, ProfileNotFoundError
from robotics_design_advisor.parts.smart_mate import suggest_mates as _suggest_mates

# ---------------------------------------------------------------------------
# Logging — stderr only, never stdout (STDIO transport uses stdout)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("parts-intelligence")

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP("parts-intelligence")

# Catalog is initialized at startup in main()
_catalog: PartsCatalog | None = None


def _get_catalog() -> PartsCatalog:
    """Return the loaded catalog or raise."""
    if _catalog is None:
        raise RuntimeError("Catalog not loaded — server not initialized")
    return _catalog


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _entry_to_dict(entry: CatalogEntry) -> dict:
    """Convert a CatalogEntry to a JSON-serializable dict."""
    return dataclasses.asdict(entry)


def _profile_to_dict(profile: PartProfile) -> dict:
    """Convert a PartProfile to a JSON-serializable dict."""
    return dataclasses.asdict(profile)


def _category_to_dict(cat: CategorySummary) -> dict:
    """Convert a CategorySummary to a JSON-serializable dict."""
    return dataclasses.asdict(cat)


def _suggestion_to_dict(s: MateSuggestion) -> dict:
    """Convert a MateSuggestion to a JSON-serializable dict."""
    return dataclasses.asdict(s)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_parts(
    query: str = "",
    category: str = "",
    min_length_mm: float = 0.0,
    max_length_mm: float = 0.0,
    max_results: int = 20,
) -> list[dict]:
    """Search goBILDA parts by keyword, category, and size.

    Args:
        query: Free-text search against SKU and name (case-insensitive).
               Supports multi-word queries — all terms must match.
        category: Filter to a specific category (e.g. "structure/channel",
                  "motion/motor"). Use list_categories() to see all options.
        min_length_mm: Minimum longest dimension in mm (0 = no minimum).
        max_length_mm: Maximum longest dimension in mm (0 = no maximum).
        max_results: Maximum number of results to return (default 20).
    """
    catalog = _get_catalog()
    results = catalog.search(
        query=query,
        category=category or None,
        min_length_mm=min_length_mm if min_length_mm > 0 else None,
        max_length_mm=max_length_mm if max_length_mm > 0 else None,
        max_results=max_results,
    )
    return [_entry_to_dict(e) for e in results]


@mcp.tool()
def get_part_profile(sku: str) -> dict:
    """Get the full engineering profile for a specific part by SKU.

    Returns detailed geometry, mounting faces, hole patterns, connection
    points, and compatibility tags. Use search_parts() first to find SKUs.

    Args:
        sku: The goBILDA part SKU (e.g. "1120-0001-0288").
    """
    catalog = _get_catalog()
    try:
        profile = catalog.get_profile(sku)
    except ProfileNotFoundError as exc:
        return {"error": str(exc)}
    return _profile_to_dict(profile)


@mcp.tool()
def find_compatible_parts(
    tag: str,
    category: str = "",
    max_results: int = 20,
) -> list[dict]:
    """Find parts that are compatible with a specific connection type.

    Args:
        tag: Compatibility tag to search for. Common tags:
             - "gobilda_8mm_pattern" — standard 8mm-pitch hole grid
             - "M4_bolt" — M4 bolt-compatible holes
             - "REX_8mm_shaft" — REX 8mm shaft bore
             - "yellow_jacket_mount" — Yellow Jacket motor mount pattern
        category: Optional category filter (e.g. "motion/wheel").
        max_results: Maximum number of results (default 20).
    """
    catalog = _get_catalog()
    results = catalog.find_compatible(
        tag=tag,
        category=category or None,
        max_results=max_results,
    )
    return [_entry_to_dict(e) for e in results]


@mcp.tool()
def list_categories() -> list[dict]:
    """List all available part categories with part counts.

    Returns category names (e.g. "structure/channel", "motion/motor")
    and how many parts are in each. Use these category names as filters
    in search_parts() and find_compatible_parts().
    """
    catalog = _get_catalog()
    categories = catalog.list_categories()
    return [_category_to_dict(c) for c in categories]


@mcp.tool()
def suggest_mates(sku_a: str, sku_b: str) -> list[dict] | dict:
    """Suggest SolidWorks mate constraints between two parts.

    Analyzes connection points and compatibility tags from both part
    profiles to suggest valid mate types (coincident, concentric,
    distance) with confidence scores and rationale.

    Args:
        sku_a: First part SKU (e.g. "1120-0001-0288").
        sku_b: Second part SKU (e.g. "2900-0005-0002").
    """
    catalog = _get_catalog()
    try:
        profile_a = catalog.get_profile(sku_a)
    except ProfileNotFoundError as exc:
        return {"error": str(exc)}
    try:
        profile_b = catalog.get_profile(sku_b)
    except ProfileNotFoundError as exc:
        return {"error": str(exc)}

    suggestions = _suggest_mates(profile_a, profile_b)
    return [_suggestion_to_dict(s) for s in suggestions]


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI args, load catalog, and run the MCP server."""
    parser = argparse.ArgumentParser(
        description="Parts Intelligence MCP Server",
    )
    parser.add_argument(
        "--profiles-dir",
        type=str,
        default=str(Path(__file__).parent / "profiles" / "gobilda"),
        help="Path to the directory containing part profile JSON files",
    )
    args = parser.parse_args()

    profiles_path = Path(args.profiles_dir)
    logger.info("Loading catalog from: %s", profiles_path)

    global _catalog  # noqa: PLW0603
    _catalog = PartsCatalog(profiles_path)
    logger.info(
        "Catalog ready: %d parts across %d categories",
        _catalog.part_count,
        len(_catalog.list_categories()),
    )

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
