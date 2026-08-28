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

**Some spreads are too wide to be one number.** peel runs 1.7-2.5 in eight
comps but 11.0 and 11.7 in the two roads comps; silence 0.9-3.0 except the same
two roads comps at 6.6; zone_control ~2 except sob_blaze at 10.8. These are
content- or style-shaped, not scale-shaped, which is direct evidence for the
per-style / per-content target modifiers the re-fit was going to need anyway.

## Open questions for the owner

1. **Re-fit basis.** Re-measure every target in person units from this table
   (shared base + content/style modifiers), or keep weapon-unit targets and
   change what counts as supply? The measurement supports the former.
2. **execute and anti_zone.** Drop the rows, or are these capabilities real
   needs the corpus happens not to cover (in which case the corpus, not the
   template, is the gap)?
3. **peel** -- still the standing open question. The corpus says the spread is
   content-shaped (roads comps field 5x what others do). Game knowledge said
   comp-relative. The two readings are compatible if roads play IS the
   peel-heavy style; a ruling would settle it.
4. **Uncurated pieces.** 31 recorded pieces resolve to real items with no
   capability sheet and so supply nothing: 20x revive potion, fish meals, one
   gatherer hood. Curate the revive potion, or rule it out of the model?
