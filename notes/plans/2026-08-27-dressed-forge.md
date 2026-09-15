# Dressed Forge — implementation plan (2026-08-27)

Status: implemented 2026-08-27 (HANDOFF.md "the DRESSED FORGE shipped",
`engine/README.md`, forge pins F25/F26). The task checkboxes were never
ticked during execution; the record below lists each task with its outcome.

**Goal:** Forge and recommend evaluate DRESSED candidates (weapon + combo + doctrine kit + divergent variants) via the exact full-build score the loaded comp displays; the page starts scoring equipped gear (a gap found during the work); forged members arrive with kits pre-filled.

**Architecture:** The dressed marginal splits cleanly along `comp_score`'s existing seams — fitness reads gear-inclusive supply, synergy stays weapon-keyed (verified: `synergy()` computes its own gears-free supply). So `party_state` grows a second supply (`s` dressed for fit, `s_syn` weapon-only for synergy), `_eval_pick` iterates combo × kit-variant with precomputed `build_extra` vectors, the beam carries `gears`, and the synergy fast path is reused untouched. The UI derives per-member gear lists from LOADOUT and passes them everywhere it scores.

**Tech stack:** Python 3 (`engine/engine.py`), the JS mirror (`engine/app_scoring.js` — contains a literal NUL byte: search with `Select-String`, read with an editor, never grep), `dashboard/_app.js`, script-style tests.

**Spec:** `notes/specs/2026-08-27-dressed-forge-design.md`

## Global constraints

- Run Python as `py -3`; tests are script-style (never pytest); exit 0 = pass.
- Change one engine port, change both; `py -3 tests/test_js_parity.py` at 1e-9 after every engine-behavior task.
- NO doctrine passives in any evaluation (`build_extra(..., role=None)` always in scoring/search paths) — standing rule: generation/display-only.
- Locked/manual members are never re-dressed; manual always scores; kit variants shape generation only.
- With `gears=None` everywhere, every number must be BIT-IDENTICAL to before (regression gate on every task).
- Golden ordinal flips (a top recommendation changing) STOP the work for a maintainer decision — never absorbed into pin edits.
- Never hand-edit generated pages; edit `dashboard/_*.js` sources and run `py -3 dashboard/build.py`.
- Commit messages via a temp file + `git commit -F` (PowerShell 5.1 trap).
- Deterministic everywhere: doctrine-tier order, lexicographic tie-breaks, no randomness.

## File map

- `engine/engine.py` — `party_state`/`_eval_pick`/`_combo_score` gears threading; `kit_variants` + `_dressed_extras` caches; `forge`/`_forge_eval_pick`/`_refine_constrained`/`_two_opt`/`recommend`/`swap_review` threading; forge returns `gears`.
- `engine/app_scoring.js` — the mirror of all of the above.
- `dashboard/_app.js` — `gearsFromLoadout` (pure), `GEARS_CUR` wiring into `partyCalc`/recommend/swap paths + cache key; forge-result kit prefill.
- `tests/test_forge.py` — F22 (dressed F1), F23 (generation-only), F24 (variant determinism); F5 rerun.
- `tests/test_js_parity.py` — dressed-party and dressed-forge cases.
- `tests/test_display_math.js` — `gearsFromLoadout` unit.
- `CLAUDE.md`, `HANDOFF.md` — docs sync (folded into the last task).

## Tasks

### Task 1: the page scores equipped gear — done

- Files: `dashboard/_app.js` (`partyCalc`; the recommend call sites; the swap-review/`explain` call sites that pass party+combos); test `tests/test_display_math.js`.
- Interfaces: `gearsFromLoadout(lo)` — pure: one LOADOUT entry (`{head, armor, shoes, cape, offhand, potion, food, q, w, p}` or undefined) → array of engine gear keys (curated only, fixed slot order) or `null` when none equipped; `GEARS_CUR` — per-member array aligned with `party`, rebuilt like `COMBOS_CUR`. Consumes the embedded `GEAR` catalog (`dataset["gear"]` keys) and `LO_SLOTS` order from `_loadout.js`.
- Gap closed: `ENG.fitness(party, COMBOS_CUR)` — the page never passed gear although `LOADOUT[i]` stores all seven slots and the engine API scores them (golden T20/T21). User-visible: equipping curated kit moves the displayed score — the member model (the seat/member is the whole build), landing deliberately.
- Steps: (1) failing test — curated slots map in fixed order; empty/uncurated → null (the test injects the gear catalog as a second argument so the unit stays pure). (2) `node tests/test_display_math.js` fails. (3) implement `gearsFromLoadout`; compute `GEARS_CUR` wherever `COMBOS_CUR` is; `partyCalc()` passes `GEARS_CUR` to `fitness` and `effectiveSupply` and extends the cache key with a gear signature; the leave-one-out fitness call threads the matching gears slice; the recommend/swap call sites are marked for Task 6 (they gain `GEARS_CUR` once Task 5 lands the JS signature). (4) `node tests/test_display_math.js` PASS; `py -3 dashboard/build.py` exit 0; `py -3 tests/test_js_parity.py` PASS (engine untouched). (5) commit `UI: the page scores equipped gear (LOADOUT -> GEARS_CUR)`.

### Task 2: `party_state` learns gears (Python), bit-identical when None — done

- Files: `engine/engine.py` — `party_state`, `_marg_syn_from`, `_marg_syn_pre`, `_combo_score`; test `tests/test_forge.py` (F22a).
- Interfaces: `party_state(party, combos=None, gears=None)`; the state dict gains `"s_syn"` (weapon-only supply). `state["s"]` = fit supply (dressed when gears are given, identical object semantics otherwise). All synergy math reads `s_syn`; all fitness math reads `s`. Tasks 3–5 rely on exactly these key names.
- Steps: (1) F22a — `party_state(gears=None)` is unchanged (`s == s_syn`); a dressed-party fit marginal (`_marg_fit_from(st["s"], member_extra)`) equals the exact fitness delta at 1e-9. (2) fails (TypeError/KeyError). (3) implement: `s_syn, J = self._syn_state(party, combos)`; `s = self.effective_supply(party, combos, gears)` when any gears are passed, else `s_syn`; `pair_vals` reads `s_syn`; the two synergy helpers read `state["s_syn"]`; `best_loadout`'s hand-built state dict carries `"s_syn"`. (4) forge (all, incl. the F1 540-eval sweep — proves bit-identity), golden, interactions, parity PASS. (5) commit `Engine: party_state carries dressed fit supply beside weapon-only synergy supply`.

### Task 3: kit variants + dressed vector cache (Python) — done

- Files: `engine/engine.py` (new methods near `kit_options`; cache reset in `set_content`); test F24.
- Interfaces: `kit_variants(weapon)` → list of `(variant_key, gears_list)`, keys `"v0"`, `"v1"`, `"v2"`; `[("v0", None)]` for weapons with no resolvable seat/doctrine (dressed == naked — menu-less weapons change behavior zero). `_dressed_extras(weapon)` → `{variant_key: [extra_per_combo, ...]}` parallel to `_combo_extras`, computed with `build_extra(weapon, combo_idx, gears, role=None)`. Both cached per `set_content` (reset wherever `_combo_extras`/hot-path caches reset). `gears_list` is the variant's piece keys in LO slot order.
- Variant rule (spec, exact): v0 = per LO slot, the seat's doctrine-tier-first top pick exactly as `kit_options(weapon, role="auto")` ranks it context-free (slots with an empty doctrine tier stay UNSET in v0 — the forge never guesses off-doctrine gear). Candidate divergent slots: for each slot, walk the doctrine tier in ranked order; a piece whose top weighted capability (argmax of `weight(cap) * gear_extra[cap]`, lexicographic tie-break) differs from v0's piece in that slot is divergent. Collect divergent (slot, piece) pairs in (slot-order, tier-order); v1/v2 = v0 with the first/second such single-slot swap applied. Cap: 3 variants total.
- Steps: (1) F24 — variants deterministic, capped at 3, v0 first; every variant piece curated and a doctrine-tier member; a menu-less weapon yields the single naked variant; dressed extras parallel the combos per variant. (2) fails. (3) implement. (4) F24 + whole `test_forge.py`, `test_golden.py` PASS (nothing consumes variants yet). (5) commit `Engine: doctrine kit variants + dressed vector cache (unused yet)`.

### Task 4: dressed evaluation — `_eval_pick`, forge, refinement, recommend (Python) — done

- Files: `engine/engine.py` — `_eval_pick`, `_pick_tail`, `forge`, `_forge_eval_pick`, `_member_tag`, `_refine_constrained`, `_two_opt`, `recommend`, the `swap_review`/`pick_report` callers of `_eval_pick`; tests F22b/F23, full suites.
- Interfaces: `_eval_pick(state, weapon)` returns `(score, d_fit, d_syn, meta, combo, variant, vgears)` — two appended fields; every unpacking call site updated in this task. `forge(...)` result gains `"gears"` (aligned with `party`: the caller's own gear for locked slots — `None` unless a future caller passes them — and the chosen variant's list for generated slots) and `"kits"` (per generated index: `{"variant": key, "gears": [...]}`) for UI annotation. `recommend(party, top_n=4, pool=None, combos=None, gears=None)` — entries gain `"kit"` naming the variant-best gear.
- Mechanics: fit half DRESSED, synergy half weapon-only — mirrors `comp_score` exactly (fitness reads gears, synergy does not; verified 2026-08-27). The naked variant's dressed vectors ARE the combo extras (`dressed["v0"][i] is extras[i]`) so the fast path stays exact; dressed variants take the `_marg_fit_from` slow path (a `_dressed_pre` items table per variant mirroring `_combo_pre` only if the F5 timing regresses past 2× — the fast/slow paths are proven equal by F1). Beams carry `gears`; expansions carry `(score, bi, w, combo, vkey, vgears)`; `_member_tag(w, combo, vkey)` returns `w + "#" + combo + "#" + vkey`; `party_state(party2, combos2, gears2)` and `comp_score(party2, combos2, gears2)` on every beam rebuild; `_forge_eval_pick` gets the same dressed loop inside its combo-feasibility filter (variants do not change predicate contributions — predicates are weapon/combo-keyed); `_refine_constrained`/`_two_opt` and the filler/held audit thread the aligned gears slice, a swapped-in candidate re-evaluates dressed and its variant's gears replace that slot's entry.
- Steps: (1) F22b — the dressed pick invariant: reported score == exact comp_score delta including the variant's gears, party dressed too (worst of 20 pool weapons < 1e-9). F23 — generation-only: a manually locked party scores bit-identically pre/post dressed forge; `forge(9, locked=manual)` keeps `gears=None` on the locked slots and exposes `kits` (a generated member whose variant is the naked fallback legitimately carries `None`; the real pin is locked-slot preservation + the `kits` surface). (2) fail. (3) implement. (4) forge (F1's assertion is score==delta, not a pinned number, so movement caused by dressing is expected); golden read case by case — numeric shifts within assertions pass, an ORDINAL flip STOPS for a maintainer decision, never a pin edit; interactions; `tier2_blindtest.py v4` (gate 70% — the number reported). (5) performance: time the F5 block before/after; `_dressed_pre` if > 2× slower; both numbers in the commit message. (6) commit `Engine: dressed evaluation — forge/recommend price weapon+kit candidates (F22/F23)`.

### Task 5: JS mirror + parity — done

- Files: `engine/app_scoring.js` (partyState, evalPick, forge, refinement, recommend, memberTag, kitVariants, dressedExtras — every Task 2–4 change mirrored); `tests/test_js_parity.py` (dressed cases).
- Interfaces: JS `recommend(party, topN, pool, combos, gears)`, `forge(...)` returning `gears`/`kits`, identical field names to Python (`kit`, `kits`, `gears`, variant keys `v0/v1/v2`).
- Steps: (1) extend parity first, following its random-party pattern: (a) N random parties WITH random curated gear lists per member — `comp_score`/`fitness`/`effective_supply` at 1e-9; (b) dressed `recommend` top-4 (score AND chosen kit identical); (c) one dressed `forge` per content at its validated size — party, combos, gears, kits, score all identical. (2) parity fails (JS lacks the signatures). (3) mirror exactly: `s_syn` in partyState; the dressed loop in evalPick (same float-op order: fit from the dressed adjusted vector, syn from the weapon extras); kitVariants (reusing the context-free `kit_options` ranking already in JS); dressedExtras cache; forge beams with gears + 3-part memberTag; refinement threading; recommend signature. (4) parity 1e-9; interactions (its JS checks); `dashboard/build.py` (the embed check runs the parity fixture in-page). (5) commit `JS mirror: dressed evaluation at 1e-9 parity`.

### Task 6: UI — forged kits prefill + annotations, docs sync — done

- Files: `dashboard/_app.js` (forge result handling; the recommend/swap call sites marked in Task 1; swap-review kit display; the `_eng` mark reuse); `CLAUDE.md` (architecture point 7), `HANDOFF.md`; tests `node tests/test_display_math.js`, `node tests/test_loadout_codec.js`, the full gate list.
- Steps: (1) after `party = r.party.slice()`, build each generated index's LOADOUT entry from `r.gears[i]` (slot-keyed from the gear catalog's `slot` field) marked `_eng: true` (the existing engine-kit mark); locked indices keep their entries verbatim — all through the existing post-forge LOADOUT reconstruction path so `sortPartyByRole`'s one permutation covers it (the central-handlers invariant). (2) pass `GEARS_CUR` at the marked recommend/swap call sites; swap-review rows display the assumed kit (small text, translation-only — no new math in `_decision_layer`). (3) rebuild, then the ENTIRE CLAUDE.md test list top to bottom (goldens settled in Task 4). (4) docs: CLAUDE.md point 7 — forge/recommend evaluate dressed candidates (doctrine kit + divergent variants, generation-only; manual never re-dressed) and the page scores equipped gear; HANDOFF current-state entry. (5) commit `Dressed forge shipped: kits searched, prefilled, and scored end to end`.

## Self-review (at write time)

- Spec coverage: the dressed-candidate model → Tasks 3–4; engine mechanics 1–6 → Tasks 2–4 (+5 JS); recommend/goldens → Task 4 steps 3–4; UI → Tasks 1+6; tests/perf → F22/F23/F24, the parity task, Task 4 step 5; exclusions respected (no passives — `role=None` pinned in Global constraints; no fill-order change). Doctrine-coherence first case (spec Tests) — DEFERRED to the comp-book increment: it needs `test_doctrine.py` scaffolding that plan owns; the gap is explicit, not silent.
- Placeholders: the `_eval_pick` sketch flagged its own tuple-slicing care note rather than hiding it; Task 1's gear-catalog handle note gave both concrete options and the test stays runnable either way.
- Type consistency: the `_eval_pick` 7-tuple `(score, d_fit, d_syn, meta, combo, variant, vgears)` is used identically in F22b, the forge threading, recommend and the JS mirror; `party_state` keys `s`/`s_syn` consistent across Tasks 2/4/5; forge result keys `gears`/`kits` consistent across Tasks 4/5/6.
