-- Import (platform phase 10): a guild's weapon aliases, the names its
-- callers matched to weapon lines while importing a spreadsheet. An
-- import reads a sheet's weapon names through the catalog on the client
-- (the dataset's display names and what the client derives from them: a
-- prefix, the words, the initials, a close spelling) and then through
-- this table: a name the client could not read, once a caller chose its
-- weapon, is kept here so the guild's next import reads it the same
-- way. The table holds names, never a copy of the catalog (rule 10).
-- Every table and function follows supabase/README.md;
-- tests/test_supabase_schema.py and tests/test_supabase_rls.mjs pin them.
--
-- Who does what:
--   every member       reads the guild's aliases (an import by any caller
--                      reads them, and a member sees what a name means)
--   caller, officer,   add, change and remove aliases (the roles that
--   admin              write comps)


-- 1. weapon_aliases -------------------------------------------------------------

create table if not exists public.weapon_aliases (
  guild_id uuid not null references public.guilds (id) on delete cascade,
  alias text not null,
  weapon_id text not null,
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (guild_id, alias),
  -- the client's normalized form: lower-case letters and digits, single
  -- spaces, at most 64 characters (ALIAS_RE, ALIAS_MAX in _import.js)
  constraint weapon_aliases_alias_form check (
    char_length(alias) <= 64 and alias ~ '^[a-z0-9]+( [a-z0-9]+)*$'),
  constraint weapon_aliases_weapon_form check (weapon_id ~ '^[A-Z0-9_]{1,64}$')
);

create index if not exists weapon_aliases_created_by on public.weapon_aliases (created_by);

comment on table public.weapon_aliases is
  'A name a guild''s import matched to a weapon line: the normalized text a caller''s sheet used, and the dataset key it means. Read by the next import; never a copy of the catalog.';
comment on column public.weapon_aliases.alias is
  'The sheet''s text, normalized on the client: lower case, letters and digits, single spaces (tier and enchantment words dropped).';

alter table public.weapon_aliases enable row level security;


-- 2. policies --------------------------------------------------------------------

drop policy if exists "Members read their guild's aliases" on public.weapon_aliases;
create policy "Members read their guild's aliases" on public.weapon_aliases
  for select to authenticated
  using (private.guild_role_of(guild_id) is not null);

drop policy if exists "Callers add aliases" on public.weapon_aliases;
create policy "Callers add aliases" on public.weapon_aliases
  for insert to authenticated
  with check (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin')
              and created_by = (select auth.uid()));

drop policy if exists "Callers change aliases" on public.weapon_aliases;
create policy "Callers change aliases" on public.weapon_aliases
  for update to authenticated
  using (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'))
  with check (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'));

drop policy if exists "Callers remove aliases" on public.weapon_aliases;
create policy "Callers remove aliases" on public.weapon_aliases
  for delete to authenticated
  using (private.guild_role_of(guild_id) in ('caller', 'officer', 'admin'));

revoke all on table public.weapon_aliases from anon, authenticated;
grant select, delete on table public.weapon_aliases to authenticated;
grant insert (guild_id, alias, weapon_id) on table public.weapon_aliases to authenticated;
grant update (weapon_id) on table public.weapon_aliases to authenticated;


-- 3. the guard: a guild keeps at most 500 aliases -------------------------------

-- A storage bound against abuse. A name the guild already holds passes
-- at the bound: the save below changes its weapon through the conflict
-- clause, which fires this trigger first.
create or replace function public.weapon_aliases_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not exists (select 1 from public.weapon_aliases a where a.guild_id = new.guild_id and a.alias = new.alias)
     and (select count(*) from public.weapon_aliases a where a.guild_id = new.guild_id) >= 500 then
    raise exception 'a guild keeps at most 500 aliases' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke execute on function public.weapon_aliases_guard() from public, anon, authenticated;

drop trigger if exists weapon_aliases_guard on public.weapon_aliases;
create trigger weapon_aliases_guard
  before insert on public.weapon_aliases
  for each row execute function public.weapon_aliases_guard();


-- 4. save_weapon_aliases: the names one import matched, in one transaction -----

-- Security invoker: the policies and grants above bound it. The payload:
--   [{alias, weapon_id}, ...], at most 100 per save (an import's review)
-- A name the guild holds takes its new weapon; one it does not is added.
-- Returns how many rows were added or changed. A failed save changes
-- nothing.
create or replace function public.save_weapon_aliases(guild uuid, aliases jsonb)
returns integer
language plpgsql
security invoker
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  n integer;
begin
  if me is null then
    raise exception 'sign in to save aliases' using errcode = '42501';
  end if;

  if jsonb_typeof(aliases) <> 'array' then
    raise exception 'aliases must be a JSON array' using errcode = '22023';
  end if;

  if jsonb_array_length(aliases) > 100 then
    raise exception 'a save holds at most 100 aliases' using errcode = '23514';
  end if;

  insert into public.weapon_aliases as a (guild_id, alias, weapon_id)
  select guild, e.item ->> 'alias', e.item ->> 'weapon_id'
    from jsonb_array_elements(aliases) as e(item)
  on conflict (guild_id, alias) do update
     set weapon_id = excluded.weapon_id
   where a.weapon_id is distinct from excluded.weapon_id;

  get diagnostics n = row_count;
  return n;
end;
$$;

revoke execute on function public.save_weapon_aliases(uuid, jsonb) from public, anon;
grant execute on function public.save_weapon_aliases(uuid, jsonb) to authenticated;
