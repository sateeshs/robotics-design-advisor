"""SolidWorks COM connection lifecycle.

Connects to a running SolidWorks instance via COM automation.
Windows-only — raises RuntimeError on other platforms.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SolidWorksSession:
    """Active SolidWorks COM session."""

    app: Any  # COM application reference (SldWorks.ISldWorks)
    active_doc: Any  # Current active document or None


def _get_com_application() -> Any:
    """Get or create a COM connection to SolidWorks.

    Raises
    ------
    RuntimeError
        If not running on Windows.
    ConnectionError
        If SolidWorks is not running or COM connection fails.
    """
    if sys.platform != "win32":
        raise RuntimeError(
            "SolidWorks COM automation requires Windows. "
            "Current platform: " + sys.platform
        )

    try:
        import win32com.client  # type: ignore[import-untyped]

        app = win32com.client.Dispatch("SldWorks.Application")
        if app is None:
            raise ConnectionError("SolidWorks COM returned None — is SolidWorks running?")
        app.Visible = True
        logger.info("Connected to SolidWorks via COM")
        return app
    except Exception as exc:
        raise ConnectionError(f"Failed to connect to SolidWorks: {exc}") from exc


def connect() -> SolidWorksSession:
    """Connect to a running SolidWorks instance.

    Raises
    ------
    ConnectionError
        If SolidWorks is not running or COM fails.
    """
    app = _get_com_application()
    return SolidWorksSession(app=app, active_doc=None)


def disconnect(session: SolidWorksSession) -> None:
    """Release COM references. Safe to call multiple times."""
    logger.info("Disconnected from SolidWorks")
