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

- **Effect-carrier pairing rules**: carrier caps and floors ship per effect
  x style x band (V: 10, Carrier caps and floors from one corrected
  measurement); which seat carries each chest beside which mechanism is
  increment 3b's remaining half. What a pairing rule measures needs a
  maintainer decision; nothing is measured yet. (roles-design.md)
- **The AoE geometry's provisional parts** (Q9): `radius_targets`,
  `reference_clump: 2` and travel-distance footprints stay PROVISIONAL.
  With each bundle reading its own spell, 147 geometric rows on 38 spells
  stay flat: their spell states no area the walk reads, mostly single
  strikes and self buffs; four state one under a reference the walk does
  not follow (Fear Aura's 4m pulse, Soul Chain's 30m tether, Frost Walk,
  Hamstring). A spell's target cap is the largest explicit cap in its
  tree, so where the one explicit cap sits on a one-target sub-effect the
  whole spell reads one target and stays flat: 15 spells carrying
  geometric rows read so, the single-target throws rightly (Harpoon, Spear
  Throw) and some areas not (Soaring Swipe, Camlann's Vendetta,
  Caltrops). Whether the walk reads those references, and the cap per
  effect, need a maintainer decision. The in-game damage bonus reads the style clump, not the
  spell's reach. (V: 10, Delivery reads the bundle's own spell)
- **Open-world fights inside the Dragon Portal's 15-20 pool**: the content
  marker tags a whole battle from one marked victim, and a bone or shard
  carried out of the Ancient Lands tags an open-world fight. On the fold
  copy 119 of the 283 parties of 15-20 come from battles of 100+ players
  (26 battles, up to 459; 174 from battles of 51+), which a 15-20
  matchmade instance cannot hold. A battle-size cap on the portal tag
  (the pool's two sides plus a margin) would move the portal page, the
  15-20 pool's own rows and its count toward the 200-roster threshold
  (the item below); the cap needs a maintainer decision. (V: 10, The
  Dragon Portal weapon table reads a two-sided win rate)
- **Iron-clad Staff's seat**: the role book keeps it off every menu as a
  small-scale weapon nobody fields in ZvZ (17 builds when graded; curation
  judgment) beside a standing >=10 viability exclusion, so it carries no
  doctrine kit and never generates at 10+. The fold copy holds 229 of its
  builds in killer parties of 10+ from 172 players (293 parties), and it
  entered the mid meta-prior bucket. Seating it, and lifting the
  exclusion, needs a maintainer decision. (V: 10, The official-list
  fold's pins)

## Needs evidence a round would produce

- **The V3 round 2 Blackzone Roam 20 form is waiting for answers**:
  `tests/tier2_form_r2_blackzone20.md` (seed 20260828), richer fields,
  engine output hidden. Score with `tests/tier2_blindtest.py score --mode
  both`. Answered blind it is the first uncontaminated validation case;
  the Castle Outpost 7 form was answered as a reviewed draft and is train.
  It predates harvest seeding: its parties come from the whole weapon
  pool (`generate --from-pool`, seed 20260828). (V: 08, the
  dressed-forge decisions, item 4; 09b, V3 round 2)
- **The V3 round 3 Dragon Portal forms are waiting for answers**:
  `tests/tier2_form_r3_portal3.md`, `tests/tier2_form_r3_portal5.md` and
  `tests/tier2_form_r3_portal7.md` (seed 20261008, 12 cases each, one form
  per matchmaking pool at its top size), every case a dominant killer
  party of the pool from the training split with members removed; the
  answer key beside each form (`*.key.json`) is never sent. Score each
  with `tests/tier2_blindtest.py score --mode both`, which prints the
  harvest agreement beside the engine's. Answered blind they are what can
  lift `validated_sizes: []` on `ancient_lands`, the page's
  "extrapolated" flag. (V: 10, V3 forms seed from harvested killer
  parties)
- **Kite weights: the style-labelling form is waiting for answers**:
  `tests/style_form_r1_kite.md` (seed 20261009, 20 cases, weapons only):
  the kite forge at Blackzone Roam and Territory Defense 10, 15, 20 and
  25 beside twelve harvested killer parties, four each of 10, 15 and 20
  players, the engine reading kite (4), clap_kite (4), clap (2) and brawl
  (2) across them; the answer key beside it (`.key.json`) is never sent. On its own kits the forged kite reads
  clap at 10 (one standoff tool), kite at 15 and clap_kite at 20 (each on
  two tools, the plan minimum) and clap at 25 (forged before a single
  party's forge stopped at 20; the generator now forges 10, 15 and 20), in
  both contents; at 15
  and 20 the bomb share sits within 0.02 of the 0.45 that divides kite
  from clap_kite, and Territory Defense 20 reads kite on its weapons
  alone. A pure kite read at 20 needs the kite style's multipliers, never
  validated, to prefer sustained ranged pressure over bombs. Score each
  filled copy with `py -3 pipeline/style_blind_round.py score <form>`:
  the agreement per source and size, and the forged kites not called
  kite. A forged 20 called kite puts the question on the identity read;
  one called clap_kite or clap puts it on the kite weights. (V: 10, Kite
  weights wait for a style-labelling form)
- **Is the Infernal Staff's E a standoff tool: the lone-tool floor waits
  for the kite form's labels.** Round 4's roster 5 (one Infernal Staff,
  bomb share 0.407, called clap) reads kite under the 0.45 floor; the
  labelled one-tool rosters fit any floor in (0.304, 0.407], and the
  midpoint would turn 333 of 807 10-14 kite reads clap. The kite form's
  one-tool rosters of 10 (a harvested kite read at 0.294, the forged
  kite 10 read clap at 0.458 and 0.481) refit the floor once answered.
  (V: 10, The lone-tool floor waits for the kite form; 09b, validation
  round 4)
- **The 20+ identity band**: no validation round yet; brawl_clap|20 still
  borrows brawl_clap|15-19 (129 distinct rosters), while kite|20 reads a
  cell of its own (174). A round once the harvest can stand it. (V: 09b)
- **Blap's escape**: winning brawls at 20 carry more disengage in their
  bottom decile than blap does (7 vs 18.5, dressed); its knockback (6.75)
  now clears that decile (5.5) and sits under the median (12.5). The next
  brawl round should ask whether the escape is real. (V: 09a, The movement
  four)
- **Calibration sharpening**: a target is the median of its evidence
  (standing rule 17); tier2 has saturated as a discriminator for per-style
  targets at this corpus size, so sharpening needs held-out labelled comps
  or validation rounds under the train / validation / holdout rule, not
  another sweep. Watch: castle-25's saturated tail. (V: 08, Re-derivation;
  THE UNIT RE-FIT)
- **More caller sheets** in `data/published_comps/` remain the highest-value
  growth per observation: they are the only source of whole comps with roles,
  which calibration and the V4 gate need.
- **Sub-10 tanks and supports outside the Dragon Portal wait for caller
  sheets**: they rest on three castle_outpost comps (roads has one, so it
  reads the healer row only); the portal's pools read role counts of their
  own from their dominant winners (V: 10, Optional rows and role counts for
  the portal pools). The harvest cannot carry them while castles and
  outposts read as open world (the content tag), so more sub-10 published
  comps are the evidence (V: 10, Sub-10 role counts wait for caller sheets;
  09b, Tanks and supports).
- **The Dragon Portal's 15-20 pool at 200 rosters**: the pool reads rows of
  its own, fitted at the floor (40 distinct rosters at the last fold; V: 10,
  The 15-20 portal pool reads its own rows), and generation at 15-20 keeps
  the open-world seat skeleton, minima and fielded gate (V: 10, The
  fielded gate at 10+) until the pool holds 200
  distinct dominant rosters (V: 10, The 15-20 portal pool takes its own list
  and counts at 200 rosters). `derive_portal_rows.py` and the fold report
  count it against the threshold; at 200, derive its fielded list and role
  counts as the smaller pools' are (both ports read a pool's role counts
  below 10 alone today), and measure its own prior on the holdout before
  `derive_portal_prior.py` carries it (the smaller pools read theirs at 8 x
  `delta`; V: 10, The Dragon Portal pools read their own prior).

## Engineering work, unblocked

- **analyze() takes no gears**: its bands and profiles read the naked
  supply; nothing on the page or in the pipeline calls it. An optional
  `gears` parameter in both ports when a caller appears.
- **Contents under three published comps keep rows fitted on earlier
  sheets**: Roads (1 comp), Territory Defense (2), Castle and Faction
  War read minimum rows written before the form-ability and anti-dive
  rows of 2026-10-04; `refit_content_targets.py` leaves a content under
  three comps alone. Blackzone Roam and Castle Outpost are re-fitted
  (V: 10, The published-comp rows re-fitted). More caller sheets are
  the fix (see "More caller sheets" above).
- **Gear-active doctrine, the next evidence**: the doctrine reads 79
  recording builds (the Character Builder comps and the MetaBattle batch);
  50 of 84 head / armor / shoes items have no vote or a single one and
  ASSUME their own active. (Soldier Boots, one vote on Rejuvenating Sprint from a
  small-scale build, assumes Wanderlust and supplies nothing from the
  slot: the piece is a solo pick, not a group build, so the reading
  stands; curation judgment.) The
  companion's spell array, if it carries armor actives (verify on the
  wire), would be the volume source; so would any caller sheet that
  records gear abilities. A gear-active OVERRIDE in the kit editor (the
  engine already scores `(key, choice)` pairs; the share codec does not
  carry a choice) is the UI increment if callers ask. (V: 10, Gear-active
  doctrine)
- **Magnitude audit queues** (`py -3 pipeline/build_magnitude_review.py`,
  a board generated locally into the gitignored `review/`): the PASV queue
  (44 rows where a passive / stat sentinel grounds a score of 4 or more —
  each needs a justification or a downgrade; by source: 18 maces and
  hammers read tankiness 4 on WEAPON_STATS, "tank-line weapon, played
  frontline", though a weapon carries no defensive stat
  (`out/item_stats.json`: durability, weight, item power) and the
  structural floors read weapon supply alone, so a downgrade moves every
  frontline floor and needs a maintainer decision; 16 fire, bow and
  repeater weapons read sustained_dps 4 on WEAPON_STATS as a stand-in for
  their auto-attack and Q/W patterns; 10 knuckles read sustained_dps 4 on
  the Fatal Fury passives, +18% damage at full stacks) and the TOP review (40 rows at
  score 6 or more, the top of every ladder, against the dumps numbers).
  The RULE flags (14 spell x capability pairs graded at two or three
  scores across the weapons sharing the spell) each state their reason in
  the row comment: the Round 9 E-supplement upgrade or the ladder the row
  sits on. After each capability:
  sheet corrections, a golden case where a score decision changes, rebuild,
  gates.
- **The W-option discount**: some W rows sit a step below their magnitude
  as "one W among five" (Armor Piercer resist_shred 2; Desecrate root 3
  at 2.6s beside Freezing Wind 4 at 2s and Snare Charge 5 at 2.56s vs
  players, the pool's 5 set on the vs-mobs 5.11s). Neither the rubric nor the decision log states
  the discount, and the loadout already charges for the W choice (one
  bundle per slot): log it as a rule or re-adjudicate the rows it held.
- **Tree Q/W spells named as kit reinforcement carry no row**: Burning
  Field (fire Q), Frozen Surge (frost Q) and Holy Orb (holy W) appear in
  comments as the reason an E row is high, and ground no row of their own;
  the E-row shares themselves (Blazing zone_control 6, Dawnsong burst_aoe 6,
  Lifetouch buff_allies 4) read lower spell by spell.
- **Impaler's burst_aoe on one spear**: Spirithunter keeps Impaler's
  burst_aoe 2 as an own row; the spear pool cannot carry it without
  `derive_ranged_presence` granting ranged_presence to every spear's Impaler
  bundle (a ground-cast at 12m), which moves golden T49. Whether Impaler is
  a ranged-presence tool decides the row.
- **Separator's knock-away**: Separator reads knockback_displace 2 on the
  knock-away rung (Force of Nature, Hurricane, Holy Explosion); whether
  isolating a rooted target earns more than that rung (Knockback Shot's 4
  is a directional push) is a validation-round question.
- **Curation grades deferred at the move to the newer snapshot** (each
  needs a rubric grade and a logged decision): Ground Shaker (every mace's
  W: 219 in a 4 radius plus an air-throw) and the 1H Mace's Deep Leap
  damage, no rows; the damage-only shared spells (Whirling Strikes,
  Throwing Blades, Explosive Arrows and others) and the scope of the 191 =
  2 burst anchor; Permafrost's burst_aoe 6
  (173 vs players: on raw magnitude the 4 rung, Hail 160 and Flame Pillar
  200; the 6 rests on the stun before the blast, and the row anchors the
  brawl 15-19 ranged-AoE minimum); the fear ladder (Demonic 4,
  Infernal 2); Flare's enemy cooldown-rate cut and the `reveal`
  capability. (V: 10, The movement rows the snapshot move deferred)
- **Black Hands' Devastating Strike knockback has no structured candidate**:
  the second hit's knockback is unscored (an `effect_overrides.yaml` add:
  entry would ground it); the weapon is retired, so only old permalinks
  read it.
- **Gatherer sets with combat actives and no sheet**: gatherer caps and
  boots (0.33% of helmets at 10+, 0.98% at 4-9) carry combat actives
  (the caps' Block, Self Cleanse and Emergency Shield; the boots' Dodge
  and Sprint) beside one active of their own per set (Magic Mushroom,
  Bear Trap, Tree Trunks and the rest), under the armor sheet's "not
  catalogued (non-combat)"; the doctrine never counts them and a kit that
  wears one scores the slot as nothing. Each set's own active needs a
  grade before an entry (V: 10, Worn items with an effect read on the
  rubric).
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
- **The outcome layer, after the party-level read**:
  `pipeline/audit_capability_outcomes.py` (report-only) labels win (kills
  >= 2 x deaths) / loss (kills < deaths) on the harvest's killer parties,
  fits outcome weights on the training split and compares the template's
  fitness() against them on the holdout, with each side's numbers from the
  battle roster's alliances (the harvest cache) as a control. The read on
  16,638 training parties of 10-20 (V: 10, Capability outcomes at party
  level, numbers controlled): numbers decide these fights (holdout AUC, the
  side ratio alone 0.75), fitness() adds nothing to them (numbers 0.763,
  numbers + fitness() 0.761; fitness() alone 0.485), no capability
  separates wins from losses alone (AUC 0.47-0.53), and the fitted
  coefficients do not rank like the template weights (Spearman -0.04);
  burst_aoe is the one capability whose coverage associates with winning
  beyond numbers (+1.19 per unit of coverage, 90% interval +0.84 to
  +1.40). Association, not cause; nothing retuned (standing rule 1), and a
  weight change it suggests is a logged decision. Open: item power and
  skill stay uncontrolled, a killer party with no kill is never recorded,
  and the roster names who fought, never who fought whom. Win-lift per
  weapon, pair and copy count, measured
  (notes/findings/2026-10-08-win-lift.md): the numbers-controlled lift
  replicates (39 of 98 weapons survive Benjamini-Hochberg at 10%, all keep
  their sign on the holdout, r = 0.81) but it is gear and guild: it tracks
  the fielding parties' item power (r = 0.67), primary-guild fixed effects
  leave 6 of 98 weapons, it does not transfer across disjoint guild sets,
  and within a guild it sits at the noise floor (true spread about 1.5
  win-rate points, one weapon's standard error about 1.5); pairs and copy
  counts carry no reliable signal. A lift that enters the prior needs the
  item-power and guild controls, and about four times the labelled corpus
  to resolve per weapon; the `v4h` A/B (standing rule 16) would test that
  controlled lift. The design doc's plan (§8.6) stands: a prior-adjuster,
  never the primary term.
- **Choice-fitted weights for the other templates**: `fit_choice_weights.py`
  fits Blackzone Roam on the killer parties of 10-20 and the Dragon Portal
  on its dominant pool parties of 2-7, which the harvest's content tag
  selects (`weight_fit` in `ancient_lands.yaml`). Castle, outpost,
  territory, faction-war and roads weights stay curation judgment until
  parties carry a content label (battle location from the killboard; the
  content tag reads every open-world fight alike) or each content has its
  own comps. Refit Blackzone Roam after each fold that moves the training
  split materially (`extract` then `fit`; the pull rule stays).
- **The forged brawl_clap reads brawl**: its seat cells clear the floor
  through a +-1 size window (50-80 rosters per size) and its copy cells at
  10-14 and 15-19 (20 reads the pooled copy cell); its band carries its
  winners' own `ranged_aoe_core` minimum, 1 in every band (V: 10, The
  ranged-AoE core minimum is generated). Forged for brawl_clap on the forge
  sweep's nine 10+ cells (a single party forges at 20 at most), the roster
  reads brawl in 6, clap in 2 (Territory Defense 15 and 20) and split in 1
  (Castle 20), never brawl_clap (the same record).
- **The forge returns a local optimum**: in 27 of 72 planner cells and 8
  of 18 Dragon Portal cells of the forge sweep a refresh alternative
  (`forge(avoid=)`) outscores the button's roster (best gap per cell:
  median 0.07% of comp score, largest 1.22% at Blackzone Roam 15
  brawl_clap, four slots apart; notes/findings/2026-10-09-forge-quality.md).
  Of the 48 beating alternatives, the shared members' combos and kits alone
  beat the button in 1; the weapon swap alone, every other member's build
  kept, beats it in 24 (twelve of them two-to-four-slot swaps with every
  shared build identical); the other 23 need the swap and other members'
  builds to move together. The constrained 1-opt already re-resolves each
  slot's build, so the gap is the weapon choice in one to four slots,
  beyond the bounded 2-opt (the four weakest slots in pairs, a shortlist
  of 12). A wider multi-slot search in both ports, held to parity and the
  browser's perf budget; measure with `py -3
  pipeline/audit_forge_quality.py` (deterministic).
- **An independent style labeller**: the harvest rosters are labelled by
  the engine's own `comp_identity`, the style x size rows and the seat
  skeleton are fitted to those labels, and the forge is judged against
  them. ~50 hand-labelled rosters cannot beat a classifier tuned on them;
  a labelled HOLDOUT round first, then a gear-plus-delivery labeller scored
  on it.
- **Whole-roster clustering on killer parties**: the observed families are
  anchor pairs. Measured on the fully-known rosters of 16-20 of the
  training split (notes/findings/2026-10-08-roster-families.md): the
  structure is real (nearest-neighbour distance median 0.20, 0.40 across
  other guilds and alliances, against 0.50-0.52 under two shuffled nulls;
  30% of holdout rosters fall inside a family against 0.3% of shuffled
  ones) but not a partition (silhouette 0.08 or less at any k), and most of
  it is guild repeats (72% of nearest neighbours are the same guild's
  roster; 9 of the 14 families at cut 0.50 are one guild's lineup). One
  family holds in every run, cut, variant and the one-roster-per-guild-a-day
  dedupe: the meta lineup at the centre of anchor family 0 (Realmbreaker +
  Spiked Gauntlets), 924 rosters across 85 guilds, top guild 7%, resampling
  stability 0.75, present every week and on the holdout at its training
  rate. Every family sits inside an existing anchor family. The one
  addition a display would carry is that lineup with copy counts (3 x
  Hallowfall, 2 x Bedrock Mace; Occult Staff 93%, Witchwork Staff 89% and
  Rotcaller Staff 77% of its rosters, none in anchor 0's cast); the other
  lineups it separates are single guilds' comps, which the anchor
  families' organization gate keeps off the page. Display only. (V: 10,
  One killboard sampler)

## Platform: accounts, guilds and CTAs

The persistent ZvZ planning, sign-up and roster platform around the engine.
Phases, their tables and the patterns phase 1 set:
`notes/specs/2026-09-28-player-platform-design.md`; the schema rules:
`supabase/README.md`. Phase 1 (accounts, the editable profile, weapon
lists), phase 2 (guilds: members with roles, the join code, guild-scoped
reads of profiles and weapon lists, the guilds dialog), phase 3 (saved
comps: a guild's templates with slots, saved from and opened in the
planner through the share hash), phase 4 (CTAs: a guild's events with a
status, a share code and slots copied from a comp), phase 5 (sign-up:
the sheet a link opens, for guests with a claim token and for accounts),
phase 6 (caller management on the sheet), phase 7 (the live sheet over
Realtime Broadcast), phase 8 (the attendance record) and phase 9 (the
history: facts over completed CTAs), phase 10 (import and export: a
spreadsheet, a CSV or an Excel workbook as a saved comp, its gear columns
read into each slot's kit, CSV out) and phase 11 (the engine's read of
the live roster, on the sheet) are built, and after them the history by
period (the last 30 days, the last 90 days, all time), the live CTAs
dialog (a private channel per guild) and an admin's renewal of a CTA's
share code; the comps dialog sets a slot's weapon, each slot keeping the
kit its saved link holds.

- **Guest identity is a name and a claim token** (phase 5). A guest who
  clears their browser loses the claim; the caller removes or moves them
  (phase 6). A renewed share code keeps the claim: the browser keeps it
  under the CTA as well as the code, and the new link finds it. A claim
  the page made before it kept claims under the CTA, and has not read
  since, sits under the old code alone, which opens nothing after a
  renewal: that guest is the caller's to move or remove. A Discord login
  (phase 12) is the stronger identity when it comes.
- **Enable leaked-password protection** (Supabase Auth, the security
  advisor's one warning): the Email provider's "Prevent use of leaked
  passwords" in the project's Auth settings, no code. A Pro plan feature
  (Supabase's password-security guide); on the free plan the warning stands.
- **Phase 12, integrations** (the spec): a Discord login and bot, a
  Google Sheets link, automatic roster construction (an optimization
  over the target comp, the players' declared weapons and their
  preferences: the first place a player's preference would meet the
  engine, a logged decision).
- **Import: a CTA from a sheet with its players**: the import makes a
  comp (a template has no player); the player column is shown and may
  ride in the slot notes. A CTA with those players on its sheet is a
  later increment (phase 12's roster construction is the place).
- **Gear names remembered per guild**: a gear piece the caller chooses in
  an import's review is not remembered (`weapon_aliases` holds weapon
  lines, one per name: "royal" cannot name a cowl in one column and a
  jacket in the next). A gear alias needs its slot in the key: a table of
  its own or a slot-qualified alias, a maintainer decision with a
  migration.
- **Import: spells and a build in one cell**: Q, W and passive columns
  are not read, and a cell holding a whole build ("Hallowfall - Cleric
  Cowl, Cleric Robe") reads its weapon alone: the gear after it is
  dropped, or read as the player's name. Later increments if callers ask
  for them.
- **Import: what a workbook's cells do not carry**: a number reads as its
  stored value, never in the cell's format (a date reads as its serial
  number); an .xlsb or .ods file and a workbook protected by a password
  are refused with the way round (save as .xlsx or CSV, remove the
  password). Reading styles, the binary format or OpenDocument is a later
  increment if a caller's sheet needs it.
- **A weapon picker per slot in the CTAs dialog**: the CTAs dialog edits a
  slot's role label and note and removes it; a slot's weapon is set on the
  sheet by the caller roles or by replacing the slots from the planner.
  The comps dialog's picker (the profile's combobox, the per-slot kit) is
  the pattern if callers ask for it there.
- **A party column on slots**: comp and CTA slots carry no party; an
  imported sheet's parties order the slots and may ride in the notes.
- **A player's own history across guilds**: the history dialog reads a
  guild's facts; a player's list of their own CTAs and marks across
  guilds (and a guest's, by claim) is a later surface.
- **A season in the history**: the facts cover the last 30 days, the
  last 90 days or all time (`guild_history` takes a period's start). A
  season, a stated start and end, needs an end beside the start and a
  list of seasons; a later increment if callers ask for it.
- **A slot's weapon changed on the sheet, in the live CTAs dialog**: the
  guild's broadcast covers the CTA and its sign-ups (`save_event` writes
  the CTA's row whenever it writes slots, so a roster saved in the dialog
  is told). A slot's weapon a caller changes on the sheet shows in an
  open dialog on its next read. Adding the slots to the guild's trigger
  costs a message per slot `save_event` writes (sixty for a full roster,
  beside the sheet's own sixty); a later increment if callers ask for it.
- **A caller's role label against the weapon's seat**: an imported
  "Witchwork (DPS)" carries DPS as the slot's role label, and the role
  tag and the per-role counts still read the weapon's primary seat
  (frontline: one role read). Whether a comp's counts follow the caller's
  label where it names a role class is a maintainer decision; the
  identity reads the same weapon by its seat too (a frontline counts melee
  in the melee share; V: 10, A frontline counts melee by its seat).
- **Multi-party comps**: the planner holds a zerg as parties of 20, one
  tab each, every party its own comp and the address carrying all of them.
  A saved comp keeps the open party's slots and address alone (a comp or
  CTA saved from a zerg brings no other party), and a CTA is one roster of
  up to 60; a template or sign-up sheet that groups slots by party is the
  later increment.
- **Guild invitations beyond the code**: a member joins only by a code an
  officer shares. An officer adding a member by Albion name, or a player
  asking to join, needs a lookup of profiles the reader is not yet allowed
  to see: a maintainer decision on what a name search may reveal.
- **Guild-scoped reads are all or nothing**: every member reads every
  co-member's character, display name, server and weapon lists. A member
  who wants to keep a secondary list private has no switch (curation
  judgment: a CTA tool exists to show a caller what members play).
- **The portal page's chrome**: the headings, labels, chips and radii
  follow the planner (the planner's chip, its radius set). The tokens are
  still a copy inside `_portal.html`; a shared stylesheet is the proper
  fix and waits for a second killboard surface.

## Product features (after v1; the comp-quality bar is the role-level gates)

Enemy-comp counter drafting; fight-plan generation; the blind-validation
workflow as a tool; the companion loot module (COMPANION_SCOPE.md, proposal
only). Saved player profiles moved to "Platform" above.

- **Seat-vs-label open list** (`notes/findings/2026-09-11-labels-vs-seats.md`):
  12 of 39 seated frontline / support weapons carry none of their seat's
  signature capability at >= 4 (ten engage tanks without a clump tool —
  Grovekeeper, Polehammer, Hammer, Great Hammer, Tombhammer, Morning Star,
  Soulscythe, Dreadstorm, Earthrune, Mace; the Primal Staff, a stopper
  under 4 everywhere; Black Monk as an off-tank). Each is a maintainer
  decision: a move changes the kit doctrine and the 15+ minima. Great
  Arcane may want a 'stopper support' seat that does not exist. (Exalted
  is decided: healer, support lane secondary; Stillgaze's stun now reads
  4.)
- **Refresh alternatives walk one swap at a time**: next-best is exact, so
  successive refreshes under the same locks usually differ by a single
  member (the forge sweep: 87 of 144 alternatives one slot from the
  button's roster, 34 two; notes/findings/2026-10-09-forge-quality.md). If
  more diverse alternatives are wanted, a diversity rule (avoid rosters
  sharing all but k members) is the knob — a maintainer decision, not a
  derivation. (V: 09b, Slot controls)
