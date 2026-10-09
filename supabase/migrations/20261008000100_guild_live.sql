-- The CTAs dialog live: a channel per guild. The dialog's calendar and
-- sign-up counts were read on open; after this file every write to a
-- guild's CTAs or their sign-ups sends one Realtime broadcast on the
-- guild's topic, guild:<guild id>, event 'changed', whose payload names
-- the table and the operation and nothing else (the sheet's pattern,
-- 20260930000700_live_sheet.sql). The dialog listens while it is open
-- and re-reads what it shows through its own helpers, under its own
-- policies: the channel only reports.
--
-- The topic is private. The sheet's topic is public because its share
-- code is the key (rule 13); a guild id is no key (the sheet names its
-- CTA's guild to whoever holds the code), so the Realtime service admits
-- a guild's members alone: a private channel's join reads the policy on
-- realtime.messages below with the joiner's claims and the topic
-- (Realtime Authorization). No policy lets an API role send (insert): the
-- trigger sends, with its definer's rights, as the sheet's does (a listed
-- exception, supabase/README.md rule 8; realtime.messages is kept from
-- the API roles by row-level security, so a send as the caller lands
-- nothing).
--
-- The tables: events (the CTA itself; save_event writes its row whenever
-- it writes the slots, so a roster saved in the dialog is told too) and
-- signups. A slot's weapon changed on the sheet reaches the dialog on its
-- next read. Without Realtime the trigger does nothing and no policy is
-- made: the dialog reads on open, as before.


-- 1. the broadcast ------------------------------------------------------------

create or replace function public.guild_ctas_changed()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  gid uuid;
begin
  -- no Realtime, no message: the dialog still reads on open
  if to_regprocedure('realtime.send(jsonb, text, text, boolean)') is null then
    return null;
  end if;

  if tg_table_name = 'events' then
    gid := case when tg_op = 'DELETE' then old.guild_id else new.guild_id end;
  else
    -- a sign-up's guild is its CTA's; a cascade from a deleted CTA finds
    -- no CTA: the CTA's own trigger has already said so
    select e.guild_id into gid
      from public.events e
     where e.id = case when tg_op = 'DELETE' then old.event_id else new.event_id end;
  end if;

  -- a cascade from a deleted guild finds no guild: nobody is left to tell
  if gid is null or not exists (select 1 from public.guilds g where g.id = gid) then
    return null;
  end if;

  perform realtime.send(
    jsonb_build_object('table', tg_table_name, 'op', tg_op),
    'changed',
    'guild:' || gid::text,
    true);

  return null;
end;
$$;

revoke execute on function public.guild_ctas_changed() from public, anon, authenticated;

drop trigger if exists events_guild_changed on public.events;
create trigger events_guild_changed
  after insert or update or delete on public.events
  for each row execute function public.guild_ctas_changed();

drop trigger if exists signups_guild_changed on public.signups;
create trigger signups_guild_changed
  after insert or update or delete on public.signups
  for each row execute function public.guild_ctas_changed();


-- 2. who may listen: a guild's members, on their guild's topic ------------------

-- One permissive select policy on realtime.messages (lint 0006): the
-- project's table had none for the API roles. The joiner and the topic
-- are read once per statement (lint 0003). A member who leaves joins no
-- more; anon is admitted nowhere here.
do $$
begin
  if to_regclass('realtime.messages') is not null
     and to_regprocedure('realtime.topic()') is not null then
    drop policy if exists "Members receive their guild's broadcasts" on realtime.messages;
    create policy "Members receive their guild's broadcasts" on realtime.messages
      for select to authenticated
      using (realtime.messages.extension = 'broadcast'
             and exists (select 1 from public.guild_members m
                          where m.user_id = (select auth.uid())
                            and (select realtime.topic()) = 'guild:' || m.guild_id::text));
  end if;
end
$$;
