# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Comp Forge — an Albion Online party-composition recommendation engine (capability model, not a role checklist) with a single-file web planner published to GitHub Pages (`docs/`). Live at <https://sodiyal.github.io/albion-comp-engine/>.

Read before substantive work:

- `HANDOFF.md` — canonical current-state document
- `MASTERSHEET.md` — the expert's control surface: its `tune:` YAML blocks are read at build time and **override** `scoring.yaml`/`mechanics.yaml`/templates/sheets. Check it first when asking "what is the engine actually using"; expert score rulings land there, not in sheets
- `pipeline/README.md` — the data pipeline, patch workflow, and effect layer
- `tests/VALIDATION.md` — validation history, standing owner rulings, and the anti-circularity rule
- `albion-comp-engine-design.md` / `MECHANICS_TODO.md` — design history and mechanics backlog
- `KILLBOARD_AFFINITY.md`, `COMPANION_SCOPE.md`, `data/README.md` — evidence-layer scope docs

## Environment traps (Windows)

- Use `py -3`, never `python`/`python3` (Microsoft Store stubs). Redirected Python stdout is block-buffered — run background samplers with `py -3 -u`.
- Commit messages MUST go via `git commit -F <file>` (PowerShell 5.1 mangles quoted here-strings into pathspec args). Write the message file BOM-less: `[System.IO.File]::WriteAllText($p,$msg,(New-Object System.Text.UTF8Encoding $false))` — `Set-Content -Encoding utf8` prepends a BOM that lands in the commit subject.
- Never pipe a build through `grep`/`tail`/`Select-Object` in the same pipeline you read `$LASTEXITCODE` from — it masks the build's exit code, and `build_dataset.py` fails closed (exit 2, `release_clean: false`) on provenance drift. Run bare, or redirect to a file.
- Every pipeline writer of a committed artifact opens with `newline="\n"` (dataset/builds JSON, dashboard pages, hashed artifacts). Keep that discipline for new writers or Windows rebuilds churn the tree with CRLF copies and invalidate recorded hashes.
- `wiki.albiononline.com` and the game forum return 403 to scripts (Cloudflare). Use the Playwright MCP (`browser_navigate` + evaluate `innerText`) for wiki pages; the dumps carry the same numbers anyway.
- Battle sampling uses `api.albionbb.com` — the official gameinfo events endpoint 504s constantly.
- The render service (`render.albiononline.com/v1/item/...`) serves every catalog weapon except `2H_IRONGAUNTLETS_HELL` (Black Hands) — 404 at every tier; retry with backoff, don't delete on first failure.
- Playwright MCP: `file://` navigation is blocked — serve with `py -3 -m http.server --directory dashboard`; hash-only URL changes do NOT reload the page; write screenshots inside `.playwright-mcp/` (gitignored).

## Tests

Script-style, **not pytest** — they run at import and call `sys.exit`, so `pytest tests/` breaks. Run each directly; exit 0 = pass. Don't trust historical pass counts in docs — read the current output.

```text
py -3 tests/test_golden.py        # recommendation golden cases (add one when an expert overrules the engine)
py -3 tests/test_forge.py         # forge/constraint contracts, pick-score invariant
py -3 tests/test_builds.py        # evidence-layer rules (provenance envelopes, quarantine, source gates)
py -3 tests/test_interactions.py  # duplicate/reflect/cleanse semantics + JS parity on those
py -3 tests/test_provenance.py    # pinned-snapshot hash chain, byte-identical rebuilds, LF checks
py -3 tests/test_patch_history.py # dumps-diff staleness detection
py -3 tests/test_js_parity.py     # Python <-> browser scoring, 60 random parties at 1e-9 + embed check
node tests/test_loadout_codec.js  # share-URL codec round-trips
node tests/test_display_math.js   # killboard bucket + cohort-affinity math (display layer)
py -3 tests/tier2_blindtest.py v4 # leave-one-out vs published comps (role-level gate: 70%)
```

## Build chain

```text
py -3 pipeline/evidence_lint.py      # CI gate: every nonzero score cites an equippable, grounding spell
py -3 pipeline/build_interactions.py # interactions.yaml -> out/interactions.json
py -3 pipeline/build_builds.py       # data/ evidence -> out/builds_index.json (+ validation/quarantine)
py -3 pipeline/build_dataset.py      # single source of truth: out/dataset-latest.json (fails closed)
py -3 dashboard/build.py             # regenerates dashboard/index.html + docs/ (GitHub Pages)
```

After editing `MASTERSHEET.md`: rebuild dataset + dashboard, then run golden + parity. After moving the game-data snapshot (`data/source_pins.yaml`): follow `pipeline/README.md` (fetch_snapshot → parse_dumps → fetch_item_stats → fetch_gear_lines → builds → dataset → full gate list), and re-check every `pipeline/effect_overrides.yaml` entry against the fresh dumps. `pipeline/sample_battles.py` (usage/cohort refresh) and `pipeline/adapters/metabattle.py fetch` are the only network steps outside snapshot fetch — both explicit, never part of a normal build. `pipeline/curate_helper.py <WEAPON>` prints the evidence worksheet for curation.

## Architecture

Three applications with explicit boundaries (each directory's README states its contract):

- **The engine** — `engine/` (both scoring ports) + `pipeline/` (its data layer). Interface out: the `CompEngine` API. Interface in: `pipeline/out/dataset-latest.json`, its only input.
- **The frontend** — `dashboard/` (sources + `build.py` bundler, generated pages, `docs/` copies). Display only: it calls the embedded `CompEngine` and translates; it never computes a score. If the UI needs a number the engine doesn't expose, extend the engine (both ports + parity), don't recompute it in the UI.
- **The companion** — `companion/` (C# .NET photon sniffer). Talks to the page only over `localhost:53321`; zero build-time coupling.

One-way data flow, provenance-checked end to end:

1. **Pinned snapshot** — `data/source_pins.yaml` pins one `ao-data/ao-bin-dumps` commit; `out/source_manifest.json` records SHA-256 per input. Any hash drift, mixed commits, or stale adapter blocks the release.
2. **Parsed game data** — `parse_dumps.py` → `out/weapon_lines.json` (full Q/W/E/passive pools), `out/spell_index.json` (function flags, direction, area geometry). The effect layer (`effect_map.yaml`, `effect_lookup.py`) maps game effects × target direction to candidate capabilities — candidates for curation, never assertions.
3. **Curation** — capability sheets scored **1–7** (2 points = one supply unit; `score_unit: 2` in scoring.yaml — thresholds and predicates speak 1–7). Shared tree Q/W spells live once in `pipeline/sheets/pools/`; each weapon's sheet carries its E (the weapon's identity). Every nonzero score cites an evidence spell; `evidence_lint.py` verifies the spell is equippable on that weapon and can ground the claim with the right direction.
4. **Templates** — `pipeline/templates/*.yaml`: six content templates (targets, hard floors, weights, validated sizes) + `styles.yaml` playstyle overlays + `composition.yaml` + `mechanics.yaml`. Comp-fitted numbers come from real published comps (see VALIDATION.md 2026-08-21 recalibration ruling).
5. **Dataset** — `build_dataset.py` compiles all of the above plus MASTERSHEET rulings into `out/dataset-latest.json`, byte-identically reproducible.
6. **Twin engines** — `engine/engine.py` is canonical; `engine/app_scoring.js` is its browser port. Change one, change both, rerun parity. Recommendation score = exact marginal comp-score delta (0.55 capability + 0.20 synergy + 0.15 meta prior ± viability/duplicates), evaluated **one player ahead** (roster+1), each candidate on its best single legal Q/W/E/passive combo.
7. **Dashboard** — `dashboard/build.py` embeds the dataset, engine JS, and the `_`-prefixed sources (`dashboard/_shell.html`, `_app.js`, `_loadout.js`, `_decision_layer.js/.css`, `_explainer.html`) into generated single-file pages: `dashboard/index.html` and the `docs/` copies. **Never hand-edit generated pages** — edit the sources and rebuild. It also inlines a parity fixture so the browser asserts against engine.py on every build.

Side layers: `data/published_comps|published_builds|armory_imports` → `build_builds.py` → reference-build evidence (quarantine rules, canonical promotion gates — display only). `sample_battles.py` → `out/weapon_usage_v2.json` fight-size prevalence + observed organization cohorts (display only; the page embeds anonymous weapon baskets, org ids stay in the JSON). `review/` holds generated audit boards (`build_effect_review.py`, `build_magnitude_review.py`, `build_stat_chart.py`). `companion/` is a separate C# .NET photon-sniffer feeding the live-party feature over localhost.

## Load-bearing invariants

- **Three layers, never merged**: engine truth (`CompEngine` scoring) / display explanation (UI translates engine output — no second hidden scoring system; `_decision_layer.js` is deliberately translation-only) / observed evidence (killboard prevalence, cohort affinity, reference builds — display-only, never a scoring input). Popularity is not effectiveness.
- **Anti-circularity** (standing rule, VALIDATION.md): comps that calibrated a template must not drive retuning against their own gate results. Findings from gate runs are hypotheses for the owner/expert, not fixes. Template retunes need the owner's ruling.
- **Judged at roster size**: the existing roster scores at actual size; `PLANNED` steers forge fill and warnings only. Do not collapse to `max(planned, roster)` scoring. Killboard *display* buckets are the opposite by design: `usageBucket()` in `_app.js` keys off `PLAN()` — the fights the comp is *for*.
- **One spell per slot**: capability supply comes from resolved combos, never the flat union of a weapon's kit; forge constraints check the selected combo, not the sheet's theoretical maximum.
- **Roster mutations** go through the central handlers (`data-add`, `data-swapat`) so loadout reset, provenance, prefill, and role re-sorting stay centralized; `sortPartyByRole()` applies one stable permutation across `party`/`PROV`/`COMBO`/`LOADOUT` — any new mutation path must preserve that.
- **Unknowns stay explicit** — evidence records store `unknown`, never inferred values; quarantined records never become canonical defaults; only *verified* interaction records may affect scoring (unknown/likely never score).
- **Fail closed, loudly**: the provenance gate, evidence lint, and MASTERSHEET parsing all block the build on errors rather than skipping them. Preserve that property in anything you add.
