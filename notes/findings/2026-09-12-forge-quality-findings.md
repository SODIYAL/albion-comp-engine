# Forge quality: what the engine fields when it builds a whole comp (2026-09-12)

The question asked: after the September work, how good are the comps the
engine comes up with? The two quality gates answer a narrower question
(the next pick, one slot at a time): `tier2_blindtest.py v4` passes at
17/23 role-level (74%) on 4 published comps; `v4h` reports 67-70% over
150 harvested killer parties (rebuild-5 recall 84-86%). Neither looks at
a forged roster as a whole, so this round added a report-only sweep,
`pipeline/audit_forge_quality.py`, and ran it on the whole planner grid:
72 cells (6 contents x sizes 5-25 x every style), the production forge
with no locks - the page's forge button - plus two refresh alternatives
per cell. The board with every number is
`notes/findings/2026-09-12-forge-quality-sweep.md`; the machine-readable
report is `pipeline/out/forge_quality_report.json`; the owner's grading
form (display names only, no engine numbers) is
`tests/forge_grading_2026-09-12.md`.

Everything below is a hypothesis for the owner (anti-circularity, standing
rule 1). Prevalence in a harvest cell is popularity, never effectiveness
(rule 7); a forged weapon nobody fields is a question, not an error.

## What holds up

- **Every cell forges a feasible roster** with no filler and no held slots
  (72/72). Every role minimum, predicate minimum and typical-count rule is
  met at every size and style.
- **Role structure matches the harvest.** At 10-20 every role count sits
  inside the harvest's [p10, p90] for the declared style at that exact
  size in 58 of 60 cells (castle 20 kite and brawl_clap read support one
  under). Below 10 the forge fields one support where the three
  castle-outpost comps field none (p90 0.8) - a 1-body question.
- **The kill checklist is green** (pierce, heal-cut, burst) in 71/72
  cells; only castle_outpost 5 brawl reads partial.
- **No hygiene faults**: no duplicates past their allowance, no unseated
  weapons, no style-unfit or excluded weapons in a generated slot.
- **Brawl and clap forges read as what they were forged for**: 13/13
  brawl cells read brawl, 12/13 clap cells read clap (one clap_kite).
- **The capability board is mostly green.** Over the 60 cells with
  harvest evidence the typical roster has 20-27 rows at or above the
  typical winner, 2-6 between min and typical, 0-1 under the bare minimum.

## What does not hold up

### 1. The forge does not build a kite (or a brawl_clap)

`comp_identity` - the engine's own read, validated over four blind rounds -
disagrees with the style the roster was forged for in 29 of 59 styled
cells, and the disagreement is one-directional:

| forged for | reads as |
|---|---|
| kite (13 cells) | clap 8, clap_kite 2, **kite 3** (blackzone 10 / 15, territory 15) |
| clap_kite (10) | clap 8, **clap_kite 2** |
| brawl_clap (10) | brawl 4, split 4, clap 2, **brawl_clap 0** |

At blackzone 20 the kite roster shares 14 of 20 weapons with the clap
roster and 17 of 20 with the clap_kite roster: the style rows move the
weights and the role bands, but the forge lands in the same basin. The
kite rosters carry no standoff tools and no evade share - the things the
identity layer looks for (blind round 1: "the kite half is STANDOFF
TOOLS") - because nothing in the kite template REQUIRES them: the kite
style multiplies weights and sets a ranged core, and the scorer's best
answer to "more mobility / disengage weight" is still catch tanks plus a
ranged bomb line. Hypotheses, in the order the evidence supports them:
(a) kite's style x band rows carry the harvest's kite median for
`disengage` / `mobility` / `evade`-class rows and those are met by gear
and passives, not the E - a weapon-unit floor on a standoff capability
(rule 10, source-aware floors) is the mechanism the brawl side already
has; (b) the generation-fit gate lets catch tanks into kite pools
because their E "fits" kite at the band, so the pool is not a kite pool.
Both are owner calls; neither is a weapon rule.

### 2. One engine core, every style

At 10+ the same weapons appear in nearly every cell whatever the style:
Fists of Avalon in 56 of 60 cells, Hand of Justice 55, Realmbreaker 55,
Fallen Staff 53, Heavy Mace 47, Polehammer 43. Some of these are what
winners field (Realmbreaker is on 73-83% of harvested 20-man rosters,
Hallowfall 86-91%). Others are not: **Fists of Avalon is forged into 56
cells and is on at most 11.5% of the rosters in any of them; it has
zero prevalence in 16 of the 60 evidenced cells** (mid-bucket meta prior
0.05, none at large). Its sheet carries fifteen nonzero capabilities
(purge 4, engage 4, mobility 4, sustained_dps 4, burst_aoe 4, peel 3, and
nine more at 2) - a breadth pick the marginal scorer loves and the
harvest does not. Same shape, smaller: Crystal Reaper (never fielded in
9 cells), Weeping Repeater (8), Great Holy (8), Carrioncaller (8),
Kingmaker (7), Grailseeker (6). E-first review of those sheets against
the dumps (the magnitude queue in BACKLOG) is the standing route; a
"breadth over depth" mechanism question is the owner's.

Evidence grades over the 60 cells with harvest evidence (killer parties
of the same size +-2 and the same identity label, holdout slice where it
held 40+ rosters):

- forged slots winners never field in that cell: 90 of 826 (11%); rare
  (under 2% of rosters): 66 (8%). By style: clap 1%, balanced 2%, kite
  10%, clap_kite 10%, brawl 15%, brawl_clap 34%.
- median share of forged weapon pairs ever seen together: 40%.
- median nearest harvested roster (multiset Jaccard): 0.33 - the closest
  real comp shares about half its members with the forged one.

### 3. Catch is over-stacked in 27 of 72 cells

`catch` sits past its soft cap in 27 rank-0 rosters (clump_create in 12,
root 6). At blackzone 20 clap the roster carries catch 29.5 against a
soft cap of 27.6 - Grailseeker 10, Polehammer 8, Hand of Justice 4 -
while `damage_debuff` (8 cells), `anti_dive` (6), `tankiness` (5) and
`root` (5) are the rows most often under the bare minimum. The
over-stack asymptote (`overstack_max` 0.5) lets a catch tank keep paying
for itself through engage / root / clump on the same E. Descriptive; the
owner decides whether "four catch tanks in a clap" is a comp they would
call.

### 4. Twenty-five is the scorer's comp, not the harvest's

Killer parties are capped at 20, so 21+ has no harvest row, no typical
count and no healer cap under a declared style (`role_min_per_players`
gives 5 healers per 25 as a MINIMUM with no cap). Result across every
25 cell: 6-7 healers of 25 on brawl / kite / clap (balanced, which keeps
the base band, fields 5), 2 supports, 5 frontline. The BACKLOG item
("castle 25 still forges 6 healers on clap") now reads: 6 on clap, 7 on
brawl and kite, at both 25-man contents. Only a 21+ harvest band or an
owner cap closes it.

### 5. The refresh alternative outscores the button in 25 of 72 cells

`forge(avoid=)` is meant to return the NEXT-best roster. In 25 cells the
first or second alternative scores HIGHER than the roster the button
returned (median gap 0.15% of comp_score, max 0.62% at blackzone 10
brawl, four slots apart). Probed at blackzone 20 clap: the better roster
differs by one weapon (Heavy Crossbow for Great Fire Staff) plus one
other member's combo; the single swap alone scores LOWER, so 1-opt
cannot see it and the bounded 2-opt (worst 4 slots x top 12 candidates)
did not reach it. The beam search returns a local optimum; the avoided
run starts from a different beam and lands on a better one. Engineering,
not a ruling: a closing pass that re-resolves every generated slot's
combo and kit under the FINAL roster, or a wider 2-opt, would close most
of it; both ports must move together (parity). Cheap to test with the
sweep.

Refresh diversity: 81 of 144 alternatives differ from the first roster by
exactly one slot, 37 by two (the walk-one-swap-at-a-time note in BACKLOG,
measured).

## What to do with this

- The owner grades `tests/forge_grading_2026-09-12.md` blind (the form
  shows names only), then the disagreements become rulings, overrides or
  golden pins the same day - the method in `tests/VALIDATION.md`.
- Items 1, 3 and 4 are owner rulings (BACKLOG, "Needs an owner ruling").
  Item 2 routes through the magnitude review queue that already exists.
  Item 5 is unblocked engineering (BACKLOG).
- Re-run `py -3 pipeline/audit_forge_quality.py` after any forge, template
  or sheet change and diff the summary board; it is deterministic.
