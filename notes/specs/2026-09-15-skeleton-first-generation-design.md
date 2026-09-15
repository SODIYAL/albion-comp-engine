# Skeleton-first generation — design (2026-09-15)

Status: implemented 2026-09-15 (working tree, not yet committed; plan
`notes/plans/2026-09-15-skeleton-first-generation.md`). Deviations from
the draft: the seat read is the first UNIFORMED menu role (the role-class
read), not `role_menu[0]` — a function-role primary (purge, pierce) would
otherwise sit a support seat in a dps body; the minimum exception admits
cross-role minima too but never a minimum an under-typical seat of the
same role could meet (brawl 20 died two short and Great Holy took the
brawl-healer seat before both refinements); a whole-roster invariant
guards refinement (a swap un-justified a spill); a present-but-empty
typical row means "fields none, no demand" and only an absent row falls
back to the pooled cell; decision 7 (plan tools) was added after the seat
gate alone left the forged kite reading as a clap. Golden rows moved: none
(75/75). Forge pins re-based: F4, F18 (the hand allowances). Decision
implemented: act in full on the assessment of the same day (the forge
fields 20 distinct weapons in 20 seats where 20-man winners field a median
16; four of six style forges read `clap` to the engine's own identity; the
forged kite shares 7 of 20 weapons with the real kite 20 and 14 with the
forged clap; every empirical input is prevalence).

## Problem

One scalar objective both generates and ranks. It is indifferent to two
things real comps are made of:

1. **The skeleton.** Real rosters have a seat shape — how many engage
   tanks, stoppers, main healers, shield supports, ranged-AoE bodies — that
   differs by style. The forge constrained only the coarse role classes
   (healer / frontline / support) with a typical count, so every style
   forged the same seat mix with different weights on top: kite 20 forged
   three engage tanks and read as a strong clap.
2. **Copies.** Which weapons winners stack is a per-weapon fact the
   harvest measures (Hallowfall is doubled in 87% of the 20-man winners
   that field it; Bedrock in 66%; Permafrost in 24%; Great Arcane in 9%),
   yet the allowance table was hand-kept from single comps and adjusted
   one weapon at a time (Permafrost `free: 2` removed 2026-09-15).

## Decisions

1. **Seat typicals, GENERATED.** `pipeline/derive_skeletons.py` reads the
   committed harvest (`out/party_rosters.json.gz`, labels from
   `out/party_styles.json`) on the TRAINING split (`battle % 5 != 0`, the
   meta prior's rule) and writes `out/skeletons.json`: per exact size at
   10+, pooled and per declared style, the p10 / p50 / p90 count of every
   PRIMARY SEAT (`Engine.seat_of`: the weapon's `role_menu[0]` — the one
   role read, never a second classification), over DISTINCT rosters
   (guild set + weapon multiset), a cell pooling a ±1 then ±2 size window
   until it holds 40 rosters (the role-count convention). `typical` =
   round(p50) where p50 ≥ 1. Below 10 no seat row exists (killer parties
   below 10 are open-world squads — rule 18); sizes the harvest does not
   reach carry none. Unknown stays explicit.
2. **The forge honours seat typicals the way it honours role typicals**
   (standing rule 18 extended): a body beyond its SEAT's typical count is
   generated only when (a) a minimum only that role can meet still demands
   it and this pick meets it (the existing exclusive-minimum rule —
   minima always win), or (b) SPILL: every seat of that role present in
   the pool already stands at or above its typical, and the role itself is
   still under its own cap. Spill is what keeps every size feasible: seat
   medians do not add up to the role's typical, and dps has no role
   typical at all (rule 18: dps is the residual) so once its typed seats
   are full any dps seat may be added. A seat absent from a cell that
   exists reads typical 0 (most winners field none) and opens only by
   spill; when NO cell exists for the size the seat gate is off entirely.
   The deadlock guard stays optimistic about seats (it never refuses on a
   seat typical) so the admissible minimum-need bound is untouched.
   Generation only: manual rosters always score. Both ports, parity.
3. **Copy allowances, GENERATED.** The same artifact carries, per style ×
   band (10-14 / 15-19 / 20+) and pooled, for every weapon fielded in at
   least 40 distinct rosters of the cell: rosters fielding it, copies p50
   / p90, the share with 2+ and 3+ copies, and the derived allowance
   `free = round-half-up(p50)`, `max = ceil(p90)` (never below `free`).
   `build_dataset.py` attaches it as
   `composition.duplication.per_weapon_cells` and REFUSES a hand-set
   `duplication.per_weapon` in `composition.yaml` (the meta-prior
   precedent, 2026-09-08). The engine resolves the cell for its declared
   style and band at `set_content` into the same `{weapon: {free, max}}`
   shape `_dup_free` / `_dup_gen_max` already read; `per_weapon_min_size`
   (10) and every default are unchanged. The 2026-09-15 Permafrost
   decision (one copy) is reproduced by the evidence (p50 1 copy),
   Hallowfall keeps its free second copy, Great Arcane / Rift Glaive /
   Wailing Bow lose the single-comp allowances the harvest does not
   support at 20.
4. **Nothing forces copies.** The concave utility curve's preference for a
   distinct weapon over a second copy stands: the 2026-08-24 and
   2026-09-15 decisions prefer distinct bombs over stacked ones (curation
   judgment), and rule 7 keeps the harvest out of the objective beyond the
   tiebreak-sized prior. The allowance table only decides where a copy is
   penalty-free.
5. **The holdout split is honoured by every derivation that can honour it
   here.** `derive_role_counts.py` learns from the training split (was:
   every battle) and records `_split`; `build_dataset.py` refuses a
   role-count artifact without one. `audit_style_rosters.py` gains the
   same `--holdout-mod` (default 5) and records `_split`, and
   `derive_style_bands.py` carries it into the yaml header — but the
   committed board was generated before this change on the harvest
   machine (the raw cache is not on this machine), so the shipped style
   rows stay weak-form until the next fold and the build says so.
6. **A baseline to beat.** `tests/tier2_blindtest.py v4 --baseline` and
   `v4h --baseline` score a role-skeleton-plus-popularity recommender
   through the same leave-one-out metrics: candidates ranked by need (the
   role under its band minimum first, then under its typical) and then by
   the meta prior's solo share, top-3. Report-only, printed beside the
   engine; the capability model must beat it or it is not earning its
   complexity.
7. **Plan tools as generation minima.** The identity read defines a
   kiting plan by its STANDOFF tools (`style_fit.standoff_e`: Bedrock,
   Grailseeker, Icicle, Hoarfrost, Arctic, Brimstone ... eleven weapons),
   yet the forge asked for a kite ignored its own definition — the forged
   kite 20 carried one and read as a strong clap. The skeleton artifact
   gains a `plan` table: per style x size, the same windowed typical of
   standoff carriers winners field (kite and clap_kite at 15+: two or
   three in every roster; brawl and clap: none). The engine carries a
   combo-independent flag predicate `standoff` beside `primary_heal` and
   lays the declared style's typical onto the band as a MINIMUM, so every
   existing minimum machinery (admissible need bound, deadlock guard,
   feasibility) enforces it. A style whose winners field none demands
   nothing. Circularity, stated: the labeller requires two standoff tools
   for a kite label at 15+, so the p50 of two is the labeller's own
   threshold; the harvest adds the p90 (three) and the 10-14 nuance (one).
   The requirement makes the forge's output satisfy the definition the
   engine judges it by; it invents no number.

## Rule precedence (the layering the assessment asked for)

Skeleton rules (seat and role typicals, minima, groups, viability) refuse
a body; plan requirements (need profiles, predicates) demand one;
preferences (the scalar objective: coverage, synergy, prior, rho) rank
among what survives. A preference can never open a seat the skeleton
closed; a minimum can. This is already the engine's order for roles and
is now stated and extended to seats.

## Data shapes

`out/skeletons.json`:

```
_source: {party_rosters_sha256, party_styles_sha256}
_split: {holdout_mod: 5, rule: "battle % 5 != 0 ..."}
_unit, _seat_read, _min_distinct: 40, _style_min_size: 10
bands: {"10-14": [10, 14], "15-19": [15, 19], "20": [20, 99]}
seats:
  cells:   {pooled: {size: {n, window, <seat>: {p10,p50,p90}}}, styles: {style: {size: {...}}}}
  typical: {pooled: {size: {seat: n}}, styles: {style: {size: {seat: n}}}}
copies:
  pooled: {band: {weapon: {n, p50, p90, share2, share3, free, max}}}
  styles: {style: {band: {weapon: {...}}}}
distinct: {pooled: {band: {n, p10, p50, p90}}, styles: {style: {band: {...}}}}
```

Dataset: `composition.skeleton = {style_min_size, seats: typical}`,
`composition.duplication.per_weapon_cells = {bands, pooled, styles}` with
`per_weapon` emptied; `composition.seat_of` is not stored — the engine
reads `role_menu[0]`.

## Engine changes (both ports)

- `seat_of(weapon)`; `_seat_typical()` resolves the cell like
  `_role_typical` (declared identity style's cell at 10+, else pooled;
  `balanced` never reads a style cell); `_dup_cell()` resolves the copy
  cell by style and band into `dup_per_weapon`.
- `_forge_counts` counts each member's primary seat under `seat:<id>` in
  the predicate map (no collision with predicate names; the need-profile
  seat predicates keep their own keys).
- `_forge_ctx` carries `seat_typ` (the cell), `seat_gate` (cell exists)
  and `role_seats` (seats of pool weapons per role).
- `_typ_ok` gains the seat branch after the role branch (decision 2).

## Tests

New gate `tests/test_skeletons.py`: artifact contracts (hash chain, split,
positive integer typicals, `free ≤ max`, `free = round(p50)`), engine
resolution (style cell vs pooled vs none), forge contracts (no seat past
its typical without spill or a minimum; spill fills a role whose typed
seats sum below its minimum; every style × size 10–20 forges a full
feasible roster), the refused hand allowance, and the copy resolution.
Existing pins that encode the hand allowances (F18) move to the generated
values with the reason. Parity on the forge cases. Golden rows that move
are re-pinned only where this decision explains the move.

## Deferred, with reasons

- Fill order (healer → frontline → support → dps as the beam's sequence):
  changes many pinned first picks; ordering-only, needs a maintainer
  decision.
- Outcome layer (win-lift from per-player kills/deaths): the raw cache is
  on the harvest machine, not this one; the derivation is specified
  in BACKLOG and must be built where it can be run.
- Opposition blocks per content, small-scale templates (hellgate,
  crystal, mists): every number would be invented — rule 3.
- Independent style labeller: ~50 caller-labelled rosters cannot beat a
  classifier tuned on them; needs a labelled holdout first.
- Spec / item-power inputs: BACKLOG item 8's five open questions.
