# Fold report 2026-09-11 - working tree vs `HEAD`

## Corpus

| unit | before | after |
|---|---|---|
| battles | 7652 | 7652 |
| killer parties | 20132 | 20132 |
| observed builds | 147163 | 147163 |
| builds with a full kit | 142147 | 142147 |
| median gear coverage | 0.72 | 0.72 |

## Style board (rosters of 10+ per style x band cell; floor 40)

labelled rosters 5679 -> 5679; labels {'brawl': 1610, 'brawl_clap': 88, 'clap': 2337, 'clap_kite': 678, 'forming': 1, 'kite': 533, 'split': 432} -> {'brawl': 1610, 'brawl_clap': 88, 'clap': 2337, 'clap_kite': 678, 'forming': 1, 'kite': 533, 'split': 432}

| cell | before | after | status |
|---|---|---|---|
| balanced|10-14 | 2092 | 2092 | ok |
| balanced|15-19 | 2668 | 2668 | ok |
| balanced|20 | 592 | 592 | ok |
| brawl_clap|10-14 | 28 | 28 | UNDER FLOOR (borrows) |
| brawl_clap|15-19 | 36 | 36 | UNDER FLOOR (borrows) |
| brawl_clap|20 | 15 | 15 | UNDER FLOOR (borrows) |
| brawl|10-14 | 710 | 710 | ok |
| brawl|15-19 | 707 | 707 | ok |
| brawl|20 | 130 | 130 | ok |
| clap_kite|10-14 | 94 | 94 | ok |
| clap_kite|15-19 | 383 | 383 | ok |
| clap_kite|20 | 141 | 141 | ok |
| clap|10-14 | 820 | 820 | ok |
| clap|15-19 | 1154 | 1154 | ok |
| clap|20 | 221 | 221 | ok |
| kite|10-14 | 273 | 273 | ok |
| kite|15-19 | 192 | 192 | ok |
| kite|20 | 41 | 41 | ok |

## Style-band rows (target / soft cap)

1030 rows compared, 308 moved; median |relative move| 0.000, p90 0.018

| row | before | after |
|---|---|---|
| balanced/10-14/requirements/silence/target | 1.5 | 2.6 |
| clap/10-14/requirements/damage_debuff/target | 2.0 | 1.0 |
| kite/15-19/requirements/damage_debuff/target | 2.0 | 1.0 |
| clap/20/requirements/damage_debuff/target | 4.5 | 2.5 |
| brawl/15-19/requirements/anti_dive/target | 2.0 | 2.5 |
| brawl_clap/15-19/requirements/anti_dive/target | 2.0 | 2.5 |
| balanced/10-14/requirements/damage_debuff/target | 2.5 | 2.0 |
| clap_kite/15-19/requirements/damage_debuff/soft_cap | 3.45 | 2.88 |
| clap/20/requirements/damage_debuff/soft_cap | 11.5 | 9.77 |
| kite/15-19/requirements/purge/target | 7.0 | 8.0 |

## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)

**20|balanced** - pooled slots 73 -> 73, 0 slots changed


**20|clap** - pooled slots 73 -> 73, 0 slots changed


**7|balanced** - pooled slots 41 -> 41, 0 slots changed


## Group voters (uniform extension needs 35)

- crossed the line this fold: 0 - none
- still under: 42; gained two or fewer voters: 42 (2H_IRONGAUNTLETS_HELL, MAIN_NATURESTAFF_AVALON, 2H_TRIDENT_UNDEAD, 2H_KNUCKLES_CRYSTAL, 2H_SHAPESHIFTER_SET1, MAIN_FROSTSTAFF_AVALON, 2H_CURSEDSTAFF, 2H_BOW_CRYSTAL, 2H_DAGGERPAIR_CRYSTAL, MAIN_NATURESTAFF_KEEPER, 2H_SPEAR, 2H_REPEATINGCROSSBOW_UNDEAD...)

## Meta prior rows per bucket

| bucket | before | after | entered | left |
|---|---|---|---|---|
| small | 93 | 94 | 2H_DAGGERPAIR_CRYSTAL, 2H_HALBERD | 2H_BOW_CRYSTAL |
| mid | 75 | 71 | - | 2H_DUALHAMMER_HELL, 2H_ENIGMATICSTAFF, 2H_INFERNOSTAFF, 2H_WARBOW |
| large | 43 | 43 | - | - |

