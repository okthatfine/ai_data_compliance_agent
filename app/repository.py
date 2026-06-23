from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select

from .db import init_db, session_scope
from .models import AuditReport, AuditRisk, KnowledgeImport, LegalArticle, LegalChunk, LegalDocument, LegalVersion, UploadedMaterial
from .rag import POLICY_DIR, PolicyVectorStore, normalize_text


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def safe_init_db() -> dict[str, Any]:
    try:
        init_db()
        return {"ok": True, "error": ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def sync_policies_to_db(policy_dir: Path = POLICY_DIR) -> dict[str, int]:
    init_db()
    store = PolicyVectorStore()
    documents = []
    for file in sorted(policy_dir.glob("*.json")):
        for policy in store._read_policy_file(file):
            documents.append((file.name, policy))
    with session_scope() as session:
        session.execute(delete(LegalChunk))
        session.execute(delete(LegalArticle))
        session.execute(delete(LegalVersion))
        session.execute(delete(LegalDocument))
        doc_count = 0
        chunk_count = 0
        for source_file, policy in documents:
            doc = LegalDocument(
                title=str(policy.get("title") or policy.get("name") or "未命名政策"),
                level=str(policy.get("level") or "政策文件"),
                issuer=str(policy.get("issuer") or ""),
                status=str(policy.get("status") or "现行有效"),
                source_url=str(policy.get("source_url") or policy.get("url") or ""),
                source_file=source_file,
                version_label=str(policy.get("version") or policy.get("version_label") or "current"),
                publish_date=str(policy.get("publish_date") or ""),
                effective_date=str(policy.get("effective_date") or ""),
                raw_json=policy,
            )
            session.add(doc)
            session.flush()
            session.add(LegalVersion(
                document_id=doc.id,
                version_label=doc.version_label,
                status=doc.status,
                publish_date=doc.publish_date,
                effective_date=doc.effective_date,
                source_url=doc.source_url,
                source_file=source_file,
                change_note=str(policy.get("change_note") or policy.get("revision_note") or ""),
                raw_json=policy,
            ))
            doc_count += 1
            chunk_docs = store._policy_to_docs(policy, source_file)
            article_cache: dict[str, LegalArticle] = {}
            for i, chunk in enumerate(chunk_docs, start=1):
                article_no = str(chunk.get("article_no") or f"片段{i}")
                article_key = f"{article_no}:{chunk.get('heading','')}"
                article = article_cache.get(article_key)
                if article is None:
                    article = LegalArticle(
                        document_id=doc.id,
                        article_no=article_no,
                        heading=str(chunk.get("heading") or ""),
                        ordinal=len(article_cache) + 1,
                        text=str(chunk.get("article_text") or chunk.get("text") or ""),
                    )
                    session.add(article)
                    session.flush()
                    article_cache[article_key] = article
                embedding_text = " ".join([doc.title, article.article_no, article.heading, str(chunk.get("text") or "")])
                session.add(LegalChunk(
                    document_id=doc.id,
                    article_id=article.id,
                    chunk_no=int(chunk.get("chunk_id") or i),
                    text=str(chunk.get("text") or ""),
                    embedding_text=normalize_text(embedding_text),
                    metadata_json={
                        "level": doc.level,
                        "source_url": doc.source_url,
                        "source_file": source_file,
                        "article_no": article.article_no,
                        "heading": article.heading,
                    },
                ))
                chunk_count += 1
        session.add(KnowledgeImport(
            filename="policy_dir_sync",
            saved_path=str(policy_dir),
            status="success",
            imported_documents=doc_count,
            imported_chunks=chunk_count,
            message="Synced policy JSON files into normalized tables.",
        ))
    return {"documents": doc_count, "chunks": chunk_count}


def record_kb_upload(filename: str, saved_path: str, documents: int, chunks: int, status: str = "success", message: str = "") -> str | None:
    try:
        init_db()
        with session_scope() as session:
            row = KnowledgeImport(filename=filename, saved_path=saved_path, imported_documents=documents, imported_chunks=chunks, status=status, message=message)
            session.add(row)
            session.flush()
            return row.id
    except Exception:
        return None


def record_uploaded_material(filename: str, storage_path: str, content_type: str, size_bytes: int, extracted_text: str) -> str | None:
    try:
        init_db()
        with session_scope() as session:
            row = UploadedMaterial(
                filename=filename,
                storage_path=storage_path,
                content_type=content_type,
                size_bytes=size_bytes,
                text_hash=_hash_text(extracted_text),
                extracted_text=extracted_text,
            )
            session.add(row)
            session.flush()
            return row.id
    except Exception:
        return None


def record_audit_report(result: dict[str, Any], report_id: str, report_path: str, material_id: str | None) -> str | None:
    try:
        init_db()
        with session_scope() as session:
            report = AuditReport(
                report_id=report_id,
                material_id=material_id,
                filename=str(result.get("filename") or ""),
                report_path=report_path,
                overall_level=str(result.get("overall_level") or ""),
                risk_count=int(result.get("risk_count") or 0),
                summary=str(result.get("summary") or ""),
                result_json=result,
            )
            session.add(report)
            session.flush()
            for risk in result.get("risks", []) or []:
                session.add(AuditRisk(
                    report_db_id=report.id,
                    title=str(risk.get("title") or ""),
                    severity=str(risk.get("severity") or ""),
                    excerpt=str(risk.get("excerpt") or ""),
                    matched_keywords=list(risk.get("matched_keywords") or []),
                    legal_basis=list(risk.get("legal_basis") or []),
                    recommendation=str(risk.get("recommendation") or ""),
                ))
            return report.id
    except Exception:
        return None


def db_counts() -> dict[str, int]:
    init_db()
    with session_scope() as session:
        return {
            "legal_documents": session.scalar(select(func.count()).select_from(LegalDocument)) or 0,
            "legal_versions": session.scalar(select(func.count()).select_from(LegalVersion)) or 0,
            "legal_articles": session.scalar(select(func.count()).select_from(LegalArticle)) or 0,
            "legal_chunks": session.scalar(select(func.count()).select_from(LegalChunk)) or 0,
            "uploads": session.scalar(select(func.count()).select_from(UploadedMaterial)) or 0,
            "reports": session.scalar(select(func.count()).select_from(AuditReport)) or 0,
            "risks": session.scalar(select(func.count()).select_from(AuditRisk)) or 0,
            "imports": session.scalar(select(func.count()).select_from(KnowledgeImport)) or 0,
        }


def list_reports(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with session_scope() as session:
        rows = session.scalars(select(AuditReport).order_by(AuditReport.created_at.desc()).limit(limit)).all()
        return [
            {
                "report_id": r.report_id,
                "filename": r.filename,
                "overall_level": r.overall_level,
                "risk_count": r.risk_count,
                "summary": r.summary,
                "report_url": f"/api/report/{r.report_id}",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]


def list_uploads(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with session_scope() as session:
        rows = session.scalars(select(UploadedMaterial).order_by(UploadedMaterial.created_at.desc()).limit(limit)).all()
        return [
            {
                "id": r.id,
                "filename": r.filename,
                "storage_path": r.storage_path,
                "content_type": r.content_type,
                "size_bytes": r.size_bytes,
                "text_hash": r.text_hash,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]


def list_legal_documents(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with session_scope() as session:
        rows = session.scalars(select(LegalDocument).order_by(LegalDocument.level, LegalDocument.title).limit(limit)).all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "level": r.level,
                "issuer": r.issuer,
                "status": r.status,
                "version_label": r.version_label,
                "source_url": r.source_url,
                "source_file": r.source_file,
                "versions": [v.version_label for v in r.versions],
            }
            for r in rows
        ]
