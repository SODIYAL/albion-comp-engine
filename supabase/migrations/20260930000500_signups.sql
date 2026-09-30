-- Sign-up (platform phase 5): players claiming slots on a CTA. A sign-up
-- names the event, the slot claimed (or none: a reserve), who signs up (an
-- account, or a guest known by the hash of a claim token their browser
-- keeps), the name shown, item power, whether they can swap, the weapons
-- declared and a note. Claiming a slot is one conditional statement under
-- a unique index, so two claims on one slot cannot both succeed, and a
-- sign-up is written only while the CTA is open.
--
-- A guest reaches ONE CTA through its share code (supabase/README.md
-- rule 13): the code rides the statement as a transaction-local setting
-- (rule 11), the policies for `anon` check it, and the grants to `anon`
-- are exactly the columns a guest sees and the sign-up a guest writes.
-- Every guest function runs as the caller (security invoker); nothing here
-- runs with its definer's rights. Members reach the same rows through
-- their guild; a signed-in player who is not a member reaches them
-- through the code, like a guest, and signs up as an account.
--
-- The claim token never reaches the database: the client keeps it, the
-- statement carries it (`app.claim_token`), and the row stores its
-- SHA-256. An account signing up from the browser that made a guest
-- sign-up on the same CTA adopts that sign-up. tests/test_supabase_schema.py
-- and tests/test_supabase_rls.mjs pin all of it.


-- 1. the hash a guest's row is keyed by -------------------------------------

create or replace function public.claim_hash(token text)
returns text
language sql
immutable
security invoker
set search_path = ''
as $$
  select encode(sha256(convert_to(token, 'utf8')), 'hex');
$$;

revoke execute on function public.claim_hash(text) from public;
grant execute on function public.claim_hash(text) to anon, authenticated;


-- 2. signups ----------------------------------------------------------------

create table if not exists public.signups (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events (id) on delete cascade,
  position smallint,
  user_id uuid default auth.uid() references public.profiles (id) on delete cascade,
  guest_token_hash text,
  player_name text not null,
  item_power smallint,
  can_swap boolean not null default false,
  weapons text[] not null default '{}',
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- the slot claimed is one of the event's; a removed slot leaves its
  -- claimant as a reserve
  constraint signups_slot foreign key (event_id, position)
    references public.event_slots (event_id, position) on delete set null (position),
  constraint signups_one_identity check ((user_id is null) <> (guest_token_hash is null)),
  constraint signups_token_form check (guest_token_hash is null or guest_token_hash ~ '^[a-f0-9]{64}$'),
  constraint signups_name_clean check (
    player_name = btrim(player_name) and char_length(player_name) between 1 and 64),
  constraint signups_item_power check (item_power is null or item_power between 0 and 3000),
  constraint signups_weapons_bound check (coalesce(array_length(weapons, 1), 0) <= 10),
  constraint signups_note_clean check (
    note is null or (note = btrim(note) and char_length(note) between 1 and 200))
);

-- one claimant per slot, one sign-up per account and per guest on an event
create unique index if not exists signups_one_per_slot on public.signups (event_id, position) where position is not null;
create unique index if not exists signups_one_per_account on public.signups (event_id, user_id) where user_id is not null;
create unique index if not exists signups_one_per_guest on public.signups (event_id, guest_token_hash) where guest_token_hash is not null;
-- the foreign keys' covering indexes (event_id leads both)
create index if not exists signups_event_position on public.signups (event_id, position);
create index if not exists signups_user_id on public.signups (user_id);

comment on table public.signups is
  'A player on a CTA: the slot claimed (null: a reserve), an account or a guest (the hash of a claim token the browser keeps), the name shown, item power, can swap, the weapons declared, a note.';
comment on column public.signups.guest_token_hash is
  'SHA-256 of the guest''s claim token (public.claim_hash). The token itself never reaches the database. Null for an account.';

alter table public.signups enable row level security;


-- 3. a guest's reach: the share code as the key --------------------------------------

-- the CTA the code names (members read theirs as before)
alter policy "Members read their guild's events" on public.events
  using (private.guild_role_of(guild_id) is not null
         or share_code = (select current_setting('app.share_code', true)));

drop policy if exists "Link holders read the CTA" on public.events;
create policy "Link holders read the CTA" on public.events
  for select to anon
  using (share_code = (select current_setting('app.share_code', true)));

-- share_code included: the guest functions select the CTA by it, and
-- the policy above already limits a guest to the one CTA the code names
grant select (id, guild_id, name, content, style, planned_size, starts_at, mass_at, notes, status, share_code, share_hash)
  on table public.events to anon;

-- its slots (the event's policy decides, for either role)
drop policy if exists "Link holders read the CTA's slots" on public.event_slots;
create policy "Link holders read the CTA's slots" on public.event_slots
  for select to anon
  using (exists (select 1 from public.events e where e.id = event_id));

grant select on table public.event_slots to anon;

-- the guild's name above the sheet (guilds.id qualified: a bare id inside
-- the subquery would name the event's)
alter policy "Members read their guilds" on public.guilds
  using (private.guild_role_of(id) is not null or created_by = (select auth.uid())
         or exists (select 1 from public.events e where e.guild_id = guilds.id
                      and e.share_code = (select current_setting('app.share_code', true))));

drop policy if exists "Link holders read the CTA's guild" on public.guilds;
create policy "Link holders read the CTA's guild" on public.guilds
  for select to anon
  using (exists (select 1 from public.events e where e.guild_id = guilds.id
                   and e.share_code = (select current_setting('app.share_code', true))));

grant select (id, name, albion_server) on table public.guilds to anon;


-- 4. policies: signups ------------------------------------------------------------------

-- reading: whoever reads the CTA reads its sheet
drop policy if exists "Link holders read the sheet" on public.signups;
create policy "Link holders read the sheet" on public.signups
  for select to anon
  using (exists (select 1 from public.events e where e.id = event_id));

drop policy if exists "Members and link holders read the sheet" on public.signups;
create policy "Members and link holders read the sheet" on public.signups
  for select to authenticated
  using (exists (select 1 from public.events e where e.id = event_id));

-- writing: while the CTA is open, a guest under the token's hash, an
-- account under its own id
drop policy if exists "Guests sign up while open" on public.signups;
create policy "Guests sign up while open" on public.signups
  for insert to anon
  with check (user_id is null
              and guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true)))
              and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'));

drop policy if exists "Players sign up while open" on public.signups;
create policy "Players sign up while open" on public.signups
  for insert to authenticated
  with check (user_id = (select auth.uid())
              and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'));

drop policy if exists "Guests edit their sign-up while open" on public.signups;
create policy "Guests edit their sign-up while open" on public.signups
  for update to anon
  using (guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true)))
         and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'))
  with check (user_id is null
              and guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true)))
              and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'));

-- an account edits its own sign-up, and adopts the guest sign-up its
-- browser's token names (the row becomes the account's)
drop policy if exists "Players edit their sign-up while open" on public.signups;
create policy "Players edit their sign-up while open" on public.signups
  for update to authenticated
  using ((user_id = (select auth.uid())
          or guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true))))
         and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'))
  with check (user_id = (select auth.uid()) and guest_token_hash is null
              and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'));

-- cancelling: until the CTA is completed (the history keeps its sheet)
drop policy if exists "Guests cancel their sign-up" on public.signups;
create policy "Guests cancel their sign-up" on public.signups
  for delete to anon
  using (guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true)))
         and exists (select 1 from public.events e where e.id = event_id and e.status <> 'completed'));

drop policy if exists "Players cancel their sign-up" on public.signups;
create policy "Players cancel their sign-up" on public.signups
  for delete to authenticated
  using (user_id = (select auth.uid())
         and exists (select 1 from public.events e where e.id = event_id and e.status <> 'completed'));

revoke all on table public.signups from anon, authenticated;
grant select, delete on table public.signups to anon, authenticated;
grant insert (event_id, position, guest_token_hash, player_name, item_power, can_swap, weapons, note)
  on table public.signups to anon;
grant update (position, player_name, item_power, can_swap, weapons, note)
  on table public.signups to anon;
grant insert (event_id, position, player_name, item_power, can_swap, weapons, note)
  on table public.signups to authenticated;
grant update (position, user_id, guest_token_hash, player_name, item_power, can_swap, weapons, note)
  on table public.signups to authenticated;

drop trigger if exists signups_set_updated_at on public.signups;
create trigger signups_set_updated_at
  before update on public.signups
  for each row execute function public.set_updated_at();

-- a CTA takes at most 120 sign-ups (a storage bound against abuse); every
-- weapon declared has a dataset key's form, listed once
create or replace function public.signups_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT'
     and (select count(*) from public.signups where event_id = new.event_id) >= 120 then
    raise exception 'a CTA takes at most 120 sign-ups' using errcode = '23514';
  end if;
  if exists (select 1 from unnest(new.weapons) as w where w !~ '^[A-Z0-9_]{1,64}$') then
    raise exception 'a declared weapon is not a weapon key' using errcode = '23514';
  end if;
  if (select count(distinct w) from unnest(new.weapons) as w) <> coalesce(array_length(new.weapons, 1), 0) then
    raise exception 'a weapon is declared twice' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke execute on function public.signups_guard() from public, anon, authenticated;

drop trigger if exists signups_guard on public.signups;
create trigger signups_guard
  before insert or update on public.signups
  for each row execute function public.signups_guard();


-- 5. the sheet: event_by_code --------------------------------------------------

-- The CTA a share code names, with its guild, slots, sign-ups and the
-- caller's own sign-up (an account's by id, a guest's by the token).
-- Runs as the caller: the code rides the statement and the policies above
-- decide what comes back. A code that names nothing is P0002.
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
                  'account', s.user_id is not null, 'created_at', s.created_at)
                  order by s.created_at), '[]'::jsonb)
                  from public.signups s where s.event_id = ev.id),
    'mine', (select jsonb_build_object(
               'id', s.id, 'position', s.position, 'player_name', s.player_name, 'item_power', s.item_power,
               'can_swap', s.can_swap, 'weapons', to_jsonb(s.weapons), 'note', s.note)
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


-- 6. sign_up: one sign-up per player per CTA, claimed in one statement -----------

-- The payload: {position?, player_name?, item_power?, can_swap?, weapons?,
-- note?}. An account signs up under its id, named after its character
-- unless the payload names it; a guest under the token's hash, and must
-- give a name. A second call from the same player updates the sign-up
-- (ON CONFLICT on the player's own index); a slot already claimed is the
-- unique index's 23505. A CTA that is not open is 55000. Runs as the
-- caller: the policies decide.
create or replace function public.sign_up(code text, token text, signup jsonb)
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
  s public.signups;
  pos smallint := nullif(signup ->> 'position', '')::smallint;
  who text := nullif(btrim(coalesce(signup ->> 'player_name', '')), '');
  ip smallint := nullif(signup ->> 'item_power', '')::smallint;
  swap boolean := coalesce((signup ->> 'can_swap')::boolean, false);
  declared text[] := coalesce((select array_agg(w.x) from jsonb_array_elements_text(coalesce(signup -> 'weapons', '[]'::jsonb)) as w(x)), '{}');
  memo text := nullif(btrim(coalesce(signup ->> 'note', '')), '');
begin
  if clean !~ '^[A-Z0-9]{10}$' then
    raise exception 'no CTA has this code' using errcode = 'P0002';
  end if;

  if me is null and hash is null then
    raise exception 'a guest sign-up needs a claim token' using errcode = '42501';
  end if;

  perform set_config('app.share_code', clean, true);
  perform set_config('app.claim_token', coalesce(token, ''), true);

  select e.id, e.status into ev from public.events e where e.share_code = clean;
  if ev.id is null then
    raise exception 'no CTA has this code' using errcode = 'P0002';
  end if;
  if ev.status <> 'open' then
    raise exception 'sign-up is not open for this CTA' using errcode = '55000';
  end if;

  if me is not null then
    who := coalesce(who, (select coalesce(p.albion_name, p.display_name) from public.profiles p where p.id = me));
    if who is null then
      raise exception 'name your character in the profile first' using errcode = '23502';
    end if;

    -- the guest sign-up this browser made becomes the account's
    if hash is not null
       and not exists (select 1 from public.signups x where x.event_id = ev.id and x.user_id = me) then
      update public.signups x
         set user_id = me, guest_token_hash = null
       where x.event_id = ev.id and x.guest_token_hash = hash;
    end if;

    insert into public.signups (event_id, position, player_name, item_power, can_swap, weapons, note)
    values (ev.id, pos, who, ip, swap, declared, memo)
    on conflict (event_id, user_id) where user_id is not null do update
       set position = excluded.position, player_name = excluded.player_name, item_power = excluded.item_power,
           can_swap = excluded.can_swap, weapons = excluded.weapons, note = excluded.note
    returning * into s;
  else
    if who is null then
      raise exception 'a guest sign-up needs a name' using errcode = '23502';
    end if;

    insert into public.signups (event_id, position, guest_token_hash, player_name, item_power, can_swap, weapons, note)
    values (ev.id, pos, hash, who, ip, swap, declared, memo)
    on conflict (event_id, guest_token_hash) where guest_token_hash is not null do update
       set position = excluded.position, player_name = excluded.player_name, item_power = excluded.item_power,
           can_swap = excluded.can_swap, weapons = excluded.weapons, note = excluded.note
    returning * into s;
  end if;

  perform set_config('app.share_code', '', true);
  perform set_config('app.claim_token', '', true);

  return jsonb_build_object(
    'id', s.id, 'position', s.position, 'player_name', s.player_name, 'item_power', s.item_power,
    'can_swap', s.can_swap, 'weapons', to_jsonb(s.weapons), 'note', s.note);
end;
$$;

revoke execute on function public.sign_up(text, text, jsonb) from public;
grant execute on function public.sign_up(text, text, jsonb) to anon, authenticated;


-- 7. cancel_sign_up: the player's own row goes, until the CTA is completed ------

create or replace function public.cancel_sign_up(code text, token text default null)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  clean text := upper(btrim(coalesce(code, '')));
  me uuid := (select auth.uid());
  hash text := case when char_length(coalesce(token, '')) < 16 then null else public.claim_hash(token) end;
  ev record;
  n integer;
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
  if ev.status = 'completed' then
    raise exception 'the CTA is completed; its sheet is kept' using errcode = '55000';
  end if;

  delete from public.signups s
   where s.event_id = ev.id
     and ((me is not null and s.user_id = me) or (hash is not null and s.guest_token_hash = hash));
  get diagnostics n = row_count;

  perform set_config('app.share_code', '', true);
  perform set_config('app.claim_token', '', true);
  return n > 0;
end;
$$;

revoke execute on function public.cancel_sign_up(text, text) from public;
grant execute on function public.cancel_sign_up(text, text) to anon, authenticated;
