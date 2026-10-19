# Fold report 2026-10-19 - working tree vs `HEAD`

## Corpus (the battle-list population the derive steps read)

| unit | before | after |
|---|---|---|
| battles | 45287 | 48630 |
| battles in the build artifact (the battle list and the Dragon Portal) | 86873 | 100542 |
| killer parties | 116100 | 126211 |
| observed builds | 823282 | 897180 |
| builds with a full kit | 795438 | 867001 |
| median gear coverage | 0.727 | 0.727 |
| Dragon Portal killer parties (kill-feed, not yet read) | 51244 | 63347 |

Dragon Portal 15-20 pool: 92 -> 115 distinct dominant rosters; its fielded list and role counts wait for 200 (BACKLOG).

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 27057 -> 30021; labels {'brawl': 7154, 'brawl_clap': 316, 'clap': 11380, 'clap_kite': 3120, 'forming': 1, 'gank': 491, 'kite': 2272, 'split': 2323} -> {'brawl': 7816, 'brawl_clap': 350, 'clap': 12736, 'clap_kite': 3471, 'forming': 2, 'gank': 537, 'kite': 2539, 'split': 2570}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 10808 | 11952 | ok |
| balanced|15-19 | 12682 | 14121 | ok |
| balanced|20 | 2516 | 2804 | ok |
| brawl_clap|10-14 | 145 | 161 | ok |
| brawl_clap|15-19 | 135 | 149 | ok |
| brawl_clap|20 | 30 | 32 | UNDER FLOOR (borrows) |
| brawl|10-14 | 3361 | 3675 | ok |
| brawl|15-19 | 3102 | 3389 | ok |
| brawl|20 | 521 | 574 | ok |
| clap_kite|10-14 | 451 | 496 | ok |
| clap_kite|15-19 | 1843 | 2052 | ok |
| clap_kite|20 | 576 | 642 | ok |
| clap|10-14 | 4286 | 4777 | ok |
| clap|15-19 | 5698 | 6405 | ok |
| clap|20 | 950 | 1073 | ok |
| kite|10-14 | 1137 | 1276 | ok |
| kite|15-19 | 798 | 884 | ok |
| kite|20 | 246 | 278 | ok |

## Style-band rows (target / soft cap)

1025 rows compared, 491 moved; median |relative move| 0.000, p90 0.053

| row | before | after |
|---|---|---|
| brawl_clap/15-19/requirements/ranged_presence/target | 1.0 | 2.0 |
| brawl_clap/20/requirements/ranged_presence/target | 1.0 | 2.0 |
| clap_kite/10-14/requirements/damage_debuff/target | 1.0 | 1.75 |
| brawl_clap/10-14/requirements/ranged_presence/soft_cap | 2.3 | 3.45 |
| brawl/20/requirements/ranged_presence/target | 2.0 | 3.0 |
| balanced/15-19/requirements/damage_debuff/target | 2.5 | 3.5 |
| brawl/10-14/requirements/damage_debuff/target | 2.5 | 3.0 |
| clap_kite/10-14/requirements/disengage/target | 5.0 | 4.0 |
| brawl_clap/15-19/requirements/heal_reduction/soft_cap | 4.6 | 3.68 |
| brawl_clap/20/requirements/heal_reduction/soft_cap | 4.6 | 3.68 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 23 -> 22, 29 slots changed

- 11 own evidence 10-29 votes, e.g. 2H_DAGGERPAIR_CRYSTAL:armor ARMOR_LEATHER_HELL(11)->ARMOR_LEATHER_SET3(14), 2H_NATURESTAFF:potion T7_POTION_REVIVE(22)->T7_POTION_STONESKIN(26)
- 8 own evidence 30+ votes (meta shift or noise), e.g. 2H_AXE_AVALON:armor ARMOR_LEATHER_HELL(1066)->ARMOR_LEATHER_ROYAL(1144), 2H_DUALCROSSBOW_HELL:shoes SHOES_CLOTH_ROYAL(37)->SHOES_PLATE_SET1(30)
- 8 own evidence under 10 votes, e.g. 2H_DAGGERPAIR_CRYSTAL:head HEAD_PLATE_SET1(7)->HEAD_CLOTH_HELL(4), 2H_DOUBLEBLADEDSTAFF_CRYSTAL:head HEAD_LEATHER_MORGANA(8)->HEAD_PLATE_SET1(8)
- 1 was pooled (thin) -> own evidence, e.g. 2H_DIVINESTAFF:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET3(5)
- 1 pooled -> pooled, e.g. MAIN_SWORD:head HEAD_PLATE_SET1(0)->HEAD_PLATE_SET3(4)

**20|clap** - pooled slots 23 -> 22, 40 slots changed

- 19 own evidence 10-29 votes, e.g. 2H_BOW:armor ARMOR_CLOTH_SET2(16)->ARMOR_LEATHER_SET2(6), 2H_DAGGERPAIR_CRYSTAL:armor ARMOR_LEATHER_HELL(11)->ARMOR_LEATHER_SET3(14)
- 14 own evidence under 10 votes, e.g. 2H_BOW:cape CAPEITEM_FW_THETFORD(4)->CAPEITEM_FW_LYMHURST(7), 2H_DAGGERPAIR_CRYSTAL:head HEAD_PLATE_SET1(7)->HEAD_LEATHER_SET3(5)
- 5 own evidence 30+ votes (meta shift or noise), e.g. 2H_GLACIALSTAFF:cape CAPEITEM_MORGANA(33)->CAPEITEM_SMUGGLER(34), 2H_LONGBOW_UNDEAD:shoes SHOES_LEATHER_MORGANA(61)->SHOES_CLOTH_ROYAL(58)
- 1 was pooled (thin) -> own evidence, e.g. 2H_DIVINESTAFF:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET3(5)
- 1 pooled -> pooled, e.g. MAIN_SWORD:head HEAD_PLATE_SET1(0)->HEAD_PLATE_SET3(4)

**7|balanced** - pooled slots 12 -> 11, 28 slots changed

- 13 own evidence 30+ votes (meta shift or noise), e.g. 2H_CROSSBOW:potion T8_POTION_COOLDOWN(117)->T7_POTION_REVIVE(165), 2H_CROSSBOWLARGE_MORGANA:cape CAPEITEM_SMUGGLER(56)->CAPEITEM_MORGANA(33)
- 12 own evidence 10-29 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:food T7_MEAL_OMELETTE(15)->T7_MEAL_OMELETTE_AVALON(16), 2H_BOW_CRYSTAL:cape CAPEITEM_UNDEAD(12)->CAPEITEM_SMUGGLER(13)
- 2 own evidence under 10 votes, e.g. 2H_GLAIVE:shoes SHOES_LEATHER_FEY(5)->SHOES_LEATHER_MORGANA(10), 2H_RAM_KEEPER:armor ARMOR_PLATE_SET3(6)->ARMOR_PLATE_SET2(6)
- 1 was pooled (thin) -> own evidence, e.g. 2H_RAM_KEEPER:food T8_MEAL_SANDWICH_AVALON(4)->T8_MEAL_SANDWICH(6)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 0 - none
- still under: 4; gained two or fewer voters: 3 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, MAIN_FROSTSTAFF_AVALON)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 105 | 106 | MAIN_NATURESTAFF_CRYSTAL | - |
| mid | 86 | 86 | 2H_CROSSBOWLARGE_MORGANA | MAIN_SPEAR_LANCE_AVALON |
| large | 53 | 54 | MAIN_MACE_CRYSTAL | - |

