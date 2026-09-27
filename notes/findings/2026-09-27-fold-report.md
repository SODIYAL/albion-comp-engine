# Fold report 2026-09-27 - working tree vs `HEAD`

## Corpus

| unit | before | after |
|---|---|---|
| battles | 20718 | 20718 |
| killer parties | 57339 | 57339 |
| observed builds | 414363 | 414363 |
| builds with a full kit | 400610 | 400610 |
| median gear coverage | 0.744 | 0.744 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 8587 -> 14131; labels {'brawl': 2419, 'brawl_clap': 131, 'clap': 3507, 'clap_kite': 1016, 'forming': 1, 'kite': 794, 'split': 719} -> {'brawl': 3735, 'brawl_clap': 202, 'clap': 6007, 'clap_kite': 1762, 'forming': 1, 'kite': 1279, 'split': 1145}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 3267 | 5459 | ok |
| balanced|15-19 | 4069 | 6730 | ok |
| balanced|20 | 878 | 1390 | ok |
| brawl_clap|10-14 | 46 | 82 | ok |
| brawl_clap|15-19 | 65 | 93 | ok |
| brawl_clap|20 | 16 | 20 | UNDER FLOOR (borrows) |
| brawl|10-14 | 1070 | 1721 | ok |
| brawl|15-19 | 1091 | 1632 | ok |
| brawl|20 | 191 | 293 | ok |
| clap_kite|10-14 | 150 | 270 | ok |
| clap_kite|15-19 | 580 | 1046 | ok |
| clap_kite|20 | 201 | 315 | ok |
| clap|10-14 | 1315 | 2277 | ok |
| clap|15-19 | 1711 | 2977 | ok |
| clap|20 | 327 | 524 | ok |
| kite|10-14 | 412 | 649 | ok |
| kite|15-19 | 282 | 451 | ok |
| kite|20 | 69 | 128 | ok |

## Style-band rows (target / soft cap)

1025 rows compared, 530 moved; median |relative move| 0.001, p90 0.050

| row | before | after |
|---|---|---|
| clap/20/requirements/execute/soft_cap | 1.79 | 4.05 |
| brawl_clap/10-14/requirements/heal_reduction/soft_cap | 3.45 | 5.75 |
| balanced/20/requirements/clump_create/target | 2.0 | 3.0 |
| clap/15-19/requirements/cleanse/target | 4.0 | 6.0 |
| kite/20/requirements/damage_debuff/target | 2.0 | 1.0 |
| brawl_clap/10-14/requirements/damage_debuff/target | 5.0 | 7.0 |
| balanced/15-19/requirements/cleanse/target | 4.0 | 5.5 |
| balanced/10-14/requirements/ranged_presence/target | 3.0 | 4.0 |
| brawl_clap/10-14/requirements/interrupt/soft_cap | 1.72 | 1.15 |
| clap_kite/20/requirements/max_health_cut/soft_cap | 2.3 | 2.99 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 30 -> 18, 47 slots changed

- 17 own evidence under 10 votes, e.g. 2H_BOW_CRYSTAL:potion T6_POTION_HEAL(5)->T7_POTION_REVIVE(10), 2H_DAGGERPAIR_CRYSTAL:shoes SHOES_CLOTH_ROYAL(4)->SHOES_LEATHER_MORGANA(5)
- 16 own evidence 10-29 votes, e.g. 2H_CLAYMORE:head HEAD_LEATHER_MORGANA(10)->HEAD_PLATE_SET3(10), 2H_DOUBLEBLADEDSTAFF:armor ARMOR_LEATHER_SET3(25)->ARMOR_PLATE_UNDEAD(40)
- 8 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANE_RINGPAIR_AVALON:shoes SHOES_LEATHER_MORGANA(31)->SHOES_LEATHER_ROYAL(40), 2H_AXE_AVALON:head HEAD_PLATE_SET1(380)->HEAD_PLATE_SET2(1049)
- 5 was pooled (thin) -> own evidence, e.g. 2H_CLAYMORE:cape CAPEITEM_FW_LYMHURST(2)->CAPEITEM_FW_CAERLEON(9), 2H_DUALCROSSBOW_CRYSTAL:head HEAD_LEATHER_SET3(3)->HEAD_PLATE_SET3(4)
- 1 pooled -> pooled, e.g. MAIN_NATURESTAFF_AVALON:head HEAD_LEATHER_SET3(2)->HEAD_CLOTH_KEEPER(0)

**20|clap** - pooled slots 30 -> 18, 63 slots changed

- 31 own evidence under 10 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:shoes SHOES_LEATHER_MORGANA(8)->SHOES_LEATHER_SET1(10), 2H_BOW:armor ARMOR_LEATHER_SET1(9)->ARMOR_CLOTH_SET2(10)
- 20 own evidence 10-29 votes, e.g. 2H_BOW_KEEPER:shoes SHOES_PLATE_SET1(15)->SHOES_LEATHER_MORGANA(56), 2H_CLAYMORE:head HEAD_LEATHER_MORGANA(10)->HEAD_PLATE_SET3(5)
- 6 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANESTAFF:shoes SHOES_LEATHER_MORGANA(88)->SHOES_LEATHER_ROYAL(155), 2H_AXE_AVALON:head HEAD_PLATE_SET1(244)->HEAD_PLATE_SET2(694)
- 5 was pooled (thin) -> own evidence, e.g. 2H_CLAYMORE:cape CAPEITEM_FW_LYMHURST(2)->CAPEITEM_FW_CAERLEON(9), 2H_DUALCROSSBOW_CRYSTAL:head HEAD_LEATHER_SET3(3)->HEAD_PLATE_SET3(4)
- 1 pooled -> pooled, e.g. MAIN_NATURESTAFF_AVALON:head HEAD_LEATHER_SET3(2)->HEAD_CLOTH_KEEPER(0)

**7|balanced** - pooled slots 12 -> 7, 59 slots changed

- 27 own evidence 30+ votes (meta shift or noise), e.g. 2H_BOW:shoes SHOES_LEATHER_ROYAL(35)->SHOES_LEATHER_SET1(67), 2H_CLEAVER_HELL:head HEAD_PLATE_AVALON(79)->HEAD_PLATE_SET1(103)
- 15 own evidence under 10 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:armor ARMOR_CLOTH_SET2(4)->ARMOR_PLATE_KEEPER(21), 2H_ARCANE_RINGPAIR_AVALON:shoes SHOES_LEATHER_SET1(7)->SHOES_LEATHER_MORGANA(14)
- 15 own evidence 10-29 votes, e.g. 2H_CROSSBOWLARGE:shoes SHOES_LEATHER_MORGANA(17)->SHOES_PLATE_SET1(21), 2H_CROSSBOWLARGE_MORGANA:shoes SHOES_CLOTH_ROYAL(21)->SHOES_LEATHER_FEY(20)
- 2 was pooled (thin) -> own evidence, e.g. 2H_ARCANE_RINGPAIR_AVALON:food T8_MEAL_STEW(4)->T7_MEAL_OMELETTE(12), 2H_TRIDENT_UNDEAD:shoes SHOES_CLOTH_ROYAL(3)->SHOES_LEATHER_SET2(5)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 0 - none
- still under: 16; gained two or fewer voters: 16 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_CURSEDSTAFF, MAIN_FROSTSTAFF_AVALON, 2H_SHAPESHIFTER_SET1, 2H_KNUCKLES_CRYSTAL, 2H_BOW_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL, 2H_DAGGERPAIR_CRYSTAL, MAIN_NATURESTAFF_KEEPER, 2H_SHAPESHIFTER_MORGANA, MAIN_FIRESTAFF_CRYSTAL...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 100 | 101 | 2H_ARCANESTAFF_HELL, 2H_GLACIALSTAFF | 2H_SHAPESHIFTER_SET3 |
| mid | 74 | 76 | 2H_DOUBLEBLADEDSTAFF, 2H_WARBOW | - |
| large | 44 | 47 | 2H_BOW_AVALON, 2H_FIRESTAFF_HELL, MAIN_MACE_HELL | - |

