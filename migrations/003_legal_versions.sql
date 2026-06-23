-- Normalize legal document versions into a dedicated table.
-- This keeps the legal document identity separate from revision/effectiveness data.

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

create index if not exists ix_legal_versions_document_id on legal_versions(document_id);
create index if not exists ix_legal_versions_version_label on legal_versions(version_label);
create index if not exists ix_legal_versions_status on legal_versions(status);
create index if not exists ix_legal_versions_source_file on legal_versions(source_file);
