from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .mcp_client import LocalMCPClient
from .multi_agent import MultiAgentRouter
from .rag import PolicyVectorStore, RetrievedChunk, normalize_text

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _deepseek_chat(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    if not api_key:
        return "未配置 DEEPSEEK_API_KEY，以下为基于本地规则和检索依据生成的初步意见。"
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=temperature, timeout=45)
        response = llm.invoke(messages)
        return str(response.content).strip()
    except Exception:
        pass
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": temperature, "stream": False},
            timeout=45,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"DeepSeek 调用失败，已回退到本地规则意见。错误：{exc}"


class ComplianceAgent:
    """LLM agent orchestrated by MCP tools."""

    def __init__(self) -> None:
        self.store = PolicyVectorStore()
        self.mcp_client = LocalMCPClient(self.store)
        self.router = MultiAgentRouter(self.mcp_client)

    def answer(self, question: str) -> dict[str, Any]:
        route = self.router.route_question(question)
        policy_search = route["tool_results"].get("policy_search") or self.mcp_client.call_tool(
            "legal.policy_search", {"query": question, "k": 6}
        )
        case_search = self.mcp_client.call_tool("case.risk_case_search", {"query": question, "k": 3})
        kg_search = self.mcp_client.call_tool("kg.relation_search", {"query": question, "k": 5})
        hits = [self._dict_to_hit(item) for item in policy_search.get("hits", [])]
        context = self._format_context(hits)
        case_context = self._format_case_context(case_search.get("hits", []))
        kg_context = self._format_kg_context(kg_search)
        system = (
            "你是面向中国 AI 科创企业的数据合规与特有风险管理智能体。"
            "必须基于 MCP 工具返回的法规、案例和知识图谱材料回答。"
            "每条关键结论尽量标注依据编号，例如[法1][案1]。"
            "如果材料不足，要明确说明不确定性，不能编造法条、案例或事实。"
            "回答结构固定为：一、结论；二、主要风险；三、法律与类案依据；四、整改建议。"
        )
        route_hint = (
            f"路由 Agent：{route['agent']['title']}；"
            f"路由原因：{route['route_reason']}；"
            f"可用 Skills：{', '.join(s['title'] for s in route['skills'])}"
        )
        user = (
            f"{route_hint}\n\n法规依据：\n{context}\n\n"
            f"类案依据：\n{case_context}\n\n"
            f"知识图谱关系：\n{kg_context}\n\n"
            f"用户问题：{question}"
        )
        draft = _deepseek_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        return {
            "answer": draft,
            "sources": [self._hit_to_dict(h) for h in hits],
            "case_sources": case_search.get("hits", []),
            "kg_relations": kg_search.get("relations", []),
            "agent_route": route["agent"],
            "route_reason": route["route_reason"],
            "skills_used": route["skills"],
            "mcp_trace": route["mcp_trace"] + self.mcp_client.pop_trace(),
        }

    def audit_text(self, text: str, filename: str = "文本输入") -> dict[str, Any]:
        clean = normalize_text(text)
        route = self.router.route_material(clean)
        audit = self.mcp_client.call_tool(
            "risk.scenario_audit",
            {"text": clean, "filename": filename, "legal_k": 4, "case_k": 3},
        )
        risks = list(audit.get("risks") or [])
        overall = str(audit.get("overall_level") or self._overall_level(risks))
        mcp_trace = route["mcp_trace"] + self.mcp_client.pop_trace()
        return {
            "filename": filename,
            "overall_level": overall,
            "risk_count": int(audit.get("risk_count") or len(risks)),
            "risks": risks,
            "summary": self._draft_audit_summary(filename, clean, risks, overall),
            "agent_route": route["agent"],
            "route_reason": route["route_reason"],
            "skills_used": route["skills"],
            "mcp_trace": mcp_trace,
            "mcp_tools_used": audit.get("tools_used", []),
            "case_library": audit.get("case_library", {}),
            "knowledge_graph": audit.get("knowledge_graph", {}),
        }

    def _draft_audit_summary(self, filename: str, text: str, risks: list[dict[str, Any]], overall: str) -> str:
        compact = []
        for risk in risks[:8]:
            legal = "；".join([f"{b.get('title')}[{i + 1}]" for i, b in enumerate(risk.get("legal_basis", [])[:2])])
            cases = "；".join([f"{b.get('title')}[{i + 1}]" for i, b in enumerate(risk.get("case_basis", [])[:2])])
            compact.append(
                f"{risk.get('severity')}｜{risk.get('title')}｜依据：{legal or '暂无'}｜"
                f"类案：{cases or '暂无'}｜建议：{risk.get('recommendation', '')}"
            )
        prompt = (
            f"文件名：{filename}\n"
            f"总体评级：{overall}\n"
            f"材料摘要：{text[:2200]}\n"
            f"识别风险：\n" + "\n".join(compact) +
            "\n请生成正式但简洁的合规审查摘要，包含总体评级、重点风险、整改优先级和下一步材料补充清单。"
        )
        return _deepseek_chat([
            {"role": "system", "content": "你是企业数据合规审查报告助手，输出中文，语气正式，避免夸大结论。"},
            {"role": "user", "content": prompt},
        ])

    @staticmethod
    def _format_context(hits: list[RetrievedChunk]) -> str:
        return "\n".join([
            f"[法{i}] {h.title}（{h.level}，chunk {h.chunk_id}，score {h.score:.3f}）\n{h.text}\n来源：{h.source_url}"
            for i, h in enumerate(hits, start=1)
        ]) or "未检索到法规依据。"

    @staticmethod
    def _format_case_context(hits: list[dict[str, Any]]) -> str:
        return "\n".join([
            f"[案{i}] {h.get('title', '')}（{h.get('case_no', '')}，{h.get('cause', '')}）\n{h.get('text', '')}"
            for i, h in enumerate(hits, start=1)
        ]) or "未检索到类案依据。"

    @staticmethod
    def _format_kg_context(result: dict[str, Any]) -> str:
        nodes = result.get("nodes", [])[:5]
        relations = result.get("relations", [])[:8]
        if not nodes and not relations:
            return "未检索到知识图谱关系。"
        return f"相关节点：{nodes}\n相关关系：{relations}"

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

    @staticmethod
    def _dict_to_hit(item: dict[str, Any]) -> RetrievedChunk:
        return RetrievedChunk(
            title=str(item.get("title", "")),
            level=str(item.get("level", "")),
            source_url=str(item.get("source_url", "")),
            text=str(item.get("text", "")),
            score=float(item.get("score", 0)),
            source_file=str(item.get("source_file", "")),
            chunk_id=int(item.get("chunk_id", 0)),
        )

    @staticmethod
    def _overall_level(risks: list[dict[str, Any]]) -> str:
        levels = [str(r.get("severity", "")) for r in risks]
        if "高" in levels:
            return "高风险"
        if "中" in levels:
            return "中风险"
        return "低风险"
