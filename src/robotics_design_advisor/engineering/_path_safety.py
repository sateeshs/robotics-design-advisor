"""Path safety utilities for file loading functions.

Prevents path traversal attacks by ensuring resolved paths stay
within the intended base directory.
"""

from __future__ import annotations

from pathlib import Path


def safe_resolve(base_dir: Path, user_provided: str) -> Path:
    """Resolve a path and verify it stays inside base_dir.

    Raises
    ------
    ValueError
        If the resolved path escapes the base directory.
    """
    resolved = (base_dir / user_provided).resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal detected: '{user_provided}' escapes the allowed directory"
        ) from None
    return resolved
