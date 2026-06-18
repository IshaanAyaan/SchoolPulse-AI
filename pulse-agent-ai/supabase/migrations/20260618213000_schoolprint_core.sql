create table if not exists public.schoolprint_agent_runs (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  prompt text not null,
  answer text not null,
  module text,
  used_llm boolean not null default false,
  action_cards jsonb not null default '[]'::jsonb,
  citations jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.schoolprint_operations_logs (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  event_time timestamptz,
  module text not null,
  source text not null,
  payload jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  constraint schoolprint_operations_logs_module_check
    check (module in ('energy', 'water', 'waste', 'events', 'transportation', 'dashboard', 'other'))
);

create table if not exists public.schoolprint_source_documents (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  source_type text not null,
  title text not null,
  url text not null default '',
  content text,
  metadata jsonb not null default '{}'::jsonb,
  constraint schoolprint_source_documents_unique unique (source_type, title, url)
);

alter table public.schoolprint_agent_runs enable row level security;
alter table public.schoolprint_operations_logs enable row level security;
alter table public.schoolprint_source_documents enable row level security;

create index if not exists schoolprint_agent_runs_created_at_idx
  on public.schoolprint_agent_runs (created_at desc);

create index if not exists schoolprint_agent_runs_module_idx
  on public.schoolprint_agent_runs (module);

create index if not exists schoolprint_operations_logs_module_time_idx
  on public.schoolprint_operations_logs (module, event_time desc);

create index if not exists schoolprint_operations_logs_payload_gin_idx
  on public.schoolprint_operations_logs using gin (payload);

create index if not exists schoolprint_source_documents_type_idx
  on public.schoolprint_source_documents (source_type);

create or replace function public.set_schoolprint_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists schoolprint_source_documents_updated_at
  on public.schoolprint_source_documents;

create trigger schoolprint_source_documents_updated_at
before update on public.schoolprint_source_documents
for each row
execute function public.set_schoolprint_updated_at();

comment on table public.schoolprint_agent_runs is
  'SchoolPrint AI voice/chat agent prompts, outputs, cards, and citations.';

comment on table public.schoolprint_operations_logs is
  'Normalized energy, water, waste, event, transportation, and dashboard logs for SchoolPrint AI.';

comment on table public.schoolprint_source_documents is
  'Google Docs, Drive, Sheets, email, and repo context indexed for SchoolPrint AI.';

