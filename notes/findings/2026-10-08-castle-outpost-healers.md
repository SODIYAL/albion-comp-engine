# R2: why Castle Outpost 7 prefers Great Holy and Rampant over Hallowfall

Report-only. No engine, template or test file was edited; every change below
is applied in memory to the dataset's copy of a template (or to the engine
through a scratch subclass) and re-resolved with `Engine.set_content`.

## Context

**Question** (BACKLOG "Healer pricing at 7", decision log `09b` "V3 round 2,
Castle Outpost 7"). In the round's Castle Outpost 7 form, dressed scoring
(V3-D) ranks Great Holy Staff and Rampant Staff above Hallowfall in every
healer case. Two candidate causes: (a) the castle_outpost `heal_sustain` :
`heal_burst` pricing; (b) worn gear closing the utility targets, so
Hallowfall's mobility and disengage earn nothing. Killer parties of 6-8 field
Hallowfall far more often than either.

**Form.** `tests/tier2_form_r2_castle7_draft.md` (the answered copy; the
blank form is `tests/tier2_form_r2_castle7.md`), `FORM_CONTEXT:
castle_outpost 7 balanced 20260827`, twelve cases. Healer cases (answer
Hallowfall): 1, 2, 3, 4, 5, 6, 7, 8, 10, 11. Non-healer cases (answer
Permafrost Prism): 9 and 12.

**Artifacts.** At `6590a51`; `pipeline/out/dataset-latest.json`
SHA-256 `9abfc0ab6e168a7f4419b67b75da22ca73e703017952d8d19a660937aabdcff6`;
`pipeline/out/party_rosters.json.gz` SHA-256
`829c8c293b0735393e66cad37602562a8d6e162c9bfc8ab77992b7c23270ba4b`. Run
stamp 2026-10-08. `MASTERSHEET.md` `tune:templates` is empty, and
`build_dataset.py` embeds the templates as-is, so an in-memory edit of the
dataset's `templates.castle_outpost` is the number a rebuilt dataset with the
edited `pipeline/templates/castle_outpost.yaml` would carry.

**Regimes.** The production path is `tier2_blindtest._score_mode(e, cases,
"d")`: incumbents in their doctrine kits (`gear_join.doctrine_gears`, the
form records no gear), candidates dressed. The four combinations:

| regime | incumbents | candidates |
| --- | --- | --- |
| DD | doctrine kits | dressed (V3-D, production) |
| NN | naked | naked (`set_dressing(False)`, V3-W) |
| DN | doctrine kits | naked |
| ND | naked | dressed (also the bare `recommend(party)` path the golden pins use) |

Decompositions read `Engine.pick_report` (caps rows sum to `d_fitness`;
`alpha * d_fitness + beta * d_synergy + delta * meta - dup` is the score).

**Harvest.** Killer parties of 6-8 with every weapon known and in the
catalog, both populations (battle list and kill-feed poll), training split
`battle % 5 != 0` (23,711 parties, 110,980 builds the analyzer linked by
party index) for the harvest read, and the holdout `battle % 5 == 0` (5,828
parties; 2,200 of size 7) for the side-effect leave-one-out.

## Numbers

### 1. The committed engine on the form

V3-D: top-1 0%, top-3 25%, acceptable top-3 33%, answer median rank 9.
V3-W: top-1 50%, top-3 75%, acceptable 83%, median rank 1.5.

Hallowfall's rank per healer case and the leader:

| case | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 10 | 11 | first |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DD | 4 | 3 | 12 | 10 | 9 | 3 | 10 | 9 | 9 | 3 | 0/10 (Rampant 7, Great Holy 3) |
| NN | 1 | 1 | 2 | 6 | 1 | 1 | 3 | 2 | 1 | 1 | 6/10 (Fallen leads 3, 4, 7, 8) |
| DN | 1 | 1 | 9 | 9 | 5 | 1 | 8 | 3 | 2 | 1 | 4/10 (Fallen leads the rest) |
| ND | 1 | 1 | 9 | 10 | 2 | 3 | 10 | 9 | 1 | 2 | 3/10 |

Mean exact pick score over the ten healer cases:

| regime | Hallowfall | Rampant | Great Holy | Fallen | Hallowfall - Rampant | Hallowfall - Great Holy |
| --- | --- | --- | --- | --- | --- | --- |
| NN | 20.278 | 18.895 | 18.933 | 20.018 | +1.383 | +1.345 |
| DN (incumbent kits only) | 19.309 | 18.781 | 18.854 | 19.935 | +0.528 | +0.455 |
| ND (candidate kits only) | 23.190 | 23.342 | 23.331 | 23.388 | -0.152 | -0.141 |
| DD | 21.504 | 22.503 | 22.053 | 22.143 | -0.999 | -0.549 |

Against Rampant the two dressing sides add up (0.855 from the incumbents'
kits, 1.535 from the candidates' kits; 2.382 together). Against Great Holy
they overlap (0.890 and 1.486 alone; 1.894 together): both kits supply the
same disengage.

### 2. Which rows move (alpha x row delta, mean over the healer cases)

| row (weight, target at 7) | NN Hallowfall | NN Rampant | NN Great Holy | DD Hallowfall | DD Rampant | DD Great Holy |
| --- | --- | --- | --- | --- | --- | --- |
| heal_sustain (10, 4.5) | 14.118 | 15.141 | 15.141 | 15.141 | 16.500 | 16.371 |
| heal_burst (6, 2.9) | 3.310 | 1.566 | 2.544 | 3.460 | 2.080 | 3.300 |
| cleanse (5, 2.7) | 0 | 1.566 | 0 | 0 | 1.566 | 0 |
| peel (8, 21.5) | 1.160 | 0 | 0.803 | 1.342 | 0.301 | 0.764 |
| disengage (4, 4.0) | 0.885 | 0 | 0 | 0.268 | 0 | 0.195 |
| mobility (3, 8.0) | 0.514 | 0 | 0 | 0.299 | 0.142 | 0.098 |
| tankiness (9, 23.6) | 0 | 0 | 0 | 0.293 | 0.293 | 0.751 |
| engage (7, 6.5) | 0 | 0 | 0 | 0 | 0.474 | 0 |
| zone_control (4, 7.0) | 0 | 0.375 | 0 | 0 | 0.311 | 0 |
| sustained_dps (5, 31.2) | 0 | 0.110 | 0 | 0.287 | 0.501 | 0.169 |
| knockback_displace (1, 3.0) | 0.195 | 0.021 | 0.296 | 0.319 | 0.239 | 0.283 |

`heal_sustain` carries the hard-floor lift (11.0 for every healer: the
parties field none, and every healer's weapon clears the 1.7-unit floor).
The coverage part is 3.12 / 4.14 / 4.14 naked and 4.14 / 5.50 / 5.37
dressed.

The vectors behind it, as the dressed pick wears them in DD (the combo and
kit variant `pick_report` records, the same in every healer case except one
Rampant case):

| healer | naked | the kit adds |
| --- | --- | --- |
| Hallowfall (v1: `HEAD_LEATHER_SET3`, `ARMOR_CLOTH_AVALON`, `OFF_HORN_KEEPER`, ...) | peel 6, heal_burst 3, mobility 3, disengage 2, heal_sustain 2, knockback 1 | heal_burst +1.5, heal_sustain +1.0, disengage +1.5, mobility +1.0, peel +1.5, knockback +1.5, tankiness +1.55, sustained_dps +3.75 |
| Rampant (v0) | heal_sustain 3, cleanse 2, heal_burst 1, slow 1, sustained_dps 1, zone_control 1 | heal_sustain +1.5, heal_burst +0.5, engage +1.0, mobility +1.5, peel +1.5, knockback +1.5, tankiness +1.55, sustained_dps +5.75 |
| Great Holy (v1) | peel 4, heal_sustain 3, heal_burst 2, buff_allies 2, knockback 2, anti_dive 1 | heal_sustain +1.35, heal_burst +0.9, disengage +1.5, mobility +1.0, tankiness +4.12, sustained_dps +2.17 |
| Fallen (v1) | peel 4, heal_burst 3, anti_dive 2, cleanse 2, heal_sustain 2 | heal_burst +1.35, heal_sustain +0.9, disengage +1.5, mobility +1.0, tankiness +3.12, sustained_dps +3.62 |
| Redemption (v0) | heal_sustain 3, peel 2, heal_burst 2 | heal_sustain +1.35, heal_burst +0.9, disengage +1.5, mobility +1.0, tankiness +3.12, sustained_dps +3.62 |
| Blight (v0) | heal_sustain 3, cleanse 2, mobility 1, heal_burst 1, slow 1, sustained_dps 1, zone_control 1 | heal_sustain +1.35, heal_burst +0.45, disengage +1.5, mobility +1.0, tankiness +3.12, sustained_dps +4.08 |
| Holy Staff (v0) | heal_burst 2, heal_sustain 2 | heal_sustain +0.9, heal_burst +0.9, disengage +1.5, mobility +1.0, tankiness +4.12, sustained_dps +2.17 |

Dressed Great Holy lands on both heal targets almost exactly (sustain 4.35 of
4.5, burst 2.9 of 2.9). Mean DD scores of the other healers: Lifetouch
21.867, Nature 21.726, Blight 21.701, Redemption 21.274, Holy Staff 19.589
(NN: 19.011, 19.025, 19.061, 18.164, 16.694); the one-handed Holy Staff
trails everywhere (two heal units, no utility).

The shift from NN to DD, Rampant minus Hallowfall (+2.382): the utility rows
(peel, disengage, mobility, knockback) +1.187; the heal rows +0.700; Rampant's
kit rows (engage, zone_control, sustained_dps, slow) +0.495; cleanse 0 (a
standing +1.566 for Rampant in every regime). Great Holy minus Hallowfall
(+1.892): heal rows +0.813, utility rows +0.767, Great Holy's kit tankiness
and the rest +0.312.

The heal-row shift is the kit's heal stat channel (`build_extra`: the cloth
chest's heal % multiplies both heal rows): it lifts the two-handers' 3.0
units of sustain to 4.35-4.5 (the 4.5 target, full coverage), while
Hallowfall's 3.0 units of burst become 4.5 past the 2.9 burst target (headroom
only) and its 2.0 sustain becomes 3.0 (67% of target). Dressed, the heal rows
net Rampant -0.02 against Hallowfall (naked -0.72) and Great Holy +1.07
(naked +0.26).

### 3. Counterfactual (c): Hallowfall's disengage and mobility

Party supply before the pick, naked -> doctrine kits, and Hallowfall's row
value (alpha x delta) in NN / DN / ND / DD:

| case | disengage before (target 4.0) | value NN / DN / ND / DD | mobility before (target 8.0) | value NN / DN / ND / DD |
| --- | --- | --- | --- | --- |
| 1 | 0.0 -> 6.5 | 1.35 / 0.05 / 2.00 / 0.10 | 4.0 -> 8.0 | 0.49 / 0.05 / 0.63 / 0.07 |
| 2 | 1.0 -> 3.0 | 0.97 / 0.43 / 1.38 / 0.47 | 2.0 -> 3.5 | 0.56 / 0.50 / 0.72 / 0.65 |
| 3 | 2.0 -> 6.5 | 0.85 / 0.05 / 0.89 / 0.10 | 3.0 -> 7.5 | 0.52 / 0.12 / 0.67 / 0.14 |
| 4 | 3.0 -> 5.5 | 0.43 / 0.05 / 0.47 / 0.10 | 5.0 -> 8.5 | 0.46 / 0.05 / 0.48 / 0.07 |
| 5 | 0.0 -> 4.0 | 1.35 / 0.05 / 2.00 / 0.10 | 2.0 -> 5.0 | 0.56 / 0.46 / 0.72 / 0.48 |
| 6 | 2.0 -> 2.0 | 0.85 / 0.85 / 0.89 / 0.89 | 6.0 -> 11.5 | 0.32 / 0.05 / 0.34 / 0.07 |
| 7 | 3.0 -> 4.5 | 0.43 / 0.05 / 0.47 / 0.10 | 6.0 -> 11.5 | 0.32 / 0.05 / 0.34 / 0.07 |
| 8 | 2.0 -> 3.5 | 0.85 / 0.24 / 0.89 / 0.28 | 3.0 -> 5.0 | 0.52 / 0.46 / 0.67 / 0.48 |
| 10 | 0.0 -> 3.0 | 1.35 / 0.43 / 2.00 / 0.47 | 0.0 -> 5.0 | 0.83 / 0.46 / 1.02 / 0.48 |
| 11 | 3.0 -> 7.5 | 0.43 / 0.05 / 0.47 / 0.10 | 2.0 -> 5.0 | 0.56 / 0.46 / 0.72 / 0.48 |
| mean | 1.6 -> 4.6 | 0.885 / 0.227 / 1.146 / 0.268 | 3.3 -> 7.0 | 0.514 / 0.268 / 0.632 / 0.299 |

The incumbents' kits put the party at or past the disengage target before
the healer joins in 6 of 10 cases (and at 3.0-3.5 in three more), and at or
past the mobility target in 4. In ND the rivals' own kits already earn disengage
(Great Holy 0.726 mean) and mobility (Rampant 0.290, Great Holy 0.201) that
Hallowfall's weapon brings.

### 4. Counterfactuals (a) and (b): what flips Hallowfall to first

One parameter at a time, V3-D, Hallowfall's rank in cases 1-8, 10, 11
(with every doctrine kit frozen at the committed template,
the ranks are identical: no change below re-picks a kit
in these cases):

| change (pipeline/templates/castle_outpost.yaml or the engine) | Hallowfall ranks | first | leaders | V3-D top-1 / top-3 |
| --- | --- | --- | --- | --- |
| committed | 4 3 12 10 9 3 10 9 9 3 | 0/10 | Rampant 7, Great Holy 3 | 0% / 25% |
| heal_sustain weight 10 -> 8 | 3 2 13 10 11 3 10 9 9 3 | 0/10 | Rampant 4, Great Holy 3, Fallen 3 | 0% / 33% |
| heal_sustain weight 10 -> 6 | 2 5 22 10 11 2 10 7 7 1 | 1/10 | Fallen 5, Hand of Justice 3 | 8% / 25% |
| heal_sustain target 4.5 -> 3.5 | 2 1 11 10 7 3 10 7 7 1 | 2/10 | Fallen 6 | 17% / 33% |
| heal_sustain target 4.5 -> 3.0 | 1 1 9 7 6 1 7 6 6 1 | **4/10** | Fallen 6 | 33% / 33% |
| heal_sustain target 4.5 -> 2.0 | 1 1 11 8 7 2 8 6 6 1 | 3/10 | Fallen 7 | 25% / 33% |
| heal_burst weight 6 -> 10 | 3 2 11 8 7 3 8 7 7 2 | 0/10 | Fallen 6, Great Holy 4 | 0% / 33% |
| heal_burst weight 6 -> 16 | 2 2 8 7 6 3 7 6 6 2 | 0/10 | Fallen 6, Great Holy 4 | 0% / 33% |
| heal_burst target 2.9 -> 4.5 | 2 1 10 7 5 1 8 5 6 2 | 2/10 | Rampant 4, Fallen 3 | 17% / 33% |
| both heal rows swapped (w 6/10, t 2.9/4.5) | 1 1 6 2 2 2 3 2 2 1 | 3/10 | Fallen 7 | 25% / 75% |
| burst_aoe weight 8 -> 6 or 10 | unchanged | 0/10 | Rampant 7, Great Holy 3 | 0% / 25% |
| cleanse weight 5 -> 1 | 4 2 5 3 2 2 2 2 2 3 | 0/10 | Great Holy 10 | 0% / 67% |
| disengage weight 4 -> 8 | 3 2 12 10 9 2 10 9 9 3 | 0/10 | Rampant 5 | 0% / 33% |
| mobility weight 3 -> 9 | 4 1 11 10 5 2 10 5 8 2 | 1/10 | Rampant 7 | 8% / 25% |
| heal stat channel off heal_sustain (mechanics) | 3 2 14 11 10 3 11 9 9 3 | 0/10 | Great Holy 4, Fallen 4 | 0% / 33% |
| heal stat channel off (mechanics) | 2 1 13 9 5 2 9 6 5 1 | 2/10 | Fallen 7 | 17% / 33% |
| worn gear supplies no disengage | 1 1 10 10 2 1 10 3 2 3 | 3/10 | Rampant 7 | 25% / 58% |
| worn gear supplies no mobility | 2 2 10 10 9 2 10 9 5 3 | 0/10 | Rampant 7 | 0% / 33% |
| worn gear supplies no disengage or mobility | 1 1 6 6 2 1 10 3 1 1 | **5/10** | Hallowfall 5, Rampant 5 | 42% / 58% |
| ... and no engage | 1 1 6 6 1 1 10 3 1 1 | 6/10 | Hallowfall 6 | 50% / 58% |
| castle_outpost rows re-fitted on the 6-8 harvest (section 5) | 3 1 8 8 4 1 6 4 4 4 | 2/10 | Fallen 6 | 17% / 25% |
| disengage + mobility rows re-fitted (7.0 / 14.0) | 3 2 11 9 9 2 9 8 8 3 | 0/10 | Rampant 6 | 0% / 33% |
| declared style kite (mobility x1.6, disengage x1.5) | 2 1 11 9 8 1 11 8 8 2 | 2/10 | Rampant 6 | - |

The `burst_aoe` row moves nothing: no healer here supplies it. Every heal-row
change that removes the two-handers' sustain edge hands the lead to Fallen
Staff (cleanse 2 plus Hallowfall's burst 3), not to Hallowfall. Raising the
utility targets to the harvest medians does not restore Hallowfall either:
the median is the whole party's, and six dressed incumbents already stand at
4.6 disengage on average.

Non-healer cases and the pins' setups, every change above: cases 9 and 12
keep Hand of Justice first (Permafrost Prism, the answer, at rank 48 and 51
committed); the golden-style probes on the production `recommend()` (T1 3 dps
-> a healer, T2 + healer -> frontline, T3 empty -> not pure dps, T4 two
healers in four -> no healer in the top 3, T5 six dps -> a healer) hold under
every change (the named pick moves: T3 Rampant -> Hallowfall under the
sustain target 3.0, -> Fallen under the full re-fit; T5 Hallowfall -> Great
Holy under the re-fits and disengage weight 8). The default forge at 7 moves
under the worn-gear rule (Fallen, Hand of Justice, Heavy Mace, Dawnsong,
Crystal Reaper, Forge Hammers, Arclight -> Fallen, Hand of Justice, Great
Hammer, Arclight, Weeping Repeater, Kingmaker, Forge Hammers) and fields
Fallen Staff as its healer under every change measured.

### 5. The harvest side (training split, 6-8)

The healer of single-healer parties (15,000 of 23,711; the size-7 subset,
6,318):

| healer | 6-8 | size 7 | battle list | kill-feed poll |
| --- | --- | --- | --- | --- |
| Redemption Staff | 36.1% | 46.1% | 32.1% | 38.9% |
| Hallowfall | 29.2% | 24.7% | 31.4% | 27.7% |
| Blight Staff | 11.8% | 10.4% | 11.9% | 11.7% |
| Great Holy Staff | 6.1% | 4.8% | 6.3% | 6.0% |
| Holy Staff | 4.6% | 3.8% | 4.4% | 4.7% |
| Fallen Staff | 4.0% | 3.5% | 4.6% | 3.7% |
| Rampant Staff | 0.4% (55) | under 0.7% | - | - |

Any-healer shares (all 6-8): Redemption 25.2%, Hallowfall 25.1%, Blight
11.3%, Great Holy 5.2%, Fallen 3.7%; Rampant 0.9% of battle-list parties.

What the rest of a single-healer party carries (person units at 7 for the
scaling rows):

| healer | parties | disengage: weapons / doctrine-dressed / recorded kits | mobility: weapons / dressed / recorded | cleanse (weapons) |
| --- | --- | --- | --- | --- |
| Hallowfall | 4,385 | 2.61 / 5.78 / 5.19 | 6.00 / 12.25 / 10.14 | 0.45 |
| Great Holy | 918 | 2.03 / 4.27 / 4.65 | 5.04 / 10.91 / 9.09 | 0.25 |
| Rampant | 55 | 1.38 / 3.54 / 3.02 | 3.52 / 10.34 / 6.30 | 1.24 |
| Fallen | 606 | 1.33 / 4.02 / 3.66 | 3.15 / 9.06 / 6.60 | 0.64 |
| Redemption | 5,419 | 1.97 / 4.48 / 4.88 | 4.01 / 10.89 / 8.72 | 0.54 |
| Blight | 1,772 | 2.71 / 5.40 / 5.76 | 6.03 / 12.11 / 10.14 | 0.44 |

Parties that field Hallowfall carry MORE disengage and mobility in their
other members than parties that field Great Holy, Rampant, Fallen or
Redemption, by weapon, by doctrine kit and by recorded kit (Blight parties
carry about as much). The whole party,
doctrine-dressed: Hallowfall parties field heal_sustain 3.40 (8% at the 4.5
target), heal_burst 4.67, disengage 9.28 (97% past 4.0), mobility 16.40;
Great Holy parties 4.82 (57%), 3.07, 5.77, 11.97; Redemption parties 5.08
(60%), 3.06, 5.98, 11.95.

The castle_outpost rows against the 6-8 harvest (23,324 parties outside the
Dragon Portal, doctrine-dressed, person units at 7), the rows that decide
the healer choice:

| row | weight | template target | harvest p10 / p50 / p90 | parties fielding any |
| --- | --- | --- | --- | --- |
| heal_sustain | 10 | 4.50 | 0.00 / 3.81 / 6.71 | 78% |
| heal_burst | 6 | 2.90 | 0.00 / 2.90 / 5.25 | 75% |
| cleanse | 5 | 2.70 | 0.00 / 0.00 / 2.00 | 39% |
| disengage | 4 | 4.00 | 3.00 / 7.00 / 13.00 | 100% |
| mobility | 3 | 8.00 | 9.00 / 14.00 / 19.25 | 100% |
| peel | 8 | 21.50 | 8.00 / 14.25 / 22.46 | 100% |

(the template was fitted on three published comps,
`fit: {comps: 3}`).

### 6. Side effects on held-out parties

Leave-one-out at castle_outpost 7 balanced over every holdout killer party of
7 (2,200 parties; the healer of a single-healer party always dropped plus two
random members, seed 20261008: 5,908 drops, 1,508 healer drops); incumbents
in their linked builds' gear where the analyzer linked one, else their
doctrine kit; candidates on the regime's path. Paired against the committed
engine (same drops; party-cluster bootstrap, 2,000 resamples):

| change | weapon top-3 (change, 95% CI) | hits gained / lost | MRR (95% CI of the change) | role-level | healer drops: top-3 | the engine's first healer (of 1,508) |
| --- | --- | --- | --- | --- | --- | --- |
| committed | 444 = 7.5% | - | 0.088 | 86.6% | 20.8% | Fallen 780, Great Holy 393, Rampant 290, Hallowfall 26 |
| heal_sustain target 4.5 -> 3.0 | 305 = 5.2% (-2.4; -2.9 .. -1.8) | 65 / 204 | 0.080 (-0.010 .. -0.006) | 86.6% | 11.6% | Fallen 1,313, Hallowfall 103, Nature 72 |
| heal rows swapped | 459 = 7.8% (+0.3; -0.4 .. +1.0) | 243 / 228 | 0.089 (-0.002 .. +0.004) | 87.3% | 22.3% | Fallen 1,383, Hallowfall 125 |
| worn gear supplies no disengage or mobility | 469 = 7.9% (+0.4; -0.1 .. +1.0) | 153 / 128 | 0.096 (+0.005 .. +0.011) | 86.7% | 23.0% | Fallen 547, Hallowfall 492, Rampant 301, Great Holy 151 |
| castle_outpost rows re-fitted on the 6-8 harvest | 420 = 7.1% (-0.4; -0.9 .. +0.1) | 108 / 132 | 0.088 (-0.003 .. +0.002) | 86.2% | 18.4% | Fallen 833, Great Holy 243, Nature 213, Rampant 100, Hallowfall 84 |
| all naked (NN) | 527 = 8.9% (+1.4; +0.6 .. +2.2) | 323 / 240 | 0.100 (+0.008 .. +0.016) | 88.6% | 23.4% | Fallen 1,018, Hallowfall 490 |

The real healer of the 1,508 healer drops: Redemption 683 (45%), Hallowfall
404 (27%), Blight 144, Great Holy 85, Holy Staff 56, Fallen 44, Nature 25,
Great Nature 19. The engine names Redemption Staff first in 2 of the 1,508
drops committed, 23 under the re-fit, and none under the other changes.

A first screen of more changes on 400 of the parties (1,078 drops, 278
healer drops; the committed engine read 7.7% there, and the worn-gear rule
9.2%, a lift the full sample does not keep):

| change (400 parties) | weapon top-3 | role-level | MRR | healer drops: top-3 | the engine's first healer (of 278) |
| --- | --- | --- | --- | --- | --- |
| committed | 83 = 7.7% | 88.9% | 0.085 | 21.6% | Fallen 140, Great Holy 82, Rampant 50, Hallowfall 4 |
| heal_sustain target 4.5 -> 3.0 | 61 = 5.7% | 88.7% | 0.081 | 13.7% | Fallen 244, Hallowfall 20 |
| heal_burst target 2.9 -> 4.5 | 74 = 6.9% | 88.7% | 0.087 | 18.3% | Fallen 228, Rampant 23, Hallowfall 14 |
| heal rows swapped | 95 = 8.8% | 89.4% | 0.092 | 26.3% | Fallen 253, Hallowfall 25 |
| heal stat channel off heal_sustain | 66 = 6.1% | 88.9% | 0.079 | 15.5% | Fallen 184, Great Holy 79 |
| incumbents naked (ND) | 67 = 6.2% | 88.9% | 0.090 | 15.8% | Fallen 174, Great Holy 46, Hallowfall 28 |
| candidates naked (DN) | 95 = 8.8% | 89.6% | 0.095 | 24.1% | Fallen 251, Hallowfall 24 |
| all naked (NN) | 94 = 8.7% | 89.6% | 0.100 | 23.0% | Fallen 187, Hallowfall 91 |
| worn gear supplies no disengage | 89 = 8.3% | 88.9% | 0.094 | 23.4% | Fallen 103, Rampant 75, Great Holy 55, Hallowfall 43 |
| worn gear supplies no disengage or mobility | 99 = 9.2% | 88.9% | 0.100 | 26.6% | Hallowfall 97, Fallen 87, Rampant 61, Great Holy 31 |
| rows re-fitted on the 6-8 harvest | 74 = 6.9% | 88.9% | 0.085 | 18.0% | Fallen 150, Great Holy 50, Nature 37 |
| disengage + mobility re-fitted | 89 = 8.3% | 88.9% | 0.088 | 23.4% | Fallen 145, Great Holy 77, Rampant 40 |

The real healer of those 278 drops: Redemption 123, Hallowfall 82, Blight
23, Great Holy 22, Fallen 8, Nature 7, Holy 7.

## Verdict

Evidence, not a decision.

1. **The evidence supports (b), worn gear, as the larger cause; (a), the
   heal pricing, does not explain the demotion on its own.** Between naked
   and dressed scoring the gap to Rampant moves 2.38 points: 1.19 from the
   utility rows (the incumbents' kits stand the party at or past the 4.0
   disengage target before the healer joins in 6 of 10 cases, and each
   rival's own kit brings the disengage and mobility Hallowfall's weapon
   does), 0.70 from the heal rows (the kit's heal stat channel: worn gear
   again, lifting the two-handers' sustain onto the 4.5 target while
   Hallowfall's burst overshoots 2.9), 0.50 from Rampant's kit. The
   incumbents' kits alone take 0.86 of it, the candidates' kits alone 1.54.
   Removing disengage and mobility from worn gear puts Hallowfall first in 5
   of 10 cases; no single heal-row change does better than 4 of 10.
2. **(a) alone is not supported.** Lowering the sustain target, raising the
   burst weight or target, swapping the two rows, or turning the heal stat
   channel off never puts Hallowfall first in more than 4 cases, and each
   hands the form's lead to Fallen Staff (fielded by 4.0% of single-healer
   6-8 winners), not to Hallowfall. On held-out 7s the sustain target 3.0
   lowers the hidden member's top-3 from 7.5% to 5.2% (-2.4 points, CI -2.9
   to -1.8) and the healer drops' top-3 from 20.8% to 11.6%, with Fallen the
   first healer in 87% of healer drops; the swap moves neither (+0.3, CI
   -0.4 to +1.0).
3. **A third cause sits outside both: the cleanse row.** In the four cases
   where even naked scoring prefers Fallen Staff (3, 4, 7, 8) the party
   fields no cleanse, and the cleanse carriers (Fallen, Rampant, Blight,
   Lifetouch, Nature) collect about 1.5-2.2 at the castle_outpost cleanse
   row (target 2.7, weight 5), where the median 6-8 winner fields none
   (p50 0.0; 39% field any).
4. **The harvest contradicts the gap-closing reading of Hallowfall.** Its
   parties carry more mobility and disengage elsewhere than the parties of
   Great Holy, Rampant, Fallen or Redemption (Blight's about as much), and
   92% of them sit under the 4.5 sustain target dressed:
   winners pick the mobile healer with mobile comps, a preference the
   marginal coverage of a met utility row cannot express (declared kite
   moves 2 of 10).
5. **Measured remedies and their side effects.**
   - The worn-gear rule (disengage and mobility read no gear supply, the
     structural floors' weapon-basis rule extended to two utility rows) is
     the one change that makes Hallowfall a common first healer on held-out
     7s (492 of 1,508 healer drops, against 26) and raises MRR (0.088 to
     0.096, CI +0.005 to +0.011) and the healer drops' top-3 (20.8% to
     23.0%); the hidden member's top-3 moves +0.4 points (CI -0.1 to +1.0).
     It is an engine-wide pricing rule in both ports, it discards utility the
     harvest says winners do carry, it reshapes the default 7 forge (Great
     Hammer, Weeping Repeater, Kingmaker replace Heavy Mace, Dawnsong,
     Crystal Reaper) and its effect at 10+ is in the next point.
   - A heal-row template retune is not supported: no flip on the form,
     Fallen as the first healer, a lower or unchanged holdout read.
   - Re-fitting the castle_outpost rows on the 6-8 harvest under the
     standing convention moves 2 of 10 on the form and leaves the holdout
     read where it is (-0.4 points, CI -0.9 to +0.1).
   - Scoring every member naked (V3-W) reads the held-out 7s better than
     the production dressed path: top-3 8.9% against 7.5% (+1.4 points, CI
     +0.6 to +2.2), MRR 0.100 against 0.088, role-level 88.6% against 86.6%.
     At castle_outpost 7 the dressing costs held-out accuracy, which is the
     same finding as the demotion seen from the harvest side.
   - Golden pins stay where they are until a decision: the probe setups of
     T1-T5 hold under every change measured.
6. **Beside the question**: the most fielded 7-man healer is Redemption
   Staff (46% of single-healer 7s in the training harvest, 45% of the
   held-out healer drops); the engine names it first in 2 of 1,508 held-out
   healer drops (23 under the re-fit, none under the other changes).

## Method note

The measurement scripts ran outside the repository, each against the committed artifacts the Context names; the method above is the whole of what they do.
