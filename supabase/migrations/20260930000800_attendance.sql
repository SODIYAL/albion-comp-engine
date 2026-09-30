-- History (platform phase 8): attendance, kept apart from the sign-up. A
-- sign-up is a live claim on a slot: it goes when the player cancels or
-- the caller removes them. The attendance row is the guild's record of
-- that player on that CTA: made when they sign up, kept when the claim
-- goes (a cancellation), settled when the CTA completes (a reserve stays
-- a reserve; the slot's weapon and the declared weapons are copied in),
-- and marked by the caller (attended, no-show) whenever, completion
-- included. A player confirms their own sign-up (signed_up <->
-- confirmed) before the CTA completes; nothing else is theirs to write.
--
-- Who writes the record:
--   attendance_record   a trigger with its definer's rights (a listed
--                       exception, supabase/README.md rule 8): the
--                       record is the guild's, so no API role holds an
--                       insert or delete grant on it; the mirror from
--                       sign-ups (made, moved, adopted, gone) and the
--                       settlement at completion write it
--   confirm_sign_up     the player, their own row, signed_up <-> confirmed
--   mark_attendance,    the caller roles, any listed status, any time;
--   mark_all_attended   marked_by and marked_at follow (the guard)
--
-- The statuses: signed_up, confirmed, attended, no_show, cancelled,
-- reserve. Deleting an account deletes its records (rule 2); deleting a
-- CTA deletes them all. tests/test_supabase_schema.py and
-- tests/test_supabase_rls.mjs pin all of it.


-- 1. attendance ---------------------------------------------------------------

create table if not exists public.attendance (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events (id) on delete cascade,
  signup_id uuid references public.signups (id) on delete set null,
  user_id uuid references public.profiles (id) on delete cascade,
  guest_token_hash text,
  player_name text not null,
  position smallint,
  weapon_id text,
  declared text[] not null default '{}',
  status text not null default 'signed_up',
  marked_by uuid references public.profiles (id) on delete set null,
  marked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint attendance_one_identity check ((user_id is null) <> (guest_token_hash is null)),
  constraint attendance_token_form check (guest_token_hash is null or guest_token_hash ~ '^[a-f0-9]{64}$'),
  constraint attendance_name_clean check (
    player_name = btrim(player_name) and char_length(player_name) between 1 and 64),
  constraint attendance_weapon_form check (weapon_id is null or weapon_id ~ '^[A-Z0-9_]{1,64}$'),
  constraint attendance_status_known check (
    status in ('signed_up', 'confirmed', 'attended', 'no_show', 'cancelled', 'reserve'))
);

-- one record per player per CTA
create unique index if not exists attendance_one_per_account on public.attendance (event_id, user_id) where user_id is not null;
create unique index if not exists attendance_one_per_guest on public.attendance (event_id, guest_token_hash) where guest_token_hash is not null;
create index if not exists attendance_event_id on public.attendance (event_id);
create index if not exists attendance_signup_id on public.attendance (signup_id);
create index if not exists attendance_user_id on public.attendance (user_id);
create index if not exists attendance_marked_by on public.attendance (marked_by);

comment on table public.attendance is
  'The guild''s record of a player on a CTA, kept apart from the live sign-up: the slot and weapon they ended with, what they declared, and the status (signed_up, confirmed, attended, no_show, cancelled, reserve).';
comment on column public.attendance.signup_id is
  'The live sign-up this record mirrors; null once the claim is gone (a cancellation keeps the record).';
comment on column public.attendance.weapon_id is
  'The weapon of the slot the player held when the CTA completed: what they played.';

alter table public.attendance enable row level security;


-- 2. policies: whoever reads the CTA reads its record; the player confirms
--    their own row, the caller marks any -------------------------------------------

drop policy if exists "Link holders read the record" on public.attendance;
create policy "Link holders read the record" on public.attendance
  for select to anon
  using (exists (select 1 from public.events e where e.id = event_id));

drop policy if exists "Members and link holders read the record" on public.attendance;
create policy "Members and link holders read the record" on public.attendance
  for select to authenticated
  using (exists (select 1 from public.events e where e.id = event_id));

drop policy if exists "Guests confirm their own record" on public.attendance;
create policy "Guests confirm their own record" on public.attendance
  for update to anon
  using (guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true))))
  with check (guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true))));

drop policy if exists "Players confirm their own record and callers mark any" on public.attendance;
create policy "Players confirm their own record and callers mark any" on public.attendance
  for update to authenticated
  using (user_id = (select auth.uid())
         or private.guild_role_of((select e.guild_id from public.events e where e.id = event_id))
            in ('caller', 'officer', 'admin'))
  with check (user_id = (select auth.uid())
              or private.guild_role_of((select e.guild_id from public.events e where e.id = event_id))
                 in ('caller', 'officer', 'admin'));

-- no insert or delete grant to any API role: the record is written by
-- its own trigger; a status is the one column the API writes
revoke all on table public.attendance from anon, authenticated;
grant select on table public.attendance to anon, authenticated;
grant update (status) on table public.attendance to anon, authenticated;

drop trigger if exists attendance_set_updated_at on public.attendance;
create trigger attendance_set_updated_at
  before update on public.attendance
  for each row execute function public.set_updated_at();


-- 3. the guard: who sets which status -------------------------------------------------

-- The record's own trigger (depth 2 and beyond: a sign-up's mirror, the
-- settlement, a foreign key) writes freely. A caller sets any listed
-- status, and the mark carries their id and the time. A player moves
-- their own row between signed_up and confirmed, before completion.
create or replace function public.attendance_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  is_caller boolean := false;
begin
  if pg_trigger_depth() >= 2 then
    return new;
  end if;

  if me is not null then
    is_caller := private.guild_role_of((select e.guild_id from public.events e where e.id = new.event_id))
                 in ('caller', 'officer', 'admin');
  end if;

  if is_caller then
    if new.status is distinct from old.status then
      new.marked_by := me;
      new.marked_at := now();
    end if;
    return new;
  end if;

  if new.status not in ('signed_up', 'confirmed') or old.status not in ('signed_up', 'confirmed') then
    raise exception 'a player confirms or unconfirms; the caller marks attendance' using errcode = '42501';
  end if;
  if (select e.status from public.events e where e.id = new.event_id) = 'completed' then
    raise exception 'the CTA is completed; its record is the caller''s to mark' using errcode = '55000';
  end if;
  return new;
end;
$$;

revoke execute on function public.attendance_guard() from public, anon, authenticated;

drop trigger if exists attendance_guard on public.attendance;
create trigger attendance_guard
  before update on public.attendance
  for each row execute function public.attendance_guard();


-- 4. the record's trigger: the mirror from sign-ups, the settlement at completion --

-- Runs with its definer's rights: the record is the guild's, and no API
-- role holds an insert or delete grant on it. A record is found by the
-- player's identity, never by the sign-up id (a foreign key sets that to
-- null before this trigger runs).
create or replace function public.attendance_record()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_table_name = 'events' then
    -- the settlement: a reserve stays a reserve, the slot's weapon and
    -- the declared weapons are what the history keeps
    if new.status = 'completed' and old.status is distinct from 'completed' then
      update public.attendance a
         set weapon_id = (select s.weapon_id from public.event_slots s where s.event_id = a.event_id and s.position = a.position),
             declared = coalesce((select x.weapons from public.signups x where x.id = a.signup_id), a.declared),
             status = case when a.status in ('signed_up', 'confirmed') and a.position is null then 'reserve' else a.status end
       where a.event_id = new.id;
    end if;
    return null;
  end if;

  if tg_op = 'INSERT' then
    if new.user_id is not null then
      insert into public.attendance (event_id, signup_id, user_id, player_name, position, declared, status)
      values (new.event_id, new.id, new.user_id, new.player_name, new.position, new.weapons, 'signed_up')
      on conflict (event_id, user_id) where user_id is not null do update
         set signup_id = excluded.signup_id, player_name = excluded.player_name, position = excluded.position,
             declared = excluded.declared, status = 'signed_up', marked_by = null, marked_at = null;
    else
      insert into public.attendance (event_id, signup_id, guest_token_hash, player_name, position, declared, status)
      values (new.event_id, new.id, new.guest_token_hash, new.player_name, new.position, new.weapons, 'signed_up')
      on conflict (event_id, guest_token_hash) where guest_token_hash is not null do update
         set signup_id = excluded.signup_id, player_name = excluded.player_name, position = excluded.position,
             declared = excluded.declared, status = 'signed_up', marked_by = null, marked_at = null;
    end if;
    return null;
  end if;

  if tg_op = 'UPDATE' then
    -- a move, a new name, an adoption: the record follows
    begin
      update public.attendance a
         set user_id = new.user_id, guest_token_hash = new.guest_token_hash, signup_id = new.id,
             player_name = new.player_name, position = new.position, declared = new.weapons
       where a.event_id = new.event_id
         and ((old.user_id is not null and a.user_id = old.user_id)
              or (old.guest_token_hash is not null and a.guest_token_hash = old.guest_token_hash));
    exception when unique_violation then
      -- the account already has a record on this CTA: the guest's keeps
      -- its own identity
      null;
    end;
    return null;
  end if;

  -- DELETE: the claim is gone; the record says cancelled unless the
  -- caller has already marked it
  update public.attendance a
     set status = case when a.status in ('signed_up', 'confirmed') then 'cancelled' else a.status end,
         signup_id = null
   where a.event_id = old.event_id
     and ((old.user_id is not null and a.user_id = old.user_id)
          or (old.guest_token_hash is not null and a.guest_token_hash = old.guest_token_hash));
  return null;
end;
$$;

revoke execute on function public.attendance_record() from public, anon, authenticated;

drop trigger if exists signups_attendance on public.signups;
create trigger signups_attendance
  after insert or update or delete on public.signups
  for each row execute function public.attendance_record();

drop trigger if exists events_attendance on public.events;
create trigger events_attendance
  after update on public.events
  for each row execute function public.attendance_record();

-- a mark is a change on the sheet: the live channel says so
drop trigger if exists attendance_changed on public.attendance;
create trigger attendance_changed
  after insert or update or delete on public.attendance
  for each row execute function public.sheet_changed();


-- 5. confirm_sign_up: the player's own record, signed_up <-> confirmed --------------

create or replace function public.confirm_sign_up(code text, token text default null, confirmed boolean default true)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  clean text := upper(btrim(coalesce(code, '')));
  me uuid := (select auth.uid());
  hash text := case when char_length(coalesce(token, '')) < 16 then null else public.claim_hash(token) end;
  ev record;
  a public.attendance;
begin
  if clean !~ '^[A-Z0-9]{10}$' then
    raise exception 'no CTA has this code' using errcode = 'P0002';
  end if;

  perform set_config('app.share_code', clean, true);
  perform set_config('app.claim_token', coalesce(token, ''), true);

  select e.id, e.status into ev from public.events e where e.share_code = clean;
  if ev.id is null then
    raise exception 'no CTA has this code' using errcode = 'P0002';
  end if;

  update public.attendance x
     set status = case when confirmed then 'confirmed' else 'signed_up' end
   where x.event_id = ev.id
     and x.signup_id is not null
     and ((me is not null and x.user_id = me) or (hash is not null and x.guest_token_hash = hash))
  returning * into a;

  if a.id is null then
    raise exception 'no sign-up of yours to confirm on this CTA' using errcode = 'P0002';
  end if;

  perform set_config('app.share_code', '', true);
  perform set_config('app.claim_token', '', true);
  return jsonb_build_object('id', a.id, 'status', a.status);
end;
$$;

revoke execute on function public.confirm_sign_up(text, text, boolean) from public;
grant execute on function public.confirm_sign_up(text, text, boolean) to anon, authenticated;


-- 6. mark_attendance and mark_all_attended: the caller's marks ---------------------

-- One record, one status (any listed). Runs as the caller: the policy's
-- caller branch decides; a mark the policy refuses changes nothing and
-- is 42501; the guard stamps marked_by and marked_at.
create or replace function public.mark_attendance(attendance_id uuid, mark text)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  a public.attendance;
begin
  update public.attendance x
     set status = mark
   where x.id = attendance_id
  returning * into a;

  if a.id is null then
    raise exception 'the record was not found, or your role does not mark it' using errcode = '42501';
  end if;

  return jsonb_build_object('id', a.id, 'status', a.status, 'marked_at', a.marked_at);
end;
$$;

revoke execute on function public.mark_attendance(uuid, text) from public, anon;
grant execute on function public.mark_attendance(uuid, text) to authenticated;

-- everyone still signed up or confirmed in a slot attended; the caller
-- then marks the no-shows one by one. Returns how many rows changed.
create or replace function public.mark_all_attended(event_id uuid)
returns integer
language plpgsql
security invoker
set search_path = ''
as $$
declare
  n integer;
begin
  update public.attendance x
     set status = 'attended'
   where x.event_id = mark_all_attended.event_id
     and x.status in ('signed_up', 'confirmed')
     and x.position is not null;
  get diagnostics n = row_count;
  return n;
end;
$$;

revoke execute on function public.mark_all_attended(uuid) from public, anon;
grant execute on function public.mark_all_attended(uuid) to authenticated;


-- 7. event_by_code: the sheet carries the record --------------------------------

create or replace function public.event_by_code(code text, token text default null)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  clean text := upper(btrim(coalesce(code, '')));
  me uuid := (select auth.uid());
  hash text := case when coalesce(token, '') = '' then null else public.claim_hash(token) end;
  ev record;
  sheet jsonb;
begin
  if clean !~ '^[A-Z0-9]{10}$' then
    raise exception 'no CTA has this code' using errcode = 'P0002';
  end if;

  perform set_config('app.share_code', clean, true);

  select e.id, e.guild_id, e.name, e.content, e.style, e.planned_size, e.starts_at, e.mass_at,
         e.notes, e.status, e.share_hash
    into ev
    from public.events e
   where e.share_code = clean;

  if ev.id is null then
    raise exception 'no CTA has this code' using errcode = 'P0002';
  end if;

  sheet := jsonb_build_object(
    'event', to_jsonb(ev) || jsonb_build_object('share_code', clean),
    'guild', (select jsonb_build_object('id', g.id, 'name', g.name, 'albion_server', g.albion_server)
                from public.guilds g where g.id = ev.guild_id),
    'slots', (select coalesce(jsonb_agg(jsonb_build_object(
                'position', s.position, 'weapon_id', s.weapon_id, 'role', s.role, 'note', s.note)
                order by s.position), '[]'::jsonb)
                from public.event_slots s where s.event_id = ev.id),
    'signups', (select coalesce(jsonb_agg(jsonb_build_object(
                  'id', s.id, 'position', s.position, 'player_name', s.player_name, 'item_power', s.item_power,
                  'can_swap', s.can_swap, 'weapons', to_jsonb(s.weapons), 'note', s.note,
                  'account', s.user_id is not null, 'created_at', s.created_at,
                  'attendance', (select a.status from public.attendance a where a.signup_id = s.id),
                  'attendance_id', (select a.id from public.attendance a where a.signup_id = s.id))
                  order by s.created_at), '[]'::jsonb)
                  from public.signups s where s.event_id = ev.id),
    'attendance', (select coalesce(jsonb_agg(jsonb_build_object(
                     'id', a.id, 'signup_id', a.signup_id, 'player_name', a.player_name, 'position', a.position,
                     'weapon_id', a.weapon_id, 'declared', to_jsonb(a.declared), 'status', a.status,
                     'marked_at', a.marked_at, 'account', a.user_id is not null)
                     order by a.created_at), '[]'::jsonb)
                     from public.attendance a where a.event_id = ev.id),
    'mine', (select jsonb_build_object(
               'id', s.id, 'position', s.position, 'player_name', s.player_name, 'item_power', s.item_power,
               'can_swap', s.can_swap, 'weapons', to_jsonb(s.weapons), 'note', s.note,
               'attendance', (select a.status from public.attendance a where a.signup_id = s.id))
               from public.signups s
              where s.event_id = ev.id
                and ((me is not null and s.user_id = me) or (hash is not null and s.guest_token_hash = hash))
              limit 1));

  perform set_config('app.share_code', '', true);
  return sheet;
end;
$$;

revoke execute on function public.event_by_code(text, text) from public;
grant execute on function public.event_by_code(text, text) to anon, authenticated;
