-- Live updates (platform phase 7): the sheet changes without a refresh.
-- After every write to a CTA's sign-ups, slots or the CTA itself, a
-- trigger sends one Realtime broadcast on the CTA's topic, cta:<share
-- code>, whose payload names the table and the operation and nothing
-- else. A client on the sheet (a guest or a member: the code is the key,
-- rule 13) listens on that topic and re-reads the sheet through
-- event_by_code, so what it sees is still what the policies allow. The
-- database enforces the concurrency (phase 5's unique index); the
-- channel only reports that something changed.
--
-- The trigger runs with its owner's rights (a listed exception,
-- supabase/README.md rule 8): realtime.send writes realtime.messages,
-- which row-level security keeps from the API roles with no policy for
-- them, so a message sent as the caller is dropped in silence (measured
-- on the project: a send as anon landed nothing). The function is small,
-- reads one column of one row, and no API role can call it (execute
-- revoked). Where Realtime is absent, it does nothing: the sheet keeps
-- its Refresh button.


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

drop trigger if exists signups_changed on public.signups;
create trigger signups_changed
  after insert or update or delete on public.signups
  for each row execute function public.sheet_changed();

drop trigger if exists event_slots_changed on public.event_slots;
create trigger event_slots_changed
  after insert or update or delete on public.event_slots
  for each row execute function public.sheet_changed();

drop trigger if exists events_changed on public.events;
create trigger events_changed
  after update or delete on public.events
  for each row execute function public.sheet_changed();
