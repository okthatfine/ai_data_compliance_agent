-- Optional pgvector migration for large-scale semantic retrieval.
-- Run after 001_postgres_schema.sql when PostgreSQL has pgvector installed.
-- Adjust vector dimensions to match the selected embedding model.

create extension if not exists vector;

alter table legal_chunks
  add column if not exists embedding_model varchar(128) not null default '',
  add column if not exists embedding_dim integer not null default 0,
  add column if not exists embedding vector(1024);

-- HNSW is a good default for read-heavy legal retrieval. Recreate this index
-- with the actual vector dimension if you choose a non-1024 embedding model.
create index if not exists ix_legal_chunks_embedding_hnsw
  on legal_chunks using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create index if not exists ix_legal_chunks_metadata_gin
  on legal_chunks using gin (metadata_json);
