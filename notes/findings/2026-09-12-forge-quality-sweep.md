# Forge quality sweep (2026-09-12)

Report-only (`pipeline/audit_forge_quality.py`). Every cell below is the production forge - `Engine.forge(size)`, dressed, default pool, no locks, the page's forge button - graded against evidence the build already carries. Rank 0 is the roster the button returns; ranks 1+ are what refresh walks (`forge(avoid=)`).

**Read before ruling:** the evidence cell is killer parties of the same size (+-2) and, at 10+, the same identity label; it is win-conditioned evidence of what is FIELDED, never a ruling, and prevalence is popularity, not effectiveness. A forged weapon nobody fields is a question, never an error. `holdout` cells use only battles with `id % 5 == 0` (the slice the meta prior never saw); `all` cells were too thin for that and use every battle. Nothing in the build reads this file.

## Summary board (rank-0 roster per cell)

| content | size | style | feasible | filler/held | roles H/F/S/D | roles vs cell | identity read | kill | weak stages | board R/O/G/P | floors | never fielded | rare | pairs seen | nearest | cell (n, split) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| castle_outpost | 5 | balanced | yes | 0/0 | 1/2/0/2 | all in | clap | ready | 0 | 3/5/15/0 | 0 | 0 | 2 | 40% | 0.33 | 900, holdout |
| castle_outpost | 5 | brawl | yes | 0/0 | 1/2/0/2 | all in | brawl | partial | 1 | 4/5/14/0 | 0 | 0 | 1 | 50% | 0.43 | 900, holdout |
| castle_outpost | 5 | clap | yes | 0/0 | 1/2/0/2 | all in | clap | ready | 0 | 2/4/17/0 | 0 | 0 | 2 | 30% | 0.25 | 900, holdout |
| castle_outpost | 5 | kite | yes | 0/0 | 1/2/0/2 | all in | **clap** | ready | 0 | 4/4/15/0 | 0 | 0 | 1 | 40% | 0.33 | 900, holdout |
| castle_outpost | 7 | balanced | yes | 0/0 | 1/2/1/3 | S:over | clap | ready | 0 | 1/3/19/0 | 0 | 0 | 1 | 62% | 0.33 | 1140, holdout |
| castle_outpost | 7 | brawl | yes | 0/0 | 1/2/1/3 | S:over | brawl | ready | 1 | 4/3/16/0 | 0 | 0 | 1 | 71% | 0.50 | 1140, holdout |
| castle_outpost | 7 | clap | yes | 0/0 | 1/2/1/3 | S:over | clap | ready | 0 | 1/4/18/0 | 0 | 0 | 1 | 62% | 0.33 | 1140, holdout |
| castle_outpost | 7 | kite | yes | 0/0 | 1/2/0/4 | D:over | **clap** | ready | 0 | 2/5/16/0 | 0 | 0 | 1 | 33% | 0.27 | 1140, holdout |
| roads | 7 | balanced | yes | 0/0 | 1/1/2/3 | F:under,S:over | brawl | ready | 0 | 1/0/25/2 | 0 | 0 | 2 | 43% | 0.33 | 1140, holdout |
| roads | 7 | brawl | yes | 0/0 | 1/2/2/2 | S:over,D:under | brawl | ready | 0 | 2/0/22/4 | 0 | 0 | 4 | 24% | 0.20 | 1140, holdout |
| roads | 7 | clap | yes | 0/0 | 1/3/1/2 | F:over,D:under | clap | ready | 0 | 2/0/24/2 | 0 | 0 | 3 | 29% | 0.23 | 1140, holdout |
| roads | 7 | kite | yes | 0/0 | 1/3/1/2 | F:over,D:under | **clap** | ready | 0 | 1/0/24/3 | 0 | 0 | 4 | 14% | 0.33 | 1140, holdout |
| faction_war | 10 | balanced | yes | 0/0 | 2/2/1/5 | all in | brawl | ready | 0 | 0/1/22/0 | 0 | 0 | 1 | 51% | 0.29 | 510, holdout |
| faction_war | 10 | brawl | yes | 0/0 | 2/2/1/5 | all in | brawl | ready | 0 | 0/1/21/1 | 0 | 2 | 2 | 11% | 0.23 | 61, holdout |
| faction_war | 10 | clap | yes | 0/0 | 2/2/1/5 | all in | clap | ready | 0 | 0/1/20/1 | 0 | 0 | 1 | 24% | 0.25 | 108, holdout |
| faction_war | 10 | kite | yes | 0/0 | 1/2/1/6 | all in | **clap** | ready | 0 | 0/4/17/1 | 1 | 1 | 0 | 4% | 0.25 | 41, holdout |
| faction_war | 10 | brawl_clap | yes | 0/0 | 2/2/0/6 | all in | **brawl** | ready | 0 | 0/2/19/2 | 0 | 4 | 0 | 0% | 0.17 | 17, all |
| faction_war | 10 | clap_kite | yes | 0/0 | 2/2/1/5 | all in | **clap** | ready | 0 | 0/4/17/1 | 0 | 1 | 0 | 40% | 0.38 | 36, all |
| faction_war | 15 | balanced | yes | 0/0 | 3/3/2/7 | all in | brawl | ready | 0 | 0/4/20/0 | 0 | 0 | 1 | 66% | 0.29 | 415, holdout |
| faction_war | 15 | brawl | yes | 0/0 | 3/3/1/8 | all in | brawl | ready | 0 | 0/3/20/0 | 0 | 1 | 0 | 32% | 0.38 | 87, holdout |
| faction_war | 15 | clap | yes | 0/0 | 3/3/1/8 | all in | clap | ready | 0 | 0/2/19/1 | 0 | 0 | 1 | 74% | 0.46 | 176, holdout |
| faction_war | 15 | kite | yes | 0/0 | 3/4/1/7 | all in | **clap** | ready | 0 | 0/5/17/1 | 0 | 0 | 1 | 60% | 0.39 | 176, all |
| faction_war | 15 | brawl_clap | yes | 0/0 | 3/3/1/8 | all in | **split** | ready | 0 | 0/2/21/1 | 0 | 3 | 0 | 13% | 0.23 | 26, all |
| faction_war | 15 | clap_kite | yes | 0/0 | 3/3/2/7 | all in | **clap** | ready | 0 | 1/3/19/0 | 0 | 2 | 0 | 55% | 0.43 | 43, holdout |
| blackzone_roam | 10 | balanced | yes | 0/0 | 2/2/1/5 | all in | clap_kite | ready | 0 | 0/1/27/0 | 0 | 0 | 0 | 60% | 0.27 | 510, holdout |
| blackzone_roam | 10 | brawl | yes | 0/0 | 2/2/1/5 | all in | brawl | ready | 0 | 0/4/22/2 | 0 | 1 | 1 | 18% | 0.31 | 61, holdout |
| blackzone_roam | 10 | clap | yes | 0/0 | 2/2/1/5 | all in | clap | ready | 0 | 0/2/25/1 | 0 | 0 | 2 | 13% | 0.25 | 108, holdout |
| blackzone_roam | 10 | kite | yes | 0/0 | 1/2/1/6 | all in | kite | ready | 0 | 0/5/23/0 | 1 | 1 | 0 | 7% | 0.25 | 41, holdout |
| blackzone_roam | 10 | brawl_clap | yes | 0/0 | 2/2/0/6 | all in | **brawl** | ready | 0 | 0/2/25/1 | 0 | 3 | 0 | 4% | 0.23 | 17, all |
| blackzone_roam | 10 | clap_kite | yes | 0/0 | 2/2/1/5 | all in | **clap** | ready | 0 | 1/8/19/0 | 0 | 1 | 0 | 24% | 0.29 | 36, all |
| blackzone_roam | 15 | balanced | yes | 0/0 | 3/3/2/7 | all in | clap | ready | 0 | 0/4/26/0 | 0 | 0 | 0 | 78% | 0.38 | 415, holdout |
| blackzone_roam | 15 | brawl | yes | 0/0 | 3/3/2/7 | all in | brawl | ready | 0 | 0/3/25/1 | 0 | 1 | 0 | 35% | 0.32 | 87, holdout |
| blackzone_roam | 15 | clap | yes | 0/0 | 3/3/2/7 | all in | clap | ready | 0 | 0/4/23/1 | 0 | 0 | 2 | 64% | 0.39 | 176, holdout |
| blackzone_roam | 15 | kite | yes | 0/0 | 3/4/2/6 | all in | kite | ready | 0 | 0/5/23/1 | 0 | 1 | 1 | 54% | 0.33 | 176, all |
| blackzone_roam | 15 | brawl_clap | yes | 0/0 | 3/3/1/8 | all in | **brawl** | ready | 0 | 0/2/27/1 | 0 | 4 | 0 | 19% | 0.23 | 26, all |
| blackzone_roam | 15 | clap_kite | yes | 0/0 | 3/4/2/6 | all in | **clap** | ready | 0 | 1/11/15/1 | 0 | 2 | 0 | 50% | 0.39 | 43, holdout |
| blackzone_roam | 20 | balanced | yes | 0/0 | 4/4/2/10 | all in | clap | ready | 0 | 0/2/28/0 | 0 | 0 | 2 | 61% | 0.33 | 357, holdout |
| blackzone_roam | 20 | brawl | yes | 0/0 | 4/4/2/10 | all in | brawl | ready | 0 | 0/5/23/1 | 0 | 4 | 0 | 28% | 0.34 | 43, holdout |
| blackzone_roam | 20 | clap | yes | 0/0 | 4/5/2/9 | all in | clap | ready | 0 | 0/3/23/2 | 0 | 1 | 3 | 54% | 0.36 | 155, holdout |
| blackzone_roam | 20 | kite | yes | 0/0 | 4/5/3/8 | all in | **clap** | ready | 0 | 1/6/20/2 | 0 | 2 | 2 | 49% | 0.36 | 125, all |
| blackzone_roam | 20 | brawl_clap | yes | 0/0 | 4/5/2/9 | all in | **brawl** | ready | 0 | 1/2/25/2 | 0 | 10 | 0 | 12% | 0.23 | 27, all |
| blackzone_roam | 20 | clap_kite | yes | 0/0 | 4/5/2/9 | all in | **clap** | ready | 0 | 0/7/21/1 | 0 | 3 | 2 | 41% | 0.34 | 79, holdout |
| territory_defense | 15 | balanced | yes | 0/0 | 3/3/2/7 | all in | clap | ready | 0 | 0/4/24/1 | 0 | 1 | 0 | 71% | 0.32 | 415, holdout |
| territory_defense | 15 | brawl | yes | 0/0 | 3/3/2/7 | all in | brawl | ready | 0 | 0/8/20/1 | 0 | 1 | 0 | 31% | 0.29 | 87, holdout |
| territory_defense | 15 | clap | yes | 0/0 | 3/3/2/7 | all in | clap | ready | 0 | 0/6/22/1 | 0 | 0 | 2 | 59% | 0.39 | 176, holdout |
| territory_defense | 15 | kite | yes | 0/0 | 3/4/2/6 | all in | kite | ready | 0 | 0/5/23/1 | 0 | 1 | 1 | 54% | 0.33 | 176, all |
| territory_defense | 15 | brawl_clap | yes | 0/0 | 3/3/2/7 | all in | **split** | ready | 0 | 0/6/21/3 | 0 | 3 | 0 | 18% | 0.28 | 26, all |
| territory_defense | 15 | clap_kite | yes | 0/0 | 3/4/2/6 | all in | **clap** | ready | 0 | 1/9/18/1 | 0 | 2 | 0 | 48% | 0.43 | 43, holdout |
| territory_defense | 20 | balanced | yes | 0/0 | 4/5/2/9 | all in | clap | ready | 0 | 0/2/26/1 | 0 | 1 | 2 | 59% | 0.36 | 357, holdout |
| territory_defense | 20 | brawl | yes | 0/0 | 4/4/2/10 | all in | brawl | ready | 0 | 0/7/21/1 | 0 | 4 | 0 | 24% | 0.30 | 43, holdout |
| territory_defense | 20 | clap | yes | 0/0 | 4/5/2/9 | all in | clap | ready | 0 | 0/5/21/2 | 0 | 0 | 4 | 55% | 0.36 | 155, holdout |
| territory_defense | 20 | kite | yes | 0/0 | 4/5/3/8 | all in | **clap_kite** | ready | 0 | 0/5/24/0 | 0 | 3 | 3 | 36% | 0.31 | 125, all |
| territory_defense | 20 | brawl_clap | yes | 0/0 | 4/5/2/9 | all in | **split** | ready | 0 | 0/4/22/3 | 0 | 8 | 0 | 16% | 0.22 | 27, all |
| territory_defense | 20 | clap_kite | yes | 0/0 | 4/6/2/8 | all in | clap_kite | ready | 0 | 1/3/24/0 | 0 | 1 | 1 | 64% | 0.50 | 79, holdout |
| territory_defense | 25 | balanced | yes | 0/0 | 5/8/2/10 | all in | clap | ready | 0 | 0/0/27/2 | 0 | 1 | 3 | 52% | 0.32 | 357, holdout, borrowed 20 |
| territory_defense | 25 | brawl | yes | 0/0 | 7/5/2/11 | all in | brawl | ready | 0 | 0/5/22/2 | 0 | 6 | 0 | 23% | 0.26 | 43, holdout, borrowed 20 |
| territory_defense | 25 | clap | yes | 0/0 | 6/5/2/12 | all in | clap | ready | 0 | 0/4/23/1 | 0 | 0 | 4 | 58% | 0.47 | 155, holdout, borrowed 20 |
| territory_defense | 25 | kite | yes | 0/0 | 7/5/2/11 | all in | **clap_kite** | ready | 0 | 1/8/18/1 | 0 | 2 | 3 | 43% | 0.34 | 125, all, borrowed 20 |
| territory_defense | 25 | brawl_clap | yes | 0/0 | 6/7/2/10 | all in | **clap** | ready | 0 | 0/3/23/3 | 0 | 8 | 0 | 18% | 0.29 | 27, all, borrowed 20 |
| territory_defense | 25 | clap_kite | yes | 0/0 | 6/8/2/9 | all in | clap_kite | ready | 0 | 1/6/19/2 | 0 | 1 | 3 | 52% | 0.54 | 79, holdout, borrowed 20 |
| castle | 20 | balanced | yes | 0/0 | 4/4/2/10 | all in | clap | ready | 0 | 0/2/21/1 | 0 | 0 | 2 | 58% | 0.33 | 357, holdout |
| castle | 20 | brawl | yes | 0/0 | 4/4/2/10 | all in | brawl | ready | 0 | 0/2/22/0 | 0 | 5 | 0 | 23% | 0.25 | 43, holdout |
| castle | 20 | clap | yes | 0/0 | 4/5/2/9 | all in | **clap_kite** | ready | 0 | 0/2/20/1 | 0 | 0 | 2 | 70% | 0.36 | 155, holdout |
| castle | 20 | kite | yes | 0/0 | 4/5/2/9 | S:under,D:over | **clap** | ready | 0 | 0/4/18/1 | 0 | 4 | 2 | 34% | 0.31 | 125, all |
| castle | 20 | brawl_clap | yes | 0/0 | 4/5/1/10 | S:under | **split** | ready | 0 | 0/2/19/3 | 0 | 7 | 0 | 16% | 0.22 | 27, all |
| castle | 20 | clap_kite | yes | 0/0 | 4/5/2/9 | all in | **clap** | ready | 0 | 1/2/17/3 | 0 | 1 | 2 | 63% | 0.48 | 79, holdout |
| castle | 25 | balanced | yes | 0/0 | 5/7/2/11 | all in | clap | ready | 0 | 0/0/24/0 | 0 | 1 | 2 | 54% | 0.32 | 357, holdout, borrowed 20 |
| castle | 25 | brawl | yes | 0/0 | 7/5/3/10 | all in | brawl | ready | 0 | 1/3/19/1 | 0 | 6 | 0 | 20% | 0.26 | 43, holdout, borrowed 20 |
| castle | 25 | clap | yes | 0/0 | 6/5/2/12 | all in | clap | ready | 0 | 0/3/19/1 | 0 | 1 | 3 | 53% | 0.34 | 155, holdout, borrowed 20 |
| castle | 25 | kite | yes | 0/0 | 7/5/3/10 | all in | **clap** | ready | 0 | 0/5/14/3 | 0 | 2 | 2 | 53% | 0.45 | 125, all, borrowed 20 |
| castle | 25 | brawl_clap | yes | 0/0 | 6/7/2/10 | all in | **clap** | ready | 0 | 0/2/20/2 | 0 | 10 | 0 | 16% | 0.26 | 27, all, borrowed 20 |
| castle | 25 | clap_kite | yes | 0/0 | 6/7/2/10 | all in | **clap** | ready | 0 | 1/5/15/2 | 0 | 1 | 3 | 54% | 0.54 | 79, holdout, borrowed 20 |

Columns: roles = healer / frontline / support / dps by `role_of`; roles vs cell = roles outside the harvest [p10, p90] for that style x size (H/F/S/D:under|over); identity read = `comp_identity` on the forged roster (bold = disagrees with the style forged for); board = capability rows under min / under typical / at typical / past soft cap; never fielded = forged weapons with zero rosters in the evidence cell; rare = under 2% of the cell's distinct rosters; pairs seen = share of distinct forged weapon pairs seen together in >= 3 rosters; nearest = multiset Jaccard to the closest harvested roster.

## Aggregates over rank-0 rosters

- cells: 72; infeasible: 0; with filler slots: 0; with held slots: 0
- identity agrees with the forged-for style: 30/59 styled cells
- kill checklist: partial 1, ready 71
- slots: 1126; never fielded in the cell: 129 (11%); rare (< 2%): 89 (8%)
- median pair share 43%; median nearest-roster Jaccard 0.33
- cells where a refresh alternative OUTSCORES the button's roster: 25 (castle_outpost/5/brawl, roads/7/clap, roads/7/kite, faction_war/10/brawl_clap, faction_war/15/balanced, faction_war/15/brawl, faction_war/15/brawl_clap, blackzone_roam/10/balanced, blackzone_roam/10/brawl, blackzone_roam/10/clap_kite, blackzone_roam/15/brawl, blackzone_roam/15/clap, blackzone_roam/15/clap_kite, blackzone_roam/20/balanced, blackzone_roam/20/clap, blackzone_roam/20/kite, territory_defense/20/balanced, territory_defense/20/clap, territory_defense/20/brawl_clap, territory_defense/25/clap, territory_defense/25/brawl_clap, castle/20/brawl, castle/20/brawl_clap, castle/25/balanced, castle/25/brawl_clap)
- roles outside the cell's [p10, p90]: support over x5, dps under x3, dps over x2, frontline over x2, support under x2, frontline under x1
- rows under the bare minimum most often: damage_debuff x8, anti_dive x6, root x5, tankiness x5, cleanse x4, heal_sustain x3, burst_aoe x2, max_health_cut x2
- rows past the soft cap most often: catch x27, clump_create x12, root x6, purge x5, stun x4, heal_reduction x4, silence x4, damage_debuff x3
- weapons the forge reaches for most (cells containing it): 2H_HAMMER_AVALON x63, 2H_HOLYSTAFF_HELL x59, 2H_AXE_AVALON x56, 2H_KNUCKLES_AVALON x56, 2H_MACE x55, 2H_FIRE_RINGPAIR_AVALON x45, 2H_POLEHAMMER x43, 2H_KNUCKLES_SET3 x41, 2H_HOLYSTAFF_CRYSTAL x41, 2H_HALBERD_MORGANA x35, 2H_KNUCKLES_HELL x34, 2H_ICECRYSTAL_UNDEAD x33, 2H_SHAPESHIFTER_SET2 x33, 2H_HAMMER x33, 2H_QUARTERSTAFF_AVALON x29
- forged but never fielded in its cell, by weapon: 2H_KNUCKLES_AVALON x22, 2H_SCYTHE_CRYSTAL x13, 2H_HOLYSTAFF x12, 2H_HALBERD_MORGANA x12, 2H_REPEATINGCROSSBOW_UNDEAD x10, 2H_QUARTERSTAFF_AVALON x10, 2H_CLAYMORE_AVALON x9, 2H_GLAIVE_CRYSTAL x5, 2H_KNUCKLES_HELL x4, 2H_BOW_CRYSTAL x4, MAIN_NATURESTAFF_CRYSTAL x3, 2H_HAMMER_AVALON x3, MAIN_ARCANESTAFF_UNDEAD x3, 2H_ARCANESTAFF_HELL x3, 2H_SHAPESHIFTER_AVALON x3

## Cells

### Castle Outpost - 5 - balanced

Evidence cell: 900 distinct rosters (944 sightings, holdout); role row: `pooled[5] (harvest, healer row only below 10)`.

**rank 0 (the button)** - score 58.429, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [2%], Heavy Mace [16%], Dawnsong [13%], Crystal Reaper [1%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red cleanse, damage_debuff, root; orange burst_aoe, peel, resist_shred, stun, sustained_dps; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON, 2H_SCYTHE_CRYSTAL; pairs seen 4/10; nearest roster Jaccard 0.33 (size 7)

**rank 1 (refresh, 1 slots differ)** - score 58.278, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [2%], Heavy Mace [16%], Dawnsong [13%], Carving Sword [7%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: split (None); conflicts: 2H_CLEAVER_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red cleanse, damage_debuff, heal_sustain; orange burst_aoe, root, stun, sustained_dps; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON; pairs seen 6/10; nearest roster Jaccard 0.33 (size 7)

**rank 2 (refresh, 1 slots differ)** - score 58.054, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [2%], Heavy Mace [16%], Dawnsong [13%], Weeping Repeater [0%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red cleanse, damage_debuff, root; orange burst_aoe, peel, resist_shred, stun; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD; pairs seen 4/10; nearest roster Jaccard 0.33 (size 7)

### Castle Outpost - 5 - brawl

Evidence cell: 900 distinct rosters (944 sightings, holdout); role row: `pooled[5] (harvest, healer row only below 10)`.

**rank 0 (the button)** - score 59.729, feasible True, filler [], held []

- roster: Fallen Staff [3%], Carrioncaller [9%], Kingmaker [6%], Heavy Mace [16%], Hand of Justice [2%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: brawl (strong)
- kill checklist: partial (pierce True, heal-cut True, burst False); weak stages: Sustain:weak
- board: red burst_aoe, cleanse, damage_debuff, heal_sustain; orange peel, root, silence, stun, sustained_dps; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON; pairs seen 5/10; nearest roster Jaccard 0.43 (size 5)

**rank 1 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 59.775, feasible True, filler [], held []

- roster: Rampant Staff [1%], Heavy Mace [16%], Carrioncaller [9%], Grovekeeper [0%], Witchwork Staff [5%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 3 (p10 0 / p50 1 / p90 2) over; support 0 (p10 0 / p50 0 / p90 1) in; dps 1 (p10 2 / p50 3 / p90 4) under
- identity: clap (strong) - DISAGREES with brawl
- kill checklist: partial (pierce True, heal-cut True, burst False); weak stages: Pressure:weak
- board: red burst_aoe, damage_debuff, heal_burst, root, sustained_dps; orange peel, resist_shred, silence; purple cleanse, heal_sustain
- evidence: never fielded -; rare 2H_NATURESTAFF_KEEPER, 2H_RAM_KEEPER; pairs seen 2/10; nearest roster Jaccard 0.43 (size 5)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 59.751, feasible True, filler [], held []

- roster: Rampant Staff [1%], Realmbreaker [8%], Hellfire Hands [2%], Heavy Mace [16%], Hand of Justice [2%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong) - DISAGREES with brawl
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red burst_aoe, cleanse, damage_debuff, heal_burst, root; orange peel, resist_shred, silence, stun; purple heal_sustain
- evidence: never fielded -; rare 2H_NATURESTAFF_KEEPER, 2H_HAMMER_AVALON; pairs seen 4/10; nearest roster Jaccard 0.43 (size 5)

### Castle Outpost - 5 - clap

Evidence cell: 900 distinct rosters (944 sightings, holdout); role row: `pooled[5] (harvest, healer row only below 10)`.

**rank 0 (the button)** - score 63.2, feasible True, filler [], held []

- roster: Nature Staff [2%], Dawnsong [13%], Arclight Blasters [1%], Heavy Mace [16%], Hand of Justice [2%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, heal_sustain; orange burst_aoe, resist_shred, sustained_dps, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL, 2H_HAMMER_AVALON; pairs seen 3/10; nearest roster Jaccard 0.25 (size 5)

**rank 1 (refresh, 2 slots differ)** - score 63.129, feasible True, filler [], held []

- roster: Fallen Staff [3%], Dawnsong [13%], Hand of Justice [2%], Dreadstorm Monarch [1%], Arclight Blasters [1%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, heal_sustain; orange burst_aoe, peel, resist_shred, sustained_dps, tankiness; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON, MAIN_MACE_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL; pairs seen 2/10; nearest roster Jaccard 0.25 (size 5)

**rank 2 (refresh, 1 slots differ)** - score 63.079, feasible True, filler [], held []

- roster: Fallen Staff [3%], Dawnsong [13%], Arclight Blasters [1%], Heavy Mace [16%], Hand of Justice [2%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, heal_sustain, root; orange burst_aoe, resist_shred, sustained_dps, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL, 2H_HAMMER_AVALON; pairs seen 4/10; nearest roster Jaccard 0.33 (size 7)

### Castle Outpost - 5 - kite

Evidence cell: 900 distinct rosters (944 sightings, holdout); role row: `pooled[5] (harvest, healer row only below 10)`.

**rank 0 (the button)** - score 56.19, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [2%], Dawnsong [13%], Heavy Mace [16%], Forge Hammers [4%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red burst_aoe, cleanse, damage_debuff, root; orange peel, resist_shred, stun, sustained_dps; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON; pairs seen 4/10; nearest roster Jaccard 0.33 (size 7)

**rank 1 (refresh, 1 slots differ)** - score 55.998, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [2%], Dawnsong [13%], Heavy Mace [16%], Weeping Repeater [0%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red cleanse, damage_debuff, root; orange burst_aoe, peel, resist_shred, stun; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD; pairs seen 4/10; nearest roster Jaccard 0.33 (size 7)

**rank 2 (refresh, 1 slots differ)** - score 55.954, feasible True, filler [], held []

- roster: Nature Staff [2%], Hand of Justice [2%], Dawnsong [13%], Heavy Mace [16%], Forge Hammers [4%]
- roles: healer 1 (p10 0 / p50 1 / p90 1) in; frontline 2 (p10 0 / p50 1 / p90 2) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 2 (p10 2 / p50 3 / p90 4) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red burst_aoe, cleanse, damage_debuff; orange peel, resist_shred, root, stun, sustained_dps; purple -
- evidence: never fielded -; rare 2H_HAMMER_AVALON; pairs seen 3/10; nearest roster Jaccard 0.25 (size 5)

### Castle Outpost - 7 - balanced

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[castle_outpost][7]`.

**rank 0 (the button)** - score 60.753, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [3%], Heavy Mace [16%], Dawnsong [14%], Rootbound Staff [9%], Arclight Blasters [1%], Permafrost Prism [13%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff; orange root, slow, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 13/21; nearest roster Jaccard 0.33 (size 9)

**rank 1 (refresh, 1 slots differ)** - score 60.674, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [3%], Heavy Mace [16%], Dawnsong [14%], Rootbound Staff [9%], Arclight Blasters [1%], Realmbreaker [10%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, root; orange slow, sustained_dps, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 13/21; nearest roster Jaccard 0.33 (size 9)

**rank 2 (refresh, 1 slots differ)** - score 60.665, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [3%], Heavy Mace [16%], Dawnsong [14%], Rootbound Staff [9%], Arclight Blasters [1%], Battle Bracers [9%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: clap (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, root; orange slow, sustained_dps, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 11/21; nearest roster Jaccard 0.40 (size 7)

### Castle Outpost - 7 - brawl

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[castle_outpost][7]`.

**rank 0 (the button)** - score 62.236, feasible True, filler [], held []

- roster: Redemption Staff [27%], Hand of Justice [3%], Heavy Mace [16%], Halberd [2%], Realmbreaker [10%], Great Arcane Staff [4%], Kingmaker [6%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True); weak stages: Sustain:weak
- board: red cleanse, damage_debuff, root, zone_control; orange burst_aoe, heal_sustain, slow; purple -
- evidence: never fielded -; rare 2H_HALBERD; pairs seen 15/21; nearest roster Jaccard 0.50 (size 5)

**rank 1 (refresh, 1 slots differ)** - score 62.212, feasible True, filler [], held []

- roster: Great Holy Staff [4%], Hand of Justice [3%], Heavy Mace [16%], Halberd [2%], Realmbreaker [10%], Great Arcane Staff [4%], Kingmaker [6%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True); weak stages: Sustain:weak
- board: red cleanse, damage_debuff, root, zone_control; orange burst_aoe, heal_sustain, slow, sustained_dps; purple -
- evidence: never fielded -; rare 2H_HALBERD; pairs seen 12/21; nearest roster Jaccard 0.33 (size 9)

**rank 2 (refresh, 1 slots differ)** - score 62.197, feasible True, filler [], held []

- roster: Rampant Staff [1%], Hand of Justice [3%], Heavy Mace [16%], Halberd [2%], Realmbreaker [10%], Great Arcane Staff [4%], Kingmaker [6%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, heal_burst, root; orange burst_aoe, tankiness, zone_control; purple cleanse
- evidence: never fielded -; rare 2H_NATURESTAFF_KEEPER, 2H_HALBERD; pairs seen 10/21; nearest roster Jaccard 0.33 (size 5)

### Castle Outpost - 7 - clap

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[castle_outpost][7]`.

**rank 0 (the button)** - score 65.541, feasible True, filler [], held []

- roster: Hand of Justice [3%], Fallen Staff [3%], Heavy Mace [16%], Dawnsong [14%], Arclight Blasters [1%], Rootbound Staff [9%], Permafrost Prism [13%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff; orange burst_aoe, root, slow, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 13/21; nearest roster Jaccard 0.33 (size 9)

**rank 1 (refresh, 1 slots differ)** - score 65.432, feasible True, filler [], held []

- roster: Hand of Justice [3%], Fallen Staff [3%], Heavy Mace [16%], Dawnsong [14%], Arclight Blasters [1%], Rootbound Staff [9%], Wailing Bow [4%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff; orange burst_aoe, peel, root, sustained_dps, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 10/21; nearest roster Jaccard 0.33 (size 5)

**rank 2 (refresh, 1 slots differ)** - score 65.375, feasible True, filler [], held []

- roster: Hand of Justice [3%], Fallen Staff [3%], Heavy Mace [16%], Dawnsong [14%], Arclight Blasters [1%], Weeping Repeater [0%], Permafrost Prism [13%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 0 (p10 0 / p50 0 / p90 0.8) in; dps 4 (p10 3 / p50 3 / p90 3.8) over
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, heal_sustain, root; orange burst_aoe, slow, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL, 2H_REPEATINGCROSSBOW_UNDEAD; pairs seen 9/21; nearest roster Jaccard 0.33 (size 9)

### Castle Outpost - 7 - kite

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[castle_outpost][7]`.

**rank 0 (the button)** - score 58.786, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [3%], Heavy Mace [16%], Dawnsong [14%], Forge Hammers [4%], Dual Swords [4%], Arclight Blasters [1%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 0 (p10 0 / p50 0 / p90 0.8) in; dps 4 (p10 3 / p50 3 / p90 3.8) over
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, heal_sustain; orange burst_aoe, peel, root, sustained_dps, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 7/21; nearest roster Jaccard 0.27 (size 7)

**rank 1 (refresh, 2 slots differ)** - score 58.658, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [3%], Heavy Mace [16%], Dawnsong [14%], Rootbound Staff [9%], Arclight Blasters [1%], Permafrost Prism [13%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 1 (p10 0 / p50 0 / p90 0.8) over; dps 3 (p10 3 / p50 3 / p90 3.8) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff; orange burst_aoe, peel, root, slow, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 13/21; nearest roster Jaccard 0.33 (size 9)

**rank 2 (refresh, 1 slots differ)** - score 58.639, feasible True, filler [], held []

- roster: Fallen Staff [3%], Hand of Justice [3%], Heavy Mace [16%], Dawnsong [14%], Forge Hammers [4%], Permafrost Prism [13%], Arclight Blasters [1%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2.8) in; support 0 (p10 0 / p50 0 / p90 0.8) in; dps 4 (p10 3 / p50 3 / p90 3.8) over
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red damage_debuff, heal_sustain, root; orange burst_aoe, peel, tankiness; purple -
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL; pairs seen 11/21; nearest roster Jaccard 0.33 (size 9)

### Roads of Avalon - 7 - balanced

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[roads][7]`.

**rank 0 (the button)** - score 72.135, feasible True, filler [], held []

- roster: Blight Staff [16%], Rootbound Staff [9%], Incubus Mace [8%], Arclight Blasters [1%], Hoarfrost Staff [0%], Kingmaker [6%], Bow of Badon [11%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 1 (p10 2 / p50 2 / p90 2) under; support 2 (p10 1 / p50 1 / p90 1) over; dps 3 (p10 3 / p50 3 / p90 3) in
- identity: brawl (leaning); conflicts: 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange -; purple self_sustain, sustained_dps; optional short execute
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL, MAIN_FROSTSTAFF_KEEPER; pairs seen 9/21; nearest roster Jaccard 0.33 (size 5)

**rank 1 (refresh, 2 slots differ)** - score 71.983, feasible True, filler [], held []

- roster: Tombhammer [1%], Blight Staff [16%], Rootbound Staff [9%], Incubus Mace [8%], Kingmaker [6%], Arclight Blasters [1%], Cursed Staff [5%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2) in; support 2 (p10 1 / p50 1 / p90 1) over; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: split (None); conflicts: 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive, knockback_displace; orange -; purple catch, max_health_cut, self_sustain, stun, sustained_dps; optional short execute
- evidence: never fielded -; rare 2H_HAMMER_UNDEAD, 2H_DUALCROSSBOW_CRYSTAL; pairs seen 7/21; nearest roster Jaccard 0.33 (size 5)

**rank 2 (refresh, 3 slots differ)** - score 71.877, feasible True, filler [], held []

- roster: Tombhammer [1%], Wild Staff [1%], Rootbound Staff [9%], Incubus Mace [8%], Kingmaker [6%], Arclight Blasters [1%], Cursed Staff [5%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2) in; support 2 (p10 1 / p50 1 / p90 1) over; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: split (None); conflicts: 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive, knockback_displace; orange -; purple catch, max_health_cut, self_sustain, stun, sustained_dps; optional short execute
- evidence: never fielded -; rare 2H_HAMMER_UNDEAD, 2H_WILDSTAFF, 2H_DUALCROSSBOW_CRYSTAL; pairs seen 3/21; nearest roster Jaccard 0.20 (size 5)

### Roads of Avalon - 7 - brawl

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[roads][7]`.

**rank 0 (the button)** - score 75.84, feasible True, filler [], held []

- roster: Rampant Staff [1%], Incubus Mace [8%], Infernal Scythe [2%], Arcane Staff [2%], Twin Slayers [1%], Mace [20%], Rootbound Staff [9%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2) in; support 2 (p10 1 / p50 1 / p90 1) over; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: brawl (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive, knockback_displace; orange -; purple catch, cleanse, self_sustain, stun; optional short execute
- evidence: never fielded -; rare 2H_NATURESTAFF_KEEPER, 2H_SCYTHE_HELL, MAIN_ARCANESTAFF, 2H_DAGGERPAIR_CRYSTAL; pairs seen 5/21; nearest roster Jaccard 0.20 (size 5)

**rank 1 (refresh, 1 slots differ)** - score 75.523, feasible True, filler [], held []

- roster: Rampant Staff [1%], Incubus Mace [8%], Infernal Scythe [2%], Arcane Staff [2%], Mace [20%], Stillgaze Staff [0%], Twin Slayers [1%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 3 (p10 2 / p50 2 / p90 2) over; support 1 (p10 1 / p50 1 / p90 1) in; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: brawl (leaning); conflicts: MAIN_ARCANESTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive, slow; orange -; purple catch, cleanse, mobility, self_sustain, stun; optional short execute
- evidence: never fielded -; rare 2H_NATURESTAFF_KEEPER, 2H_SCYTHE_HELL, MAIN_ARCANESTAFF, 2H_SHAPESHIFTER_CRYSTAL, 2H_DAGGERPAIR_CRYSTAL; pairs seen 3/21; nearest roster Jaccard 0.20 (size 5)

**rank 2 (refresh, 2 slots differ)** - score 75.639, feasible True, filler [], held []

- roster: Rampant Staff [1%], Incubus Mace [8%], Infernal Scythe [2%], Arcane Staff [2%], Rootbound Staff [9%], Witchwork Staff [5%], Fists of Avalon [3%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2) in; support 2 (p10 1 / p50 1 / p90 1) over; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: brawl (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive, root; orange -; purple cleanse, engage, self_sustain; optional short execute
- evidence: never fielded -; rare 2H_NATURESTAFF_KEEPER, 2H_SCYTHE_HELL, MAIN_ARCANESTAFF; pairs seen 2/21; nearest roster Jaccard 0.20 (size 5)

### Roads of Avalon - 7 - clap

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[roads][7]`.

**rank 0 (the button)** - score 72.213, feasible True, filler [], held []

- roster: Great Hammer [5%], Blight Staff [16%], Witchwork Staff [5%], Incubus Mace [8%], Arcane Staff [2%], Brimstone Staff [2%], Arclight Blasters [1%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 3 (p10 2 / p50 2 / p90 2) over; support 1 (p10 1 / p50 1 / p90 1) in; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive, buff_allies; orange -; purple cleanse, engage; optional short execute
- evidence: never fielded -; rare MAIN_ARCANESTAFF, 2H_FIRESTAFF_HELL, 2H_DUALCROSSBOW_CRYSTAL; pairs seen 6/21; nearest roster Jaccard 0.23 (size 9)

**rank 1 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 72.356, feasible True, filler [], held []

- roster: Great Hammer [5%], Blight Staff [16%], Stillgaze Staff [0%], Incubus Mace [8%], Arcane Staff [2%], Brimstone Staff [2%], Astral Staff [3%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 3 (p10 2 / p50 2 / p90 2) over; support 1 (p10 1 / p50 1 / p90 1) in; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: kite (strong) - DISAGREES with clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange -; purple cleanse; optional short execute
- evidence: never fielded -; rare 2H_SHAPESHIFTER_CRYSTAL, MAIN_ARCANESTAFF, 2H_FIRESTAFF_HELL; pairs seen 5/21; nearest roster Jaccard 0.27 (size 7)

**rank 2 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 72.32, feasible True, filler [], held []

- roster: Great Hammer [5%], Blight Staff [16%], Stillgaze Staff [0%], Incubus Mace [8%], Arcane Staff [2%], Brimstone Staff [2%], Enigmatic Staff [2%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 3 (p10 2 / p50 2 / p90 2) over; support 2 (p10 1 / p50 1 / p90 1) over; dps 1 (p10 3 / p50 3 / p90 3) under
- identity: kite (strong) - DISAGREES with clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange -; purple cleanse; optional short execute
- evidence: never fielded -; rare 2H_SHAPESHIFTER_CRYSTAL, MAIN_ARCANESTAFF, 2H_FIRESTAFF_HELL, 2H_ENIGMATICSTAFF; pairs seen 5/21; nearest roster Jaccard 0.23 (size 9)

### Roads of Avalon - 7 - kite

Evidence cell: 1140 distinct rosters (1187 sightings, holdout); role row: `comps[roads][7]`.

**rank 0 (the button)** - score 76.141, feasible True, filler [], held []

- roster: Blight Staff [16%], Stillgaze Staff [0%], Incubus Mace [8%], Arclight Blasters [1%], Arcane Staff [2%], Truebolt Hammer [1%], Forge Hammers [4%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 3 (p10 2 / p50 2 / p90 2) over; support 1 (p10 1 / p50 1 / p90 1) in; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange -; purple catch, heal_sustain, purge; optional short execute
- evidence: never fielded -; rare 2H_SHAPESHIFTER_CRYSTAL, 2H_DUALCROSSBOW_CRYSTAL, MAIN_ARCANESTAFF, 2H_HAMMER_CRYSTAL; pairs seen 3/21; nearest roster Jaccard 0.33 (size 5)

**rank 1 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 76.252, feasible True, filler [], held []

- roster: Blight Staff [16%], Incubus Mace [8%], Arclight Blasters [1%], Arcane Staff [2%], Forge Hammers [4%], Stillgaze Staff [0%], Rootbound Staff [9%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2) in; support 2 (p10 1 / p50 1 / p90 1) over; dps 2 (p10 3 / p50 3 / p90 3) under
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange -; purple -; optional short execute
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL, MAIN_ARCANESTAFF, 2H_SHAPESHIFTER_CRYSTAL; pairs seen 6/21; nearest roster Jaccard 0.33 (size 5)

**rank 2 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 76.294, feasible True, filler [], held []

- roster: Blight Staff [16%], Incubus Mace [8%], Arclight Blasters [1%], Arcane Staff [2%], Forge Hammers [4%], Stillgaze Staff [0%], Lightcaller [5%]
- roles: healer 1 (p10 1 / p50 1 / p90 1) in; frontline 2 (p10 2 / p50 2 / p90 2) in; support 1 (p10 1 / p50 1 / p90 1) in; dps 3 (p10 3 / p50 3 / p90 3) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange -; purple mobility; optional short execute
- evidence: never fielded -; rare 2H_DUALCROSSBOW_CRYSTAL, MAIN_ARCANESTAFF, 2H_SHAPESHIFTER_CRYSTAL; pairs seen 5/21; nearest roster Jaccard 0.33 (size 5)

### Faction War (Red Zone) - 10 - balanced

Evidence cell: 510 distinct rosters (515 sightings, holdout); role row: `pooled[10]`.

**rank 0 (the button)** - score 68.783, feasible True, filler [], held []

- roster: Hand of Justice [8%], Wild Staff [2%], Great Hammer [6%], Dawnsong [19%], Hallowfall [47%], Battle Bracers [20%], Fists of Avalon [4%], Icicle Staff [6%], Carrioncaller [2%], Kingmaker [6%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: brawl (leaning); conflicts: 2H_KNUCKLES_SET2, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies; purple -
- evidence: never fielded -; rare 2H_WILDSTAFF; pairs seen 23/45; nearest roster Jaccard 0.29 (size 8)

**rank 1 (refresh, 1 slots differ)** - score 68.655, feasible True, filler [], held []

- roster: Hand of Justice [8%], Wild Staff [2%], Great Hammer [6%], Dawnsong [19%], Hallowfall [47%], Battle Bracers [20%], Fists of Avalon [4%], Infernal Scythe [3%], Icicle Staff [6%], Carrioncaller [2%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: brawl (leaning); conflicts: 2H_KNUCKLES_SET2, 2H_SCYTHE_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies; purple -
- evidence: never fielded -; rare 2H_WILDSTAFF; pairs seen 20/45; nearest roster Jaccard 0.29 (size 12)

**rank 2 (refresh, 2 slots differ)** - score 68.553, feasible True, filler [], held []

- roster: Hand of Justice [8%], Wild Staff [2%], Great Hammer [6%], Dawnsong [19%], Hallowfall [47%], Battle Bracers [20%], Infernal Scythe [3%], Icicle Staff [6%], Carrioncaller [2%], Spiked Gauntlets [15%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: split (None); conflicts: 2H_KNUCKLES_SET2, 2H_SCYTHE_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, resist_shred; purple -
- evidence: never fielded -; rare 2H_WILDSTAFF; pairs seen 21/45; nearest roster Jaccard 0.29 (size 12)

### Faction War (Red Zone) - 10 - brawl

Evidence cell: 61 distinct rosters (61 sightings, holdout); role row: `styles[brawl][10]`.

**rank 0 (the button)** - score 70.873, feasible True, filler [], held []

- roster: Hallowfall [70%], Hand of Justice [2%], Polehammer [5%], Hellfire Hands [3%], Forgebark Staff [0%], Rotcaller Staff [2%], Battle Bracers [30%], Kingmaker [13%], Arcane Staff [0%], Fists of Avalon [12%]
- roles: healer 2 (p10 0.6 / p50 2 / p90 2.4) in; frontline 2 (p10 1 / p50 2 / p90 3.4) in; support 1 (p10 0 / p50 0 / p90 1) in; dps 5 (p10 4 / p50 6 / p90 7) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe; purple clump_create
- evidence: never fielded MAIN_NATURESTAFF_CRYSTAL, MAIN_ARCANESTAFF; rare 2H_HAMMER_AVALON, MAIN_CURSEDSTAFF_CRYSTAL; pairs seen 5/45; nearest roster Jaccard 0.23 (size 11)

**rank 1 (refresh, 2 slots differ)** - score 70.865, feasible True, filler [], held []

- roster: Hallowfall [70%], Hand of Justice [2%], Great Hammer [12%], Hellfire Hands [3%], Rampant Staff [3%], Rotcaller Staff [2%], Battle Bracers [30%], Kingmaker [13%], Arcane Staff [0%], Fists of Avalon [12%]
- roles: healer 2 (p10 0.6 / p50 2 / p90 2.4) in; frontline 2 (p10 1 / p50 2 / p90 3.4) in; support 1 (p10 0 / p50 0 / p90 1) in; dps 5 (p10 4 / p50 6 / p90 7) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe; purple clump_create
- evidence: never fielded MAIN_ARCANESTAFF; rare 2H_HAMMER_AVALON, MAIN_CURSEDSTAFF_CRYSTAL; pairs seen 5/45; nearest roster Jaccard 0.18 (size 10)

**rank 2 (refresh, 2 slots differ)** - score 70.826, feasible True, filler [], held []

- roster: Hallowfall [70%], Hand of Justice [2%], Great Hammer [12%], Hellfire Hands [3%], Hallowfall [70%], Rotcaller Staff [2%], Battle Bracers [30%], Kingmaker [13%], Arcane Staff [0%], Fists of Avalon [12%]
- roles: healer 2 (p10 0.6 / p50 2 / p90 2.4) in; frontline 2 (p10 1 / p50 2 / p90 3.4) in; support 1 (p10 0 / p50 0 / p90 1) in; dps 5 (p10 4 / p50 6 / p90 7) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe; purple clump_create
- evidence: never fielded MAIN_ARCANESTAFF; rare 2H_HAMMER_AVALON, MAIN_CURSEDSTAFF_CRYSTAL; pairs seen 5/36; nearest roster Jaccard 0.18 (size 10)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Faction War (Red Zone) - 10 - clap

Evidence cell: 108 distinct rosters (110 sightings, holdout); role row: `styles[clap][10]`.

**rank 0 (the button)** - score 74.218, feasible True, filler [], held []

- roster: Hand of Justice [15%], Rampant Staff [5%], Great Hammer [6%], Dawnsong [40%], Fists of Avalon [3%], Fallen Staff [14%], Icicle Staff [5%], Realmbreaker [46%], Permafrost Prism [47%], Carrioncaller [1%]
- roles: healer 2 (p10 1 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 5 / p90 7) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange peel; purple heal_reduction; optional short execute
- evidence: never fielded -; rare 2H_HALBERD_MORGANA; pairs seen 11/45; nearest roster Jaccard 0.25 (size 10)

**rank 1 (refresh, 1 slots differ)** - score 74.083, feasible True, filler [], held []

- roster: Hand of Justice [15%], Rampant Staff [5%], Great Hammer [6%], Dawnsong [40%], Fists of Avalon [3%], Fallen Staff [14%], Icicle Staff [5%], Realmbreaker [46%], Spirithunter [21%], Permafrost Prism [47%]
- roles: healer 2 (p10 1 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 5 / p90 7) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange peel, tankiness; purple -; optional short execute
- evidence: never fielded -; rare -; pairs seen 16/45; nearest roster Jaccard 0.29 (size 12)

**rank 2 (refresh, 2 slots differ)** - score 74.201, feasible True, filler [], held []

- roster: Hand of Justice [15%], Rampant Staff [5%], Great Hammer [6%], Fists of Avalon [3%], Fallen Staff [14%], Icicle Staff [5%], Carrioncaller [1%], Permafrost Prism [47%], Rotcaller Staff [11%], Wailing Bow [14%]
- roles: healer 2 (p10 1 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 5 / p90 7) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange tankiness; purple -; optional short execute
- evidence: never fielded -; rare 2H_HALBERD_MORGANA; pairs seen 5/45; nearest roster Jaccard 0.25 (size 10)

### Faction War (Red Zone) - 10 - kite

Evidence cell: 41 distinct rosters (41 sightings, holdout); role row: `styles[kite][10]`.

**rank 0 (the button)** - score 70.272, feasible True, filler [], held []

- roster: Fallen Staff [10%], Hand of Justice [10%], Hellfire Hands [12%], Heavy Mace [17%], Fists of Avalon [2%], Realmbreaker [22%], Rootbound Staff [10%], Spiked Gauntlets [7%], Permafrost Prism [10%], Weeping Repeater [0%]
- roles: healer 1 (p10 0.3 / p50 1 / p90 2) in; frontline 2 (p10 1 / p50 2 / p90 3) in; support 1 (p10 0 / p50 1 / p90 3.7) in; dps 6 (p10 2.3 / p50 5 / p90 7) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange cleanse, heal_burst, heal_sustain, peel; purple clump_create; optional short execute; ARMED FLOORS heal_sustain
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare -; pairs seen 2/45; nearest roster Jaccard 0.25 (size 10)

**rank 1 (refresh, 1 slots differ)** - score 70.238, feasible True, filler [], held []

- roster: Fallen Staff [10%], Hand of Justice [10%], Hellfire Hands [12%], Heavy Mace [17%], Fists of Avalon [2%], Realmbreaker [22%], Rootbound Staff [10%], Spiked Gauntlets [7%], Glacial Staff [2%], Weeping Repeater [0%]
- roles: healer 1 (p10 0.3 / p50 1 / p90 2) in; frontline 2 (p10 1 / p50 2 / p90 3) in; support 1 (p10 0 / p50 1 / p90 3.7) in; dps 6 (p10 2.3 / p50 5 / p90 7) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange cleanse, heal_burst, heal_sustain; purple clump_create; optional short execute; ARMED FLOORS heal_sustain
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare -; pairs seen 2/45; nearest roster Jaccard 0.22 (size 12)

**rank 2 (refresh, 3 slots differ)** - score 70.117, feasible True, filler [], held []

- roster: Fallen Staff [10%], Grovekeeper [0%], Hellfire Hands [12%], Great Hammer [2%], Fists of Avalon [2%], Realmbreaker [22%], Rootbound Staff [10%], Spiked Gauntlets [7%], Glacial Staff [2%], Weeping Repeater [0%]
- roles: healer 1 (p10 0.3 / p50 1 / p90 2) in; frontline 2 (p10 1 / p50 2 / p90 3) in; support 1 (p10 0 / p50 1 / p90 3.7) in; dps 6 (p10 2.3 / p50 5 / p90 7) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange cleanse, heal_burst, heal_sustain; purple catch, engage; optional short execute; ARMED FLOORS heal_sustain
- evidence: never fielded 2H_RAM_KEEPER, 2H_REPEATINGCROSSBOW_UNDEAD; rare -; pairs seen 1/45; nearest roster Jaccard 0.18 (size 10)

### Faction War (Red Zone) - 10 - brawl_clap

Evidence cell: 17 distinct rosters (20 sightings, all); role row: `pooled[10]`.

**rank 0 (the button)** - score 74.867, feasible True, filler [], held []

- roster: Hand of Justice [12%], Great Holy Staff [0%], Dawnsong [6%], Great Hammer [12%], Fists of Avalon [6%], Fallen Staff [0%], Crystal Reaper [0%], Kingmaker [0%], Battle Bracers [82%], Permafrost Prism [6%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 0 (p10 0 / p50 1 / p90 2) in; dps 6 (p10 3 / p50 6 / p90 7) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_FIRE_RINGPAIR_AVALON, 2H_ICECRYSTAL_UNDEAD
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, resist_shred; purple burst_aoe, clump_create
- evidence: never fielded 2H_HOLYSTAFF, 2H_HOLYSTAFF_HELL, 2H_SCYTHE_CRYSTAL, 2H_CLAYMORE_AVALON; rare -; pairs seen 0/45; nearest roster Jaccard 0.17 (size 11)

**rank 1 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 74.894, feasible True, filler [], held []

- roster: Hand of Justice [12%], Great Holy Staff [0%], Dawnsong [6%], Great Hammer [12%], Fists of Avalon [6%], Fallen Staff [0%], Kingmaker [0%], Realmbreaker [47%], Battle Bracers [82%], Icicle Staff [6%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_CLAYMORE_AVALON, 2H_KNUCKLES_SET2
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, resist_shred; purple clump_create
- evidence: never fielded 2H_HOLYSTAFF, 2H_HOLYSTAFF_HELL, 2H_CLAYMORE_AVALON; rare -; pairs seen 1/45; nearest roster Jaccard 0.18 (size 10)

**rank 2 (refresh, 2 slots differ)** - score 74.845, feasible True, filler [], held []

- roster: Hand of Justice [12%], Great Holy Staff [0%], Dawnsong [6%], Great Hammer [12%], Fists of Avalon [6%], Fallen Staff [0%], Kingmaker [0%], Realmbreaker [47%], Battle Bracers [82%], Glacial Staff [6%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 0 (p10 0 / p50 1 / p90 2) in; dps 6 (p10 3 / p50 6 / p90 7) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_CLAYMORE_AVALON, 2H_KNUCKLES_SET2
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange resist_shred; purple clump_create
- evidence: never fielded 2H_HOLYSTAFF, 2H_HOLYSTAFF_HELL, 2H_CLAYMORE_AVALON; rare -; pairs seen 1/45; nearest roster Jaccard 0.17 (size 11)

### Faction War (Red Zone) - 10 - clap_kite

Evidence cell: 36 distinct rosters (36 sightings, all); role row: `pooled[10]`.

**rank 0 (the button)** - score 72.777, feasible True, filler [], held []

- roster: Hand of Justice [19%], Blight Staff [19%], Great Hammer [3%], Dawnsong [36%], Fallen Staff [22%], Permafrost Prism [64%], Realmbreaker [42%], Icicle Staff [19%], Spiked Gauntlets [31%], Fists of Avalon [0%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness; purple damage_debuff; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON; rare -; pairs seen 18/45; nearest roster Jaccard 0.38 (size 12)

**rank 1 (refresh, 1 slots differ)** - score 72.597, feasible True, filler [], held []

- roster: Hand of Justice [19%], Blight Staff [19%], Great Hammer [3%], Dawnsong [36%], Fists of Avalon [0%], Fallen Staff [22%], Permafrost Prism [64%], Realmbreaker [42%], Hellfire Hands [3%], Icicle Staff [19%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness; purple damage_debuff; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON; rare -; pairs seen 13/45; nearest roster Jaccard 0.29 (size 12)

**rank 2 (refresh, 1 slots differ)** - score 72.514, feasible True, filler [], held []

- roster: Hand of Justice [19%], Blight Staff [19%], Great Hammer [3%], Fists of Avalon [0%], Fallen Staff [22%], Permafrost Prism [64%], Realmbreaker [42%], Icicle Staff [19%], Rotcaller Staff [22%], Spiked Gauntlets [31%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, ranged_presence, tankiness; purple damage_debuff; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON; rare -; pairs seen 15/45; nearest roster Jaccard 0.31 (size 11)

### Faction War (Red Zone) - 15 - balanced

Evidence cell: 415 distinct rosters (416 sightings, holdout); role row: `pooled[15]`.

**rank 0 (the button)** - score 69.408, feasible True, filler [], held []

- roster: Nature Staff [12%], Hand of Justice [10%], Polehammer [28%], Dawnsong [33%], Fallen Staff [17%], Heavy Mace [37%], Fists of Avalon [2%], Realmbreaker [52%], Exalted Staff [12%], Great Frost Staff [10%], Kingmaker [4%], Icicle Staff [9%], Carrioncaller [2%], Bear Paws [12%], Rootbound Staff [24%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: brawl (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, peel, resist_shred, tankiness; purple -
- evidence: never fielded -; rare 2H_HALBERD_MORGANA; pairs seen 69/105; nearest roster Jaccard 0.29 (size 16)

**rank 1 (refresh, 4 slots differ, OUTSCORES rank 0)** - score 69.569, feasible True, filler [], held []

- roster: Nature Staff [12%], Hand of Justice [10%], Polehammer [28%], Fallen Staff [17%], Heavy Mace [37%], Fists of Avalon [2%], Exalted Staff [12%], Permafrost Prism [43%], Kingmaker [4%], Icicle Staff [9%], Carrioncaller [2%], Rootbound Staff [24%], Battle Bracers [31%], Rotcaller Staff [17%], Spiked Gauntlets [43%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, resist_shred, tankiness; purple -
- evidence: never fielded -; rare 2H_HALBERD_MORGANA; pairs seen 74/105; nearest roster Jaccard 0.32 (size 14)

**rank 2 (refresh, 4 slots differ, OUTSCORES rank 0)** - score 69.461, feasible True, filler [], held []

- roster: Nature Staff [12%], Hand of Justice [10%], Polehammer [28%], Fallen Staff [17%], Heavy Mace [37%], Fists of Avalon [2%], Exalted Staff [12%], Permafrost Prism [43%], Kingmaker [4%], Carrioncaller [2%], Rootbound Staff [24%], Battle Bracers [31%], Rotcaller Staff [17%], Skystrider Bow [0%], Icicle Staff [9%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: brawl (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, tankiness; purple -
- evidence: never fielded -; rare 2H_HALBERD_MORGANA, 2H_BOW_CRYSTAL; pairs seen 60/105; nearest roster Jaccard 0.26 (size 14)

### Faction War (Red Zone) - 15 - brawl

Evidence cell: 87 distinct rosters (87 sightings, holdout); role row: `styles[brawl][15]`.

**rank 0 (the button)** - score 70.411, feasible True, filler [], held []

- roster: Blight Staff [29%], Hand of Justice [0%], Polehammer [23%], Carrioncaller [2%], Fallen Staff [14%], Heavy Mace [39%], Battle Bracers [54%], Realmbreaker [47%], Great Holy Staff [6%], Kingmaker [8%], Fists of Avalon [5%], Hellfire Hands [3%], Rootbound Staff [28%], Forge Hammers [2%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 1.5 / p90 3) in; dps 8 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, damage_debuff, heal_burst; purple -; optional short anti_zone
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 34/105; nearest roster Jaccard 0.38 (size 14)

**rank 1 (refresh, 4 slots differ, OUTSCORES rank 0)** - score 70.624, feasible True, filler [], held []

- roster: Nature Staff [9%], Hand of Justice [0%], Polehammer [23%], Rotcaller Staff [3%], Fallen Staff [14%], Heavy Mace [39%], Battle Bracers [54%], Realmbreaker [47%], Exalted Staff [13%], Kingmaker [8%], Fists of Avalon [5%], Hellfire Hands [3%], Rootbound Staff [28%], Carving Sword [33%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 1.5 / p90 3) in; dps 8 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, damage_debuff, tankiness, zone_control; purple -
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 41/105; nearest roster Jaccard 0.45 (size 14)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 70.563, feasible True, filler [], held []

- roster: Nature Staff [9%], Hand of Justice [0%], Polehammer [23%], Rotcaller Staff [3%], Fallen Staff [14%], Heavy Mace [39%], Battle Bracers [54%], Realmbreaker [47%], Exalted Staff [13%], Kingmaker [8%], Fists of Avalon [5%], Hellfire Hands [3%], Rootbound Staff [28%], Forge Hammers [2%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 1.5 / p90 3) in; dps 8 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, damage_debuff, mobility, tankiness; purple -
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 32/105; nearest roster Jaccard 0.38 (size 14)

### Faction War (Red Zone) - 15 - clap

Evidence cell: 176 distinct rosters (177 sightings, holdout); role row: `styles[clap][15]`.

**rank 0 (the button)** - score 74.885, feasible True, filler [], held []

- roster: Hand of Justice [12%], Rampant Staff [14%], Polehammer [30%], Rotcaller Staff [17%], Heavy Mace [40%], Fallen Staff [22%], Realmbreaker [60%], Hallowfall [77%], Fists of Avalon [2%], Permafrost Prism [59%], Carrioncaller [3%], Permafrost Prism [59%], Wailing Bow [8%], Rootbound Staff [23%], Spiked Gauntlets [57%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 1 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, tankiness; purple catch; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_KNUCKLES_AVALON; pairs seen 67/91; nearest roster Jaccard 0.46 (size 17)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ)** - score 74.854, feasible True, filler [], held []

- roster: Hand of Justice [12%], Rampant Staff [14%], Polehammer [30%], Rotcaller Staff [17%], Heavy Mace [40%], Fallen Staff [22%], Spiked Gauntlets [57%], Realmbreaker [60%], Hallowfall [77%], Fists of Avalon [2%], Permafrost Prism [59%], Longbow [56%], Rootbound Staff [23%], Carrioncaller [3%], Wailing Bow [8%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 1 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, zone_control; purple -; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_KNUCKLES_AVALON; pairs seen 80/105; nearest roster Jaccard 0.39 (size 17)

**rank 2 (refresh, 1 slots differ)** - score 74.83, feasible True, filler [], held []

- roster: Hand of Justice [12%], Rampant Staff [14%], Polehammer [30%], Dawnsong [40%], Heavy Mace [40%], Fallen Staff [22%], Spiked Gauntlets [57%], Realmbreaker [60%], Hallowfall [77%], Fists of Avalon [2%], Permafrost Prism [59%], Rootbound Staff [23%], Carrioncaller [3%], Permafrost Prism [59%], Wailing Bow [8%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 1 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, peel, tankiness; purple catch; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_KNUCKLES_AVALON; pairs seen 67/91; nearest roster Jaccard 0.52 (size 17)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Faction War (Red Zone) - 15 - kite

Evidence cell: 176 distinct rosters (180 sightings, all); role row: `styles[kite][15]`.

**rank 0 (the button)** - score 73.388, feasible True, filler [], held []

- roster: Blight Staff [30%], Hand of Justice [20%], Great Hammer [5%], Grailseeker [13%], Exalted Staff [16%], Fists of Avalon [3%], Realmbreaker [39%], Fallen Staff [23%], Permafrost Prism [46%], Spiked Gauntlets [38%], Carrioncaller [2%], Heavy Mace [25%], Great Arcane Staff [37%], Hellfire Hands [8%], Longbow [42%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 1 (p10 1 / p50 2 / p90 4.5) in; dps 7 (p10 4 / p50 6 / p90 8.5) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, resist_shred, sustained_dps; purple silence; optional short execute
- evidence: never fielded -; rare 2H_HALBERD_MORGANA; pairs seen 63/105; nearest roster Jaccard 0.39 (size 17)

**rank 1 (refresh, 1 slots differ)** - score 73.383, feasible True, filler [], held []

- roster: Blight Staff [30%], Hand of Justice [20%], Great Hammer [5%], Grailseeker [13%], Exalted Staff [16%], Fists of Avalon [3%], Realmbreaker [39%], Fallen Staff [23%], Permafrost Prism [46%], Spiked Gauntlets [38%], Carrioncaller [2%], Heavy Mace [25%], Great Arcane Staff [37%], Hellfire Hands [8%], Weeping Repeater [0%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 1 (p10 1 / p50 2 / p90 4.5) in; dps 7 (p10 4 / p50 6 / p90 8.5) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, tankiness; purple silence; optional short execute
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HALBERD_MORGANA; pairs seen 52/105; nearest roster Jaccard 0.33 (size 17)

**rank 2 (refresh, 2 slots differ)** - score 73.355, feasible True, filler [], held []

- roster: Blight Staff [30%], Hand of Justice [20%], Dawnsong [33%], Great Hammer [5%], Grailseeker [13%], Exalted Staff [16%], Fists of Avalon [3%], Realmbreaker [39%], Fallen Staff [23%], Permafrost Prism [46%], Spiked Gauntlets [38%], Carrioncaller [2%], Heavy Mace [25%], Great Arcane Staff [37%], Wailing Bow [7%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 1 (p10 1 / p50 2 / p90 4.5) in; dps 7 (p10 4 / p50 6 / p90 8.5) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness; purple silence; optional short execute
- evidence: never fielded -; rare 2H_HALBERD_MORGANA; pairs seen 62/105; nearest roster Jaccard 0.33 (size 17)

### Faction War (Red Zone) - 15 - brawl_clap

Evidence cell: 26 distinct rosters (26 sightings, all); role row: `pooled[15]`.

**rank 0 (the button)** - score 74.952, feasible True, filler [], held []

- roster: Hand of Justice [4%], Nature Staff [42%], Polehammer [19%], Dawnsong [4%], Fallen Staff [12%], Heavy Mace [58%], Fists of Avalon [0%], Hellfire Hands [8%], Exalted Staff [38%], Kingmaker [0%], Battle Bracers [96%], Carving Sword [4%], Permafrost Prism [27%], Carrioncaller [0%], Rootbound Staff [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: split (None) - DISAGREES with brawl_clap; conflicts: 2H_CLAYMORE_AVALON, 2H_KNUCKLES_SET2, 2H_CLEAVER_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, mobility; purple stun
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA; rare -; pairs seen 14/105; nearest roster Jaccard 0.23 (size 17)

**rank 1 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 75.113, feasible True, filler [], held []

- roster: Hand of Justice [4%], Nature Staff [42%], Grovekeeper [0%], Permafrost Prism [27%], Fallen Staff [12%], Heavy Mace [58%], Fists of Avalon [0%], Hellfire Hands [8%], Exalted Staff [38%], Kingmaker [0%], Battle Bracers [96%], Carving Sword [4%], Permafrost Prism [27%], Carrioncaller [0%], Rootbound Staff [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_CLAYMORE_AVALON, 2H_KNUCKLES_SET2, 2H_CLEAVER_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, mobility; purple -
- evidence: never fielded 2H_RAM_KEEPER, 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA; rare -; pairs seen 12/91; nearest roster Jaccard 0.18 (size 17)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 75.031, feasible True, filler [], held []

- roster: Hand of Justice [4%], Wild Staff [0%], Grovekeeper [0%], Permafrost Prism [27%], Fallen Staff [12%], Heavy Mace [58%], Fists of Avalon [0%], Hellfire Hands [8%], Exalted Staff [38%], Kingmaker [0%], Battle Bracers [96%], Carving Sword [4%], Permafrost Prism [27%], Carrioncaller [0%], Rootbound Staff [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_CLAYMORE_AVALON, 2H_KNUCKLES_SET2, 2H_CLEAVER_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, mobility, tankiness; purple -
- evidence: never fielded 2H_WILDSTAFF, 2H_RAM_KEEPER, 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA; rare -; pairs seen 7/91; nearest roster Jaccard 0.15 (size 15)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Faction War (Red Zone) - 15 - clap_kite

Evidence cell: 43 distinct rosters (43 sightings, holdout); role row: `styles[clap_kite][15]`.

**rank 0 (the button)** - score 74.708, feasible True, filler [], held []

- roster: Hand of Justice [23%], Blight Staff [30%], Polehammer [40%], Dawnsong [79%], Heavy Mace [26%], Exalted Staff [21%], Realmbreaker [81%], Fists of Avalon [0%], Permafrost Prism [100%], Fallen Staff [9%], Carrioncaller [0%], Spiked Gauntlets [70%], Permafrost Prism [100%], Occult Staff [63%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 3 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red peel; orange disengage, heal_burst, tankiness; purple -; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA; rare -; pairs seen 50/91; nearest roster Jaccard 0.43 (size 15)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ)** - score 74.686, feasible True, filler [], held []

- roster: Hand of Justice [23%], Exalted Staff [21%], Polehammer [40%], Dawnsong [79%], Heavy Mace [26%], Hallowfall [95%], Realmbreaker [81%], Fists of Avalon [0%], Permafrost Prism [100%], Fallen Staff [9%], Carrioncaller [0%], Spiked Gauntlets [70%], Permafrost Prism [100%], Occult Staff [63%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 3 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red peel; orange cleanse, tankiness; purple -; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA; rare -; pairs seen 53/91; nearest roster Jaccard 0.41 (size 16)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 1 slots differ)** - score 74.682, feasible True, filler [], held []

- roster: Hand of Justice [23%], Blight Staff [30%], Polehammer [40%], Dawnsong [79%], Heavy Mace [26%], Hallowfall [95%], Realmbreaker [81%], Fists of Avalon [0%], Permafrost Prism [100%], Fallen Staff [9%], Carrioncaller [0%], Spiked Gauntlets [70%], Permafrost Prism [100%], Occult Staff [63%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 3 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red peel; orange tankiness; purple -; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA; rare -; pairs seen 54/91; nearest roster Jaccard 0.43 (size 15)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Blackzone Roam - 10 - balanced

Evidence cell: 510 distinct rosters (515 sightings, holdout); role row: `pooled[10]`.

**rank 0 (the button)** - score 74.023, feasible True, filler [], held []

- roster: Hand of Justice [8%], Great Holy Staff [8%], Great Hammer [6%], Fallen Staff [8%], Dawnsong [19%], Realmbreaker [24%], Fists of Avalon [4%], Frost Staff [13%], Battle Bracers [20%], Icicle Staff [6%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: clap_kite (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange root; purple -; optional short execute
- evidence: never fielded -; rare -; pairs seen 27/45; nearest roster Jaccard 0.27 (size 9)

**rank 1 (refresh, 4 slots differ, OUTSCORES rank 0)** - score 74.327, feasible True, filler [], held []

- roster: Hand of Justice [8%], Great Holy Staff [8%], Heavy Mace [18%], Nature Staff [7%], Realmbreaker [24%], Fists of Avalon [4%], Icicle Staff [6%], Permafrost Prism [23%], Battle Bracers [20%], Carrioncaller [2%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: brawl (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange -; purple -; optional short execute
- evidence: never fielded -; rare -; pairs seen 28/45; nearest roster Jaccard 0.36 (size 9)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 74.245, feasible True, filler [], held []

- roster: Hand of Justice [8%], Great Holy Staff [8%], Heavy Mace [18%], Fallen Staff [8%], Realmbreaker [24%], Fists of Avalon [4%], Icicle Staff [6%], Permafrost Prism [23%], Battle Bracers [20%], Carrioncaller [2%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: brawl (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange root; purple -; optional short execute
- evidence: never fielded -; rare -; pairs seen 28/45; nearest roster Jaccard 0.36 (size 9)

### Blackzone Roam - 10 - brawl

Evidence cell: 61 distinct rosters (61 sightings, holdout); role row: `styles[brawl][10]`.

**rank 0 (the button)** - score 75.424, feasible True, filler [], held []

- roster: Blight Staff [33%], Hand of Justice [2%], Polehammer [5%], Hallowfall [70%], Realmbreaker [16%], Hellfire Hands [3%], Demonfang [12%], Carving Sword [33%], Spiked Gauntlets [5%], Arcane Staff [0%]
- roles: healer 2 (p10 0.6 / p50 2 / p90 2.4) in; frontline 2 (p10 1 / p50 2 / p90 3.4) in; support 1 (p10 0 / p50 0 / p90 1) in; dps 5 (p10 4 / p50 6 / p90 7) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe, heal_burst, root, zone_control; purple anti_dive, clump_create; optional short execute
- evidence: never fielded MAIN_ARCANESTAFF; rare 2H_HAMMER_AVALON; pairs seen 8/45; nearest roster Jaccard 0.31 (size 11)

**rank 1 (refresh, 4 slots differ, OUTSCORES rank 0)** - score 75.889, feasible True, filler [], held []

- roster: Blight Staff [33%], Hand of Justice [2%], Heavy Mace [16%], Hallowfall [70%], Realmbreaker [16%], Hellfire Hands [3%], Bear Paws [41%], Carving Sword [33%], Fists of Avalon [12%], Kingmaker [13%]
- roles: healer 2 (p10 0.6 / p50 2 / p90 2.4) in; frontline 2 (p10 1 / p50 2 / p90 3.4) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 6 (p10 4 / p50 6 / p90 7) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, heal_burst, resist_shred, slow; purple clump_create
- evidence: never fielded -; rare 2H_HAMMER_AVALON; pairs seen 18/45; nearest roster Jaccard 0.43 (size 10)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 75.811, feasible True, filler [], held []

- roster: Blight Staff [33%], Hand of Justice [2%], Heavy Mace [16%], Hallowfall [70%], Realmbreaker [16%], Hellfire Hands [3%], Bear Paws [41%], Carving Sword [33%], Spiked Gauntlets [5%], Kingmaker [13%]
- roles: healer 2 (p10 0.6 / p50 2 / p90 2.4) in; frontline 2 (p10 1 / p50 2 / p90 3.4) in; support 0 (p10 0 / p50 0 / p90 1) in; dps 6 (p10 4 / p50 6 / p90 7) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, heal_burst, resist_shred; purple clump_create
- evidence: never fielded -; rare 2H_HAMMER_AVALON; pairs seen 16/45; nearest roster Jaccard 0.43 (size 10)

### Blackzone Roam - 10 - clap

Evidence cell: 108 distinct rosters (110 sightings, holdout); role row: `styles[clap][10]`.

**rank 0 (the button)** - score 81.116, feasible True, filler [], held []

- roster: Hand of Justice [15%], Rampant Staff [5%], Great Hammer [6%], Permafrost Prism [47%], Fallen Staff [14%], Realmbreaker [46%], Fists of Avalon [3%], Icicle Staff [5%], Heavy Crossbow [2%], Carrioncaller [1%]
- roles: healer 2 (p10 1 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 5 / p90 7) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe, root; purple slow; optional short execute
- evidence: never fielded -; rare 2H_CROSSBOWLARGE, 2H_HALBERD_MORGANA; pairs seen 6/45; nearest roster Jaccard 0.25 (size 10)

**rank 1 (refresh, 2 slots differ)** - score 81.087, feasible True, filler [], held []

- roster: Hand of Justice [15%], Rampant Staff [5%], Great Hammer [6%], Dawnsong [40%], Fallen Staff [14%], Icicle Staff [5%], Carrioncaller [1%], Realmbreaker [46%], Skystrider Bow [0%], Fists of Avalon [3%]
- roles: healer 2 (p10 1 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 5 / p90 7) in
- identity: brawl (leaning) - DISAGREES with clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe, sustained_dps, zone_control; purple -; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL; rare 2H_HALBERD_MORGANA; pairs seen 6/45; nearest roster Jaccard 0.18 (size 10)

**rank 2 (refresh, 1 slots differ)** - score 81.009, feasible True, filler [], held []

- roster: Hand of Justice [15%], Rampant Staff [5%], Great Hammer [6%], Dawnsong [40%], Fallen Staff [14%], Icicle Staff [5%], Heavy Crossbow [2%], Carrioncaller [1%], Fists of Avalon [3%], Realmbreaker [46%]
- roles: healer 2 (p10 1 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 5 / p90 7) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange root, sustained_dps, zone_control; purple -; optional short execute
- evidence: never fielded -; rare 2H_CROSSBOWLARGE, 2H_HALBERD_MORGANA; pairs seen 6/45; nearest roster Jaccard 0.18 (size 10)

### Blackzone Roam - 10 - kite

Evidence cell: 41 distinct rosters (41 sightings, holdout); role row: `styles[kite][10]`.

**rank 0 (the button)** - score 74.424, feasible True, filler [], held []

- roster: Polehammer [20%], Blight Staff [24%], Great Hammer [2%], Hellfire Hands [12%], Rootbound Staff [10%], Fists of Avalon [2%], Realmbreaker [22%], Frost Staff [27%], Spiked Gauntlets [7%], Weeping Repeater [0%]
- roles: healer 1 (p10 0.3 / p50 1 / p90 2) in; frontline 2 (p10 1 / p50 2 / p90 3) in; support 1 (p10 0 / p50 1 / p90 3.7) in; dps 6 (p10 2.3 / p50 5 / p90 7) in
- identity: kite (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange cleanse, heal_burst, peel, root, tankiness; purple -; optional short execute; ARMED FLOORS heal_sustain
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare -; pairs seen 3/45; nearest roster Jaccard 0.25 (size 10)

**rank 1 (refresh, 1 slots differ)** - score 74.346, feasible True, filler [], held []

- roster: Grovekeeper [0%], Blight Staff [24%], Great Hammer [2%], Hellfire Hands [12%], Rootbound Staff [10%], Fists of Avalon [2%], Realmbreaker [22%], Frost Staff [27%], Spiked Gauntlets [7%], Weeping Repeater [0%]
- roles: healer 1 (p10 0.3 / p50 1 / p90 2) in; frontline 2 (p10 1 / p50 2 / p90 3) in; support 1 (p10 0 / p50 1 / p90 3.7) in; dps 6 (p10 2.3 / p50 5 / p90 7) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, cleanse, heal_burst, root, tankiness; purple engage; optional short execute; ARMED FLOORS heal_sustain
- evidence: never fielded 2H_RAM_KEEPER, 2H_REPEATINGCROSSBOW_UNDEAD; rare -; pairs seen 3/45; nearest roster Jaccard 0.25 (size 10)

**rank 2 (refresh, 2 slots differ)** - score 74.259, feasible True, filler [], held []

- roster: Grovekeeper [0%], Blight Staff [24%], Great Hammer [2%], Dawnsong [20%], Rootbound Staff [10%], Fists of Avalon [2%], Realmbreaker [22%], Frost Staff [27%], Spiked Gauntlets [7%], Weeping Repeater [0%]
- roles: healer 1 (p10 0.3 / p50 1 / p90 2) in; frontline 2 (p10 1 / p50 2 / p90 3) in; support 1 (p10 0 / p50 1 / p90 3.7) in; dps 6 (p10 2.3 / p50 5 / p90 7) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, cleanse, heal_burst, peel, root, tankiness; purple -; optional short execute; ARMED FLOORS heal_sustain
- evidence: never fielded 2H_RAM_KEEPER, 2H_REPEATINGCROSSBOW_UNDEAD; rare -; pairs seen 2/45; nearest roster Jaccard 0.18 (size 10)

### Blackzone Roam - 10 - brawl_clap

Evidence cell: 17 distinct rosters (20 sightings, all); role row: `pooled[10]`.

**rank 0 (the button)** - score 80.763, feasible True, filler [], held []

- roster: Hand of Justice [12%], Great Holy Staff [0%], Heavy Mace [24%], Nature Staff [12%], Fists of Avalon [6%], Realmbreaker [47%], Battle Bracers [82%], Crystal Reaper [0%], Permafrost Prism [6%], Hellfire Hands [0%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 0 (p10 0 / p50 1 / p90 2) in; dps 6 (p10 3 / p50 6 / p90 7) in
- identity: brawl (strong) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, mobility; purple clump_create; optional short execute
- evidence: never fielded 2H_HOLYSTAFF, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_HELL; rare -; pairs seen 2/45; nearest roster Jaccard 0.23 (size 11)

**rank 1 (refresh, 1 slots differ)** - score 80.572, feasible True, filler [], held []

- roster: Hand of Justice [12%], Great Holy Staff [0%], Heavy Mace [24%], Nature Staff [12%], Fists of Avalon [6%], Realmbreaker [47%], Battle Bracers [82%], Demonfang [29%], Permafrost Prism [6%], Hellfire Hands [0%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 0 (p10 0 / p50 1 / p90 2) in; dps 6 (p10 3 / p50 6 / p90 7) in
- identity: brawl (strong) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, resist_shred; purple burst_aoe, clump_create, interrupt; optional short execute
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_HELL; rare -; pairs seen 3/45; nearest roster Jaccard 0.23 (size 11)

**rank 2 (refresh, 2 slots differ)** - score 80.541, feasible True, filler [], held []

- roster: Hand of Justice [12%], Great Holy Staff [0%], Great Hammer [12%], Nature Staff [12%], Fists of Avalon [6%], Realmbreaker [47%], Battle Bracers [82%], Demonfang [29%], Permafrost Prism [6%], Hellfire Hands [0%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 0 (p10 0 / p50 1 / p90 2) in; dps 6 (p10 3 / p50 6 / p90 7) in
- identity: brawl (strong) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st; purple anti_dive, burst_aoe, clump_create; optional short execute
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_HELL; rare -; pairs seen 2/45; nearest roster Jaccard 0.23 (size 11)

### Blackzone Roam - 10 - clap_kite

Evidence cell: 36 distinct rosters (36 sightings, all); role row: `pooled[10]`.

**rank 0 (the button)** - score 77.892, feasible True, filler [], held []

- roster: Hand of Justice [19%], Blight Staff [19%], Great Hammer [3%], Realmbreaker [42%], Fallen Staff [22%], Icicle Staff [19%], Dawnsong [36%], Spiked Gauntlets [31%], Fists of Avalon [0%], Skystrider Bow [3%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red root; orange buff_allies, burst_aoe, damage_debuff, heal_burst, interrupt, peel, tankiness, zone_control; purple -; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON; rare -; pairs seen 11/45; nearest roster Jaccard 0.29 (size 12)

**rank 1 (refresh, 1 slots differ)** - score 77.863, feasible True, filler [], held []

- roster: Hand of Justice [19%], Rampant Staff [6%], Great Hammer [3%], Realmbreaker [42%], Fallen Staff [22%], Icicle Staff [19%], Dawnsong [36%], Spiked Gauntlets [31%], Fists of Avalon [0%], Skystrider Bow [3%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red root; orange buff_allies, burst_aoe, damage_debuff, heal_burst, interrupt, peel, tankiness, zone_control; purple -; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON; rare -; pairs seen 8/45; nearest roster Jaccard 0.29 (size 12)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 78.118, feasible True, filler [], held []

- roster: Hand of Justice [19%], Blight Staff [19%], Heavy Mace [11%], Realmbreaker [42%], Fallen Staff [22%], Icicle Staff [19%], Dawnsong [36%], Dual Swords [0%], Fists of Avalon [0%], Permafrost Prism [64%]
- roles: healer 2 (p10 0 / p50 2 / p90 3) in; frontline 2 (p10 1 / p50 2 / p90 4) in; support 1 (p10 0 / p50 1 / p90 2) in; dps 5 (p10 3 / p50 6 / p90 7) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red root; orange anti_dive, buff_allies, burst_aoe, damage_debuff, heal_burst, interrupt, knockback_displace, peel, ranged_presence, tankiness; purple silence; optional short execute
- evidence: never fielded 2H_DUALSWORD, 2H_KNUCKLES_AVALON; rare -; pairs seen 14/45; nearest roster Jaccard 0.31 (size 11)

### Blackzone Roam - 15 - balanced

Evidence cell: 415 distinct rosters (416 sightings, holdout); role row: `pooled[15]`.

**rank 0 (the button)** - score 75.163, feasible True, filler [], held []

- roster: Hand of Justice [10%], Nature Staff [12%], Polehammer [28%], Fallen Staff [17%], Dawnsong [33%], Heavy Mace [37%], Realmbreaker [52%], Carving Sword [20%], Exalted Staff [12%], Spiked Gauntlets [43%], Permafrost Prism [43%], Fists of Avalon [2%], Icicle Staff [9%], Kingmaker [4%], Rootbound Staff [24%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, knockback_displace, mobility, tankiness; purple -
- evidence: never fielded -; rare -; pairs seen 82/105; nearest roster Jaccard 0.38 (size 14)

**rank 1 (refresh, 1 slots differ)** - score 75.121, feasible True, filler [], held []

- roster: Hand of Justice [10%], Nature Staff [12%], Polehammer [28%], Fallen Staff [17%], Dawnsong [33%], Heavy Mace [37%], Realmbreaker [52%], Carving Sword [20%], Exalted Staff [12%], Spiked Gauntlets [43%], Permafrost Prism [43%], Fists of Avalon [2%], Rootbound Staff [24%], Kingmaker [4%], Hoarfrost Staff [3%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, slow, tankiness, zone_control; purple -
- evidence: never fielded -; rare -; pairs seen 77/105; nearest roster Jaccard 0.38 (size 14)

**rank 2 (refresh, 2 slots differ)** - score 74.928, feasible True, filler [], held []

- roster: Hand of Justice [10%], Nature Staff [12%], Polehammer [28%], Fallen Staff [17%], Dawnsong [33%], Heavy Mace [37%], Realmbreaker [52%], Carving Sword [20%], Great Holy Staff [9%], Spiked Gauntlets [43%], Permafrost Prism [43%], Fists of Avalon [2%], Rootbound Staff [24%], Kingmaker [4%], Hoarfrost Staff [3%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange mobility, slow; purple -; optional short anti_zone
- evidence: never fielded -; rare -; pairs seen 76/105; nearest roster Jaccard 0.38 (size 14)

### Blackzone Roam - 15 - brawl

Evidence cell: 87 distinct rosters (87 sightings, holdout); role row: `styles[brawl][15]`.

**rank 0 (the button)** - score 76.175, feasible True, filler [], held []

- roster: Hand of Justice [0%], Hallowfall [85%], Polehammer [23%], Fallen Staff [14%], Heavy Mace [39%], Realmbreaker [47%], Fists of Avalon [5%], Great Holy Staff [6%], Carving Sword [33%], Occult Staff [2%], Hellfire Hands [3%], Arcane Staff [6%], Kingmaker [8%], Bear Paws [33%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 1.5 / p90 3) in; dps 7 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe, burst_st, zone_control; purple purge; optional short anti_zone
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 37/105; nearest roster Jaccard 0.32 (size 14)

**rank 1 (refresh, 1 slots differ)** - score 76.059, feasible True, filler [], held []

- roster: Hand of Justice [0%], Blight Staff [29%], Polehammer [23%], Fallen Staff [14%], Heavy Mace [39%], Realmbreaker [47%], Fists of Avalon [5%], Great Holy Staff [6%], Carving Sword [33%], Occult Staff [2%], Hellfire Hands [3%], Arcane Staff [6%], Kingmaker [8%], Bear Paws [33%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 1.5 / p90 3) in; dps 7 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, burst_st, heal_burst, tankiness, zone_control; purple purge; optional short anti_zone
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 33/105; nearest roster Jaccard 0.32 (size 14)

**rank 2 (refresh, 4 slots differ, OUTSCORES rank 0)** - score 76.395, feasible True, filler [], held []

- roster: Hand of Justice [0%], Nature Staff [9%], Polehammer [23%], Fallen Staff [14%], Heavy Mace [39%], Realmbreaker [47%], Fists of Avalon [5%], Exalted Staff [13%], Carving Sword [33%], Rootbound Staff [28%], Hellfire Hands [3%], Forge Hammers [2%], Bear Paws [33%], Kingmaker [8%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 1.5 / p90 3) in; dps 8 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, damage_debuff, mobility, root, tankiness; purple anti_dive
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 41/105; nearest roster Jaccard 0.32 (size 14)

### Blackzone Roam - 15 - clap

Evidence cell: 176 distinct rosters (177 sightings, holdout); role row: `styles[clap][15]`.

**rank 0 (the button)** - score 82.071, feasible True, filler [], held []

- roster: Hand of Justice [12%], Rampant Staff [14%], Polehammer [30%], Permafrost Prism [59%], Heavy Mace [40%], Fallen Staff [22%], Realmbreaker [60%], Fists of Avalon [2%], Hallowfall [77%], Permafrost Prism [59%], Spiked Gauntlets [57%], Longbow [56%], Rootbound Staff [23%], Carrioncaller [3%], Hoarfrost Staff [1%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, root, tankiness, zone_control; purple catch; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_KNUCKLES_AVALON, MAIN_FROSTSTAFF_KEEPER; pairs seen 58/91; nearest roster Jaccard 0.39 (size 17)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ)** - score 82.053, feasible True, filler [], held []

- roster: Hand of Justice [12%], Rampant Staff [14%], Polehammer [30%], Dawnsong [40%], Heavy Mace [40%], Fallen Staff [22%], Realmbreaker [60%], Fists of Avalon [2%], Hallowfall [77%], Permafrost Prism [59%], Spiked Gauntlets [57%], Longbow [56%], Rootbound Staff [23%], Carrioncaller [3%], Hoarfrost Staff [1%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, root, tankiness; purple -; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_KNUCKLES_AVALON, MAIN_FROSTSTAFF_KEEPER; pairs seen 69/105; nearest roster Jaccard 0.41 (size 16)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 82.307, feasible True, filler [], held []

- roster: Hand of Justice [12%], Nature Staff [11%], Polehammer [30%], Dawnsong [40%], Heavy Mace [40%], Fallen Staff [22%], Realmbreaker [60%], Fists of Avalon [2%], Exalted Staff [14%], Hoarfrost Staff [1%], Spiked Gauntlets [57%], Longbow [56%], Rootbound Staff [23%], Carrioncaller [3%], Permafrost Prism [59%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, disengage, mobility, slow, tankiness, zone_control; purple -; optional short execute
- evidence: never fielded -; rare 2H_KNUCKLES_AVALON, MAIN_FROSTSTAFF_KEEPER; pairs seen 68/105; nearest roster Jaccard 0.33 (size 17)

### Blackzone Roam - 15 - kite

Evidence cell: 176 distinct rosters (180 sightings, all); role row: `styles[kite][15]`.

**rank 0 (the button)** - score 78.991, feasible True, filler [], held []

- roster: Hand of Justice [20%], Blight Staff [30%], Great Hammer [5%], Exalted Staff [16%], Dawnsong [33%], Grailseeker [13%], Realmbreaker [39%], Fists of Avalon [3%], Fallen Staff [23%], Skystrider Bow [0%], Icicle Staff [25%], Bedrock Mace [52%], Spiked Gauntlets [38%], Arcane Staff [38%], Carrioncaller [2%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4.5) in; dps 6 (p10 4 / p50 6 / p90 8.5) in
- identity: kite (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness, zone_control; purple catch; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL; rare 2H_HALBERD_MORGANA; pairs seen 57/105; nearest roster Jaccard 0.33 (size 17)

**rank 1 (refresh, 1 slots differ)** - score 78.819, feasible True, filler [], held []

- roster: Hand of Justice [20%], Blight Staff [30%], Great Hammer [5%], Hallowfall [70%], Dawnsong [33%], Grailseeker [13%], Realmbreaker [39%], Fists of Avalon [3%], Fallen Staff [23%], Skystrider Bow [0%], Icicle Staff [25%], Bedrock Mace [52%], Spiked Gauntlets [38%], Arcane Staff [38%], Carrioncaller [2%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4.5) in; dps 6 (p10 4 / p50 6 / p90 8.5) in
- identity: kite (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, knockback_displace, resist_shred, tankiness, zone_control; purple catch; optional short anti_zone, execute
- evidence: never fielded 2H_BOW_CRYSTAL; rare 2H_HALBERD_MORGANA; pairs seen 61/105; nearest roster Jaccard 0.39 (size 17)

**rank 2 (refresh, 1 slots differ)** - score 78.841, feasible True, filler [], held []

- roster: Hand of Justice [20%], Blight Staff [30%], Great Hammer [5%], Exalted Staff [16%], Dawnsong [33%], Grailseeker [13%], Realmbreaker [39%], Fists of Avalon [3%], Fallen Staff [23%], Spiked Gauntlets [38%], Icicle Staff [25%], Bedrock Mace [52%], Carrioncaller [2%], Arcane Staff [38%], Heavy Crossbow [2%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4.5) in; dps 6 (p10 4 / p50 6 / p90 8.5) in
- identity: kite (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, disengage, heal_burst, sustained_dps, tankiness, zone_control; purple -; optional short execute
- evidence: never fielded -; rare 2H_HALBERD_MORGANA, 2H_CROSSBOWLARGE; pairs seen 58/105; nearest roster Jaccard 0.33 (size 17)

### Blackzone Roam - 15 - brawl_clap

Evidence cell: 26 distinct rosters (26 sightings, all); role row: `pooled[15]`.

**rank 0 (the button)** - score 81.417, feasible True, filler [], held []

- roster: Hand of Justice [4%], Exalted Staff [38%], Grovekeeper [0%], Fallen Staff [12%], Carrioncaller [0%], Heavy Mace [58%], Realmbreaker [42%], Fists of Avalon [0%], Permafrost Prism [27%], Nature Staff [42%], Carving Sword [4%], Battle Bracers [96%], Permafrost Prism [27%], Kingmaker [0%], Rootbound Staff [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_CLEAVER_HELL, 2H_KNUCKLES_SET2, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, mobility; purple anti_dive
- evidence: never fielded 2H_RAM_KEEPER, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON; rare -; pairs seen 17/91; nearest roster Jaccard 0.23 (size 17)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ)** - score 81.286, feasible True, filler [], held []

- roster: Hand of Justice [4%], Exalted Staff [38%], Grovekeeper [0%], Fallen Staff [12%], Carrioncaller [0%], Heavy Mace [58%], Realmbreaker [42%], Fists of Avalon [0%], Permafrost Prism [27%], Wild Staff [0%], Carving Sword [4%], Battle Bracers [96%], Permafrost Prism [27%], Kingmaker [0%], Rootbound Staff [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_CLEAVER_HELL, 2H_KNUCKLES_SET2, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, heal_burst, mobility; purple anti_dive
- evidence: never fielded 2H_RAM_KEEPER, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, 2H_WILDSTAFF, 2H_CLAYMORE_AVALON; rare -; pairs seen 11/91; nearest roster Jaccard 0.18 (size 17)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 2 slots differ)** - score 81.299, feasible True, filler [], held []

- roster: Hand of Justice [4%], Exalted Staff [38%], Grovekeeper [0%], Fallen Staff [12%], Bear Paws [8%], Heavy Mace [58%], Realmbreaker [42%], Fists of Avalon [0%], Permafrost Prism [27%], Nature Staff [42%], Carving Sword [4%], Battle Bracers [96%], Hellfire Hands [8%], Kingmaker [0%], Rootbound Staff [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: brawl (strong) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_st; purple anti_dive
- evidence: never fielded 2H_RAM_KEEPER, 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON; rare -; pairs seen 17/105; nearest roster Jaccard 0.23 (size 17)

### Blackzone Roam - 15 - clap_kite

Evidence cell: 43 distinct rosters (43 sightings, holdout); role row: `styles[clap_kite][15]`.

**rank 0 (the button)** - score 80.455, feasible True, filler [], held []

- roster: Hand of Justice [23%], Blight Staff [30%], Polehammer [40%], Hallowfall [95%], Dawnsong [79%], Heavy Mace [26%], Realmbreaker [81%], Grailseeker [0%], Fists of Avalon [0%], Fallen Staff [9%], Hellfire Hands [2%], Spiked Gauntlets [70%], Occult Staff [63%], Longbow [33%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 4 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 6 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange buff_allies, burst_aoe, damage_debuff, interrupt, knockback_displace, peel, root, slow, sustained_dps, tankiness, zone_control; purple catch; optional short anti_zone, execute
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON; rare -; pairs seen 53/105; nearest roster Jaccard 0.39 (size 17)

**rank 1 (refresh, 1 slots differ)** - score 80.444, feasible True, filler [], held []

- roster: Hand of Justice [23%], Blight Staff [30%], Polehammer [40%], Hallowfall [95%], Dawnsong [79%], Heavy Mace [26%], Realmbreaker [81%], Grailseeker [0%], Fists of Avalon [0%], Fallen Staff [9%], Hellfire Hands [2%], Spiked Gauntlets [70%], Occult Staff [63%], Wailing Bow [7%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 4 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 6 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange buff_allies, damage_debuff, interrupt, knockback_displace, peel, root, slow, tankiness, zone_control; purple catch; optional short anti_zone, execute
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON; rare -; pairs seen 44/105; nearest roster Jaccard 0.36 (size 15)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 80.635, feasible True, filler [], held []

- roster: Hand of Justice [23%], Blight Staff [30%], Polehammer [40%], Hallowfall [95%], Dawnsong [79%], Heavy Mace [26%], Realmbreaker [81%], Bedrock Mace [91%], Fists of Avalon [0%], Fallen Staff [9%], Hellfire Hands [2%], Spiked Gauntlets [70%], Great Frost Staff [0%], Permafrost Prism [100%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 4 (p10 2.9 / p50 4 / p90 6) in; support 1 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange anti_dive, buff_allies, cleanse, damage_debuff, root, slow, tankiness; purple -; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_FROSTSTAFF; rare -; pairs seen 55/105; nearest roster Jaccard 0.46 (size 17)

### Blackzone Roam - 20 - balanced

Evidence cell: 357 distinct rosters (365 sightings, holdout); role row: `pooled[20]`.

**rank 0 (the button)** - score 75.8, feasible True, filler [], held []

- roster: Hand of Justice [21%], Great Holy Staff [2%], Polehammer [39%], Fallen Staff [17%], Heavy Mace [43%], Dawnsong [52%], Realmbreaker [77%], Grovekeeper [2%], Nature Staff [16%], Crystal Reaper [0%], Exalted Staff [31%], Fists of Avalon [1%], Carving Sword [22%], Permafrost Prism [56%], Permafrost Prism [56%], Spiked Gauntlets [68%], Kingmaker [5%], Occult Staff [33%], Energy Shaper [12%], Rootbound Staff [32%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 10 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange heal_burst, tankiness; purple -
- evidence: never fielded -; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 104/171; nearest roster Jaccard 0.33 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 76.077, feasible True, filler [], held []

- roster: Hand of Justice [21%], Great Holy Staff [2%], Polehammer [39%], Fallen Staff [17%], Heavy Mace [43%], Energy Shaper [12%], Realmbreaker [77%], Grovekeeper [2%], Nature Staff [16%], Crystal Reaper [0%], Exalted Staff [31%], Fists of Avalon [1%], Carving Sword [22%], Permafrost Prism [56%], Permafrost Prism [56%], Spiked Gauntlets [68%], Kingmaker [5%], Occult Staff [33%], Carrioncaller [2%], Rootbound Staff [32%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 10 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange peel, tankiness; purple -
- evidence: never fielded -; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 95/171; nearest roster Jaccard 0.29 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 76.059, feasible True, filler [], held []

- roster: Hand of Justice [21%], Great Holy Staff [2%], Polehammer [39%], Fallen Staff [17%], Heavy Mace [43%], Weeping Repeater [0%], Realmbreaker [77%], Grovekeeper [2%], Nature Staff [16%], Crystal Reaper [0%], Exalted Staff [31%], Fists of Avalon [1%], Carving Sword [22%], Permafrost Prism [56%], Permafrost Prism [56%], Spiked Gauntlets [68%], Kingmaker [5%], Occult Staff [33%], Carrioncaller [2%], Rootbound Staff [32%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 10 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange peel, tankiness; purple -
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 83/171; nearest roster Jaccard 0.29 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Blackzone Roam - 20 - brawl

Evidence cell: 43 distinct rosters (44 sightings, holdout); role row: `styles[brawl][20]`.

**rank 0 (the button)** - score 77.021, feasible True, filler [], held []

- roster: Hand of Justice [5%], Blight Staff [23%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Realmbreaker [58%], Great Holy Staff [0%], Icicle Staff [9%], Carving Sword [33%], Fists of Avalon [0%], Hallowfall [98%], Crystal Reaper [0%], Hellfire Hands [2%], Battle Bracers [56%], Kingmaker [14%], Spiked Gauntlets [33%], Rootbound Staff [26%], Rotcaller Staff [14%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 2 (p10 2 / p50 3 / p90 4) in; dps 10 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange cleanse, damage_debuff, heal_burst, tankiness, zone_control; purple heal_reduction; optional short anti_zone
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 53/190; nearest roster Jaccard 0.34 (size 19)

**rank 1 (refresh, 1 slots differ)** - score 77.02, feasible True, filler [], held []

- roster: Hand of Justice [5%], Blight Staff [23%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Realmbreaker [58%], Great Holy Staff [0%], Icicle Staff [9%], Carving Sword [33%], Fists of Avalon [0%], Hallowfall [98%], Crystal Reaper [0%], Hellfire Hands [2%], Battle Bracers [56%], Kingmaker [14%], Spiked Gauntlets [33%], Rootbound Staff [26%], Rotcaller Staff [14%], Clarent Blade [2%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 2 (p10 2 / p50 3 / p90 4) in; dps 10 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange cleanse, damage_debuff, heal_burst, tankiness, zone_control; purple heal_reduction; optional short anti_zone
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL; rare -; pairs seen 53/190; nearest roster Jaccard 0.34 (size 19)

**rank 2 (refresh, 1 slots differ)** - score 76.906, feasible True, filler [], held []

- roster: Hand of Justice [5%], Blight Staff [23%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Realmbreaker [58%], Great Holy Staff [0%], Icicle Staff [9%], Carving Sword [33%], Fists of Avalon [0%], Hallowfall [98%], Crystal Reaper [0%], Hellfire Hands [2%], Battle Bracers [56%], Kingmaker [14%], Spiked Gauntlets [33%], Rootbound Staff [26%], Malevolent Locus [26%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 3 (p10 2 / p50 3 / p90 4) in; dps 9 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe, damage_debuff, heal_burst, tankiness, zone_control; purple -; optional short anti_zone
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 59/190; nearest roster Jaccard 0.34 (size 19)

### Blackzone Roam - 20 - clap

Evidence cell: 155 distinct rosters (159 sightings, holdout); role row: `styles[clap][20]`.

**rank 0 (the button)** - score 83.013, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Polehammer [37%], Dawnsong [57%], Heavy Mace [52%], Fallen Staff [17%], Realmbreaker [83%], Grailseeker [1%], Fists of Avalon [1%], Great Hammer [6%], Hallowfall [91%], Carrioncaller [2%], Nature Staff [17%], Spiked Gauntlets [70%], Great Fire Staff [3%], Longbow [52%], Occult Staff [27%], Weeping Repeater [0%], Rootbound Staff [37%], Energy Shaper [17%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange slow, tankiness, zone_control; purple catch, root; optional short anti_zone, execute
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA; pairs seen 102/190; nearest roster Jaccard 0.36 (size 18)

**rank 1 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 83.044, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Polehammer [37%], Dawnsong [57%], Heavy Mace [52%], Fallen Staff [17%], Realmbreaker [83%], Grailseeker [1%], Fists of Avalon [1%], Great Hammer [6%], Hallowfall [91%], Carrioncaller [2%], Nature Staff [17%], Spiked Gauntlets [70%], Heavy Crossbow [2%], Longbow [52%], Occult Staff [27%], Weeping Repeater [0%], Rootbound Staff [37%], Energy Shaper [17%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, slow, tankiness; purple catch, root; optional short anti_zone, execute
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA, 2H_CROSSBOWLARGE; pairs seen 99/190; nearest roster Jaccard 0.36 (size 18)

**rank 2 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 83.021, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Polehammer [37%], Dawnsong [57%], Heavy Mace [52%], Fallen Staff [17%], Realmbreaker [83%], Grailseeker [1%], Fists of Avalon [1%], Great Hammer [6%], Hallowfall [91%], Carrioncaller [2%], Nature Staff [17%], Longbow [52%], Occult Staff [27%], Weeping Repeater [0%], Rootbound Staff [37%], Heavy Crossbow [2%], Spiked Gauntlets [70%], Great Fire Staff [3%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange slow, tankiness, zone_control; purple catch, root; optional short anti_zone, execute
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA, 2H_CROSSBOWLARGE; pairs seen 88/190; nearest roster Jaccard 0.36 (size 18)

### Blackzone Roam - 20 - kite

Evidence cell: 125 distinct rosters (140 sightings, all); role row: `styles[kite][20]`.

**rank 0 (the button)** - score 79.457, feasible True, filler [], held []

- roster: Hand of Justice [37%], Blight Staff [27%], Great Hammer [2%], Dawnsong [49%], Fallen Staff [20%], Polehammer [42%], Realmbreaker [73%], Grailseeker [4%], Hallowfall [86%], Skystrider Bow [0%], Great Arcane Staff [59%], Exalted Staff [40%], Hellfire Hands [4%], Heavy Mace [22%], Longbow [38%], Occult Staff [63%], Spiked Gauntlets [71%], Weeping Repeater [0%], Enigmatic Staff [10%], Carrioncaller [2%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 3 (p10 3 / p50 4 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 8) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red root; orange anti_dive, buff_allies, heal_burst, knockback_displace, slow, tankiness; purple catch, silence; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL, 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 93/190; nearest roster Jaccard 0.36 (size 18)

**rank 1 (refresh, 1 slots differ)** - score 79.41, feasible True, filler [], held []

- roster: Hand of Justice [37%], Blight Staff [27%], Great Hammer [2%], Dawnsong [49%], Hallowfall [86%], Polehammer [42%], Realmbreaker [73%], Grailseeker [4%], Hallowfall [86%], Skystrider Bow [0%], Great Arcane Staff [59%], Exalted Staff [40%], Hellfire Hands [4%], Heavy Mace [22%], Longbow [38%], Occult Staff [63%], Spiked Gauntlets [71%], Weeping Repeater [0%], Enigmatic Staff [10%], Carrioncaller [2%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 3 (p10 3 / p50 4 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 8) in
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red root; orange anti_dive, buff_allies, cleanse, heal_burst, knockback_displace, slow, tankiness; purple catch, silence; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL, 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 80/171; nearest roster Jaccard 0.41 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 79.486, feasible True, filler [], held []

- roster: Hand of Justice [37%], Blight Staff [27%], Great Hammer [2%], Dawnsong [49%], Fallen Staff [20%], Grovekeeper [2%], Realmbreaker [73%], Grailseeker [4%], Hallowfall [86%], Skystrider Bow [0%], Fists of Avalon [0%], Exalted Staff [40%], Hellfire Hands [4%], Heavy Mace [22%], Rift Glaive [30%], Occult Staff [63%], Spiked Gauntlets [71%], Weeping Repeater [0%], Enigmatic Staff [10%], Carrioncaller [2%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 3 / p50 4 / p90 5) under; dps 9 (p10 6 / p50 7 / p90 8) over
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True); weak stages: Slow:weak
- board: red root; orange anti_dive, buff_allies, cleanse, heal_burst, knockback_displace, peel, slow, tankiness; purple -; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL, 2H_KNUCKLES_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HAMMER, 2H_RAM_KEEPER, 2H_HALBERD_MORGANA; pairs seen 66/190; nearest roster Jaccard 0.27 (size 18)

### Blackzone Roam - 20 - brawl_clap

Evidence cell: 27 distinct rosters (33 sightings, all); role row: `pooled[20]`.

**rank 0 (the button)** - score 81.813, feasible True, filler [], held []

- roster: Grailseeker [0%], Great Holy Staff [0%], Heavy Mace [78%], Polehammer [30%], Hallowfall [100%], Great Hammer [7%], Realmbreaker [78%], Witchwork Staff [0%], Hallowfall [100%], Fists of Avalon [0%], Exalted Staff [48%], Battle Bracers [100%], Crystal Reaper [0%], Occult Staff [0%], Kingmaker [0%], Carrioncaller [0%], Rootbound Staff [67%], Lightcaller [4%], Hellfire Hands [0%], Wailing Bow [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: brawl (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange cleanse, max_health_cut; purple catch, clump_create
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, MAIN_ARCANESTAFF_UNDEAD, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_ARCANESTAFF_HELL, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_KNUCKLES_HELL, 2H_BOW_HELL; rare -; pairs seen 21/171; nearest roster Jaccard 0.23 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 2 slots differ)** - score 81.808, feasible True, filler [], held []

- roster: Grailseeker [0%], Great Holy Staff [0%], Heavy Mace [78%], Polehammer [30%], Hallowfall [100%], Great Hammer [7%], Realmbreaker [78%], Witchwork Staff [0%], Hallowfall [100%], Fists of Avalon [0%], Exalted Staff [48%], Battle Bracers [100%], Crystal Reaper [0%], Occult Staff [0%], Kingmaker [0%], Carrioncaller [0%], Rootbound Staff [67%], Hellfire Hands [0%], Longbow [4%], Galatine Pair [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: brawl (strong) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange buff_allies, burst_st, cleanse, disengage, resist_shred; purple catch, clump_create
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, MAIN_ARCANESTAFF_UNDEAD, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_ARCANESTAFF_HELL, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_KNUCKLES_HELL, 2H_DUALSCIMITAR_UNDEAD; rare -; pairs seen 21/171; nearest roster Jaccard 0.23 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 2 (refresh, 2 slots differ)** - score 81.81, feasible True, filler [], held []

- roster: Grailseeker [0%], Great Holy Staff [0%], Heavy Mace [78%], Polehammer [30%], Hallowfall [100%], Great Hammer [7%], Realmbreaker [78%], Witchwork Staff [0%], Hallowfall [100%], Fists of Avalon [0%], Exalted Staff [48%], Battle Bracers [100%], Crystal Reaper [0%], Occult Staff [0%], Kingmaker [0%], Carrioncaller [0%], Longbow [4%], Wailing Bow [0%], Malevolent Locus [56%], Lightcaller [4%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: brawl (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange max_health_cut, tankiness, zone_control; purple catch, clump_create
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, MAIN_ARCANESTAFF_UNDEAD, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_ARCANESTAFF_HELL, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_BOW_HELL; rare -; pairs seen 21/171; nearest roster Jaccard 0.23 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Blackzone Roam - 20 - clap_kite

Evidence cell: 79 distinct rosters (82 sightings, holdout); role row: `styles[clap_kite][20]`.

**rank 0 (the button)** - score 82.454, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Polehammer [57%], Hallowfall [95%], Grailseeker [2%], Great Hammer [1%], Realmbreaker [89%], Dawnsong [81%], Fists of Avalon [1%], Carrioncaller [0%], Fallen Staff [23%], Exalted Staff [43%], Spiked Gauntlets [86%], Heavy Mace [13%], Longbow [30%], Occult Staff [73%], Hellfire Hands [6%], Rootbound Staff [19%], Weeping Repeater [0%], Heavy Crossbow [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 5 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 6 / p50 7 / p90 9) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange anti_dive, buff_allies, cleanse, peel, root, slow, tankiness; purple silence; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA, 2H_REPEATINGCROSSBOW_UNDEAD, 2H_CROSSBOWLARGE; rare 2H_HAMMER, 2H_KNUCKLES_AVALON; pairs seen 78/190; nearest roster Jaccard 0.34 (size 19)

**rank 1 (refresh, 1 slots differ)** - score 82.445, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Polehammer [57%], Hallowfall [95%], Grailseeker [2%], Great Hammer [1%], Realmbreaker [89%], Dawnsong [81%], Fists of Avalon [1%], Carrioncaller [0%], Fallen Staff [23%], Skystrider Bow [0%], Exalted Staff [43%], Spiked Gauntlets [86%], Heavy Mace [13%], Longbow [30%], Occult Staff [73%], Hellfire Hands [6%], Rootbound Staff [19%], Heavy Crossbow [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 5 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 6 / p50 7 / p90 9) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange anti_dive, buff_allies, cleanse, knockback_displace, peel, root, slow, sustained_dps, tankiness, zone_control; purple silence; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA, 2H_BOW_CRYSTAL, 2H_CROSSBOWLARGE; rare 2H_HAMMER, 2H_KNUCKLES_AVALON; pairs seen 78/190; nearest roster Jaccard 0.34 (size 19)

**rank 2 (refresh, 1 slots differ)** - score 82.437, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Polehammer [57%], Hallowfall [95%], Grailseeker [2%], Great Hammer [1%], Realmbreaker [89%], Dawnsong [81%], Fists of Avalon [1%], Carrioncaller [0%], Fallen Staff [23%], Longbow [30%], Exalted Staff [43%], Spiked Gauntlets [86%], Heavy Mace [13%], Great Frost Staff [5%], Occult Staff [73%], Hellfire Hands [6%], Rootbound Staff [19%], Heavy Crossbow [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 5 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 6 / p50 7 / p90 9) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange anti_dive, buff_allies, cleanse, knockback_displace, peel, root, sustained_dps, tankiness; purple catch, silence; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA, 2H_CROSSBOWLARGE; rare 2H_HAMMER, 2H_KNUCKLES_AVALON; pairs seen 83/190; nearest roster Jaccard 0.34 (size 19)

### Territory Defense - 15 - balanced

Evidence cell: 415 distinct rosters (416 sightings, holdout); role row: `pooled[15]`.

**rank 0 (the button)** - score 73.325, feasible True, filler [], held []

- roster: Hand of Justice [10%], Great Holy Staff [9%], Heavy Mace [37%], Fallen Staff [17%], Grailseeker [5%], Realmbreaker [52%], Crystal Reaper [0%], Exalted Staff [12%], Permafrost Prism [43%], Spiked Gauntlets [43%], Carving Sword [20%], Permafrost Prism [43%], Hellfire Hands [5%], Occult Staff [19%], Arcane Staff [15%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange anti_dive, burst_st, mobility, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_SCYTHE_CRYSTAL; rare -; pairs seen 65/91; nearest roster Jaccard 0.32 (size 14)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 2 slots differ)** - score 73.322, feasible True, filler [], held []

- roster: Hand of Justice [10%], Great Holy Staff [9%], Heavy Mace [37%], Fallen Staff [17%], Grailseeker [5%], Realmbreaker [52%], Crystal Reaper [0%], Exalted Staff [12%], Permafrost Prism [43%], Longbow [42%], Carving Sword [20%], Permafrost Prism [43%], Arcane Staff [15%], Hellfire Hands [5%], Kingmaker [4%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange anti_dive, buff_allies, burst_st, mobility, tankiness; purple catch
- evidence: never fielded 2H_SCYTHE_CRYSTAL; rare -; pairs seen 58/91; nearest roster Jaccard 0.28 (size 17)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 3 slots differ)** - score 73.302, feasible True, filler [], held []

- roster: Hand of Justice [10%], Great Holy Staff [9%], Heavy Mace [37%], Fallen Staff [17%], Grailseeker [5%], Realmbreaker [52%], Crystal Reaper [0%], Exalted Staff [12%], Permafrost Prism [43%], Longbow [42%], Carving Sword [20%], Permafrost Prism [43%], Arcane Staff [15%], Carrioncaller [2%], Kingmaker [4%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 1 (p10 0 / p50 2 / p90 4) in; dps 8 (p10 5 / p50 7 / p90 9) in
- identity: split (None); conflicts: 2H_SCYTHE_CRYSTAL, 2H_CLEAVER_HELL, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange anti_dive, buff_allies, knockback_displace, mobility, tankiness; purple -
- evidence: never fielded 2H_SCYTHE_CRYSTAL; rare 2H_HALBERD_MORGANA; pairs seen 54/91; nearest roster Jaccard 0.25 (size 15)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Territory Defense - 15 - brawl

Evidence cell: 87 distinct rosters (87 sightings, holdout); role row: `styles[brawl][15]`.

**rank 0 (the button)** - score 74.767, feasible True, filler [], held []

- roster: Nature Staff [9%], Hand of Justice [0%], Heavy Mace [39%], Fallen Staff [14%], Incubus Mace [10%], Icicle Staff [5%], Realmbreaker [47%], Exalted Staff [13%], Carving Sword [33%], Fists of Avalon [5%], Hellfire Hands [3%], Great Arcane Staff [23%], Battle Bracers [54%], Rotcaller Staff [3%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 1.5 / p90 3) in; dps 7 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, disengage, heal_sustain, knockback_displace, mobility, tankiness, zone_control; purple anti_dive; optional short execute
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 33/105; nearest roster Jaccard 0.29 (size 16)

**rank 1 (refresh, 1 slots differ)** - score 74.55, feasible True, filler [], held []

- roster: Blight Staff [29%], Hand of Justice [0%], Heavy Mace [39%], Nature Staff [9%], Incubus Mace [10%], Icicle Staff [5%], Realmbreaker [47%], Exalted Staff [13%], Carving Sword [33%], Fists of Avalon [5%], Hellfire Hands [3%], Great Arcane Staff [23%], Battle Bracers [54%], Rotcaller Staff [3%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 1.5 / p90 3) in; dps 7 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, disengage, heal_burst, knockback_displace, mobility, peel, tankiness; purple anti_dive; optional short execute
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 35/105; nearest roster Jaccard 0.32 (size 14)

**rank 2 (refresh, 1 slots differ)** - score 74.518, feasible True, filler [], held []

- roster: Blight Staff [29%], Hand of Justice [0%], Heavy Mace [39%], Fallen Staff [14%], Incubus Mace [10%], Icicle Staff [5%], Realmbreaker [47%], Exalted Staff [13%], Carving Sword [33%], Fists of Avalon [5%], Hellfire Hands [3%], Great Arcane Staff [23%], Battle Bracers [54%], Rotcaller Staff [3%], Spiked Gauntlets [28%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 1.5 / p90 3) in; dps 7 (p10 6 / p50 8 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, disengage, heal_burst, heal_sustain, mobility, tankiness, zone_control; purple anti_dive; optional short execute
- evidence: never fielded 2H_HAMMER_AVALON; rare -; pairs seen 39/105; nearest roster Jaccard 0.32 (size 14)

### Territory Defense - 15 - clap

Evidence cell: 176 distinct rosters (177 sightings, holdout); role row: `styles[clap][15]`.

**rank 0 (the button)** - score 81.315, feasible True, filler [], held []

- roster: Hand of Justice [12%], Nature Staff [11%], Heavy Mace [40%], Dawnsong [40%], Fallen Staff [22%], Grailseeker [1%], Realmbreaker [60%], Exalted Staff [14%], Permafrost Prism [59%], Spiked Gauntlets [57%], Fists of Avalon [2%], Occult Staff [21%], Great Arcane Staff [30%], Carrioncaller [3%], Wailing Bow [8%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange disengage, heal_sustain, mobility, resist_shred, tankiness, zone_control; purple root; optional short execute
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON; pairs seen 62/105; nearest roster Jaccard 0.39 (size 17)

**rank 1 (refresh, 1 slots differ)** - score 81.273, feasible True, filler [], held []

- roster: Hand of Justice [12%], Nature Staff [11%], Heavy Mace [40%], Dawnsong [40%], Fallen Staff [22%], Grailseeker [1%], Realmbreaker [60%], Exalted Staff [14%], Permafrost Prism [59%], Spiked Gauntlets [57%], Fists of Avalon [2%], Occult Staff [21%], Great Arcane Staff [30%], Carrioncaller [3%], Skystrider Bow [1%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange heal_sustain, resist_shred, tankiness, zone_control; purple root; optional short execute
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_BOW_CRYSTAL; pairs seen 54/105; nearest roster Jaccard 0.39 (size 17)

**rank 2 (refresh, 2 slots differ)** - score 81.13, feasible True, filler [], held []

- roster: Hand of Justice [12%], Rampant Staff [14%], Heavy Mace [40%], Dawnsong [40%], Fallen Staff [22%], Grailseeker [1%], Realmbreaker [60%], Exalted Staff [14%], Permafrost Prism [59%], Spiked Gauntlets [57%], Fists of Avalon [2%], Occult Staff [21%], Great Arcane Staff [30%], Carrioncaller [3%], Skystrider Bow [1%]
- roles: healer 3 (p10 2 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, resist_shred, tankiness, zone_control; purple -; optional short execute
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_BOW_CRYSTAL; pairs seen 55/105; nearest roster Jaccard 0.39 (size 17)

### Territory Defense - 15 - kite

Evidence cell: 176 distinct rosters (180 sightings, all); role row: `styles[kite][15]`.

**rank 0 (the button)** - score 74.63, feasible True, filler [], held []

- roster: Hand of Justice [20%], Blight Staff [30%], Great Hammer [5%], Dawnsong [33%], Fallen Staff [23%], Grailseeker [13%], Realmbreaker [39%], Exalted Staff [16%], Icicle Staff [25%], Fists of Avalon [3%], Skystrider Bow [0%], Bedrock Mace [52%], Spiked Gauntlets [38%], Arcane Staff [38%], Carrioncaller [2%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4.5) in; dps 6 (p10 4 / p50 6 / p90 8.5) in
- identity: kite (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness, zone_control; purple catch; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL; rare 2H_HALBERD_MORGANA; pairs seen 57/105; nearest roster Jaccard 0.33 (size 17)

**rank 1 (refresh, 3 slots differ)** - score 74.54, feasible True, filler [], held []

- roster: Hand of Justice [20%], Blight Staff [30%], Great Hammer [5%], Dawnsong [33%], Fallen Staff [23%], Grailseeker [13%], Realmbreaker [39%], Exalted Staff [16%], Fists of Avalon [3%], Permafrost Prism [46%], Skystrider Bow [0%], Bedrock Mace [52%], Hellfire Hands [8%], Arcane Staff [38%], Occult Staff [36%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 2 (p10 1 / p50 2 / p90 4.5) in; dps 6 (p10 4 / p50 6 / p90 8.5) in
- identity: clap_kite (leaning) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness; purple -; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL; rare -; pairs seen 63/105; nearest roster Jaccard 0.35 (size 16)

**rank 2 (refresh, 1 slots differ)** - score 74.539, feasible True, filler [], held []

- roster: Hand of Justice [20%], Blight Staff [30%], Great Hammer [5%], Dawnsong [33%], Fallen Staff [23%], Grailseeker [13%], Realmbreaker [39%], Exalted Staff [16%], Fists of Avalon [3%], Permafrost Prism [46%], Skystrider Bow [0%], Bedrock Mace [52%], Carrioncaller [2%], Arcane Staff [38%], Spiked Gauntlets [38%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 4 (p10 2 / p50 4 / p90 5) in; support 1 (p10 1 / p50 2 / p90 4.5) in; dps 7 (p10 4 / p50 6 / p90 8.5) in
- identity: clap_kite (leaning) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, resist_shred, slow, tankiness; purple -; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL; rare 2H_HALBERD_MORGANA; pairs seen 57/105; nearest roster Jaccard 0.39 (size 17)

### Territory Defense - 15 - brawl_clap

Evidence cell: 26 distinct rosters (26 sightings, all); role row: `pooled[15]`.

**rank 0 (the button)** - score 79.793, feasible True, filler [], held []

- roster: Grailseeker [0%], Nature Staff [42%], Heavy Mace [58%], Fallen Staff [12%], Polehammer [19%], Dawnsong [4%], Exalted Staff [38%], Realmbreaker [42%], Fists of Avalon [0%], Occult Staff [4%], Battle Bracers [96%], Rootbound Staff [27%], Carving Sword [4%], Kingmaker [0%], Permafrost Prism [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: split (None) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_CLEAVER_HELL, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, disengage, knockback_displace, mobility, resist_shred, tankiness; purple catch, root, stun
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON; rare -; pairs seen 19/105; nearest roster Jaccard 0.28 (size 17)

**rank 1 (refresh, 1 slots differ)** - score 79.727, feasible True, filler [], held []

- roster: Grailseeker [0%], Blight Staff [8%], Heavy Mace [58%], Fallen Staff [12%], Polehammer [19%], Dawnsong [4%], Exalted Staff [38%], Realmbreaker [42%], Fists of Avalon [0%], Occult Staff [4%], Battle Bracers [96%], Rootbound Staff [27%], Carving Sword [4%], Kingmaker [0%], Permafrost Prism [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: split (None) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_CLEAVER_HELL, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, disengage, heal_burst, mobility, resist_shred, tankiness; purple catch, root, stun
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON; rare -; pairs seen 13/105; nearest roster Jaccard 0.23 (size 17)

**rank 2 (refresh, 1 slots differ)** - score 79.698, feasible True, filler [], held []

- roster: Grailseeker [0%], Rampant Staff [0%], Heavy Mace [58%], Fallen Staff [12%], Polehammer [19%], Dawnsong [4%], Exalted Staff [38%], Realmbreaker [42%], Fists of Avalon [0%], Occult Staff [4%], Battle Bracers [96%], Rootbound Staff [27%], Carving Sword [4%], Kingmaker [0%], Permafrost Prism [27%]
- roles: healer 3 (p10 1 / p50 3 / p90 4) in; frontline 3 (p10 1 / p50 3 / p90 5) in; support 2 (p10 0 / p50 2 / p90 4) in; dps 7 (p10 5 / p50 7 / p90 9) in
- identity: split (None) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_CLEAVER_HELL, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, disengage, heal_burst, mobility, resist_shred, tankiness; purple catch, root, stun
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_NATURESTAFF_KEEPER, 2H_KNUCKLES_AVALON, 2H_CLAYMORE_AVALON; rare -; pairs seen 13/105; nearest roster Jaccard 0.23 (size 17)

### Territory Defense - 15 - clap_kite

Evidence cell: 43 distinct rosters (43 sightings, holdout); role row: `styles[clap_kite][15]`.

**rank 0 (the button)** - score 78.477, feasible True, filler [], held []

- roster: Hand of Justice [23%], Blight Staff [30%], Heavy Mace [26%], Dawnsong [79%], Fallen Staff [9%], Polehammer [40%], Realmbreaker [81%], Grailseeker [0%], Exalted Staff [21%], Fists of Avalon [0%], Hellfire Hands [2%], Permafrost Prism [100%], Spiked Gauntlets [70%], Occult Staff [63%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 4 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 6 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange buff_allies, disengage, heal_burst, interrupt, knockback_displace, peel, root, slow, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON; rare -; pairs seen 50/105; nearest roster Jaccard 0.43 (size 15)

**rank 1 (refresh, 1 slots differ)** - score 78.451, feasible True, filler [], held []

- roster: Hand of Justice [23%], Rampant Staff [9%], Heavy Mace [26%], Dawnsong [79%], Fallen Staff [9%], Polehammer [40%], Realmbreaker [81%], Grailseeker [0%], Exalted Staff [21%], Fists of Avalon [0%], Hellfire Hands [2%], Permafrost Prism [100%], Spiked Gauntlets [70%], Occult Staff [63%], Rootbound Staff [14%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 4 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 6 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange buff_allies, disengage, heal_burst, interrupt, knockback_displace, peel, root, slow, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON; rare -; pairs seen 48/105; nearest roster Jaccard 0.36 (size 15)

**rank 2 (refresh, 1 slots differ)** - score 78.084, feasible True, filler [], held []

- roster: Hand of Justice [23%], Blight Staff [30%], Heavy Mace [26%], Dawnsong [79%], Fallen Staff [9%], Polehammer [40%], Realmbreaker [81%], Grailseeker [0%], Exalted Staff [21%], Fists of Avalon [0%], Hellfire Hands [2%], Permafrost Prism [100%], Spiked Gauntlets [70%], Occult Staff [63%], Enigmatic Staff [7%]
- roles: healer 3 (p10 2 / p50 2 / p90 4) in; frontline 4 (p10 2.9 / p50 4 / p90 6) in; support 2 (p10 1 / p50 2 / p90 4) in; dps 6 (p10 4 / p50 6 / p90 8) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red anti_dive; orange buff_allies, disengage, heal_burst, interrupt, knockback_displace, peel, root, slow, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON; rare -; pairs seen 46/105; nearest roster Jaccard 0.43 (size 15)

### Territory Defense - 20 - balanced

Evidence cell: 357 distinct rosters (365 sightings, holdout); role row: `pooled[20]`.

**rank 0 (the button)** - score 74.264, feasible True, filler [], held []

- roster: Hand of Justice [21%], Nature Staff [16%], Heavy Mace [43%], Fallen Staff [17%], Grailseeker [2%], Polehammer [39%], Dawnsong [52%], Realmbreaker [77%], Exalted Staff [31%], Great Hammer [5%], Great Holy Staff [2%], Crystal Reaper [0%], Carving Sword [22%], Hellfire Hands [6%], Spiked Gauntlets [68%], Weeping Repeater [0%], Longbow [39%], Occult Staff [33%], Kingmaker [5%], Rootbound Staff [32%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange slow, tankiness; purple catch; optional short anti_zone
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL; pairs seen 112/190; nearest roster Jaccard 0.36 (size 18)

**rank 1 (refresh, 2 slots differ)** - score 74.208, feasible True, filler [], held []

- roster: Hand of Justice [21%], Nature Staff [16%], Heavy Mace [43%], Fallen Staff [17%], Grailseeker [2%], Polehammer [39%], Dawnsong [52%], Realmbreaker [77%], Exalted Staff [31%], Great Hammer [5%], Great Holy Staff [2%], Crystal Reaper [0%], Carving Sword [22%], Permafrost Prism [56%], Spiked Gauntlets [68%], Carrioncaller [2%], Longbow [39%], Occult Staff [33%], Kingmaker [5%], Rootbound Staff [32%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange tankiness; purple catch; optional short anti_zone
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL; pairs seen 121/190; nearest roster Jaccard 0.36 (size 18)

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 74.281, feasible True, filler [], held []

- roster: Hand of Justice [21%], Nature Staff [16%], Heavy Mace [43%], Fallen Staff [17%], Grailseeker [2%], Polehammer [39%], Dawnsong [52%], Realmbreaker [77%], Exalted Staff [31%], Great Hammer [5%], Great Holy Staff [2%], Rotcaller Staff [30%], Carving Sword [22%], Fists of Avalon [1%], Spiked Gauntlets [68%], Energy Shaper [12%], Longbow [39%], Occult Staff [33%], Kingmaker [5%], Rootbound Staff [32%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange tankiness; purple catch; optional short anti_zone
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON; pairs seen 131/190; nearest roster Jaccard 0.34 (size 19)

### Territory Defense - 20 - brawl

Evidence cell: 43 distinct rosters (44 sightings, holdout); role row: `styles[brawl][20]`.

**rank 0 (the button)** - score 75.818, feasible True, filler [], held []

- roster: Blight Staff [23%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Hellfire Hands [2%], Great Holy Staff [0%], Exalted Staff [33%], Occult Staff [5%], Carving Sword [33%], Fists of Avalon [0%], Realmbreaker [58%], Kingmaker [14%], Crystal Reaper [0%], Battle Bracers [56%], Rotcaller Staff [14%], Rootbound Staff [26%], Spiked Gauntlets [33%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 2 (p10 2 / p50 3 / p90 4) in; dps 10 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe, damage_debuff, disengage, heal_burst, mobility, tankiness, zone_control; purple heal_reduction; optional short anti_zone
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 45/190; nearest roster Jaccard 0.30 (size 19)

**rank 1 (refresh, 2 slots differ)** - score 75.781, feasible True, filler [], held []

- roster: Blight Staff [23%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Hellfire Hands [2%], Great Holy Staff [0%], Exalted Staff [33%], Icicle Staff [9%], Carving Sword [33%], Fists of Avalon [0%], Malevolent Locus [26%], Kingmaker [14%], Crystal Reaper [0%], Battle Bracers [56%], Rotcaller Staff [14%], Rootbound Staff [26%], Spiked Gauntlets [33%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 3 (p10 2 / p50 3 / p90 4) in; dps 9 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, damage_debuff, disengage, heal_burst, mobility, tankiness; purple -; optional short anti_zone
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 44/190; nearest roster Jaccard 0.30 (size 19)

**rank 2 (refresh, 2 slots differ)** - score 75.728, feasible True, filler [], held []

- roster: Blight Staff [23%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Hellfire Hands [2%], Great Holy Staff [0%], Exalted Staff [33%], Icicle Staff [9%], Carving Sword [33%], Fists of Avalon [0%], Kingmaker [14%], Enigmatic Staff [21%], Crystal Reaper [0%], Battle Bracers [56%], Rotcaller Staff [14%], Rootbound Staff [26%], Spiked Gauntlets [33%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 3 (p10 2 / p50 3 / p90 4) in; dps 9 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_aoe, damage_debuff, heal_burst, mobility, resist_shred, tankiness; purple -; optional short anti_zone
- evidence: never fielded 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 40/190; nearest roster Jaccard 0.26 (size 19)

### Territory Defense - 20 - clap

Evidence cell: 155 distinct rosters (159 sightings, holdout); role row: `styles[clap][20]`.

**rank 0 (the button)** - score 82.341, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Dawnsong [57%], Fallen Staff [17%], Realmbreaker [83%], Grailseeker [1%], Exalted Staff [28%], Fists of Avalon [1%], Carrioncaller [2%], Nature Staff [17%], Great Hammer [6%], Permafrost Prism [59%], Wailing Bow [6%], Spiked Gauntlets [70%], Occult Staff [27%], Rootbound Staff [37%], Heavy Crossbow [2%], Energy Shaper [17%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, mobility, peel, tankiness; purple catch, root; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA, 2H_CROSSBOWLARGE; pairs seen 105/190; nearest roster Jaccard 0.36 (size 18)

**rank 1 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 82.353, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Dawnsong [57%], Fallen Staff [17%], Realmbreaker [83%], Grailseeker [1%], Exalted Staff [28%], Fists of Avalon [1%], Carrioncaller [2%], Nature Staff [17%], Great Hammer [6%], Permafrost Prism [59%], Wailing Bow [6%], Spiked Gauntlets [70%], Occult Staff [27%], Rootbound Staff [37%], Heavy Crossbow [2%], Rift Glaive [21%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, disengage, heal_burst, mobility, tankiness; purple catch, root; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA, 2H_CROSSBOWLARGE; pairs seen 104/190; nearest roster Jaccard 0.36 (size 18)

**rank 2 (refresh, 1 slots differ)** - score 82.269, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Dawnsong [57%], Fallen Staff [17%], Realmbreaker [83%], Grailseeker [1%], Exalted Staff [28%], Fists of Avalon [1%], Carrioncaller [2%], Nature Staff [17%], Spiked Gauntlets [70%], Permafrost Prism [59%], Great Hammer [6%], Wailing Bow [6%], Occult Staff [27%], Rootbound Staff [37%], Rift Glaive [21%], Energy Shaper [17%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, disengage, heal_burst, mobility, tankiness; purple catch, root; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA; pairs seen 119/190; nearest roster Jaccard 0.36 (size 18)

### Territory Defense - 20 - kite

Evidence cell: 125 distinct rosters (140 sightings, all); role row: `styles[kite][20]`.

**rank 0 (the button)** - score 75.137, feasible True, filler [], held []

- roster: Hand of Justice [37%], Blight Staff [27%], Great Hammer [2%], Dawnsong [49%], Exalted Staff [40%], Grailseeker [4%], Realmbreaker [73%], Grovekeeper [2%], Fallen Staff [20%], Skystrider Bow [0%], Fists of Avalon [0%], Hallowfall [86%], Carrioncaller [2%], Hellfire Hands [4%], Occult Staff [63%], Bedrock Mace [84%], Weeping Repeater [0%], Great Arcane Staff [59%], Spiked Gauntlets [71%], Enigmatic Staff [10%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 3 (p10 3 / p50 4 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 8) in
- identity: clap_kite (leaning) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, knockback_displace, slow, tankiness; purple -; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL, 2H_KNUCKLES_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HAMMER, 2H_RAM_KEEPER, 2H_HALBERD_MORGANA; pairs seen 69/190; nearest roster Jaccard 0.31 (size 18)

**rank 1 (refresh, 1 slots differ)** - score 75.098, feasible True, filler [], held []

- roster: Hand of Justice [37%], Blight Staff [27%], Great Hammer [2%], Dawnsong [49%], Exalted Staff [40%], Grailseeker [4%], Realmbreaker [73%], Grovekeeper [2%], Fallen Staff [20%], Skystrider Bow [0%], Fists of Avalon [0%], Hallowfall [86%], Longbow [38%], Hellfire Hands [4%], Occult Staff [63%], Bedrock Mace [84%], Weeping Repeater [0%], Great Arcane Staff [59%], Spiked Gauntlets [71%], Enigmatic Staff [10%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 3 (p10 3 / p50 4 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 8) in
- identity: clap_kite (leaning) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, knockback_displace, tankiness; purple -; optional short execute
- evidence: never fielded 2H_BOW_CRYSTAL, 2H_KNUCKLES_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HAMMER, 2H_RAM_KEEPER; pairs seen 83/190; nearest roster Jaccard 0.34 (size 19)

**rank 2 (refresh, 2 slots differ)** - score 75.076, feasible True, filler [], held []

- roster: Hand of Justice [37%], Blight Staff [27%], Great Hammer [2%], Dawnsong [49%], Exalted Staff [40%], Grailseeker [4%], Realmbreaker [73%], Grovekeeper [2%], Fallen Staff [20%], Bow of Badon [2%], Fists of Avalon [0%], Hallowfall [86%], Longbow [38%], Hellfire Hands [4%], Occult Staff [63%], Bedrock Mace [84%], Weeping Repeater [0%], Great Arcane Staff [59%], Spiked Gauntlets [71%], Enigmatic Staff [10%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 3 (p10 3 / p50 4 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 8) in
- identity: kite (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, knockback_displace, tankiness; purple -; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HAMMER, 2H_RAM_KEEPER; pairs seen 84/190; nearest roster Jaccard 0.34 (size 19)

### Territory Defense - 20 - brawl_clap

Evidence cell: 27 distinct rosters (33 sightings, all); role row: `pooled[20]`.

**rank 0 (the button)** - score 80.638, feasible True, filler [], held []

- roster: Grailseeker [0%], Nature Staff [41%], Heavy Mace [78%], Great Holy Staff [0%], Polehammer [30%], Dawnsong [15%], Witchwork Staff [0%], Great Hammer [7%], Exalted Staff [48%], Realmbreaker [78%], Fallen Staff [4%], Fists of Avalon [0%], Battle Bracers [100%], Occult Staff [0%], Longbow [4%], Crystal Reaper [0%], Carving Sword [15%], Kingmaker [0%], Hellfire Hands [0%], Rootbound Staff [67%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: split (None) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_SCYTHE_CRYSTAL, 2H_CLEAVER_HELL, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, max_health_cut, mobility, tankiness; purple catch, clump_create, root; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, MAIN_ARCANESTAFF_UNDEAD, 2H_KNUCKLES_AVALON, 2H_ARCANESTAFF_HELL, 2H_SCYTHE_CRYSTAL, 2H_CLAYMORE_AVALON, 2H_KNUCKLES_HELL; rare -; pairs seen 31/190; nearest roster Jaccard 0.22 (size 19)

**rank 1 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 80.826, feasible True, filler [], held []

- roster: Grailseeker [0%], Great Holy Staff [0%], Heavy Mace [78%], Hallowfall [100%], Polehammer [30%], Dawnsong [15%], Witchwork Staff [0%], Great Hammer [7%], Exalted Staff [48%], Realmbreaker [78%], Fallen Staff [4%], Fists of Avalon [0%], Battle Bracers [100%], Occult Staff [0%], Longbow [4%], Crystal Reaper [0%], Carving Sword [15%], Kingmaker [0%], Carrioncaller [0%], Rootbound Staff [67%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_SCYTHE_CRYSTAL, 2H_CLEAVER_HELL, 2H_CLAYMORE_AVALON
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, max_health_cut, mobility, tankiness; purple catch, clump_create, heal_reduction; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, MAIN_ARCANESTAFF_UNDEAD, 2H_KNUCKLES_AVALON, 2H_ARCANESTAFF_HELL, 2H_SCYTHE_CRYSTAL, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA; rare -; pairs seen 32/190; nearest roster Jaccard 0.25 (size 20)

**rank 2 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 80.841, feasible True, filler [], held []

- roster: Grailseeker [0%], Great Holy Staff [0%], Heavy Mace [78%], Hallowfall [100%], Polehammer [30%], Carrioncaller [0%], Witchwork Staff [0%], Great Hammer [7%], Exalted Staff [48%], Realmbreaker [78%], Fallen Staff [4%], Fists of Avalon [0%], Battle Bracers [100%], Occult Staff [0%], Longbow [4%], Crystal Reaper [0%], Carving Sword [15%], Kingmaker [0%], Hellfire Hands [0%], Rootbound Staff [67%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: brawl (strong) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange max_health_cut, mobility, tankiness; purple catch, clump_create; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, 2H_HALBERD_MORGANA, MAIN_ARCANESTAFF_UNDEAD, 2H_KNUCKLES_AVALON, 2H_ARCANESTAFF_HELL, 2H_SCYTHE_CRYSTAL, 2H_CLAYMORE_AVALON, 2H_KNUCKLES_HELL; rare -; pairs seen 27/190; nearest roster Jaccard 0.22 (size 19)

### Territory Defense - 20 - clap_kite

Evidence cell: 79 distinct rosters (82 sightings, holdout); role row: `styles[clap_kite][20]`.

**rank 0 (the button)** - score 80.085, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Grailseeker [2%], Hallowfall [95%], Dawnsong [81%], Polehammer [57%], Realmbreaker [89%], Carrioncaller [0%], Exalted Staff [43%], Witchwork Staff [63%], Fists of Avalon [1%], Hallowfall [95%], Permafrost Prism [95%], Spiked Gauntlets [86%], Bedrock Mace [94%], Occult Staff [73%], Longbow [30%], Hellfire Hands [6%], Great Arcane Staff [61%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 6 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 9) in
- identity: clap_kite (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange anti_dive, buff_allies, slow; purple -; optional short anti_zone, execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_KNUCKLES_AVALON; pairs seen 110/171; nearest roster Jaccard 0.50 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 1 slots differ)** - score 80.022, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Grailseeker [2%], Fallen Staff [23%], Dawnsong [81%], Polehammer [57%], Realmbreaker [89%], Carrioncaller [0%], Exalted Staff [43%], Witchwork Staff [63%], Fists of Avalon [1%], Hallowfall [95%], Permafrost Prism [95%], Spiked Gauntlets [86%], Bedrock Mace [94%], Occult Staff [73%], Longbow [30%], Hellfire Hands [6%], Great Arcane Staff [61%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 6 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 9) in
- identity: clap_kite (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange anti_dive, buff_allies, disengage, knockback_displace, slow; purple -; optional short anti_zone, execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_KNUCKLES_AVALON; pairs seen 123/190; nearest roster Jaccard 0.46 (size 18)

**rank 2 (refresh, 1 slots differ)** - score 80.056, feasible True, filler [], held []

- roster: Hand of Justice [33%], Rampant Staff [38%], Heavy Mace [13%], Grailseeker [2%], Hallowfall [95%], Dawnsong [81%], Polehammer [57%], Realmbreaker [89%], Carrioncaller [0%], Exalted Staff [43%], Witchwork Staff [63%], Hallowfall [95%], Fists of Avalon [1%], Permafrost Prism [95%], Spiked Gauntlets [86%], Bedrock Mace [94%], Occult Staff [73%], Longbow [30%], Hellfire Hands [6%], Great Arcane Staff [61%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 6 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 9) in
- identity: clap_kite (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange anti_dive, buff_allies, slow; purple -; optional short anti_zone, execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_KNUCKLES_AVALON; pairs seen 110/171; nearest roster Jaccard 0.56 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Territory Defense - 25 - balanced

Evidence cell: 357 distinct rosters (365 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 75.302, feasible True, filler [], held []

- roster: Hand of Justice [21%], Wild Staff [7%], Heavy Mace [43%], Fallen Staff [17%], Polehammer [39%], Dawnsong [52%], Grailseeker [2%], Realmbreaker [77%], Great Holy Staff [2%], Crystal Reaper [0%], Great Hammer [5%], Exalted Staff [31%], Grovekeeper [2%], Hallowfall [93%], Fists of Avalon [1%], Permafrost Prism [56%], Weeping Repeater [0%], Longbow [39%], Carrioncaller [2%], Bedrock Mace [39%], Kingmaker [5%], Energy Shaper [12%], Incubus Mace [15%], Occult Staff [33%], Rootbound Staff [32%]
- roles: no evidence row
- identity: clap (strong); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange -; purple catch, purge; optional short anti_zone
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 157/300; nearest roster Jaccard 0.32 (size 20)

**rank 1 (refresh, 1 slots differ)** - score 75.258, feasible True, filler [], held []

- roster: Hand of Justice [21%], Wild Staff [7%], Heavy Mace [43%], Fallen Staff [17%], Polehammer [39%], Dawnsong [52%], Grailseeker [2%], Realmbreaker [77%], Great Holy Staff [2%], Crystal Reaper [0%], Great Hammer [5%], Exalted Staff [31%], Grovekeeper [2%], Hallowfall [93%], Fists of Avalon [1%], Permafrost Prism [56%], Spiked Gauntlets [68%], Weeping Repeater [0%], Carrioncaller [2%], Bedrock Mace [39%], Kingmaker [5%], Energy Shaper [12%], Incubus Mace [15%], Occult Staff [33%], Rootbound Staff [32%]
- roles: no evidence row
- identity: clap (strong); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange slow; purple purge; optional short anti_zone
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 156/300; nearest roster Jaccard 0.36 (size 20)

**rank 2 (refresh, 1 slots differ)** - score 75.229, feasible True, filler [], held []

- roster: Hand of Justice [21%], Wild Staff [7%], Heavy Mace [43%], Fallen Staff [17%], Polehammer [39%], Dawnsong [52%], Grailseeker [2%], Realmbreaker [77%], Great Holy Staff [2%], Crystal Reaper [0%], Great Hammer [5%], Exalted Staff [31%], Grovekeeper [2%], Hallowfall [93%], Fists of Avalon [1%], Permafrost Prism [56%], Spiked Gauntlets [68%], Longbow [39%], Carrioncaller [2%], Bedrock Mace [39%], Kingmaker [5%], Energy Shaper [12%], Incubus Mace [15%], Occult Staff [33%], Rootbound Staff [32%]
- roles: no evidence row
- identity: clap (strong); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange -; purple purge; optional short anti_zone
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 177/300; nearest roster Jaccard 0.36 (size 20)

### Territory Defense - 25 - brawl

Evidence cell: 43 distinct rosters (44 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 77.0, feasible True, filler [], held []

- roster: Hallowfall [98%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Grailseeker [0%], Crystal Reaper [0%], Great Holy Staff [0%], Nature Staff [44%], Realmbreaker [58%], Fists of Avalon [0%], Carving Sword [33%], Battle Bracers [56%], Icicle Staff [9%], Exalted Staff [33%], Hallowfall [98%], Hellfire Hands [2%], Kingmaker [14%], Forgebark Staff [0%], Arcane Staff [23%], Bear Paws [16%], Rotcaller Staff [14%], Spiked Gauntlets [33%], Rift Glaive [0%]
- roles: no evidence row
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, resist_shred, tankiness, zone_control; purple clump_create, root; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, MAIN_NATURESTAFF_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 64/276; nearest roster Jaccard 0.26 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 1 slots differ)** - score 76.981, feasible True, filler [], held []

- roster: Blight Staff [23%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Grailseeker [0%], Crystal Reaper [0%], Great Holy Staff [0%], Nature Staff [44%], Realmbreaker [58%], Fists of Avalon [0%], Carving Sword [33%], Battle Bracers [56%], Icicle Staff [9%], Exalted Staff [33%], Hallowfall [98%], Hellfire Hands [2%], Kingmaker [14%], Forgebark Staff [0%], Arcane Staff [23%], Bear Paws [16%], Rotcaller Staff [14%], Spiked Gauntlets [33%], Rift Glaive [0%]
- roles: no evidence row
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, knockback_displace, mobility, resist_shred, tankiness; purple cleanse, clump_create, root; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, MAIN_NATURESTAFF_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 72/300; nearest roster Jaccard 0.26 (size 19)

**rank 2 (refresh, 1 slots differ)** - score 76.989, feasible True, filler [], held []

- roster: Hallowfall [98%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Incubus Mace [12%], Heavy Mace [46%], Grailseeker [0%], Crystal Reaper [0%], Great Holy Staff [0%], Nature Staff [44%], Realmbreaker [58%], Fists of Avalon [0%], Carving Sword [33%], Battle Bracers [56%], Icicle Staff [9%], Exalted Staff [33%], Hallowfall [98%], Hellfire Hands [2%], Kingmaker [14%], Forgebark Staff [0%], Malevolent Locus [26%], Bear Paws [16%], Rotcaller Staff [14%], Spiked Gauntlets [33%], Rift Glaive [0%]
- roles: no evidence row
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, damage_debuff, silence, tankiness; purple clump_create, root; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, MAIN_NATURESTAFF_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 69/276; nearest roster Jaccard 0.29 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Territory Defense - 25 - clap

Evidence cell: 155 distinct rosters (159 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 82.676, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Fallen Staff [17%], Dawnsong [57%], Grailseeker [1%], Realmbreaker [83%], Carrioncaller [2%], Hallowfall [91%], Spiked Gauntlets [70%], Fists of Avalon [1%], Exalted Staff [28%], Permafrost Prism [59%], Occult Staff [27%], Permafrost Prism [59%], Hallowfall [91%], Bedrock Mace [26%], Longbow [52%], Lightcaller [3%], Spirithunter [58%], Arcane Staff [18%], Forge Hammers [2%], Redemption Staff [17%], Wailing Bow [6%]
- roles: no evidence row
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange damage_debuff, max_health_cut, resist_shred, tankiness; purple catch; optional short anti_zone, execute
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, 2H_DUALHAMMER_HELL; pairs seen 146/253; nearest roster Jaccard 0.47 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2, 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 82.709, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Fallen Staff [17%], Dawnsong [57%], Grailseeker [1%], Realmbreaker [83%], Carrioncaller [2%], Arclight Blasters [0%], Spiked Gauntlets [70%], Fists of Avalon [1%], Exalted Staff [28%], Occult Staff [27%], Permafrost Prism [59%], Hallowfall [91%], Bedrock Mace [26%], Lightcaller [3%], Arcane Staff [18%], Forge Hammers [2%], Redemption Staff [17%], Longbow [52%], Lifecurse Staff [39%], Wailing Bow [6%], Wailing Bow [6%]
- roles: no evidence row
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange damage_debuff, max_health_cut, mobility, slow, tankiness, zone_control; purple purge, root; optional short anti_zone, execute
- evidence: never fielded 2H_DUALCROSSBOW_CRYSTAL; rare 2H_QUARTERSTAFF_AVALON, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, 2H_DUALHAMMER_HELL; pairs seen 146/276; nearest roster Jaccard 0.39 (size 18)
- hygiene: duplicates 2H_BOW_HELL x2

**rank 2 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 82.708, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Fallen Staff [17%], Dawnsong [57%], Grailseeker [1%], Realmbreaker [83%], Carrioncaller [2%], Arclight Blasters [0%], Spiked Gauntlets [70%], Fists of Avalon [1%], Exalted Staff [28%], Permafrost Prism [59%], Occult Staff [27%], Permafrost Prism [59%], Hallowfall [91%], Bedrock Mace [26%], Lightcaller [3%], Arcane Staff [18%], Forge Hammers [2%], Redemption Staff [17%], Wailing Bow [6%], Longbow [52%], Lifecurse Staff [39%]
- roles: no evidence row
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange damage_debuff, max_health_cut, peel, resist_shred, tankiness; purple catch, purge; optional short anti_zone, execute
- evidence: never fielded 2H_DUALCROSSBOW_CRYSTAL; rare 2H_QUARTERSTAFF_AVALON, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, 2H_DUALHAMMER_HELL; pairs seen 146/276; nearest roster Jaccard 0.38 (size 19)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Territory Defense - 25 - kite

Evidence cell: 125 distinct rosters (140 sightings, all, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 75.695, feasible True, filler [], held []

- roster: Blight Staff [27%], Hand of Justice [37%], Heavy Mace [22%], Dawnsong [49%], Exalted Staff [40%], Polehammer [42%], Realmbreaker [73%], Grailseeker [4%], Hellfire Hands [4%], Fallen Staff [20%], Rampant Staff [34%], Fists of Avalon [0%], Icicle Staff [28%], Hallowfall [86%], Heavy Crossbow [2%], Spiked Gauntlets [71%], Bedrock Mace [84%], Forgebark Staff [6%], Longbow [38%], Hallowfall [86%], Carrioncaller [2%], Forge Hammers [3%], Flamewalker Staff [1%], Lightcaller [0%], Enigmatic Staff [10%]
- roles: no evidence row
- identity: clap_kite (leaning) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red max_health_cut; orange anti_dive, buff_allies, cleanse, knockback_displace, resist_shred, slow, sustained_dps, tankiness; purple catch; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; rare 2H_CROSSBOWLARGE, 2H_HALBERD_MORGANA, MAIN_FIRESTAFF_CRYSTAL; pairs seen 119/276; nearest roster Jaccard 0.34 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 2 slots differ)** - score 75.67, feasible True, filler [], held []

- roster: Blight Staff [27%], Hand of Justice [37%], Heavy Mace [22%], Dawnsong [49%], Exalted Staff [40%], Polehammer [42%], Realmbreaker [73%], Grailseeker [4%], Hellfire Hands [4%], Fallen Staff [20%], Wild Staff [13%], Fists of Avalon [0%], Icicle Staff [28%], Hallowfall [86%], Rotcaller Staff [46%], Spiked Gauntlets [71%], Bedrock Mace [84%], Forgebark Staff [6%], Longbow [38%], Hallowfall [86%], Carrioncaller [2%], Forge Hammers [3%], Flamewalker Staff [1%], Lightcaller [0%], Enigmatic Staff [10%]
- roles: no evidence row
- identity: clap_kite (leaning) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red interrupt, max_health_cut; orange anti_dive, buff_allies, cleanse, knockback_displace, resist_shred, slow, sustained_dps, tankiness; purple catch; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; rare 2H_HALBERD_MORGANA, MAIN_FIRESTAFF_CRYSTAL; pairs seen 132/276; nearest roster Jaccard 0.39 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 2 (refresh, 1 slots differ)** - score 75.693, feasible True, filler [], held []

- roster: Blight Staff [27%], Hand of Justice [37%], Heavy Mace [22%], Heavy Crossbow [2%], Exalted Staff [40%], Polehammer [42%], Realmbreaker [73%], Grailseeker [4%], Hellfire Hands [4%], Fallen Staff [20%], Rampant Staff [34%], Fists of Avalon [0%], Icicle Staff [28%], Hallowfall [86%], Wailing Bow [10%], Spiked Gauntlets [71%], Bedrock Mace [84%], Forgebark Staff [6%], Longbow [38%], Hallowfall [86%], Carrioncaller [2%], Forge Hammers [3%], Flamewalker Staff [1%], Lightcaller [0%], Enigmatic Staff [10%]
- roles: no evidence row
- identity: clap_kite (leaning) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red max_health_cut; orange anti_dive, buff_allies, cleanse, knockback_displace, peel, resist_shred, slow, sustained_dps, tankiness; purple catch; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; rare 2H_CROSSBOWLARGE, 2H_HALBERD_MORGANA, MAIN_FIRESTAFF_CRYSTAL; pairs seen 115/276; nearest roster Jaccard 0.32 (size 20)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Territory Defense - 25 - brawl_clap

Evidence cell: 27 distinct rosters (33 sightings, all, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 82.268, feasible True, filler [], held []

- roster: Grailseeker [0%], Hallowfall [100%], Heavy Mace [78%], Fallen Staff [4%], Polehammer [30%], Dawnsong [15%], Hand of Justice [30%], Realmbreaker [78%], Great Holy Staff [0%], Great Hammer [7%], Permafrost Prism [15%], Wild Staff [0%], Fists of Avalon [0%], Crystal Reaper [0%], Battle Bracers [100%], Exalted Staff [48%], Kingmaker [0%], Dreadstorm Monarch [22%], Hallowfall [100%], Incubus Mace [30%], Carrioncaller [0%], Occult Staff [0%], Lightcaller [4%], Longbow [4%], Malevolent Locus [56%]
- roles: no evidence row
- identity: clap (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, mobility, tankiness; purple catch, clump_create, stun; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, 2H_WILDSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_ARCANESTAFF_HELL; rare -; pairs seen 49/276; nearest roster Jaccard 0.29 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 82.283, feasible True, filler [], held []

- roster: Grailseeker [0%], Blight Staff [11%], Heavy Mace [78%], Fallen Staff [4%], Polehammer [30%], Dawnsong [15%], Hand of Justice [30%], Realmbreaker [78%], Great Holy Staff [0%], Great Hammer [7%], Permafrost Prism [15%], Hallowfall [100%], Fists of Avalon [0%], Crystal Reaper [0%], Battle Bracers [100%], Exalted Staff [48%], Kingmaker [0%], Dreadstorm Monarch [22%], Hallowfall [100%], Incubus Mace [30%], Carrioncaller [0%], Occult Staff [0%], Lightcaller [4%], Longbow [4%], Malevolent Locus [56%]
- roles: no evidence row
- identity: clap (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, mobility, tankiness; purple catch, clump_create, stun; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_ARCANESTAFF_HELL; rare -; pairs seen 52/276; nearest roster Jaccard 0.29 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 2 (refresh, 1 slots differ)** - score 82.259, feasible True, filler [], held []

- roster: Grailseeker [0%], Rampant Staff [0%], Heavy Mace [78%], Fallen Staff [4%], Polehammer [30%], Dawnsong [15%], Hand of Justice [30%], Realmbreaker [78%], Great Holy Staff [0%], Great Hammer [7%], Permafrost Prism [15%], Hallowfall [100%], Fists of Avalon [0%], Crystal Reaper [0%], Battle Bracers [100%], Exalted Staff [48%], Kingmaker [0%], Dreadstorm Monarch [22%], Hallowfall [100%], Incubus Mace [30%], Carrioncaller [0%], Occult Staff [0%], Lightcaller [4%], Longbow [4%], Malevolent Locus [56%]
- roles: no evidence row
- identity: clap (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange burst_st, mobility, tankiness; purple catch, clump_create, heal_sustain, stun; optional short anti_zone
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_NATURESTAFF_KEEPER, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_SCYTHE_CRYSTAL, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_ARCANESTAFF_HELL; rare -; pairs seen 49/276; nearest roster Jaccard 0.29 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Territory Defense - 25 - clap_kite

Evidence cell: 79 distinct rosters (82 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 80.992, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Grailseeker [2%], Fallen Staff [23%], Polehammer [57%], Realmbreaker [89%], Dawnsong [81%], Witchwork Staff [63%], Carrioncaller [0%], Rampant Staff [38%], Hellfire Hands [6%], Great Hammer [1%], Hallowfall [95%], Fists of Avalon [1%], Occult Staff [73%], Exalted Staff [43%], Permafrost Prism [95%], Bedrock Mace [94%], Spiked Gauntlets [86%], Bedrock Mace [94%], Hallowfall [95%], Lightcaller [1%], Permafrost Prism [95%], Great Arcane Staff [61%]
- roles: no evidence row
- identity: clap_kite (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red max_health_cut; orange burst_aoe, disengage, heal_reduction, resist_shred, slow, tankiness; purple burst_st, damage_debuff; optional short anti_zone, execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_HAMMER, 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; pairs seen 121/231; nearest roster Jaccard 0.54 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2, 2H_ICECRYSTAL_UNDEAD x2, MAIN_ROCKMACE_KEEPER x2

**rank 1 (refresh, 1 slots differ)** - score 80.858, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Grailseeker [2%], Fallen Staff [23%], Polehammer [57%], Realmbreaker [89%], Dawnsong [81%], Witchwork Staff [63%], Carrioncaller [0%], Rampant Staff [38%], Hellfire Hands [6%], Great Hammer [1%], Hallowfall [95%], Fists of Avalon [1%], Occult Staff [73%], Exalted Staff [43%], Permafrost Prism [95%], Bedrock Mace [94%], Spiked Gauntlets [86%], Bedrock Mace [94%], Hallowfall [95%], Lightcaller [1%], Wailing Bow [5%], Great Arcane Staff [61%]
- roles: no evidence row
- identity: clap_kite (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red max_health_cut; orange burst_aoe, disengage, heal_reduction, resist_shred, slow, sustained_dps, tankiness, zone_control; purple burst_st, damage_debuff; optional short anti_zone, execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_HAMMER, 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; pairs seen 128/253; nearest roster Jaccard 0.50 (size 20)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2, MAIN_ROCKMACE_KEEPER x2

**rank 2 (refresh, 2 slots differ)** - score 80.837, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Grailseeker [2%], Fallen Staff [23%], Polehammer [57%], Realmbreaker [89%], Dawnsong [81%], Witchwork Staff [63%], Carrioncaller [0%], Rampant Staff [38%], Hellfire Hands [6%], Great Hammer [1%], Hallowfall [95%], Fists of Avalon [1%], Icicle Staff [18%], Exalted Staff [43%], Permafrost Prism [95%], Bedrock Mace [94%], Spiked Gauntlets [86%], Bedrock Mace [94%], Hallowfall [95%], Lightcaller [1%], Wailing Bow [5%], Great Arcane Staff [61%]
- roles: no evidence row
- identity: clap_kite (leaning)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red max_health_cut; orange buff_allies, burst_aoe, heal_reduction, slow, sustained_dps, tankiness, zone_control; purple burst_st, catch, damage_debuff; optional short anti_zone, execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_HAMMER, 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; pairs seen 125/253; nearest roster Jaccard 0.48 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2, MAIN_ROCKMACE_KEEPER x2

### Castle Fight - 20 - balanced

Evidence cell: 357 distinct rosters (365 sightings, holdout); role row: `pooled[20]`.

**rank 0 (the button)** - score 72.054, feasible True, filler [], held []

- roster: Hand of Justice [21%], Nature Staff [16%], Heavy Mace [43%], Fallen Staff [17%], Dawnsong [52%], Polehammer [39%], Crystal Reaper [0%], Exalted Staff [31%], Fists of Avalon [1%], Grovekeeper [2%], Great Holy Staff [2%], Hellfire Hands [6%], Permafrost Prism [56%], Kingmaker [5%], Permafrost Prism [56%], Carving Sword [22%], Longbow [39%], Occult Staff [33%], Rotcaller Staff [30%], Rootbound Staff [32%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 10 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange mobility, tankiness; purple catch
- evidence: never fielded -; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 100/171; nearest roster Jaccard 0.33 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 4 slots differ)** - score 72.037, feasible True, filler [], held []

- roster: Hand of Justice [21%], Redemption Staff [13%], Heavy Mace [43%], Fallen Staff [17%], Dawnsong [52%], Polehammer [39%], Crystal Reaper [0%], Exalted Staff [31%], Fists of Avalon [1%], Great Hammer [5%], Great Holy Staff [2%], Hellfire Hands [6%], Grailseeker [2%], Kingmaker [5%], Permafrost Prism [56%], Carving Sword [22%], Longbow [39%], Occult Staff [33%], Rotcaller Staff [30%], Malevolent Locus [25%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange tankiness; purple catch, purge
- evidence: never fielded -; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON, 2H_QUARTERSTAFF_AVALON; pairs seen 105/190; nearest roster Jaccard 0.29 (size 20)

**rank 2 (refresh, 5 slots differ)** - score 72.03, feasible True, filler [], held []

- roster: Hand of Justice [21%], Redemption Staff [13%], Heavy Mace [43%], Fallen Staff [17%], Grailseeker [2%], Polehammer [39%], Crystal Reaper [0%], Exalted Staff [31%], Fists of Avalon [1%], Great Hammer [5%], Great Holy Staff [2%], Hellfire Hands [6%], Great Fire Staff [2%], Kingmaker [5%], Permafrost Prism [56%], Carving Sword [22%], Longbow [39%], Occult Staff [33%], Rotcaller Staff [30%], Malevolent Locus [25%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap (leaning); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange tankiness; purple catch, purge
- evidence: never fielded -; rare 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 92/190; nearest roster Jaccard 0.25 (size 20)

### Castle Fight - 20 - brawl

Evidence cell: 43 distinct rosters (44 sightings, holdout); role row: `styles[brawl][20]`.

**rank 0 (the button)** - score 73.853, feasible True, filler [], held []

- roster: Nature Staff [44%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Crystal Reaper [0%], Heavy Mace [46%], Realmbreaker [58%], Great Holy Staff [0%], Great Hammer [2%], Exalted Staff [33%], Battle Bracers [56%], Forge Hammers [0%], Kingmaker [14%], Carving Sword [33%], Hellfire Hands [2%], Rootbound Staff [26%], Enigmatic Staff [21%], Spiked Gauntlets [33%], Fists of Avalon [0%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 2 (p10 2 / p50 3 / p90 4) in; dps 10 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe; purple -
- evidence: never fielded 2H_SCYTHE_CRYSTAL, 2H_HOLYSTAFF, 2H_DUALHAMMER_HELL, 2H_KNUCKLES_AVALON, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 44/190; nearest roster Jaccard 0.25 (size 20)

**rank 1 (refresh, 1 slots differ)** - score 73.799, feasible True, filler [], held []

- roster: Nature Staff [44%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Crystal Reaper [0%], Heavy Mace [46%], Realmbreaker [58%], Great Holy Staff [0%], Great Hammer [2%], Exalted Staff [33%], Battle Bracers [56%], Icicle Staff [9%], Kingmaker [14%], Carving Sword [33%], Hellfire Hands [2%], Rootbound Staff [26%], Enigmatic Staff [21%], Spiked Gauntlets [33%], Fists of Avalon [0%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 3 (p10 2 / p50 3 / p90 4) in; dps 9 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, tankiness; purple purge
- evidence: never fielded 2H_SCYTHE_CRYSTAL, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 45/190; nearest roster Jaccard 0.25 (size 20)

**rank 2 (refresh, 1 slots differ, OUTSCORES rank 0)** - score 73.935, feasible True, filler [], held []

- roster: Nature Staff [44%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Crystal Reaper [0%], Heavy Mace [46%], Realmbreaker [58%], Great Holy Staff [0%], Great Hammer [2%], Exalted Staff [33%], Battle Bracers [56%], Forge Hammers [0%], Kingmaker [14%], Carving Sword [33%], Hellfire Hands [2%], Rootbound Staff [26%], Occult Staff [5%], Spiked Gauntlets [33%], Fists of Avalon [0%], Rift Glaive [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 4 / p90 6) in; support 2 (p10 2 / p50 3 / p90 4) in; dps 10 (p10 7 / p50 9 / p90 10) in
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, mobility; purple -
- evidence: never fielded 2H_SCYTHE_CRYSTAL, 2H_HOLYSTAFF, 2H_DUALHAMMER_HELL, 2H_KNUCKLES_AVALON, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 39/190; nearest roster Jaccard 0.29 (size 20)

### Castle Fight - 20 - clap

Evidence cell: 155 distinct rosters (159 sightings, holdout); role row: `styles[clap][20]`.

**rank 0 (the button)** - score 80.238, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Dawnsong [57%], Polehammer [37%], Fallen Staff [17%], Carrioncaller [2%], Fists of Avalon [1%], Exalted Staff [28%], Great Hammer [6%], Permafrost Prism [59%], Nature Staff [17%], Bedrock Mace [26%], Spiked Gauntlets [70%], Wailing Bow [6%], Realmbreaker [83%], Icicle Staff [13%], Rootbound Staff [37%], Longbow [52%], Energy Shaper [17%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap_kite (leaning) - DISAGREES with clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange heal_burst, mobility; purple catch; optional short execute
- evidence: never fielded -; rare 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON; pairs seen 133/190; nearest roster Jaccard 0.36 (size 18)

**rank 1 (refresh, 2 slots differ)** - score 80.233, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Dawnsong [57%], Polehammer [37%], Fallen Staff [17%], Carrioncaller [2%], Fists of Avalon [1%], Exalted Staff [28%], Great Hammer [6%], Weeping Repeater [0%], Nature Staff [17%], Grailseeker [1%], Spiked Gauntlets [70%], Wailing Bow [6%], Realmbreaker [83%], Icicle Staff [13%], Rootbound Staff [37%], Longbow [52%], Energy Shaper [17%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap_kite (leaning) - DISAGREES with clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, mobility, peel, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, 2H_QUARTERSTAFF_AVALON; pairs seen 105/190; nearest roster Jaccard 0.27 (size 18)

**rank 2 (refresh, 1 slots differ)** - score 80.232, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Dawnsong [57%], Polehammer [37%], Fallen Staff [17%], Carrioncaller [2%], Fists of Avalon [1%], Exalted Staff [28%], Great Hammer [6%], Permafrost Prism [59%], Nature Staff [17%], Grailseeker [1%], Spiked Gauntlets [70%], Wailing Bow [6%], Realmbreaker [83%], Icicle Staff [13%], Rootbound Staff [37%], Longbow [52%], Energy Shaper [17%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 1 / p50 3 / p90 5) in; dps 9 (p10 7 / p50 8 / p90 10) in
- identity: clap_kite (leaning) - DISAGREES with clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, mobility, peel, tankiness; purple catch; optional short execute
- evidence: never fielded -; rare 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, 2H_QUARTERSTAFF_AVALON; pairs seen 120/190; nearest roster Jaccard 0.31 (size 18)

### Castle Fight - 20 - kite

Evidence cell: 125 distinct rosters (140 sightings, all); role row: `styles[kite][20]`.

**rank 0 (the button)** - score 72.622, feasible True, filler [], held []

- roster: Blight Staff [27%], Hand of Justice [37%], Great Hammer [2%], Dawnsong [49%], Exalted Staff [40%], Polehammer [42%], Hellfire Hands [4%], Grailseeker [4%], Fallen Staff [20%], Fists of Avalon [0%], Hallowfall [86%], Realmbreaker [73%], Weeping Repeater [0%], Heavy Mace [22%], Spiked Gauntlets [71%], Occult Staff [63%], Enigmatic Staff [10%], Astral Staff [0%], Carrioncaller [2%], Lightcaller [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 3 / p50 4 / p90 5) under; dps 9 (p10 6 / p50 7 / p90 8) over
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD, 2H_ARCANESTAFF_CRYSTAL, 2H_SHAPESHIFTER_AVALON; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 65/190; nearest roster Jaccard 0.31 (size 18)

**rank 1 (refresh, 1 slots differ)** - score 72.608, feasible True, filler [], held []

- roster: Blight Staff [27%], Hand of Justice [37%], Great Hammer [2%], Dawnsong [49%], Exalted Staff [40%], Polehammer [42%], Hellfire Hands [4%], Grailseeker [4%], Fallen Staff [20%], Fists of Avalon [0%], Hallowfall [86%], Realmbreaker [73%], Weeping Repeater [0%], Heavy Mace [22%], Spiked Gauntlets [71%], Occult Staff [63%], Wailing Bow [10%], Enigmatic Staff [10%], Carrioncaller [2%], Astral Staff [0%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 3 / p50 4 / p90 5) under; dps 9 (p10 6 / p50 7 / p90 8) over
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD, 2H_ARCANESTAFF_CRYSTAL; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 74/190; nearest roster Jaccard 0.31 (size 18)

**rank 2 (refresh, 1 slots differ)** - score 72.607, feasible True, filler [], held []

- roster: Blight Staff [27%], Hand of Justice [37%], Great Hammer [2%], Exalted Staff [40%], Polehammer [42%], Hellfire Hands [4%], Grailseeker [4%], Fallen Staff [20%], Fists of Avalon [0%], Hallowfall [86%], Realmbreaker [73%], Weeping Repeater [0%], Heavy Mace [22%], Spiked Gauntlets [71%], Occult Staff [63%], Enigmatic Staff [10%], Dawnsong [49%], Astral Staff [0%], Carrioncaller [2%], Rift Glaive [30%]
- roles: healer 4 (p10 3 / p50 4 / p90 4.3) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 2 (p10 3 / p50 4 / p90 5) under; dps 9 (p10 6 / p50 7 / p90 8) over
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, heal_burst, peel, tankiness; purple catch; optional short execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_REPEATINGCROSSBOW_UNDEAD, 2H_ARCANESTAFF_CRYSTAL; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 77/190; nearest roster Jaccard 0.31 (size 18)

### Castle Fight - 20 - brawl_clap

Evidence cell: 27 distinct rosters (33 sightings, all); role row: `pooled[20]`.

**rank 0 (the button)** - score 78.881, feasible True, filler [], held []

- roster: Grailseeker [0%], Nature Staff [41%], Heavy Mace [78%], Exalted Staff [48%], Polehammer [30%], Dawnsong [15%], Witchwork Staff [0%], Fallen Staff [4%], Great Hammer [7%], Great Holy Staff [0%], Realmbreaker [78%], Battle Bracers [100%], Kingmaker [0%], Crystal Reaper [0%], Carving Sword [15%], Carrioncaller [0%], Rootbound Staff [67%], Lightcaller [4%], Fists of Avalon [0%], Longbow [4%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 1 (p10 2 / p50 3 / p90 5) under; dps 10 (p10 7 / p50 8 / p90 10) in
- identity: split (None) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_CLAYMORE_AVALON, 2H_SCYTHE_CRYSTAL, 2H_CLEAVER_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange mobility, tankiness; purple catch, clump_create, heal_reduction
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, MAIN_ARCANESTAFF_UNDEAD, 2H_HOLYSTAFF, 2H_CLAYMORE_AVALON, 2H_SCYTHE_CRYSTAL, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON; rare -; pairs seen 31/190; nearest roster Jaccard 0.22 (size 19)

**rank 1 (refresh, 1 slots differ)** - score 78.868, feasible True, filler [], held []

- roster: Grailseeker [0%], Nature Staff [41%], Heavy Mace [78%], Exalted Staff [48%], Polehammer [30%], Dawnsong [15%], Witchwork Staff [0%], Fallen Staff [4%], Great Hammer [7%], Great Holy Staff [0%], Realmbreaker [78%], Battle Bracers [100%], Kingmaker [0%], Crystal Reaper [0%], Carving Sword [15%], Carrioncaller [0%], Rootbound Staff [67%], Fists of Avalon [0%], Lightcaller [4%], Spiked Gauntlets [56%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 5 (p10 3 / p50 5 / p90 6) in; support 1 (p10 2 / p50 3 / p90 5) under; dps 10 (p10 7 / p50 8 / p90 10) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_CLAYMORE_AVALON, 2H_SCYTHE_CRYSTAL, 2H_CLEAVER_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange mobility, tankiness; purple catch, clump_create, heal_reduction
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, MAIN_ARCANESTAFF_UNDEAD, 2H_HOLYSTAFF, 2H_CLAYMORE_AVALON, 2H_SCYTHE_CRYSTAL, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON; rare -; pairs seen 39/190; nearest roster Jaccard 0.26 (size 19)

**rank 2 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 78.946, feasible True, filler [], held []

- roster: Lightcaller [4%], Nature Staff [41%], Heavy Mace [78%], Exalted Staff [48%], Polehammer [30%], Dawnsong [15%], Witchwork Staff [0%], Fallen Staff [4%], Great Hammer [7%], Great Holy Staff [0%], Realmbreaker [78%], Battle Bracers [100%], Kingmaker [0%], Crystal Reaper [0%], Carving Sword [15%], Carrioncaller [0%], Rootbound Staff [67%], Fists of Avalon [0%], Hoarfrost Staff [0%], Permafrost Prism [15%]
- roles: healer 4 (p10 3 / p50 4 / p90 5) in; frontline 4 (p10 3 / p50 5 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 10 (p10 7 / p50 8 / p90 10) in
- identity: brawl (leaning) - DISAGREES with brawl_clap; conflicts: 2H_KNUCKLES_SET2, 2H_CLAYMORE_AVALON, 2H_SCYTHE_CRYSTAL, 2H_CLEAVER_HELL
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange mobility; purple stun
- evidence: never fielded MAIN_ARCANESTAFF_UNDEAD, 2H_HOLYSTAFF, 2H_CLAYMORE_AVALON, 2H_SCYTHE_CRYSTAL, 2H_HALBERD_MORGANA, 2H_KNUCKLES_AVALON, MAIN_FROSTSTAFF_KEEPER; rare -; pairs seen 34/190; nearest roster Jaccard 0.22 (size 19)

### Castle Fight - 20 - clap_kite

Evidence cell: 79 distinct rosters (82 sightings, holdout); role row: `styles[clap_kite][20]`.

**rank 0 (the button)** - score 77.632, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Exalted Staff [43%], Dawnsong [81%], Polehammer [57%], Witchwork Staff [63%], Realmbreaker [89%], Carrioncaller [0%], Fallen Staff [23%], Spiked Gauntlets [86%], Fists of Avalon [1%], Hallowfall [95%], Permafrost Prism [95%], Permafrost Prism [95%], Lightcaller [1%], Occult Staff [73%], Bedrock Mace [94%], Hellfire Hands [6%], Arcane Staff [51%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 5 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 6 / p50 7 / p90 9) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange buff_allies, peel; purple burst_st, purge, silence; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; pairs seen 108/171; nearest roster Jaccard 0.48 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ)** - score 77.607, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Exalted Staff [43%], Dawnsong [81%], Polehammer [57%], Witchwork Staff [63%], Realmbreaker [89%], Carrioncaller [0%], Fallen Staff [23%], Spiked Gauntlets [86%], Fists of Avalon [1%], Hallowfall [95%], Permafrost Prism [95%], Permafrost Prism [95%], Lightcaller [1%], Occult Staff [73%], Bedrock Mace [94%], Hellfire Hands [6%], Great Arcane Staff [61%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 5 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 9 (p10 6 / p50 7 / p90 9) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red burst_st, tankiness; orange buff_allies, peel; purple -; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; pairs seen 108/171; nearest roster Jaccard 0.48 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 3 slots differ)** - score 77.403, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Exalted Staff [43%], Dawnsong [81%], Polehammer [57%], Witchwork Staff [63%], Realmbreaker [89%], Carrioncaller [0%], Fallen Staff [23%], Spiked Gauntlets [86%], Fists of Avalon [1%], Hallowfall [95%], Permafrost Prism [95%], Grailseeker [2%], Occult Staff [73%], Permafrost Prism [95%], Quarterstaff [0%], Hellfire Hands [6%], Great Arcane Staff [61%]
- roles: healer 4 (p10 3 / p50 4 / p90 4) in; frontline 6 (p10 4 / p50 6 / p90 6) in; support 2 (p10 2 / p50 3 / p90 5) in; dps 8 (p10 6 / p50 7 / p90 9) in
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red buff_allies, burst_st, tankiness; orange peel; purple catch; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA, 2H_QUARTERSTAFF; rare 2H_KNUCKLES_AVALON; pairs seen 93/171; nearest roster Jaccard 0.43 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Castle Fight - 25 - balanced

Evidence cell: 357 distinct rosters (365 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 73.266, feasible True, filler [], held []

- roster: Hand of Justice [21%], Wild Staff [7%], Heavy Mace [43%], Exalted Staff [31%], Polehammer [39%], Dawnsong [52%], Crystal Reaper [0%], Hellfire Hands [6%], Fallen Staff [17%], Great Holy Staff [2%], Great Hammer [5%], Grovekeeper [2%], Realmbreaker [77%], Hallowfall [93%], Fists of Avalon [1%], Permafrost Prism [56%], Permafrost Prism [56%], Kingmaker [5%], Glacial Staff [4%], Bedrock Mace [39%], Occult Staff [33%], Weeping Repeater [0%], Incubus Mace [15%], Energy Shaper [12%], Rootbound Staff [32%]
- roles: no evidence row
- identity: clap (strong); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange -; purple -
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 149/276; nearest roster Jaccard 0.32 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 2 slots differ)** - score 73.238, feasible True, filler [], held []

- roster: Hand of Justice [21%], Wild Staff [7%], Heavy Mace [43%], Exalted Staff [31%], Polehammer [39%], Spiked Gauntlets [68%], Crystal Reaper [0%], Hellfire Hands [6%], Fallen Staff [17%], Great Holy Staff [2%], Great Hammer [5%], Grovekeeper [2%], Realmbreaker [77%], Hallowfall [93%], Fists of Avalon [1%], Permafrost Prism [56%], Permafrost Prism [56%], Kingmaker [5%], Weeping Repeater [0%], Bedrock Mace [39%], Occult Staff [33%], Longbow [39%], Incubus Mace [15%], Energy Shaper [12%], Rootbound Staff [32%]
- roles: no evidence row
- identity: clap (strong); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange -; purple -
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 161/276; nearest roster Jaccard 0.34 (size 18)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 3 slots differ, OUTSCORES rank 0)** - score 73.277, feasible True, filler [], held []

- roster: Hand of Justice [21%], Nature Staff [16%], Heavy Mace [43%], Exalted Staff [31%], Polehammer [39%], Dawnsong [52%], Crystal Reaper [0%], Spiked Gauntlets [68%], Fallen Staff [17%], Great Holy Staff [2%], Great Hammer [5%], Grovekeeper [2%], Realmbreaker [77%], Hallowfall [93%], Fists of Avalon [1%], Permafrost Prism [56%], Permafrost Prism [56%], Kingmaker [5%], Weeping Repeater [0%], Bedrock Mace [39%], Occult Staff [33%], Carrioncaller [2%], Incubus Mace [15%], Energy Shaper [12%], Rootbound Staff [32%]
- roles: no evidence row
- identity: clap (strong); conflicts: 2H_HOLYSTAFF
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange -; purple -
- evidence: never fielded 2H_REPEATINGCROSSBOW_UNDEAD; rare 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON; pairs seen 153/276; nearest roster Jaccard 0.36 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Castle Fight - 25 - brawl

Evidence cell: 43 distinct rosters (44 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 75.187, feasible True, filler [], held []

- roster: Hallowfall [98%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Heavy Mace [46%], Rotcaller Staff [14%], Crystal Reaper [0%], Grailseeker [0%], Great Holy Staff [0%], Redemption Staff [19%], Great Hammer [2%], Battle Bracers [56%], Exalted Staff [33%], Realmbreaker [58%], Kingmaker [14%], Icicle Staff [9%], Carving Sword [33%], Hallowfall [98%], Damnation Staff [37%], Fists of Avalon [0%], Forgebark Staff [0%], Hellfire Hands [2%], Spiked Gauntlets [33%], Enigmatic Staff [21%], Rift Glaive [0%]
- roles: no evidence row
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange buff_allies, burst_aoe, damage_debuff; purple clump_create
- evidence: never fielded 2H_SCYTHE_CRYSTAL, 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, MAIN_NATURESTAFF_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 56/276; nearest roster Jaccard 0.26 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 1 slots differ)** - score 75.186, feasible True, filler [], held []

- roster: Nature Staff [44%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Heavy Mace [46%], Rotcaller Staff [14%], Crystal Reaper [0%], Grailseeker [0%], Great Holy Staff [0%], Hallowfall [98%], Great Hammer [2%], Battle Bracers [56%], Exalted Staff [33%], Realmbreaker [58%], Kingmaker [14%], Icicle Staff [9%], Carving Sword [33%], Hallowfall [98%], Damnation Staff [37%], Fists of Avalon [0%], Forgebark Staff [0%], Hellfire Hands [2%], Spiked Gauntlets [33%], Enigmatic Staff [21%], Rift Glaive [0%]
- roles: no evidence row
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange buff_allies, burst_aoe, damage_debuff; purple clump_create
- evidence: never fielded 2H_SCYTHE_CRYSTAL, 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, MAIN_NATURESTAFF_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 60/276; nearest roster Jaccard 0.23 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 2 (refresh, 1 slots differ)** - score 75.17, feasible True, filler [], held []

- roster: Nature Staff [44%], Hand of Justice [5%], Polehammer [21%], Fallen Staff [12%], Heavy Mace [46%], Rotcaller Staff [14%], Crystal Reaper [0%], Grailseeker [0%], Great Holy Staff [0%], Redemption Staff [19%], Great Hammer [2%], Battle Bracers [56%], Exalted Staff [33%], Realmbreaker [58%], Kingmaker [14%], Icicle Staff [9%], Carving Sword [33%], Hallowfall [98%], Damnation Staff [37%], Fists of Avalon [0%], Forgebark Staff [0%], Hellfire Hands [2%], Spiked Gauntlets [33%], Enigmatic Staff [21%], Rift Glaive [0%]
- roles: no evidence row
- identity: brawl (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, burst_aoe, damage_debuff, mobility, tankiness; purple clump_create
- evidence: never fielded 2H_SCYTHE_CRYSTAL, 2H_QUARTERSTAFF_AVALON, 2H_HOLYSTAFF, 2H_KNUCKLES_AVALON, MAIN_NATURESTAFF_CRYSTAL, 2H_GLAIVE_CRYSTAL; rare -; pairs seen 67/300; nearest roster Jaccard 0.26 (size 19)

### Castle Fight - 25 - clap

Evidence cell: 155 distinct rosters (159 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 81.13, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Exalted Staff [28%], Wailing Bow [6%], Witchwork Staff [17%], Fists of Avalon [1%], Carrioncaller [2%], Great Hammer [6%], Fallen Staff [17%], Realmbreaker [83%], Forgebark Staff [4%], Permafrost Prism [59%], Spiked Gauntlets [70%], Permafrost Prism [59%], Hallowfall [91%], Icicle Staff [13%], Lightcaller [3%], Longbow [52%], Flamewalker Staff [0%], Redemption Staff [17%], Forge Hammers [2%], Great Arcane Staff [47%], Rotcaller Staff [24%]
- roles: no evidence row
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, peel, tankiness; purple catch; optional short execute
- evidence: never fielded MAIN_FIRESTAFF_CRYSTAL; rare 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA, 2H_DUALHAMMER_HELL; pairs seen 146/276; nearest roster Jaccard 0.34 (size 18)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ)** - score 81.117, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Exalted Staff [28%], Dawnsong [57%], Witchwork Staff [17%], Fists of Avalon [1%], Carrioncaller [2%], Great Hammer [6%], Fallen Staff [17%], Realmbreaker [83%], Forgebark Staff [4%], Permafrost Prism [59%], Spiked Gauntlets [70%], Permafrost Prism [59%], Hallowfall [91%], Icicle Staff [13%], Lightcaller [3%], Longbow [52%], Flamewalker Staff [0%], Redemption Staff [17%], Forge Hammers [2%], Great Arcane Staff [47%], Rotcaller Staff [24%]
- roles: no evidence row
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, peel, resist_shred, tankiness; purple catch; optional short execute
- evidence: never fielded MAIN_FIRESTAFF_CRYSTAL; rare 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA, 2H_DUALHAMMER_HELL; pairs seen 156/276; nearest roster Jaccard 0.36 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 1 slots differ)** - score 81.111, feasible True, filler [], held []

- roster: Hand of Justice [17%], Rampant Staff [12%], Heavy Mace [52%], Polehammer [37%], Exalted Staff [28%], Wailing Bow [6%], Witchwork Staff [17%], Fists of Avalon [1%], Carrioncaller [2%], Great Hammer [6%], Fallen Staff [17%], Realmbreaker [83%], Wild Staff [6%], Permafrost Prism [59%], Spiked Gauntlets [70%], Permafrost Prism [59%], Hallowfall [91%], Icicle Staff [13%], Lightcaller [3%], Longbow [52%], Flamewalker Staff [0%], Redemption Staff [17%], Forge Hammers [2%], Great Arcane Staff [47%], Rotcaller Staff [24%]
- roles: no evidence row
- identity: clap (strong)
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, peel, tankiness; purple catch; optional short execute
- evidence: never fielded MAIN_FIRESTAFF_CRYSTAL; rare 2H_KNUCKLES_AVALON, 2H_HALBERD_MORGANA, 2H_DUALHAMMER_HELL; pairs seen 144/276; nearest roster Jaccard 0.32 (size 20)
- hygiene: duplicates 2H_ICECRYSTAL_UNDEAD x2

### Castle Fight - 25 - kite

Evidence cell: 125 distinct rosters (140 sightings, all, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 73.887, feasible True, filler [], held []

- roster: Blight Staff [27%], Heavy Mace [22%], Hand of Justice [37%], Dawnsong [49%], Exalted Staff [40%], Polehammer [42%], Hellfire Hands [4%], Grailseeker [4%], Realmbreaker [73%], Fallen Staff [20%], Fists of Avalon [0%], Wild Staff [13%], Hallowfall [86%], Great Hammer [2%], Permafrost Prism [73%], Spiked Gauntlets [71%], Occult Staff [63%], Hallowfall [86%], Carrioncaller [2%], Rootbound Staff [18%], Arcane Staff [54%], Rotcaller Staff [46%], Lightcaller [0%], Rift Glaive [30%], Forgebark Staff [6%]
- roles: no evidence row
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, cleanse, peel, resist_shred, tankiness; purple catch, heal_sustain, purge; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 146/276; nearest roster Jaccard 0.45 (size 20)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 1 slots differ)** - score 73.876, feasible True, filler [], held []

- roster: Blight Staff [27%], Heavy Mace [22%], Hand of Justice [37%], Dawnsong [49%], Exalted Staff [40%], Polehammer [42%], Hellfire Hands [4%], Grailseeker [4%], Realmbreaker [73%], Fallen Staff [20%], Fists of Avalon [0%], Wild Staff [13%], Hallowfall [86%], Great Hammer [2%], Permafrost Prism [73%], Spiked Gauntlets [71%], Occult Staff [63%], Hallowfall [86%], Carrioncaller [2%], Rootbound Staff [18%], Arcane Staff [54%], Rotcaller Staff [46%], Lightcaller [0%], Longbow [38%], Forgebark Staff [6%]
- roles: no evidence row
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, cleanse, peel; purple catch, heal_sustain, purge; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 148/276; nearest roster Jaccard 0.43 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 2 (refresh, 1 slots differ)** - score 73.877, feasible True, filler [], held []

- roster: Blight Staff [27%], Heavy Mace [22%], Hand of Justice [37%], Dawnsong [49%], Exalted Staff [40%], Polehammer [42%], Hellfire Hands [4%], Grailseeker [4%], Realmbreaker [73%], Fallen Staff [20%], Fists of Avalon [0%], Wild Staff [13%], Hallowfall [86%], Great Hammer [2%], Permafrost Prism [73%], Spiked Gauntlets [71%], Occult Staff [63%], Hallowfall [86%], Carrioncaller [2%], Rootbound Staff [18%], Arcane Staff [54%], Rotcaller Staff [46%], Lightcaller [0%], Wailing Bow [10%], Forgebark Staff [6%]
- roles: no evidence row
- identity: clap (strong) - DISAGREES with kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, cleanse, peel, tankiness; purple catch, heal_sustain, purge; optional short anti_zone, execute
- evidence: never fielded 2H_KNUCKLES_AVALON, 2H_SHAPESHIFTER_AVALON; rare 2H_HAMMER, 2H_HALBERD_MORGANA; pairs seen 143/276; nearest roster Jaccard 0.43 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Castle Fight - 25 - brawl_clap

Evidence cell: 27 distinct rosters (33 sightings, all, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 80.533, feasible True, filler [], held []

- roster: Grailseeker [0%], Hallowfall [100%], Heavy Mace [78%], Exalted Staff [48%], Polehammer [30%], Dawnsong [15%], Hand of Justice [30%], Fallen Staff [4%], Crystal Reaper [0%], Great Hammer [7%], Fists of Avalon [0%], Great Holy Staff [0%], Battle Bracers [100%], Realmbreaker [78%], Wild Staff [0%], Kingmaker [0%], Dreadstorm Monarch [22%], Hallowfall [100%], Carrioncaller [0%], Hellfire Hands [0%], Bedrock Mace [0%], Malevolent Locus [56%], Lifecurse Staff [33%], Longbow [4%], Great Fire Staff [0%]
- roles: no evidence row
- identity: clap (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange mobility, silence; purple catch, clump_create
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON, 2H_HOLYSTAFF, 2H_WILDSTAFF, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_KNUCKLES_HELL, MAIN_ROCKMACE_KEEPER, 2H_FIRESTAFF; rare -; pairs seen 44/276; nearest roster Jaccard 0.26 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 1 (refresh, 1 slots differ)** - score 80.529, feasible True, filler [], held []

- roster: Grailseeker [0%], Hallowfall [100%], Heavy Mace [78%], Exalted Staff [48%], Polehammer [30%], Dawnsong [15%], Hand of Justice [30%], Fallen Staff [4%], Crystal Reaper [0%], Great Hammer [7%], Fists of Avalon [0%], Great Holy Staff [0%], Battle Bracers [100%], Realmbreaker [78%], Wild Staff [0%], Kingmaker [0%], Dreadstorm Monarch [22%], Hallowfall [100%], Carrioncaller [0%], Hellfire Hands [0%], Bedrock Mace [0%], Malevolent Locus [56%], Lifecurse Staff [33%], Longbow [4%], Astral Staff [4%]
- roles: no evidence row
- identity: clap (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange buff_allies, mobility; purple catch, clump_create
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON, 2H_HOLYSTAFF, 2H_WILDSTAFF, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_KNUCKLES_HELL, MAIN_ROCKMACE_KEEPER; rare -; pairs seen 44/276; nearest roster Jaccard 0.26 (size 19)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

**rank 2 (refresh, 2 slots differ, OUTSCORES rank 0)** - score 80.552, feasible True, filler [], held []

- roster: Grailseeker [0%], Hallowfall [100%], Heavy Mace [78%], Exalted Staff [48%], Polehammer [30%], Dawnsong [15%], Hand of Justice [30%], Fallen Staff [4%], Crystal Reaper [0%], Great Hammer [7%], Fists of Avalon [0%], Great Holy Staff [0%], Battle Bracers [100%], Realmbreaker [78%], Blight Staff [11%], Kingmaker [0%], Dreadstorm Monarch [22%], Hallowfall [100%], Carrioncaller [0%], Occult Staff [0%], Hellfire Hands [0%], Bedrock Mace [0%], Malevolent Locus [56%], Longbow [4%], Lifecurse Staff [33%]
- roles: no evidence row
- identity: brawl (leaning) - DISAGREES with brawl_clap
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red -; orange mobility; purple catch, clump_create
- evidence: never fielded 2H_QUARTERSTAFF_AVALON, 2H_SCYTHE_CRYSTAL, 2H_KNUCKLES_AVALON, 2H_HOLYSTAFF, 2H_CLAYMORE_AVALON, 2H_HALBERD_MORGANA, 2H_ARCANESTAFF_HELL, 2H_KNUCKLES_HELL, MAIN_ROCKMACE_KEEPER; rare -; pairs seen 47/276; nearest roster Jaccard 0.29 (size 20)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2

### Castle Fight - 25 - clap_kite

Evidence cell: 79 distinct rosters (82 sightings, holdout, borrowed 20); role row: `none`.

**rank 0 (the button)** - score 78.985, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Exalted Staff [43%], Dawnsong [81%], Polehammer [57%], Witchwork Staff [63%], Fists of Avalon [1%], Realmbreaker [89%], Carrioncaller [0%], Fallen Staff [23%], Hellfire Hands [6%], Great Hammer [1%], Hallowfall [95%], Grailseeker [2%], Hallowfall [95%], Permafrost Prism [95%], Permafrost Prism [95%], Lightcaller [1%], Rotcaller Staff [53%], Spiked Gauntlets [86%], Occult Staff [73%], Rampant Staff [38%], Bedrock Mace [94%], Great Arcane Staff [61%]
- roles: no evidence row
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange buff_allies, burst_aoe, disengage, peel, resist_shred; purple burst_st, damage_debuff; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA; rare 2H_KNUCKLES_AVALON, 2H_HAMMER, 2H_SHAPESHIFTER_AVALON; pairs seen 137/253; nearest roster Jaccard 0.54 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2, 2H_ICECRYSTAL_UNDEAD x2

**rank 1 (refresh, 1 slots differ)** - score 78.964, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Exalted Staff [43%], Dawnsong [81%], Polehammer [57%], Witchwork Staff [63%], Fists of Avalon [1%], Realmbreaker [89%], Carrioncaller [0%], Fallen Staff [23%], Hellfire Hands [6%], Great Hammer [1%], Hallowfall [95%], Grailseeker [2%], Hallowfall [95%], Permafrost Prism [95%], Permafrost Prism [95%], Lightcaller [1%], Rotcaller Staff [53%], Spiked Gauntlets [86%], Occult Staff [73%], Rampant Staff [38%], Quarterstaff [0%], Great Arcane Staff [61%]
- roles: no evidence row
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red buff_allies, tankiness; orange disengage, peel, resist_shred; purple burst_st, damage_debuff; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA, 2H_QUARTERSTAFF; rare 2H_KNUCKLES_AVALON, 2H_HAMMER, 2H_SHAPESHIFTER_AVALON; pairs seen 120/253; nearest roster Jaccard 0.48 (size 18)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2, 2H_ICECRYSTAL_UNDEAD x2

**rank 2 (refresh, 1 slots differ)** - score 78.957, feasible True, filler [], held []

- roster: Hand of Justice [33%], Blight Staff [16%], Heavy Mace [13%], Exalted Staff [43%], Dawnsong [81%], Polehammer [57%], Witchwork Staff [63%], Fists of Avalon [1%], Realmbreaker [89%], Carrioncaller [0%], Fallen Staff [23%], Hellfire Hands [6%], Great Hammer [1%], Hallowfall [95%], Grailseeker [2%], Hallowfall [95%], Permafrost Prism [95%], Permafrost Prism [95%], Lightcaller [1%], Rotcaller Staff [53%], Spiked Gauntlets [86%], Occult Staff [73%], Wild Staff [0%], Bedrock Mace [94%], Great Arcane Staff [61%]
- roles: no evidence row
- identity: clap (strong) - DISAGREES with clap_kite
- kill checklist: ready (pierce True, heal-cut True, burst True)
- board: red tankiness; orange buff_allies, burst_aoe, disengage, peel, resist_shred; purple burst_st, damage_debuff; optional short execute
- evidence: never fielded 2H_HALBERD_MORGANA, 2H_WILDSTAFF; rare 2H_KNUCKLES_AVALON, 2H_HAMMER, 2H_SHAPESHIFTER_AVALON; pairs seen 123/253; nearest roster Jaccard 0.50 (size 20)
- hygiene: duplicates MAIN_HOLYSTAFF_AVALON x2, 2H_ICECRYSTAL_UNDEAD x2

