# Player platform — design (2026-09-28)

Status: phase 1 (accounts and the player profile) implemented 2026-09-28;
phases 2–12 open (`BACKLOG.md` "Platform"). The schema and its rules:
`supabase/README.md`. The client modules: `dashboard/README.md` "Accounts".

## Problem

ZvZ callers run CTAs from spreadsheets: a comp sheet posted in Discord,
players typing their names beside weapons, the caller watching by eye for
missing roles and moving people by hand. Attendance and what each player
plays are rarely kept in a form the next CTA can use.

The site already answers the composition question (the capability engine).
It keeps nothing between visits: no player, no guild, no comp, no event.

## The product rule

The site's advantage over a spreadsheet is structured data read by the
engine, not a spreadsheet inside a page. Every feature stores what a caller
will want to ask later — which slots are open, which roles are missing, who
can fill a need, who attends, who plays what — as rows the engine and the
analytics can read, never as free text.

## Architecture

Three layers, never merged:

1. **The engine** (`engine/`) — composition logic, capability scoring,
   recommendations, weaknesses, overstack, replacements. It holds no account,
   database or sign-up logic and reads no attendance.
2. **Supabase** — identity (Supabase Auth) and every persistent row:
   profiles, guilds, memberships, comp templates, events, slots, sign-ups,
   attendance, imports.
3. **The dashboard** — display, forms, caller controls, and the translation
   of engine output into caller language.

One account type. A user's powers come from guild membership roles
(`member`, `caller`, `officer`, `admin`), never from a second kind of
account: a player and a caller are the same user in different guilds or
roles.

## Phases and their data (a sketch; each table follows supabase/README.md)

1. **Accounts and the player profile** (implemented) — `profiles` (the
   character: Albion name and server; a display name), `player_weapons`
   (weapon lines, `main` / `secondary`, order).
2. **Guilds** — `guilds` (name, created_by), `guild_members` (guild, user,
   role in member / caller / officer / admin). Guild-scoped read policies on
   profiles and weapon lists arrive here.
3. **Saved comps** — `comp_templates` (guild, name, content, planned size,
   style) and `comp_template_slots` (party, position, weapon key, role,
   note). A template is never a live roster.
4. **CTAs** — `events` (guild, caller, name, start, mass time, notes, status
   draft / open / locked / completed, share code) and `event_slots`, COPIED
   from the template at creation: editing an event never touches its
   template.
5. **Sign-up** — `signups` (event, slot or none, user or guest name, item
   power, can-swap, the weapons declared). Claiming a slot is one conditional
   statement (`where status = 'open'`), so two claims cannot both succeed.
   Guests stay possible; an account gets the better experience (names filled
   in, profile weapons offered, history kept).
6. **Caller management** — move, remove, lock, change weapon, reserves,
   promote, close and reopen sign-up: each a function under the caller's
   guild role.
7. **Live updates** — Supabase Realtime on slots and sign-ups; the database
   enforces the concurrency, the channel only reports it.
8. **History** — attendance (`signed_up`, `confirmed`, `attended`,
   `no_show`, `cancelled`, `reserve`) kept apart from the sign-up; a
   completed event keeps its slots and attendance.
9. **Analytics** — facts over completed events: CTAs, sign-ups, attendance
   and show rate, regulars, roles and weapons played ("played Heavy Mace in
   31 CTAs"). No skill rating without a defined, evidenced measure.
10. **Import / export** — Excel / CSV / Sheets to a normalized template:
    detect columns, map weapon / player / role / party / count, match names
    to weapon keys through an alias table, show uncertain matches for review.
    One-way import first; no live sync.
11. **Engine on the live roster** — the event's weapon keys through the
    engine: weaknesses, overstack, open-slot priorities, replacements; then
    beside player availability and preference. Descriptive, like every
    other analyzer: attendance and preference never enter capability
    scoring without a logged decision.
12. **Integrations** — Discord OAuth and bot, Google Sheets, automatic
    roster construction (an optimization over the target comp, the players'
    declared weapons and their preferences).

## Patterns phase 1 sets

- **The schema lives in the repository** as migrations, pinned by two tests:
  the rules as text (`tests/test_supabase_schema.py`) and the behaviour in a
  real Postgres (`tests/test_supabase_rls.mjs`).
- **User-owned rows**: a `user_id` defaulted from `auth.uid()`, a policy per
  operation, column grants that follow the form, `check` constraints
  mirroring the client's validation with the bounds pinned equal, a bounded
  list, `updated_at` by trigger.
- **Writes that span rows are one invoker function** (`set_my_weapons`): one
  transaction, the caller's own policies bounding it.
- **Client modules**: each feature its own source file and `<script>` after
  `_auth.js`, split into helpers (the only code touching `window.DB`), pure
  functions (node-tested) and UI; identity from `window.Account`; dialogs
  through the shared kit (`acctWireDialog`, `acctBusy`, `acctFlagFields`,
  `acctMessage`).
- **A weapon is the dataset's weapon-line key everywhere** — profiles,
  templates, slots, sign-ups. The build's `ACCOUNT_CATALOG` carries each
  key's name, role class and render item; a key the catalog no longer holds
  stays, shown as unknown.
- **Roles derive from weapons**: the catalog's role is the engine's
  `role_class` (the one role read), stamped at build and pinned against the
  engine by the layout test. A player's roles are read from their weapons,
  never stored beside them.

## Phase 1 decisions

- **`profiles` column grants narrowed** to the two names (insert also the
  id). Evidence: the project granted `authenticated` UPDATE on every column,
  `id`, `created_at` and `updated_at` included
  (`information_schema.column_privileges`).
- **Names trimmed, 1–64 characters, or null**, in `check` constraints and in
  the sign-up trigger, which now trims and cuts instead of failing a
  sign-up. 64 is a storage bound against abuse, not a game rule (curation
  judgment). No stored row broke the rule when it was added.
- **`updated_at` by trigger**: the column had a default and no trigger, so
  it never moved.
- **`handle_new_user` loses API execute.** Evidence: Supabase database lints
  0028 and 0029 flagged it as callable by `anon` and `authenticated` through
  `/rest/v1/rpc`. The trigger still fires (pinned by the RLS test).
- **`player_weapons`**: one row per weapon line per player, `main` (brought
  when the caller needs it) or `secondary` (can also play), in the player's
  order; at most 50 rows (storage bound, curation judgment); `created_at`
  kept across saves so "listed since" stays a fact later phases can read.
- **Weapon keys checked for form in the database, against the catalog in
  the client.** A database copy of the catalog would be a second weapon
  catalog beside the dataset.
- **Profiles and weapon lists readable by their own account alone** until guilds
  define who else may read them.
- **Profiles record the Albion server** (`americas`, `asia`, `europe`):
  character names are unique per server, not across the game, and a guild
  lives on one server. Required in both forms; null for rows that predate
  it and for sign-ups from clients that do not send it (a value off the list
  is stored as null, never a failed sign-up). Guilds carry a server in
  phase 2.
- **Deferred**: experience level, avatars (Storage), stored preferred
  roles, weapon aliases (phase 10).

## Open questions

- **Guest identity.** What a guest sign-up records, and how a guest's
  history joins an account created later. The candidates:
  - a name only: the least friction, but anyone can type any name, a guest
    cannot safely edit or cancel their own sign-up, and attendance ties to a
    typed string (typos and duplicates split one player);
  - a name and a claim token: a random secret kept in the guest's browser,
    its hash in the database; that browser alone (and the caller) edits or
    cancels the sign-up, and an account created later on the same browser
    can take over the guest's history;
  - a Discord login (phase 12): real identity, at a sign-in's friction.
- **Who sees what inside a guild**: which profile fields and weapon lists
  members, callers and officers read.
- **Supabase Auth settings**: leaked-password protection is off (security
  advisor).
