# Target Is The Median — Implementation Plan

> Executed 2026-09-10 inline (branch `target-median`). Deviations are listed at the top of the spec; the four-stage `min` line was added to Tasks 1, 3, 4 and 5 mid-execution.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every capability target — harvest band rows and hand-fitted content rows — becomes the median of what winning parties field, the board labels it as "typical", and thin rows say so.

**Architecture:** The scoring formula is untouched; only the number `target` holds moves. The harvest derivation (`derive_style_bands.py`) writes p50 instead of 0.9×p10 and gains a pooled `balanced` cell; the engine (Python + JS port) lets `balanced` read its band and exposes a descriptive `target_source(cap)`; the content templates are re-fit to the median of their fitted comps by a new reusable script and carry a `fit:` block; the dashboard relabels and chips rows from `target_source`, and the SIZE stepper follows the roster.

**Tech Stack:** Python 3 (`py -3`), Node (parity + codec tests), YAML templates, single-file dashboard built by `dashboard/build.py`.

**Spec:** `notes/specs/2026-09-10-target-is-the-median-design.md`

## Global Constraints

- Windows: `py -3` only; every committed-artifact writer opens with `newline="\n"`; never pipe a build through `grep`/`Select-Object` where `$LASTEXITCODE` is read.
- `engine/app_scoring.js` reads as binary to ripgrep — search with `Select-String`, read with the Read tool.
- Tests are script-style: run directly, exit 0 = pass; read the output.
- Engine change = both `engine/engine.py` and `engine/app_scoring.js`, then `py -3 tests/test_js_parity.py`.
- Never hand-edit `dashboard/index.html` / `docs/index.html` / `templates/style_bands.yaml` / `out/*.json` — they are generated.
- Descriptive layers never score: `target_source` is display provenance only; nothing reads it in a scoring path.
- No invented numbers: a row without a measured median keeps its current value and is labelled.
- The raw party cache is NOT on this checkout: `audit_style_rosters.py` cannot run here. Code it, test it on a fixture, and record that the harvest checkout regenerates the board.
- The tree carries unrelated uncommitted work (F29 need-bound fix, 2026-09-10). Do not revert it; do not fold it into these commits — commit only the files each task touches.

---

### Task 1: Harvest derivation writes the median (+ pooled `balanced` when present)

**Files:**
- Modify: `pipeline/derive_style_bands.py` (constants at lines 63-72, docstring, header lines, row loop at lines 148-170)
- Create: `tests/test_style_bands_derive.py`

**Interfaces:**
- Produces: `derive_style_bands.derive(board_doc) -> list[str]` (the YAML lines; `main()` becomes load → `derive` → write) so a test can run it on a fixture without touching `out/`. Convention constants `TARGET_OF_P50 = 1.0`, `SOFT_OF_P90 = 1.15`, `MIN_DISTINCT = 40`. `STYLES` gains `"balanced"` at the front; `PARENT` unchanged (balanced has none).
- YAML output: `convention: {target_of_p50: 1.0, soft_of_p90: 1.15, min_distinct: 40}`; per-row comment keeps `p10/p50/p90`; a row whose p50 is 0 writes `{soft_cap: X}   # p10/p50/p90 …; most winners field none, content target stands`.

- [x] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
"""derive_style_bands contracts (2026-09-10, target is the median).

Script-style, not pytest. Runs derive() on a fixture evidence board.
    py -3 tests/test_style_bands_derive.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import derive_style_bands as dsb  # noqa: E402

FAILS = []
def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("\n      " + detail) if detail else ""))
    if not cond:
        FAILS.append(name)

def cell(distinct, supply, ref=12):
    return {"distinct": distinct, "size_ref": ref, "supply": supply}

def stat(p10, p50, p90, zero=0.0):
    return {"n": 100, "p10": p10, "p50": p50, "p90": p90, "zero_share": zero}

board = {
    "kite|10-14": cell(201, {
        "heal_burst": stat(1.2, 5.8, 11.0, zero=0.10),   # >5% zeros, p50 > 0
        "silence":    stat(0.0, 0.0, 4.0,  zero=0.60),   # p50 == 0
        "peel":       stat(9.0, 20.0, 50.0),
        "anti_zone":  stat(0.0, 0.0, 0.0),               # p90 == 0 -> no row
    }),
    "balanced|10-14": cell(900, {"heal_burst": stat(2.0, 6.5, 12.0)}),
    "kite|15-19": cell(10, {"heal_burst": stat(5.8, 10.3, 16.4)}),   # thin -> borrows
}
doc = {"_generated": "2026-09-10", "rosters_total": 1000, "board": board}
lines = dsb.derive(doc)
text = "\n".join(lines)

def row(style, band, cap):
    """the requirement line for cap inside bands: style: "band":"""
    i = text.index(f"  {style}:")
    j = text.index(f'    "{band}":', i)
    k = text.find("\n    \"", j + 1)
    k2 = text.find(f"\n  ", j + 1)
    seg = text[j:(k if k > 0 else len(text))]
    for ln in seg.splitlines():
        if ln.strip().startswith(cap + ":"):
            return ln
    return ""

hb = row("kite", "10-14", "heal_burst")
check("D1 target is the median (p50), not 0.9 x p10",
      "target:    5.80" in hb, hb)
check("D2 soft cap stays 1.15 x p90", "soft_cap:   12.65" in hb, hb)
check("D3 a >5% zero share no longer suppresses the target",
      "target:" in hb and "no minimum" not in hb, hb)
si = row("kite", "10-14", "silence")
check("D4 p50 == 0 writes the soft cap only, content target stands",
      "target:" not in si and "soft_cap:    4.60" in si
      and "most winners field none" in si, si)
check("D5 zero p90 writes no row", row("kite", "10-14", "anti_zone") == "")
check("D6 convention line names p50 and carries no zero-share knob",
      "convention: {target_of_p50: 1.0, soft_of_p90: 1.15, min_distinct: 40}" in text)
check("D7 the balanced cell is emitted like any style",
      "target:    6.50" in row("balanced", "10-14", "heal_burst"))
check("D8 a thin cell borrows its nearest filled band",
      'borrowed_from: "kite|10-14"' in text)
check("D9 the row comment keeps p10/p50/p90 for the reader",
      "# p10/p50/p90 1.2/5.8/11.0" in hb)

if FAILS:
    print(f"\n{len(FAILS)} failed: {', '.join(FAILS)}")
    sys.exit(1)
print("\nall derive contracts pass")
sys.exit(0)
```

- [x] **Step 2: Run it to verify it fails**

Run: `py -3 tests/test_style_bands_derive.py`
Expected: traceback `AttributeError: module 'derive_style_bands' has no attribute 'derive'`.

- [x] **Step 3: Refactor `main()` into `derive(ev)` and switch the convention**

Replace lines 63-72 (constants) with:

```python
STYLES = ("balanced", "brawl", "clap", "kite", "brawl_clap", "clap_kite")
BANDS = (("10-14", 10, 14, 12), ("15-19", 15, 19, 17), ("20", 20, 99, 20))
PARENT = {"brawl_clap": "brawl", "clap_kite": "clap"}
MIN_DISTINCT = 40
EXCLUDED = ()   # none since 2026-09-04 (see docstring, rule 3)
TARGET_OF_P50 = 1.0     # target IS the median (owner 2026-09-10)
SOFT_OF_P90 = 1.15
```

Split `main()`: everything from `board = ev["board"]` to the `lines` list becoming complete moves into `def derive(ev):` returning `lines`; `main()` becomes:

```python
def main():
    if not os.path.exists(EVIDENCE):
        sys.exit("no evidence board - run audit_style_rosters.py first")
    with open(EVIDENCE, encoding="utf-8") as f:
        ev = json.load(f)
    lines = derive(ev)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {os.path.relpath(TARGET, HERE)}")
    for ln in lines:
        if ln.startswith("    \"") or ln.startswith("      borrowed_from"):
            print("  " + ln.strip())
```

(The old per-cell `summary` print is replaced by echoing the band and borrowed lines — same information, no second bookkeeping list.)

Inside `derive`, the header comment lines that mention the convention become:

```python
        "# content row - a zero p90 is 'we do not know', never a number; a zero",
        "# p50 (most winners field none) writes the soft cap only and the",
        "# content target stands.",
        f"# Convention (owner 2026-09-10, 'the data should come from the harvest",
        f"# median'): target = {TARGET_OF_P50} x p50 - the TYPICAL winner, the number",
        f"# to aim for - and soft_cap = {SOFT_OF_P90} x p90. Until 2026-09-10 the target",
        "# was 0.9 x p10, the LEAST any winner fielded: every row overshot and the",
        "# score gave full credit at the floor (one healer 'covered' 15 people).",
        f"# Cells with fewer than {MIN_DISTINCT} distinct rosters borrow their nearest",
```

and the `convention:` line becomes:

```python
        f"convention: {{target_of_p50: {TARGET_OF_P50}, soft_of_p90: {SOFT_OF_P90}, min_distinct: {MIN_DISTINCT}}}",
```

Also drop the two header lines about `balanced` never reading a band, replacing them with:

```python
        "# rows since the 2026-08-29 unit re-fit). Hard floors are untouched",
        "# (weapon units, content facts); weights are untouched (styles.yaml).",
        "# `balanced` reads the POOLED cell (every winner at the size, any style)",
        "# when the audit has written one. A capability absent from a cell keeps the",
```

The row loop becomes:

```python
            for cap in sorted(e["supply"]):
                if cap in EXCLUDED:
                    continue
                s = e["supply"][cap]
                p10, p50, p90 = (s.get("p10") or 0.0, s.get("p50") or 0.0,
                                 s.get("p90") or 0.0)
                if p90 <= 0:
                    continue
                target = round(TARGET_OF_P50 * p50, 2)
                soft = round(SOFT_OF_P90 * p90, 2)
                if soft <= target:
                    continue
                if target > 0:
                    lines.append(f"        {cap + ':':<20}{{target: {target:>7.2f}, soft_cap: {soft:>7.2f}}}"
                                 f"   # p10/p50/p90 {p10:.1f}/{p50:.1f}/{p90:.1f}")
                else:
                    lines.append(f"        {cap + ':':<20}{{soft_cap: {soft:>7.2f}}}"
                                 f"   # p10/p50/p90 {p10:.1f}/{p50:.1f}/{p90:.1f};"
                                 f" most winners field none, content target stands")
```

Update the module docstring: replace the convention sentence in the first paragraph with "under the standing convention (target = p50, the typical winner; soft cap 1.15 x p90 …)", replace the paragraph starting "A capability whose p10 is zero" through "…the test is the zero share, not the ratio." with:

```
A capability whose p90 is zero in a cell gets NO row (the content row
stands) — never invent a number to fill a hole. A capability whose p50 is
zero (most winners field none) carries the soft cap only and the content
target stands. The 2026-09-09 zero-share rule is retired with the p10
convention it protected: the median does not sit on the edge of the zero
mass (kite|10-14 heal_burst: 10% zeros, p50 5.8, stable across folds).
`balanced` reads a POOLED cell — every winning roster at the size, any
style — written by audit_style_rosters.py; before the audit runs on the
harvest checkout the cell is absent and balanced keeps the content row.
```

Remove `ZERO_SHARE_MAX` entirely (constant, header line, convention line).

- [x] **Step 4: Run the test**

Run: `py -3 tests/test_style_bands_derive.py`
Expected: `all derive contracts pass`, exit 0.

- [x] **Step 5: Regenerate the real YAML from the committed board and eyeball it**

Run: `py -3 pipeline/derive_style_bands.py`
Then: `git diff --stat pipeline/templates/style_bands.yaml` and spot-check `kite` `15-19` `heal_burst` reads `target: 10.26, soft_cap: 18.92` and no `balanced:` block appears (the committed board has no pooled cell yet).

- [x] **Step 6: Commit**

```
git add pipeline/derive_style_bands.py pipeline/templates/style_bands.yaml tests/test_style_bands_derive.py
git commit -F <bom-less file>: "Style bands: target is the harvest median (p50), not 0.9 x p10"
```

---

### Task 2: The audit writes a pooled `balanced` cell

**Files:**
- Modify: `pipeline/audit_style_rosters.py:342-392` (the per-style × band aggregation loop)

**Interfaces:**
- Produces: `out/style_roster_evidence.json` `board["balanced|<band>"]` with the same entry shape as every style cell, aggregated over EVERY roster in the band (labelled or not). Only runnable on the harvest checkout; here only the syntax check and the fixture test from Task 1 cover it.

- [x] **Step 1: Add the pooled style to the loop**

At line 342 change:

```python
    styles = sorted({r["style"] for r in rosters if r["style"]})
```

to:

```python
    styles = sorted({r["style"] for r in rosters if r["style"]})
    # POOLED cell (owner 2026-09-10, target is the median): `balanced` is
    # "every winner at this size, whatever it was playing" — labelled and
    # unlabelled rosters alike. Same dedupe, same stats, same MIN_DISTINCT
    # downstream; derive_style_bands emits it like any style.
    styles.append("balanced")
```

and at line 347 change:

```python
            rs = [r for r in rosters
                  if r["style"] == style and lo <= r["size"] <= hi]
```

to:

```python
            rs = [r for r in rosters
                  if (style == "balanced" or r["style"] == style)
                  and lo <= r["size"] <= hi]
```

The `entry["current"]` block sets `e.set_content(content, ref, style)` — `balanced` is a legal style there already.

- [x] **Step 2: Syntax-check (the script cannot run here)**

Run: `py -3 -m py_compile pipeline/audit_style_rosters.py`
Expected: no output, exit 0.

- [x] **Step 3: Record the deferred step**

Append to `BACKLOG.md` under "## Engineering work, unblocked":

```
- [x] **Regenerate the evidence board on the harvest checkout** (`py -3
  pipeline/audit_style_rosters.py` then `derive_style_bands.py`,
  `build_dataset.py`, the gates) so `balanced` gets its pooled median rows
  (2026-09-10 target-is-the-median; the raw party cache is not on the C:
  checkout). Until then `balanced` keeps the median-fitted content rows,
  labelled `content` on the board.
```

- [x] **Step 4: Commit**

```
git add pipeline/audit_style_rosters.py BACKLOG.md
git commit: "Style roster audit: pooled balanced cell (every winner at the size)"
```

---

### Task 3: Engine — `balanced` reads its band; `target_source(cap)`; parity

**Files:**
- Modify: `engine/engine.py:381-413` (band block in `set_content`), add method after `soft_cap` (line 763)
- Modify: `engine/app_scoring.js:334-363` (band block), add `targetSource` next to `softCap`
- Modify: `tests/test_forge.py` (new `t_target_source`, registered before `t_min_need_disjoint_seats()` at line 1099)
- Modify: `tests/test_js_parity.py:191` area (payload) and the compare loop at ~line 285; `tests/js_parity_runner.js:95` area

**Interfaces:**
- Produces: `Engine.target_source(cap) -> str` in `{"harvest", "harvest_borrowed", "content", "content_min"}`; JS `targetSource(cap)` identical. `Engine.band_row` may now be set for `style == "balanced"`.
- Reads: `self.template.get("fit")` = `{"comps": int, "stat": "median"|"minimum"|"none"}` (Task 4 adds it to the YAML; absent → treated as `"minimum"`, i.e. `content_min`, so the engine is honest on a pre-fit dataset).

- [x] **Step 1: Write the failing tests (test_forge.py)**

Add before `# --- F10 locks` (or anywhere among the t_ functions):

```python
# ---------------------------------------------------- F30 target provenance
def t_target_source():
    """Target is the median (owner 2026-09-10). A declared style at 10+
    reads the harvest cell; balanced reads its pooled cell when the
    board carries one; every row says where its target came from —
    display provenance, never a scoring input."""
    e = Engine(content="castle_outpost", size=15, style="kite")
    srcs = {c: e.target_source(c) for c in e.reqs}
    check("F30a a harvest-targeted row reports 'harvest'",
          srcs.get("heal_burst") == "harvest", str(srcs.get("heal_burst")))
    fit = (e.template.get("fit") or {}).get("stat")
    want = "content" if fit == "median" else "content_min"
    check("F30b a soft-cap-only harvest row falls back to the content row's provenance",
          e.target_source("interrupt") == want
          if "interrupt" in e.band_row["requirements"]
          and e.band_row["requirements"]["interrupt"].get("target") is None
          else True)
    check("F30c every source is one of the four words",
          all(v in ("harvest", "harvest_borrowed", "content", "content_min")
              for v in srcs.values()), str(srcs))
    # balanced reads a pooled band when — and only when — the board has one
    eb = Engine(content="castle_outpost", size=15, style="balanced")
    has_pool = "balanced" in ((eb.data.get("style_bands") or {}).get("bands") or {})
    check("F30d balanced reads its pooled band iff the board carries one",
          (eb.band_row is not None) == has_pool,
          f"has_pool={has_pool} band_key={eb.band_key}")
    # below min_size nothing reads a band
    es = Engine(content="castle_outpost", size=7, style="kite")
    check("F30e below min_size every row is content-sourced",
          es.band_row is None and all(
              es.target_source(c) in ("content", "content_min") for c in es.reqs))
    # the median actually moves the pick: kite 15-19 heal_burst p50 is
    # ~2x the old floor, so two healers no longer 'cover' fifteen
    check("F30f kite at 15 asks for more than one healer's heal_burst",
          e.target("heal_burst") > 8.0, f"{e.target('heal_burst'):.2f}")
```

Register it: add `t_target_source()` after `t_min_need_disjoint_seats()` in the run list.

- [x] **Step 2: Run to verify failure**

Run: `py -3 tests/test_forge.py`
Expected: `AttributeError: 'Engine' object has no attribute 'target_source'`.

- [x] **Step 3: Implement in engine.py**

In `set_content`, replace the band block (from `self.band_row = None` through the `if self.band_row:` loop) with:

```python
        # STYLE x SIZE ROWS (templates/style_bands.yaml, owner ruling
        # 2026-09-04 after blind rounds 1+2; TARGET IS THE MEDIAN, owner
        # 2026-09-10): at min_size+, the harvest's per-style x band
        # target/soft cap replaces the content row's for the capabilities
        # the cell lists, scaled linearly from the cell's ref_size (person
        # units both). The target is what the TYPICAL winner fields (p50);
        # a soft-cap-only row (most winners field none) keeps the content
        # target and takes the harvest soft cap when it clears that target.
        # `balanced` reads the POOLED cell (every winner at the size) when
        # the audit has written one; before that it keeps the content row.
        # The rows are MEASURED PER STYLE, so styles.yaml target_mults do
        # not stack on them. Hard floors and weights are untouched; below
        # min_size the content row (with its target_mults) stands. The cell
        # is exposed as `band_row` for display, never a second scorer.
        # `_target_src` records per capability where the effective target
        # came from (display provenance only — the board's "typical" /
        # "min" chips read it; nothing in scoring does).
        self.band_row = None
        self.band_key = None
        fit_stat = ((self.template.get("fit") or {}).get("stat") or "minimum")
        content_src = "content" if fit_stat == "median" else "content_min"
        self._target_src = {c: content_src for c in self.reqs}
        bands = self.data.get("style_bands") or {}
        if (style in (bands.get("bands") or {})
                and self.size >= (bands.get("min_size") or 10)):
            for bk, row in (bands["bands"][style] or {}).items():
                lo, hi = row["sizes"]
                if lo <= self.size <= hi:
                    self.band_row, self.band_key = row, bk
                    break
        if self.band_row:
            ref = float(self.band_row["ref_size"])
            harvest_src = ("harvest_borrowed" if self.band_row.get("borrowed_from")
                           else "harvest")
            for c, v in self.band_row["requirements"].items():
                if c not in self._targets:
                    continue
                if v.get("target") is not None:
                    self._targets[c] = v["target"] * self.size / ref
                    self._softs[c] = v["soft_cap"] * self.size / ref
                    self._target_src[c] = harvest_src
                else:
                    soft = v["soft_cap"] * self.size / ref
                    if soft > self._targets[c]:
                        self._softs[c] = soft
```

(The only behavioural change is dropping nothing: `balanced` was never excluded by code — the YAML simply had no `balanced` key. Confirm by reading: the old condition was `style in bands["bands"]`, which is the same test. So the engine change is `_target_src` only; the balanced behaviour arrives with the data.)

After `soft_cap`:

```python
    def target_source(self, cap):
        """Where this capability's effective target came from — DISPLAY
        provenance (owner 2026-09-10, target is the median): 'harvest'
        (this style x band's measured median), 'harvest_borrowed' (a thin
        cell borrowing its nearest), 'content' (the content row, re-fit
        to the median of its comps), 'content_min' (a content row still
        on the old 0.9 x least-comp minimum: thin or no comps). Never a
        scoring input."""
        return self._target_src[cap]
```

- [x] **Step 4: Implement in app_scoring.js**

Replace the band block (lines 334-363) with the mirror:

```js
    /* STYLE x SIZE ROWS (style_bands.yaml, owner 2026-09-04; TARGET IS
       THE MEDIAN, owner 2026-09-10; mirrors engine.py set_content): at
       min_size+ the harvest's per-band target (the TYPICAL winner, p50)
       and soft cap replace the content row's, scaled from ref_size; a
       soft-cap-only row keeps the content target; rows are measured per
       style, so target_mults do not stack on them. `balanced` reads the
       pooled cell when the board carries one. _targetSrc records per
       capability where the target came from — display provenance only. */
    this.bandRow = null; this.bandKey = null;
    var fitStat = ((this.template.fit || {}).stat) || "minimum";
    var contentSrc = (fitStat === "median") ? "content" : "content_min";
    this._targetSrc = {};
    for (var capS in this.reqs) this._targetSrc[capS] = contentSrc;
    var bands = this.data.style_bands || {};
    var bstyle = (bands.bands || {})[this.style];
    if (bstyle && this.size >= (bands.min_size || 10)) {
      for (var bk in bstyle) {
        var brow = bstyle[bk];
        if (brow.sizes[0] <= this.size && this.size <= brow.sizes[1]) {
          this.bandRow = brow; this.bandKey = bk; break;
        }
      }
    }
    if (this.bandRow) {
      var bref = this.bandRow.ref_size;
      var harvestSrc = this.bandRow.borrowed_from ? "harvest_borrowed" : "harvest";
      for (var capB in this.bandRow.requirements) {
        if (!(capB in this._targets)) continue;
        var bv = this.bandRow.requirements[capB];
        if (bv.target !== undefined && bv.target !== null) {
          this._targets[capB] = bv.target * this.size / bref;
          this._softs[capB] = bv.soft_cap * this.size / bref;
          this._targetSrc[capB] = harvestSrc;
        } else {
          var softB = bv.soft_cap * this.size / bref;
          if (softB > this._targets[capB]) this._softs[capB] = softB;
        }
      }
    }
```

Next to `softCap` (find with `Select-String -Pattern "softCap: function|softCap\(cap\)"`), add:

```js
  /* display provenance of a capability's target (mirrors engine.py
     target_source): harvest | harvest_borrowed | content | content_min */
  targetSource: function (cap) { return this._targetSrc[cap]; },
```

(match the surrounding method-definition style — prototype assignment or object literal — exactly as `softCap` is written.)

- [x] **Step 5: Add to parity**

`tests/test_js_parity.py`, in the Python payload dict next to `"size_bucket"`:

```python
            "target_source": {cap: e.target_source(cap) for cap in e.reqs},
```

and in the compare loop after the `size_bucket` check:

```python
        if a["target_source"] != b.get("target_source"):
            errs.append(f"target_source: py={a['target_source']} "
                        f"js={b.get('target_source')}")
```

`tests/js_parity_runner.js`, next to `size_bucket:`:

```js
    target_source: (() => { const o = {}; for (const cap in e.reqs) o[cap] = e.targetSource(cap); return o; })(),
```

- [x] **Step 6: Run the tests**

Run: `py -3 tests/test_forge.py` → all PASS including F30a-f (F30d will report `has_pool=False`, band_row None — passes).
Run: `py -3 tests/test_js_parity.py` → `60/60` parity, exit 0.
Run: `py -3 tests/test_golden.py` → note any flips (the dataset has NOT been rebuilt yet, so none expected here).

- [x] **Step 7: Commit**

```
git add engine/engine.py engine/app_scoring.js tests/test_forge.py tests/test_js_parity.py tests/js_parity_runner.js
git commit: "Engine: target_source() provenance; band rows documented as medians"
```

---

### Task 4: Content rows re-fit to the median of their comps; `fit:` blocks; build validation

**Files:**
- Create: `pipeline/refit_content_targets.py`
- Modify: `pipeline/templates/blackzone_roam.yaml`, `castle_outpost.yaml`, `roads.yaml`, `territory_defense.yaml`, `castle.yaml`, `faction_war.yaml` (a `fit:` block under `validated_sizes`; targets rewritten in the first two)
- Modify: `pipeline/build_dataset.py:2428` (validate `fit`)
- Modify: `pipeline/audit_dressed_templates.py` — no code change; re-run it first (it is stale at 2026-09-02 and the 16 `zvz_20man` comps landed after)

**Interfaces:**
- `refit_content_targets.py [--apply]`: reads `out/dressed_template_audit.json`, groups parties by `content`, computes per capability the median of `supply.dressed` scaled to `base_size` per person for `scales: true` rows (raw for `scales: false`), prints a table `content cap old new n`, and with `--apply` rewrites only the `target:` number on matching requirement lines in the template YAML (regex on `^(\s+<cap>:\s*\{target:\s*)([0-9.]+)`), leaving comments and every other field intact. Contents with fewer than `MIN_COMPS = 3` distinct comps (by `comp` id) are printed and skipped.
- `fit:` block: `fit: {comps: N, stat: median|minimum|none, source: dressed_template_audit, date: "2026-09-10"}`. `build_dataset.load_templates` fails closed unless `stat` is one of the three words and `comps` is an int ≥ 0.

- [x] **Step 1: Refresh the dressed audit**

Run: `py -3 pipeline/audit_dressed_templates.py`
Expected: prints per-comp rows; `out/dressed_template_audit.json` now carries 18 blackzone_roam parties (2 stated + 16 `zvz_20man`), 3 castle_outpost, 4 territory_defense parties from 2 comps, 1 roads. Confirm with:
`py -3 -c "import json,collections;d=json.load(open('pipeline/out/dressed_template_audit.json',encoding='utf-8'));print(collections.Counter(p['content'] for p in d['parties']))"`

- [x] **Step 2: Write the refit script**

```python
#!/usr/bin/env python3
"""Re-fit content template TARGETS to the median of their fitted comps.

Owner ruling 2026-09-10 ("the data should come from the harvest median"):
a target is what the TYPICAL good comp fields, not the least any comp got
away with. The hand-fitted content rows were written under "0.9 x the
least" from the dressed audit (audit_dressed_templates.py, person units);
this script reads the same audit, the same comps, and writes the MEDIAN.

Per content, per capability:
  scales: true  -> median over comps of supply.dressed * base_size / comp size
  scales: false -> median over comps of supply.dressed (a threshold need)
Only the `target:` number moves; soft caps, weights, scales, ramps,
optional flags, floors and every comment stay. A capability whose median
is 0 keeps its current target (never invent a number). Contents with
fewer than MIN_COMPS distinct comps are reported and left alone — their
`fit:` block says `minimum` (or `none`) and the board labels them.

    py -3 pipeline/refit_content_targets.py            # report only
    py -3 pipeline/refit_content_targets.py --apply    # rewrite the YAML
"""
import json, os, re, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "out", "dressed_template_audit.json")
TEMPLATES = os.path.join(HERE, "templates")
MIN_COMPS = 3


def load_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def medians(parties, tpl):
    base = tpl["base_size"]
    reqs = tpl["requirements"]
    per_cap = {}
    for p in parties:
        for row in p["caps"]:
            cap = row["cap"]
            if cap not in reqs:
                continue
            v = row["supply"]["dressed"]
            if reqs[cap].get("scales"):
                v = v * base / p["size"]
            per_cap.setdefault(cap, []).append(v)
    return {cap: statistics.median(vs) for cap, vs in per_cap.items()}


def rewrite(path, changes):
    """Rewrite only the target number on `  cap: {target: X, ...}` lines."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for cap, new in changes.items():
        pat = re.compile(r"^(\s+%s:\s*\{target:\s*)([0-9.]+)" % re.escape(cap), re.M)
        text, n = pat.subn(lambda m: m.group(1) + ("%g" % new), text, count=1)
        if n != 1:
            sys.exit(f"{os.path.basename(path)}: no single target line for {cap}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    apply = "--apply" in sys.argv[1:]
    with open(AUDIT, encoding="utf-8") as f:
        audit = json.load(f)
    by_content = {}
    for p in audit["parties"]:
        by_content.setdefault(p["content"], []).append(p)
    for content in sorted(by_content):
        parties = by_content[content]
        comps = {p["comp"] for p in parties}
        path = os.path.join(TEMPLATES, content + ".yaml")
        tpl = load_yaml(path)
        if len(comps) < MIN_COMPS:
            print(f"{content}: {len(comps)} comp(s) < {MIN_COMPS} - left alone (fit: minimum)")
            continue
        med = medians(parties, tpl)
        changes = {}
        print(f"{content}: {len(comps)} comps, {len(parties)} parties")
        for cap, r in sorted(tpl["requirements"].items()):
            new = round(med.get(cap, 0.0), 2)
            old = r["target"]
            if new <= 0:
                print(f"  {cap:<20} {old:>7}  keep (median 0)")
                continue
            print(f"  {cap:<20} {old:>7} -> {new:>7}")
            if abs(new - old) > 1e-9:
                changes[cap] = new
        if apply and changes:
            rewrite(path, changes)
            print(f"  wrote {len(changes)} target(s) to {os.path.relpath(path, HERE)}")


if __name__ == "__main__":
    main()
```

- [x] **Step 3: Report, read the table, then apply**

Run: `py -3 pipeline/refit_content_targets.py`
Expected: `blackzone_roam: 18 comps …` and `castle_outpost: 3 comps …` tables; `territory_defense: 2 comp(s) < 3 - left alone`; `roads: 1 comp(s) …`. Sanity: castle_outpost heal_burst old 1.7 → new ≈ 2.9 (the three comps field 2.6 / 2.9 / 3.0).
Then: `py -3 pipeline/refit_content_targets.py --apply` and `git diff pipeline/templates/` — confirm only `target:` numbers changed.

- [x] **Step 4: Add the `fit:` blocks (by hand, six files, under `validated_sizes`)**

```yaml
# FIT PROVENANCE (owner 2026-09-10, target is the median): how the targets
# below were measured. stat median = the median of `comps` published comps
# in the dressed audit (refit_content_targets.py); minimum = still the
# 2026-08-29 "0.9 x the least comp" fit (too few comps to take a median);
# none = no comp in the corpus, rows borrowed from a sibling content.
# The board labels minimum/none rows so a thin number is never read as
# what winners field.
fit: {comps: 18, stat: median, source: dressed_template_audit, date: "2026-09-10"}
```

Values: blackzone_roam `comps: 18, stat: median`; castle_outpost `comps: 3, stat: median`; territory_defense `comps: 2, stat: minimum`; roads `comps: 1, stat: minimum`; castle `comps: 0, stat: none`; faction_war `comps: 0, stat: none`.

- [x] **Step 5: Validate in build_dataset.py**

At line 2428 (`templates[doc["content"]] = doc`) change to:

```python
        else:
            fit = doc.get("fit")
            if not (isinstance(fit, dict) and fit.get("stat") in ("median", "minimum", "none")
                    and type(fit.get("comps")) is int and fit["comps"] >= 0):
                sys.exit(f"{base}: needs fit: {{comps: N, stat: median|minimum|none}} "
                         f"(target provenance, owner 2026-09-10), got {fit!r}")
            templates[doc["content"]] = doc
```

- [x] **Step 6: Rebuild and run the build-chain gates**

Run (bare, not piped):
```
py -3 pipeline/evidence_lint.py
py -3 pipeline/build_dataset.py
py -3 pipeline/build_cohort_families.py
py -3 dashboard/build.py
```
Expected: each exit 0. Then:
```
py -3 tests/test_forge.py
py -3 tests/test_js_parity.py
py -3 tests/test_golden.py
py -3 tests/test_provenance.py
py -3 tests/test_validation_modes.py
py -3 tests/tier2_blindtest.py v4
```
Read every output. F30b/F30f now run against median data. Golden flips: list them (case id, old pick, new pick) — do NOT re-pin; they go to the owner in Task 7. If `tier2 v4` drops below 70%, stop and report before continuing.

- [x] **Step 7: Commit**

```
git add pipeline/refit_content_targets.py pipeline/templates/*.yaml pipeline/build_dataset.py pipeline/out/dressed_template_audit.json pipeline/out/dataset-latest.json pipeline/out/cohort_families.json dashboard/index.html docs/index.html
git commit: "Content rows: targets re-fit to the median of their comps; fit provenance per template"
```
(If `build_dataset.py` also rewrote `roles_report.json` / other `out/*.json`, add those too — the provenance test pins byte-identical rebuilds.)

---

### Task 5: Dashboard — "typical" label, provenance chips, pick-card fix, SIZE follows the roster

**Files:**
- Modify: `dashboard/_shell.html:1658` (section label)
- Modify: `dashboard/_app.js:1380-1426` (board rows/legend), `:427-440` (`whySentence`), `:37-40` (`syncEngine`), `:569-585` (extrapolated notice)
- Modify: `dashboard/_decision_layer.css` or `_shell.html` styles (a `.tag.src` chip)
- Modify: `tests/test_dashboard_layout.py` (new L20 block before the FAILURES summary)

**Interfaces:**
- Consumes: `ENG.targetSource(cap)` from Task 3.
- Page helper: `const targetSource = cap => ENG.targetSource(cap);` beside `target`/`softCap` at line 86.

- [x] **Step 1: Write the failing layout contracts**

Insert before `if FAILURES:` in `tests/test_dashboard_layout.py`:

```python
print("L20 - the board shows the TYPICAL winner, and says when it cannot")
# 2026-09-10 (target is the median): the second number on every row was
# the least any winner fielded, labelled 'target'; every row overshot and
# the reader concluded three healers at 15 was too many. The label now
# says typical, and a row whose target is not a measured median wears a
# chip the ENGINE supplies (targetSource) — never a page-side rule.
check("capability supply vs. typical winner" in SHELL.lower(),
      "L20a the section label says typical winner")
check("const targetSource = cap => ENG.targetSource(cap);" in APP,
      "L20b the page reads provenance from the engine")
board = seg(APP, "function renderCapBoard", "function renderWeaknesses", "L20 board anchors")
check("targetSource(" in board and 'class="tag src' in board,
      "L20c the board chips content_min / none rows from targetSource")
check("supply / typical" in board or "/ typical" in board or "typical" in board,
      "L20d the legend value is labelled typical")
why = seg(APP, "function whySentence", "function setFacet", "L20 why anchors") or \
      seg(APP, "function whySentence", "const roleCls", "L20 why anchors")
check("c !== lead" in why or "!== lead.cap" in why or "!= lead.cap" in why,
      "L20e the lead gap never appears in 'already covers'")
sync = seg(APP, "function syncEngine", "function gearsFromLoadout", "L20 sync anchors")
check("PLANNED = Math.max(PLANNED, party.length)" in sync,
      "L20f the SIZE stepper follows roster growth on every path")
```

Adjust the exact anchor names in Step 3 if `renderCapBoard` is not the board function's name — find it with `Select-String -Path dashboard/_app.js -Pattern "cap-rings"` and use the enclosing `function` name.

- [x] **Step 2: Run to verify failure**

Run: `py -3 tests/test_dashboard_layout.py` → L20a-f FAIL, exit 1.

- [x] **Step 3: Implement**

`_shell.html:1658`: `<div class="sec-label">Capability supply vs. typical winner</div>`

`_app.js:86` add: `const targetSource = cap => ENG.targetSource(cap);`

Board rows (inside the `rows = … map` at ~1380): after `const over = have > soft;` add

```js
      /* target provenance (owner 2026-09-10, target is the median): the
         engine says whether this row's 'typical' is a measured harvest
         median or a thin content minimum — the chip is its word, not ours */
      const src = targetSource(c);
      const srcTag = src === "content_min"
        ? `<span class="tag src" title="no measured median for this row at this content — this is the old minimum (the least any fitted comp brought). Read it as a floor, not as what winners field.">min</span>`
        : src === "harvest_borrowed"
        ? `<span class="tag src" title="thin harvest cell — this median is borrowed from the nearest band of the same style">~</span>`
        : "";
```

return `srcTag` in the row object and render it in the legend after `styleTag`:

```js
        <button class="cap-name" data-cap="${x.c}" title="${esc(prose(x.c))} \u2014 click for evidence">${x.c}${x.below ? '<span class="tag floor">below floor</span>' : ""}${x.over ? '<span class="tag over">overstacked</span>' : ""}${x.styleTag}${x.srcTag}</button>
        <span class="cap-val" title="have / typical winner">${x.have.toFixed(0)} / ${x.t.toFixed(1)}</span>
```

and change the ring `<title>` to `${esc(x.c)} ${x.have.toFixed(0)} / typical ${x.t.toFixed(1)}`. Update the `styleTag` title text: replace "targets never change with style — style changes what the engine emphasises, not what keeps a party alive" with "the typical number is measured per style at 10+, so it already reflects how this style fights; below 10 it is the content row".

Add the chip style beside `.tag.over` (find with `Select-String -Path dashboard/_shell.html -Pattern "\.tag\.over"`):

```css
.tag.src{color:var(--muted,#9aa3b2);border:1px dashed currentColor;opacity:.8}
```

`whySentence`: change the `strong` filter to exclude the lead:

```js
  const lead = terms[0], rest = terms.slice(1,3).map(t => prose(t.cap));
  const strong = Object.keys(REQS()).filter(c => (!lead || c !== lead.cap) && (s[c]||0)/target(c) >= 0.85)
    .sort((a,b) => REQS()[b].weight - REQS()[a].weight).slice(0,2).map(prose);
```

(move the `lead`/`rest` line above `strong`; delete the old `strong` line). Also change "at X of Y units" to "at X of the typical Y units".

`syncEngine` (line 37): first line becomes

```js
function syncEngine(){
  /* the plan follows the roster (2026-09-10): the header read 7 while
     eleven were seated — judgement was already at roster size, only the
     stepper lagged, and only on the manual paths */
  PLANNED = Math.max(PLANNED, party.length);
  SIZE = Math.max(party.length, 1);
```

Extrapolated notice (line 570 and the `mh.title` at ~584): replace "Per-player targets are scaled linearly to ${SIZE}; flat threshold targets are unchanged." with "At ${SIZE} the typical numbers come from the harvest median for this style (10+) or the content row scaled per person; nothing here has been blind-validated at this size yet." and the chip title with "validated at size ${validatedSizes().join(", ")} only — the typical numbers at ${SIZE} are harvest medians / scaled content rows, not yet blind-validated. Details in the setup panel".

- [x] **Step 4: Rebuild the page and run the contracts**

Run: `py -3 dashboard/build.py` then `py -3 tests/test_dashboard_layout.py` → all pass. Also `node tests/test_loadout_codec.js`, `node tests/test_live_party.js`, `node tests/test_display_math.js` (the page sources changed) → exit 0.

- [x] **Step 5: Look at it**

Run: `py -3 -m http.server 8765 --directory dashboard` in the background and open `http://localhost:8765/#c=castle_outpost&n=7&st=kite&p=<the 15-man from the owner's screenshot>` with the Playwright MCP; screenshot the capability board to `.playwright-mcp/typical-board.png`. Confirm: label reads typical winner; heal_burst reads `12 / ~9`; content-min rows (if any at 15 kite) wear `min`; SIZE stepper shows 15.

- [x] **Step 6: Commit**

```
git add dashboard/_shell.html dashboard/_app.js dashboard/index.html docs/index.html tests/test_dashboard_layout.py
git commit: "Board: supply vs. typical winner; provenance chips; the plan follows the roster"
```

---

### Task 6: Golden flips → owner rulings; the records

**Files:**
- Modify: `tests/VALIDATION.md` (rulings index row), `notes/validation/2026-09b.md` (dated entry, append-only), `MASTERSHEET.md` (~line 94, the `tune:templates` section), `HANDOFF.md` ("The engine today"), `pipeline/README.md:387` paragraph, `BACKLOG.md`, `notes/specs/2026-09-10-target-is-the-median-design.md` (status → SHIPPED with the deferred balanced note)

- [x] **Step 1: Collect the golden flips from Task 4 Step 6**

For each failing golden case: case id, content/size/style, party, old expected pick, new top pick, the two capability rows that drove it (`explain()`), one line each. If there are none, say so in the log.

- [x] **Step 2: Put them to the owner as a blind round**

Present the flips as "the engine now picks X here; what would you pick?" — collect the owner's call BEFORE showing the engine's — then per case: re-pin (owner agrees with the new pick), keep the old pin plus an override with its citation (owner disagrees), or open question. Do not proceed to Step 3 for a case still open; log it under "Open questions".

- [x] **Step 3: Write the records**

`notes/validation/2026-09b.md`, append:

```
## 2026-09-10 — Target is the median: the board stops calling a floor a target

Owner (after the p10/p50/p90 explainer): "the data should come from the
harvest median". The case: "if someone sees they have heal burst / heal
sustain at 12/4 they will think they have too many healers in party but
in reality 3 healers in a party of 15 people is totally normal and
standard to try to reach."

What was wrong: every target was 0.9 x p10 — the least any winner
fielded — and the score gave full credit there (one healer "covered"
fifteen; a second earned ~0.3 of 6 points). The measured median was in
the YAML comments and used by nothing.

Ruling, shipped: target = p50 (harvest bands, every style x band);
soft cap 1.15 x p90 unchanged; one smooth curve below; content rows
re-fit to the median of their comps where >= 3 comps exist
(blackzone_roam 18, castle_outpost 3), left and LABELLED otherwise
(territory_defense 2, roads 1, castle/faction_war 0); `balanced` reads a
pooled harvest cell once the audit runs on the harvest checkout
(BACKLOG). Board: "supply vs. typical winner", `min` chip from the
engine's target_source(). SIZE stepper follows the roster.

Before/after, kite 15 (ref 17 scaled): heal_burst 4.6 -> 9.1,
heal_sustain 4.9 -> 10.0, cleanse 1.6 -> 5.3, tankiness 34.9 -> ~42.
Probe: a 14-man kite with two healers moved Hallowfall #26 -> #9.

Golden flips and rulings: <one line per case from Step 2, or "none">.
Gates: forge F30a-f, parity 60/60 + target_source, tier2 v4 <NN%>.
Anti-circularity: the bands are derived from the harvest; the gate
results above are hypotheses for the owner, not a retuning input.
```

`tests/VALIDATION.md` rulings index, append a row:

```
| 09-10 | "the data should come from the harvest median" — target = p50 on every row (bands + content re-fit), soft cap 1.15 x p90, one curve below; `balanced` pooled cell deferred to the harvest checkout; board says typical + `min` chips | derive_style_bands.py, templates/*.yaml fit:, engine target_source | F30, L20, <golden ids> | 09b, Target is the median |
```

`MASTERSHEET.md` `tune:templates` section, after "Fields per capability…":

```
Targets are the TYPICAL winner (harvest median, p50) since 2026-09-10 —
style x size rows for every declared style at 10+, content rows below
that (re-fit to the median of their comps where >= 3 exist; `fit:` in
each template says which). Soft caps are 1.15 x p90. A `target` set here
overrides that number for one content and is read as a median.
```

`pipeline/README.md:387` paragraph: replace "The content rows were comp-fitted 2026-08-21 and re-fitted to person units 2026-08-29 (all rows together); castle and faction_war still rest on no comps in the corpus." with "The content rows were comp-fitted 2026-08-21, re-fitted to person units 2026-08-29 and to the MEDIAN of their comps 2026-09-10 (`refit_content_targets.py`, all rows together; each template's `fit:` block states comps and stat); territory_defense (2 comps) and roads (1) stay on the old minimum and say so; castle and faction_war rest on no comps."

`HANDOFF.md` "The engine today": one paragraph under the templates/targets description stating the median convention, `target_source`, and the deferred balanced cell.

`BACKLOG.md`: close any item about targets overshooting / board readability if one exists; keep the Task 2 item.

Spec status line: `Status: SHIPPED 2026-09-10 (balanced pooled cell deferred — BACKLOG)`.

- [x] **Step 4: Final full gate run**

Run every line of the CLAUDE.md test list (bare). All exit 0. Report each result in the final summary with its printed tail, not a count.

- [x] **Step 5: Commit**

```
git add tests/VALIDATION.md notes/validation/2026-09b.md MASTERSHEET.md HANDOFF.md pipeline/README.md BACKLOG.md notes/specs/2026-09-10-target-is-the-median-design.md notes/plans/2026-09-10-target-is-the-median.md tests/test_golden.py
git commit: "Validation: target is the median (2026-09-10) — rulings, records, golden re-pins"
```

---

## Self-review

- Spec §1 (derivation, zero-share retired, balanced pooled) → Tasks 1, 2. §2 (engine, balanced reads band, target_source, parity) → Task 3. §3 (content re-fit, fit blocks, build validation) → Task 4. §4 (board label, chips, whySentence, SIZE stepper, notice text) → Task 5. §5 (gates, golden as rulings, records) → Tasks 4.6 and 6. Out-of-scope items untouched.
- Names: `target_source` / `targetSource`, `_target_src` / `_targetSrc`, `fit.stat`, `TARGET_OF_P50`, `derive(ev)` — used consistently across tasks.
- No placeholder steps; every code step carries the code. The one open lookup (the board function's name for the L20 anchor) is stated with the command to resolve it.
