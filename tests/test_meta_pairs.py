#!/usr/bin/env python3
"""
Pair-aware meta prior contracts (standing rule 7, spec
notes/specs/2026-09-11-pair-meta-prior-design.md).

Part A — derivation (pipeline/derive_meta_prior.py) on a synthetic
party_rosters doc: the training split is honoured, one party = one vote
per DISTINCT pair, the org gate holds, lift is capped/shrunk exactly as
specified, anti-affinity is omitted (never a penalty), the map is
symmetric and the split is recorded.

Part B — engine blend (engine/engine.py) on the committed dataset:
meta_of is (1-lam)*solo + λ·best-partner, self-seat excluded, ≤ 1, and the
pick score stays the EXACT comp_score delta with pair terms in play.

Part C — the matchmaking pools' own prior (pipeline/derive_portal_prior.py,
build_dataset.load_portal_prior, both engine ports through meta_pools):
only dominant, fully known, in-catalog parties of a pool's sizes on the
training split vote, one player one vote, the floor holds, and the build
refuses an all-battles, mismatched or misplaced file; inside a pool the
pick score stays the exact comp_score delta at the pool's weight.

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
    appears in every party (lift = 1 -> neutral, omitted)."""
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
        # three distinct guilds so only the SPLIT, not the org gate, drops E+F
        ps.append(party(h, ["E", "F", "X", "Y"] + ["S%d" % i for i in range(6)], ("H%d" % (h // 5 % 3),), 10))
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
    allb = dmp.derive(doc, holdout_mod=None)
    check("A11 --all-battles derivation includes E+F and records the split as None",
          "F" in allb["meta_pairs"]["mid"].get("E", {})
          and allb["_split"]["holdout_mod"] is None, "")
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
    check("B2 meta_of alone = (1-lam)*solo",
          abs(e.meta_of(w, [w], 0) - (1 - lam) * solo.get(w, 0.0)) < 1e-12,
          f"{e.meta_of(w, [w], 0)}")
    check("B3 meta_of with its best partner = (1-lam)*solo + lam*s",
          abs(e.meta_of(w, [m, w], 1) - ((1 - lam) * solo.get(w, 0.0) + lam * s)) < 1e-12, "")
    check("B4 self-seat excluded: a duplicate of w is not w's partner",
          abs(e.meta_of(w, [w, w], 0) - (1 - lam) * solo.get(w, 0.0)) < 1e-12, "")
    check("B5 meta_of never exceeds 1",
          all(e.meta_of(x, [m, x], 1) <= 1.0 + 1e-12 for x in e.weapons), "")
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
          abs(rep["meta_prior"] - (after - before)) < 1e-9,
          f"{rep['meta_prior']} vs {after - before}")
    # same pattern as test_forge F1: None combos are legal, the kit the
    # pick chose rides along as the candidate's gear
    check("B8 pick score is the exact comp_score delta",
          abs(rep["score"] - (e.comp_score(p + [w], [None, rep["combo"]],
                                           [None, rep["kit"] or None])
                              - e.comp_score(p, [None]))) < 1e-9,
          "")


def portal_doc():
    """Training battles: six dominant trios fielding A+B+C and six fielding
    M+N+O, each set across three guilds; one trio with a death (D+E+F),
    one trio on a holdout battle (G+H+I), one fielding a weapon outside
    the catalog (J+K+Z), one dominant eight (L x8). Player P1 plays A in
    two battles."""
    ps, builds, bid = [], [], 1

    def add(battle, weapons, guild, deaths=0, kills=2, players=None):
        ps.append({"battle": battle, "index": 0, "size": len(weapons),
                   "known_weapons": len(weapons), "weapons": list(weapons),
                   "guilds": [guild], "deaths": deaths, "kills": kills})
        for i, w in enumerate(weapons):
            pl = (players or {}).get(i) or f"{battle}-{i}"
            builds.append({"battle": battle, "party": 0, "player": pl, "weapon": w})

    def nxt():
        nonlocal bid
        bid += 1
        while bid % 5 == 0:
            bid += 1
        return bid
    for j, g in enumerate(("G1", "G2", "G3", "G1", "G2", "G3")):
        add(nxt(), ["A", "B", "C"], g, players={0: "P1"} if j < 2 else None)
        add(nxt(), ["M", "N", "O"], g)
    add(nxt(), ["D", "E", "F"], "G1", deaths=1)
    add(10, ["G", "H", "I"], "G2")
    add(nxt(), ["J", "K", "Z"], "G3")
    add(nxt(), ["L"] * 8, "G1")
    return {"parties": ps, "builds": builds}


def part_c():
    import json
    import tempfile
    import derive_portal_prior as dpp
    catalog = set("ABCDEFGHIJKLMNO")
    out = dpp.derive(portal_doc(), catalog, floor=1)
    pool = out["pools"].get("2-3") or {}
    solo = pool.get("solo") or {}
    check("C1 the pool prior records the training split and its content",
          out["_split"] == {"holdout_mod": 5,
                            "rule": "battle % 5 != 0 (training split; % 5 == 0 is the v4h holdout)"}
          and out["_content"] == "ancient_lands", str(out.get("_split")))
    check("C2 only dominant, fully known, in-catalog parties of the pool on the "
          "training split vote (a death, a holdout battle, a weapon outside the "
          "catalog, a size outside every pool cast none)",
          set(solo) == set("ABCMNO") and sorted(out["pools"]) == ["2-3"], str(sorted(solo)))
    check("C3 one player, one vote: P1 on A in two battles counts once",
          pool["players"]["A"] == 5 and pool["players"]["B"] == 6, str(pool.get("players")))
    check("C4 the pool's top weapon reads 1.0", max(solo.values()) == 1.0, str(solo))
    lift = 6 * 12 / (6 * 6)
    want = round(min(math.log2(lift), 3.0) / 3.0 * 6 / (6 + 8.0), 3)
    pairs = pool.get("pairs") or {}
    check("C5 pairs: one party one vote, symmetric, the meta prior's formula",
          pairs.get("A", {}).get("B") == want == pairs.get("B", {}).get("A")
          and "M" not in pairs.get("A", {}), f"{pairs.get('A')} vs {want}")
    check("C6 a pool under the floor of distinct rosters carries no prior",
          dpp.derive(portal_doc(), catalog)["pools"] == {}, "")
    import build_dataset as bd
    import rosters_io
    sha = rosters_io.sha256(rosters_io.path(bd.OUT))
    tpl = {"ancient_lands": {"pool_fielded": {"2-3": {"sizes": [2, 3], "weapons": []}}}}

    def load(doc):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f)
        try:
            return bd.load_portal_prior(catalog, tpl, path)
        except SystemExit:
            return "refused"
        finally:
            os.unlink(path)
    good = dict(out, _source={"party_rosters_sha256": sha})
    got = load(good)
    check("C7 the build attaches a pool's sizes, solo and pairs under its content",
          got != "refused" and got["ancient_lands"]["2-3"]["solo"] == solo
          and got["ancient_lands"]["2-3"]["pairs"] == pairs, str(got)[:120])
    check("C8 the build refuses an all-battles file, a file of another artifact "
          "and a pool with no fielded list of its sizes",
          load(dict(good, _split={"holdout_mod": None})) == "refused"
          and load(dict(out, _source={"party_rosters_sha256": "0" * 64})) == "refused"
          and load(dict(good, pools={"6-7": dict(pool, sizes=[6, 7])})) == "refused", "")
    from engine import Engine
    e = Engine(content="ancient_lands", size=5)
    p5 = e.prior_pool
    if p5 is None:
        check("C9 the portal's 4-5 pool reads a prior of its own", False, "no pool prior at 5")
        return
    w, m, s = max(((a, b, v) for a, row in p5["pairs"].items() for b, v in row.items()
                   if a in e.weapons and b in e.weapons), key=lambda t: (t[2], t[0], t[1]))
    rep = e.pick_report([m], w)
    check("C9 inside a pool the pick score is the exact comp_score delta at the "
          "pool's weight, its own best pair in play",
          abs(e.delta - e._delta_base * e.pool_delta_x) < 1e-12 and rep["meta_pair"] == s
          and abs(rep["score"] - (e.comp_score([m, w], [None, rep["combo"]],
                                               [None, rep["kit"] or None])
                                  - e.comp_score([m], [None]))) < 1e-9,
          f"{w}+{m} s={s} meta_pair={rep['meta_pair']}")


def run():
    part_a()
    part_b()
    part_c()
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
