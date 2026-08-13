from __future__ import annotations

from typing import Any

from .rag import normalize_text

RISK_RULES: list[dict[str, Any]] = [
    {
        "risk_type": "RISK-DATA",
        "name": "训练数据合法来源不足",
        "keywords": ["抓取", "爬取", "公开网页", "论坛", "语料", "训练数据", "数据集", "预训练", "微调"],
        "severity": "高",
        "query": "生成式人工智能 训练数据 合法来源 知识产权 个人信息",
        "suggestion": "建立训练数据来源台账，记录授权、公开许可、平台规则、去标识化和过滤流程；对含个人信息或版权内容的数据集设置准入审查。",
    },
    {
        "risk_type": "RISK-DATA",
        "name": "个人信息处理告知与同意不足",
        "keywords": ["个人信息", "手机号", "身份证", "位置", "设备信息", "日志", "默认同意", "隐私政策", "敏感个人信息"],
        "severity": "高",
        "query": "个人信息处理 告知 同意 必要原则 敏感个人信息",
        "suggestion": "补充处理目的、方式、范围、保存期限和撤回路径；敏感个人信息应说明必要性并取得单独同意。",
    },
    {
        "risk_type": "RISK-GEO",
        "name": "数据出境路径不明确",
        "keywords": ["境外", "海外", "跨境", "出境", "国外服务器", "全球团队", "海外供应商"],
        "severity": "高",
        "query": "个人信息 数据出境 安全评估 标准合同 认证 境外接收方",
        "suggestion": "识别出境数据类型、规模、接收方和目的，判断是否触发安全评估、标准合同或认证，并在告知文本中披露境外接收方信息。",
    },
    {
        "risk_type": "RISK-DATA",
        "name": "重要数据识别与数据安全制度不足",
        "keywords": ["重要数据", "核心数据", "网络数据", "分类分级", "数据处理活动", "数据安全负责人"],
        "severity": "中",
        "query": "网络数据安全 重要数据 申报 分类分级 风险评估",
        "suggestion": "建立数据处理活动台账和分类分级规则；对可能属于重要数据的目录、来源、流向和安全措施进行专项识别并保留评估记录。",
    },
    {
        "risk_type": "RISK-ALGO",
        "name": "自动化决策透明度不足",
        "keywords": ["自动化决策", "画像", "个性化推荐", "算法推荐", "差别定价", "精准营销"],
        "severity": "中",
        "query": "自动化决策 透明度 公平公正 算法推荐 关闭选项",
        "suggestion": "向用户说明自动化决策逻辑和影响，提供非个性化选项、关闭入口、人工复核和申诉机制。",
    },
    {
        "risk_type": "RISK-ALGO",
        "name": "AI生成合成内容标识义务缺失",
        "keywords": ["生成内容", "合成内容", "AIGC", "深度合成", "水印", "标识", "虚拟人", "AI生成"],
        "severity": "中",
        "query": "人工智能 生成合成内容 标识 显式标识 隐式标识",
        "suggestion": "对文本、图片、音视频、虚拟场景等生成合成内容配置显式标识和必要的元数据隐式标识，并在发布、传播、下载环节保留标识提示。",
    },
    {
        "risk_type": "RISK-DATA",
        "name": "人脸信息与生物识别数据处理依据不足",
        "keywords": ["人脸", "刷脸", "生物识别", "面部识别", "摄像头", "活体检测"],
        "severity": "高",
        "query": "人脸识别 人脸信息 单独同意 必要性 安全管理",
        "suggestion": "明确人脸识别的必要性和替代方案，取得单独同意，限制采集范围和保存期限；研发训练场景也应落实去标识化、访问控制和安全评估。",
    },
    {
        "risk_type": "RISK-DATA",
        "name": "第三方共享或委托处理约束不足",
        "keywords": ["第三方", "供应商", "外包", "共享", "委托处理", "SDK", "合作伙伴"],
        "severity": "中",
        "query": "个人信息 委托处理 第三方共享 数据安全 管理制度",
        "suggestion": "与第三方签署数据处理协议，约定处理目的、期限、权限、安全措施、再委托限制和删除返还机制，并开展供应商安全评估。",
    },
    {
        "risk_type": "RISK-TECH",
        "name": "数据安全技术与组织措施不足",
        "keywords": ["权限", "泄露", "加密", "备份", "访问控制", "日志审计", "安全负责人", "漏洞"],
        "severity": "中",
        "query": "数据安全 管理制度 分类分级 风险评估 技术措施",
        "suggestion": "建立访问控制、加密、日志审计、备份恢复和事件响应制度；对重要系统和数据处理活动定期开展安全评估。",
    },
    {
        "risk_type": "RISK-IP",
        "name": "知识产权与商业秘密保护不足",
        "keywords": ["专利", "著作权", "开源协议", "商业秘密", "源代码", "模型权重", "技术秘密", "职务发明"],
        "severity": "中",
        "query": "知识产权 商业秘密 开源协议 模型训练 著作权 专利",
        "suggestion": "建立开源组件和数据授权审查流程，明确研发成果权属、商业秘密分级保护、访问权限和离职交接机制。",
    },
    {
        "risk_type": "RISK-HR",
        "name": "核心人员流动与竞业保密风险",
        "keywords": ["竞业限制", "竞业禁止", "保密协议", "离职", "核心员工", "股权激励", "客户资源"],
        "severity": "中",
        "query": "劳动合同 竞业限制 保密协议 商业秘密 股权激励",
        "suggestion": "明确保密义务、竞业限制范围期限和补偿机制，对核心研发人员设置代码、数据和客户资源交接清单。",
    },
    {
        "risk_type": "RISK-FIN",
        "name": "融资协议与对赌安排风险",
        "keywords": ["融资", "对赌", "估值调整", "股权回购", "增资", "天使轮", "股东出资"],
        "severity": "中",
        "query": "公司法 融资 对赌协议 股权回购 增资 股东出资",
        "suggestion": "审查估值调整、回购、优先权、信息披露和创始人责任条款，避免触发无效或过度约束经营的安排。",
    },
    {
        "risk_type": "RISK-MKT",
        "name": "市场竞争与不正当竞争风险",
        "keywords": ["不正当竞争", "商业诋毁", "爬虫", "反垄断", "流量劫持", "混淆", "虚假宣传"],
        "severity": "中",
        "query": "反不正当竞争 反垄断 商业诋毁 数据爬取 虚假宣传",
        "suggestion": "规范数据获取、营销宣传和竞品比较行为，避免商业诋毁、混淆宣传、流量劫持和滥用市场优势。",
    },
    {
        "risk_type": "RISK-REG",
        "name": "监管备案与安全评估义务缺失",
        "keywords": ["备案", "安全评估", "算法备案", "生成式人工智能服务", "行政许可", "行政处罚", "合规审计"],
        "severity": "高",
        "query": "生成式人工智能服务 算法备案 安全评估 合规审计 行政处罚",
        "suggestion": "识别产品是否属于生成式人工智能服务、算法推荐、深度合成或数据出境场景，建立备案、评估、审计和整改闭环。",
    },
]


def scan_risk_rules(text: str) -> list[dict[str, Any]]:
    clean = normalize_text(text)
    lower = clean.lower()
    hits: list[dict[str, Any]] = []
    for rule in RISK_RULES:
        matched = [kw for kw in rule["keywords"] if kw.lower() in lower]
        if matched:
            hits.append({
                "risk_type": rule["risk_type"],
                "name": rule["name"],
                "severity": rule["severity"],
                "matched_keywords": matched,
                "query": rule["query"],
                "suggestion": rule["suggestion"],
            })
    hits.sort(key=lambda r: {"高": 0, "中": 1, "低": 2}.get(str(r["severity"]), 3))
    return hits
