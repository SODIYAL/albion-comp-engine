-- CTAs (platform phase 4): a guild's events and their slots. An event is a
-- CTA a caller runs: the name, when it starts and when the guild masses,
-- notes, a status (draft / open / locked / completed), a share code for
-- the sign-up link (phase 5), the comp it was made from and up to 60
-- slots COPIED from that template when the event is created. Editing an
-- event never touches its template, and deleting the template leaves the
-- event whole. Every table and function follows supabase/README.md;
-- tests/test_supabase_schema.py and tests/test_supabase_rls.mjs pin them.
--
-- Who does what:
--   every member       reads the guild's events and slots
--   caller, officer,   create, edit, move through the statuses and delete
--   admin              events (the caller's tool, as comps are)
--
-- The status moves draft -> open -> locked -> completed, open and locked
-- back a step; completed is final. A completed event keeps its slots
-- (phase 8 reads them as history): no slot is added, changed or removed.


-- 1. events -----------------------------------------------------------------

create table if not exists public.events (
  id uuid primary key default gen_random_uuid(),
  guild_id uuid not null references public.guilds (id) on delete cascade,
  template_id uuid references public.comp_templates (id) on delete set null,
  name text not null,
  content text not null default 'territory_defense',
  style text,
  planned_size smallint not null default 20,
  starts_at timestamptz not null,
  mass_at timestamptz,
  notes text,
  status text not null default 'draft',
  share_code text not null default public.new_join_code(),
  share_hash text,
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  updated_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint events_name_clean check (
    name = btrim(name) and char_length(name) between 1 and 64),
  constraint events_content_form check (content ~ '^[a-z0-9_]{1,40}$'),
  constraint events_style_form check (style is null or style ~ '^[a-z0-9_]{1,40}$'),
  constraint events_planned_size check (planned_size between 2 and 60),
  constraint events_mass_before_start check (mass_at is null or mass_at <= starts_at),
  constraint events_notes_bound check (notes is null or char_length(notes) <= 1000),
  constraint events_status_known check (status in ('draft', 'open', 'locked', 'completed')),
  constraint events_share_code_form check (share_code ~ '^[A-Z0-9]{10}$'),
  constraint events_share_code_unique unique (share_code),
  constraint events_share_hash_form check (
    share_hash is null
    or (char_length(share_hash) <= 8000 and share_hash ~ '^[A-Za-z0-9_.,=&%:~!*()-]+$'))
);

-- the guild's calendar: its events by start; the leading column covers
-- the foreign key
create index if not exists events_guild_starts on public.events (guild_id, starts_at);
create index if not exists events_template_id on public.events (template_id);
create index if not exists events_created_by on public.events (created_by);
create index if not exists events_updated_by on public.events (updated_by);

comment on table public.events is
  'A CTA a guild runs: name, start and mass time, notes, status, the share code of its sign-up link, the comp it was copied from.';
comment on column public.events.template_id is
  'The comp the slots were copied from at creation, null once that comp is deleted. Editing the event never touches it.';
comment on column public.events.status is
  'draft (being set up), open (sign-up open), locked (roster fixed), completed (kept as history; slots frozen).';
comment on column public.events.share_code is
  'A 10-character code for the event''s sign-up link (phase 5). Generated; never chosen.';
comment on column public.events.share_hash is
  'The planner''s share link hash copied from the template, so the event opens in the planner with its kits and picks.';

alter table public.events enable row level security;


-- 2. event_slots ----------------------------------------------------------------

create table if not exists public.event_slots (
  event_id uuid not null references public.events (id) on delete cascade,
  position smallint not null,
  weapon_id text,
  role text,
  note text,
  primary key (event_id, position),
  constraint event_slots_position check (position between 1 and 60),
  constraint event_slots_weapon_form check (
    weapon_id is null or weapon_id ~ '^[A-Z0-9_]{1,64}$'),
  constraint event_slots_role_clean check (
    role is null or (role = btrim(role) and char_length(role) between 1 and 40)),
  constraint event_slots_note_clean check (
    note is null or (note = btrim(note) and char_length(note) between 1 and 200))
);

comment on table public.event_slots is
  'One slot of an event: its position in the roster, the weapon line (null for an open slot), the caller''s role label and a note. Copied from the template; the event''s own from then on.';

alter table public.event_slots enable row level security;


-- 3. policies: events ---------------------------------------------------------------

drop policy if exists "Members read their guild's events" on public.events;
create policy "Members read their guild's events" on public.events
  for select to authenticated
  using (private.guild_role_of(guild_id) is not null);

drop policy if exists "Callers create events" on public.events;
create policy "Callers create events" on public.events
  for insert to authenticated
  with check (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin')
              and created_by = (select auth.uid()));

drop policy if exists "Callers edit events" on public.events;
create policy "Callers edit events" on public.events
  for update to authenticated
  using (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'))
  with check (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'));

drop policy if exists "Callers delete events" on public.events;
create policy "Callers delete events" on public.events
  for delete to authenticated
  using (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'));

revoke all on table public.events from anon, authenticated;
grant select, delete on table public.events to authenticated;
grant insert (guild_id, template_id, name, content, style, planned_size, starts_at, mass_at, notes, status, share_hash)
  on table public.events to authenticated;
grant update (name, content, style, planned_size, starts_at, mass_at, notes, status, share_hash)
  on table public.events to authenticated;

drop trigger if exists events_set_updated_at on public.events;
create trigger events_set_updated_at
  before update on public.events
  for each row execute function public.set_updated_at();

-- a guild keeps at most 200 events (a storage bound against abuse);
-- updated_by follows every change; the status moves one step at a time
-- and completed is final
create or replace function public.events_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if (select count(*) from public.events where guild_id = new.guild_id) >= 200 then
      raise exception 'a guild keeps at most 200 events' using errcode = '23514';
    end if;
    return new;
  end if;
  if new.status is distinct from old.status
     and (old.status, new.status) not in (('draft', 'open'), ('open', 'draft'), ('open', 'locked'),
                                          ('locked', 'open'), ('locked', 'completed')) then
    raise exception 'a CTA moves from draft to open, open to locked and back, locked to completed'
      using errcode = '23514';
  end if;
  new.updated_by := (select auth.uid());
  return new;
end;
$$;

revoke execute on function public.events_guard() from public, anon, authenticated;

drop trigger if exists events_guard on public.events;
create trigger events_guard
  before insert or update on public.events
  for each row execute function public.events_guard();


-- 4. policies: event_slots -------------------------------------------------------------

-- a slot's guild is its event's; the event's own policy decides who reads
-- it, and the caller roles who write it
drop policy if exists "Members read their guild's event slots" on public.event_slots;
create policy "Members read their guild's event slots" on public.event_slots
  for select to authenticated
  using (exists (select 1 from public.events e where e.id = event_id));

drop policy if exists "Callers add event slots" on public.event_slots;
create policy "Callers add event slots" on public.event_slots
  for insert to authenticated
  with check ((select private.guild_role_of(e.guild_id) from public.events e where e.id = event_id)
              in ('caller', 'officer', 'admin'));

drop policy if exists "Callers edit event slots" on public.event_slots;
create policy "Callers edit event slots" on public.event_slots
  for update to authenticated
  using ((select private.guild_role_of(e.guild_id) from public.events e where e.id = event_id)
         in ('caller', 'officer', 'admin'))
  with check ((select private.guild_role_of(e.guild_id) from public.events e where e.id = event_id)
              in ('caller', 'officer', 'admin'));

drop policy if exists "Callers remove event slots" on public.event_slots;
create policy "Callers remove event slots" on public.event_slots
  for delete to authenticated
  using ((select private.guild_role_of(e.guild_id) from public.events e where e.id = event_id)
         in ('caller', 'officer', 'admin'));

revoke all on table public.event_slots from anon, authenticated;
grant select, delete on table public.event_slots to authenticated;
grant insert (event_id, position, weapon_id, role, note) on table public.event_slots to authenticated;
grant update (weapon_id, role, note) on table public.event_slots to authenticated;

-- a completed event keeps its slots: the trigger reads the event under
-- the caller's own policy; a cascade from a deleted event sees no event
-- and lets the slots go with it
create or replace function public.event_slots_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  eid uuid := case when tg_op = 'DELETE' then old.event_id else new.event_id end;
begin
  if (select status from public.events where id = eid) = 'completed' then
    raise exception 'a completed CTA keeps its slots' using errcode = '23514';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke execute on function public.event_slots_guard() from public, anon, authenticated;

drop trigger if exists event_slots_guard on public.event_slots;
create trigger event_slots_guard
  before insert or update or delete on public.event_slots
  for each row execute function public.event_slots_guard();


-- 5. save_event: the event and its slots in one transaction ---------------

-- Security invoker: the policies and grants above bound it. The payload:
--   {id?, guild_id, template_id?, name, content?, style?, planned_size?,
--    starts_at, mass_at?, notes?, status?, share_hash?,
--    slots?: [{position, weapon_id, role, note}, ...]}
-- Without an id the event is created: with a template and no slots key,
-- the template's content, style, size, share hash and slots are copied
-- (a field the payload names wins); with a slots key, those slots are
-- written. With an id the event is updated, and when the payload names
-- slots, unlisted ones go and listed ones are added or changed. A failed
-- save changes nothing.
create or replace function public.save_event(event jsonb)
returns public.events
language plpgsql
security invoker
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  eid uuid := nullif(event ->> 'id', '')::uuid;
  tid uuid := nullif(event ->> 'template_id', '')::uuid;
  slots jsonb := event -> 'slots';
  t public.comp_templates;
  e public.events;
begin
  if me is null then
    raise exception 'sign in to save a CTA' using errcode = '42501';
  end if;

  if slots is not null and jsonb_typeof(slots) <> 'array' then
    raise exception 'slots must be a JSON array' using errcode = '22023';
  end if;

  if slots is not null and jsonb_array_length(slots) > 60 then
    raise exception 'a CTA holds at most 60 slots' using errcode = '23514';
  end if;

  if eid is null then
    if tid is not null then
      select * into t from public.comp_templates where id = tid;
      if t.id is null then
        raise exception 'the comp was not found' using errcode = 'P0002';
      end if;
      if slots is null then
        select coalesce(jsonb_agg(jsonb_build_object(
                 'position', s.position, 'weapon_id', s.weapon_id, 'role', s.role, 'note', s.note)), '[]'::jsonb)
          into slots
          from public.comp_template_slots s
         where s.template_id = t.id;
      end if;
    end if;

    insert into public.events (guild_id, template_id, name, content, style, planned_size,
                               starts_at, mass_at, notes, status, share_hash)
    values ((event ->> 'guild_id')::uuid,
            t.id,
            btrim(coalesce(event ->> 'name', '')),
            coalesce(event ->> 'content', t.content, 'territory_defense'),
            case when event ? 'style' then nullif(event ->> 'style', '') else t.style end,
            coalesce((event ->> 'planned_size')::smallint, t.planned_size, 20),
            (event ->> 'starts_at')::timestamptz,
            nullif(event ->> 'mass_at', '')::timestamptz,
            nullif(btrim(coalesce(event ->> 'notes', '')), ''),
            coalesce(nullif(event ->> 'status', ''), 'draft'),
            case when event ? 'share_hash' then nullif(event ->> 'share_hash', '') else t.share_hash end)
    returning * into e;
  else
    update public.events
       set name = btrim(coalesce(event ->> 'name', name)),
           content = coalesce(event ->> 'content', content),
           style = case when event ? 'style' then nullif(event ->> 'style', '') else style end,
           planned_size = coalesce((event ->> 'planned_size')::smallint, planned_size),
           starts_at = coalesce((event ->> 'starts_at')::timestamptz, starts_at),
           mass_at = case when event ? 'mass_at' then nullif(event ->> 'mass_at', '')::timestamptz else mass_at end,
           notes = case when event ? 'notes' then nullif(btrim(event ->> 'notes'), '') else notes end,
           status = coalesce(nullif(event ->> 'status', ''), status),
           share_hash = case when event ? 'share_hash' then nullif(event ->> 'share_hash', '') else share_hash end
     where id = eid
    returning * into e;
    if e.id is null then
      raise exception 'the CTA was not found, or your role does not edit it' using errcode = '42501';
    end if;
  end if;

  if slots is not null then
    delete from public.event_slots s
     where s.event_id = e.id
       and not exists (
         select 1 from jsonb_array_elements(slots) as x(item)
          where (x.item ->> 'position')::smallint = s.position);

    insert into public.event_slots (event_id, position, weapon_id, role, note)
    select e.id,
           (x.item ->> 'position')::smallint,
           nullif(x.item ->> 'weapon_id', ''),
           nullif(btrim(coalesce(x.item ->> 'role', '')), ''),
           nullif(btrim(coalesce(x.item ->> 'note', '')), '')
      from jsonb_array_elements(slots) as x(item)
    on conflict (event_id, position) do update
       set weapon_id = excluded.weapon_id,
           role = excluded.role,
           note = excluded.note;
  end if;

  return e;
end;
$$;

revoke execute on function public.save_event(jsonb) from public, anon;
grant execute on function public.save_event(jsonb) to authenticated;
