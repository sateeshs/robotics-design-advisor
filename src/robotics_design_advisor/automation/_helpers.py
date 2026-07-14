"""Shared helpers for automation mixins."""

from __future__ import annotations

from typing import Any

SW_DOC_ASSEMBLY = 2


def get_assembly_doc(host: Any) -> tuple[Any | None, dict | None]:
    """Return the active doc if it is an assembly, else an error dict.

    Parameters
    ----------
    host : object
        Mixin host with ``_sw_app`` and ``_result()`` attributes.
    """
    doc = host._sw_app.ActiveDoc
    if doc is None:
        return None, host._result(False, "No document open", error_code=1)
    if doc.GetType() != SW_DOC_ASSEMBLY:
        return None, host._result(
            False,
            "Active document is not an assembly. Open or create an assembly first.",
            error_code=2,
        )
    return doc, None
