# The Engine

The scoring core of Comp Forge, in two parity-locked ports:

- `engine.py` — the canonical implementation. Every scoring decision is
  authored here first.
- `app_scoring.js` — the browser twin, inlined into the generated dashboard
  by `dashboard/build.py`. **Change one, change both**, then rerun
  `py -3 tests/test_js_parity.py` (60 random parties, 1e-9 tolerance, plus a
  check that the built pages embed this exact source).

## Boundary

- **Consumes** exactly one input: `pipeline/out/dataset-latest.json`, built by
  the engine domain's data layer (`pipeline/` — sheets, templates,
  MASTERSHEET overrides, provenance gates). No other file feeds scoring.
- **Exposes** `CompEngine` (recommend / fitness / weaknesses / explain /
  swapReview / forge / refine) plus the parity-locked DESCRIPTIVE family
  (comp_identity / kill_pressure / fight_chain / pick_report / analyze /
  duplicate_conflicts / detect_role / role_advisory) and the kit advisor
  (kit_options, doctrine read through `_seat_kit`). The frontend calls
  this API and translates its output; it never computes a score of its own.
- **Validation affordances** (both ports, parity-pinned):
  `set_dressing(false)` makes every CANDIDATE evaluate naked through the
  identity short-circuit into the naked scorer — the V3-W symmetric
  weapon-only mode; same formula, no second scoring path; default is
  dressed and nothing in the product turns it off. Python-only:
  `BION_DATASET` overrides the default dataset PATH so the fold comparison
  can point test suites at another dataset copy — path plumbing, never set
  in production or normal test runs.
- **Synergy is weapon-interaction synergy**: `synergy()` deliberately prices
  weapons only — worn-gear capabilities count in fitness, never in the pair
  bonuses (finding: `notes/findings/2026-08-27-gear-synergy-finding.md`).
- **Structural floors are source-aware** (Option C, standing rule 10): hard
  floors read the weapon+loadout supply in `fitness` and every marginal
  path — worn gear improves coverage/headroom/overstack, never floor relief,
  on parties AND candidates alike.
- **Locked gear is sacred**: `forge(locked_gears=)` scores a locked member in
  exactly the supplied kit and never re-dresses it (naked when none —
  nothing is invented); `refine(gears=)` runs the dressed local search and
  returns `{party, gears}` (gears=None keeps the legacy weapon-only list).
- **A combo is the larger, never the sum**: `_merge_max` (JS `mergeMax`)
  merges one weapon's or gear item's always-on capabilities with its chosen
  bundles by the maximum per capability — the build credits every sheet
  row to its own spell, and a sheet score is the item's total with that
  spell equipped. Different items and different members add. A
  non-stacking spell's count-once share is what it adds over the member's
  other sources (F43).
- **A near-tie keeps the earlier build**: a candidate's builds (combo x kit
  variant) whose pick values differ by less than `PICK_TIE_EPS` (1e-9, the
  parity tolerance) tie, and the earlier build in search order keeps it.
  Several combos of one weapon often merge to the same capabilities, and a
  last-bit float difference between the ports must not choose the combo.
- **Inputs read alike in both ports**: `combos` / `gears` are parallel to the
  party, and a list shorter than the party reads None past its end (the
  default combo, a naked member; F38). `pool=None` reads the default pool;
  a given list, empty included, is the candidate set as given, in every
  entry point that takes one (F37).
- **The count-once rule reads what is worn**: a verified non-stacking
  spell's capability keeps its largest single contribution, a dressed
  member's taken as worn (the kit's stat channel multiplies the spell's
  units with the rest of the member's damage); synergy and the floor basis
  keep the weapon-only shares (F39, F40).
- **The why text is the scored rows**: `explain()` is the gap-closing half
  of `pick_report()`'s rows, kit included (T54); `fight_chain` reads the
  identity and the explain terms on the same gears (T26d).
- **swapReview reads weapon choice and reports the build**: `score`, `rank`
  and each option's `gain` value weapons at their best builds into the
  rest (T17); `built_score`, `build_gap` and each option's `delta` (with its
  `combo` and `kit`) are the member as built and the exact comp-score
  change of the swap (F41), `built_score` priced as a marginal on the rest's
  state (`_as_built`, F41b).
- **The kit advisor reads the rest as equipped**: comp-aware `kit_options`
  takes the rest's combos and kits (`party_combos`, `party_gears`; F42) and
  dresses that rest once per waived set (`fitness(memo=)`; an item that
  completes a self-cost offset dresses it once more), every item's value
  the exact fitness delta.
- **Never** reads UI state, killboard/usage evidence, or reference builds —
  those are display-only layers by standing rule (popularity is not
  effectiveness).

Score semantics live in `MASTERSHEET.md` (the tuning control surface — its
`tune:` blocks override the underlying config at build time) and the design
doc. Forge STRUCTURE (role bands, need profiles, style bands) is curated or
generated data in `pipeline/roles.yaml` + `pipeline/templates/` — shipped
inside the dataset, generation-only, never a bar to scoring a manual party.
Regression truth lives in `tests/test_golden.py`, `tests/test_forge.py` and
`tests/test_roles.py`.
