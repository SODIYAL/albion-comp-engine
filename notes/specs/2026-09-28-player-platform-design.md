# Player platform — design (2026-09-28)

Status: phase 1 (accounts and the player profile) implemented 2026-09-28;
phase 2 (guilds), phase 3 (saved comps), phase 4 (CTAs), phase 5
(sign-up), phase 6 (caller management), phase 7 (live updates), phase 8
(history), phase 9 (analytics), phase 10 (import and export) and phase
11 (the engine on the live roster) implemented 2026-09-30; phase 12 open
(`BACKLOG.md` "Platform"). The schema and its rules:
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
6. **Caller management** (implemented) — move (a held slot swaps),
   remove, add a player by name, change a slot's weapon, promote a
   reserve, lock, reopen and complete: on the sheet, under the caller's
   guild role, until the CTA is completed.
7. **Live updates** (implemented) — Realtime Broadcast on the CTA's
   topic after every write to the sheet; the database enforces the
   concurrency, the channel only reports it, and the sheet re-reads
   itself under its own policies.
8. **History** (implemented) — `attendance` (`signed_up`, `confirmed`,
   `attended`, `no_show`, `cancelled`, `reserve`), one record per player
   per CTA, kept apart from the sign-up by its own trigger; a completed
   event keeps its slots and its record, the slot's weapon copied in.
9. **Analytics** (implemented) — facts over completed events, computed
   on read from the attendance record (`guild_history`): CTAs, records,
   attendance and show rate, fill, regulars, weapons played ("played the
   Longbow in 31 CTAs") and the weapons fielded. No skill rating.
10. **Import / export** (implemented) — Excel / CSV / Sheets to a normalized template:
    detect columns, map weapon / player / role / party / count, match names
    to weapon keys through an alias table, show uncertain matches for review.
    One-way import first; no live sync.
11. **Engine on the live roster** (implemented) — the event's weapon keys through the
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

- **A template is one planner roster.** Slots are positions 1–60, three
  full parties of the planner's party cap (`HARD_CAP`, 20; the schema test
  pins the relation); the spec's "party" column is dropped. A ZvZ of several
  parties is several templates until CTAs need a grouping.
- **The planner is the editor; the bridge is the address bar.** A comp is
  saved from `location.hash`, the share link the planner already
  publishes (the loadout codec), and opened by setting it, which the
  planner applies as a pasted link. The account layer reads no planner
  state and the planner never calls it (layout contract L30). The saved
  hash is stored whole (`share_hash`), so the kits and spell picks come
  back while its members still match the slots position by position.
  Each slot carries the kit the saved hash holds for it, read through the
  loadout codec (the member at the slot's position while the slot names
  that member's weapon, the sheet's rule); once a slot changes, the link
  is built from the slots and their kits (`kitHash`): a changed slot
  opens without a kit, the others keep theirs, a removed slot takes its
  own along, and a save stores that link. A roster without any kit opens
  as a plain `c=` / `n=` / `st=` / `p=` link built from the slots.
- **A slot's weapon is set in the dialog too.** A writer picks it with
  the profile's combobox on the slot's name (the profile's search, and
  the open slot, which Enter never picks unasked), inside the slot guard:
  a catalog key or null through `save_comp_template`, the
  `update (weapon_id, role, note)` grant and the weapon form check.
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
- **Deferred**: multi-party grouping, template versions.

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

## Phase 6 decisions

- **The caller runs the sheet from the sheet.** The controls live in
  the sign-up dialog, offered to a caller, officer or admin of the CTA's
  guild (`callerPowers`: the policies' roles, until completed): a move
  list beside every sign-up, a removal, a weapon list on every slot,
  add-a-player, the status moves. No second surface.
- **The policies gain a caller branch; a guard keeps the player.** The
  sheet's insert, update and delete policies admit the caller roles
  until the CTA is completed beside the player's own row. The caller's
  grants on the identity columns (the phase 5 adoption needs them) buy
  no other change: the guard refuses any change to `user_id` or the
  hash that is not a guest row becoming the calling account's.
- **A move onto a held slot is a swap in one transaction**
  (`move_signup`): the holder steps to the mover's old place, through
  the reserves, so the slot index never sees two holders. A player
  moving their own row cannot swap another out (the holder's update is
  refused and the transaction rolls back).
- **A player the caller adds is a guest row nobody holds a token for**
  (`add_player`, the hash of a random UUID): the caller alone changes
  them, and the row reads as a guest on the sheet. A caller writing
  from Discord needs no account for the player.
- **Locked still lets the caller work.** Players stop signing up and
  changing at lock; the caller still moves, adds and removes, and a
  player still cancels. Completed freezes the sheet for everyone.
- **Deferred**: bulk moves, a caller's note on a player, attendance
  marks (phase 8), Realtime (phase 7).

## Phase 7 decisions

- **Broadcast, not Postgres Changes.** Postgres Changes checks a
  subscriber's row-level policies outside any statement, so a guest,
  whose policy reads the share code from the statement (rule 13), would
  receive nothing, and an account would receive rows. The sheet instead
  listens on a public Broadcast topic, `cta:<share code>` (the code is
  the key), for a message that names a table and an operation and
  nothing else, then re-reads the sheet through `event_by_code`. One
  mechanism for guests and members; no row crosses the channel; the
  policies still decide what is read.
- **The broadcast trigger runs with its definer's rights** (a listed
  exception, rule 8). Evidence: `realtime.messages` is protected by row-level security
  with no policy for the API roles, and `realtime.send` catches the
  refusal and drops the message, so a send as `anon` on the project
  landed nothing. The function reads one column of one row, sends a
  fixed-shape message, and no API role can call it. The RLS suite runs
  beside a stand-in whose message table is protected the same way, so
  the reason stays pinned.
- **The channel only reports.** A swap sends a message per row changed;
  the sheet settles a moment and reads once. A change someone else made
  never refills the player's form; a move or removal of their own row
  is said out loud. Without Realtime (a self-hosted database without
  it) the trigger does nothing and the sheet keeps its Refresh.
- **Deferred**: a live CTAs dialog (a channel per guild), presence (who
  has the sheet open), a live planner roster from the sheet (phase 11).

## Phase 8 decisions

- **The record is its own table, written by its own trigger.** A
  sign-up is a live claim: it goes when the player cancels or the
  caller removes them, and the slot frees. The record stays: made when
  the player signs up, kept in step with moves, renames and adoptions,
  `cancelled` when the claim goes (unless the caller has already
  marked it), settled at completion. Found by the player's identity,
  never by the sign-up id (a foreign key nulls that before the trigger
  runs). No API role holds an insert or delete grant on it, so the
  trigger runs with its definer's rights, a listed exception to rule 8
  beside the broadcast trigger.
- **Who writes which status.** The player moves their own record
  between `signed_up` and `confirmed` before completion; a caller,
  officer or admin sets any listed status, any time, completion
  included, and the guard stamps who and when; `cancelled` and
  `reserve` are the record's own findings, shown in the caller's list
  only when a row already holds them. The guard tells the record's own
  writes apart by trigger depth (two and beyond).
- **Completion settles, it does not guess.** A reserve becomes
  `reserve`; a slot holder keeps `signed_up` or `confirmed` until the
  caller marks `attended` or `no_show` (one by one, or everyone in a
  slot at once, then the no-shows); the slot's weapon at completion is
  what the player played, and the declared weapons are copied. An
  unmarked row is unknown, never counted as attended (phase 9).
- **A mark already made survives the claim going**: a player marked
  attended and then removed stays attended. Signing up again brings
  the same record back to `signed_up`, cleared of any mark.
- **Deleting an account deletes its records** (rule 2), the guild's
  history losing that player; deleting a CTA deletes them all.
- **Deferred**: a player's own history across CTAs (phase 9), a
  caller's note on a record, a mark's audit trail.

## Phase 9 decisions

- **Computed on read, as the caller.** One function returns a guild's
  facts from the attendance record; nothing is stored, nothing is
  summed ahead, and the caller's own policies bound what is counted (a
  member reads the guild's CTAs; anyone else gets empty facts, not a
  refusal). Only completed CTAs are history: a live sheet is not.
- **Every measure is defined and shown beside the facts.** Show rate is
  attended over attended plus no-show, with the unmarked counted apart,
  so a caller who never marked a CTA never inflates or deflates a rate;
  fill is the slots held at the end over the roster's slots; played is
  the slot's weapon at completion, over attended records alone; a
  regular attended three or more at 75% or better (a curation
  judgment, stated in the dialog). No skill rating exists, and none is
  offered as one.
- **A player is an account by id, a guest by name** whatever its case.
  The claim token that keys a guest's own sign-up would split one
  player into many when a caller adds the same name CTA after CTA;
  grouping guests by name makes "Disc came to six of eight" true at the
  cost of merging two guests who share a name. A guest who wants their
  own line makes an account.
- **Roles are read through the catalog, on the client**, from the
  weapons played: one role read, no second classification in the
  database.
- **Deferred**: a period window, a player's own history across guilds,
  a caller's leaderboard by role. The export of the facts is phase 10.

## Phase 10 decisions

- **The sheet is read in the browser, never uploaded.** Pasted cells
  (Excel and Sheets copy them tab-separated), a CSV, TSV or text file,
  a Discord or Markdown table: the parser reads tabs, commas,
  semicolons, pipes and quotes. An Excel workbook (.xlsx, .xlsm) is read
  by the page itself, no library: the zip's directory, its parts stored
  or deflated and checked against their size and CRC-32, the worksheets
  in tab order, the shared strings and the chosen sheet's cells (a merge
  read in its top-left cell, as Excel copies it); a workbook of several
  sheets offers them, and the chosen sheet's cells take the paste's
  path. A password, an .xls, a zip that is no workbook and a damaged
  file are refused with the way round. Nothing about the sheet is stored
  but the comp it becomes and the names the caller chose.
- **Gear columns become each slot's kit.** Helm, armor, boots, cape,
  off-hand, potion and food columns are read within their slot of the
  gear catalog the page carries (one name over several tiers reads the
  tier the sheet writes, else the highest); an uncertain or unread piece
  is no piece (never guessed), a two-hander holds no off-hand and an
  open slot no kit. The kits ride in the comp's share hash through the
  loadout codec, an open slot an empty entry of `p=` so every slot keeps
  its position. A gear choice is not remembered: the guild's remembered
  names are weapon lines.
- **Columns are detected, then the caller's.** A header row (one of the
  first three rows naming a kind and holding no weapon) decides where
  it can; the cells decide the rest: mostly weapons, integers (1, 2, 3
  in order is a slot number, anything else a count), party labels, role
  words, short texts (a player), long ones (a note). Two weapon columns
  are parties side by side (a grid); one is a list, in which a row with
  one cell that is a party label or a role word opens a section. The
  map is shown as a select per column and the rows are re-read as it is
  changed.
- **A name is read through the catalog, then the guild's names, then
  derived.** The dataset key, the display name, an alias (the guild's
  remembered names, then a short built-in list of dual-line plurals),
  then in order: all the words, a prefix, word prefixes, the initials,
  the key's own words, a text inside the name, a close spelling (one
  edit, two for a long text). One candidate is likely (accepted, marked
  for a glance); several are uncertain (the caller chooses; the plain
  line named "X Staff" decides "arcane", "holy", "fire" among the great
  ones); none is an open slot with the text as its note, or its role
  when the text is a role word. "1h" and "2h" narrow the pool to a
  hand; tier, enchantment and quality words are dropped. Removed lines
  never match. The matcher is pinned against the dataset's own catalog
  (`tests/test_import.js`).
- **A chosen name is remembered per guild** (`weapon_aliases`: the
  normalized text and the key; at most 500 per guild, 100 per save):
  the next import reads it as an alias. A name the derivation read and
  the caller kept is not stored (it reads the same way again); a
  catalog name given another line is not stored (the name wins). A
  member sees the names, the caller roles change and remove them.
  Never a copy of the catalog (rule 10).
- **A template has no player and no party.** The player column and the
  party labels are shown in the review; each may ride in the slot's
  note (players off by default, parties on when there are two or more).
  The slots follow the sheet's order, parties in sequence. A CTA made
  from a sheet with its players, and a party column on slots, are
  deferred.
- **The comp is saved through the comps module's helper** under its
  rules (the name, the content, the size, the slot bounds); the import
  module writes no template of its own. The comps dialog opens the
  import through a DOM event with the guild and gets the comp back the
  same way.
- **The export is the shared kit**: CSV text (RFC 4180, CRLF, a
  byte-order mark for Excel), a file name from a title, a download. A
  comp exports as CSV (what the import reads back exactly) and as lines
  for a Discord post; the history exports the players and the completed
  CTAs as CSV. The same measures as the tables; nothing new is
  computed.
- **Deferred**: a CTA with its players from a sheet, a party column on
  slots, gear names remembered per guild, spell columns and a build
  written in one cell, a live link to a Google Sheet (phase 12).

## Phase 11 decisions

- **The sheet's read is the planner's engine on its own instance.** The
  roster module makes one `CompEngine` over `DATASET` (the code the
  parity gate runs, the data the planner embeds) and never reads the
  planner's instance, roster, kits or address bar. The inputs are what
  a share link carries: the CTA's content and style and the weapon
  keys of its slots. The account layer still reads no planner state;
  this is the one account surface that calls the engine, and it is
  display only.
- **The held roster is judged at its number.** A held slot counts its
  weapon, or its claimant's first declared weapon when the slot names
  none; a free slot never counts. Coverage is fitness over its ceiling
  at the held size (the planner's own judgment), the next pick is
  asked one body ahead (the planner's one-ahead rule), the plan's
  coverage stands beside it when the plan is bigger than what is held.
  The needs are the planner's gap cut and its needed marks (a hard
  floor unmet, a heavy capability under half); the replacements are
  the swap review's redundant, off-comp or off-style seats with their
  better options; overstack is what sits past its soft cap; the
  duplicate checks are the engine's.
- **People are shown beside the needs, never scored.** For every next
  pick and open slot the read names who can bring the weapon: the
  reserves who declared it, the guild's members not on the sheet who
  list it (main, then can also play), then reserves who can swap.
  Members come through the guild module's helpers for a member of the
  CTA's guild, matched to the sheet by character name whatever its
  case; a guest sees the engine's read without them. Nothing about a
  player reaches the engine: the parties it is handed are weapon keys
  alone, pinned on a stub engine. Attendance and preference entering
  capability scoring would be a logged decision, and none is made.
- **The read rides the sheet's own event.** The sign-up module hands
  its roster over as a `sheet-read` DOM event after every render (the
  live sheet included) and clears it on close; the roster module
  paints into the sheet's `rr-*` elements, which the sign-up module
  never touches. Capability words are the planner's tables, read at
  call time.
- **Deferred**: the role advisory, kill pressure and the fight chain on
  the sheet; the read on a draft CTA or a saved comp (both open in the
  planner); a caller's own kit picks on the sheet's slots.

## Open questions

- **Guest identity** is decided (phase 5 decisions: a name and a claim
  token). Open: how a guest's history joins an account made on another
  browser (a Discord login, phase 12, is the candidate).
- **Supabase Auth settings**: leaked-password protection is off (security
  advisor).
