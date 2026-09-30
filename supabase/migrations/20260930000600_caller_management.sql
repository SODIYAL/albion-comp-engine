-- Caller management (platform phase 6): the caller runs the sheet. A
-- caller, officer or admin of the guild moves a player to another slot or
-- to the reserves (swapping with whoever holds the target), removes a
-- sign-up, adds a player by name (someone signing up in Discord, kept as
-- a guest row nobody holds a token for), and changes a slot's weapon
-- (event_slots, the phase 4 grant). Lock, reopen and complete are the
-- phase 4 status moves. All of it until the CTA is completed; a
-- completed sheet is history.
--
-- The policies gain a caller branch beside the player's own; a guard
-- keeps every sign-up's player (the identity columns change only for the
-- phase 5 adoption). The functions run as the caller: a member who calls
-- them changes nothing and is told so. tests/test_supabase_schema.py and
-- tests/test_supabase_rls.mjs pin all of it.


-- 1. the caller branch on the sheet's policies ---------------------------------

-- a caller adds a player (a guest row, no account) until the CTA is completed
alter policy "Players sign up while open" on public.signups
  with check ((user_id = (select auth.uid())
               and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'))
              or (user_id is null
                  and private.guild_role_of((select e.guild_id from public.events e where e.id = event_id))
                      in ('caller', 'officer', 'admin')
                  and exists (select 1 from public.events e where e.id = event_id and e.status <> 'completed')));

-- a caller moves and edits any sign-up until the CTA is completed
alter policy "Players edit their sign-up while open" on public.signups
  using (((user_id = (select auth.uid())
           or guest_token_hash = public.claim_hash((select current_setting('app.claim_token', true))))
          and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'))
         or (private.guild_role_of((select e.guild_id from public.events e where e.id = event_id))
             in ('caller', 'officer', 'admin')
             and exists (select 1 from public.events e where e.id = event_id and e.status <> 'completed')))
  with check ((user_id = (select auth.uid()) and guest_token_hash is null
               and exists (select 1 from public.events e where e.id = event_id and e.status = 'open'))
              or (private.guild_role_of((select e.guild_id from public.events e where e.id = event_id))
                  in ('caller', 'officer', 'admin')
                  and exists (select 1 from public.events e where e.id = event_id and e.status <> 'completed')));

-- a caller removes any sign-up until the CTA is completed
alter policy "Players cancel their sign-up" on public.signups
  using (exists (select 1 from public.events e where e.id = event_id and e.status <> 'completed')
         and (user_id = (select auth.uid())
              or private.guild_role_of((select e.guild_id from public.events e where e.id = event_id))
                 in ('caller', 'officer', 'admin')));


-- the caller writes the guest row's hash and a null user_id (add_player:
-- the column's default is the caller's own id); the policy's own branch
-- still binds user_id to the caller, and the one-identity check refuses
-- both columns at once
grant insert (user_id, guest_token_hash) on table public.signups to authenticated;


-- 2. the guard: a sign-up keeps its player ----------------------------------------

-- The identity columns (user_id, guest_token_hash) change only for the
-- phase 5 adoption: a guest row becomes the row of the account whose
-- browser holds the token. A caller's grant on those columns (the
-- adoption needs it) buys no other change.
create or replace function public.signups_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT'
     and (select count(*) from public.signups where event_id = new.event_id) >= 120 then
    raise exception 'a CTA takes at most 120 sign-ups' using errcode = '23514';
  end if;
  if tg_op = 'UPDATE'
     and (new.user_id is distinct from old.user_id or new.guest_token_hash is distinct from old.guest_token_hash)
     and not (old.user_id is null and new.user_id = (select auth.uid()) and new.guest_token_hash is null) then
    raise exception 'a sign-up keeps its player' using errcode = '42501';
  end if;
  if exists (select 1 from unnest(new.weapons) as w where w !~ '^[A-Z0-9_]{1,64}$') then
    raise exception 'a declared weapon is not a weapon key' using errcode = '23514';
  end if;
  if (select count(distinct w) from unnest(new.weapons) as w) <> coalesce(array_length(new.weapons, 1), 0) then
    raise exception 'a weapon is declared twice' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke execute on function public.signups_guard() from public, anon, authenticated;


-- 3. move_signup: a player to a slot, the reserves, or another player's slot ------

-- The target slot's holder, if any, takes the moved player's old place
-- (a swap, in one transaction: the slot index never sees two holders).
-- Runs as the caller: the policies decide who moves whom (a player their
-- own row while open, a caller anyone until completed); a move the
-- policies refuse changes nothing and is 42501.
create or replace function public.move_signup(signup_id uuid, target smallint)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  s public.signups;
  ev record;
  holder uuid;
  n integer;
begin
  select * into s from public.signups where id = signup_id;
  if s.id is null then
    raise exception 'the sign-up was not found' using errcode = 'P0002';
  end if;

  select e.id, e.status into ev from public.events e where e.id = s.event_id;
  if ev.status = 'completed' then
    raise exception 'the CTA is completed; its sheet is kept' using errcode = '55000';
  end if;

  if target is not null and target is not distinct from s.position then
    return jsonb_build_object('id', s.id, 'position', s.position, 'swapped', null);
  end if;

  holder := null;
  if target is not null then
    select x.id into holder from public.signups x
     where x.event_id = s.event_id and x.position = target and x.id <> s.id;
  end if;

  if holder is not null then
    update public.signups set position = null where id = holder;
    get diagnostics n = row_count;
    if n = 0 then
      raise exception 'your role does not manage this sheet' using errcode = '42501';
    end if;
  end if;

  update public.signups set position = target where id = s.id;
  get diagnostics n = row_count;
  if n = 0 then
    raise exception 'your role does not manage this sheet' using errcode = '42501';
  end if;

  if holder is not null then
    update public.signups set position = s.position where id = holder;
  end if;

  return jsonb_build_object('id', s.id, 'position', target, 'swapped', holder);
end;
$$;

revoke execute on function public.move_signup(uuid, smallint) from public, anon;
grant execute on function public.move_signup(uuid, smallint) to authenticated;


-- 4. add_player: the caller writes a player onto the sheet -----------------------

-- A player without the link (signing up in Discord, say) as a guest row
-- with a token hash nobody holds: the caller alone edits it. The payload:
-- {player_name, position?, item_power?, can_swap?, weapons?, note?}. Runs
-- as the caller: the insert policy's caller branch decides; a member is
-- refused (42501), a taken slot is 23505.
create or replace function public.add_player(event_id uuid, player jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  s public.signups;
  who text := nullif(btrim(coalesce(player ->> 'player_name', '')), '');
  declared text[] := coalesce((select array_agg(w.x) from jsonb_array_elements_text(coalesce(player -> 'weapons', '[]'::jsonb)) as w(x)), '{}');
begin
  if who is null then
    raise exception 'a player needs a name' using errcode = '23502';
  end if;

  insert into public.signups (event_id, position, user_id, guest_token_hash, player_name, item_power, can_swap, weapons, note)
  values (add_player.event_id,
          nullif(player ->> 'position', '')::smallint,
          null,
          public.claim_hash(gen_random_uuid()::text),
          who,
          nullif(player ->> 'item_power', '')::smallint,
          coalesce((player ->> 'can_swap')::boolean, false),
          declared,
          nullif(btrim(coalesce(player ->> 'note', '')), ''))
  returning * into s;

  return jsonb_build_object(
    'id', s.id, 'position', s.position, 'player_name', s.player_name, 'item_power', s.item_power,
    'can_swap', s.can_swap, 'weapons', to_jsonb(s.weapons), 'note', s.note);
end;
$$;

revoke execute on function public.add_player(uuid, jsonb) from public, anon;
grant execute on function public.add_player(uuid, jsonb) to authenticated;
