# MCP 工具层说明

本项目的 Agent 不再直接依赖本地数据库或本地检索实现，而是通过 MCP 工具完成法规检索、案例检索、风险扫描、知识图谱查询和报告生成。

## 工具清单

| 工具名 | 作用 |
| --- | --- |
| `legal.policy_search` | 检索法规、政策和团队知识库 chunk |
| `case.risk_case_search` | 检索科创企业风险案例库 |
| `risk.rule_scan` | 基于规则扫描企业材料风险信号 |
| `risk.scenario_audit` | 综合风险扫描、法规检索、案例检索和知识图谱查询，输出场景化风险清单 |
| `kg.relation_search` | 查询风险、法规、案例、生命周期之间的知识图谱关系 |
| `report.audit_generate` | 基于审查结果生成 PDF 报告 |
| `system.status` | 查询 MCP、知识库、案例库、知识图谱和数据库状态 |
| `skills.catalog` | 返回可复用 Skills 清单 |

兼容旧工具名：

| 旧工具名 | 等价新工具 |
| --- | --- |
| `compliance.risk_scan` | `risk.rule_scan` |
| `system.db_status` | `system.status` 中的数据库状态 |

## 本地 / 远程 MCP 切换

默认使用进程内本地 MCP 工具。若配置远程 MCP 服务：

```env
MCP_BASE_URL=http://127.0.0.1:8018
MCP_TIMEOUT=30
```

客户端会调用：

```text
GET  /api/mcp/manifest
POST /api/mcp/call
```

远程调用失败时，会自动回退本地工具。

## 案例库接入

把案例库导出到以下任一位置：

```text
data/cases.json
data/cases.jsonl
data/cases.csv
data/cases/*.json
data/cases/*.jsonl
data/cases/*.csv
```

推荐字段：

```json
{
  "title": "案例标题",
  "case_no": "案号",
  "court": "法院",
  "year": "年份",
  "cause": "案由",
  "risk_types": ["RISK-DATA", "RISK-IP"],
  "lifecycle_stage": "成长期",
  "identified": "本院认为",
  "referee_result": "裁判结果",
  "referee_basis": "裁判依据",
  "content": "全文",
  "source_url": "来源链接"
}
```

代码也兼容 `CaseFlag`、`Title`、`Category`、`Court`、`Url`、`本院认为`、`裁判结果` 等常见字段。

## 知识图谱接入

支持两种格式：

```text
data/kg/graph.json
```

```json
{
  "nodes": [
    {"id": "risk_DATA", "type": "risk", "name": "数据风险", "risk_type": "RISK-DATA"}
  ],
  "edges": [
    {"source": "risk_DATA", "target": "law_PIPL", "relation": "对应"}
  ]
}
```

或拆分为：

```text
data/kg/nodes.json
data/kg/edges.json
```

## Agent 调用链

材料审查：

```text
Agent -> risk.scenario_audit
      -> risk.rule_scan
      -> legal.policy_search
      -> case.risk_case_search
      -> kg.relation_search
      -> report.audit_generate
```

问答：

```text
Agent -> legal.policy_search
Agent -> case.risk_case_search
Agent -> kg.relation_search
Agent -> LLM 生成带来源回答
```
