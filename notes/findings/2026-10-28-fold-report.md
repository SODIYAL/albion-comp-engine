# Fold report 2026-10-28 - working tree vs `HEAD`

## Corpus (the battle-list population the derive steps read)

| unit | before | after |
|---|---|---|
| battles | 48630 | 66756 |
| battles in the build artifact (the battle list and the Dragon Portal) | 100542 | 137370 |
| killer parties | 126211 | 165891 |
| observed builds | 897180 | 1170601 |
| builds with a full kit | 867001 | 1129996 |
| median gear coverage | 0.727 | 0.727 |
| Dragon Portal killer parties (kill-feed, not yet read) | 63347 | 86699 |

Dragon Portal 15-20 pool: 115 -> 143 distinct dominant rosters; its fielded list and role counts wait for 200 (BACKLOG).

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 30021 -> 36617; labels {'brawl': 7816, 'brawl_clap': 350, 'clap': 12736, 'clap_kite': 3471, 'forming': 2, 'gank': 537, 'kite': 2539, 'split': 2570} -> {'brawl': 9374, 'brawl_clap': 385, 'clap': 15787, 'clap_kite': 4127, 'forming': 2, 'gank': 705, 'kite': 3181, 'split': 3056}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 11952 | 15136 | ok |
| balanced|15-19 | 14121 | 16741 | ok |
| balanced|20 | 2804 | 3287 | ok |
| brawl_clap|10-14 | 161 | 183 | ok |
| brawl_clap|15-19 | 149 | 159 | ok |
| brawl_clap|20 | 32 | 33 | UNDER FLOOR (borrows) |
| brawl|10-14 | 3675 | 4667 | ok |
| brawl|15-19 | 3389 | 3847 | ok |
| brawl|20 | 574 | 638 | ok |
| clap_kite|10-14 | 496 | 599 | ok |
| clap_kite|15-19 | 2052 | 2440 | ok |
| clap_kite|20 | 642 | 752 | ok |
| clap|10-14 | 4777 | 6031 | ok |
| clap|15-19 | 6405 | 7813 | ok |
| clap|20 | 1073 | 1322 | ok |
| kite|10-14 | 1276 | 1667 | ok |
| kite|15-19 | 884 | 1048 | ok |
| kite|20 | 278 | 325 | ok |

## Style-band rows (target / soft cap)

1025 rows compared, 447 moved; median |relative move| 0.000, p90 0.029

| row | before | after |
|---|---|---|
| brawl_clap/10-14/requirements/clump_create/target | 1.5 | 2.0 |
| brawl_clap/15-19/requirements/burst_st/soft_cap | 2.99 | 3.83 |
| brawl_clap/20/requirements/burst_st/soft_cap | 2.99 | 3.83 |
| kite/10-14/requirements/disengage/target | 4.0 | 3.0 |
| clap_kite/10-14/requirements/cleanse/soft_cap | 9.2 | 6.9 |
| brawl_clap/15-19/requirements/heal_reduction/soft_cap | 3.68 | 4.6 |
| brawl_clap/20/requirements/heal_reduction/soft_cap | 3.68 | 4.6 |
| brawl_clap/10-14/requirements/heal_reduction/soft_cap | 4.6 | 5.52 |
| balanced/15-19/requirements/clump_create/target | 3.0 | 3.5 |
| brawl_clap/10-14/requirements/damage_debuff/target | 6.0 | 5.0 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 22 -> 16, 42 slots changed

- 16 own evidence 30+ votes (meta shift or noise), e.g. 2H_DUALCROSSBOW_HELL:armor ARMOR_CLOTH_KEEPER(48)->ARMOR_CLOTH_SET2(51), 2H_FROSTSTAFF:head HEAD_PLATE_SET1(293)->HEAD_CLOTH_SET2(416)
- 13 own evidence 10-29 votes, e.g. 2H_DAGGERPAIR_CRYSTAL:armor ARMOR_LEATHER_SET3(14)->ARMOR_LEATHER_HELL(19), 2H_DAGGERPAIR_CRYSTAL:shoes SHOES_CLOTH_ROYAL(11)->SHOES_LEATHER_MORGANA(14)
- 9 own evidence under 10 votes, e.g. 2H_BOW:head HEAD_PLATE_SET3(9)->HEAD_PLATE_SET1(10), 2H_DAGGERPAIR_CRYSTAL:head HEAD_CLOTH_HELL(4)->HEAD_PLATE_SET1(9)
- 3 was pooled (thin) -> own evidence, e.g. MAIN_HOLYSTAFF_MORGANA:shoes SHOES_LEATHER_SET1(3)->SHOES_LEATHER_MORGANA(4), MAIN_NATURESTAFF_AVALON:cape CAPEITEM_FW_CAERLEON(0)->CAPEITEM_FW_LYMHURST(6)
- 1 pooled -> pooled, e.g. 2H_CURSEDSTAFF:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET3(2)

**20|clap** - pooled slots 22 -> 16, 54 slots changed

- 22 own evidence under 10 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:food T7_MEAL_OMELETTE(9)->T7_MEAL_OMELETTE_AVALON(11), 2H_DIVINESTAFF:head HEAD_PLATE_SET3(5)->HEAD_PLATE_SET1(6)
- 14 own evidence 30+ votes (meta shift or noise), e.g. 2H_AXE:shoes SHOES_LEATHER_MORGANA(35)->SHOES_CLOTH_ROYAL(34), 2H_GLACIALSTAFF:cape CAPEITEM_SMUGGLER(34)->CAPEITEM_MORGANA(41)
- 14 own evidence 10-29 votes, e.g. 2H_DAGGERPAIR:cape CAPEITEM_MORGANA(14)->CAPEITEM_SMUGGLER(23), 2H_DAGGERPAIR_CRYSTAL:cape CAPEITEM_SMUGGLER(14)->CAPEITEM_FW_LYMHURST(6)
- 3 was pooled (thin) -> own evidence, e.g. MAIN_HOLYSTAFF_MORGANA:shoes SHOES_LEATHER_SET1(3)->SHOES_LEATHER_MORGANA(4), MAIN_NATURESTAFF_AVALON:cape CAPEITEM_FW_CAERLEON(0)->CAPEITEM_FW_LYMHURST(6)
- 1 pooled -> pooled, e.g. 2H_CURSEDSTAFF:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET3(2)

**7|balanced** - pooled slots 11 -> 8, 49 slots changed

- 26 own evidence 30+ votes (meta shift or noise), e.g. 2H_DOUBLEBLADEDSTAFF:food T8_MEAL_STEW(30)->T7_MEAL_OMELETTE(34), 2H_DUALCROSSBOW_CRYSTAL:potion T7_POTION_STONESKIN(31)->T7_POTION_REVIVE(58)
- 16 own evidence 10-29 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:food T7_MEAL_OMELETTE_AVALON(16)->T7_MEAL_OMELETTE(21), 2H_BOW_CRYSTAL:cape CAPEITEM_SMUGGLER(13)->CAPEITEM_UNDEAD(22)
- 6 own evidence under 10 votes, e.g. 2H_BOW_CRYSTAL:shoes SHOES_LEATHER_MORGANA(9)->SHOES_CLOTH_AVALON(11), 2H_GLAIVE:armor ARMOR_LEATHER_SET2(3)->ARMOR_PLATE_ROYAL(10)
- 1 was pooled (thin) -> own evidence, e.g. 2H_CURSEDSTAFF:potion T7_POTION_REVIVE(2)->T7_POTION_STONESKIN(5)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 1 - MAIN_FROSTSTAFF_AVALON
- still under: 3; gained two or fewer voters: 1 (2H_IRONGAUNTLETS_HELL)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 106 | 107 | 2H_ENIGMATICSTAFF | - |
| mid | 86 | 91 | 2H_BOW, 2H_CLAYMORE, 2H_IRONCLADEDSTAFF, 2H_SHAPESHIFTER_HELL, MAIN_SPEAR_LANCE_AVALON | - |
| large | 54 | 55 | 2H_CLAYMORE_AVALON | - |

