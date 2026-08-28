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
- `roles-design.md` + `pipeline/roles.yaml` — the role layer (roles are member-in-comp properties selected by kit, never 1:1 weapon labels; role book memberships are evidence-cited; detection/advisory are descriptive)

## Environment traps (Windows)

- Use `py -3`, never `python`/`python3` (Microsoft Store stubs). Redirected Python stdout is block-buffered — run background samplers with `py -3 -u`.
- Commit messages MUST go via `git commit -F <file>` (PowerShell 5.1 mangles quoted here-strings into pathspec args). Write the message file BOM-less: `[System.IO.File]::WriteAllText($p,$msg,(New-Object System.Text.UTF8Encoding $false))` — `Set-Content -Encoding utf8` prepends a BOM that lands in the commit subject.
- Never pipe a build through `grep`/`tail`/`Select-Object` in the same pipeline you read `$LASTEXITCODE` from — it masks the build's exit code, and `build_dataset.py` fails closed (exit 2, `release_clean: false`) on provenance drift. Run bare, or redirect to a file.
- Every pipeline writer of a committed artifact opens with `newline="\n"` (dataset/builds JSON, dashboard pages, hashed artifacts). Keep that discipline for new writers or Windows rebuilds churn the tree with CRLF copies and invalidate recorded hashes.
- `wiki.albiononline.com` and the game forum return 403 to scripts (Cloudflare). Use the Playwright MCP (`browser_navigate` + evaluate `innerText`) for wiki pages; the dumps carry the same numbers anyway.
- Battle sampling uses `api.albionbb.com` — the official gameinfo events endpoint 504s constantly.
- The render service (`render.albiononline.com/v1/item/...`) serves every catalog weapon except `2H_IRONGAUNTLETS_HELL` (Black Hands) — 404 at every tier; retry with backoff, don't delete on first failure.
- Playwright MCP: `file://` navigation is blocked — serve with `py -3 -m http.server --directory dashboard`; hash-only URL changes do NOT reload the page; write screenshots inside `.playwright-mcp/` (gitignored).
- `engine/app_scoring.js` reads as BINARY to grep/ripgrep (a literal NUL byte serves as a cache-key separator) — search it with `Select-String`, read it with the Read tool.
- Port 53321 may be held by the RUNNING companion (the user leaves it up) — check `localhost:53321/status` before binding a mock there.

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
node tests/test_display_math.js   # killboard bucket + cohort-affinity/neighbour/family math (display layer)
py -3 tests/test_cohort_families.py # observed-family artifact contracts (determinism, disjointness, no id leaks)
py -3 tests/test_roles.py         # role-book contracts, kit-aware detection, advisory flags (descriptive)
py -3 tests/tier2_blindtest.py v4 # leave-one-out vs published comps (role-level gate: 70%)
```

## Build chain

```text
py -3 pipeline/evidence_lint.py      # CI gate: every nonzero score cites an equippable, grounding spell
py -3 pipeline/build_interactions.py # interactions.yaml -> out/interactions.json
py -3 pipeline/build_builds.py       # data/ evidence -> out/builds_index.json (+ validation/quarantine)
py -3 pipeline/build_dataset.py      # single source of truth: out/dataset-latest.json (fails closed)
py -3 pipeline/build_cohort_families.py # cohort sample -> out/cohort_families.json (display-only observed cores; after build_dataset)
py -3 dashboard/build.py             # regenerates dashboard/index.html + docs/ (GitHub Pages)
```

After editing `MASTERSHEET.md`: rebuild dataset + dashboard, then run golden + parity. After moving the game-data snapshot (`data/source_pins.yaml`): follow `pipeline/README.md` (fetch_snapshot → parse_dumps → fetch_item_stats → fetch_gear_lines → builds → dataset → full gate list), and re-check every `pipeline/effect_overrides.yaml` entry against the fresh dumps. `pipeline/sample_battles.py` (usage/cohort refresh), `pipeline/sample_rosters.py` (near-complete fight-roster mixes behind the need profiles; `--pages 0` re-analyzes offline) and `pipeline/adapters/metabattle.py fetch` are the only network steps outside snapshot fetch — all explicit, never part of a normal build. `pipeline/curate_helper.py <WEAPON>` prints the evidence worksheet for curation.

## Architecture

Three applications with explicit boundaries (each directory's README states its contract):

- **The engine** — `engine/` (both scoring ports) + `pipeline/` (its data layer). Interface out: the `CompEngine` API. Interface in: `pipeline/out/dataset-latest.json`, its only input.
- **The frontend** — `dashboard/` (sources + `build.py` bundler, generated pages, `docs/` copies). Display only: it calls the embedded `CompEngine` and translates; it never computes a score. If the UI needs a number the engine doesn't expose, extend the engine (both ports + parity), don't recompute it in the UI.
- **The companion** — `companion/` (C# .NET photon sniffer). Talks to the page only over `localhost:53321`; zero build-time coupling.

One-way data flow, provenance-checked end to end:

1. **Pinned snapshot** — `data/source_pins.yaml` pins one `ao-data/ao-bin-dumps` commit; `out/source_manifest.json` records SHA-256 per input. Any hash drift, mixed commits, or stale adapter blocks the release.
2. **Parsed game data** — `parse_dumps.py` → `out/weapon_lines.json` (full Q/W/E/passive pools), `out/spell_index.json` (function flags, direction, area geometry). The effect layer (`effect_map.yaml`, `effect_lookup.py`) maps game effects × target direction to candidate capabilities — candidates for curation, never assertions.
3. **Curation** — capability sheets scored **1–7** (2 points = one supply unit; `score_unit: 2` in scoring.yaml — thresholds and predicates speak 1–7). Shared tree Q/W spells live once in `pipeline/sheets/pools/`; each weapon's sheet carries its E (the weapon's identity). Every nonzero score cites an evidence spell; `evidence_lint.py` verifies the spell is equippable on that weapon and can ground the claim with the right direction.
4. **Templates** — `pipeline/templates/*.yaml`: six content templates (targets, hard floors, weights, validated sizes) + `styles.yaml` — five playstyles (brawl / clap / kite / brawl_clap / clap_kite, the last owner-identified 2026-08-23) each carrying weight multipliers, delivery mechanics, AND a `chain` (the fight-stage sequence the fight-chain feature grades) + `composition.yaml` + `mechanics.yaml` (focus fire, escalation, geometry, build stats, kill_pressure lens config). Comp-fitted numbers come from real published comps (VALIDATION.md 2026-08-21 recalibration ruling).
5. **Weapon identity** — `apply_resilience_penetration` stamps `resil_pen` from the cited wiki table (`pipeline/resilience_penetration.yaml`, melee-only stat; both engine ports rebate the weapon's burst_st/execute supply by the Focus-Fire physics it ignores — F20); `derive_economics` stamps `cost_tier` (name-suffix ladder; only crystal gates), `heal_scale` and `full_healer` (E heal magnitude × the spell's own area facts; `heal_overrides.yaml` = cited sub-effect fact corrections; audit in `out/economics_report.json`); `derive_style_fit` in `build_dataset.py` stamps every weapon with `style_fit` (delivery melee/flex/ranged from the E's own reach — "the E is the weapon's identity"; group-vs-single damage scale from the E's area footprint; utility-carrier flag; fits/situational/unfit per style × size band trio/gang/group). Owner rulings override via `pipeline/style_overrides.yaml` (cited, validated, release-blocking on errors); the full derivation is auditable in `out/style_fit_report.json` with a MetaBattle cross-check review queue.
6. **Dataset** — `build_dataset.py` compiles all of the above plus MASTERSHEET rulings into `out/dataset-latest.json`, byte-identically reproducible.
7. **Twin engines** — `engine/engine.py` is canonical; `engine/app_scoring.js` is its browser port. Change one, change both, rerun parity. Recommendation score = exact marginal comp-score delta (0.55 capability + 0.20 synergy + 0.15 meta prior ± viability/duplicates), evaluated **one player ahead** (roster+1), each candidate on its best single legal Q/W/E/passive combo. Beside scoring, both ports carry the DESCRIPTIVE analyzer family — `comp_identity` (bottom-up playstyle label + per-member fit verdicts + bomb-squad archetype), `kill_pressure` (pierce/heal-cut/burst lights), `fight_chain` (stage-graded sequence + which stage a pick strengthens, with per-stage spell `sources` and named improves `terms`), `pick_report` (signed decomposition of the exact pick marginal — negative/redundant verdicts, 2026-08-24; its terms reconstruct the score at 1e-9), `analyze` (now with per-cap saturation bands), `duplicate_conflicts`, and the ROLE LAYER (2026-08-25, roles-design.md + pipeline/roles.yaml): `detect_role`/`role_advisory` read each member's played seat + riding functions + carried gear effects from weapon menus (E-primary / Q-W-secondary, derived) and the worn kit, and flag off-role kits and comp balance holes ("no engage tank") — all parity-carried per case, none of them scoring inputs. `kit_options` is DOCTRINE-LED (increment 2): the chest pool hard-gates to the resolved seat's uniform, other slots rank a doctrine tier mined from the seat's observed reference builds (build-id cited; doctrine-tier-first in BOTH modes since 2026-08-27 — the observed tier bounds the suggestion, exact marginal picks within it), passive doctrine (cloth damage / leather CDR / plate CC-duration-or-CCR, dumps-resolved per piece) and the CC-duration stat feed `build_extra`'s stat channels (`cc_mult_caps` — offhand pairing as physics, never a hand list); generated kits only — manual builds always score. The DRESSED FORGE (2026-08-27, spec `docs/superpowers/specs/2026-08-27-dressed-forge-design.md`): forge/recommend evaluate every candidate as weapon + combo + doctrine kit (`kit_variants` — v0 + one divergent single-slot swap, perf-capped), priced by the exact comp_score-with-gears the page displays (fit half dressed, synergy weapon-only — comp_score's own seams); forge returns `gears`/`kits` and the page prefills them `_eng`-marked; the page passes LOADOUT gear (`GEARS_CUR`) to every scoring/suggestion call; locked members are never re-dressed; doctrine passives never enter evaluation (F22/F23 pin it; T30c re-pinned dressed). Suggestion pools funnel through `suggest_pool()`: viability exclusions, the style gate, the cost gate (crystal below 30 — `off_budget`), and the generation-fit gate (2026-08-24: default comps field damage picks whose derived verdict is "fits"; single-ally-heal-E healers never generate at 10+; 2026-08-25: non-stacking-group members — the cursed line — need a debuff-E to generate at 10+) — all bar suggestion POOLS only; manual picks always score, flagged `off_comp`/`off_style`/`off_budget` in swap review. Forge structure additionally enforces `primary_heal` foundation minima, per-style role-band overrides (styles.yaml — incl. the clap/clap_kite 7-strong ranged-AoE core at 20, owner 2026-08-26), a 1-copy generation default (dup allowances cite real comps), derived job groups (clump_core, curse_pressure — membership computed at build, never hand lists), and the owner-ruled NEED PROFILES (roles.yaml `need_profiles`, 2026-08-26): fine-seat bands (engage/stopper split, support caps) + function coverage (pierce, heal-cut) riding the forge's predicate channel — armed at 15+, scaled by size, generation-only (manual parties always score; F21 pins it).
8. **Dashboard** — `dashboard/build.py` embeds the dataset, engine JS, and the `_`-prefixed sources (`dashboard/_shell.html`, `_app.js`, `_loadout.js`, `_decision_layer.js/.css`, `_explainer.html`) into generated single-file pages: `dashboard/index.html` and the `docs/` copies. **Never hand-edit generated pages** — edit the sources and rebuild. It also inlines a parity fixture so the browser asserts against engine.py on every build.

Side layers: `data/published_comps|published_builds|armory_imports` → `build_builds.py` → reference-build evidence (quarantine rules, canonical promotion gates — display only; records may carry a validated `style:` key). `sample_battles.py` → `out/weapon_usage_v2.json` fight-size prevalence + observed organization cohorts (display only; the page embeds anonymous weapon baskets, org ids stay in the JSON). `sample_rosters.py` → `out/roster_mixes.json` near-complete killboard fight-roster mixes (wiped sides attribute whole rosters; the need-profile evidence — display/evidence only, the profiles themselves are owner-ruled constants). The page's killboard strip also renders observed effect quotas (roster chests vs the median effect carriers observed rosters field — advice only, never a score). `review/` holds generated audit boards (`build_effect_review.py`, `build_magnitude_review.py`, `build_stat_chart.py`). `companion/` is a separate C# .NET photon-sniffer feeding the live-party feature over localhost — LIVE-VERIFIED end to end (2026-08-23: shape-based auto-calibration survives patches, spells resolve to sheet evidence IDs, and the web side live-syncs the loaded comp: weapon swaps update slots, members' real Q/W picks flow into loadouts).

The validation loop that built the identity system: in-chat **blind rounds** with the owner (present cases, collect their call BEFORE revealing the engine's, log both in VALIDATION.md). Every disagreement converts into a same-day ruling, override, or golden pin — one round produced a new playstyle (clap_kite), a new archetype (bomb squad), and two systemic derivation fixes. Prefer this loop over guessing what the expert would say.

## Load-bearing invariants

- **Three layers, never merged**: engine truth (`CompEngine` scoring) / display explanation (UI translates engine output — no second hidden scoring system; `_decision_layer.js` is deliberately translation-only) / observed evidence (killboard prevalence, cohort affinity, reference builds — display-only, never a scoring input). Popularity is not effectiveness.
- **Anti-circularity** (standing rule, VALIDATION.md): comps that calibrated a template must not drive retuning against their own gate results. Findings from gate runs are hypotheses for the owner/expert, not fixes. Template retunes need the owner's ruling.
- **Judged at roster size**: the existing roster scores at actual size; `PLANNED` steers forge fill and warnings only. Do not collapse to `max(planned, roster)` scoring. Killboard *display* buckets are the opposite by design: `usageBucket()` in `_app.js` keys off `PLAN()` — the fights the comp is *for*.
- **One spell per slot**: capability supply comes from resolved combos, never the flat union of a weapon's kit; forge constraints check the selected combo, not the sheet's theoretical maximum.
- **Roster mutations** go through the central handlers (`data-add`, `data-swapat`) so loadout reset, provenance, prefill, and role re-sorting stay centralized; `sortPartyByRole()` applies one stable permutation across `party`/`PROV`/`COMBO`/`LOADOUT` — any new mutation path must preserve that.
- **Descriptive layers never score**: `comp_identity`, `kill_pressure`, `fight_chain`, `pick_report`, the role layer (`detect_role`/`role_advisory` — test_roles R5), and the killboard surfaces describe — golden T23c/T25b/T26b/T30d literally prove fitness is untouched by computing them. The one sanctioned influence is the suggestion gate (bars suggestion POOLS, never scoring — forge F6/F13 pin the contract). Identity-aware *scoring* stays parked until more blind rounds validate the labels.
- **E-first identity**: a weapon's identity is its E spell first (sheets are structured that way; `derive_style_fit` reads the E's delivery and footprint; a utility-E weapon like Harpoon is a utility carrier whose damage never anchors an identity split).
- **Unknowns stay explicit** — evidence records store `unknown`, never inferred values; quarantined records never become canonical defaults; only *verified* interaction records may affect scoring (unknown/likely never score).
- **Fail closed, loudly**: the provenance gate, evidence lint, and MASTERSHEET parsing all block the build on errors rather than skipping them. Preserve that property in anything you add.
