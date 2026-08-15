from __future__ import annotations

from typing import Any

from .case_store import CaseStore, case_hit_to_dict
from .db import db_status
from .kg_store import KnowledgeGraphStore
from .pkulaw_mcp import PkulawMCPClient
from .rag import PolicyVectorStore, RetrievedChunk
from .report import build_pdf_report
from .repository import db_counts
from .rules import scan_risk_rules
from .skills import list_skills

RISK_ORDER = {"高": 0, "中": 1, "低": 2}


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
    """MCP-compatible tool layer for the risk-management demo.

    Agents call this layer instead of touching local stores directly. The tool
    names are stable, so the backend can later move from local JSON/SQLite to a
    remote MCP service, vector database, case database, or graph database.
    """

    def __init__(
        self,
        store: PolicyVectorStore,
        case_store: CaseStore | None = None,
        kg_store: KnowledgeGraphStore | None = None,
    ):
        self.store = store
        self.case_store = case_store or CaseStore()
        self.kg_store = kg_store or KnowledgeGraphStore()
        self.pkulaw = PkulawMCPClient()

    def manifest(self) -> dict[str, Any]:
        return {
            "name": "ai-data-compliance-mcp",
            "version": "1.0.0",
            "transport": "fastapi-json",
            "tools": self.list_tools(),
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            _tool("legal.policy_search", "Search legal policies, laws, and team knowledge-base chunks.", {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5},
            }, ["query"]),
            _tool("case.risk_case_search", "Search the sci-tech enterprise risk case library.", {
                "query": {"type": "string"},
                "risk_type": {"type": "string"},
                "k": {"type": "integer", "default": 3},
            }, ["query"]),
            _tool("risk.rule_scan", "Scan enterprise material against local risk rules.", {
                "text": {"type": "string"},
            }, ["text"]),
            _tool("risk.scenario_audit", "Run scenario audit with risk scan, legal search, case search, and graph query.", {
                "text": {"type": "string"},
                "filename": {"type": "string", "default": "文本输入"},
                "legal_k": {"type": "integer", "default": 4},
                "case_k": {"type": "integer", "default": 3},
            }, ["text"]),
            _tool("kg.relation_search", "Search risk-law-case-lifecycle knowledge graph relations.", {
                "query": {"type": "string"},
                "risk_type": {"type": "string"},
                "k": {"type": "integer", "default": 5},
            }, ["query"]),
            _tool("report.audit_generate", "Generate a PDF report from an audit result payload.", {
                "audit_result": {"type": "object"},
            }, ["audit_result"]),
            _tool("system.status", "Return MCP, retriever, case library, knowledge graph, and database status.", {}, []),
            _tool("skills.catalog", "List reusable agent skills.", {}, []),
            _tool("compliance.risk_scan", "Backward-compatible alias for risk.rule_scan.", {
                "text": {"type": "string"},
            }, ["text"]),
            _tool("system.db_status", "Backward-compatible database status tool.", {}, []),
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        if name == "legal.policy_search":
            return self._policy_search(args)
        if name == "case.risk_case_search":
            return self._case_search(args)
        if name in {"risk.rule_scan", "compliance.risk_scan"}:
            return self._risk_scan(args)
        if name == "risk.scenario_audit":
            return self._scenario_audit(args)
        if name == "kg.relation_search":
            return self._kg_relation_search(args)
        if name == "report.audit_generate":
            return self._report_generate(args)
        if name == "system.status":
            return self._system_status()
        if name == "system.db_status":
            return self._db_status()
        if name == "skills.catalog":
            return {"skills": list_skills()}
        raise ValueError(f"Unknown MCP tool: {name}")

    def _policy_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        k = max(1, min(int(args.get("k") or 5), 12))
        pkulaw_hits = self.pkulaw.search_policies(query, k=k)
        if pkulaw_hits:
            return {
                "query": query,
                "backend": "pkulaw_mcp",
                "embedding_model": "",
                "hits": [hit_to_dict(hit) for hit in pkulaw_hits],
                "pkulaw": self.pkulaw.status(),
                "fallback_used": False,
            }
        hits = self.store.search(query, k=k)
        return {
            "query": query,
            "backend": self.store.backend(),
            "embedding_model": self.store.stats().get("embedding_model", ""),
            "hits": [hit_to_dict(hit) for hit in hits],
            "pkulaw": self.pkulaw.status(),
            "fallback_used": self.pkulaw.ready(),
        }

    def _case_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        risk_type = str(args.get("risk_type") or "").strip()
        k = max(1, min(int(args.get("k") or 3), 10))
        pkulaw_hits = self.pkulaw.search_cases(query=query, risk_type=risk_type, k=k)
        if pkulaw_hits:
            return {
                "query": query,
                "risk_type": risk_type,
                "backend": "pkulaw_mcp",
                "ready": True,
                "hits": [case_hit_to_dict(hit) for hit in pkulaw_hits],
                "stats": {"ready": True, "source": "pkulaw_mcp", "cases": "external"},
                "pkulaw": self.pkulaw.status(),
                "fallback_used": False,
            }
        hits = self.case_store.search(query=query, risk_type=risk_type, k=k)
        stats = self.case_store.stats()
        return {
            "query": query,
            "risk_type": risk_type,
            "backend": "file_case_store",
            "ready": stats["ready"],
            "hits": [case_hit_to_dict(hit) for hit in hits],
            "stats": stats,
            "pkulaw": self.pkulaw.status(),
            "fallback_used": self.pkulaw.ready(),
        }

    def _risk_scan(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text") or "")
        risks = [self._normalize_rule_risk(risk, text) for risk in scan_risk_rules(text)]
        return {"risks": risks, "risk_count": len(risks)}

    def _scenario_audit(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text") or "")
        filename = str(args.get("filename") or "文本输入")
        legal_k = max(1, min(int(args.get("legal_k") or 4), 8))
        case_k = max(1, min(int(args.get("case_k") or 3), 8))
        scan = self._risk_scan({"text": text})
        risks = []
        for scanned in scan["risks"]:
            matched = " ".join(scanned.get("matched_keywords") or [])
            search_query = f"{scanned.get('query', '')} {matched}".strip() or scanned["risk_name"]
            legal = self._policy_search({"query": search_query, "k": legal_k})
            cases = self._case_search({
                "query": f"{scanned['risk_name']} {matched}".strip(),
                "risk_type": scanned.get("risk_type", ""),
                "k": case_k,
            })
            graph = self._kg_relation_search({
                "query": scanned["risk_name"],
                "risk_type": scanned.get("risk_type", ""),
                "k": 5,
            })
            risks.append({
                "title": scanned["risk_name"],
                "risk_type": scanned["risk_type"],
                "risk_name": scanned["risk_name"],
                "severity": scanned["severity"],
                "matched_keywords": scanned["matched_keywords"],
                "excerpt": scanned["excerpt"],
                "reason": scanned["reason"],
                "legal_basis": legal["hits"],
                "case_basis": cases["hits"],
                "kg_relations": graph.get("relations", []),
                "kg_nodes": graph.get("nodes", []),
                "recommendation": scanned["suggestion"],
                "suggestion": scanned["suggestion"],
            })
        if not risks:
            legal = self._policy_search({"query": "数据安全 个人信息保护 合规义务 AI 科创企业", "k": legal_k})
            risks.append({
                "title": "未发现显著关键词风险，建议人工复核",
                "risk_type": "RISK-GENERAL",
                "risk_name": "通用合规复核",
                "severity": "低",
                "matched_keywords": [],
                "excerpt": text[:320],
                "reason": "材料未命中当前规则库中的高频风险关键词。",
                "legal_basis": legal["hits"],
                "case_basis": [],
                "kg_relations": [],
                "kg_nodes": [],
                "recommendation": "补充业务流程、数据流向、供应商、系统权限和企业发展阶段材料后复核。",
                "suggestion": "补充业务流程、数据流向、供应商、系统权限和企业发展阶段材料后复核。",
            })
        risks.sort(key=lambda r: RISK_ORDER.get(str(r["severity"]), 3))
        return {
            "filename": filename,
            "risks": risks,
            "risk_count": len(risks),
            "overall_level": self._overall_level(risks),
            "tools_used": [
                "risk.rule_scan",
                "legal.policy_search",
                "case.risk_case_search",
                "kg.relation_search",
            ],
            "case_library": self.case_store.stats(),
            "knowledge_graph": self.kg_store.stats(),
        }

    def _kg_relation_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        risk_type = str(args.get("risk_type") or "").strip()
        k = max(1, min(int(args.get("k") or 5), 50))
        return self.kg_store.search(query=query, risk_type=risk_type, k=k)

    @staticmethod
    def _report_generate(args: dict[str, Any]) -> dict[str, Any]:
        audit_result = args.get("audit_result")
        if not isinstance(audit_result, dict):
            raise ValueError("audit_result must be an object")
        report_id, path = build_pdf_report(audit_result)
        return {
            "report_id": report_id,
            "report_path": str(path),
            "report_url": f"/api/report/{report_id}",
        }

    def _system_status(self) -> dict[str, Any]:
        status = self._db_status()
        return {
            "ok": status.get("ok", False),
            "database": status,
            "retriever": self.store.stats(),
            "case_library": self.case_store.stats(),
            "knowledge_graph": self.kg_store.stats(),
            "pkulaw": self.pkulaw.status(),
            "mcp": self.manifest(),
        }

    @staticmethod
    def _db_status() -> dict[str, Any]:
        status = db_status()
        try:
            status["counts"] = db_counts() if status["ok"] else {}
        except Exception as exc:
            status["counts"] = {}
            status["count_error"] = str(exc)
        return status

    @staticmethod
    def _normalize_rule_risk(risk: dict[str, Any], text: str) -> dict[str, Any]:
        matched = list(risk.get("matched_keywords") or [])
        name = str(risk.get("name") or "")
        return {
            "risk_type": risk.get("risk_type") or _infer_risk_type(name),
            "risk_name": name,
            "severity": _normalize_severity(str(risk.get("severity") or "中")),
            "matched_keywords": matched,
            "query": str(risk.get("query") or ""),
            "suggestion": str(risk.get("suggestion") or ""),
            "reason": _build_reason(name, matched),
            "excerpt": _find_excerpt(text, matched),
        }

    @staticmethod
    def _overall_level(risks: list[dict[str, Any]]) -> str:
        levels = [str(r.get("severity") or "") for r in risks]
        if "高" in levels:
            return "高风险"
        if "中" in levels:
            return "中风险"
        return "低风险"


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _normalize_severity(value: str) -> str:
    if value.startswith("高"):
        return "高"
    if value.startswith("低"):
        return "低"
    return "中"


def _infer_risk_type(name: str) -> str:
    mapping = [
        ("训练", "RISK-DATA"),
        ("个人信息", "RISK-DATA"),
        ("数据出境", "RISK-GEO"),
        ("出境", "RISK-GEO"),
        ("跨境", "RISK-GEO"),
        ("重要数据", "RISK-DATA"),
        ("自动化决策", "RISK-ALGO"),
        ("算法", "RISK-ALGO"),
        ("生成", "RISK-ALGO"),
        ("标识", "RISK-ALGO"),
        ("人脸", "RISK-DATA"),
        ("第三方", "RISK-DATA"),
        ("供应商", "RISK-DATA"),
        ("安全技术", "RISK-TECH"),
    ]
    for keyword, risk_type in mapping:
        if keyword in name:
            return risk_type
    return "RISK-DATA"


def _build_reason(name: str, matched: list[str]) -> str:
    if matched:
        return f"命中{name}相关风险信号：{', '.join(matched[:8])}。"
    return f"命中{name}相关风险规则。"


def _find_excerpt(text: str, keywords: list[str]) -> str:
    lower = text.lower()
    positions = [lower.find(k.lower()) for k in keywords if lower.find(k.lower()) >= 0]
    start = max(0, min(positions) - 100) if positions else 0
    return text[start:start + 420]
