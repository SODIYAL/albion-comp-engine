# Dashboard Density Redesign — Design

**Date:** 2026-09-02
**Status:** approved in chat ("ok go ahead")
**Base:** branch `dashboard-density-redesign` off `origin/main` (`12b4597`)
**Owner decisions embedded:** promote capability supply + kill pressure/roles
+ caller tools (killboard stays deep); wheel shrinks to ~520px as one column
of four; stacked edge-tab rails on BOTH viewport edges; status bar carries the
verdict plus live setup chips; layout consolidates into a new `_layout.css`
with `.pdash` generalised to `.epanel`.

## 1. Goal

Comp Forge's planner spends its first screen on two things — a 680px wheel
and a tall decision stack — while five real surfaces (capability supply,
caller tools, kill pressure, role check, forge warnings) sit below the fold or
inside a hover tooltip. The owner's reference is a health dashboard whose
density comes from having *no* below-the-fold: a persistent verdict bar, one
hero band of several visualizations, then a tight card grid.

This redesign converts the planner to that shape without changing a single
number the engine produces. It is a **display-layer change only**: no new
engine calls beyond the two already made, no arithmetic added to the UI.

## 2. The grid

`.shell`'s `max-width:1560px` cap is removed; the page runs full-bleed with
edge padding, recovering ~300px of horizontal room on a 1867px viewport.

`.main` becomes a four-column grid at >=1700px. `.wheelstage` and
`.decision-layer` already dissolve with `display:contents`, so their children
place directly onto that grid — the DOM barely moves.

| Card | Column | Row |
|---|---|---|
| `.dl-status` — radar + identity center | 1 | 1 |
| `#groups` — capability supply vs. target | 1 | 2 |
| `.ws-center` — wheel + filters + comp board foot | 2 | 1/3 (spans) |
| `.dl-pick` — need to chain to pick to gains to still-weak | 3 | 1/3 (spans) |
| `.dl-kp` + `.dl-roles` — **new cards** | 4 | 1 |
| `#warn-slot` — forge honesty reports | 4 | 2 |

Columns: `minmax(320px,.8fr) minmax(540px,1.15fr) minmax(380px,.95fr)
minmax(380px,1fr)` — approximately 340 / 540 / 400 / 420 at 1867px.

The wheel's `--wd` drops from `min(680px,100cqi)` to `min(520px,100cqi)`, so
the semicircle occupies 520x393 instead of 680x513. All wheel geometry already
derives from `--wd`, so no other wheel rule changes.

`#meta-sec` (killboard) and `.livefeed` are not part of the grid — see
sections 3 and 9.

### Breakpoints

Deliberately additive: everything below 1251px keeps today's behaviour, which
bounds the regression surface to wide viewports.

- `>=1700px` — four columns (new)
- `1400-1699px` — three columns (new). Column 4 dissolves: `.dl-kp`,
  `.dl-roles` and `#warn-slot` become one full-width row beneath the hero,
  laid out side by side within it. Columns 1-3 keep their assignments and
  their `1fr`-relative proportions.
- `1251-1399px` — today's two-column hero grid, untouched
- `<=1250px` — today's stacked stage rules, untouched

## 3. Edge panels

`.pdash` generalises into `.epanel[data-edge="left|right"]`, keeping its exact
chrome: `position:fixed`, `transform:translateX(...)` on `[data-open]`, a
vertical `writing-mode:vertical-rl` tab, backdrop blur, edge shadow. Tabs stack
inside an `.epanel-rail` per edge, so a panel costs zero layout when shut and
adding a sixth surface later is a markup line.

- **Left edge:** `setup` (content type, forge full comp, share, export, clear,
  size presets), `tools` (player pool + swap lab, today's `.dl-tools-fold`)
- **Right edge:** `party` (today's `#pdash`, behaviour unchanged),
  `live` (the companion feed, relocated from the deep boards)

**Deleted:** `.rail`, `.rail-strip`, `.rail-body`, `.rail-toggle`, `.msetup`,
`.rs-btn` / `.rs-forge`, and the entire `data-rail="min"` state machine. The
56px collapsed track disappears; `.shell`'s two-column grid collapses to a
single content region.

**Open/closed state** persists per panel in `localStorage` under
`epanel:<id>`, replacing the `data-rail` key. A saved `data-rail` value is
ignored — no migration.

Below 960px every `.epanel` becomes a full-width bottom sheet instead of a
side panel, matching how the rail used to stack.

## 4. Status bar

The masthead grows a second line:

- fitness — `76.2 / 35.6 covered`
- identity — the `identityCenter()` glyph + label + strength
- live `style` select, `size` stepper, `content` select — the existing
  `#style` / `#size-input` / `#content` controls, relocated, with their
  existing handlers
- party count `20/20`
- the parity and dataset chips, relocated from `.foot-chips`

Style and size are turned constantly; leaving them behind a tab would cost
more than the space it saves. Every value shown already renders somewhere on
the page today — nothing new is computed.

## 5. New cards: kill pressure and role check

These do not exist as cards on main. `killPressure` and `roleAdvisory` render
today only as lines inside the radar's hover tooltip (`_decision_layer.js`,
`centerTipHtml`). Promoting them means extracting those two blocks into
standalone card renderers.

- `.dl-kp` — the caller's three-light checklist: pierce / heal-cut / burst,
  each `ok` or a percentage of its bar, from
  `ENG.killPressure(party, COMBOS_CUR)`.
- `.dl-roles` — the fine-role tally, the function tally, and the balance flags
  (`no_engage_tank`, off-role chest), from `ENG.roleAdvisory(party, chests)`
  via the existing `roleAdvisory()` helper.

`centerTipHtml` keeps its lines by calling the same extracted helpers, so the
tooltip and the cards can never disagree.

**Both stay descriptive.** They are display translations of engine output and
never feed scoring — the standing invariant that `comp_identity`,
`kill_pressure`, `fight_chain`, `pick_report` and the role layer describe
rather than score is unaffected, because no scoring call site changes.

## 6. Files

**New:** `dashboard/_layout.css` — registered in `build.py` and inlined
**last** into `_shell.html`'s single `<style>` block, so it wins on source
order without needing `!important`.

Layout rules move into it from their three current homes:

- from `_shell.html`: `.shell` / `.main` grid, `.rail*`, `.wheelstage` /
  `.ws-*`, `.pdash*`, and the `@media` 960 / 1251 / 1560 layout blocks
- from `_decision_layer.css`: `.wheelstage{display:contents}`,
  `.ws-right{display:none}`, and the whole `@media (min-width:1251px)` hero
  grid that re-parents those same children

Both files keep only component chrome. One rule, one home — this is the point
of the refactor, and it retires the `!important` specificity war documented in
`_decision_layer.css`'s own comments.

**Changed:**

- `dashboard/_shell.html` — masthead markup (status bar), rail markup replaced
  by the two `.epanel-rail`s, `#pdash` re-marked as an `.epanel`
- `dashboard/_decision_layer.js` — extract the kill-pressure and role blocks
  out of `centerTipHtml` into `killPressureCard()` / `roleCard()`; render both
  into the new column
- `dashboard/_app.js` — `data-rail` state machine replaced by generic
  `.epanel` open/close + persistence; status-bar chip wiring; `.livefeed` and
  `.dl-tools-fold` render into their panels
- `dashboard/build.py` — read and inline `_layout.css`

**Generated, never hand-edited:** `dashboard/index.html`,
`dashboard/how-it-works.html`, `docs/index.html`, `docs/how-it-works.html`.
Regenerate with `py -3 dashboard/build.py`.

## 7. Invariants held

- **Display only.** No capability numbers and no scoring math enter
  `dashboard/`. The only engine calls added are `ENG.killPressure` and
  `ENG.roleAdvisory`, both already called on this page.
- **Three layers never merged.** Engine truth / display explanation / observed
  evidence stay separate; the killboard strip remains evidence display and is
  not promoted.
- **Descriptive layers never score.** Rendering kill pressure and roles as
  cards changes no scoring call site.
- **Roster mutations stay centralised.** `data-add` / `data-swapat` and
  `sortPartyByRole()` are untouched; no new mutation path is introduced.
- **Judged at roster size.** No change to `PLAN()` / `usageBucket()`
  semantics; the killboard bucket still keys off planned size.
- **LF newlines.** Any new writer in `build.py` opens with `newline="\n"`.

## 8. Verification

- `py -3 dashboard/build.py` — the build embeds a parity fixture, so a clean
  build asserts the browser scoring still matches `engine.py`
- `py -3 tests/test_js_parity.py` — Python/browser parity at 1e-9
- `node tests/test_display_math.js` — killboard bucket + cohort math
- `node tests/test_loadout_codec.js` — share-URL codec round-trips
- Playwright MCP against `py -3 -m http.server --directory dashboard`, at
  1867 / 1500 / 1300 / 900 px wide, confirming: four columns, three columns,
  the untouched 1251-1399 hero grid, and the mobile stack with bottom-sheet
  panels

Layout work cannot change engine output; the parity and display-math gates are
there to prove exactly that.

## 9. Out of scope

- Promoting the killboard strip (`#meta-sec` stays a full-width deep board
  below the grid, unchanged)
- Any change to scoring, forge structure, need profiles, or the role book
- Identity-aware scoring (parked pending more blind rounds)
- `how-it-works.html` / `_explainer.html` restyling
