# Roles Design Record

The design record for the role layer: why generated kits were wrong, and how
roles fix them. This is the durable record — the layer was designed to be
fixed once, not revisited.

## STATUS

Increments 1, 2, 2.5 and 3 are SHIPPED; the layer then kept growing
(fail-closed generation, the seat-all pass, killboard kit doctrine, the
observed-build overlay, carrier quotas, one player one vote, size bands). The
invariants are in CLAUDE.md ("One role read", "Kits are what winners wear");
every round, score and board grade is in `tests/VALIDATION.md` (round 10, the
full-board entry, R12–R28); the current shipped surface is HANDOFF.md "The
engine today". The decisions that shaped the layer, kept here because this
is the durable design record:

- **The kit is the whole build.** Food, potion and cape are kit slots like
  the armor pieces, and passive defaults are doctrine — kits are doctrine-led
  through every slot; passive doctrine is resolved from the dumps.
- **An effect-carrier chest is a comp allocation, not weapon doctrine.** Hand
  of Justice does not wear Demon Armor by identity; an engage tank takes one
  when the comp lacks Demon Armors — per-weapon tiers + effect quotas, later
  the carrier quota.
- **What matters is what the data says.** The need profiles were fixed after
  a validation round and the killboard roster evidence; the data's
  engage-leaning split overrode the stopper-heavy blind grade, which survives
  as the territory-defense override.

**Pending** (tracked in `BACKLOG.md`): increment 3b's second half (carrier
floors + pairing rules), increment 4 (uptime economics), the menu-less weapons.

## The problem (both verified)

1. The kit advisor gave every member of a brawl 20 comp the same gear
   (Hellion Jacket class) regardless of job — because it scored items by
   COMP-POOL marginal fitness: tank gear counts as pooled tankiness (which
   saturates), while a damage aura is the biggest unsaturated marginal for
   every body. Verified: item values were byte-identical across wearers.
2. Roles were 1:1 curator hints (`role_hint: melee` -> dps), so Grailseeker
   (4 damage points vs 18 utility, E deals 125) sat in a dps slot wearing a
   damage jacket.

## The model

- **A role is a property of the member-in-comp** — weapon × spells × gear ×
  what the team needs — not of the weapon. One Realmbreaker plays different
  roles in different situations, so roles are never locked 1:1 to a weapon.
- **Gear selects the role**: Royal Armor = team energy (Energy Source),
  Royal Jacket = team cooldowns (Royal Banner), Hellion = damage+sustain.
  Healers likewise: main heal / backline heal / tanky brawl heal by kit.
- **Roles are the primary objects, not weapon menus**: there is no
  hand-built 137-entry role menu. Items and weapons fall into roles from the
  comps in the corpus, the data online, the gear people wear and the guides.
  The per-weapon menu is the inverse index of role membership.
- **Coarse classes stay**: frontline / healer / support / dps are the default
  role, but each role has more jobs it has to do. Two-level taxonomy, as
  detailed as needed, built once.
- **Cross-class assignment allowed and highlighted**: the engine may give
  Grailseeker the d-tank role when no d-tank exists — and highlights it.
- **Advisory is a headline feature**: detect the role a member IS playing
  from their kit and flag mismatches — the Longbow + Mercenary Jacket case
  (the jacket reduces the damage they do, and they are wasting a DPS slot),
  and comp-level balance (three Heavy Maces and zero engage tanks is an
  obvious flag).
- **Scoring is untouched**: role labels never add or subtract points; the
  member scores as the kit it actually wears. Roles steer generation, kit
  building, and explanation only — the capability model stays the engine.

## Architecture

1. **Role book** — `pipeline/roles.yaml`: one record per fine role: id,
   class (frontline/healer/support/dps, plus `meta` for
   battlemount/caller/scout which are recorded but never forged), job
   description, gear uniform (catalog ids + named items not yet modelled),
   spell doctrine where decided (Incubus tank = Sacred Ground + Snare
   Charge, cited), and MEMBERSHIP: weapons and items with an evidence
   source each (a comp slot label `comp:<id>`, a guide research citation, a
   logged decision cited by its `tests/VALIDATION.md` entry, or
   `derived:<capability signature>`). No guessed memberships — same evidence
   discipline as capability sheets. Weapons without evidence stay off menus
   and fall back to the coarse `role_class` behavior.
2. **Build step** — build_dataset validates the role book (known ids,
   evidence present), ships `roles` + derived per-weapon `role_menu` into
   the dataset, writes `out/roles_report.json` (the audit board that is
   graded in validation rounds).
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
   mixes and graded in a validation round before they gate anything.
6. **Uptime economics (increment 4, optional)** — gear survivability
   multiplies the wearer's own delivery; derives the cloth-in-brawl ban
   from mechanism.

## Taxonomy v2: functions, not trees

Tree-shaped roles are rejected: a "curse support" role would hide that
those weapons belong in the pierce, purge and heal-cut categories, and
auras are typed individually (the Demon Armor aura, the Judicator Armor
aura, the Guardian Armor aura). Two structural kinds exist:

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
tags; the corpus comps' own slot labels (which already use tank/main_tank/
support/healer/dps/rdps/battlemount); gear-convention research (Royal
Armor "Energy Source", Royal Jacket "Royal Banner", Hellion "Life Steal
Aura" — wiki-cited). Full citations live in the role book entries.

## The gear model — the UNIQUE-ABILITY-FIRST law

The general form of the weapons' E-first rule, named for equipment because
armor abilities sit on D/F/R rather than E: identity comes from the slot
whose ability is UNIQUE to the item — the E for weapons, the D/F/R active
for equipment. An armor/hat/shoes piece offers three ability choices, the
FIRST TWO shared across its tree (every leather armor piece offers health
regen and inferno shield) and the third unique — like a weapon, the
identity of the equipment is derived from its unique spell.

The tree carries the stat identity — damage and tankiness follow the tree
the equipment belongs to, so items are classified into roles by pulled
numbers — and the tree's PASSIVE choices count toward it (the damage/heal
bonus alone understates cloth: most cloth users take the damage passive to
raise damage further). Measured: chest stats cloth 54-68 armor / +40-50%
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
the motivating cases (Longbow+sustain-jacket flag; 3-stoppers-0-engage
flag; fitness untouched); parity carries detection/advisory per case; the
membership board (`out/roles_report.json`) is graded in batches in
validation rounds, and corrections land as cited overrides.
