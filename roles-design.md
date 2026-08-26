# Roles Design Record — 2026-08-25

Owner-approved design (chat rounds, 2026-08-25) for the role layer: why
generated kits were wrong, and how roles fix them. This is the durable
record ("we want to fix this one time and not have to come back").

## STATUS (2026-08-25, end of session)

**Increment 1 SHIPPED**, grown well past its original scope through eight
owner grading passes (all recorded in tests/VALIDATION.md round 10):

- the role book (`pipeline/roles.yaml`): 19 roles — seats + FUNCTION
  roles (taxonomy v2) + the typed `gear_effects` catalog
- the E-first TIERED SWEEP: function membership derived from every
  weapon's own slot structure (E = primary, Q/W ability = secondary),
  spell-classified splits (shield_break claims its spells away from
  purge)
- equipment classified under the UNIQUE-ABILITY-FIRST law: chests by
  tree stat numbers, the FULL 18-offhand roster by stat profile,
  heads/shoes by unique active; tree passives recorded
- both engine ports: `detect_role` (seat + functions + secondary +
  carrying), `role_advisory` (off-role-kit and no-engage-tank flags) —
  descriptive, parity-carried, rendered in the status card
- contracts: tests/test_roles.py R1–R11

**Increment 2 SHIPPED** (same day; owner ruling: "yes its the whole
build. infact we might even need to include food, potion and capes and
you are right about passive defaults"):

- generated kits are DOCTRINE-LED (`kit_options`, both ports, parity +
  the R12–R16 contracts): the chest pool hard-gates to the seat's
  uniform (the everyone-gets-Hellion bug is dead — R12); every other
  slot (head/shoes/cape/offhand/food/potion) carries a doctrine tier
  mined from the seat's OBSERVED reference builds (builds_index,
  build-id cited, audited in roles_report `kit_doctrine`) — tier-first
  in context-free mode, exact-marginal-first in comp-aware mode (T22:
  the engine's own physics outranks a sparse observation). Manual
  builds still score anything; role_advisory flags them.
- PASSIVE DOCTRINE (owner-confirmed defaults): cloth → Aggression (+8%
  damage & healing cast), leather → Quick Thinker (+5% CDR,
  display-only — no invented channel), plate → Authority (+10% CC
  duration) on the frontline and Tenacity (+20% CCR) elsewhere.
  roles.yaml names only the FAMILY; ids resolve from each piece's own
  dumps menu, magnitudes parse from the spell descriptions
  (`doctrine_passives` per piece), and the resolved stats feed the
  build channels.
- the Leering-Cane pairing is EMERGENT PHYSICS, not a hand list: the
  CC-duration stat (`bonusccdurationvsplayers`, now in the dataset)
  multiplies the wearer's own duration-bearing CC via the new
  `cc_mult_caps` build channel — worth something on Incubus, exactly
  nothing on Great Fire (R13).
- kit options annotate `doctrine` / `carries` (typed gear effects — the
  Royal-Jacket-on-Realmbreaker variant surfaces cited, R16) /
  `passive`; the loadout panel shows the seat + passive + carried
  effect line.

**Board GRADED 2026-08-26** — the owner reviewed all 465 rows of
out/roles_report.json (seats, kit doctrine, gear effects, equipment)
on the interactive grading artifact: 15 rulings, everything else
accepted as shipped. Corrections landed same day (VALIDATION.md
full-board entry): eight membership fixes in roles.yaml, the new cited
`kit_doctrine.overrides` (drop/add on the mined pools, fail-closed)
and `gear_affinity_overrides` layers, and the dive-dagger ≥7
viability exclusion. R17 pins the batch.

**Increment 2.5 SHIPPED 2026-08-26 — per-weapon doctrine + effect
quotas** (owner design, from the Demon-Armor-on-Hand-of-Justice case:
"its not likely that hand of justice would be using demon armor ...
maybe the composition didnt have enough demon armors so the engage
tank has to take one"). Verified on the data first: the sighting is
cb_clonepeek seat 19, and that roster fields FOUR reflect shells —
the chest is a comp allocation, not weapon doctrine. Shipped: (a)
kit pools also mine PER WEAPON (`kit_weapon`, report `by_weapon`);
the kit advisor's context-free ranking puts the weapon's own observed
tier first (`doctrine`: weapon/seat/false, `doctrine_n` = [count,
total] sample honesty); (b) chests granting a typed gear effect are
EXCLUDED from the per-weapon tier, tagged `effect:` in seat pools,
and quota-mined per near-complete observed roster
(`mine_effect_quotas` → report `effect_quotas`, display-only until
owner-graded — reflect shells: 7 of 8 rosters, typically 3 copies);
(c) kit overrides extend to weapon scope (`overrides.<seat>.weapons`)
and seat-level drops cascade into per-weapon pools. R18 pins it;
60/60 parity carries the tier strings through both ports.

**Pending**: increment 3 (forge role assignment + owner-graded
fine-role need profiles — plus grading of the effect-quota table and
mechanism pairing rules for effect carriers), increment 4 (uptime
economics).

## The problem (owner observations, both verified)

1. The kit advisor gave every member of a brawl 20 comp the same gear
   (Hellion Jacket class) regardless of job — because it scored items by
   COMP-POOL marginal fitness: tank gear counts as pooled tankiness (which
   saturates), while a damage aura is the biggest unsaturated marginal for
   every body. Verified: item values were byte-identical across wearers.
2. Roles were 1:1 curator hints (`role_hint: melee` -> dps), so Grailseeker
   (4 damage points vs 18 utility, E deals 125) sat in a dps slot wearing a
   damage jacket.

## The model (owner rulings, verbatim anchors)

- **A role is a property of the member-in-comp** — weapon × spells × gear ×
  what the team needs — not of the weapon. "one realmbreaker can play
  different roles in different situations. therefore roles shouldnt be
  locked 1:1."
- **Gear selects the role**: Royal Armor = team energy (Energy Source),
  Royal Jacket = team cooldowns (Royal Banner), Hellion = damage+sustain.
  Healers likewise: main heal / backline heal / tanky brawl heal by kit.
- **Roles are the primary objects, not weapon menus**: "I dont think we
  build the 137 role menu. different items and weapons fall into different
  roles ... you get that from the comps we have made, from the data online,
  from the gear people wear, from guides." The per-weapon menu is the
  inverse index of role membership.
- **Coarse classes stay**: frontline / healer / support / dps are "the
  default role but each role has more jobs it has to do". Two-level
  taxonomy, as detailed as needed, built once.
- **Cross-class assignment allowed and highlighted**: "can the engine give
  grailseeker d-tank role when no d tank exists? yes - just highlight it."
- **Advisory is a headline feature**: detect the role a member IS playing
  from their kit and flag mismatches — the Longbow + Mercenary Jacket case
  ("the jacket they are wearing is reducing the damage they do and they
  are actively wasting a DPS slot"), and comp-level balance ("having 3
  heavy maces in party and 0 engage tanks would be an obvious flag").
- **Scoring is untouched**: role labels never add or subtract points; the
  member scores as the kit it actually wears. Roles steer generation, kit
  building, and explanation only — the capability model stays the engine.

## Architecture

1. **Role book** — `pipeline/roles.yaml`: one record per fine role: id,
   class (frontline/healer/support/dps, plus `meta` for
   battlemount/caller/scout which are recorded but never forged), job
   description, gear uniform (catalog ids + named items we don't model
   yet), spell doctrine where ruled (Incubus tank = Sacred Ground + Snare
   Charge, owner 2026-08-25), and MEMBERSHIP: weapons and items with an
   evidence source each (comp:<id> slot label / guide research citation /
   owner:<date> ruling / derived:<capability signature>). No guessed
   memberships — same evidence discipline as capability sheets. Weapons
   without evidence stay off menus and fall back to the coarse
   `role_class` behavior.
2. **Build step** — build_dataset validates the role book (known ids,
   evidence present), ships `roles` + derived per-weapon `role_menu` into
   the dataset, writes `out/roles_report.json` (the audit board the owner
   grades).
3. **Engine (both ports)** — `detect_role(weapon, gear, spells)` = played
   role; `role_advisory(party, ...)` = descriptive flags:
   member-level (kit fights the needed role) and comp-level (fine-role
   balance truisms: e.g. frontline present but zero engage tank at 10+).
   DESCRIPTIVE ONLY in increment 1 — never gates, never scores.
4. **Kit advisor rework (increment 2)** — kit = the assigned role's
   uniform, evidence-led (reference builds first), engine marginals only
   choosing between the role's legal variants (royal-energy vs royal-CDR
   vs hellion on the same weapon).
5. **Forge role assignment (increment 3)** — generated slots get fine
   roles from comp needs; fine-role need profiles derived from real comp
   mixes and owner-graded (blind round) before they gate anything.
6. **Uptime economics (increment 4, optional)** — gear survivability
   multiplies the wearer's own delivery; derives the cloth-in-brawl ban
   from mechanism.

## Taxonomy v2 (owner correction 2026-08-25: functions, not trees)

The owner rejected tree-shaped roles ("why is curse support its own role,
shouldnt those weapons be in like the pierce, purge, healcut
role/category") and asked for auras typed individually ("there is also
the demon armor aura, judicator armor aura, guardian armor aura"). Two
structural kinds now exist:

- **SEAT roles** carry a chest uniform and are what a body occupies:
  - frontline: `engage_tank` (clump maker), `stopper_tank`
    (defensive/d-tank), `off_tank`
  - healer: `main_healer`, `kite_healer`, `brawl_healer` (kit-flavors)
  - support: `shield_support` (cleanse/shield lane), `zone_support`
    (ice/slow ground denial)
  - dps: `ranged_aoe`, `sustained_brawler`, `bomb_aoe`, `dive_cleanup`
  - meta (never forged): `battlemount_pilot`, `caller`, `scout`
- **FUNCTION roles** have NO uniform and ride along with whatever seat
  the member occupies — kits are judged against seats only (Incubus cuts
  heals in tank plate, Carrioncaller in brawler leather): `pierce`
  (Damnation, Spirithunter), `purge` (Lifecurse, Fists of Avalon),
  `anti_heal` (the round-9 heal-cut roster). Cross-tree by construction.
- **GEAR EFFECTS** (`gear_effects` in roles.yaml) are not roles at all:
  each aura/active is typed individually (energy font = Royal Armor,
  cooldown banner = Royal Jacket, enemy-weaken aura = Guardian, ally
  force shield = Judicator, reflect area = Demon, lifesteal steroid =
  Hellion) with the items granting it and the weapons EVIDENCED as
  dedicated carriers (Realmbreaker royal, Oathkeepers/Occult royal
  jacket). They attach to whatever role wears them — a Guardian-Armor
  engage tank stays an engage tank CARRYING the weaken aura. Detection
  reports "seat + functions + carrying".

Sources: albiononlinegrind ZvZ build labels + an 18-slot published comp
with named support slots; albionzvzmanual.github.io/roles/; metabattle
tags; our own comps' slot labels (which already use tank/main_tank/
support/healer/dps/rdps/battlemount); gear-convention research (Royal
Armor "Energy Source", Royal Jacket "Royal Banner", Hellion "Life Steal
Aura" — wiki-cited). Full citations live in the role book entries.

## The gear model — the UNIQUE-ABILITY-FIRST law (owner 2026-08-25)

The general form of the weapons' E-first rule, named by owner correction
("dont call it E-first law, it should be something like unique ability
first law because armor pieces arent on e, they might be on d,f,r"):
identity comes from the slot whose ability is UNIQUE to the item —
the E for weapons, the D/F/R active for equipment. An armor/hat/shoes
piece offers three ability choices, the FIRST TWO shared across its tree
("all leather armor piece for example have health regen, inferno
shield") and the third unique — "just like weapons, the identity of the
equipment is derived from its unique spell."

The tree carries the stat identity — "damage and tankiness is based on
which tree the equipment belongs to. you need to pull numbers to
classify items into right role" — and the tree's PASSIVE choices count
toward it (owner: "the damage/heal bonus isnt taking into account the
passives which are also unique to that tree ... most cloth users will
take the damage passive on equipment to increase damage even higher").
Measured (2026-08-25): chest stats cloth 54-68 armor / +40-50%
damage-heal, leather 92-100 / +25-30%, plate 152-161 / +0-5%; tree
passives from the dumps (gear_spells.json) — cloth +8% damage/heal or
-10% cast time or energy cost; leather balance / AA speed / CD
reduction; plate MR-AR / CC duration / CCR / threat. `classify_gear`
stamps `gear_class` (numbers first, tree id fallback), `role_affinity`
(the seat roles whose uniform admits the class) and `tree_passives`;
out/roles_report.json carries the items board + gear-effect candidates.
Recorded gaps: the stats bank holds zeros for head/shoes/offhand pieces
(class falls back to tree id until fetched); the gear records curate
only each item's UNIQUE active — the tree-shared first two abilities and
the passive PICK (which passive a role's doctrine takes, e.g. cloth dps
= the damage passive) are not yet modeled per kit.

## Validation

Role book contracts in `tests/test_roles.py`; detection/advisory pinned on
the owner's own cases (Longbow+sustain-jacket flag; 3-stoppers-0-engage
flag; fitness untouched); parity carries detection/advisory per case; the
membership board (`out/roles_report.json`) goes to the owner for grading
in batches, corrections land as cited rulings.
