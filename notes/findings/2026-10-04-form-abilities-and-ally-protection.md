# Form abilities and ally protection — 2026-10-04

What `pipeline/audit_form_abilities.py` lists on the pinned snapshot
(`5cf2e8e9b702`): 25 form abilities across the eight shapeshifter forms,
and 24 equippable spells that protect another ally. Both lists were
graded the same day (maintainer decision; V: 10, Form abilities score on
the E; Form abilities and ally protection graded). This note records what
was found, the grade each row received, and what was left without a row.
The full text of every ability, numbers resolved, is the worksheet the
audit writes to `review/form_abilities.md`.

## 1. Why these were not on a sheet

A sheet row cites an equippable spell, and `curate_helper.py` prints the
text of equippable spells. A shapeshifter staff's E transforms the
wielder; the form's two abilities and its passive carry their own names
and descriptions in `spells.json` and sit on no equip menu. The staves
were scored on the E's own text ("Offensive: medium", the transform
grant), so a form ability nobody read is a capability nobody scored. The
dumps link a form to its abilities in a file the snapshot cache does not
carry; the audit links them by name and lists any form spell it cannot
place.

Two reading traps the audit handles:

- A reworked ability keeps its id and points at a new description.
  Barbed Roots reads `SPELLS_ENT_CHANNEL_TREE_V2_DESC`; the text under
  the id's default tag is the retired one and still says the channel
  cleanses allies. The live ability does not. The spell's own
  description tag is the one to read (the rule `parse_dumps.py` follows).
- A named follow-up of an equippable spell (Giant Smash, Sky Bolt, the
  Wild Magic effects, the bleeds) is already inside its parent's indexed
  description. The transform is the one class whose abilities are not.

## 2. Form abilities and the row each received

Base values (item power scales them in game). Every row is on the staff's
E; the scores are curation judgment.

| Weapon | Form ability | Row |
| --- | --- | --- |
| Rootbound Staff | Seedling's Bloom: a ground heal zone, 8s, on a 3s cooldown | heal_sustain 2 to 4 |
| Rootbound Staff | Barbed Roots: 175 absorb and Forced Movement immunity for allies in 11m, enemies slowed 50% | peel 2, slow 2, anti_dive 2 |
| Earthrune Staff | Boulder Crash: 125 in a 3.5 radius, stuns 1.2s, 4s cooldown | stun 4 |
| Earthrune Staff | Tectonic Shift: a stone wall knocks enemies back 2 and pulls those between wall and caster in; Tectonic Slam throws a 6 radius in the air | clump_create 2, knockback_displace 2 |
| Earthrune Staff | Tectonic Slam's Rune: Max and Current Health -10% inside, 5s | max_health_cut 2 |
| Primal Staff | Feral Bash: 130 in a 4 radius; with a Shift Charge stuns 0.9s | stun 2 |
| Primal Staff | Wild Onslaught: a dash, damage resistances -15% for 3s | resist_shred 2, mobility 2 |
| Primal Staff | Roar: enemies in the cone flee for 1s | peel 2 |
| Primal Staff | Swipes: auto-attacks slow 20% for 1s on a Shift Charge | none |
| Stillgaze Staff | Serpent's Gaze: a 3s channel petrifies unmounted enemies (ignores Crowd Control Resistance, cannot be cleansed) | stun 4 |
| Stillgaze Staff | Crystalburst: Healing Received -20% in a 4 radius | heal_reduction 2 |
| Stillgaze Staff | Neurotoxin: poisoned enemies deal 12% less damage | damage_debuff 2 |
| Prowling Staff | Infected Scrapes: Healing Received -4% a stack, five stacks | heal_reduction 2 |
| Prowling Staff | Sinister Swipes and Pounce: three charges through the target, a leap | mobility 2 |
| Hellspawn Staff | Fireflash Orb: the recast teleports the imp to the explosion | mobility 2 |
| Hellspawn Staff | Hellfire Barrage: a single-target channel, 30 every 0.2s | burst_st 2 |
| Hellspawn Staff | Melting Point: a lava puddle every third auto-attack | none |
| Lightcaller | Judgment: 350 in a 7 radius after 1.2s | burst_aoe 4 to 5 |
| Bloodmoon Staff | Rip Through, Tear Open, Frenzied Slashes | none: the rows it has cover them; the auto-attack speed stacks fall under standing rule 13 |

A row on an E takes the capability from the tree pool's Q or W on that
weapon (one slot per capability): the pool row sits under `except:` on
the Rootbound (peel, slow, anti_dive), Earthrune (clump_create), Primal
(resist_shred, peel), Prowling (mobility) and Hellspawn (mobility)
sheets.

## 3. Ally protection under the anti-dive rule

The rule: anti_dive counts an effect landed on the diver, and a
protection placed on other allies at the moment of the dive: an absorb
shield, a damage immunity or a damage redirection on an ally, and a
protective zone or aura (an area that stays and raises the damage
resistances of the allies inside it).

| Spell | Holder | What it does | anti_dive |
| --- | --- | --- | --- |
| Protective Beam | Enigmatic Staff E | a 240 absorb bubble around the targeted ally, re-applied every second | 4 |
| Salvation | Fallen Staff E | 20 allies healed and immune to damage for 2s | 4 |
| Arcane Protection | arcane tree Q | 300 absorb for 2s on the targeted ally | 2 |
| Tether Shift | shapeshifter tree W | 300 absorb on the tethered ally, pulled to the caster | 2 |
| Divine Protection | Divine Staff E | 456 absorb for 4s on the targeted ally | 2 |
| Glacial Prison | Chillhowl E, the ally use | the targeted ally frozen for 2s, immune to damage | 2 |
| Soul Link | Ironroot Staff E | half the damage one linked ally takes moves to the other | 2 |
| Shield Charge | Knight Boots | 250 absorb on the ally charged to | 2 |
| Barbed Roots | Rootbound Staff E (form) | 175 absorb on allies in 11m, the divers slowed | 2 |
| Force Shield | Judicator Armor | a zone for 8s: +25% damage resistances and Healing Received | 2 |
| Guard Rune | mace tree W | a zone for 5s: +6% damage resistances, Forced Movement and Stun immunity | 2 |
| Protection of the Fiends | Demon Armor | a 7 radius aura: +43% damage resistances on allies, half the damage reflected | 2 |
| The Void | Malevolent Locus E | a bubble for the allies inside: cleanse and +30% damage resistances | 2 |
| Holy Explosion | Great Holy Staff E | a channel around the caster: divers shoved 10m, +16% ally resistances | 2 |

A weapon whose E already holds anti_dive takes none from its tree pool:
Great Arcane (Time Freeze), Enigmatic and Malevolent Locus decline Arcane
Protection's row, the Rootbound declines Tether Shift's, Bedrock declines
Guard Rune's.

Left without an anti_dive row:

- Group shields cast into the clump, not on a dive: Adapting Matter,
  Hyperstatic, Blessed Aurora, Dual Nature. Emergency Shield (gathering
  helmets) and Clinging Frost (a prototype helmet) are not fielded gear.
- A resistance buff on one targeted ally (Holy Blessing, Protection of
  Nature, Living Armor, Rejuvenating Breeze) and Defensive Slam's instant
  buff with no area that stays: these remain buff_allies.

## 4. What the grades move

The Dragon Portal rows are re-derived on the committed roster artifact
with the new sheets (`derive_portal_rows.py`), so supply and its typical
stay in one unit there. The style x band rows at 10+ come from
`audit_style_rosters.py`, which reads the cache: they re-derive at the
next fold. Until then anti_dive at 10+ reads supply on the new sheets
against a typical measured on the earlier ones (BACKLOG).
