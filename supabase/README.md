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
   signed-in user needs. Nothing is granted to `anon`.
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
8. **`security definer` is a listed exception, never a default.** The one
   allowed today is `handle_new_user`, the sign-up trigger, which writes the
   new user's profile before any session exists. A trigger function has
   execute revoked from `public`, `anon` and `authenticated`: triggers run it,
   the API never does.
9. **A user-writable list is bounded** (a storage bound against abuse,
   enforced by a trigger, not a product rule).
10. **Weapons are dataset keys.** A weapon is always the dataset's weapon-line
    key (`pipeline/out/dataset-latest.json` `weapons`, e.g.
    `2H_ICECRYSTAL_UNDEAD`). The database checks its form; the client checks
    it against the build's catalog and shows a key it no longer knows as
    unknown. The dataset stays the one weapon catalog: no copy of it lives in
    the database.

## Schema

| Table / function | Holds / does | Read by | Written by |
| --- | --- | --- | --- |
| `profiles` | one row per account: `albion_name`, `display_name` (trimmed, 1–64 characters, or null), `albion_server` (`americas` / `asia` / `europe`, or null), `avatar_url` | its own account | its own account (the two names and the server); `handle_new_user` at sign-up |
| `player_weapons` | the weapon lines a player plays: `weapon_id`, `preference` (`main` / `secondary`), `sort_order`; at most 50 per player | its own account | its own account, through `set_my_weapons` or row by row |
| `set_my_weapons(weapons jsonb)` | saves a player's whole list in one transaction; a weapon kept across saves keeps its `created_at` | — | signed-in users |
| `handle_new_user()` | trigger on `auth.users`: creates the profile from the sign-up metadata, names trimmed and cut to the bound, a server off the list stored as null | — | the trigger |
| `set_updated_at()`, `player_weapons_bound()` | trigger functions | — | triggers |

Profiles and weapon lists are readable by their own account alone until guilds
exist; guild-scoped read policies arrive with the guild tables
(`notes/specs/2026-09-28-player-platform-design.md`).

## Tests

- `tests/test_supabase_schema.py` — the rules above as text, no database:
  RLS and anon revokes per table, policy roles and the `(select auth.uid())`
  form, `search_path` and execute grants per function, the definer
  allowlist, and the client's bounds equal to the database's.
- `tests/test_supabase_rls.mjs` — every migration run in a real Postgres
  (PGlite) beside a stand-in for the Supabase platform, each case run as an
  API role with a user's JWT claims: own rows only, column grants, anon
  reaches nothing, the sign-up trigger, atomic saves, the bound, cascades.
  Needs `npm install --no-save @electric-sql/pglite@0.5.8` (a test-only
  install; the repository keeps no npm dependencies).
