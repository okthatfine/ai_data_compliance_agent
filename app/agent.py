from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .case_store import CaseStore, case_hit_to_dict
from .pkulaw_mcp import PkulawMCPClient
from .rag import PolicyVectorStore, RetrievedChunk, normalize_text
from .risk_map import load_risk_map
from .rules import scan_risk_rules

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RISK_ORDER = {"高": 0, "中": 1, "低": 2}


def _deepseek_chat(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    if not api_key:
        return "未配置 DEEPSEEK_API_KEY，以下为基于本地法规和规则生成的初步意见。"
    try:
        from langchain_openai import ChatOpenAI

        response = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            timeout=45,
        ).invoke(messages)
        return str(response.content).strip()
    except Exception:
        pass
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": temperature, "stream": False},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"DeepSeek 调用失败，已回退到本地合规意见。错误：{exc}"


class ComplianceAgent:
    """Single-process compliance service using PKULaw evidence and risk rules."""

    def __init__(self) -> None:
        self.store = PolicyVectorStore()
        self.case_store = CaseStore()
        self.pkulaw = PkulawMCPClient()
        self.risk_map = load_risk_map()

    def status(self) -> dict[str, Any]:
        return {
            "retriever": self.store.stats(),
            "case_library": self.case_store.stats(),
            "knowledge_graph": self.risk_map["summary"],
            "pkulaw": self.pkulaw.status(),
        }

    def answer(self, question: str) -> dict[str, Any]:
        hits = self.pkulaw.search_policies(question, k=6)
        case_hits = self.pkulaw.search_cases(question, k=3)
        graph = self._map_context(question)
        context = self._format_context(hits)
        case_context = self._format_case_context([case_hit_to_dict(hit) for hit in case_hits])
        graph_context = self._format_graph_context(graph)
        answer = _deepseek_chat(
            [
                {
                    "role": "system",
                    "content": "你是面向中国 AI 科创企业的数据合规助手。必须基于给出的法规、案例和知识图谱材料回答；材料不足时明确说明不确定性。回答按结论、主要风险、法律与类案依据、整改建议组织。",
                },
                {
                    "role": "user",
                    "content": f"法规依据：\n{context}\n\n类案依据：\n{case_context}\n\n知识图谱关系：\n{graph_context}\n\n用户问题：{question}",
                },
            ]
        )
        return {
            "answer": answer,
            "sources": [self._hit_to_dict(hit) for hit in hits],
            "case_sources": [case_hit_to_dict(hit) for hit in case_hits],
            "kg_relations": graph.get("relations", []),
            "retrieval": {"legal": "pkulaw_mcp", "cases": "pkulaw_mcp", "pkulaw": self.pkulaw.status()},
        }

    def audit_text(self, text: str, filename: str = "文本输入") -> dict[str, Any]:
        clean = normalize_text(text)
        risks = []
        for rule in scan_risk_rules(clean):
            risk = self._normalize_rule_risk(rule, clean)
            matched = " ".join(risk["matched_keywords"])
            legal_hits = self.pkulaw.search_policies(f"{risk['query']} {matched}".strip(), k=4)
            case_hits = self.pkulaw.search_cases(
                query=f"{risk['risk_name']} {matched}".strip(),
                risk_type=risk["risk_type"],
                k=3,
            )
            graph = self._map_context(risk["risk_name"], risk["risk_type"])
            risks.append(
                {
                    "title": risk["risk_name"],
                    "risk_type": risk["risk_type"],
                    "risk_name": risk["risk_name"],
                    "severity": risk["severity"],
                    "matched_keywords": risk["matched_keywords"],
                    "excerpt": risk["excerpt"],
                    "reason": risk["reason"],
                    "legal_basis": [self._hit_to_dict(hit) for hit in legal_hits],
                    "case_basis": [case_hit_to_dict(hit) for hit in case_hits],
                    "kg_relations": graph.get("relations", []),
                    "kg_nodes": graph.get("nodes", []),
                    "lifecycle_stages": graph.get("lifecycle_stages", []),
                    "graph_laws": graph.get("laws", []),
                    "graph_cases": graph.get("cases", []),
                    "recommendation": risk["suggestion"],
                    "suggestion": risk["suggestion"],
                }
            )
        if not risks:
            legal_hits = self.pkulaw.search_policies("数据安全 个人信息保护 合规义务 AI 科创企业", k=4)
            risks.append(
                {
                    "title": "未发现显著关键词风险，建议人工复核",
                    "risk_type": "RISK-GENERAL",
                    "risk_name": "通用合规复核",
                    "severity": "低",
                    "matched_keywords": [],
                    "excerpt": clean[:320],
                    "reason": "材料未命中当前规则库中的高频风险关键词。",
                    "legal_basis": [self._hit_to_dict(hit) for hit in legal_hits],
                    "case_basis": [],
                    "kg_relations": [],
                    "kg_nodes": [],
                    "lifecycle_stages": [],
                    "graph_laws": [],
                    "graph_cases": [],
                    "recommendation": "补充业务流程、数据流向、供应商、系统权限和企业发展阶段材料后复核。",
                    "suggestion": "补充业务流程、数据流向、供应商、系统权限和企业发展阶段材料后复核。",
                }
            )
        risks.sort(key=lambda risk: RISK_ORDER.get(str(risk["severity"]), 3))
        overall_level = self._overall_level(risks)
        return {
            "filename": filename,
            "overall_level": overall_level,
            "risk_count": len(risks),
            "risks": risks,
            "summary": self._draft_audit_summary(filename, clean, risks, overall_level),
            "case_library": self.case_store.stats(),
            "knowledge_graph": self.risk_map["summary"],
            "retrieval": {"legal": "pkulaw_mcp", "cases": "pkulaw_mcp", "pkulaw": self.pkulaw.status()},
        }

    @staticmethod
    def _normalize_rule_risk(rule: dict[str, Any], text: str) -> dict[str, Any]:
        matched = list(rule.get("matched_keywords") or [])
        name = str(rule.get("name") or "")
        severity = str(rule.get("severity") or "中")
        if severity not in RISK_ORDER:
            severity = "中"
        return {
            "risk_type": str(rule.get("risk_type") or "RISK-GENERAL"),
            "risk_name": name,
            "severity": severity,
            "matched_keywords": matched,
            "query": str(rule.get("query") or ""),
            "suggestion": str(rule.get("suggestion") or ""),
            "reason": f"命中“{name}”相关关键词：{', '.join(matched) or '无'}。",
            "excerpt": ComplianceAgent._find_excerpt(text, matched),
        }

    @staticmethod
    def _find_excerpt(text: str, keywords: list[str]) -> str:
        for keyword in keywords:
            position = text.lower().find(keyword.lower())
            if position >= 0:
                return text[max(0, position - 90): position + len(keyword) + 180]
        return text[:280]

    @staticmethod
    def _overall_level(risks: list[dict[str, Any]]) -> str:
        levels = {str(risk.get("severity")) for risk in risks}
        if "高" in levels:
            return "高"
        if "中" in levels:
            return "中"
        return "低"

    def _draft_audit_summary(self, filename: str, text: str, risks: list[dict[str, Any]], overall: str) -> str:
        compact = "\n".join(
            f"{risk['severity']}风险：{risk['title']}；整改建议：{risk['recommendation']}"
            for risk in risks[:8]
        )
        return _deepseek_chat(
            [
                {"role": "system", "content": "你是企业数据合规审查报告助手，使用中文，表述正式且简洁。"},
                {"role": "user", "content": f"文件：{filename}\n总体评级：{overall}\n材料摘要：{text[:2200]}\n风险：\n{compact}\n请生成审查摘要，包含总体评级、重点风险、整改优先级和待补充材料。"},
            ]
        )

    def _map_context(self, query: str, risk_code: str = "") -> dict[str, Any]:
        risks = self.risk_map.get("risks", [])
        selected = [risk for risk in risks if risk.get("code") == risk_code]
        if not selected:
            lowered = query.lower()
            selected = [risk for risk in risks if risk.get("name", "").lower().replace("风险", "") in lowered]
        selected_codes = {risk.get("code") for risk in selected}
        if not selected_codes:
            return {"nodes": [], "relations": [], "lifecycle_stages": [], "laws": [], "cases": []}
        nodes = self.risk_map.get("nodes", [])
        stages = [node for node in nodes if node.get("type") == "stage" and any(node.get("id") in risk.get("stage_ids", []) for risk in selected)]
        law_ids = {law_id for risk in selected for law_id in risk.get("law_ids", [])}
        laws = [node for node in nodes if node.get("type") == "law" and node.get("id") in law_ids]
        cases = [node for node in nodes if node.get("type") == "case" and selected_codes.intersection(node.get("risk_codes", []))][:8]
        relations = [edge for edge in self.risk_map.get("edges", []) if edge.get("source") in selected_codes or edge.get("target") in selected_codes]
        return {"nodes": stages + laws + cases, "relations": relations, "lifecycle_stages": stages, "laws": laws, "cases": cases}

    @staticmethod
    def _format_context(hits: list[RetrievedChunk]) -> str:
        return "\n".join(
            f"[{index}] {hit.title}（{hit.level}，chunk {hit.chunk_id}）\n{hit.text}\n来源：{hit.source_url}"
            for index, hit in enumerate(hits, start=1)
        ) or "未检索到法规依据。"

    @staticmethod
    def _format_case_context(hits: list[dict[str, Any]]) -> str:
        return "\n".join(
            f"[{index}] {hit.get('title', '')}（{hit.get('case_no', '')}）\n{hit.get('text', '')}"
            for index, hit in enumerate(hits, start=1)
        ) or "未检索到类案依据。"

    @staticmethod
    def _format_graph_context(graph: dict[str, Any]) -> str:
        nodes = graph.get("nodes", [])[:5]
        relations = graph.get("relations", [])[:8]
        return f"相关节点：{nodes}\n相关关系：{relations}" if nodes or relations else "未检索到知识图谱关系。"

    @staticmethod
    def _hit_to_dict(hit: RetrievedChunk) -> dict[str, Any]:
        return {
            "title": hit.title,
            "level": hit.level,
            "source_url": hit.source_url,
            "text": hit.text,
            "score": round(hit.score, 4),
            "source_file": hit.source_file,
            "chunk_id": hit.chunk_id,
        }
