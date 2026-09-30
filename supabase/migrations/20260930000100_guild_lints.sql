-- Guilds, the advisor's findings on the first migration (Supabase
-- database lints 0029, 0001, 0006), each fixed at the source:
--
--   0029  a SECURITY DEFINER function signed-in users can call through
--         the API: the policy helper moves to the schema `private`, which
--         the API does not expose, and join_guild runs as the caller. A
--         code is checked by the insert policy itself, through a private
--         helper that reads the guild the joiner cannot yet see.
--   0001  a foreign key without a covering index: guild_members.user_id
--         and guilds.created_by get theirs.
--   0006  two permissive select policies for one role on profiles and
--         player_weapons: the guild-scoped read joins the own-row policy.
--
-- After this file the only SECURITY DEFINER function in the API schema
-- is the sign-up trigger, which no API role can execute; every other
-- definer lives in `private` (supabase/README.md rule 8).


-- 1. the private schema: helpers policies call, out of the API's reach ----

create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

-- the caller's role in a guild, or null. Reads guild_members with its
-- definer's rights (a policy on guild_members cannot read the table under
-- its own policy) and answers for the caller alone.
create or replace function private.guild_role_of(guild uuid)
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

revoke execute on function private.guild_role_of(uuid) from public, anon;
grant execute on function private.guild_role_of(uuid) to authenticated;

-- the guild a join code names, or null: the insert policy checks a code
-- against a guild the joiner is not yet allowed to read
create or replace function private.guild_id_for_code(code text)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select g.id
    from public.guilds g
   where g.join_code = upper(btrim(coalesce(code, '')));
$$;

revoke execute on function private.guild_id_for_code(text) from public, anon;
grant execute on function private.guild_id_for_code(text) to authenticated;

-- how many members a guild holds: the storage bound counts every row,
-- which a joiner, not yet a member, cannot read
create or replace function private.guild_member_count(guild uuid)
returns integer
language sql
stable
security definer
set search_path = ''
as $$
  select count(*)::integer from public.guild_members m where m.guild_id = guild;
$$;

revoke execute on function private.guild_member_count(uuid) from public, anon;
grant execute on function private.guild_member_count(uuid) to authenticated;


-- 2. every policy and the view read the private helper ----------------------

alter policy "Members read their guilds" on public.guilds
  using (private.guild_role_of(id) is not null or created_by = (select auth.uid()));

alter policy "Admins rename their guild and renew its code" on public.guilds
  using (private.guild_role_of(id) = 'admin')
  with check (private.guild_role_of(id) = 'admin');

alter policy "Admins delete their guild" on public.guilds
  using (private.guild_role_of(id) = 'admin');

-- A member reads their own rows besides the guild's: a row this statement
-- inserts (join_guild's ON CONFLICT, a RETURNING) is checked against the
-- select policy before the helper's snapshot can see the membership.
alter policy "Members read their guild's members" on public.guild_members
  using (user_id = (select auth.uid()) or private.guild_role_of(guild_id) is not null);

-- one insert policy: the creator seats itself as admin (create_guild), a
-- code holder seats itself as member (join_guild sets the code for the
-- statement; a direct insert carries none and is refused)
alter policy "Creators seat themselves as admin" on public.guild_members
  with check (
    user_id = (select auth.uid())
    and ((role = 'admin'
          and private.guild_role_of(guild_id) is null
          and (select g.created_by from public.guilds g where g.id = guild_id) = (select auth.uid()))
         or (role = 'member'
             and guild_id = private.guild_id_for_code(current_setting('app.join_code', true)))));

alter policy "Officers and admins set roles" on public.guild_members
  using (private.guild_role_of(guild_id) in ('officer', 'admin'))
  with check (private.guild_role_of(guild_id) in ('officer', 'admin'));

alter policy "Members leave and officers or admins remove" on public.guild_members
  using (user_id = (select auth.uid())
         or private.guild_role_of(guild_id) in ('officer', 'admin'));

create or replace view public.guild_join_codes
with (security_invoker = true)
as
  select g.id as guild_id, g.join_code
    from public.guilds g
   where private.guild_role_of(g.id) in ('officer', 'admin');

revoke all on table public.guild_join_codes from anon, authenticated;
grant select on table public.guild_join_codes to authenticated;


-- 3. the guard reads the private helpers ---------------------------------------

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
    if private.guild_member_count(new.guild_id) >= 500 then
      raise exception 'a guild holds at most 500 members' using errcode = '23514';
    end if;
    if (select count(*) from public.guild_members where user_id = new.user_id) >= 20 then
      raise exception 'an account belongs to at most 20 guilds' using errcode = '23514';
    end if;
    return new;
  end if;

  -- an officer's reach: rows below officer, roles below officer
  my_role := private.guild_role_of(old.guild_id);
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


-- 4. join_guild runs as the caller ---------------------------------------------

-- The code rides the statement (a transaction-local setting) and the
-- insert policy checks it; the policies and grants bound the write
-- exactly as they bound a direct insert.
create or replace function public.join_guild(code text)
returns public.guilds
language plpgsql
security invoker
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
  clean text := upper(btrim(coalesce(code, '')));
  gid uuid;
  g public.guilds;
begin
  if me is null then
    raise exception 'sign in to join a guild' using errcode = '42501';
  end if;

  gid := private.guild_id_for_code(clean);
  if gid is null then
    raise exception 'no guild has this join code' using errcode = 'P0002';
  end if;

  perform set_config('app.join_code', clean, true);
  insert into public.guild_members (guild_id, role)
  values (gid, 'member')
  on conflict (guild_id, user_id) do nothing;
  perform set_config('app.join_code', '', true);

  select * into g from public.guilds where id = gid;
  return g;
end;
$$;

revoke execute on function public.join_guild(text) from public, anon;
grant execute on function public.join_guild(text) to authenticated;


-- 5. the foreign keys' indexes ------------------------------------------------------

create index if not exists guild_members_user_id on public.guild_members (user_id);
create index if not exists guilds_created_by on public.guilds (created_by);


-- 6. one select policy per table: own row, or a guild shared -------------------------

alter policy "Users can view their own profile" on public.profiles
  using ((select auth.uid()) = id
         or exists (
           select 1 from public.guild_members m
            where m.user_id = profiles.id
              and private.guild_role_of(m.guild_id) is not null));

drop policy if exists "Guild members read each other's profile" on public.profiles;

alter policy "Players read their own weapons" on public.player_weapons
  using ((select auth.uid()) = user_id
         or exists (
           select 1 from public.guild_members m
            where m.user_id = player_weapons.user_id
              and private.guild_role_of(m.guild_id) is not null));

drop policy if exists "Guild members read each other's weapons" on public.player_weapons;


-- 7. the public helper goes: nothing reads it now -------------------------------------

drop function if exists public.guild_role_of(uuid);
