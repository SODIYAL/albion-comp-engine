# R1: a style x band fielded gate at 10+, measured on the v4h holdout

Report-only. No engine, template or test file was edited; the gate below is
an experiment in a scratch subclass of `Engine`.

## Context

**Question** (BACKLOG "The fielded gate beyond the portal"). Inside the
Dragon Portal pools of 2-3, 4-5 and 6-7 the engine bars from suggestions and
generation every weapon the pool's dominant winners do not field
(`pool_fielded`, `derive_portal_rows.fielded()`); on the v4h holdout that gate
moved the hidden member's top-3 hit from 9.1 / 13.8 / 9.4% to 9.5 / 19.3 /
12.6%. Contents of 10+ carry no weapon-level evidence gate. Measured here:
whether a fielded list per style x size band, built from killer parties of
10+, lifts the same holdout measure.

**Artifacts.** At `6590a51`.
`pipeline/out/party_rosters.json.gz` SHA-256 `829c8c293b0735393e66cad37602562a8d6e162c9bfc8ab77992b7c23270ba4b`
(the hash `skeletons.json` records); `pipeline/out/dataset-latest.json`
SHA-256 `9abfc0ab6e168a7f4419b67b75da22ca73e703017952d8d19a660937aabdcff6`.
Run stamp 2026-10-08.

**Split.** Lists learn from the training split (`battle % 5 != 0`);
evaluation reads the holdout (`battle % 5 == 0`). The committed style board,
meta prior, role counts and seat skeleton learn from the same training split
(`style_bands.yaml` `split.holdout_mod: 5`), so the holdout is unseen by every
harvest-derived table, the lists included.

**The lists.** Population: battle-list killer parties of 10-20 with every
weapon known and in the catalog (the `_harvest_parties` filter v4h uses),
18,592 training parties. Cells: the party's weapons-only style label
(`party_styles.json`; an unlabelled party is `balanced`, as in v4h) x the band
edges the style board and the skeleton use (10-14, 15-19, 20; the band `20`
reads 20-99 and no party exceeds 20). Rule: `derive_portal_rows.fielded()`
itself (a weapon in at least 5 distinct rosters, across at least 3 distinct
guild-sets, and in at least 5% of the rosters of the cell's most fielded
weapon). A cell under 40 distinct rosters (the portal's floor) carries no
list: nothing is gated there. Label counts in the training population: clap
8,579, brawl 3,245, unlabelled 2,594, clap_kite 2,303, kite 1,612, brawl_clap
259.

Arms:

| arm | list read by an engine of style S at size N |
| --- | --- |
| `none` | no gate (the committed engine) |
| `styled` | the S x band(N) list; `balanced` reads the pooled band list (the style board's convention: balanced reads the pooled cell) |
| `pooled` | the pooled band list for every style |
| `dom_styled`, `dom_pooled` | as above, lists from dominant parties only (no deaths, a kill; 8,547 parties) |

**Gate mechanics.** Applied the way the engine applies `pool_fielded`
(`engine.py` `set_content`, after the viability, style-fit and generation-fit
gates): a weapon outside the list leaves `suggest_pool()` and joins
`_unfielded`. It therefore leaves the v4h ranking and the V4b rebuild;
scoring is untouched. Removing candidates never lowers a remaining weapon's
rank (scores do not change), so the only top-3 losses are barred weapons.

**Measure.** `tests/tier2_blindtest.py` `v4h`, unchanged (imported; its
`Engine` name swapped for the gated subclass): `--holdout-mod 5 --n 500
--drop 3 --rebuild 5 --baseline`, content `blackzone_roam`, sizes 10-20,
battle-list population, seed 20260910 (1,500 drops, 2,500 rebuild members),
and a second sample at seed 20261008. The full n = 500 ran in about 4-7
minutes per arm, so no reduced sample was needed. The harness read a slim copy
of the holdout battles (a slim copy: holdout parties of 10+ with
their pre-assigned indices and gear-carrying builds); every arm checked that
the slim copy yields the full artifact's holdout party list (4,679 eligible
parties, identical SHA-256 of the list).

## Numbers

### v4h, seed 20260910, `harvest_gear` class (incumbents in their linked builds' gear)

| arm | weapon top-3 | role-level | median rank (in pool) | top-10 | MRR | outside pool | V4b weapon | V4b role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | 115/1500 = 7.7% | 378/607 = 62.3% | 28 | 309 = 20.6% | 0.090 | 170 | 384/2500 = 15.4% | 1478/1684 = 87.8% |
| styled | 152/1500 = 10.1% | 392/607 = 64.6% | 16 | 439 = 29.3% | 0.114 | 229 | 429/2500 = 17.2% | 1483/1684 = 88.1% |
| pooled | 143/1500 = 9.5% | 388/607 = 63.9% | 17 | 413 = 27.5% | 0.109 | 233 | 411/2500 = 16.4% | 1489/1684 = 88.4% |
| dom_styled | 153/1500 = 10.2% | 390/607 = 64.3% | 16 | 445 = 29.7% | 0.114 | 226 | 440/2500 = 17.6% | 1483/1684 = 88.1% |
| dom_pooled | 139/1500 = 9.3% | 387/607 = 63.8% | 18 | 398 = 26.5% | 0.107 | 230 | 416/2500 = 16.6% | 1493/1684 = 88.7% |
| baseline (ungated pool) | 290/1500 = 19.3% | 329/607 = 54.2% | 19 | 491 = 32.7% | 0.180 | 170 | 803/2500 = 32.1% | 1346/1684 = 79.9% |

The baseline ranks `suggest_pool()` too, so in a gated arm it ranks the gated
pool: 294 / 295 / 291 top-3 hits (styled / dom_styled / pooled), MRR 0.187 /
0.188 / 0.185, rebuild unchanged at 803/2500.

The other incumbent classes move the same way: `weapon_only` 115 -> 153
(styled) / 139 (pooled), MRR 0.092 -> 0.116 / 0.109; `harvest_gear_doctrine`
125 -> 160 / 152, MRR 0.094 -> 0.117 / 0.112.

### Paired against the ungated arm (same drops; party-cluster bootstrap, 2,000 resamples)

| arm | seed | top-3 change (95% CI) | hits gained / lost (lost = barred) | MRR (95% CI of the change) |
| --- | --- | --- | --- | --- |
| styled | 20260910 | +2.5 pts (+1.7 .. +3.3) | 39 / 2 | 0.090 -> 0.114 (+0.021 .. +0.027) |
| pooled | 20260910 | +1.9 pts (+1.1 .. +2.7) | 30 / 2 | 0.090 -> 0.109 (+0.016 .. +0.022) |
| dom_styled | 20260910 | +2.5 pts (+1.7 .. +3.4) | 40 / 2 | 0.090 -> 0.114 (+0.021 .. +0.027) |
| dom_pooled | 20260910 | +1.6 pts (+0.9 .. +2.3) | 26 / 2 | 0.090 -> 0.107 (+0.014 .. +0.020) |
| styled | 20261008 | +2.3 pts (+1.5 .. +3.1) | 37 / 2 | 0.090 -> 0.112 (+0.019 .. +0.026) |
| pooled | 20261008 | +1.8 pts (+1.1 .. +2.5) | 29 / 2 | 0.090 -> 0.107 (+0.015 .. +0.020) |

Seed 20261008, `harvest_gear`: none 116/1500 = 7.7%, role 389/601 = 64.7%,
MRR 0.090, V4b weapon 345/2500 = 13.8%; styled 151 = 10.1%, role 402/601 =
66.9%, MRR 0.112, V4b 389/2500 = 15.6%; pooled 143 = 9.5%, role 401/601 =
66.7%, MRR 0.107, V4b 374/2500 = 15.0%; baseline 251 = 16.7%, role 45.1%,
MRR 0.169, V4b 775/2500 = 31.0%.

Role-level by style label (`harvest_gear`), none -> styled: seed 20260910
balanced 62% -> 62%, brawl 58% -> 62%, brawl_clap 60% -> 60%, clap 61% -> 62%,
clap_kite 77% -> 81%, kite 50% -> 57%; seed 20261008 balanced 64% -> 68%,
brawl 78% -> 80%, brawl_clap 50% -> 50%, clap 60% -> 61%, clap_kite 67% ->
70%, kite 64% -> 68%.

Against the portal: the styled gate's weapon top-3 lift at 10+ (7.7% -> 10.1%,
x1.31) sits beside the portal's 6-7 pool (9.4% -> 12.6%, x1.34), under the 4-5
pool (13.8% -> 19.3%, x1.40) and over the 2-3 pool (9.1% -> 9.5%, x1.04).

### What each list keeps (training split)

| cell | distinct rosters | top weapon's rosters (5% floor) | kept / seen | healer / frontline / support / dps kept |
| --- | --- | --- | --- | --- |
| pooled 10-14 | 7,306 | 4,891 (244.6) | 74 / 136 | 9 / 15 / 11 / 39 |
| pooled 15-19 | 8,690 | 7,822 (391.1) | 54 / 136 | 8 / 12 / 10 / 24 |
| pooled 20 | 1,798 | 1,720 (86.0) | 55 / 133 | 9 / 13 / 10 / 23 |
| brawl 10-14 | 1,554 | 1,097 (54.9) | 63 / 136 | 7 / 11 / 10 / 35 |
| brawl 15-19 | 1,368 | 1,289 (64.5) | 50 / 132 | 7 / 12 / 9 / 22 |
| brawl 20 | 231 | 224 (11.2) | 49 / 98 | 6 / 12 / 9 / 22 |
| clap 10-14 | 3,305 | 2,280 (114.0) | 55 / 136 | 8 / 12 / 9 / 26 |
| clap 15-19 | 4,147 | 3,691 (184.6) | 49 / 136 | 8 / 12 / 10 / 19 |
| clap 20 | 753 | 718 (35.9) | 51 / 119 | 8 / 13 / 10 / 20 |
| kite 10-14 | 832 | 459 (23.0) | 80 / 135 | 11 / 15 / 13 / 41 |
| kite 15-19 | 552 | 466 (23.3) | 54 / 131 | 10 / 12 / 10 / 22 |
| kite 20 | 162 | 154 (7.7) | 45 / 92 | 7 / 10 / 10 / 18 |
| brawl_clap 10-14 | 110 | 93 (4.7) | 41 / 82 | 7 / 10 / 10 / 14 |
| brawl_clap 15-19 | 118 | 114 (5.7) | 40 / 69 | 8 / 12 / 8 / 12 |
| brawl_clap 20 | **24 (thin: no list)** | 23 | (20 / 50) | - |
| clap_kite 10-14 | 322 | 258 (12.9) | 45 / 97 | 7 / 10 / 11 / 17 |
| clap_kite 15-19 | 1,370 | 1,259 (63.0) | 40 / 110 | 7 / 9 / 10 / 14 |
| clap_kite 20 | 411 | 399 (20.0) | 39 / 90 | 7 / 9 / 10 / 13 |

Only one cell is
under the 40-roster floor: brawl_clap 20 (24 distinct rosters; 9 in the
dominant variant, where brawl_clap 15-19 holds 44 rosters and keeps 17
weapons). Three holdout drops sit in the thin cell and stay ungated. In a big
cell the 5% floor is the binding rule (pooled 15-19 cuts Camlann Mace at 389
rosters against a floor of 391).

The committed `blackzone_roam` suggestion pool against the list (weapons kept):

| band | balanced | brawl | clap | kite | brawl_clap | clap_kite |
| --- | --- | --- | --- | --- | --- | --- |
| 10-14, styled | 96 -> 63 | 71 -> 43 | 77 -> 44 | 77 -> 55 | 95 -> 38 | 78 -> 43 |
| 15-19, styled | 96 -> 51 | 71 -> 40 | 77 -> 42 | 77 -> 47 | 95 -> 38 | 78 -> 39 |
| 20, styled | 96 -> 53 | 71 -> 39 | 77 -> 43 | 77 -> 42 | 95 (no list) | 78 -> 39 |
| 10-14, pooled | 96 -> 63 | 71 -> 49 | 77 -> 52 | 77 -> 52 | 95 -> 62 | 78 -> 53 |
| 15-19, pooled | 96 -> 51 | 71 -> 40 | 77 -> 44 | 77 -> 44 | 95 -> 50 | 78 -> 45 |
| 20, pooled | 96 -> 53 | 71 -> 42 | 77 -> 46 | 77 -> 46 | 95 -> 52 | 78 -> 47 |

### The cost: hidden picks the gate bars

| arm | drops outside the list | barred by this gate alone (inside the committed pool) | of them healer or frontline | top-3 hits lost | rebuild members barred |
| --- | --- | --- | --- | --- | --- |
| styled | 116 / 1500 | 59 = 3.9% | 18 | 2 | 103 / 2500 |
| pooled | 114 / 1500 | 63 = 4.2% | 19 | 2 | 94 / 2500 |
| dom_styled | 109 / 1500 | 56 = 3.7% | 19 | 2 | 97 / 2500 |
| dom_pooled | 108 / 1500 | 60 = 4.0% | 20 | 2 | 97 / 2500 |

The committed engine already holds 170 of the 1,500 hidden picks outside
`suggest_pool()` (the other gates). Seed 20261008: the styled gate bars 80
drops (5.3%), the pooled 73; two top-3 hits lost in each. Most barred hidden
weapons (styled, seed 20260910): Glacial Staff 4, Astral Staff 4, Fists of
Avalon 4, Grovekeeper 3, Brimstone Staff 3, Forge Hammers 3. The styled lists
hold 92.4% of every holdout member slot (66,020 / 71,476 over the 4,679
holdout parties; pooled 92.7%).

### What the gate removes from the engine's proposals

The committed engine's top 3 over the same 1,500 drops (`harvest_gear`
class): 1,066 of its 4,500 proposals (23.7%) and 190 of its 1,500 first picks
(12.7%) are weapons outside the styled list (pooled: 18.5% and 9.0%). By
weapon (outside / all proposals where available): Grovekeeper 289 / 289,
Camlann Mace 192 / 278, Morning Star 84 / 84, Wild Staff 75 / 136, Great
Hammer 61 / 93, Tombhammer 52, Stillgaze Staff 48, Rampant Staff 43 / 156,
Fists of Avalon 42, Grailseeker 36, Witchwork Staff 28 / 93, Hand of Justice
27 / 615. The same pattern the portal measured (Claws and Hand of Justice,
forged in every style while one dominant 6-7 party in 162 fields each).

### Published comps (static check; v4 itself is a gate and was not run)

Slots of the published 10-20 parties `v4` scores whose every listed
alternative lies outside the styled list for the party's declared style and
band: 36 of 463 (brawl_clap 20 ungated; pooled list 45 of 503). Examples:
`albioncompo_brawl_by_lattex` brawl 20: Truebolt Hammer, Stillgaze Staff,
Infinity Blade, Daybreaker, Forge Hammers; `albioncompo_comp_5_v2` balanced
20: 8 of 20; `timothy_blap_blackzone_roam` brawl 20: Carrioncaller, Clarent
Blade. These are weapon-level misses a gated engine would take on the
published corpus by construction. v4's role-level gate counts the healer and
tank slots; none of the slots the styled list bars is one (the pooled list
bars one main-tank slot, Camlann Mace in the blap).

### Generation: the default forge under the gate

v4h ranks through `recommend()`; the gate's real use is generation.
`Engine.forge(size)` at `blackzone_roam` 10, 15 and 20, every style, ungated
against the styled gate:

| style | ungated forge: members inside the list at 10 / 15 / 20 | gated forge at 10 / 15 / 20 |
| --- | --- | --- |
| balanced | 8/10, 11/15, 16/20 | complete at all three |
| brawl | 9/10, 11/15, 15/20 | complete; **13 of 15, infeasible; 17 of 20, infeasible** |
| clap | 6/10, 11/15, 14/20 | complete at all three |
| kite | 9/10, 14/15, 16/20 | complete at all three |
| brawl_clap | 5/10, 12/15, no list at 20 | complete at all three |
| clap_kite | 9/10, 12/15, 17/20 | complete at all three |

The gated brawl forge stops short because of a forge minimum, not a seat:
the `ranged_aoe_core` predicate (`composition.yaml`: burst_aoe >= 4 and
ranged_presence >= 2 sheet points; the base band's minimum 2 / 3 / 4 at 10-14
/ 15-19 / 20-29, which brawl does not override). The gated brawl pool holds one
carrier (Spiked Gauntlets); the ungated pool seven (Rift Glaive, Fists of
Avalon, Hellfire Hands, Spiked Gauntlets, Soulscythe, Witchwork Staff,
Clarent Blade), and at the depth where the gated beam dies the forge's own
feasibility check accepts only those. The minimum is not
what brawl winners field (holdout killer parties, flat membership):

| cell | parties | carriers per party p10 / p50 / p90 | forge minimum | parties at or past it |
| --- | --- | --- | --- | --- |
| brawl 10-14 | 406 | 0 / 1 / 2 | 2 | 17% |
| brawl 15-19 | 324 | 0 / 1 / 2 | 3 | 5% |
| brawl 20 | 63 | 0 / 1 / 2 | 4 | 0% |
| balanced 20 | 61 | 1 / 2 / 4 | 4 | 16% |
| clap 20 | 206 | 3 / 5 / 7 | 7 | 14% |
| clap_kite 20 | 156 | 4 / 5 / 7 | 7 | 12% |
| kite 20 | 37 | 4 / 5 / 6 | 5 | 59% |

Ungated, the forge meets the brawl minimum by drafting ranged-AoE weapons
brawl winners field below the 5% floor; gated, it cannot. Elsewhere the
gated forge completes; its comp score moves -0.87 to +0.12 against the
ungated forge, and between 2 and 18 weapons change their count in the
roster.

## Verdict

Evidence, not a decision.

1. **The gate lifts the holdout numbers at 10+ the way it did at the portal's
   6-7 pool.** The styled list raises the hidden member's top-3 hit from 7.7%
   to 10.1% (+2.5 points, 95% CI +1.7 to +3.3; replicated at +2.3 on an
   independent sample), MRR from 0.090 to 0.114, top-10 from 20.6% to 29.3%,
   role-level from 62.3% to 64.6%, and the V4b rebuild's weapon recall from
   15.4% to 17.2%. Every incumbent-gear class moves the same way. The
   relative lift (x1.31) matches the 6-7 pool's (x1.34).
2. **The cost is small and lands where the engine already misses.** The
   gate bars 3.9-5.3% of hidden picks, and only 2 of them were top-3 hits
   without the gate; in-pool ranks never worsen. The lists hold 92% of the
   holdout's member slots.
3. **Style x band beats pooled.** Styled +2.5 / +2.3 points against pooled
   +1.9 / +1.8, MRR 0.114 / 0.112 against 0.109 / 0.107; the pooled list is
   clap-heavy (clap is 46% of the training population) and cuts what brawl
   and kite winners field. Dominant-party lists add nothing over the
   killer-party lists (10.2% against 10.1%) and thin the small cells.
4. **One cell is too thin**: brawl_clap 20 (24 distinct rosters) carries no
   list under the 40-roster floor; brawl_clap 10-14 and 15-19 (110 and 118
   rosters) clear it with lists of 41 and 40 weapons.
5. **The gap to the popularity baseline stays.** Gated, the engine's weapon
   top-3 (10.1%) is still about half the baseline's (19.3%) and its MRR
   (0.114) about 60% of the baseline's (0.180); the engine keeps its
   role-level lead (64.6% against 54.2%). The gate removes the off-evidence
   proposals (a quarter of the committed top 3: Grovekeeper, Camlann Mace,
   Morning Star), not the in-list ordering problem the baseline finding
   records.
6. **The gate collides with a curated forge minimum.** Gated, the default
   brawl forge at 15 and 20 returns a partial roster (13 of 15, 17 of 20,
   `feasible` false): the base band's `ranged_aoe_core` minimum (3 at 15-19,
   4 at 20) has one carrier left in the brawl list, and the minimum itself is
   met by 5% and 0% of holdout brawl winners (median 1). A gate at 10+ cannot
   ship beside that minimum as it stands; the minimum per style is the
   question it surfaces (the same minimum is met by 12-16% of balanced, clap
   and clap_kite winners at 20, where the gated forge still completes).
7. **Side effect to weigh**: published 10-20 parties field weapons the
   harvest's winners do not (36 of 463 slots outside the styled list). A
   gated engine never generates them at 10+; a manual pick still scores.
   v4 was not run under the gate.

A caveat on reading: v4h rewards naming what winners field, and a fielded
list mechanically favours exactly that; the lift is evidence that the gate
aligns generation with the killer-party evidence unit, not that the gated
comps fight better (popularity is not effectiveness).

## Method note

The measurement scripts ran outside the repository, each against the committed artifacts the Context names; the method above is the whole of what they do.
