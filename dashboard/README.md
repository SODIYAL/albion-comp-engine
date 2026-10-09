# The Frontend

Comp Zaddy's planner UI: a single self-contained HTML page, generated — never
hand-edited.

- `_shell.html`, `_layout.css`, `_app.js`, `_loadout.js`,
  `_decision_layer.js/.css`, `_supabase.js`, `_auth.js/.css`, `_profile.js`,
  `_guild.js`, `_comps.js`, `_events.js`, `_signup.js`, `_history.js`,
  `_explainer.html` — the **sources** (the `_` prefix marks them).
- `build.py` — the bundler: inlines the dataset, the engine
  (`engine/app_scoring.js`), the sources, and a parity fixture into
  `index.html` + `how-it-works.html` here and the GitHub Pages copies in
  `docs/`. Regenerate with `py -3 dashboard/build.py`.
- `index.html`, `how-it-works.html` — **generated output**. Edit the sources
  and rebuild.

## One home per layout rule

`_layout.css` owns the `.shell`/`.main` grid, the wheel stage, the `.epanel`
edge-panel system and **every** layout `@media` block. It is inlined LAST
into `_shell.html`'s single `<style>`, so its rules win on source order and
never need `!important`. `_shell.html` and `_decision_layer.css` keep
component chrome only — colour, type, borders, motion.

The layout is a four-column card grid at ≥1700px, three columns from 1400px
(the band a 1080p screen at 120% zoom lands in, so it is built as a
first-class layout, not a fallback), and the pre-redesign flow below 1251px
(the new column wrappers keep their card gap there too). Band boundaries use
fractional bounds (`max-width:1399.98px`) — display scaling yields viewport
widths like 1399.5px, and an integer bound left an open interval matching NO
band, collapsing the page to one column. Setup, caller tools, party and live
party are `.epanel` flyouts pinned to the viewport edges: a shut panel costs
zero layout, so the grid always gets the full width. One panel opens per
edge — per *phone* they collapse to one panel TOTAL (every sheet shares the
bottom slot), the overlapping bottom tab bars are click-through outside
their tabs, and a transient close (the evidence drawer overlaying the party
panel) never persists over the user's saved layout choice.

`tests/test_dashboard_layout.py` pins all of this. Several of its contracts
exist because the bug they describe actually shipped — an `<svg>` clipping
its own glow, a toolbar clipping its own dropdowns, a popover destroyed by
the panel it was re-parented into. **Display geometry fails silently:** the
CSS stays valid and the JS still runs, so the only other gate is a person
looking at it.

## The display contracts

- **The masthead is one line; the comp's settings live in the setup
  panel.** The masthead carries the brand, fitness, the identity verdict,
  the links and the account. Content, playstyle, planned size (with the
  party count), the suggested sizes, the size notice, the forge actions
  (`#forge-slot`) and the build diagnostics (parity, dataset stamp) sit in
  `#setup-panel`. While the panel is shut its tab carries a dot and a
  tooltip for an open size notice (`data-note`); a link that arrives with
  the size ask raised opens the panel for that visit; an empty comp shows
  an "open setup" control; a parity mismatch shows in the masthead
  (`#parity-alarm`) whatever the panel's state.
- **The comp-status card is the identity headline over the radar.** The
  headline is `comp_identity` (glyph, name, strength; brass once strong).
  The radar has one axis per capability GROUP (the `GROUPS` map, "Other"
  guard included) and draws the coverage shape alone: no label inside it
  and no per-axis target mark. Every further piece of prose sits in a
  hover popup — the card carries no explainer text and no fitness number
  of its own. Axis hovers give the per-capability breakdown; the headline
  hover gives triage, exact fitness, kill-pressure lights, role tally and
  advisory flags.
- **The ceiling ruler.** The radar and the capability board both measure
  against the comp-fitted **soft cap**, not the target: 100% means "the most
  any good comp fields", per-capability supply counts only up to its own
  ceiling (so nothing can read above 100), stacking past it shows as the
  purple over-stack marker rather than a bigger number. The capability
  board's rings mark the typical winner and the bare minimum with ticks
  (keyed above the board); the radar marks neither. Floor state reads `supplyFloor` (the
  weapon+loadout basis, standing rule 10), never the dressed supply.
- **The wheel is a semicircle and the comp board is the roster dock.**
  Frameless weapon art rides the top arc (the art is the star — no card
  boxes); the hub floats in the arc's mouth; drag-to-rotate derives the
  wheel centre from the box WIDTH, never its height. The board REPLACED
  the old `ws-party` strip and, since the density redesign, lives in the
  right-edge party flyout (`#pdash`, an `.epanel`), not under the wheel:
  four main-role columns of full `dm` tiles that share `memberPop()` with
  what the strip used to render, plus the open-slots column and the notes
  rail (duplicate checks + kit editor). The board is built inside
  `renderRoster` and cached in `BOARD_HTML`, so spinning the wheel never
  pays for the roster analysis.

## Boundary

- **Display only.** No capability numbers and no scoring math live in this
  directory: the UI calls the embedded `CompEngine` API and translates its
  output into caller language (`_decision_layer.js` is deliberately
  translation-only). If a feature needs a number the engine doesn't expose,
  extend the engine (both ports + parity), don't recompute it here.
- Killboard/usage/cohort surfaces are **evidence display**, never scoring
  inputs; their fight-size bucket keys off the planned size (`usageBucket()`).
- Roster mutations go through the central handlers (`data-add`,
  `data-swapat`, `data-replaceto`, `data-remove`, `applyForgeResult()`)
  so loadout reset, provenance, prefill, and role re-sorting stay in one
  place; `sortPartyByRole()` applies one permutation across
  `party`/`PROV`/`COMBO`/`LOADOUT`. Provenance is `m` / `f` / `l` (locked);
  the slot controls (`data-lock`, `data-replace`, `data-refresh`) and
  `refreshUnlocked()` never rank or score — the replace list is
  `ENG.replaceOptions()` verbatim and a refresh hands the forge the rosters
  already shown (`AVOID`) and takes what it returns.
- The companion app talks to this page only over `localhost:53321` — no
  build-time coupling.

## Accounts

Log in and create account run on Supabase Auth; a `profiles` row
(`albion_name`, `display_name`) is created per account by the project's
`handle_new_user` trigger from the sign-up metadata. The schema, its rules
and its tests: `supabase/README.md`.

- `_supabase.js` creates the one client (`window.DB`). `_auth.js` holds the
  helpers (`signUpUser`, `signInUser`, `signOutUser`, `getCurrentUser`,
  `getCurrentProfile`, …), the pure validation/wording functions, the UI kit
  every account dialog shares (`acctWireDialog`, `acctBusy`/`acctIdle`,
  `acctFlagFields`, `acctMessage`), and the account UI, which calls only the
  helpers. `_auth.css` is the chrome of every account surface; the phone
  placement rules live in `_layout.css`. The markup (the masthead button,
  the account menu, the dialogs) is in `_shell.html`.
- **`window.Account`** is the identity store feature modules use instead of
  asking Supabase again: `current()`, `subscribe(fn)` (called at once and on
  every identity or profile change), `updateProfile(row)` (a module saved
  the profile; the masthead follows), `registerView(name, open)` (the
  account menu's items, e.g. Profile).
- **Feature modules** follow `_profile.js`: their own source file and
  `<script>` after `_auth.js`; helpers (the only code touching `window.DB`),
  pure functions (node-tested), and a UI that reaches identity through
  `window.Account`. `_profile.js` edits the character (Albion name and
  server), the display name, and the player's weapon lists (main / can also
  play), the lists saved through `set_my_weapons` in one transaction. Its
  weapon combobox (`weaponCombo`: an input bound to its listbox, the
  results opening in the flow, the arrows, Enter never submitting, the
  first Escape closing the list) is the one picker the other dialogs
  share: the profile's two lists and the saved comps dialog's slots.
- **`_guild.js`** (platform phase 2) follows the same shape: helpers over
  `guilds`, `guild_members`, the `guild_join_codes` view and the
  `create_guild` / `join_guild` functions; pure functions for validation,
  the member table (admins first; each member's lists and the roles they
  cover, read through `weaponInfo` and `rolesCovered`), role coverage, what
  the caller's own role may offer (`memberPowers`: the guard's rules, never
  more) and error wording (`tests/test_guild.js`); and the guilds dialog
  the account menu opens (`registerView("guilds")`): the guild list with
  join-by-code and create, the selected guild's join code (officers and
  admins), members per role, the member table with the role controls and
  removals the caller's role allows, and the admin's rename, leave and
  delete. A write the server refused comes back as no row; the helpers
  report it (`refused`), never swallow it.
- **`_comps.js`** (platform phase 3) keeps a guild's comp templates:
  helpers over `comp_templates`, `comp_template_slots` and
  `save_comp_template`; pure functions for the planner's share hash (read
  into a template, written back as the hash the planner opens), slot
  normalization, the role summary, validation, who writes (callers,
  officers, admins) and error wording (`tests/test_comps.js`); and the
  saved comps dialog (`registerView("comps")`). Its one contact with the
  planner is the address bar: "Save the planner's comp" reads
  `location.hash` (the share link the planner already publishes, the
  loadout codec's `c=`, `n=`, `st=`, `p=`, `g=`, `f=`, `k=`) and "Open in
  planner" sets it, which the planner applies as it applies a pasted link.
  A writer sets a slot's weapon in the dialog (the profile's combobox on
  the slot's name: the search, and the open slot, which Enter never picks
  unasked), edits its role label and note, and removes it. Each slot
  carries the kit its saved link holds for it (`slotKits`: the member at
  the slot's position while the slot names that member's weapon, read
  through the codec's functions, never the planner's state), marked
  "kit". The saved hash is kept whole while its members still match the
  slots position by position, so kits and spell picks come back; once a
  slot changes, "Open in planner" and the save build the link from the
  slots (`kitHash`): the changed slot without a kit, the others in
  theirs, a removed slot taking its own along. A pick or a removal
  repaints the slots alone, the typed fields kept. `ACCOUNT_CONTENTS` and
  `ACCOUNT_STYLES` (built beside it) are the dataset's content and style
  names, the planner's own vocabulary.
- **`_events.js`** (platform phase 4) runs a guild's CTAs: helpers over
  `events`, `event_slots` and `save_event`; pure functions for the
  statuses and the moves the guard allows (draft → open → locked →
  completed, open and locked a step back; completed final), the times
  both ways (a date-time field typed in UTC, the default, or in the
  caller's own zone, each field echoing its other reading; the ISO
  instant stored; a label with the reader's local time and the UTC time
  the game runs on, and on the sheet the reader's zone named and a
  countdown to the start kept current), the
  guild's calendar split into ahead and past, an event made from a
  saved comp or the planner's hash, validation on top of the comp's
  rules (a start required, the mass time never after it), who writes
  and error wording (`tests/test_events.js`); and the CTAs dialog
  (`registerView("events")`): the guild's calendar, a new CTA with its
  roster from a saved comp, the planner's current comp or none, the
  status row with the one-step moves and the share code, the slot table
  the comps dialog uses, open in planner, replace the slots from the
  planner, save and delete. An event's roster is COPIED from the comp
  (by the database when the payload names a comp and no slots; the
  dialog shows the copy first): the module never writes a template, and
  a comp deleted later leaves the CTA whole. A completed CTA's slots are
  frozen; the payload carries none. The dialog is live while it is open:
  `watchGuildEvents` joins the guild's private Realtime channel
  (`guild:<guild id>`, a broadcast the database sends after every write
  to the guild's CTAs and their sign-ups, naming the table and the
  operation only; the service admits the guild's members alone), one
  channel for the guild shown, left for another guild and on close. A
  message settles (`GUILD_LIVE_SETTLE_MS`; messages arriving meanwhile
  ride the same read, and an action in progress holds it), then the
  dialog reads its list again and, while the form holds no unsaved edit,
  the open CTA; an edited form is kept and a change under it is said
  once, a CTA deleted elsewhere leaves the view. The live read has its
  own sequence, so it never cancels a read the caller started; a mark
  beside the list says whether the channel is live. An admin renews a
  CTA's share code beside the code (`renewShareCode`: a value written
  that the guard replaces, the guild join code's rule), after a confirm
  that says the current link stops opening the sheet at once, guests'
  included, while everyone signed up keeps their place.
- **`_signup.js`** (platform phase 5) is the sheet of a CTA, one surface
  for guests and accounts: helpers over the three guest functions
  (`event_by_code`, `sign_up`, `cancel_sign_up`; the module reaches no
  table directly, since the share code rides each statement); pure
  functions for the link (`index.html?cta=<code>`) and the code in it,
  the claim token (16 random bytes as hex, kept in `localStorage` under
  the CTA's code and under the CTA itself, so the new link of a renewed
  code finds the claim again; the old link opens nothing), the board (each slot with its claimant, the
  reserves, the free slots), validation on the database's bounds, the
  payload, a profile's lists as the first declaration, the tally (slots
  held of slots planned per role, the open slots to fill next grouped by
  role in the comp's order) and error wording (`tests/test_signup.js`);
  and the sheet page: the link's page shows the sheet in place of the
  planner (the head script sets `html[data-view="sheet"]` from the
  address before the planner draws; `_layout.css` hides the planner's
  shell, rails, panels and drawer and the masthead's planner-only parts;
  the hidden planner writes neither the address nor storage). On it: the
  roster with who holds what (every weapon with its icon; the caller's
  weapon list carries the chosen weapon's icon beside it), the role bar
  above the roster, the reserves, the player's form (a name for guests,
  the slot among the free ones or reserve, the weapons they bring
  through the profile's search, item power, can swap, a note), update
  and cancel, refresh, open in planner (a page load of the planner's
  address with the share hash), the link to copy. The link opens the
  sheet once the stored session has been read, so an account signs up
  as itself; the CTAs dialog's sheet button goes to the link (the
  address is the one handover between the modules). A guest's claim
  token never leaves the browser except inside the statement; the row
  keeps its hash, so this browser alone edits or cancels the sign-up,
  and an account signing up here later adopts it. The sheet is no
  account-menu view: a guest has no menu. The caller runs the sheet from
  the same page (phase 6): a caller, officer or admin of the CTA's
  guild (the role read through the guild module's helper) gets a move
  list beside every sign-up (the reserves, every other slot, a held one
  as a swap), a removal, a weapon list on every slot (the catalog grouped
  by role), add-a-player by name, and the status moves, until the CTA is
  completed. `callerPowers` offers what the policies allow; every action
  is a helper the policies bound (`move_signup`, `add_player`, a
  removal, a slot's weapon). The sheet is live (phase 7): `watchSheet`
  joins the CTA's Realtime channel (`cta:<code>`, a broadcast the
  database sends after every write, naming the table and the operation
  only) once the sheet is read and leaves it when the page goes; a message
  settles, then the sheet re-reads itself through `event_by_code`, the
  player's typing kept, and a move or removal of the player's own row
  is said out loud. A live mark beside the status says whether the
  channel is up; Refresh stays for when it is not. The sheet carries the
  record (phase 8): each sign-up shows its attendance mark, the counts
  line says how many are confirmed (and, once completed, attended,
  no-show and reserve), a Record list keeps the players whose claim is
  gone (a cancellation, a settled reserve), the player gets "Confirm I'm
  coming" before completion, and the caller roles get a mark list per
  record any time plus "mark everyone in a slot as attended" once the
  CTA is completed (`markPowers`; `confirm_sign_up`, `mark_attendance`,
  `mark_all_attended`). The caller's move list, removal and the
  record's mark sit on one row under each player; a link naming no
  CTA, or a CTA deleted under a live sheet, leaves the page with its
  title and the error alone.
- **`_history.js`** (platform phase 9) shows the facts over a guild's
  completed CTAs: one helper (`guild_history`, computed on read in the
  database from the attendance record, as the caller); pure functions
  for the show rate and its wording, the regular's definition
  (`REGULAR_MIN_ATTENDED`, `REGULAR_MIN_RATE`, a stated curation
  judgment), the player rows (attended first, the weapons played named
  and given roles through the catalog), the name filter, the weapons
  fielded, the completed CTAs with their fill, the totals and error
  wording (`tests/test_history.js`); and the history dialog
  (`registerView("history")`): the guild's totals, the players table
  with a search, the weapons fielded, the completed CTAs, and the
  definitions beside them. The facts cover a period (`HISTORY_WINDOWS`:
  the last 30 days, the last 90 days, all time, the default; remembered
  per browser): the dialog sends the period's start, the database reads
  every fact from the completed CTAs that started in it, so each measure
  keeps its definition, and the line under the totals, the empty state
  and an exported file's name say which period was read. A season is a
  later period. No skill rating is offered.
- **`_import.js`** (platform phase 10) reads a caller's spreadsheet as a
  saved comp: helpers over `weapon_aliases` and `save_weapon_aliases`
  (the guild's remembered names; the comp itself is saved through the
  comps module's `saveTemplate`); pure functions for the text beside a
  weapon (tiers, counts, list markers, a player after a dash, a
  bracketed word as the caller's label for the slot: "Witchwork (DPS)"
  is the Witchwork Staff with the role DPS), the
  parser (tabs, commas, semicolons, pipes, quotes, one column), how a
  name is read (`matchWeapon`: the key, the catalog name, an alias, then
  the words, a prefix, word prefixes, the initials, the key's words, a
  text inside the name, a word of the line's own E spell ("Golem": the
  catalog carries each line's E names), a close spelling; one candidate
  is likely,
  several uncertain, none an open slot), the columns (`detectColumns`:
  a header row where one names a kind, a gear header (helm, chest,
  boots, cape, off-hand, potion, food) naming its slot, the cells
  otherwise, a column mostly one slot's items naming that slot; two
  weapon columns are parties side by side), how a gear name is read
  (`matchGear`, within its column's slot of the gear catalog the page
  carries, `GEAR`: the key, the name, a city cape's short name, then
  the derivations; items of one name that differ in tier are one name,
  the tier the sheet writes picking one, else the highest; several names
  uncertain, none unread; the guild's remembered names are weapon names
  and do not apply), the rows (sections, counts, a grid's parties, each
  row's gear), the slots and their kits (`importSlots`: a weapon slot
  carries its row's pieces, a two-hander no off-hand, an open slot
  none), the names learned and error wording (`tests/test_import.js`,
  run over the dataset's own catalog and the gear catalog as build.py
  ships it); and the import dialog: the guild, the pasted cells or a
  file, the column map the caller may reset, the review table with a
  weapon list per row (the suggestions first, then the catalog by role;
  open slot; skip) and the row's kit beside it (a read piece with its
  art, a likely one marked to check, an uncertain one a list of its
  candidates that keeps no piece until one is chosen, an unread one by
  its text; the column hidden for a sheet without gear), the options
  (remember the names chosen; player names and party labels as slot
  notes), the comp's fields, and the guild's remembered names with a
  removal each. A file's bytes say what it is (`fileKind`): text is
  read as a CSV (UTF-8, UTF-16 by its mark, else Windows-1252); an Excel
  workbook (.xlsx, .xlsm) is read by the page itself, no library
  (`readWorkbook`: the zip's directory, stored and deflated parts,
  `DecompressionStream("deflate-raw")`, each checked against its size and
  CRC-32; the package's and the workbook's relationships for the
  worksheets in tab order, a hidden one marked, the one open when saved
  read first; the shared strings; the chosen sheet's cells, a merged
  range read in its top-left cell and empty in the others, as Excel
  copies a merge; a formula as its saved result; bounded by the file,
  the entries, a part, the paste's rows and characters and 64 columns,
  `tests/test_xlsx.js`), a workbook of several sheets offering them, and
  the chosen sheet's cells written into the paste box as Excel copies
  them and read on the paste's path. A workbook protected by a password,
  an Excel 97-2003 .xls, a zip that is no workbook (.xlsb, .ods), a zip64
  or another compression and a damaged file are refused with the way
  round. The import saves each slot's kit in the comp's share hash
  through the comps module's `kitHash` (the planner's codec): "Open in
  planner" shows each slot in its kit, and a CTA made from the comp
  shows each slot's build on its sheet. The comps dialog opens it by
  dispatching a `comp-import` DOM event with the guild and gets the comp
  back through `comp-imported` (no call between modules). The export
  is the shared kit (`acctCsvText`, `acctFilename`, `acctDownloadText`
  in `_auth.js`): the comps dialog exports a comp as CSV
  (`compSheetRows`, what the import reads back exactly) and copies it as
  lines for a Discord post (`compText`); the history dialog exports the
  players and the completed CTAs as CSV (`historySheetRows`).
- **`_roster.js`** (platform phase 11) is the engine's read of a CTA's
  live roster, on the sheet: the one account surface that reads the
  engine. It makes its own `CompEngine` over `DATASET` (the planner's
  engine and data, never the planner's instance, roster, kits or address
  bar) and asks it about the weapon keys of the HELD slots (the slot's
  weapon, else the claimant's first declared weapon) at their number,
  the CTA's content and style, each slot in its build: the build the
  CTA's saved link holds for it, read as the planner reads the link
  (curated pieces, the explicit combo, else the picked spells), when the
  slot still names that member's weapon, else the engine's default kit
  for the weapon (`kitVariants(w)[0]`, the doctrine kit) on its default
  spells; a hard floor reads the weapon and spell supply alone, as the
  planner's does. The read reports how many held slots read a saved
  build. Then the coverage (fitness over its ceiling),
  the biggest needs (the planner's gap cut; a hard floor unmet or a
  heavy capability under half marked needed), the next picks one body
  ahead with their verdict, the held seats a swap improves
  (`swapReview`), what sits past its soft cap and the duplicate checks,
  and the planner's three descriptive reads of the held slots in their
  builds at their number: the kill-pressure lights (`killPressure`:
  pierce, anti-heal and burst against the content's bare minimums), the
  role check (`roleAdvisory` on each seat's worn chest: the tally and
  the role book's warnings) and the fight chain (`fightChain`: the
  playstyle's stages, each graded), none of which scores;
  the plan's coverage beside it when the plan is bigger than what is
  held. The open slots of the plan are listed with the engine's rank
  for their weapon, and beside every pick and open slot who can bring
  it: the reserves who declared it, the guild's members not on the
  sheet who list it (main, then can also play), then reserves who can
  swap; members come through the guild module's helpers, for a member
  of the CTA's guild (matched to the sheet by name, whatever its case).
  None of that reaches the engine: the parties it is handed are weapon
  keys and their builds (`tests/test_roster.js` pins it on a stub engine
  and runs the read on the real one, where a forged comp's saved link
  reads the planner's fitness). The sheet hands its roster over as a
  `sheet-read` DOM event after every render and clears it on close; the
  read is painted into the sheet's `rr-*` elements, which the sign-up
  module never touches; it is computed again only when the roster's
  weapons, content or style change (a mark or a note keeps it), and
  the members' lists are forgotten when the sheet closes. Capability
  words are the planner's own tables
  (`CAP_LABEL`, `CAP_PROSE`), read at call time. Descriptive, like
  every analyzer in the planner: the engine ranks, the module
  translates; the definitions stand under the read. The saved comps
  and CTAs dialogs carry the same read of the comp or CTA they show,
  read as designed (`planBoard`: every slot naming a weapon read as
  held, a slot naming none open, no player): each dialog hands its
  slots' weapons and roles and the record's content, style and saved
  link over as a `plan-read` DOM event after every render of its slots
  (the content and style as the form holds them), and an empty one when
  none is open; the read follows one tick later, in the dialog's
  `comp-rr-*` or `ev-rr-*` elements, which the dialogs never touch, on
  the module's one engine. The dialogs' read lists no fillers: who can
  bring a weapon is the sheet's question.
- **`_build.js`** (platform phase 12) is the build on the sheet: the
  loadout the planner saved for each slot, named. A CTA's share hash
  carries the comp's weapons (`p=`) and, per member, the gear and the
  Q/W/passive picks (`g=`, the codec in `_loadout.js`); `sheetBuilds`
  reads them for every slot and names helm, armor, boots, cape,
  off-hand, potion and food with their art (`GEAR`, the render service
  with the picker's retry) and the picked spells and the weapon's E
  (`SPELLS`). A slot is the member at its position (in a link built
  from a comp's slots an open slot is an empty entry of `p=`, so every
  later slot keeps its position; `_roster.js` reads the link the same
  way); its build holds while the slot still names that member's
  weapon. A slot with no
  weapon, a changed weapon and a comp saved without loadouts each say
  so (`tests/test_sheet_build.js`). Display only: it scores nothing,
  writes nothing and reaches no table. After every `sheet-read` it
  fills the build place each slot cell leaves empty (folded until the
  slot's Build toggle opens it; the open ones survive a redraw), which
  the sign-up module never fills.
- **`ACCOUNT_CATALOG`** (built by `build.py` beside `_profile.js`): every
  weapon line's display name, role class and render item. The role is the
  engine's `role_class`, stamped at build — the account layer never calls
  the engine, and `test_dashboard_layout.py` L28 pins the stamp against it.
- **Isolated from the planner.** The Supabase library, `_supabase.js`,
  `_auth.js`, `_profile.js`, `_guild.js`, `_comps.js`, `_events.js`,
  `_signup.js`, `_history.js`, `_import.js`, `_roster.js` and `_build.js` load after the planner, each in its own
  `<script>`: a blocked or slow CDN never holds the first paint, and a throw
  there stops only itself. The account layer reads and writes no planner
  state and never scores; the planner never calls it. The one account
  surface that reads the engine is the sheet's engine read
  (`_roster.js`): its own engine instance on the roster's weapon keys,
  display only. The sheet's build read (`_build.js`) reads the
  planner's gear and spell tables and its codec, nothing of its state;
  the import reads the gear catalog (`GEAR`), the codec's slot rule
  (`loSlotOpen`) and the art retry, and the comps module calls the
  codec's functions (`loadoutEncode`, `loadoutDecode`, `provEncode`,
  `provDecode`, `comboEncode`, `comboDecode`), neither any of the
  planner's state (`test_dashboard_layout.py` L37w, `test_comps` 8).
- **Dialog conventions** (the design check in the decision log): every
  part of the account layer gives the `hidden` attribute its meaning
  whatever display its class sets (`.auth-dialog [hidden]`, the
  `.lf-sync` lesson); a comp or CTA slot is one line (icon, name, role
  tag; in the comps dialog a writer's name is the slot's combobox, read
  as text until pointed at, with the kit mark beside the tag); each
  dialog has one primary action, the side column's creators
  and the rename are secondary; the list dialogs open with focus on
  their title, the sign-in and profile dialogs on their first field; the
  sheet page groups its slots into role bands (Tanks, Supports, DPS,
  Healers, Any weapon; two slots across, one on a phone), its sign-up
  panel is the page's one brass element, pinned beside the roster, and
  every free slot's button names that slot in it; the caller's line
  under a player reads "Move to…", the mark and the removal, laid over
  the cell's corner until pointed at; the start counts down beside the
  title with an .ics to add it to a calendar; the status row copies the
  roster as text and the link and opens every build at once; once the
  CTA is completed the panel is the record (the counts, mark everyone,
  the guild's history through the account store's `open`), fill-next
  and the live mark go, a slot nobody took reads unfilled and the marks
  stay in view; a sheet that takes no sign-up keeps no column for the
  form; a numeric
  table header is aligned by class (`hs-num`), never by position; small
  text inside the dialogs uses the layer's own tertiary grey and melee
  tone, which clear 4.5:1 on its surfaces while the planner's tokens
  stand. On a phone the member and slot tables scroll sideways and a
  date field takes its row. `test_dashboard_layout.py` L39 pins them.
- **Email links.** A verification link returns with the session in the hash
  (`#access_token=…`). The planner's boot rewrites the hash with the saved
  comp, so a `<head>` script sets the return aside first (`AUTH_LINK`) and
  strips the tokens from the address bar; `_auth.js` adopts it. The link
  returns to the page that signed up only when that address is on the
  Supabase project's Redirect URLs list; otherwise it goes to the Site URL.
- The session persists in `localStorage` (supabase-js); `onAuthStateChange`
  keeps the button in step with other tabs.

`tests/test_auth_ui.js`, `tests/test_profile.js`, `tests/test_guild.js`,
`tests/test_comps.js`, `tests/test_events.js`, `tests/test_signup.js`,
`tests/test_history.js`, `tests/test_import.js`, `tests/test_xlsx.js`, `tests/test_roster.js` and `tests/test_sheet_build.js` pin validation, error wording, the name fallback,
link parsing, the weapon lists and search, the member table and role
powers, the share hash both ways and the kits it carries per slot, the
statuses and their moves, the times, the calendar, the guild's channel
and the share code's renewal, the sheet's board, link, record and
channel, the history's measures, rows and periods, the import's parser,
workbook reader, matchers, columns, slots and kits, the export's sheets,
the engine's read of a roster (what the engine is asked and handed), and
what the helpers send;
`test_dashboard_layout.py` L27–L38 pin the markup, the isolation, the
boundary, the catalog and the address-bar bridge.

To view locally: `py -3 -m http.server --directory dashboard` (the page also
works from `file://`, but automated browsers block it).
