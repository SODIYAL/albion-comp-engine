-- Saved comps (platform phase 3): a guild's comp templates and their
-- slots. A template is a planner comp a guild keeps: the content, the
-- planned size, the style, up to 60 slots (the planner's roster cap) each
-- holding a weapon line, a caller's role label and a note, and the
-- planner's own share hash so the kits and spell picks the comp was saved
-- with come back when it is opened. A template is never a live roster:
-- CTAs (phase 4) copy it. Every table and function follows
-- supabase/README.md; tests/test_supabase_schema.py and
-- tests/test_supabase_rls.mjs pin them.
--
-- Who does what:
--   every member       reads the guild's templates and slots
--   caller, officer,   create, edit and delete templates (the caller's
--   admin              first power: comps are the caller's tool)


-- 1. comp_templates ------------------------------------------------------------

create table if not exists public.comp_templates (
  id uuid primary key default gen_random_uuid(),
  guild_id uuid not null references public.guilds (id) on delete cascade,
  name text not null,
  content text not null default 'territory_defense',
  style text,
  planned_size smallint not null default 20,
  notes text,
  share_hash text,
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  updated_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint comp_templates_name_clean check (
    name = btrim(name) and char_length(name) between 1 and 64),
  constraint comp_templates_content_form check (content ~ '^[a-z0-9_]{1,40}$'),
  constraint comp_templates_style_form check (style is null or style ~ '^[a-z0-9_]{1,40}$'),
  constraint comp_templates_planned_size check (planned_size between 2 and 60),
  constraint comp_templates_notes_bound check (notes is null or char_length(notes) <= 1000),
  constraint comp_templates_share_hash_form check (
    share_hash is null
    or (char_length(share_hash) <= 8000 and share_hash ~ '^[A-Za-z0-9_.,=&%:~!*()-]+$'))
);

-- a template's name is unique in its guild, whatever its case
create unique index if not exists comp_templates_name_per_guild
  on public.comp_templates (guild_id, lower(name));
create index if not exists comp_templates_guild_id on public.comp_templates (guild_id);
create index if not exists comp_templates_created_by on public.comp_templates (created_by);
create index if not exists comp_templates_updated_by on public.comp_templates (updated_by);

comment on table public.comp_templates is
  'A comp a guild keeps: content, planned size, style, notes, the planner share hash it was saved with. Never a live roster.';
comment on column public.comp_templates.content is
  'A content key of the dashboard dataset (pipeline/out/dataset-latest.json templates, e.g. territory_defense). The database checks its form; the client checks it against the build''s list.';
comment on column public.comp_templates.style is
  'A style key of the dataset (styles, e.g. clap), or null for balanced.';
comment on column public.comp_templates.share_hash is
  'The planner''s share link hash (c=, n=, st=, p=, g=, f=, k=) at save time: opening the template restores the kits and spell picks too. Null for a template written without the planner.';

alter table public.comp_templates enable row level security;


-- 2. comp_template_slots --------------------------------------------------------

create table if not exists public.comp_template_slots (
  template_id uuid not null references public.comp_templates (id) on delete cascade,
  position smallint not null,
  weapon_id text,
  role text,
  note text,
  primary key (template_id, position),
  constraint comp_template_slots_position check (position between 1 and 60),
  constraint comp_template_slots_weapon_form check (
    weapon_id is null or weapon_id ~ '^[A-Z0-9_]{1,64}$'),
  constraint comp_template_slots_role_clean check (
    role is null or (role = btrim(role) and char_length(role) between 1 and 40)),
  constraint comp_template_slots_note_clean check (
    note is null or (note = btrim(note) and char_length(note) between 1 and 200))
);

comment on table public.comp_template_slots is
  'One slot of a template: its position in the roster, the weapon line (null for an open slot), the caller''s role label and a note.';

alter table public.comp_template_slots enable row level security;


-- 3. policies: comp_templates ---------------------------------------------------------

drop policy if exists "Members read their guild's templates" on public.comp_templates;
create policy "Members read their guild's templates" on public.comp_templates
  for select to authenticated
  using (private.guild_role_of(guild_id) is not null);

drop policy if exists "Callers create templates" on public.comp_templates;
create policy "Callers create templates" on public.comp_templates
  for insert to authenticated
  with check (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin')
              and created_by = (select auth.uid()));

drop policy if exists "Callers edit templates" on public.comp_templates;
create policy "Callers edit templates" on public.comp_templates
  for update to authenticated
  using (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'))
  with check (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'));

drop policy if exists "Callers delete templates" on public.comp_templates;
create policy "Callers delete templates" on public.comp_templates
  for delete to authenticated
  using (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'));

revoke all on table public.comp_templates from anon, authenticated;
grant select, delete on table public.comp_templates to authenticated;
grant insert (guild_id, name, content, style, planned_size, notes, share_hash)
  on table public.comp_templates to authenticated;
grant update (name, content, style, planned_size, notes, share_hash)
  on table public.comp_templates to authenticated;

drop trigger if exists comp_templates_set_updated_at on public.comp_templates;
create trigger comp_templates_set_updated_at
  before update on public.comp_templates
  for each row execute function public.set_updated_at();

-- updated_by follows every change (the caller writes no id columns);
-- a guild keeps at most 100 templates (a storage bound against abuse)
create or replace function public.comp_templates_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if (select count(*) from public.comp_templates where guild_id = new.guild_id) >= 100 then
      raise exception 'a guild keeps at most 100 templates' using errcode = '23514';
    end if;
    return new;
  end if;
  new.updated_by := (select auth.uid());
  return new;
end;
$$;

revoke execute on function public.comp_templates_guard() from public, anon, authenticated;

drop trigger if exists comp_templates_guard on public.comp_templates;
create trigger comp_templates_guard
  before insert or update on public.comp_templates
  for each row execute function public.comp_templates_guard();


-- 4. policies: comp_template_slots -----------------------------------------------------

-- a slot's guild is its template's; the template's own policy decides who
-- reads it, and the caller roles who write it
drop policy if exists "Members read their guild's slots" on public.comp_template_slots;
create policy "Members read their guild's slots" on public.comp_template_slots
  for select to authenticated
  using (exists (select 1 from public.comp_templates t where t.id = template_id));

drop policy if exists "Callers add slots" on public.comp_template_slots;
create policy "Callers add slots" on public.comp_template_slots
  for insert to authenticated
  with check ((select private.guild_role_of(t.guild_id) from public.comp_templates t where t.id = template_id)
              in ('caller', 'officer', 'admin'));

drop policy if exists "Callers edit slots" on public.comp_template_slots;
create policy "Callers edit slots" on public.comp_template_slots
  for update to authenticated
  using ((select private.guild_role_of(t.guild_id) from public.comp_templates t where t.id = template_id)
         in ('caller', 'officer', 'admin'))
  with check ((select private.guild_role_of(t.guild_id) from public.comp_templates t where t.id = template_id)
              in ('caller', 'officer', 'admin'));

drop policy if exists "Callers remove slots" on public.comp_template_slots;
create policy "Callers remove slots" on public.comp_template_slots
  for delete to authenticated
  using ((select private.guild_role_of(t.guild_id) from public.comp_templates t where t.id = template_id)
         in ('caller', 'officer', 'admin'));

revoke all on table public.comp_template_slots from anon, authenticated;
grant select, delete on table public.comp_template_slots to authenticated;
grant insert (template_id, position, weapon_id, role, note) on table public.comp_template_slots to authenticated;
grant update (weapon_id, role, note) on table public.comp_template_slots to authenticated;


-- 5. save_comp_template: the template and its slots in one transaction --------

-- Security invoker: the policies and grants above bound it. The payload:
--   {id?, guild_id, name, content, style, planned_size, notes, share_hash,
--    slots: [{position, weapon_id, role, note}, ...]}
-- Without an id the template is created; with one it is updated. Slots
-- not in the payload go; listed slots are added or take their new weapon,
-- role and note. A failed save changes nothing.
create or replace function public.save_comp_template(template jsonb)
returns public.comp_templates
language plpgsql
security invoker
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  tid uuid := nullif(template ->> 'id', '')::uuid;
  slots jsonb := coalesce(template -> 'slots', '[]'::jsonb);
  t public.comp_templates;
begin
  if me is null then
    raise exception 'sign in to save a comp' using errcode = '42501';
  end if;

  if jsonb_typeof(slots) <> 'array' then
    raise exception 'slots must be a JSON array' using errcode = '22023';
  end if;

  if jsonb_array_length(slots) > 60 then
    raise exception 'a comp holds at most 60 slots' using errcode = '23514';
  end if;

  if tid is null then
    insert into public.comp_templates (guild_id, name, content, style, planned_size, notes, share_hash)
    values ((template ->> 'guild_id')::uuid,
            btrim(coalesce(template ->> 'name', '')),
            coalesce(template ->> 'content', 'territory_defense'),
            nullif(template ->> 'style', ''),
            coalesce((template ->> 'planned_size')::smallint, 20),
            nullif(btrim(coalesce(template ->> 'notes', '')), ''),
            nullif(template ->> 'share_hash', ''))
    returning * into t;
  else
    update public.comp_templates
       set name = btrim(coalesce(template ->> 'name', name)),
           content = coalesce(template ->> 'content', content),
           style = case when template ? 'style' then nullif(template ->> 'style', '') else style end,
           planned_size = coalesce((template ->> 'planned_size')::smallint, planned_size),
           notes = case when template ? 'notes' then nullif(btrim(template ->> 'notes'), '') else notes end,
           share_hash = case when template ? 'share_hash' then nullif(template ->> 'share_hash', '') else share_hash end
     where id = tid
    returning * into t;
    if t.id is null then
      raise exception 'the template was not found, or your role does not edit it' using errcode = '42501';
    end if;
  end if;

  delete from public.comp_template_slots s
   where s.template_id = t.id
     and not exists (
       select 1 from jsonb_array_elements(slots) as e(item)
        where (e.item ->> 'position')::smallint = s.position);

  insert into public.comp_template_slots (template_id, position, weapon_id, role, note)
  select t.id,
         (e.item ->> 'position')::smallint,
         nullif(e.item ->> 'weapon_id', ''),
         nullif(btrim(coalesce(e.item ->> 'role', '')), ''),
         nullif(btrim(coalesce(e.item ->> 'note', '')), '')
    from jsonb_array_elements(slots) as e(item)
  on conflict (template_id, position) do update
     set weapon_id = excluded.weapon_id,
         role = excluded.role,
         note = excluded.note;

  return t;
end;
$$;

revoke execute on function public.save_comp_template(jsonb) from public, anon;
grant execute on function public.save_comp_template(jsonb) to authenticated;
