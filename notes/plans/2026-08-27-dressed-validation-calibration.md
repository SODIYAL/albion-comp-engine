# Dressed Validation and Calibration Hardening — implementation plan (2026-08-27)

Status: implemented 2026-08-27 (all tasks). Deliverables and measured
results: `notes/findings/2026-08-27-*.md` (5 findings/reports),
`pipeline/out/*_audit*.json` + `calibration_report.json`, the reworked
`tests/tier2_blindtest.py`, `tests/test_validation_modes.py`,
`tests/gear_blindtest.py`, `pipeline/gear_join.py` + 5 audit/calibration
scripts, and the `calibration/` layer. The open decisions are listed in
VALIDATION.md's 2026-08-27 hardening entry. No coefficient, target,
floor, weight, or sheet score changed.

**Goal:** Make the validation and calibration layers correctly reflect the dressed production engine (weapon + combo + doctrine kit) — symmetric weapon-only and production-dressed validation modes, gear-aware V4, dressed template/floor/synergy audits, calibration scaffolding — before any coefficient tuning is attempted.

**Architecture:** No scoring change. One small engine affordance (candidate-dressing off-switch, both ports, parity-pinned) routed through the existing identity short-circuit so validation reuses the authoritative scoring machinery. Everything else is harness, audit-report, and calibration scaffolding built on `recommend(party, top_n, pool, combos, gears)` — which already accepts incumbent gear in both ports and which the validation harness had never used.

**Tech stack:** Python 3 (script-style tests, `py -3`), Node for the JS twin + parity runner, YAML evidence layer, JSON audit artifacts written `newline="\n"`.

**Spec:** the work order "Dressed Validation and Calibration Hardening" (12 phases / 17 execution steps). Standing project rules apply: `tests/VALIDATION.md` anti-circularity, `CLAUDE.md` invariants, the dressed-forge spec `notes/specs/2026-08-27-dressed-forge-design.md`.

## Global constraints

- **No number tuning to green a test.** alpha/beta/delta/gamma/rho, headroom, overstack, synergy bonuses, weights, targets, floors, style multipliers, gear/weapon scores, meta priors: untouched. Disagreements get classified (representation / validation / mechanical model / data / genuine calibration) — only class 5 may ever lead to tuning, and not in this pass.
- **No silent golden re-pins.** Ordinal changes are stopped on, documented old vs new, classified, and left for a maintainer decision. Baseline before the pass: 57/57 golden, 35/35 forge, 18/18 roles, 32/32 interactions, 60/60 parity, V4 role 25/32 = 78% PASS (weapon 13/92).
- **Scoring vs evidence stays separated.** Killboard/doctrine/observed layers remain display/generation-only; nothing in this plan promotes evidence into scoring.
- **Twin-engine parity.** Any engine change lands in `engine/engine.py` AND `engine/app_scoring.js` with a parity case at 1e-9. `app_scoring.js` reads as binary to grep (NUL at line ~1184) — search with `Select-String`, read with an editor.
- **Windows discipline:** `py -3`; committed-artifact writers open `newline="\n"`; never read `$LASTEXITCODE` through a pipeline; commit messages via `git commit -F` BOM-less (no commits were made in this pass).
- **Determinism:** all generated artifacts byte-stable (sorted keys / stable ordering, seeded RNG).
- Engine facts this plan builds on (verified 2026-08-27): `recommend(party, top_n=4, pool=None, combos=None, gears=None)` at engine.py:1977; naked-party fast path at party_state engine.py:1592; unconditional candidate dressing at `_eval_pick` engine.py:1817 via `kit_variants` engine.py:1026; dressed/naked identity short-circuit `_combo_score_dressed` engine.py:1794 (`dextra is wextra` → `_combo_score`); caches `_variant_cache/_dressed_cache/_dressed_pre_cache` cleared at set_content engine.py:482-489. JS mirrors: `recommend` app_scoring.js:1886, `kitVariants` :1543, `_dressedExtras` :1604, `_comboScoreDressed` :1629 (identity check :1635), constructor cache init/clear :484-489.

---

### Task 1: Phase-1A/2 audit — document V3/V4 behavior + empirical asymmetry probes — done

**Files:** create `notes/findings/2026-08-27-dressed-validation-report.md` (started here, completed in Task 12); create `pipeline/audit_validation_asymmetry.py` (probe script, report-only).

**Produces:** the audit section of required report 1; probe JSON `pipeline/out/validation_asymmetry_probe.json`.

- [x] **Step 1: Record the audit facts** (from code reading, verified):
  - V3 `score()` calls `e.recommend(party, TOP_N)` (tier2_blindtest.py:105) — incumbents naked (party_state fast path), candidates dressed (`_eval_pick` → `kit_variants`). Neither V3-W nor V3-D: an asymmetric hybrid.
  - V4 `v4()` same shape at tier2_blindtest.py:197; it iterates 4 of 13 published comps (92 slots) and **ignores the `gear:` blocks present on all 201 slots**.
  - The golden suite itself documents the distortion: T30c honesty rider (test_golden.py:818) — a 5th Longbow's kit alone closes >5 units against a naked four-stack.
  - Decision recorded: the V3/V4 numbers of the time are a **weapon-only-incumbent benchmark with dressed candidates**, not production accuracy.
- [x] **Step 2: Write the probe script.** For (a) seed-20260812 V3 case parties and (b) the V4 leave-one-out slots of `timothy_blap`, run `recommend` under three regimes — legacy (naked incumbents), symmetric-naked (needs Task 2's switch; the probe runs after Task 2), dressed incumbents (doctrine v0 kits) — and emit ordinal diffs (top-3 membership changes, rank moves of the eventual production pick). Deterministic output, `newline="\n"`.
- [x] **Step 3: Run and fold the numbers into the findings doc** (completed after Tasks 2–5 landed; changed-recommendation examples are a required report ingredient).

### Task 2: candidate-dressing off-switch (both ports + parity) — the V3-W enabler — done

**Files:** modify `engine/engine.py` (~line 176 init; ~line 1026 `kit_variants`; new `set_dressing` near set_content); modify `engine/app_scoring.js` (constructor ~:49; `kitVariants` ~:1543; new `setDressing`); create `tests/test_validation_modes.py` (script-style, exit 0 = pass); modify `tests/test_js_parity.py` + `tests/js_parity_runner.js` (one new mirrored result key).

**Produces:** `Engine.set_dressing(enabled: bool)` / `CompEngine.setDressing(on)`; attribute `dress_candidates`/`dressCandidates` default `True`. With dressing off, `kit_variants(w)` returns `[("v0", None)]` for every weapon, so `_dressed_extras` aliases the weapon-only vectors and `_combo_score_dressed` short-circuits into `_combo_score` — the naked path, bit-identical formula, no second scorer. Consumed by Tasks 1, 3, 11.

- [x] **Step 1: Failing contract test** in `tests/test_validation_modes.py` — V1a dress-off: every candidate evaluates naked (`kit` empty) and the pick score equals the naked comp-score delta at 1e-9; V1b default restored: with dressing back on a doctrine weapon's kit is non-empty again; V1c the switch never leaks: a fresh engine defaults to dressed.
- [x] **Step 2: Run to verify failure** — `AttributeError: set_dressing`.
- [x] **Step 3: Implement Python.** `self.dress_candidates = True` in `__init__` (before `set_content`); `set_dressing(enabled)` sets the flag and clears `_variant_cache`, `_dressed_cache`, `_dressed_pre_cache`; first line of `kit_variants`: `if not self.dress_candidates: return [("v0", None)]` (before the cache). Docstring: validation affordance (V3-W); same formula, no second scoring path; scoring semantics with dressing ON are bit-identical to before.
- [x] **Step 4: Mirror in JS.** Constructor `this.dressCandidates = true;`; `setDressing` clearing the same caches (the JS dressed-pre cache name verified in the setContent clear block ~:484-489); guard first line of `kitVariants`.
- [x] **Step 5: Parity case.** In `test_js_parity.py` py_results add `"recommend_naked_cand"`: `set_dressing(False)` → `e.recommend(c["party"], 5, None, c["combos"], c["gears"])` rows (weapon/score/kit) → `set_dressing(True)`; mirrored in `js_parity_runner.js`; diffed with the existing recommend list pattern (EPS on score, exact weapon order, kit must be empty). Dressing is restored before the other keys compute.
- [x] **Step 6: Run** `test_validation_modes.py`, `test_js_parity.py`, `test_golden.py`, `test_forge.py` — golden/forge untouched (57/57, 35/35).

### Task 3: V3 scoring modes — V3-W (symmetric naked) and V3-D (production dressed) — done

**Files:** modify `tests/tier2_blindtest.py` (`score()`; helpers `_doctrine_gears`, mode plumbing); test `tests/test_validation_modes.py` (mode-behavior cases via importable helpers).

**Interfaces:** consumes Task 2's `set_dressing`. Produces `score --mode w|d|both` (default `both`); helper `_doctrine_gears(e, party) -> list[gear-list|None]` = `dict(e.kit_variants(w)).get("v0")` per member (doctrine source, recorded); V3-D calls `e.recommend(party, TOP_N, gears=incumbent_gears)`; V3-W calls `set_dressing(False)` + no gears. The gate (70%) applies to **V3-D** (production metric); V3-W printed as the weapon-model benchmark. Both sections labeled with their gear source per case.

- [x] Step 1: failing test — helpers importable, W-mode symmetric (candidate kits empty AND incumbents naked), D-mode dresses incumbents (`gear_source: doctrine` recorded).
- [x] Step 2: implement; the legacy single-regex path keeps working for old filled forms.
- [x] Step 3: run the new test + a smoke `score` on a synthetically-filled seed form (2 cases filled in a temp copy) verifying both sections print and the exit code keys off D.

### Task 4: V3 richer case schema + metrics (Tasks 1C/1D) — done

**Files:** modify `tests/tier2_blindtest.py` (`generate` emits the richer form; new block parser `_parse_cases(text)`; `_metrics(cases, results)`); test `tests/test_validation_modes.py`.

**Interfaces:** per-case dict `{party, gears?, need, best, good[], bad[], confidence, reason, pick_legacy}` — every field optional except party; form fields `PRIMARY NEED / BEST PICK / OTHER GOOD PICKS / BAD PICK / CONFIDENCE / REASON`, `YOUR PICK` accepted as legacy alias of BEST PICK; optional `GEAR_KEYS:` line (`;`-separated member kits, `-` = naked) so future comp-derived cases can store actual gear. Metrics emitted per mode: top1, top3, acceptable-top3 (best ∪ good), mean/median best-pick rank (rank over the full pool via `recommend(party, top_n=10**6)`; `None` = outside pool, counted separately), primary-need agreement (alias table need→cap, hit iff cap in top-3 of `e.weaknesses(party)`), bad-pick-in-top3 violation rate, confidence-weighted top3 (High 1.0 / Medium 0.6 / Low 0.3 — PROVISIONAL, documented). No single collapsed accuracy number. `--json out.json` dumps the full per-case record.

- Need-alias table (PROVISIONAL, in-file, documented): pierce→resist_shred, heal/healing/healer→heal_sustain, frontline/tank/tankiness→tankiness, anti-heal/heal cut→heal_reduction, clump→clump_create, damage/aoe damage→burst_aoe, single target→burst_st, peel→peel, engage→engage, purge→purge, mobility→mobility, catch→catch, cleanse→cleanse.

- [x] Step 1: failing parser tests (rich case, legacy case, unfilled case, GEAR_KEYS case, unresolved weapon name).
- [x] Step 2: implement parser + metrics; `generate` writes the richer form (unfilled fields legal).
- [x] Step 3: metrics unit test on a synthetic 3-case fixture with hand-computed expected values; run.

### Task 5: V4 dressed leave-one-out (Phase 2) — done

**Files:** modify `tests/tier2_blindtest.py` (`v4()`; helpers `_load_builds_index`, `_slot_gears`, `_normalize_gear_id` port); test `tests/test_validation_modes.py` (join + normalization cases against the real blap record).

**Interfaces:** consumes `pipeline/out/builds_index.json` (join key `f"{comp_id}:{party_name}:{slot_idx}"`, slot_idx over ALL slots incl. battlemounts); merge `dict(rec["raw"]) | {k:v for k,v in rec["gear"].items() if v}`; normalize ids exact-else-unique-`T4..T8_`-prefix against `dataset["gear"]` (mirror of build_dataset.py:1000 `_normalize_gear_id`); combos from rec `q`/`w` indexes where present via `e.combo_from_picks` (recorded, optional). Produces: `v4` runs three sections — `weapon_only` (legacy, the exit-code gate until the same-day re-basing, meaning unchanged), `doctrine_inferred` (incumbents in kit_variants v0), `actual_gear` (incumbents in their recorded kits; per-comp resolution stats "resolved P/Q pieces over N members"; unresolved pieces stay off the member — never silently doctrine-filled). Per-section role+weapon metrics + misses; divergence lines where the dressed top-3 differs from legacy. Caveats printed: the existing circularity note + a new one — the doctrine pools were mined from these same comp slots, so `doctrine_inferred` reproduction is doubly weak-form; `actual_gear` incumbents avoid doctrine circularity but the CANDIDATE's kit doctrine still descends from these comps.

- [x] Step 1: failing tests — join key computation, blap slot-0 gear resolves to known catalog ids, nickname slots that fail normalization are counted not guessed.
- [x] Step 2: implement; run `py -3 tests/tier2_blindtest.py v4` and `--verbose`; capture all three sections.
- [x] Step 3: STOP-AND-DOCUMENT check — the legacy section's numbers must be byte-equivalent in metric terms (a move means a regression); the two new sections' numbers recorded in the findings doc.

### Task 6: dressed template audit (Phase 3 + 3A) — done

**Files:** create `pipeline/audit_dressed_templates.py` → `pipeline/out/dressed_template_audit.json`.

**Interfaces:** consumes `data/published_comps/*.yaml` (all 13, mapped to templates where possible incl. a `_meta.content_covers`-style mapping table, non-gating), Engine `effective_supply/target/soft_cap/_floors_eff/floor_armed`, actual-gear reconstruction from Task 5's helpers — the join helpers live in `pipeline/gear_join.py` so the audit scripts and tier2 import one implementation. Produces per comp-party × capability: target, soft cap, floor (armed? units), supply under (1) weapon-only (2) weapon+resolved combos (3) dressed-actual (4) dressed-doctrine; coverage %s, gear delta, flags `gear_flips_target`, `gear_breaks_soft`, `gear_clears_floor`, `gear_delta_pct>50%` (threshold PROVISIONAL). Aggregates per template per capability (how many comps flip), with the Phase-3A watch list (tankiness, purge, cleanse, heal_reduction, resist_shred, peel, mobility, heal_sustain, heal_burst, damage_debuff) called out. Report-only; deterministic; `newline="\n"`.

- [x] Steps: write, run, spot-verify two rows by hand against engine calls in a REPL-style probe, fold the headline findings into the findings doc.

### Task 7: tankiness/frontline floor investigation (Phase 4) — done

**Files:** create `pipeline/audit_frontline_floor.py` → `pipeline/out/frontline_floor_audit.json`; create `notes/findings/2026-08-27-tankiness-frontline-finding.md`.

**Interfaces:** produces Cases A (7-man, no frontline-menu weapon, doctrine kits), B (one member → genuine engage tank), C (DPS party in explicit plate/defensive kits — hand-built gear lists from catalog plate ids). Per case: tankiness supply naked/dressed, floor armed + cleared?, floor penalty magnitude, per-member gear tankiness contributions, `role_advisory` no-engage-tank flag state, fitness deltas. The finding weighs Options A–D (single cap / split / source-aware floors / role-layer structural rule) + the Phase-11 structural-floor question (primary_heal, frontline) and recommends the smallest structural fix — **no implementation in this task**; a maintainer decision was required (taken the same day: Option C).

- [x] Steps: write the script with weapons chosen programmatically from the role book (no frontline seat in menus for case A), run, write the finding.

### Task 8: gear synergy semantics (Phase 5) — done

**Files:** create `pipeline/audit_gear_synergy.py` → `pipeline/out/gear_synergy_audit.json`; create `notes/findings/2026-08-27-gear-synergy-finding.md`.

**Interfaces:** for each pair (clump_create×burst_aoe 1.5, engage×catch 0.8, resist_shred×burst_st 0.8, heal_reduction×sustained_dps 0.8): three constructions (weapon A + weapon B; gear A + weapon B; weapon A + gear B) using real items (heal_reduction: HEAD_LEATHER_AVALON…; resist_shred/engage/catch/clump/burst from the catalog aggregate), measured `synergy()`/`comp_score` deltas, plus the labeled-hypothetical forgone bonus (the engine's own pair rule `bonus*max(0,min(a,b)-J)` computed over gear-inclusive supply — analysis only, never a scoring path). The finding recommends Model 1 vs 2 vs 3 with the measured cases; no implementation.

- [x] Steps: write, run, write the finding.

### Task 9: gear/doctrine blind-test cards (Phase 6) — done, later retired

**Files:** create `tests/gear_blindtest.py` (`generate` → `tests/gear_form.md` + hidden `tests/out/gear_form_answers.json`; `score <filled>`).

**Interfaces:** the 12 card classes from the spec (engage-tank head/shoes, stopper cape/offhand, healer offhand/potion, clap-DPS chest/shoes, brawl-DPS chest, kite-DPS shoes, anti-heal head/chest, pierce and defensive support kits), seats/weapons resolved from the role book, options = doctrine tier + off-tier distractors, engine pick hidden in the answers file (never in the form). Scoring records preferred/acceptable/situational/bad per the relative-ranking philosophy (6B). Caller answers require a validation round — the generated form was the deliverable. (Retired 2026-09-10: R24 supersedes the cards; see `notes/findings/2026-08-27-gear-validation-status.md`.)

- [x] Steps: write generator + scorer, generate the form, verify no engine answers leak into the form text.

### Task 10: calibration dataset structure (Phase 7 + 7A) — done

**Files:** create `calibration/README.md`, `calibration/cases.yaml`, `calibration/expert_answers/README.md`, `calibration/train_cases.yaml`, `calibration/validation_cases.yaml`, `calibration/holdout_cases.yaml`.

**Interfaces:** case schema (same record shape as Task 4's parser output + provenance + split assignment); seeded train cases transcribed from VALIDATION.md's documented 2026-08-23 V3 validation round (only what the log actually records — named-weapon answers for cases 2/4/7/8, role-level for the rest — provenance-marked; nothing invented); validation/holdout **empty with the discipline documented** (holdout can only come from future unexamined validation rounds; holdout misses are never converted to goldens mid-round). The README carries the train/validation/holdout rules and the anti-circularity bridge.

- [x] Steps: write the files; cross-check every transcribed answer against VALIDATION.md verbatim.

### Task 11: calibration harness + outer-coefficient sensitivity (Phases 8–10, 12 scaffolding) — done

**Files:** create `pipeline/calibrate_scoring.py` → `pipeline/out/calibration_report.json`.

**Interfaces:** loads calibration cases; evaluates under parameter overrides via attribute mutation (`e.alpha/e.beta/e.delta/e.rho/e.viability_w/e.gamma/e.headroom/e.overstack_max` — read at scoring time; **self-check required**: alpha=0 ⇒ comp_score == beta·syn + tail at 1e-9, else abort) + `set_content` refresh for anything content-baked (synergy bonus overrides mutate `data["scoring"]["capability_synergies"]` then re-set_content to rebuild the active-pair table); sweeps the spec ranges (alpha .30–.80, beta 0–.50, delta 0–.30, rho 0–.75, viability 0–.30; synergy bonus ladder 0–3.0; gamma/headroom/overstack targeted probes); reports per point: top1/top3/acceptable/bad-violations/mean-rank/golden-regression count (golden run = subprocess, counted not auto-fixed); finds stable regions, never argmax. **Honesty clause printed in the report:** with only the seeded train set (n≈12, one caller, role-level), sweep output is a sensitivity map, not a calibration — every coefficient stays at its current value, marked provisional, awaiting validation rounds. Phase 10 curve probes + Phase 12 style sections emitted as "cases generated / awaiting caller answers".

- [x] Steps: write the harness + the self-check test in test_validation_modes.py; run the sensitivity sweep; write the report JSON + doc section; **verify zero engine files changed** (`git status` on engine/ + templates/).

### Task 12: required reports, docs sync, full battery — done

**Files:** complete `notes/findings/2026-08-27-dressed-validation-report.md` (report 1: V3-W/V3-D/V4-by-class numbers, weapon-only baseline, changed-recommendation examples); create `notes/findings/2026-08-27-dressed-template-audit.md` (report 2 summary over the JSON); reports 3/4 are Tasks 7/8's findings; report 5 = the gear card status doc (answers pending); report 6 = the calibration report + provisional-coefficient table. Modify `HANDOFF.md`, `tests/VALIDATION.md` (new dated section: V3-W/V3-D distinction, V4 evidence classes, audit findings, decisions needed), `CLAUDE.md` (test list + audit scripts), `engine/README.md` (set_dressing), `pipeline/README.md` (audit scripts), `MASTERSHEET.md` only if a pointer row is warranted.

- [x] Steps: write the docs; run the FULL battery (golden, forge, builds, interactions, provenance, patch, parity, codec, display, cohort, roles, tier2, validation_modes); summarize; enumerate the decisions required (gate re-basing to dressed metrics, tankiness architecture, synergy source model, gear-card answers, calibration rounds, the forge locked-gears gap, `refine()` gear-blindness).

## Self-review notes

- Spec coverage: Phases 1A/1B/1C/1D → Tasks 1–4; 2A/2B → Task 5; 3/3A → Task 6; 4A/4B → Task 7; 5A/5B → Task 8; 6A/6B → Task 9; 7/7A → Task 10; 8/8A + 9 + 10 + 12 scaffolding → Task 11; 11 → Task 7 finding + Task 11 report section; reports/docs/battery → Task 12. Execution order preserved.
- Known deliberate deferrals (stated, not hidden): caller answers (Phases 6/9/10/12 data) require a validation round; coefficient changes are out of scope by rule; gate re-basing needed a maintainer decision (taken 2026-08-27: re-based to `actual_gear` role-level after Option C).
