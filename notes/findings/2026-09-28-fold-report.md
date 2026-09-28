# Fold report 2026-09-28 - working tree vs `HEAD`

## Corpus (the battle-list population the derive steps read)

| unit | before | after |
|---|---|---|
| battles | 23603 | 23603 |
| battles in the file, every source | 83648 | 92789 |
| killer parties | 63931 | 63855 |
| observed builds | 458344 | 457460 |
| builds with a full kit | 443088 | 442250 |
| median gear coverage | 0.727 | 0.727 |
| Dragon Portal killer parties (kill-feed, not yet read) | 5348 | 6552 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 14809 -> 15589; labels {'brawl': 3919, 'brawl_clap': 213, 'clap': 6314, 'clap_kite': 1835, 'forming': 1, 'kite': 1316, 'split': 1211} -> {'brawl': 4148, 'brawl_clap': 218, 'clap': 6652, 'clap_kite': 1908, 'forming': 1, 'kite': 1383, 'split': 1279}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 5753 | 6113 | ok |
| balanced|15-19 | 7030 | 7367 | ok |
| balanced|20 | 1447 | 1508 | ok |
| brawl_clap|10-14 | 89 | 91 | ok |
| brawl_clap|15-19 | 97 | 100 | ok |
| brawl_clap|20 | 20 | 20 | UNDER FLOOR (borrows) |
| brawl|10-14 | 1803 | 1935 | ok |
| brawl|15-19 | 1717 | 1797 | ok |
| brawl|20 | 304 | 315 | ok |
| clap_kite|10-14 | 278 | 287 | ok |
| clap_kite|15-19 | 1093 | 1145 | ok |
| clap_kite|20 | 330 | 340 | ok |
| clap|10-14 | 2416 | 2558 | ok |
| clap|15-19 | 3106 | 3264 | ok |
| clap|20 | 549 | 575 | ok |
| kite|10-14 | 679 | 721 | ok |
| kite|15-19 | 456 | 471 | ok |
| kite|20 | 130 | 140 | ok |

## Style-band rows (target / soft cap)

1027 rows compared, 397 moved; median |relative move| 0.000, p90 0.028

| row | before | after |
|---|---|---|
| clap_kite/10-14/requirements/damage_debuff/soft_cap | 2.88 | 5.17 |
| clap_kite/15-19/requirements/damage_debuff/soft_cap | 3.91 | 5.75 |
| clap_kite/10-14/requirements/max_health_cut/soft_cap | 2.3 | 1.61 |
| kite/15-19/requirements/clump_create/target | 2.0 | 2.5 |
| clap_kite/20/requirements/damage_debuff/soft_cap | 4.66 | 5.75 |
| brawl_clap/10-14/requirements/heal_burst/soft_cap | 18.1 | 14.65 |
| brawl_clap/15-19/requirements/heal_burst/soft_cap | 20.45 | 16.65 |
| brawl_clap/20/requirements/heal_burst/soft_cap | 20.45 | 16.65 |
| brawl_clap/15-19/requirements/purge/target | 6.0 | 5.0 |
| brawl_clap/20/requirements/purge/target | 6.0 | 5.0 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 20 -> 19, 11 slots changed

- 4 own evidence 10-29 votes, e.g. 2H_INFERNOSTAFF:shoes SHOES_LEATHER_MORGANA(21)->SHOES_CLOTH_ROYAL(21), 2H_KNUCKLES_AVALON:head HEAD_PLATE_SET1(21)->HEAD_LEATHER_SET3(31)
- 3 own evidence under 10 votes, e.g. 2H_DEMONICSTAFF:food T7_MEAL_OMELETTE(9)->T8_MEAL_STEW(10), 2H_HAMMER_UNDEAD:head HEAD_PLATE_SET1(8)->HEAD_PLATE_SET3(10)
- 2 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_CAERLEON(0)->CAPEITEM_FW_LYMHURST(0), MAIN_NATURESTAFF_AVALON:head HEAD_LEATHER_SET3(1)->HEAD_CLOTH_KEEPER(0)
- 2 own evidence 30+ votes (meta shift or noise), e.g. MAIN_HAMMER:armor ARMOR_PLATE_SET3(184)->ARMOR_PLATE_FEY(183), MAIN_MACE:offhand OFF_SHIELD_AVALON(252)->OFF_JESTERCANE_HELL(475)

**20|clap** - pooled slots 20 -> 19, 22 slots changed

- 8 own evidence under 10 votes, e.g. 2H_BOW:armor ARMOR_LEATHER_SET1(8)->ARMOR_LEATHER_SET2(9), 2H_DIVINESTAFF:shoes SHOES_LEATHER_SET1(5)->SHOES_CLOTH_SET1(6)
- 7 own evidence 10-29 votes, e.g. 2H_INFERNOSTAFF:shoes SHOES_LEATHER_MORGANA(21)->SHOES_CLOTH_ROYAL(21), 2H_SCYTHE_HELL:shoes SHOES_LEATHER_MORGANA(15)->SHOES_PLATE_AVALON(12)
- 5 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANESTAFF:shoes SHOES_LEATHER_ROYAL(143)->SHOES_LEATHER_MORGANA(143), 2H_BOW_KEEPER:head HEAD_PLATE_ROYAL(40)->HEAD_LEATHER_SET3(69)
- 2 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_CAERLEON(0)->CAPEITEM_FW_LYMHURST(0), MAIN_NATURESTAFF_AVALON:head HEAD_LEATHER_SET3(1)->HEAD_CLOTH_KEEPER(0)

**7|balanced** - pooled slots 8 -> 8, 24 slots changed

- 11 own evidence 30+ votes (meta shift or noise), e.g. 2H_CLEAVER_HELL:head HEAD_PLATE_AVALON(88)->HEAD_LEATHER_MORGANA(98), 2H_DOUBLEBLADEDSTAFF:food T8_MEAL_STEW(37)->T7_MEAL_OMELETTE(27)
- 8 own evidence 10-29 votes, e.g. 2H_BOW_CRYSTAL:potion T7_POTION_REVIVE(19)->T6_POTION_HEAL(10), 2H_DAGGERPAIR_CRYSTAL:cape CAPEITEM_AVALON(13)->CAPEITEM_UNDEAD(13)
- 5 own evidence under 10 votes, e.g. 2H_BOW_CRYSTAL:cape CAPEITEM_FW_THETFORD(9)->CAPEITEM_SMUGGLER(9), 2H_CURSEDSTAFF:cape CAPEITEM_FW_THETFORD(7)->CAPEITEM_FW_CAERLEON(7)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 0 - none
- still under: 14; gained two or fewer voters: 14 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_CURSEDSTAFF, 2H_SHAPESHIFTER_SET1, MAIN_FROSTSTAFF_AVALON, 2H_KNUCKLES_CRYSTAL, 2H_BOW_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL, MAIN_NATURESTAFF_KEEPER, 2H_SHAPESHIFTER_MORGANA, 2H_DAGGERPAIR_CRYSTAL, MAIN_FIRESTAFF_CRYSTAL...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 101 | 101 | - | - |
| mid | 77 | 79 | 2H_HALBERD, 2H_NATURESTAFF | - |
| large | 47 | 47 | - | - |

