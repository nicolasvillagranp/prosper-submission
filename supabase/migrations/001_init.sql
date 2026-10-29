-- Profiles, daily topics, interview sessions and the recordings bucket.
-- Row level security on every table: a signed-in user only ever sees their own rows.
-- Writes to topics and sessions come from server code (morning job, agent) with the
-- secret key, which bypasses RLS, so users get no insert/update policies there.

-- Profiles: what the user sets at onboarding and changes in Settings ------------------
create table public.profiles (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  interests  text not null check (char_length(interests) between 3 and 2000),
  language   text not null default 'es' check (language in ('es', 'en')),
  depth      text not null default 'intermediate' check (depth in ('beginner', 'intermediate', 'expert')),
  tone       text not null default 'balanced' check (tone in ('explainer', 'balanced', 'sparring')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles: read own" on public.profiles
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "profiles: create own" on public.profiles
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "profiles: update own" on public.profiles
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create function public.touch_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

-- Topics: the morning job writes up to 5 per user per day --------------------------
create table public.topics (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,
  date           date not null,
  rank           smallint not null check (rank >= 1),
  title          text not null,
  summary        text not null,
  persona        jsonb not null,
  config         jsonb not null,
  brief          text not null,
  study_dialogue text not null,
  sources        jsonb not null,
  created_at     timestamptz not null default now(),
  unique (user_id, date, rank)
);

create index topics_user_date on public.topics (user_id, date desc);

alter table public.topics enable row level security;

create policy "topics: read own" on public.topics
  for select to authenticated using ((select auth.uid()) = user_id);

-- Sessions: one row per interview, written by the web server and the agent --------
create table public.sessions (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,
  topic_id       uuid references public.topics (id) on delete set null,
  room           text not null unique,
  record         boolean not null default false,
  started_at     timestamptz not null default now(),
  ended_at       timestamptz,
  transcript     jsonb,
  recording_path text
);

create index sessions_user_started on public.sessions (user_id, started_at desc);

alter table public.sessions enable row level security;

create policy "sessions: read own" on public.sessions
  for select to authenticated using ((select auth.uid()) = user_id);

-- Recordings: private bucket, files under <user_id>/<session_id>/ -----------------
insert into storage.buckets (id, name, public)
values ('recordings', 'recordings', false)
on conflict (id) do nothing;

create policy "recordings: read own" on storage.objects
  for select to authenticated
  using (bucket_id = 'recordings' and (storage.foldername(name))[1] = (select auth.uid())::text);
