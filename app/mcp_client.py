from __future__ import annotations

from typing import Any

from .mcp_server import MCPToolServer
from .rag import PolicyVectorStore


class LocalMCPClient:
    """Client facade for calling the app's MCP tool server from agents."""

    def __init__(self, store: PolicyVectorStore):
        self.server = MCPToolServer(store)
        self.trace: list[dict[str, Any]] = []

    def manifest(self) -> dict[str, Any]:
        return self.server.manifest()

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        result = self.server.call_tool(name, args)
        self.trace.append({
            "tool": name,
            "arguments": self._safe_args(args),
            "result_keys": sorted(result.keys()),
        })
        return result

    def pop_trace(self) -> list[dict[str, Any]]:
        trace = self.trace[:]
        self.trace.clear()
        return trace

    @staticmethod
    def _safe_args(args: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in args.items():
            if isinstance(value, str) and len(value) > 160:
                safe[key] = value[:160] + "..."
            else:
                safe[key] = value
        return safe
