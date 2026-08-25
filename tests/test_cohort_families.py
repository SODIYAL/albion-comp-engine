#!/usr/bin/env python3
"""
Cohort-family artifact contracts — pipeline/build_cohort_families.py.

The families feed a public display surface, so the artifact must hold the
same honesty rules as the rest of the killboard layer: counts only (no
organization or battle identifiers can reach the page), disjoint families
(cohort counts never double-count), gates actually enforced, and a
byte-identical rebuild (the LF/determinism discipline every committed
pipeline artifact keeps).

Run:  py -3 tests/test_cohort_families.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
BUILDER = os.path.join(ROOT, "pipeline", "build_cohort_families.py")
OUT = os.path.join(ROOT, "pipeline", "out", "cohort_families.json")
USAGE = os.path.join(ROOT, "pipeline", "out", "weapon_usage_v2.json")
DATASET = os.path.join(ROOT, "pipeline", "out", "dataset-latest.json")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def run():
    r1 = subprocess.run([sys.executable, BUILDER], capture_output=True,
                        text=True, encoding="utf-8")
    check("builder exits 0", r1.returncode == 0, r1.stdout + r1.stderr)
    with open(OUT, "rb") as f:
        first = f.read()
    r2 = subprocess.run([sys.executable, BUILDER], capture_output=True,
                        text=True, encoding="utf-8")
    with open(OUT, "rb") as f:
        second = f.read()
    check("rebuild is byte-identical (deterministic, LF-only)",
          r2.returncode == 0 and first == second and b"\r" not in first,
          f"len {len(first)} vs {len(second)}")

    doc = json.loads(first.decode("utf-8"))
    with open(USAGE, encoding="utf-8") as f:
        usage = json.load(f)
    with open(DATASET, encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])
    p = doc["params"]

    # counts only — no organization or battle identifiers in the artifact
    text = first.decode("utf-8")
    check("no org/battle identifiers leak into the artifact",
          "alliance:" not in text and "guild:" not in text
          and "battle_id" not in text,
          "identifier substring found")

    ok_shape, ok_gates, ok_disjoint = True, True, True
    detail = []
    for bucket, fams in doc["buckets"].items():
        usable = sum(
            1 for r in usage["cohorts"].get(bucket, [])
            if len(set(w for w in (r.get("weapons") or []) if w in known)) >= 2)
        claimed = sum(f["cohorts"] for f in fams)
        if claimed + doc["unassigned"][bucket] != usable:
            ok_disjoint = False
            detail.append(f"{bucket}: {claimed}+{doc['unassigned'][bucket]}"
                          f" != {usable} usable")
        for f in fams:
            a = f["anchor"]
            if not (len(a) == 2 and a == sorted(a)
                    and all(w in known for w in a)):
                ok_shape = False
                detail.append(f"{bucket} anchor {a}")
            if not (f["cohorts"] >= p["min_cohorts"]
                    and p["min_orgs"] <= f["orgs"] <= f["cohorts"]
                    and p["min_battles"] <= f["battles"] <= f["cohorts"]
                    and f["lift"] >= p["min_lift"]):
                ok_gates = False
                detail.append(f"{bucket} gates {a}: {f['cohorts']}/"
                              f"{f['orgs']}/{f['battles']}/{f['lift']}")
            shares = [c["share"] for c in f["cast"]]
            if not all(0 < s <= 1 for s in shares) or \
                    any(shares[i] < shares[i + 1]
                        for i in range(len(shares) - 1)):
                ok_shape = False
                detail.append(f"{bucket} cast shares {a}: {shares}")
    check("families are disjoint: per-bucket cohort counts + unassigned "
          "sum to the usable cohorts", ok_disjoint, "; ".join(detail))
    check("anchors are sorted known pairs; cast shares in (0,1], "
          "non-increasing", ok_shape, "; ".join(detail))
    check("every family passes the published support/org/battle/lift gates",
          ok_gates, "; ".join(detail))

    # the 2026-08 sample's known yield — a canary against silent gate drift
    # (update alongside a sample refresh, not to make a red test green)
    check("committed sample yields families where the data supports them "
          "(large >= 3) and none where it does not (small == 0)",
          len(doc["buckets"].get("large") or []) >= 3
          and len(doc["buckets"].get("small") or []) == 0,
          f"large={len(doc['buckets'].get('large') or [])} "
          f"small={len(doc['buckets'].get('small') or [])}")

    print("=" * 74)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, det in results:
        print(f"{'PASS' if ok else 'FAIL':4}  {name}"
              + (f"\n      {det}" if det and not ok else ""))
    print("=" * 74)
    print(f"{passed}/{len(results)} cohort-family tests passed")
    return passed, len(results)


if __name__ == "__main__":
    p, n = run()
    sys.exit(0 if p == n else 1)
