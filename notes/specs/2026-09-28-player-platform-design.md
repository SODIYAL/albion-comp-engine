# Player platform — design (2026-09-28)

Status: phase 1 (accounts and the player profile) implemented 2026-09-28;
phase 2 (guilds), phase 3 (saved comps), phase 4 (CTAs) and phase 5
(sign-up) implemented 2026-09-30; phases 6–12 open (`BACKLOG.md`
"Platform"). The schema and its rules:
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
2. **Guilds** (implemented) — `guilds` (name, server, join code,
   created_by), `guild_members` (guild, user, role in member / caller /
   officer / admin). Guild-scoped read policies on profiles and weapon
   lists arrive here.
3. **Saved comps** (implemented) — `comp_templates` (guild, name, content,
   planned size, style, notes, the planner's share hash) and
   `comp_template_slots` (position, weapon key, role, note). A template is
   never a live roster.
4. **CTAs** (implemented) — `events` (guild, the comp it was copied from,
   name, content, style, planned size, start, mass time, notes, status
   draft / open / locked / completed, share code, the comp's share hash)
   and `event_slots`, COPIED from the template at creation: editing an
   event never touches its template.
5. **Sign-up** (implemented) — `signups` (event, slot or none, an account
   or a guest's claim-token hash, the name shown, item power, can-swap,
   the weapons declared, a note). Claiming a slot is one conditional
   statement under a unique index, so two claims cannot both succeed.
   Guests sign up through the CTA's link; an account gets the better
   experience (named after its character, profile weapons offered,
   history kept, the guest sign-up its browser made adopted).
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

## Phase 2 decisions

- **A guild lives on one server and its name is unique there**, whatever
  its case (a game fact: guild names are unique per server). The creator
  is its first admin; `created_by` goes null when that account is deleted
  and the guild stays.
- **Joining is by code.** A guild carries a 10-character code (40 bits of a
  random UUID; no extension needed). Whoever holds it joins as a member
  through `join_guild`, which runs as the caller: the code rides the
  statement as a transaction-local setting and the insert policy checks
  it through a private helper that reads the guild the joiner cannot yet
  see, so a direct insert, which carries no code, is refused. Officers and
  admins read the code through a view (`guild_join_codes`); an admin
  renews it by writing any value, which the guard replaces with a fresh
  code, so a code is never chosen.
- **Roles and reach, enforced by the database.** Officers set members and
  callers between those two roles and remove them; admins set any role and
  remove anyone; a member leaves. The policies say who may write; a guard
  trigger says what: an officer's reach, the four roles, and that the last
  admin can neither step down nor leave by their own statement. Callers
  carry no extra power in this phase (CTAs, phase 4). The client offers
  only what the guard would allow (`memberPowers`) and reads a refusal as
  a sentence; it never decides.
- **Succession.** When the last admin's account is deleted, the
  longest-standing officer, else caller, else member becomes admin; a guild
  with no one left is deleted with the account. Evidence: without it the
  cascade from `auth.users` hit the guard and the account deletion failed
  (the RLS suite's first run of the case). The rule runs after the delete
  and only ever sees a last-admin row a cascade removed, since the guard
  refused every other path.
- **Who sees what inside a guild** (the phase 1 open question): every
  member reads every co-member's character name, display name, server and
  weapon lists, through guild-scoped select policies on `profiles` and
  `player_weapons`. Nothing else: email addresses live in `auth.users`.
  Curation judgment: the tool exists to show a caller what members play.
- **Definer helpers live outside the API schema.** `guild_role_of` reads
  `guild_members` with its definer's rights because a policy on that
  table cannot read the table under its own policy (recursion); it answers
  for the caller alone (`auth.uid()` inside). It and the two helpers
  beside it (the guild a code names, a guild's member count) live in the
  schema `private`, which the API does not expose. Evidence: the security
  advisor flagged the first migration's `guild_role_of` and `join_guild`
  (lint 0029: a definer signed-in users can call through `/rest/v1/rpc`);
  the second migration moved the helper and made `join_guild` an invoker.
  The schema test lists every definer and pins that a non-trigger definer
  lives in `private`. The performance advisor's two findings (unindexed
  foreign keys, two permissive select policies on `profiles` and
  `player_weapons`) landed the same way: indexes, and the guild clause
  joined to the own-row select policies.
- **Bounds**: 500 members per guild, 20 guilds per account, the guild name
  under the account name bound (64). Storage bounds against abuse, not
  product rules.
- **Deferred**: invitations by name or request (a profile lookup outside
  the guild), per-member privacy of lists, guild avatars, a caller-only
  power.

## Phase 3 decisions

- **A template is one planner roster.** Slots are positions 1–60, the
  planner's roster cap (`HARD_CAP`, pinned equal to the slot bound by the
  schema test); the spec's "party" column is dropped. A ZvZ of several
  parties is several templates until CTAs need a grouping.
- **The planner is the editor; the bridge is the address bar.** A comp is
  saved from `location.hash`, the share link the planner already
  publishes (the loadout codec), and opened by setting it, which the
  planner applies as a pasted link. The account layer reads no planner
  state and the planner never calls it (layout contract L30). The saved
  hash is stored whole (`share_hash`), so the kits and spell picks come
  back while the roster still matches the slots; a changed roster opens as
  a plain `c=` / `n=` / `st=` / `p=` link built from the slots.
- **Callers write comps.** The caller role's first power: callers,
  officers and admins create, edit and delete a guild's templates; members
  read them. `save_comp_template` writes the template and its slots in one
  transaction; a slot's position never moves (a slot is removed and
  re-added), and `updated_by` follows every change by trigger.
- **Content and style are dataset keys.** The database checks the form,
  the client the list (`ACCOUNT_CONTENTS`, `ACCOUNT_STYLES`, stamped at
  build from the dataset's templates and styles; balanced is the absence of
  a style), the same rule weapon keys follow.
- **Bounds**: 100 templates per guild, 60 slots per template, notes ≤ 1000,
  a role label ≤ 40, a slot note ≤ 200, the name under the account name
  bound. Storage bounds against abuse, not product rules.
- **Deferred**: a weapon picker per slot inside the dialog, multi-party
  grouping, template versions.

## Phase 4 decisions

- **An event is a copy.** `save_event` copies the comp's content, style,
  size, share hash and slots into the event when the payload names a comp
  and no slots (a field the payload names wins); the dialog shows the
  copy before the caller saves and sends it. The event remembers the comp
  (`template_id`, null once the comp is deleted; the event stays whole),
  and nothing on an event ever writes a template. The planner's current
  comp is the other source, through the share hash, as for a comp.
- **The status moves one step at a time, by the guard.** draft → open,
  open → draft or locked, locked → open or completed; completed is final.
  The client offers the guard's moves (`EVENT_MOVES`, pinned equal to the
  guard's list by the schema test) and reads a refusal as a sentence.
- **A completed event keeps its slots.** Phase 8 reads them as history,
  so the slot guard refuses every add, change and removal once the event
  is completed; the payload of a completed event carries no slots. Its
  notes still change. A cascade from a deleted event or guild sees no
  event and lets the slots go: the trigger reads the event under the
  caller's own policy, and a row the statement removed is not there.
- **Callers run CTAs.** Callers, officers and admins create, edit, move
  and delete a guild's events; members read them, share codes included
  (the guild's own calendar; a guest reaches an event through the code
  in phase 5, by a function that needs no membership).
- **The share code is generated, never chosen**, the guild join code's
  form and generator (`new_join_code`), unique across events. It is the
  sign-up link of phase 5; renewing it is deferred there.
- **Times are instants.** `starts_at` (required) and `mass_at` (optional,
  never after the start: a check and the client's sentence) are
  `timestamptz`; the dialog reads and writes them in the viewer's local
  time and shows the UTC time the game runs on beside each start. The
  calendar lists ahead (soonest first) and past (latest first): completed
  events and starts more than twelve hours gone are past.
- **A start in the past is allowed**: a caller records a CTA that ran
  without the tool, so phase 8 can keep its attendance.
- **Bounds**: 200 events per guild, the slot, notes, role and note bounds
  the comp's. Storage bounds against abuse, not product rules.
- **Deferred**: renewing a share code, a guild-wide time zone, per-event
  multi-party grouping, a caller-only "my CTAs" view.

## Phase 5 decisions

- **Guest identity is a name and a claim token** (the open question,
  decided). The browser makes 16 random bytes on the first sign-up and
  keeps them per CTA in `localStorage`; the row stores their SHA-256
  (`claim_hash`); the token rides each statement (`app.claim_token`) and
  never lands in a column. That browser alone edits or cancels the
  sign-up; an account signing up from it later adopts the row (the row
  becomes the account's, the hash goes). A name alone would let anyone
  edit anyone and tie attendance to a typed string; a login would cost
  a guest the frictionless path the spec asks for. A cleared browser
  loses the claim: the caller's removal (phase 6) is the way out.
- **The share code is the guest's key, and `anon` gets a bounded
  reach** (rule 13). Rule 1's "nothing to anon" stood while no guest
  existed; the spec's guest needs the CTA, its slots, its guild's name
  and its sheet, and a sign-up of their own. The code rides the
  statement as the join code does (rule 11), policies `to anon` check it
  or delegate to the event's policy, and the grants to `anon` are the
  columns a guest sees (the share code among them, since the functions
  select the CTA by it and the policy already limits a guest to that
  one) and the sign-up columns a guest writes. Every guest function runs
  as the caller: no definer, so the advisor's lint on definers exposed
  to the API stays quiet and the same policies bound a guest and a
  member. The schema test lists the reach (`GUEST_TABLES`,
  `GUEST_FUNCTIONS`) and refuses any other grant to `anon` or any `anon`
  policy that does not read the code.
- **One sign-up per player per CTA, claimed in one statement.**
  `sign_up` inserts with `ON CONFLICT` on the player's own partial
  unique index (account, or guest hash), so a second call updates; a
  slot already claimed is the slot index's `23505`; a slot not on the
  roster is the foreign key's `23503`; a removed slot leaves its
  claimant a reserve (`on delete set null (position)`).
- **Open to sign up, not completed to cancel.** Sign-ups are written
  while the CTA is open (a policy clause and `55000` from the function);
  a player cancels until it is completed; a completed CTA keeps its sheet
  (phase 8 reads it).
- **The sheet's name is a snapshot.** `player_name` is stored for every
  sign-up (an account's from its character, or the payload's for an
  alt), so the sheet reads without a join to `profiles` and the history
  keeps the name as declared.
- **Time and identity on the link.** The link opens the sheet once the
  stored session has been read, so an account signs up as itself and a
  guest never makes a needless claim; the CTAs dialog opens the sheet by
  a DOM event (`cta-sheet`), never a call between modules.
- **Bounds**: 120 sign-ups per CTA, 10 weapons declared, item power
  0–3000, a note ≤ 200, the name under the account name bound. Storage
  bounds against abuse, not product rules.
- **Deferred**: caller controls on the sheet (phase 6), Realtime
  (phase 7), a guest's history joining an account made elsewhere, a
  guild-scoped name search for callers filling slots.

## Open questions

- **Guest identity** is decided (phase 5 decisions: a name and a claim
  token). Open: how a guest's history joins an account made on another
  browser (a Discord login, phase 12, is the candidate).
- **Supabase Auth settings**: leaked-password protection is off (security
  advisor).
