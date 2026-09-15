# Dressed Forge — design (2026-08-27)

**Status:** implemented 2026-08-27 (plan `notes/plans/2026-08-27-dressed-forge.md`; HANDOFF.md "the DRESSED FORGE shipped", `engine/README.md`, forge pins F25/F26).
**Decisions embedded:** doctrine kit + variants (not single-kit, not full kit search); evaluation unit only (fill order, need profiles, style bands untouched); the evidence-first kit doctrine (T22, 2026-08-27) is the variant source.

## Problem

The forge (and every suggestion path) evaluated naked weapons while the
loaded comp displayed a full-build score. The forge must evaluate DRESSED
candidates — weapon + combo + doctrine kit — so generation optimizes the
same full-build score the loaded comp displays, and kit choices with
comp-conditional value (Cleric vs Druid Cowl; shield vs Leering Cane)
become searchable. This is the "comp-builder, not weapon picker" increment;
it builds directly on the 2026-08-27 gear combat expansion (129 curated
pieces) and the doctrine-tier-first kit rule.

## Decisions

### The dressed-candidate model

A forge/recommend candidate becomes `(weapon, best-combo, kit-variant)`:

- **Variant 0 (always):** the seat's doctrine kit — the top doctrine
  pick per slot exactly as `kit_options` ranks it (uniform-gated
  chest, doctrine-tier-first, exact marginal within tier).
- **Variants 1–2 (only where the doctrine tier genuinely diverges):**
  alternative kits swapping the slot(s) where the tier holds pieces
  with different top capability contributions. A capability-equivalent
  tier yields no variants; most weapons stay at one dressed vector.
  Variant count hard-capped at 3 (v0 + 2).

**Invariants preserved, explicitly:**

- **Scoring truth / F1:** candidates are priced by `comp_score(party,
  combos, gears)` — the exact call the loaded comp scores with. NO
  doctrine passives in evaluation (they are generation/display-only by
  standing rule; including them would make the search optimize a number
  the UI never shows). Pick score == comp-score delta at 1e-9 extends to
  dressed picks.
- **Locked/manual members are never re-dressed:** evaluated in the kits
  they actually have equipped (naked if none).
- **Manual always scores:** kit variants shape generation only.
- **Gates untouched:** suggestion-pool gates, style bands, need
  profiles, dup allowances, cost gate, filler/held audit see the same
  weapons, dressed.

### recommend(), pick_report, swap review

`recommend()` prices each suggested weapon in its variant-best kit
against the party's actual loadouts. `pick_report` decomposition gains
the kit's capability terms (reconstruction at 1e-9 unchanged). Swap
review displays the kit each marginal assumed.

**Golden policy:** the full golden suite re-runs; ordinal flips (a top
recommendation changing) are STOPPED ON and reported as validation-round
cases for a maintainer decision — never silently absorbed into pin updates.
Purely numeric shifts within existing assertions pass as-is.

### UI

Forge results prefill each generated member's `LOADOUT` through the
central `data-add`/`data-swapat` handlers (the one-permutation rule
holds), so the displayed score is the searched score. Forged tiles show
the kit annotation (doctrine tier + variant reason). Manual gear swaps
afterward score as always. `_decision_layer` stays translation-only.

## Data shapes

- Candidate: `(weapon, combo index, variant key)` with variant keys
  `v0`, `v1`, `v2`; a menu-less weapon carries the single naked variant
  `("v0", None)`.
- `forge()` returns `gears` (variant-resolved kit per generated member;
  the caller's own gear for locked slots) plus a per-member kit
  annotation for the UI.
- `recommend()` rows carry `kit` (the variant-best gear list).

## Engine changes (both ports, parity-carried)

1. **Dressed-vector precompute** extends the hot-path tables: at
   `set_content`, for each pool weapon × combo × kit-variant, the
   `build_extra` vector (member-local, context-free) is computed once.
   The beam never calls `build_extra` inline.
2. **`party_state` + `_eval_pick` thread `gears`** so marginals price
   dressed joins exactly — one threading change shared by `forge`,
   `recommend`, and swap review.
3. **The beam carries `gears`** alongside `party`/`combos`;
   `_member_tag` gains the kit-variant id so the canonical-multiset
   dedup key cannot collapse beams differing only by a kit.
4. **`forge()` returns `gears`** (see Data shapes).
5. **Refinement (`1-opt`/`2-opt`) and the filler/held audit** evaluate
   swaps dressed with the same precomputed vectors.
6. **Variant enumeration is deterministic:** doctrine-tier order,
   lexicographic tie-breaks, no randomness; "divergent" = the tier
   piece's top weighted-capability contribution differs from variant
   0's piece in that slot.

## Tests, gates, performance

- **F-series:** F1 re-proven over dressed picks; new case pinning
  generation-only (a manually locked party scores bit-identically
  regardless of what the forge would have dressed); F5 determinism
  matrix re-run including variant enumeration.
- **Parity:** dressed-forge fixtures at 1e-9 + browser embed check.
- **Doctrine coherence:** first `test_doctrine.py` case lands here —
  forge output kits match seat doctrine (cloth-on-DPS in kite styles,
  comp-book spec, doctrine-coherence tests), report-only where floors are
  undecided.
- **Performance:** measured on the F5 matrix before/after; expected
  ~1.3× (average variant factor), 3× worst case; if size-25 forge
  regresses past ~2×, variants cap at 2. Precompute keeps
  per-evaluation cost flat.
- **Docs:** CLAUDE.md architecture blurb + HANDOFF sync.

## Sequencing

1. Thread `gears` through `party_state`/`_eval_pick`/`comp_score`
   callers (no behavior change with gears=None) — both ports + parity.
2. Variant enumeration + dressed-vector precompute (deterministic,
   tested standalone).
3. Forge beam + refinement dressed; return `gears`; F-series + parity.
4. recommend()/pick_report/swap review dressed; golden re-run; flips
   reported before any pin change (maintainer decision).
5. UI prefill + annotations; embed parity.
6. Doctrine-coherence case; performance measurement; docs sync.

## Deferred / out of scope

Seat-first fill and comp-book targets (Plan B, after ratification);
doctrine passives entering scoring (standing rule); budget-band
gates (comp-book spec, Decision 5); any scoring-weight change.
