from __future__ import annotations

from typing import Any

from .db import db_status
from .rag import PolicyVectorStore, RetrievedChunk
from .repository import db_counts
from .rules import scan_risk_rules
from .skills import list_skills


def hit_to_dict(hit: RetrievedChunk) -> dict[str, Any]:
    return {
        "title": hit.title,
        "level": hit.level,
        "source_url": hit.source_url,
        "text": hit.text,
        "score": round(hit.score, 4),
        "source_file": hit.source_file,
        "chunk_id": hit.chunk_id,
    }


class MCPToolServer:
    """Small JSON MCP-compatible tool server used by API endpoints and local clients."""

    def __init__(self, store: PolicyVectorStore):
        self.store = store

    def manifest(self) -> dict[str, Any]:
        return {
            "name": "ai-data-compliance-mcp",
            "version": "0.1.0",
            "transport": "fastapi-json",
            "tools": self.list_tools(),
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "legal.policy_search",
                "description": "使用 embedding RAG 检索数据合规法律政策依据。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "compliance.risk_scan",
                "description": "基于规则扫描企业材料中的数据合规风险关键词和风险类型。",
                "input_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            {
                "name": "system.db_status",
                "description": "查询 PostgreSQL、法规表、上传记录和报告记录状态。",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "skills.catalog",
                "description": "列出系统内可复用合规 Skills。",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        if name == "legal.policy_search":
            return self._policy_search(args)
        if name == "compliance.risk_scan":
            return self._risk_scan(args)
        if name == "system.db_status":
            return self._db_status()
        if name == "skills.catalog":
            return {"skills": list_skills()}
        raise ValueError(f"Unknown MCP tool: {name}")

    def _policy_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        k = int(args.get("k") or 5)
        hits = self.store.search(query, k=max(1, min(k, 12)))
        return {
            "query": query,
            "backend": self.store.backend(),
            "embedding_model": self.store.stats().get("embedding_model", ""),
            "hits": [hit_to_dict(hit) for hit in hits],
        }

    def _risk_scan(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text") or "")
        risks = scan_risk_rules(text)
        return {"risks": risks, "risk_count": len(risks)}

    @staticmethod
    def _db_status() -> dict[str, Any]:
        status = db_status()
        try:
            status["counts"] = db_counts() if status["ok"] else {}
        except Exception as exc:
            status["counts"] = {}
            status["count_error"] = str(exc)
        return status
