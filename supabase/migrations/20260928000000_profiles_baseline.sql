-- Baseline: the profiles schema as it runs in the Supabase project, built
-- in the SQL editor before migrations were kept in this repository. Every
-- statement is idempotent: applied to that project it changes nothing;
-- applied to an empty project it reproduces it.
--
-- One profile row per auth user, created by a trigger from the sign-up
-- metadata (dashboard/_auth.js signUpUser sends albion_name and
-- display_name). The rules every table follows: supabase/README.md.

create table if not exists public.profiles (
  id uuid not null primary key references auth.users (id) on delete cascade,
  albion_name text,
  display_name text,
  avatar_url text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.profiles enable row level security;

drop policy if exists "Users can view their own profile" on public.profiles;
create policy "Users can view their own profile" on public.profiles
  for select to authenticated
  using ((select auth.uid()) = id);

drop policy if exists "Users can create their own profile" on public.profiles;
create policy "Users can create their own profile" on public.profiles
  for insert to authenticated
  with check ((select auth.uid()) = id);

drop policy if exists "Users can update their own profile" on public.profiles;
create policy "Users can update their own profile" on public.profiles
  for update to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

-- The project's default privileges grant every new table to anon; this one
-- is for signed-in users only.
revoke all on table public.profiles from anon, authenticated;
grant select, insert, update on table public.profiles to authenticated;

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
    new.raw_user_meta_data ->> 'albion_name',
    new.raw_user_meta_data ->> 'display_name'
  );

  return new;
end;
$$;

-- created only when missing: dropping a trigger on auth.users is reserved
-- to the Supabase-managed role that holds that table, not the migration role
do $$
begin
  if not exists (
    select 1 from pg_trigger
     where tgname = 'on_auth_user_created' and tgrelid = 'auth.users'::regclass
  ) then
    create trigger on_auth_user_created
      after insert on auth.users
      for each row execute function public.handle_new_user();
  end if;
end;
$$;
