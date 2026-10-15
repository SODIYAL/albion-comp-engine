# Fold report 2026-10-14 - working tree vs `HEAD`

## Corpus (the battle-list population the derive steps read)

| unit | before | after |
|---|---|---|
| battles | 31258 | 45287 |
| battles in the build artifact (the battle list and the Dragon Portal) | 362212 | 86873 |
| killer parties | 82738 | 116100 |
| observed builds | 588876 | 823282 |
| builds with a full kit | 569144 | 795438 |
| median gear coverage | 0.727 | 0.727 |
| Dragon Portal killer parties (kill-feed, not yet read) | 24942 | 51244 |

Dragon Portal 15-20 pool: 40 -> 92 distinct dominant rosters; its fielded list and role counts wait for 200 (BACKLOG).

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 20117 -> 27057; labels {'brawl': 5375, 'brawl_clap': 288, 'clap': 8556, 'clap_kite': 2438, 'forming': 1, 'kite': 1790, 'split': 1669} -> {'brawl': 7154, 'brawl_clap': 316, 'clap': 11380, 'clap_kite': 3120, 'forming': 1, 'gank': 491, 'kite': 2272, 'split': 2323}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 7916 | 10808 | ok |
| balanced|15-19 | 9492 | 12682 | ok |
| balanced|20 | 1930 | 2516 | ok |
| brawl_clap|10-14 | 122 | 145 | ok |
| brawl_clap|15-19 | 129 | 135 | ok |
| brawl_clap|20 | 30 | 30 | UNDER FLOOR (borrows) |
| brawl|10-14 | 2539 | 3361 | ok |
| brawl|15-19 | 2313 | 3102 | ok |
| brawl|20 | 398 | 521 | ok |
| clap_kite|10-14 | 345 | 451 | ok |
| clap_kite|15-19 | 1461 | 1843 | ok |
| clap_kite|20 | 444 | 576 | ok |
| clap|10-14 | 3295 | 4286 | ok |
| clap|15-19 | 4193 | 5698 | ok |
| clap|20 | 737 | 950 | ok |
| kite|10-14 | 931 | 1137 | ok |
| kite|15-19 | 620 | 798 | ok |
| kite|20 | 174 | 246 | ok |

## Style-band rows (target / soft cap)

1024 rows compared, 765 moved; median |relative move| 0.056, p90 0.459

| row | before | after |
|---|---|---|
| brawl_clap/15-19/requirements/clump_create/target | 1.0 | 4.5 |
| brawl_clap/20/requirements/clump_create/target | 1.0 | 4.5 |
| brawl_clap/15-19/requirements/clump_create/soft_cap | 3.45 | 8.97 |
| brawl_clap/20/requirements/clump_create/soft_cap | 3.45 | 8.97 |
| clap_kite/10-14/requirements/clump_create/target | 2.0 | 4.5 |
| brawl_clap/10-14/requirements/clump_create/soft_cap | 2.3 | 4.94 |
| clap/10-14/requirements/damage_debuff/target | 1.0 | 2.0 |
| clap/15-19/requirements/clump_create/target | 2.0 | 4.0 |
| kite/15-19/requirements/damage_debuff/target | 1.0 | 2.0 |
| kite/20/requirements/damage_debuff/target | 1.0 | 2.0 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 37 -> 23, 65 slots changed

- 23 own evidence 10-29 votes, e.g. 2H_DUALCROSSBOW_HELL:shoes SHOES_PLATE_SET1(20)->SHOES_CLOTH_ROYAL(37), 2H_DUALSWORD:head HEAD_LEATHER_SET2(13)->HEAD_PLATE_SET1(20)
- 20 own evidence under 10 votes, e.g. 2H_BOW:head HEAD_PLATE_SET1(6)->HEAD_PLATE_SET3(8), 2H_CLAYMORE:armor ARMOR_LEATHER_HELL(6)->ARMOR_CLOTH_SET2(9)
- 13 own evidence 30+ votes (meta shift or noise), e.g. 2H_CROSSBOWLARGE_MORGANA:shoes SHOES_CLOTH_ROYAL(34)->SHOES_LEATHER_FEY(50), 2H_CROSSBOW_CANNON_AVALON:shoes SHOES_LEATHER_FEY(151)->SHOES_CLOTH_ROYAL(312)
- 5 was pooled (thin) -> own evidence, e.g. 2H_BOW_CRYSTAL:head HEAD_PLATE_SET1(0)->HEAD_CLOTH_AVALON(5), 2H_HAMMER_UNDEAD:head HEAD_PLATE_KEEPER(2)->HEAD_LEATHER_HELL(5)
- 4 pooled -> pooled, e.g. 2H_CURSEDSTAFF:head HEAD_PLATE_SET3(0)->HEAD_LEATHER_SET3(0), MAIN_NATURESTAFF_AVALON:cape CAPEITEM_FW_LYMHURST(2)->CAPEITEM_FW_CAERLEON(0)

**20|clap** - pooled slots 39 -> 23, 69 slots changed

- 26 own evidence 10-29 votes, e.g. 2H_AXE:shoes SHOES_CLOTH_ROYAL(26)->SHOES_LEATHER_MORGANA(30), 2H_CROSSBOWLARGE_MORGANA:shoes SHOES_CLOTH_ROYAL(25)->SHOES_LEATHER_FEY(45)
- 25 own evidence under 10 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:shoes SHOES_LEATHER_ROYAL(5)->SHOES_LEATHER_MORGANA(13), 2H_ARCANE_RINGPAIR_AVALON:food T7_MEAL_OMELETTE_AVALON(5)->T7_MEAL_OMELETTE(9)
- 9 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANESTAFF_CRYSTAL:cape CAPEITEM_SMUGGLER(61)->CAPEITEM_FW_LYMHURST(71), 2H_AXE_AVALON:armor ARMOR_LEATHER_HELL(551)->ARMOR_LEATHER_ROYAL(687)
- 5 was pooled (thin) -> own evidence, e.g. 2H_BOW_CRYSTAL:head HEAD_PLATE_SET1(0)->HEAD_CLOTH_AVALON(5), 2H_HAMMER_UNDEAD:head HEAD_PLATE_KEEPER(2)->HEAD_LEATHER_HELL(5)
- 4 pooled -> pooled, e.g. 2H_CURSEDSTAFF:head HEAD_PLATE_SET3(0)->HEAD_LEATHER_SET3(0), MAIN_NATURESTAFF_AVALON:cape CAPEITEM_FW_LYMHURST(2)->CAPEITEM_FW_CAERLEON(0)

**7|balanced** - pooled slots 16 -> 12, 64 slots changed

- 30 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANESTAFF_CRYSTAL:shoes SHOES_CLOTH_ROYAL(58)->SHOES_CLOTH_MORGANA(83), 2H_ARCANESTAFF_CRYSTAL:armor ARMOR_LEATHER_MORGANA(67)->ARMOR_LEATHER_AVALON(94)
- 22 own evidence 10-29 votes, e.g. 2H_CLAYMORE:cape CAPEITEM_FW_LYMHURST(20)->CAPEITEM_FW_CAERLEON(24), 2H_DAGGERPAIR_CRYSTAL:cape CAPEITEM_SMUGGLER(14)->CAPEITEM_UNDEAD(22)
- 11 own evidence under 10 votes, e.g. 2H_BOW_CRYSTAL:shoes SHOES_CLOTH_AVALON(6)->SHOES_LEATHER_MORGANA(9), 2H_COMBATSTAFF_MORGANA:head HEAD_LEATHER_HELL(8)->HEAD_LEATHER_SET3(16)
- 1 was pooled (thin) -> own evidence, e.g. 2H_FLAIL:head HEAD_PLATE_KEEPER(3)->HEAD_PLATE_SET1(4)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 5 - 2H_BOW_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL, 2H_KNUCKLES_CRYSTAL, 2H_SHAPESHIFTER_SET1, MAIN_NATURESTAFF_KEEPER
- still under: 4; gained two or fewer voters: 1 (2H_IRONGAUNTLETS_HELL)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 103 | 105 | 2H_KNUCKLES_CRYSTAL, 2H_SKULLORB_HELL, 2H_SPEAR | MAIN_NATURESTAFF_CRYSTAL |
| mid | 81 | 86 | 2H_FROSTSTAFF_CRYSTAL, 2H_HALBERD_MORGANA, 2H_KNUCKLES_SET1, 2H_ROCKSTAFF_KEEPER, MAIN_SPEAR_LANCE_AVALON | - |
| large | 49 | 53 | 2H_ARCANESTAFF_CRYSTAL, 2H_AXE, 2H_KNUCKLES_HELL, 2H_LONGBOW_UNDEAD | - |

