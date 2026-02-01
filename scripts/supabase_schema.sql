create extension if not exists pgcrypto;

create table if not exists complaints (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  full_name text not null,
  phone text null,
  email text null,
  complaint_text text not null,
  borough text null,
  location_details text null,
  incident_time text null,
  urgency_hint text null,
  status text not null default 'new'
);

create table if not exists executions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  complaint_id uuid references complaints(id),
  final_agency text,
  final_urgency text,
  final_action text,
  confidence float,
  escalated boolean,
  top_matches jsonb,
  steps jsonb,
  response_text text
);
