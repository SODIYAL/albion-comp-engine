# Validation — Composition Engine

The index of the ruling log. Every dated round, every owner quote and every score
lives in full under `notes/validation/` (append-only, never edited); this file
carries what has to stay in front of anyone changing the engine: the standing
rules, the method, one line per ruling with its pin and where the full entry is,
and the questions still waiting on the owner. Code and yaml cite the log as
`VALIDATION.md <date>` or by section title — resolve them in the index below.

Archive files (`notes/validation/`): **plan** = `2026-08-12-plan.md`,
**08** = `2026-08.md`, **09a** = `2026-09a.md`, **09b** = `2026-09b.md`.

## Standing rules

Each was ruled once and must not be re-litigated silently. Dates point at the
index rows where the owner's words are.

1. **Anti-circularity** (from the first V4 run, 2026-08-13; disclosed 2026-08-18):
   comps that calibrated a template never drive retuning against their own gate
   results. Findings from gate runs are hypotheses for the owner, never fixes.
   Template retunes need the owner's ruling.
2. **Real comps set the numbers** (2026-08-21): target = 0.9x the least any good
   comp fields, soft cap = 1.15x the most; rows where comps disagree are left
   alone. Since 2026-09-04 the style x band rows apply the same convention to
   harvested winners (p10 / p90) beside the content rows.
3. **Never invent a number to fill a hole** (2026-08-27, 2026-08-28): a row exists
   only where real comps supply the measurement; where evidence cannot ground a
   claim, drop the claim, never reach for the override channel. Say "we do not
   know" in the file.
4. **No rules on individual weapons** (2026-08-23, restated 2026-08-24, 2026-09-01):
   "it should all be based on what the weapon does and its effect." Rulings land
   as derivations from the E's own facts; cited fact overrides correct the
   evidence, never express taste.
5. **Unique-ability first** (2026-08-25; E-first for weapons, 2026-08-24): a
   weapon's identity is its E; a gear piece's is its unique active. Check the
   E's effect, magnitude, radius and delivery first and bring the owner only the
   unresolved cases.
6. **Descriptive layers never score** (2026-08-23 onward): comp_identity,
   kill_pressure, fight_chain, pick_report, the role layer and every killboard
   surface describe; the one sanctioned influence is the suggestion gate, which
   bars generation POOLS only. Manual picks always score.
7. **Popularity is not effectiveness**: the killboard, cohort families and
   reference builds are display/evidence only; effectiveness claims are
   reserved for win-lift evidence (kill-vs-death contrast needs a ruling before
   it orders anything, 2026-09-08).
8. **Unknowns stay explicit** (2026-08-12 catches, 2026-08-28 gear): records store
   `unknown`; quarantined records never become defaults; only verified
   interaction records score.
9. **One unit, everywhere** (2026-08-29): targets and soft caps speak person
   units; a unit conversion can only RAISE a target; hard floors stay in weapon
   units (Option C, 2026-08-27); any re-fit moves every row at once.
10. **Structural floors are source-aware** (Option C, 2026-08-27): floors read the
    weapon+loadout supply only; worn gear never buys floor relief. Synergy is
    weapon-interaction synergy (Model 2, 2026-08-27).
11. **The app models no enemy** (2026-08-28): "our playstyle dictates how we fight
    regardless of who or where." Resistance stays one number; peel is explained
    by comp or content alone.
12. **No automatic 1H damage discount** (2026-08-25): the offhand compensates.
13. **An auto-attack steroid is not large-scale utility** (2026-08-24).
14. **Kits are what winners wear** (2026-09-01, 2026-09-03): the kit channel speaks
    evidence end to end and proposes nothing where evidence runs out; the VOTER
    is the player (2026-09-04); the evidence unit is the killer party of 10+.
15. **A miss where the expert is right becomes a golden case.** Golden tests are
    the regression floor and are all train-contaminated by definition.
16. **Tuning discipline** (train / validation / holdout, 2026-08-27, kept
    2026-09-10): train may be inspected freely and anything ever discussed is
    train forever; validation compares settings on aggregates only; holdout is
    never examined while tuning, scored once when a round is declared finished,
    then retired. Until validation and holdout sets exist, any parameter sweep
    is a sensitivity map — no coefficient moves on train evidence alone.

## The method — how a round runs

The identity system, the role book and the kit doctrine were built by **blind
rounds** with the owner: present cases, collect the owner's call BEFORE
revealing the engine's, log both, and convert every disagreement the same day
into a ruling, a cited override, or a golden pin. Forms: `tests/tier2_blindtest.py
generate|score` (V3 next-pick forms; `score --mode d` is the gate),
`pipeline/audit_style_rosters.py --blind-sizes LO HI --blind-round N` (harvested
rosters, weapons only), `pipeline/kit_blind_round.py` (a weapon's most-worn
builds without labels), `tests/gear_blindtest.py` (gear doctrine cards). Graded
battles join `GRADED_BATTLES` so no later form re-samples them. Owner
disagreements that the data contradicts are shown the data (2026-09-04 roster 5,
2026-09-08 Arcane helmet); the ruling then stands on the evidence, not the
guess.

Gates (CI, exit code): the list in CLAUDE.md. The recommendation-quality gate is
`tests/tier2_blindtest.py v4` — `actual_gear` role-level >= 70% on published
comps minus one member (re-based from `weapon_only` 2026-08-29; it enforces via
exit code since the same day). Read the current output; historical pass counts
in the log are history.

## Rulings index

One line per ruling or landed finding. `Pin` names the test that holds it
(T golden, F forge, R roles, V validation-modes, H builds, L layout). The last
column is the archive file and the section title to search for.

| Date | Ruling / finding | Landed as | Pin | Where |
|---|---|---|---|---|
| 08-12 | Hard floors are load-bearing (soft targets alone let breadth out-rank a healer) | `hard_floor` mechanic | T1–T7 | plan, V1 |
| 08-12 | Momentary defensives ground no tankiness (pseudo-tankiness) | 41 scores removed | — | plan, V1 status |
| 08-12 | Directionality rule; per-item sheets with mandatory `evidence_spell` | catches #1/#2, evidence lint (V5b) | lint | plan, V5 |
| 08-13 | First V4 run 69%; nothing retuned — anti-circularity stated | standing rule 1 | — | 08, First V4 run |
| 08-18 | Style-declared scoring, anti_zone/damage_debuff trims, redundancy + viability; 77% — reweights PROVISIONAL | scoring.yaml | — | 08, V4 after the forge rework; Circularity disclosure |
| 08-18 | Chillhowl (`MAIN_FROSTSTAFF_AVALON`) excluded >= 10 | composition.yaml exclusion | H16 | 08 (cited 09-02) |
| 08-21 | Real comps set the numbers: 0.9x least / 1.15x most; Bist's Roam 15 admitted | 31 rows re-fitted | T15 | 08, RULED + RECALIBRATED |
| 08-21 | Hoarfrost scores adjudicated; shield break sits below true purge | sheets | — | 08 (cited 08-25) |
| 08-23 | V3 round 1: 12/12 role-level; clump-first is right (case 4) | no change | — | 08, FIRST V3 ROUND |
| 08-23 | Partial comps have an identity — `comp_identity` descriptive v1 | both ports | T23 | 08, FIRST V3 ROUND (F-V3-2) |
| 08-23 | "It's a bomb squad ... a different play style" — new archetype | comp_identity | T23e | 08, BLIND LABEL SPOT-CHECK |
| 08-23 | Utility carriers never anchor a damage-identity split (Harpoon) | derivation | T23e | 08, BLIND LABELS 3/4 |
| 08-23 | "clap kite could be its own playstyle" — fifth style | styles.yaml `clap_kite` | T23f | 08, BLIND LABELS 3/4 |
| 08-23 | Crystal weapons too expensive below 30 — cost gate (RETIRED 09-07) | viability.cost_gate | F14/T27 | 08, FORGE-QUALITY BLIND ROUND |
| 08-23 | A hybrid healer can never be the sole foundation — full_healer = E heal >= 6 AND group scale | `full_healer`, `heal_overrides.yaml`, primary_heal minima | F15/T27/T27c | 08, FORGE-QUALITY; ROUND 2 REFINEMENT |
| 08-23 | Role bands per style: 20-man healers brawl 3-4 / clap 2-3 / kite 2; frontline caps | styles.yaml `constraint_overrides` | F16 | 08, FORGE-QUALITY |
| 08-23 | Great Holy is brawl-only ("has to stop moving") | style_overrides.yaml | T27 | 08, FORGE-QUALITY |
| 08-23 | "I don't want to make rules on individual weapons" — standing rule 4 | — | — | 08, ROUND 2 REFINEMENT |
| 08-23 | "leave it, keep everything consistent" — bands split trio/gang/group, no 4-5 seam | — | — | 08, ROUND 2 REFINEMENT |
| 08-23 | Situational never generated: the generation-fit gate (fits at band; balanced = fits somewhere) | both ports | F17/T28 | 08, ROUND 3 |
| 08-24 | Single-ally-heal-E healers never generate at 10+ | healer gate | T28b | 08, ROUND 4 |
| 08-24 | Duplicates earn their place: default 1 copy; allowances cite real comps; clump_core derived | composition.yaml | F18 | 08, ROUND 4 |
| 08-24 | CURSEDOT verified non-stacking (count once) | interactions | interactions | 08, ROUND 4 |
| 08-24 | Hellfire is brawl-clap, not clap | style_overrides.yaml | T29 | 08, ROUND 4 |
| 08-24 | "usually 2 curse is max" — curse_pressure derived, max 2; clap_kite healers 3-4 at 20 | composition/styles | F18b/F16 | 08, ROUND 5 |
| 08-24 | Round 6 withdrawn: no weapon-specific rule; "check first and then ask me" (E-first directive) | standing rules 4/5 | — | 08, ROUND 6 SUPERSEDED |
| 08-24 | Two-prong E rule: single-target Es, or low damage AND nothing for the group, bar generation | `weak_group_e` derived; Warbow / 1H Fire / Hellspawn cited overrides | T31/T31b | 08, ROUND 7 RULED |
| 08-24 | Battle Bracers' E damage was never scored — curation gap fixed | sheet burst_aoe 4 | T31 | 08, ROUND 7 (C7-A) |
| 08-24 | Spirithunter is clap ("massive pierce that enables the whole dps line") | style_overrides.yaml | T31c | 08, ROUND 7 (C7-B) |
| 08-24 | Bloodletter prominence is a mount-carrier artifact; Galatine Pair is a solo bomb | no gate change | — | 08, ROUND 7 (C7-C/D) |
| 08-24 | Fists of Avalon purge 4; Trinity Spear group-unfit — an auto-attack steroid is not large-scale utility | MASTERSHEET; style_overrides | T31d | 08, FIRST FULL E-AUDIT |
| 08-25 | Non-stacking slots are EARNED by an E debuff tool (Damnation / Lifecurse / Rotcaller) | derivation + gate | F19 | 08, ROUND 8 |
| 08-25 | "bigger than 15" = the group band at 10+ (confirmed round 9) | band seam | — | 08, ROUND 8/9 |
| 08-25 | Engine darlings stand; Evensong burst 4 -> 2, Damnation 6 -> 2 by the numbers; Clarent is AoE | sheets | — | 08, C7-E RULED; ROUND 9 |
| 08-25 | Size-physics tables owner-confirmed (Q16) | mechanics.yaml | — | 08, Q16 SIGNED OFF |
| 08-25 | Resilience penetration wired as a partial rebate; RULE batch fine; no 1H discount (Rotcaller 2 -> 4); Evensong heal-cut 3 | resilience_penetration.yaml | F20 | 08, ROUND 9 |
| 08-25 | The role layer: roles are member-in-comp properties, weapons carry menus, roles never score | roles.yaml, roles-design.md | R1–R6 | 08, ROUND 10 |
| 08-25 | Taxonomy is FUNCTIONS (pierce / purge / anti_heal) beside uniformed SEATS; primary from the E, secondary from Q/W | derived sweep | R7/R8 | 08, Owner grading; E-FIRST TIERED SWEEP |
| 08-25 | Shield break split out of purge (Black Monk primary) | `spells:` on role records | R9 | 08, Third grading pass |
| 08-25 | Equipment identity = its unique spell; class from the numbers; offhands classified by stats; Mistcaller/Lymhurst are self buffs | `classify_gear`, role_affinity | R10/R11 | 08, Fourth–Seventh passes |
| 08-25 | Kit doctrine covers "the whole build ... food, potion and capes"; passives per class; Leering Cane as physics (`cc_mult_caps`) | kit_options uniform gate + doctrine tiers | R12–R16 | 08, INCREMENT 2 |
| 08-26 | Full-board grading: 15 rulings (Iron-clad off stopper, Great Holy brawl healer, Witchwork/Black Monk off shield_support, frost dps off zone_support, Great Arcane setup seat; kit overrides; Dagger Pair + Deathgivers excluded >= 7) | roles.yaml, composition.yaml | R17 | 08, FULL-BOARD GRADING |
| 08-26 | "its fine if a weapon wears that armor once but ... find why" — per-weapon doctrine + effect quotas | `kit_weapon`, `effect_quotas` | R18 | 08, INCREMENT 2.5 |
| 08-26 | "what matters is what the data says" — need profiles from rosters (engage > stopper) | roles.yaml `need_profiles` | F21 | 08, INCREMENT 3 |
| 08-26 | "I dont want to set a hard rule that a weapon needs to be range or melle" — the conditional-payload rule (ramp / channel Es are situational for clap) | `channel` fact, derive_style_fit | T32 | 08, CONDITIONAL-PAYLOAD RULE |
| 08-26 | Kite gets the same rule plus a ranged core min 5 at 20 / 4 at 15-19 | styles.yaml | T33 | 08, KITE EXTENSION |
| 08-27 | "never above 100 ... based on ground facts" — the display ruler: 100% = soft cap | dashboard | layout | 08, THE DISPLAY RULER |
| 08-27 | Six orphan capabilities promoted with rows only where comps exist; castle / faction_war left unscored | templates | — | 08, SIX CAPABILITIES PROMOTED |
| 08-27 | `reveal` refused (every weapon source is a purge); "reduce enemy CC resistance" retracted; Defensive Slam curated | effect_map.yaml | lint | 08, THE LAST TWO EFFECTS |
| 08-27 | Effect catalogue covers gear; six bad claims caught, Demon Armor's tankiness was backwards | gear sheets | lint | 08, THE EFFECT CATALOGUE NOW COVERS GEAR |
| 08-27 | "search more comps to see what tanks are actually wearing" — doctrine-tier-first kit ranking | both ports | T22 | 08, GEAR COMBAT EXPANSION |
| 08-27 | Dressed forge: candidates priced dressed; re-pin with the dressed fixture | both ports | T30c | 08, DRESSED FORGE |
| 08-27 | Option C: structural floors read weapon+loadout only; gate re-basing deferred; synergy Model 2; next round prepared; locked_gears / dressed refine | both ports | V5, F25/F26 | 08, FIVE RULINGS DELIVERED |
| 08-28 | "they always bring 2 or more [Demon Armor]" — reflect structural, `self_costs`, `self_cost_offset_min_copies` (the only super-additive duplicate) | sheets, interactions, build_extra | interactions | 08, REFLECT + SELF-COSTS |
| 08-28 | Corpus style labels; bomb squad and the tracking comp get no style (`fit_exclude`); DH parties 2/3 excluded | published_comps | tier2 | 08, THE STYLE LABELS |
| 08-28 | "zvz 20man can be blackzone roaming or castle outposts or ..." — `content_candidates` | builds_lib | — | 08, ONE COMP, SEVERAL CONTENTS |
| 08-28 | Do not split resistance; the app models no enemy | mechanics.yaml | — | 08, WIKI RESEARCH PASS |
| 08-28 | Ranged core 7 at 20 (clap / clap_kite); Icicle stays zone_support; healers at 5-7 stay 1-2; effect quotas graduate to advice | styles.yaml, dashboard | F21, display 14 | 08, FOUR RULINGS |
| 08-28 | Gear resolver: item ids, caller shorthand ("GG", "blink", "cleanse") | builds_lib | builds | 08, GEAR RESOLVER |
| 08-28 | anti_zone and execute are OPTIONAL rows (denominator only) | templates `optional` | V | 08, Optional capabilities |
| 08-28 | Peel = enemy CC plus cancelling enemy CC on an ally; protection is buff_allies/tankiness | effect_map, five claims removed, Polymorph re-cited | lint | 08, Peel is CC |
| 08-28 | Ignore tier everywhere in gear lookup (Gigantify was scored zero) | `gear_key()` both ports | — | 08, Tier-agnostic gear lookup |
| 08-28 | `target_mults` mechanism (floors never scale; balanced empty); burst_aoe 1.71 / 1.29 derived from ruled seat counts; "go with your recommendation" — kite peel 1.25, disengage 1.20 | styles.yaml | V6 | 08, Per-style target modifiers (three sections) |
| 08-29 | "do what needs to be done" — corpus 13 -> 36 comps, author-declared styles; re-derivation changed nothing (tier2 saturated) | published_comps | H16 split | 08, Corpus ingestion; Re-derivation |
| 08-29 | THE UNIT RE-FIT — "go ahead": 152 rows to person units; a conversion can only add; 13 gear-fed caps moved | templates | T26/T30d | 08, THE UNIT RE-FIT |
| 08-29 | Gate re-based to actual_gear and it now enforces ("ok do that") | tier2_blindtest | exit code | 08, Gate re-based |
| 08-29 | Killer parties from `GroupMembers`; "it's okay if the losing party couldn't get a single kill" | sample_parties.py | — | 08, Real party rosters; The party sample's bias |
| 08-29 | Observed builds validate the role book (frontline 85% plate, healers 72% cloth); Nature Staff plate contradiction OPEN | — | — | 08, Observed BUILDS |
| 09-01 | "fix the underlying issue" — fail-closed kits: no seat, no kit; no tier, slot unset | both ports | R19 | 09a, Fail-closed kit generation |
| 09-01 | "lets fix seat for all weapons" — 135/137 seated, `curse_support` seat | roles.yaml | R17 | 09a, THE SEAT-ALL PASS |
| 09-01 | Killboard as a doctrine stream, noise floors; Leering Cane add retired by observation | derive_kit_doctrine | R18 | 09a, KILLBOARD KIT DOCTRINE |
| 09-01 | "based on what real people wear" — the conditional modal build chain fronts the kit | `kit_build`, both ports | R20 | 09a, THE OBSERVED-BUILD OVERLAY |
| 09-02 | Chillhowl off every menu; Stillgaze is a d-tank; Iron-clad "some random rat weapon" | roles.yaml | R17 | 09a, The two exceptions ruled |
| 09-03 | Bug round: need measured dressed; two-handers have no off-hand; one role read (seat); Occult is support; "reforge all" reports Unchanged | both ports, page | T22, R21–R23 | 09a, Owner bug round |
| 09-03 | THE KIT AUDIT: carriers are weapon evidence; observed chest class admitted; chain guards; count-first ranking; carrier quota; identity chest exempt; evidence band; party_size >= 10 is the evidence unit | build_dataset, both ports | R24–R26, T22 | 09a, THE KIT AUDIT (+ two addenda) |
| 09-04 | Harvest refresh, deep harvest, the overnight task; R18 pinned as a mechanism | harvest_overnight.ps1 | R18 | 09a, Harvest refresh; Deep harvest |
| 09-04 | Blind round 1 (4/10 -> 7/10): Galatine is not a clap bomb, Realmbreaker is; the kite half is STANDOFF TOOLS | comp_identity, `standoff_e` | T34 | 09a, Blind round 1; Rulings from blind round 1 |
| 09-04 | Rift Glaive's ramp is FREE (`ramp_free`); Carving checked against the harvest; "brawl is dps on leather, clap and kite on cloth" — kits decide a split | derive_style_fit, comp_identity | T35 | 09a, Rulings batch 2 |
| 09-04 | Blind round 2 (8/16 -> 12/16): flex bombs join the rigid core; slow fields are standoff tools; bomb line 0.45; THE BALL CARRIES THE BOMB; roster 5 re-ruled brawl on its kits | comp_identity | T36 | 09a, Blind round 2 |
| 09-04 | "ok do it" — style x band rows beside the content templates, generated from winners (p10 / p90); zero p10 = soft-cap-only; target_mults never stack | derive_style_bands.py, style_bands.yaml | T37 | 09a, Style x band rows |
| 09-04 | "go ahead with your recommendation" — the movement four admitted; fixtures judged DRESSED | derive_style_bands | T37/T38 | 09a, The movement four |
| 09-04 | One player, one vote — every doctrine floor counts distinct people | sample_parties, derive_kit_doctrine | R27 | 09a, One player, one vote |
| 09-04 | Doctrine per size band: group (10+) and GANG (4-9) via `_seat_kit` | both ports | R28 | 09a, Kit doctrine per size band |
| 09-05 | Blind round 3 (4/10 -> 8/10): a lone tool only makes a kite of a non-bombing comp; the bomb's delivery names the mid band; flex home needs 2x melee; utility-carrier exclusion REJECTED | comp_identity | T39 | 09a, Blind round 3 |
| 09-05 | "grailseeker can be kite or d tank. accept" — leather admitted; a root field at range is a standoff tool | kit doctrine, `standoff_e` | R6/R12/R26 | 09a, Harvest refresh, first overnight run |
| 09-05 | "point of clap is high dps which is not possible if majority ... wearing leather" — leather-majority dps overrule a weapons-decided clap to brawl; bomb squad exempt | comp_identity | T40 | 09a, Kit blind rounds 1-2 |
| 09-05 | Per-item chest lean (Royal Jacket / Tenacity / Hunter Jacket lean ranged) | `chest_lean.json` | T41 | 09a, Per-item chest lean |
| 09-07 | "not restricting weapons but rather focusing on mechanics" — THE COST GATE RETIRED; anti_zone rows deleted at 7-man contents | both ports, templates | T42/F14 | 09b, Cost gate retired |
| 09-07 | "don't really need it at 10-14 ... a good requirement at like 25+" — `ramp: {none_until: 14, full_at: 25}` | both ports (general row mechanism) | T42/F14 | 09b, THE ANTI_ZONE DEMAND RAMP |
| 09-08 | Blind round 4 (9 exact / 3 half / 1 miss of 14); gank tells ("claws, dagger pair, whispering bow"); Bloodletter stack = battlemount sub-party | comp_identity (nothing retuned) | T43 | 09b, Blind round 4 |
| 09-08 | "go ahead and do 1 and 2"; "Declared style only" — chain guard by shares; style cells with the 5-voter floor per slot | build_dataset, `_seat_kit` | R29–R33, R24b | 09b, Coherent builds and style cells |
| 09-08 | "1 healer per 5 people ... for clap" — `role_min_per_players`, a minimum with no cap | styles.yaml | F16 | 09b, mastersheet review |
| 09-08 | "i leave it up 2 you" — seat pooling for thin slots (same-chest pool 80% vs 58%) | `kit_pool`, `kit_by_chest` | R34a/b | 09b, Seat pooling |
| 09-08 | Double Bladed "a good ganking weapon but not a good brawl weapon" — excluded >= 10 after the stats | composition.yaml | F27 | 09b, The Double Bladed audit |
| 09-08 | "when an e lands the caster should read as melee delivery" — payload reach, not travel (`caster_moves`); flex bombs excepted | parse_dumps, derive_style_fit | T45 | 09b, Payload reach, not travel |
| 09-08 | "sure on 3" — the meta prior is GENERATED from the harvest; hand-set maps refused at build | derive_meta_prior.py | T46/H18 | 09b, The generated meta prior |
| 09-08 | Healers per five on every style but kite and balanced; balanced at 25 OPEN | styles.yaml | F16 | 09b, Healers per five |
| 09-08 | "ok on arcane helmet" — chain steps need 5 voters | CHAIN_STEP_MIN_VOTERS | R35 | 09b, Chain-step voter floor |
| 09-08 | "you r hoarfrost ruling" — Avalanche burst_aoe 3 | MASTERSHEET | T44 | 09b, Hoarfrost burst_aoe 3 |
| 09-09 | First fold (2,042 -> 3,583 battles); `[id, count, players]` rows, THIN judged on people; audit slack at the half-line | build_dataset, both ports | R24b/R28 | 09b, first fold |
| 09-09 | Harvest review: twice-daily task, `--workers`, three retries; second floor stays 8; EU is an OWNER CALL | harvest scripts | — | 09b, harvest review |
| 09-09 | "go ahead with your recommendations" — a zero-heavy capability has no harvest minimum (`zero_share` >= 0.05 = soft-cap-only) | derive_style_bands | V7 | 09b, ruling: a zero-heavy capability |
| 09-10 | The sweep: the page reads `ENG.reqs`; the forge's need bound made admissible; expansion sort quantized | both ports, page | L19, F28 | 09b, the sweep |
| 09-10 | R36: a failed PICK skips its slot, only a failed POOL ends the chain; F29: the need bound discounts only provable bodies; territory_defense at 25 OPEN | build_dataset, both ports | R36/F29 | 09b, Chains reach past a slot |
| 09-10 | Calibration scaffold retired; the tuning discipline kept as standing rule 16 | — | — | 09b, the calibration scaffold retired |

## Open questions recorded in the log (owner rulings pending)

HANDOFF.md carries the working list; these are the ones the log itself left open,
with where the evidence sits.

- Nature Staff seated main_healer but 53% of users wear plate (08, Observed BUILDS).
- `MAIN_FROSTSTAFF_AVALON` >= 10 exclusion premise is weaker since "AvA Raid" fields it (08, Corpus ingestion).
- Whether a cloth Lifecurse should detect as dps (09a, THE KIT AUDIT addendum).
- A descriptive `gank` read at <= 14 — proposed, not built (09b, Blind round 4).
- Is the Infernal Staff's E a standoff tool; should one tool out-vote five ranged dealers at 0.36 (09b, Blind round 4 roster 5).
- A frontline's damage points making a ranged carrier (09b, Blind round 4 roster 11).
- `balanced` healers at castle 25 (3 forged; the guild sheet says 4 minimum) (09b, Healers per five).
- territory_defense at 25: stopper minimum 3 inside a frontline cap of 5 deadlocks the search (09b, Chains reach past a slot).
- Carrier FLOORS (which of the six gear effects are needs); the guild's "2 Royals per 10" is not supported by the harvest (09b, Other numbers).
- Kill-vs-death contrast and item-power gating (09b, Coherent builds; Seat pooling).
- Adding the EU server to the harvest (09b, Coverage, not speed).
- Whether 10-14 should field the Exalted Staff (09b, Cost gate retired).
- Hellfire Hands in kite generation (08, KITE EXTENSION); `brawl_clap` target_mults (08, Per-style targets round 2); blap's low disengage vs winning brawls (09a, The movement four).
