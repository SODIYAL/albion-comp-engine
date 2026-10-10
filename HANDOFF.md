# Handoff — Albion Online Composition Engine

Comp Forge is an Albion Online party-composition recommendation engine and
research tool, live at <https://sodiyal.github.io/albion-comp-engine/>.

This file is the current state: what the product is, how the engine and the
planner work today, the rules that shape generation, and what is open. It
carries no history — every decision's date, evidence and pin are one index
row in `tests/VALIDATION.md`; the full log is `notes/validation/`.
`MASTERSHEET.md` is the LIVE tuning control surface (its `tune:` blocks
override everything at build time — read it first for what the engine
actually uses). `CLAUDE.md` has the environment traps, the gate list and the
invariants. `pipeline/README.md` has the pipeline, the patch workflow and the
mechanics layer.

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
  comps, build sources, validation-round results. They never alter ranking
  unless a calibration decision promotes them into scoring and is validated.
  Popularity is not effectiveness. Semantics and caveats:
  `KILLBOARD_AFFINITY.md`.

## The engine today

- 137 combat weapons; 31 sheet capabilities (`evidence_lint.CAPABILITIES`),
  every one but `reflect` scored by at least one template (the
  `effect_map.yaml` reflect note); `ranged_presence` is derived by the build
  (`reveal` is proposed-only, refused with evidence in `effect_map.yaml`).
  Sheets score 1–7; 2 points = one supply unit. One sheet per weapon tree
  (`pipeline/sheets/<tree>.yaml`) beside the tree's shared pool
  (`sheets/pools/<tree>.yaml`); gear one sheet per slot
  (`pipeline/sheets/README.md` "Layout").
- Six content templates with comp-fitted targets and soft caps (person units)
  and hard floors (weapon units); five playstyles (brawl / clap / kite /
  brawl_clap / clap_kite) carrying weight multipliers, `target_mults`,
  constraint overrides and a fight chain; GENERATED style x size rows beside
  the content rows (`templates/style_bands.yaml`, from harvested winners,
  read at 10+; `balanced` reads the pooled cell, every winner at the
  size, any style).
- **Target is the median (standing rule 17).** Every row carries three
  measured lines: `min` = the least winners get away with (harvest p10 /
  least fitted comp), `target` = the TYPICAL winner (p50 / median of the
  fitted comps) — the point of full credit and the board's second number
  — and `soft_cap` = 1.15 x p90. Before this rule the target was 0.9 x p10
  and the score gave full credit at the floor (one healer "covered" fifteen).
  The utility curve is unchanged; the number it aims at moved, on every row
  at once. `target_min(cap)` / `target_source(cap)` (harvest / harvest_borrowed
  / content / content_min, from each template's `fit:` block) are display
  provenance, parity-carried, never scored. Kill-pressure lights bar on the
  minimum ("enough to kill"); fight-chain stages grade weak < min <= ok <
  typical <= strong; the redundancy lens reads "under one weighted unit".
  Content rows: `pipeline/refit_content_targets.py` (median of the dressed
  audit's comps; blackzone_roam 18, castle_outpost 3; territory_defense 2 /
  roads 1 / castle 0 / faction_war 0 stay on the old minimum and say so).
- **Capability weights.** Curation judgment on five templates. Blackzone
  Roam's are FITTED to what training-split killer parties pick
  (`pipeline/fit_choice_weights.py`, standing rule 7 as amended): a
  conditional logit over the engine's own pick-score terms, pulled toward
  the curated weights its `weight_fit` block records; the build enforces
  the pull rule (every curated weight >= 4 keeps half or more). Revealed
  preference, not win evidence: `audit_capability_outcomes.py` is the
  outcome side (its party-level read, each side's numbers from the battle
  roster: numbers decide the outcome and fitness() adds nothing to them;
  tests/VALIDATION.md).
- Fitness: coverage with diminishing returns, hard floors on the
  weapon+loadout basis, the `disengage` and `mobility` rows on the same
  basis (worn gear neither adds to nor changes them, mechanics
  `weapon_basis_caps`), headroom, overstack, Focus Fire / Resilience and AoE
  escalation, per-weapon Resilience Penetration as a rebate, optional rows,
  ramped rows (`anti_zone`: none through 14, full at 25).
- Recommendation score = exact marginal comp-score delta (0.55 capability +
  0.20 synergy + 0.15 meta prior ± viability / duplicates), one player ahead,
  each candidate on its best legal Q/W/E/passive combo, DRESSED in its doctrine
  kit. Synergy is weapon-interaction only. The meta prior is GENERATED from
  the killer-party harvest per size bucket (`out/meta_prior.json`): per
  member 0.5 x the weapon's own share + 0.5 x its best observed partner on
  the roster (`meta_pairs`, one party one vote per pair, >=3 guild-sets,
  log2-lift capped at 8x, shrunk; standing rule 7), both tables on the
  training split `battle % 5 != 0`; a hand-set map fails the build.
  Inside the Dragon Portal's 2-3, 4-5 and 6-7 pools the meta term reads
  the pool's own tables (`out/portal_prior.json`, the pool's dominant
  winners, `derive_portal_prior.py`) at `pool_delta_x` 8 x 0.15.
  Duplicates: 1 copy by default; the one super-additive case is
  `self_cost_offset_min_copies` (Demon Armor).
- Gear scores (curated `sheets/gear/<slot>.yaml`, the tree-shared actives once in
  `sheets/gear/pools/` and composed per item) through `build_extra`: stat
  channels, doctrine passives, `cc_mult_caps`, `self_costs`. An off-hand
  carries no row: its supply is its stats, read at their tier-4 value
  (mechanics `offhand_t4_scale`): defense vs players multiplies the
  wearer's tankiness, damage and heal % its output, cooldown % its output,
  cast time % the output its weapon casts (`cast_caps`), attack speed its
  sustained damage. A weapon's E may carry `self_costs` too, charged on
  the wielder's own supply like a gear piece's. Tier-agnostic
  lookup (`gear_key()`). The active a piece scores is the gear-active
  doctrine's (`doctrine_active`, stamped by `build_dataset`): the one the
  recording published builds equip (two votes, by band too), else the
  item's own active (`assumed`) — never the template-weighted argmax
  across the menu; an active with no scored row is an empty bundle.
  `gear_choice_source` / `gear_active_spell` name the pick for the UI
  (VALIDATION.md 10-03).
- The role layer (`roles-design.md`, `pipeline/roles.yaml`): seats (uniformed)
  and functions (pierce / purge / anti_heal / shield_break) derived E-first;
  `detect_role` / `role_advisory` descriptive; `role_class` for forge bands
  derives from the primary seat.
- **Tile labels** (`roles.yaml labels`, R37): every weapon
  ships `label = {primary, tags}` — PRIMARY is the seat's plain word (Engage /
  Stopper / Bruiser / Support / Ranged AoE / Melee / Bomb / Dive; healers read
  their heal profile, Burst or Sustain), tags are the cited function roles on
  the primary menu then the weapon's own capabilities at >= 4, at most two,
  E-first, never what the primary implies; healers tag their line (holy /
  nature). Label overrides are cited and inside the vocabulary. Display only;
  the tile composes `PRIMARY · tag · tag` from the member's DETECTED seat word
  and the weapon's tags. Seat moves the labels suggest are an open list
  (`notes/findings/2026-09-11-labels-vs-seats.md`, BACKLOG), never a change
  made by the label layer.
- Kits: `kit_options` is doctrine-led, observed-build-led and fail-closed.
  Every doctrine reader goes through `_seat_kit` (group band at 10+, gang band
  at <= 9, a declared style's cell laid over the band). Slots rank by observed
  votes (one player, one vote; killer parties of 10+; only builds at or above
  the item-power cut vote, the training split's bottom decile of party item
  power, recomputed and recorded at every build as `kit_item_power`), the
  observed-build chain fronts a real worn combination (chains may have gaps),
  thin slots pool to
  the seat (`kit_pool` / `kit_by_chest`), carrier chests obey a comp-level
  quota, two-handers get no off-hand (nor from the planner's caller-reference
  fill, L40f), and where evidence runs out nothing is proposed. Comp-aware,
  an item is priced against the rest as equipped, the worn rest dressed once
  per waived set (F42). Manual kits always score.
- Descriptive analyzers, parity-carried, never scoring inputs: `comp_identity`
  (playstyle label, per-member fit, bomb-squad archetype, kit-aware; at 14
  or fewer the gank read, a label with no style that votes into no style
  cell, T43b), `kill_pressure`,
  `fight_chain`, `pick_report` (signed decomposition reconstructing the pick
  marginal at 1e-9), `analyze`, `duplicate_conflicts`, the role advisory.
- `engine/app_scoring.js` mirrors `engine/engine.py`; parity on 60 random
  parties at 1e-9 plus an embed check on every build.

### How a recommendation is computed

1. `CompEngine` loads content, effective roster size and playstyle.
2. Members resolve to their selected / stored / default legal spell combos.
   Every sheet row scores on its own spell's bundle; within one weapon or
   gear item, two chosen spells carrying one capability merge by the
   maximum (a score is the item's total with that spell equipped; F43).
3. Effective capability supply is computed (weapon + loadout + worn gear).
4. Fitness evaluates coverage, floors, headroom, overstack and mechanics.
5. Candidates run one ahead (`roster + 1`) so thresholds that arm on the next
   body are anticipated.
6. Every candidate is evaluated on its best legal loadout, dressed in its
   doctrine kit (builds within 1e-9 of each other tie, and the earlier in
   search order keeps it).
7. Score = exact marginal fitness + synergy + meta prior ± viability and
   duplicate terms.
8. `explain()` / `pick_report()` return the per-capability deltas from the same
   candidate kit.

Do not rewrite this flow in the dashboard layer.

### The self-cost offset in the pick score

The one super-additive duplicate (`self_cost_offset_min_copies`, Demon
Armor) rides the pick score exactly: `party_state` carries the items the
roster has waived and the refund pending for an item one copy short;
`_eval_pick` / `_forge_eval_pick` price a candidate whose kit hits either
on its exact vector (own cost waived, the wearers' refund added after the
non-stacking adjustment, never on the floor basis) and `_pick_caps` rows
still sum to the fitness delta. Every party-level reader (waivers,
carrier quota, kit lean) compares worn keys in their curated form:
`gear_key` resolves a tiered key to a tierless curated item and a
(key, choice) pair to its key. F1d / F1e and two parity cases pin it.

### The count-once rule on dressed members

A verified non-stacking spell (Vile Curse on `sustained_dps`, the one such
record) keeps its largest single contribution. A dressed member's
contribution is its share AS WORN (`_ns_share`: the kit's damage, heal and
CC-duration % multiply the spell's units as `build_extra` multiplies the
member's whole capability), so a duplicate keeps no part of its copy.
`party_state` carries two tables: `ns_max` on the weapon-only basis, read
by the synergy terms and the floor basis, and `ns_max_fit` on the fit
supply; every marginal prices the fit side on the second and the synergy
and floor sides on the first, as `comp_score` does. F39 / F40 pin the
pick score's exactness on dressed duplicates, dressed and naked
candidates alike.

### The swap advisor

`swap_review` is a weapon-choice read: each member's weapon is valued as a
pick into the rest in its best combo and doctrine kit, like every
alternative (`score`, `rank`, `verdict`, each option's `gain`; T17), so a
build shortfall never turns into weapon advice. Beside it the member as
built: `built_score` (the exact comp-score contribution in its own combo
and kit, priced as a marginal on the rest's state like every pick,
`_as_built`), `build_gap`, and per option the exact comp-score change of
the swap (`delta`) with the combo and kit it assumed (F41, F41b). The
planner's hint gates on the gain, shows the delta, and a click lands the
option in that combo and kit, as the replace list does. A member
`min_gain` or more short of its own best build (`build_gap`) is offered
that build in one click, the weapon kept, and its swap buttons then show
the gain (delta = gain + build_gap), so a build shortfall is never
credited to another weapon (L40g).

### The Dragon Portal: rows per matchmaking pool

`ancient_lands` (Dragon Portal) reads rows GENERATED from the portal
harvest (`pipeline/derive_portal_rows.py`, `fit: {stat: median, source:
harvest}`): the unit is the dominant killer party of the pool's size on
the training split, floor 40 distinct rosters per pool. The base rows are
the 4-5 pool's; the 2-3 and 6-7 pools carry `pool_rows` of their own,
read by both ports at a size inside the pool (`Engine.pool_key`,
`target_source` says `harvest`), and a capability the median winner does
not field is no requirement at that pool: at 4-5 and 6-7 it is an
OPTIONAL row where at least one winning party in ten fields it (target
and soft cap read over the parties that field it, no minimum: the
silence a Heavy Mace brings earns its coverage, a five without silence
is not short of it), `none` otherwise and at 2-3 (F34e-i). The pools
carry role counts of their own (`role_counts.json` `pools`, read before
every other table below 10; a role may be typical at zero), so a forged
trio fields no frontline and a five one (F31l-o, T50). The 15-20 pool carries rows
of its own from the floor of 40 distinct rosters; inside it they outrank
the style x size rows in both engine ports (F34j), and it carries no
fielded list. The
weights are fitted to the same winners' picks (`weight_fit`, pulled
toward the Roads weights the template started from) and apply at every
pool. `validated_sizes` is empty (no validation round has covered a pool), so every
size is still flagged extrapolated. A content that keeps full
single-target value (`st_full_value`: roads and the portal) admits a
single-scale carry's `situational` verdict at the gang band into default
generation (F34d). The same step lists, per pool at the floor, the
weapons its dominant winners field (`pool_fielded`: at least 5 distinct
rosters across 3 guild-sets and 5% of the rosters of the pool's most
fielded weapon); at a size inside the pool both ports suggest and
generate from that list only (`is_unfielded`, F35, T51), the wheel marks
the rest "not fielded here", and a manual pick always scores. The
capability score alone ranked wide-sheet weapons no winner fields first
(Claws and Hand of Justice in a forged seven, 1 of 162 dominant 6-7
parties each). The pools that carry a fielded list carry a meta prior
of their own as well (`derive_portal_prior.py` -> `out/portal_prior.json`
-> `scoring.meta_pools`: the same dominant winners, one player one vote,
the pair table on the bucket prior's rules); inside such a pool both
ports read it in place of the size bucket's at `weights.pool_delta_x` (8)
x `delta` (T56; on the holdout the hidden weapon's top-3 rises from
8.5% / 20.8% / 8.2% to 12.3% / 21.9% / 10.6% at 2-3 / 4-5 / 6-7). The
15-20 pool's prior waits with its list. A content with no harvested evidence follows the rule
this content used before: `fit: {stat: none, borrowed_from: <sibling>}`,
every target read as `content_min`, the borrowed-evidence notice on the
page.

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

- **Slot controls**: every roster tile carries lock / replace / refresh-rest /
  remove (hover on desktop, the popover's action row on touch), drawn by the
  monoline inline-SVG helper `ui()` (24 grid, 1.75 stroke, round caps,
  currentColor). Slot provenance is `m` manual / `f` forged / `l` LOCKED —
  the lock is the only thing a refresh holds, manual picks included; it
  rides the permalink (`f=` string) and survives a content switch.
  **Replace** lists the engine's `replace_options()` — a one-slot forge:
  every option is scored as a dressed pick into the rest of the comp and
  passes the forge's gates with no slot to spare, so it never offers what
  the forge would refuse; applying one lands its combo and kit and makes
  the slot the user's pick (a locked slot stays locked). **Refresh** (a
  tile's ↻ locks that tile first; the header's "refresh unlocked" holds
  only locks) rebuilds every unlocked slot and gives the NEXT-BEST comp
  each press: the page passes every roster already shown under the
  current lock signature (the one on screen included) as `forge(avoid=)`
  and the forge returns the best roster not among them — the final beam
  depth drops avoided completions and the 1-opt / 2-opt refuse moves
  onto one; deterministic, both ports, parity-carried. A changed lock,
  content, style or size starts the list over; when nothing new is
  reachable the roster stays and the note says so (`exhausted`). "Forge
  the rest" still fills empty slots holding everyone present.

- **Suggestion pools** go through `suggest_pool()`: viability exclusions
  (Dagger Pair / Deathgivers at 7+, Double Bladed at 10+, 1H Cursed and
  Ironclad at 10+ — evidence-gated, lifted by a canonical large-group
  build), the style gate,
  and the generation-fit gate (damage picks whose derived verdict is "fits";
  single-ally-heal-E healers never at 10+; non-stacking-group members need an
  E debuff tool at 10+), inside a Dragon Portal pool the pool-fielded
  gate (only weapons the pool's dominant winners field, generated), and at
  10+ outside such a pool the fielded gate (only weapons the declared
  style's killer parties of 10+ field in the size's band, generated by the
  same rule; `balanced` reads the pooled list; a cell under 40 rosters
  gates nothing). There is no cost gate.
- **Healing foundation**: `primary_heal` band minima need `full_healer`
  weapons (E heal >= 6 AND group scale). One healer per five members is a
  MINIMUM on clap, brawl and both hybrids; kite keeps its minima; balanced
  keeps the base band.
- **Typical role counts** (`derive_role_counts.py`, standing rule 18): the
  band carries `typical` for healer / frontline / support, and at 10+ for
  dps — below 10 the content's fitted-comps median (harvest healer row
  where a content has under 3 comps; dps there is the residual role), at
  10+ the declared style's harvest cell per exact size (`balanced` and
  thin styles read the pooled row). The forge generates a body beyond its
  role's typical only for an unmet minimum no other role still under its
  typical could meet (a minimum only that role can meet always), or by
  ROLE SPILL once every role the pool supplies stands at its typical
  (`_role_spill`, the seat skeleton's rule at the role level), and never
  spends a typical slot on a body that leaves such a minimum short. Sizes
  the harvest does not reach (21+) carry none.
- **Role bands per style** (`styles.yaml constraint_overrides`): healer and
  frontline rows; the ranged-AoE core minimum is generated (below).
- **Seat skeleton** (standing rule 18 extended to seats; spec
  `notes/specs/2026-09-15-skeleton-first-generation-design.md`):
  `derive_skeletons.py` -> `out/skeletons.json` (training split, distinct
  rosters) carries per exact size at 10+, pooled and per declared style, the
  TYPICAL count of every primary seat (`Engine.seat_of`, the first uniformed
  menu role — the one role read). The forge closes a seat at its typical: a
  body past it generates only for a minimum no under-typical seat of its role
  could meet (a Great Holy may not take the brawl-healer seat to cover
  primary_heal while main-healer seats stand open; a flex bomb in the brawler
  seat may cover the ranged-AoE core the ranged seat's pool cannot), or by
  SPILL once every seat of the role the pool supplies stands at typical.
  Refinement and replace-options check the roster a swap would leave
  (`_seat_mix_ok`), so a move never trades away the seat that justified a
  spill. No cell for the size = no seat gate.
- **Plan minima**: the same artifact's `plan` table — the typical count of
  STANDOFF-tool carriers (`style_fit.standoff_e`, the fact the identity read
  defines a kiting plan by) per style x size — rides the band as a
  generation MINIMUM through the flag predicate `standoff` (beside
  `primary_heal`). Kite and clap_kite winners at 15+ field two or three in
  every roster; brawl and clap none, so they demand none. The forged kite 20
  reads as a kiting plan to the engine's own identity (clap_kite; it read as
  a strong clap before the plan minimum).
- **The ranged-AoE core minimum**: the same artifact's `minima` table — per
  style x band (10-14 / 15-19 / 20+) and pooled, round(p50) of the
  `ranged_aoe_core` carriers per roster (a weapon some combo of which meets
  the predicate, `Engine._pred_possible`) where that p50 is 1 or more, the
  standoff rule — replaces the band's minimum at 10+ (the declared style's
  row, else pooled; `balanced` reads pooled). Most of a style's winners
  fielding none sets none (brawl); a style's band under 40 rosters borrows
  its nearest filled band, else its parent style's (the style rows' rule);
  below 10 there is none. A hand minimum in `composition.yaml` or
  `styles.yaml` fails the build (S7).
- **The fielded gate at 10+**: the same artifact's `fielded` table — per
  style x band and pooled, the weapons the cell's killer rosters field by
  the Dragon Portal's rule (`derive_portal_rows.fielded`: 5 distinct
  rosters across 3 guild-sets at 5% of the rosters of the cell's most
  fielded weapon) — bars every other weapon from suggestions and
  generation at 10+ wherever no pool list applies (the declared style's
  list, `balanced` the pooled one; brawl_clap 20, under 40 rosters,
  carries no list and gates nothing). The wheel marks a barred weapon
  "not fielded here"; a manual pick always scores (S8).
- **Duplicates**: 1 copy by default; penalty-free copies and the forge cap
  are GENERATED per style x band (`skeletons.json` copies: free =
  round(p50), max = ceil(p90) of the rosters fielding the weapon; the
  declared style's cell laid over the pooled cell) — Hallowfall keeps a free
  second copy (88% of 20-man winners double it), Bedrock too, Permafrost's
  stays gone (the evidence reproduces the earlier decision to remove it),
  Great Arcane / Rift Glaive / Wailing lose their single-comp allowances. A
  hand `per_weapon` list fails the build. Derived job groups `clump_core`
  and `curse_pressure` max 2 each.
- **Need profiles** (`roles.yaml need_profiles`): fine-seat bands + function
  coverage, armed at 15+, scaled by size / 20.
- **Carrier caps and floors**: one coverage-corrected measurement per effect
  x style x band of the killer rosters of 10+ (`carrier_quotas`; an unlinked
  member wears at its weapon's linked rate, counts exact). The cap is
  max(floor, max(1, round(share x size))) and counts discretionary wearers
  (a weapon's identity chest, worn by half its builds, is exempt); the floor
  is the cell's median carriers per roster where it is 1 or more, and the
  forge dresses its roster to it after the search (a generated member's
  chest swapped to a carrier its own doctrine tier offers, the cheapest
  swap first; locked members never; the result's `floors` says what each
  effect holds). Below 10 no floor; generation only.
- **Dressed forge**: candidates are priced dressed; forged members arrive with
  kits prefilled (`_eng`-marked); locked members keep their supplied gear and
  are never re-dressed; doctrine passives never enter evaluation. A weapon's
  one alternative kit (`kit_variants` v1) swaps in a piece whose worn
  configuration (the active and passive its wearers equip) carries a
  capability row; a piece that supplies nothing as worn (the plain Cape,
  Soldier Boots on Wanderlust) is named in v0 where winners wear it, never
  as the alternative.
- The forge's minimum-need bound is admissible (never more than a legal
  completion needs, never less); the expansion sort is quantized in both ports.
- **One party, at most 20**: the game seats at most 20 players in a party,
  so the forge (its refresh too), `replace_options` and `refine` refuse a
  party past 20 with the cap message (`PARTY_CAP`, both ports, F47 and the
  parity field `forge_cap`); a zerg is forged party by party (the planner's
  parties). Scoring and reading a manual roster of any size stays allowed.

The dashboard tracks `party`, `PROV` (manual / live / forged), `COMBO` and
`LOADOUT`; `sortPartyByRole()` applies one stable permutation across all of
them, and every roster mutation goes through `data-add` / `data-swapat`. The
forge handler wraps `ENG.forge(goal)` in a target-size `setContent`.

Audit artifacts: `out/economics_report.json`, `out/style_fit_report.json`,
`out/roles_report.json`, `out/roster_mixes.json` (frozen), `out/style_roster_evidence.json`.

## The planner today

Source files: `dashboard/_shell.html`, `_app.js`, `_loadout.js`,
`_decision_layer.js/.css`, `_layout.css`, `_explainer.html`, `build.py`.
Generated: `dashboard/index.html`, `docs/` — never hand-edit.

- **Layout**: a card grid (four columns >= 1700px, three from 1400px, the
  single flow below 1251px; fractional band bounds) in `_layout.css`, inlined
  last. Setup, caller tools, party and live party are `.epanel` edge flyouts
  (one per edge on desktop, one total on phones). The masthead is a status
  bar on one line: fitness and the identity verdict. Content, playstyle,
  planned size, the party count, the forge actions and the build
  diagnostics live in the setup panel; its tab carries a dot while a size
  notice is open, and a parity mismatch raises an alarm in the masthead.
- **A content may ask for its size** (template `size_prompt`; the Dragon
  Portal's pools 3 / 5 / 7 / 20): the switch into it raises the ask, the
  forge slot shows the pools as size controls until one is picked, the
  setup tab names the open ask (the panel opens on a link that arrives
  with the ask raised), a link's `n=` answers it and the link
  carries no `n=` while the ask is open; no generation path forges past
  an open ask; a hand-set plan survives the switch. A template whose
  `fit.stat` is `none` shows the borrowed-evidence notice.
- **Dragon Portal stats page** (`dashboard/_portal.html` ->
  `portal.html`, linked from the masthead and the welcome page): the
  killboard's own read of the Ancient Lands per matchmaking pool, from
  `out/portal_stats.json` (`pipeline/build_portal_stats.py`). Weapons
  ranked by winning parties with their modal winning build, comps seen
  twice or more, dominant share and K/D beside every count, small samples
  marked. A display surface with no engine embedded; the planner's
  recommendations never read it (three layers, never merged).
- **Live members are found by guid** (stamped on the member's loadout);
  the weapon match is the fallback for a slot restored without one, so
  two members on one weapon stay two people. Clearing the comp stops
  live sync. Swap impact and the after-pick gaps read the DRESSED roster.
- **Comp status is THE RADAR**: one axis per capability group against the
  comp-fitted CEILING (100% = soft cap, nothing above 100; purple =
  over-ceiling stacking; pink = under a hard floor); `comp_identity` as
  the headline above the diagram (glyph, name, strength); no label inside
  the diagram and no per-axis target mark; all further prose in hovers.
- **Capability board = four stages** (standing rule 17): red below the bare
  minimum winners get away with, orange from there to the typical winner,
  green from typical to the soft cap, purple past it. The legend reads
  `have / typical`; a `min` chip (from `targetSource`) marks a content row
  still on the old minimum fit, `~` a borrowed harvest cell.
- **Biggest need** (floor failures first) -> **best next pick** with its
  engine-derived explanation, **what it fixes**, **still weak after** (one
  ahead, on the candidate's scored combo), and the **fight chain** strip
  (stages graded at roster size, the pick's claim read one ahead like its
  gain tiles).
- **Kill pressure** (pierce · heal-cut · burst lights) and **role check**
  (seat tally, function and carried-aura chips, advisory flags) as cards —
  descriptive only.
- **Negative recommendations**: `pick_report()` drives the "why not" block,
  dims redundant alternatives, chips covered jobs.
- **Capability supply** as nested rings per group on the same ceiling ruler;
  the full capability board is the deep diagnostic on the same ruler.
- **Observed killboard context**: affinity strip, cohort note, neighbours,
  recurring cores (`out/cohort_families.json`), observed effect quotas — all
  display only. A cohort is a killer party; the strip's artifact is derived
  from the party harvest (`derive_usage.py`), the one killboard sampler.
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
  records never become defaults; `unknown` stays `unknown`. Record conventions
  (source kinds, statuses, the promotion gate): `data/README.md`.
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

`BACKLOG.md` — the one list, grouped by what each item waits on (a maintainer
decision, evidence a validation round would produce, plain engineering,
deprioritized product features). No other document keeps its own list.


## Files to read before major changes

Scoring / mechanics: `albion-comp-engine-design.md`, `MASTERSHEET.md`,
`pipeline/README.md` ("Mechanics"), `pipeline/templates/mechanics.yaml`,
`engine/engine.py`, `engine/app_scoring.js`,
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
