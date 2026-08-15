# 北大法宝 MCP 接入说明

## 目标

原项目的法律法规和案例检索主要依赖本地小型数据集，数据量少，只适合作为演示兜底。现在改为：

1. 优先通过北大法宝 MCP 查询外部权威数据库；
2. 查询失败、未配置 Token、接口不可用时，再回退到本地法规/案例库；
3. 前端、Agent 和内部 MCP 工具名保持不变，避免大面积重构。

也就是说，项目内部仍调用：

- `legal.policy_search`
- `case.risk_case_search`

但这两个工具背后的数据源已经变成“北大法宝 MCP 优先”。

## 需要准备

1. 北大法宝 MCP Token

   从北大法宝 MCP 平台控制台获取，填入本地 `.env`：

   ```env
   PKULAW_TOKEN=你的Token
   ```

   代码也兼容 `PKULAW_ACCESS_TOKEN` 这个别名。

   不要把真实 Token 提交到 GitHub。

2. 北大法宝 MCP 权限

   账号需要有相关 MCP 接口访问权限，至少包括：

   - 司法案例检索；
   - 法律法规检索；
   - 法条检索。

3. 官方入口

   - 北大法宝 MCP 平台：https://mcp.pkulaw.com/
   - MCP 控制台：https://mcp.pkulaw.com/console/apps

## 已配置的接口

```env
PKULAW_MCP_ENABLED=1
PKULAW_TIMEOUT=35
PKULAW_MIN_INTERVAL_SECONDS=1.2
PKULAW_CASE_KEYWORD_URL=https://apim-gateway.pkulaw.com/mcp-case
PKULAW_CASE_SEMANTIC_URL=https://apim-gateway.pkulaw.com/mcp-case-search-service
PKULAW_LAW_SEMANTIC_URL=https://apim-gateway.pkulaw.com/mcp-law-search-service
PKULAW_LAW_KEYWORD_URL=https://apim-gateway.pkulaw.com/mcp-law
PKULAW_FATIAO_KEYWORD_URL=https://apim-gateway.pkulaw.com/mcp-fatiao
```

## 查询链路

### 法规检索

`legal.policy_search` 的顺序：

1. 调北大法宝法规语义检索；
2. 调北大法宝法规关键词检索；
3. 调北大法宝法条关键词检索；
4. 如果没有 Token 或外部接口不可用，回退到本地 `PolicyVectorStore`。

法规语义检索使用官方 CLI 示例中的工具名 `search_article`。

### 案例检索

`case.risk_case_search` 的顺序：

1. 调北大法宝案例语义检索；
2. 调北大法宝案例关键词检索；
3. 如果没有 Token 或外部接口不可用，回退到本地 `CaseStore`。

案例语义检索使用工具名 `search_case`；案例关键词检索按资料清单中的说明使用 `get_case_list`。

## 代码位置

- `app/pkulaw_mcp.py`：北大法宝 MCP 客户端，负责 Token、请求头、JSON-RPC、SSE 解析和结果字段归一。
- `app/mcp_server.py`：内部 MCP 工具层，已改成北大法宝优先、本地兜底。
- `.env.example`：新增北大法宝 MCP 配置模板。

## 测试方式

无 Token 时测试系统不崩：

```powershell
python -m compileall -q app
python -c "from app.agent import ComplianceAgent; a=ComplianceAgent(); print(a.mcp_client.call_tool('system.status', {})['pkulaw'])"
```

配置 Token 后测试真实检索：

```powershell
$env:PKULAW_TOKEN="你的Token"
python -c "from app.agent import ComplianceAgent; a=ComplianceAgent(); print(a.mcp_client.call_tool('case.risk_case_search', {'query':'人工智能训练数据侵权案例','k':3}))"
python -c "from app.agent import ComplianceAgent; a=ComplianceAgent(); print(a.mcp_client.call_tool('legal.policy_search', {'query':'生成式人工智能训练数据个人信息合规要求','k':3}))"
```

返回结果里如果看到：

```json
"backend": "pkulaw_mcp"
```

说明已经使用北大法宝 MCP；如果是：

```json
"backend": "file_case_store"
```

或本地 `tfidf/embedding`，说明走了本地兜底。

## 说明

当前接入是“在线检索优先”的模式，不强制把北大法宝数据批量下载到本地。这样更符合“用北大法宝作为外部大数据库检索依据”的目标，也避免本地存储过多受版权和授权限制的数据。后续如果需要稳定演示，可以只缓存检索摘要、案号、标题、链接和风险标签，不保存大段全文。

## 当前验收结果

已使用 `.env` 中的 `PKULAW_ACCESS_TOKEN` 完成真实调用验证。

### 1. 北大法宝状态

`system.status` 返回：

```json
{
  "enabled": true,
  "ready": true,
  "reason": "ready"
}
```

说明项目已经成功读取 Token，北大法宝 MCP 处于可调用状态。

### 2. 案例检索

调用：

```text
case.risk_case_search
```

参数：

```json
{
  "query": "房屋租赁纠纷",
  "k": 3
}
```

结果关键字段：

```json
{
  "backend": "pkulaw_mcp",
  "fallback_used": false,
  "ready": true,
  "hit_count": 3
}
```

已返回北大法宝案例结果，包括案号、法院、案由和北大法宝链接。

### 3. 法规检索

调用：

```text
legal.policy_search
```

参数：

```json
{
  "query": "生成式人工智能训练数据 个人信息 合规要求",
  "k": 3
}
```

结果关键字段：

```json
{
  "backend": "pkulaw_mcp",
  "fallback_used": false,
  "hit_count": 3
}
```

已返回北大法宝法规结果，例如：

- `生成式人工智能服务管理暂行办法`
- `生成式人工智能服务企业合规指引`
- `信息安全技术 生成式人工智能预训练和优化训练数据安全规范` 相关征求意见稿

### 4. 验收结论

北大法宝 MCP 已成功接入。当前项目的法规检索和案例检索主链路已经切换到北大法宝，只有在 Token 缺失或外部接口失败时才回退到本地小库。
