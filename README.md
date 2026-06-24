# AI 科创企业数据合规智能系统

面向“科创企业风险的识别与管理”选题的法律合规智能 Demo，聚焦 AI 科创企业的数据合规场景。

## 功能

- 数据合规专题知识库：默认接入官方法律政策种子库，并支持在前端上传团队整理的 JSON 政策文件后自动重建索引。
- RAG 法律政策问答：使用 `BAAI/bge-small-zh-v1.5` 中文 embedding 语义向量检索，返回答案、依据片段、来源 URL、相似度和 chunk 编号；模型不可用时自动回退 TF-IDF。
- 企业材料分析：支持 TXT、PDF、DOCX 上传，识别训练数据、个人信息、数据出境、自动化决策、AI 内容标识、人脸识别、第三方共享等风险。
- 风险分级与整改建议：高/中/低风险分级，输出法律依据和建议。
- MCP 工具层：内置 `/api/mcp/manifest` 和 `/api/mcp/call`，提供法规检索、风险扫描、数据库状态、Skills 目录等工具。
- LangGraph 多 Agent 路由：使用 `StateGraph` 按任务自动路由到法律政策检索、企业材料审查、数据出境、AIGC 标识、系统治理等 Agent。
- 可复用 Skills：`skills/` 目录保存可复用能力说明，后端 `app/skills.py` 提供统一注册表。
- 报告生成：可导出 PDF 合规审查报告。
- 前后端一体部署：FastAPI 提供 API 和静态前端。

## 快速启动

```bash
cd /mnt/data2/lzh/ai_data_compliance_agent
.venv/bin/python scripts/build_kb.py
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8018
```

本机已通过 SSH 转发访问：`http://127.0.0.1:8018/`

## MCP / Skills / LangGraph 多 Agent

系统内置轻量 MCP-compatible JSON 工具服务，并使用 LangGraph `StateGraph` 编排 Agent 路由：

```bash
curl http://127.0.0.1:8018/api/mcp/manifest
curl http://127.0.0.1:8018/api/agents/status
curl -X POST http://127.0.0.1:8018/api/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"name":"legal.policy_search","arguments":{"query":"数据出境安全评估","k":3}}'
```

当前 MCP tools：

- `legal.policy_search`：调用 embedding RAG 检索法规依据。
- `compliance.risk_scan`：扫描企业材料中的合规风险关键词。
- `system.db_status`：查询数据库、法规、报告和上传记录状态。
- `skills.catalog`：列出可复用 Skills。

当前 LangGraph 节点：

- `classify`
- `select_skills`
- `call_mcp_tools`
- `finalize`

当前 Agent：

- 法律政策检索 Agent
- 企业材料审查 Agent
- 数据出境 Agent
- 生成合成内容标识 Agent
- 系统治理 Agent

## 配置

`.env` 中配置 DeepSeek API，不要提交或公开该文件。

```bash
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
```

## 团队政策文件格式

前端“政策知识库”页可上传 JSON。格式示例：

```json
[
  {
    "title": "某数据合规政策",
    "level": "团队资料",
    "source_url": "https://example.com/source",
    "chunks": ["第一段政策内容", "第二段政策内容"]
  }
]
```

## 已接入的官方政策法规

- 《中华人民共和国个人信息保护法》
- 《中华人民共和国数据安全法》
- 《中华人民共和国网络安全法》
- 《网络数据安全管理条例》
- 《个人信息保护合规审计管理办法》
- 《生成式人工智能服务管理暂行办法》
- 《人工智能生成合成内容标识办法》
- 《数据出境安全评估办法》
- 《促进和规范数据跨境流动规定》
- 《互联网信息服务算法推荐管理规定》
- 《互联网信息服务深度合成管理规定》
- 《人脸识别技术应用安全管理办法》

## 开源知识库来源调研

未找到成熟的“AI 数据合规现成向量库”。当前采用“官方来源种子库 + 可上传团队资料 + 本地可复建向量索引”的方案。可继续扩展的资源包括 `twang2218/law-datasets`、`lawtext/law-book`、`Ansvar-Systems/chinese-law-mcp`。

本系统用于竞赛 Demo 和合规辅助，不替代律师正式法律意见。
