# MCP 模块工作说明

## 一、任务定位

本次工作完成的是“本地检索/本地数据库能力向 MCP 工具层解耦”的改造。

改造前，Agent 更偏向直接调用本地检索、规则和数据库逻辑；改造后，Agent 通过统一 MCP 工具调用完成法规检索、风险扫描、案例检索、知识图谱查询和报告生成。本地数据库仍可保留，用于上传记录、报告记录、知识库同步和演示状态管理，但核心能力已经被 MCP 工具封装。

## 二、完成内容

### 1. MCP 工具层扩展

在 `app/mcp_server.py` 中完成 MCP 工具层重构，形成以下工具：

| 工具名 | 作用 |
| --- | --- |
| `legal.policy_search` | 检索法规、政策和团队知识库依据 |
| `case.risk_case_search` | 检索科创企业风险案例库 |
| `risk.rule_scan` | 对企业材料进行规则化风险扫描 |
| `risk.scenario_audit` | 综合风险扫描、法规检索、案例检索和知识图谱查询，生成审查清单 |
| `kg.relation_search` | 查询风险、法规、案例和生命周期关系 |
| `report.audit_generate` | 根据审查结果生成 PDF 报告 |
| `system.status` | 查询数据库、知识库、案例库、知识图谱和 MCP 状态 |
| `skills.catalog` | 返回系统 Skills 清单 |

同时保留兼容旧工具名：

- `compliance.risk_scan`
- `system.db_status`

### 2. MCP Client 支持本地/远程切换

在 `app/mcp_client.py` 中实现 MCP Client。

默认使用本地进程内 MCP 工具；如果配置：

```env
MCP_BASE_URL=http://127.0.0.1:8018
MCP_TIMEOUT=30
```

则优先调用远程 MCP 接口：

```text
GET  /api/mcp/manifest
POST /api/mcp/call
```

远程调用失败时会回退本地 MCP 工具。

### 3. Agent 调用链重构

在 `app/agent.py` 中，将问答和材料审查流程改为 MCP 工具编排。

材料审查链路：

```text
Agent
-> risk.scenario_audit
-> risk.rule_scan
-> legal.policy_search
-> case.risk_case_search
-> kg.relation_search
-> report.audit_generate
```

法律问答链路：

```text
Agent
-> legal.policy_search
-> case.risk_case_search
-> kg.relation_search
-> LLM 生成带来源回答
```

### 4. 案例库检索模块

新增 `app/case_store.py`。

支持自动读取：

```text
data/cases.json
data/cases.jsonl
data/cases.csv
data/cases/*.json
data/cases/*.jsonl
data/cases/*.csv
```

后续把 551 条科创企业风险案例导出到上述目录后，`case.risk_case_search` 可直接检索，不需要再改 MCP 接口。

### 5. 知识图谱查询模块

新增 `app/kg_store.py`。

支持自动读取：

```text
data/kg/graph.json
```

或：

```text
data/kg/nodes.json
data/kg/edges.json
```

用于后续接入“风险-法规-案例-生命周期”知识图谱。

### 6. 风险规则库重写

重写 `app/rules.py`，将原有偏数据合规的规则扩展为更贴合科创企业特有风险的规则，覆盖：

- `RISK-TECH` 技术风险
- `RISK-DATA` 数据风险
- `RISK-ALGO` 算法风险
- `RISK-IP` 知识产权风险
- `RISK-HR` 人力资本风险
- `RISK-FIN` 融资风险
- `RISK-REG` 监管风险
- `RISK-MKT` 市场竞争风险
- `RISK-GEO` 地缘/跨境风险

### 7. 报告生成纳入 MCP

重写 `app/report.py`，修复报告中文显示，并支持展示：

- 风险类型
- 命中关键词
- 触发原因
- 法律依据
- 类案参考
- 整改建议

在 `app/main.py` 中，`/api/audit` 不再直接调用报告函数，而是通过：

```text
report.audit_generate
```

生成 PDF 报告。

### 8. 文档补充

新增 `docs/MCP_TOOLS.md`，说明：

- MCP 工具清单
- 远程 MCP 配置方式
- 案例库接入格式
- 知识图谱接入格式
- Agent 调用链路

## 三、验证情况

已完成以下验证：

```text
python -m compileall -q app scripts
```

结果通过。

MCP 工具链实测：

- `risk.rule_scan` 可识别训练数据、个人信息、数据出境、AIGC 标识、第三方共享等风险；
- `risk.scenario_audit` 可返回总体风险等级、风险清单和工具链结果；
- `report.audit_generate` 可生成 PDF 报告；
- `system.status` 可返回 MCP、数据库、法规检索、案例库、知识图谱状态。

## 四、当前边界

当前 MCP 模块已经完成整体架构和工具层实现。

后续如果要进一步丰富效果，只需要补充数据：

1. 将 551 条案例库导出到 `data/cases/`；
2. 将知识图谱节点和边导出到 `data/kg/`；
3. 补充更多法规政策 JSON 到 `data/policies/`。

不需要再改 MCP 工具接口。

## 五、可写入个人分工的表述

本人负责 MCP 工具层与检索重构模块，完成法规检索、案例检索、风险扫描、场景审查、知识图谱查询和报告生成等能力的 MCP 工具化封装；重构 Agent 调用链，使系统通过统一、可追踪、可扩展的 MCP 工具完成科创企业特有风险识别、依据检索和审查报告生成，并为后续接入案例库和知识图谱预留标准数据接口。
