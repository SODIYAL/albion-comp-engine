# Fold report 2026-09-09 - working tree vs `HEAD`

## Corpus

| unit | before | after |
|---|---|---|
| battles | 3583 | 4283 |
| killer parties | 11547 | 12862 |
| observed builds | 88016 | 96483 |
| builds with a full kit | 85227 | 93307 |
| median gear coverage | 0.75 | 0.735 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 4051 -> 4188; labels {'brawl': 1124, 'brawl_clap': 64, 'clap': 1638, 'clap_kite': 518, 'kite': 404, 'split': 303} -> {'brawl': 1165, 'brawl_clap': 66, 'clap': 1701, 'clap_kite': 526, 'kite': 416, 'split': 314}

| cell | before | after | status |
|---|---|---|---|
| brawl_clap|10-14 | 19 | 21 | UNDER FLOOR (borrows) |
| brawl_clap|15-19 | 27 | 27 | UNDER FLOOR (borrows) |
| brawl_clap|20 | 12 | 12 | UNDER FLOOR (borrows) |
| brawl|10-14 | 462 | 481 | ok |
| brawl|15-19 | 520 | 537 | ok |
| brawl|20 | 98 | 101 | ok |
| clap_kite|10-14 | 74 | 77 | ok |
| clap_kite|15-19 | 293 | 297 | ok |
| clap_kite|20 | 108 | 108 | ok |
| clap|10-14 | 575 | 603 | ok |
| clap|15-19 | 809 | 838 | ok |
| clap|20 | 161 | 166 | ok |
| kite|10-14 | 193 | 201 | ok |
| kite|15-19 | 156 | 160 | ok |
| kite|20 | 31 | 31 | UNDER FLOOR (borrows) |

## Style-band rows (target / soft cap)

773 rows compared, 449 moved; median |relative move| 0.003, p90 0.063

| row | before | after |
|---|---|---|
| brawl/20/requirements/silence/target | 0.92 | 4.14 |
| brawl_clap/20/requirements/silence/target | 0.92 | 4.14 |
| clap_kite/10-14/requirements/heal_reduction/target | 0.27 | 0.54 |
| kite/10-14/requirements/purge/target | 0.9 | 1.35 |
| kite/10-14/requirements/max_health_cut/soft_cap | 2.07 | 1.15 |
| clap_kite/10-14/requirements/cleanse/target | 1.35 | 0.81 |
| kite/15-19/requirements/max_health_cut/soft_cap | 1.72 | 1.26 |
| kite/20/requirements/max_health_cut/soft_cap | 1.72 | 1.26 |
| brawl/10-14/requirements/cleanse/soft_cap | 4.6 | 5.75 |
| brawl_clap/10-14/requirements/cleanse/soft_cap | 4.6 | 5.75 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 108 -> 98, 22 slots changed

- 7 pooled -> pooled, e.g. 2H_BOW:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET1(2), 2H_CURSEDSTAFF:cape CAPEITEM_SMUGGLER(0)->CAPEITEM_FW_LYMHURST(0)
- 6 own evidence under 10 votes, e.g. 2H_BOW:armor ARMOR_CLOTH_SET2(4)->ARMOR_LEATHER_SET3(5), 2H_CURSEDSTAFF:armor ARMOR_PLATE_HELL(0)->ARMOR_CLOTH_SET2(2)
- 4 was pooled (thin) -> own evidence, e.g. 2H_BOW:cape CAPEITEM_FW_LYMHURST(2)->CAPEITEM_FW_THETFORD(5), 2H_BOW_CRYSTAL:head HEAD_PLATE_SET1(0)->HEAD_CLOTH_AVALON(5)
- 3 own evidence 30+ votes (meta shift or noise), e.g. 2H_HOLYSTAFF_CRYSTAL:food T7_MEAL_OMELETTE(81)->T7_MEAL_OMELETTE_AVALON(68), 2H_KNUCKLES_HELL:armor ARMOR_LEATHER_HELL(31)->ARMOR_LEATHER_SET2(32)
- 2 own evidence 10-29 votes, e.g. 2H_CLAYMORE_AVALON:head HEAD_LEATHER_MORGANA(28)->HEAD_PLATE_SET1(25), 2H_GLACIALSTAFF:cape CAPEITEM_FW_LYMHURST(11)->CAPEITEM_SMUGGLER(11)

**20|clap** - pooled slots 108 -> 98, 31 slots changed

- 17 own evidence under 10 votes, e.g. 2H_BOW:armor ARMOR_CLOTH_SET2(4)->ARMOR_LEATHER_SET3(5), 2H_COMBATSTAFF_MORGANA:head HEAD_LEATHER_SET3(8)->HEAD_LEATHER_HELL(5)
- 7 pooled -> pooled, e.g. 2H_BOW:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET1(2), 2H_CURSEDSTAFF:cape CAPEITEM_SMUGGLER(0)->CAPEITEM_FW_LYMHURST(0)
- 4 was pooled (thin) -> own evidence, e.g. 2H_BOW:cape CAPEITEM_FW_LYMHURST(2)->CAPEITEM_FW_THETFORD(5), 2H_BOW_CRYSTAL:head HEAD_PLATE_SET1(0)->HEAD_CLOTH_AVALON(5)
- 3 own evidence 10-29 votes, e.g. 2H_CLAYMORE_AVALON:head HEAD_LEATHER_MORGANA(28)->HEAD_PLATE_SET1(25), 2H_DUALSCIMITAR_UNDEAD:cape CAPEITEM_FW_LYMHURST(13)->CAPEITEM_SMUGGLER(17)

**7|balanced** - pooled slots 101 -> 80, 59 slots changed

- 21 own evidence under 10 votes, e.g. 2H_BOW:head HEAD_LEATHER_SET3(6)->HEAD_PLATE_SET3(14), 2H_BOW_CRYSTAL:armor ARMOR_LEATHER_SET3(2)->ARMOR_CLOTH_SET2(4)
- 11 pooled -> pooled, e.g. 2H_BOW_CRYSTAL:cape CAPEITEM_FW_FORTSTERLING(0)->CAPEITEM_FW_LYMHURST(0), 2H_BOW_CRYSTAL:shoes SHOES_LEATHER_AVALON(0)->SHOES_LEATHER_MORGANA(2)
- 10 own evidence 30+ votes (meta shift or noise), e.g. 2H_BOW_KEEPER:armor ARMOR_CLOTH_SET2(39)->ARMOR_LEATHER_SET3(52), 2H_HALBERD_MORGANA:potion T7_POTION_REVIVE(45)->T7_POTION_STONESKIN(60)
- 9 was pooled (thin) -> own evidence, e.g. 2H_DUALCROSSBOW_CRYSTAL:shoes SHOES_LEATHER_MORGANA(0)->SHOES_CLOTH_AVALON(7), 2H_FIRESTAFF:head HEAD_LEATHER_SET3(4)->HEAD_PLATE_SET3(6)
- 8 own evidence 10-29 votes, e.g. 2H_DUALSICKLE_UNDEAD:cape CAPEITEM_FW_THETFORD(20)->CAPEITEM_UNDEAD(27), 2H_INFERNOSTAFF:shoes SHOES_LEATHER_SET1(13)->SHOES_CLOTH_ROYAL(16)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 1 - 2H_COMBATSTAFF_MORGANA
- still under: 52; gained two or fewer voters: 48 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_TRIDENT_UNDEAD, 2H_CURSEDSTAFF, 2H_DAGGERPAIR_CRYSTAL, 2H_SHAPESHIFTER_SET1, 2H_KNUCKLES_CRYSTAL, MAIN_FROSTSTAFF_AVALON, 2H_BOW_CRYSTAL, 2H_SHAPESHIFTER_MORGANA, MAIN_NATURESTAFF_KEEPER, 2H_DOUBLEBLADEDSTAFF_CRYSTAL...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 82 | 86 | 2H_ARCANESTAFF_CRYSTAL, 2H_FIRESTAFF, 2H_KNUCKLES_KEEPER, MAIN_DAGGER | - |
| mid | 68 | 70 | 2H_ARCANESTAFF_CRYSTAL, 2H_CROSSBOW, 2H_ICEGAUNTLETS_HELL | 2H_ENIGMATICSTAFF |
| large | 41 | 42 | 2H_INFERNOSTAFF_MORGANA | - |

