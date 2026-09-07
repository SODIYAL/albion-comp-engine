# What real comps actually field, per person (2026-08-28)

REPORT ONLY. Per the anti-circularity rule in `tests/VALIDATION.md`, these are
measurements and hypotheses for the owner, not fixes. No template number was
changed to produce them.

## Why this could not be measured before today

The evidence layer was discarding most of the gear the comps record. 11 of 13
published comps write gear as game item IDs (`ARMOR_CLOTH_AVALON`), and
`match_gear` matched only display names, so 729 of 1124 gear cells resolved to
nothing. Only two comps carried gear into the builds index. After the resolver
fix (commit "Gear resolver: read item IDs, not just display names"), all 13
carry gear: 0 of 1117 recorded pieces unresolved, 1086 = 97.2% reaching a
curated record.

## The measurement

Each comp scored dressed, in its own content template at its own size, with
`effective_supply(party, None, gears)`. The number shown is **fielded supply
divided by the template target** for that capability. 1.00 means the comp
fields exactly what the template asks for.

```text
comp                                         n dressed
albioncompo_20v20_competitive_2026_08       20      20
albioncompo_bist_roam15_2026_01             15      15
albioncompo_push_monkey_7_2026_05            7       7
albioncompo_roads_oneshot_2026_07            7       7
albioncompo_sob_blaze_os_2026_06             7       7
albioncompo_sortasaucy_7man_ftb_2026_05      7       7
albioncompo_ss_kite_20_2026_06              20      20
cb_clonepeek_zvz20_2026_03                  20      20
deadlyhooker_large_scale_2026_08            20      20
timothy_blap_blackzone_roam_2026_08         20      20


SUPPLY PER PERSON vs TARGET PER PERSON  (ratio; 1.00 = exactly the template target)
a ratio far above 1 means the target is fitted in the wrong unit

capability             albionc albionc albionc albionc albionc albionc albionc      cb deadlyh timothy
anti_dive                 9.58    5.42    1.67    2.08    2.08    0.83   10.42    5.83   11.25    2.50
anti_zone                 2.50    0.00    0.00    0.00    0.00    0.00    2.50    0.00    0.00    0.00
buff_allies              10.00    4.40    3.20    5.00    5.00    1.80   12.00    9.80   11.20   10.20
burst_aoe                 3.56    2.23    1.72    1.71    2.18    2.09    2.34    2.17    3.04    1.25
burst_st                  0.59    2.42    0.00    0.82    0.00    0.00    1.26    0.00    0.00    4.62
catch                     1.71    1.65    1.52    1.54    1.54    1.64    1.39    1.35    1.19    1.11
cleanse                   5.00    2.50    0.00    2.22    2.22    0.00    7.50   10.00   10.00    5.00
clump_create              2.00    0.00    0.00    0.00    0.00    0.40    1.20    2.00    1.20    1.60
damage_debuff             3.12    1.25    2.50    0.00    0.00    0.00    5.62    3.12    0.00    3.12
disengage                 5.00    3.33    0.63    5.59    2.06    1.67    5.40    3.97    2.06    1.11
engage                    1.62    2.39    2.69    2.65    2.65    1.59    0.94    1.45    2.65    2.82
execute                   0.00    0.00    0.00    0.00    0.00    0.00    0.00    0.00    0.00    4.24
heal_burst                2.04    1.73    0.92    2.31    2.31    1.02    1.08    1.57    0.00    1.33
heal_reduction            2.94    0.59    1.76    2.06    1.18    5.88    3.82    2.65    1.76    2.94
heal_sustain              1.74    2.04    2.02    1.73    1.73    1.66    1.13    2.21    0.28    1.91
interrupt                 2.22    2.22    0.00    1.11    1.11    1.11    2.22    2.22    0.00    1.11
knockback_displace        5.51    4.21    0.00    4.72    5.28    2.04    4.80    4.63    3.33    1.37
max_health_cut            1.11    1.11    0.00    1.11    0.00    0.00    3.33    1.11    1.11    1.11
mobility                  1.84    2.29    2.16    2.21    1.76    1.01    1.41    1.52    1.79    2.63
peel                      2.00    2.54    1.77   10.96   11.73    1.70    1.77    2.12    2.14    2.17
purge                     1.33    2.67    0.89    3.33    2.22    0.89    1.33    1.33    1.78    1.11
ranged_presence           1.20    0.80    0.57       -       -    1.14    1.20    1.20    1.40    0.60
resist_shred              1.50    1.30    0.80    2.31    0.00    0.80    2.10    2.60    2.70    2.60
root                      3.00    1.23    1.56    1.51    1.83    2.08    4.36    3.90    1.61    2.93
self_sustain                 -       -       -    0.59    0.59       -       -       -       -       -
silence                   1.14    2.22    0.00    6.61    6.61    1.46    0.85    2.93    2.52    5.98
slow                      3.34    1.84    1.75    0.83    2.76    1.76    2.84    2.63    4.07    2.21
stun                      8.89   10.33    0.00    7.09    5.32    7.71    7.97    2.30    6.49    2.35
sustained_dps             3.51    3.23    4.82    5.69    9.31    3.18    2.88    2.92    4.91    4.80
tankiness                 4.31    5.82    5.46    5.83    5.06    6.64    5.04    4.62    4.19    5.93
zone_control              2.56    1.93    1.90    2.31   10.77    2.22    1.22    2.56    1.89    2.67
```

## What it shows

**The unit defect is real and it is not uniform.** Splitting the rows by what
supplies them separates cleanly:

- **Weapon-driven capabilities are roughly calibrated.** catch 1.1-1.7,
  ranged_presence 0.6-1.4, engage 0.9-2.8, mobility 1.0-2.6, heal_sustain
  0.3-2.2. These are close to the 0.9x-least/1.15x-most fitting convention.
- **Gear-driven capabilities overshoot hugely and inconsistently.** tankiness
  4.2-6.6x in EVERY comp without exception; buff_allies 1.8-12x; stun 2.3-10.3x;
  cleanse 0-10x; anti_dive 0.8-11.3x; knockback_displace 0-5.5x.

That is the defect stated precisely: targets were fitted in weapon+spell-pick
units, supply is now measured on whole dressed people, and the gap is worst
exactly where worn gear contributes most. tankiness is the cleanest single
signal -- ten of ten comps, 4-7x, no exceptions -- and it is the same failure
mode the 2026-08-12 pseudo-tankiness ruling addressed, arriving through the
gear stat channel.

**Two template rows may be asking for something nobody fields.** `execute` is
0.00 in nine of ten comps (only blap, 4.24). `anti_zone` is 0.00 in eight of
ten. Under the comp-fitting convention (target = 0.9x the least any good comp
fields), a capability that good comps field zero of has a target that cannot be
justified from the corpus.

**CORRECTED (same day).** This section first read: "peel runs 1.7-2.5 in eight
comps but 11.0 and 11.7 in the two roads comps ... these are content- or
style-shaped." **That was wrong, and it was wrong because a ratio was read as
if it were a measurement.** Checking the raw numbers per person:

```text
style       content         n  comp                          peel/person  (target/person)
brawl       blackzone_roam  7  push_monkey                      3.57        (2.01)
brawl       blackzone_roam 15  bist_roam15                      5.11        (2.02)
brawl       blackzone_roam 20  blap                             4.36        (2.01)
brawl_clap  blackzone_roam 20  clonepeek                        4.28        (2.01)
clap        blackzone_roam  7  sortasaucy                       3.43        (2.01)
clap_kite   blackzone_roam 20  deadlyhooker                     4.32        (2.01)
clap_kite   roads           7  roads_oneshot                    4.07        (0.37)
clap_kite   roads           7  sob_blaze                        4.36        (0.37)
kite        blackzone_roam 20  20v20_competitive                4.04        (2.01)
kite        blackzone_roam 20  ss_kite_20                       3.57        (2.01)
```

**Peel per person is essentially CONSTANT -- 3.4 to 5.1 across every style,
every content, every size.** The two roads comps sit at 4.07 and 4.36, dead in
the middle of the pack. They did not field 5x the peel; the roads template asks
for 0.37 per person where blackzone_roam asks 2.01, a 5.4x difference in the
TARGET. The whole apparent spread was the denominator.

This is the real finding, and it is stronger than the one it replaces: **the
templates disagree with each other about peel far more than real comps do.**
Same shape in silence (targets 0.13-1.01 per person) and zone_control
(0.19-0.45). Comps are consistent; the templates are not. Every ratio in the
big table above carries this hazard -- a high number can mean "comps bring a
lot" OR "this template asks for little", and only the raw per-person view
separates them. The re-fit should be done on raw per-person supply, not on
ratios.

## Open questions for the owner

1. **Re-fit basis.** Re-measure every target in person units from this table
   (shared base + content/style modifiers), or keep weapon-unit targets and
   change what counts as supply? The measurement supports the former.
2. **execute and anti_zone -- RULED 2026-08-28, shipped.** Owner: "the anti
   zone is only on one weapon, the crystal healing staff and it's brought [by]
   some zvz groups but usually when party is like 30+ people. so it's fine to
   keep those targets just maybe make some optional. as for execute keep that
   too but optional." Confirmed against the catalogue before implementing:
   `anti_zone` is supplied by exactly ONE item, Exalted Staff
   (`2H_HOLYSTAFF_CRYSTAL`); `execute` by five single-target melee weapons.
   Both rows now carry `optional: true` in all six templates. See below.
3. **peel -- RULED 2026-08-28.** Owner: "peel is about how you are fighting."
   The corpus neither confirms nor contradicts it: once measured per person,
   peel is flat at ~4 everywhere, so the data shows no content effect AND no
   style effect. My earlier claim that the corpus showed a content effect was
   an artifact (see the correction above). The ruling stands on game knowledge,
   and converts into per-style target modifiers during the re-fit -- there is
   no corpus-derived number to fit them to yet.
4. **Uncurated pieces.** 31 recorded pieces resolve to real items with no
   capability sheet and so supply nothing: 20x revive potion, fish meals, one
   gatherer hood. Curate the revive potion, or rule it out of the model?

## Shipped from these rulings (2026-08-28)

`optional: true` on a template requirement row. Semantics: bringing the
capability earns its coverage exactly as before; NOT bringing it is not a hole.

Mechanically this is a **denominator-only rule, and provably so**: every
fitness term for a capability at zero supply is already zero -- coverage is
`min(1, 0/target)^gamma`, headroom requires `have > target`, over-stack
requires `have > soft_cap`. So an optional capability can only leave
`max_fitness()`, never `fitness()`. A hard floor IS charged at zero supply, so
optional + hard floor is contradictory; both ports raise on that combination
rather than scoring inconsistently. Neither capability has a floor in any
template.

Consequence: **no score, ranking, pick value, or forge decision moves** -- only
the percentage shown. Confirmed by the full battery green with zero re-pins
(57/57 golden, 38/38 forge, 60/60 parity including a new party-aware
`max_fitness` case). Measured display effect:

```text
comp                       content          was     now   shift
20v20_competitive          blackzone_roam  87.3%   87.5%   +0.2
bist_roam15                blackzone_roam  78.9%   79.7%   +0.8
push_monkey_7              blackzone_roam  69.0%   69.9%   +1.0
roads_oneshot              roads           79.2%   82.5%   +3.3
sob_blaze_os               roads           71.8%   74.8%   +3.0
sortasaucy_7man            blackzone_roam  80.4%   81.6%   +1.1
ss_kite_20                 blackzone_roam  87.1%   87.2%   +0.2
clonepeek_zvz20            blackzone_roam  86.5%   87.4%   +0.9
deadlyhooker               blackzone_roam  68.6%   69.2%   +0.7
blap                       blackzone_roam  85.6%   86.2%   +0.7
```

The roads comps move most because roads carried `execute` at weight 4, the
heaviest row in the corpus that nobody fields. The radar follows the same rule:
an optional capability at zero supply leaves the axis instead of reading as a
gap.
