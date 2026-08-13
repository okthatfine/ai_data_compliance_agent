from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .rag import normalize_text

ROOT = Path(__file__).resolve().parents[1]
KG_DIR = ROOT / "data" / "kg"


class KnowledgeGraphStore:
    """File-backed risk knowledge graph used behind the MCP tool.

    Supported inputs:
    - data/kg/graph.json with {"nodes": [...], "edges": [...]}
    - data/kg/nodes.json and data/kg/edges.json
    """

    def __init__(self, kg_dir: Path = KG_DIR):
        self.kg_dir = kg_dir
        self._nodes: list[dict[str, Any]] | None = None
        self._edges: list[dict[str, Any]] | None = None

    def stats(self) -> dict[str, Any]:
        nodes, edges = self.load()
        node_types: dict[str, int] = {}
        for node in nodes:
            typ = str(node.get("type") or "unknown")
            node_types[typ] = node_types.get(typ, 0) + 1
        return {
            "ready": bool(nodes or edges),
            "nodes": len(nodes),
            "edges": len(edges),
            "node_types": node_types,
        }

    def load(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if self._nodes is not None and self._edges is not None:
            return self._nodes, self._edges
        graph_file = self.kg_dir / "graph.json"
        nodes_file = self.kg_dir / "nodes.json"
        edges_file = self.kg_dir / "edges.json"
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        try:
            if graph_file.exists():
                raw = json.loads(graph_file.read_text(encoding="utf-8"))
                nodes = list(raw.get("nodes") or [])
                edges = list(raw.get("edges") or raw.get("links") or [])
            else:
                if nodes_file.exists():
                    nodes_raw = json.loads(nodes_file.read_text(encoding="utf-8"))
                    nodes = list(nodes_raw.get("nodes") if isinstance(nodes_raw, dict) else nodes_raw)
                if edges_file.exists():
                    edges_raw = json.loads(edges_file.read_text(encoding="utf-8"))
                    edges = list(edges_raw.get("edges") if isinstance(edges_raw, dict) else edges_raw)
        except Exception:
            nodes, edges = [], []
        self._nodes = [n for n in nodes if isinstance(n, dict)]
        self._edges = [e for e in edges if isinstance(e, dict)]
        return self._nodes, self._edges

    def search(self, query: str, risk_type: str = "", k: int = 5) -> dict[str, Any]:
        query = normalize_text(query)
        risk_type = normalize_text(risk_type)
        nodes, edges = self.load()
        node_by_id = {str(n.get("id")): n for n in nodes if n.get("id") is not None}
        matched_ids = set()
        for node in nodes:
            haystack = " ".join(str(v) for v in node.values() if not isinstance(v, (dict, list)))
            risk_values = " ".join(str(x) for x in _as_list(node.get("risk") or node.get("risk_types") or node.get("risk_type")))
            if _match(query, haystack) or (risk_type and risk_type in risk_values):
                if node.get("id") is not None:
                    matched_ids.add(str(node.get("id")))
        related_edges = []
        related_ids = set(matched_ids)
        for edge in edges:
            source = str(edge.get("source") or edge.get("from") or "")
            target = str(edge.get("target") or edge.get("to") or "")
            if source in matched_ids or target in matched_ids:
                related_edges.append(edge)
                related_ids.update([source, target])
        visible_nodes = [node_by_id[i] for i in related_ids if i in node_by_id]
        limit = max(1, min(k, 50))
        return {
            "query": query,
            "risk_type": risk_type,
            "nodes": visible_nodes[:limit],
            "relations": related_edges[: limit * 3],
            "node_count": len(visible_nodes),
            "relation_count": len(related_edges),
            "backend": "file_graph" if nodes or edges else "empty_graph",
        }


def _match(query: str, text: str) -> bool:
    if not query:
        return False
    lowered = text.lower()
    return any(token.lower() in lowered for token in _tokens(query))


def _tokens(query: str) -> list[str]:
    words = [w for w in re.split(r"[\s,，;；|/]+", query) if len(w) >= 2]
    if words:
        return words
    return [query]


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]
