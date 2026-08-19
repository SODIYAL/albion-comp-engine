# Handoff — Albion Online Composition Engine

Paste the prompt below into a new session with this repo folder connected.

---

I'm building an Albion Online dynamic party-composition recommendation engine.
Previous sessions completed the research, design, validation harness, the data
pipeline, the engine, capability sheets for **all 137 combat weapons**
(`release_clean: True`) — and the product itself: **Comp Forge**, live at
<https://sodiyal.github.io/albion-comp-engine/>. Read these files before doing
anything:

1. `albion-comp-engine-design.md` — feasibility research + system design
   (data sources verified live, capability taxonomy incl. the `anti_zone` and
   `damage_debuff` amendments, content templates, scoring algorithm,
   architecture; dated amendments track what changed since)
2. `pipeline/README.md` — the pipeline workflow, current status, patch
   procedure (including the `effect_overrides.yaml` re-check step)
3. `tests/VALIDATION.md` — the test plan: Tier 1 passed, Tier 2 is the gate,
   and the first V4 baseline (with its three findings) is recorded there
4. `engine/engine.py` + `tests/test_golden.py` — the engine (it has a CLI:
   `py -3 engine/engine.py camlann hallowfall --content blackzone_roam
   --size 10 --style clap`) and its golden regression cases (24)

## Environment (Windows)

- Use `py -3`, **not** `python`/`python3` — those hit the Microsoft Store stub.
- `pyyaml` and `Pillow` are installed. Node is available (parity tests).
  `gh` is authenticated as SODIYAL (used for the Pages config).
- **Commit messages must go through `git commit -F <file>`** — PowerShell 5.1
  mangles here-strings containing double quotes into pathspec arguments.
- The ao-bin-dumps clone is not in the repo and is only needed after a game
  patch. See `pipeline/README.md` for the correct clone command.
- Day-to-day work lands on `main` in small verified slices (gates below);
  use a branch when a change is risky or needs review before it ships,
  because pushing `main` **deploys the public site**.

## Rebuild everything

```
py -3 pipeline/evidence_lint.py        # CI gate — exit 1 blocks release
py -3 pipeline/build_builds.py         # data/ evidence layer -> out/builds_index.json + validation
py -3 pipeline/build_dataset.py        # sheets + templates + styles + composition -> out/dataset-latest.json
                                       # (verifies snapshot provenance; exit 2 = release blocked)
py -3 tests/test_golden.py             # must stay 24/24
py -3 tests/test_forge.py              # forge rework contracts: invariant, synergy rules,
                                       # redundancy, size-11 matrix, exclusions, combo-aware minima (14/14)
py -3 tests/tier2_blindtest.py v4      # role gate >= 70% (73% since the ranged rework)
                                       # (reads data/published_comps/ — the production comp files)
py -3 tests/test_js_parity.py          # browser scoring == engine.py incl. forge (needs node)
node tests/test_loadout_codec.js       # permalink codec + provenance + pick bridges
py -3 tests/test_patch_history.py      # patch-diff + staleness units, no clone needed
py -3 tests/test_provenance.py         # chapter-2 §A gates: pinned snapshot, hashes,
                                       # determinism, fail-closed release, coverage (24/24)
py -3 tests/test_builds.py             # chapter-2 §B-§F gates: ranged evidence, builds schema,
                                       # equippability, independence, 1v1 bar, semantics,
                                       # quarantine-never-canonical (46/46)
py -3 pipeline/build_interactions.py   # PvP interaction records -> out/interactions.json
py -3 tests/test_interactions.py       # interaction gates: count-once scoring, twin parity on
                                       # duplicates, analyzer, seeds, interrupt facts (27/27; needs node)
py -3 pipeline/build_dashboard.py      # -> dashboard/index.html AND docs/index.html
py -3 pipeline/build_effect_review.py  # -> review/effects.html
py -3 pipeline/build_magnitude_review.py  # -> review/magnitude.html (score-vs-dumps audit boards)
py -3 pipeline/fetch_icons.py          # only after a patch ADDS weapons (cached; --force redownloads)
py -3 pipeline/sample_battles.py       # optional: refresh FIGHT-SIZE equipment prevalence
                                       # (albionbb API; per-battle cache; display-only data)
```

Game-patch procedure (chapter 2): update `data/source_pins.yaml` to the new
ao-bin-dumps commit, then `fetch_snapshot.py` -> `parse_dumps.py` ->
`fetch_item_stats.py` -> `fetch_gear_lines.py` -> the full gate list above.
Every derived input records its snapshot commit + adapter version in
`out/source_manifest.json`; `build_dataset.py` fails closed on any mismatch.

## Session 2026-08-19 (review fixes) — combo-aware constraints, quarantine gate

Two defects from the owner's chapter-2 review, both verified then fixed:

- **Forge minima now bind the SELECTED spell kits.** `ranged_presence`
  lives in spell bundles (§B), but the forge's `ranged_aoe_core` minimum
  counted the flat sheet map — a member counted as ranged AoE even when
  its equipped combo supplied nothing (reproduced via locked non-AoE spell
  picks: static 7 vs selected 6). Predicate membership is now
  `_pred_contrib(weapon, combo)` from RAW loadout caps; the beam prune
  keeps an optimistic any-combo bound (`_pred_possible`) while
  `_forge_eval_pick` refuses combos that leave more unmet minima than
  remaining slots; refinement checks minima against rest-roster
  combo-aware counts (`_swap_ok` replaced by `_add_ok` + exact need); a
  final feasibility net re-verifies every minimum on the selected combos
  (locked non-qualifying picks surface as infeasible, never pass through
  the flat map). Mirrored line-for-line in app_scoring.js; parity 60/60.
  test_forge's static core check is now combo-aware + new F12a-c pin the
  locked-pick scenario (14/14). 40-forge sweep: 0 violations.
- **A quarantined record can no longer become the canonical default.**
  The Enigmatic p5 build (quarantined field, approved comp envelope) was
  shipping as the dashboard default. `builds_lib.promotable()` gates
  `canonical_eligible` and `selection_order` (quarantined/rejected sink
  last); `build_builds` promotes the first PROMOTABLE variant, pins can't
  rescue a quarantined record; variants carry `status`. Canonical
  defaults 46 -> 45 (blackzone Locus now has none — basis
  "no non-quarantined record"). New H8 assertions pin both.

## Session 2026-08-19 (UX) — rail forge button, role-ordered rosters

- The setup rail gained **"forge full comp"** (`#forge-rail`): fills every
  open slot like the next-pick bar's forge; on a fully forged roster it
  acts as a reforge. Same handler, same engine call.
- The roster is now **ALWAYS kept in role order** — tanks, supports,
  damage (melee, range), healers, the order caller sheets read in
  (`sortPartyByRole()` on `role_hint`). Every membership-changing path
  runs it: add (click + Enter), swap, forge, companion load, permalink/
  storage restore, seed boot; removal and content switches preserve a
  sorted order. One stable permutation over all parallel slot state
  (party/PROV/COMBO/LOADOUT) with live slot indexes (open kit panel,
  gear picker, forge-note filler/held) remapped; scoring, permalinks and
  codecs are order-independent, so only presentation moves. Stable within
  a role, so re-sorting is a no-op and members never shuffle
  gratuitously.

## Session 2026-08-19 (later) — PvP interaction layer ("new prompt")

Spell-keyed PvP interaction records: duplicate semantics, reflect/cleanse/
purge per COMPONENT, CC classes — with chapter-2 confidence provenance.
The revised spec (repo-fitted, stale examples corrected against the pinned
game data) is the `new prompt` file at the repo root.

- **Data**: `pipeline/interactions.yaml` (9 seed spells; every claim cites
  the spell description @ the pinned snapshot; unstated facts stay
  `unknown`) → `pipeline/build_interactions.py` → `out/interactions.json`
  (validated: enums, equippability, verified-requires-source,
  nonstacking_caps only on verified entries + must be caps the spell
  grounds) → embedded in the dataset, part of the provenance chain.
  Structural pre-pass extracts "cannot be reflected" statements from
  descriptions; 19 spells with such facts await curation
  (`_meta.structural_unclaimed`).
- **Scoring (BOTH engines, parity-pinned)**: the one coupling is verified
  `nonstacking_caps` — party supply counts that spell's listed caps ONCE
  across members equipping it (max, not sum), in `effective_supply` and
  exactly mirrored in `_eval_pick` marginals (F1-style invariant holds at
  1e-9; cross-engine duplicate case tested at 1e-9). unknown/likely/
  community_reported NEVER change a score. The shipped seeds carry ZERO
  verified nonstacking caps — nothing in the game data verifies one yet —
  so live scoring is unchanged; the machinery is proven with synthetic
  fixtures in `tests/test_interactions.py`.
- **Analysis**: `Engine.analyze(party, combos)` + `duplicate_conflicts`
  (+ JS mirrors): strengths / missing capabilities / duplicate conflicts
  (severity high|warning only on verified non-stacking; verified full and
  shared stacks are info; unstated = "verify", never a penalty) / CC
  coverage / damage-utility-defense profiles.
- **Dashboard**: dossier "PvP interactions" section (badges + §14 tooltips
  + confidence chip carrying the source + component detail), roster
  duplicate notices, "utility" filter chips (purge/cleanse/anti-heal/
  pierce/displace/no-reflect/dup-verified).
- **Corrected stale examples**: Enchanted Quiver is a self-buff (duplicates
  verified `full`, no resistance shred exists on it in current data);
  Vile Curse Charges are the verified `shared_stack` case; Witchwork
  carries curated cleanse (the "no cleanse" example trio was wrong).
- **mechanics.yaml**: `cc_diminishing_returns: null` +
  `healing_modifiers: null` placeholders (numbers only when citable).
- Gates: everything green incl. new interactions 25/25.

## Session 2026-08-19 — Chapter 2: evidence layer (changeschapter2.md)

Implemented the reproducible game-data + build-provenance layer. Design
record: `docs/superpowers/specs/2026-08-19-evidence-layer-design.md`.

- **Pinned snapshot (§A).** All five ao-bin-dumps inputs (items, spells,
  localization, formatted names) now come from ONE commit —
  `data/source_pins.yaml`, fetched by `pipeline/fetch_snapshot.py`, cached
  by commit, SHA-256s + timestamps + patch in `out/source_manifest.json`.
  Verified byte-identical to the inputs the old outputs were built from
  (zero drift). `build_dataset.py` verifies the derived chain (hashes,
  adapter versions, one-commit rule, curated coverage) and exits 2 with
  `release_clean: false` on any failure. Normalization fixes: tier from the
  dump's own `@tier` (regex is corroboration only), nested enchantment IP
  preserved (`ip_ench`), zero-to-nonzero tier transitions kept, cross-tier
  slot/category consistency validated, per-tier raw item ids kept, dev
  entries dropped by the no-localized-name rule.
- **ranged_presence rework (§B).** The `attackrange >= 9` always-on rule is
  GONE. Now per SPELL BUNDLE: curated `burst_aoe` claim + the spell's own
  delivery (ground/enemy) + `castrange >= 9`, with cited grant/deny
  overrides in `pipeline/ranged_overrides.yaml` (gap-closer leaps denied);
  full audit trail in `out/ranged_presence_report.json`. 42 weapons qualify
  (was 57); 1H Cursed, Chillhowl, Ironclad correctly excluded. It lands in
  the qualifying bundle, never `loadout.always`. V4 role gate moved 77% ->
  73% (still >= 70%) — a legitimate consequence of the sounder rule.
  parse_dumps.py now also extracts structural spell geometry
  (radius/area/max_targets) from spells.json.
- **Evidence layer (§C-§F).** `data/` is the versioned home: caller comps
  migrated OUT of tests/ into `data/published_comps/` (verbatim slots +
  provenance envelopes; tests/meta_comps.yaml deleted), MetaBattle imports
  in `data/published_builds/` (31 ZvZ builds via the MediaWiki API adapter
  `pipeline/adapters/metabattle.py`, fixtures checked in, CC BY-SA
  attribution, all `candidate`), manual Armory format in
  `data/armory_imports/`. `pipeline/builds_lib.py` +
  `pipeline/build_builds.py` normalize/validate/promote ->
  `out/builds_index.json` + `out/builds_validation.json`. Spell picks
  resolve q3/w2/p1 -> exact UniqueNames with bounds quarantine (caught the
  Enigmatic p5 overflow). Canonical promotion gate: Armory+validation OR
  two independent families OR shotcaller approval. Composition exclusions
  now carry evidence records + an evidence gate that flags contradictions.
- **Observation semantics (§E).** sample_battles.py reworked: fight-size
  prevalence (party/side size explicitly unknown), loadout swaps tracked,
  event/battle dedup, battle-level aggregation, abilities stored unknown.
  Dashboard copy relabeled. Still display-only, never in scoring.
- **Dashboard (§G).** Reference builds selected by §F criteria (never
  `variants[0]`), provenance line (source, date, patch, party size,
  approval + canonical basis, confidence by dimension, unknowns, explicit
  fallbacks). Gear catalogue no longer filtered by icon availability;
  ITEM_STATS aliased instead of double-embedded (~190 KB saved).
- **Gates:** golden 24/24, forge 11/11, parity 60/60 + embed, V4 73%
  (gate 70%), codec 24/24, patch-history 14/14, lint clean, provenance
  24/24, builds 44/44.

**Deploy = rebuild + push.** GitHub Pages serves `main:/docs`;
`build_dashboard.py` writes `docs/index.html` (the doctype'd copy of the
dashboard) on every build, so pushing `main` updates the live site.

## Session 2026-08-18 — Forge structural rework (one objective, real optimizer,
## composition constraints)

Forge used to greedy-append top-1 picks and 1-opt them, with a candidate
scorer (dynamic bestLoadout) that disagreed with the completed-party scorer
(static _equipped) — so an 11-man Territory Defense clap comp shipped 3×
basic Cursed Staff plus Iron-clad, and removing one of its own picks RAISED
its own score. Structural fixes, all mirrored in `pipeline/app_scoring.js`
and pinned by `tests/test_forge.py` (11/11) + extended parity (60/60 incl.
forge/locks/redundancy):

- **One canonical objective.** A party member is (weapon, one-spell-per-slot
  combo); `_eval_pick` reports the EXACT `comp_score` delta (invariant test
  at 1e-9 across every content × style). The forge persists the combos it
  scored; the dashboard maps the user's real Q/W/passive picks into combos
  (`combo_from_picks`), so spell picks now affect scoring where curated
  data exists. Gear stays display-only.
- **Synergy rules.** A pair is inactive unless BOTH capabilities are in the
  template (castle_outpost can no longer pay resist_shred × burst_st), and
  one weapon supplying both sides cannot self-trigger a pair (largest
  single-member joint supply is subtracted).
- **comp_score grew three terms:** exact-weapon redundancy (rho, growing
  per-copy cost; free allowances seeded from meta_comps duplicates),
  viability tier (weapons real callers field at size >= 10), and a small
  target→soft-cap headroom slope (a covered capability's extra body is
  mildly good, not worthless — fixes negative tail filler).
- **Forge = deterministic constrained beam search** (`Engine.forge`) + 1-opt
  + bounded 2-opt + a filler/held audit, under `templates/composition.yaml`:
  role-count bands, exact-copy limits, non-stacking groups, ranged-AoE core
  minimum, and the owner's viability exclusions (basic Cursed / Iron-clad /
  Chillhowl are not default large-group picks at size >= 10; manual adds
  still load, score, and get flagged off-comp with swap advice). Infeasible
  or objective-negative slots are SURFACED (UI notices), never silent.
  Perf: ~0.6 s at 20, ~2.5 s at 60 (node).
- **Size behavior.** Piecewise absolute size-physics table replaces the
  linear grow(); no single-target boost above 5 players from a sub-base
  size (T16's small-gang inversion preserved); size-banded ST VALUE
  devaluation (st_value_mult — the T15 fix; roads opts out via
  `st_full_value`); hard floors clamp to the scaled target; the usage
  bucket axis maps party size through 2× (participants), display-only.
- **Data corrections:** Iron-clad tankiness 2→1 (channel-conditional buff),
  Chillhowl's Frozen Crystal split into exclusive ally-save / enemy-control
  uses (`use:` sheet field → exclusive bundles), role_hints for Longbow /
  Heavy Mace / Mace, ranged_presence requirement extended to castle /
  territory_defense / faction_war, anti_zone + damage_debuff reweighted to
  honor their own "can never dominate" rule, brawl burst_aoe 0.85→0.7,
  blap's declared style recorded (`style: brawl`) and used by the V4 runner.
- **Slot provenance** ('m'/'f', permalink `f=` param): "forge the rest"
  locks all current members; "reforge all" rebuilds every forged slot for
  the current content/style/size; content switches keep manual members and
  drop forged ones. Roster rows show a `forged` chip; roleOf() now derives
  from the scored loadout, not the two highest raw capabilities.

Gates after the rework: golden 24/24 (T15 passes for the intended reason),
V4 role 20/26 = 77% (first pass of the 70% gate on the current suite),
forge 11/11, parity 60/60 + dashboard-embed check, codec 24/24,
patch-history 14/14, lint clean. Full size-11 large-content matrix: zero
Cursed/Iron-clad/Chillhowl, constraints hold, no unheld negative slots.

A five-lens adversarial review pass (parity / UI state / engine / data /
spec+test-integrity; every finding independently re-verified) then fixed:
JS [] -truthiness divergences in forge locked_combos and refine pool,
swap-in-place carrying the old weapon's spell picks and forged flag,
kit-panel-open silently changing scores via spell prefill (now gear-only),
positional permalink decode shifting loadouts past unknown weapon keys,
stale 2-opt slot indexes after an accepted pair move, max_fitness missing
the headroom band, per-weapon duplicate allowances applying at small sizes
(now gated by per_weapon_min_size), and explicit combos not surviving
permalinks (new `k=` param). One review finding is a standing OWNER
question, disclosed in tests/VALIDATION.md: the 77% V4 pass is load-bearing
on the 2026-08-18 reweights, which were motivated by defects visible in the
gate comps themselves — weak-form evidence until adjudicated.

## RESUME HERE — Party Companion (2026-08-14, one live run from done)

`companion/` is a C# console app that reads your live Albion party (roster,
weapons, gear, spells) and serves it as JSON on `localhost:53321`; Comp Forge's
new "connect live party" button pulls it into a comp. **Read
`companion/README.md`'s "Status — pick up here" block first** — it has the exact
one-live-run checklist. Design + event map + legality: `COMPANION_SCOPE.md`.

Everything is BUILT and committed (tree clean — check `git status`). The whole
thing needs **one live in-game run** to confirm three things at once:

1. **Spells resolve** to sheet-matching UniqueNames in `/party` (`SpellDb.cs`).
2. **Auto-calibration binds** — `/status` `detected_codes` shows e.g.
   `NewCharacter:29`. Events now dispatch by parameter SHAPE, not hardcoded
   numbers, so a patch that renumbers events self-heals.
3. **Connect button works end-to-end** — in Comp Forge's left rail; polls
   `/party`, lists the party, "load party into comp" fills slots. Verified
   against a mock; needs the live companion to confirm.

- Run the exe **as Administrator** (`run-companion.bat` rebuilds + self-elevates).
  Needs .NET 8 SDK (installed).
- **Key facts** (COMPANION_SCOPE.md / companion/README.md): current Albion uses
  Photon **Protocol18** (stock NuGet parser is Protocol16, decodes nothing) —
  working parser vendored under `companion/photon/` (GPL-3.0; companion binary
  is GPL, Comp Forge unaffected). Item/spell indices shift per patch (delete the
  cache to re-pull); event codes now self-heal via shape detection.
- Commits this session: `907ee88` mechanics+corrections · `953244b` UI ·
  `6a75dc3` companion core · `a50e620` spell resolution · `4e1e779` shape
  auto-calibration · `afa0f62` connect button. None pushed (public site
  untouched).

## Session 2026-08-15 — Roads template + per-member swap advisor

Goal driven ("caller picks the content; small parties may lack roles, big
ones shouldn't; poor picks get multiple better options"):

- **`pipeline/templates/roads.yaml`** — Roads of Avalon (base 7, `max_size: 7`
  = the in-game cap, UI warns above it). PROVISIONAL like all templates; the
  header documents the small-scale inversion (burst_st weight 7 vs
  blackzone's 1, heal_reduction 7, mobility/catch/disengage high, AoE/zone
  low; `self_sustain` used for the first time — healer-less duos/trios are
  legitimate). Floors arm by size: heal from 5, tank from 6 — a 3-man
  without a healer is fine (T16 pins this), a 7-man is flagged broken.
- **Swap advisor** — `Engine.swap_review(party)` (+ identical
  `swapReview` in `app_scoring.js`, parity-covered on every 6th case): each
  member's CURRENT weapon valued exactly as recommend() would value it into
  the rest of the party, ranked vs all alternatives (strictly-better counts
  only), top-3 upgrade options with gains. CLI: `--review`. Comp Forge
  renders it per roster slot — silent for decent picks (rank < 15 or gain
  < 1.0), "better options" links otherwise, "off-comp here — rank N/137"
  past rank 60; options click-to-swap in place. T17 pins the directions
  (Realmbreaker in a roads 7-man: rank 105, healer-staff options offered).
- Golden 24/24 (T16 roads size graduation, T17 swap advisor); parity 60/60;
  headless Chromium run verified the built page (picker, hints, swap click,
  cap notice, parity chip OK, zero console errors).
- `build_dashboard.py` now builds on Python 3.11 too (backslash-in-f-string
  expressions hoisted out — 3.12-only syntax).

Still open for the goal: gear-quality advice needs gear sheets (§2.4, the
known big build item); live-join re-advice works via the companion connect
button (poll → load party → advisor runs on every render).

### Full code-review pass (same day) — web app + companion

Three reviews ran (scoped diff review + holistic web-app + companion C#);
every confirmed finding is fixed, gates green after each batch:

- **Cross-engine rounding divergence (HIGH, was live)**: Python `round()` is
  half-to-even, JS `Math.round` half-up, and the Q16 `grow()` curve lands on
  exact .5 counts at ordinary sizes (faction_war@10/brawl measured 16% apart
  on burst_st supply). Both engines now share one explicit half-UP rule
  (`_half_up` / `Math.floor(x+0.5)`). The parity suite was blind to it
  because all 60 cases ran at base_size — sizes now cycle through shrunk /
  grown / .5-tie / >30 variants per case.
- Swap advisor: party-wide gaps no longer nag every member (per-role dedupe,
  cheapest converter keeps the hint); empty-pool JS/Python divergence fixed
  (`_pool()`); score formula deduped into `pick_score`/`pickScore`; sweep
  memoized in the dashboard.
- Dashboard robustness: share-hash roster capped at HARD_CAP; junk hashes
  fall back to seed; empty-party links clear the roster; `loadStored` uses
  replaceState (no history pollution / double render); facet dead-end
  auto-clears; stale usage keys filtered at build AND render (a rename
  previously killed every render); keyboard activation for the picker's "i"
  span; groups/weakness "have" numbers now show EFFECTIVE supply (they mixed
  raw numbers with effective gap scores); parity fixture compares at 1e-9
  instead of 2dp rounding; a handful of esc() gaps closed.
- Companion (compile-verified, dotnet 0 warnings): per-request try/catch —
  one aborted poll used to kill the process; Photon fragment reassembly TTL
  sweep + 4MB totalLength cap (leak + hostile allocation); parser calls
  serialized across capture threads; CORS wildcard → allowlist per
  COMPANION_SCOPE + OPTIONS/Private-Network-Access preflight; CRC branch
  read header bytes as the CRC (latent, fixed per upstream semantics);
  objectId map bounded (4096); roster/self-join shape guards require
  plausible character names (3-16 alphanumeric). Cross-zone objectId reuse
  stays a KNOWN LIMITATION (companion/README.md) — needs a live zone-change
  event identified before it can be fixed properly.

### Cleanup/efficiency pass (2026-08-15, four-angle review: reuse /
### simplification / efficiency / altitude)

- **Engines ~2x faster on the hot path** (JS swapReview 56→18ms, recommend
  2.2→0.94ms; Python swap_review 89→70ms): per-set_content caches for
  scaled targets / styled weights / per-weapon loadout combos
  (`_loadout_extras`) — same expressions, same floats, parity 60/60
  unchanged. Scoring math deduped into `_overstack` + `_cover_terms`
  (the T10 base-weight rule now lives ONCE per engine); `_table_lookup`,
  `size_bucket()` and `floor_armed()` are the single homes of the clamp
  rule, the usage buckets and the below-floor predicate — the dashboard
  consumes the last two instead of re-deriving them (bucket boundaries were
  written 5x across 3 files; the floor predicate 3x).
- Dashboard: swap-advisor thresholds moved to `templates/scoring.yaml
  swap_advisor` (data layer, visible to the expert pass); needed-now split
  uses STYLED weight (raw weight silently disagreed with the greedy-trap
  warning under any style); weapon list sorted once not per keystroke;
  fitness/supply computed once per state; static <select>s built once;
  companion poll skips DOM churn on unchanged payloads and pauses in
  hidden tabs; capability board grew an "Other" fallback group — which
  immediately surfaced that `damage_debuff` had been silently missing from
  the board (now in Denial); parity fixture carries its own seed party
  (was 3 hardcoded copies that had to agree by eyeball).
- Companion: UDP port filter now runs BEFORE the per-packet copy (the
  promiscuous socket was copying every datagram on the host); shared
  `CachedFetch` (ItemDb/SpellDb had drifted copies); shared
  JsonSerializerOptions; ItemDb injected once instead of threaded through
  every UpdateLoadout call; dead code deleted (AddMember/RemoveMember/
  Disband, `_guidToName`); Upsert lock discipline documented; self-join
  gate consolidated into its handler. dotnet build 0 warnings.
- Deliberately SKIPPED: rerouting _app.js's tpl/REQS accessors through ENG
  (they run before syncEngine during state transitions — would read stale
  context); moving `load_loadouts` into build_dataset (dataset schema +
  meta_comps format decision for the owner); merging companionRoleClass
  into roleCls (different unknown-weapon semantics).

## Session 2026-08-15 (later) — "The War Table" visual redesign

Comp Forge + the how-it-works page now wear one committed dark identity
(single theme by design — no light mode): iron surfaces with a warm
undertone, forge-light atmosphere (ember bloom + steel wash + film grain),
ember-brass reserved for the machine's voice (recommendations, actions,
evidence), game item renders as the decorative color. All markup IDs/classes
consumed by `_app.js` unchanged — the redesign is the `_shell.html` style
layer + masthead (SVG sigil, sticky glass header) and `_explainer.html`
tokens. Data colors are VALIDATED, not eyeballed (dataviz six-checks vs the
dark surface): role palette #3987E5/#D95926/#199E70/#C98500/#D55181 passes
CVD + normal-vision + contrast gates in that order; bar status colors always
sit beside text labels. Verified headlessly: desktop/mobile/drawer
screenshots, forge + picker + evidence interactions, parity chip OK, zero
console errors; golden 24/24, parity 60/60 (CSS-only change).

### Weapon dossier + asset upgrade (same session)

- The weapon drawer is now a DOSSIER: "where it lives" content-affinity
  board (opening-pick rank of 137 per content template, balanced/base-size,
  computed in-browser from the same engine — tier chips prime/solid/
  situational/fringe, current content highlighted), field reports across
  all three fight-size buckets, capabilities+evidence, spell pools with
  spell icons.
- Assets: the dossier hero + spell lists hot-load full-res art from the
  official render service at RUNTIME (render.albiononline.com; item ids
  injected as `ITEMS` by build_dashboard) with silent onerror fallback to
  the inlined icons — zero page-weight cost, works offline. Inline icons:
  fetch_icons.py bumped 64px → 96px for retina-crisp list icons —
  **owner must rerun `py -3 pipeline/fetch_icons.py --force` once** (the
  render service is proxy-blocked from the cloud session; page works with
  the old 64px manifest until then).

## Current state (verified 2026-08-13)

**One source of truth.** Capability numbers live only in `pipeline/sheets/*.yaml`;
global combat-mechanics numbers live only in `pipeline/templates/mechanics.yaml`.
The engine, the golden tests and the page all consume `out/dataset-latest.json`.
All gates green: lint 0 errors across 60 sheet files, golden 24/24, JS/Python
parity 60/60 across all templates × styles at 1e-9 (now also covering
swap_review), patch-history 14/14.

- **Curated: 137/137 combat weapons.** The remaining 24 catalog entries are
  vanity items / gathering tools — no sheets, on purpose. Drafts: 0.
  Illustrative placeholders: 0 (`sheets/illustrative/prototype_v0.yaml` is a
  tombstone record of the §2.3 prototype numbers and their corrections).
- **Six content templates, sizes set by the content**: `blackzone_roam` (20),
  `territory_defense` (20), `castle` (25), `faction_war` (15),
  `castle_outpost` (7), `roads` (7, `max_size: 7` — the in-game Roads party
  cap; the UI warns above it) — plus **five playstyles** in `templates/styles.yaml`
  (balanced/brawl/clap/kite/brawl_clap) that multiply capability WEIGHTS on
  top of any template (floors and over-stack stay on base weight — T10 caught
  the alternative punishing a clap comp for stacking bombs). Party size is
  free-form (2–60): effective size = max(planned, roster).
- **The product page is `dashboard/index.html` — "Comp Forge"**, public at
  <https://sodiyal.github.io/albion-comp-engine/>. Generated by
  `build_dashboard.py` from `_shell.html` (markup/CSS) + `_app.js`
  (rendering only). Features: content + playstyle pickers, adaptive party
  size, numbered slots with role tally and per-member fitness contribution
  ("least load-bearing" / "comp gains without it"), tree + text weapon
  filters, "forge a full comp" greedy auto-build, needed-now vs nice-to-have
  gap split, full capability board with evidence drawer, weapon detail
  drawer (real Q/W/E/passive pools by in-game name + caller loadouts from
  the `skills` columns in `tests/meta_comps.yaml`), killboard meta strip +
  per-weapon field reports (display-only), embedded item icons (136/137 —
  Black Hands is missing from the render service itself), share-link hash
  state, localStorage restore, Discord comp export. Scoring runs in the
  browser via `pipeline/app_scoring.js` — a line-for-line port of
  `engine/engine.py`; **change one, change both, rerun parity**. A
  build-time fixture re-checks parity on every page load (masthead chip).
  A short-lived duplicate app (`app/`, 2026-08-12) was folded back in —
  don't recreate it.
- **Real-usage data**: `out/weapon_usage_v2.json` — 149 battles / 1,252
  players / **99.4% weapon attribution (V7 gate ≥85%: PASS)**, bucketed
  small (<12) / mid (12–30) / large (>30). Zero unknown weapon keys — the
  catalog covered everything seen in the wild. Large bucket is thin (6
  battles); a `--force`-free rerun tops it up when the albionbb API isn't
  throttling. **Display-only by rule** until validation admits it to scoring.
- **First V4 baseline exists** (`py -3 tests/tier2_blindtest.py v4`):
  role-level 18/26 = **69%** (gate 70%), weapon-level 9%, over 70
  leave-one-out slots. Three findings recorded in VALIDATION.md: leave-one-
  out degenerates at full-party saturation; breadth-over-depth wins the
  saturated margin; dedicated support never reproduces (undervalued at the
  margin). **Nothing was retuned** — these comps calibrated the templates
  (circularity), so the findings await the expert and independent comps.
- **Game-mechanics layer (2026-08-13)**: `pipeline/templates/mechanics.yaml`
  holds the wiki-sourced ZvZ mechanics (Focus Fire/Resilience tables, AoE
  Escalation curve, Disarray — the last recorded but UNWIRED: it cancels in
  a mirror fight). Styles carry `mechanics: {expected_aoe_targets,
  focus_attackers}`; the engine turns these into effectiveness multipliers
  on `burst_aoe` (escalation) and `burst_st`/`execute` (Resilience),
  NORMALIZED so balanced ≡ identity — template calibration untouched, V4
  baseline unchanged by construction. Golden T11 pins the directions.
  Open questions + provisional numbers tracked in `MECHANICS_TODO.md`.
- **Line structure is the organizing principle**: all weapons in a line share
  the same Q/W spell pool; only the E differs. Line-mates carry identical
  QW-conditional scores (marked `(QW)` in comments).
- **`pipeline/effect_overrides.yaml`** documents every runtime correction to
  parser output (direction bugs, reference-chain artifacts, heal-flag
  reclassification, `add:` entries for real mechanics outside the structured
  vocabulary). MUST be re-checked after every ao-bin-dumps re-clone.
- `effect_lookup.py`: structured effects SUPERSEDE direction-blind prose
  flags (ally-direction guard for the heal flag). Seeder and lint share it.

## Non-negotiable rules established in review

- Every nonzero capability score cites its evidence spell; weapon sheets
  contain only the weapon's own kit; gear capabilities go on gear sheets.
- Effect direction matters: self-targeted abilities never ground enemy/ally-
  directed capabilities. Lifesteal is `self_sustain`, never `heal_sustain`.
- **Momentary-defensive ruling:** personal channel/dash defensives (Parry,
  Deflecting Spin, Counter stance, Cartwheel, untargetable windows) do NOT
  ground `tankiness`. Sustained/identity durability does.
- Knock-ups, knockbacks and stuns HOLD (or scatter) clumps; only drag/pull
  mechanics CREATE them (Onslaught, Vendetta, Black Hole, Triple Kick's
  kidnap). Great Hammer's Tackle is a knockback, NOT a clump creator —
  expert-corrected 2026-08-13, pinned by golden T12.
- **Magnitude, not existence — ALL capabilities** (expert, 2026-08-13):
  every score encodes impact magnitude; a token effect is not the same
  number as a battle-shaping one. First applied to `knockback_displace`
  (golden T13): 3 = battle-shaping (≥12m or kit-wide, CC-resist-ignoring);
  2 = real AoE travel; 1 = minor/incidental (single-target bolts, small
  scatters, ALL knock-ups/air-throws — no travel, control value lives in
  peel/stun); 0 = trivial in group fights (healer self-peel nudges, AA
  passives). Never score the same control twice across
  clump_create/peel/knockback_displace. The dataset-wide audit runs
  through `review/magnitude.html` (`py -3 pipeline/build_magnitude_review.py`
  — per-capability boards with dumps numbers beside every score; RULE/PASV/
  TOP flags). Open queue in MECHANICS_TODO.md. When a shared QW spell's
  score is topped up by an E contribution, the sheet comment MUST say so —
  a same-spell score mismatch without that comment is a bug.
- Interrupts are not silences; charge-scaled burst is not execute (execute =
  health-threshold scaling, e.g. Bloodletter E).
- Hard floors are load-bearing; the golden suite (15 cases) is permanent —
  add a case whenever an expert corrects the engine and is right.
- Never invent a capability to fill a gap. If the evidence isn't there, the
  score is 0. When the PARSER is wrong, fix it in `effect_overrides.yaml`
  with the dumps text cited — never by fudging a sheet.
- Meta comps (`tests/meta_comps.yaml`) and caller loadouts are **real data
  only, never invented**; killboard usage stays display-only pre-validation.

## PROVISIONAL numbers awaiting the expert

- `castle_outpost.yaml` heal floor `penalty_mult: 2.0` (raised from 1.5 when
  synergy+meta leakage out-ranked healers). Structural alternative worth
  testing after Tier-2: step-function floors (no partial-credit relief).
- The entire requirement sets of `blackzone_roam`, `territory_defense`,
  `castle`, `faction_war` — calibrated first drafts, reasoning in headers.
- Every multiplier in `templates/styles.yaml` — golden T10 pins only the
  style DIRECTIONS, not magnitudes.
- `anti_zone` weight (sole supplier: Exalted Staff) and `damage_debuff`
  weight (6 defining carriers; small carriers held at 0).
- The ~15 `add:` entries in `effect_overrides.yaml` — text-verified but
  judgment-flavored; SOUL_LINK→peel especially (HAMMERTACKLE→clump_create
  was expert-adjudicated 2026-08-13: removed, tombstoned in the overrides).
- The per-style `mechanics` parameters in `styles.yaml`
  (`expected_aoe_targets`, `focus_attackers`) — research-derived, not
  expert numbers yet (`MECHANICS_TODO.md` Q14; curves themselves are wiki
  data in `mechanics.yaml` and are NOT provisional).
- Black Hands: empty dumps description AND missing from the render service;
  scores rest on structured effects + community sources.
- From the V4 baseline: support undervaluation at the margin and a possible
  redundancy/diversity term for the saturated range — expert questions, not
  numbers to tweak blind.
- 2026-08-18 forge rework additions (all data, all owner-reviewable):
  everything in `templates/composition.yaml` (role bands seeded from the
  four meta_comps parties, copy limits/free allowances, the exalted_slot
  group, the viability core list + exclusions, size_physics count_mult and
  st_value_mult tables); `scoring.yaml` rho 0.25 / viability 0.15 /
  headroom 0.1; the cross-member synergy formulation (min-minus-best-self-
  joint); `roads.yaml` `st_full_value: true`; the anti_zone/damage_debuff
  reweights; brawl `burst_aoe: 0.7`; ranged_presence rows on castle /
  territory_defense / faction_war (0.25/player, copied from
  blackzone_roam); Iron-clad tankiness 1; the Chillhowl `use:` split.

## Immediate next step: Tier-2 blind validation (V3)

Everything else is tuning noise until expert data arrives — floors, style
magnitudes, template weights and score ladders all get adjudicated by this.

```
tests/tier2_form.md      # seed 20260812, generated against all 137 weapons
#   send the SAME file to 3+ shotcallers; it deliberately shows no engine output
py -3 tests/tier2_blindtest.py score tier2_form_filled.md
```

Gate: expert pick in engine top-3 on ≥70% of cases. Every miss where the
expert is right becomes a golden case.

**V4 has its baseline** (69% role-level, see VALIDATION.md) but it's
weak-form: the 20-size templates were calibrated on the same two comps. The
single highest-value data acquisition is **one more real comp from a caller
who didn't shape the templates** — that turns V4 into real evidence. More
caller loadout sheets (like Timothy's q/w/p columns) extend the in-app spell
suggestions to more content types for free.

## After Tier-2

- Expert correction pass over proposed scores (sheet headers flag every
  judgment call), template weights, style magnitudes, and the V4 findings.
- Gear sheets — the biggest remaining build item; blocks archetype
  composition and the "cleanse if running X" conditional-capability UI.
  Default kits: Metabattle open MediaWiki API (~120 builds, CC BY-SA) +
  Albion Free Market (4,478 builds; ask their Discord before bulk harvest);
  two-source agreement = high-confidence kit (design doc §2.4). Gear icons
  come free from the same render service once gear item IDs exist.
- More content templates (Hellgate 5v5, Roads 7) and a V4b runner that
  reconstructs the last ~5 slots instead of leave-one-out at saturation.
- Phase 3 proper: battle-data ingestion for MetaPrior (replace the hand-set
  guard values), content labeling (V6), win-lift backtest (V8).
