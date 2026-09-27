# Fold report 2026-09-27 - working tree vs `HEAD`

## Corpus (the battle-list population the derive steps read)

| unit | before | after |
|---|---|---|
| battles | 20718 | 21815 |
| battles in the file, every source | 20718 | 40960 |
| killer parties | 57339 | 60178 |
| observed builds | 414363 | 434266 |
| builds with a full kit | 400610 | 419860 |
| median gear coverage | 0.744 | 0.736 |
| Dragon Portal killer parties (kill-feed, not yet read) | 0 | 1176 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 14131 -> 14809; labels {'brawl': 3735, 'brawl_clap': 202, 'clap': 6007, 'clap_kite': 1762, 'forming': 1, 'kite': 1279, 'split': 1145} -> {'brawl': 3919, 'brawl_clap': 213, 'clap': 6314, 'clap_kite': 1835, 'forming': 1, 'kite': 1316, 'split': 1211}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 5459 | 5753 | ok |
| balanced|15-19 | 6730 | 7030 | ok |
| balanced|20 | 1390 | 1447 | ok |
| brawl_clap|10-14 | 82 | 89 | ok |
| brawl_clap|15-19 | 93 | 97 | ok |
| brawl_clap|20 | 20 | 20 | UNDER FLOOR (borrows) |
| brawl|10-14 | 1721 | 1803 | ok |
| brawl|15-19 | 1632 | 1717 | ok |
| brawl|20 | 293 | 304 | ok |
| clap_kite|10-14 | 270 | 278 | ok |
| clap_kite|15-19 | 1046 | 1093 | ok |
| clap_kite|20 | 315 | 330 | ok |
| clap|10-14 | 2277 | 2416 | ok |
| clap|15-19 | 2977 | 3106 | ok |
| clap|20 | 524 | 549 | ok |
| kite|10-14 | 649 | 679 | ok |
| kite|15-19 | 451 | 456 | ok |
| kite|20 | 128 | 130 | ok |

## Style-band rows (target / soft cap)

1027 rows compared, 450 moved; median |relative move| 0.000, p90 0.034

| row | before | after |
|---|---|---|
| brawl_clap/10-14/requirements/ranged_presence/target | 2.0 | 1.0 |
| brawl_clap/10-14/requirements/heal_burst/soft_cap | 14.65 | 18.1 |
| brawl_clap/15-19/requirements/heal_burst/soft_cap | 16.9 | 20.45 |
| brawl_clap/20/requirements/heal_burst/soft_cap | 16.9 | 20.45 |
| brawl_clap/10-14/requirements/silence/soft_cap | 18.78 | 22.23 |
| brawl_clap/10-14/requirements/heal_burst/target | 7.45 | 8.7 |
| balanced/10-14/requirements/silence/target | 2.9 | 2.42 |
| clap/15-19/requirements/cleanse/soft_cap | 9.89 | 11.5 |
| clap_kite/20/requirements/damage_debuff/soft_cap | 4.02 | 4.66 |
| brawl_clap/15-19/requirements/heal_sustain/soft_cap | 21.3 | 24.6 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 18 -> 20, 25 slots changed

- 13 own evidence 10-29 votes, e.g. 2H_BOW:armor ARMOR_CLOTH_SET2(20)->ARMOR_LEATHER_SET1(16), 2H_CLAYMORE:head HEAD_PLATE_SET3(10)->HEAD_LEATHER_MORGANA(15)
- 5 own evidence 30+ votes (meta shift or noise), e.g. 2H_BOW_KEEPER:shoes SHOES_PLATE_SET1(50)->SHOES_LEATHER_MORGANA(68), 2H_HALBERD_MORGANA:armor ARMOR_LEATHER_HELL(37)->ARMOR_PLATE_ROYAL(33)
- 5 own evidence under 10 votes, e.g. 2H_DAGGERPAIR_CRYSTAL:armor ARMOR_LEATHER_HELL(8)->ARMOR_LEATHER_SET3(7), 2H_DAGGERPAIR_CRYSTAL:cape CAPEITEM_SMUGGLER(5)->CAPEITEM_UNDEAD(5)
- 2 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_LYMHURST(0)->CAPEITEM_FW_CAERLEON(0), MAIN_NATURESTAFF_AVALON:head HEAD_CLOTH_KEEPER(0)->HEAD_LEATHER_SET3(1)

**20|clap** - pooled slots 18 -> 20, 32 slots changed

- 14 own evidence 10-29 votes, e.g. 2H_BOW:head HEAD_PLATE_SET3(11)->HEAD_LEATHER_SET2(7), 2H_BOW:armor ARMOR_CLOTH_SET2(10)->ARMOR_LEATHER_SET1(8)
- 14 own evidence under 10 votes, e.g. 2H_CLAYMORE:head HEAD_PLATE_SET3(5)->HEAD_LEATHER_MORGANA(15), 2H_DAGGERPAIR_CRYSTAL:armor ARMOR_LEATHER_HELL(8)->ARMOR_LEATHER_SET3(7)
- 2 own evidence 30+ votes (meta shift or noise), e.g. 2H_BOW_KEEPER:armor ARMOR_LEATHER_SET3(43)->ARMOR_LEATHER_ROYAL(47), 2H_FROSTSTAFF:head HEAD_CLOTH_SET2(200)->HEAD_PLATE_SET1(159)
- 2 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_LYMHURST(0)->CAPEITEM_FW_CAERLEON(0), MAIN_NATURESTAFF_AVALON:head HEAD_CLOTH_KEEPER(0)->HEAD_LEATHER_SET3(1)

**7|balanced** - pooled slots 7 -> 8, 29 slots changed

- 14 own evidence 10-29 votes, e.g. 2H_BOW_CRYSTAL:cape CAPEITEM_SMUGGLER(11)->CAPEITEM_FW_THETFORD(9), 2H_COMBATSTAFF_MORGANA:head HEAD_LEATHER_SET3(17)->HEAD_LEATHER_HELL(9)
- 11 own evidence 30+ votes (meta shift or noise), e.g. 2H_CLEAVER_HELL:head HEAD_PLATE_SET1(103)->HEAD_PLATE_AVALON(88), 2H_CROSSBOW:head HEAD_LEATHER_ROYAL(74)->HEAD_LEATHER_SET3(63)
- 4 own evidence under 10 votes, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_CAERLEON(7)->CAPEITEM_FW_THETFORD(7), 2H_TRIDENT_UNDEAD:head HEAD_LEATHER_SET3(7)->HEAD_LEATHER_SET2(9)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 2 - MAIN_HOLYSTAFF_MORGANA, MAIN_SWORD
- still under: 14; gained two or fewer voters: 14 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_CURSEDSTAFF, 2H_SHAPESHIFTER_SET1, MAIN_FROSTSTAFF_AVALON, 2H_KNUCKLES_CRYSTAL, 2H_BOW_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL, 2H_DAGGERPAIR_CRYSTAL, MAIN_NATURESTAFF_KEEPER, 2H_SHAPESHIFTER_MORGANA, MAIN_FIRESTAFF_CRYSTAL...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 101 | 101 | - | - |
| mid | 76 | 77 | 2H_SCYTHE_HELL | - |
| large | 47 | 47 | - | - |

