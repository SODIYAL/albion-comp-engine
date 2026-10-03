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

- **The Dragon Portal's 15-20 pool**: under the 40-roster floor (five
  dominant rosters on the training split), so it reads the 4-5 base rows
  scaled and the style x size rows at 10+. `derive_portal_rows.py` gives
  it rows of its own once the poll has filled it; whether a large portal
  party is its own pool or the ZvZ rows is the decision to take then.
- **The popularity baseline on the portal pools**: with the pool-fielded
  gate on, the engine names the hidden member in its top 3 on 9.5% /
  19.3% / 12.6% of holdout drops at 2-3 / 4-5 / 6-7 (9.1% / 13.8% / 9.4%
  without the gate); the pool's three most fielded weapons name it on
  27.3% / 29.6% / 13.9%. At role level the engine leads (76% / 62% / 46%
  against 47% / 52% / 38%). Inside the list the engine still prefers a
  wide sheet (Battle Bracers and Crystal Reaper over the Rotcaller Staff
  and the Longbow, which 26% and 20% of 6-7 winners field): the capability
  score pays a first unit on many rows more than depth on one. Whether
  the meta prior should bucket by content with a larger `delta` at the
  portal, or the sheets under-credit sustained ranged pressure, is the
  question to settle from evidence.
- **The fielded gate beyond the portal**: the gate applies where a
  matchmaking pool has its own harvest (the Dragon Portal's 2-3, 4-5 and
  6-7). The 10+ contents generate through the seat skeleton and the
  style bands with no weapon-level evidence gate; whether a style x band
  fielded list (the killer party of 10+, the kit doctrine's unit) should
  gate their generation is a decision to take from the same holdout
  measure.
- **A blind validation round on the portal pools**: `validated_sizes` is
  empty for `ancient_lands`, so the page flags every size as extrapolated.
  The rows are measured; the round (one form per pool, graded before the
  engine's answer) is what lifts the flag.
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
- **Gear-active doctrine, the next evidence**: the doctrine reads 79
  recording builds (the Character Builder comps and the MetaBattle batch);
  47 of 81 head / armor / shoes items have no vote and ASSUME their own
  active, and Soldier Boots sits one vote under the floor on Rejuvenating
  Sprint, so it supplies nothing until a second build records it. The
  companion's spell array, if it carries armor actives (verify on the
  wire), would be the volume source; so would any caller sheet that
  records gear abilities. A gear-active OVERRIDE in the kit editor (the
  engine already scores `(key, choice)` pairs; the share codec does not
  carry a choice) is the UI increment if callers ask. (V: 10, Gear-active
  doctrine)
- **Magnitude audit queues** (`py -3 pipeline/build_magnitude_review.py`,
  a board generated locally into the gitignored `review/`): the PASV queue
  (39 rows where a passive / stat sentinel grounds a score >= 2 — each needs
  a justification or a downgrade) and the TOP review (44 score-3 rows, the
  top of every ladder, against the dumps numbers). After each capability:
  sheet corrections, a golden case where a score decision changes, rebuild,
  gates.
- **Catalogue gaps with nothing to score**: the plain Cape (7.5% of
  winners' capes), Cabbage Soup (4.7% of their meals), Pork Pie and a raw
  fish eaten as food carry no combat effect, so they have no sheet and a
  kit that wears one shows the slot uncatalogued. Whether a no-row entry
  belongs in the catalogue (the kit doctrine would then name it) is a
  display decision. The meals with a combat effect are curated (V: 10,
  The meals winners eat).
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
  signal planted. A first read on GUILD-level labels (the daily fetch's
  kill lists, 582 training parties of 10-20): `fitness()` AUC 0.50, no
  capability separates wins from losses, party size alone predicts better
  (0.61) — numbers decide these fights. Before the party-level read, add a
  numbers control: each side's size from the battle roster's alliances.
  Any weight change it suggests is a logged decision, and Blackzone Roam's
  weights are now choice-fitted (standing rule 7 as amended), so the
  outcome audit tests the fitted weights. Later: win-lift per weapon, pair
  and copy count, into the prior only after a `v4h` A/B (standing rule
  16); the design doc's plan (§8.6): a prior-adjuster, never the primary
  term.
- **Choice-fitted weights for the other templates**: the harvest records
  no content, so `fit_choice_weights.py` reads every killer party against
  one template (Blackzone Roam). Castle, outpost, territory, faction-war
  and roads weights stay curation judgment until parties carry a content
  label (battle location from the killboard) or each content has its own
  comps. Refit Blackzone Roam after each fold that moves the training
  split materially (`extract` then `fit`; the pull rule stays).
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
- **Cross-check the Resilience Penetration table**
  (`pipeline/resilience_penetration.yaml`, the cited 69-row melee table,
  wiki values) against the dumps. Optional. (Q7)

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
spreadsheet as a saved comp, CSV out) and phase 11 (the engine's read of
the live roster, on the sheet) are built.

- **Guest identity is a name and a claim token** (phase 5). A guest who
  clears their browser loses the claim; the caller removes or moves them
  (phase 6). A Discord login (phase 12) is the stronger identity when it
  comes.
- **Enable leaked-password protection** (Supabase Auth, security advisor
  warning). Project dashboard, no code.
- **Phase 12, integrations** (the spec): a Discord login and bot, a
  Google Sheets link, automatic roster construction (an optimization
  over the target comp, the players' declared weapons and their
  preferences: the first place a player's preference would meet the
  engine, a logged decision).
- **The engine read's role check and kill pressure**: the sheet's read
  lists needs, picks, open slots, replacements and overstack; the
  planner's role advisory, kill-pressure lights and fight chain are a
  later increment on the sheet if callers ask for them (open the CTA in
  the planner meanwhile).
- **The engine read on the CTAs and comps dialogs**: the read runs on
  the sheet alone; a draft CTA or a saved comp is read through "Open in
  planner".
- **Import: an Excel workbook** (`.xlsx`) is not parsed in the page; its
  cells are pasted, or the sheet saved as CSV. A zip-and-XML reader in
  the page is a later increment if callers ask for it.
- **Import: a CTA from a sheet with its players**: the import makes a
  comp (a template has no player); the player column is shown and may
  ride in the slot notes. A CTA with those players on its sheet is a
  later increment (phase 12's roster construction is the place).
- **A party column on slots**: comp and CTA slots carry no party; an
  imported sheet's parties order the slots and may ride in the notes.
- **A player's own history across guilds**: the history dialog reads a
  guild's facts; a player's list of their own CTAs and marks across
  guilds (and a guest's, by claim) is a later surface.
- **History by period**: the facts run over every completed CTA; a
  window (the last 30 days, a season) is a later increment if callers
  ask for it.
- **The CTAs dialog is not live**: the calendar and the sign-up counts
  read on open; the sheet is the live surface. A channel per guild for the
  dialog is a later increment if callers ask for it.
- **Renewing a CTA's share code**: the code is generated at creation and
  never changes; a leaked link needs a new CTA. An admin's renewal (the
  guild join code's pattern) is a later increment if callers ask for it.
- **A caller's role label against the weapon's seat**: an imported
  "Witchwork (DPS)" carries DPS as the slot's role label, and the role
  tag and the per-role counts still read the weapon's primary seat
  (frontline: one role read). Whether a comp's counts follow the caller's
  label where it names a role class is a maintainer decision; the same
  weapon's seat is the open question under "A frontline's damage points
  making a ranged carrier".
- **Gear columns on an imported sheet**: head, chest and boots columns
  are ignored (a comp's slot holds a weapon line; its kit is set in the
  planner). Reading them into the planner's kit through the share hash
  is a later increment.
- **Slot editing inside the comps dialog**: a slot's weapon is set in the
  planner (save, or replace the slots from the planner); the dialog edits
  role labels and notes and removes slots. A weapon picker per slot (the
  profile's combobox) is a later increment if callers ask for it.
- **Multi-party comps**: a template is one planner roster of up to 60. A
  ZvZ of several parties is several templates, and a CTA one roster of up
  to 60, until a grouping is needed.
- **Guild invitations beyond the code**: a member joins only by a code an
  officer shares. An officer adding a member by Albion name, or a player
  asking to join, needs a lookup of profiles the reader is not yet allowed
  to see: a maintainer decision on what a name search may reveal.
- **Guild-scoped reads are all or nothing**: every member reads every
  co-member's character, display name, server and weapon lists. A member
  who wants to keep a secondary list private has no switch (curation
  judgment: a CTA tool exists to show a caller what members play).
- **The caller's controls as their own column**: the sheet keeps the move
  list and the record's mark on one line by sizing the weapon and role
  columns; a window under the sheet's full width wraps them. A fifth
  column for the caller's controls is the next step if callers work on
  narrow windows.
- **The portal page's chrome**: the headings, labels, chips and radii
  follow the planner (the planner's chip, its radius set). The tokens are
  still a copy inside `_portal.html`; a shared stylesheet is the proper
  fix and waits for a second killboard surface.

## Product features (deprioritized until comp quality satisfies)

Enemy-comp counter drafting; fight-plan generation; the blind-validation
workflow as a tool; the companion loot module (COMPANION_SCOPE.md, proposal
only). Saved player profiles moved to "Platform" above.

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
- **Back up the raw battle cache off this machine**: `pipeline/out/party_cache.sqlite`
  (one file since the per-battle JSON files were folded into it; 127k
  battles, kill events included) is gitignored, the only copy of the
  harvest's evidence. A storage bucket (Supabase is a candidate) as a nightly upload
  target after each harvest — a BACKUP, never a build input, so CI and
  provenance stay as they are; a fresh machine pulls it down and re-derives.
  Not the committed artifact (5 MB gzipped when this was written, 52 MB now).
