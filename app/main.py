from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from docx import Document
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader

from .agent import ComplianceAgent
from .db import db_status
from .report import REPORT_DIR, build_pdf_report
from .rag import POLICY_DIR
from .repository import (
    db_counts,
    list_legal_documents,
    list_reports,
    list_uploads,
    record_audit_report,
    record_kb_upload,
    record_uploaded_material,
    safe_init_db,
    sync_policies_to_db,
)

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
POLICY_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AI Data Compliance Agent", version="1.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
agent = ComplianceAgent()
store = agent.store
LAST_RESULTS: dict[str, dict] = {}


class AskRequest(BaseModel):
    question: str


class MCPCallRequest(BaseModel):
    name: str
    arguments: dict = {}


@app.on_event("startup")
def startup() -> None:
    safe_init_db()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((FRONTEND / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "kb_ready": store.ready(), "version": app.version, "retriever": store.stats(), "agents": len(agent.router.status()["agents"]), "mcp_tools": len(agent.mcp_client.manifest()["tools"]), "db": db_status()}


@app.get("/api/agents/status")
def agents_status() -> dict:
    return agent.router.status()


@app.get("/api/mcp/manifest")
def mcp_manifest() -> dict:
    return agent.mcp_client.manifest()


@app.post("/api/mcp/call")
def mcp_call(req: MCPCallRequest) -> dict:
    try:
        result = agent.mcp_client.call_tool(req.name, req.arguments)
        return {"ok": True, "tool": req.name, "result": result, "mcp_trace": agent.mcp_client.pop_trace()}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/db/status")
def database_status() -> dict:
    status = db_status()
    try:
        status["counts"] = db_counts() if status["ok"] else {}
    except Exception as exc:
        status["counts"] = {}
        status["count_error"] = str(exc)
    return status


@app.get("/api/db/policies")
def db_policies(limit: int = 100) -> dict:
    return {"items": list_legal_documents(limit=limit)}


@app.get("/api/uploads")
def uploads(limit: int = 20) -> dict:
    return {"items": list_uploads(limit=limit)}


@app.get("/api/reports")
def reports(limit: int = 20) -> dict:
    return {"items": list_reports(limit=limit)}


@app.get("/api/kb/stats")
def kb_stats() -> dict:
    if not store.ready():
        store.build_from_seed()
    stats = store.stats()
    try:
        stats["db_counts"] = db_counts()
    except Exception:
        stats["db_counts"] = {}
    return stats


@app.post("/api/kb/rebuild")
def rebuild_kb() -> dict:
    count = store.build_from_policy_dir()
    db_sync = sync_policies_to_db()
    return {"ok": True, "chunks": count, "db_sync": db_sync, "stats": store.stats()}


@app.post("/api/kb/upload")
async def upload_policy(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(400, "请上传 JSON 格式的政策文件")
    raw = await file.read()
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        record_kb_upload(file.filename or "unknown", "", 0, 0, status="failed", message=f"JSON 解析失败：{exc}")
        raise HTTPException(400, f"JSON 解析失败：{exc}") from exc
    if not _looks_like_policy_payload(parsed):
        record_kb_upload(file.filename or "unknown", "", 0, 0, status="failed", message="JSON 字段结构不符合要求")
        raise HTTPException(400, "JSON 需包含政策对象或政策数组，字段建议包含 title/source_url/chunks/articles")
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", file.filename)
    target = POLICY_DIR / f"team_{safe_name}"
    target.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    count = store.build_from_policy_dir()
    db_sync = sync_policies_to_db()
    record_kb_upload(file.filename, str(target), db_sync["documents"], db_sync["chunks"], status="success")
    return {"ok": True, "saved_as": target.name, "chunks": count, "db_sync": db_sync, "stats": store.stats()}


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    if not req.question.strip():
        raise HTTPException(400, "question is required")
    return agent.answer(req.question.strip())


@app.post("/api/audit")
async def audit(file: Optional[UploadFile] = File(None), text: str = Form("")) -> dict:
    filename = "文本输入"
    content = text
    saved: Path | None = None
    size_bytes = len((text or "").encode("utf-8"))
    content_type = "text/plain"
    if file is not None:
        filename = file.filename or "uploaded_file"
        content_type = file.content_type or "application/octet-stream"
        raw = await file.read()
        size_bytes = len(raw)
        safe_name = re.sub(r"[^A-Za-z0-9_.\u4e00-\u9fa5-]", "_", filename)
        saved = UPLOAD_DIR / safe_name
        saved.write_bytes(raw)
        content = extract_text(saved)
    if not content.strip():
        raise HTTPException(400, "请上传文件或输入待审查文本")
    material_id = record_uploaded_material(filename, str(saved or ""), content_type, size_bytes, content)
    result = agent.audit_text(content, filename)
    report_id, path = build_pdf_report(result)
    result["report_id"] = report_id
    result["report_url"] = f"/api/report/{report_id}"
    record_audit_report(result, report_id, str(path), material_id)
    LAST_RESULTS[report_id] = result | {"report_path": str(path)}
    return result


@app.get("/api/report/{report_id}")
def report(report_id: str) -> FileResponse:
    info = LAST_RESULTS.get(report_id)
    path = Path(info["report_path"]) if info else next(REPORT_DIR.glob(f"*{report_id}.pdf"), None)
    if not path or not path.exists():
        raise HTTPException(404, "report not found")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gb18030", errors="ignore")


def _looks_like_policy_payload(payload) -> bool:
    records = payload.get("policies") if isinstance(payload, dict) and "policies" in payload else payload
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list) or not records:
        return False
    first = records[0]
    return isinstance(first, dict) and any(k in first for k in ["title", "name"]) and any(k in first for k in ["chunks", "articles", "text", "content"])
