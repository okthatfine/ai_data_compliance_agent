from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .mcp_client import LocalMCPClient
from .multi_agent import MultiAgentRouter
from .rag import PolicyVectorStore, RetrievedChunk, normalize_text
from .rules import RISK_RULES

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _deepseek_chat(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    if not api_key:
        return "未配置 DEEPSEEK_API_KEY，以下为本地规则引擎生成的初步意见。"
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
    """LangChain LLM + RAG retrieval + risk-rule routing agent."""

    def __init__(self) -> None:
        self.store = PolicyVectorStore()
        self.mcp_client = LocalMCPClient(self.store)
        self.router = MultiAgentRouter(self.mcp_client)

    def answer(self, question: str) -> dict[str, Any]:
        route = self.router.route_question(question)
        hits = [self._dict_to_hit(item) for item in route["tool_results"]["policy_search"]["hits"]]
        context = self._format_context(hits)
        system = "你是面向中国 AI 科创企业的数据合规法律智能体。必须使用检索材料编号引用依据，例如[1][2]。回答结构固定为：一、结论；二、主要风险；三、法律依据；四、整改建议。若材料不足，要明确说明不确定性，不能编造条文编号。"
        route_hint = f"路由 Agent：{route['agent']['title']}；路由原因：{route['route_reason']}；可用 Skills：{', '.join(s['title'] for s in route['skills'])}"
        user = f"{route_hint}\n\n检索材料：\n{context}\n\n用户问题：{question}"
        draft = _deepseek_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        return {
            "answer": draft,
            "sources": [self._hit_to_dict(h) for h in hits],
            "agent_route": route["agent"],
            "route_reason": route["route_reason"],
            "skills_used": route["skills"],
            "mcp_trace": route["mcp_trace"],
        }

    def audit_text(self, text: str, filename: str = "文本输入") -> dict[str, Any]:
        clean = normalize_text(text)
        route = self.router.route_material(clean)
        risks = []
        lower = clean.lower()
        for rule in RISK_RULES:
            matched = [kw for kw in rule["keywords"] if kw.lower() in lower]
            if not matched:
                continue
            search = self.mcp_client.call_tool("legal.policy_search", {"query": rule["query"] + " " + " ".join(matched), "k": 4})
            hits = [self._dict_to_hit(item) for item in search["hits"]]
            risks.append({
                "title": rule["name"],
                "severity": rule["severity"],
                "matched_keywords": matched,
                "excerpt": self._find_excerpt(clean, matched),
                "legal_basis": [self._hit_to_dict(h) for h in hits],
                "recommendation": rule["suggestion"],
            })
        if not risks:
            search = self.mcp_client.call_tool("legal.policy_search", {"query": "数据安全 个人信息保护 合规义务 AI 科创企业", "k": 4})
            hits = [self._dict_to_hit(item) for item in search["hits"]]
            risks.append({
                "title": "未发现显著关键词风险，建议进行人工复核",
                "severity": "低",
                "matched_keywords": [],
                "excerpt": clean[:320],
                "legal_basis": [self._hit_to_dict(h) for h in hits],
                "recommendation": "补充业务流程、数据流向、供应商和系统权限材料后复核；当前文本未出现明显高频数据合规风险表述。",
            })
        risks.sort(key=lambda r: {"高": 0, "中": 1, "低": 2}.get(r["severity"], 3))
        overall = self._overall_level(risks)
        mcp_trace = route["mcp_trace"] + self.mcp_client.pop_trace()
        return {
            "filename": filename,
            "overall_level": overall,
            "risk_count": len(risks),
            "risks": risks,
            "summary": self._draft_audit_summary(filename, clean, risks, overall),
            "agent_route": route["agent"],
            "route_reason": route["route_reason"],
            "skills_used": route["skills"],
            "mcp_trace": mcp_trace,
        }

    def _draft_audit_summary(self, filename: str, text: str, risks: list[dict[str, Any]], overall: str) -> str:
        compact = []
        for risk in risks[:8]:
            basis = "；".join([f"{b['title']}[{i+1}]" for i, b in enumerate(risk["legal_basis"][:2])])
            compact.append(f"{risk['severity']}｜{risk['title']}｜依据：{basis}｜建议：{risk['recommendation']}")
        prompt = f"文件名：{filename}\n总体评级：{overall}\n材料摘要：{text[:2200]}\n识别风险：\n" + "\n".join(compact) + "\n请生成正式但简洁的合规审查摘要，包含总体评级、重点风险、整改优先级和下一步材料补充清单。"
        return _deepseek_chat([{"role": "system", "content": "你是企业数据合规审查报告助手，输出中文，语气正式，避免夸大结论。"}, {"role": "user", "content": prompt}])

    @staticmethod
    def _format_context(hits: list[RetrievedChunk]) -> str:
        return "\n".join([f"[{i}] {h.title}（{h.level}，chunk {h.chunk_id}，score {h.score:.3f}）\n{h.text}\n来源：{h.source_url}" for i, h in enumerate(hits, start=1)])

    @staticmethod
    def _hit_to_dict(hit: RetrievedChunk) -> dict[str, Any]:
        return {"title": hit.title, "level": hit.level, "source_url": hit.source_url, "text": hit.text, "score": round(hit.score, 4), "source_file": hit.source_file, "chunk_id": hit.chunk_id}

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
    def _find_excerpt(text: str, keywords: list[str]) -> str:
        lower = text.lower()
        positions = [lower.find(k.lower()) for k in keywords if lower.find(k.lower()) >= 0]
        start = max(0, min(positions) - 100) if positions else 0
        return text[start:start + 420]

    @staticmethod
    def _overall_level(risks: list[dict[str, Any]]) -> str:
        levels = [r["severity"] for r in risks]
        if "高" in levels:
            return "高风险"
        if "中" in levels:
            return "中风险"
        return "低风险"
