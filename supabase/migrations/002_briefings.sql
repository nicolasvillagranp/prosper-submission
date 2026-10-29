-- Audio briefing requests: the page asks, the Docker worker makes the mp3 and marks it ready.
-- The page reads its own rows (RLS) and plays recordings/<user_id>/briefings/<topic_id>.mp3.

create table public.briefings (
  topic_id     uuid primary key references public.topics (id) on delete cascade,
  user_id      uuid not null references auth.users (id) on delete cascade,
  status       text not null default 'requested'
               check (status in ('requested', 'working', 'ready', 'failed')),
  audio_path   text,
  script       text,
  error        text,
  requested_at timestamptz not null default now(),
  ready_at     timestamptz
);

create index briefings_pending on public.briefings (requested_at) where status = 'requested';

alter table public.briefings enable row level security;

create policy "briefings: read own" on public.briefings
  for select to authenticated using ((select auth.uid()) = user_id);

-- A user may request a briefing only for one of their own topics.
create policy "briefings: request own" on public.briefings
  for insert to authenticated
  with check (
    (select auth.uid()) = user_id
    and status = 'requested'
    and exists (select 1 from public.topics t where t.id = topic_id and t.user_id = (select auth.uid()))
  );

-- Asking again (e.g. after a failure) puts it back in the queue; only the worker sets other states.
create policy "briefings: retry own" on public.briefings
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check (
    (select auth.uid()) = user_id
    and status = 'requested'
    and exists (select 1 from public.topics t where t.id = topic_id and t.user_id = (select auth.uid()))
  );
