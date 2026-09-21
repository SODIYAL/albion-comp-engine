# Escape-healer floor — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** At party size 10 and above, the comp score pays a seat floor when no healer's own weapon carries an escape, so a mobile healer wins the healer seat while that floor is open, in both engine ports, the forge and the page.

**Architecture:** A new flag predicate `escape_heal` rides the existing combo-aware predicate machinery (`_pred_contrib`); a new hard-floor row kind (`min_members` instead of `floor_units`) is read in `set_content`, charged in `fitness`, and priced as an exact delta inside the per-combo candidate scoring so pick score stays the exact comp-score delta. The constraint bands gain a `min: 1` on the same predicate for generation. Display reads one engine call.

**Tech Stack:** Python 3 (`py -3`, script-style tests, exit code = result), the browser port `engine/app_scoring.js` (ES5 style, mirrors engine.py function by function, parity at 1e-9), YAML templates compiled by `pipeline/build_dataset.py`.

**Spec:** `notes/specs/2026-09-21-escape-healer-floor-design.md`

## Global Constraints

- Change one engine port, change the other; `py -3 tests/test_js_parity.py` must pass at the end of every task that touches scoring.
- Every writer of a committed artifact opens with `newline="\n"`.
- Use `py -3`, never `python`. Never pipe a build through `grep`/`tail` when reading `$LASTEXITCODE`.
- `engine/app_scoring.js` reads as binary to grep: locate with PowerShell `Select-String`, read with the Read tool, edit with the Edit tool.
- Comments and test names state the rule, never who decided it; no dates outside the decision log; `py -3 tests/test_tone.py` is a gate (VALIDATION.md and test_tone.py carry pre-existing failures; a touched file must add none).
- Floors read the weapon+loadout basis only; worn gear never satisfies the predicate.
- Hard floors stay on the BASE weight (`self.reqs[cap]["weight"]`), never the style-multiplied one.
- Commit messages go through a BOM-less file (`[System.IO.File]::WriteAllText($p,$msg,(New-Object System.Text.UTF8Encoding $false))` from PowerShell), then `git commit -F <file>`. Messages read as plain rules, no attribution.
- After any template or composition YAML edit: `py -3 pipeline/build_dataset.py` (fails closed, exit 2) before any test that reads the dataset.
- Sheet-point threshold for the predicate: `mobility >= 2` or `disengage >= 2` on the resolved loadout's raw caps.
- Floor row shape (spec): `escape_heal: {min_party_size: 10, min_members: 1, penalty_mult: 0.5, weight_of: heal_sustain}`.

---

## File map

| File | Responsibility in this change |
|---|---|
| `engine/engine.py` | constants; predicate membership (`_pred_contrib`, flat `pred_members`); floor parsing in `set_content`; `escape_count`, `_escape_penalty`, `_escape_delta`, `escape_floor`; `fitness`, `party_state`, `_combo_score`, `_combo_score_dressed`, `explain`; `_forge_ctx` key check |
| `engine/app_scoring.js` | the same, mirrored |
| `pipeline/templates/*.yaml` (six contents) | the floor row |
| `pipeline/templates/composition.yaml` | `escape_heal: {min: 1}` on bands at `min_size >= 10` |
| `pipeline/audit_style_rosters.py` | the predicate in `PREDS` and one board column |
| `dashboard/_app.js` | the roster note |
| `tests/test_forge.py` | F34 predicate pins, F35 forge pin |
| `tests/test_validation_modes.py` | V8 floor pins (gear never satisfies) |
| `tests/test_golden.py` | T50 ranking pin at 12, unchanged at 7 |
| `tests/test_js_parity.py` | two directed cases at 12 |
| `tests/test_dashboard_layout.py` | L25 note contract |
| `HANDOFF.md`, `CLAUDE.md`, `tests/VALIDATION.md`, `notes/validation/2026-09b.md`, `BACKLOG.md` | the rule, the decision, the index row |

---

### Task 1: The `escape_heal` predicate, both ports

**Files:**
- Modify: `engine/engine.py:82-86` (constants), `engine/engine.py:211-227` (flat view), `engine/engine.py:1989-2014` (`_pred_contrib`), `engine/engine.py:3753` (`_forge_ctx` key check)
- Modify: `engine/app_scoring.js:189-202` (flat view), `engine/app_scoring.js:2411-2435` (`_predContrib`), `engine/app_scoring.js:3379` (`_forgeCtx` key check)
- Test: `tests/test_forge.py` (new `t_escape_heal_predicate`, called from the runner)

**Interfaces:**
- Produces: `Engine.ESCAPE_HEAL == "escape_heal"`, `Engine.ESCAPE_HEAL_MIN_PTS == 2`; `escape_heal` appears in `_pred_contrib(weapon, combo)` when the member's primary seat class is `healer` and its raw caps carry mobility or disengage `>= 2`; `pred_members["escape_heal"]` is the flat could-qualify set. JS: `this.ESCAPE_HEAL`, `this.ESCAPE_HEAL_MIN_PTS`, `_predContrib` and `predMembers[this.ESCAPE_HEAL]` likewise.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_forge.py` before the runner block (after `t_replace_options`'s definition), and add `t_escape_heal_predicate()` to the runner list after `t_replace_options()`:

```python
# --------------------------------------------- F34 escape-heal predicate
def t_escape_heal_predicate():
    # A healer carries its own escape when the RESOLVED loadout's raw caps
    # supply mobility or disengage at 2 sheet points or more; the seat
    # class is the one role read; worn gear is never consulted. No hand
    # list: membership derives from the sheets and the role book.
    e = Engine(content="blackzone_roam", size=12)
    HALLOWFALL, GREAT_HOLY, BLIGHT = ("MAIN_HOLYSTAFF_AVALON", "2H_HOLYSTAFF",
                                     "2H_NATURESTAFF_HELL")
    n_h = len(e._combo_extras(HALLOWFALL))
    hf_all = all(e.ESCAPE_HEAL in e._pred_contrib(HALLOWFALL, i) for i in range(n_h))
    n_b = len(e._combo_extras(BLIGHT))
    bl = [e.ESCAPE_HEAL in e._pred_contrib(BLIGHT, i) for i in range(n_b)]
    gh_none = not any(e.ESCAPE_HEAL in e._pred_contrib(GREAT_HOLY, i)
                      for i in range(len(e._combo_extras(GREAT_HOLY))))
    check("F34a Hallowfall satisfies escape_heal with every combo (the E moves it)",
          hf_all, f"combos={n_h}")
    check("F34b Blight satisfies escape_heal only with its mobility spell equipped",
          any(bl) and not all(bl), f"per-combo={bl}")
    check("F34c Great Holy never satisfies escape_heal",
          gh_none, "")
    members = e.pred_members[e.ESCAPE_HEAL]
    derived = {k for k, w in e.weapons.items()
               if e._primary_seat_class(k) == "healer"
               and max(w["capabilities"].get("mobility", 0),
                       w["capabilities"].get("disengage", 0)) >= e.ESCAPE_HEAL_MIN_PTS}
    check("F34d the flat view is derived from sheets + role book, healers only",
          members == derived and all(e._primary_seat_class(k) == "healer" for k in members)
          and e.ESCAPE_HEAL in e._pred_possible(BLIGHT)
          and e.ESCAPE_HEAL not in e._pred_possible(GREAT_HOLY),
          f"members={sorted(members)}")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `py -3 tests/test_forge.py`
Expected: `AttributeError: 'Engine' object has no attribute 'ESCAPE_HEAL'` (the script aborts) or the F34 lines print `FAIL`.

- [ ] **Step 3: Python constants and flat view**

In `engine/engine.py` after line 86 (`STANDOFF = "standoff"`), add:

```python
    # seat floor: a healer whose OWN weapon carries an escape (resolved
    # loadout raw caps: mobility or disengage at ESCAPE_HEAL_MIN_PTS sheet
    # points); worn gear never counts. Combo-dependent, so it rides
    # _pred_contrib like the capability predicates.
    ESCAPE_HEAL = "escape_heal"
    ESCAPE_HEAL_MIN_PTS = 2
```

After the `self.pred_members[self.STANDOFF] = set(...)` block (around line 227), add:

```python
        # flat could-qualify view of the escape-heal predicate (display
        # and the optimistic beam bound); the counted view is per combo
        self.pred_members[self.ESCAPE_HEAL] = set(
            k for k, d in self.weapons.items()
            if self._primary_seat_class(k) == "healer"
            and max(d["capabilities"].get("mobility", 0),
                    d["capabilities"].get("disengage", 0)) >= self.ESCAPE_HEAL_MIN_PTS)
```

- [ ] **Step 4: Python `_pred_contrib` and `_forge_ctx`**

In `_pred_contrib`, after `if weapon in self.pred_members[self.STANDOFF]: out.add(self.STANDOFF)`, add:

```python
        # escape-heal: seat class from the role book, escape from the
        # resolved loadout's raw caps (never worn gear)
        if (self._primary_seat_class(weapon) == "healer"
                and max(caps.get("mobility", 0), caps.get("disengage", 0))
                >= self.ESCAPE_HEAL_MIN_PTS):
            out.add(self.ESCAPE_HEAL)
```

In `_forge_ctx` change the key check to:

```python
            if key in self.pred_defs or key in (self.PRIMARY_HEAL, self.STANDOFF,
                                                self.ESCAPE_HEAL):
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `py -3 tests/test_forge.py`
Expected: F34a-F34d `ok`, every earlier F pin unchanged, exit 0.

- [ ] **Step 6: JS mirror**

In `engine/app_scoring.js` after line 202 (`this.predMembers[this.STANDOFF] = soMembers;`), insert:

```javascript
    /* seat floor predicate (mirrors engine.py ESCAPE_HEAL): a healer whose
       OWN weapon carries an escape — resolved loadout raw caps, mobility or
       disengage at ESCAPE_HEAL_MIN_PTS sheet points; worn gear never
       counts. The flat view here; the counted view is per combo. */
    this.ESCAPE_HEAL = "escape_heal";
    this.ESCAPE_HEAL_MIN_PTS = 2;
    var ehMembers = {};
    for (k in this.weapons) {
      var ehc = this.weapons[k].capabilities || {};
      if (this._primarySeatClass(k) === "healer"
          && Math.max(ehc.mobility || 0, ehc.disengage || 0) >= this.ESCAPE_HEAL_MIN_PTS)
        ehMembers[k] = true;
    }
    this.predMembers[this.ESCAPE_HEAL] = ehMembers;
```

In `_predContrib` after the STANDOFF line (2432), insert:

```javascript
    if (this._primarySeatClass(weapon) === "healer"
        && Math.max(caps.mobility || 0, caps.disengage || 0) >= this.ESCAPE_HEAL_MIN_PTS)
      out[this.ESCAPE_HEAL] = true;
```

In `_forgeCtx` (line 3379) change the condition to:

```javascript
      if (key in this.predDefs || key === this.PRIMARY_HEAL || key === this.STANDOFF
          || key === this.ESCAPE_HEAL) {
```

- [ ] **Step 7: Parity and the gates that read the engine**

Run: `py -3 tests/test_js_parity.py` then `py -3 tests/test_golden.py` then `py -3 tests/test_skeletons.py`
Expected: all exit 0 (no scoring path changed yet; the parity outputs are byte-identical to before).

- [ ] **Step 8: Commit**

Write `msg1.txt` in the scratchpad, BOM-less (the PowerShell recipe in Global Constraints):

```
Engine: escape_heal flag predicate, both ports

A healer carries its own escape when its resolved loadout's raw caps
supply mobility or disengage at 2 sheet points; the seat class is the one
role read; worn gear never counts. Rides _pred_contrib beside primary_heal
and standoff. F34 pins it. No scoring change.

```

Run: `git add engine/engine.py engine/app_scoring.js tests/test_forge.py; git commit -F <path to msg1.txt>`

---

### Task 2: The floor row, the party penalty and the display call, both ports

**Files:**
- Modify: six templates, the `hard_floors:` block of each: `pipeline/templates/blackzone_roam.yaml:152-154`, `castle.yaml:88-90`, `castle_outpost.yaml:110-112`, `faction_war.yaml:88-90`, `roads.yaml:142-144`, `territory_defense.yaml:121-123`
- Modify: `engine/engine.py:307` (`set_content`, after `self.floors = ...`), `engine/engine.py:496-501` (`_floors_eff` loop), `engine/engine.py:2183-2205` (`fitness`), new methods beside `floor_armed` (line 2122)
- Modify: `engine/app_scoring.js:278` (`setContent`), `:427-432` (`_floorsEff`), `:1876-1898` (`fitness`), new methods beside `floorArmed` (line 1824)
- Test: `tests/test_validation_modes.py` (new `t_escape_floor`, V8)

**Interfaces:**
- Consumes: `Engine.ESCAPE_HEAL`, `_pred_contrib` from Task 1.
- Produces: `Engine._escape_floor` = `None` or `(need:int, unit:float)` where `unit = penalty_mult * base weight of weight_of`; `Engine.escape_count(party, combos=None) -> int`; `Engine._escape_penalty(count) -> float`; `Engine.escape_floor(party, combos=None) -> {"armed": bool, "count": int, "need": int}`. JS: `_escapeFloor`, `escapeCount`, `_escapePenalty`, `escapeFloor` with the same semantics.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_validation_modes.py` before `if __name__ == "__main__":` and call `t_escape_floor()` after `t_median_rows()` in the runner:

```python
# ------------------------------------------------- V8 escape-healer floor
def t_escape_floor():
    # One healer must carry an escape on the WEAPON at 10+; boots and a
    # defensive chest give every healer a baseline escape and never count.
    HALLOWFALL, GREAT_HOLY = "MAIN_HOLYSTAFF_AVALON", "2H_HOLYSTAFF"
    core = ["2H_HAMMER_AVALON", "2H_POLEHAMMER", "2H_MACE", "MAIN_HAMMER",
            "2H_ARCANESTAFF_HELL", "2H_ARCANESTAFF", "2H_AXE_AVALON",
            "MAIN_CURSEDSTAFF_CRYSTAL", "2H_KNUCKLES_SET3",
            "2H_FIRE_RINGPAIR_AVALON", "2H_ICECRYSTAL_UNDEAD"]
    e12 = Engine(content="blackzone_roam", size=12)
    gh = core + [GREAT_HOLY]
    sandals = [None] * len(core) + [["SHOES_CLOTH_SET2"]]   # Cleric Sandals: Blink
    st = e12.escape_floor(gh, None)
    check("V8a at 12 the floor is armed and a Great Holy in Cleric Sandals "
          "does not satisfy it (gear never buys floor relief)",
          st["armed"] and st["count"] == 0 and st["need"] == 1
          and e12.escape_count(gh) == 0,
          f"state={st}")
    pen = e12._escape_penalty(0)
    w = e12.reqs["heal_sustain"]["weight"]
    check("V8b the open floor costs penalty_mult x the base heal_sustain weight",
          abs(pen - 0.5 * w) < EPS and abs(e12._escape_penalty(1)) < EPS,
          f"pen={pen} w={w}")
    naked = e12.fitness(gh)
    dressed = e12.fitness(gh, None, sandals)
    # dressing adds the sandals' coverage terms only; the escape penalty is
    # charged identically on both sides
    e12_nofloor = Engine(content="blackzone_roam", size=12)
    e12_nofloor._escape_floor = None
    check("V8c fitness pays the penalty once, naked and dressed alike",
          abs((e12_nofloor.fitness(gh) - naked) - pen) < EPS
          and abs((e12_nofloor.fitness(gh, None, sandals) - dressed) - pen) < EPS,
          f"naked={naked} dressed={dressed} pen={pen}")
    hf = core + [HALLOWFALL]
    st_hf = e12.escape_floor(hf)
    check("V8d a Hallowfall clears the floor (armed by size, met by count)",
          st_hf["armed"] and st_hf["count"] == 1
          and abs(e12._escape_penalty(st_hf["count"])) < EPS,
          f"state={st_hf}")
    e7 = Engine(content="castle_outpost", size=7)
    check("V8e below 10 the floor is not armed and costs nothing",
          e7._escape_floor is None and not e7.escape_floor(gh[:6])["armed"]
          and abs(e7._escape_penalty(0)) < EPS, "")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `py -3 tests/test_validation_modes.py`
Expected: `AttributeError: ... escape_floor` or V8 lines `FAIL`.

- [ ] **Step 3: The template rows**

In each of the six templates, add one line at the end of the `hard_floors:` block, e.g. for `castle_outpost.yaml` after the `tankiness:` line:

```yaml
  # Seat floor: one healer must carry an escape on the WEAPON itself
  # (flag predicate escape_heal: resolved loadout mobility or disengage
  # >= 2 sheet points; boots and chests give every healer a baseline
  # escape and never count). Armed from 10: training-split killer parties
  # field one in 85% at 10-14, 95% at 15-19, 97% at 20+, and 50% at 6-8
  # (never armed below 10). min_members is a count, not units; the
  # penalty is penalty_mult x the base weight of weight_of. penalty_mult
  # PROVISIONAL.
  escape_heal:  {min_party_size: 10, min_members: 1, penalty_mult: 0.5, weight_of: heal_sustain}
```

Put the same row (same comment, shortened to two lines in the five others: `# Seat floor (escape_heal): see castle_outpost.yaml hard_floors. Armed from 10.`) into the other five templates.

Then rebuild: `py -3 pipeline/build_dataset.py` — expected exit 0 and `out/dataset-latest.json` rewritten.

- [ ] **Step 4: Python `set_content` and `_floors_eff`**

After `self.floors = self.template.get("hard_floors", {}) or {}` (line 307) add:

```python
        # Seat floor (escape_heal): armed by size; unit = penalty_mult x the
        # BASE weight of the row it borrows (hard floors never read the
        # style-multiplied weight). None when the template has no row or
        # the size is under min_party_size.
        ef = self.floors.get(self.ESCAPE_HEAL)
        self._escape_floor = None
        if ef and size >= int(ef.get("min_party_size", 0)):
            wcap = ef.get("weight_of", "heal_sustain")
            wrow = self.template["requirements"].get(wcap) or {}
            self._escape_floor = (int(ef.get("min_members", 1)),
                                  float(ef.get("penalty_mult", 0.0))
                                  * float(wrow.get("weight", 0.0)))
```

Change the `_floors_eff` loop (line 498) so a row without `floor_units` is skipped:

```python
        for c, f in self.floors.items():
            if "floor_units" not in f:
                continue      # a seat floor (escape_heal) is a member count
            fu = f["floor_units"]
```

Check line 473 `bad = sorted(self.optional & set(self.floors))`: `escape_heal` is never optional, no change.

- [ ] **Step 5: Python methods and `fitness`**

Beside `floor_armed` (after `_floor_penalty`), add:

```python
    # ----------------------------------------------------- seat floor
    def escape_count(self, party, combos=None):
        """Members whose RESOLVED loadout satisfies escape_heal — the
        weapon+loadout basis; gears are never consulted."""
        n = 0
        for i, w in enumerate(party):
            if self.ESCAPE_HEAL in self._pred_contrib(
                    w, combos[i] if combos else None):
                n += 1
        return n

    def _escape_penalty(self, count):
        if self._escape_floor is None:
            return 0.0
        need, unit = self._escape_floor
        if count >= need:
            return 0.0
        return unit * (need - count) / need

    def escape_floor(self, party, combos=None):
        """Display read of the seat floor: armed at this size, members
        satisfying it, members required."""
        need = self._escape_floor[0] if self._escape_floor else 0
        return {"armed": self._escape_floor is not None,
                "count": self.escape_count(party, combos), "need": need}
```

In `fitness`, after the `for cap in self.reqs:` loop and before `return total`, add:

```python
        # seat floor: charged after the capability terms, one float op
        total -= self._escape_penalty(self.escape_count(party, combos))
```

- [ ] **Step 6: Run the test**

Run: `py -3 tests/test_validation_modes.py`
Expected: V8a-V8e `ok`, V5 pins unchanged, exit 0.

- [ ] **Step 7: JS mirror**

In `setContent` after line 278 (`this.floors = this.template.hard_floors || {};`) add:

```javascript
    /* seat floor (mirrors engine.py set_content): armed by size; unit =
       penalty_mult x the BASE weight of the borrowed row. */
    var ef = this.floors[this.ESCAPE_HEAL];
    this._escapeFloor = null;
    if (ef && size >= (ef.min_party_size || 0)) {
      var wrow = (this.template.requirements || {})[ef.weight_of || "heal_sustain"] || {};
      this._escapeFloor = [ef.min_members === undefined ? 1 : ef.min_members,
                           (ef.penalty_mult || 0.0) * (wrow.weight || 0.0)];
    }
```

Change the `_floorsEff` loop (427-432):

```javascript
    this._floorsEff = {};
    for (var fc in this.floors) {
      if (this.floors[fc].floor_units === undefined) continue;   /* seat floor */
      var fu = this.floors[fc].floor_units;
      var ft = this._targets[fc];
      this._floorsEff[fc] = (ft === undefined || ft > fu) ? fu : ft;
    }
```

After `_floorPenalty` (line 1836), add:

```javascript
  /* ----------------------------------------------------- seat floor
     (mirrors engine.py escape_count / _escape_penalty / escape_floor) */
  CompEngine.prototype.escapeCount = function (party, combos) {
    var n = 0;
    for (var i = 0; i < party.length; i++) {
      if (this._predContrib(party[i], combos ? combos[i] : null)[this.ESCAPE_HEAL]) n += 1;
    }
    return n;
  };
  CompEngine.prototype._escapePenalty = function (count) {
    if (this._escapeFloor === null) return 0.0;
    var need = this._escapeFloor[0], unit = this._escapeFloor[1];
    if (count >= need) return 0.0;
    return unit * (need - count) / need;
  };
  CompEngine.prototype.escapeFloor = function (party, combos) {
    var need = this._escapeFloor ? this._escapeFloor[0] : 0;
    return { armed: this._escapeFloor !== null,
             count: this.escapeCount(party, combos), need: need };
  };
```

In `fitness` before `return total;` add:

```javascript
    total -= this._escapePenalty(this.escapeCount(party, combos));
```

- [ ] **Step 8: Parity, golden, forge, provenance**

Run: `py -3 tests/test_js_parity.py`; `py -3 tests/test_golden.py`; `py -3 tests/test_forge.py`; `py -3 tests/test_provenance.py`
Expected: parity 60/60; provenance exit 0; golden and forge pass counts unchanged. One caveat: F1 and V5f pin pick score == comp_score delta, and until Task 3 prices the floor into the candidate those two can disagree on a roster at 10+ where the candidate changes the escape count. Both pins sit at Castle Outpost 7 today, where the floor is unarmed, so they hold. If either fails here, do not commit; continue to Task 3 and commit Tasks 2 and 3 together at Task 3's end.

- [ ] **Step 9: Commit**

Message (`msg2.txt`):

```
Engine: escape_heal seat floor row, party penalty, display read

Every content template carries hard_floors.escape_heal (min_party_size
10, min_members 1, penalty_mult 0.5 of the base heal_sustain weight).
fitness pays it when fewer members than min_members satisfy the
predicate; the read is weapon+loadout, worn gear never counts.
escape_floor() is the display read. V8 pins it. Both ports.

```

Run: `git add engine/engine.py engine/app_scoring.js pipeline/templates/*.yaml pipeline/out/dataset-latest.json tests/test_validation_modes.py; git commit -F <msg2.txt>`

---

### Task 3: The candidate delta and the explain term, both ports

**Files:**
- Modify: `engine/engine.py:2380-2423` (`party_state`), `:2593-2613` (`_combo_score`), `_combo_score_dressed` (after line 2613), `:2742-2760` (`explain`)
- Modify: `engine/app_scoring.js:2058-2102` (`partyState`), `:2181-2192` (`_comboScore`), `:2333-2350` (`_comboScoreDressed`), `:2452-2476` (`explain`)
- Test: `tests/test_golden.py` (T50), `tests/test_js_parity.py` (two directed cases)

**Interfaces:**
- Consumes: `_escape_floor`, `escape_count`, `_escape_penalty` from Task 2.
- Produces: `party_state()["escape_count"]`; `Engine._escape_delta(state, weapon, combo) -> float` (penalty(count) - penalty(count+1 if the combo satisfies), 0.0 when unarmed); `explain()` emits a term `{"cap": "escape_heal", ...}` when the delta exceeds 0.05. JS: `state.escapeCount`, `_escapeDelta`.

- [ ] **Step 1: Write the failing golden test**

In `tests/test_golden.py` `run()`, after the T49 block, add:

```python
    # T50 — the escape-healer seat floor (spec notes/specs/2026-09-21-
    # escape-healer-floor-design.md): at 10+ one healer must carry an
    # escape on the weapon itself; while that floor is open the mobile
    # healer wins the healer seat over the stationary one, dressed and
    # naked. Below 10 the floor is not armed and the healer ranking is
    # the heal rows' own.
    import gear_join as _gj50
    e12 = Engine(content="blackzone_roam", size=12)
    core12 = ["2H_HAMMER_AVALON", "2H_POLEHAMMER", "2H_MACE", "MAIN_HAMMER",
              "2H_ARCANESTAFF_HELL", "2H_ARCANESTAFF", "2H_AXE_AVALON",
              "MAIN_CURSEDSTAFF_CRYSTAL", "2H_KNUCKLES_SET3",
              "2H_FIRE_RINGPAIR_AVALON", PERMAFROST]
    doc12 = _gj50.doctrine_gears(e12, core12)
    rank = lambda recs, w: [r["weapon"] for r in recs].index(w) + 1  # noqa: E731
    dressed12 = e12.recommend(core12, 200, gears=doc12)
    e12.set_dressing(False)
    naked12 = e12.recommend(core12, 200)
    e12.set_dressing(True)
    top_d = dressed12[0]["weapon"]
    check("T50a at 12 with the escape floor open, Hallowfall outranks Great "
          "Holy dressed and naked, and is the top pick",
          rank(dressed12, HALLOWFALL) < rank(dressed12, GREAT_HOLY)
          and rank(naked12, HALLOWFALL) < rank(naked12, GREAT_HOLY)
          and top_d == HALLOWFALL,
          f"dressed HF r{rank(dressed12, HALLOWFALL)} GH r{rank(dressed12, GREAT_HOLY)}; "
          f"naked HF r{rank(naked12, HALLOWFALL)} GH r{rank(naked12, GREAT_HOLY)}; top={top_d}")
    terms = e12.explain(core12, HALLOWFALL, gears=doc12)
    check("T50b the explain terms name the seat floor for the Hallowfall pick",
          any(t["cap"] == "escape_heal" for t in terms),
          f"terms={[t['cap'] for t in terms]}")
    # exact-marginal invariant with the floor: pick score == comp_score delta
    r0 = dressed12[0]
    d0 = (e12.comp_score(core12 + [r0["weapon"]], [None] * len(core12) + [r0["combo"]],
                         doc12 + [r0["kit"] or None])
          - e12.comp_score(core12, None, doc12))
    check("T50c pick score == dressed comp_score delta at 1e-9 with the seat floor",
          abs(d0 - r0["score"]) < 1e-9, f"score={r0['score']!r} delta={d0!r}")
    check("T50d Castle Outpost at 7 does not arm the floor; the explain terms "
          "carry no escape_heal term",
          E._escape_floor is None
          and not any(t["cap"] == "escape_heal"
                      for t in E.explain([LONGBOW, WITCHWORK, PERMAFROST], HALLOWFALL)),
          "")
```

`gear_join` lives in `pipeline/`; confirm `sys.path` in test_golden already includes it (grep `pipeline` in the file's imports; if absent add `sys.path.insert(0, os.path.join(ROOT, "pipeline"))` beside the engine path insert).

- [ ] **Step 2: Run it to confirm it fails**

Run: `py -3 tests/test_golden.py`
Expected: T50a `FAIL` (Great Holy still first) and T50b `FAIL`; T50c may pass or fail; T50d passes.

- [ ] **Step 3: Python `party_state`, `_escape_delta`, combo scores, `explain`**

In `party_state`'s returned dict add one key (after `"party": list(party),`):

```python
                # seat floor: members satisfying escape_heal now
                "escape_count": self.escape_count(party, combos),
```

Add the method beside `_escape_penalty`:

```python
    def _escape_delta(self, state, weapon, combo):
        """Exact seat-floor delta of adding `weapon` with `combo`: the
        penalty now minus the penalty after (the combo decides whether
        the candidate satisfies). 0.0 when the floor is not armed."""
        if self._escape_floor is None:
            return 0.0
        n = state["escape_count"]
        n2 = n + (1 if self.ESCAPE_HEAL in self._pred_contrib(weapon, combo) else 0)
        return self._escape_penalty(n) - self._escape_penalty(n2)
```

In `_combo_score`, replace the final `return` with:

```python
        if self._escape_floor is not None:
            d_fit = d_fit + self._escape_delta(state, weapon, i)
        return self.alpha * d_fit + self.beta * d_syn, d_fit, d_syn
```

In `_combo_score_dressed`, the same two lines before its `return`.

In `explain`, before `return sorted(terms, ...)`:

```python
        ed = self._escape_delta(state, candidate, combo)
        if ed > 0.05:
            n = state["escape_count"]
            terms.append({"delta": round(ed, 2), "cap": self.ESCAPE_HEAL,
                          "before": n, "after": n + 1,
                          "target": self._escape_floor[0]})
```

- [ ] **Step 4: Run golden and forge**

Run: `py -3 tests/test_golden.py`; `py -3 tests/test_forge.py`; `py -3 tests/test_validation_modes.py`
Expected: T50a-d `ok`; F1 and V5f (pick == delta) `ok`; every earlier pin unchanged. If an earlier golden case at 10+ moves, record which in the log entry (Task 6) — a moved pin is a finding, and the plan's assumption is that none moves because every pinned 10+ roster already fields Hallowfall.

- [ ] **Step 5: JS mirror**

`partyState` returned object: add `escapeCount: this.escapeCount(party, combos),` after `party: party.slice(),`.

Add beside `_escapePenalty`:

```javascript
  CompEngine.prototype._escapeDelta = function (state, weapon, combo) {
    /* mirrors engine.py _escape_delta */
    if (this._escapeFloor === null) return 0.0;
    var n = state.escapeCount;
    var n2 = n + (this._predContrib(weapon, combo)[this.ESCAPE_HEAL] ? 1 : 0);
    return this._escapePenalty(n) - this._escapePenalty(n2);
  };
```

`_comboScore`: before `return { val: ... }` add `if (this._escapeFloor !== null) dFit = dFit + this._escapeDelta(state, weapon, i);`. `_comboScoreDressed`: the same line before its `return`.

`explain`: before `return terms.sort(...)`:

```javascript
    var ed = this._escapeDelta(state, candidate, pick.combo);
    if (ed > 0.05) {
      var n0 = state.escapeCount;
      terms.push({ delta: Math.round(ed * 100) / 100, cap: this.ESCAPE_HEAL,
                   before: n0, after: n0 + 1, target: this._escapeFloor[0] });
    }
```

- [ ] **Step 6: Directed parity cases**

In `tests/test_js_parity.py` `make_cases`, before `return cases`, append:

```python
    # directed: the escape-healer seat floor at 12, Blight Staff with and
    # without its mobility spell (the combo decides membership)
    from engine import Engine as _E
    _e = _E(content="blackzone_roam", size=12)
    blight = "2H_NATURESTAFF_HELL"
    n_b = _combo_count(data, blight)
    on = next(i for i in range(n_b) if _e.ESCAPE_HEAL in _e._pred_contrib(blight, i))
    off = next(i for i in range(n_b) if _e.ESCAPE_HEAL not in _e._pred_contrib(blight, i))
    core = ["2H_HAMMER_AVALON", "2H_POLEHAMMER", "2H_MACE", "2H_ARCANESTAFF",
            "2H_AXE_AVALON", "2H_KNUCKLES_SET3", "2H_ICECRYSTAL_UNDEAD"]
    for combo in (on, off):
        cases.append({"content": "blackzone_roam", "size": 12, "style": "balanced",
                      "party": [blight] + core, "combos": [combo] + [None] * len(core),
                      "gears": None, "refine_pool": weapons[3::11]})
    return cases
```

Run: `py -3 tests/test_js_parity.py`
Expected: `62/62 parity cases identical`.

- [ ] **Step 7: Commit**

Message (`msg3.txt`):

```
Engine: the escape floor prices every candidate exactly, both ports

The per-combo candidate score adds the seat floor's exact delta (penalty
now minus penalty after; the combo decides Blight's membership) so pick
score stays the comp_score delta at 1e-9. explain names the term. T50
pins Hallowfall over Great Holy at 12 dressed and naked and Castle
Outpost 7 unarmed; two directed parity cases at 12.

```

Run: `git add engine/engine.py engine/app_scoring.js tests/test_golden.py tests/test_js_parity.py; git commit -F <msg3.txt>`

---

### Task 4: The generation minimum

**Files:**
- Modify: `pipeline/templates/composition.yaml:101-105` (five band rows at `min_size >= 10`)
- Test: `tests/test_forge.py` (new `t_escape_heal_forge`, F35)

**Interfaces:**
- Consumes: the `escape_heal` predicate in `_forge_ctx` (Task 1) — the forge counts it through `_forge_counts` with no further code.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_forge.py` and call `t_escape_heal_forge()` after `t_escape_heal_predicate()`:

```python
# --------------------------------------------- F35 escape healer generated
def t_escape_heal_forge():
    # From 10 the bands demand one escape healer; the primary-heal minimum
    # keeps priority and the healer typical bounds the bodies, so the
    # escape healer takes one of the typical healer seats.
    for st in ("balanced", "brawl", "clap", "kite"):
        e = Engine(content="blackzone_roam", size=20, style=st)
        r = e.forge(20)
        cnt = e.escape_count(r["party"], r["combos"])
        healers = sum(1 for w in r["party"] if e.role_of(w) == "healer")
        typ = (e._role_typical() or {}).get("healer")
        check(f"F35 {st} 20: the forged roster fields an escape healer within "
              "the healer typical and stays feasible",
              r["feasible"] and cnt >= 1 and (typ is None or healers <= max(typ, 1)),
              f"escape={cnt} healers={healers} typical={typ} party={r['party']}")
    e9 = Engine(content="blackzone_roam", size=9)
    band9 = e9._band or {}
    check("F35e below 10 no band carries the escape_heal minimum",
          "escape_heal" not in band9, f"band={sorted(band9)}")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `py -3 tests/test_forge.py`
Expected: at least one F35 style line `FAIL` with `escape=0`. If every F35 line already passes (the floor's penalty alone steers every style), say so in the commit message and still land Step 3: the band minimum is the feasibility guard the spec requires, and F35 then pins both.

- [ ] **Step 3: The band rows**

Edit the five rows in `composition.yaml` with `min_size` 10, 15, 20, 30, 45: append `, escape_heal: {min: 1}` inside each row's braces, e.g.:

```yaml
  - {min_size: 10, max_size: 14, healer: {min: 2, max: 3}, frontline: {min: 2, max: 5}, support: {max: 4}, ranged_aoe_core: {min: 2}, primary_heal: {min: 1}, escape_heal: {min: 1}}
```

Add above `constraint_bands:` a comment:

```yaml
# `escape_heal` minima (seat floor, hard_floors.escape_heal in every
# content template): from 10 one healer must carry an escape on the
# weapon itself. Counted like a predicate minimum; primary_heal keeps
# priority in the fill logic and the healer typical bounds the bodies.
```

Rebuild: `py -3 pipeline/build_dataset.py` (exit 0).

- [ ] **Step 4: Run forge, parity, golden, skeletons**

Run: `py -3 tests/test_forge.py`; `py -3 tests/test_js_parity.py`; `py -3 tests/test_golden.py`; `py -3 tests/test_skeletons.py`; `py -3 tests/test_provenance.py`
Expected: all exit 0; parity 62/62 (the forge cases at size 8 sit below the band).

- [ ] **Step 5: Commit**

Message (`msg4.txt`):

```
Composition: one escape healer generated from 10 (escape_heal minimum)

The constraint bands at min_size 10 and above carry escape_heal {min: 1},
counted through the predicate machinery like primary_heal. F35 pins a
forged 20 in four styles.

```

Run: `git add pipeline/templates/composition.yaml pipeline/out/dataset-latest.json tests/test_forge.py; git commit -F <msg4.txt>`

---

### Task 5: The audit line and the page note

**Files:**
- Modify: `pipeline/audit_style_rosters.py:95` (`PREDS`), `:504-518` (board columns)
- Modify: `dashboard/_app.js:832-841` (`renderRoster` notes)
- Test: `tests/test_dashboard_layout.py` (L25), then `py -3 dashboard/build.py`

**Interfaces:**
- Consumes: `ENG.escapeFloor(party, combos)` (Task 2), `ENG.predMembers[ENG.ESCAPE_HEAL]` (Task 1).

- [ ] **Step 1: Write the failing layout contract**

In `tests/test_dashboard_layout.py` before `if FAILURES:` add:

```python
# L25 - the escape-healer seat floor is a roster note the ENGINE reads:
# the page calls escapeFloor and lists the qualifying healers from the
# engine's own predicate view; it computes nothing
ren = seg(APP, "function renderRoster(){", "NOTES_HTML = notes.join", "L25 renderRoster anchors")
check("ENG.escapeFloor(party, COMBOS_CUR)" in ren
      and "ENG.predMembers[ENG.ESCAPE_HEAL]" in ren
      and "no healer carries its own escape" in ren
      and "worn boots never count" in ren,
      "L25 the roster note reads the seat floor from the engine and names the qualifying healers from its predicate view")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `py -3 tests/test_dashboard_layout.py`
Expected: `FAIL L25 ...`

- [ ] **Step 3: The note**

In `renderRoster`, after `if (inotes) notes.push(inotes);` add:

```javascript
  /* the escape-healer seat floor (hard_floors.escape_heal, armed at 10+):
     display only — the engine reads it, the page translates */
  const ef = ENG.escapeFloor(party, COMBOS_CUR);
  if (ef.armed && ef.count < ef.need){
    const who = Object.keys(ENG.predMembers[ENG.ESCAPE_HEAL]).map(nameOf).sort().join(", ");
    notes.push(`<div class="inote int-warning"><span class="fn">no healer carries its own escape — at ${SIZE} the typical winner fields one (${esc(who)}); worn boots never count</span></div>`);
  }
```

`inote int-warning` is the wrapper the interaction notices already use (`interactionNotices()`), so the note inherits their styling; no CSS change.

- [ ] **Step 4: The audit column**

In `pipeline/audit_style_rosters.py` add `"escape_heal"` to the `PREDS` tuple, and in the structure table add a column: header `| escape healer |` after `| main healer |`, separator one more `---|`, and the cell `fmt(pr["escape_heal"])` after `fmt(se.get("main_healer"))`. The script cannot run on this checkout (the party cache lives on the harvest machine): verify with `py -3 -m py_compile pipeline/audit_style_rosters.py` and state that in the commit.

- [ ] **Step 5: Build and gates**

Run: `py -3 dashboard/build.py`; `py -3 tests/test_dashboard_layout.py`; `py -3 tests/test_js_parity.py` (the embed check reads the built page); `node tests/test_display_math.js`
Expected: all exit 0.

- [ ] **Step 6: Smoke the note**

Serve `py -3 -m http.server 8765 --directory dashboard`, drive the built page over CDP (the recipe in the session tooling memory: chromium headless shell + Node WebSocket): load `#c=blackzone_roam&n=12&p=2H_HAMMER_AVALON,2H_POLEHAMMER,2H_MACE,MAIN_HAMMER,2H_ARCANESTAFF_HELL,2H_ARCANESTAFF,2H_AXE_AVALON,MAIN_CURSEDSTAFF_CRYSTAL,2H_KNUCKLES_SET3,2H_FIRE_RINGPAIR_AVALON,2H_ICECRYSTAL_UNDEAD,2H_HOLYSTAFF` and assert `document.querySelector('.roster-notes').textContent` contains "no healer carries its own escape"; then with `2H_HOLYSTAFF` replaced by `MAIN_HOLYSTAFF_AVALON` assert it does not. Screenshot to `.playwright-mcp/escape-note.png`.

- [ ] **Step 7: Commit**

Message (`msg5.txt`):

```
Dashboard and audit: the escape-healer floor as a roster note and a board column

The page reads escapeFloor from the embedded engine and names the
qualifying healers from its predicate view (L25). The style-roster audit
counts escape_heal per band beside the seat rows (report-only; runs on the
harvest checkout).

```

Run: `git add dashboard/_app.js dashboard/index.html docs/index.html pipeline/audit_style_rosters.py tests/test_dashboard_layout.py; git commit -F <msg5.txt>`

---

### Task 6: The rule, the decision and the full gate list

**Files:**
- Modify: `CLAUDE.md:229-231`, `HANDOFF.md:68-71`, `tests/VALIDATION.md` (standing rule 19 after rule 18, one index row after the 09-21 V3 row), `notes/validation/2026-09b.md` (append), `BACKLOG.md:26-33`, `notes/specs/2026-09-21-escape-healer-floor-design.md:3` (status line)

- [ ] **Step 1: CLAUDE.md invariant**

After the "Structural floors are source-aware" bullet add:

```markdown
- **One healer carries its own escape at 10+**: the seat floor `escape_heal`
  (a healer whose resolved loadout supplies mobility or disengage at 2
  sheet points) is charged in fitness and demanded by the bands from size
  10; worn boots and chests never satisfy it; below 10 it never arms.
```

- [ ] **Step 2: HANDOFF.md**

In the Fitness bullet (line 68) after "hard floors on the weapon+loadout basis," insert "the escape-healer seat floor at 10+ (`hard_floors.escape_heal`, a member count on the same basis),".

- [ ] **Step 3: VALIDATION.md standing rule and index row**

After rule 18's last line (before `## The method`), add:

```markdown
19. **One healer carries its own escape at 10+** (2026-09-21): the seat
    floor `escape_heal` (flag predicate: primary seat class healer, resolved
    loadout mobility or disengage >= 2 sheet points; worn gear never
    counts) is charged in fitness from size 10 (`min_members` 1,
    `penalty_mult` 0.5 of the base heal_sustain weight, PROVISIONAL) and
    demanded by the constraint bands. Training-split killer parties field
    one in 85% at 10-14, 95% at 15-19, 97% at 20+, 50% at 6-8: the floor
    never arms below 10, and the Castle Outpost 7 healer miss stays the
    prior-weight question. Spec `notes/specs/2026-09-21-escape-healer-
    floor-design.md`.
```

After the `| 09-21 | V3 round 2, Castle Outpost 7 ...` row add:

```markdown
| 09-21 | The escape-healer seat floor: from 10 one healer must carry an escape on the weapon itself (escape_heal predicate, hard_floors row, band minimum; gear never counts); armed at 10 on the training-split shares 85 / 95 / 97%, never below (50% at 6-8). Hallowfall's sheet stands (its E heals 135 per 30s; Holy Explosion about 500 per 18s). The 7-man miss stays open | both ports, six templates, composition.yaml, audit, page | T50, F34/F35, V8, L25, parity 62 | 09b, The escape-healer seat floor |
```

- [ ] **Step 4: The log entry**

Append to `notes/validation/2026-09b.md`:

```markdown

## 2026-09-21 — The escape-healer seat floor

**Context.** V3 round 2 (Castle Outpost 7, reviewed draft) traced every
healer miss to the party's disengage and mobility rows being met by worn
kit alone, so a weapon's own escape was worth nothing once the party was
dressed. Two causes were put to a decision: the shoes saturating the
utility rows, and Hallowfall's heal sheet. The spell facts settle the
second against the sheet (Divine Intervention heals 135 once per 30s;
Holy Explosion about 500 per ally per 18s; the shared Holy Flash 117 per
3.5s is scored 4 where the E is scored 6). A row-level fix was measured
on the reviewed form: gear removed from the two rows with targets as
fitted lifts dressed top-3 to 58% only by making a target of 7
unreachable; re-fitted to weapon-only medians it falls to 33%.

**Decision.** A seat-level floor: from size 10 one healer must carry an
escape on the weapon itself (standing rule 19). Grounded on the training
split: fully known killer parties with a healer field one in 85% at
10-14, 95% at 15-19, 97% at 20+; 50% at 6-8 and 73% at 9, so the floor
never arms below 10. Uniform across labelled styles. "Every healer" is
not the rule (46% at 10-14, 25% at 20+). The escape reads the weapon's
own sheet and spell pool on the resolved loadout (Hallowfall on the E,
Blight only with its mobility spell), never worn boots or chests, which
give every healer a baseline escape.

**Evidence.** The training-split table in the spec; the dressed template
audit (weapon-only mobility 0 / 1 / 6 units against dressed 6 / 7 / 15
in the three Castle Outpost comps); the sensitivity map above.

**Changes.** `engine/engine.py`, `engine/app_scoring.js` (predicate,
floor, exact candidate delta, explain term, display read); the six
content templates (`hard_floors.escape_heal`); `composition.yaml` (band
minima from 10); `audit_style_rosters.py` (board column);
`dashboard/_app.js` (roster note). Pins: T50, F34, F35, V8, L25, two
directed parity cases. Spec `notes/specs/2026-09-21-escape-healer-floor-
design.md`; plan `notes/plans/2026-09-21-escape-healer-floor.md`. Golden
rows moved: none (record any that did).
```

- [ ] **Step 5: BACKLOG and spec status**

Replace the "Healer pricing at 7" item in BACKLOG's decision list with, under "Needs evidence a round would produce":

```markdown
- **The Castle Outpost 7 healer miss** (V3 round 2): the escape-healer
  seat floor (rule 19) arms at 10, not 7 (50% of 6-8 winners). What
  remains at 7 is the prior-weight question: Hallowfall is the most
  fielded of several viable healers and the meta prior cannot close a
  one-point fit gap. Waits on validation rounds (rule 16). (V: 09b, The
  escape-healer seat floor)
```

Change the spec's status line to `Status: implemented (plan notes/plans/2026-09-21-escape-healer-floor.md).`

- [ ] **Step 6: The full gate list**

Run every line of the CLAUDE.md gate list in order, bare (no pipes), and read each exit code:

```
py -3 tests/test_golden.py
py -3 tests/test_forge.py
py -3 tests/test_builds.py
py -3 tests/test_interactions.py
py -3 tests/test_provenance.py
py -3 tests/test_patch_history.py
py -3 tests/test_js_parity.py
py -3 tests/test_dashboard_layout.py
py -3 tests/test_cohort_families.py      # from PowerShell
py -3 tests/test_roles.py
py -3 tests/test_validation_modes.py
py -3 tests/test_meta_pairs.py
py -3 tests/test_skeletons.py
py -3 tests/test_tone.py                 # pre-existing: VALIDATION.md 53 lines, test_tone.py 2 — no NEW file may appear
py -3 pipeline/evidence_lint.py
node tests/test_loadout_codec.js
node tests/test_display_math.js
node tests/test_live_party.js
py -3 tests/tier2_blindtest.py v4
py -3 tests/tier2_blindtest.py v4h --rebuild 5     # report-only: record role-level before/after in the log entry
```

Expected: every gate exit 0 except tone's pre-existing two files; `v4` >= 70% role-level. Record the `v4` and `v4h` numbers in the log entry's Evidence paragraph.

- [ ] **Step 7: Commit**

Message (`msg6.txt`):

```
Rule 19: one healer carries its own escape at 10+ (docs, log, index)

Standing rule 19, the decision entry, the index row, the CLAUDE.md
invariant, the HANDOFF fitness line, the BACKLOG item re-scoped to the
prior-weight question, the spec status.

```

Run: `git add CLAUDE.md HANDOFF.md tests/VALIDATION.md notes/validation/2026-09b.md BACKLOG.md notes/specs/2026-09-21-escape-healer-floor-design.md notes/plans/2026-09-21-escape-healer-floor.md; git commit -F <msg6.txt>`

Do not push; the maintainer pushes.
