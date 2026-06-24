from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from .mcp_client import LocalMCPClient
from .skills import list_skills, select_skills


@dataclass(frozen=True)
class AgentProfile:
    name: str
    title: str
    description: str
    skills: tuple[str, ...]
    triggers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


AGENTS: tuple[AgentProfile, ...] = (
    AgentProfile(
        name="legal_research_agent",
        title="法律政策检索 Agent",
        description="负责法规语义检索、依据引用和法律问答。",
        skills=("legal_policy_retrieval",),
        triggers=("法律", "法规", "依据", "政策", "条款", "问答", "RAG"),
    ),
    AgentProfile(
        name="material_audit_agent",
        title="企业材料审查 Agent",
        description="负责企业材料中的数据合规风险识别、分级和整改建议。",
        skills=("enterprise_material_audit", "legal_policy_retrieval"),
        triggers=("审查", "材料", "风险", "整改", "上传", "合规审计"),
    ),
    AgentProfile(
        name="cross_border_agent",
        title="数据出境 Agent",
        description="负责跨境传输、境外接收方、安全评估、标准合同和认证路径判断。",
        skills=("cross_border_data_transfer", "legal_policy_retrieval"),
        triggers=("出境", "跨境", "境外", "海外", "国外", "标准合同", "安全评估"),
    ),
    AgentProfile(
        name="aigc_label_agent",
        title="生成合成内容标识 Agent",
        description="负责 AIGC、深度合成、水印、显式标识和隐式标识义务审查。",
        skills=("aigc_content_labeling", "legal_policy_retrieval"),
        triggers=("AIGC", "生成内容", "合成内容", "水印", "标识", "深度合成", "虚拟人"),
    ),
    AgentProfile(
        name="governance_agent",
        title="系统治理 Agent",
        description="负责系统状态、知识库状态、数据库状态和工具目录说明。",
        skills=("governance_status_check",),
        triggers=("数据库", "状态", "知识库", "运行", "MCP", "skills", "agents", "工具"),
    ),
)


class AgentGraphState(TypedDict, total=False):
    mode: Literal["question", "material"]
    content: str
    agent: dict[str, Any]
    skills: list[dict[str, Any]]
    route_reason: str
    tool_results: dict[str, Any]
    mcp_trace: list[dict[str, Any]]


class MultiAgentRouter:
    def __init__(self, client: LocalMCPClient):
        self.client = client
        self.graph = self._build_graph()

    def status(self) -> dict[str, Any]:
        return {
            "agents": [agent.to_dict() for agent in AGENTS],
            "skills": list_skills(),
            "mcp": self.client.manifest(),
            "framework": "langgraph",
            "graph_nodes": ["classify", "select_skills", "call_mcp_tools", "finalize"],
        }

    def route_question(self, question: str) -> dict[str, Any]:
        return self.graph.invoke({"mode": "question", "content": question})

    def route_material(self, text: str) -> dict[str, Any]:
        return self.graph.invoke({"mode": "material", "content": text})

    def _build_graph(self):
        graph = StateGraph(AgentGraphState)
        graph.add_node("classify", self._classify_node)
        graph.add_node("select_skills", self._skills_node)
        graph.add_node("call_mcp_tools", self._tools_node)
        graph.add_node("finalize", self._finalize_node)
        graph.add_edge(START, "classify")
        graph.add_edge("classify", "select_skills")
        graph.add_edge("select_skills", "call_mcp_tools")
        graph.add_edge("call_mcp_tools", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _classify_node(self, state: AgentGraphState) -> dict[str, Any]:
        default = "material_audit_agent" if state.get("mode") == "material" else "legal_research_agent"
        content = state.get("content", "")
        agent = self._select_agent(content, default=default)
        return {"agent": agent.to_dict(), "route_reason": self._route_reason(content, agent)}

    @staticmethod
    def _skills_node(state: AgentGraphState) -> dict[str, Any]:
        return {"skills": select_skills(state.get("content", ""))}

    def _tools_node(self, state: AgentGraphState) -> dict[str, Any]:
        content = state.get("content", "")
        mode = state.get("mode", "question")
        agent_name = state.get("agent", {}).get("name", "")
        tool_results: dict[str, Any] = {}
        if mode == "material":
            tool_results["risk_scan"] = self.client.call_tool("compliance.risk_scan", {"text": content})
        else:
            if agent_name == "governance_agent":
                tool_results["db_status"] = self.client.call_tool("system.db_status", {})
                tool_results["skills"] = self.client.call_tool("skills.catalog", {})
            tool_results["policy_search"] = self.client.call_tool("legal.policy_search", {"query": content, "k": 6})
        return {"tool_results": tool_results, "mcp_trace": self.client.pop_trace()}

    @staticmethod
    def _finalize_node(state: AgentGraphState) -> dict[str, Any]:
        return {
            "agent": state.get("agent", {}),
            "skills": state.get("skills", []),
            "route_reason": state.get("route_reason", ""),
            "tool_results": state.get("tool_results", {}),
            "mcp_trace": state.get("mcp_trace", []),
        }

    @staticmethod
    def _select_agent(text: str, default: str) -> AgentProfile:
        lowered = text.lower()
        scored: list[tuple[int, AgentProfile]] = []
        for agent in AGENTS:
            score = sum(1 for trigger in agent.triggers if trigger.lower() in lowered)
            if score:
                scored.append((score, agent))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        if scored:
            return scored[0][1]
        return next(agent for agent in AGENTS if agent.name == default)

    @staticmethod
    def _route_reason(text: str, agent: AgentProfile) -> str:
        matched = [trigger for trigger in agent.triggers if trigger.lower() in text.lower()]
        if matched:
            return f"命中关键词：{', '.join(matched[:5])}"
        return "未命中特定专项关键词，使用默认合规 Agent。"
