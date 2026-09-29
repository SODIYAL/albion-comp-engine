# Fold report 2026-09-28 - working tree vs `HEAD`

## Corpus (the battle-list population the derive steps read)

| unit | before | after |
|---|---|---|
| battles | 23603 | 24365 |
| battles in the file, every source | 92789 | 120335 |
| killer parties | 63855 | 65252 |
| observed builds | 457460 | 465779 |
| builds with a full kit | 442250 | 450241 |
| median gear coverage | 0.727 | 0.726 |
| Dragon Portal killer parties (kill-feed, not yet read) | 6552 | 9444 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 15589 -> 15845; labels {'brawl': 4148, 'brawl_clap': 218, 'clap': 6652, 'clap_kite': 1908, 'forming': 1, 'kite': 1383, 'split': 1279} -> {'brawl': 4220, 'brawl_clap': 223, 'clap': 6753, 'clap_kite': 1942, 'forming': 1, 'kite': 1406, 'split': 1300}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 6113 | 6214 | ok |
| balanced|15-19 | 7367 | 7482 | ok |
| balanced|20 | 1508 | 1539 | ok |
| brawl_clap|10-14 | 91 | 93 | ok |
| brawl_clap|15-19 | 100 | 101 | ok |
| brawl_clap|20 | 20 | 22 | UNDER FLOOR (borrows) |
| brawl|10-14 | 1935 | 1968 | ok |
| brawl|15-19 | 1797 | 1826 | ok |
| brawl|20 | 315 | 323 | ok |
| clap_kite|10-14 | 287 | 289 | ok |
| clap_kite|15-19 | 1145 | 1171 | ok |
| clap_kite|20 | 340 | 346 | ok |
| clap|10-14 | 2558 | 2599 | ok |
| clap|15-19 | 3264 | 3308 | ok |
| clap|20 | 575 | 587 | ok |
| kite|10-14 | 721 | 734 | ok |
| kite|15-19 | 471 | 478 | ok |
| kite|20 | 140 | 141 | ok |

## Style-band rows (target / soft cap)

1029 rows compared, 308 moved; median |relative move| 0.000, p90 0.006

| row | before | after |
|---|---|---|
| clap/10-14/requirements/anti_zone/soft_cap | 2.3 | 0.46 |
| kite/10-14/requirements/damage_debuff/soft_cap | 6.9 | 5.75 |
| kite/10-14/requirements/silence/target | 2.9 | 2.42 |
| kite/10-14/requirements/clump_create/soft_cap | 3.45 | 4.02 |
| clap_kite/10-14/requirements/max_health_cut/soft_cap | 1.61 | 1.38 |
| brawl/10-14/requirements/purge/target | 3.5 | 4.0 |
| clap_kite/20/requirements/burst_st/soft_cap | 2.71 | 2.96 |
| kite/15-19/requirements/damage_debuff/soft_cap | 6.9 | 6.32 |
| brawl/15-19/requirements/cleanse/soft_cap | 6.9 | 7.47 |
| kite/20/requirements/silence/soft_cap | 22.06 | 20.39 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 19 -> 19, 5 slots changed

- 2 own evidence 30+ votes (meta shift or noise), e.g. MAIN_CURSEDSTAFF:offhand OFF_DEMONSKULL_HELL(64)->OFF_LAMP_UNDEAD(52), MAIN_HAMMER:armor ARMOR_PLATE_FEY(183)->ARMOR_PLATE_SET3(196)
- 1 own evidence 10-29 votes, e.g. 2H_SHAPESHIFTER_CRYSTAL:armor ARMOR_PLATE_SET2(16)->ARMOR_PLATE_SET3(15)
- 1 own evidence under 10 votes, e.g. MAIN_NATURESTAFF_AVALON:armor ARMOR_CLOTH_ROYAL(1)->ARMOR_CLOTH_SET2(2)
- 1 pooled -> pooled, e.g. MAIN_NATURESTAFF_AVALON:head HEAD_CLOTH_KEEPER(0)->HEAD_PLATE_SET3(2)

**20|clap** - pooled slots 19 -> 19, 8 slots changed

- 3 own evidence 30+ votes (meta shift or noise), e.g. 2H_SCYTHE_CRYSTAL:cape CAPEITEM_FW_MARTLOCK(37)->CAPEITEM_FW_LYMHURST(5), 2H_SHAPESHIFTER_KEEPER:shoes SHOES_CLOTH_SET2(115)->SHOES_LEATHER_SET2(176)
- 2 own evidence 10-29 votes, e.g. 2H_DUALHAMMER_HELL:cape CAPEITEM_FW_LYMHURST(11)->CAPEITEM_FW_CAERLEON(11), 2H_HAMMER_UNDEAD:cape CAPEITEM_FW_LYMHURST(12)->CAPEITEM_SMUGGLER(12)
- 2 own evidence under 10 votes, e.g. 2H_HALBERD:head HEAD_LEATHER_MORGANA(5)->HEAD_PLATE_SET1(7), MAIN_NATURESTAFF_AVALON:armor ARMOR_CLOTH_ROYAL(1)->ARMOR_CLOTH_SET2(2)
- 1 pooled -> pooled, e.g. MAIN_NATURESTAFF_AVALON:head HEAD_CLOTH_KEEPER(0)->HEAD_PLATE_SET3(2)

**7|balanced** - pooled slots 8 -> 8, 11 slots changed

- 6 own evidence 10-29 votes, e.g. 2H_DEMONICSTAFF:cape CAPEITEM_SMUGGLER(14)->CAPEITEM_FW_LYMHURST(15), 2H_GLAIVE:potion T7_POTION_STONESKIN(17)->T7_POTION_REVIVE(17)
- 3 own evidence 30+ votes (meta shift or noise), e.g. 2H_ROCKSTAFF_KEEPER:potion T7_POTION_SLOWFIELD(39)->T8_POTION_CLEANSE(20), MAIN_CURSEDSTAFF_UNDEAD:food T8_MEAL_STEW(130)->T7_MEAL_OMELETTE(126)
- 2 own evidence under 10 votes, e.g. 2H_TRIDENT_UNDEAD:armor ARMOR_LEATHER_HELL(5)->ARMOR_CLOTH_SET2(10), MAIN_SWORD:cape CAPEITEM_FW_THETFORD(9)->CAPEITEM_SMUGGLER(9)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 1 - 2H_SPEAR
- still under: 13; gained two or fewer voters: 13 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_CURSEDSTAFF, 2H_SHAPESHIFTER_SET1, MAIN_FROSTSTAFF_AVALON, 2H_KNUCKLES_CRYSTAL, 2H_BOW_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL, MAIN_NATURESTAFF_KEEPER, 2H_SHAPESHIFTER_MORGANA, 2H_DAGGERPAIR_CRYSTAL, MAIN_FIRESTAFF_CRYSTAL...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 101 | 101 | - | - |
| mid | 79 | 80 | 2H_WILDSTAFF | - |
| large | 47 | 47 | - | - |

