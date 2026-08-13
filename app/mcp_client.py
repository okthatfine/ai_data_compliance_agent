from __future__ import annotations

import os
from typing import Any

import requests

from .case_store import CaseStore
from .kg_store import KnowledgeGraphStore
from .mcp_server import MCPToolServer
from .rag import PolicyVectorStore


class LocalMCPClient:
    """Client facade for MCP tools.

    If `MCP_BASE_URL` is set, the client uses the remote HTTP MCP endpoints:
    - GET  {base}/api/mcp/manifest
    - POST {base}/api/mcp/call

    Otherwise it falls back to an in-process MCP server backed by local stores.
    """

    def __init__(
        self,
        store: PolicyVectorStore,
        case_store: CaseStore | None = None,
        kg_store: KnowledgeGraphStore | None = None,
    ):
        self.base_url = os.getenv("MCP_BASE_URL", "").strip().rstrip("/")
        self.timeout = float(os.getenv("MCP_TIMEOUT", "30"))
        self.server = MCPToolServer(store, case_store=case_store, kg_store=kg_store)
        self.trace: list[dict[str, Any]] = []

    def manifest(self) -> dict[str, Any]:
        if self.base_url:
            try:
                resp = requests.get(f"{self.base_url}/api/mcp/manifest", timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception:
                pass
        return self.server.manifest()

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        if self.base_url:
            try:
                resp = requests.post(
                    f"{self.base_url}/api/mcp/call",
                    json={"name": name, "arguments": args},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                result = payload.get("result", payload)
                self.trace.append({
                    "tool": name,
                    "arguments": self._safe_args(args),
                    "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
                    "transport": "http",
                })
                return result
            except Exception:
                pass
        result = self.server.call_tool(name, args)
        self.trace.append({
            "tool": name,
            "arguments": self._safe_args(args),
            "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
            "transport": "local",
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
