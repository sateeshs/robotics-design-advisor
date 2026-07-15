"""SKU → STEP file path resolver.

Maps goBILDA SKU strings (e.g. "1120-0001-0288") to absolute file paths
on the Windows machine where STEP files are stored.

Pure logic — no filesystem access.  The resolver builds paths from a
category map and base directory; actual file existence is verified by
the SolidWorks MCP server at insertion time.
"""

from __future__ import annotations

import re


class SkuNotFoundError(Exception):
    """Raised when a SKU cannot be mapped to a known category."""


# SKU format: digits and hyphens only, no path separators or special chars
_VALID_SKU_RE = re.compile(r"^[A-Za-z0-9\-]+$")


class SkuResolver:
    """Resolve part SKUs to file system paths.

    Parameters
    ----------
    base_path : str
        Root directory containing category subdirectories
        (e.g. ``C:\\goBILDA`` or ``/home/user/parts``).
    category_map : dict[str, str]
        Maps SKU prefix (first 4 digits) to subdirectory name.
        Example: ``{"1120": "channel", "5202": "motors"}``.
    extension : str
        File extension including dot (default ``.step``).
    profiles_dir : str
        Directory containing cached profile JSON files (optional).
        If provided, resolve_with_profile() will load profiles from here.
    """

    def __init__(
        self,
        base_path: str,
        category_map: dict[str, str],
        extension: str = ".step",
        profiles_dir: str = "",
    ) -> None:
        self._base_path = base_path.rstrip("/\\")
        self._category_map = dict(category_map)
        self._extension = extension
        self._profiles_dir = profiles_dir

        # Detect path separator from base_path
        self._sep = "\\" if "\\" in base_path else "/"

    def resolve(self, sku: str) -> str:
        """Resolve a SKU to its full file path.

        Raises
        ------
        ValueError
            If the SKU is empty or contains invalid characters.
        SkuNotFoundError
            If the SKU prefix is not in the category map.
        """
        if not sku:
            raise ValueError("SKU must not be empty")

        if not _VALID_SKU_RE.match(sku) or "\x00" in sku:
            raise ValueError(f"Invalid SKU format: '{sku}'")

        if len(sku) < 4:
            raise ValueError(f"SKU too short: '{sku}'")

        category = self._lookup_category(sku)
        if category is None:
            raise SkuNotFoundError(
                f"No category found for SKU '{sku}'. "
                f"Known prefixes: {sorted(self._category_map.keys())}"
            )

        return f"{self._base_path}{self._sep}{category}{self._sep}{sku}{self._extension}"

    def get_category(self, sku: str) -> str | None:
        """Return the category for a SKU, or None if unknown."""
        if not sku:
            return None
        return self._lookup_category(sku)

    def list_categories(self) -> list[str]:
        """Return sorted unique category names."""
        return sorted(set(self._category_map.values()))

    def _lookup_category(self, sku: str) -> str | None:
        """Extract SKU prefix and look up category."""
        prefix = sku.split("-")[0] if "-" in sku else sku[:4]
        return self._category_map.get(prefix)

    def resolve_with_profile(self, sku: str) -> tuple[str, dict | None]:
        """Resolve a SKU to its file path and cached profile.

        Returns
        -------
        tuple[str, dict | None]
            (step_file_path, profile_dict) where profile is None
            if no cached profile exists for this SKU.

        Raises
        ------
        ValueError
            If the SKU is empty or has invalid format.
        SkuNotFoundError
            If the SKU prefix is not in the category map.
        """
        path = self.resolve(sku)
        profile = self._load_cached_profile(sku)
        return (path, profile)

    def _load_cached_profile(self, sku: str) -> dict | None:
        """Load a cached profile JSON for a SKU, or return None."""
        if not self._profiles_dir:
            return None
        import json
        from pathlib import Path
        profile_path = Path(self._profiles_dir) / f"{sku}.json"
        if not profile_path.exists():
            return None
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
