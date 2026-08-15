# AI 科创企业数据合规智能系统

面向“科创企业风险的识别与管理”场景的法律合规演示系统，聚焦 AI 科创企业的数据合规审查。

## 功能

- 法律政策知识库：内置官方法律政策种子库，支持上传 JSON 政策文件并重建索引。
- RAG 合规问答：检索法规片段、类案和风险知识图谱，为问题生成有依据的建议；语义模型不可用时自动回退到 TF-IDF。
- 企业材料审查：支持 TXT、PDF、DOCX，识别训练数据、个人信息、数据出境、自动化决策、AIGC 标识、人脸识别和第三方共享等风险。
- 风险分级与整改建议：输出高、中、低风险、法规依据、类案参考和整改建议。
- 报告生成：导出 PDF 合规审查报告。
- 前后端一体化：FastAPI 同时提供 API 和静态前端。

系统采用单体本地服务实现：规则扫描、法规检索、案例库查询、知识图谱查询和报告生成由应用直接调用，便于部署和演示。

## 快速启动

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8018
```

打开 <http://127.0.0.1:8018/>。

## 配置

在 `.env` 中配置可选的 DeepSeek API：

```bash
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
```

未配置 API 密钥时，系统仍会返回基于本地规则和知识库的初步意见。

## 团队政策文件格式

前端“政策知识库”页面支持上传 JSON：

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

本系统用于竞赛演示和内部合规辅助，不替代正式法律意见。
