# PostgreSQL 结构化存储改造说明

当前系统已经新增 SQLAlchemy 数据层，支持 PostgreSQL，并在没有配置 `DATABASE_URL` 时使用 `data/app.db` 作为本机 SQLite fallback，便于 Demo 服务器继续稳定运行。

## 目标结构

数据库把过去散落在 JSON、pickle、PDF 文件中的业务对象正规化为以下表：

- `legal_documents`：法规/政策主档，保存标题、层级、发布机关等稳定身份信息
- `legal_versions`：法规版本，保存版本标签、效力状态、发布日期、生效日期、来源文件和变更说明
- `legal_articles`：法条结构，支持第几条、标题、排序和正文
- `legal_chunks`：RAG 检索片段，保留 article 归属和 embedding_text
- `knowledge_imports`：团队政策 JSON 导入记录和重建索引记录
- `uploaded_materials`：企业上传材料或文本输入记录、hash、抽取文本
- `audit_reports`：审查报告主表、总体评级、报告文件路径、结果 JSON
- `audit_risks`：单项风险、等级、命中关键词、法律依据、整改建议

## 当前项目内便携 PostgreSQL

本服务器没有系统级 PostgreSQL 和 Docker，也没有免密 sudo。当前已采用用户态解包方式，在项目目录内运行真实 PostgreSQL 14：

- 二进制目录：`vendor/pgsql/`
- 数据目录：`data/pg14/`
- socket 目录：`pg_run/`
- 端口：`55432`
- 数据库：`compliance_db`
- 连接串：`postgresql+psycopg://shiliguo@127.0.0.1:55432/compliance_db`

常用命令：

```bash
cd /mnt/data2/lzh/ai_data_compliance_agent
scripts/start_postgres.sh
scripts/status_postgres.sh
scripts/stop_postgres.sh
scripts/start_app.sh
```

`start_app.sh` 会启动 PostgreSQL、初始化表、导入法规、重启 FastAPI。

## 切换到外部 PostgreSQL

1. 准备 PostgreSQL 数据库。

可以手工创建：

```sql
create database compliance_db;
create user compliance with encrypted password '<password>';
grant all privileges on database compliance_db to compliance;
```

也可以在有 Docker 的环境中运行：

```bash
cd /mnt/data2/lzh/ai_data_compliance_agent
docker compose -f docker-compose.postgres.yml up -d
```

2. 配置 `.env`：

```bash
DATABASE_URL=postgresql+psycopg://compliance:<password>@127.0.0.1:5432/compliance_db
```

3. 初始化表并导入法规：

```bash
cd /mnt/data2/lzh/ai_data_compliance_agent
.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/import_policies_to_db.py
```

4. 重启服务：

```bash
if [ -f app.pid ]; then kill $(cat app.pid); fi
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8018 > server.log 2>&1 & echo $! > app.pid
```

## 新增 API

- `GET /api/db/status`：数据库连接与各表计数
- `GET /api/db/policies`：结构化法规文件列表
- `GET /api/uploads`：上传材料记录
- `GET /api/reports`：审查报告记录

原有 API 保持兼容：

- `POST /api/kb/upload` 上传团队 JSON 后，会同步写入 `knowledge_imports`，并把法规重建到 `legal_*` 表。
- `POST /api/kb/rebuild` 会重建 embedding 语义向量索引并同步法规结构表；embedding 不可用时回退 TF-IDF。
- `POST /api/audit` 会写入 `uploaded_materials`、`audit_reports`、`audit_risks`。

## 法条 JSON 推荐格式

大规模法典建议使用 `articles` 而不是单纯 `chunks`：

```json
[
  {
    "title": "中华人民共和国个人信息保护法",
    "level": "法律",
    "issuer": "全国人大常委会",
    "status": "现行有效",
    "version": "2021",
    "source_url": "https://example.com",
    "articles": [
      {
        "article_no": "第二十三条",
        "heading": "向其他处理者提供个人信息",
        "text": "个人信息处理者向其他个人信息处理者提供其处理的个人信息的，应当向个人告知接收方的名称或者姓名、联系方式、处理目的、处理方式和个人信息的种类，并取得个人的单独同意。"
      }
    ]
  }
]
```

系统会把文章结构同步到 `legal_versions` 和 `legal_articles`，并把每条或每款拆成 `legal_chunks`。

## 后续建议

当前 RAG 主路径使用 `BAAI/bge-small-zh-v1.5` 生成中文语义 embedding，并在本地索引中保存归一化 dense vector 做余弦相似度检索；TF-IDF 仅作为模型不可用时的兜底。下一阶段可把 `legal_chunks.embedding_text` 接入 pgvector、Qdrant 或 Milvus，实现更适合大规模法典的 ANN 向量检索；PostgreSQL 继续负责结构化过滤、版本和审计记录。

## 冒烟验证

服务启动后运行：

```bash
cd /mnt/data2/lzh/ai_data_compliance_agent
.venv/bin/python scripts/smoke_db.py http://127.0.0.1:8018
```

该脚本会检查：

- `/api/health` 数据库连接状态
- `/api/kb/rebuild` 是否同步法规结构表
- `/api/audit` 是否写入上传材料、报告和风险项
- `/api/db/status`、`/api/reports`、`/api/uploads`、`/api/db/policies` 是否返回结构化数据

## pgvector 可选迁移

如果后续要把向量也放在 PostgreSQL 中，可以安装 pgvector 后执行：

```bash
psql "$DATABASE_URL" -f migrations/002_pgvector.sql
```

`002_pgvector.sql` 会给 `legal_chunks` 增加 `embedding_model`、`embedding_dim` 和 `embedding vector(1024)`，并创建 HNSW 余弦索引。实际落地时要根据 embedding 模型维度调整 `vector(1024)`，例如 bge-large-zh 可能使用 1024 维，其他模型可能是 768 或 1536 维。
