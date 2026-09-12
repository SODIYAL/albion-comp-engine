# Fold report 2026-09-11 - working tree vs `HEAD`

## Corpus

| unit | before | after |
|---|---|---|
| battles | 4283 | 7652 |
| killer parties | 12862 | 20132 |
| observed builds | 96483 | 147163 |
| builds with a full kit | 93307 | 142147 |
| median gear coverage | 0.735 | 0.72 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 4188 -> 5679; labels {'brawl': 1165, 'brawl_clap': 66, 'clap': 1701, 'clap_kite': 526, 'kite': 416, 'split': 314} -> {'brawl': 1610, 'brawl_clap': 88, 'clap': 2337, 'clap_kite': 678, 'forming': 1, 'kite': 533, 'split': 432}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 0 | 2092 | ok |
| balanced|15-19 | 0 | 2668 | ok |
| balanced|20 | 0 | 592 | ok |
| brawl_clap|10-14 | 21 | 28 | UNDER FLOOR (borrows) |
| brawl_clap|15-19 | 27 | 36 | UNDER FLOOR (borrows) |
| brawl_clap|20 | 12 | 15 | UNDER FLOOR (borrows) |
| brawl|10-14 | 481 | 710 | ok |
| brawl|15-19 | 537 | 707 | ok |
| brawl|20 | 101 | 130 | ok |
| clap_kite|10-14 | 77 | 94 | ok |
| clap_kite|15-19 | 297 | 383 | ok |
| clap_kite|20 | 108 | 141 | ok |
| clap|10-14 | 603 | 820 | ok |
| clap|15-19 | 838 | 1154 | ok |
| clap|20 | 166 | 221 | ok |
| kite|10-14 | 201 | 273 | ok |
| kite|15-19 | 160 | 192 | ok |
| kite|20 | 31 | 41 | ok |

## Style-band rows (target / soft cap)

853 rows compared, 506 moved; median |relative move| 0.006, p90 0.126

| row | before | after |
|---|---|---|
| kite/20/requirements/max_health_cut/soft_cap | 1.26 | 3.45 |
| clap/20/requirements/damage_debuff/target | 2.5 | 4.5 |
| kite/10-14/requirements/max_health_cut/soft_cap | 1.15 | 2.07 |
| kite/20/requirements/cleanse/target | 6.0 | 10.0 |
| kite/20/requirements/burst_st/target | 3.39 | 1.45 |
| kite/20/requirements/burst_st/soft_cap | 11.24 | 5.34 |
| brawl/10-14/requirements/anti_dive/target | 2.0 | 1.0 |
| kite/20/requirements/clump_create/target | 2.0 | 3.0 |
| brawl_clap/10-14/requirements/anti_dive/target | 2.0 | 1.0 |
| clap_kite/20/requirements/max_health_cut/soft_cap | 2.3 | 1.15 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 98 -> 73, 48 slots changed

- 17 own evidence under 10 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:armor ARMOR_CLOTH_FEY(2)->ARMOR_PLATE_KEEPER(12), 2H_BOW:armor ARMOR_LEATHER_SET3(5)->ARMOR_LEATHER_SET1(8)
- 11 was pooled (thin) -> own evidence, e.g. 2H_BOW:head HEAD_PLATE_SET1(2)->HEAD_PLATE_SET3(7), 2H_DIVINESTAFF:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET3(6)
- 11 own evidence 10-29 votes, e.g. 2H_COMBATSTAFF_MORGANA:head HEAD_LEATHER_HELL(12)->HEAD_LEATHER_SET3(24), 2H_DUALCROSSBOW_HELL:armor ARMOR_CLOTH_SET2(15)->ARMOR_LEATHER_SET1(19)
- 6 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_LYMHURST(0)->CAPEITEM_FW_CAERLEON(0), 2H_RAM_KEEPER:shoes SHOES_LEATHER_ROYAL(2)->SHOES_LEATHER_SET2(5)
- 3 own evidence 30+ votes (meta shift or noise), e.g. 2H_CLAYMORE_AVALON:cape CAPEITEM_FW_LYMHURST(44)->CAPEITEM_SMUGGLER(56), 2H_HOLYSTAFF_CRYSTAL:food T7_MEAL_OMELETTE_AVALON(68)->T7_MEAL_OMELETTE(99)

**20|clap** - pooled slots 98 -> 73, 69 slots changed

- 32 own evidence under 10 votes, e.g. 2H_ARCANE_RINGPAIR_AVALON:armor ARMOR_CLOTH_FEY(2)->ARMOR_PLATE_KEEPER(12), 2H_AXE:head HEAD_LEATHER_MORGANA(6)->HEAD_LEATHER_SET3(8)
- 14 own evidence 10-29 votes, e.g. 2H_DUALHAMMER_HELL:cape CAPEITEM_FW_CAERLEON(19)->CAPEITEM_FW_LYMHURST(5), 2H_DUALSCIMITAR_UNDEAD:cape CAPEITEM_SMUGGLER(17)->CAPEITEM_FW_LYMHURST(16)
- 11 was pooled (thin) -> own evidence, e.g. 2H_BOW:head HEAD_PLATE_SET1(2)->HEAD_PLATE_SET3(7), 2H_DIVINESTAFF:head HEAD_LEATHER_SET3(0)->HEAD_PLATE_SET3(6)
- 6 own evidence 30+ votes (meta shift or noise), e.g. 2H_CLAWPAIR:potion T8_POTION_COOLDOWN(36)->T7_POTION_REVIVE(6), 2H_DAGGERPAIR:cape CAPEITEM_MORGANA(38)->CAPEITEM_SMUGGLER(5)
- 6 pooled -> pooled, e.g. 2H_CURSEDSTAFF:cape CAPEITEM_FW_LYMHURST(0)->CAPEITEM_FW_CAERLEON(0), 2H_RAM_KEEPER:shoes SHOES_LEATHER_ROYAL(2)->SHOES_LEATHER_SET2(5)

**7|balanced** - pooled slots 80 -> 41, 91 slots changed

- 30 own evidence under 10 votes, e.g. 2H_BOW_CRYSTAL:armor ARMOR_CLOTH_SET2(4)->ARMOR_LEATHER_SET3(6), 2H_CLAYMORE:armor ARMOR_LEATHER_SET1(9)->ARMOR_CLOTH_SET2(15)
- 23 was pooled (thin) -> own evidence, e.g. 2H_ARCANE_RINGPAIR_AVALON:shoes SHOES_LEATHER_MORGANA(0)->SHOES_LEATHER_SET1(5), 2H_ARCANE_RINGPAIR_AVALON:cape CAPEITEM_FW_LYMHURST(0)->CAPEITEM_SMUGGLER(5)
- 22 own evidence 10-29 votes, e.g. 2H_ARCANESTAFF:shoes SHOES_LEATHER_MORGANA(10)->SHOES_LEATHER_ROYAL(18), 2H_BOW:shoes SHOES_LEATHER_SET1(16)->SHOES_LEATHER_ROYAL(23)
- 11 own evidence 30+ votes (meta shift or noise), e.g. 2H_CLEAVER_HELL:cape CAPEITEM_SMUGGLER(61)->CAPEITEM_FW_LYMHURST(73), 2H_DUALMACE_AVALON:armor ARMOR_LEATHER_ROYAL(45)->ARMOR_PLATE_HELL(59)
- 5 pooled -> pooled, e.g. 2H_BOW_CRYSTAL:shoes SHOES_LEATHER_MORGANA(2)->SHOES_LEATHER_AVALON(0), 2H_HAMMER_CRYSTAL:shoes SHOES_LEATHER_MORGANA(3)->SHOES_LEATHER_SET2(2)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 10 - 2H_ARCANE_RINGPAIR_AVALON, 2H_CROSSBOWLARGE, 2H_DOUBLEBLADEDSTAFF, 2H_FIRESTAFF, 2H_HALBERD_MORGANA, 2H_NATURESTAFF, 2H_WARBOW, MAIN_1HCROSSBOW, MAIN_FIRESTAFF_KEEPER, MAIN_SCIMITAR_MORGANA
- still under: 42; gained two or fewer voters: 14 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_TRIDENT_UNDEAD, 2H_KNUCKLES_CRYSTAL, 2H_SHAPESHIFTER_SET1, MAIN_FROSTSTAFF_AVALON, 2H_CURSEDSTAFF, 2H_BOW_CRYSTAL, MAIN_NATURESTAFF_KEEPER, 2H_SPEAR, 2H_REPEATINGCROSSBOW_UNDEAD, MAIN_SWORD...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 86 | 93 | 2H_BOW_CRYSTAL, 2H_SCYTHE_CRYSTAL, 2H_SHAPESHIFTER_SET3, MAIN_1HCROSSBOW, MAIN_FIRESTAFF_KEEPER, MAIN_SCIMITAR_MORGANA, MAIN_SPEAR_LANCE_AVALON | - |
| mid | 70 | 75 | 2H_DUALHAMMER_HELL, 2H_ENIGMATICSTAFF, 2H_INFERNOSTAFF, 2H_KNUCKLES_AVALON, 2H_WARBOW | - |
| large | 42 | 43 | 2H_ICEGAUNTLETS_HELL | - |

