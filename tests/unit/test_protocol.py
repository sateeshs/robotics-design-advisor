"""Tests for MCP JSON-RPC protocol helpers."""

import json

import pytest

from robotics_design_advisor.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    decode,
    encode,
    make_error,
    make_notification,
    make_request,
    make_response,
)


class TestEncode:
    def test_basic_encode(self):
        msg = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        encoded = encode(msg)

        assert isinstance(encoded, bytes)
        assert encoded.endswith(b"\n")
        decoded = json.loads(encoded)
        assert decoded == msg

    def test_compact_json(self):
        msg = {"key": "value"}
        encoded = encode(msg)

        # Should use compact separators (no spaces)
        assert b": " not in encoded
        assert b", " not in encoded


class TestDecode:
    def test_basic_decode(self):
        msg = decode('{"jsonrpc":"2.0","id":1,"method":"ping"}')

        assert msg["method"] == "ping"
        assert msg["id"] == 1

    def test_strips_whitespace(self):
        msg = decode('  {"method":"ping"}  \n')

        assert msg["method"] == "ping"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            decode("not json")


class TestMakeRequest:
    def test_with_params(self):
        msg = make_request("tools/call", {"name": "foo"}, id=5)

        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "tools/call"
        assert msg["params"]["name"] == "foo"
        assert msg["id"] == 5

    def test_without_params(self):
        msg = make_request("ping", id=1)

        assert "params" not in msg
        assert msg["method"] == "ping"

    def test_without_id(self):
        msg = make_request("ping")

        assert "id" not in msg


class TestMakeResponse:
    def test_success_response(self):
        msg = make_response(1, {"tools": [{"name": "foo"}]})

        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1
        assert msg["result"]["tools"][0]["name"] == "foo"


class TestMakeError:
    def test_error_response(self):
        msg = make_error(1, METHOD_NOT_FOUND, "Not found")

        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1
        assert msg["error"]["code"] == METHOD_NOT_FOUND
        assert msg["error"]["message"] == "Not found"

    def test_error_with_data(self):
        msg = make_error(1, INTERNAL_ERROR, "Failed", data={"detail": "oom"})

        assert msg["error"]["data"]["detail"] == "oom"

    def test_error_without_data(self):
        msg = make_error(1, PARSE_ERROR, "Bad")

        assert "data" not in msg["error"]


class TestMakeNotification:
    def test_notification(self):
        msg = make_notification("notifications/initialized")

        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "notifications/initialized"
        assert "id" not in msg

    def test_notification_with_params(self):
        msg = make_notification("log", {"level": "info", "message": "hi"})

        assert msg["params"]["level"] == "info"
