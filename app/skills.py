from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ComplianceSkill:
    name: str
    title: str
    description: str
    tools: tuple[str, ...]
    triggers: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


SKILLS: tuple[ComplianceSkill, ...] = (
    ComplianceSkill(
        name="legal_policy_retrieval",
        title="法律政策语义检索",
        description="面向数据合规政策、法条和监管文件执行 embedding RAG 检索，并返回可引用依据。",
        tools=("legal.policy_search",),
        triggers=("法律", "法规", "依据", "条款", "政策", "问答", "RAG"),
    ),
    ComplianceSkill(
        name="enterprise_material_audit",
        title="企业材料风险审查",
        description="识别企业材料中的训练数据、个人信息、数据出境、第三方共享等数据合规风险。",
        tools=("risk.scenario_audit", "risk.rule_scan", "legal.policy_search", "case.risk_case_search"),
        triggers=("审查", "材料", "风险", "上传", "合规审计", "整改"),
    ),
    ComplianceSkill(
        name="cross_border_data_transfer",
        title="数据出境专项审查",
        description="针对境外供应商、海外团队、跨境同步日志和个人信息等场景生成合规路径建议。",
        tools=("risk.scenario_audit", "risk.rule_scan", "legal.policy_search", "case.risk_case_search"),
        triggers=("出境", "跨境", "境外", "海外", "国外", "标准合同", "安全评估"),
    ),
    ComplianceSkill(
        name="aigc_content_labeling",
        title="生成合成内容标识审查",
        description="检查 AI 文本、图片、音视频、虚拟人等生成合成内容的显式和隐式标识义务。",
        tools=("risk.scenario_audit", "risk.rule_scan", "legal.policy_search", "case.risk_case_search"),
        triggers=("AIGC", "生成内容", "合成内容", "水印", "标识", "深度合成", "虚拟人"),
    ),
    ComplianceSkill(
        name="governance_status_check",
        title="系统治理状态检查",
        description="查询知识库、数据库、上传记录、审查报告等系统运行状态，辅助 Demo 运维展示。",
        tools=("system.status", "skills.catalog"),
        triggers=("数据库", "状态", "知识库", "运行", "MCP", "skills", "agents"),
    ),
)


def list_skills() -> list[dict]:
    return [skill.to_dict() for skill in SKILLS]


def select_skills(text: str, limit: int = 3) -> list[dict]:
    lowered = text.lower()
    scored: list[tuple[int, ComplianceSkill]] = []
    for skill in SKILLS:
        score = sum(1 for trigger in skill.triggers if trigger.lower() in lowered)
        if score:
            scored.append((score, skill))
    scored.sort(key=lambda item: (-item[0], item[1].name))
    selected = [skill.to_dict() for _, skill in scored[:limit]]
    return selected or [SKILLS[0].to_dict()]
