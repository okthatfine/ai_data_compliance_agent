-- PostgreSQL schema for AI 科创企业数据合规智能系统
-- Use SQLAlchemy create_all or run this as a reference migration.

create table if not exists legal_documents (
  id varchar(32) primary key,
  title varchar(512) not null,
  level varchar(128) not null default '政策文件',
  issuer varchar(256) not null default '',
  status varchar(64) not null default '现行有效',
  source_url text not null default '',
  source_file varchar(512) not null default '',
  version_label varchar(128) not null default 'current',
  publish_date varchar(32) not null default '',
  effective_date varchar(32) not null default '',
  raw_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_legal_document_source_version unique (title, source_file, version_label)
);


create table if not exists legal_versions (
  id varchar(32) primary key,
  document_id varchar(32) not null references legal_documents(id) on delete cascade,
  version_label varchar(128) not null default 'current',
  status varchar(64) not null default '现行有效',
  publish_date varchar(32) not null default '',
  effective_date varchar(32) not null default '',
  source_url text not null default '',
  source_file varchar(512) not null default '',
  change_note text not null default '',
  raw_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_legal_version_doc_label_source unique (document_id, version_label, source_file)
);
create table if not exists legal_articles (
  id varchar(32) primary key,
  document_id varchar(32) not null references legal_documents(id) on delete cascade,
  article_no varchar(128) not null default '',
  heading varchar(512) not null default '',
  ordinal integer not null default 0,
  text text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_legal_article_doc_no_ord unique (document_id, article_no, ordinal)
);

create table if not exists legal_chunks (
  id varchar(32) primary key,
  document_id varchar(32) not null references legal_documents(id) on delete cascade,
  article_id varchar(32) references legal_articles(id) on delete set null,
  chunk_no integer not null default 1,
  text text not null,
  embedding_text text not null,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists knowledge_imports (
  id varchar(32) primary key,
  filename varchar(512) not null,
  saved_path text not null default '',
  status varchar(64) not null default 'success',
  imported_documents integer not null default 0,
  imported_chunks integer not null default 0,
  message text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists uploaded_materials (
  id varchar(32) primary key,
  filename varchar(512) not null,
  storage_path text not null default '',
  content_type varchar(256) not null default '',
  size_bytes integer not null default 0,
  text_hash varchar(64) not null default '',
  extracted_text text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists audit_reports (
  id varchar(32) primary key,
  report_id varchar(64) not null unique,
  material_id varchar(32) references uploaded_materials(id) on delete set null,
  filename varchar(512) not null default '',
  report_path text not null default '',
  overall_level varchar(64) not null default '',
  risk_count integer not null default 0,
  summary text not null default '',
  result_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists audit_risks (
  id varchar(32) primary key,
  report_db_id varchar(32) not null references audit_reports(id) on delete cascade,
  title varchar(512) not null,
  severity varchar(32) not null,
  excerpt text not null default '',
  matched_keywords jsonb not null default '[]'::jsonb,
  legal_basis jsonb not null default '[]'::jsonb,
  recommendation text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ix_legal_documents_title on legal_documents(title);
create index if not exists ix_legal_documents_level on legal_documents(level);
create index if not exists ix_legal_documents_status on legal_documents(status);
create index if not exists ix_legal_documents_source_file on legal_documents(source_file);
create index if not exists ix_legal_versions_document_id on legal_versions(document_id);
create index if not exists ix_legal_versions_version_label on legal_versions(version_label);
create index if not exists ix_legal_versions_status on legal_versions(status);
create index if not exists ix_legal_versions_source_file on legal_versions(source_file);
create index if not exists ix_legal_articles_document_id on legal_articles(document_id);
create index if not exists ix_legal_articles_article_no on legal_articles(article_no);
create index if not exists ix_legal_chunks_document_id on legal_chunks(document_id);
create index if not exists ix_legal_chunks_article_id on legal_chunks(article_id);
create index if not exists ix_legal_chunks_doc_chunk on legal_chunks(document_id, chunk_no);
create index if not exists ix_uploaded_materials_text_hash on uploaded_materials(text_hash);
create index if not exists ix_audit_reports_report_id on audit_reports(report_id);
create index if not exists ix_audit_reports_material_id on audit_reports(material_id);
create index if not exists ix_audit_reports_overall_level on audit_reports(overall_level);
create index if not exists ix_audit_risks_report_db_id on audit_risks(report_db_id);
create index if not exists ix_audit_risks_title on audit_risks(title);
create index if not exists ix_audit_risks_severity on audit_risks(severity);
