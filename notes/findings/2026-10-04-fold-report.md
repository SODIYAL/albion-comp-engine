# Fold report 2026-10-04 - working tree vs `HEAD`

## Corpus (the battle-list population the derive steps read)

| unit | before | after |
|---|---|---|
| battles | 24365 | 31258 |
| battles in the file, every source | 120335 | 362212 |
| killer parties | 65252 | 82738 |
| observed builds | 465779 | 588876 |
| builds with a full kit | 450241 | 569144 |
| median gear coverage | 0.726 | 0.727 |
| Dragon Portal killer parties (kill-feed, not yet read) | 9444 | 24942 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 15845 -> 20117; labels {'brawl': 4220, 'brawl_clap': 223, 'clap': 6753, 'clap_kite': 1942, 'forming': 1, 'kite': 1406, 'split': 1300} -> {'brawl': 5375, 'brawl_clap': 288, 'clap': 8556, 'clap_kite': 2438, 'forming': 1, 'kite': 1790, 'split': 1669}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 6214 | 7916 | ok |
| balanced|15-19 | 7482 | 9492 | ok |
| balanced|20 | 1539 | 1930 | ok |
| brawl_clap|10-14 | 93 | 122 | ok |
| brawl_clap|15-19 | 101 | 129 | ok |
| brawl_clap|20 | 22 | 30 | UNDER FLOOR (borrows) |
| brawl|10-14 | 1968 | 2539 | ok |
| brawl|15-19 | 1826 | 2313 | ok |
| brawl|20 | 323 | 398 | ok |
| clap_kite|10-14 | 289 | 345 | ok |
| clap_kite|15-19 | 1171 | 1461 | ok |
| clap_kite|20 | 346 | 444 | ok |
| clap|10-14 | 2599 | 3295 | ok |
| clap|15-19 | 3308 | 4193 | ok |
| clap|20 | 587 | 737 | ok |
| kite|10-14 | 734 | 931 | ok |
| kite|15-19 | 478 | 620 | ok |
| kite|20 | 141 | 174 | ok |

## Style-band rows (target / soft cap)

1027 rows compared, 542 moved; median |relative move| 0.002, p90 0.089

| row | before | after |
|---|---|---|
| brawl_clap/10-14/requirements/anti_dive/target | 1.0 | 8.0 |
| brawl/10-14/requirements/anti_dive/target | 1.0 | 6.0 |
| brawl/15-19/requirements/anti_dive/target | 2.0 | 11.0 |
| brawl/20/requirements/anti_dive/target | 2.5 | 13.5 |
| brawl_clap/15-19/requirements/anti_dive/target | 2.5 | 13.5 |
| brawl_clap/20/requirements/anti_dive/target | 2.5 | 13.5 |
| brawl/20/requirements/anti_dive/soft_cap | 5.75 | 21.27 |
| brawl_clap/10-14/requirements/anti_dive/soft_cap | 4.02 | 14.32 |
| brawl/15-19/requirements/anti_dive/soft_cap | 5.17 | 18.4 |
| balanced/10-14/requirements/anti_dive/target | 2.0 | 7.0 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 19 -> 18, 42 slots changed

- 19 own evidence 10-29 votes, e.g. 2H_CLAYMORE:armor ARMOR_LEATHER_SET1(12)->ARMOR_CLOTH_SET2(16), 2H_CROSSBOWLARGE:cape CAPEITEM_SMUGGLER(20)->CAPEITEM_FW_LYMHURST(25)
- 15 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANESTAFF_CRYSTAL:cape CAPEITEM_SMUGGLER(104)->CAPEITEM_FW_LYMHURST(164), 2H_BOW_KEEPER:shoes SHOES_LEATHER_MORGANA(70)->SHOES_CLOTH_ROYAL(70)
- 8 own evidence under 10 votes, e.g. 2H_DAGGERPAIR_CRYSTAL:cape CAPEITEM_UNDEAD(6)->CAPEITEM_SMUGGLER(7), 2H_DAGGERPAIR_CRYSTAL:shoes SHOES_LEATHER_MORGANA(5)->SHOES_CLOTH_ROYAL(7)

**20|clap** - pooled slots 19 -> 18, 44 slots changed

- 17 own evidence 10-29 votes, e.g. 2H_CLAYMORE:armor ARMOR_LEATHER_SET1(12)->ARMOR_CLOTH_SET2(16), 2H_CLAYMORE:shoes SHOES_LEATHER_SET3(19)->SHOES_PLATE_SET1(6)
- 16 own evidence under 10 votes, e.g. 2H_DAGGERPAIR_CRYSTAL:cape CAPEITEM_UNDEAD(6)->CAPEITEM_SMUGGLER(7), 2H_DAGGERPAIR_CRYSTAL:shoes SHOES_LEATHER_MORGANA(5)->SHOES_CLOTH_ROYAL(7)
- 11 own evidence 30+ votes (meta shift or noise), e.g. 2H_ARCANESTAFF:shoes SHOES_LEATHER_MORGANA(144)->SHOES_LEATHER_ROYAL(181), 2H_BOW_KEEPER:head HEAD_LEATHER_SET3(69)->HEAD_PLATE_ROYAL(56)

**7|balanced** - pooled slots 8 -> 6, 36 slots changed

- 16 own evidence 10-29 votes, e.g. 2H_BOW_CRYSTAL:cape CAPEITEM_SMUGGLER(10)->CAPEITEM_UNDEAD(12), 2H_BOW_CRYSTAL:potion T6_POTION_HEAL(10)->T7_POTION_REVIVE(21)
- 14 own evidence 30+ votes (meta shift or noise), e.g. 2H_BOW_KEEPER:armor ARMOR_LEATHER_SET3(202)->ARMOR_PLATE_SET1(291), 2H_CROSSBOW:head HEAD_LEATHER_SET3(69)->HEAD_LEATHER_ROYAL(91)
- 6 own evidence under 10 votes, e.g. 2H_RAM_KEEPER:armor ARMOR_PLATE_SET3(5)->ARMOR_PLATE_SET2(8), 2H_REPEATINGCROSSBOW_UNDEAD:shoes SHOES_LEATHER_FEY(8)->SHOES_CLOTH_ROYAL(12)

## Group voters (uniform extension needs 35)

- crossed the line this fold: 4 - 2H_DAGGERPAIR_CRYSTAL, 2H_SHAPESHIFTER_MORGANA, 2H_TRIDENT_UNDEAD, MAIN_FIRESTAFF_CRYSTAL
- still under: 9; gained two or fewer voters: 2 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 101 | 103 | 2H_SHAPESHIFTER_SET3, MAIN_FIRESTAFF_CRYSTAL, MAIN_NATURESTAFF_CRYSTAL | 2H_SPEAR |
| mid | 80 | 81 | MAIN_MACE_CRYSTAL | - |
| large | 47 | 49 | 2H_ENIGMATICSTAFF, 2H_SHAPESHIFTER_AVALON | - |

