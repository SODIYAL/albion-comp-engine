# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

Comp Forge — an Albion Online party-composition engine (a capability model, not a
role checklist) with a single-file web planner on GitHub Pages (`docs/`). Live at
<https://sodiyal.github.io/albion-comp-engine/>.

Read before substantive work:

- `HANDOFF.md` — current state, the engine model, forge/loadout rules
- `BACKLOG.md` — the one list of open work; no other file keeps its own
- `MASTERSHEET.md` — the expert's control panel: `tune:` blocks that OVERRIDE
  scoring/mechanics/templates/sheets at build time, rulings in force only
- `pipeline/sheets/README.md` — the 1–7 curation rubric
- `tests/VALIDATION.md` — the ruling index: standing rules, one line per owner
  ruling with its pin and archive location, open questions. Full dated log in
  `notes/validation/` (append-only)
- `pipeline/README.md` — the data pipeline, patch workflow, effect layer
- `roles-design.md` + `pipeline/roles.yaml` — the role layer
- `albion-comp-engine-design.md`, `MECHANICS_TODO.md` — design history, the mechanics Q ledger
- `notes/` — plans, specs, findings (internal, not served)

## Environment traps (Windows)

- Use `py -3`, never `python`/`python3` (Store stubs). Redirected Python stdout is
  block-buffered — run background samplers with `py -3 -u`.
- Commit messages go via `git commit -F <file>`; write the file BOM-less with
  `[System.IO.File]::WriteAllText($p,$msg,(New-Object System.Text.UTF8Encoding $false))`.
  PowerShell 5.1 mangles quoted here-strings and `Set-Content -Encoding utf8`
  prepends a BOM into the subject.
- Never pipe a build through `grep`/`tail`/`Select-Object` in the pipeline you
  read `$LASTEXITCODE` from — it masks the exit code, and `build_dataset.py`
  fails closed (exit 2). Run bare or redirect to a file.
- Every writer of a committed artifact opens with `newline="\n"`, or Windows
  rebuilds churn the tree with CRLF and invalidate recorded hashes.
- `wiki.albiononline.com` and the forum 403 scripts. Use the Playwright MCP
  (`browser_navigate` + `innerText`); the dumps carry the same numbers anyway.
- Killboard: `api.albionbb.com` for DISCOVERY (only source with `minPlayers`;
  fight size comes from its battle list). The official gameinfo API for DETAIL
  (`GroupMembers` = the killer's party with gear; albionbb strips it). The old
  "official events endpoint 504s" note is stale — re-tested fine 2026-08-29.
- `render.albiononline.com` serves every weapon except `2H_IRONGAUNTLETS_HELL`
  (404 at every tier) — retry with backoff, don't delete on first failure.
- Playwright MCP: `file://` is blocked — serve with
  `py -3 -m http.server --directory dashboard`; hash-only URL changes do not
  reload; screenshots go in `.playwright-mcp/` (gitignored).
- `engine/app_scoring.js` reads as BINARY to grep/ripgrep (a literal NUL byte is
  a cache-key separator) — search with `Select-String`, read with the Read tool.
- Port 53321 may be held by the RUNNING companion — check `localhost:53321/status`
  before binding a mock.
- `tests/test_cohort_families.py` decodes a child process as UTF-8; under a
  Git-Bash console the child emits cp1252 and it dies with `UnicodeDecodeError`.
  Run it from PowerShell before suspecting the artifact.

## Tests

Script-style, **not pytest** — each runs at import and calls `sys.exit`; run
directly, exit 0 = pass. Don't trust pass counts in docs; read the output. CI
(`.github/workflows/gates.yml`) runs this list plus the build chain on every push.

```text
py -3 tests/test_golden.py          # recommendation golden cases (add one when an expert overrules the engine)
py -3 tests/test_forge.py           # forge/constraint contracts, pick-score invariant
py -3 tests/test_builds.py          # evidence-layer rules (provenance, quarantine, source gates)
py -3 tests/test_interactions.py    # duplicate/reflect/cleanse semantics + JS parity on those
py -3 tests/test_provenance.py      # pinned-snapshot hash chain, byte-identical rebuilds, LF checks
py -3 tests/test_patch_history.py   # dumps-diff staleness detection
py -3 tests/test_js_parity.py       # Python <-> browser scoring, 60 random parties at 1e-9 + embed check
py -3 tests/test_dashboard_layout.py # generated-page layout contracts + no engine calls from the UI
py -3 tests/test_cohort_families.py # observed-family artifact contracts
py -3 tests/test_roles.py           # role book, kit doctrine, advisory (descriptive)
py -3 tests/test_validation_modes.py # dressed-validation contracts, set_dressing, gear join
py -3 pipeline/evidence_lint.py     # every nonzero score cites an equippable, grounding spell
node tests/test_loadout_codec.js    # share-URL codec round-trips
node tests/test_display_math.js     # killboard bucket / cohort / family display math
node tests/test_live_party.js       # companion equipment -> loadout gear keys
py -3 tests/tier2_blindtest.py v4   # GATE: actual_gear role-level >= 70% on published comps minus one member
```

Report-only beside the gate: `py -3 tests/tier2_blindtest.py v4h --rebuild 5` —
the same leave-one-out over ~700 harvested killer parties (holdout slice
`battle id % 5 == 0`), plus a rebuild-the-last-5 recall. Never a gate until
`derive_style_bands.py` honours the same holdout split.

Expert-round tooling (human in the loop, not gates): `tests/tier2_blindtest.py
generate|score` (V3 forms; `score --mode d` is the gate),
`pipeline/audit_style_rosters.py --blind-sizes LO HI --blind-round N`,
`pipeline/kit_blind_round.py`. Report-only audits: `pipeline/audit_*.py`. Findings
and open rulings: `notes/findings/`. The `BION_DATASET` env override on `engine.py`
is plumbing for `pipeline/compare_fold.py` only — never set it normally.

## Build chain

```text
py -3 pipeline/evidence_lint.py
py -3 pipeline/build_interactions.py    # interactions.yaml -> out/interactions.json
py -3 pipeline/build_builds.py          # data/ evidence -> out/builds_index.json
py -3 pipeline/build_dataset.py         # single source of truth: out/dataset-latest.json (fails closed)
py -3 pipeline/build_cohort_families.py # display-only observed cores (after build_dataset)
py -3 dashboard/build.py                # regenerates dashboard/index.html + docs/
```

- After editing `MASTERSHEET.md`: rebuild dataset + dashboard, run golden + parity.
- After a harvest: `pipeline/fold_harvest.ps1` (re-derives rosters, runs
  `sample_parties --pages 0` -> `audit_style_rosters` -> `derive_style_bands` ->
  `derive_party_styles` -> `derive_meta_prior` -> `derive_role_counts` ->
  `build_dataset` -> every gate ->
  `compare_fold.py`; never commits). Weekly, Tuesdays.
- After moving the game-data snapshot (`data/source_pins.yaml`): `pipeline/README.md`.
- Network steps are explicit, never part of a build: `sample_parties.py`,
  `sample_battles.py`, `sample_rosters.py`, `adapters/metabattle.py fetch`. The
  scheduled task "CompForge overnight harvest" runs `harvest_overnight.ps1` at
  03:00 and 15:00 — harvest only; rebuild, gates and commit stay in-session.
- `pipeline/curate_helper.py <WEAPON>` prints the evidence worksheet for curation.

## Architecture

Three applications with explicit boundaries (each directory's README is its contract):

- **Engine** — `engine/engine.py` (canonical) and `engine/app_scoring.js` (browser
  port). Change one, change both, rerun parity. Input: `pipeline/out/dataset-latest.json`
  only. Output: the `CompEngine` API.
- **Frontend** — `dashboard/`: `build.py` bundles the `_`-prefixed sources plus the
  dataset and engine JS into `dashboard/index.html` and `docs/`. Display only: it
  calls the embedded engine and translates; it never computes a score. **Never
  hand-edit generated pages.**
- **Companion** — `companion/` (C# photon sniffer), talks to the page over
  `localhost:53321` only; zero build-time coupling.

One-way, provenance-checked data flow:

1. `data/source_pins.yaml` pins one `ao-bin-dumps` commit; any hash drift blocks the release.
2. `parse_dumps.py` -> `out/weapon_lines.json`, `out/spell_index.json` (spell facts:
   function flags, direction, area, `channel`, `caster_moves`). The effect layer
   (`effect_map.yaml`, `effect_catalogue.py`) proposes capabilities — candidates for
   curation, never assertions. It indexes weapon spells AND gear actives/passives.
3. Curation: capability sheets scored 1–7 (2 points = one supply unit), every
   nonzero score citing an evidence spell the lint can ground. Shared Q/W pools in
   `sheets/pools/`, each weapon's E on its own sheet, gear in `sheets/gear/`.
4. Templates: six content templates + `styles.yaml` (five playstyles with weight
   multipliers, delivery mechanics, a fight chain) + `composition.yaml` +
   `mechanics.yaml`. Numbers are comp-fitted from real comps. `style_bands.yaml`
   and `out/meta_prior.json` are GENERATED from the harvest — never hand-edit.
5. Derived weapon facts stamped at build: `resil_pen`, `cost_tier`, `heal_scale`,
   `full_healer`, `style_fit` (delivery / damage scale / fits per style x band, from
   the E's own payload). Owner rulings override via `style_overrides.yaml`, cited.
6. `build_dataset.py` compiles everything plus MASTERSHEET rulings into
   `out/dataset-latest.json`, byte-identically.
7. Scoring: recommendation = exact marginal comp-score delta (0.55 capability +
   0.20 synergy + 0.15 meta prior), evaluated one player ahead, each candidate on
   its best legal spell combo, DRESSED in its doctrine kit. Beside scoring sit the
   descriptive analyzers (`comp_identity`, `kill_pressure`, `fight_chain`,
   `pick_report`, `analyze`, the role layer) — parity-carried, never a scoring input.
8. Suggestion pools go through `suggest_pool()`: viability exclusions, the style
   gate, the generation-fit gate. They bar POOLS only; manual picks always score.
9. Kits: `kit_options` is doctrine-led and fail-closed — every slot serves what
   harvested winners wear (`_seat_kit` picks the band and style cell); where
   evidence runs out it proposes nothing.

The full model, with each rule's owner ruling: `HANDOFF.md` "The engine today"
and "Forge and loadouts"; `tests/VALIDATION.md` for the why.

## Load-bearing invariants

Rules a change must not break. The ruling behind each is in `tests/VALIDATION.md`.

- **Three layers, never merged**: engine truth / display explanation / observed
  evidence. The UI never computes a score; killboard prevalence, cohort families
  and reference builds never feed scoring. Popularity is not effectiveness.
- **Anti-circularity**: comps that calibrated a template never drive retuning
  against their own gate results. Gate findings are hypotheses for the owner.
- **Never invent a number**: a template row exists only where real comps supply
  the measurement; an ungroundable claim is dropped, not overridden in.
- **No rules on individual weapons**: rulings land as derivations from the E's
  facts (E-first / unique-ability-first); `style_overrides.yaml` corrects cited
  facts, never taste.
- **Descriptive layers never score**: identity, kill pressure, fight chain, roles,
  the killboard surfaces. The one sanctioned influence is the suggestion gate.
- **Judged at roster size**: the roster scores at its actual size; `PLANNED`
  steers forge fill and warnings only. Killboard display buckets key off the plan.
- **One spell per slot**: supply comes from resolved combos, never a kit's union.
- **Structural floors are source-aware**: hard floors read weapon+loadout supply
  only (weapon units); worn gear never buys floor relief. Synergy is
  weapon-interaction synergy, never gear.
- **One unit, everywhere**: targets and soft caps speak person units; a unit
  conversion can only raise a target; any re-fit moves every row at once.
- **Unknowns stay explicit**: `unknown` is stored, never inferred; quarantined
  records never become defaults; only verified interaction records score.
- **Duplicates**: 1 copy by default; the only super-additive duplicate is
  `self_cost_offset_min_copies` (it cancels a cost, never adds supply).
- **One role read**: `role_class`, the comp board column, tile colour and roster
  order all derive from the weapon's primary seat. Never a second classification.
- **Roster mutations** go through the central handlers (`data-add`, `data-swapat`).
- **Kits are what winners wear**: the voter is the player, the evidence unit is
  the killer party of 10+, thin evidence is absent — never filled.
- **Fail closed, loudly**: provenance, lint and MASTERSHEET parsing block the
  build on errors. Preserve that in anything you add.
- **Validation is a blind round**: collect the owner's call BEFORE revealing the
  engine's; every disagreement becomes a same-day ruling, override or golden pin,
  logged in `notes/validation/` with an index row in `tests/VALIDATION.md`.
