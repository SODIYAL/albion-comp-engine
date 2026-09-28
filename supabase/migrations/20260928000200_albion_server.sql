-- Profiles record the Albion server their character plays on. Character
-- names are unique per server, not across the game, so the name alone does
-- not identify a character; a guild (phase 2) lives on one server.


-- 1. the column --------------------------------------------------------------

-- The game's three servers. Null until the player picks one: rows from
-- before this migration, and sign-ups from clients that do not send it.
alter table public.profiles add column if not exists albion_server text;

alter table public.profiles drop constraint if exists profiles_albion_server_known;
alter table public.profiles add constraint profiles_albion_server_known check (
  albion_server is null or albion_server in ('americas', 'asia', 'europe'));

comment on column public.profiles.albion_server is
  'The server the Albion character plays on: americas, asia or europe. Null until the player picks one.';

-- a player writes their server beside their two names
grant insert (albion_server) on table public.profiles to authenticated;
grant update (albion_server) on table public.profiles to authenticated;


-- 2. the sign-up trigger stores it ------------------------------------------

-- A server off the list is stored as null instead of failing the sign-up,
-- the same rule the names follow.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, albion_name, display_name, albion_server)
  values (
    new.id,
    nullif(btrim(left(btrim(new.raw_user_meta_data ->> 'albion_name'), 64)), ''),
    nullif(btrim(left(btrim(new.raw_user_meta_data ->> 'display_name'), 64)), ''),
    case when new.raw_user_meta_data ->> 'albion_server' in ('americas', 'asia', 'europe')
         then new.raw_user_meta_data ->> 'albion_server' end
  );

  return new;
end;
$$;

-- replacing a function keeps its grants; restated so this file reads whole
revoke execute on function public.handle_new_user() from public, anon, authenticated;
