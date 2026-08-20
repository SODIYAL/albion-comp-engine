# MASTERSHEET — the control surface for the comp engine

This file is two things at once:

1. **The plain-language explanation** of where every number in the engine
   comes from and why a weapon ranks where it does.
2. **The control panel.** The yaml blocks below marked `tune:` are read at
   build time and **override** the underlying config files. Edit a value
   here, rebuild, and the engine — the live dashboard and the Python engine
   both — follows. You never have to hunt through the pipeline files.

To apply your edits:

```
py -3 pipeline/build_dataset.py
py -3 pipeline/build_dashboard.py
```

(Recommended after big edits: `py -3 tests/test_golden.py` and
`py -3 tests/test_js_parity.py` to confirm nothing structural broke.)

Safety: the build **fails loudly** on any mistake here — an unknown weapon
name, a capability a weapon doesn't have, a typo'd section — it will never
silently ignore your edit. And whatever is set here **wins** over the
underlying files, so this file is the single place to look when asking
"what is the engine actually using?"

---

## 1. Where the data comes from

The chain, start to finish:

| Layer | What it is | Where it lives |
| --- | --- | --- |
| **Game files** | The game's own data: every spell's numbers, areas, escalation flags — pinned to one exact game-data snapshot so results are reproducible | `out/dumps_cache/` (snapshot), `data/source_pins.yaml` (the pin) |
| **Parsed spells** | Each spell's damage, radius, max targets, escalation factors, cooldown, description | `out/spell_index.json` |
| **Capability sheets** | The human judgment layer: what each weapon is actually good at, scored 0–3 (soon 1–7), with the exact spell cited as evidence. Shared Q/W spells are curated once per tree; each weapon's sheet carries only its E — the E is the weapon's identity | `pipeline/sheets/pools/` (tree Q/W), `pipeline/sheets/*.yaml` (the E) |
| **Delivery physics** | Auto-derived per capability from its evidence spell: area footprint, target cap, escalation — this is what makes an AoE slow count more than a self speed-buff in big fights | stamped into the dataset at build time |
| **Content templates** | What each content type demands: how much healing, catch, AoE damage etc. a castle fight vs a roads gank wants | `pipeline/templates/*.yaml` |
| **The dataset** | Everything above compiled into one file; the browser engine and the Python engine read this same file, verified identical to 9 decimal places | `out/dataset-latest.json` |

No score exists without a cited spell (the evidence lint blocks the build
otherwise), and no data ships unless its whole chain hash-verifies against
the pinned snapshot.

## 2. Why a weapon ranks where it does

A candidate's score is **exactly how much the party's total comp score
changes if it joins**:

```
score = 0.55·(capability gain) + 0.20·(synergy gain) + 0.15·(meta prior)
        ± viability/duplication adjustments
```

What happens inside "capability gain", in order:

1. **One spell per slot.** The weapon is scored on its best single Q/W/E/passive
   loadout — never the whole spell menu at once.
2. **Geometry.** AoE-delivered utility (catch, peel, slow, stun, root,
   silence, displace) is multiplied by how many enemies the spell's real
   footprint reaches in this fight size and playstyle. A 7m Tornado ≈ 3× a
   self-only speed buff at 20-man; the gap closes in small gangs. Effects
   the game gives CC Escalation to (duration grows per target hit) get that
   on top — read per spell from the game files.
3. **Fight physics.** AoE damage escalates with clump size; stacked
   single-target damage is taxed by the game's Focus Fire protection
   (up to 75% at 26+ attackers).
4. **Demand.** What's left is compared against the content template: filling
   an empty need is worth the full weight, topping up a covered one is worth
   little (concave), and over-stacking costs.

The dashboard's "Why" panel shows these exact terms for any pick — the
numbers there ARE the scoring, not a summary of it.

**Known blind spots** (the improvement roadmap, in priority order):
damage magnitude is flat (a 1v1 weapon's AoE reads equal to Kingmaker's —
the 1–7 rubric in §7 fixes this); enabler value is missing (Soulscythe's
knockup line that makes everyone's damage land earns nothing yet); the
"who actually plays this at scale" reality-check exists but is unwired;
gear coherence (Heavy Mace on cloth) has no layer at all yet.

---

## 3. The dials — scoring

These values are LIVE: edit and rebuild. They currently mirror the tuned
defaults.

```yaml tune:scoring
weights:
  alpha: 0.55        # weight of raw capability gain
  beta: 0.20         # weight of synergy gain
  delta: 0.15        # weight of the meta prior
  gamma: 0.70        # concavity: how fast a filled need stops paying
  overstack_max: 0.5 # max penalty for over-stacking a capability
  rho: 0.25          # per-copy cost of duplicate weapons
  viability: 0.15    # bonus for core-listed weapons at large sizes
  headroom: 0.1      # small credit for supply between target and soft cap

# Pairs worth more across two players than their sum. Add a pair by copying
# a line; capability names must exist in the content template's demands.
capability_synergies:
  - {a: clump_create,   b: burst_aoe,      bonus: 1.5}
  - {a: engage,         b: catch,          bonus: 0.8}
  - {a: resist_shred,   b: burst_st,       bonus: 0.8}
  - {a: heal_reduction, b: sustained_dps,  bonus: 0.8}

# Hand-set "people actually play this" nudges, 0–1 per weapon.
# Real win-rate data replaces these in Phase 3.
meta_prior:
  MAIN_HOLYSTAFF_AVALON: 1.0   # Hallowfall
  2H_MACE:               1.0   # Heavy Mace
  2H_HAMMER:             0.8   # Great Hammer
  2H_ICECRYSTAL_UNDEAD:  0.8   # Permafrost Prism
  2H_HOLYSTAFF:          0.6   # Great Holy Staff
  2H_LONGBOW:            0.6   # Longbow
  MAIN_MACE:             0.6   # Mace
```

## 4. The dials — fight physics

```yaml tune:mechanics
aoe_geometry:
  # How many enemies an area of a given radius realistically affects
  # (step table: the largest radius <= the spell's radius wins).
  radius_targets:
    0: 1
    2: 2
    3.5: 3
    5: 4
    6.5: 6
    8: 8
  # Which capabilities scale with targets reached. zone_control is excluded
  # on purpose — area already IS its identity.
  geometric_caps: [catch, peel, slow, stun, root, silence, knockback_displace]
  # Which of those also get the game's CC Escalation (longer duration per
  # target hit) when the spell carries the flag in the game files.
  cc_duration_caps: [stun, root, silence]
  escalation_cap_targets: 8
  # THE ANCHOR: the clump size at which an AoE utility spell counts exactly
  # its sheet score. 2 = "a small skirmish". Raise it and AoE utility gets
  # weaker everywhere; lower it and AoE utility gets stronger everywhere.
  reference_clump: 2
```

## 5. Per-content demand overrides

Adjust what a content type demands without touching the template files.
Empty = no overrides. Example (uncomment and edit):

```yaml tune:templates
# castle:
#   catch:   {weight: 5, target: 3.5}   # castle wants more catch
# blackzone_roam:
#   burst_st: {weight: 0}               # zero out single-target at roam
```

Valid fields per capability: `target`, `weight`, `soft_cap`, `scales`.
Contents: `blackzone_roam`, `castle`, `castle_outpost`, `faction_war`,
`roads`, `territory_defense`.

## 6. Per-weapon score overrides

Your expert rulings, applied instantly without editing sheets. You can
**re-rank** a capability the weapon already has, or **remove** it
(score 0). You cannot invent a new capability here — that needs a sheet
row with spell evidence, which keeps the no-score-without-proof rule
intact. Empty = no overrides. Example:

```yaml tune:sheets
# Expert ruling 2026-08-20 (pinned by golden T19): Bedrock Mace is THE
# anti-dive pick at scale — Primal Slam's 18m CC-resist-ignoring throw
# leaves a PERSISTENT WALL (an extra peel layer, fire-and-forget), on a
# support-tank kit with Guard Rune; guild runs it double-CORE. Iron-clad's
# whirlwind must physically contact the diver while channeling — in large
# fights nobody uses it for this. The raw numbers alone (18m vs 12m) hid
# the delivery nuance; this is rubric Q2 reliability + Q8 kit fit.
MAIN_ROCKMACE_KEEPER:          # Bedrock Mace
  anti_dive: 3
2H_IRONCLADEDSTAFF:            # Iron-clad Staff
  anti_dive: 1

# 2H_TWINSCYTHE_HELL:          # Soulscythe
#   knockback_displace: 2      # the line knockup is undervalued at 1
# 2H_DOUBLEBLADEDSTAFF:
#   catch: 1                   # gank kit, not ZvZ catch — down from 2
```

Weapon keys are the game's unique names — see any weapon's dossier in the
dashboard, or `pipeline/sheets/*.yaml`.

## 7. The 1–7 ability rubric (designed, not yet wired)

The 0–3 scale is being replaced by a 1–7 score per (spell, capability),
judged on eleven questions: raw magnitude · reliability · controllability ·
ease of execution · uptime economy · cost of use · counterability ·
kit/role fit · purpose fit · payload/follow-up · **team enablement** (does
it make everyone else's damage land — the Soulscythe question). Targets
count and content-fit are deliberately NOT in the rubric: geometry and
templates already compute those, and scoring them twice would double-count.
When this lands, question 1 is pre-filled from the game files. The judging
instruments already exist: `review/stat_chart.html` (the REAL numbers —
damage, CC durations, knockback distances, slow-power — per capability,
sorted, with the current score beside each row) and
`review/magnitude.html` (score-vs-dumps-text audit boards). Rebuild the
chart after sheet edits with `py -3 pipeline/build_stat_chart.py`.

## 8. Guild-approved builds

The guild announcement, recorded 2026-08-20, structured but in the guild's
own words and weapon names. It ships into the dataset verbatim as a
**guideline layer**: visible in tooling, usable as a validation reference,
never a hard rule the scorer enforces. (Mapping the guild's weapon names to
game ids is a separate wiring step.)

```yaml tune:guild_builds
source: guild announcement — approved builds, group content
recorded: 2026-08-20
scope: castle/outpost content, everything listed is regear-eligible
status: guideline, not hard rules — "if your build isn't listed, ask"

legend:
  CORE: first choice — if you don't know what to play, play this
  APPROVED: regear-eligible, but don't bring it while a CORE slot is open
  size_tags:
    "5": best small-scale (5-10)
    "10": comes online at 10+
    "20": needs 20+ to matter
    bomb: bomb squad — spec-gated, not main zerg
    untagged: works at any size

standard_kit:
  cape: Smugglers 4.3 always; Lymhurst on healers with no Chariot
  potions: Gigantify — no choice, no substitutes
  food: >
    Ava Pork Omelette 7.1 default; Ava Beef Sandwich acceptable; brawl DPS
    run Beef Stew 8.1+; support tanks on Demon may run regular Beef Sandwich.
    7.1 food / 4.3 cape is the cost-efficient line.
  shoes: >
    Blink shoes standard in brawl and clap, Stalker usually favored.
    Exceptions: healers and some tanks run Royal Shoes (NOT Sandals).
  fallback_helm: >
    Melee and unsure? Cleric Cowl. Not always ideal, never wrong.

comp_rules:
  - "Under 10: at least 1 healer, at least 1 tank; don't stack all-melee or
    all-range; everything approved at larger sizes is approved here."
  - "10-man: minimum 2 healers, 3-4 tanks, rest DPS. Unusual picks genuinely
    work here (Primal Staff as a main is fine)."
  - "10-20 FILL ORDER: healer first, tanky support second, DPS last. Do not
    bring the 5th DPS while the 3rd healer slot is open — support needs grow
    faster than damage needs. Most common way comps go wrong."
  - "20+: caller declares clap/kite or brawl. 6 tanks minimum, 4 healers
    minimum, then DPS."
  - "Kite comps need at least 1 Occult Staff."
  - "Brawl zergs always, always run a Carving (as pierce tank)."
  - "Kite zergs practically never run Carving — Spirit Hunter or Damnation."
  - "Royal armor: minimum 2 Royals per 10 people for mana; can cut if
    there's a Chariot."
  - "Bomb squad is a separate group, spec-gated (~100 spec floor, often the
    whole tree). Join when the caller asks, not because it looks fun."

bomb_weapons: [Brimstone, Blazing, Wildfire, Infernal, Energy Shaper (most
  common), Weeping Repeater, Siegebow, Heavy Crossbow, Arclight Blasters]

roles_20plus:
  clump_tank:
    count: 1
    core: [Hand of Justice, Earthrune (Golem), 1H Mace]

  support_tanks_clap_kite:
    count: 5
    core:
      - Bedrock Mace x2 (Guard Rune, now hits 10)
      - Polehammer (Groundbreaker, 20m — longest-reach hard CC in the game)
      - Great Arcane (silence)
    armor: >
      Head Judicator Helm or Cleric Cowl; chest Knight, Demon, or
      Duskweaver; blink shoes (some zergs GG Boots or Boots of Valor).
    approved: [Grail Seeker, 1H Hammer, 1H Arcane, Icicle, Stillgaze,
      Black Monk Stave, Camlann Mace, Dreadstorm Monarch, Truebolt Hammer,
      Grovekeeper, Soulscythe, Primal Staff, "Forge Hammer (5, disrupt)"]

  tanky_support_pierce_clap_kite:
    count: 2
    core: [Spirit Hunter, Damnation]
    approved: [Oathkeepers, Life Curse, "Rootbound (midline — keeps the
      frontline topped, opens a retreat path)", Shadowcaller, Hoarfrost,
      "Locus (backline tank / cleanse bot)", "Occult (20+)"]

  support_tanks_brawl:
    count: 5
    core: ["1H Mace (offhand Kaitiff Shield or Astral Aegis)", Heavy Mace,
      Great Hammer, Staff of Balance]
    armor_split: >
      THE RULE, not a suggestion: roughly 50/50 Hellion Hoods and Judicator
      Helms, leaning toward extra Hellion Hoods. Most Hellion Hood tanks run
      Duskweaver armor; other tanks Judicator or Guardian. Blink shoes
      standard, Stalker usually favored. Unsure? Cleric Cowl.
    approved: [Grail Seeker, 1H Hammer, Bedrock Mace, Polehammer,
      Black Monk Stave, Camlann Mace, Dreadstorm Monarch, Truebolt Hammer,
      Grovekeeper, Soulscythe, Icicle, Stillgaze, Primal Staff,
      "Forge Hammer (5, disrupt)"]

  tanky_support_pierce_brawl:
    count: 2
    core: [Carving Sword, Oathkeepers]
    armor: >
      Support tank weapons run Judicator or Demon armor almost without
      exception (Oathkeepers, Life Curse, Rootbound, Shadowcaller,
      Hoarfrost, Locus).
    approved: [Life Curse, Rootbound, Shadowcaller, Hoarfrost, Locus,
      "Occult (20+)"]

  healers:
    minimum: 4
    filled_first: true
    core_holy: [Hallowfall, Redemption]
    core_nature: [Blight, Rampant]
    approved: ["Exalted (20+, required in some larger comps)", Forgebark,
      Fallen, Wild Staff, "1H Nature (5)", "Divine (5)", "Great Holy (5)"]
    never: [1H Holy, Lifetouch, Druidic Staff, Ironroot, Great Nature]

  dps_clap_kite:
    requirement: at least 1 Occult Staff in kite comps
    core: [Permafrost, Spirit Hunter, Rift Glaive, Realm Breaker,
      Spiked Gauntlets, Damnation, Rotcaller, Witchwork]
    scaling: "As the party grows: add Wailing and more Rift Glaives;
      possibly an off-timer Spiked for extra pierce."
    approved: ["Dawnsong (the one common zerg fire staff)", Astral,
      Evensong, Icicle, Hoarfrost, Arctic, Glacial, Mistpiercer, Badon,
      Skystrider, Lightcaller, Hellfire Staff, "Wailing (20+)"]

  dps_brawl:
    core: [Battle Bracers, Infernal Scythe, Realm Breaker, Ursine Maulers,
      Astral, Bloodletter, Demonfang, Galatine Pair, Bear Paws,
      Spiked Gauntlets, Hellfire Hands]
    note: "Demonfang is extremely strong right now — many brawl zergs run
      2, 3, or more. Don't treat it as a niche pick."
    scaling: "As the party grows: more of the above; possibly a Witchwork,
      Wailing, Permafrost, or a small kite/clap pocket for burst."
    approved: ["Carving Sword (fine as straight damage, but pierce tank is
      the better use)", Kingmaker, Dual Swords, Infinity Blade,
      Clarent Blade, Great Axe, Brawler Gloves, Spear, Heron Spear,
      Daybreaker, Hellspawn Staff, Quarterstaff, "Blood Moon (5)",
      "Demonic (5)"]

gear_sets:
  supports_not_support_tanks: >
    Usually Occult. Assassin Hood, Royal Jacket (no swaps allowed), blink
    shoes, Smugglers 4.3.
  healers_clap_kite: >
    Head depends on battlemounts — with Chariot at least 1 Assassin + 1
    Guardian; without, at least 2 Druid Cowls. Chest Robe of Purity or
    Feyscale, no real alternative (Cleric Robe under 10). Blink shoes
    (Merc/Stalker/Cleric/Royal). Smugglers 4.3, swap Lymhurst if no
    Chariot. Ava Pork Omelette, Gigantify.
  healers_brawl: >
    Same as clap/kite except: Judicator chest, Lymhurst cape priority,
    offhand Shield or Blueflame Torch.
  dps_clap_kite: >
    Head mostly Assassin for the reset, some swap to cleanse; 1 Knight
    Helmet; Mistwalker for melee DPS. Chest Scholar, Feyscale, Robe of
    Purity, or Royal Jacket. Blink shoes, sometimes Feyscale. Smugglers
    4.3, Gigantify, food Beef Stew or Ava Pork Omelette — check with
    caller.
  dps_brawl: >
    Head almost always Cleric (Soldier occasionally, Cleric just better).
    Chest Hellion almost always; Soldier for specific roles; Royal for
    mana with no Chariot. Stalker shoes for damage (Boots of Valor okay,
    Stalker almost always better). Smugglers 4.3, Beef Stew 8.1+,
    Gigantify.

battlemounts:
  status: not running them until we get better
  priority: [Chariot, Behemoth / Beetle, Eagle / Bastion / Ballista]
  build: >
    Same on all: Mace or Bloodletter, offhand Aegis or Mistcaller, chest
    Judicator or Guardian as high tier as affordable (T9 ideal, best
    defence per silver), helmet Soldier or Mistwalker (Soldier = more
    health), Feyscale Sandals 4.4 (cheapest optimal, no real alternative;
    4.3 fine).
```

---

## 9. House rules (how this stays trustworthy)

- **No score without a cited spell.** The evidence lint fails the build on
  any capability score that can't point at an equippable spell.
- **The game files are the authority** on magnitudes, areas, and escalation
  — patch data beats wiki notes beats memory.
- **Every expert ruling becomes a pinned test** (the golden suite, 26 cases)
  so later changes can't silently undo it.
- **Browser and Python engines are bit-identical** (parity gate, 60 cases at
  1e-9) — what the dashboard shows is what the engine computed.
- **Fail closed.** Broken provenance, lint errors, or a bad edit in this
  file stop the build; they never ship quietly.
