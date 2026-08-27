# Dressed Validation Report

**Date:** 2026-08-27 · **Scope:** Phases 1–2 of the dressed-validation & calibration hardening pass (work order of the same date; plan `docs/superpowers/plans/2026-08-27-dressed-validation-calibration.md`).

Machine artifacts: `pipeline/out/validation_asymmetry_probe.json`, the `--json` dumps of `tests/tier2_blindtest.py v4`, `pipeline/out/dressed_template_audit.json`, `pipeline/out/frontline_floor_audit.json`, `pipeline/out/gear_synergy_audit.json`, `pipeline/out/calibration_report.json`.

## 1. The audit (Phase 1A) — what V3/V4 actually measured

Both harness modes called `e.recommend(party, 3)` with weapon keys only. Since the dressed forge (2026-08-27), that call prices **naked incumbents against doctrine-dressed candidates**:

- `party_state` takes the weapon-only fast path when no gears are passed (engine.py ~1592);
- `_eval_pick` unconditionally dresses every candidate through `kit_variants` (engine.py ~1817);
- golden T30c's honesty rider had already pinned the per-candidate effect (a 5th Longbow's kit closes >5 units against a naked four-stack).

So the historical V3 rounds and every V4 number were an **asymmetric hybrid**: neither a weapon-model benchmark nor production behavior. Production (the page) passes `GEARS_CUR` into every scoring and suggestion call.

**Ruling recorded:** all pre-2026-08-27 V3/V4 numbers are re-labeled *"weapon-only-incumbent benchmark with dressed candidates."* They are not production accuracy.

## 2. The fix — explicit validation modes (Phases 1B/1C/1D, 2A/2B)

- **`Engine.set_dressing(False)`** (both ports, parity case at 1e-9, contract tests `tests/test_validation_modes.py` V1a–V1d): candidates evaluate naked through the identity short-circuit into the authoritative naked scorer — one formula, no second path. Default is dressed; nothing in the product turns it off.
- **V3-W** (`score --mode w`): symmetric weapon-only — incumbents naked AND candidates naked. The weapon/capability-model benchmark.
- **V3-D** (`score --mode d`, in the default `both` run): incumbents in recorded gear (`GEAR_KEYS`) else doctrine kits (`kit_variants` v0) else honestly naked, per-member source recorded; candidates dressed as in production. **The 70% gate now applies to V3-D.**
- **Richer blind form** (backward-compatible parser): PRIMARY NEED / BEST PICK / OTHER GOOD PICKS / BAD PICK / CONFIDENCE / REASON (+ optional GEAR_KEYS). Seed-20260812 party generation is byte-identical to the committed round-1 form.
- **Metric set** (never collapsed to one number): top-1, top-3, acceptable-top-3, mean/median expert-pick rank (+outside-pool count), primary-need agreement (alias table, PROVISIONAL), explicit-bad-pick rate, confidence-weighted top-3 (High 1.0 / Med 0.6 / Low 0.3, PROVISIONAL).
- **V4** reports three incumbent-gear classes — `weapon_only` (legacy; still the exit-code gate pending an owner ruling), `doctrine_inferred` (labeled inferred; doubly weak-form since the doctrine pools were mined from these same comps), `actual_gear` (kits joined from `builds_index` — published comps record gear on all 201 slots; the join is `comp:party:slot_index`, normalization conservative, unresolved pieces counted and never guessed).

## 3. Results

### V4 leave-one-out (92 slots, 4 comps, top-3)

| incumbent gear | weapon-level | role-level (n=32) |
|---|---|---|
| weapon_only (legacy gate) | 13/92 = 14% | **25/32 = 78% PASS** |
| doctrine_inferred | 6/92 = 7% | **11/32 = 34%** |
| actual_gear | 10/92 = 11% | **13/32 = 41%** |

- **92/92 slots change their top-3** when incumbents dress. The asymmetry is total, not marginal.
- Gear resolution (actual_gear class): all 92 members dressed; 387/485 recorded pieces resolved into the curated catalog (per-party counts printed by the runner; unresolved = uncurated or unmatched nicknames, left off honestly).
- **12/32 role hits are LOST when incumbents dress, 0 gained** — and 11 of the 12 are tank/main_tank drops (blap and Deadlyhooker tanks; bist healers hold). Mechanism: worn-armor tankiness fills the dropped tank's hole, so the top-3 becomes scarce-cap utility (Spirithunter, Black Monk, Fists of Avalon) instead of a frontline weapon. Full decomposition and options: `2026-08-27-tankiness-frontline-finding.md`.

### V3 seed parties (12 blind-form cases)

- 9/12 top-3s change when incumbents dress (doctrine kits); 12/12 differ between the legacy hybrid and symmetric V3-W.
- No filled expert form exists as a file (round 1 was in-chat); the 4 documented named-weapon answers are seeded into `calibration/cases.yaml` as train data. Under the dressed regime only 1/4 of those historical answers lands top-3 (mean rank ~28) — weak-form (n=4, one expert, answers given under legacy conditions), recorded for the next expert round to re-measure properly.

### Changed-recommendation examples (from the probe artifact)

- bist roam15, drop the 1H Mace tank: naked top-3 *Camlann, Rootbound, Witchwork* → actual-gear top-3 *Earthrune, Camlann, Hand of Justice* (still frontline-shaped — bist's healer demand survives dressing).
- blap, drop Staff of Balance (tank): dressed top-3 becomes *Fists of Avalon, Spiked Gauntlets, Hoarfrost* — no frontline weapon (the tankiness-saturation case).
- Deadlyhooker party_1, drop Hallowfall (healer): dressed top-3 *Spirithunter, Black Monk, Rampant* — only one healer-class pick survives.

## 4. Classification of the disagreement (work-order rule 1)

The 78%→34–41% collapse decomposes into:

1. **Representation problem (category 1), primary:** worn-armor stats pour into the same `tankiness` currency the frontline demand reads — measured at +419–622% of target across all templates, floors clearable by gear alone in adversarial no-tank parties. → tankiness/frontline finding, Options A–D, owner ruling required.
2. **Validation-metric meaning (category 2), secondary:** at dressed saturation, leave-one-out at full size tests "best generic body" rather than "replace what was lost" — the saturation-degeneracy caveat from 2026-08-13, amplified by gear. The dressed sections inherit it; a future V4b (reconstruct the last ~5 slots) remains the cleaner instrument.
3. **Genuine calibration (category 5), deferred:** template targets/soft caps were comp-fitted in weapon-loadout units and predate dressed supply (and the 129-piece catalog). No number moved; waits for expert rounds under the calibration discipline.

**No coefficient, target, floor, weight, or score was changed anywhere in this pass.** The full existing battery is green and byte-stable on the legacy metrics (57/57 golden, 35/35 forge, 18/18 roles, 32/32 interactions, 60/60 parity + embed, tier2 legacy 78% PASS).

## 5. Owner rulings needed (validation layer)

1. **Gate re-basing:** keep the exit-code gate on legacy weapon_only role-level (status quo), or re-base to `actual_gear` role-level once the tankiness ruling lands? (Recommendation: rule on tankiness first — it is the dominant term in the dressed collapse; re-basing before it would freeze a known representation bug into the gate.)
2. **V3 next round:** run a fresh-seed round on the new richer form, scored V3-D (production) with V3-W beside it — this creates the first uncontaminated validation/holdout cases (calibration/README.md).
3. Two adjacent engine gaps found during the audit, reported not fixed: `forge()` hard-codes locked members naked (F23 pins it — the spec's "evaluated in the kits they actually have equipped" is not yet true for forge locks), and standalone `refine()` is gear-blind. Both need a ruling on intended behavior before any change.
