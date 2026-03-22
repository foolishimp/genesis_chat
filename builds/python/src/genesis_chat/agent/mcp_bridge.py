# Implements: REQ-F-MCP-001
"""MCP bridge — connects to MCP servers, discovers tools, proxies calls.

MCP servers provide F_P-level capabilities (code execution, file access,
external APIs) that the agent can invoke alongside F_D tools.

Supports stdio transport (subprocess) — the standard MCP pattern.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    import json as _json

    class _yaml_shim:
        @staticmethod
        def safe_load(text):
            return _json.loads(text)

    yaml = _yaml_shim()  # type: ignore[assignment]


class MCPBridge:
    """Aggregates tools from configured MCP servers."""

    def __init__(self, config_path: Path | None = None):
        self._servers: dict[str, _StdioMCPConnection] = {}
        self._tool_map: dict[str, str] = {}  # tool_name → server_name
        self._tool_defs: list[dict] = []

        if config_path and config_path.exists():
            self._load_config(config_path)

    def _load_config(self, path: Path) -> None:
        data = yaml.safe_load(path.read_text())
        servers = data.get("mcp_servers", {})

        for name, cfg in servers.items():
            transport = cfg.get("transport", "stdio")
            if transport != "stdio":
                print(f"MCP: unsupported transport '{transport}' for '{name}'")
                continue

            conn = _StdioMCPConnection(
                name=name,
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )

            try:
                conn.connect()
                tools = conn.list_tools()
                self._servers[name] = conn

                for tool in tools:
                    tool_name = tool["name"]
                    qualified = f"mcp_{name}_{tool_name}"
                    self._tool_map[qualified] = name
                    self._tool_defs.append({
                        "name": qualified,
                        "description": f"[MCP:{name}] {tool.get('description', '')}",
                        "input_schema": tool.get(
                            "inputSchema",
                            {"type": "object", "properties": {}},
                        ),
                    })
                    # Unqualified alias if no collision
                    if tool_name not in self._tool_map:
                        self._tool_map[tool_name] = name

                print(f"MCP: connected to '{name}' — {len(tools)} tools")
            except Exception as e:
                print(f"MCP: failed to connect to '{name}': {e}")

    def tool_definitions(self) -> list[dict]:
        return list(self._tool_defs)

    def call_tool(self, name: str, arguments: dict) -> str:
        server_name = self._tool_map.get(name)
        if not server_name:
            return f"MCP tool '{name}' not found"

        conn = self._servers.get(server_name)
        if not conn:
            return f"MCP server '{server_name}' not connected"

        # Strip qualified prefix for the actual call
        actual_name = name
        prefix = f"mcp_{server_name}_"
        if name.startswith(prefix):
            actual_name = name[len(prefix):]

        try:
            return conn.call_tool(actual_name, arguments)
        except Exception as e:
            return f"MCP tool error: {e}"

    def shutdown(self) -> None:
        for conn in self._servers.values():
            try:
                conn.close()
            except Exception:
                pass


class _StdioMCPConnection:
    """MCP server connection via stdio (JSON-RPC 2.0 over subprocess)."""

    def __init__(self, name: str, command: str, args: list[str], env: dict | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.extra_env = env
        self._proc: subprocess.Popen | None = None
        self._request_id = 0
        self._lock = threading.Lock()

    def connect(self) -> None:
        env = dict(os.environ)
        if self.extra_env:
            env.update(self.extra_env)

        self._proc = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        # MCP initialize handshake
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "genesis_chat", "version": "0.2.0"},
        })
        self._notify("notifications/initialized", {})

    def list_tools(self) -> list[dict]:
        result = self._rpc("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(text_parts) or json.dumps(result)

    def close(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()

    def _rpc(self, method: str, params: dict) -> dict:
        with self._lock:
            self._request_id += 1
            req_id = self._request_id
            self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
            return self._recv(req_id)

    def _notify(self, method: str, params: dict) -> None:
        with self._lock:
            self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, msg: dict) -> None:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("MCP server not connected")
        data = json.dumps(msg)
        self._proc.stdin.write((data + "\n").encode())
        self._proc.stdin.flush()

    def _recv(self, expected_id: int) -> dict:
        if not self._proc or not self._proc.stdout:
            raise RuntimeError("MCP server not connected")
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed connection")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" not in msg:
                continue  # skip notifications
            if msg.get("id") == expected_id:
                if "error" in msg:
                    raise RuntimeError(f"MCP error: {msg['error']}")
                return msg.get("result", {})
