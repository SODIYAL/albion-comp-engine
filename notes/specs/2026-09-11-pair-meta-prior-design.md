# Pair-aware meta prior — design

Date: 2026-09-11. Status: DRAFT, owner-approved in conversation (ruling A of
three offered; vote unit "one party, gated by orgs"; holdout "training
split only"). Owner ruling this implements: observed weapon PAIRINGS from
the killer-party harvest may enter scoring, through the harvest-generated
meta prior only (the 0.15 `delta` slot), tiebreak-sized, never through the
synergy term, a floor, a role slot or a suggestion pool.

## Problem (owner's words)

> wouldnt it be cool to add synergy to comps based on what weapons are
> often seen playing together with real data ?

Today the harvest reaches scoring only per WEAPON: `derive_meta_prior.py`
counts distinct players per weapon per size bucket and the engine adds
`delta * prior_w` per member. Which weapons winning parties field
TOGETHER is mined (`build_cohort_families.py`, the "recurring observed
cores" and "observed rosters most like yours" panels) but display-only,
by standing rule 7 ("popularity is not effectiveness") and
`KILLBOARD_AFFINITY.md` "still parked behind review". A throwaway probe
on the committed artifact (2026-09-11) shows the pairing signal is real
and mechanistic — the top small-fight pair is Arcane + Brimstone (24x
over chance across 18 guilds), then Bow of Badon + Locus (15x, 40 guilds):
the interactions the engine already prices from spell facts.

## Decisions

1. **Where**: inside the meta prior. `scoring.meta_prior` (solo, as today)
   gains a sibling `scoring.meta_pairs`. The `delta = 0.15` weight, the
   size-bucket axis and the "top = 1.0, never a penalty" semantics are
   unchanged. The synergy term (`beta`, verified interaction records only)
   is untouched. Standing rule 7 is amended, not repealed: cohort
   families, reference builds and the killboard panels stay display-only;
   the ONE empirical scoring input is the harvest-generated prior, solo and
   pair.
2. **Source**: `out/party_rosters.json` `parties[]` (the killer's party at
   kill time from the official API's `GroupMembers`, overlap-deduplicated
   per battle, with `guilds` and the full known `weapons` list). NOT the
   albionbb cohort channel the panels use (partial baskets, mount-carrier
   bias, not party membership).
3. **Vote unit**: one party, one vote per distinct pair it fields
   (duplicates within a party collapse to the set; a weapon never pairs
   with itself). Honesty gate mirroring cohort families: a pair carries a
   row only with >= 5 parties AND >= 3 distinct guild-sets in its bucket.
4. **Holdout**: the shipped artifact is derived from battles with
   `battle % 5 != 0` ONLY — BOTH tables, solo and pair, so
   `tier2_blindtest v4h` (holdout `% 5 == 0`) is out-of-sample for the
   whole prior term. `--all-battles` exists for audits and never ships
   (the artifact records its split; build_dataset refuses an all-battles
   artifact).
5. **Pair score** (per bucket, symmetric):
   `lift = n_ab * N / (n_a * n_b)`;
   `s = clamp(log2(lift), 0, LOG_CAP) / LOG_CAP * n_ab / (n_ab + K)`;
   `LOG_CAP = 3` (8x over chance saturates), `K = 8` parties (the solo
   prior's shrinkage constant; both PROVISIONAL, recorded in the artifact).
   Rows with `s < MIN_PRIOR` (0.05) are omitted. Anti-affinity (lift < 1)
   is 0 — absence is not evidence, never a penalty.
6. **Blend** (engine, per member w of party P at the roster's bucket):
   `pair(w, P) = max over m in P, m != w (by seat) of s[bucket][w][m]`,
   0 with no partner row;
   `meta(w, P) = 0.5 * solo(w) + 0.5 * pair(w, P)`.
   Always the blend, also for a roster of one (pair = 0): continuous, the
   first-pick RANKING is exactly today's, the magnitude halves. `max`, not
   mean: a member is credited for its best observed partner, which the
   why-panel can name. Both inputs in [0, 1] so `delta` remains the cap.
7. **Exact marginal**: `comp_score` sums `meta(w, P)` over the party; a
   candidate's pick score stays the exact `comp_score` delta (test_forge
   F1): `0.5 * solo(c) + 0.5 * pair(c, P) + 0.5 * sum over m in P of
   max(0, s[c][m] - pair(m, P))`. `party_state` carries the party and each
   member's current pair max so `_pick_tail` computes this in O(|P|).
8. **Explanation**: the pick record gains `meta_solo`, `meta_pair`,
   `meta_partner` (the arg-max partner weapon or null) beside `meta_prior`.
   The why-panel renders one translation line when a partner exists; the
   formula line's `metaPrior` prose is updated. No math in the UI.
9. **Not in scope**: pool ordering, forge objective, style bands / role
   counts holdout (BACKLOG follow-up), win-lift, the cohort panels.

## Components

- `pipeline/derive_meta_prior.py` — `derive(doc, holdout_mod=5, ...)`
  returns `meta_prior` (solo, players) AND `meta_pairs`, `pairs_n`
  (support per pair) and `_split`; `--all-battles` flag. `bucket_of`
  unchanged (golden T46 pins it).
- `pipeline/build_dataset.py` `load_meta_prior` — also validates
  `meta_pairs` (bucketed, symmetric, values in (0, 1], both weapons known,
  `_split.holdout_mod == 5`) and attaches `scoring.meta_pairs`. Fail
  closed on any drift.
- `engine/engine.py` — `meta_of(weapon, party=None)` (solo+pair blend),
  `_pair_of(weapon, party, skip_index)`, `party_state` gains `party` and
  `pair_max`, `comp_score` / `_pick_tail` / `_forge_eval_pick` read them,
  `recommend` / `pick_report` expose `meta_solo` / `meta_pair` /
  `meta_partner`.
- `engine/app_scoring.js` — the same, line for line (`metaOf`, `pairOf`,
  `partyState`, `compScore`, `_pickTail`).
- `dashboard/_app.js` — carry the three fields through `recommend()`;
  one translation line in the why-panel; updated prose.
- Docs: `tests/VALIDATION.md` rule 7 + ruling row, `notes/validation/`
  dated entry, `KILLBOARD_AFFINITY.md` "still parked" paragraph,
  `HANDOFF.md` engine section, `pipeline/README.md` derive docstring
  reference, `BACKLOG.md` (style_bands/role_counts holdout follow-up;
  re-derive on the harvest checkout).

## Data flow

party_rosters.json (committed harvest) -> derive_meta_prior.py (training
split) -> out/meta_prior.json {meta_prior, meta_pairs} -> build_dataset.py
(hash + split gated) -> dataset-latest.json scoring.{meta_prior,
meta_pairs} -> engine meta_of(w, party) -> comp_score / pick score ->
dashboard translation.

## Testing

- `tests/test_meta_pairs.py` (new, script-style): derivation contracts on
  a synthetic doc — holdout split honoured, org gate, party-set votes, no
  self-pair, symmetry, clamp/shrink arithmetic on a hand-computed case,
  anti-pair omitted, `_split` recorded; blend contracts on a stub engine
  — empty/one-member roster = 0.5 solo, max partner, self-seat excluded,
  value <= 1, pick delta == comp_score delta with pair terms.
- `tests/test_forge.py` F1 pick-score invariant — must hold unchanged.
- `tests/test_js_parity.py` — the 60 random parties cover the new path;
  `meta_prior` field parity at 1e-9 plus the three new fields.
- `tests/test_golden.py` — every case whose ranking moves is listed for
  the owner; none re-pinned silently (anti-circularity).
- `tests/tier2_blindtest.py v4` — gate >= 70% must hold; `v4h --rebuild 5`
  reported before/after (report-only).
- `tests/test_provenance.py` / byte-identical rebuild — artifact written
  with `newline="\n"` via `jsonfmt`.
- `tests/test_dashboard_layout.py` — no engine calls from the UI.

## Error handling

Fail closed, loudly: missing artifact, hash drift, an all-battles
artifact, a non-bucketed / asymmetric / out-of-range pair map, or an
unknown weapon in a pair all `sys.exit` the build. A weapon or pair with
no row reads 0 in the engine (neutral). No network step.
