# Dashboard Density Redesign — implementation plan (2026-09-02)

Status: implemented 2026-09-02 (HANDOFF.md layout section;
`tests/test_dashboard_layout.py` pins the contracts; PR merged to main).
The task checkboxes were never ticked during execution; the record below
lists each task with its outcome and the contracts it added.

**Goal:** Rebuild the Comp Forge planner's first screen as a four-column card grid with edge-anchored flyout panels, so capability supply, kill pressure, role check and caller tools are visible without scrolling.

**Architecture:** All layout rules consolidate into one new source file, `dashboard/_layout.css`, inlined last so it wins on source order without `!important`. The existing right-edge party panel (`.pdash`) generalises into a reusable `.epanel[data-edge]` component; the in-flow setup rail is deleted and becomes a left-edge panel. `.main` becomes a four-column grid at >=1700px. This is a display-layer change only — no scoring, engine, forge or pipeline code is touched.

**Tech stack:** Vanilla HTML/CSS/JS single-file bundle. Python 3 bundler (`dashboard/build.py`). Script-style tests (NOT pytest) run directly with `py -3` / `node`.

**Spec:** `notes/specs/2026-09-02-dashboard-density-redesign-design.md`

## Global constraints

- **Branch:** `dashboard-density-redesign`, created off `origin/main` (`12b4597`).
- **Windows environment:** use `py -3`, never `python`/`python3`. Commit messages go via `git commit -F <file>` — PowerShell 5.1 mangles quoted here-strings into pathspec args. The message file is written BOM-less; `Set-Content -Encoding utf8` prepends a BOM that lands in the commit subject. Every commit step writes it with `io.open(..., newline="\n")`.
- **`/tmp` does not exist for Windows Python.** Git Bash maps it, `py -3` does not — `io.open('/tmp/x')` raises `FileNotFoundError`. The commit steps write to `.git/cm.txt`, which always exists and is never committed.
- **Never hand-edit generated pages.** `dashboard/index.html`, `dashboard/how-it-works.html`, `docs/index.html`, `docs/how-it-works.html` are build output. Edit the `_`-prefixed sources and run `py -3 dashboard/build.py`.
- **Display only.** No capability numbers and no scoring math may enter `dashboard/`. The only permitted engine calls are the twelve already present (pinned by the allowlist in Task 1).
- **Never pipe a build through `grep`/`tail`/`Select-Object`** in the same pipeline that reads `$LASTEXITCODE` — it masks the exit code. Run bare, or redirect to a file.
- **LF newlines.** Every writer of a committed artifact in `build.py` opens with `newline="\n"`.
- **`engine/app_scoring.js` reads as BINARY** to grep/ripgrep (embedded NUL byte). Use `Select-String` or an editor. It should not need changes.
- **Tests are script-style**, not pytest — they run at import and call `sys.exit`. Run each directly; exit 0 = pass.
- **Do not change** `#meta-sec` (killboard), scoring, forge structure, need profiles, the role book, or `_explainer.html`.

Each task follows the same shape: write the failing contract in `tests/test_dashboard_layout.py`, run it to see it fail, implement, run it to see it pass, rebuild with `py -3 dashboard/build.py` (bare), verify in a headless browser (Playwright against `py -3 -m http.server --directory dashboard 8099`; `file://` navigation is blocked, hash-only URL changes do not reload), commit via `.git/cm.txt`.

---

### Task 1: Layout contract test + `_layout.css` wired into the build — done

Establishes the test harness the rest of the plan is verified against, and the empty file every later task moves rules into.

- Files: create `tests/test_dashboard_layout.py`; create `dashboard/_layout.css`; modify `dashboard/build.py:106-110`.
- Produces: `dashboard/_layout.css`, inlined into `_shell.html`'s `<style>` block *after* `_decision_layer.css`. `tests/test_dashboard_layout.py`, a script-style test exiting 0 on pass and 1 on failure, with a `check(cond, label, detail="")` helper that later tasks add contracts to.
- Contracts: **L1** — layout source exists and is wired into the build (L1a `_layout.css` non-empty; L1b `build.py` reads it; L1c it is inlined AFTER `_decision_layer.css` — source order is what lets layout rules win without `!important`). **L2** — display-only boundary: L2a `_decision_layer.js` calls only the allowlisted engine members (`compIdentity`, `effectiveSupply`, `fightChain`, `fitness`, `killPressure`, `pickReport`, `recommend`, `roleAdvisory`, `rolesBook`, `target`, `weaknesses`, `weight`); L2b `sortPartyByRole`, `data-add`, `data-swapat` still route roster mutation; L2c exactly one `sortPartyByRole` definition.
- Steps: (1) the failing test (fails with `FileNotFoundError` on `_layout.css`). (2) create `_layout.css` with only its header comment (owns: `.shell` / `.main` grid, `.wheelstage` / `.ws-*`, the `.epanel` edge-panel system, every layout `@media` block; component chrome stays in `_shell.html` and `_decision_layer.css`). (3) in `build.py`, read `_layout.css` after `_decision_layer.js` and replace the single `</style>` with decision CSS + layout CSS (the old one-file replacement line deleted, not added to). (4) test passes; build exit 0 (the build embeds a parity fixture, so a clean build also asserts browser scoring still matches `engine.py`). (5) commit `Layout source file, wired last into the style block`.

### Task 2: Move every layout rule into `_layout.css` — done

A pure refactor: rules move verbatim, the page must look identical. Doing this before any redesign means every later task edits exactly one file.

- Files: `dashboard/_shell.html` (delete the rule blocks listed below and the `@media` layout blocks), `dashboard/_decision_layer.css` (delete lines 92-143 — `.ws-right`, `.wheelstage{display:contents}`, the whole `@media (min-width:1251px)` hero grid), `dashboard/_layout.css` (receive them), `tests/test_dashboard_layout.py` (contract L3).
- Produces: `_layout.css` containing the sole definition of `.shell`, `.main`, `.rail*`, `.rs-*`, `.msetup`, `.wheelstage`, `.ws-flank`, `.ws-center`, `.ws-right`, `.pdash*`, and all layout `@media` blocks. `_shell.html` and `_decision_layer.css` retain only component chrome.
- Contract **L3** — one home per layout rule: for each of `.shell{`, `.main{`, `.wheelstage{`, `.ws-flank{`, `.ws-center{`, `.pdash{`, `.pdash-tab{`, `.pdash-body{`: L3a defined in `_layout.css`, L3b NOT left in `_shell.html`, L3c NOT left in `_decision_layer.css`; L3d `_decision_layer.css` declares no `grid-template-columns`.
- Rule blocks cut verbatim from `_shell.html` (relative order and comments preserved):

| Lines | What |
|---|---|
| 134-138 | `.shell{...}` + its `max-width:960px` override |
| 140-178 | `.rail`, `.rail-body`, `.rail-toggle`, `.rail-strip`, `.rs-btn`, `.rs-forge`, all `.shell[data-rail="min"]` rules, and the `@media (max-width:960px)` rail block at 171-178 |
| 179 | `.main{...}` |
| 314-338 | the three `.ws-party` popover-placement `@media` blocks |
| 613-648 | `.wheelstage{...}` and its four `@media` blocks (1560 / 1251-1560 / 1250 / 960) |
| 649 | `.ws-flank{...}` |
| 665 | `.ws-center{min-width:0; container-type:inline-size}` |
| 927-950 | `.pdash`, `.pdash[data-open]`, `.pdash-tab`, `.pdash-tab b`, `.pdash-tab:hover`, `.pdash-body`, `.pdash-empty` |
| 1454 | `.msetup{display:none}` and its `@media (max-width:960px)` block at 1456 |

  Left in `_shell.html`: `.ws-fit` and its children (type/colour chrome), `.meter-track`, `.meter-fill`, `.pdash .wf-*` and `.pdash-fly*` (component chrome scoped under the panel, not layout of the panel itself). The `_decision_layer.css` hero grid is appended **after** the `_shell.html` rules so relative precedence is unchanged from the old concatenation order.
- Steps: contract fails → cut the blocks → contract passes → rebuild → screenshot at 1867x945 compared against the pre-refactor page (a pure move: the layout MUST be visually identical; any shift means a rule was dropped or reordered) → commit `Consolidate layout rules into _layout.css` (pure move, no visual change).

### Task 3: Generalise `.pdash` into a reusable `.epanel` — done

The party panel becomes the first instance of the component every later panel uses.

- Files: `dashboard/_layout.css` (rename and generalise the panel rules), `dashboard/_shell.html:1709-1716` (party panel markup) + the two edge rails, `dashboard/_app.js:2395-2399` (panel toggle) and `:788-795` (`closePdash`), `tests/test_dashboard_layout.py` (contract L4).
- Produces: CSS `.epanel[data-edge="left"|"right"][data-open="true"|"false"]`, `.epanel-rail[data-edge]`, `.epanel-tab[data-panel]`, `.epanel-body`. Markup: `<aside class="epanel" data-edge="right" data-open="false" id="pdash">` with `<div class="epanel-body" id="pdash-body">`; tabs live in `<div class="epanel-rail" data-edge="right">` as `<button class="epanel-tab" data-panel="pdash">`. JS: `setPanel(id, open)` — sets `data-open`, syncs the tab's `aria-expanded`, persists to `localStorage` under `"epanel:" + id` (try/catch for private mode); `restorePanels()` — called once at startup, reads those keys.
- Contract **L4** — the edge-panel component: L4a `.epanel{` and L4b `.epanel-tab{` defined in `_layout.css`; L4c right edge and L4d left edge styled; L4e at least one `.epanel` in the markup; L4f every panel has a tab; L4g every `.epanel` declares `data-edge`; L4h `_app.js` defines `setPanel`; L4i panel state persists under an `epanel:` key.
- Design values: the component keeps `.pdash`'s exact visual values (a rename plus a left-edge mirror, not a restyle): fixed, `width:min(430px, 92vw)`, `transform:translateX(±100%)` shut and `transform:none` open, backdrop blur, edge shadow; rails fixed at 50% of the viewport height, tabs `writing-mode:vertical-rl`; below 960px panels become bottom sheets (`max-height:76vh`, `translateY(100%)` shut) and the rails a horizontal row above them. The `#pdash-toggle` button id goes; the tab is addressed by `data-panel`. Panel-scoped chrome that stayed in `_shell.html` (`.pdash .wf-*`, `.pdash .dm-pop`) is renamed to the `.epanel` prefix; `pdash-fly` keeps its id and class (party-specific chrome, not part of the component).
- Steps: contract fails → generalise the CSS → replace the markup (both rails placed immediately before the `.drawer` markup; the left rail empty until Task 5) → replace the `#pdash-toggle` click branch with a generic `.epanel-tab` handler and `closePdash()` with `setPanel("pdash", false)` (keeping `hidePdashFly()` first) → `restorePanels()` at startup → contract passes → rebuild; verify the panel slides in from the right, member tiles render, state survives a reload, click closes → commit `Generalise the party panel into a reusable .epanel`.

### Task 4: The status bar — done

Puts the verdict and the constantly-turned knobs in the masthead, before the rail is deleted, so the selects move once.

- Files: `dashboard/_shell.html` (masthead at 1561-1575; `.ws-fit` removed from `.ws-right` at ~1690; `.foot-chips` removed), `dashboard/_layout.css` (masthead layout), `dashboard/_decision_layer.js:603` (write the identity into the bar), `dashboard/_app.js:1128-1137` (write the party count into the bar), `tests/test_dashboard_layout.py` (contract L5).
- Produces: masthead ids `sb-identity` (identity glyph + label + strength) and `sb-count` (`N/M`). `#fit-num`, `#fit-of`, `#fit-bar`, `#parity-dot`, `#parity-chip`, `#build-stamp`, `#style`, `#size-input`, `#size-minus`, `#size-plus`, `#content` all keep their existing ids and handlers — relocated, not rewritten.
- Contract **L5** — status bar: L5a the masthead carries `fit-num`, `fit-of`, `fit-bar`, `sb-identity`, `sb-count`, `style`, `size-input`, `content`, `parity-chip`, `build-stamp`; L5b-d `#fit-num`, `#style`, `#size-input` are not duplicated; L5e `.foot-chips` retired; L5f the decision layer fills `#sb-identity`; L5g `_app.js` fills `#sb-count`.
- Layout: a two-line masthead — `.mh-top` (brandmark, the moved `.ws-fit` as `.sb-fit`, `.sb-identity`, spacer, the how-it-works link and the companion connect/sync controls) and `.mh-bar` (style select, size stepper, content select, `.sb-count`, spacer, the parity and dataset chips). The rail keeps `#style-blurb`, `#size-presets`, `#size-hint`, `#size-notice`, `#forge-rail`, `#share`, `#export`, `#clear`.
- Identity: `statusRadar()` already computes `identityCenter(id)` (`_decision_layer.js:258-259`); the bar is written from that same value — no new engine call, and the bar and the radar's hollow centre can never disagree. `renderDecisionLayer()` clears the bar as its first statement because `statusRadar()` returns early on an empty comp. Count: written next to the `#pdash-count` writer in `_app.js`.
- Steps: contract fails → masthead markup → masthead layout in `_layout.css` → fill `#sb-identity` and `#sb-count` → contract passes → rebuild + `py -3 tests/test_js_parity.py`; verify the style select re-renders the radar and pick card, size `+`/`−` moves the target numbers, fitness / identity / count populate → commit `Status bar: the verdict and the knobs that are actually turned`.

### Task 5: Retire the rail; setup becomes a left-edge panel — done

- Files: `dashboard/_shell.html` (delete the whole `<aside class="rail">`, add the setup panel), `dashboard/_layout.css` (delete `.rail*`, `.rs-*`, `.msetup`, `.shell[data-rail]`; collapse `.shell` to one column), `dashboard/_app.js` (delete `setRail`, `RAIL_KEY`, the `#rail-*`/`#msetup` click branches, the `#msetup-sum` writer, the startup rail restore), `tests/test_dashboard_layout.py` (contract L6).
- Produces: `#setup-panel`, an `.epanel[data-edge="left"]` holding the remaining setup controls. `.shell` is a single content region: `.shell{display:block; max-width:none; margin:0}` — the `max-width:1560px` cap goes with it, which is the ~300px of horizontal room the redesign spends.
- Contract **L6** — the in-flow rail is gone: for each of `data-rail`, `rail-toggle`, `rail-strip`, `rail-expand`, `msetup`, `rs-btn`, `rs-forge`, `RAIL_KEY`, `setRail`: L6a absent from `_shell.html`, L6b from `_layout.css`, L6c from `_app.js`; L6d `id="setup-panel"` exists; L6e it has a tab; L6f the panel keeps `forge-rail`, `share`, `export`, `clear`, `size-presets`, `size-hint`, `style-blurb`, `size-notice`.
- Also deleted: the dead `.ws-party` rules (the party dock was retired on `origin/main`, `9c8c946`); the `#forge-rail-mini` clauses in the forge click handler (the button no longer exists), leaving the `#forge-rail` cases intact.
- Steps: contract fails → markup (setup tab in the left rail; the panel next to `#pdash`) → delete the rail rules → delete the rail state machine → contract passes → rebuild + `node tests/test_loadout_codec.js`; verify forge fills a roster, copy share link confirms, clear comp keeps its two-step arm-then-clear → commit `Retire the setup rail for a left-edge panel`.

### Task 6: Caller tools and live party become panels — done

Empties `.main` of everything that is not grid content.

- Files: `dashboard/_shell.html` (tabs + two panels; the `.livefeed` section removed from `.main`), `dashboard/_decision_layer.js:512-539` (mount the tools fold into its panel), `tests/test_dashboard_layout.py` (contract L7).
- Produces: `#tools-panel` (left edge, hosts `#dl-tools-fold` via `#tools-panel-body`) and `#live-panel` (right edge, hosts `#companion`). `.main`'s only remaining children are `.decision-layer`, `.wheelstage`, `#warn-slot`, `#groups`, `#meta-sec`, `.footnote`. `#companion-connect` and `#companion-sync` stay in the masthead.
- Contract **L7** — deep interactive surfaces live in panels: L7a/L7b the two panels exist; L7c/L7d each has a tab; L7e `.livefeed` left `.main`; L7f the killboard `#meta-sec` stays a deep board in `.main`; L7g the tools fold mounts into its panel.
- Steps: contract fails → tabs and panels (the livefeed section moved, not copied) → re-anchor the tools fold (`tools-panel-body` when present, else the old host; the stale hero-grid comment updated) → contract passes → rebuild; verify the tools panel's player pool survives a re-render and the live panel renders its connect/status UI (port 53321 may be held by the RUNNING companion — check `localhost:53321/status` before binding anything there; never kill a live companion to test) → commit `Caller tools and live party move to edge panels`.

### Task 7: The four-column grid — done

- Files: `dashboard/_layout.css` (replace the `@media (min-width:1251px)` hero grid; add the 1400 and 1700 blocks; set `--wd`), `tests/test_dashboard_layout.py` (contract L8).
- Produces: the four-column grid. Column 4 is empty until Task 8 fills it — expected and correct.
- Contract **L8** — the column grid: L8a `@media (min-width:1700px)` exists; L8b `@media (min-width:1400px) and (max-width:1699px)` exists; L8c `@media (min-width:1251px) and (max-width:1399px)` preserves the previous hero grid untouched; L8d the wheel shrinks to `min(520px, 100cqi)`; L8e no `680px` override remains.
- Grid: at >=1700px `.main` is `grid-template-columns:minmax(320px,.8fr) minmax(540px,1.15fr) minmax(380px,.95fr) minmax(380px,1fr)`, gap `18px 24px`; `.decision-layer` and `.wheelstage` dissolve with `display:contents`; placements `.dl-status` 1/1, `#groups` 1/2, `.ws-center` 2 rows 1-3, `.dl-pick` 3 rows 1-3, `.dl-kp` 4/1, `.dl-roles` 4/2, `#warn-slot` 4/3, `.dl-empty` 1 rows 1-3; `#meta-sec` and `.footnote` full-width in DOM order. At 1400-1699px three columns (`minmax(320px,.85fr) minmax(500px,1.2fr) minmax(380px,1fr)`) with `.dl-kp`, `.dl-roles`, `#warn-slot` on row 3 side by side. The original `@media (min-width:1251px)` block is pasted back narrowed to `1251-1399px`, minus its `.shell[data-rail="min"] .ws-center` line and minus its `.wheel{--wd:min(680px,100cqi)}` line (the `_shell.html` default `min(720px,100cqi)` is correct at that width).
- Verification table (forged 20-player comp, screenshots per width):

| Width | Expect |
|---|---|
| 1867 | four columns; column 4 holds only the warn slot (Task 8 fills the rest) |
| 1500 | three columns; warn slot on the full-width row under the hero |
| 1300 | the pre-existing two-column hero grid, visually unchanged from `origin/main` |
| 900 | single-column stack; panels are bottom sheets |

  The 1300px screenshot is the regression check that matters — it must match `origin/main`.
- Steps: contract fails → rewrite the grid blocks → contract passes (L8e because the only `680px` occurrence was the removed override) → rebuild and verify all four widths → commit `Four-column card grid above 1700px`.

### Task 8: Kill pressure and role check as cards — done

These rendered only as lines inside the radar's hover tooltip. Extracted so the tooltip and the cards call the same helpers and can never disagree.

- Files: `dashboard/_decision_layer.js` (extract from `centerTipHtml` at lines 173-200; render into the grid), `dashboard/_decision_layer.css` (card chrome), `tests/test_dashboard_layout.py` (contract L9).
- Produces: `killPressureModel()` returning `null` or `{pierce, heal_cut, burst}` each `{ok, have, bar, pct}`; `killPressureCard()` and `roleCard()` returning HTML strings (empty string when there is nothing to show, so an empty comp renders no card and the grid rows collapse); `killPressureLine()` and `roleLines()` returning the tooltip's existing `<div class="dlt-line">` markup. `centerTipHtml` calls the two line helpers instead of the engine directly. Both cards carry the note "descriptive — never scores".
- Contract **L9** — kill pressure and role check are cards: L9a `killPressureCard` and L9b `roleCard` defined; L9c `.dl-kp` and L9d `.dl-roles` rendered; L9e/L9f their chrome lives in `_decision_layer.css`; L9g `.dl-kp` chrome is NOT in `_layout.css` (layout placed it in Task 7; only chrome goes here); L9h `centerTipHtml` no longer calls `ENG.killPressure` directly.
- Steps: contract fails → extract the shared model and helpers, delete the two inline blocks from `centerTipHtml` → append the two cards to `renderDecisionLayer()`'s template after `.dl-pick` → card chrome in `_decision_layer.css` → contract passes → rebuild + parity; verify the lights and the role tally on the cards match the radar tooltip's values (a shared model — any disagreement is a bug in the extraction) → commit `Kill pressure and role check become cards`.

### Task 9: Full gate run and docs regeneration — done

- Files: regenerated `dashboard/index.html`, `dashboard/how-it-works.html`, `docs/index.html`, `docs/how-it-works.html`; `dashboard/README.md` (document `_layout.css`); `HANDOFF.md` (record the redesign).
- Steps: (1) regenerate every page from clean sources (`py -3 dashboard/build.py`, bare). (2) the display-layer gate list, each run directly and its output read: `py -3 tests/test_dashboard_layout.py`, `py -3 tests/test_js_parity.py`, `node tests/test_display_math.js`, `node tests/test_loadout_codec.js` — a layout change cannot legitimately move a parity or display-math result. (3) `git diff --stat` shows only the intended files; a generated page rewriting whole-file with no visible content change means a writer lost its `newline="\n"`. (4) visual verification at 1867 / 1500 / 1300 / 900 with a forged 20-player comp: four columns with no horizontal scrollbar; three columns with the pressure row beneath; the `origin/main` two-column hero grid; the single-column stack with horizontal tab rails and bottom-sheet panels; at every width all four panels (setup, tools, party, live) open, close, and persist across reload. (5) `dashboard/README.md`: `_layout.css` added to the sources list, and under **Boundary**: one home per layout rule — `_layout.css` owns the `.shell`/`.main` grid, the wheel stage, the `.epanel` edge-panel system and every layout `@media` block, inlined LAST so it wins on source order without `!important`; `_shell.html` and `_decision_layer.css` keep component chrome only; `tests/test_dashboard_layout.py` pins this. (6) `HANDOFF.md` entry: the four-column grid, the `.epanel` system replacing the rail, the status bar, the two new descriptive cards, the new gate `py -3 tests/test_dashboard_layout.py`. (7) commit `Document the layout boundary and regenerate the pages`. (8) push the branch and open a PR against `main` describing the redesign and listing the gates run; the PR is reviewed before merge.

---

## Execution notes

- **The 1300px screenshot is the regression contract.** Everything below 1251px is meant to be byte-for-byte the behaviour on `origin/main`. If it moved, a rule was dropped in Task 2 or a `[data-rail]` selector removal in Task 5 took a live rule with it.
- **`tests/test_cohort_families.py` is not in this plan's gate list** — it is unrelated to the display layer, and under a Git-Bash-spawned console it dies with a `UnicodeDecodeError` that is an environment artifact, not a contract failure.
- **If a rule cannot move cleanly**, stop and report rather than adding `!important`. The whole point of `_layout.css` is that source order makes `!important` unnecessary; reaching for it means a rule is in the wrong file.
