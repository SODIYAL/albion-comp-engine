# Backlog

The one list of open work. Every other document points here instead of
keeping its own. Grouped by what each item is waiting on, because that is the
question that gets asked: what can be decided now, what needs more evidence,
what is just work. One line per item, with where the evidence or the record
sits (`V:` = the `tests/VALIDATION.md` index / `notes/validation/`; `Q<n>` =
the mechanics question ledger in `pipeline/README.md` "Mechanics"). Shipped
items are deleted, not struck through — git has them. Closed decisions are
index rows in `tests/VALIDATION.md`, never here.

## Needs a maintainer decision

Each is decidable today from evidence already in the repo.

- **The baseline finding** (`tier2_blindtest.py --baseline`, report-only):
  ranking candidates by role need then the prior's solo share names the
  exact missing weapon 29% of the time on the published comps where the
  engine names it 13% (rebuild-5 on the harvest: 30% vs 14%), and loses at
  role level (57% vs 74%; 81% vs 84-86%). Popularity carries the exact-weapon
  signal the capability model's tiebreak-sized prior does not; the
  capability model carries the structure. A hypothesis, never tuned on
  (standing rule 16): raise `delta`, blend the ranker, or accept that the
  engine optimises comps rather than the published pick. (V: 09b,
  Skeleton-first)
- **Healer pricing at 7** (V3 round 2, Castle Outpost 7): dressed mode
  ranks Great Holy and Rampant above Hallowfall in every healer case
  because the incumbents' doctrine kits already close disengage and
  mobility and the choice falls to `heal_sustain` (weight 10, target 4.5;
  two-handers supply 3.0 units, Hallowfall 2.0). Killer parties of 6-8
  field Hallowfall in 29.1%, Rampant in 1.0%. Candidate causes: the
  castle_outpost sustain : burst pricing, or worn gear closing utility
  targets. Decide which before any golden pin. (V: 09b, V3 round 2)
- **The V3 generator seeds from every weapon**: partial parties are drawn
  from the whole pool, so forms carry Glaive, Druidic Staff, Spear, Pike
  and Warbow at seven, weapons the harvest fields in under 2% of size-7
  killer parties. Proposed: seed from harvested killer parties at the
  form's size, members removed at random, graded battles and the holdout
  slice excluded. Changes what a round measures. (V: 09b, V3 round 2)
- **Kite weights**: with the seat skeleton and the standoff minimum the
  forged kite 20 reads clap_kite to the engine's own identity (it read as a
  strong clap before); a PURE kite read needs the kite style's multipliers
  — never validated — to prefer sustained ranged pressure over bombs. Label
  a forged kite in the next validation round.
- **Fill order as the beam's sequence** (healer -> frontline -> support ->
  dps, the guild sheet's "10-20 FILL ORDER"): the seat skeleton fixes the
  END state; the greedy beam still picks its path by marginal. Ordering
  changes many pinned first picks — a maintainer decision, not started.

- **Gap-closers and ranged_presence: should `caster_moves` deny by default?**
  `derive_ranged_presence` grants from structure (ground/enemy target,
  cast_range >= 9) and denies leaps only by hand in `ranged_overrides.yaml`;
  the parser carries `caster_moves` and this path never reads it. The three
  obvious cases (Fists of Avalon stays, Trinity Spear melee, Skystrider
  ranged) are cited overrides, which leaves two undecided grants a default
  would flip: Rift Glaive's Razor's Edge (caster moves, 17 line) and Spiked
  Gauntlets' Gravitational Collapse (no leap - a 13 cone "in front of you";
  is a brawler's long cone ranged pressure?). Decide those two and the
  derivation can read the fact. (V: 09b, Duplicates never outrank a
  distinct bomb)
- **Is one unit of shred "pierce on the clump" in a 7-man?** The kill
  lights bar on the bare minimum ("enough to kill" is a minimum question,
  standing rule 17), and castle_outpost's refreshed three-comp fit says the
  least winning 7-man brought exactly one unit of resist_shred — so the
  burst trio (Longbow / Witchwork / Permafrost, one unit) now reads pierce
  GREEN where the earlier pin (T25b) said red. Thin evidence, not a
  semantic call: decide it (a fourth castle-outpost comp would settle it),
  or raise the content `min` for resist_shred by hand. (V: 09b, Target is
  the median; T25b)
- **Repo size: `pipeline/out/party_rosters.json.gz` is 52 MB and committed**,
  growing with every fold (it was 83 KB before builds joined the artifact
  and 4.4 MB the same day they did). The split proposed then: commit the
  aggregates, gitignore the raw `builds` array beside the other caches. Not
  done because the raw builds are the evidence. Decide. (V: 08, Observed
  BUILDS)
- **The Armory import path** (`data/armory_imports/`, `pipeline/parse_armory.py`,
  `out/armory_activities.json`, the H-test fixture): built, never fed — the
  Armory has no export and the harvest now supplies the same class of
  evidence at scale. Keep the door or remove it.
- **EU server in the harvest**: would double the 25+ corpus but mixes a second
  server's meta into rows meant to describe the maintainer's own fights.
  Review deferred to the date the log entry records. (V: 09b, Coverage, not
  speed)
- **territory_defense at 25** forges one to two members short (brawl / clap /
  kite): the profile scales stopper_tank to a minimum of 3 inside a frontline
  cap of 5, and the deadlock guard checks capacity exists, not that it is
  enough. Wider band, lower stopper scale, or a counting guard. (V: 09b,
  Chains reach past a slot)
- **`balanced` and the one-per-five healer minimum**: it keeps the base band
  and forges 3 healers at castle 25; the guild sheet says 4 at 20+ with no
  style attached. (V: 09b, Healers per five)
- **Role counts past the minimum at 21+**: the typical role count (standing
  rule 18) holds the forge to the evidence through size 20 (healer /
  frontline / support, per style at 10+); the harvest has no 21+ rows, so
  castle 25 still forges 6 healers on clap — the scorer's preference, to be
  graded, not assumed right. A 21+ harvest band closes it. (V: 09b, Tanks
  and supports)
- **Supports UNDER typical on clap / clap_kite at 20** (forge 2, cell p50
  4): a typical only bars bodies beyond it; the shortfall is a support
  demand question (which support capabilities the 20-man rows under-ask
  for), not a role-count one. (V: 09b, Tanks and supports)
- **Sub-10 tanks and supports rest on three castle_outpost comps** (roads
  has one, so it reads the healer row only). More sub-10 published comps,
  or a sub-10 killboard filter that separates content comps from open-world
  squads, would let the harvest carry them. (V: 09b, Tanks and supports)
- **Melee instant-payload bombs in clap dps** (Spiked Gauntlets, Realmbreaker)
  generate under the standing conditional-payload rule; the "bomb builds
  in clap" complaint has no derived rule left without a new one. (V: 09a,
  bug round)
- **A descriptive `gank` read at <= 14**: catch-and-execute damage core with
  no bomb share (claws, dagger pair, whispering bow — catching and
  dismounting); would label the board, stay OUT of the style rows, never be
  a forge style. Until decided those rosters vote into brawl / clap at
  10-14. (V: 09b, validation round 4)
- **Is the Infernal Staff's E a standoff tool** (it alone made a kite of
  round-4 roster 5), and should one tool out-vote five ranged dealers at bomb
  share 0.36. (V: 09b, validation round 4)
- **A frontline's damage points making a ranged carrier** (Witchwork, round-4
  roster 11) — same shape as the rejected utility-carrier rule. (V: 09b)
- **Carrier FLOORS**: which of the six gear effects are needs. The harvest has
  Royal Armor on 3.65% of builds at 20-59 (~0.7 per 20) against the guild's
  "2 Royals per 10". Increment 3b's second half; then mechanism pairing rules
  for effect carriers. (V: 09b, Other numbers; roles-design.md)
- **Kill-vs-death contrast** in kit doctrine: needs a win-lift decision before
  it orders anything (effectiveness claims are reserved for win-lift,
  standing rule 7). (V: 09b, Coherent builds)
- **Item-power gating**: the harvest's `item_power` is the API's average; the
  per-slot tier lives only in the raw cache. Five questions: which slot
  decides "geared", tier line or relative, per size band, quality, doctrine
  votes only. (V: 09b, Seat pooling)
- **A dps seat for cloth Lifecurse** (9% of winning builds, Assassin Hood /
  Soldier Helmet kits; the book gives the 1H curse line no dps seat). (V:
  09a, THE KIT AUDIT addendum)
- **Nature Staff**: seated main_healer, 53% of its users wear plate (n=93).
  Plate frontline healer, or a wrong seat. (V: 08, Observed BUILDS)
- **`MAIN_FROSTSTAFF_AVALON` (Chillhowl) >= 10 exclusion**: its stated premise
  ("no build fields it at 10+") is weaker since "AvA Raid" (10 players)
  fields one; the record is candidate, the exclusion stands. (V: 08, Corpus
  ingestion)
- **Chillhowl / Stillgaze / Iron-clad menus**: off every seat pending a
  decision (Stillgaze has stopper_tank; the other two stay out).
- **Hellfire Hands in kite generation**: its E is unconditional so the derived
  rule passes it; the clap exclusion is a clap-scoped override. (V: 08, KITE
  EXTENSION)
- **`brawl_clap` target_mults**: undecided, n=3 declared; every clap row beyond
  burst_aoe likewise (peel / disengage flipped sign between samples). (V:
  08, Per-style targets round 2)
- **Whether 10-14 should field the Exalted Staff** (7% of winners do; one
  curated 10-man does); the lever is the ramp anchors, never a weapon rule.
  (V: 09b, Cost gate retired)
- **Per-spell `burst_aoe` escalation gating** (Q10 refuted the uniform AoE
  class; factors are extracted on `cap_delivery.escalation`, not wired).
  Its stated precondition — a styled validation pass — is met: rounds 1-4
  have run. Also PROVISIONAL: `radius_targets`, `reference_clump: 2`,
  travel-distance footprints uncounted. (Q9 / Q10)
- **The enemy model** (Q2 / Q2b / Q5): attackers-per-target and
  expected-targets-hit are style properties, delegated to curation under the
  Q14 ordering rule; no public numeric source exists. Open inside it: the
  unit-scale of one dedicated attacker, expected targets per content size
  for the escalation curve (caps at 8). (Q14)
- **Asymmetric numbers at 21+** (Q11 / Q13): Disarray is a no-op in a mirror
  fight; CC Escalation vs Disarray vs forced-dismount immunity removed at 21+
  need netting together. Parked until templates gain an enemy-size field;
  the app models no enemy (standing rule 11).
- **A dive / assassination style**: only as a 20+-size style, if ever
  (curation judgment). Not started.

## Needs evidence a round would produce

- **The V3 round 2 Blackzone Roam 20 form is waiting for answers**:
  `tests/tier2_form_r2_blackzone20.md` (seed 20260828), richer fields,
  engine output hidden. Score with `tests/tier2_blindtest.py score --mode
  both`. Answered blind it is the first uncontaminated validation case;
  the Castle Outpost 7 form was answered as a reviewed draft and is train.
  (V: 08, the dressed-forge decisions, item 4; 09b, V3 round 2)
- **Harvest V4 findings** (`tier2_blindtest.py v4h`, true holdout since the
  style board learns from the training split): at `--n 500` (1,500 drops)
  role-level 59% (harvest_gear) against the baseline's 55%, weapon top-3 5%
  against 18%; rank metric median 31 against the baseline's 20, top-10 15%
  against 33%, MRR 0.070 against 0.177; 173 of 1,500 dropped weapons sit
  outside the suggestion pool. The 150-party reading (68% against 47%) was
  sample noise. v4h stays report-only (maintainer decision) until the
  outcome audit has run. Hypotheses only (standing rule 1), nothing
  retuned. (V: 09b, Harvest V4)
- **The 20+ identity band**: no validation round yet; kite|20 still borrows
  kite|15-19 (31 distinct rosters) and brawl_clap borrows brawl in every band.
  A round once the harvest can stand it. (V: 09b)
- **Blap's escape**: winning brawls at 20 carry more disengage / knockback in
  their bottom decile than blap does (7 vs 16, 5.8 vs 10.3); the next brawl
  round should ask whether the escape is real. (V: 09a, The movement four)
- **Calibration sharpening**: targets stay conservative (median coverage
  ~1.8x); tier2 has saturated as a discriminator for per-style targets at
  this corpus size, so sharpening needs held-out labelled comps or
  validation rounds under the train / validation / holdout rule, not another
  sweep. Watch: castle-25's saturated tail. (V: 08, Re-derivation; THE UNIT
  RE-FIT)
- **More caller sheets** in `data/published_comps/` remain the highest-value
  growth per observation: they are the only source of whole comps with roles,
  which calibration and the V4 gate need.

## Engineering work, unblocked

- **Regenerate the evidence board on the harvest machine** so `balanced`
  gets its pooled median rows: `py -3 pipeline/audit_style_rosters.py`
  (needs the raw party cache, harvest machine only) -> `derive_style_bands.py`
  -> `build_dataset.py` -> the gates. Target-is-the-median shipped the pooled
  `balanced|<band>` cell in the audit and the engine reads it like any
  style, but the committed board predates it, so balanced at 10+ still reads
  the content row (labelled `content` / `min` on the board) until the audit
  reruns there. (V: 09b, Target is the median)
- **Gear-active doctrine — pick the ability people equip, not the one that
  scores best.** `default_gear_choice()` takes the sheet option worth most
  under the template's weights; where a strong-on-paper ability is never
  taken (Cleric Cowl's Force Field: MetaBattle 4/4 Ice Block) that credits
  phantom supply. Mine an observed active per item (and per size band where
  the evidence splits) from every source that records gear abilities —
  MetaBattle `gear_spells_raw`, caller sheets, the companion's spell array if
  it carries armor actives (verify) — the engine prefers the evidenced
  active, keeps the argmax as a labelled `assumed` fallback, and the UI
  exposes the pick like Q/W/E. Do this BEFORE the gear pools below, which
  would otherwise spread the Force Field over-credit to all ten cloth heads.
  (V: 09b, Cleric Cowl)
- **Gear pools — the tree-shared actives are uncurated.** Every cloth head
  carries Energy Barrier + Force Field as its first two actives and only the
  third is unique, yet only Cleric Cowl's sheet cites Force Field; a Fiend
  Cowl running it supplies zero knockback / peel. Same for every armor tree
  and slot. Give gear the weapon sheets' pool structure (`sheets/gear/pools/`
  per tree x slot, each item's sheet keeping its unique active), so the
  engine's one-active-per-piece pick chooses among what the item can really
  equip. Recorded as pending (the tree-shared first two abilities await
  curation); do it BEFORE any gear magnitude review. (V: 08, Fourth pass)
- **Magnitude audit queues** (`py -3 pipeline/build_magnitude_review.py`,
  a board generated locally into the gitignored `review/`): the PASV queue
  (39 rows where a passive / stat sentinel grounds a score >= 2 — each needs
  a justification or a downgrade) and the TOP review (44 score-3 rows, the
  top of every ladder, against the dumps numbers). After each capability:
  sheet corrections, a golden case where a score decision changes, rebuild,
  gates.
- **Food curation**: the fish meals (`T8_MEAL_STEW_FISH`, `T7_MEAL_OMELETTE_FISH`)
  have no sheet at any tier and the pipeline carries no meal nutrition; needs
  the real bonuses (wiki via Playwright, or a dumps re-parse) — ~10 pieces.
  Catalogue gaps in the kit audit (a plain Cape, a plain sandwich) are the
  same class. (V: 08, Tier-agnostic gear lookup)
- **V4b**: leave-one-out at a full party tests "best generic 20th body", not
  "replace what was lost" (saturation degeneracy). Reconstruct the last ~5
  slots instead, where targets still bind. (V: 08, FIRST V4 RUN)
- **Killboard roster import, stage 1** (ToS-clean): paste names or a guild
  name -> per-player recent MainHand distribution by fight-size bucket ->
  auto-fill slots with confidence and click-to-override; enables constrained
  forging over player weapon pools. Decide the CORS route: Worker proxy vs a
  local helper JSON (the gameinfo API sends no CORS header). Deprioritized
  with the product items below until comp quality satisfies.
- **Close the loop, stage 3**: post-fight battle ingestion labels the fielded
  comp + outcome -> V6 content labels, V8 win-lift.
- **Companion — mid-fight joins / leaves**: only the bulk roster event updates
  membership; determine the incremental event by watching a live join with
  `--debug` (do not guess the shape — a party-join looks like NewCharacter).
  The companion must be running before you zone.
- **Companion — unverified on the wire**: whether the inspect response
  carries spells (the companion takes a 14-slot array opportunistically);
  whether the inspect shape holds on the current patch (first live inspect
  with `--debug` confirms; the inspect key still needs one capture); whether
  gear-change fires for all members on zone-in or only on change.
  (COMPANION_SCOPE.md)
- **Companion polish**: spell names in the connect box / weapon drawer;
  version-check cache refresh instead of the 7-day timer; pick a default
  capture mode (Npcap optional, raw sockets + prompt as fallback).
- **Uptime economics** (role layer increment 4): gear survivability as a
  time-on-target term. Optional. (roles-design.md)
- **Harvest targeting**: focused nights at 10-14 and 20+ (`-MinPlayers` /
  `-MaxPlayers`) once the bands need them; a mechanism for choosing which.
- **The outcome layer — first step: test the template weights**: the
  party artifact now carries `in_fight` / `kills` / `deaths` per party
  (`sample_parties.py analyze`, summed over members the battle roster
  places in the fight); the committed artifact gains them at the next
  fold on the harvest machine. `pipeline/audit_capability_outcomes.py`
  (report-only) then labels win (kills >= 2 x deaths) / loss (kills <
  deaths), fits outcome weights on the training split and compares the
  template's fitness() against them on the holdout. Planted-weight
  recovery checks: Spearman 0.94 recovered, holdout AUC 0.49 with no
  signal planted. Any weight change it suggests is a logged decision.
  Later: win-lift per weapon, pair and copy count, into the prior only
  after a `v4h` A/B (standing rule 16); the design doc's plan (§8.6): a
  prior-adjuster, never the primary term.
- **brawl_clap under the floor everywhere** (28 / 36 / 15 rosters): its seat
  and plan rows fall back to the pooled cell, its copy rows to pooled; the
  forged brawl_clap 20 reads as a split identity. Nothing to derive until
  the harvest supplies the cell.
- **An independent style labeller**: the harvest rosters are labelled by
  the engine's own `comp_identity`, the style x size rows and the seat
  skeleton are fitted to those labels, and the forge is judged against
  them. ~50 hand-labelled rosters cannot beat a classifier tuned on them;
  a labelled HOLDOUT round first, then a gear-plus-delivery labeller scored
  on it.
- **One killboard sampler**: `sample_battles.py` (`battles_cache/` ->
  `weapon_usage_v2.json`, the display strip's fight-size prevalence and the
  cohort families) and `sample_rosters.py` (`roster_cache/` ->
  `roster_mixes.json`, the need-profile evidence) are strictly weaker views of
  what `sample_parties.py` already harvests with party structure and gear.
  Re-derive both artifacts from `party_rosters.json.gz`, retire the two older
  samplers and their caches, and the overnight task feeds everything.
- **Stale comments**: `engine/engine.py` and `engine/app_scoring.js` still
  open with a "KNOWN OPEN DEFECT" note about the unit defect, which the unit
  re-fit resolved (standing rule 9). Fix on the next engine touch (the JS
  change requires a dashboard rebuild).
- **Cross-check the Resilience Penetration table**
  (`pipeline/resilience_penetration.yaml`, the cited 69-row melee table,
  wiki values) against the dumps. Optional. (Q7)

## Product features (deprioritized until comp quality satisfies)

Saved player profiles; enemy-comp counter drafting; fight-plan generation;
the blind-validation workflow as a tool; the companion loot module
(COMPANION_SCOPE.md, proposal only).

- **Seat-vs-label open list** (`notes/findings/2026-09-11-labels-vs-seats.md`):
  14 of 40 seated frontline / support weapons carry none of their seat's
  signature capability at >= 4 (ten engage tanks without a clump tool —
  Grovekeeper, Polehammer, Hammer, Great Hammer, Tombhammer, Morning Star,
  Soulscythe, Dreadstorm, Earthrune, Mace; Primal / Stillgaze stoppers under
  4 everywhere; Exalted on the shield seat; Black Monk as an off-tank). Each
  is a maintainer decision: a move changes the kit doctrine and the 15+
  minima. Great Arcane may want a 'stopper support' seat that does not
  exist. (Exalted is decided: healer, support lane secondary.)
- **Refresh alternatives walk one swap at a time**: next-best is exact, so
  successive refreshes under the same locks usually differ by a single
  member. If more diverse alternatives are wanted, a diversity rule (avoid
  rosters sharing all but k members) is the knob — a maintainer decision,
  not a derivation. (V: 09b, Slot controls)
- **Back up the raw battle cache off this machine**: `pipeline/out/party_cache/`
  is 157 MB of kill events, gitignored, the only copy of the harvest's
  evidence. A storage bucket (Supabase is a candidate) as a nightly upload
  target after each harvest — a BACKUP, never a build input, so CI and
  provenance stay as they are; a fresh machine pulls it down and re-derives.
  Not the committed artifact (5 MB gzipped when this was written, 52 MB now).
