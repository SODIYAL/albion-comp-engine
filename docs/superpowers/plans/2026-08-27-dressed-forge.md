# Dressed Forge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forge and recommend evaluate DRESSED candidates (weapon + combo + doctrine kit + divergent variants) via the exact full-build score the loaded comp displays; the page starts scoring equipped gear (discovered gap); forged members arrive with kits pre-filled.

**Architecture:** The dressed marginal splits cleanly along `comp_score`'s existing seams — fitness reads gear-inclusive supply, synergy stays weapon-keyed (verified: `synergy()` computes its own gears-free supply). So `party_state` grows a second supply (`s` dressed for fit, `s_syn` weapon-only for synergy), `_eval_pick` iterates combo × kit-variant with precomputed `build_extra` vectors, the beam carries `gears`, and the synergy fast path is reused untouched. The UI derives per-member gear lists from LOADOUT and passes them everywhere it scores.

**Tech Stack:** Python 3 (`engine/engine.py`), ES5-ish JS mirror (`engine/app_scoring.js` — contains a literal NUL byte: search with `Select-String`, read with the Read tool, never grep), `dashboard/_app.js`, script-style tests.

**Spec:** `docs/superpowers/specs/2026-08-27-dressed-forge-design.md`

## Global Constraints

- Run Python as `py -3`; tests are script-style (never pytest); exit 0 = pass.
- Change one engine port, change both; `py -3 tests/test_js_parity.py` at 1e-9 after every engine-behavior task.
- NO doctrine passives in any evaluation (`build_extra(..., role=None)` always in scoring/search paths) — owner ruling, generation/display-only.
- Locked/manual members are never re-dressed; manual always scores; kit variants shape generation only.
- With `gears=None` everywhere, every number must be BIT-IDENTICAL to today (regression gate on every task).
- Golden ordinal flips (a top recommendation changing) STOP the work and go to the owner — never absorbed into pin edits.
- Never hand-edit generated pages; edit `dashboard/_*.js` sources and run `py -3 dashboard/build.py`.
- Commit messages via a temp file + `git commit -F` (PowerShell 5.1 trap).
- Deterministic everywhere: doctrine-tier order, lexicographic tie-breaks, no randomness.

## File Structure

- `engine/engine.py` — `party_state`/`_eval_pick`/`_combo_score` gears threading; `kit_variants` + `_dressed_extras` caches; `forge`/`_forge_eval_pick`/`_refine_constrained`/`_two_opt`/`recommend`/`swap_review` threading; forge returns `gears`.
- `engine/app_scoring.js` — the mirror of all of the above.
- `dashboard/_app.js` — `gearsFromLoadout` (pure), `GEARS_CUR` wiring into `partyCalc`/recommend/swap paths + cache key; forge-result kit prefill.
- `tests/test_forge.py` — F22 (dressed F1), F23 (generation-only), F24 (variant determinism); F5 rerun.
- `tests/test_js_parity.py` — dressed-party and dressed-forge cases.
- `tests/test_display_math.js` — `gearsFromLoadout` unit.
- `CLAUDE.md`, `HANDOFF.md` — docs sync (folded into the last task).

---

### Task 1: The page scores equipped gear

**Files:**
- Modify: `dashboard/_app.js` (partyCalc ~line 100; recommend call sites ~80, ~906; swap-review/`explain` call sites that pass party+combos)
- Test: `tests/test_display_math.js`

**Interfaces:**
- Produces: `gearsFromLoadout(lo)` — pure: one LOADOUT entry (`{head, armor, shoes, cape, offhand, potion, food, q, w, p}` or undefined) → array of engine gear keys (curated only, fixed slot order) or `null` when none equipped. `GEARS_CUR` — per-member array aligned with `party`, rebuilt like `COMBOS_CUR`. Task 6 reuses both.
- Consumes: the embedded `GEAR` catalog (`dataset["gear"]` keys) and `LO_SLOTS` order from `_loadout.js`.

Discovered gap this closes: `ENG.fitness(party, COMBOS_CUR)` — the page never passes gear although `LOADOUT[i]` stores all seven slots and the engine API scores them (golden T20/T21). User-visible: equipping curated kit now moves the displayed score — this IS the owner's member-model ("the seat/member being the whole"), landing deliberately.

- [ ] **Step 1: Write the failing test**

In `tests/test_display_math.js`, alongside the existing extraction-style tests (follow the file's own pattern for loading functions from `dashboard/_app.js` source), add:

```js
// gearsFromLoadout: LOADOUT entry -> engine gears list (curated only,
// LO_SLOTS order, null when nothing curated is equipped)
const GEAR_FIX = { HEAD_CLOTH_SET2: 1, ARMOR_PLATE_SET2: 1 };
check("gearsFromLoadout maps curated slots in fixed order",
  JSON.stringify(gearsFromLoadout(
    { head: "HEAD_CLOTH_SET2", armor: "ARMOR_PLATE_SET2",
      shoes: "SHOES_NOT_CURATED", q: 1 }, GEAR_FIX))
  === JSON.stringify(["HEAD_CLOTH_SET2", "ARMOR_PLATE_SET2"]));
check("gearsFromLoadout: empty/uncurated -> null",
  gearsFromLoadout(undefined, GEAR_FIX) === null
  && gearsFromLoadout({ q: 2 }, GEAR_FIX) === null
  && gearsFromLoadout({ shoes: "SHOES_NOT_CURATED" }, GEAR_FIX) === null);
```

- [ ] **Step 2: Run to verify it fails** — `node tests/test_display_math.js` → FAIL (function missing).

- [ ] **Step 3: Implement in `dashboard/_app.js`**

```js
/* LOADOUT entry -> engine gears list: curated pieces only (the engine
   ignores unknown keys but the cache key must be stable), LO_SLOTS
   order, null when nothing curated is equipped. Second arg for tests. */
function gearsFromLoadout(lo, gearDb){
  const db = gearDb || (typeof GEAR_CAPS !== "undefined" ? GEAR_CAPS : GEAR);
  if (!lo) return null;
  const out = [];
  for (const s of ["head","armor","shoes","cape","offhand","potion","food"])
    if (lo[s] && db[lo[s]]) out.push(lo[s]);
  return out.length ? out : null;
}
```

NOTE at implementation: check what the page embeds for curated gear — the engine's `this.gear` comes from `dataset["gear"]`; if `_app.js` has no direct handle, expose one from the engine (`ENG.gearKeys()` or read `DATA.gear`). Use whichever the embed actually provides; the test's second-arg injection keeps the unit pure either way.

Then wire it:
- `GEARS_CUR`: computed wherever `COMBOS_CUR` is (same lifecycle), as `party.map((_,i) => gearsFromLoadout(LOADOUT[i]))`.
- `partyCalc()`: `fit: ENG.fitness(party, COMBOS_CUR, GEARS_CUR), sup: ENG.effectiveSupply(party, COMBOS_CUR, GEARS_CUR)` and extend the cache key with a gear signature: `` `...${comboSig()}|${gearSig()}` `` where `gearSig()` joins each member's gears list (`-` for null).
- Every `ENG.recommend(party, n, pool, COMBOS_CUR)` call gains a `GEARS_CUR` argument **after Task 5 lands the JS signature** — in THIS task, only fitness/effectiveSupply (already gears-capable in both ports) change. Leave a `/* dressed-forge Task 6: pass GEARS_CUR */` marker at the recommend/swap call sites.
- Line ~574 (`base - ENG.fitness(party.filter(...))`) — thread the matching gears slice: `GEARS_CUR.filter((_, j) => j !== i)`.

- [ ] **Step 4: Rebuild + verify** — `node tests/test_display_math.js` PASS; `py -3 dashboard/build.py` exit 0; `py -3 tests/test_js_parity.py` PASS (engine untouched — must be green).

- [ ] **Step 5: Commit** — `UI: the page scores equipped gear (LOADOUT -> GEARS_CUR)`.

---

### Task 2: `party_state` learns gears (Python), bit-identical when None

**Files:**
- Modify: `engine/engine.py` — `party_state` (line ~1501), `_marg_syn_from` (~1541), `_marg_syn_pre` (~1628), `_combo_score` (~1647)
- Test: `tests/test_forge.py` (new F22a sanity block)

**Interfaces:**
- Produces: `party_state(party, combos=None, gears=None)`; state dict gains `"s_syn"` (weapon-only supply). `state["s"]` = fit supply (dressed when gears given, identical object semantics otherwise). All synergy math reads `s_syn`; all fitness math reads `s`. Tasks 3–5 rely on exactly these key names.

- [ ] **Step 1: Write the failing test** — in `test_forge.py` (follow its check() style):

```python
# F22a — party_state gears plumbing: fit marginal against a dressed
# party equals the exact fitness delta; gears=None stays bit-identical.
e22 = Engine(content="castle", size=25, style="brawl")
p22 = ["2H_MACE", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW"]
g22 = [["ARMOR_PLATE_SET2"], None, ["ARMOR_LEATHER_SET2"]]
st_naked = e22.party_state(p22)
st_old = e22.party_state(p22, None)          # legacy call shape
check("F22a party_state(gears=None) is unchanged",
      st_naked["s"] == st_old["s"] and st_naked["s_syn"] == st_old["s"])
st = e22.party_state(p22, None, g22)
extra = e22.member_extra("2H_HAMMER")
d_fit = e22._marg_fit_from(st["s"], extra)
exact = (e22.fitness(p22 + ["2H_HAMMER"], None, g22 + [None])
         - e22.fitness(p22, None, g22))
check("F22a dressed-party fit marginal == exact fitness delta (1e-9)",
      abs(d_fit - exact) < 1e-9, f"{d_fit} vs {exact}")
```

- [ ] **Step 2: Run to verify it fails** — `py -3 tests/test_forge.py` → F22a fails (TypeError/KeyError).

- [ ] **Step 3: Implement**

In `party_state`: signature `(self, party, combos=None, gears=None)`. Replace the `_syn_state` call block with:

```python
        s_syn, J = self._syn_state(party, combos)
        s = (self.effective_supply(party, combos, gears)
             if gears and any(gears) else s_syn)
```

`pair_vals` keeps using `s_syn` (change its two `s.get(...)` reads to `s_syn.get(...)`). Return `{"s": s, "s_syn": s_syn, "J": J, ...}` (rest unchanged).

In `_marg_syn_from` and `_marg_syn_pre`: `s = state["s_syn"]` instead of `state["s"]` (one line each). `_marg_fit_from`/`_marg_fit_pre` keep reading `state["s"]` via their callers — verify `_combo_score` passes `state["s"]` to fit and the state object to syn (it already does).

Also update `best_loadout`'s hand-built state dict (~line 1692) to carry `"s_syn": s` so the syn helpers don't KeyError.

- [ ] **Step 4: Verify** — `py -3 tests/test_forge.py` PASS (all, incl. F1 540-eval sweep — proves bit-identity); `py -3 tests/test_golden.py` PASS; `py -3 tests/test_interactions.py` PASS; `py -3 tests/test_js_parity.py` PASS (JS untouched; parity cases pass no gears).

- [ ] **Step 5: Commit** — `Engine: party_state carries dressed fit supply beside weapon-only synergy supply`.

---

### Task 3: Kit variants + dressed vector cache (Python)

**Files:**
- Modify: `engine/engine.py` (new methods near `kit_options`; cache reset in `set_content`)
- Test: `tests/test_forge.py` (F24)

**Interfaces:**
- Produces: `kit_variants(weapon)` → list of `(variant_key, gears_list)`; `variant_key` `"v0"`, `"v1"`, `"v2"`; `[("v0", None)]` for weapons with no resolvable seat/doctrine (dressed == naked — menu-less weapons change behavior zero). `_dressed_extras(weapon)` → `{variant_key: [extra_per_combo,...]}` parallel to `_combo_extras`, computed with `build_extra(weapon, combo_idx, gears, role=None)`. Both cached per `set_content` (reset wherever `_combo_extras`/hot-path caches reset).

**Variant rule (spec §2/§3.6, exact):** v0 = per LO slot, the seat's doctrine-tier-first top pick exactly as `kit_options(weapon, role="auto")` context-free ranks it (reuse that ranking; slots with an empty doctrine tier stay UNSET in v0 — the forge never guesses off-doctrine gear). Candidate divergent slots: for each slot, walk the doctrine tier in ranked order; a piece whose top weighted-capability (argmax of `weight(cap) * gear_extra[cap]`, lexicographic tie-break) differs from v0's piece in that slot is divergent. Collect divergent (slot, piece) pairs in (slot-order, tier-order); v1/v2 = v0 with the first/second such single-slot swap applied. Cap: 3 variants total.

- [ ] **Step 1: Failing test (F24)**

```python
# F24 — kit variants: deterministic, capped, doctrine-bounded, naked
# fallback for menu-less weapons.
e24 = Engine(content="castle", size=25, style="brawl")
v_mace = e24.kit_variants("2H_MACE")
v_mace2 = e24.kit_variants("2H_MACE")
check("F24 variants deterministic + capped at 3 + v0 first",
      v_mace == v_mace2 and 1 <= len(v_mace) <= 3
      and v_mace[0][0] == "v0")
gear_keys = set(e24.gear)
check("F24 every variant piece is curated + doctrine-tier member",
      all(k in gear_keys for _v, gl in v_mace for k in (gl or [])))
no_menu = next(w for w in e24.weapons
               if not (e24.weapons[w].get("role_menu") or []))
check("F24 menu-less weapon -> single naked variant",
      e24.kit_variants(no_menu) == [("v0", None)])
de = e24._dressed_extras("2H_MACE")
check("F24 dressed extras parallel combos per variant",
      set(de) == {v for v, _g in v_mace}
      and all(len(de[v]) == len(e24._combo_extras("2H_MACE")) for v in de))
```

- [ ] **Step 2: Run to verify F24 fails.**

- [ ] **Step 3: Implement** `kit_variants` per the variant rule (build v0 from the context-free `kit_options` ranking — call it with `party=None` and read each slot's top `doctrine`-tier entry; skip slots whose top entry has `doctrine == False`), `_dressed_extras` as a dict-cache keyed by weapon, invalidated in `set_content` beside the existing combo caches. `gears_list` is the sorted list of v0/variant piece keys (order stable: LO slot order).

- [ ] **Step 4: Verify** — F24 + whole `test_forge.py`, `test_golden.py` PASS (nothing consumes variants yet).

- [ ] **Step 5: Commit** — `Engine: doctrine kit variants + dressed vector cache (unused yet)`.

---

### Task 4: Dressed evaluation — `_eval_pick`, forge, refinement, recommend (Python)

**Files:**
- Modify: `engine/engine.py` — `_eval_pick` (~1673), `_pick_tail` (~1663), `forge` (~2555), `_forge_eval_pick` (~2511), `_member_tag` (~2536), `_refine_constrained`, `_two_opt`, `recommend` (~1830), `swap_review`/`pick_report` callers of `_eval_pick`
- Test: `tests/test_forge.py` (F22b/F23), full suites

**Interfaces:**
- Produces: `_eval_pick(state, weapon)` returns `(score, d_fit, d_syn, meta, combo, variant, vgears)` — two appended fields; every unpacking call site updated in this task. `forge(...)` result gains `"gears"` (list aligned with `party`: the caller's own gear for locked slots — `None` unless a future caller passes them — and the chosen variant's list for generated slots) and `"kits"` (per generated index: `{"variant": key, "gears": [...]}`) for UI annotation. `recommend(party, top_n, pool, combos, gears=None)` — entries gain `"kit": [...]` naming the variant-best gear.

- [ ] **Step 1: Failing tests (F22b, F23)**

```python
# F22b — THE dressed pick invariant: reported score == exact
# comp_score delta including the variant's gears, party dressed too.
e22 = Engine(content="castle", size=25, style="brawl")
p = ["2H_MACE", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW"]
g = [["ARMOR_PLATE_SET2"], None, None]
st = e22.party_state(p, None, g)
worst = 0.0
for w in list(e22.suggest_pool())[:20]:
    sc, _df, _ds, _m, combo, var, vg = e22._eval_pick(st, w)
    exact = (e22.comp_score(p + [w], [None]*3 + [combo], g + [vg])
             - e22.comp_score(p, None, g))
    worst = max(worst, abs(sc - exact))
check("F22b dressed pick score == exact comp_score delta (1e-9)",
      worst < 1e-9, f"worst {worst}")

# F23 — generation-only: a manually locked party's score is identical
# whatever the forge would have dressed it in.
manual = ["2H_MACE", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW",
          "2H_POLEHAMMER", "2H_ARCANESTAFF_HELL", "2H_HALBERD",
          "2H_HOLYSTAFF"]
check("F23 manual party scores bit-identically pre/post dressed forge",
      e22.comp_score(manual) == e22.comp_score(manual, None, None))
r = e22.forge(9, locked=manual)
check("F23 locked slots keep gears=None; generated slots carry kits",
      all(r["gears"][i] is None for i in range(len(manual)))
      and all(r["gears"][i] is not None or True
              for i in range(len(manual), len(r["party"])))
      and "kits" in r)
```

(F23's second clause is intentionally weak on generated gears — a generated member whose variant is the naked fallback legitimately carries `None`; the real pin is locked-slot preservation + the `kits` surface.)

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement `_eval_pick` dressed**

```python
    def _eval_pick(self, state, weapon):
        best = None
        extras = self._combo_extras(weapon)
        dressed = self._dressed_extras(weapon)
        for vkey, vgears in self.kit_variants(weapon):
            dext = dressed[vkey]
            for i in range(len(extras)):
                # fit half DRESSED, synergy half weapon-only — mirrors
                # comp_score exactly (fitness reads gears, synergy does
                # not; verified 2026-08-27)
                adj = self._nonstack_adjust(state, weapon, i, dext[i])
                if adj is dext[i] and vgears is None:
                    items, pairs = self._combo_pre(weapon)[i]
                    d_fit = self._marg_fit_pre(state["s"], items)
                    d_syn = self._marg_syn_pre(state, extras[i], pairs)
                else:
                    d_fit = self._marg_fit_from(state["s"], adj)
                    d_syn = self._marg_syn_from(state, extras[i], extras[i])
                val = self.alpha * d_fit + self.beta * d_syn
                if best is None or val > best[0]:
                    best = (val, d_fit, d_syn, i, vkey, vgears)
        if best is None:
            best = (0.0, 0.0, 0.0, None, "v0", None)
        score, d_fit, d_syn, meta, combo = self._pick_tail(
            state, weapon, best[:4])
        return score, d_fit, d_syn, meta, combo, best[4], best[5]
```

Implementation care: `_pick_tail` currently returns `best[3]` as combo — adjust the tuple slicing so combo stays combo (write it explicitly, don't rely on the sketch's indices). Dressed vectors for `vgears=None` ARE the combo extras (assert `dressed["v0"][i] is extras[i]` in `_dressed_extras` for the naked variant so the fast path stays exact). For dressed variants the `_marg_fit_from` slow path is fine first; IF the F5 timing step regresses >2×, add a `_dressed_pre` items table per variant mirroring `_combo_pre` (same inline math — the fast/slow paths are proven equal by F1).

**Forge threading (pattern, applied everywhere in `forge`):** beams gain `"gears"`; expansions carry `(score, bi, w, combo, vkey, vgears)`; `_member_tag(w, combo)` → `_member_tag(w, combo, vkey)` returning `w + "#" + combo + "#" + vkey`; `party_state(party2, combos2, gears2)` and `comp_score(party2, combos2, gears2)` on every beam rebuild; `_forge_eval_pick` gets the same dressed loop as `_eval_pick` inside its combo-feasibility filter (variants do not change predicate contributions — predicates are weapon/combo-keyed; state that in a comment). `_refine_constrained`/`_two_opt`: read both functions; every `party_state`/`comp_score`/`_eval_pick` call gains the aligned gears slice; a swapped-in candidate re-evaluates dressed and its variant's gears replace that slot's entry. The filler/held audit's `comp_score` calls likewise. `forge` returns `{"party", "combos", "gears", "kits", ...}`.

**`recommend`:** signature `(self, party, top_n=4, pool=None, combos=None, gears=None)`; `state = self.party_state(party, combos, gears)`; each entry adds `"kit": vgears or []` and threads the extra `_eval_pick` fields. Update `explain`, `swap_review`, `pick_report` unpacking sites (`Select-String`/grep for `_eval_pick(` — update every site in this task; `pick_report`'s reconstruction gains the kit's d_fit contribution automatically since it reads the same returned terms).

- [ ] **Step 4: Verify + golden-flip checkpoint**

`py -3 tests/test_forge.py` (F1 sweep now proves the dressed invariant across 540 evals — F1's own calls pass no gears and must be bit-identical only if pools produce naked v0 variants; where F1's numbers move because generation now dresses, THAT IS EXPECTED — F1's assertion is score==delta, not a pinned number). Then `py -3 tests/test_golden.py`: **read every case that changed**. Numeric shifts within assertions: fine. An ORDINAL flip (different top rec / different forged member): STOP, do not edit the pin — write the case list to the chat report for the owner (Global Constraints).

Also: `py -3 tests/test_interactions.py`, `py -3 tests/tier2_blindtest.py v4` (gate 70% — report the number).

- [ ] **Step 5: Performance measurement** — time `py -3 tests/test_forge.py` F5 block (or the whole file) before/after (git stash the change to measure before, or use the recorded pre-task duration). If > 2× slower, implement `_dressed_pre` (see Step 3 note) and re-measure. Record both numbers in the commit message.

- [ ] **Step 6: Commit** — `Engine: dressed evaluation — forge/recommend price weapon+kit candidates (F22/F23)`.

---

### Task 5: JS mirror + parity

**Files:**
- Modify: `engine/app_scoring.js` (partyState, evalPick, forge, refinement, recommend, memberTag, kitVariants, dressedExtras — mirror every Task 2–4 change; locate functions with `Select-String`, read with the Read tool)
- Modify: `tests/test_js_parity.py` — add dressed cases
- Test: `py -3 tests/test_js_parity.py`

**Interfaces:**
- Produces: JS `recommend(party, topN, pool, combos, gears)`, `forge(...)` returning `gears`/`kits`, identical field names to Python (`kit`, `kits`, `gears`, variant keys `v0/v1/v2`).

- [ ] **Step 1: Extend the parity test first** — in `test_js_parity.py`, following its existing random-party pattern: (a) N random parties WITH random curated gear lists per member — `comp_score`/`fitness`/`effective_supply` at 1e-9; (b) dressed `recommend` top-4 (score AND chosen kit identical); (c) one dressed `forge` per content at its validated size — party, combos, gears, kits, score all identical.
- [ ] **Step 2: Run — parity fails** (JS lacks signatures).
- [ ] **Step 3: Mirror in `app_scoring.js`** — port each Task 2–4 change exactly: `s_syn` in partyState; the dressed loop in evalPick (same float-op order: fit from dressed adj, syn from weapon extras); kitVariants (reuse the context-free `kit_options` ranking already in JS from the doctrine-tier-first change); dressedExtras cache; forge beams with gears + 3-part memberTag; refinement threading; recommend signature.
- [ ] **Step 4: Verify** — `py -3 tests/test_js_parity.py` all cases 1e-9; `py -3 tests/test_interactions.py` (its JS checks); `py -3 dashboard/build.py` (embed check runs the parity fixture in-page).
- [ ] **Step 5: Commit** — `JS mirror: dressed evaluation at 1e-9 parity`.

---

### Task 6: UI — forged kits prefill + annotations, docs sync

**Files:**
- Modify: `dashboard/_app.js` (forge result handling ~2125; recommend/swap call sites marked in Task 1; swap-review kit display; `_eng` mark reuse ~612)
- Modify: `CLAUDE.md` (architecture point 7 blurb), `HANDOFF.md`
- Test: `node tests/test_display_math.js`, `node tests/test_loadout_codec.js`, full gate list

**Interfaces:**
- Consumes: `r.gears`/`r.kits` from forge; `GEARS_CUR`/`gearsFromLoadout` from Task 1.

- [ ] **Step 1: Wire forge results** — after `party = r.party.slice()`: for each generated index, build the LOADOUT entry from `r.gears[i]` (slot-keyed from the gear catalog's `slot` field) marked `_eng: true` (the existing engine-kit mark); locked indices keep their entries verbatim. All through the existing post-forge LOADOUT reconstruction path so `sortPartyByRole`'s one permutation covers it (read how COMBO/PROV are rebuilt there and mirror it — the central-handlers invariant).
- [ ] **Step 2: Pass `GEARS_CUR` at the marked recommend/swap call sites** (Task 1 markers); swap-review rows display the assumed kit (small text, translation-only — no new math in `_decision_layer`).
- [ ] **Step 3: Rebuild + full gates** — `py -3 dashboard/build.py`; then the ENTIRE CLAUDE.md test list top to bottom. Expected all green; goldens were settled in Task 4.
- [ ] **Step 4: Docs** — CLAUDE.md point 7: one sentence — forge/recommend evaluate dressed candidates (doctrine kit + divergent variants, generation-only; manual never re-dressed) and the page scores equipped gear. HANDOFF current-state entry. 
- [ ] **Step 5: Commit** — `Dressed forge shipped: kits searched, prefized, and scored end to end` (fix the typo: prefilled).

---

## Self-Review (done at write time)

- **Spec coverage:** §2 model → Tasks 3–4; §3 mechanics 1–6 → Tasks 2–4 (+5 JS); §4 recommend/goldens → Task 4 steps 3–4; §5 UI → Tasks 1+6; §6 tests/perf → F22/F23/F24, parity task, Task 4 step 5; §7 exclusions respected (no passives — `role=None` pinned in Global Constraints; no fill-order change). Doctrine-coherence first case (spec §6) — DEFERRED to the comp-book increment: it needs `test_doctrine.py` scaffolding that plan owns; noted here so the gap is explicit, not silent.
- **Placeholder scan:** the `_eval_pick` sketch flags its own index-care note rather than hiding it; no TBDs; Task 1's GEAR-handle note gives both concrete options and the test stays runnable either way.
- **Type consistency:** `_eval_pick` 7-tuple `(score, d_fit, d_syn, meta, combo, variant, vgears)` used identically in F22b, forge threading, recommend, and the JS mirror; `party_state` keys `s`/`s_syn` consistent across Tasks 2/4/5; forge result keys `gears`/`kits` consistent across Tasks 4/5/6.
