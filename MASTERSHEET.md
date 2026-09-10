# MASTERSHEET — the expert's control panel

The yaml blocks below marked `tune:` are read at build time and **override**
the underlying config files — `templates/scoring.yaml`, `templates/mechanics.yaml`,
the content templates and the weapon sheets. Edit a value here, rebuild, and
both engines follow:

```
py -3 pipeline/build_dataset.py
py -3 dashboard/build.py
py -3 tests/test_golden.py && py -3 tests/test_js_parity.py
```

The build **fails loudly** on any mistake here — an unknown weapon, a
capability the weapon doesn't have, a typo'd section — never silently
ignores an edit. Whatever is set here wins, so this file is the single answer
to "what is the engine actually using?" beyond the files themselves. It
carries only rulings in force: each one cites the owner's words and the test
that pins it; the history behind them is the `tests/VALIDATION.md` index.
Sections: `scoring`, `mechanics`, `templates`, `sheets`, `guild_builds`
(`pipeline/mastersheet.py`).

## Per-weapon score overrides — `tune:sheets`

Re-rank a capability a weapon already has, or remove it (score 0). A NEW
capability needs a sheet row with spell evidence — the no-score-without-proof
rule stays intact. Keys are game unique names (`pipeline/sheets/*.yaml`).

```yaml tune:sheets
# Expert ruling 2026-08-20 (pinned by golden T19): Bedrock Mace is THE
# anti-dive pick at scale — Primal Slam's 18m CC-resist-ignoring throw
# leaves a PERSISTENT WALL (an extra peel layer, fire-and-forget), on a
# support-tank kit with Guard Rune; guild runs it double-CORE. Iron-clad's
# whirlwind must physically contact the diver while channeling — in large
# fights nobody uses it for this. The raw numbers alone (18m vs 12m) hid
# the delivery nuance; this is rubric Q2 reliability + Q8 kit fit.
MAIN_ROCKMACE_KEEPER:          # Bedrock Mace  (1-7 scale)
  anti_dive: 6
2H_IRONCLADEDSTAFF:            # Iron-clad Staff
  anti_dive: 2

# Expert ruling 2026-08-24 (round 7 E-audit follow-up): "fist of ava purge
# can be a 4." Purifying Fist strips ALL buffs from ALL enemies hit inside
# a 232-damage area punch — the true-purge benchmark delivered as a dive
# bomb, above the sheet's 3.
2H_KNUCKLES_AVALON:            # Fists of Avalon
  purge: 4

# Owner ruling 2026-09-08 ("sure on 3 ... you r hoarfrost ruling"): the
# 2026-08-20 rescore HELD Avalanche's burst at 2 because +0.5 unit tipped
# the blap tank slot in the V4 blind test (69% vs the 70% gate). Re-measured
# 2026-09-08 with the structure that landed since (need profiles, frontline
# floors, the dressed forge): V4 is byte-identical at 2 and at 3 (17/23
# actual_gear, 19/23 weapon_only), so the hold was a symptom of missing
# team structure, not a wrong rating. The evidence stands on its own:
# Avalanche measures 280/cast, top-20% of the burst_aoe board. Pinned by
# golden T44.
MAIN_FROSTSTAFF_KEEPER:        # Hoarfrost Staff
  burst_aoe: 3

# 2H_TWINSCYTHE_HELL:          # Soulscythe
#   knockback_displace: 4      # the line knockup is undervalued at 2
# 2H_DOUBLEBLADEDSTAFF:
#   catch: 2                   # gank kit, not ZvZ catch — down from 4
```

## Scoring dials — `tune:scoring`

Empty: the engine runs on `templates/scoring.yaml` as committed (alpha 0.55 /
beta 0.20 / delta 0.15 / gamma 0.70, rho, headroom, the synergy pairs). To
override, uncomment and edit — dicts merge, scalars replace. `meta_prior` is
GENERATED (`derive_meta_prior.py`); a hand-set map here fails the build.

```yaml tune:scoring
# weights:
#   gamma: 0.65         # concavity: how fast a filled need stops paying
# capability_synergies:
#   - {a: clump_create, b: burst_aoe, bonus: 1.5}
```

## Fight physics — `tune:mechanics`

Empty: `templates/mechanics.yaml` as committed (Focus Fire / Resilience and
AoE Escalation tables owner-verified 2026-08-25; `aoe_geometry` with
`reference_clump: 2` — raise it and AoE utility weakens everywhere).

```yaml tune:mechanics
# aoe_geometry:
#   reference_clump: 3
```

## Per-content demand — `tune:templates`

Empty. Fields per capability: `target`, `weight`, `soft_cap`, `scales`.
Contents: `blackzone_roam`, `castle`, `castle_outpost`, `faction_war`,
`roads`, `territory_defense`. Style x size rows are GENERATED
(`templates/style_bands.yaml`) and are not overridden here.

```yaml tune:templates
# castle:
#   catch: {weight: 5, target: 3.5}
```

## What this file does NOT control

The forge's structure lives beside the role book, every entry cited, with the
same fail-loud promise:

| Dial | Where |
| --- | --- |
| Role book: seats, functions, memberships | `pipeline/roles.yaml` `roles:` |
| Kit-pool and gear-affinity rulings | `pipeline/roles.yaml` `kit_doctrine.overrides`, `gear_affinity_overrides` |
| Need profiles | `pipeline/roles.yaml` `need_profiles` |
| Style role bands, healer minima | `pipeline/templates/styles.yaml` `constraint_overrides`, `role_min_per_players` |
| Viability exclusions, duplicate allowances | `pipeline/templates/composition.yaml` |
| Style-fit rulings per weapon | `pipeline/style_overrides.yaml` |
| Style x size rows, meta prior | GENERATED from the harvest — never hand-set |

## Guild-approved builds — `tune:guild_builds`

The guild announcement of 2026-08-20, in the guild's own words. Ships into
the dataset verbatim as a guideline layer for display and validation — never
a rule the scorer enforces.

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
