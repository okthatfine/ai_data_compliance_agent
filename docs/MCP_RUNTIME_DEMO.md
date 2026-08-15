# MCP 调用运行展示

> 验证日期：2026-08-15  
> 验证目标：确认项目已经通过北大法宝 MCP 查询外部法律数据资源，而不是依赖本地小数据库。  
> 注意：文档不展示真实 Token。

## 一、环境状态检查

### 调用命令

```powershell
python -c "from app.agent import ComplianceAgent; a=ComplianceAgent(); print(a.mcp_client.call_tool('system.status', {})['pkulaw'])"
```

### 关键结果

```json
{
  "enabled": true,
  "ready": true,
  "reason": "ready",
  "endpoints": {
    "case_keyword": "https://apim-gateway.pkulaw.com/mcp-case",
    "case_semantic": "https://apim-gateway.pkulaw.com/mcp-case-search-service",
    "law_semantic": "https://apim-gateway.pkulaw.com/mcp-law-search-service",
    "law_keyword": "https://apim-gateway.pkulaw.com/mcp-law",
    "fatiao_keyword": "https://apim-gateway.pkulaw.com/mcp-fatiao"
  },
  "last_error": ""
}
```

### 说明

`ready=true` 表示项目已经成功读取 `.env` 中的北大法宝 Token，并且北大法宝 MCP 功能处于启用状态。

## 二、案例检索调用

### 调用工具

```text
case.risk_case_search
```

### 调用参数

```json
{
  "query": "房屋租赁纠纷",
  "k": 3
}
```

### 调用链路

```text
Agent / MCP Client
-> app.mcp_server.MCPToolServer
-> case.risk_case_search
-> app.pkulaw_mcp.PkulawMCPClient.search_cases
-> 北大法宝 mcp-case-search-service
-> 工具名 search_case
-> 返回案例结果
```

### 关键结果

```json
{
  "backend": "pkulaw_mcp",
  "fallback_used": false,
  "ready": true,
  "hit_count": 3,
  "hits": [
    {
      "title": "原告罗某诉被告赵某房屋租赁合同纠纷案",
      "case_no": "(2025)赣0791民初9033号",
      "court": "江西省赣州经济技术开发区人民法院",
      "year": "2026-03-11",
      "cause": "房屋租赁合同纠纷",
      "source_url": "https://pkulaw.com/pfnl/c7ed112b8012f8163890b37f4cd43e9f2cd7807d83f06f99bdfb.html"
    },
    {
      "title": "朱云飞与张楚房屋租赁合同纠纷民事裁定书",
      "case_no": "(2019)鲁01民辖终274号",
      "court": "山东省济南市中级人民法院",
      "year": "2019-04-10",
      "cause": "房屋租赁合同纠纷",
      "source_url": "https://pkulaw.com/pfnl/a6bdb3332ec0adc46fd9ccc925df6ee29563019b070c1a14bdfb.html"
    },
    {
      "title": "杭国祥与张银梅、杭天柱、陆从智、南京晟脉商贸有限公司租赁合同纠纷二审民事裁定书",
      "case_no": "(2018)苏01民辖终883号",
      "court": "江苏省南京市中级人民法院",
      "year": "2018-08-31",
      "cause": "房屋租赁合同纠纷",
      "source_url": "https://pkulaw.com/pfnl/a25051f3312b07f3203ccc7bd932b45d73a20cb42b73d454bdfb.html"
    }
  ]
}
```

### 判断

`backend=pkulaw_mcp` 且 `fallback_used=false`，说明案例检索没有走本地案例库，而是直接使用北大法宝 MCP。

## 三、法规检索调用

### 调用工具

```text
legal.policy_search
```

### 调用参数

```json
{
  "query": "生成式人工智能训练数据 个人信息 合规要求",
  "k": 3
}
```

### 调用链路

```text
Agent / MCP Client
-> app.mcp_server.MCPToolServer
-> legal.policy_search
-> app.pkulaw_mcp.PkulawMCPClient.search_policies
-> 北大法宝 mcp-law-search-service
-> 工具名 search_article
-> 返回法规结果
```

### 关键结果

```json
{
  "backend": "pkulaw_mcp",
  "fallback_used": false,
  "hit_count": 3,
  "hits": [
    {
      "title": "生成式人工智能服务管理暂行办法",
      "level": "北大法宝法规",
      "source_url": "https://pkulaw.com/chl/6dc227b9153496c2bdfb.html",
      "text_excerpt": "第七条 生成式人工智能服务提供者（以下称提供者）应当依法开展预训练、优化训练等训练数据处理活动，遵守以下规定： （一）使用具有合法来源的数据和基础模型； （二）涉及知识产权的，不得侵害他人依法享有的知识产权； （三）涉及个人信息的，应当取得个人同意或者符合法律、行政法规规定的其他情形；"
    },
    {
      "title": "生成式人工智能服务企业合规指引",
      "level": "北大法宝法规",
      "source_url": "https://pkulaw.com/lar/3d2230bec4101155343368c75a38f75fbdfb.html",
      "text_excerpt": "第九条 【训练数据安全】 生成式人工智能服务企业训练数据应遵循以下安全要求： （一）数据来源安全，采集前需对数据来源进行安全评估，若违法不良信息占比超 5% 则禁止采集或使用；应确保数据来源多样性，合理搭配境内外及多类型数据；"
    },
    {
      "title": "全国信息安全标准化技术委员会秘书处关于国家标准《信息安全技术 生成式人工智能预训练和优化训练数据安全规范》征求意见稿征求意见的通知",
      "level": "北大法宝法规",
      "source_url": "https://pkulaw.com/protocol/49a019a6528143df0ef80a1cab92c3e5bdfb.html"
    }
  ]
}
```

### 判断

`backend=pkulaw_mcp` 且返回了北大法宝法规链接，说明法规检索已经接入北大法宝 MCP。

## 四、完整审查链路调用

### 调用工具

```text
risk.scenario_audit
```

### 输入材料

```text
公司拟抓取公开网页语料训练大模型，收集用户日志并同步给海外供应商，生成图片暂无水印标识。
```

### 关键结果

```json
{
  "overall_level": "高风险",
  "risk_count": 5,
  "tools_used": [
    "risk.rule_scan",
    "legal.policy_search",
    "case.risk_case_search",
    "kg.relation_search"
  ],
  "risk_titles": [
    "训练数据合法来源不足",
    "个人信息处理告知与同意不足",
    "数据出境路径不明确",
    "AI生成合成内容标识义务缺失",
    "第三方共享或委托处理约束不足"
  ],
  "first_risk_case_backend_hint": "case_basis_count=2"
}
```

### 判断

完整审查链路会调用：

```text
risk.rule_scan
legal.policy_search
case.risk_case_search
kg.relation_search
```

其中 `legal.policy_search` 和 `case.risk_case_search` 的主数据源已经是北大法宝 MCP。

## 五、结论

当前 MCP 模块已经成功接入北大法宝：

1. Token 可读取；
2. 北大法宝 MCP 状态为 ready；
3. 案例检索返回 `backend=pkulaw_mcp`；
4. 法规检索返回 `backend=pkulaw_mcp`；
5. 完整风险审查链路能调用北大法宝检索结果作为依据。

因此，本项目已经实现“用北大法宝外部大数据库替代本地小数据库作为检索依据”的目标。
