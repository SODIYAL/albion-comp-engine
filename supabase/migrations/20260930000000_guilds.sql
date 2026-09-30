-- Guilds (platform phase 2): a guild on one Albion server, its members
-- with a role (member / caller / officer / admin), a join code the guild
-- shares, and the guild-scoped reads that let members see each other's
-- character and weapon lists. Every table and function follows
-- supabase/README.md; tests/test_supabase_schema.py and
-- tests/test_supabase_rls.mjs pin them.
--
-- Who does what:
--   anyone signed in   creates a guild (and is its first admin), joins one
--                      by its code, leaves one
--   every member       reads the guild, its members, and each member's
--                      profile and weapon lists
--   caller             a role only: no extra power here (CTAs, phase 4)
--   officer            reads the join code; sets members' roles between
--                      member and caller; removes members and callers
--   admin              everything an officer does; sets any role; renames
--                      the guild; regenerates the join code; deletes the
--                      guild; the last admin can neither leave nor be
--                      demoted by hand. When the last admin's ACCOUNT is
--                      deleted, the longest-standing officer (else caller,
--                      else member) becomes admin, and a guild left with
--                      no member is deleted with the account.


-- 1. the join code ----------------------------------------------------------

-- Ten hex characters of a random UUID (40 bits): a guild's invitation.
-- Runs as the caller (a column default and a trigger call it).
create or replace function public.new_join_code()
returns text
language sql
volatile
security invoker
set search_path = ''
as $$
  select upper(left(replace(gen_random_uuid()::text, '-', ''), 10));
$$;

revoke execute on function public.new_join_code() from public, anon;
grant execute on function public.new_join_code() to authenticated;


-- 2. guilds -----------------------------------------------------------------

create table if not exists public.guilds (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  albion_server text not null,
  join_code text not null default public.new_join_code(),
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint guilds_name_clean check (
    name = btrim(name) and char_length(name) between 1 and 64),
  constraint guilds_albion_server_known check (
    albion_server in ('americas', 'asia', 'europe')),
  constraint guilds_join_code_form check (join_code ~ '^[A-Z0-9]{10}$'),
  constraint guilds_join_code_unique unique (join_code)
);

-- a guild name is unique on its server (a game fact), whatever its case
create unique index if not exists guilds_name_per_server
  on public.guilds (albion_server, lower(name));

comment on table public.guilds is
  'A guild on one Albion server. Members read it; admins rename it, renew its join code and delete it.';
comment on column public.guilds.join_code is
  'The invitation: whoever holds it joins as a member (join_guild). Officers and admins read it; an admin renews it by writing any value, which the guard replaces with a fresh code.';
comment on column public.guilds.created_by is
  'The account that created the guild (its first admin). Null once that account is deleted; the guild stays.';

alter table public.guilds enable row level security;


-- 3. guild_members ------------------------------------------------------------

create table if not exists public.guild_members (
  guild_id uuid not null references public.guilds (id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (guild_id, user_id),
  constraint guild_members_role_known check (role in ('member', 'caller', 'officer', 'admin'))
);

comment on table public.guild_members is
  'Who belongs to a guild and with what role: member, caller, officer or admin.';

alter table public.guild_members enable row level security;


-- 4. the policy helper: the caller's role in a guild ------------------------

-- Reads guild_members with its definer's rights, which is what a policy on
-- guild_members itself needs: a policy that read the table under its own
-- policy would recurse. It answers only for the caller (auth.uid() is
-- read inside), so no other account's membership can be probed through
-- it. A listed SECURITY DEFINER exception (supabase/README.md rule 8).
create or replace function public.guild_role_of(guild uuid)
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select m.role
    from public.guild_members m
   where m.guild_id = guild
     and m.user_id = (select auth.uid());
$$;

revoke execute on function public.guild_role_of(uuid) from public, anon;
grant execute on function public.guild_role_of(uuid) to authenticated;


-- 5. policies: guilds ---------------------------------------------------------

-- members read their guilds; the creator reads the row it just made
drop policy if exists "Members read their guilds" on public.guilds;
create policy "Members read their guilds" on public.guilds
  for select to authenticated
  using (public.guild_role_of(id) is not null or created_by = (select auth.uid()));

drop policy if exists "Signed-in users create guilds" on public.guilds;
create policy "Signed-in users create guilds" on public.guilds
  for insert to authenticated
  with check (created_by = (select auth.uid()));

drop policy if exists "Admins rename their guild and renew its code" on public.guilds;
create policy "Admins rename their guild and renew its code" on public.guilds
  for update to authenticated
  using (public.guild_role_of(id) = 'admin')
  with check (public.guild_role_of(id) = 'admin');

drop policy if exists "Admins delete their guild" on public.guilds;
create policy "Admins delete their guild" on public.guilds
  for delete to authenticated
  using (public.guild_role_of(id) = 'admin');

-- The join code is read by officers and admins alone: a column-level
-- rule, which row policies cannot state, so it is a view over the table
-- (below) and the table's select grant keeps the column too (PostgREST
-- resource embedding needs it); the client reads the code through the
-- view only.
revoke all on table public.guilds from anon, authenticated;
grant select, delete on table public.guilds to authenticated;
grant insert (name, albion_server) on table public.guilds to authenticated;
grant update (name, join_code) on table public.guilds to authenticated;

drop trigger if exists guilds_set_updated_at on public.guilds;
create trigger guilds_set_updated_at
  before update on public.guilds
  for each row execute function public.set_updated_at();

-- A written join code is never kept: any change becomes a fresh code.
-- Names arrive trimmed from the form; a blank one fails the check.
create or replace function public.guilds_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.join_code is distinct from old.join_code then
    new.join_code := public.new_join_code();
  end if;
  return new;
end;
$$;

revoke execute on function public.guilds_guard() from public, anon, authenticated;

drop trigger if exists guilds_guard on public.guilds;
create trigger guilds_guard
  before update on public.guilds
  for each row execute function public.guilds_guard();


-- 6. policies: guild_members ----------------------------------------------------

drop policy if exists "Members read their guild's members" on public.guild_members;
create policy "Members read their guild's members" on public.guild_members
  for select to authenticated
  using (public.guild_role_of(guild_id) is not null);

-- the creator seats itself as the first admin (create_guild); joining by
-- code goes through join_guild, which runs with its definer's rights
drop policy if exists "Creators seat themselves as admin" on public.guild_members;
create policy "Creators seat themselves as admin" on public.guild_members
  for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and role = 'admin'
    and public.guild_role_of(guild_id) is null
    and (select g.created_by from public.guilds g where g.id = guild_id) = (select auth.uid()));

drop policy if exists "Officers and admins set roles" on public.guild_members;
create policy "Officers and admins set roles" on public.guild_members
  for update to authenticated
  using (public.guild_role_of(guild_id) in ('officer', 'admin'))
  with check (public.guild_role_of(guild_id) in ('officer', 'admin'));

drop policy if exists "Members leave and officers or admins remove" on public.guild_members;
create policy "Members leave and officers or admins remove" on public.guild_members
  for delete to authenticated
  using (user_id = (select auth.uid())
         or public.guild_role_of(guild_id) in ('officer', 'admin'));

revoke all on table public.guild_members from anon, authenticated;
grant select, delete on table public.guild_members to authenticated;
grant insert (guild_id, role) on table public.guild_members to authenticated;
grant update (role) on table public.guild_members to authenticated;

drop trigger if exists guild_members_set_updated_at on public.guild_members;
create trigger guild_members_set_updated_at
  before update on public.guild_members
  for each row execute function public.set_updated_at();

-- The rules a policy cannot state, as one guard:
--   an officer sets and removes members and callers only;
--   the last admin can neither be demoted nor removed by a member's own
--   statement (pg_trigger_depth() = 1); a cascade, from the guild's or
--   the account's deletion, passes and the succession trigger follows;
--   at most 500 members per guild, at most 20 guilds per account
--   (storage bounds against abuse, not product rules).
create or replace function public.guild_members_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  my_role text;
  admins integer;
begin
  if tg_op = 'INSERT' then
    if (select count(*) from public.guild_members where guild_id = new.guild_id) >= 500 then
      raise exception 'a guild holds at most 500 members' using errcode = '23514';
    end if;
    if (select count(*) from public.guild_members where user_id = new.user_id) >= 20 then
      raise exception 'an account belongs to at most 20 guilds' using errcode = '23514';
    end if;
    return new;
  end if;

  -- an officer's reach: rows below officer, roles below officer
  my_role := public.guild_role_of(old.guild_id);
  if my_role = 'officer' and old.user_id <> me then
    if old.role in ('officer', 'admin')
       or (tg_op = 'UPDATE' and new.role in ('officer', 'admin')) then
      raise exception 'an officer manages members and callers only' using errcode = '42501';
    end if;
  end if;

  -- the last admin stays, unless a cascade is removing the row
  if old.role = 'admin' and (tg_op = 'DELETE' or new.role <> 'admin')
     and pg_trigger_depth() <= 1 then
    select count(*) into admins
      from public.guild_members
     where guild_id = old.guild_id and role = 'admin' and user_id <> old.user_id;
    if admins = 0 then
      raise exception 'a guild keeps at least one admin' using errcode = '23514';
    end if;
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke execute on function public.guild_members_guard() from public, anon, authenticated;

drop trigger if exists guild_members_guard on public.guild_members;
create trigger guild_members_guard
  before insert or update or delete on public.guild_members
  for each row execute function public.guild_members_guard();

-- Succession: when a cascade (the deletion of the last admin's account)
-- removes a guild's last admin, the longest-standing officer, else
-- caller, else member becomes admin; a guild left with no member goes
-- with the account. A member's own statement never reaches this with no
-- admin left: the guard refused it before the row went.
create or replace function public.guild_members_succession()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  heir uuid;
begin
  if old.role <> 'admin' then
    return old;
  end if;
  if not exists (select 1 from public.guilds g where g.id = old.guild_id) then
    return old;
  end if;
  if exists (select 1 from public.guild_members
              where guild_id = old.guild_id and role = 'admin') then
    return old;
  end if;

  select user_id into heir
    from public.guild_members
   where guild_id = old.guild_id
   order by array_position(array['officer', 'caller', 'member'], role), created_at
   limit 1;

  if heir is null then
    delete from public.guilds where id = old.guild_id;
  else
    update public.guild_members set role = 'admin'
     where guild_id = old.guild_id and user_id = heir;
  end if;
  return old;
end;
$$;

revoke execute on function public.guild_members_succession() from public, anon, authenticated;

drop trigger if exists guild_members_succession on public.guild_members;
create trigger guild_members_succession
  after delete on public.guild_members
  for each row execute function public.guild_members_succession();


-- 7. the join code, read by officers and admins -------------------------------

-- A view that runs as the caller (security invoker): the table's policies
-- decide the rows, the view decides the column. PostgREST exposes it
-- beside the tables.
create or replace view public.guild_join_codes
with (security_invoker = true)
as
  select g.id as guild_id, g.join_code
    from public.guilds g
   where public.guild_role_of(g.id) in ('officer', 'admin');

revoke all on table public.guild_join_codes from anon, authenticated;
grant select on table public.guild_join_codes to authenticated;


-- 8. create_guild: the guild and its first admin in one transaction ----------

-- Security invoker: the policies and grants above bound it.
create or replace function public.create_guild(name text, albion_server text)
returns public.guilds
language plpgsql
security invoker
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  g public.guilds;
begin
  if me is null then
    raise exception 'sign in to create a guild' using errcode = '42501';
  end if;

  insert into public.guilds (name, albion_server)
  values (btrim(create_guild.name), create_guild.albion_server)
  returning * into g;

  insert into public.guild_members (guild_id, role)
  values (g.id, 'admin');

  return g;
end;
$$;

revoke execute on function public.create_guild(text, text) from public, anon;
grant execute on function public.create_guild(text, text) to authenticated;


-- 9. join_guild: the code holder becomes a member ----------------------------

-- The guild is found by a code the caller is not yet allowed to read, so
-- this one runs with its definer's rights: a listed SECURITY DEFINER
-- exception (supabase/README.md rule 8). It writes one row, for the
-- caller alone, as a member; the bounds guard still runs. A member
-- joining again is answered with the guild, not an error.
create or replace function public.join_guild(code text)
returns public.guilds
language plpgsql
security definer
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  g public.guilds;
begin
  if me is null then
    raise exception 'sign in to join a guild' using errcode = '42501';
  end if;

  select * into g from public.guilds
   where join_code = upper(btrim(coalesce(code, '')));
  if g.id is null then
    raise exception 'no guild has this join code' using errcode = 'P0002';
  end if;

  insert into public.guild_members (guild_id, user_id, role)
  values (g.id, me, 'member')
  on conflict (guild_id, user_id) do nothing;

  return g;
end;
$$;

revoke execute on function public.join_guild(text) from public, anon;
grant execute on function public.join_guild(text) to authenticated;


-- 10. guild-scoped reads of profiles and weapon lists ------------------------

-- A member reads the character, display name and server of every member
-- of a guild they share, and the weapon lists those members keep: what a
-- caller needs to fill a comp. Email addresses live in auth.users and
-- are never exposed.
drop policy if exists "Guild members read each other's profile" on public.profiles;
create policy "Guild members read each other's profile" on public.profiles
  for select to authenticated
  using (exists (
    select 1 from public.guild_members m
     where m.user_id = profiles.id
       and public.guild_role_of(m.guild_id) is not null));

drop policy if exists "Guild members read each other's weapons" on public.player_weapons;
create policy "Guild members read each other's weapons" on public.player_weapons
  for select to authenticated
  using (exists (
    select 1 from public.guild_members m
     where m.user_id = player_weapons.user_id
       and public.guild_role_of(m.guild_id) is not null));

comment on table public.player_weapons is
  'The weapon lines a player plays. Read by the player and by the members of the guilds they share.';
