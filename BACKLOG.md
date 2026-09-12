# Backlog

The one list of open work. Every other document points here instead of
keeping its own. Grouped by what each item is waiting on, because that is the
question that gets asked: what can be ruled on now, what needs more evidence,
what is just work. One line per item, with where the evidence or the record
sits (`V:` = the `tests/VALIDATION.md` index / `notes/validation/`; `Q<n>` =
`MECHANICS_TODO.md`). Shipped items are deleted, not struck through — git has
them. Closed rulings are index rows in `tests/VALIDATION.md`, never here.

## Needs an owner ruling

Each is decidable today from evidence already in the repo.

- **Is one unit of shred "pierce on the clump" in a 7-man?** The kill
  lights bar on the bare minimum since 2026-09-10 ("enough to kill" is a
  minimum question), and castle_outpost's refreshed three-comp fit says the
  least winning 7-man brought exactly one unit of resist_shred — so the
  owner's burst trio (Longbow / Witchwork / Permafrost, one unit) now reads
  pierce GREEN where the 2026-08-23 pin said red. Thin evidence, not a
  semantic call: rule it (a fourth castle-outpost comp would settle it), or
  raise the content `min` for resist_shred by hand. (V: 09b, Target is the
  median; T25b)
- **Repo size: `pipeline/out/party_rosters.json.gz` is 52 MB and committed**,
  growing with every fold (it was 83 KB on 2026-08-29, 4.4 MB the same day
  once builds joined). The split proposed then: commit the aggregates,
  gitignore the raw `builds` array beside the other caches. Not done because
  the raw builds are the evidence. Decide. (V: 08, Observed BUILDS)
- **The Armory import path** (`data/armory_imports/`, `pipeline/parse_armory.py`,
  `out/armory_activities.json`, the H-test fixture): built 2026-08-19, never
  fed — the Armory has no export and the harvest now supplies the same class
  of evidence at scale. Keep the door or remove it.
- **EU server in the harvest**: would double the 25+ corpus but mixes a second
  server's meta into rows meant to describe the owner's fights. Review was
  set for 2026-09-23. (V: 09b, Coverage, not speed)
- **territory_defense at 25** forges one to two members short (brawl / clap /
  kite): the profile scales stopper_tank to a minimum of 3 inside a frontline
  cap of 5, and the deadlock guard checks capacity exists, not that it is
  enough. Wider band, lower stopper scale, or a counting guard. (V: 09b,
  Chains reach past a slot) Re-measured 2026-09-12: every territory_defense
  25 cell now forges a full, feasible roster with no filler or held slots
  (the sweep) — confirm on the page before closing this.
- **`balanced` and the one-per-five healer minimum**: it keeps the base band
  and forges 3 healers at castle 25; the guild sheet says 4 at 20+ with no
  style attached. (V: 09b, Healers per five)
- **Role counts past the minimum at 21+**: the typical role count
  (2026-09-11) holds the forge to the evidence through size 20 (healer /
  frontline / support, per style at 10+); the harvest has no 21+ rows
  (killer parties cap at 20), so every 25 cell forges 6 healers on clap
  and 7 on brawl and kite (castle and territory_defense alike; the
  2026-09-12 sweep) — the scorer's preference, to be graded, not assumed
  right. A 21+ harvest band or an owner cap closes it. (V: 09b, Tanks
  and supports; notes/findings/2026-09-12-forge-quality-findings.md)
- **The forge does not build a kite**: forged FOR kite, the roster reads
  clap or clap_kite by the engine's own `comp_identity` in 10 of 13 cells
  (brawl_clap: 0 of 10 read brawl_clap); at blackzone 20 the kite roster
  shares 14/20 weapons with the clap one. Nothing in the kite rows
  requires a standoff tool or evade share from the E, so catch tanks plus
  a ranged bomb line is the scorer's best kite. Candidate mechanisms: a
  weapon-unit floor on a standoff-class row (rule 10), or a kite pool gate
  on `standoff_e`. Owner call; no weapon rule. (2026-09-12 sweep)
- **Catch over-stacks in a third of forged comps** (27/72 cells past the
  soft cap; Grailseeker 10 + Polehammer 8 + Hand of Justice 4 at
  blackzone 20 clap) while `damage_debuff` / `anti_dive` / `tankiness` are
  the rows most often under the bare minimum. Whether four catch tanks in
  a clap is a comp the owner would call decides if `overstack_max` or the
  catch-tank E derivation moves. (2026-09-12 sweep)
- **Breadth picks the harvest never fields**: Fists of Avalon is forged
  into 56 of 60 evidenced 10+ cells and is on at most 11.5% of the
  rosters in any (zero in 16); Crystal Reaper, Weeping Repeater, Great
  Holy, Carrioncaller, Kingmaker, Grailseeker follow. Its sheet carries
  fifteen nonzero rows. Route: the magnitude review queue, E-first;
  then the "breadth over depth" question if the sheets survive.
  (2026-09-12 sweep)
- **Supports UNDER typical on clap / clap_kite at 20** (forge 2, cell p50
  4): a typical only bars bodies beyond it; the shortfall is a support
  demand question (which support capabilities the 20-man rows under-ask
  for), not a role-count one. (V: 09b, Tanks and supports)
- **Sub-10 tanks and supports rest on three castle_outpost comps** (roads
  has one, so it reads the healer row only). More sub-10 published comps,
  or a sub-10 killboard filter that separates content comps from open-world
  squads, would let the harvest carry them. (V: 09b, Tanks and supports)
- **Melee instant-payload bombs in clap dps** (Spiked Gauntlets, Realmbreaker)
  generate under the standing conditional-payload ruling; the "bomb builds
  in clap" complaint has no derived rule left without a new one. (V: 09a,
  Owner bug round)
- **A descriptive `gank` read at <= 14**: catch-and-execute damage core with
  no bomb share, in the owner's words ("claws, dagger pair, whispering bow —
  catching and dismounting"); would label the board, stay OUT of the style
  rows, never be a forge style. Until ruled those rosters vote into brawl /
  clap at 10-14. (V: 09b, Blind round 4)
- **Is the Infernal Staff's E a standoff tool** (it alone made a kite of
  round-4 roster 5), and should one tool out-vote five ranged dealers at bomb
  share 0.36. (V: 09b, Blind round 4)
- **A frontline's damage points making a ranged carrier** (Witchwork, round-4
  roster 11) — same shape as the rejected utility-carrier rule. (V: 09b)
- **Carrier FLOORS**: which of the six gear effects are needs. The harvest has
  Royal Armor on 3.65% of builds at 20-59 (~0.7 per 20) against the guild's
  "2 Royals per 10". Increment 3b's second half; then mechanism pairing rules
  for effect carriers. (V: 09b, Other numbers; roles-design.md)
- **Kill-vs-death contrast** in kit doctrine: needs a win-lift ruling before
  it orders anything (effectiveness claims are reserved for win-lift). (V:
  09b, Coherent builds)
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
- **Chillhowl / Stillgaze / Iron-clad menus**: off every seat pending a word
  (Stillgaze got stopper_tank 2026-09-02; the other two stay out).
- **Hellfire Hands in kite generation**: its E is unconditional so the derived
  rule passes it; the clap exclusion is a clap-scoped override. (V: 08, KITE
  EXTENSION)
- **`brawl_clap` target_mults**: unruled, n=3 declared; every clap row beyond
  burst_aoe likewise (peel / disengage flipped sign between samples). (V:
  08, Per-style targets round 2)
- **Whether 10-14 should field the Exalted Staff** (7% of winners do; one
  curated 10-man does); the lever is the ramp anchors, never a weapon rule.
  (V: 09b, Cost gate retired)
- **Per-spell `burst_aoe` escalation gating** (Q10 refuted the uniform AoE
  class; factors are extracted on `cap_delivery.escalation`, not wired).
  Stated precondition was "after a styled expert pass" — rounds 1-4 have run.
  Also PROVISIONAL: `radius_targets`, `reference_clump: 2`, travel-distance
  footprints uncounted. (Q9 / Q10)
- **The enemy model** (Q2 / Q2b / Q5): attackers-per-target and
  expected-targets-hit are style properties, owner-delegated with the Q14
  ordering rule; no public numeric source exists. Open inside it: the
  unit-scale of one dedicated attacker, expected targets per content size
  for the escalation curve (caps at 8).
- **Asymmetric numbers at 21+** (Q11 / Q13): Disarray is a no-op in a mirror
  fight; CC Escalation vs Disarray vs forced-dismount immunity removed at 21+
  need netting together. Parked until templates gain an enemy-size field;
  the app currently models no enemy by ruling.
- **A dive / assassination style**: "sure but only if we have more than 20
  people" — a 20+-size style if ever. Not started.

## Needs evidence a round would produce

- **V3 round 2 forms are waiting for answers**: `tests/tier2_form_r2_castle7.md`
  (seed 20260827) and `tests/tier2_form_r2_blackzone20.md` (seed 20260828),
  richer fields, engine output hidden. Score with
  `tests/tier2_blindtest.py score --mode both`. These create the first
  uncontaminated validation / holdout cases. (V: 08, FIVE RULINGS, ruling 4)
- **Harvest V4 findings** (`tier2_blindtest.py v4h`, 2026-09-10, weak-form):
  leave-one-out role-level 64-65% over 150 holdout killer parties against the
  published-comp gate's 74% on 23 slots; kite parties 38% (n=10); rebuild-5
  role recall 82-87%. Hypotheses for the owner, nothing retuned. (V: 09b,
  Harvest V4)
- **The 20+ identity band**: no blind round yet; kite|20 still borrows
  kite|15-19 (31 distinct rosters) and brawl_clap borrows brawl in every band.
  A round once the harvest can stand it. (V: 09b)
- **Blap's escape**: winning brawls at 20 carry more disengage / knockback in
  their bottom decile than blap does (7 vs 16, 5.8 vs 10.3); the next brawl
  round should ask whether the escape is real. (V: 09a, The movement four)
- **Calibration sharpening**: targets stay conservative (median coverage
  ~1.8x); tier2 has saturated as a discriminator for per-style targets at
  this corpus size, so sharpening needs held-out labelled comps or expert
  rounds under the train / validation / holdout rule, not another sweep.
  Watch: castle-25's saturated tail. (V: 08, Re-derivation; THE UNIT RE-FIT)
- **More caller sheets** in `data/published_comps/` remain the highest-value
  growth per observation: they are the only source of whole comps with roles,
  which calibration and the V4 gate need.

## Engineering work, unblocked

- **Regenerate the evidence board on the harvest checkout** so `balanced`
  gets its pooled median rows: `py -3 pipeline/audit_style_rosters.py`
  (needs the raw party cache, D: checkout only) -> `derive_style_bands.py`
  -> `build_dataset.py` -> the gates. Target-is-the-median (2026-09-10)
  shipped the pooled `balanced|<band>` cell in the audit and the engine
  reads it like any style, but the committed board predates it, so
  balanced at 10+ still reads the content row (labelled `content` /
  `min` on the board) until the audit reruns there. (V: 09b, Target is
  the median)
- **Gear-active doctrine — pick the ability people equip, not the one that
  scores best.** `default_gear_choice()` takes the sheet option worth most
  under the template's weights; where a strong-on-paper ability is never
  taken (Cleric Cowl's Force Field: owner 2026-09-10, MetaBattle 4/4 Ice
  Block) that credits phantom supply. Mine an observed active per item (and
  per size band where the evidence splits) from every source that records
  gear abilities — MetaBattle `gear_spells_raw`, caller sheets, the
  companion's spell array if it carries armor actives (verify) — the engine
  prefers the evidenced active, keeps the argmax as a labelled `assumed`
  fallback, and the UI exposes the pick like Q/W/E. Do this BEFORE the gear
  pools below, which would otherwise spread the Force Field over-credit to
  all ten cloth heads. (V: 09b, Cleric Cowl)
- **Gear pools — the tree-shared actives are uncurated.** Every cloth head
  carries Energy Barrier + Force Field as its first two actives and only the
  third is unique, yet only Cleric Cowl's sheet cites Force Field; a Fiend
  Cowl running it supplies zero knockback / peel. Same for every armor tree
  and slot. Give gear the weapon sheets' pool structure (`sheets/gear/pools/`
  per tree x slot, each item's sheet keeping its unique active), so the
  engine's one-active-per-piece pick chooses among what the item can really
  equip. Recorded as pending 2026-08-25 ("the tree-shared first two abilities
  await curation"); do it BEFORE any gear magnitude review. (V: 08, Fourth
  pass)
- **Magnitude audit queues** (`py -3 pipeline/build_magnitude_review.py` ->
  `review/magnitude.html`): the PASV queue (39 rows where a passive / stat
  sentinel grounds a score >= 2 — each needs a justification or a downgrade)
  and the TOP review (44 score-3 rows, the top of every ladder, against the
  dumps numbers). After each capability: sheet corrections, a golden case
  where a ruling changes, rebuild, gates.
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
  local helper JSON (the gameinfo API sends no CORS header). Owner-deprioritized
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
- **Honour the holdout split end to end**: `v4h` evaluates battles with
  `id % 5 == 0`. `derive_meta_prior.py` honours it since 2026-09-11
  (`HOLDOUT_MOD`, both tables); `derive_style_bands.py` and
  `derive_role_counts.py` still fit on every battle. Give them the same
  split constant so every harvest-derived row is fitted on the other four
  fifths; then `v4h` is a true holdout measurement and can be considered
  for a gate (owner decision). Until then every styled `v4h` number is
  weak-form. Re-derive the pair prior on the harvest checkout after the
  next fold (`fold_harvest.ps1` already runs `derive_meta_prior`).
- **One killboard sampler**: `sample_battles.py` (`battles_cache/` ->
  `weapon_usage_v2.json`, the display strip's fight-size prevalence and the
  cohort families) and `sample_rosters.py` (`roster_cache/` ->
  `roster_mixes.json`, the need-profile evidence) are strictly weaker views of
  what `sample_parties.py` already harvests with party structure and gear.
  Re-derive both artifacts from `party_rosters.json.gz`, retire the two older
  samplers and their caches, and the overnight task feeds everything.
- **The forge returns a local optimum**: in 25 of 72 sweep cells a
  refresh alternative (`forge(avoid=)`) OUTSCORES the button's roster
  (median 0.15% of comp_score, max 0.62%); the probe at blackzone 20 clap
  is a one-weapon swap plus another member's combo — invisible to 1-opt,
  missed by the bounded 2-opt (worst 4 x top 12). A closing pass that
  re-resolves every generated slot's combo and kit under the final
  roster, or a wider 2-opt, both ports, parity. Measure with
  `py -3 pipeline/audit_forge_quality.py` (deterministic; diff the
  summary board). (2026-09-12 sweep)
- **Stale comments**: `engine/engine.py` and `engine/app_scoring.js` still
  open with "KNOWN OPEN DEFECT (ruling pending, see HANDOFF.md)" about the
  unit defect resolved 2026-08-29. Fix on the next engine touch (the JS
  change requires a dashboard rebuild).

## Product features (owner-deprioritized until comp quality satisfies)

Saved player profiles; enemy-comp counter drafting; fight-plan generation;
the blind-validation workflow as a tool; the companion loot module
(COMPANION_SCOPE.md, proposal only). (Slot locks, per-slot replace and the
next-best refresh shipped 2026-09-11 — V: 09b, Slot controls.)
- **Seat-vs-label ruling list** (`notes/findings/2026-09-11-labels-vs-seats.md`):
  14 of 40 seated frontline / support weapons carry none of their seat's
  signature capability at >= 4 (ten engage tanks without a clump tool —
  Grovekeeper, Polehammer, Hammer, Great Hammer, Tombhammer, Morning Star,
  Soulscythe, Dreadstorm, Earthrune, Mace; Primal / Stillgaze stoppers under
  4 everywhere; Exalted on the shield seat; Black Monk as an off-tank). Each
  is an owner call: a move changes the kit doctrine and the 15+ minima.
  Great Arcane may want a 'stopper support' seat that does not exist.
  (Exalted ruled the same day: healer, support lane secondary.)
- **Refresh alternatives walk one swap at a time**: next-best is exact, so
  successive refreshes under the same locks usually differ by a single
  member. If the owner wants "more different" alternatives, a diversity
  rule (avoid rosters sharing all but k members) is the knob — an owner
  call, not a derivation. (V: 09b, Slot controls)
Slot locks / constrained reforge; saved player profiles; enemy-comp counter
drafting; fight-plan generation; the blind-validation workflow as a tool;
the companion loot module (COMPANION_SCOPE.md, proposal only).

- **Back up the raw battle cache off this machine** (2026-09-11): `pipeline/out/party_cache/` is 157 MB of kill events, gitignored, the only copy of the harvest's evidence. A storage bucket (the owner mentioned Supabase) as a nightly upload target after each harvest — a BACKUP, never a build input, so CI and provenance stay as they are; a fresh machine pulls it down and re-derives. Not the committed artifact: that is 5 MB gzipped now.
