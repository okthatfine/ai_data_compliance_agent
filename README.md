# AI 科创企业数据合规智能系统

面向科创企业风险识别与管理场景的法律合规演示系统。

## 核心能力

- 北大法宝 MCP 检索：问答和材料审查实时检索北大法宝的法律法规、法条和裁判案例，不再依赖本地法规知识库作为主数据源。
- 企业材料审查：支持 TXT、PDF、DOCX，识别训练数据、个人信息、数据出境、自动化决策、AIGC 标识、人脸识别和第三方共享等风险。
- 法规与案例双依据：每项风险同时返回法律法规依据和类案参考，用于生成整改建议和 PDF 报告。
- 风险知识图谱：内置团队“科创企业风险知识地图”的九类风险、六个企业生命周期阶段、22 条法规及 67 个典型案例（其中包含北大法宝缓存案例）。
- 报告生成：导出 PDF 合规审查报告。

## 配置

在 `.env` 中填写北大法宝授权 Token：

```env
PKULAW_MCP_ENABLED=1
PKULAW_ACCESS_TOKEN=你的Token
PKULAW_TIMEOUT=35
PKULAW_MIN_INTERVAL_SECONDS=1.2

DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Token 只应保存于本地 `.env`，不要提交到 Git。

## 启动

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8018
```

访问 <http://127.0.0.1:8018/>。

## 北大法宝 MCP 调用顺序

- 法规：法规语义检索 → 法规关键词检索 → 法条关键词检索。
- 案例：案例语义检索 → 案例关键词检索。
- 失败时会在结果状态中标注北大法宝调用异常，不会以本地法规库替代远程检索结果。

本系统用于竞赛演示和内部合规辅助，不替代正式法律意见。
