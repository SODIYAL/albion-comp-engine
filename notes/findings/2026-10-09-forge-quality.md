# Forge quality on today's engine: the planner grid and the Dragon Portal pools

Report-only. No engine, template, sheet or test file was edited, and nothing
here changes a score.

## Context

**Question.** What the forge button builds when it builds a whole comp,
graded against the harvest, on the engine as it stands, and which readings
of the earlier forge-quality sweep still hold. The quality gates measure the
next pick (`tests/tier2_blindtest.py v4` on published comps minus one
member; `v4h` on the harvest, report-only); this sweep reads the forged
roster whole.

**What ran.** `Engine.forge(size)` as the planner's forge button calls it
(dressed, the default suggestion pool, no locks), then the two rosters the
refresh button walks next (`forge(avoid=)` over every roster already shown).
Two grids:

- the planner grid of the earlier sweep, 72 cells: Castle Outpost 5 and 7
  and Roads 7 under balanced, brawl, clap and kite; Faction War 10 and 15,
  Blackzone Roam 10, 15 and 20, Territory Defense 15, 20 and 25, Castle 20
  and 25 under all six styles;
- the Dragon Portal, 18 cells: each matchmaking pool at its top size (3, 5
  and 7 under the four small-size styles, 20 under all six).

**Artifacts.** Commit `c634dff`. `pipeline/out/dataset-latest.json`
SHA-256 `457179b2ea43e3dd9f964ad29b8bd1b5000f89000815e6e2fa7961ac0420d582`;
`pipeline/out/party_rosters.json.gz` SHA-256
`829c8c293b0735393e66cad37602562a8d6e162c9bfc8ab77992b7c23270ba4b` (31,258
battle-list battles; the hash `role_counts.json` and `skeletons.json`
record); `pipeline/out/party_styles.json` SHA-256
`6b056a5a27cdd58bb655f2ab8d1de9ef801c70f24f8980c25f58d61ffa5b66b7`. Run
stamp 2026-10-09.

**Evidence.** Battle-list killer parties with every weapon known (59,475
parties of 3+), each with its `party_styles.json` label, and the Dragon
Portal's dominant parties (no deaths, a kill, every weapon known and in the
catalog: the unit its rows and fielded lists are fitted on; 7,910 parties).
A cell reads the parties of the forged size +-2 and, at 10+, the same
identity label; a portal pool reads its own sizes under any label (portal
parties carry none). Each cell reads the holdout slice (`battle % 5 == 0`,
which no shipped table learns from) wherever that slice holds 40 rosters,
else every battle: 52 of the 60 planner cells at 20 or under read the
holdout (the other 8 are brawl_clap), a median 334 distinct rosters per
cell. Killer parties stop at 20, so the 25 cells borrow the 18-20 cell. Role
counts grade against `role_counts.json` (p10 / p90), seats and standoff
tools against `skeletons.json`.

**The earlier sweep.** Commit `2a8805f`, never merged (its note
`notes/findings/2026-09-12-forge-quality-findings.md` and its board at that
commit), on the artifact of 7,652 battles: before skeleton-first generation
(`99a3c5b`: seat typicals, plan minima, generated copy allowances), the
portal's own rows, fielded gate and role counts (`7c958ec`, `9c16eca`,
`a3d1259`), off-hands scored from their stats and E self-costs (`4e12c7a`),
the gap-closer rule (`e9278ea`) and the plain Cape (`6effaed`). Its
evidence cells held a median 125 distinct rosters against 334 now, so a
weapon a few winners field read "never" more often there. Every comparison
below is the same measure computed on each sweep's own report.

## Numbers

### The planner grid against the earlier sweep

| measure | earlier sweep | today |
| --- | --- | --- |
| full, feasible rosters with no filler or held slot | 72 / 72 | 71 / 72 (Territory Defense 25 clap forges 23 of 25) |
| identity agrees with the forged-for style (styled cells) | 30 / 59 | 37 / 59 |
| kill checklist ready | 71 / 72 | 71 / 72 (the same cell: Castle Outpost 5 brawl, burst light off) |
| role counts inside [p10, p90] at 10-20 | 46 / 48 | 47 / 48 |
| cells with `catch` past its soft cap | 27 / 72 | 9 / 72 |
| cells with any row under the bare minimum | 24 / 72 | 22 / 72 |
| slots at 20 or under never fielded in the cell | 90 / 826 (11%) | 48 / 826 (6%) |
| ... fielded by under 2% of the cell's rosters | 66 / 826 (8%) | 105 / 826 (13%) |
| ... the two together | 156 / 826 (19%) | 153 / 826 (19%) |
| ... the two together at 10-20 | 133 / 750 (18%) | 132 / 750 (18%) |
| median share of forged weapon pairs seen together in 3+ rosters | 40% | 57% |
| median nearest harvested roster (multiset Jaccard) | 0.33 | 0.33 |
| Fists of Avalon: cells at 10+ / highest prevalence / cells never fielding it | 56 of 60 / 11.5% / 22 | 53 of 60 / 6.6% / 16 |
| cells where a refresh alternative outscores the button | 25 / 72 | 27 / 72 |
| ... best gap per such cell, median / largest (share of comp score) | 0.20% / 0.62% | 0.07% / 1.22% |
| alternatives one / two slots from the button's roster | 81 / 37 of 144 | 87 / 34 of 144 |
| healers in the styled 25-man forges | 6-7 in 10 of 10 | 6-7 in 9 of 10 (5 at Territory Defense clap_kite) |
| slots kite and clap rank-0 rosters share (mean; Blackzone Roam 20) | 55%; 14 of 20 | 50%; 10 of 20 |
| slots clap_kite and clap rank-0 rosters share (mean; Blackzone Roam 20) | 70%; 16 of 20 | 55%; 11 of 20 |

No generated slot carries a weapon a suggestion gate bars (viability
exclusion, style unfit, generation situational, pool unfielded) or an
unseated weapon; the earlier sweep checked exclusions, style-unfit and
unseated members, with the same result.

### Identity: what a forged roster reads as

| forged for | earlier sweep | today |
| --- | --- | --- |
| brawl (13 cells) | brawl 13 | brawl 13 |
| clap (13) | clap 12, clap_kite 1 | clap 12, kite 1 (Roads 7, one standoff tool) |
| kite (13) | clap 8, kite 3, clap_kite 2 | clap 6, kite 3, clap_kite 3, brawl 1 |
| clap_kite (10) | clap 8, clap_kite 2 | clap_kite 9, clap 1 (Castle 25) |
| brawl_clap (10) | brawl 4, split 4, clap 2 | brawl 9, split 1 (Castle 20) |

The kite cells by size: at 15 the roster reads kite in all three contents
(Faction War, Blackzone Roam, Territory Defense) and at 20 clap_kite in all
three (Blackzone Roam, Territory Defense, Castle), each with the plan
minimum's two standoff tools. At 10 it reads clap (Faction War, Blackzone
Roam): one standoff tool, the plan minimum at 10, which the identity read
counts as a kite only under a low bomb share. Below 10 (Castle Outpost 5
and 7 clap, Roads 7 brawl) and at 25 (clap at both contents) no plan row
applies and the forge fields one standoff tool or none. Every kite and
clap_kite cell at 10-20 forges exactly its plan minimum.

The brawl_clap cells now read seat cells of their own (50-80 rosters per
size through a +-1 window) and copy cells at 10-14 and 15-19; their band
keeps the base `ranged_aoe_core` minimum (3 at 15-19, 4 at 20). The forged
roster reads brawl, a melee ball, in nine of ten cells and never
brawl_clap; at Territory Defense 20 and Castle 20 it fields three
ranged-AoE seats against the brawl_clap cell's typical of one and p90 of
two.

### Structure

- Role counts: the one cell at 10-20 outside the harvest band is Castle 20
  clap (one support; the cell's p10 is 2). Supports at 20 sit at the cell's
  p10 on clap and clap_kite: two in five of the six cells, one at Castle 20
  clap, against a typical of 4 (clap) and 3 (clap_kite).
- Below 10 the role cells are published comps (Castle Outpost 7: three
  comps; Roads 7: one comp). Six of the eight cells at 7 sit outside them in
  one or two roles: a support over at Castle Outpost 7 brawl and kite and
  Roads 7 balanced, a dps or frontline count off by one elsewhere.
- Seats: 42 of the 48 cells at 10-20 keep every primary seat inside the
  skeleton cell's [p10, p90]. Outside: a zone support in four brawl cells
  (Blackzone Roam 10 and 20, Territory Defense 20, Castle 20; the brawl
  cell's p90 is 0), a brawl healer at Blackzone Roam 10 brawl (p90 0), and
  the brawl_clap ranged-AoE seats above.

### Supply board

- Over the 60 cells at 20 or under: 14-28 rows at or above typical (median
  21; 22 before), 0-12 between the minimum and typical (median 4), 0-4 under
  the bare minimum (median 0). Rows under the minimum most often: anti_dive
  6, tankiness 4, cleanse 3, burst_aoe 3, burst_st 3 (before: damage_debuff
  8, anti_dive 6, root 5, tankiness 5).
- Past the soft cap: purge in 11 cells, catch 9, silence 7, clump_create 7,
  engage 6 (before: catch 27, clump_create 12, root 6). Outside Roads 7
  (catch 6-7 against a soft cap of 5.28, Hand of Justice carrying 3-4 of
  it) the purge and catch excesses stay under 10% of the cap and spread over
  three or four members (Polehammer, Heavy Mace, Fists of Avalon, Icicle
  Staff, Hand of Justice); the largest is Castle 25 clap_kite, catch 38.5
  against 36.65 (Grailseeker 10, Polehammer 8, Grovekeeper 5, Hand of
  Justice 4). Every silence excess carries one Heavy Mace in its doctrine
  kit, which alone supplies 14.83 units (its E plus the Hellion Hood's Smoke
  Bomb) against soft caps of 12.4-23.4.

### Evidence: what winners field

The never-fielded share halved and the under-2% share rose by about the
same slots: the harvest grew fourfold, and a weapon a few winners field
moves from "never" to "rare" by construction. Together they hold at 19% of
forged slots (18% at 10-20). By style, never / under 2% over the cells at
20 or under: balanced 0% / 17%, brawl 2% / 15% (13% / 6% before), clap
2% / 20%, kite 6% / 11%, clap_kite 10% / 6%, brawl_clap 17% / 5% (34% / 0%
before).

The weapons the forge reaches for at 10-20 (48 cells), with the highest and
the median share of a cell's rosters that field them:

| weapon | cells | highest | median | cells never fielding it |
| --- | --- | --- | --- | --- |
| Hand of Justice | 43 | 39% | 15% | 0 |
| Fists of Avalon | 41 | 6.6% | 1.3% | 12 |
| Realmbreaker | 39 | 90% | 64% | 0 |
| Fallen Staff | 39 | 20% | 11% | 0 |
| Exalted Staff | 35 | 49% | 26% | 0 |
| Polehammer | 35 | 56% | 32% | 0 |
| Heavy Mace | 32 | 69% | 37% | 0 |
| Permafrost Prism | 29 | 94% | 59% | 0 |
| Hallowfall | 27 | 97% | 94% | 0 |
| Kingmaker | 22 | 13% | 4.7% | 6 |
| Wild Staff | 22 | 6.9% | 4.3% | 1 |
| Hellfire Hands | 21 | 6.9% | 4.5% | 0 |
| Arclight Blasters | 19 | 0.8% | 0.0% | 11 |

Fists of Avalon (fifteen nonzero capability rows; the catalog's p90 is 14)
is still the second most forged weapon and still on a few percent of the
rosters in any cell it is forged into. Arclight Blasters is new to the
forge's reach (no cell of the earlier sweep): 26 of the 60 cells at 10+, on
under 1% of any cell's rosters. The other breadth picks the earlier note
named are forged into fewer cells and fielded in more of them (cells at 10+
/ cells never fielding them, before and now): Great Holy Staff 21 / 12 and
5 / 0, Grailseeker 29 / 10 and 9 / 1, Crystal Reaper 18 / 13 and 8 / 3,
Carrioncaller 34 / 12 and 21 / 4, Weeping Repeater 10 / 10 and 5 / 2;
Kingmaker stays (25 / 9 and 27 / 7).

### Refresh alternatives

A refresh alternative outscores the button's roster in 27 of the 72 planner
cells and 8 of the 18 portal cells: 48 alternatives in all. Each gap,
split:

- the shared members' combos and kits alone (the button's weapons, each
  shared member in the alternative's build) beat the button in 1 of 48
  (Territory Defense 15 balanced);
- the weapon swap alone (the alternative's weapons, every shared member in
  the button's build) beats it in 24 of 48, twelve of them swaps of two to
  four slots with every shared member's build identical; the largest gaps
  are swaps (Blackzone Roam 15 brawl_clap: four slots, +0.92 and +0.97 comp
  score, the swap alone +0.72 and +0.70);
- in the other 23 the swap scores below the button until other members'
  builds move with it.

The gap is the weapon choice in one to four slots: the alternative's builds
on the button's weapons beat the button once in 48, and the constrained
1-opt already re-resolves each slot's build in place, so a closing pass
over combos and kits has little left to find. The bounded 2-opt (the four
weakest slots in pairs, a shortlist of 12) does not reach the multi-slot
swaps.

### Past 20

No page forges a single party past 20; the 25 cells read the engine API.
Territory Defense 25 clap forges 23 of 25 (`feasible` false), and refresh
returns the same partial roster without `exhausted`: the beam dies before
the final depth, where `avoid` is applied. Healers in the styled 25 cells:
6-7 in nine of ten (Territory Defense clap_kite 5); balanced forges 5 at
both contents (the base band's maximum).

The forge now refuses a single party past 20 (V: 10, Forges stop at 20),
and the sweep's grid stops at 20; the 25 cells above stay as measured.

### The Dragon Portal pools

All 18 rosters are full, feasible and kill-ready, and none carries a weapon
the pool's dominant winners do not field (the fielded gate holds at 3, 5
and 7). In the gated pools no slot is a weapon the holdout winners never
field and 10 of 60 sit under 2% of their rosters (17%, against 18% at
10-20 on the planner grid); at 20 (the 15-20 pool: 49 rosters, every
battle) 4 of 120 slots are never fielded. Identity agrees in 8 of 14 styled
cells: kite reads kite only at 20, and the trio is one roster (Hallowfall,
Battle Bracers, Longbow) under balanced, clap and kite, read as split. At
20 the clap, kite, clap_kite and brawl_clap rosters each field one
ranged-AoE seat past the open-world seat cell's p90 (7, 6, 7 and 3). A
refresh alternative outscores the button in 8 of 18 cells.

## Verdict

Evidence, not a decision.

**No longer holds.**

1. *clap_kite forges read clap*: 9 of 10 read clap_kite (2 before): the
   eight cells at 10-20 each on the plan minimum's two standoff tools,
   Territory Defense 25 on three; Castle 25 (one tool, no plan row past 20)
   reads clap.
2. *The forge never builds a kite*: at 15 and 20 the kite forge reads a
   kiting plan in all six cells (kite at 15, clap_kite at 20). At 10, below
   10 and at 25, where the plan row demands one tool or none, it still
   reads clap or brawl (7 of 7). A pure kite at 20 is the open question
   BACKLOG "Kite weights" carries.
3. *Catch over-stacks in a third of forged comps*: 9 of 72 cells, under 10%
   past the cap outside Roads 7; no capability is past its soft cap in more
   than 11 cells.
4. *Every cell forges a full roster*: Territory Defense 25 clap is two
   short, and its refresh repeats the roster unflagged.

**Still holds.**

5. *brawl_clap never reads brawl_clap*: 0 of 10. It now reads brawl, with
   ranged-AoE seats past the cell's p90 at 20 under the base band's
   minimum.
6. *Breadth picks winners rarely field*: Fists of Avalon in 53 of 60 cells
   at 10+ on at most 6.6% of a cell's rosters, joined by Arclight Blasters
   (26 cells, under 1%). About a fifth of forged slots sit on weapons under
   2% of the cell's winners field, the same share as before.
7. *A refresh alternative outscores the button*: 27 of 72 cells; the
   median best gap is smaller (0.07% of comp score) and the largest larger
   (1.22%). The gap is a multi-slot weapon choice, not combos or kits.
8. *Twenty-five is the scorer's comp*: 6-7 healers in nine of ten styled
   25 cells.
9. *Refresh walks one swap at a time*: 87 of 144 alternatives differ from
   the button's roster by one slot.
10. *Structure and kill pressure*: role counts inside the harvest band in
    47 of 48 cells at 10-20; the kill checklist ready in 71 of 72; no gated
    or unseated member in any generated slot.

**New readings.** Seats sit inside the skeleton's band in 42 of 48 cells
(brawl zone supports, brawl_clap ranged seats). Supports at 20 stay at the
cell's p10 on clap and clap_kite. The gated portal pools never forge a
weapon their holdout winners never field. The styles diverge more than
before (clap_kite and clap rosters share 55% of their slots, 70% before).

Prevalence is popularity, not effectiveness: the evidence columns say what
winners field, never that a forged comp fights worse.

## Method note

The measurement script lives at `pipeline/audit_forge_quality.py`
(report-only; nothing in the build reads it). `py -3
pipeline/audit_forge_quality.py` writes the machine-readable report, the
board and a grading form to `review/forge_quality/` (gitignored; `--out`
moves them). The first run on an artifact parses the roster artifact
(several GB of memory at peak) and caches the evidence parties beside the
report, keyed by the SHA-256 of the artifact and of `party_styles.json`;
later runs on the same artifacts are engine-only. This run built the
evidence in 18 seconds and forged and graded the 90 cells in 21 minutes at
below-normal priority; three cells rerun from the cache matched the full
run exactly. The comparison with the earlier sweep reads both reports
through the same definitions, and the refresh-gap split rescored each
beating alternative with `Engine.comp_score`; both are scratch tooling, not
committed.
