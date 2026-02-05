-- 2026-02-04_create_uploads_table.sql
create table if not exists uploads (
  id text primary key,
  bucket text not null,
  path text not null,
  filename text not null,
  metadata jsonb,
  created_at timestamptz not null default now()
);

create index if not exists uploads_created_at_idx on uploads (created_at desc);
