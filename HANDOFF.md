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

## Planner layout (2026-09-02)

The planner was re-laid-out for density — spec
`docs/superpowers/specs/2026-09-02-dashboard-density-redesign-design.md`,
plan `docs/superpowers/plans/2026-09-02-dashboard-density-redesign.md`.
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
  same model, and both remain descriptive (golden 59/59 proves it).
- **Capability supply became nested rings**, faceted one panel per group,
  on the same soft-cap ruler as the bars and the radar.
- The pick card split into diagnosis / fight chain / the pick, and its gain
  rows absorbed the verdict that a second box used to repeat.

New gate: `py -3 tests/test_dashboard_layout.py` (contracts L1–L18; the
2026-09-02 review round added L15–L18 plus popover-lifetime, phone-rail,
band-gap and honesty-mirror contracts, and `test_display_math.js` now
sweeps the ring geometry across every group size with source-extracted
constants instead of a hand copy).

## Current engine model

**2026-08-27 — the DRESSED FORGE shipped** (spec `docs/superpowers/specs/2026-08-27-dressed-forge-design.md`): forge and recommend evaluate every candidate as a full build — weapon + combo + doctrine kit (v0 + one divergent variant) — priced by the exact comp_score-with-gears the page displays, and forged members arrive with their kits prefilled (`_eng`-marked). The same day closed two adjacent gaps: the page now passes equipped LOADOUT gear into every scoring/suggestion call (the engine had scored full builds since 2026-08-20; the UI never sent them), and the gear capability catalog was completed (129 curated pieces, `sheets/gear/combat_expansion.yaml`). Owner rulings: kit suggestions are doctrine-tier-first in both modes (evidence-first, T22 re-pin), T30c re-pinned dressed with a naked-party honesty rider. Locked members are never re-dressed; doctrine passives never enter evaluation.

**2026-08-27 (same day, follow-up pass) — DRESSED VALIDATION & CALIBRATION HARDENING** (plan `docs/superpowers/plans/2026-08-27-dressed-validation-calibration.md`; findings `docs/superpowers/findings/2026-08-27-*.md`; VALIDATION.md carries the dated entry + open rulings): the validation/calibration layers were re-based onto the dressed engine BEFORE any tuning. The audit found every historical V3/V4 number was an asymmetric hybrid (naked incumbents vs dressed candidates). Shipped, with zero scoring changes: `Engine.set_dressing(False)` (both ports, parity-pinned — the V3-W symmetric weapon-only mode), V3-D production-dressed scoring with the richer expert form + full metric set, V4 in three incumbent-gear classes (legacy gate unchanged; actual-gear kits joined from builds_index — published comps carry gear on all 201 slots), the dressed template audit, the adversarial frontline-floor audit, the gear-synergy audit, 16 gear blind cards, and the `calibration/` train/validation/holdout layer + `pipeline/calibrate_scoring.py` sensitivity harness. HEADLINE MEASUREMENTS: dressed incumbents collapse V4 role-level 78%→34–41% (11 of 12 lost hits are tank drops); worn-armor tankiness adds +419–622% of target everywhere and ordinary doctrine kits alone clear the tankiness hard floor for a no-tank 7-man — the 2026-08-12 pseudo-tankiness failure recreated through the gear stat channel (representation problem; Options A–D written, Option C source-aware floors recommended, OWNER RULING PENDING). Synergy stays weapon-only by recommendation (gear participation would move real comps negatively under the current J rule). Every coefficient remains at its shipped value, PROVISIONAL — the calibration report is a sensitivity map (train n=4; validation/holdout empty until fresh expert rounds).

**2026-08-27 (third pass, same day) — THE FIVE RULINGS LANDED** (VALIDATION.md carries the full record): **Option C structural floors** shipped in both ports — hard floors read the WEAPON+LOADOUT supply everywhere (fitness, every marginal, pick_report, explain, dashboard floor tags); worn gear still counts toward coverage/headroom/overstack but can never satisfy a structural floor, and a candidate's kit can never buy floor relief (V5a–V5f pin it; naked paths bit-identical; 2 V4 tank-drop slots recovered → actual_gear role 47%; the remaining dressed shortfall is the saturation/calibration question). A pre-existing forge pruning blind spot found en route (band-stranded predicate minima killing the beam) is fixed with per-predicate capacity gates in `_forge_feasible`. **Ruling 5**: `forge(locked_gears=)` preserves supplied lock kits verbatim (never re-dressed, never invented) and `refine(gears=)` runs the dressed local search returning `{party, gears}` (legacy calls bit-identical) — F25/F26. **Ruling 3**: synergy documented as WEAPON-INTERACTION SYNERGY (scoring.yaml rule 3). **Ruling 4**: round-2 blind forms committed (`tier2_form_r2_castle7.md`, `tier2_form_r2_blackzone20.md`; forms carry FORM_CONTEXT; gear cards regenerated). **Ruling 2**: the V4 exit gate deliberately stays on weapon_only role-level until the owner picks the dressed gate post-fix.

**2026-08-27/28 (fourth pass) — THE TAXONOMY AND THE DISPLAY RULER.** Four things landed after the merge, all owner-ruled:

1. **Conditional-payload rule** (VALIDATION.md, the comp-status radar round). The radar surfaced a forged clap reading "split identity" at 59% melee — the forge had filled the clap's ranged-AoE core with melee-stat FLEX bruisers, which the predicate legitimately admits. The owner rejected a delivery-category fix and ruled on job difficulty instead: clap trades leather tankiness for damage that lands from ONE action. Wired fully derived: `parse_dumps` gains a structural `channel` fact; `derive_style_fit` demotes a group damage carrier to situational at clap/kite/clap_kite (gang+group) when EVERY damage E is ramp-dependent (consumes charges other spells build) or a non-ranged channel. Exactly four weapons flip (Clarent, Carving, Ursine, Rift Glaive); brawl keeps them all. Kite additionally gained `ranged_aoe_core` min 5 at 20 / 4 at 15-19, fitted from the one real kite 20-man. T32/T33 pin both.
2. **Six capabilities promoted** — `slow`, `root`, `knockback_displace`, `anti_dive`, `interrupt`, `max_health_cut` were curated on every sheet and used by the fight chain, but NO template scored them, so fitness weighted them zero (an AoE root earned nothing). Fitted from the real comps by the standing 0.9x/1.15x convention in the SAME weapon+spell-pick unit as the existing rows; weight 1 low-and-flat start. Honest gaps recorded rather than invented: castle and faction_war get no rows (zero comps in the corpus), castle_outpost no max_health_cut, and roads (single comp) borrows the multi-comp median spread for its ceilings. blackzone now scores 30 items, weight 121.5 -> 127.5.
3. **The effect catalogue covers GEAR** — it indexed weapon spells only (367), so every gear-sheet claim rested on prose + overrides and the lint could check none of them. Now 194 gear actives/passives are indexed too (559 total), with `gear_lines` counts and gap reports spanning both sources. The first run failed with six grounded errors, all adjudicated against the newly visible structured effects — including **Demon Armor's `tankiness`, which was backwards**: its aura buffs ALLIES' resistances while REDUCING the wearer's own. Gear sheets: 6 errors + 34 unverifiable warnings -> 0 errors, 5 warnings. Also curated in the same pass: **Defensive Slam** (a Q on five maces granting +0.15 resistances AND +0.15 CCR to 10 allies) had never been cited at all. `reveal` was investigated and deliberately REFUSED (every weapon source is a purge spell — invisibility is a buff — and the only two non-purge sources are gear the catalogue then couldn't ground); the "reduce enemy CC resistance" capability was RETRACTED (no such effect: what exists is a per-spell ignore-CCR flag on 54 spells, a quality shaped like `resil_pen`).
4. **The display ruler** — both the comp-status radar and the capability board now measure against the comp-fitted CEILING (soft cap), not the target: 100% is "the most any good comp fields", per-cap supply counts only up to its own ceiling so nothing can exceed 100, over-ceiling stacking shows as the purple marker, and the target minimum rides as a brass tick. Scoring untouched; only what the display quotes changed.

**RESOLVED 2026-08-29 — THE UNIT RE-FIT SHIPPED** (owner: "go ahead"). Targets and soft caps now speak PERSON units: 152 rows across all six templates moved together. tankiness coverage on real comps fell from 4.2-6.6x target to 1.19-2.12x, and the blind gate's dressed classes rose from 26%/57% to 87%/87%. The full method — including three approaches that failed first — is in VALIDATION.md "THE UNIT RE-FIT". Two outcomes worth carrying: (1) a unit conversion can only ever RAISE a target, since gear adds supply and never removes it, so any factor below 1 is a recalibration claim rather than a unit fix (twelve were clamped; without the clamp burst_st's target fell 47% and silently priced a real synergy at zero); (2) only 13 of 29 capabilities moved, all of them gear-fed — the other 16 were already correct in person terms, so the defect was narrower than the statement below assumed. Blocking decision (a) was answered by fitting on the OWNER-VETTED comps only, which sidesteps the kit-fill problem; (b) was answered by the fight-chain re-pin — a naked roster now reads weak, correctly, and the production path dresses members in doctrine kits. The original statement is kept below for the record.

**[HISTORICAL — the problem as it stood before 2026-08-29.]** Every reference number (targets AND soft caps) was measured counting WEAPONS. The engine and both charts now measure whole PEOPLE (weapon + worn kit), which is ~1.88x weapon-only across all audited comps and far more on gear-heavy rows. Measured against the same real comps re-read as people, the numbers would become: tankiness need 6.9 -> 49.1 / ceiling 10.1 -> 86.1; sustained_dps 10.8 -> 45.6; buff_allies 2.5 -> 10.2; while catch and ranged_presence barely move (gear supplies neither). Option C floors are unaffected (they read the weapon+loadout basis by ruling). TWO DECISIONS BLOCK THE RE-FIT: (a) which comps qualify as evidence — gear records run 100%/103%/102%/84% kit fill on four comps but blap is 71.7% and the Deadlyhooker parties 51-60%, and since target = 0.9x the LEAST, an under-recorded comp drags the number down for a recording gap rather than a real one; (b) what a comp with no kit set should read — person-sized numbers make a naked roster read catastrophically low (correctly, but unusably), so the app likely needs to assume the role's doctrine kit when none is set (the dressed forge already dresses what it builds, so this is wiring, not invention). Do not re-fit rows piecemeal: the unit correction must move every row at once or the templates end up in mixed currencies.

The production engine currently includes:

- 137 combat weapons
- 31 capability dimensions, every one now scored by at least one content template (a single template scores a subset — blackzone_roam scores 30, omitting `self_sustain`). `reveal` remains PROPOSED-ONLY: not curated on any sheet, not scored anywhere, with the refusal evidence written into `effect_map.yaml`.
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
- per-weapon Resilience Penetration (2026-08-25: cited wiki table wired as
  a supply-side rebate on the single-target Focus-Fire tax — dagger-class
  pen keeps more ST value at scale, never enough to make ST good)
- geometric AoE escalation for relevant utility
- one-spell-per-slot loadout resolution
- combo-aware forge constraints
- constrained composition generation / forge
- forge-quality generation gates (2026-08-23/25 expert rounds): crystal
  economics gate, primary-healer foundation minima, style-aware role bands,
  the generation-fit gate (only "fits" damage picks generate), duplicates
  that must earn their place, derived job budgets (clump core, curse
  pressure), the first verified non-stacking scoring record (CURSEDOT),
  and earned non-stacking slots (a group-band curse slot needs a debuff-E:
  Damnation / Lifecurse / Rotcaller)
- swap review
- the role layer (2026-08-25/26, roles-design.md — increments 1, 2,
  2.5 and 3 shipped): an evidence-cited role book (19 roles: SEAT roles
  with gear uniforms, FUNCTION roles — pierce / purge / shield_break /
  anti_heal — that ride along with any seat, and a typed gear_effects
  catalog), per-weapon role MENUS derived E-first across all 137
  weapons, equipment classified by the unique-ability-first law,
  kit-aware role detection and the descriptive role advisory in both
  ports and the status card. The kit advisor is DOCTRINE-LED (increment
  2): chest hard-gated to the seat uniform, every other slot ranked
  from pools mined out of the seat's real reference builds, passive
  doctrine resolved from the dumps — and PER-WEAPON (increment 2.5):
  a weapon's own observed kit outranks the seat aggregate with honest
  sample sizes, while effect-carrier chests (Demon/Judicator/Guardian/
  Royal/Hellion) are comp-level allocations, quota-mined per observed
  roster and advised on the page, never counted as weapon identity.
  The full board was owner-graded 2026-08-26 (15 rulings — R17) with
  cited override layers for kit pools (`kit_doctrine.overrides`, seat
  and weapon scope) and gear affinity (`gear_affinity_overrides`);
  increments pending: 3b (effect-quota-aware kit allocation +
  mechanism pairing rules), 4 (uptime economics)
- NEED PROFILES gate the forge (increment 3, owner-ruled 2026-08-26
  after a blind round + the evidence pass — 8 curated rosters, 139
  near-complete killboard fight rosters via `pipeline/sample_rosters.py`
  → `out/roster_mixes.json`, Wardergrip's guide): fine-seat bands
  (engage 2-3 / stopper 1-2 default, stopper-heavy as the
  territory-defense override, off-tank ≤1, shield support 1-3, zone ≤1)
  plus function coverage (pierce ≥1, heal-cut ≥1), armed at 15+ and
  scaled by size/20; clap/clap_kite additionally require a 7-strong
  ranged-AoE core at 20. Generation-only — manual parties always
  score; F21 pins the contract in both ports
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

- **Comp Status — THE RADAR** (owner pass 2026-08-26/27): the status card *is* a diagram. One axis per capability GROUP (the `GROUPS` taxonomy, "Other" guard included) measured against the comp-fitted CEILING, so nothing reads above 100% and playstyle tradeoffs show as shape; a brass tick per spoke marks the target minimum; vertices carry state (pink below a hard floor, purple over-ceiling). Axis icons wear the app's role palette, re-stepped where the colorblind validator demanded. The hollow centre renders `comp_identity` verbatim — playstyle glyph + label, dashed ring while "leaning", solid when strong, amber warn dot when conflicts or role flags exist. **Everything textual lives in hovers**: each axis opens its per-capability breakdown; the centre opens status triage, exact fitness, the kill-pressure lights, the role tally and every advisory flag. The card carries no explainer prose and no fitness number of its own.
- **Biggest Need** — hard-floor failures outrank softer deficits
- **Best Next Pick** — prominent weapon recommendation, score, role/function, and engine-derived explanation
- **What it fixes** — strongest marginal capability gains
- **Still weak after this pick** — recalculated one slot ahead using the candidate's scored combo
- **Comp identity** — the status card names the playstyle the party is becoming (brawl / clap / kite / brawl-clap / clap-kite / bomb squad / mixed), with per-member fit verdicts and named misfit conflicts, descriptive only
- **Kill pressure** — the status card's three-light checklist (pierce · heal-cut · burst vs the comp-fitted targets), descriptive only
- **Fight chain** — the pick card's stage strip (the fight as the playstyle sequences it, stages graded strong/ok/weak/missing) with the pick connected to the stage it strengthens
- **Role check** — the status card's roles line (2026-08-25): the fine-role tally read from weapons + worn kits, primary-function and carried-aura chips, and the advisory flags ("no engage tank — nobody makes a clump"; a member whose chest fights their role's uniform), descriptive only
- **Observed killboard context** — the contextual affinity strip, the pick card's observed-cohort note, the recurring observed cores, and (2026-08-26) the **observed effect quotas** line — the roster's set chests counted against the median effect carriers near-complete observed rosters field (PLAN-scaled, armed 15+, unknown gear never claims a shortfall) — all display evidence only
- **Caller tools** — the player-pool and swap-impact fold, collapsed by default
- **Live party** — the companion feed (live-verified 2026-08-23) with **live sync**: after a load, weapon swaps update slots in place, newly visible weapons fill in, and members' real Q/W picks flow into the loadouts

Layout (owner passes 2026-08-23, then 2026-08-27): the forge honesty reports (`#warn-slot`) live **under the wheel** — the wheel column's next row on the hero grid, right after the stage on stacked layouts — still never hidden. The old right-hand fitness / weakness / recommendation stack is intentionally hidden to avoid duplicating the same questions. The full capability board remains the deep diagnostic layer, and it now uses the same ceiling ruler as the radar (bar fills to the soft cap, brass tick at the target).

**THE WHEEL IS A SEMICIRCLE AND THE PARTY STRIP IS GONE** (owner 2026-08-27). The wheel is no longer a square instrument: frameless weapon art rides the TOP ARC of a virtual `--wd` circle anchored at the top of a half-height box (the art is the star — no card boxes; the focused weapon scales up and glows brass), and the hub is a smaller circle floating in the arc's open mouth. Drag-to-rotate derives the centre from the box WIDTH, never its height. The width freed by the missing lower half goes to the **comp board**, which REPLACED the `ws-party` strip entirely: the roster in four main-role columns (Tank / Support / DPS / Healer, from `roleAdvisory`), each member a full `dm` tile sharing THE member popover with everything the strip's tiles carried (contribution, swap hints, off-comp/redundancy flags, kit/dossier/remove actions, the ≤960 bottom sheet). The strip's other jobs moved with it: open slots became a dashed brass column, duplicate-check notices and the kit editor became a notes rail under the board, and the role-filter tally chips retired outright (the column headers carry the counts). `memberPop()` is shared by construction so the docks can never disagree; the board is built in `renderRoster` and cached (`BOARD_HTML`), so wheel spins never pay for the roster analysis.

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

### Forge-quality rounds (2026-08-23/24) — six expert gradings, every miss now a mechanism

Five blind grading rounds with the owner converted every complaint into a structural rule (full log + verbatim rulings: `tests/VALIDATION.md`; pins F14–F18b, T27–T29):

- **Economics** (`viability.cost_gate` + derived `cost_tier`): crystal weapons leave suggestions/generation below 30 players — regear cost makes them rich-group picks. Manual picks score, flagged `off_budget`.
- **Healing foundation** (`primary_healer` + derived `full_healer`/`heal_scale`): band minima require healers whose E heals BIG and heals a GROUP — both derived from the E bundle + the spell's own area facts (`heal_overrides.yaml` carries two cited sub-effect fact-corrections: Divine Jump, Celestial Sphere). Single-ally-heal-E healers (1H Holy, Druidic…) grade gang situational / group unfit and never generate at 10+; gang slots stay open by ruling.
- **Style-aware role bands** (`styles.yaml constraint_overrides`): owner-ruled healer/frontline counts per style (20-man healers: brawl 3-4 / clap 2-3 / kite 2 / clap_kite 3-4; kite@7 = 1; brawl frontline capped at blap's 5).
- **Generation-fit gate** (engine, both ports): a DEFAULT generated comp fields damage picks whose derived verdict is **fits** — declared style's verdict, or fits-for-at-least-one-style under balanced. "Situational" is caller territory: manual picks score, never flagged. Trio gates nothing; a fits-nothing weapon (Battleaxe) now leaves balanced too.
- **Duplicates earn their place** (`duplication`): generation default is 1 copy at every size; a second copy only through a per-weapon allowance citing a real comp.
- **Derived job budgets** (`composition.yaml derived_groups` → build-time membership, no hand lists): `clump_core` (flat clump_create ≥ 4 — HoJ/Camlann/Witchwork) max 2; `curse_pressure` (the cursed line via its shared Q pool) max 2.
- **First verified non-stacking scoring record**: CURSEDOT (`pipeline/interactions.yaml`) — the target-side Vile-Curse pool caps at 4 across wielders, so the curse Q's sustained_dps counts once per party.
- **Non-stacking slots are earned** (round 8, 2026-08-25 — the round-6 derivation landed): a member of a derived non-stacking group (today the cursed line) earns a group-band (10+) slot only with an E enemy-DEBUFF tool ≥ 4 (purge / pierce / heal-cut class — `E_DEBUFF_CAPS` in build_dataset). Damnation, Lifecurse and Rotcaller earn ("the only curse weapons in any party bigger than 15"); Cursed Skull, Shadowcaller, Great Cursed, 1H Cursed and Demonic (fear = displacement, not a debuff) demote to situational at group for every style and leave 10+ generation, balanced included. Manual picks score, never flagged. F19 pins it; F5 was strengthened to allow only IRREDUCIBLE saturation filler (a filler slot with a better legal replacement still fails).

- **Need profiles** (2026-08-26, increment 3 — see the engine-model bullet above): fine-seat bands + function coverage riding the same predicate machinery, owner-ruled from the blind round + the killboard roster evidence; ranged styles carry a 7-strong ranged-AoE core at 20 (F21).

Audit artifacts: `out/economics_report.json` (cost tiers, heal scales, full healers), `out/style_fit_report.json` (`e_debuff_max` / `nonstack_member` per weapon), `out/roster_mixes.json` (the killboard roster-mix evidence behind the need profiles), derived group membership printed at dataset build. The round-6 open ruling (utility-E vs damage-E within the cursed line) is CLOSED by round 8.

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

The Comp Status → Biggest Need → Best Next Pick hierarchy is the headline surface. Its regressions were repaired on `main` afterwards: the forge honesty reports moved to a full-width slot above the wheel stage (never hidden; rehomed again 2026-08-23 to live under the wheel), the click-to-add alternatives render inside the pick card, and layout overrides follow the shell's own breakpoints instead of `!important`.

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

**#1 — THE UNIT RE-FIT: DONE 2026-08-29.** Shipped; see "Current engine model" above and VALIDATION.md "THE UNIT RE-FIT" for the method and the three approaches that failed before it. The residual is a CALIBRATION question, not a unit one: median coverage across reference comps is 1.82 where ~1.0-1.3 would be ideal, so the targets remain conservative (good comps over-cover) — the safe direction. Sharpening that needs the expert blind rounds, not another rescale.

**The E-audit RAN (2026-08-24, owner's check-first directive — VALIDATION.md).** Round 6's curse reading is WITHDRAWN as a rule (it was an explanation of a general principle: don't stack a tree when its shared mechanics don't stack — the CURSEDOT count-once + derived curse_pressure group already embody it). The first full sweep of all 137 Es (description damage vs scored caps, radius/pierce wording vs scale, candidates vs curation) flagged 17, resolved 13 on inspection, and fixed two Battle-Bracers-class gaps with dump citations: **Fists of Avalon** (232 area purge-punch → burst_aoe 4, now group pools) and **Trinity Spear** (191/r3 impact beside the root → burst_aoe 2, now group pools). Both open items ruled same session: Fists' purge → 4 (MASTERSHEET); Trinity Spear OUT of large-scale generation (cited override — "never the main weapon in party", its large-scale use is a structure-siege swap; general principle recorded: auto-attack steroids are not large-scale utility). T31d pins both, 56/56 golden. Roadmap items 4/5 (slot locks, player profiles) owner-deprioritized until comp quality satisfies. Watch items: Hellfire under clap_kite, castle-25's saturated tail quality. Evensong RESOLVED 2026-08-25 (round 8's C7-E number check: the E's 112 damage was scored like a 264-class bomb — burst_aoe trimmed 4→2 with citation; the stacking aura debuff identity stands) and the rest of the C7-E watch list is CLOSED as owner-accepted with numbers verified (VALIDATION.md).

**Round 7 RULED + SHIPPED (2026-08-24, VALIDATION.md)** — the two-prong E rule: prong-1 fact fixes (Battle Bracers' unscored Falcon Smash AoE damage restored with dump citation → back in group pools, killboard-corroborated; Warbow / 1H Fire / Hellspawn owner-ruled solo-class via cited style overrides) + the derived `weak_group_e` demotion (low E damage AND no real E tool → trio-class; the AND protects Heavy-Mace-style utility Es). Golden T31/T31b pin it. Same-session follow-up closed the rest: Spirithunter PROMOTED to clap/clap_kite fits (cited override; T23e refined, T31c pins pools — "massive pierce that enables the whole dps line"), Bloodletter resolved as a battlemount-pilot killboard artifact (no gate change; mount-carrier bias caveat added to KILLBOARD_AFFINITY.md), Galatine Pair confirmed a solo-bomb specialist (stays pooled, forge correctly passes). Round 7 fully closed at 55/55 golden.

The preferred product sequence is:

1. **Fight-chain explanation** — SHIPPED (2026-08-23)
   - `fight_chain()` in both engine ports: the declared style's stage sequence (chains are DATA in `styles.yaml` per style — clap: engage→clump→pierce→burst→secure→reset; brawl: contact→pressure→sustain→denial→secure; kite: space→slow→peel→ranged pressure→reset; hybrids have their own; balanced falls back to the detected identity's chain), every stage graded strong/ok/weak/missing/quiet against the comp-fitted template targets over effective supply — the same lens as kill-pressure, zero new scoring
   - the recommended pick connects to the stage it improves most, from the same `explain()` terms the why-panel shows, and only when that stage holds a real share (≥30%) of the pick's value — a healer into a clap chain claims nothing (its value is survival, not a stage)
   - rendered as a stage strip in the decision layer's pick card; golden T26/T26b pin blap all-strong on the brawl sequence, the weak-five grading, the Carving→Pressure connection, and that fitness is untouched
   - 2026-08-24 addendum (from a user unable to reconcile "strengthens Reset" with gain tiles led by other caps): every stage now carries `sources` — the equipped spells that ARE the stage, from each member's resolved loadout (slot + spell id + effective units; `spell: null` = the weapon's always-on kit) — and `improves` names its per-cap `terms` (a stage can win on SUMMED caps none of which is the pick's top tile). Stage chips are clickable in the UI (fold lists the spells by capability, duplicates grouped "N×"); golden T26c pins that sources cite real loadout spells and terms sum to the claimed gain; parity carries both

2. **Composition identity detection** — SHIPPED descriptive v2 (2026-08-23, from V3 finding F-V3-2 + the owner's weapon-identity model)
   - identity builds UP from members (owner ruling: a weapon's identity = its E first, then chosen Q/W, equipment, team role). `derive_style_fit` in the dataset build derives per-weapon delivery (melee / flex / ranged — flex = melee stat line whose E damage lands at range, e.g. Realmbreaker the all-rounder, DERIVED not curated) and style × size-band fit verdicts; `pipeline/style_overrides.yaml` carries cited owner rulings (Battleaxe unfit as a group pick >3); `out/style_fit_report.json` is the audit + MetaBattle review queue (Q15 ANSWERED)
   - `comp_identity()` v2 in both ports: comp label from the member fingerprint, per-member fit verdicts for the DECLARED style (style selection = build intent, owner ruling) at the current size band (trio ≤3 / gang 4–9 / group 10+); unfit members become named conflicts ("Battleaxe: its E is not a group-scale damage tool at this size"); flex weapons never read as split-identity conflicts
   - DESCRIPTIVE ONLY — no scoring path reads it (golden T23c pins that); T23/T23b/T23d pin the classifications and the two owner rulings
   - Phase C SHIPPED (2026-08-23): **style selection is build intent.** A declared style gates suggestions exactly like viability exclusions — style-unfit weapons leave `suggest_pool()`/forge/recommend in BOTH ports (never scoring; manual and locked picks score and get flagged `off_style` in swap review with replacement advice — forge F13 pins the whole contract, T24 the kit rule); the kit advisor never suggests cloth armor under a declared brawl for non-healers (owner ruling verbatim in the code); build records carry an optional validated `style:` key so canonical builds can be stored per content × style. Balanced declares no intent and gates nothing; trio sizes gate nothing.
   - Phase D SHIPPED (2026-08-23): **kill pressure** — the caller's checklist as a three-light verdict (pierce on the clump / heal-cut applied / enough burst) in both engine ports (`kill_pressure()`), rendered in the status card. The bars are deliberately a LENS over the comp-fitted template targets (the 2026-08-21 recalibration evidence defines "enough"; focus-fire and escalation physics are already inside effective supply) — not a second physics model. Config: `mechanics.yaml kill_pressure` (pass_ratio 0.85, PROVISIONAL, MASTERSHEET-tunable). Golden T25/T25b pin the owner's own example (20 Heavy Maces = lacking on all three lights) and that nothing scores. Deeper enemy-toughness modeling (gear tier/IP, buffs, exact EHP) is the recorded v2 question — computable once the companion/gear layer supplies real item power per member.

3. **Negative recommendations / redundancy warnings** — SHIPPED (2026-08-24)
   - deliberately NOT a new scoring term (Q18 rejected a scoring-side redundancy penalty; the exact marginal already collapses for a redundant pick) — this ships the *decomposition* the score always contained: `pick_report()` in both ports returns the full SIGNED breakdown of `_eval_pick` (per-cap coverage / floor-lift / over-stack cost, count-once spell losses, the duplicate-copy penalty), test-pinned to reconstruct the score and `d_fitness` at 1e-9
   - one verdict rule everywhere (`_pick_verdict`): **negative** = marginal ≤ 0; **redundant** = zero gap-closing gain (below-target coverage + floor lift, headroom-band depth deliberately excluded so saturation is reachable) — threshold `mechanics.yaml negative_recs.redundant_gain_max` (0.05, PROVISIONAL, MASTERSHEET-tunable)
   - surfaces: `recommend()` rows carry `verdict`/`caps_gain`; `swap_review()` flags members whose jobs the REST covers (`redundant` — with 2 healers neither is, a 3rd is); `analyze()` rows carry the saturation `band` (gap / headroom / overstacked) + `soft_cap`; dashboard renders a "why not" block on the pick card (saturated caps, over-stack cost, dup penalty, count-once losses), dims redundant alternatives, and chips roster members "jobs covered without it"
   - DESCRIPTIVE ONLY, display translates verbatim; golden T30–T30d pin reconciliation, both verdicts, the swap-review semantics and that fitness is untouched; parity carries pick_report / verdicts / bands per case (60/60)

4. **Slot locks / constrained reforge**
   - keep fixed players/weapons locked and optimize only flexible slots

5. **Saved player profiles**
   - persistent weapon pools for guild members rather than recreating candidate lists each session

6. **Observed composition neighbours** — SHIPPED (2026-08-24)
   - `cohortNeighbours()` in `dashboard/_app.js` (display layer, deliberately NOT the engine — observed evidence never enters `CompEngine`): the anonymous cohort baskets most like the current roster, shown AS rosters under the contextual killboard strip. A neighbour must share ≥2 of the selected unique weapons; ranked shared-count desc, then Jaccard over unique weapons (so a 28-weapon alliance basket ranks below an exact 15-man echo), then original basket order; top 3 rendered with shared picks highlighted, completions as muted dossier links, capped at 14 icons with an honest "+N more"
   - same rules as the affinity pass: bucket = `usageBucket()` (the size the comp is FOR), ≥8 usable cohorts or the panel stays hidden, language says "observed rosters"/"cohort" never "party"/"winning comp", and the ka-note disclaimer stays
   - `tests/test_display_math.js` covers the ranking, the pair minimum, unknown-key stripping, dedup of duplicate roster weapons, and the top-3-slice-vs-full-count split (11/11)
   - clustering (item 7) and any empirical scoring stay parked behind owner review per `KILLBOARD_AFFINITY.md`

7. **Composition clustering** — SHIPPED as anchor-pair families (2026-08-24, owner-directed; display only)
   - NOT whole-roster clustering, by measured finding: the cohort baskets are PARTIAL observations (most hold 2–5 weapons of a 20-man lineup; cross-org Jaccard median 0.0, p90 0.17; the lift-gated co-occurrence graph is one connected component at every threshold) — distance clustering on this sample separates observation noise, not comps
   - `pipeline/build_cohort_families.py` mines greedy DISJOINT anchor-pair families per bucket: anchor = strongest remaining recurring pair (gates: ≥5 cohorts, ≥3 distinct orgs, ≥3 battles, lift ≥1.2 — all PROVISIONAL constants in the script), family = its cohorts, cast = weapons in ≥40% of them with observed shares; deterministic, byte-identical rebuilds, counts only (org/battle ids never leave `weapon_usage_v2.json`) → `out/cohort_families.json` (run after `build_dataset.py`; anchors filtered against the catalog)
   - committed 2026-08 sample yields: large 5 families — F1 IS the observed ZvZ meta (Realmbreaker + Spiked Gauntlets, cast Battle Bracers 84% / Hallowfall 73% / Harpoon 68% / Permafrost 63%), plus fire+frost bomb, two Longbow cores, Heavy Mace + Hallowfall; mid 1; small 0 (honestly thin)
   - dashboard embeds the artifact (`FAMILIES`), renders "Recurring observed cores" in both killboard-strip modes, marks roster-carried pieces and full-anchor matches; `tests/test_cohort_families.py` (7 contracts: determinism, disjointness, no id leaks, gates) + `familyRows` cases in `test_display_math.js` (13/13)
   - empirical/scoring integration REMAINS PARKED behind an owner ruling (`KILLBOARD_AFFINITY.md`)
   - **Follow-through (2026-08-24, same session):**
     - **Round-7 candidate cases** — first forge-vs-families reconciliation logged in `tests/VALIDATION.md` (PENDING, no rulings): Battle Bracers 84%-observed yet ST-E-gated (the utility-carrier/Harpoon shape), Spirithunter 68% vs its situational ruling, Bloodletter (kill-event sampling bias suspect), Galatine Pair pooled-but-never-forged, plus weak-form darlings evidence (Evensong 0-1 observed — bears on the round-1 watch item)
     - **Observed-core loader** — "add core" button on family rows loads the anchor pair as MANUAL picks through the standard `data-add` mutation path (engine flags/scoring apply as usual; forge completes the rest); hidden once the anchor is in the roster
     - **Forge-context bug FIXED in `_app.js`** (pre-existing, surfaced by the loader): the engine is judged at roster size (owner ruling 2026-08-21) but the forge handler ran `ENG.forge(goal)` under that roster-size context — a 2-member roster forging to 20 searched under TRIO rules, so single-target-E dps and gang-only picks generated into ZvZ comps. Every Python/test forge constructs the engine at target size, which is why 21/21 forge + parity never caught it. The handler now wraps the forge in a target-size `setContent` (restore mirrors `inPickContext`); browser-verified end to end (core → forge → sane 20-man, zero gate violations)

**ACTIVE TRACK — the ROLE LAYER (2026-08-25, roles-design.md; increments 1 AND 2 SHIPPED).** The owner's kit-quality observations (everyone getting the same damage jacket; Grailseeker as dps) became the role architecture: roles are member-in-comp properties selected by kit, never 1:1 weapon labels. Increment 1: the role book (seats / functions / gear effects), the E-first tiered sweep, equipment classification by the unique-ability-first law, detection + advisory in both ports. Increment 2 (same day, owner: "yes its the whole build ... include food, potion and capes and you are right about passive defaults"): `kit_options` is DOCTRINE-LED — the chest hard-gates to the seat uniform (R12 kills the Hellion bug), every other slot (through food/potion/cape) ranks a doctrine tier mined from the seat's observed reference builds (build-id cited, roles_report `kit_doctrine`; tier-first context-free, exact-marginal-first comp-aware per T22), passive doctrine resolves per piece from the dumps (cloth Aggression / leather Quick Thinker / plate Authority-or-Tenacity) into the build stat channels, and the Leering-Cane pairing is emergent physics via the new `cc_mult_caps` CC-duration channel (R13) — contracts R12–R16, kit parity carried per case. **2026-08-26, all in one day (VALIDATION.md carries every ruling verbatim):** the full board was owner-graded on an interactive artifact (465 rows, 15 rulings → eight membership corrections, the cited `kit_doctrine.overrides` + `gear_affinity_overrides` layers, the dive-dagger ≥7 exclusion — R17); increment 2.5 shipped per-weapon doctrine tiers + comp-level effect quotas (R18); the MetaBattle adapter grew to every group-PvP category (corpus 222 → 237 records, 74 weapons); and increment 3 shipped the NEED PROFILES (blind round first, then the owner's "what matters is what the data says" — the killboard roster miner `sample_rosters.py` delivered 139 near-complete fight rosters; the data's engage-leaning split overruled the owner's stopper-heavy blind call, preserved as the terry override) wired into both forge ports (F21), plus four follow-up rulings: clap/clap_kite ranged core 7 at 20, Icicle stays zone_support, healers 1-2 at 5-7 stand, and effect quotas GRADUATED to on-page advice. NEXT INCREMENTS: (3b) effect-quota-aware kit allocation + mechanism pairing rules for effect carriers (grading material on the board); (4) uptime economics (gear survivability multiplies the wearer's own delivery). **2026-09-01 — FAIL-CLOSED GENERATION (owner ruling, VALIDATION.md entry):** `kit_options`' seatless fallback (whole catalog, marginal-ranked) was how Hellion Hood reached every seatless member of every full comp — 75 of 137 weapons resolve no seat, and a saturated comp's one uncovered cap (silence) topped the same helm everywhere. The channel now only speaks evidence in BOTH ports: no seat → empty kit/options (`seat: None`), an evidence-less slot stays unset, `role=None` stays the diagnostic escape, manual builds always score (R19; parity 60/60; the loadout panel says why when it proposes nothing). Follow-up now urgent: seat curation for the 75 seatless weapons. **Same day — THE SEAT-ALL PASS (owner: "lets fix seat for all weapons"):** 73 of the 75 seated in roles.yaml, every entry killboard-cited from `party_rosters.json` armor distributions (uniform) + derived E identity (class); one new seat `curse_support` (cloth+plate, the observed curse-line uniform); the two 2026-08-26 grading-board exclusions (Chillhowl/Stillgaze id 2H_SHAPESHIFTER_CRYSTAL, Iron-clad) stay off every menu pending an owner word. Role book now covers 135/137; tier2 v4 actual_gear role-level rose 70%→87% (gate PASS); all suites green (VALIDATION.md carries the full entry). **Then — KILLBOARD KIT DOCTRINE (owner: "base it on seen evidence from the data we harvested from all the battles"):** `derive_kit_doctrine` mines `party_rosters.json` (9,569 fielded builds, ~54k gear observations) as a second stream beside builds_index — noise floor KB_MIN_SEAT 3 / KB_MIN_WEAPON 2, separate `kb` provenance, off-uniform still reported-never-admitted; the Leering Cane hand-add retired (observation superseded it, the build's fail-closed check caught it). Tiers are now observation-led (per-weapon doctrine across the catalog — Light Crossbow wears its own observed kit); tier2 v4 78% (18/23) gate PASS, the 87→78 movement logged as an owner observation, not tuned. **Then — THE OBSERVED-BUILD OVERLAY (owner: "gear each seat is wearing should be based on what real people wear; the engine keeps making up random builds"):** per-slot marginal assembly produced Frankenstein kits, so `_modal_build_chain` mines a CONDITIONAL MODAL build per weapon (chest first, then head among-builds-wearing-that-chest, …; ≥3 builds, ≥2 per step, uniform-gated, effect carriers out; seat fallback) shipped as `kit_build`/`kit_weapon_build`; both ports front the archetype item per slot (`observed_build: [n, of]`) so the kit pick and forge v0 ARE the fielded combination (Heavy Mace = Knight+Hellion+Royal Shoes 42/142; Hallowfall = Robe of Purity 672/1169). R20 pins it; all gates green with zero re-pins; tier2 v4 rose 78%→83% (19/23).

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
py -3 tests/test_roles.py
py -3 tests/test_validation_modes.py
py -3 tests/tier2_blindtest.py v4
py -3 tests/test_js_parity.py
node tests/test_loadout_codec.js
node tests/test_display_math.js
py -3 tests/test_patch_history.py
py -3 tests/test_provenance.py
py -3 tests/test_builds.py
py -3 tests/test_cohort_families.py
py -3 pipeline/build_interactions.py
py -3 tests/test_interactions.py
py -3 dashboard/build.py
```

The effect catalogue is NOT part of a normal build — it reads the pinned dumps
directly and is regenerated only when the snapshot moves or its extraction
changes (it now covers gear as well as weapons):

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
