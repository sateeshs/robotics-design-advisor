"""Transports for MCP communication.

StdioServerTransport — reads stdin / writes stdout (server side).
SSEServerTransport  — serves MCP over HTTP with Server-Sent Events.

Adapted from freecad-ai. FreeCAD-specific AppImage cleanup removed.
API key authentication added for cross-machine security.
"""

import json
import logging
import sys
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Callable

from . import protocol

logger = logging.getLogger(__name__)


class StdioServerTransport:
    """Server-side transport: reads JSON-RPC from stdin, writes to stdout."""

    def run(self, handler: Callable[[dict], dict | None]) -> None:
        """Blocking loop: read requests from stdin, dispatch to handler, write responses."""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                text = line.strip()
                if not text:
                    continue
                msg = protocol.decode(text)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._write(protocol.make_error(
                    None, protocol.PARSE_ERROR, "Parse error"
                ))
                continue
            except Exception:
                break

            try:
                response = handler(msg)
            except Exception as e:
                msg_id = msg.get("id")
                if msg_id is not None:
                    response = protocol.make_error(
                        msg_id, protocol.INTERNAL_ERROR, str(e)
                    )
                else:
                    response = None

            if response is not None:
                self._write(response)

    def _write(self, msg: dict) -> None:
        """Write a JSON-RPC message to stdout."""
        data = json.dumps(msg, separators=(",", ":")) + "\n"
        sys.stdout.write(data)
        sys.stdout.flush()


class SSEServerTransport:
    """Server-side transport: serves MCP over HTTP + Server-Sent Events.

    Endpoints:
        GET  /sse       -- SSE event stream (client subscribes here)
        POST /messages  -- JSON-RPC requests (responses arrive via SSE)
        GET  /health    -- Health check endpoint
        POST /mcp       -- Direct JSON-RPC (request/response, no SSE)

    Supports API key authentication via Authorization: Bearer <key> header.
    Designed for cross-machine Robotics Design Advisor communication.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8585,
        api_key: str | None = None,
        health_check: Callable[[], dict] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._api_key = api_key
        self._health_check = health_check
        self._handler: Callable[[dict], dict | None] | None = None
        self._sse_wfile: Any = None
        self._sse_lock = threading.Lock()

    def run(self, handler: Callable[[dict], dict | None]) -> None:
        """Start the HTTP server (blocking)."""
        self._handler = handler
        server = self._make_server()
        logger.info(
            "MCP SSE server listening on http://%s:%d (auth: %s)",
            self._host, self._port,
            "enabled" if self._api_key else "disabled",
        )
        server.serve_forever()

    def _make_server(self):
        """Build the threaded HTTP server."""
        transport = self

        class RequestHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                logger.debug(fmt, *args)

            def _base_path(self) -> str:
                return self.path.split("?")[0].rstrip("/")

            def _check_auth(self) -> bool:
                """Verify API key if configured. Returns True if authorized."""
                if transport._api_key is None:
                    return True
                auth_header = self.headers.get("Authorization", "")
                if auth_header == f"Bearer {transport._api_key}":
                    return True
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"Unauthorized","message":"Invalid or missing API key"}')
                return False

            def do_GET(self):
                path = self._base_path()

                # Health check is unauthenticated
                if path == "/health":
                    self._handle_health()
                    return

                if not self._check_auth():
                    return

                if path == "/sse":
                    self._handle_sse()
                else:
                    self.send_error(404)

            def do_POST(self):
                if not self._check_auth():
                    return

                path = self._base_path()
                if path == "/messages":
                    self._handle_messages()
                elif path == "/mcp":
                    self._handle_mcp_direct()
                else:
                    self.send_error(404)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.end_headers()

            def _handle_health(self):
                """Return server health status."""
                health = {"status": "ok", "server": "robotics-design-advisor", "version": "1.0.0"}
                if transport._health_check:
                    try:
                        health.update(transport._health_check())
                    except Exception as e:
                        health["error"] = str(e)

                data = json.dumps(health).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _handle_sse(self):
                """SSE event stream for async tool responses."""
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                session_id = uuid.uuid4().hex
                with transport._sse_lock:
                    transport._sse_wfile = self.wfile

                try:
                    endpoint_data = f"/messages?sessionId={session_id}"
                    endpoint_event = (
                        f"event: endpoint\ndata: {endpoint_data}\n\n".encode()
                    )
                    if not transport._write_locked(endpoint_event):
                        return
                    while transport._write_locked(b": keepalive\n\n"):
                        time.sleep(15)
                finally:
                    with transport._sse_lock:
                        if transport._sse_wfile is self.wfile:
                            transport._sse_wfile = None

            def _handle_messages(self):
                """Handle JSON-RPC via SSE channel."""
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")

                try:
                    msg = json.loads(body)
                except json.JSONDecodeError:
                    err = protocol.make_error(
                        None, protocol.PARSE_ERROR, "Parse error"
                    )
                    self._send_json(400, err)
                    return

                try:
                    response = transport._handler(msg) if transport._handler else None
                except Exception as e:
                    msg_id = msg.get("id")
                    response = protocol.make_error(
                        msg_id, protocol.INTERNAL_ERROR, str(e)
                    ) if msg_id is not None else None

                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"accepted":true}')
                self.wfile.flush()

                if response is not None:
                    transport._send_sse(response)

            def _handle_mcp_direct(self):
                """Direct JSON-RPC: request in, response out (no SSE needed).

                This is the primary endpoint for Claude Code's HTTP MCP client.
                """
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")

                try:
                    msg = json.loads(body)
                except json.JSONDecodeError:
                    err = protocol.make_error(
                        None, protocol.PARSE_ERROR, "Parse error"
                    )
                    self._send_json(400, err)
                    return

                try:
                    response = transport._handler(msg) if transport._handler else None
                except Exception as e:
                    msg_id = msg.get("id")
                    response = protocol.make_error(
                        msg_id, protocol.INTERNAL_ERROR, str(e)
                    ) if msg_id is not None else None

                if response is not None:
                    self._send_json(200, response)
                else:
                    self.send_response(204)
                    self.end_headers()

            def _send_json(self, code: int, msg: dict):
                data = json.dumps(msg, separators=(",", ":")).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
            daemon_threads = True

        return ThreadedHTTPServer((self._host, self._port), RequestHandler)

    def _send_sse(self, msg: dict) -> None:
        """Send a JSON-RPC message to the connected SSE client."""
        data = json.dumps(msg, separators=(",", ":"))
        payload = f"event: message\ndata: {data}\n\n".encode()
        self._write_locked(payload)

    def _write_locked(self, payload: bytes) -> bool:
        """Write raw bytes to the SSE client, serialized by _sse_lock."""
        with self._sse_lock:
            wfile = self._sse_wfile
            if wfile is None:
                return False
            try:
                wfile.write(payload)
                wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                self._sse_wfile = None
                return False
