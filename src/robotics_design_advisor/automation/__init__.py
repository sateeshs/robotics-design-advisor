"""Automation package — SolidWorks COM operation mixins.

These mixins are designed to be mixed into a host class that provides:
- self._sw_app: SolidWorks COM application object
- self.is_connected: bool property
- self._result(success, message, error_code=0, data=None): result factory

Usage
-----
On the Windows SolidWorks MCP server, combine these mixins with the
existing ``SolidWorksAutomation`` base class::

    from robotics_design_advisor.automation.assemblies import AssemblyOperations
    from robotics_design_advisor.automation.patterns import PatternOperations

    class SolidWorksAutomation(BaseAutomation, DocumentOperations,
                               SketchOperations, FeatureOperations,
                               AssemblyOperations, PatternOperations):
        pass
"""

from .assemblies import AssemblyOperations, MateType
from .patterns import PatternOperations

__all__ = [
    "AssemblyOperations",
    "MateType",
    "PatternOperations",
]
