# Fold report 2026-09-16 - working tree vs `HEAD`

## Corpus

| unit | before | after |
|---|---|---|
| battles | 12824 | 13978 |
| killer parties | 34376 | 36907 |
| observed builds | 251360 | 268761 |
| builds with a full kit | 243043 | 259824 |
| median gear coverage | 0.733 | 0.731 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 5679 -> 8587; labels {'brawl': 1610, 'brawl_clap': 88, 'clap': 2337, 'clap_kite': 678, 'forming': 1, 'kite': 533, 'split': 432} -> {'brawl': 2419, 'brawl_clap': 131, 'clap': 3507, 'clap_kite': 1016, 'forming': 1, 'kite': 794, 'split': 719}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 2092 | 3267 | ok |
| balanced|15-19 | 2668 | 4069 | ok |
| balanced|20 | 592 | 878 | ok |
| brawl_clap|10-14 | 28 | 46 | ok |
| brawl_clap|15-19 | 36 | 65 | ok |
| brawl_clap|20 | 15 | 16 | UNDER FLOOR (borrows) |
| brawl|10-14 | 710 | 1070 | ok |
| brawl|15-19 | 707 | 1091 | ok |
| brawl|20 | 130 | 191 | ok |
| clap_kite|10-14 | 94 | 150 | ok |
| clap_kite|15-19 | 383 | 580 | ok |
| clap_kite|20 | 141 | 201 | ok |
| clap|10-14 | 820 | 1315 | ok |
| clap|15-19 | 1154 | 1711 | ok |
| clap|20 | 221 | 327 | ok |
| kite|10-14 | 273 | 412 | ok |
| kite|15-19 | 192 | 282 | ok |
| kite|20 | 41 | 69 | ok |

## Style-band rows (target / soft cap)

1022 rows compared, 621 moved; median |relative move| 0.010, p90 0.167

| row | before | after |
|---|---|---|
| brawl_clap/15-19/requirements/damage_debuff/target | 5.0 | 15.0 |
| brawl_clap/20/requirements/damage_debuff/target | 5.0 | 15.0 |
| brawl_clap/10-14/requirements/damage_debuff/soft_cap | 6.9 | 16.1 |
| kite/15-19/requirements/damage_debuff/target | 1.0 | 2.25 |
| kite/15-19/requirements/max_health_cut/soft_cap | 1.15 | 2.3 |
| brawl_clap/10-14/requirements/damage_debuff/target | 2.5 | 5.0 |
| brawl_clap/15-19/requirements/damage_debuff/soft_cap | 11.5 | 23.0 |
| clap_kite/20/requirements/max_health_cut/soft_cap | 1.15 | 2.3 |
| brawl_clap/10-14/requirements/burst_st/soft_cap | 26.68 | 3.27 |
| brawl_clap/15-19/requirements/burst_st/soft_cap | 17.28 | 2.56 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 73 -> 30, 86 slots changed

- 23 own evidence under 10 votes, e.g. 2H_BOW:armor ARMOR_LEATHER_SET1(8)->ARMOR_CLOTH_SET2(16), 2H_DEMONICSTAFF:food T8_MEAL_STEW(5)->T7_MEAL_OMELETTE_AVALON(7)
- 21 was pooled (thin) -> own evidence, e.g. 2H_BOW_CRYSTAL:potion T7_POTION_REVIVE(2)->T6_POTION_HEAL(5), 2H_DAGGERPAIR_CRYSTAL:shoes SHOES_LEATHER_MORGANA(2)->SHOES_CLOTH_ROYAL(4)
- 19 own evidence 10-29 votes, e.g. 2H_BOW_KEEPER:shoes SHOES_LEATHER_MORGANA(28)->SHOES_PLATE_SET1(38), 2H_CROSSBOWLARGE:cape CAPEITEM_FW_LYMHURST(12)->CAPEITEM_SMUGGLER(15)
- 18 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANESTAFF:shoes SHOES_LEATHER_MORGANA(110)->SHOES_LEATHER_ROYAL(182), 2H_ARCANESTAFF_CRYSTAL:cape CAPEITEM_FW_LYMHURST(59)->CAPEITEM_SMUGGLER(63)
- 5 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_CAERLEON(0)->CAPEITEM_FW_LYMHURST(0), 2H_KNUCKLES_CRYSTAL:shoes SHOES_PLATE_SET1(0)->SHOES_LEATHER_MORGANA(3)

**20|clap** - pooled slots 73 -> 30, 103 slots changed

- 43 own evidence under 10 votes, e.g. 2H_BOW:cape CAPEITEM_FW_THETFORD(7)->CAPEITEM_FW_LYMHURST(6), 2H_CLAWPAIR:potion T7_POTION_REVIVE(6)->T8_POTION_COOLDOWN(11)
- 25 own evidence 10-29 votes, e.g. 2H_ARCANESTAFF_CRYSTAL:cape CAPEITEM_FW_LYMHURST(17)->CAPEITEM_SMUGGLER(31), 2H_ARCANE_RINGPAIR_AVALON:food T7_MEAL_OMELETTE_AVALON(18)->T7_MEAL_OMELETTE(6)
- 21 was pooled (thin) -> own evidence, e.g. 2H_BOW_CRYSTAL:potion T7_POTION_REVIVE(2)->T6_POTION_HEAL(5), 2H_DAGGERPAIR_CRYSTAL:shoes SHOES_LEATHER_MORGANA(2)->SHOES_CLOTH_ROYAL(4)
- 9 own evidence 30+ votes (meta shift or noise), e.g. 2H_CROSSBOW_CANNON_AVALON:cape CAPEITEM_MORGANA(51)->CAPEITEM_SMUGGLER(76), 2H_CROSSBOW_CANNON_AVALON:head HEAD_LEATHER_FEY(52)->HEAD_LEATHER_SET3(129)
- 5 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_CAERLEON(0)->CAPEITEM_FW_LYMHURST(0), 2H_KNUCKLES_CRYSTAL:shoes SHOES_PLATE_SET1(0)->SHOES_LEATHER_MORGANA(3)

**7|balanced** - pooled slots 41 -> 12, 91 slots changed

- 31 own evidence 10-29 votes, e.g. 2H_ARCANESTAFF:food T7_MEAL_OMELETTE(26)->T7_MEAL_OMELETTE_AVALON(35), 2H_CLAYMORE:cape CAPEITEM_FW_CAERLEON(12)->CAPEITEM_FW_THETFORD(22)
- 22 own evidence 30+ votes (meta shift or noise), e.g. 2H_BOW_KEEPER:cape CAPEITEM_FW_LYMHURST(116)->CAPEITEM_UNDEAD(115), 2H_CLEAVER_HELL:head HEAD_LEATHER_MORGANA(53)->HEAD_PLATE_AVALON(79)
- 21 own evidence under 10 votes, e.g. 2H_CROSSBOWLARGE_MORGANA:shoes SHOES_LEATHER_MORGANA(8)->SHOES_CLOTH_ROYAL(21), 2H_DAGGERPAIR_CRYSTAL:cape CAPEITEM_UNDEAD(6)->CAPEITEM_AVALON(9)
- 16 was pooled (thin) -> own evidence, e.g. 2H_BOW_CRYSTAL:shoes SHOES_LEATHER_AVALON(0)->SHOES_CLOTH_AVALON(5), 2H_COMBATSTAFF_MORGANA:food T8_MEAL_STEW(3)->T7_MEAL_OMELETTE_AVALON(6)
- 1 pooled -> pooled, e.g. 2H_SHAPESHIFTER_CRYSTAL:food T8_MEAL_SANDWICH_AVALON(0)->T7_MEAL_OMELETTE(3)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 3 - 2H_DIVINESTAFF, 2H_FROSTSTAFF_CRYSTAL, 2H_GLAIVE
- still under: 23; gained two or fewer voters: 20 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_CURSEDSTAFF, MAIN_FROSTSTAFF_AVALON, 2H_BOW_CRYSTAL, 2H_SHAPESHIFTER_SET1, 2H_TRIDENT_UNDEAD, 2H_DAGGERPAIR_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL, 2H_SPEAR, MAIN_NATURESTAFF_KEEPER, 2H_REPEATINGCROSSBOW_UNDEAD...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 94 | 100 | 2H_BOW_CRYSTAL, 2H_ROCKSTAFF_KEEPER, 2H_SPEAR, MAIN_ARCANESTAFF, MAIN_DAGGER_HELL, MAIN_SWORD | - |
| mid | 71 | 74 | 2H_DUALHAMMER_HELL, 2H_ENIGMATICSTAFF, 2H_INFERNOSTAFF | - |
| large | 43 | 44 | 2H_BOW_HELL | - |

