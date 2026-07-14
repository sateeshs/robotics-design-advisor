"""Tests for assembly operations mixin (Phase 2E.2).

All SolidWorks COM calls are mocked — these tests run on Linux.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from robotics_design_advisor.automation.assemblies import (
    AssemblyOperations,
    MateType,
)


# ---------------------------------------------------------------------------
# Fixtures: mock COM objects
# ---------------------------------------------------------------------------

class MockAssemblyHost(AssemblyOperations):
    """Minimal host that satisfies the mixin's requirements."""

    def __init__(self):
        self._sw_app = MagicMock()
        self._connected = True

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _result(self, success, message, error_code=0, data=None):
        result = {"success": success, "message": message, "error_code": error_code}
        if data is not None:
            result["data"] = data
        return result


@pytest.fixture()
def host():
    h = MockAssemblyHost()
    # Set up a mock active doc that looks like an assembly
    doc = MagicMock()
    doc.GetType.return_value = 2  # swDocASSEMBLY = 2
    h._sw_app.ActiveDoc = doc
    return h


@pytest.fixture()
def mock_component():
    comp = MagicMock()
    comp.Name2 = "channel-1"
    comp.GetPathName.return_value = r"C:\goBILDA\channel\1120-0001-0288.step"
    comp.IsSuppressed.return_value = False

    transform = MagicMock()
    transform.ArrayData = (
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0.1, 0.2, 0.3, 1,
    )
    comp.Transform2 = transform
    return comp


# ---------------------------------------------------------------------------
# insert_component
# ---------------------------------------------------------------------------

class TestInsertComponent:
    def test_returns_success(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        inserted = MagicMock()
        inserted.Name2 = "part-1"
        doc.AddComponent5.return_value = inserted

        result = host.insert_component(r"C:\Parts\test.step", (0, 0, 0))
        assert result["success"] is True

    def test_passes_filepath_to_com(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        inserted = MagicMock()
        inserted.Name2 = "part-1"
        doc.AddComponent5.return_value = inserted

        host.insert_component(r"C:\Parts\test.step", (0, 0, 0))
        doc.AddComponent5.assert_called_once()
        call_args = doc.AddComponent5.call_args
        assert call_args[0][0] == r"C:\Parts\test.step"

    def test_position_passed_as_meters(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        inserted = MagicMock()
        inserted.Name2 = "part-1"
        doc.AddComponent5.return_value = inserted

        host.insert_component(r"C:\Parts\test.step", (100.0, 50.0, 200.0))
        call_args = doc.AddComponent5.call_args[0]
        # Position args are in meters (mm / 1000)
        assert abs(call_args[1] - 0.1) < 0.001
        assert abs(call_args[2] - 0.05) < 0.001
        assert abs(call_args[3] - 0.2) < 0.001

    def test_returns_component_name_in_data(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        inserted = MagicMock()
        inserted.Name2 = "channel-1"
        doc.AddComponent5.return_value = inserted

        result = host.insert_component(r"C:\Parts\test.step", (0, 0, 0))
        assert result["data"]["component_name"] == "channel-1"

    def test_failure_when_add_returns_none(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        doc.AddComponent5.return_value = None

        result = host.insert_component(r"C:\Parts\test.step", (0, 0, 0))
        assert result["success"] is False

    def test_not_assembly_returns_error(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        doc.GetType.return_value = 1  # swDocPART

        result = host.insert_component(r"C:\Parts\test.step", (0, 0, 0))
        assert result["success"] is False
        assert "assembly" in result["message"].lower()


# ---------------------------------------------------------------------------
# insert_library_part (SKU-based)
# ---------------------------------------------------------------------------

class TestInsertLibraryPart:
    def test_resolves_sku_and_inserts(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        inserted = MagicMock()
        inserted.Name2 = "1120-0001-0288-1"
        doc.AddComponent5.return_value = inserted

        result = host.insert_library_part(
            sku="1120-0001-0288",
            position=(0, 0, 0),
            resolver_base_path=r"C:\goBILDA",
            resolver_category_map={"1120": "channel"},
        )
        assert result["success"] is True
        assert result["data"]["sku"] == "1120-0001-0288"

    def test_sku_not_found_returns_error(self, host) -> None:
        result = host.insert_library_part(
            sku="9999-0001-0001",
            position=(0, 0, 0),
            resolver_base_path=r"C:\goBILDA",
            resolver_category_map={"1120": "channel"},
        )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# add_mate
# ---------------------------------------------------------------------------

class TestAddMate:
    def test_coincident_mate(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        mate_feature = MagicMock()
        doc.AddMate3.return_value = mate_feature

        result = host.add_mate(
            mate_type=MateType.COINCIDENT,
            entity1="face1@channel-1",
            entity2="face2@channel-2",
        )
        assert result["success"] is True

    def test_distance_mate_with_value(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        mate_feature = MagicMock()
        doc.AddMate3.return_value = mate_feature

        result = host.add_mate(
            mate_type=MateType.DISTANCE,
            entity1="face1@channel-1",
            entity2="face2@channel-2",
            value_mm=10.0,
        )
        assert result["success"] is True

    def test_mate_failure_returns_error(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        doc.AddMate3.return_value = None

        result = host.add_mate(
            mate_type=MateType.COINCIDENT,
            entity1="face1@channel-1",
            entity2="face2@channel-2",
        )
        assert result["success"] is False

    def test_not_assembly_returns_error(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        doc.GetType.return_value = 1

        result = host.add_mate(
            mate_type=MateType.COINCIDENT,
            entity1="face1",
            entity2="face2",
        )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_assembly_tree
# ---------------------------------------------------------------------------

class TestGetAssemblyTree:
    def test_returns_tree_dict(self, host, mock_component) -> None:
        doc = host._sw_app.ActiveDoc
        config = MagicMock()
        root = MagicMock()
        root.GetChildren.return_value = [mock_component]
        config.GetRootComponent3.return_value = root
        doc.GetActiveConfiguration.return_value = config

        result = host.get_assembly_tree()
        assert result["success"] is True
        assert "components" in result["data"]
        assert len(result["data"]["components"]) == 1

    def test_component_has_name_and_path(self, host, mock_component) -> None:
        doc = host._sw_app.ActiveDoc
        config = MagicMock()
        root = MagicMock()
        root.GetChildren.return_value = [mock_component]
        config.GetRootComponent3.return_value = root
        doc.GetActiveConfiguration.return_value = config

        result = host.get_assembly_tree()
        comp = result["data"]["components"][0]
        assert comp["name"] == "channel-1"
        assert "1120-0001-0288" in comp["path"]

    def test_empty_assembly(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        config = MagicMock()
        root = MagicMock()
        root.GetChildren.return_value = []
        config.GetRootComponent3.return_value = root
        doc.GetActiveConfiguration.return_value = config

        result = host.get_assembly_tree()
        assert result["data"]["components"] == []


# ---------------------------------------------------------------------------
# list_mates
# ---------------------------------------------------------------------------

class TestListMates:
    def test_returns_mate_list(self, host) -> None:
        doc = host._sw_app.ActiveDoc
        mate = MagicMock()
        mate.Name = "Coincident1"
        mate.Type = 0  # coincident
        mate.GetMateEntityCount.return_value = 2

        entity1 = MagicMock()
        entity1.ReferenceComponent.Name2 = "channel-1"
        entity2 = MagicMock()
        entity2.ReferenceComponent.Name2 = "channel-2"
        mate.MateEntity.side_effect = [entity1, entity2]

        doc.GetMateCount.return_value = 1
        doc.GetMates.return_value = [mate]

        result = host.list_mates()
        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert result["data"]["mates"][0]["entities"] == ["channel-1", "channel-2"]
