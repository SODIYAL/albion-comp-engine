-- Player profile foundation: a player edits their own two names and keeps
-- a structured list of the weapon lines they play. Every table and
-- function here follows the user-owned data rules in supabase/README.md;
-- tests/test_supabase_schema.py and tests/test_supabase_rls.mjs pin them.


-- 1. updated_at follows every change --------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- a trigger function: triggers run it, the API never does
revoke execute on function public.set_updated_at() from public, anon, authenticated;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();


-- 2. profiles: a player writes their two names and nothing else ------------

-- The table-level grants let a signed-in user write every column of their
-- own row, id and timestamps included. Inserting keeps the id (the policy
-- ties it to the caller) for a row the sign-up trigger failed to create.
revoke insert, update on table public.profiles from authenticated;
grant insert (id, albion_name, display_name) on table public.profiles to authenticated;
grant update (albion_name, display_name) on table public.profiles to authenticated;

-- Names are stored trimmed; an empty name is stored as null. 64 characters
-- is a storage bound against abuse, not a game rule.
alter table public.profiles drop constraint if exists profiles_albion_name_clean;
alter table public.profiles add constraint profiles_albion_name_clean check (
  albion_name is null
  or (albion_name = btrim(albion_name) and char_length(albion_name) between 1 and 64));

alter table public.profiles drop constraint if exists profiles_display_name_clean;
alter table public.profiles add constraint profiles_display_name_clean check (
  display_name is null
  or (display_name = btrim(display_name) and char_length(display_name) between 1 and 64));

-- The sign-up trigger stores names the same way, so an untrimmed, empty or
-- oversized name from any client never fails a sign-up.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, albion_name, display_name)
  values (
    new.id,
    nullif(btrim(left(btrim(new.raw_user_meta_data ->> 'albion_name'), 64)), ''),
    nullif(btrim(left(btrim(new.raw_user_meta_data ->> 'display_name'), 64)), '')
  );

  return new;
end;
$$;

-- The trigger runs it with its definer's rights; no API role calls it (Supabase database
-- lints 0028 and 0029 flagged it as callable by anon and authenticated).
revoke execute on function public.handle_new_user() from public, anon, authenticated;


-- 3. player_weapons: the weapon lines a player plays ------------------------

create table if not exists public.player_weapons (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid()
    references public.profiles (id) on delete cascade,
  weapon_id text not null,
  preference text not null default 'main',
  sort_order smallint not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint player_weapons_one_per_weapon unique (user_id, weapon_id),
  constraint player_weapons_weapon_id_format check (weapon_id ~ '^[A-Z0-9_]{1,64}$'),
  constraint player_weapons_preference check (preference in ('main', 'secondary')),
  constraint player_weapons_sort_order check (sort_order between 0 and 99)
);

comment on table public.player_weapons is
  'The weapon lines a player plays. Read by the player alone until guilds exist.';
comment on column public.player_weapons.weapon_id is
  'A weapon line key of the dashboard dataset (pipeline/out/dataset-latest.json '
  'weapons, e.g. 2H_ICECRYSTAL_UNDEAD). The database checks its form; the client '
  'checks it against the catalog and shows a key it no longer knows as unknown.';
comment on column public.player_weapons.preference is
  'main: brought when the caller needs it; secondary: can also play.';
comment on column public.player_weapons.sort_order is
  'The order the player listed the weapons, mains first.';

alter table public.player_weapons enable row level security;

drop policy if exists "Players read their own weapons" on public.player_weapons;
create policy "Players read their own weapons" on public.player_weapons
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Players add their own weapons" on public.player_weapons;
create policy "Players add their own weapons" on public.player_weapons
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "Players reorder their own weapons" on public.player_weapons;
create policy "Players reorder their own weapons" on public.player_weapons
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "Players remove their own weapons" on public.player_weapons;
create policy "Players remove their own weapons" on public.player_weapons
  for delete to authenticated
  using ((select auth.uid()) = user_id);

-- user_id comes from auth.uid() (the column default) and the id and
-- timestamps from the server: a player writes the weapon, its preference
-- and its position.
revoke all on table public.player_weapons from anon, authenticated;
grant select, delete on table public.player_weapons to authenticated;
grant insert (weapon_id, preference, sort_order) on table public.player_weapons to authenticated;
grant update (preference, sort_order) on table public.player_weapons to authenticated;

drop trigger if exists player_weapons_set_updated_at on public.player_weapons;
create trigger player_weapons_set_updated_at
  before update on public.player_weapons
  for each row execute function public.set_updated_at();

-- 50 rows per player: a storage bound against abuse, not a product rule.
-- A row that already exists passes (an upsert re-saving a full list).
create or replace function public.player_weapons_bound()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if exists (
    select 1 from public.player_weapons
     where user_id = new.user_id and weapon_id = new.weapon_id
  ) then
    return new;
  end if;

  if (select count(*) from public.player_weapons where user_id = new.user_id) >= 50 then
    raise exception 'a player lists at most 50 weapons' using errcode = '23514';
  end if;

  return new;
end;
$$;

revoke execute on function public.player_weapons_bound() from public, anon, authenticated;

drop trigger if exists player_weapons_bound on public.player_weapons;
create trigger player_weapons_bound
  before insert on public.player_weapons
  for each row execute function public.player_weapons_bound();


-- 4. set_my_weapons: the profile form saves the whole list at once ---------

-- Security invoker: it runs as the caller, so the policies and grants above
-- bound it exactly as they bound a direct write. Weapons no longer listed
-- go; listed weapons are added or take their new preference and position;
-- a weapon kept across saves keeps its created_at. One transaction: a
-- failed save changes nothing.
create or replace function public.set_my_weapons(weapons jsonb)
returns setof public.player_weapons
language plpgsql
security invoker
set search_path = ''
as $$
declare
  me uuid := (select auth.uid());
begin
  if me is null then
    raise exception 'sign in to save weapons' using errcode = '42501';
  end if;

  if weapons is null or jsonb_typeof(weapons) <> 'array' then
    raise exception 'weapons must be a JSON array' using errcode = '22023';
  end if;

  if jsonb_array_length(weapons) > 50 then
    raise exception 'a player lists at most 50 weapons' using errcode = '23514';
  end if;

  delete from public.player_weapons p
   where p.user_id = me
     and not exists (
       select 1 from jsonb_array_elements(weapons) as e(item)
        where e.item ->> 'weapon_id' = p.weapon_id);

  insert into public.player_weapons (weapon_id, preference, sort_order)
  select e.item ->> 'weapon_id',
         coalesce(e.item ->> 'preference', 'main'),
         (e.position - 1)::smallint
    from jsonb_array_elements(weapons) with ordinality as e(item, position)
  on conflict (user_id, weapon_id) do update
     set preference = excluded.preference,
         sort_order = excluded.sort_order;

  return query
    select * from public.player_weapons
     where user_id = me
     order by sort_order;
end;
$$;

revoke execute on function public.set_my_weapons(jsonb) from public, anon;
grant execute on function public.set_my_weapons(jsonb) to authenticated;
