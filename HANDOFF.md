# Handoff — Albion Online Composition Engine

Comp Forge is an Albion Online party-composition recommendation engine and research tool, live at:

<https://sodiyal.github.io/albion-comp-engine/>

This file is the current-state handoff. Historical implementation notes still live in the repository (`albion-comp-engine-design.md`, `MECHANICS_TODO.md`, `MASTERSHEET.md`, `pipeline/README.md`, and `tests/VALIDATION.md`) and should be consulted when changing mechanics, calibration, provenance, or validation.

## What the product is

Comp Forge does **not** score parties by simplistic role counts. Weapons are represented as capability bundles and the engine asks:

> What can this party do, what does this content/playstyle reward, and which next weapon improves the answer most?

The current planner is deliberately decision-first:

1. Comp status
2. Biggest need
3. Best next pick
4. Why that pick helps
5. What remains weak after it joins
6. Wheel / roster exploration
7. Deep capability, build, spell, evidence, and math inspection

Roles remain useful player-facing labels, but scoring is capability-driven.

## Current engine model

The production engine currently includes:

- 137 combat weapons
- 29 capability dimensions
- content-specific templates
- playstyle weight modifiers
- adaptive party-size targets
- hard floors for load-bearing requirements
- diminishing returns and headroom
- overstack penalties
- capability synergies
- duplicate handling
- viability exclusions / priors
- Focus Fire / Resilience mechanics where modeled
- geometric AoE escalation for relevant utility
- one-spell-per-slot loadout resolution
- combo-aware forge constraints
- constrained composition generation / forge
- swap review
- weapon dossiers, spell facts, PvP interaction evidence, reference builds, and suggested gear

The JavaScript engine (`engine/app_scoring.js`) mirrors the Python engine and is parity-tested.

## Important product principle

Keep these layers separate:

### Mechanical recommendation

`CompEngine` is the authoritative scoring layer. It should answer which weapon most improves the modeled composition under the selected content, size, style, current roster, and resolved kits.

### Explanation

The UI should translate existing engine output into caller language. Do not create a second hidden scoring system in the UI.

The merged decision-first layer in `dashboard/_decision_layer.js` is intentionally display/translation logic over engine outputs.

### Empirical evidence

Killboard prevalence, observed pairings, reference comps, build sources, and expert results are evidence layers. They should not silently alter mechanical recommendation ranking unless a future calibration decision explicitly promotes them into scoring and is validated.

Popularity is not effectiveness.

## Current live UX on `main`

The planner now leads with:

- **Comp Status** — critical gaps / weak areas / overstacking, with fitness demoted to supporting context
- **Biggest Need** — hard-floor failures outrank softer deficits
- **Best Next Pick** — prominent weapon recommendation, score, role/function, and engine-derived explanation
- **What it fixes** — strongest marginal capability gains
- **Still weak after this pick** — recalculated one slot ahead using the candidate's scored combo
- **Comp identity** — the status card names the playstyle the party is becoming (brawl/clap/kite/mixed) and flags split identities, descriptive only
- **Observed killboard context** — the contextual affinity strip and the pick card's observed-cohort note, display evidence only
- **Caller tools** — the player-pool and swap-impact fold below the wheel stage, collapsed by default

The old right-hand fitness / weakness / recommendation stack is intentionally hidden to avoid duplicating the same questions. The wheel remains an exploration surface and the full capability board remains the deep diagnostic layer.

Source files:

- `dashboard/_decision_layer.js`
- `dashboard/_decision_layer.css`
- `dashboard/_app.js`
- `dashboard/_shell.html`
- `dashboard/build.py`

## How recommendations are computed

At a high level:

1. `CompEngine` loads the selected content, effective roster size, and playstyle.
2. Current members resolve to their selected / stored / default legal spell combos.
3. Effective capability supply is calculated.
4. Fitness evaluates coverage, floors, headroom, overstacking, mechanics, and other modeled terms.
5. Candidate recommendations run in a **one-ahead** context (`roster + 1`) so thresholds that arm on the next body are anticipated while choosing.
6. Every candidate is evaluated with its best legal loadout.
7. Recommendation score combines exact marginal fitness, synergy, meta prior, viability, and duplicate terms.
8. `explain()` returns the per-capability deltas from the same chosen candidate kit.

Do not rewrite this flow in the dashboard layer.

## Roster size vs planned size

Owner ruling: attendance is fluid.

- The existing roster is judged at the **actual roster size**.
- `PLANNED` controls how many slots the forge aims to fill and warning/cap behavior.
- Next-pick advice runs one player ahead.

This distinction is important and should not be collapsed back to `max(planned, roster)` scoring.

## Forge and loadouts

Forge constraints are combo-aware: a weapon does not satisfy a minimum just because its flat sheet theoretically can; the selected/resolved spell combination must satisfy it.

The dashboard tracks:

- `party`
- `PROV` — manual/live vs forged provenance
- `COMBO` — explicit scored combos where stored
- `LOADOUT` — player-facing gear/spell selections

`sortPartyByRole()` applies one stable permutation across all parallel slot state and remaps live slot indexes. Any new roster mutation path must preserve that invariant.

## Evidence / provenance rules

Curated nonzero capability scores must cite equippable spells.

Generated source artifacts are provenance-checked and release fails closed on mismatches. Hashed generated artifacts must remain LF-normalized so Windows checkout cannot invalidate recorded hashes — and **every pipeline writer of a committed artifact opens with `newline="\n"`** (dataset/builds JSON and the generated dashboard pages included), so Windows rebuilds stay byte-clean instead of churning the tree with CRLF copies.

Reference build records carry source/provenance/confidence and quarantined records must never become canonical defaults.

Unknown mechanics should remain explicitly unknown rather than guessed.

## Current public How It Works page

The public explanation source is:

- `dashboard/_explainer.html`

Generated copies are:

- `dashboard/how-it-works.html`
- `docs/how-it-works.html`

The current page explains:

- party → requirements → gaps → candidates → next pick
- capability scoring instead of role scoring
- one-spell-per-slot truth
- decision-first recommendation UX
- distinction between mechanical score and evidence
- current live vs experimental roadmap

`dashboard/build.py` rewrites the two generated copies from `_explainer.html`, so keep the source authoritative.

## Recently integrated work (2026-08-22) — no open branches

PRs #1–#6 are all merged or integrated and every feature branch has been deleted (`archive/pr6-player-pools` is a local safety tag only). The last three landed as:

### PR #4 — decision-first UX (merged)

The Comp Status → Biggest Need → Best Next Pick hierarchy is the headline surface. Its regressions were repaired on `main` afterwards: the forge honesty reports moved to a full-width slot above the wheel stage (never hidden), the click-to-add alternatives render inside the pick card, and layout overrides follow the shell's own breakpoints instead of `!important`.

### PR #5 — killboard affinity (closed; evidence layer cherry-picked into `main`)

`pipeline/sample_battles.py` preserves **observed organization cohorts**: actors grouped only when the kill feed states the same Alliance (or Guild) identity, ≥2 players and ≥2 known weapons per cohort. These are **not** parties, sides, or win-rate samples. The page embeds only anonymous weapon baskets per fight-size bucket; the killboard strip turns contextual ("Observed with your weapons", ranked by matching cohorts with popularity-corrected pair lift) when cohort data matches the selected party, and falls back to the prevalence strip otherwise. The best-pick card carries an observed-context note when cohorts echo the engine's pick. Semantics: `KILLBOARD_AFFINITY.md`. A fresh sample (214 battles, 305 usable cohorts) is committed. The PR's own decision layer was deliberately **not** taken (it hid the analysis flank and fought the layout).

### PR #6 — player weapon pools + swap impact (closed; ported by hand onto the reconciled layer)

Caller tools live in a collapsed `<details>` fold below the wheel stage (owner rule: the party dock stays above the fold):

- a per-player **weapon pool** feeding `CompEngine.recommend(..., pool)`, with a best-of-pool card and runner-up mini-rank
- a **swap impact** lab comparing replacements per slot (pool-limited when a pool is set, the memoized engine swap sweep otherwise), applied through the existing `data-swapat`/`data-swapto` handler so loadout reset, provenance, prefill, and role re-sorting stay centralized

Display/workflow only; no scoring changes.

### Killboard display-bucket rule (2026-08-22 fix)

The killboard strip, prevalence footnotes, and cohort affinity key their fight-size bucket off `usageBucket()` in `dashboard/_app.js` — `2 × PLAN()`, the size the comp is **for** — not the judged roster size. A 20-man plan with 3 weapons picked must quote large-fight evidence, or the affinity strip stays invisible for the whole planning phase. Engine judgment still runs at roster size; nothing in scoring reads `sizeBucket()` anymore (H18 pins the shipped meta prior to the hand-set flat map).

## Recommended next work

The preferred product sequence is:

1. **Fight-chain explanation**
   - derive a playstyle-specific sequence from existing capability state rather than creating new scoring
   - examples:
     - clap: engage → clump → pierce → burst → secure → reset
     - brawl: contact → pressure → sustain → denial → secure
     - kite: space → slow → peel → ranged pressure → reset
   - show strong / weak / missing stages and connect the recommended weapon to the stage it improves

2. **Composition identity detection** — SHIPPED descriptive v2 (2026-08-23, from V3 finding F-V3-2 + the owner's weapon-identity model)
   - identity builds UP from members (owner ruling: a weapon's identity = its E first, then chosen Q/W, equipment, team role). `derive_style_fit` in the dataset build derives per-weapon delivery (melee / flex / ranged — flex = melee stat line whose E damage lands at range, e.g. Realmbreaker the all-rounder, DERIVED not curated) and style × size-band fit verdicts; `pipeline/style_overrides.yaml` carries cited owner rulings (Battleaxe unfit as a group pick >3); `out/style_fit_report.json` is the audit + MetaBattle review queue (Q15 ANSWERED)
   - `comp_identity()` v2 in both ports: comp label from the member fingerprint, per-member fit verdicts for the DECLARED style (style selection = build intent, owner ruling) at the current size band (trio ≤3 / gang 4–9 / group 10+); unfit members become named conflicts ("Battleaxe: its E is not a group-scale damage tool at this size"); flex weapons never read as split-identity conflicts
   - DESCRIPTIVE ONLY — no scoring path reads it (golden T23c pins that); T23/T23b/T23d pin the classifications and the two owner rulings
   - Phase C SHIPPED (2026-08-23): **style selection is build intent.** A declared style gates suggestions exactly like viability exclusions — style-unfit weapons leave `suggest_pool()`/forge/recommend in BOTH ports (never scoring; manual and locked picks score and get flagged `off_style` in swap review with replacement advice — forge F13 pins the whole contract, T24 the kit rule); the kit advisor never suggests cloth armor under a declared brawl for non-healers (owner ruling verbatim in the code); build records carry an optional validated `style:` key so canonical builds can be stored per content × style. Balanced declares no intent and gates nothing; trio sizes gate nothing.
   - next per the approved identity plan: Phase D (kill-pressure verdict: pierce + heal-cut + burst-in-window vs an enemy toughness baseline — the enemy-toughness research is delegated to the assistant, numbers land PROVISIONAL for owner tuning)

3. **Negative recommendations / redundancy warnings**
   - explicitly say when another clump weapon, healer, engage tool, etc. adds little because the comp is already saturated

4. **Slot locks / constrained reforge**
   - keep fixed players/weapons locked and optimize only flexible slots

5. **Saved player profiles**
   - persistent weapon pools for guild members rather than recreating candidate lists each session

6. **Observed composition neighbours**
   - the cohort sample is committed (214 battles, 305 cohorts); find observed cohorts similar to the current partial roster and show commonly observed completions — `KILLBOARD_AFFINITY.md` flags this as the next step and asks for review before any clustering or empirical scoring work

7. **Composition clustering**
   - discover recurring observed roster families instead of assuming every archetype manually

8. **Enemy-comp counter drafting**
   - enter/observe an enemy roster and change the *target problem* (peel, purge, cleanse, anti-heal, displacement, etc.) without hardcoding weapon counters

9. **Fight-plan generation**
   - derive a short practical sequence from the capability/loadout state, not generic AI prose

10. **Expert blind-validation workflow**
    - present partial comps without the engine answer, collect experienced callers' acceptable picks, then compare top-3 agreement

## Current validation commands

Windows development environment historically uses `py -3` rather than `python`/`python3`.

Core rebuild / gates:

```text
py -3 pipeline/evidence_lint.py
py -3 pipeline/build_builds.py
py -3 pipeline/build_dataset.py
py -3 tests/test_golden.py
py -3 tests/test_forge.py
py -3 tests/tier2_blindtest.py v4
py -3 tests/test_js_parity.py
node tests/test_loadout_codec.js
node tests/test_display_math.js
py -3 tests/test_patch_history.py
py -3 tests/test_provenance.py
py -3 tests/test_builds.py
py -3 pipeline/build_interactions.py
py -3 tests/test_interactions.py
py -3 dashboard/build.py
```

Do not assume historical test counts in this handoff are permanent; read each test's current output. The important rule is that all required gates remain green before shipping mechanics/data changes.

## Game-patch workflow

For a real Albion data patch, read `pipeline/README.md` first.

The high-level chain is:

1. update `data/source_pins.yaml`
2. fetch pinned snapshot
3. parse dumps
4. refresh item/gear data
5. rebuild interactions/builds/dataset
6. run provenance/evidence/mechanics/parity gates
7. rebuild dashboard and review artifacts
8. only refresh icons when new weapons/items require them

Never silently move the source snapshot or bypass the fail-closed provenance gates.

## Files to read before major changes

For scoring/mechanics:

- `albion-comp-engine-design.md`
- `MASTERSHEET.md`
- `MECHANICS_TODO.md`
- `engine/engine.py`
- `engine/app_scoring.js`
- `pipeline/templates/composition.yaml`
- `tests/test_golden.py`
- `tests/test_forge.py`
- `tests/VALIDATION.md`

For data/provenance:

- `pipeline/README.md`
- `data/README.md`
- `data/source_pins.yaml`
- `pipeline/build_dataset.py`
- `tests/test_provenance.py`
- `tests/test_builds.py`

For product/UI:

- `dashboard/_shell.html`
- `dashboard/_app.js`
- `dashboard/_loadout.js`
- `dashboard/_decision_layer.js`
- `dashboard/_decision_layer.css`
- `dashboard/_explainer.html`
- `dashboard/build.py`

For the companion:

- `COMPANION_SCOPE.md`
- `companion/`

## Product direction

The long-term target is not an Albion build calculator.

It is an explainable **composition assistant / virtual shotcaller** that can:

- understand what the current party is trying to do
- diagnose what it lacks
- recommend the next practical player/weapon
- explain why
- work within what real players can actually play
- show the consequences of swaps
- compare mechanical theory with observational evidence
- eventually reason about opposing compositions

Preserve the distinction between **engine truth**, **display explanation**, and **observed evidence** as the project grows.
