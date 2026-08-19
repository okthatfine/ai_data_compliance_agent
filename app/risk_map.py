from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "risk_map_seed.json"
CACHE_PATH = ROOT / "data" / "pkulaw_cases_cache.json"


def load_risk_map() -> dict[str, Any]:
    """Build a browser-ready graph from the team's nine-risk taxonomy."""
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    cached_cases = _load_cached_cases()
    cases = list(seed.get("cases") or []) + cached_cases
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    for stage in seed.get("stages") or []:
        nodes.append({**stage, "type": "stage"})
    for risk in seed.get("risks") or []:
        risk_id = risk["code"]
        nodes.append({**risk, "id": risk_id, "type": "risk"})
        for stage_id in risk.get("stage_ids") or []:
            edges.append(_edge(risk_id, stage_id, "高发阶段"))
        for law_id in risk.get("law_ids") or []:
            edges.append(_edge(risk_id, law_id, "法律依据"))
    for law in seed.get("laws") or []:
        nodes.append({**law, "type": "law"})
    for case in cases:
        if not case.get("id"):
            continue
        nodes.append({**case, "type": "case"})
        for risk_id in case.get("risk_codes") or []:
            edges.append(_edge(case["id"], risk_id, "关联风险"))
        for stage_id in case.get("stage_ids") or []:
            edges.append(_edge(case["id"], stage_id, "发生阶段"))
        for law_id in case.get("law_ids") or []:
            edges.append(_edge(case["id"], law_id, "裁判依据"))

    seen: set[str] = set()
    unique_nodes = []
    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id and node_id not in seen:
            seen.add(node_id)
            unique_nodes.append(node)
    return {
        "meta": seed.get("meta") or {},
        "risks": seed.get("risks") or [],
        "stages": seed.get("stages") or [],
        "nodes": unique_nodes,
        "edges": edges,
        "summary": {
            "risk_count": len(seed.get("risks") or []),
            "stage_count": len(seed.get("stages") or []),
            "law_count": len(seed.get("laws") or []),
            "case_count": len(cases),
            "pkulaw_case_count": len(cached_cases),
        },
    }


def _load_cached_cases() -> list[dict[str, Any]]:
    if not CACHE_PATH.exists():
        return []
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return [item for item in data.get("cases", []) if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError):
        return []


def _edge(source: str, target: str, relation: str) -> dict[str, str]:
    return {"id": f"{source}::{relation}::{target}", "source": source, "target": target, "relation": relation}
