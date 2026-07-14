"""MCP Server -- exposes tools to external MCP clients.

Handles initialize, tools/list, tools/call, and ping requests over
transport (STDIO or HTTP/SSE).

Ported from freecad-ai (zero CAD dependency). Works with any ToolRegistry.
"""

import logging

from ..tools.registry import ToolRegistry
from . import protocol

logger = logging.getLogger(__name__)

SERVER_INFO = {"name": "Robotics Design Advisor", "version": "1.0.0"}
PROTOCOL_VERSION = "2025-03-26"


class MCPServer:
    """Exposes a ToolRegistry as an MCP server."""

    def __init__(
        self,
        registry: ToolRegistry,
        transport=None,
        server_info: dict | None = None,
    ) -> None:
        self._registry = registry
        self._transport = transport
        self._server_info = server_info or SERVER_INFO

    def run(self) -> None:
        """Start the server (blocking)."""
        if self._transport is None:
            from .transport import StdioServerTransport
            self._transport = StdioServerTransport()
        logger.info(
            "MCP server starting with %d tools",
            len(self._registry.list_tools()),
        )
        self._transport.run(self._handle)

    def _handle(self, msg: dict) -> dict | None:
        """Route a JSON-RPC message to the appropriate handler."""
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            return protocol.make_response(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": self._server_info,
            })

        if method == "notifications/initialized":
            return None  # Notification, no response

        if method == "tools/list":
            return protocol.make_response(msg_id, {
                "tools": self._registry.to_mcp_schema(),
            })

        if method == "tools/call":
            return self._handle_tool_call(msg_id, params)

        if method == "ping":
            return protocol.make_response(msg_id, {})

        # Unknown method
        if msg_id is not None:
            return protocol.make_error(
                msg_id, protocol.METHOD_NOT_FOUND,
                f"Method not found: {method}",
            )
        return None  # Unknown notification, ignore

    def _handle_tool_call(self, msg_id, params: dict) -> dict:
        """Execute a tool and return the result in MCP format."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        result = self._registry.execute(tool_name, arguments)

        if result.success:
            content = [{"type": "text", "text": result.output}]
            if result.data:
                content.append({"type": "text", "text": str(result.data)})
            return protocol.make_response(msg_id, {
                "content": content,
                "isError": False,
            })
        else:
            return protocol.make_response(msg_id, {
                "content": [{"type": "text", "text": result.error or "Unknown error"}],
                "isError": True,
            })
