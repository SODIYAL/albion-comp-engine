# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Comp Forge — an Albion Online party-composition recommendation engine (capability model, not a role checklist) with a single-file web planner, published to GitHub Pages. `HANDOFF.md` is the canonical current-state document; read it before substantive work. `MASTERSHEET.md` is the expert's control surface — its `tune:` YAML blocks override `scoring.yaml`/`mechanics.yaml`/templates/sheets at build time, so check it first when asking "what is the engine actually using".

## Environment and commands

Windows. Use `py -3` (not `python3`). Commit messages must go via `git commit -F <file>` (PowerShell 5.1 mangles quoted here-strings into pathspec args); write the message file BOM-less (`Set-Content -Encoding utf8` prepends a BOM that lands in the subject).

Tests are **script-style, not pytest** — they run at import and call `sys.exit`, so `pytest tests/` breaks. Run each directly; exit code 0 = pass:

```text
py -3 tests/test_golden.py        # recommendation golden cases
py -3 tests/test_forge.py         # forge/constraint contracts
py -3 tests/test_builds.py        # evidence-layer rules
py -3 tests/test_interactions.py  # spell-interaction semantics
py -3 tests/test_provenance.py    # pinned-snapshot / hash gates
py -3 tests/test_patch_history.py
py -3 tests/test_js_parity.py     # Python <-> browser scoring, 1e-9
node tests/test_loadout_codec.js  # URL codec round-trips
```

Rebuild chain (order matters; each is deterministic against the pinned snapshot):

```text
py -3 pipeline/evidence_lint.py
py -3 pipeline/build_interactions.py
py -3 pipeline/build_builds.py
py -3 pipeline/build_dataset.py
py -3 pipeline/build_dashboard.py   # regenerates dashboard/index.html + docs/ (GitHub Pages)
```

Never pipe a build through `grep`/`tail` — it masks the exit code, and `build_dataset.py` fails closed (non-zero, `release_clean: false`) on provenance drift. Every pipeline writer of a committed artifact opens files with `newline="\n"`; keep that discipline for new writers or Windows rebuilds churn the tree with CRLF copies (the provenance hashes require LF-stable bytes).

To view the dashboard, serve it (`py -3 -m http.server --directory dashboard`) — `file://` navigation is blocked in the Playwright MCP, and hash-only URL changes do not reload the page.

## Architecture

Data flows one way, from pinned game data to a self-contained page:

1. **Pinned snapshot** — `data/source_pins.yaml` pins an `ao-data/ao-bin-dumps` commit; `pipeline/fetch_*.py` fetch it, `pipeline/parse_dumps.py` parses it. Derived artifacts in `pipeline/out/` carry SHA-256s in `source_manifest.json`; `tests/test_provenance.py` verifies the chain and the release fails closed on any mismatch.
2. **Curation** — per-weapon capability sheets in `pipeline/sheets/` (1–7 scale). Every nonzero score must cite an equippable evidence spell; `pipeline/evidence_lint.py` enforces it against the parsed game data. Content templates in `pipeline/templates/` set targets, floors, and weights. `MASTERSHEET.md` rulings override all of it at build time.
3. **Dataset** — `pipeline/build_dataset.py` compiles sheets + templates + rulings into `pipeline/out/dataset-latest.json`, byte-identically reproducible.
4. **Engine** — `engine/engine.py` is the canonical scorer; `pipeline/app_scoring.js` is its browser twin, held identical by `tests/test_js_parity.py` at 1e-9. Recommendation = exact marginal comp-score delta, evaluated one player ahead (roster+1) with each candidate's best legal spell combo.
5. **Dashboard** — `pipeline/build_dashboard.py` embeds the dataset, engine JS, and display sources (`dashboard/_shell.html`, `_app.js`, `_loadout.js`, `_decision_layer.js/.css`, `_explainer.html`) into generated single-file pages: `dashboard/index.html` (local) and `docs/index.html` (Pages). **Never hand-edit the generated pages** — edit the `_`-prefixed sources and rebuild.

## Load-bearing invariants

- **Three layers, never merged**: engine truth (`CompEngine` scoring), display explanation (UI translates engine output — no second hidden scoring system), and observed evidence (killboard prevalence/cohort affinity, reference comps — display-only, never a scoring input). Popularity is not effectiveness.
- **Anti-circularity**: comps that calibrated a template must not drive retuning against their own gate results; findings from gate runs are hypotheses for the owner/expert, not fixes (`tests/VALIDATION.md` records the standing rule and rulings).
- **Judged at roster size**: the existing roster scores at actual size; `PLANNED` only steers forge fill and warnings. Do not collapse this back to `max(planned, roster)` scoring. Killboard *display* buckets are the opposite by design: `usageBucket()` keys off `PLAN()` — the size the comp is for.
- **One spell per slot**: capability supply comes from resolved Q/W/E/passive combos, never the flat union of a weapon's kit; forge constraints check the selected combo.
- **Roster mutations** must go through the central handlers (`data-add`, `data-swapat`) and preserve `sortPartyByRole()`'s single permutation across `party`/`PROV`/`COMBO`/`LOADOUT`.
- **Unknowns stay explicit** — evidence records store `unknown`, never inferred values; quarantined records never become canonical defaults.
