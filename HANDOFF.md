# Handoff — Albion Online Composition Engine

Comp Forge is an Albion Online party-composition recommendation engine and
research tool, live at <https://sodiyal.github.io/albion-comp-engine/>.

This file is the current state: what the product is, how the engine and the
planner work today, the rules that shape generation, and what is open. It
carries no history — every ruling's date, the owner's words and the pin are
one line in `tests/VALIDATION.md`; the full log is `notes/validation/`.
`MASTERSHEET.md` is the LIVE expert control surface (its `tune:` blocks
override everything at build time — read it first for what the engine
actually uses). `CLAUDE.md` has the environment traps, the gate list and the
invariants. `pipeline/README.md` has the pipeline and the patch workflow.

## What the product is

Comp Forge does **not** score parties by role counts. Weapons are capability
bundles and the engine asks: *what can this party do, what does this content
and playstyle reward, and which next weapon improves the answer most?*

The planner is decision-first: comp status -> biggest need -> best next pick
-> why it helps -> what stays weak after it joins -> wheel and roster
exploration -> deep capability / build / spell / evidence / math inspection.
Roles are player-facing labels; scoring is capability-driven.

Three layers, never merged:

- **Mechanical recommendation** — `CompEngine` is the authoritative scorer:
  which weapon most improves the modeled composition under the selected
  content, size, style, roster and resolved kits.
- **Explanation** — the UI translates engine output into caller language
  (`dashboard/_decision_layer.js` is translation only). No second scoring
  system in the UI.
- **Empirical evidence** — killboard prevalence, observed pairings, reference
  comps, build sources, expert results. They never alter ranking unless a
  calibration decision promotes them into scoring and is validated.
  Popularity is not effectiveness. Semantics and caveats:
  `KILLBOARD_AFFINITY.md`.

## The engine today

- 137 combat weapons; 31 capabilities, every one scored by at least one
  content template (`reveal` is proposed-only, refused with evidence in
  `effect_map.yaml`). Sheets score 1–7; 2 points = one supply unit.
- Six content templates with comp-fitted targets and soft caps (person units)
  and hard floors (weapon units); five playstyles (brawl / clap / kite /
  brawl_clap / clap_kite) carrying weight multipliers, `target_mults`,
  constraint overrides and a fight chain; GENERATED style x size rows beside
  the content rows (`templates/style_bands.yaml`, from harvested winners,
  read for a declared style at 10+).
- Fitness: coverage with diminishing returns, hard floors on the
  weapon+loadout basis, headroom, overstack, Focus Fire / Resilience and AoE
  escalation, per-weapon Resilience Penetration as a rebate, optional rows,
  ramped rows (`anti_zone`: none through 14, full at 25).
- Recommendation score = exact marginal comp-score delta (0.55 capability +
  0.20 synergy + 0.15 meta prior ± viability / duplicates), one player ahead,
  each candidate on its best legal Q/W/E/passive combo, DRESSED in its doctrine
  kit. Synergy is weapon-interaction only. The meta prior is GENERATED from
  the killer-party harvest per size bucket (`out/meta_prior.json`); a hand-set
  map fails the build. Duplicates: 1 copy by default; the one super-additive
  case is `self_cost_offset_min_copies` (Demon Armor).
- Gear scores (curated `sheets/gear/`) through `build_extra`: stat
  channels, doctrine passives, `cc_mult_caps`, `self_costs`. Tier-agnostic
  lookup (`gear_key()`).
- The role layer (`roles-design.md`, `pipeline/roles.yaml`): seats (uniformed)
  and functions (pierce / purge / anti_heal / shield_break) derived E-first;
  `detect_role` / `role_advisory` descriptive; `role_class` for forge bands
  derives from the primary seat.
- Kits: `kit_options` is doctrine-led, observed-build-led and fail-closed.
  Every doctrine reader goes through `_seat_kit` (group band at 10+, gang band
  at <= 9, a declared style's cell laid over the band). Slots rank by observed
  votes (one player, one vote; killer parties of 10+), the observed-build chain
  fronts a real worn combination (chains may have gaps), thin slots pool to
  the seat (`kit_pool` / `kit_by_chest`), carrier chests obey a comp-level
  quota, two-handers get no off-hand, and where evidence runs out nothing is
  proposed. Manual kits always score.
- Descriptive analyzers, parity-carried, never scoring inputs: `comp_identity`
  (playstyle label, per-member fit, bomb-squad archetype, kit-aware), `kill_pressure`,
  `fight_chain`, `pick_report` (signed decomposition reconstructing the pick
  marginal at 1e-9), `analyze`, `duplicate_conflicts`, the role advisory.
- `engine/app_scoring.js` mirrors `engine/engine.py`; parity on 60 random
  parties at 1e-9 plus an embed check on every build.

### How a recommendation is computed

1. `CompEngine` loads content, effective roster size and playstyle.
2. Members resolve to their selected / stored / default legal spell combos.
3. Effective capability supply is computed (weapon + loadout + worn gear).
4. Fitness evaluates coverage, floors, headroom, overstack and mechanics.
5. Candidates run one ahead (`roster + 1`) so thresholds that arm on the next
   body are anticipated.
6. Every candidate is evaluated on its best legal loadout, dressed in its
   doctrine kit.
7. Score = exact marginal fitness + synergy + meta prior ± viability and
   duplicate terms.
8. `explain()` / `pick_report()` return the per-capability deltas from the same
   candidate kit.

Do not rewrite this flow in the dashboard layer.

### Roster size vs planned size

Attendance is fluid. The roster is judged at its **actual size**; `PLANNED`
controls how many slots the forge fills and warning / cap behaviour; next-pick
advice runs one ahead. Never collapse to `max(planned, roster)`. Killboard
*display* buckets are the opposite by design: `usageBucket()` keys off
`PLAN()` (the fights the comp is for); the meta prior keys off roster size.

## Forge and loadouts

Constraints are combo-aware: the selected spell combination must satisfy a
minimum, not the sheet's theoretical maximum. Generation rules (each is an
index row in `tests/VALIDATION.md`; manual picks always score):

- **Suggestion pools** go through `suggest_pool()`: viability exclusions
  (Dagger Pair / Deathgivers at 7+, Double Bladed at 10+, Chillhowl at 10+ —
  evidence-gated, lifted by a canonical large-group build), the style gate,
  and the generation-fit gate (damage picks whose derived verdict is "fits";
  single-ally-heal-E healers never at 10+; non-stacking-group members need an
  E debuff tool at 10+). There is no cost gate.
- **Healing foundation**: `primary_heal` band minima need `full_healer`
  weapons (E heal >= 6 AND group scale). One healer per five members is a
  MINIMUM on clap, brawl and both hybrids; kite keeps its minima; balanced
  keeps the base band.
- **Role bands per style** (`styles.yaml constraint_overrides`), including the
  clap / clap_kite 7-strong ranged-AoE core at 20 and kite's 5 / 4.
- **Duplicates**: 1 copy by default; allowances cite real comps. Derived job
  groups `clump_core` and `curse_pressure` max 2 each.
- **Need profiles** (`roles.yaml need_profiles`): fine-seat bands + function
  coverage, armed at 15+, scaled by size / 20.
- **Carrier quota**: discretionary effect-carrier chests capped per roster at
  killboard share x size; a weapon's identity chest (worn by half its builds)
  is exempt.
- **Dressed forge**: candidates are priced dressed; forged members arrive with
  kits prefilled (`_eng`-marked); locked members keep their supplied gear and
  are never re-dressed; doctrine passives never enter evaluation.
- The forge's minimum-need bound is admissible (never more than a legal
  completion needs, never less); the expansion sort is quantized in both ports.

The dashboard tracks `party`, `PROV` (manual / live / forged), `COMBO` and
`LOADOUT`; `sortPartyByRole()` applies one stable permutation across all of
them, and every roster mutation goes through `data-add` / `data-swapat`. The
forge handler wraps `ENG.forge(goal)` in a target-size `setContent`.

Audit artifacts: `out/economics_report.json`, `out/style_fit_report.json`,
`out/roles_report.json`, `out/roster_mixes.json`, `out/style_roster_evidence.json`.

## The planner today

Source files: `dashboard/_shell.html`, `_app.js`, `_loadout.js`,
`_decision_layer.js/.css`, `_layout.css`, `_explainer.html`, `build.py`.
Generated: `dashboard/index.html`, `docs/` — never hand-edit.

- **Layout**: a card grid (four columns >= 1700px, three from 1400px, the
  single flow below 1251px; fractional band bounds) in `_layout.css`, inlined
  last. Setup, caller tools, party and live party are `.epanel` edge flyouts
  (one per edge on desktop, one total on phones). The masthead is a status
  bar: fitness, identity verdict, style / size / content, forge actions.
- **Comp status is THE RADAR**: one axis per capability group against the
  comp-fitted CEILING (100% = soft cap, nothing above 100; a brass tick marks
  the target; purple = over-ceiling stacking; pink = under a hard floor);
  `comp_identity` in the hub; all prose in hovers.
- **Biggest need** (floor failures first) -> **best next pick** with its
  engine-derived explanation, **what it fixes**, **still weak after** (one
  ahead, on the candidate's scored combo), and the **fight chain** strip.
- **Kill pressure** (pierce · heal-cut · burst lights) and **role check**
  (seat tally, function and carried-aura chips, advisory flags) as cards —
  descriptive only.
- **Negative recommendations**: `pick_report()` drives the "why not" block,
  dims redundant alternatives, chips covered jobs.
- **Capability supply** as nested rings per group on the same ceiling ruler;
  the full capability board is the deep diagnostic on the same ruler.
- **Observed killboard context**: affinity strip, cohort note, neighbours,
  recurring cores (`out/cohort_families.json`), observed effect quotas — all
  display only.
- **The wheel** is a semicircle (art on the top arc, hub in the mouth); the
  **comp board** in the right-edge party flyout has four seat columns of
  member tiles sharing `memberPop()`, an open-slots column, and a notes rail
  (duplicate checks, kit editor).
- **Caller tools**: per-player weapon pools and the swap-impact lab.
- **Live party**: the companion feed with live sync — weapon swaps update
  slots, real Q/W picks and worn kits flow into loadouts, in-game inspect
  refreshes a member. Companion: `companion/README.md`, `COMPANION_SCOPE.md`.
- Public explanation: `dashboard/_explainer.html` -> `how-it-works.html`.

Gates for the page: `tests/test_dashboard_layout.py` (L1–L19),
`tests/test_display_math.js`, `tests/test_live_party.js`, `test_loadout_codec.js`.

## Evidence and provenance rules

- Curated nonzero scores cite equippable spells the lint can ground (weapon
  spells and gear actives/passives are both indexed).
- Generated artifacts are provenance-checked; the release fails closed on
  mismatch. Every writer of a committed artifact opens with `newline="\n"`.
- Reference build records carry source / provenance / confidence; quarantined
  records never become defaults; `unknown` stays `unknown`.
- Evidence is harvested on a schedule (the overnight task, 03:00 and 15:00)
  and folded weekly with `pipeline/fold_harvest.ps1` (never commits; writes
  `notes/findings/<date>-fold-report.md`). Because the corpus grows daily,
  tests pin mechanisms, never exact counts. A focused night
  (`-MinPlayers 10 -MaxPlayers 14`) adds to the cache, never narrows it.
- The effect catalogue is not part of a normal build; regenerate it when the
  snapshot moves: `py -3 pipeline/effect_catalogue.py pipeline/out/dumps_cache/<commit> [--report]`.

Game-patch chain (details in `pipeline/README.md`): update
`data/source_pins.yaml` -> fetch snapshot -> parse dumps -> refresh item /
gear data -> rebuild interactions / builds / dataset -> every gate -> rebuild
dashboard and review artifacts -> icons only if new items need them. Never
move the snapshot silently or bypass the fail-closed gates.

## Open work

`BACKLOG.md` — the one list, grouped by what each item waits on (an owner
ruling, evidence a round would produce, plain engineering, deprioritized
product features). No other document keeps its own list.


## Files to read before major changes

Scoring / mechanics: `albion-comp-engine-design.md`, `MASTERSHEET.md`,
`MECHANICS_TODO.md`, `engine/engine.py`, `engine/app_scoring.js`,
`pipeline/templates/composition.yaml`, `styles.yaml`, `style_bands.yaml`
(generated), `pipeline/style_overrides.yaml`, `roles-design.md` +
`pipeline/roles.yaml`, `tests/test_golden.py`, `test_forge.py`,
`test_roles.py`, `tests/VALIDATION.md`.

Data / provenance: `pipeline/README.md`, `data/README.md`,
`data/source_pins.yaml`, `pipeline/build_dataset.py`,
`tests/test_provenance.py`, `test_builds.py`.

Product / UI: the `dashboard/_*` sources and `dashboard/build.py`.

Companion: `COMPANION_SCOPE.md`, `companion/README.md`, `companion/`.

## Product direction

Not an Albion build calculator: an explainable **composition assistant /
virtual shotcaller** that understands what the party is trying to do,
diagnoses what it lacks, recommends the next practical player / weapon,
explains why, works within what real players can play, shows the
consequences of swaps, compares mechanical theory with observed evidence, and
eventually reasons about opposing compositions. Preserve the distinction
between engine truth, display explanation and observed evidence as it grows.
