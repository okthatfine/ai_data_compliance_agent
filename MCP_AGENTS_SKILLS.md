# MCP、Skills 与 LangGraph 多 Agent 路由设计

本项目新增一层 LangGraph 工具编排能力，用于答辩展示“智能体不是单一路径问答，而是根据任务选择工具和专家 Agent”。

## 结构

```text
FastAPI API
  -> LangGraph StateGraph
  -> LocalMCPClient
  -> MCPToolServer
  -> RAG / 风险规则 / 数据库 / Skills 注册表
```

LangGraph 图节点：

```text
START
  -> classify
  -> select_skills
  -> call_mcp_tools
  -> finalize
  -> END
```

## MCP Server

项目内置 MCP-compatible JSON server，不需要另起进程：

- `GET /api/mcp/manifest`：查看工具清单。
- `POST /api/mcp/call`：调用工具。

工具列表：

- `legal.policy_search`
- `compliance.risk_scan`
- `system.db_status`
- `skills.catalog`

## MCP Client

`app/mcp_client.py` 提供 `LocalMCPClient`，Agent 不直接调用数据库或 RAG，而是通过统一的 `call_tool()` 入口调用 MCP 工具，并记录 `mcp_trace`。

## Skills

`skills/` 目录存放可复用能力说明，`app/skills.py` 提供可被前端、Agent Router 和 MCP 工具复用的注册表。

当前 Skills：

- 法律政策语义检索
- 企业材料风险审查
- 数据出境专项审查
- 生成合成内容标识审查
- 系统治理状态检查

## 多 Agent 路由

`app/multi_agent.py` 使用 LangGraph `StateGraph` 根据问题或材料中的关键词选择专家 Agent：

- 法律政策检索 Agent
- 企业材料审查 Agent
- 数据出境 Agent
- 生成合成内容标识 Agent
- 系统治理 Agent

问答和审查接口会返回：

- `agent_route`
- `route_reason`
- `skills_used`
- `mcp_trace`

前端工作台会展示 Agent 数量、MCP 工具数量、Skills 数量和最近路由结果。
