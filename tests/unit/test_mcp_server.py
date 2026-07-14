"""Tests for the MCP server handler."""

import pytest

from robotics_design_advisor.mcp.server import MCPServer
from robotics_design_advisor.mcp import protocol
from robotics_design_advisor.tools.registry import (
    ToolDefinition,
    ToolParam,
    ToolRegistry,
    ToolResult,
)


def _make_registry_with_tool() -> ToolRegistry:
    """Create a registry with a single echo tool."""
    registry = ToolRegistry()

    def echo_handler(message: str) -> ToolResult:
        return ToolResult(success=True, output=f"Echo: {message}", data={"message": message})

    registry.register(ToolDefinition(
        name="echo",
        description="Echo a message back",
        parameters=[ToolParam("message", "string", "The message to echo")],
        handler=echo_handler,
    ))
    return registry


class TestMCPServerHandle:
    def test_initialize(self):
        server = MCPServer(registry=ToolRegistry())

        response = server._handle(protocol.make_request("initialize", id=1))

        assert response["id"] == 1
        assert "protocolVersion" in response["result"]
        assert "serverInfo" in response["result"]
        assert "capabilities" in response["result"]

    def test_tools_list(self):
        registry = _make_registry_with_tool()
        server = MCPServer(registry=registry)

        response = server._handle(protocol.make_request("tools/list", id=2))

        assert response["id"] == 2
        tools = response["result"]["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "echo"

    def test_tools_call_success(self):
        registry = _make_registry_with_tool()
        server = MCPServer(registry=registry)

        response = server._handle(protocol.make_request(
            "tools/call",
            {"name": "echo", "arguments": {"message": "hello"}},
            id=3,
        ))

        assert response["id"] == 3
        assert response["result"]["isError"] is False
        assert "Echo: hello" in response["result"]["content"][0]["text"]

    def test_tools_call_unknown_tool(self):
        server = MCPServer(registry=ToolRegistry())

        response = server._handle(protocol.make_request(
            "tools/call",
            {"name": "nonexistent", "arguments": {}},
            id=4,
        ))

        assert response["result"]["isError"] is True
        assert "Unknown tool" in response["result"]["content"][0]["text"]

    def test_ping(self):
        server = MCPServer(registry=ToolRegistry())

        response = server._handle(protocol.make_request("ping", id=5))

        assert response["id"] == 5
        assert response["result"] == {}

    def test_unknown_method(self):
        server = MCPServer(registry=ToolRegistry())

        response = server._handle(protocol.make_request("unknown/method", id=6))

        assert response["error"]["code"] == protocol.METHOD_NOT_FOUND

    def test_notification_returns_none(self):
        server = MCPServer(registry=ToolRegistry())

        response = server._handle(
            protocol.make_notification("notifications/initialized")
        )

        assert response is None

    def test_custom_server_info(self):
        info = {"name": "Custom", "version": "9.9.9"}
        server = MCPServer(registry=ToolRegistry(), server_info=info)

        response = server._handle(protocol.make_request("initialize", id=1))

        assert response["result"]["serverInfo"]["name"] == "Custom"
        assert response["result"]["serverInfo"]["version"] == "9.9.9"
