# Handoff — Albion Online Composition Engine

Comp Forge is an Albion Online party-composition recommendation engine and research tool, live at:

<https://sodiyal.github.io/albion-comp-engine/>

This file is the current-state handoff. `MASTERSHEET.md` is the LIVE expert control surface — its `tune:` blocks override everything at build time, so read it first for what the engine actually uses. `tests/VALIDATION.md` is the append-only ruling log: every dated round, every owner quote, every score. `albion-comp-engine-design.md`, `MECHANICS_TODO.md` and `pipeline/README.md` hold the design history, the mechanics backlog and the patch workflow. `CLAUDE.md` carries the load-bearing invariants and the one authoritative gate list. Consult them when changing mechanics, calibration, provenance, or validation. History that used to live here (PR archaeology, shipped-roadmap narrative, harvest counts) was removed 2026-09-07; `git log` and VALIDATION.md have it.

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

## Planner layout (2026-09-02)

The planner was re-laid-out for density — spec
`notes/specs/2026-09-02-dashboard-density-redesign-design.md`,
plan `notes/plans/2026-09-02-dashboard-density-redesign.md`.
Display layer only: no scoring, engine, forge or pipeline code changed, and
golden/parity carried through unchanged at every step.

- **A card grid**, four columns at ≥1700px and three from 1400px; below
  1251px the pre-redesign flow (the new column wrappers keep their card gap
  there). All layout rules moved into a new `dashboard/_layout.css`,
  inlined last so it wins on source order. Band bounds are fractional
  (`max-width:1399.98px`): integer bounds left scaled-display widths like
  1399.5px matching no band, collapsing the page to one column.
- **Edge panels.** The in-flow setup rail is gone; setup, caller tools,
  party and live party are `.epanel` flyouts on the viewport edges. One
  panel per edge on desktop, one TOTAL on phones (all sheets share the
  bottom slot); the phone tab bars are click-through outside their tabs;
  transient closes (drawer overlay) never persist; connecting the
  companion opens the live panel its feed renders into.
- **A status bar.** The masthead carries fitness, the identity verdict, and
  live style/size/content plus the forge actions — about 63px for both rows.
- **Kill pressure and role check became cards.** They previously existed
  only as lines inside the radar's hover tooltip; both surfaces now read the
  same model, and both remain descriptive (golden proves it).
- **Capability supply became nested rings**, faceted one panel per group,
  on the same soft-cap ruler as the bars and the radar.
- The pick card split into diagnosis / fight chain / the pick, and its gain
  rows absorbed the verdict that a second box used to repeat.

Gate: `py -3 tests/test_dashboard_layout.py` (contracts L1–L18, popover
lifetime, phone rail, band gap, honesty mirror; `test_display_math.js`
sweeps the ring geometry with source-extracted constants).

## The kit audit and the style × size rows (2026-09-03 → 09-05)

The rulings that came out of this stretch are invariants now (CLAUDE.md:
"Identity halves are derived facts", "Style x size rows sit BESIDE the
content templates", "Kits are what winners wear", "One role read"). The
full record — every round's scores, board tallies, harvest counts — is
VALIDATION.md "THE KIT AUDIT", "Style x band rows", T34–T41, R24–R28.
What a reader of this file needs:

- **The harness.** Owner: "judge 10 random weapons using the data we have
  for what people really wear vs what the engine gives ... build fixes
  until the engine agrees." R24 pins killboard modal item per slot vs the
  forge's v0 kit at ≥ 85% agreement. The evidence UNIT is the KILLER PARTY
  (parties of 10+ only — gank kits inside big battles were polluting
  doctrine), the VOTER is the player (R27), and doctrine ships in two size
  bands, group and gang (R28).
- **The harvest is an OVERNIGHT TASK**: `pipeline/harvest_overnight.ps1`,
  Windows scheduled task "CompForge overnight harvest", daily 03:00. It
  only harvests; rebuild + gates + audit + commit stay in-session. Rerun
  order after a harvest: `sample_parties` -> `audit_style_rosters` ->
  `derive_style_bands` -> `build_dataset` -> gates. Because the corpus
  grows nightly, tests pin MECHANISMS, never exact counts.
- **The style × size ruling** ("ok do it", four parts — VALIDATION.md):
  `derive_style_bands.py` GENERATES `templates/style_bands.yaml` from the
  labelled-roster board; `set_content` reads the band for a declared style
  at 10+ after the content row. Never hand-edit the yaml, never fill a thin
  cell. Validation fixtures are judged DRESSED (T38).
- **Identity rulings in the owner's words** (all derived, never weapon
  lists): the kite half is standoff tools; flex bombs join the rigid core;
  the ball carries the bomb; "grailseeker can be kite or d tank. accept"
  (root fields laid at range are standoff tools; Grailseeker's
  harvest-admitted leather stands, Incubus is the off-role pin); leather
  dps are melee and brawl, clap is cloth, the exception is a secondary bomb
  squad in Assassin Jackets (leather-majority dps overrule a
  weapons-decided clap, bomb squads exempt); a chest votes by its ITEM lean
  first (`out/chest_lean.json`), the class rule where it has none.
- **Open for the owner:** a gank read for non-ZvZ killer parties (round 2
  roster 9; round-4 roster 3 was called "gank" too); the 20+ band once the
  harvest can stand it; blind round 4 (`notes/findings/2026-09-05-style-roster-evidence.md`)
  is only partially graded.

## Owner bug round (2026-09-03)

Five reported defects, all reproduced and fixed (VALIDATION.md carries
the full record): the biggest-need row was measured on the naked roster
while the pick and the radar read the worn kits (display layer now
passes `GEARS_CUR` everywhere); every two-hander was dressed with an
off-hand (the dataset now carries the dumps' `two_handed` fact and
`kit_options` drops the slot in both ports); three role classifications
disagreed (board column = seat, tile colour = role_hint, forge bands =
role_class) — `role_class` now derives from the primary SEAT's class in
both ports, and the page colours/sorts from the same seat; Occult Staff
re-seated from dive_cleanup to zone_support (owner: "support weapon like
occult"); "reforge all" reports "Unchanged" when the deterministic
search returns the same roster instead of silently re-rendering it.

**Open for the owner:** melee instant-payload weapons (Spiked Gauntlets,
Realmbreaker) still generate into clap dps under the standing
conditional-payload ruling. (The `test_cohort_families.py` canary was
re-pinned 2026-09-07 to a mechanism — the large bucket carries >= 3 families,
no bucket more than its cohorts support — and the families artifact regenerated
from the current sample.)

## Current engine model

The standing rulings behind the model, each with where its record lives:

- **The DRESSED FORGE** (2026-08-27, spec `notes/specs/2026-08-27-dressed-forge-design.md`):
  forge and recommend evaluate every candidate as weapon + combo + doctrine
  kit, priced by the exact comp score the page displays; forged members
  arrive with kits prefilled (`_eng`-marked); the page passes LOADOUT gear
  into every scoring/suggestion call. Locked members are never re-dressed
  (Ruling 5, F25/F26); doctrine passives never enter evaluation.
- **The five 2026-08-27 rulings** (VALIDATION.md): Option C structural
  floors (hard floors read WEAPON+LOADOUT supply everywhere; worn gear
  counts toward coverage/headroom/overstack, never a floor — V5 pins it);
  locked-gear preservation; synergy is WEAPON-INTERACTION synergy
  (scoring.yaml rule 3); round-2 blind forms committed; the V4 gate deferred
  and later re-based to `actual_gear` role-level 70%, enforcing.
- **The conditional-payload rule** (2026-08-27/28): clap trades leather
  tankiness for damage that lands from ONE action, so a group damage
  carrier whose every damage E is ramp-dependent or a non-ranged channel
  reads situational at clap/kite/clap_kite (Clarent, Carving, Ursine, Rift
  Glaive — Rift Glaive later derived back via `ramp_free`). T32/T33.
- **Six capabilities promoted** the same day (`slow`, `root`,
  `knockback_displace`, `anti_dive`, `interrupt`, `max_health_cut`): rows
  only where real comps supply the measurement — castle and faction_war
  have none and were left unscored on purpose.
- **The effect catalogue covers GEAR** (194 gear actives/passives beside
  367 weapon spells), which is how Demon Armor's backwards `tankiness`
  claim was caught and how `reveal` was refused.
- **The display ruler**: radar and capability board measure against the
  comp-fitted CEILING (soft cap); nothing reads above 100%; the target
  minimum is a brass tick. Scoring untouched.
- **THE UNIT RE-FIT** (owner: "go ahead", 2026-08-29): targets and soft
  caps speak PERSON units — 152 rows moved together. Two standing rules: a
  unit conversion can only ever RAISE a target, and hard floors stay in
  WEAPON units. Method and the three approaches that failed first:
  VALIDATION.md "THE UNIT RE-FIT". The residual is a calibration question
  (median coverage 1.82 where ~1.0–1.3 would be ideal — the safe
  direction), which needs expert blind rounds, not another rescale.

The production engine currently includes:

- 137 combat weapons
- 31 capability dimensions, every one scored by at least one content template (a single template scores a subset — blackzone_roam scores 30, omitting `self_sustain`). `reveal` remains PROPOSED-ONLY: not curated on any sheet, not scored anywhere, with the refusal evidence written into `effect_map.yaml`.
- content-specific templates, plus GENERATED style × size rows beside them
- playstyle weight modifiers
- adaptive party-size targets
- hard floors for load-bearing requirements (weapon+loadout basis)
- diminishing returns and headroom
- overstack penalties
- capability synergies (weapon-interaction only)
- duplicate handling, including the one verified super-additive case (`self_cost_offset_min_copies`)
- viability exclusions / priors
- Focus Fire / Resilience mechanics where modeled
- per-weapon Resilience Penetration (cited wiki table wired as a supply-side rebate on the single-target Focus-Fire tax)
- geometric AoE escalation for relevant utility
- one-spell-per-slot loadout resolution
- combo-aware forge constraints
- constrained composition generation / forge, dressed
- forge-quality generation gates (below)
- swap review
- the role layer (roles-design.md): an evidence-cited role book, per-weapon role MENUS derived E-first, kit-aware role detection and the descriptive role advisory in both ports; the kit advisor is DOCTRINE-LED, OBSERVED-BUILD-LED and FAIL-CLOSED — every doctrine reader goes through `_seat_kit` (group band at 10+, gang band at ≤ 9); carrier chests are a comp-level CARRIER QUOTA, never weapon identity
- NEED PROFILES gating the forge (roles.yaml `need_profiles`, owner-ruled 2026-08-26 after a blind round + the killboard roster evidence): fine-seat bands + function coverage, armed at 15+, scaled by size/20; clap/clap_kite require a 7-strong ranged-AoE core at 20. Generation-only — manual parties always score; F21
- the descriptive analyzer family: `comp_identity`, `kill_pressure`, `fight_chain`, `pick_report`, `analyze` bands, `duplicate_conflicts`, `detect_role`/`role_advisory` — none a scoring input
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

Killboard prevalence, observed pairings, reference comps, build sources, and expert results are evidence layers. They should not silently alter mechanical recommendation ranking unless a future calibration decision explicitly promotes them into scoring and is validated. Semantics, limitations and the mount-carrier caveat: `KILLBOARD_AFFINITY.md`.

Popularity is not effectiveness.

**Killboard display-bucket rule (2026-08-22):** the killboard strip, prevalence footnotes, cohort affinity, neighbours and families key their fight-size bucket off `usageBucket()` in `dashboard/_app.js` — `2 × PLAN()`, the size the comp is **for** — not the judged roster size. Engine judgment still runs at roster size; nothing in scoring reads `sizeBucket()` (H18 pins the shipped meta prior to the hand-set flat map).

## Current live UX on `main`

The planner leads with:

- **Comp Status — THE RADAR** (owner pass 2026-08-26/27): the status card *is* a diagram. One axis per capability GROUP measured against the comp-fitted CEILING, so nothing reads above 100% and playstyle tradeoffs show as shape; a brass tick per spoke marks the target minimum; vertices carry state (pink below a hard floor, purple over-ceiling). The hollow centre renders `comp_identity` verbatim. **Everything textual lives in hovers**; the card carries no explainer prose and no fitness number of its own.
- **Biggest Need** — hard-floor failures outrank softer deficits
- **Best Next Pick** — prominent weapon recommendation, score, role/function, and engine-derived explanation
- **What it fixes** — strongest marginal capability gains
- **Still weak after this pick** — recalculated one slot ahead using the candidate's scored combo
- **Comp identity** — the playstyle the party is becoming (brawl / clap / kite / brawl-clap / clap-kite / bomb squad / mixed), with per-member fit verdicts and named misfit conflicts, descriptive only
- **Kill pressure** — the three-light checklist (pierce · heal-cut · burst vs the comp-fitted targets), descriptive only
- **Fight chain** — the pick card's stage strip (the fight as the playstyle sequences it, stages graded strong/ok/weak/missing) with the pick connected to the stage it strengthens; every stage carries `sources` (the equipped spells that ARE the stage) and `improves` names its per-cap `terms`
- **Role check** — the fine-role tally read from weapons + worn kits, primary-function and carried-aura chips, and the advisory flags ("no engage tank — nobody makes a clump"), descriptive only
- **Negative recommendations** — `pick_report()`'s signed decomposition: a "why not" block on the pick card, redundant alternatives dimmed, roster members chipped "jobs covered without it"; verdict rule `_pick_verdict` (negative = marginal ≤ 0; redundant = zero gap-closing gain, threshold `mechanics.yaml negative_recs.redundant_gain_max`)
- **Observed killboard context** — the contextual affinity strip, the pick card's observed-cohort note, observed composition neighbours, the recurring observed cores (anchor-pair families, `out/cohort_families.json`), and the **observed effect quotas** line — all display evidence only
- **Caller tools** — per-player weapon pools feeding `CompEngine.recommend(..., pool)` and the swap-impact lab, applied through the central `data-swapat`/`data-swapto` handler
- **Live party** — the companion feed with **live sync**: after a load, weapon swaps update slots in place, newly visible weapons fill in, members' real Q/W picks and worn kits flow into the loadouts, and an in-game inspect refreshes any member on demand (2026-09-06)

Layout (owner passes 2026-08-23, 2026-08-27, then the 2026-09-02 density redesign above): the forge honesty reports (`#warn-slot`) are placed per width band by `_layout.css` (beside the kill-pressure card at four columns, a full-width row at three) — never hidden. The old right-hand fitness / weakness / recommendation stack is intentionally hidden. The full capability board remains the deep diagnostic layer on the same ceiling ruler as the radar.

**THE WHEEL IS A SEMICIRCLE AND THE PARTY STRIP IS GONE** (owner 2026-08-27): frameless weapon art rides the TOP ARC of a virtual `--wd` circle, the hub floats in the arc's open mouth, drag-to-rotate derives the centre from the box WIDTH. The **comp board** REPLACED the `ws-party` strip entirely and now lives in the right-edge party flyout: four main-role columns (Tank / Support / DPS / Healer, from `roleAdvisory`), each member a full `dm` tile sharing THE member popover (`memberPop()`, shared by construction), open slots as a dashed brass column, duplicate checks and the kit editor in a notes rail under the board. The board is built in `renderRoster` and cached (`BOARD_HTML`), so wheel spins never pay for the roster analysis.

Source files:

- `dashboard/_decision_layer.js`
- `dashboard/_decision_layer.css`
- `dashboard/_app.js`
- `dashboard/_loadout.js`
- `dashboard/_layout.css`
- `dashboard/_shell.html`
- `dashboard/build.py`

## How recommendations are computed

At a high level:

1. `CompEngine` loads the selected content, effective roster size, and playstyle.
2. Current members resolve to their selected / stored / default legal spell combos.
3. Effective capability supply is calculated.
4. Fitness evaluates coverage, floors, headroom, overstacking, mechanics, and other modeled terms.
5. Candidate recommendations run in a **one-ahead** context (`roster + 1`) so thresholds that arm on the next body are anticipated while choosing.
6. Every candidate is evaluated with its best legal loadout, dressed in its doctrine kit.
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

### Forge-quality rules (expert rounds 2026-08-23/25) — every miss a mechanism

Blind grading rounds with the owner converted every complaint into a structural rule (full log + verbatim rulings: `tests/VALIDATION.md`; pins F14–F19, T27–T29, T31):

- **Economics — RETIRED 2026-09-07.** The 2026-08-23 crystal cost gate is gone ("remove the cost gate for weapons ... focusing on mechanics"): every cost tier is in every pool, `cost_tier` is a display fact only. What the gate was covering for — the Exalted Staff, sole `anti_zone` supplier, forged into everything — is now the `anti_zone` rows' physics: no row at the 7-man contents (no 7-man comp fields it; 2% of 4-9 man winners do), size-scaled everywhere else (32% of 20+ winners). Measured: no Exalted in any default 7-man forge, present from 10 up. T42 / F14.
- **Healing foundation** (`primary_healer` + derived `full_healer`/`heal_scale`): band minima require healers whose E heals BIG and heals a GROUP — both derived from the E bundle + the spell's own area facts (`heal_overrides.yaml` carries cited sub-effect corrections). Single-ally-heal-E healers never generate at 10+.
- **Style-aware role bands** (`styles.yaml constraint_overrides`): owner-ruled healer/frontline counts per style (20-man healers: brawl 3-4 / clap 2-3 / kite 2 / clap_kite 3-4; kite@7 = 1; brawl frontline capped at blap's 5).
- **Generation-fit gate** (both ports): a DEFAULT generated comp fields damage picks whose derived verdict is **fits**. "Situational" is caller territory: manual picks score, never flagged.
- **Duplicates earn their place**: generation default is 1 copy at every size; a second copy only through a per-weapon allowance citing a real comp.
- **Derived job budgets** (`composition.yaml derived_groups` → build-time membership, no hand lists): `clump_core` max 2; `curse_pressure` max 2.
- **First verified non-stacking scoring record**: CURSEDOT — the curse Q's sustained_dps counts once per party.
- **Non-stacking slots are earned**: a member of a derived non-stacking group earns a group-band slot only with an E enemy-DEBUFF tool ≥ 4. Damnation, Lifecurse and Rotcaller earn ("the only curse weapons in any party bigger than 15"); the rest demote to situational at group and leave 10+ generation. F19 pins it.
- **The two-prong E rule** (round 7): prong-1 fact fixes with dump citations (Battle Bracers' Falcon Smash AoE restored; Warbow / 1H Fire / Hellspawn owner-ruled solo-class via cited overrides) + the derived `weak_group_e` demotion (low E damage AND no real E tool → trio-class). Spirithunter PROMOTED to clap/clap_kite ("massive pierce that enables the whole dps line"); Trinity Spear OUT of large-scale generation ("never the main weapon in party" — auto-attack steroids are not large-scale utility). T31 family.
- **Need profiles** (2026-08-26, above): fine-seat bands + function coverage riding the same predicate machinery.

Audit artifacts: `out/economics_report.json`, `out/style_fit_report.json` (`e_debuff_max` / `nonstack_member` per weapon), `out/roster_mixes.json` (the killboard roster-mix evidence behind the need profiles), derived group membership printed at dataset build.

The dashboard tracks:

- `party`
- `PROV` — manual/live vs forged provenance
- `COMBO` — explicit scored combos where stored
- `LOADOUT` — player-facing gear/spell selections

`sortPartyByRole()` applies one stable permutation across all parallel slot state and remaps live slot indexes. Any new roster mutation path must preserve that invariant. The forge handler wraps `ENG.forge(goal)` in a target-size `setContent` — the engine is judged at roster size, but a 2-member roster forging to 20 must search under 20-man rules, not trio rules.

## Evidence / provenance rules

Curated nonzero capability scores must cite equippable spells.

Generated source artifacts are provenance-checked and release fails closed on mismatches. Hashed generated artifacts must remain LF-normalized so Windows checkout cannot invalidate recorded hashes — and **every pipeline writer of a committed artifact opens with `newline="\n"`** (dataset/builds JSON and the generated dashboard pages included), so Windows rebuilds stay byte-clean instead of churning the tree with CRLF copies.

Reference build records carry source/provenance/confidence and quarantined records must never become canonical defaults.

Unknown mechanics should remain explicitly unknown rather than guessed.

## Current public How It Works page

The public explanation source is `dashboard/_explainer.html`; generated copies are `dashboard/how-it-works.html` and `docs/how-it-works.html`. `dashboard/build.py` rewrites the two generated copies from the source, so keep the source authoritative.

## Open work

Shipped roadmap items are one line each; their records are in VALIDATION.md and the golden pins named there.

- ~~Fight-chain explanation~~ — shipped 2026-08-23 (T26 family).
- ~~Composition identity detection~~ — shipped descriptive v2 2026-08-23 (T23 family, F13); identity-aware *scoring* stays parked until more blind rounds validate the labels.
- ~~Negative recommendations~~ — shipped 2026-08-24 as `pick_report()` (T30 family; Q18's scoring-side penalty stays rejected).
- ~~Observed composition neighbours~~ and ~~anchor-pair families~~ — shipped 2026-08-24, display only (`KILLBOARD_AFFINITY.md`; empirical/scoring integration REMAINS PARKED behind an owner ruling).
- ~~The role layer, increments 1 / 2 / 2.5 / 3~~ — shipped 2026-08-25/26 (roles-design.md); then FAIL-CLOSED generation, THE SEAT-ALL PASS, KILLBOARD KIT DOCTRINE, the OBSERVED-BUILD OVERLAY, carrier quotas, one-player-one-vote and size bands (2026-09-01 → 09-04; R19–R28). Owner directives in their words: "yes its the whole build ... include food, potion and capes and you are right about passive defaults"; "what matters is what the data says"; "lets fix seat for all weapons"; "base it on seen evidence from the data we harvested from all the battles"; "gear each seat is wearing should be based on what real people wear; the engine keeps making up random builds".
- ~~The unit re-fit~~ — done 2026-08-29.
- ~~The E-audit~~ — ran 2026-08-24 (T31d); Fists of Avalon and Trinity Spear ruled; Evensong resolved 2026-08-25.

Still open, by track:

- **Role layer**: increment 3b (effect-quota-aware kit allocation + mechanism pairing rules for effect carriers), increment 4 (uptime economics); Chillhowl/Stillgaze (`2H_SHAPESHIFTER_CRYSTAL`) and Iron-clad stay off every menu pending an owner word.
- **Identity**: the gank read for non-ZvZ killer parties; the 20+ band; blind round 4 grading; melee instant-payload weapons generating into clap dps (bug round above).
- **Calibration**: the targets remain conservative (good comps over-cover ~1.8×); sharpening needs expert blind rounds (`calibration/README.md` discipline). Watch items: Hellfire under clap_kite, castle-25's saturated tail quality.
- **Mechanics**: `MECHANICS_TODO.md` (per-spell `burst_aoe` escalation gating, Q2/Q5/Q11/Q13, the PASV and TOP magnitude queues).
- **Companion**: incremental mid-fight join/leave; the inspect response shape confirmed on a live run (`companion/README.md`).
- **Product** (owner-deprioritized until comp quality satisfies): slot locks / constrained reforge; saved player profiles; enemy-comp counter drafting; fight-plan generation; the expert blind-validation workflow as a tool.

## Current validation commands

Windows development environment uses `py -3` rather than `python`/`python3`.

Core rebuild / gates: the authoritative list is `CLAUDE.md` ("Tests" and "Build chain") — one list, kept current there.

The effect catalogue is NOT part of a normal build — it reads the pinned dumps
directly and is regenerated only when the snapshot moves or its extraction
changes (it covers gear as well as weapons):

```text
py -3 pipeline/effect_catalogue.py pipeline/out/dumps_cache/<commit> [--report]
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
- `pipeline/templates/styles.yaml` (playstyles, weights, mechanics params, fight-chain stage data)
- `pipeline/templates/style_bands.yaml` (GENERATED — never hand-edit)
- `pipeline/style_overrides.yaml` (owner rulings on weapon style fit)
- `roles-design.md` + `pipeline/roles.yaml` (the role layer: seats, functions, gear effects)
- `tests/test_golden.py`
- `tests/test_forge.py`
- `tests/test_roles.py`
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
- `dashboard/_layout.css`
- `dashboard/_explainer.html`
- `dashboard/build.py`

For the companion:

- `COMPANION_SCOPE.md`
- `companion/README.md`
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
