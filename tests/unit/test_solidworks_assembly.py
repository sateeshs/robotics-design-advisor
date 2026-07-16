"""Tests for SolidWorks COM adapter — all COM calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from robotics_design_advisor.solidworks.assembly import (
    AssemblyDoc,
    ComponentRef,
    MateRef,
    add_mate,
    create_assembly,
    insert_component,
    list_components,
    save_assembly,
)
from robotics_design_advisor.solidworks.connection import (
    SolidWorksSession,
    connect,
    disconnect,
)
from robotics_design_advisor.solidworks.placement import Position


def _make_mock_session() -> SolidWorksSession:
    """Create a SolidWorksSession with a mock COM object."""
    mock_app = MagicMock()
    return SolidWorksSession(app=mock_app, active_doc=None)


class TestSolidWorksSession:
    def test_creation(self):
        session = _make_mock_session()
        assert session.app is not None
        assert session.active_doc is None

    def test_frozen(self):
        session = _make_mock_session()
        with pytest.raises(AttributeError):
            session.active_doc = "changed"  # type: ignore[misc]


class TestConnect:
    @patch("robotics_design_advisor.solidworks.connection._get_com_application")
    def test_connect_returns_session(self, mock_get_com):
        mock_get_com.return_value = MagicMock()
        session = connect()
        assert isinstance(session, SolidWorksSession)

    @patch("robotics_design_advisor.solidworks.connection._get_com_application")
    def test_connect_failure_raises(self, mock_get_com):
        mock_get_com.side_effect = ConnectionError("SolidWorks not running")
        with pytest.raises(ConnectionError):
            connect()


class TestDisconnect:
    def test_disconnect_does_not_raise(self):
        session = _make_mock_session()
        disconnect(session)  # should not raise


class TestCreateAssembly:
    def test_returns_assembly_doc(self):
        session = _make_mock_session()
        mock_doc = MagicMock()
        session.app.NewDocument.return_value = mock_doc

        asm = create_assembly(session, "test_robot", "/tmp/test_robot.SLDASM")
        assert isinstance(asm, AssemblyDoc)
        assert asm.name == "test_robot"
        assert asm.save_path == "/tmp/test_robot.SLDASM"


class TestInsertComponent:
    def test_returns_component_ref(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        pos = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)

        mock_comp = MagicMock()
        asm.com_ref.AddComponent5.return_value = mock_comp

        ref = insert_component(session, asm, "/parts/motor.STEP", pos)
        assert isinstance(ref, ComponentRef)
        assert ref.step_path == "/parts/motor.STEP"
        assert ref.position == pos

    def test_extracts_sku_from_path(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        pos = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)

        asm.com_ref.AddComponent5.return_value = MagicMock()

        ref = insert_component(session, asm, "/parts/5202-0002-0019.STEP", pos)
        assert ref.sku == "5202-0002-0019"


class TestAddMate:
    def test_returns_mate_ref(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        comp_a = ComponentRef(
            name="motor_1", step_path="/a.STEP", sku="A",
            position=Position(0, 0, 0, 0, 0, 0), com_ref=MagicMock(),
        )
        comp_b = ComponentRef(
            name="bracket_1", step_path="/b.STEP", sku="B",
            position=Position(0, 0, 0, 0, 0, 0), com_ref=MagicMock(),
        )

        mate = add_mate(session, asm, comp_a, comp_b, "coincident", 0.0)
        assert isinstance(mate, MateRef)
        assert mate.mate_type == "coincident"
        assert mate.component_a_name == "motor_1"
        assert mate.component_b_name == "bracket_1"

    def test_invalid_mate_type_raises(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        comp = ComponentRef(
            name="x", step_path="/x.STEP", sku="X",
            position=Position(0, 0, 0, 0, 0, 0), com_ref=MagicMock(),
        )
        with pytest.raises(ValueError, match="mate_type"):
            add_mate(session, asm, comp, comp, "glue", 0.0)


class TestListComponents:
    def test_returns_empty_tuple_initially(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        asm.com_ref.GetComponents.return_value = []
        result = list_components(session, asm)
        assert result == ()


class TestSaveAssembly:
    def test_calls_save(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        save_assembly(session, asm)
        asm.com_ref.Save.assert_called_once()
