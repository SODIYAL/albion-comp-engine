# The Frontend

Comp Zaddy's planner UI: a single self-contained HTML page, generated — never
hand-edited.

- `_shell.html`, `_layout.css`, `_app.js`, `_loadout.js`,
  `_decision_layer.js/.css`, `_supabase.js`, `_auth.js/.css`, `_profile.js`,
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

- **The comp-status card IS the radar.** One axis per capability GROUP (the
  `GROUPS` map, "Other" guard included), the `comp_identity` glyph in the
  hollow centre, and *every* piece of prose in a hover popup — the card
  carries no explainer text and no fitness number of its own. Axis hovers
  give the per-capability breakdown; the centre hover gives triage, exact
  fitness, kill-pressure lights, role tally and advisory flags.
- **The ceiling ruler.** The radar and the capability board both measure
  against the comp-fitted **soft cap**, not the target: 100% means "the most
  any good comp fields", per-capability supply counts only up to its own
  ceiling (so nothing can read above 100), stacking past it shows as the
  purple over-stack marker rather than a bigger number, and a brass tick
  marks the target minimum. Floor state reads `supplyFloor` (the
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
  play), the lists saved through `set_my_weapons` in one transaction.
- **`ACCOUNT_CATALOG`** (built by `build.py` beside `_profile.js`): every
  weapon line's display name, role class and render item. The role is the
  engine's `role_class`, stamped at build — the account layer never calls
  the engine, and `test_dashboard_layout.py` L28 pins the stamp against it.
- **Isolated from the planner.** The Supabase library, `_supabase.js`,
  `_auth.js` and `_profile.js` load after the planner, each in its own
  `<script>`: a blocked or slow CDN never holds the first paint, and a throw
  there stops only itself. The account layer reads and writes no planner
  state and never scores; the planner never calls it.
- **Email links.** A verification link returns with the session in the hash
  (`#access_token=…`). The planner's boot rewrites the hash with the saved
  comp, so a `<head>` script sets the return aside first (`AUTH_LINK`) and
  strips the tokens from the address bar; `_auth.js` adopts it. The link
  returns to the page that signed up only when that address is on the
  Supabase project's Redirect URLs list; otherwise it goes to the Site URL.
- The session persists in `localStorage` (supabase-js); `onAuthStateChange`
  keeps the button in step with other tabs.

`tests/test_auth_ui.js` and `tests/test_profile.js` pin validation, error
wording, the name fallback, link parsing, the weapon lists and search, and
what the helpers send; `test_dashboard_layout.py` L27–L28 pin the markup,
the isolation, the boundary and the catalog.

To view locally: `py -3 -m http.server --directory dashboard` (the page also
works from `file://`, but automated browsers block it).
