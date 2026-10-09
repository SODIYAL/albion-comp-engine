-- Renewing a CTA's share code. The code is the key of the CTA's sign-up
-- link (rule 13), generated at creation and never changed, so a leaked
-- link needed a new CTA. An admin of the CTA's guild now renews it the way
-- the guild join code is renewed (20260930000000_guilds.sql): the client
-- writes any value into the column and the guard replaces it with a fresh
-- code from the same generator (public.new_join_code), so a code is never
-- chosen. The role is the join code's: an admin. The update policy on
-- events admits the caller roles, who edit CTAs, so the guard refuses a
-- changed code from any role but admin (42501): a rule a row policy
-- cannot state, as the guild members guard keeps an officer's reach. The
-- grant is a column grant to signed-in users; anon writes no CTA.
--
-- The old code stops opening the sheet at once: every guest policy and
-- guest function compares the code the statement carries with the
-- column, so through the old code event_by_code, sign_up, confirm_sign_up
-- and cancel_sign_up answer P0002 (no CTA has this code) and no row reads.
-- The sign-ups and their records stay as they are: a guest's row is keyed
-- by the hash of their claim token, never by the code, so the same token
-- reaches it through the new code.
--
-- The sheet's broadcast trigger tells the old topic too: a sheet still
-- open on the old link reads again and finds that the link opens nothing.


-- 1. the grant ---------------------------------------------------------------------

grant update (share_code) on table public.events to authenticated;

comment on column public.events.share_code is
  'The key of the CTA''s sign-up link (rule 13): 10 letters and digits, generated, never chosen. An admin renews it by writing any value, which the guard replaces with a fresh code; the old code opens nothing from then on.';


-- 2. the guard: the bound, updated_by, the status moves, and the renewal -----------

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
  -- a written share code is never kept: an admin's write renews it
  if new.share_code is distinct from old.share_code then
    if private.guild_role_of(old.guild_id) is distinct from 'admin' then
      raise exception 'an admin of the guild renews a CTA''s share code' using errcode = '42501';
    end if;
    new.share_code := public.new_join_code();
  end if;
  new.updated_by := (select auth.uid());
  return new;
end;
$$;

revoke execute on function public.events_guard() from public, anon, authenticated;


-- 3. the sheet's broadcast tells the old topic of a renewed code ----------------------

create or replace function public.sheet_changed()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  code text;
begin
  -- no Realtime, no message: the sheet still refreshes by hand
  if to_regprocedure('realtime.send(jsonb, text, text, boolean)') is null then
    return null;
  end if;

  if tg_table_name = 'events' then
    code := case when tg_op = 'DELETE' then old.share_code else new.share_code end;
    -- a renewed code: a sheet still open on the old link reads again and
    -- finds that its link opens nothing now
    if tg_op = 'UPDATE' then
      if old.share_code is distinct from new.share_code then
        perform realtime.send(
          jsonb_build_object('table', tg_table_name, 'op', tg_op),
          'changed',
          'cta:' || old.share_code,
          false);
      end if;
    end if;
  else
    -- a cascade from a deleted CTA finds no CTA: the CTA's own trigger
    -- has already said so
    select e.share_code into code
      from public.events e
     where e.id = case when tg_op = 'DELETE' then old.event_id else new.event_id end;
  end if;

  if code is null then
    return null;
  end if;

  perform realtime.send(
    jsonb_build_object('table', tg_table_name, 'op', tg_op),
    'changed',
    'cta:' || code,
    false);

  return null;
end;
$$;

revoke execute on function public.sheet_changed() from public, anon, authenticated;
