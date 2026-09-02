# The Frontend

Comp Forge's planner UI: a single self-contained HTML page, generated — never
hand-edited.

- `_shell.html`, `_layout.css`, `_app.js`, `_loadout.js`,
  `_decision_layer.js/.css`, `_explainer.html` — the **sources** (the `_`
  prefix marks them).
- `build.py` — the bundler: inlines the dataset, the engine
  (`engine/app_scoring.js`), the sources, and a parity fixture into
  `index.html` + `how-it-works.html` here and the GitHub Pages copies in
  `docs/`. Regenerate with `py -3 dashboard/build.py`.
- `index.html`, `how-it-works.html` — **generated output**. Edit the sources
  and rebuild.

## One home per layout rule (2026-09-02)

`_layout.css` owns the `.shell`/`.main` grid, the wheel stage, the `.epanel`
edge-panel system and **every** layout `@media` block. It is inlined LAST
into `_shell.html`'s single `<style>`, so its rules win on source order and
never need `!important`. `_shell.html` and `_decision_layer.css` keep
component chrome only — colour, type, borders, motion.

The layout is a four-column card grid at ≥1700px, three columns from 1400px
(the band a 1080p screen at 120% zoom lands in, so it is built as a
first-class layout, not a fallback), and unchanged below 1251px. Setup,
caller tools, party and live party are `.epanel` flyouts pinned to the
viewport edges: a shut panel costs zero layout, so the grid always gets the
full width.

`tests/test_dashboard_layout.py` pins all of this. Several of its contracts
exist because the bug they describe actually shipped — an `<svg>` clipping
its own glow, a toolbar clipping its own dropdowns, a popover destroyed by
the panel it was re-parented into. **Display geometry fails silently:** the
CSS stays valid and the JS still runs, so the only other gate is a person
looking at it.

## The two display contracts (owner rulings 2026-08-26/27)

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
  weapon+loadout basis) per the Option C ruling, never the dressed supply.
- **The wheel is a semicircle and the comp board is the roster dock.**
  Frameless weapon art rides the top arc (the art is the star — no card
  boxes); the hub floats in the arc's mouth; drag-to-rotate derives the
  wheel centre from the box WIDTH, never its height. The board beneath it
  REPLACED the old `ws-party` strip: four main-role columns of full `dm`
  tiles that share `memberPop()` with what the strip used to render, plus
  the open-slots column and the notes rail (duplicate checks + kit editor).
  The board is built inside `renderRoster` and cached in `BOARD_HTML`, so
  spinning the wheel never pays for the roster analysis.

## Boundary

- **Display only.** No capability numbers and no scoring math live in this
  directory: the UI calls the embedded `CompEngine` API and translates its
  output into caller language (`_decision_layer.js` is deliberately
  translation-only). If a feature needs a number the engine doesn't expose,
  extend the engine (both ports + parity), don't recompute it here.
- Killboard/usage/cohort surfaces are **evidence display**, never scoring
  inputs; their fight-size bucket keys off the planned size (`usageBucket()`).
- Roster mutations go through the central handlers (`data-add`,
  `data-swapat`) so loadout reset, provenance, prefill, and role re-sorting
  stay in one place; `sortPartyByRole()` applies one permutation across
  `party`/`PROV`/`COMBO`/`LOADOUT`.
- The companion app talks to this page only over `localhost:53321` — no
  build-time coupling.

To view locally: `py -3 -m http.server --directory dashboard` (the page also
works from `file://`, but automated browsers block it).
