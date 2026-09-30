# The account database

The planner needs no backend: the engine and the dataset ship inside the
page. Accounts, and everything a player or caller keeps between visits, live
in the Supabase project "Albion Comp Forge": Supabase Auth for identity,
Postgres for the data, reached from the page through `window.DB`
(`dashboard/_supabase.js`) with the project's publishable key.

The publishable key is public by design. The rules below, enforced inside the
database, are the only thing that keeps one player's data from another's.

## Layout

- `migrations/` — the schema, one file per change, applied in file-name order
  (`<14-digit version>_<snake_case>.sql`, LF line endings).
- `migrations/20260928000000_profiles_baseline.sql` reproduces what the SQL
  editor built before migrations were kept here. Every statement in it is
  idempotent: applied to the project it changes nothing.

## Applying a migration

- An applied migration is never edited; a change is a new file.
- Apply the file's text with the Supabase CLI (`supabase db push`), the SQL
  editor, or the Supabase MCP `apply_migration`, then read the security
  advisor. The advisor must show no new warning.
- A page that needs a new table or function ships after its migration is
  applied. A page that meets a missing table says the feature is not
  available yet (`profileErrorKind` "missing" in `dashboard/_profile.js`); it
  never fails silently.

## The rules every table follows

1. **Row-level security on, before the first grant.** The project's default
   privileges grant every new `public` table and function to `anon` and
   `authenticated`, so every table starts with
   `revoke all ... from anon, authenticated` and grants back only what a
   signed-in user needs. Nothing is granted to `anon` beyond a guest's
   reach through a CTA's share code (rule 13).
2. **The account column comes from the session.** A user-owned row carries
   `user_id uuid not null default auth.uid() references public.profiles (id)
   on delete cascade`. Deleting an account deletes its data.
3. **One policy per operation, for signed-in users.** Each policy is
   `to authenticated` and reads `(select auth.uid())` (evaluated once per
   statement, Supabase lint 0003), never a bare `auth.uid()`.
4. **Column grants follow the form.** A user inserts and updates only the
   columns a form edits. Ids, the account column and timestamps are the
   server's.
5. **The database is the authority; the client gives the wording.** Every
   rule the client validates is also a `check` constraint, and the two bounds
   are pinned equal by a test (`ACCOUNT_NAME_MAX`, `ALBION_SERVERS`,
   `WEAPONS_MAX`, `WEAPON_KEY_RE`, `WEAPON_PREFERENCES`).
6. **`updated_at` is a trigger's job** (`public.set_updated_at()`), never the
   client's.
7. **A write that spans rows is one function call.** It is `security invoker`
   (the caller's policies and grants bound it exactly as they bound a direct
   write), `set search_path = ''`, execute revoked from `public` and `anon`,
   granted to `authenticated`. A contended write (claiming a sign-up slot)
   follows the same rule: one conditional statement, so two claims cannot
   both succeed.
8. **`security definer` is a listed exception, never a default.** The list
   (`DEFINER_ALLOWED` in `tests/test_supabase_schema.py`): `handle_new_user`,
   the sign-up trigger, which writes the new user's profile before any
   session exists, and the helpers policies and guards call, which live in
   the schema `private`, one the API does not expose (Supabase lint 0029):
   `private.guild_role_of` (a policy on `guild_members` that read
   `guild_members` under its own policy would recurse; it answers for the
   caller alone, `auth.uid()` read inside), `private.guild_id_for_code`
   (the insert policy checks a join code against a guild the joiner cannot
   yet read) and `private.guild_member_count` (the member bound counts rows
   the joiner cannot yet read). Every API function runs as the caller. A
   trigger function has execute revoked from `public`, `anon` and
   `authenticated`: triggers run it, the API never does.
9. **A user-writable list is bounded** (a storage bound against abuse,
   enforced by a trigger, not a product rule).
10. **Weapons are dataset keys.** A weapon is always the dataset's weapon-line
    key (`pipeline/out/dataset-latest.json` `weapons`, e.g.
    `2H_ICECRYSTAL_UNDEAD`). The database checks its form; the client checks
    it against the build's catalog and shows a key it no longer knows as
    unknown. The dataset stays the one weapon catalog: no copy of it lives in
    the database.
11. **A write that needs a fact the caller cannot read** (a join code names a
    guild the joiner cannot see) passes it through a transaction-local
    setting the policy reads (`join_guild` sets `app.join_code`, the insert
    policy checks it through the private helper): the function stays
    `security invoker`, and a direct write, which carries no setting, is
    refused.
12. **One permissive policy per table and action** (Supabase lint 0006): a
    second reader joins the existing policy's expression (own row, or a
    guild shared) instead of adding a policy. Every foreign key has a
    covering index (lint 0001). After a migration is applied the advisor
    must show no new warning.
13. **A guest reaches one CTA through its share code.** The code is a
    bearer key: it rides the statement as a transaction-local setting
    (rule 11, `app.share_code`), the policies `to anon` on `events`,
    `event_slots`, `guilds` and `signups` check it (or delegate to the
    event's policy), and `anon` is granted exactly the columns a guest
    sees and the sign-up a guest writes. The guest functions
    (`event_by_code`, `sign_up`, `cancel_sign_up`, `claim_hash`) run as
    the caller, signed in or not: the same policies bound a guest and a
    member. A guest's own row is keyed by the SHA-256 of a claim token
    the browser keeps (`app.claim_token` rides the statement; the token
    is never stored). `GUEST_TABLES` and `GUEST_FUNCTIONS` in
    `tests/test_supabase_schema.py` list the reach; nothing else is
    granted to `anon`, and no `anon` policy stands without the code.

## Schema

| Table / function | Holds / does | Read by | Written by |
| --- | --- | --- | --- |
| `profiles` | one row per account: `albion_name`, `display_name` (trimmed, 1–64 characters, or null), `albion_server` (`americas` / `asia` / `europe`, or null), `avatar_url` | its own account | its own account (the two names and the server); `handle_new_user` at sign-up |
| `player_weapons` | the weapon lines a player plays: `weapon_id`, `preference` (`main` / `secondary`), `sort_order`; at most 50 per player | its own account | its own account, through `set_my_weapons` or row by row |
| `set_my_weapons(weapons jsonb)` | saves a player's whole list in one transaction; a weapon kept across saves keeps its `created_at` | — | signed-in users |
| `handle_new_user()` | trigger on `auth.users`: creates the profile from the sign-up metadata, names trimmed and cut to the bound, a server off the list stored as null | — | the trigger |
| `set_updated_at()`, `player_weapons_bound()` | trigger functions | — | triggers |
| `guilds` | a guild on one server: `name` (trimmed, 1–64, unique per server whatever its case), `albion_server`, `join_code` (10 letters and digits, unique), `created_by` (null once that account is deleted; the guild stays) | its members; its creator | `create_guild`; admins rename it, renew its code (any written value becomes a fresh code) and delete it |
| `guild_members` | who belongs and as what: `role` in `member` / `caller` / `officer` / `admin`; at most 500 per guild, 20 per account | the guild's members | `create_guild` (the creator as admin), `join_guild` (the code holder as member); officers set members and callers between those two roles and remove them; admins set any role and remove anyone; a member removes their own row (leaves); the last admin is refused by the guard, and when the last admin's account is deleted the longest-standing officer, else caller, else member becomes admin (a guild with no one left goes with the account) |
| `guild_join_codes` | a view: `guild_id`, `join_code` for the guilds the caller is an officer or admin of | officers and admins | — |
| `create_guild(name, albion_server)` | the guild and its first admin in one transaction | — | signed-in users |
| `join_guild(code)` | the code holder becomes a member; a wrong code is `P0002`; a member joining again gets the guild. Runs as the caller: the code rides the statement (`app.join_code`) and the insert policy checks it (rule 11) | — | signed-in users |
| `private.guild_role_of(guild)`, `private.guild_id_for_code(code)`, `private.guild_member_count(guild)` | the helpers policies and the guard call, with their definer's rights, in the schema the API does not expose (rule 8) | policies, the guard | — |
| `new_join_code()`, `guilds_guard()`, `guild_members_guard()`, `guild_members_succession()` | the code generator (a column default); the guard triggers and the succession | — | the default expression; triggers |
| `comp_templates` | a comp a guild keeps: `name` (trimmed, 1–64, unique in the guild whatever its case), `content` and `style` (dataset keys; the database checks the form, the client the list), `planned_size` (2–60), `notes` (≤ 1000), `share_hash` (the planner's share link at save time, ≤ 8000), `created_by` / `updated_by` (null once that account is deleted; the comp stays); at most 100 per guild | the guild's members | callers, officers and admins, through `save_comp_template` or column by column |
| `comp_template_slots` | one slot of a comp: `position` (1–60, the planner's roster cap), `weapon_id` (a dataset key, or null for an open slot), `role` (the caller's label, ≤ 40), `note` (≤ 200) | the guild's members | callers, officers and admins (the position never moves: a slot is removed and re-added) |
| `save_comp_template(template jsonb)` | the comp and its slots in one transaction: created without an id, updated with one; unlisted slots go, listed ones are added or changed; a comp the caller cannot edit is `42501` | — | signed-in users |
| `comp_templates_guard()` | trigger: the 100-per-guild bound; `updated_by` follows every change | — | triggers |
| `events` | a CTA a guild runs: `name` (trimmed, 1–64), `content` and `style` (dataset keys), `planned_size` (2–60), `starts_at`, `mass_at` (never after the start), `notes` (≤ 1000), `status` (`draft` / `open` / `locked` / `completed`), `share_code` (10 letters and digits, unique, generated: the sign-up link of phase 5), `share_hash` (copied from the comp), `template_id` (the comp the slots were copied from; null once that comp is deleted, the CTA stays), `created_by` / `updated_by` (null once that account is deleted); at most 200 per guild | the guild's members | callers, officers and admins, through `save_event` or column by column; the status moves one step at a time (draft → open, open → draft or locked, locked → open or completed; completed is final), by the guard |
| `event_slots` | one slot of a CTA: `position` (1–60), `weapon_id` (a dataset key, or null for an open slot), `role` (≤ 40), `note` (≤ 200). COPIED from the comp's slots when the CTA is created; the CTA's own from then on | the guild's members | callers, officers and admins, until the CTA is completed: a completed CTA keeps its slots (the guard refuses every add, change and removal) |
| `save_event(event jsonb)` | the CTA and its slots in one transaction: created without an id (with a comp and no slots, the comp's content, style, size, share hash and slots are copied; a field the payload names wins), updated with one; when the payload names slots, unlisted ones go and listed ones are added or changed; a comp the caller cannot read is `P0002`; a CTA the caller cannot edit is `42501` | — | signed-in users |
| `events_guard()`, `event_slots_guard()` | triggers: the 200-per-guild bound, `updated_by` following every change, the status moves; the frozen slots of a completed CTA | — | triggers |
| `signups` | a player on a CTA: `position` (the slot claimed, or null: a reserve; a removed slot leaves its claimant a reserve), `user_id` (an account) or `guest_token_hash` (a guest: SHA-256 of the claim token their browser keeps), one of the two, `player_name` (trimmed, 1–64), `item_power` (0–3000), `can_swap`, `weapons` (dataset keys, each once, ≤ 10), `note` (≤ 200); one claimant per slot, one sign-up per account and per guest on a CTA; at most 120 per CTA | the guild's members; whoever holds the code | the player, through `sign_up` (while the CTA is open) and `cancel_sign_up` (until it is completed); a guest under the token, an account under its id |
| `event_by_code(code, token?)` | the CTA a share code names, with its guild, slots, sign-ups and the caller's own sign-up (by account, or by the token); `P0002` for a code that names nothing. Runs as the caller: the code rides the statement (rule 13) | — | guests and signed-in users |
| `sign_up(code, token, signup jsonb)` | the caller's sign-up on the CTA, made or changed in one statement: an account under its id, named after its character unless the payload names it (and adopting the guest sign-up its browser's token names); a guest under the token's hash, with a name. A claimed slot is `23505`; a CTA not open is `55000` | — | guests and signed-in users |
| `cancel_sign_up(code, token?)` | the caller's own sign-up gone, until the CTA is completed (`55000` after) | — | guests and signed-in users |
| `claim_hash(token)` | SHA-256 as hex: the policies compare the token the statement carries with the row's hash | policies, the functions | — |
| `signups_guard()` | trigger: the 120-per-CTA bound; every declared weapon a key, listed once | — | triggers |

**Who reads whom.** A profile and a weapon list are readable by their own
account and by every member of a guild the two share (the own-row select
policies on `profiles` and `player_weapons` carry the guild clause): a
caller reads what a member plays. Email addresses live in `auth.users` and
are never exposed. The join code is readable by officers and admins alone,
through the view. A CTA's share code is readable by the guild's members
and, through the code itself, by whoever holds it: it opens that one
CTA, its slots, its guild's name and its sheet, to guests too (rule 13).

## Tests

- `tests/test_supabase_schema.py` — the rules above as text, no database:
  RLS and anon revokes per table, policy roles and the `(select auth.uid())`
  form, `search_path` and execute grants per function, the definer
  allowlist, and the client's bounds equal to the database's.
- `tests/test_supabase_rls.mjs` — every migration run in a real Postgres
  (PGlite) beside a stand-in for the Supabase platform, each case run as an
  API role with a user's JWT claims: own rows only, column grants, anon
  reaches nothing without a share code and one CTA with it, the sign-up
  trigger, atomic saves, the bounds, the slot claim race, cascades.
  Needs `npm install --no-save @electric-sql/pglite@0.5.8` (a test-only
  install; the repository keeps no npm dependencies).
