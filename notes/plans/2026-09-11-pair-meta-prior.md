# Pair-Aware Meta Prior Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let observed weapon PAIRINGS from the killer-party harvest enter scoring through the meta prior (the 0.15 `delta` slot) — `meta(w, party) = (1-λ)·solo(w) + λ·best-partner(w, party)`, λ = 0.5 — with the artifact derived on the training split, org-gated, shrunk, and never a penalty.

**Architecture:** `derive_meta_prior.py` grows a second table (`meta_pairs`) in the same `out/meta_prior.json`; `build_dataset.py` validates and attaches it as `scoring.meta_pairs` and the blend weight `weights.meta_pair` comes from `templates/scoring.yaml`; both engine twins read it in `meta_of` / `metaOf`, `comp_score` and `_pick_tail`, keeping the pick score an exact `comp_score` delta; the dashboard only translates three new descriptive fields.

**Tech Stack:** Python 3 (`py -3`), Node (engine twin + parity), script-style tests (not pytest), `jsonfmt` for artifacts.

**Spec:** `notes/specs/2026-09-11-pair-meta-prior-design.md`

## Global Constraints

- Windows: always `py -3`; never pipe a build/test through `grep`/`Select-Object` when you read `$LASTEXITCODE`; commit messages via `git commit -F <file>` written BOM-less.
- `engine/app_scoring.js` contains a NUL byte: search it with `Select-String`, read it with the Read tool, edit it with the Edit tool.
- Every committed artifact writer uses `jsonfmt.dump` (LF-only); rebuilds must be byte-identical (`tests/test_provenance.py`).
- Change `engine/engine.py` and `engine/app_scoring.js` together; `py -3 tests/test_js_parity.py` must pass at 1e-9 before any commit that touches either.
- An OLDER dataset (no `meta_pairs`, no `weights.meta_pair`) must score bit-identically to today: absent key → λ = 0 → pure solo.
- Constants (spec §5): `K = 8.0`, `MIN_PRIOR = 0.05`, `LOG_CAP = 3.0`, `MIN_PAIR_PARTIES = 5`, `MIN_PAIR_ORGS = 3`, `HOLDOUT_MOD = 5`. All PROVISIONAL, all recorded in the artifact.
- Never a penalty: lift ≤ 1 → score 0 → row omitted. Absence reads 0 in the engine.
- Golden cases whose RANKING changes are reported to the owner, never re-pinned by the implementer (anti-circularity).
- Tests are script-style: run directly, exit 0 = pass, read the output.
- Never hand-edit `dashboard/index.html` or `docs/` — `py -3 dashboard/build.py` regenerates them.

---

## File map

| File | Responsibility in this plan |
|---|---|
| `pipeline/derive_meta_prior.py` | derive `meta_prior` (solo) AND `meta_pairs` on the training split; `--all-battles` audit flag |
| `pipeline/templates/scoring.yaml` | `weights.meta_pair: 0.5` |
| `pipeline/build_dataset.py` | `load_meta_prior` returns solo + pairs; validates split, symmetry, ranges; attaches `scoring.meta_pairs` |
| `engine/engine.py` | `meta_pair_w`, `meta_pairs`, `_pair_of`, `meta_of(w, party, skip)`, `party_state.pair_max`, `_pick_tail` exact delta, `meta_explain` |
| `engine/app_scoring.js` | the same, mirrored |
| `dashboard/_app.js` | carry `meta_solo/meta_pair/meta_partner/meta_raise`; one why-panel line; updated prose |
| `tests/test_meta_pairs.py` | NEW: derivation + blend contracts |
| `tests/test_js_parity.py` | compare the four new fields |
| `.github/workflows/gates.yml` | run the new test |
| `tests/VALIDATION.md`, `notes/validation/2026-09b.md`, `KILLBOARD_AFFINITY.md`, `HANDOFF.md`, `pipeline/README.md`, `BACKLOG.md` | rulings and docs |

---

### Task 1: Derivation — `meta_pairs` on the training split

**Files:**
- Modify: `pipeline/derive_meta_prior.py` (whole file; currently ~120 lines)
- Create: `tests/test_meta_pairs.py`

**Interfaces:**
- Produces: `derive(doc, k=8.0, min_prior=0.05, holdout_mod=5, log_cap=3.0, min_pair_parties=5, min_pair_orgs=3) -> dict` with keys `meta_prior` (unchanged shape `{bucket: {weapon: float}}`), `players`, `meta_pairs` (`{bucket: {weapon: {partner: float}}}`, symmetric), `pairs_n` (`{bucket: {"A|B": int}}`, A < B), `_split` (`{"holdout_mod": int|None, "rule": str}`), `_pair_params`.
- Produces: `pair_score(n_ab, n_a, n_b, n_total, k, log_cap) -> float` (pure, testable).
- Produces: `bucket_of(party_size)` unchanged (golden T46 pins it).

- [ ] **Step 1: Write the failing derivation tests**

Create `tests/test_meta_pairs.py`:

```python
#!/usr/bin/env python3
"""
Pair-aware meta prior contracts (owner ruling 2026-09-11, spec
notes/specs/2026-09-11-pair-meta-prior-design.md).

Part A — derivation (pipeline/derive_meta_prior.py) on a synthetic
party_rosters doc: the training split is honoured, one party = one vote
per DISTINCT pair, the org gate holds, lift is capped/shrunk exactly as
specified, anti-affinity is omitted (never a penalty), the map is
symmetric and the split is recorded.

Part B — engine blend (engine/engine.py) on the committed dataset:
meta_of is (1-λ)·solo + λ·best-partner, self-seat excluded, ≤ 1, and the
pick score stays the EXACT comp_score delta with pair terms in play.

Run:  py -3 tests/test_meta_pairs.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "engine"))

import derive_meta_prior as dmp  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def party(battle, weapons, guilds=("G",), size=None):
    return {"battle": battle, "index": 0, "size": size or len(weapons),
            "known_weapons": len(weapons), "weapons": list(weapons),
            "guilds": list(guilds), "seen_in_events": 1}


def synthetic():
    """Mid bucket (size 10). Pair A+B fielded by 6 parties across 4 guilds
    on training battles; C+D by 6 parties but ONE guild; E+F only on
    holdout battles (battle % 5 == 0); A+A duplicates in one party; X+Y
    appears in every party (lift ≈ 1 -> anti/neutral, omitted)."""
    ps, bid = [], 1
    def nxt_train():
        nonlocal bid
        bid += 1
        while bid % 5 == 0:
            bid += 1
        return bid
    for g in ("G1", "G2", "G3", "G4", "G1", "G2"):
        ps.append(party(nxt_train(), ["A", "B", "X", "Y"] + ["P%d" % i for i in range(6)], (g,), 10))
    for _ in range(6):
        ps.append(party(nxt_train(), ["C", "D", "X", "Y"] + ["Q%d" % i for i in range(6)], ("ONLY",), 10))
    for _ in range(6):
        ps.append(party(nxt_train(), ["A", "A", "X", "Y"] + ["R%d" % i for i in range(6)], ("G9",), 10))
    for h in (5, 10, 15, 20, 25, 30):
        ps.append(party(h, ["E", "F", "X", "Y"] + ["S%d" % i for i in range(6)], ("H1", "H2")[h % 2:], 10))
    builds = []
    for p in ps:
        for i, w in enumerate(p["weapons"]):
            builds.append({"battle": p["battle"], "party": p["index"],
                           "party_size": p["size"], "player": f"{p['battle']}-{i}",
                           "weapon": w, "seen_as": "killer"})
    return {"parties": ps, "builds": builds}


def part_a():
    doc = synthetic()
    out = dmp.derive(doc)
    mid = out["meta_pairs"]["mid"]
    n = out["pairs_n"]["mid"]
    check("A1 _split records the holdout rule",
          out["_split"] == {"holdout_mod": 5,
                            "rule": "battle % 5 != 0 (training split; % 5 == 0 is the v4h holdout)"},
          str(out.get("_split")))
    check("A2 A+B carries a row (6 parties, 4 guilds)",
          "B" in mid.get("A", {}) and n.get("A|B") == 6, str(mid.get("A")))
    check("A3 map is symmetric", mid["A"]["B"] == mid["B"]["A"], "")
    check("A4 C+D omitted: one guild fails the >=3 org gate",
          "D" not in mid.get("C", {}) and "C" not in mid.get("D", {}), str(mid.get("C")))
    check("A5 E+F omitted: only on holdout battles",
          "E" not in mid and "F" not in mid, str(sorted(mid)))
    check("A6 no self-pair from the A,A party", "A" not in mid.get("A", {}), "")
    check("A7 X+Y omitted: lift 1 is neutral, never a penalty",
          "Y" not in mid.get("X", {}), str(mid.get("X")))
    # hand computation: N=18 training parties, n_A = 12 (6 A+B, 6 A+A),
    # n_B = 6, n_AB = 6 -> lift = 6*18/(12*6) = 1.5
    lift = 6 * 18 / (12 * 6)
    want = min(math.log2(lift), 3.0) / 3.0 * 6 / (6 + 8.0)
    check("A8 pair score = clamp(log2 lift,0,3)/3 * n/(n+K) on the hand case",
          abs(mid["A"]["B"] - round(want, 3)) < 1e-9, f"{mid['A']['B']} vs {want}")
    check("A9 pair_score is 0 at lift <= 1 and saturates at 8x",
          dmp.pair_score(6, 12, 6, 6, 8.0, 3.0) == 0.0
          and abs(dmp.pair_score(100, 10, 10, 8000, 8.0, 3.0) - 100 / 108.0) < 1e-12, "")
    solo = out["meta_prior"]["mid"]
    check("A10 solo prior ignores holdout battles too (E, F absent)",
          "E" not in solo and "F" not in solo, str(sorted(solo)))
    check("A11 --all-battles derivation includes E+F and records the split as None",
          "F" in dmp.derive(doc, holdout_mod=None)["meta_pairs"]["mid"].get("E", {})
          and dmp.derive(doc, holdout_mod=None)["_split"]["holdout_mod"] is None, "")
    check("A12 _pair_params recorded",
          out["_pair_params"] == {"k": 8.0, "log_cap": 3.0, "min_pair_parties": 5,
                                  "min_pair_orgs": 3, "min_prior": 0.05},
          str(out.get("_pair_params")))
    check("A13 every pair value in (0, 1]",
          all(0.0 < v <= 1.0 for bk in out["meta_pairs"].values()
              for row in bk.values() for v in row.values()), "")


def part_b():
    from engine import Engine
    e = Engine(content="castle", size=10)
    lam = e.meta_pair_w
    check("B1 dataset carries the pair blend weight 0.5", lam == 0.5, str(lam))
    bk = e.size_bucket()
    pairs = e.meta_pairs.get(bk) or {}
    solo = e.meta_prior.get(bk) or {}
    # pick the strongest pair in this bucket among weapons the engine knows
    best = max(((w, m, s) for w, row in pairs.items() for m, s in row.items()
                if w in e.weapons and m in e.weapons), key=lambda t: t[2])
    w, m, s = best
    check("B2 meta_of alone = (1-λ)·solo", abs(e.meta_of(w, [w], 0) - (1 - lam) * solo.get(w, 0.0)) < 1e-12,
          f"{e.meta_of(w, [w], 0)}")
    check("B3 meta_of with its best partner = (1-λ)·solo + λ·s",
          abs(e.meta_of(w, [m, w], 1) - ((1 - lam) * solo.get(w, 0.0) + lam * s)) < 1e-12, "")
    check("B4 self-seat excluded: a duplicate of w is not w's partner",
          abs(e.meta_of(w, [w, w], 0) - (1 - lam) * solo.get(w, 0.0)) < 1e-12, "")
    check("B5 meta_of never exceeds 1", all(e.meta_of(x, [m, x], 1) <= 1.0 + 1e-12 for x in e.weapons), "")
    mx = e.meta_explain(w, [m])
    check("B6 meta_explain names the partner and splits the term",
          mx["meta_solo"] == solo.get(w, 0.0) and mx["meta_pair"] == s
          and mx["meta_partner"] == m and mx["meta_raise"] >= 0.0
          and set(mx) == {"meta_solo", "meta_pair", "meta_partner", "meta_raise"},
          str(mx))
    # exact-marginal invariant with pair terms: the candidate's meta_prior
    # field must equal comp meta(P+c) - comp meta(P), including the raise
    # of m's own pair term when c is m's best partner
    p = [m]
    rep = e.pick_report(p, w)
    before = sum(e.meta_of(x, p, i) for i, x in enumerate(p))
    after = sum(e.meta_of(x, p + [w], i) for i, x in enumerate(p + [w]))
    check("B7 pick meta_prior is the exact party meta delta (incl. partner raise)",
          abs(rep["meta_prior"] - (after - before)) < 1e-9, f"{rep['meta_prior']} vs {after - before}")
    # same pattern as test_forge F1: None combos are legal, the kit the
    # pick chose rides along as the candidate's gear
    check("B8 pick score is the exact comp_score delta",
          abs(rep["score"] - (e.comp_score(p + [w], [None, rep["combo"]],
                                           [None, rep["kit"] or None])
                              - e.comp_score(p, [None]))) < 1e-9,
          "")


def run():
    part_a()
    part_b()
    print("=" * 74)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, det in results:
        print(f"{'PASS' if ok else 'FAIL':4}  {name}"
              + (f"\n      {det}" if det and not ok else ""))
    print("=" * 74)
    print(f"{passed}/{len(results)} pair-prior tests passed")
    return passed, len(results)


if __name__ == "__main__":
    p, n = run()
    sys.exit(0 if p == n else 1)
```

Note for the implementer: Part B fails until Tasks 2–3 land; in this task only Part A must pass. Temporarily run with `py -3 -c "import sys; sys.path.insert(0,'tests'); import test_meta_pairs as t; t.part_a(); ..."` or just read the A-rows of the output.

- [ ] **Step 2: Run to verify Part A fails**

Run: `py -3 tests/test_meta_pairs.py`
Expected: A-rows FAIL (`KeyError: 'meta_pairs'` / `TypeError: derive() got an unexpected keyword argument 'holdout_mod'`) — the script may crash before printing; that counts as failing.

- [ ] **Step 3: Implement the derivation**

Replace the constants block and `derive()` in `pipeline/derive_meta_prior.py`. Keep `bucket_of`, `sha256_of` and the docstring's first paragraphs; extend the docstring with the pair table:

```python
BUCKETS = ("small", "mid", "large")
K = 8.0            # shrinkage mass in PLAYERS (solo) / PARTIES (pairs); PROVISIONAL
MIN_PRIOR = 0.05   # below this a weapon / pair carries no signal (row omitted)
HOLDOUT_MOD = 5    # battles with id % 5 == 0 are tier2_blindtest v4h's holdout
LOG_CAP = 3.0      # log2(lift) saturates at 8x over chance; PROVISIONAL
MIN_PAIR_PARTIES = 5   # honesty gate (mirrors build_cohort_families MIN_COHORTS)
MIN_PAIR_ORGS = 3      # ...across this many distinct guild-sets (MIN_ORGS)


def in_split(battle, holdout_mod):
    """Training-split membership: the shipped prior never learns from the
    holdout slice tier2_blindtest v4h evaluates on."""
    if not holdout_mod:
        return True
    try:
        return int(battle) % holdout_mod != 0
    except (TypeError, ValueError):
        return False


def pair_score(n_ab, n_a, n_b, n_total, k, log_cap):
    """Spec §5: lift = n_ab*N/(n_a*n_b); s = clamp(log2 lift, 0, cap)/cap
    * n_ab/(n_ab+k). 0 at or under chance — never a penalty."""
    if not (n_ab and n_a and n_b and n_total):
        return 0.0
    lift = n_ab * n_total / (n_a * n_b)
    if lift <= 1.0:
        return 0.0
    lg = min(math.log2(lift), log_cap)
    return lg / log_cap * n_ab / (n_ab + k)


def derive(doc, k=K, min_prior=MIN_PRIOR, holdout_mod=HOLDOUT_MOD,
           log_cap=LOG_CAP, min_pair_parties=MIN_PAIR_PARTIES,
           min_pair_orgs=MIN_PAIR_ORGS):
    # ---- solo: distinct players per weapon per bucket (R27), training split
    voters = {b: {} for b in BUCKETS}
    for b in doc.get("builds") or []:
        size, player, weapon = b.get("party_size"), b.get("player"), b.get("weapon")
        if not size or size < 2 or not player or not weapon:
            continue
        if not in_split(b.get("battle"), holdout_mod):
            continue
        voters[bucket_of(size)].setdefault(weapon, set()).add(player)
    prior, players = {}, {}
    for bk in BUCKETS:
        counts = {w: len(s) for w, s in voters[bk].items()}
        total = sum(counts.values())
        if not total:
            prior[bk], players[bk] = {}, {}
            continue
        shrunk = {w: (n / total) * (n / (n + k)) for w, n in counts.items()}
        top = max(shrunk.values())
        rows = {w: round(s / top, 3) for w, s in shrunk.items()}
        prior[bk] = {w: v for w, v in sorted(rows.items()) if v >= min_prior}
        players[bk] = {w: counts[w] for w in prior[bk]}
    # ---- pairs: one PARTY, one vote per distinct pair it fields
    n_parties = {b: 0 for b in BUCKETS}
    n_w = {b: {} for b in BUCKETS}
    n_ab = {b: {} for b in BUCKETS}
    orgs = {b: {} for b in BUCKETS}
    for p in doc.get("parties") or []:
        size = p.get("size")
        if not size or size < 2 or not in_split(p.get("battle"), holdout_mod):
            continue
        ws = sorted(set(p.get("weapons") or []))
        if not ws:
            continue
        bk = bucket_of(size)
        n_parties[bk] += 1
        for w in ws:
            n_w[bk][w] = n_w[bk].get(w, 0) + 1
        org = tuple(sorted(p.get("guilds") or []))
        for a, b2 in itertools.combinations(ws, 2):
            n_ab[bk][(a, b2)] = n_ab[bk].get((a, b2), 0) + 1
            if org:      # an unknown guild-set casts no ORG vote
                orgs[bk].setdefault((a, b2), set()).add(org)
    pairs, pairs_n = {}, {}
    for bk in BUCKETS:
        rows, support = {}, {}
        for (a, b2), n in sorted(n_ab[bk].items()):
            if n < min_pair_parties or len(orgs[bk].get((a, b2), ())) < min_pair_orgs:
                continue
            s = round(pair_score(n, n_w[bk][a], n_w[bk][b2], n_parties[bk], k, log_cap), 3)
            if s < min_prior:
                continue
            rows.setdefault(a, {})[b2] = s
            rows.setdefault(b2, {})[a] = s
            support[f"{a}|{b2}"] = n
        pairs[bk] = {w: dict(sorted(r.items())) for w, r in sorted(rows.items())}
        pairs_n[bk] = support
    return {
        "_source": {"party_rosters_sha256": None},
        "_unit": ("distinct players per weapon per bucket (one player, one "
                  "vote); share of the bucket's voters, shrunk n/(n+K), "
                  "normalized so the bucket's top weapon is 1.0; rows under "
                  "min_prior omitted (no signal, never a penalty)"),
        "_pair_unit": ("one killer PARTY, one vote per distinct weapon pair it "
                       "fields (2026-09-11); a pair needs min_pair_parties "
                       "parties across min_pair_orgs distinct guild-sets; "
                       "s = clamp(log2 lift, 0, log_cap)/log_cap * n/(n+K); "
                       "lift <= 1 reads 0 (anti-affinity is never a penalty)"),
        "_bucket_rule": ("Engine.size_bucket on the party size: 2-5 small, "
                         "6-15 mid, 16+ large (participant axis 2 x size, "
                         "cuts at 12 / 30)"),
        "_split": {"holdout_mod": holdout_mod,
                   "rule": (f"battle % {holdout_mod} != 0 (training split; "
                            f"% {holdout_mod} == 0 is the v4h holdout)"
                            if holdout_mod else "all battles (AUDIT ONLY, never shipped)")},
        "_k": k, "_min_prior": min_prior,
        "_pair_params": {"k": k, "log_cap": log_cap,
                         "min_pair_parties": min_pair_parties,
                         "min_pair_orgs": min_pair_orgs, "min_prior": min_prior},
        "meta_prior": prior, "players": players,
        "meta_pairs": pairs, "pairs_n": pairs_n,
    }
```

Add `import itertools` and `import math` at the top. Update `main()`:

```python
def main():
    all_battles = "--all-battles" in sys.argv[1:]
    if not os.path.exists(ARTIFACT):
        sys.exit("no out/party_rosters.json -- run sample_parties.py first")
    with open(ARTIFACT, encoding="utf-8") as f:
        doc = json.load(f)
    out = derive(doc, holdout_mod=None if all_battles else HOLDOUT_MOD)
    out["_generated"] = datetime.date.today().isoformat()
    out["_source"]["party_rosters_sha256"] = sha256_of(ARTIFACT)
    target = TARGET.replace(".json", "-all-battles.json") if all_battles else TARGET
    jsonfmt.dump(out, target)
    for bk in BUCKETS:
        rows = out["meta_prior"][bk]
        top = sorted(rows.items(), key=lambda kv: -kv[1])[:3]
        print(f"  {bk:<5} {len(rows):>3} weapons  top: "
              + ", ".join(f"{w} {v}" for w, v in top))
        npairs = sum(len(r) for r in out["meta_pairs"][bk].values()) // 2
        tp = sorted(((a, b, s) for a, r in out["meta_pairs"][bk].items()
                     for b, s in r.items() if a < b), key=lambda t: -t[2])[:3]
        print(f"        {npairs:>4} pairs    top: "
              + ", ".join(f"{a}+{b} {s}" for a, b, s in tp))
    print(f"meta prior ({out['_split']['rule']}) -> {os.path.relpath(target, HERE)}")
```

Add to the docstring's usage lines: `py -3 pipeline/derive_meta_prior.py --all-battles   # audit copy -> out/meta_prior-all-battles.json, never shipped`. Add `out/meta_prior-all-battles.json` to `.gitignore` (check `pipeline/.gitignore` or root `.gitignore` for the existing `out/` pattern style and follow it).

- [ ] **Step 4: Run the test — Part A passes**

Run: `py -3 tests/test_meta_pairs.py`
Expected: A1–A13 PASS; B-rows FAIL or crash (engine not yet changed). Also run `py -3 tests/test_golden.py` — T46 (bucket_of) must still PASS; other rows unaffected because the dataset is not rebuilt yet.

- [ ] **Step 5: Regenerate the artifact and eyeball it**

Run: `py -3 pipeline/derive_meta_prior.py`
Expected output includes `(battle % 5 != 0 ...)` and per bucket a `pairs` line whose top small pair is Arcane/Brimstone-class. Confirm `git diff --stat pipeline/out/meta_prior.json` shows the file changed and `Select-String -Path pipeline/out/meta_prior.json -Pattern '"holdout_mod": 5'` hits.

Do NOT run `build_dataset.py` yet — it will refuse nothing today but Task 2 adds the gate; keep the dataset untouched in this commit.

- [ ] **Step 6: Commit**

```powershell
$p = Join-Path $env:TEMP "cf_msg.txt"
[System.IO.File]::WriteAllText($p, "Prior: derive observed weapon pairs on the training split (2026-09-11)`n`nmeta_prior.json gains meta_pairs / pairs_n: one killer party one vote per`ndistinct pair, >=5 parties across >=3 guild-sets, s = clamp(log2 lift,0,3)/3`n* n/(n+8), lift<=1 reads 0. Both tables now learn from battle % 5 != 0`nonly (v4h holdout excluded); --all-battles writes an audit copy.`n`nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`n", (New-Object System.Text.UTF8Encoding $false))
git add pipeline/derive_meta_prior.py pipeline/out/meta_prior.json tests/test_meta_pairs.py .gitignore
git commit -F $p
```

---

### Task 2: Dataset — validate and attach `meta_pairs`, blend weight

**Files:**
- Modify: `pipeline/templates/scoring.yaml:11-15` (weights block)
- Modify: `pipeline/build_dataset.py:2441-2471` (`load_meta_prior`), `:2688`, `:2698-2700`

**Interfaces:**
- Consumes: `out/meta_prior.json` with `meta_pairs`, `_split` (Task 1).
- Produces: `dataset-latest.json` `scoring.meta_pairs = {bucket: {weapon: {partner: float}}}` (known weapons only, symmetric, values in (0,1]) and `scoring.weights.meta_pair = 0.5`.
- Produces: `load_meta_prior(known_weapons) -> (solo, pairs)`.

- [ ] **Step 1: Add the blend weight to scoring.yaml**

In `pipeline/templates/scoring.yaml` after `delta: 0.15   # meta prior` add:

```yaml
  # Pair-aware prior (owner ruling 2026-09-11, spec
  # notes/specs/2026-09-11-pair-meta-prior-design.md): per member,
  # meta = (1 - meta_pair) * solo + meta_pair * best observed partner in
  # the roster (scoring.meta_pairs, GENERATED by derive_meta_prior.py from
  # the killer-party harvest, training split only). Both inputs are in
  # [0, 1], so delta stays the cap. Absent (older dataset) = 0 = pure solo,
  # bit-identical to the 2026-09-08 prior.
  meta_pair: 0.5
```

- [ ] **Step 2: Extend `load_meta_prior`**

Replace the body of `load_meta_prior` in `pipeline/build_dataset.py` after the hash check (keep the existing missing-file and hash-drift exits):

```python
    split = doc.get("_split") or {}
    if split.get("holdout_mod") != 5:
        sys.exit("out/meta_prior.json was not derived on the training split "
                 "(battle % 5 != 0) — an all-battles prior is AUDIT ONLY; "
                 "rerun py -3 pipeline/derive_meta_prior.py without --all-battles")
    prior = doc.get("meta_prior") or {}
    if not prior or set(prior) - {"small", "mid", "large"}:
        sys.exit("out/meta_prior.json: meta_prior must be bucketed "
                 "small / mid / large")
    out = {}
    for bk in ("small", "mid", "large"):
        rows = prior.get(bk) or {}
        out[bk] = {w: float(v) for w, v in sorted(rows.items())
                   if w in known_weapons and 0.0 < float(v) <= 1.0}
    pairs_in = doc.get("meta_pairs")
    if not isinstance(pairs_in, dict) or set(pairs_in) - {"small", "mid", "large"}:
        sys.exit("out/meta_prior.json: meta_pairs missing or not bucketed — "
                 "rerun py -3 pipeline/derive_meta_prior.py")
    pairs = {}
    for bk in ("small", "mid", "large"):
        rows = pairs_in.get(bk) or {}
        kept = {}
        for w, row in sorted(rows.items()):
            if w not in known_weapons:
                continue
            for m, v in sorted((row or {}).items()):
                if m not in known_weapons or m == w:
                    continue
                v = float(v)
                if not 0.0 < v <= 1.0:
                    sys.exit(f"out/meta_prior.json: meta_pairs {bk} {w}|{m} = {v} "
                             "out of (0, 1]")
                if abs(float((rows.get(m) or {}).get(w, -1.0)) - v) > 1e-12:
                    sys.exit(f"out/meta_prior.json: meta_pairs {bk} {w}|{m} is not "
                             "symmetric — rerun derive_meta_prior.py")
                kept.setdefault(w, {})[m] = v
        pairs[bk] = kept
    return out, pairs
```

Update the docstring's first sentence to mention the pair table and the split gate (2026-09-11).

- [ ] **Step 3: Attach it**

At `build_dataset.py:2688` change:

```python
    scoring["meta_prior"], scoring["meta_pairs"] = load_meta_prior(set(weapons))
```

and extend the print at `:2698`:

```python
    print("  meta prior    : generated (out/meta_prior.json, training split), "
          + ", ".join(f"{bk} {len(rows)}" for bk, rows in scoring["meta_prior"].items())
          + " weapon rows; pairs "
          + ", ".join(f"{bk} {sum(len(r) for r in rows.values()) // 2}"
                      for bk, rows in scoring["meta_pairs"].items()))
```

Also in the hand-set guard at `:2616` extend the condition to `if scoring.get("meta_prior") or scoring.get("meta_pairs"):` and the message to name both keys.

- [ ] **Step 4: Rebuild the dataset and verify**

Run (bare, no pipe): `py -3 pipeline/build_dataset.py`
Expected: exit 0, the `meta prior` line shows pair counts per bucket (hundreds in small, thousands in mid/large).
Then: `py -3 -c "import json; d=json.load(open('pipeline/out/dataset-latest.json',encoding='utf-8')); s=d['scoring']; print(s['weights']['meta_pair'], {b: sum(len(r) for r in s['meta_pairs'][b].values())//2 for b in s['meta_pairs']})"`
Expected: `0.5 {'small': N, 'mid': N, 'large': N}` with N > 0 each.

Negative check: run `py -3 pipeline/derive_meta_prior.py --all-battles`, copy the audit file over `out/meta_prior.json` temporarily, run `py -3 pipeline/build_dataset.py` — expect exit 2 with the "training split" message — then `git checkout pipeline/out/meta_prior.json` and delete the audit copy.

- [ ] **Step 5: Run the gates that only need the dataset**

Run: `py -3 tests/test_provenance.py` and `py -3 tests/test_builds.py`
Expected: exit 0. (Golden/parity/forge run after Task 3 — the engine ignores `meta_pairs` until then and the new weight is a no-op, so they should still pass; run `py -3 tests/test_golden.py` to confirm nothing moved yet.)

- [ ] **Step 6: Commit**

```powershell
$p = Join-Path $env:TEMP "cf_msg.txt"
[System.IO.File]::WriteAllText($p, "Dataset: attach scoring.meta_pairs and weights.meta_pair (2026-09-11)`n`nload_meta_prior validates the training-split stamp, bucketing, symmetry`nand (0,1] ranges, drops unknown weapons, and fails closed on an`nall-battles artifact. scoring.yaml carries meta_pair: 0.5 (absent = solo).`n`nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`n", (New-Object System.Text.UTF8Encoding $false))
git add pipeline/templates/scoring.yaml pipeline/build_dataset.py pipeline/out/dataset-latest.json
git commit -F $p
```

---

### Task 3: Python engine — blend, exact marginal, explanation

**Files:**
- Modify: `engine/engine.py:104-116` (weights/prior load), `:2249-2254` (`meta_of`), `:2262-2280` (`comp_score`), `:2290-2320` (`party_state`), `:2514-2520` (`_pick_tail`), `:2606-2611` (`best_loadout` state stub), `:2755-2760` (pick_report record), `:2762-2800` (`recommend`)
- Test: `tests/test_meta_pairs.py` Part B (written in Task 1)

**Interfaces:**
- Produces: `Engine.meta_pair_w: float`, `Engine.meta_pairs: dict`
- Produces: `Engine._pair_of(weapon, party, skip=None) -> (score: float, partner: str|None)` — best partner among `party` seats other than index `skip`.
- Produces: `Engine.meta_of(weapon, party=None, skip=None) -> float` = `(1-λ)·solo + λ·pair`.
- Produces: `Engine.meta_explain(weapon, party) -> {"meta_solo", "meta_pair", "meta_partner", "meta_raise"}` for a CANDIDATE joining `party`.
- Produces: `party_state[...]["party"]: list`, `["pair_max"]: list[float]` (per seat, best partner among the other seats).
- Keeps: `_pick_tail` returns `(score, d_fit, d_syn, meta, combo)` where `meta` is now the EXACT party-meta delta.

- [ ] **Step 1: Confirm Part B fails**

Run: `py -3 tests/test_meta_pairs.py`
Expected: B1 FAIL (`AttributeError: 'Engine' object has no attribute 'meta_pair_w'`) or crash.

- [ ] **Step 2: Load the weight and the pair table**

At `engine/engine.py:109` (after `self.headroom = ...`) add:

```python
        # Pair-aware prior (owner 2026-09-11): blend weight for the best
        # observed partner; absent = 0 = pure solo (older dataset scores
        # exactly as it used to).
        self.meta_pair_w = w.get("meta_pair", 0.0)
```

After `self.meta_bucketed = ...` add:

```python
        # {bucket: {weapon: {partner: s}}}, symmetric, GENERATED with the
        # solo prior; read only through _pair_of at roster size.
        self.meta_pairs = self.scoring.get("meta_pairs", {}) or {}
```

- [ ] **Step 3: Replace `meta_of`, add `_pair_of` and `meta_explain`**

Replace `meta_of` at `:2249-2254`:

```python
    def _pair_of(self, weapon, party, skip=None):
        """Best observed partner of `weapon` among the other seats of
        `party` (seat `skip` is the weapon's own seat and never pairs with
        itself). (score, partner) — (0.0, None) with no row: absence is
        neutral, never a penalty. Ties break on the partner id so the
        explanation is deterministic across the twins."""
        if not party or not self.meta_pair_w:
            return 0.0, None
        rows = (self.meta_pairs.get(self.size_bucket()) or {}).get(weapon)
        if not rows:
            return 0.0, None
        best, who = 0.0, None
        for i, m in enumerate(party):
            if i == skip:
                continue
            s = rows.get(m, 0.0)
            if s > best or (s == best and who is not None and s and m < who):
                best, who = s, m
        return best, who

    def meta_of(self, weapon, party=None, skip=None):
        """Meta-prior value for a weapon at the current size: (1 - λ)·solo
        + λ·best observed partner in `party` (λ = weights.meta_pair, 0 on
        an older dataset). Flat solo map -> direct lookup; size-bucketed
        map -> size_bucket()."""
        if not self.meta_bucketed:
            solo = self.meta_prior.get(weapon, 0.0)
        else:
            solo = (self.meta_prior.get(self.size_bucket()) or {}).get(weapon, 0.0)
        lam = self.meta_pair_w
        if not lam:
            return solo
        pair, _who = self._pair_of(weapon, party, skip)
        return (1.0 - lam) * solo + lam * pair

    def meta_explain(self, weapon, party):
        """Descriptive split of a CANDIDATE's meta term when it joins
        `party`: its solo prior, its best-partner score and who, and the
        `raise` its arrival adds to the members' own pair terms. Never a
        scoring input — the score already carries the sum."""
        if not self.meta_bucketed:
            solo = self.meta_prior.get(weapon, 0.0)
        else:
            solo = (self.meta_prior.get(self.size_bucket()) or {}).get(weapon, 0.0)
        pair, who = self._pair_of(weapon, party or [])
        raise_ = 0.0
        if self.meta_pair_w and party:
            for i, m in enumerate(party):
                cur, _ = self._pair_of(m, party, i)
                new, _ = self._pair_of(m, list(party) + [weapon], i)
                if new > cur:
                    raise_ += new - cur
        return {"meta_solo": solo, "meta_pair": pair, "meta_partner": who,
                "meta_raise": raise_}
```

- [ ] **Step 4: `comp_score` sums the blend per seat**

At `:2274` change the loop:

```python
        for i, w in enumerate(party):
            meta += self.meta_of(w, party, i)
            viab += self.viability_of(w)
```

- [ ] **Step 5: `party_state` carries the party and per-seat pair max**

In `party_state` (`:2316`) extend the returned dict:

```python
        return {"s": s, "s_syn": s_syn, "J": J, "pair_vals": pair_vals,
                "counts": counts, "ns_max": ns_max,
                # carrier quota (2026-09-03): what this roster already
                # wears of each capped effect-carrier chest
                "carriers": self._carrier_counts(party, gears),
                # pair-aware prior (2026-09-11): each seat's best observed
                # partner so far, so a candidate's exact meta delta can
                # include the raise it hands existing members
                "party": list(party),
                "pair_max": [self._pair_of(w, party, i)[0]
                             for i, w in enumerate(party)]}
```

In `best_loadout` (`:2610-2611`) add `"party": [], "pair_max": []` to the stub state.

- [ ] **Step 6: `_pick_tail` computes the exact meta delta**

Replace `_pick_tail` (`:2514-2520`):

```python
    def _pick_tail(self, state, weapon, best):
        """The combo-independent terms of a candidate score — shared by
        _eval_pick and _forge_eval_pick so the formula can never drift.
        `meta` is the EXACT party-meta delta of adding `weapon` (2026-09-11):
        its own blended prior plus the raise its arrival hands each
        member's best-partner term, so the pick score stays the exact
        comp_score delta (test_forge F1, test_meta_pairs B7)."""
        party = state.get("party") or []
        meta = self.meta_of(weapon, party)
        lam = self.meta_pair_w
        if lam and party:
            rows = (self.meta_pairs.get(self.size_bucket()) or {})
            pmax = state["pair_max"]
            for i, m in enumerate(party):
                s = (rows.get(m) or {}).get(weapon, 0.0)
                if s > pmax[i]:
                    meta += lam * (s - pmax[i])
        dup = state["counts"].get(weapon, 0) + 1 - self._dup_free(weapon)
        score = (best[0] + self.delta * meta
                 + self.viability_w * self.viability_of(weapon)
                 - (self.rho * dup if dup > 0 else 0.0))
        return score, best[1], best[2], meta, best[3]
```

- [ ] **Step 7: Expose the explanation on returned rows only**

In `recommend` (`:2790`, the loop that sets `caps_gain`/`verdict` on the top rows) add `r.update(self.meta_explain(r["weapon"], party))`. In `pick_report`'s returned dict (`:2755`) add after `"meta_prior": meta,`: `**self.meta_explain(candidate, party),`. (`pick_report` has `party` in scope — confirm by reading its signature at `:2712`.)

- [ ] **Step 8: Run the Python tests**

Run, each bare:
`py -3 tests/test_meta_pairs.py` → all A and B rows PASS.
`py -3 tests/test_forge.py` → exit 0 (F1 pick-score invariant).
`py -3 tests/test_golden.py` → read the output. Record every FAIL row (name + detail) in the commit message body under "Golden rows moved (owner to rule)" — do NOT re-pin. If a failing row is a pure tolerance/reconstruction case (T30-style reconstruction), it must still PASS — a failure there is a bug in Step 6, fix it.
`py -3 tests/test_validation_modes.py`, `py -3 tests/test_roles.py` → exit 0.

- [ ] **Step 9: Commit**

```powershell
$p = Join-Path $env:TEMP "cf_msg.txt"
[System.IO.File]::WriteAllText($p, "Engine: pair-aware meta prior, exact marginal (2026-09-11)`n`nmeta_of(w, party, seat) = (1-λ)·solo + λ·best observed partner; comp_score`nsums it per seat; _pick_tail adds the raise a candidate hands members'`npair terms so the pick score stays the exact comp_score delta.`nmeta_explain() exposes solo / pair / partner / raise on returned rows.`n`nGolden rows moved (owner to rule): <list or 'none'>`n`nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`n", (New-Object System.Text.UTF8Encoding $false))
git add engine/engine.py
git commit -F $p
```

(Parity will FAIL until Task 4 — do not push between Tasks 3 and 4.)

---

### Task 4: JS engine twin + parity

**Files:**
- Modify: `engine/app_scoring.js:63-66` (prior load), `:1945-1948` (`metaOf`), `:1955-1967` (`compScore`), `:1970-2009` (`partyState`), `:2101-2110` (`_pickTail`), `:2468-2478` (`pickReport` record), `:2488-2530` (`recommend`), and the `bestLoadout` stub state (search `pairVals: []` with Select-String)
- Modify: `tests/test_js_parity.py:352-370` (recommend rows) and `:370-380` (pick_report head)

**Interfaces:**
- Consumes: dataset `scoring.meta_pairs`, `scoring.weights.meta_pair` (Task 2); Python semantics (Task 3).
- Produces: `CompEngine.prototype._pairOf(weapon, party, skip) -> [score, partner|null]`, `metaOf(w, party, skip)`, `metaExplain(w, party)`, `partyState(...).party`, `.pairMax`.

- [ ] **Step 1: Extend parity to the new fields (failing first)**

In `tests/test_js_parity.py` recommend-row loop (`:357`), after the existing `score/combo/kit` check add an `elif`:

```python
                elif any(abs(ra[k] - rb.get(k, 9e9)) > EPS
                         for k in ("meta_prior", "meta_solo", "meta_pair", "meta_raise")) \
                        or ra["meta_partner"] != rb.get("meta_partner"):
                    errs.append(f"rec meta {ra['weapon']}: "
                                f"py={ra['meta_prior']!r}/{ra['meta_solo']!r}/{ra['meta_pair']!r}/"
                                f"{ra['meta_partner']}/{ra['meta_raise']!r} "
                                f"js={rb.get('meta_prior')!r}/{rb.get('meta_solo')!r}/"
                                f"{rb.get('meta_pair')!r}/{rb.get('meta_partner')}/{rb.get('meta_raise')!r}")
```

In the pick_report head tuple (`:377`) add `"meta_solo", "meta_pair", "meta_raise"` to the EPS key list and `or pa["meta_partner"] != pb.get("meta_partner")` to the condition.

Run: `py -3 tests/test_js_parity.py` → expected FAIL (JS lacks the fields / scores differ).

- [ ] **Step 2: Load the weight and pairs in JS**

At `app_scoring.js:63` (where `this.metaPrior = this.scoring.meta_prior || {};`) add:

```javascript
    /* pair-aware prior (owner 2026-09-11, mirrors engine.py): blend weight
       for the best observed partner; absent = 0 = pure solo */
    this.metaPairW = w.meta_pair || 0.0;
    this.metaPairs = this.scoring.meta_pairs || {};
```

(`w` is the weights object in that constructor — confirm the local name by reading lines 40–70; if it is `weights`, use that.)

- [ ] **Step 3: Replace `metaOf`, add `_pairOf` and `metaExplain`**

Replace lines 1945–1948:

```javascript
  CompEngine.prototype._pairOf = function (weapon, party, skip) {
    /* Best observed partner of `weapon` among the OTHER seats of `party`
       (mirrors engine.py _pair_of): [score, partner|null]; [0, null] with
       no row — absence is neutral, never a penalty. Ties break on the
       partner id so the explanation matches Python. */
    if (!party || !party.length || !this.metaPairW) return [0.0, null];
    var rows = (this.metaPairs[this.sizeBucket()] || {})[weapon];
    if (!rows) return [0.0, null];
    var best = 0.0, who = null;
    for (var i = 0; i < party.length; i++) {
      if (i === skip) continue;
      var m = party[i], s = rows[m] || 0.0;
      if (s > best || (s === best && who !== null && s && m < who)) { best = s; who = m; }
    }
    return [best, who];
  };

  CompEngine.prototype._soloOf = function (w) {
    if (!this.metaBucketed) return this.metaPrior[w] || 0.0;
    return (this.metaPrior[this.sizeBucket()] || {})[w] || 0.0;
  };

  CompEngine.prototype.metaOf = function (w, party, skip) {
    /* (1 - λ)·solo + λ·best observed partner (mirrors engine.py meta_of). */
    var solo = this._soloOf(w), lam = this.metaPairW;
    if (!lam) return solo;
    return (1.0 - lam) * solo + lam * this._pairOf(w, party, skip)[0];
  };

  CompEngine.prototype.metaExplain = function (w, party) {
    /* Descriptive split of a CANDIDATE's meta term (mirrors engine.py
       meta_explain). Never a scoring input. */
    party = party || [];
    var pr = this._pairOf(w, party), raise_ = 0.0;
    if (this.metaPairW && party.length) {
      var plus = party.concat([w]);
      for (var i = 0; i < party.length; i++) {
        var cur = this._pairOf(party[i], party, i)[0];
        var nw = this._pairOf(party[i], plus, i)[0];
        if (nw > cur) raise_ += nw - cur;
      }
    }
    return { meta_solo: this._soloOf(w), meta_pair: pr[0], meta_partner: pr[1],
             meta_raise: raise_ };
  };
```

Python's `meta_of` must produce the same floating-point sequence: `(1.0 - lam) * solo + lam * pair` in both — keep the operand order identical.

- [ ] **Step 4: `compScore`, `partyState`, `bestLoadout` stub, `_pickTail`**

`compScore` (`:1959`): `meta += this.metaOf(party[i], party, i);`

`partyState` return (`:2005-2008`): add

```javascript
             party: party.slice(),
             pairMax: party.map(function (w, i) { return this._pairOf(w, party, i)[0]; }, this)
```

`bestLoadout` stub state (Select-String `pairVals: \[\]`): add `party: [], pairMax: []`.

`_pickTail` (`:2101-2110`):

```javascript
  CompEngine.prototype._pickTail = function (state, weapon, best) {
    /* Combo-independent candidate-score terms (mirrors engine.py
       _pick_tail). `meta` is the EXACT party-meta delta (2026-09-11): the
       candidate's blended prior plus the raise it hands each member's
       best-partner term. */
    var party = state.party || [];
    var meta = this.metaOf(weapon, party), lam = this.metaPairW;
    if (lam && party.length) {
      var rows = this.metaPairs[this.sizeBucket()] || {};
      for (var i = 0; i < party.length; i++) {
        var s = (rows[party[i]] || {})[weapon] || 0.0;
        if (s > state.pairMax[i]) meta += lam * (s - state.pairMax[i]);
      }
    }
    var dup = (state.counts[weapon] || 0) + 1 - this._dupFree(weapon);
    var score = best.val + this.delta * meta
              + this.viabilityW * this.viabilityOf(weapon)
              - (dup > 0 ? this.rho * dup : 0.0);
    return { score: score, dFit: best.dFit, dSyn: best.dSyn, meta: meta, combo: best.combo };
  };
```

Python adds `lam * (s - pmax[i])` per member in seat order; JS must too (same summation order → same bits).

- [ ] **Step 5: Expose the fields**

`pickReport` record (`:2473`): after `meta_prior: pick.meta,` add `meta_solo: mx.meta_solo, meta_pair: mx.meta_pair, meta_partner: mx.meta_partner, meta_raise: mx.meta_raise,` with `var mx = this.metaExplain(candidate, party);` declared before the return.

`recommend`: in the post-sort loop that sets `caps_gain`/`verdict` on the returned rows, add `var mx = this.metaExplain(r.weapon, party); r.meta_solo = mx.meta_solo; r.meta_pair = mx.meta_pair; r.meta_partner = mx.meta_partner; r.meta_raise = mx.meta_raise;`.

- [ ] **Step 6: Run parity and the JS/Python gates**

Run bare: `py -3 tests/test_js_parity.py` → exit 0, 60 parties at 1e-9.
Then: `py -3 tests/test_forge.py`, `py -3 tests/test_meta_pairs.py`, `py -3 tests/test_interactions.py` → exit 0.

- [ ] **Step 7: Commit**

```powershell
$p = Join-Path $env:TEMP "cf_msg.txt"
[System.IO.File]::WriteAllText($p, "Engine JS: pair-aware meta prior twin; parity on the four meta fields (2026-09-11)`n`n_pairOf / metaOf(w, party, seat) / metaExplain mirror engine.py operand`nfor operand; compScore, partyState (party, pairMax) and _pickTail carry`nthe exact marginal. test_js_parity compares meta_solo / meta_pair /`nmeta_partner / meta_raise on recommend rows and pick_report.`n`nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`n", (New-Object System.Text.UTF8Encoding $false))
git add engine/app_scoring.js tests/test_js_parity.py
git commit -F $p
```

---

### Task 5: Dashboard translation + rebuild + remaining gates

**Files:**
- Modify: `dashboard/_app.js:132-134` (recommend map), `:1685-1700` (why-panel formula block)
- Regenerate: `dashboard/index.html`, `docs/` via `py -3 dashboard/build.py`
- Modify: `.github/workflows/gates.yml:45` (add the new test)

**Interfaces:**
- Consumes: `recommend()` rows carrying `meta_solo`, `meta_pair`, `meta_partner`, `meta_raise` (Tasks 3–4).

- [ ] **Step 1: Carry the fields**

At `dashboard/_app.js:132` extend the mapped object: after `meta: r.meta_prior,` add `metaSolo: r.meta_solo, metaPair: r.meta_pair, metaPartner: r.meta_partner, metaRaise: r.meta_raise,`.

- [ ] **Step 2: One translation line in the why-panel**

In the formula block (`:1691-1699`), after the `<span class="k">metaPrior</span> is observed relevance: ...` sentence, replace that prose sentence with:

```javascript
          <span class="k">metaPrior</span> is observed relevance, half the weapon's own share of killer parties at this fight size (one player, one vote, shrunk on thin counts, the most-fielded weapon = 1) and half its best observed partner already on your roster (one killer party, one vote per pairing, ≥3 guilds, capped at 8× over chance) — a tiebreak-sized nudge that never buys a floor or a seat.${top.metaPartner ? `<br><span class="k">observed with</span> ${nameOf(top.metaPartner)} on your roster — pair score <b>${top.metaPair.toFixed(2)}</b>${top.metaRaise > 0.005 ? `, and it raises the roster's own pairings by <b>${top.metaRaise.toFixed(2)}</b>` : ""}` : ""}
```

`nameOf` is defined at `_app.js:239`. No arithmetic beyond `toFixed` — the UI never computes a score.

- [ ] **Step 3: Rebuild the pages and run the UI gates**

Run: `py -3 dashboard/build.py` then `py -3 tests/test_dashboard_layout.py` and `node tests/test_display_math.js` → exit 0.
Smoke: `py -3 -m http.server --directory dashboard 8765` in the background, open the page (Playwright MCP `browser_navigate` to `http://localhost:8765/`), add Brimstone Staff (`2H_FIRESTAFF_HELL`) to an empty castle 10-man, confirm the why-panel of the top recommendation shows an "observed with Brimstone Staff" line when the top pick has a partner row, screenshot to `.playwright-mcp/`. Stop the server.

- [ ] **Step 4: Add the new test to CI**

In `.github/workflows/gates.yml` after the `python3 tests/test_cohort_families.py` line add `python3 tests/test_meta_pairs.py`. Add the same line to the test list in `CLAUDE.md` (`py -3 tests/test_meta_pairs.py  # pair-aware prior: derivation + blend contracts`).

- [ ] **Step 5: Run the full gate list**

Run each bare, read every output:

```text
py -3 pipeline/evidence_lint.py
py -3 tests/test_golden.py
py -3 tests/test_forge.py
py -3 tests/test_builds.py
py -3 tests/test_interactions.py
py -3 tests/test_provenance.py
py -3 tests/test_patch_history.py
py -3 tests/test_js_parity.py
py -3 tests/test_dashboard_layout.py
py -3 tests/test_cohort_families.py
py -3 tests/test_roles.py
py -3 tests/test_validation_modes.py
py -3 tests/test_meta_pairs.py
node tests/test_loadout_codec.js
node tests/test_display_math.js
node tests/test_live_party.js
py -3 tests/tier2_blindtest.py v4
py -3 tests/tier2_blindtest.py v4h --rebuild 5
```

`v4` must report ≥ 70%. Note `v4` and `v4h` numbers; compare with the pre-change numbers by checking out `HEAD~4` in a scratch worktree (`git worktree add ../bion-before HEAD~4`) and running the same two commands there. Record both in the commit body. Golden failures from Task 3 remain listed, not fixed.

- [ ] **Step 6: Commit**

```powershell
$p = Join-Path $env:TEMP "cf_msg.txt"
[System.IO.File]::WriteAllText($p, "Page: observed-partner line in the why-panel; gates list the pair test (2026-09-11)`n`nv4 before/after: <a>% -> <b>%. v4h before/after: <c>% -> <d>%.`n`nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`n", (New-Object System.Text.UTF8Encoding $false))
git add dashboard/_app.js dashboard/index.html docs/ .github/workflows/gates.yml CLAUDE.md
git commit -F $p
```

---

### Task 6: Rulings and docs

**Files:**
- Modify: `tests/VALIDATION.md` (standing rule 7 at `:42-45`; add an index row in the owner-rulings table for 2026-09-11)
- Modify: `notes/validation/2026-09b.md` (append a dated entry)
- Modify: `KILLBOARD_AFFINITY.md:87-89` ("sanctioned uses" / "still parked")
- Modify: `HANDOFF.md` "The engine today" prior bullet (search `meta prior is GENERATED`)
- Modify: `pipeline/README.md` (search `derive_meta_prior`)
- Modify: `BACKLOG.md`
- Modify: `notes/specs/2026-09-11-pair-meta-prior-design.md` status line

- [ ] **Step 1: Amend standing rule 7**

Replace rule 7 in `tests/VALIDATION.md`:

```markdown
7. **Popularity is not effectiveness**: the killboard, cohort families and
   reference builds are display/evidence only; effectiveness claims are
   reserved for win-lift evidence (kill-vs-death contrast needs a ruling before
   it orders anything, 2026-09-08). The ONE empirical scoring input is the
   harvest-generated meta prior — solo (2026-09-08) and best-observed-partner
   (2026-09-11) — tiebreak-sized under `delta`, derived on the training split
   (`battle % 5 != 0`), never a floor, a seat, a pool place or a penalty.
```

Add an index row (match the table's existing columns) : `2026-09-11 | pair-aware meta prior: observed pairings enter through the prior only, one party one vote gated by >=3 guilds, training split, 0.5/0.5 blend | pins: test_meta_pairs A1-A13, B1-B8; parity fields | notes/validation/2026-09b.md "Pair-aware meta prior"`.

- [ ] **Step 2: Append the dated log entry**

Append to `notes/validation/2026-09b.md`:

```markdown
## 2026-09-11 — Pair-aware meta prior

Owner: "wouldnt it be cool to add synergy to comps based on what weapons
are often seen playing together with real data ?" Offered A (inside the
meta prior), B (inside synergy — advised against: only verified
interaction records score), C (pool ordering only). Ruling: **A**. Vote
unit: one killer party, one vote per distinct pair, a pair carries a row
only across >=3 distinct guild-sets and >=5 parties. Holdout: the shipped
prior (solo AND pair) learns from `battle % 5 != 0` only. Blend: 0.5 solo
+ 0.5 best observed partner, always (continuous; first-pick ranking
unchanged, magnitude halved). Anti-affinity reads 0. Probe that grounded
it: top small-fight pair Arcane + Brimstone 24x over chance across 18
guilds; Badon + Locus 15x / 40 guilds — the interactions the engine
already prices from spell facts. Golden rows moved: <from Task 3>. Gate:
v4 <a> -> <b>; v4h <c> -> <d> (report-only; style_bands / role_counts
still learn from all battles — BACKLOG).
Spec: notes/specs/2026-09-11-pair-meta-prior-design.md.
```

- [ ] **Step 3: KILLBOARD_AFFINITY, HANDOFF, pipeline README, BACKLOG, spec status**

`KILLBOARD_AFFINITY.md:89`: replace "Still parked behind review: ANY empirical/scoring integration beyond the two owner-ruled uses above" with "Still parked behind review: ANY empirical/scoring integration beyond the two owner-ruled uses above and the harvest-generated meta prior (solo 2026-09-08, best-observed-partner 2026-09-11 — from the official-API party channel, never from this cohort channel)". Keep the rest of the sentence.

`HANDOFF.md` prior bullet: after "The meta prior is GENERATED from the harvest" add "(solo share and, since 2026-09-11, the best observed partner already on the roster, blended 0.5/0.5 under `weights.meta_pair`; training split only; `derive_meta_prior.py`)".

`pipeline/README.md`: where `derive_meta_prior.py` is described, add one sentence: "Since 2026-09-11 it also writes `meta_pairs` (one party one vote per distinct pair, >=3 guild-sets, log2-lift capped at 8x, shrunk n/(n+8)) and both tables learn from `battle % 5 != 0` only; `--all-battles` writes an audit copy `build_dataset` refuses."

`BACKLOG.md`: add under the harvest/validation section: "- **Holdout everywhere**: `derive_style_bands.py` and `derive_role_counts.py` still learn from all battles; the prior honours `battle % 5 != 0` since 2026-09-11. Until they match, `v4h` stays report-only. Re-derive the pair prior on the harvest checkout after the next fold (`fold_harvest.ps1` already runs `derive_meta_prior`)."

Spec status line → `Status: SHIPPED 2026-09-11 (main). Deviations: <none | list>`.

- [ ] **Step 4: Commit and push**

```powershell
$p = Join-Path $env:TEMP "cf_msg.txt"
[System.IO.File]::WriteAllText($p, "Validation: pair-aware meta prior ruling (2026-09-11) — rule 7 amended, log, docs`n`nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`n", (New-Object System.Text.UTF8Encoding $false))
git add tests/VALIDATION.md notes/validation/2026-09b.md KILLBOARD_AFFINITY.md HANDOFF.md pipeline/README.md BACKLOG.md notes/specs/2026-09-11-pair-meta-prior-design.md
git commit -F $p
git push origin main
```

Push only after every gate in Task 5 Step 5 passed (CI runs the same list; deploy is on push).
