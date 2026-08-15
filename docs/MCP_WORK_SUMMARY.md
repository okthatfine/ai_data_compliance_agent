# MCP 模块工作说明

## 一、目标

本次 MCP 改造的核心，不是把本地小数据库包装成 MCP，而是把项目的检索依据切换到北大法宝 MCP。

改造前，系统主要依赖本地法规库、案例库和规则库，数据量少，只适合演示。改造后：

1. `legal.policy_search` 优先查询北大法宝法规资源；
2. `case.risk_case_search` 优先查询北大法宝案例资源；
3. `risk.rule_scan`、`risk.scenario_audit`、`kg.relation_search`、`report.audit_generate` 继续保留在项目内部，形成完整审查链路；
4. 本地小库只作为兜底和演示缓存，不再作为主数据源。

## 二、完成内容

### 1. MCP 工具层统一

在 `app/mcp_server.py` 中保留并统一了以下工具名：

| 工具名 | 作用 |
| --- | --- |
| `legal.policy_search` | 检索法规、政策和依据 |
| `case.risk_case_search` | 检索科创企业风险案例 |
| `risk.rule_scan` | 扫描企业材料中的风险信号 |
| `risk.scenario_audit` | 综合风险扫描、法规检索、案例检索和知识图谱查询 |
| `kg.relation_search` | 查询风险-法规-案例关系 |
| `report.audit_generate` | 生成 PDF 审查报告 |
| `system.status` | 查看 MCP、北大法宝、本地库和数据库状态 |

### 2. 北大法宝 MCP 接入

新增 `app/pkulaw_mcp.py`，负责：

- 读取 `PKULAW_TOKEN` 或 `PKULAW_ACCESS_TOKEN`
- 拼装 `Authorization: Bearer ...`
- 调用北大法宝 MCP 的 streamable HTTP 端点
- 兼容 JSON-RPC / `tools/call`
- 解析 SSE 和 JSON 返回
- 将北大法宝结果转换为项目内部可用的案例/法规结构

### 3. 主链路切换

`legal.policy_search` 和 `case.risk_case_search` 已改成：

1. 先查北大法宝 MCP；
2. 成功则直接返回北大法宝结果；
3. 失败或未配置 Token 时，回退到本地小库。

### 4. 配置文件

在 `.env.example` 中补充了：

- `PKULAW_MCP_ENABLED`
- `PKULAW_TOKEN`
- `PKULAW_ACCESS_TOKEN`
- `PKULAW_CASE_KEYWORD_URL`
- `PKULAW_CASE_SEMANTIC_URL`
- `PKULAW_LAW_SEMANTIC_URL`
- `PKULAW_LAW_KEYWORD_URL`
- `PKULAW_FATIAO_KEYWORD_URL`

### 5. 文档

新增并维护了：

- `docs/PKULAW_MCP_INTEGRATION.md`
- `docs/MCP_RUNTIME_DEMO.md`

## 三、验证结果

已完成真实运行验证：

- `system.status` 中北大法宝状态为 `ready=True`
- `case.risk_case_search` 返回 `backend=pkulaw_mcp`
- `legal.policy_search` 返回 `backend=pkulaw_mcp`
- `risk.scenario_audit` 会调用北大法宝法规和案例作为依据

## 四、当前结论

MCP 模块已经完成，并且北大法宝已成功接入，当前检索主链路不再依赖本地小数据库。

本地库仍保留作为兜底，不影响主功能。
