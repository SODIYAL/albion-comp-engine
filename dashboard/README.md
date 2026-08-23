# The Frontend

Comp Forge's planner UI: a single self-contained HTML page, generated — never
hand-edited.

- `_shell.html`, `_app.js`, `_loadout.js`, `_decision_layer.js/.css`,
  `_explainer.html` — the **sources** (the `_` prefix marks them).
- `build.py` — the bundler: inlines the dataset, the engine
  (`engine/app_scoring.js`), the sources, and a parity fixture into
  `index.html` + `how-it-works.html` here and the GitHub Pages copies in
  `docs/`. Regenerate with `py -3 dashboard/build.py`.
- `index.html`, `how-it-works.html` — **generated output**. Edit the sources
  and rebuild.

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
