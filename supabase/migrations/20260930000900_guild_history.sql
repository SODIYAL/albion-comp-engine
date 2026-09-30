-- Analytics (platform phase 9): facts over a guild's completed CTAs, read
-- from the attendance record (phase 8). One function answers a member
-- with the guild's totals, each completed CTA's counts, each player's
-- record (CTAs, attended, no-shows, cancellations, reserves, unmarked,
-- show rate, the weapons they played) and the weapons fielded. Nothing
-- is stored: the facts are computed on read, as the caller, from rows the
-- caller's policies let them see (a member reads the guild's CTAs and
-- their records; anyone else reads nothing and gets empty facts).
--
-- The measures, defined:
--   show rate   attended / (attended + no_show); an unmarked record (a
--               slot holder the caller never marked) is neither, and is
--               counted apart, so a rate is never guessed
--   fill        the slots held at the end / the roster's slots
--   played      the weapon of the slot a player held when the CTA
--               completed, counted over attended records alone
--   a player    an account by its id; a guest by their name, whatever
--               its case (a caller adds the same name to CTA after CTA;
--               the claim token that keys a guest's own sign-up would
--               split one player into many)
-- No skill rating: none of these is one, and none is offered as one.


create or replace function public.guild_history(guild_id uuid)
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$
  with ev as (
    select e.id, e.name, e.starts_at, e.content, e.style, e.planned_size,
           (select count(*)::int from public.event_slots s where s.event_id = e.id) as slots
      from public.events e
     where e.guild_id = guild_history.guild_id
       and e.status = 'completed'
  ),
  rec as (
    select a.id, a.event_id, a.user_id, a.player_name, a.position, a.weapon_id, a.status,
           case when a.user_id is not null then 'account:' || a.user_id::text
                else 'guest:' || lower(a.player_name) end as who,
           ev.starts_at
      from public.attendance a
      join ev on ev.id = a.event_id
  ),
  per_event as (
    select ev.id, ev.name, ev.starts_at, ev.content, ev.style, ev.planned_size, ev.slots,
           count(r.id)::int as records,
           (count(r.id) filter (where r.position is not null and r.status <> 'cancelled'))::int as claimed,
           (count(r.id) filter (where r.status = 'attended'))::int as attended,
           (count(r.id) filter (where r.status = 'no_show'))::int as no_show,
           (count(r.id) filter (where r.status in ('signed_up', 'confirmed')))::int as unmarked,
           (count(r.id) filter (where r.status = 'cancelled'))::int as cancelled,
           (count(r.id) filter (where r.status = 'reserve'))::int as reserve
      from ev
      left join rec r on r.event_id = ev.id
     group by ev.id, ev.name, ev.starts_at, ev.content, ev.style, ev.planned_size, ev.slots
  ),
  per_player as (
    select r.who,
           (array_agg(r.player_name order by r.starts_at desc))[1] as name,
           bool_or(r.user_id is not null) as account,
           count(*)::int as ctas,
           (count(*) filter (where r.status = 'attended'))::int as attended,
           (count(*) filter (where r.status = 'no_show'))::int as no_show,
           (count(*) filter (where r.status = 'cancelled'))::int as cancelled,
           (count(*) filter (where r.status = 'reserve'))::int as reserve,
           (count(*) filter (where r.status in ('signed_up', 'confirmed')))::int as unmarked,
           max(r.starts_at) filter (where r.status = 'attended') as last_attended,
           min(r.starts_at) as first_seen
      from rec r
     group by r.who
  ),
  played as (
    select r.who, r.weapon_id, count(*)::int as n
      from rec r
     where r.status = 'attended' and r.weapon_id is not null
     group by r.who, r.weapon_id
  )
  select jsonb_build_object(
    'totals', (select jsonb_build_object(
                 'ctas', count(*)::int,
                 'records', coalesce(sum(p.records), 0)::int,
                 'attended', coalesce(sum(p.attended), 0)::int,
                 'no_show', coalesce(sum(p.no_show), 0)::int,
                 'unmarked', coalesce(sum(p.unmarked), 0)::int,
                 'cancelled', coalesce(sum(p.cancelled), 0)::int,
                 'reserve', coalesce(sum(p.reserve), 0)::int,
                 'show_rate', round(sum(p.attended)::numeric / nullif(sum(p.attended) + sum(p.no_show), 0), 3),
                 'fill', round(avg(p.claimed::numeric / nullif(p.slots, 0)), 3))
                 from per_event p),
    'ctas', (select coalesce(jsonb_agg(to_jsonb(p) order by p.starts_at desc), '[]'::jsonb) from per_event p),
    'players', (select coalesce(jsonb_agg(jsonb_build_object(
                  'who', p.who, 'name', p.name, 'account', p.account, 'ctas', p.ctas,
                  'attended', p.attended, 'no_show', p.no_show, 'cancelled', p.cancelled,
                  'reserve', p.reserve, 'unmarked', p.unmarked,
                  'show_rate', round(p.attended::numeric / nullif(p.attended + p.no_show, 0), 3),
                  'last_attended', p.last_attended, 'first_seen', p.first_seen,
                  'weapons', (select coalesce(jsonb_agg(jsonb_build_object('weapon_id', w.weapon_id, 'n', w.n)
                                                        order by w.n desc, w.weapon_id), '[]'::jsonb)
                                from (select x.weapon_id, x.n from played x where x.who = p.who
                                       order by x.n desc, x.weapon_id limit 5) w))
                  order by p.attended desc, p.ctas desc, p.name), '[]'::jsonb)
                  from per_player p),
    'weapons', (select coalesce(jsonb_agg(jsonb_build_object('weapon_id', w.weapon_id, 'n', w.n, 'players', w.players)
                                          order by w.n desc, w.weapon_id), '[]'::jsonb)
                  from (select x.weapon_id, sum(x.n)::int as n, count(distinct x.who)::int as players
                          from played x group by x.weapon_id) w)
  );
$$;

revoke execute on function public.guild_history(uuid) from public, anon;
grant execute on function public.guild_history(uuid) to authenticated;
