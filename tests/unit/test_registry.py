"""Tests for the tool registry (ported from freecad-ai)."""

import pytest

from robotics_design_advisor.tools.registry import (
    ToolDefinition,
    ToolParam,
    ToolRegistry,
    ToolResult,
)


def _make_echo_handler(**kwargs) -> ToolResult:
    """Simple handler that echoes params back."""
    return ToolResult(success=True, output="ok", data=kwargs)


def _make_tool(name: str = "test_tool", **kwargs) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=kwargs.get("description", f"Test tool {name}"),
        parameters=kwargs.get("parameters", [
            ToolParam("value", "string", "A test value"),
        ]),
        handler=kwargs.get("handler", _make_echo_handler),
        category=kwargs.get("category", "test"),
    )


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = _make_tool("my_tool")
        registry.register(tool)

        result = registry.get("my_tool")

        assert result is not None
        assert result.name == "my_tool"

    def test_get_missing_returns_none(self):
        registry = ToolRegistry()

        assert registry.get("nonexistent") is None

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a"))
        registry.register(_make_tool("tool_b"))

        tools = registry.list_tools()

        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"tool_a", "tool_b"}

    def test_search_by_name(self):
        registry = ToolRegistry()
        registry.register(_make_tool("search_parts"))
        registry.register(_make_tool("get_profile"))

        results = registry.search_tools("search")

        assert len(results) == 1
        assert results[0].name == "search_parts"

    def test_search_by_description(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a", description="Find goBILDA parts"))
        registry.register(_make_tool("tool_b", description="Extrude a shape"))

        results = registry.search_tools("gobilda")

        assert len(results) == 1
        assert results[0].name == "tool_a"

    def test_search_case_insensitive(self):
        registry = ToolRegistry()
        registry.register(_make_tool("Search_Parts"))

        results = registry.search_tools("SEARCH")

        assert len(results) == 1

    def test_execute_success(self):
        registry = ToolRegistry()
        registry.register(_make_tool("echo"))

        result = registry.execute("echo", {"value": "hello"})

        assert result.success
        assert result.data == {"value": "hello"}

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()

        result = registry.execute("nonexistent", {})

        assert not result.success
        assert "Unknown tool" in result.error

    def test_execute_invalid_params(self):
        def strict_handler(required_param: str) -> ToolResult:
            return ToolResult(success=True, output=required_param)

        registry = ToolRegistry()
        registry.register(_make_tool("strict", handler=strict_handler))

        result = registry.execute("strict", {"wrong_param": "value"})

        assert not result.success
        assert "Invalid parameters" in result.error

    def test_execute_handler_exception(self):
        def failing_handler(**kwargs) -> ToolResult:
            raise RuntimeError("Boom")

        registry = ToolRegistry()
        registry.register(_make_tool("failing", handler=failing_handler))

        result = registry.execute("failing", {})

        assert not result.success
        assert "Boom" in result.error


class TestToolDefinitionLazyParams:
    def test_deferred_params(self):
        call_count = 0

        def lazy_loader():
            nonlocal call_count
            call_count += 1
            return [ToolParam("lazy_val", "string", "Lazily loaded")]

        tool = ToolDefinition(
            name="lazy_tool",
            description="Has lazy params",
            parameters=[],
            handler=_make_echo_handler,
            lazy_params=lazy_loader,
        )

        assert tool.has_deferred_params
        assert call_count == 0

        resolved = tool.resolve_params()

        assert len(resolved) == 1
        assert resolved[0].name == "lazy_val"
        assert call_count == 1
        assert not tool.has_deferred_params

        # Second call should not re-invoke loader
        tool.resolve_params()
        assert call_count == 1


class TestSchemaGeneration:
    def test_to_mcp_schema(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a", parameters=[
            ToolParam("query", "string", "Search query"),
            ToolParam("limit", "integer", "Max results", required=False, default=20),
        ]))

        schema = registry.to_mcp_schema()

        assert len(schema) == 1
        assert schema[0]["name"] == "tool_a"
        props = schema[0]["inputSchema"]["properties"]
        assert "query" in props
        assert "limit" in props
        assert props["limit"]["default"] == 20
        assert schema[0]["inputSchema"]["required"] == ["query"]

    def test_to_openai_schema(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a"))

        schema = registry.to_openai_schema()

        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "tool_a"

    def test_to_anthropic_schema(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a"))

        schema = registry.to_anthropic_schema()

        assert len(schema) == 1
        assert schema[0]["name"] == "tool_a"
        assert "input_schema" in schema[0]

    def test_filter_names(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a"))
        registry.register(_make_tool("tool_b"))
        registry.register(_make_tool("tool_c"))

        schema = registry.to_mcp_schema(filter_names={"tool_a", "tool_c"})

        assert len(schema) == 2
        names = {s["name"] for s in schema}
        assert names == {"tool_a", "tool_c"}
