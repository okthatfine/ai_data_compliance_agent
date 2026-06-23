from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LegalDocument(Base, TimestampMixin):
    __tablename__ = "legal_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(128), default="政策文件", nullable=False, index=True)
    issuer: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="现行有效", nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_file: Mapped[str] = mapped_column(String(512), default="", nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(128), default="current", nullable=False)
    publish_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    effective_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    versions: Mapped[list["LegalVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    articles: Mapped[list["LegalArticle"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    chunks: Mapped[list["LegalChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("title", "source_file", "version_label", name="uq_legal_document_source_version"),)


class LegalVersion(Base, TimestampMixin):
    __tablename__ = "legal_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(128), default="current", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), default="现行有效", nullable=False, index=True)
    publish_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    effective_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_file: Mapped[str] = mapped_column(String(512), default="", nullable=False, index=True)
    change_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    document: Mapped[LegalDocument] = relationship(back_populates="versions")

    __table_args__ = (UniqueConstraint("document_id", "version_label", "source_file", name="uq_legal_version_doc_label_source"),)


class LegalArticle(Base, TimestampMixin):
    __tablename__ = "legal_articles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    article_no: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    heading: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    document: Mapped[LegalDocument] = relationship(back_populates="articles")
    chunks: Mapped[list["LegalChunk"]] = relationship(back_populates="article", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("document_id", "article_no", "ordinal", name="uq_legal_article_doc_no_ord"),)


class LegalChunk(Base, TimestampMixin):
    __tablename__ = "legal_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("legal_articles.id", ondelete="SET NULL"), nullable=True, index=True)
    chunk_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    document: Mapped[LegalDocument] = relationship(back_populates="chunks")
    article: Mapped[LegalArticle | None] = relationship(back_populates="chunks")

    __table_args__ = (Index("ix_legal_chunks_doc_chunk", "document_id", "chunk_no"),)


class KnowledgeImport(Base, TimestampMixin):
    __tablename__ = "knowledge_imports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    saved_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="success", nullable=False, index=True)
    imported_documents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)


class UploadedMaterial(Base, TimestampMixin):
    __tablename__ = "uploaded_materials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    reports: Mapped[list["AuditReport"]] = relationship(back_populates="material")


class AuditReport(Base, TimestampMixin):
    __tablename__ = "audit_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    material_id: Mapped[str | None] = mapped_column(ForeignKey("uploaded_materials.id", ondelete="SET NULL"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    report_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    overall_level: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    risk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    material: Mapped[UploadedMaterial | None] = relationship(back_populates="reports")
    risks: Mapped[list["AuditRisk"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class AuditRisk(Base, TimestampMixin):
    __tablename__ = "audit_risks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    report_db_id: Mapped[str] = mapped_column(ForeignKey("audit_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    matched_keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    legal_basis: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    report: Mapped[AuditReport] = relationship(back_populates="risks")
