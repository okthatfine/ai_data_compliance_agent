from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .rag import PolicyVectorStore, RetrievedChunk, normalize_text

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RISK_RULES = [
    {"name": "训练数据合法来源不足", "keywords": ["爬取", "抓取", "公开网页", "论坛", "新闻", "预训练", "训练数据", "语料", "数据集"], "severity": "高", "query": "生成式人工智能 训练数据 合法来源 知识产权 个人信息", "suggestion": "建立训练数据来源台账，记录授权、公开许可、robots/平台规则、去标识化与过滤流程；对含个人信息或版权内容的数据集设置准入审查。"},
    {"name": "个人信息处理告知与同意不足", "keywords": ["个人信息", "手机号", "身份证", "位置", "设备信息", "日志", "默认同意", "隐私政策", "敏感个人信息"], "severity": "高", "query": "个人信息处理 告知 同意 必要原则 撤回同意 敏感个人信息", "suggestion": "补充清晰的处理目的、方式、范围、保存期限和撤回路径；将非必要处理与基础服务解绑，避免默认勾选或捆绑授权。"},
    {"name": "数据出境路径不明确", "keywords": ["境外", "海外", "跨境", "出境", "国外服务器", "全球团队", "海外供应商"], "severity": "高", "query": "个人信息 数据出境 安全评估 标准合同 认证 境外接收方", "suggestion": "识别出境数据类型、规模、接收方和目的，判断是否触发安全评估、标准合同或认证，并在告知文本中披露境外接收方信息。"},
    {"name": "重要数据识别与网络数据安全制度不足", "keywords": ["重要数据", "核心数据", "网络数据", "分类分级", "数据处理活动", "数据安全负责人"], "severity": "中", "query": "网络数据安全管理条例 重要数据 申报 分类分级 风险评估", "suggestion": "建立网络数据处理活动台账和分类分级规则；对可能属于重要数据的目录、来源、流向和安全措施进行专项识别并保留评估记录。"},
    {"name": "自动化决策透明度不足", "keywords": ["自动化决策", "画像", "个性化推荐", "算法推荐", "差别定价", "精准营销"], "severity": "中", "query": "自动化决策 透明度 公平公正 算法推荐 关闭选项", "suggestion": "向用户说明自动化决策逻辑和影响，提供不针对个人特征的选项或关闭入口，并建立人工复核与申诉机制。"},
    {"name": "AI生成合成内容标识义务缺失", "keywords": ["生成内容", "合成内容", "AIGC", "深度合成", "水印", "标识", "虚拟人", "AI生成"], "severity": "中", "query": "人工智能生成合成内容标识办法 显式标识 隐式标识", "suggestion": "对文本、图片、音视频、虚拟场景等生成合成内容配置显式标识和必要的元数据隐式标识，并在用户发布、传播、下载环节保留标识提示。"},
    {"name": "人脸信息与生物识别数据处理依据不足", "keywords": ["人脸", "刷脸", "生物识别", "面部识别", "摄像头", "活体检测"], "severity": "高", "query": "人脸识别技术应用安全管理办法 人脸信息 单独同意 必要性", "suggestion": "明确人脸识别的必要性和替代方式，取得单独同意，限制采集范围和保存期限；研发训练场景也应落实去标识化、访问控制和安全评估。"},
    {"name": "个人信息保护合规审计机制不足", "keywords": ["合规审计", "审计", "个人信息处理者", "处理活动记录", "委托审计"], "severity": "中", "query": "个人信息保护合规审计管理办法 定期审计 专业机构", "suggestion": "建立个人信息处理活动定期合规审计机制，明确内部责任部门、审计频次、审计问题整改闭环和外部专业机构选聘标准。"},
    {"name": "第三方共享或委托处理约束不足", "keywords": ["第三方", "供应商", "外包", "共享", "委托处理", "SDK", "合作伙伴"], "severity": "中", "query": "个人信息 委托处理 第三方共享 数据安全 管理制度", "suggestion": "与第三方签署数据处理协议，约定处理目的、期限、权限、安全措施、再委托限制和删除返还机制，并开展供应商安全评估。"},
    {"name": "数据安全技术与组织措施不足", "keywords": ["权限", "泄露", "加密", "备份", "访问控制", "日志审计", "安全负责人", "漏洞"], "severity": "中", "query": "数据安全 管理制度 分类分级 风险评估 技术措施", "suggestion": "建立访问控制、加密、日志审计、备份恢复和事件响应制度；对重要系统和数据处理活动定期开展安全评估。"},
]


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

    def answer(self, question: str) -> dict[str, Any]:
        hits = self.store.search(question, k=6)
        context = self._format_context(hits)
        system = "你是面向中国 AI 科创企业的数据合规法律智能体。必须使用检索材料编号引用依据，例如[1][2]。回答结构固定为：一、结论；二、主要风险；三、法律依据；四、整改建议。若材料不足，要明确说明不确定性，不能编造条文编号。"
        user = f"检索材料：\n{context}\n\n用户问题：{question}"
        draft = _deepseek_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        return {"answer": draft, "sources": [self._hit_to_dict(h) for h in hits]}

    def audit_text(self, text: str, filename: str = "文本输入") -> dict[str, Any]:
        clean = normalize_text(text)
        risks = []
        lower = clean.lower()
        for rule in RISK_RULES:
            matched = [kw for kw in rule["keywords"] if kw.lower() in lower]
            if not matched:
                continue
            hits = self.store.search(rule["query"] + " " + " ".join(matched), k=4)
            risks.append({
                "title": rule["name"],
                "severity": rule["severity"],
                "matched_keywords": matched,
                "excerpt": self._find_excerpt(clean, matched),
                "legal_basis": [self._hit_to_dict(h) for h in hits],
                "recommendation": rule["suggestion"],
            })
        if not risks:
            hits = self.store.search("数据安全 个人信息保护 合规义务 AI 科创企业", k=4)
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
        return {"filename": filename, "overall_level": overall, "risk_count": len(risks), "risks": risks, "summary": self._draft_audit_summary(filename, clean, risks, overall)}

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