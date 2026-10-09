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

- **The popularity baseline on the portal pools**: with the pool-fielded
  gate on, the engine names the hidden member in its top 3 on 9.5% /
  19.3% / 12.6% of holdout drops at 2-3 / 4-5 / 6-7 (9.1% / 13.8% / 9.4%
  without the gate); the pool's three most fielded weapons name it on
  27.3% / 29.6% / 13.9%. At role level the engine leads (76% / 62% / 46%
  against 47% / 52% / 38%). With the optional rows at 4-5 and 6-7 (V: 10,
  Optional rows and role counts for the portal pools; a 400-party holdout
  sample on the artifact of that day) the role read rises to 86% and 69%
  and the weapon's top-3 stays under the baseline's (16% and 12% against
  22% and 17%); at the frontline seat of a five Heavy Mace is the first
  pick in 41 of 150 cases where Great Hammer still leads in 79, on stun
  (+3.8), catch and heal_reduction, capabilities Heavy Mace's sheet does
  not carry. Inside the list the engine still prefers a
  wide sheet (Battle Bracers and Crystal Reaper over the Rotcaller Staff
  and the Longbow, which 26% and 20% of 6-7 winners field): the capability
  score pays a first unit on many rows more than depth on one. Whether
  the meta prior should bucket by content with a larger `delta` at the
  portal, or the sheets under-credit sustained ranged pressure, is the
  question to settle from evidence.
- **The fielded gate beyond the portal**: the gate applies where a
  matchmaking pool has its own harvest (the Dragon Portal's 2-3, 4-5 and
  6-7). The 10+ contents generate through the seat skeleton and the
  style bands with no weapon-level evidence gate. Measured on the v4h
  holdout (notes/findings/2026-10-08-fielded-gate-at-10.md): a style x
  band fielded list from killer parties of 10+ (the portal's rule: 5
  rosters, 3 guild-sets, 5% of the cell's top weapon) lifts the hidden
  member's top-3 from 7.7% to 10.1% (+2.5 points, 95% CI +1.7 to +3.3,
  replicated at +2.3), MRR 0.090 to 0.114, role-level 62.3% to 64.6%, the
  same relative lift as the 6-7 pool; it bars 4-5% of hidden picks (2 of
  them top-3 hits) and a quarter of the engine's committed top 3
  (Grovekeeper, Camlann Mace, Morning Star); a pooled list lifts less;
  brawl_clap 20 is too thin for a list. Beside the base band's
  `ranged_aoe_core` minimum the gated brawl forge stopped at 13 of 15 and
  17 of 20; brawl now carries no such minimum (V: 10, A gap-closer grounds
  no ranged presence) and the gated forge is not re-measured since (see
  "Forge minima above what winners field"). The ungated default forge
  measured whole (notes/findings/2026-10-09-forge-quality.md): 18% of its
  slots at 10-20 are weapons under 2% of the cell's winners field (6%
  fielded by none of them), the share the earlier sweep measured; Fists of
  Avalon is forged into 41 of 48 cells on at most 6.6% of a cell's
  rosters, Arclight Blasters into 19 on under 1%. Decide the gate, styled,
  once the minima are settled.
- **Forge minima above what winners field**: with a gap-closer grounding
  no ranged presence (H6c), killer parties of 10+ field `ranged_aoe_core`
  carriers per party at a p50 of 3 / 3 / 4 on clap, 3 / 4 / 4 on clap_kite,
  2 / 3 / 3 on kite, 1 / 1 / 1 on brawl_clap and 2 / 3 / 3 pooled at
  10-14 / 15-19 / 20 (distinct rosters of the training split), against the
  base band's 2 / 3 / 4 (met by 63 / 57 / 46% pooled and 10 / 0 / 0% of
  brawl_clap rosters) and the styles' 5 and 7 at 15-19 and 20 on clap and
  clap_kite, 4 and 5 on kite. The forge meets them by drafting carriers
  winners field rarely: forged for brawl_clap at Territory Defense 20 and
  Castle 20 the roster seats three ranged-AoE bodies against the brawl_clap
  seat cell's typical of one and p90 of two
  (notes/findings/2026-10-09-forge-quality.md). Brawl carries none (p50 0;
  V: 10, A gap-closer grounds no ranged presence). A minimum per style x
  band from the harvest (the standoff rule: round-half-up of the p50 where
  it is 1 or more) is the derivation to take.
- **The baseline finding** (`tier2_blindtest.py --baseline`, report-only):
  ranking candidates by role need then the prior's solo share places the
  real weapon at median rank 20 on 500 holdout parties (MRR 0.177, top-10
  33%) where the engine, after the fitted Blackzone Roam weights, places it
  at 30 (MRR 0.083, top-10 20%); the engine leads at role level (64% vs
  55%). The choice fit locates the gap: free, the meta prior would sit at
  about 1,180 x `delta`, and copies would be rewarded instead of charged
  (30% of killer-party members share their weapon; the engine ranks such a
  copy at median 53). Measured in the engine: `delta` 0.5 / 1.5 move MRR
  0.070 -> 0.072 / 0.081 and fail T49; `delta` 5 reaches 0.112 and fails
  T16 and T49. Raise `delta` (popularity outweighs capability), soften the
  duplicate cost against T49, or accept that the engine optimises comps
  rather than the published pick. (V: 09b, Skeleton-first; Fitted
  capability weights)
- **Healer pricing at 7** (V3 round 2, Castle Outpost 7): dressed mode
  ranks Great Holy and Rampant above Hallowfall in every healer case
  because the incumbents' doctrine kits already close disengage and
  mobility and the choice falls to `heal_sustain` (weight 10, target 4.5;
  two-handers supply 3.0 units, Hallowfall 2.0). Killer parties of 6-8
  field Hallowfall in 29.1%, Rampant in 1.0%. Measured
  (notes/findings/2026-10-08-castle-outpost-healers.md): worn gear is
  the larger cause. Between naked and dressed scoring Rampant's lead over
  Hallowfall moves 2.38 points, 1.19 from the utility rows (the
  incumbents' kits stand the party at or past the 4.0 disengage target in
  6 of 10 cases, and each rival's own kit brings the disengage and
  mobility Hallowfall's weapon does) and 0.70 from the heal rows (the kit's
  heal stat channel lifts the two-handers onto the 4.5 sustain target);
  no heal-row retune puts Hallowfall first in more than 4 of 10 cases, each
  hands the lead to Fallen Staff, and the sustain target at 3.0 lowers the
  held-out 7s' top-3 from 7.5% to 5.2%. Reading disengage and mobility on
  the weapon basis alone (the structural floors' rule extended to two
  utility rows) makes Hallowfall the first healer in 492 of 1,508 held-out
  healer drops (26 now) and lifts MRR 0.088 to 0.096, an engine-wide rule
  that reshapes the default 7. Beside it: the cleanse row (target 2.7, the
  median 6-8 winner fields none) favours Fallen Staff, and Redemption Staff,
  46% of single-healer 7s, is named first in 2 of 1,508. Scoring every
  member naked reads the held-out 7s better (top-3 8.9% against 7.5%).
  (V: 09b, V3 round 2)
- **Fill order as the beam's sequence** (healer -> frontline -> support ->
  dps, the guild sheet's "10-20 FILL ORDER"): the seat skeleton fixes the
  END state; the greedy beam still picks its path by marginal. Ordering
  changes many pinned first picks — a maintainer decision, not started.
- **Single-party forges past 20**: no page forges a party past 20 (the
  planner forges each party of a zerg at its own plan, capped at 20; the
  sheet's engine read recommends, it never forges), so three readings of
  the forge at 25 concern the engine API and its tests only:
  territory_defense at 25 forges members short (the forge sweep: clap 23
  of 25, the other five styles full; the profile scales stopper_tank to a
  minimum of 3 inside a frontline cap of 5, and the deadlock guard checks
  capacity exists, not that it is enough; V: 09b, Chains reach past a
  slot), and refresh then returns the same partial roster without
  `exhausted` (`avoid` applies at the final depth, which a beam that dies
  short never reaches); `balanced` keeps the base band (3-5 healers) and
  forges 5 healers at both 25-man contents where the guild sheet says 4 at
  20+ with no style attached (V: 09b, Healers per five); and with no 21+
  harvest rows the typical role count (standing rule 18) stops at 20, so
  the styled 25 forges field 6-7 healers (9 of 10 sweep cells; 6 on clap)
  (V: 09b, Tanks and supports; notes/findings/2026-10-09-forge-quality.md).
  They return if a single party past 20 does; a 21+ harvest band would
  settle the third.
- **Supports UNDER typical on clap / clap_kite at 20** (forge 2, cell p50
  4 on clap and 3 on clap_kite; the forge sweep: 2 in five of the six clap
  and clap_kite cells at 20 and 1 at Castle 20 clap, under the cell's p10
  of 2,
  notes/findings/2026-10-09-forge-quality.md): a typical only bars bodies
  beyond it; the shortfall is a support demand question (which support
  capabilities the 20-man rows under-ask for), not a role-count one. (V:
  09b, Tanks and supports)
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
  the plate Royal Armor on 2.7% of builds in battles of 20-59 players (about
  0.5 per 20; the 3.65% the log records does not reproduce on that week's
  artifacts, which read 2.6-2.7%) against the guild's "2 Royals per 10".
  Increment 3b's second half; then mechanism pairing rules for effect
  carriers. (V: 09b, Other numbers; roles-design.md)
- **Item-power gating**: the harvest's `item_power` is the API's average; the
  per-slot tier lives only in the raw cache. Five questions: which slot
  decides "geared", tier line or relative, per size band, quality, doctrine
  votes only. (V: 09b, Seat pooling)
- **Nature Staff**: seated main_healer, 53% of its users wear plate (n=93).
  Plate frontline healer, or a wrong seat. (V: 08, Observed BUILDS)
- **`MAIN_FROSTSTAFF_AVALON` (Chillhowl) >= 10 exclusion**: its stated premise
  ("no build fields it at 10+") is weaker since "AvA Raid" (10 players)
  fields one; the record is candidate, the exclusion stands. (V: 08, Corpus
  ingestion)
- **Hellfire Hands in kite generation**: its E is unconditional so the derived
  rule passes it; the clap exclusion is a clap-scoped override. (V: 08, KITE
  EXTENSION)
- **`brawl_clap` target_mults**: undecided, n=3 declared; every clap row beyond
  burst_aoe likewise (peel / disengage flipped sign between samples). (V:
  08, Per-style targets round 2)
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
- **A no-row piece as the dressed forge's one alternative**: kit_variants
  takes as v1 the first in-band piece whose top weighted capability
  differs from v0's, and a piece with no row has none, so in 19 band x
  style x weapon cells v1 now swaps a scored cape for the plain Cape, a
  variant that never scores above v0 (gang band: Dagger Pair and Great
  Nature Staff in every style, Dagger in five, its Demon Cape alternative
  displaced; group band under kite: Great Holy Staff, Great Nature Staff).
  No golden, forge or skeleton pin moves. Whether an alternative must
  supply something (both ports) needs a maintainer decision (V: 10, Kits
  name the worn items that carry no combat effect).

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
  two tools, the plan minimum) and clap at 25, in both contents; at 15
  and 20 the bomb share sits within 0.02 of the 0.45 that divides kite
  from clap_kite, and Territory Defense 20 reads kite on its weapons
  alone. A pure kite read at 20 needs the kite style's multipliers, never
  validated, to prefer sustained ranged pressure over bombs. Score each
  filled copy with `py -3 pipeline/style_blind_round.py score <form>`:
  the agreement per source and size, and the forged kites not called
  kite. A forged 20 called kite puts the question on the identity read;
  one called clap_kite or clap puts it on the kite weights. (V: 10, Kite
  weights wait for a style-labelling form)
- **Harvest V4 findings** (`tier2_blindtest.py v4h`, true holdout since the
  style board learns from the training split): at `--n 500` (1,500 drops),
  on the fitted Blackzone Roam weights, role-level 64% (harvest_gear)
  against the baseline's 55%, weapon top-3 7% against 18%; rank metric
  median 30 against the baseline's 20, top-10 20% against 33%, MRR 0.083
  against 0.177; 173 of 1,500 dropped weapons sit outside the suggestion
  pool. The 150-party reading (68% against 47%) was sample noise. v4h
  stays report-only (maintainer decision); the outcome audit it waited for
  has run, on guild-level labels and at party level (fitness() adds
  nothing to the numbers), so whether v4h becomes a gate is the decision
  left. Hypotheses only (standing rule 1), nothing retuned. (V: 09b,
  Harvest V4; Fitted capability weights; 10, Capability outcomes at party
  level, numbers controlled)
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
  the open-world seat skeleton and suggestion pool until the pool holds 200
  distinct dominant rosters (V: 10, The 15-20 portal pool takes its own list
  and counts at 200 rosters). `derive_portal_rows.py` and the fold report
  count it against the threshold; at 200, derive its fielded list and role
  counts as the smaller pools' are (both ports read a pool's role counts
  below 10 alone today).

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
  each needs a justification or a downgrade) and the TOP review (40 rows at
  score 6 or more, the top of every ladder, against the dumps numbers),
  and the RULE flags (15 spell x capability pairs graded at two or three
  scores across the weapons that share the spell; each needs its reason in
  the row comment or a downgrade — Heavy Mace's engage on Snare Charge 4
  and zone_control on Sacred Ground 4 state none). After each capability:
  sheet corrections, a golden case where a score decision changes, rebuild,
  gates.
- **Rows marked for review when curated and never reviewed**: Defensive
  Slam's buff_allies 3 and peel 2 (`pools/mace.yaml`; the dumps text grants
  the buff "for you and up to 10 allies in a 8 radius").
- **Small W and passive carriers held at no row**: the sword Weakening
  passive (`PASSIVE_REDUCE_DMG_SWORD`, every auto-attack cuts the target's
  damage dealt by 0.02 for 2s, stacking) and Frost Beam (`FROSTBEAM`,
  attack-speed debuff and a 0.15 slow stacking to 5) carry no
  damage_debuff or slow row, though damage_debuff scores elsewhere
  (Stillgaze's Neurotoxin 2). Grade each on the rubric and log it.
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
- **Polehammer's engage cites its W**: engage 6 sits on Slowing Charge
  (the Round 9 RULE queue as recorded: "engage 6 on Slowing Charge") while
  the row's own comment credits the E's 20m line stun, so with every row
  scoring on its own spell the engage exists only with that W equipped and
  every dressed Polehammer reads Slowing Charge. Moving it to Groundbreaker
  needs an `effect_overrides.yaml` engage candidate (the lint reads anti_dive,
  catch, peel and stun there), a logged decision against the recorded
  Round 9 list, and the `roles.yaml` source text ("Slowing Charge identity").
  Needs a maintainer decision.
- **Impaler's burst_aoe on one spear**: Spirithunter keeps Impaler's
  burst_aoe 2 as an own row; the spear pool cannot carry it without
  `derive_ranged_presence` granting ranged_presence to every spear's Impaler
  bundle (a ground-cast at 12m), which moves golden T49. Whether Impaler is
  a ranged-presence tool decides the row.
- **Separator's knock-away**: Separator reads knockback_displace 2 on the
  knock-away rung (Force of Nature, Hurricane, Holy Explosion); whether
  isolating a rooted target earns more than that rung (Knockback Shot's 4
  is a directional push) is a validation-round question.
- **Magnitudes the list-index fix corrected, for a rubric read**: with the
  description tags' list indices kept, 55 cited spells read their real
  numbers (V: 10, Description numbers read the element their tag names);
  no score crossed a rung the logged ladders state, the comments now carry
  the real numbers, and these rows read a magnitude the score was not set
  on (each needs a rubric grade and a logged decision): Ice Storm's tick
  (72 every 0.5s vs players where 25 was read; both damage elements target
  every enemy in the data) on burst_aoe 2 and sustained_dps 2; Haste's +60%
  Auto-Attack speed (20% was read) on sustained_dps 2; the Spectral
  Trident's soul mist, 6s (0.5s was read) of +50% Move Speed, +75%
  Auto-Attack speed and -30% cast time for up to 10 allies, on buff_allies
  3; Royal Banner's +50% cooldown rate for allies (30% was read) on
  buff_allies 4; Circle of Life's 107 / 133 / 173 / 227 by Rejuvenation
  Charges (107 flat was read) on heal_burst 4; Mystic Rocks' -35% Healing
  Received aura (-50% was read) on heal_reduction 4, under the -40/-50%
  rung; Magic Rune's +5% magic damage and Healing Cast a stack (10% was
  read) on buff_allies 3; Anguished Soul's fear, 1.25s rising to 2.25s with
  charges, on peel and knockback_displace 4; Earth Crusher's radius, 5
  rising to 9 with charges, on burst_aoe 4.
- **Curation grades deferred at the move to the newer snapshot** (each
  needs a rubric grade and a logged decision): Oathkeepers' heal_sustain on
  Blessed Aurora (50 per auto-attack for 5s); Hoarfrost's Avalanche at 320
  per cast against the T44 pin; Ground Shaker (every mace's W: 219 in a 4
  radius plus an air-throw) and the 1H Mace's Deep Leap damage, no rows;
  Harpoon's catch; Battleaxe burst_st 2 on a rejected "1H budget"; Fleet
  Footwork and Shockwave mobility; the damage-only shared spells (Whirling
  Strikes, Throwing Blades, Explosive Arrows and others) and the scope of
  the 191 = 2 burst anchor; Soulscythe's knockback 4 on an air-throw;
  Siegebow and Energy Shaper's Bolt Shot 4 now that Explosive Salvo scores
  its own row; Permafrost's burst_aoe 6 (173 vs players); Raging Blink's
  missing disengage; the Smuggler Cape's tankiness on GEAR_STATS; Fallen
  Staff's and Chillhowl's ally-save peel; the fear ladder (Demonic 4,
  Infernal 2); Wings of Fire's engage; the Dragon omelette's Healing Cast
  rider; Flare's enemy cooldown-rate cut and the `reveal` capability; gear
  self-costs stated in cited texts.
- **Black Hands' Devastating Strike knockback has no structured candidate**:
  the second hit's knockback is unscored (an `effect_overrides.yaml` add:
  entry would ground it); the weapon is retired, so only old permalinks
  read it.
- **Worn items with an effect and no sheet**: the doctrine never counts
  them and a kit that wears one scores the slot as nothing (V: 10, Kits
  name the worn items that carry no combat effect). The Calming Potion
  (1.04% of the potions in killer parties of 10+, 4.75% at 4-9) hides the
  drinker and up to 20 group members from mobs and shields them for 90.85
  damage over 5.7s at T7; the fish sandwich (0.66% and 0.99% of the meals) raises
  max health 10.87% and healing received 9.5%; each needs a curated row.
  The common raw fish (0.87% and 2.71% of the meals) is recorded without
  its tier: T1-T7 regenerate health out of combat while the T8 fish raises
  crowd-control duration 10% (FOOD_FISH_FRESHWATER_8_RAW,
  FOOD_FISH_SALTWATER_8_RAW), so keeping the tier on the harvest's food
  ids, or a curated row, decides it. Gatherer caps and boots (0.33% of
  helmets at 10+, 0.98% at 4-9) carry combat actives (the caps' Block,
  Self Cleanse and Emergency Shield) under the armor sheet's "not
  catalogued (non-combat)".
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
- **The committed rosters artifact grows about 1 MB a day**: it keeps the
  battle list and the Dragon Portal, what the build reads (29.0 MB gzipped
  at 69,958 battles; the kill-feed poll's other records live in
  the local `party_rosters_full.json.gz`; V: 10, The committed rosters
  artifact keeps what the build reads), so GitHub's 100 MiB file limit
  returns in about two months. The permanent fix: every table the build
  reads (the kit doctrine included) derived at the fold and committed, the
  raw records local beside the cache, the derived tables' provenance read
  off the fold's record.
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
  10-14 and 15-19 (20 reads the pooled copy cell); its band keeps the base
  `ranged_aoe_core` minimum. Forged for brawl_clap, the roster reads brawl
  in 9 of 10 sweep cells and split in one (Castle 20), never brawl_clap
  (notes/findings/2026-10-09-forge-quality.md). The ranged minimum it
  keeps sits above what brawl_clap winners field ("Forge minima above what
  winners field").
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
- **A status move in the CTAs dialog drops unsaved edits**: with the form
  edited, a status move asks "Unsaved changes are kept in the form.
  Change the status now?" and then redraws the form from the saved CTA,
  so the typed name, times, size and notes go (slots edited stay). Seen
  in the stub-database page: a typed name came back as the saved one and
  "Unsaved changes" cleared. The move handler redraws through
  `renderEvent()`; the renewal repaints the share row alone
  (`renderShare`, `renderMeta`) and keeps the typed fields. A fix keeps
  the typed values across the move's redraw.
- **A caller's role label against the weapon's seat**: an imported
  "Witchwork (DPS)" carries DPS as the slot's role label, and the role
  tag and the per-role counts still read the weapon's primary seat
  (frontline: one role read). Whether a comp's counts follow the caller's
  label where it names a role class is a maintainer decision; the same
  weapon's seat is the open question under "A frontline's damage points
  making a ranged carrier".
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

## Product features (deprioritized until comp quality satisfies)

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
