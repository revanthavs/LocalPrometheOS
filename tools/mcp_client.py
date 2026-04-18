"""Minimal MCP client supporting stdio and HTTP transports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
import logging
import threading
import uuid
import time
import os
import subprocess
import requests

from tools.builtin_tools import ToolSpec
from config.config import MCPServerConfig

logger = logging.getLogger(__name__)


class MCPError(Exception):
    pass


class _BaseConnection:
    def request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Any:
        raise NotImplementedError


class HttpMCPConnection(_BaseConnection):
    def __init__(self, url: str, timeout: int = 30) -> None:
        self.url = url
        self.timeout = timeout

    def request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
        response = requests.post(self.url, json=payload, timeout=timeout or self.timeout)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise MCPError(data["error"])
        return data.get("result")


class StdioMCPConnection(_BaseConnection):
    def __init__(self, command: List[str], env: Optional[Dict[str, str]] = None) -> None:
        self.command = command
        self.env = env or {}
        self.process: Optional[subprocess.Popen[str]] = None
        self._responses: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._reader_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.process:
            return
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env={**os.environ, **self.env},
            )
        except OSError as exc:
            raise MCPError(f"Failed to start MCP process {self.command!r}: {exc}") from exc
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        if not self.process or not self.process.stdout:
            logger.error("MCP reader loop started before process was ready; aborting reader")
            return
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_id = message.get("id")
            if msg_id is None:
                continue
            with self._condition:
                self._responses[str(msg_id)] = message
                self._condition.notify_all()

    def request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Any:
        self.start()
        if not self.process or not self.process.stdin:
            raise MCPError("Failed to start MCP process")
        msg_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params or {},
        }
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

        end_time = time.time() + timeout
        with self._condition:
            while time.time() < end_time:
                if msg_id in self._responses:
                    message = self._responses.pop(msg_id)
                    if "error" in message:
                        raise MCPError(message["error"])
                    return message.get("result")
                remaining = end_time - time.time()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)
        raise MCPError("MCP stdio request timed out")


@dataclass
class MCPToolMapping:
    server_name: str
    tool_name: str


class MCPClient:
    def __init__(self, servers: List[MCPServerConfig]) -> None:
        self._servers = servers
        self._connections: Dict[str, _BaseConnection] = {}
        self._tool_map: Dict[str, MCPToolMapping] = {}
        self._tool_specs: Dict[str, ToolSpec] = {}
        self._initialized: set[str] = set()

    def _get_connection(self, server: MCPServerConfig) -> _BaseConnection:
        if server.name in self._connections:
            return self._connections[server.name]
        if server.transport == "http":
            if not server.url:
                raise MCPError(f"HTTP MCP server '{server.name}' missing url")
            conn = HttpMCPConnection(server.url, timeout=server.timeout)
        elif server.transport == "stdio":
            if not server.command:
                raise MCPError(f"Stdio MCP server '{server.name}' missing command")
            conn = StdioMCPConnection(server.command, env=server.env)
        else:
            raise MCPError(f"Unknown MCP transport: {server.transport}")
        self._connections[server.name] = conn
        return conn

    def _initialize(self, server_name: str, conn: _BaseConnection, timeout: int) -> None:
        if server_name in self._initialized:
            return
        try:
            conn.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "LocalPrometheOS", "version": "0.1.0"},
                },
                timeout=timeout,
            )
            self._initialized.add(server_name)
        except MCPError:
            pass

    def list_tools(self) -> List[ToolSpec]:
        self._tool_map.clear()
        self._tool_specs.clear()
        for server in self._servers:
            conn = self._get_connection(server)
            self._initialize(server.name, conn, timeout=server.timeout)
            result = conn.request("tools/list", timeout=server.timeout)
            if not result:
                continue
            tools = result.get("tools") if isinstance(result, dict) else result
            if not tools:
                continue
            for tool in tools:
                name = tool.get("name")
                description = tool.get("description", "")
                input_schema = tool.get("inputSchema", {"type": "object"})
                namespaced = f"{server.name}/{name}"
                self._tool_map[namespaced] = MCPToolMapping(
                    server_name=server.name,
                    tool_name=name,
                )
                self._tool_specs[namespaced] = ToolSpec(
                    name=namespaced,
                    description=description,
                    input_schema=input_schema,
                )
        return list(self._tool_specs.values())

    def call_tool(self, namespaced_tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if namespaced_tool not in self._tool_map:
            self.list_tools()
        mapping = self._tool_map.get(namespaced_tool)
        if not mapping:
            raise MCPError(f"Unknown MCP tool: {namespaced_tool}")
        server = next((s for s in self._servers if s.name == mapping.server_name), None)
        if not server:
            raise MCPError(f"Missing MCP server for tool: {namespaced_tool}")
        conn = self._get_connection(server)
        self._initialize(server.name, conn, timeout=server.timeout)
        result = conn.request(
            "tools/call",
            {"name": mapping.tool_name, "arguments": args},
            timeout=server.timeout,
        )
        return result if isinstance(result, dict) else {"result": result}
