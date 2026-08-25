#!/usr/bin/env python3
"""
Recurring observed composition families (roadmap item 7, 2026-08-24).

Reads the committed cohort sample (out/weapon_usage_v2.json) and mines the
recurring weapon CORES per fight-size bucket into out/cohort_families.json.

Why anchor pairs, not roster clustering: the cohort baskets are PARTIAL
observations of rosters (kill-event coverage — most baskets hold 2-5 of a
20-man lineup), so whole-basket distance clustering measured on this
sample separates observation noise, not comps (cross-org Jaccard median
0.0, p90 0.17 on the 2026-08 sample; the lift-gated co-occurrence graph is
one connected component at every threshold tried). Pairs are the largest
itemset with real support, so a family is:

  anchor  — the strongest remaining recurring PAIR (support gates below),
  cohorts — every remaining cohort containing BOTH anchor weapons,
  cast    — weapons observed in >= CAST_SHARE of those cohorts (with their
            observed shares; descriptive, never a membership claim).

Families are extracted greedily and DISJOINT (a family's cohorts leave the
pool before the next anchor is mined), so cohort counts never double-count
and one ubiquitous weapon cannot anchor everything. Deterministic: pure
counting, lexicographic tie-breaks, no randomness, LF-only output.

Honesty gates: an anchor needs MIN_COHORTS cohorts, MIN_ORGS distinct
organizations and MIN_BATTLES distinct battles (one alliance spamming one
lineup, or one battle observed many times, is not a "recurring family"),
plus popularity-corrected pair lift >= MIN_LIFT (two globally common
weapons co-occurring at chance rate are not a core). Weapon keys are
filtered against the built dataset so retired keys can never anchor a
family — run AFTER build_dataset.py.

The output carries COUNTS only: organization identifiers and battle ids
stay in weapon_usage_v2.json for audit and never enter this artifact or
the page. DISPLAY EVIDENCE ONLY — nothing here feeds scoring, suggestion
pools, or the forge (KILLBOARD_AFFINITY.md; empirical scoring stays
parked behind an owner ruling).

Run:  py -3 pipeline/build_cohort_families.py
"""
import collections
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
USAGE = os.path.join(HERE, "out", "weapon_usage_v2.json")
DATASET = os.path.join(HERE, "out", "dataset-latest.json")
OUT = os.path.join(HERE, "out", "cohort_families.json")

# PROVISIONAL thresholds (2026-08-24) — chosen by inspection of the
# committed 2026-08 sample (305 cohorts): large yields 5 families incl.
# the observed ZvZ meta core, mid 1, small 0 (honestly thin). Revisit
# with a bigger sample, not by loosening gates until families appear.
MIN_COHORTS = 5    # anchor pair must recur in this many cohorts
MIN_ORGS = 3       # ...across this many distinct organizations
MIN_BATTLES = 3    # ...and this many distinct battles
MIN_LIFT = 1.2     # pair lift both*N/(cA*cB): >= 20% over chance
CAST_SHARE = 0.4   # cast = weapons in >= this share of the family's cohorts


def mine_bucket(rows, known):
    """Greedy disjoint anchor-pair families for one bucket."""
    remaining = [(frozenset(w for w in (r.get("weapons") or []) if w in known),
                  r["cohort"], r["battle_id"]) for r in rows]
    remaining = [x for x in remaining if len(x[0]) >= 2]
    families = []
    while len(remaining) >= MIN_COHORTS:
        n_total = len(remaining)
        count = collections.Counter()
        for ws, _, _ in remaining:
            for w in ws:
                count[w] += 1
        stats = collections.defaultdict(lambda: [0, set(), set()])
        for ws, org, bid in remaining:
            for p in itertools.combinations(sorted(ws), 2):
                st = stats[p]
                st[0] += 1
                st[1].add(org)
                st[2].add(bid)
        best = None
        for p in sorted(stats):   # lexicographic tie-break, deterministic
            n, orgs, bats = stats[p]
            if n < MIN_COHORTS or len(orgs) < MIN_ORGS \
                    or len(bats) < MIN_BATTLES:
                continue
            lift = n * n_total / (count[p[0]] * count[p[1]])
            if lift < MIN_LIFT:
                continue
            key = (n, len(orgs), len(bats))
            if best is None or key > best[0]:
                best = (key, p, lift)
        if best is None:
            break
        (n, n_orgs, n_battles), anchor, lift = best
        members = [x for x in remaining
                   if anchor[0] in x[0] and anchor[1] in x[0]]
        cast_count = collections.Counter()
        for ws, _, _ in members:
            for w in ws:
                if w not in anchor:
                    cast_count[w] += 1
        floor = max(2, CAST_SHARE * len(members))
        cast = [{"weapon": w, "share": round(c / len(members), 3)}
                for w, c in sorted(cast_count.items(),
                                   key=lambda kv: (-kv[1], kv[0]))
                if c >= floor]
        families.append({
            "anchor": sorted(anchor),
            "cohorts": n,
            "orgs": n_orgs,
            "battles": n_battles,
            "lift": round(lift, 2),
            "cast": cast,
        })
        remaining = [x for x in remaining if x not in members]
    return families, len(remaining)


def main():
    if not os.path.exists(USAGE):
        print("FAIL: out/weapon_usage_v2.json missing — nothing to mine")
        return 2
    if not os.path.exists(DATASET):
        print("FAIL: out/dataset-latest.json missing — run build_dataset.py "
              "first (family anchors are filtered against the catalog)")
        return 2
    with open(USAGE, encoding="utf-8") as f:
        usage = json.load(f)
    with open(DATASET, encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])
    cohorts = usage.get("cohorts")
    if not isinstance(cohorts, dict):
        print("FAIL: usage sample carries no cohorts — refresh with "
              "sample_battles.py before mining families")
        return 2
    out = {
        "generated_from": usage.get("generated_utc"),
        "server": usage.get("server"),
        "semantics": (
            "Recurring observed cores mined from organization cohorts: an "
            "anchor pair seen together across multiple orgs and battles, "
            "with the weapons frequently observed alongside. Cohorts are "
            "Alliance/Guild kill-feed observations, NOT parties; counts "
            "only, no identifiers; display evidence only — never a "
            "scoring input."),
        "params": {"min_cohorts": MIN_COHORTS, "min_orgs": MIN_ORGS,
                   "min_battles": MIN_BATTLES, "min_lift": MIN_LIFT,
                   "cast_share": CAST_SHARE},
        "buckets": {},
        "unassigned": {},
    }
    for bucket in sorted(cohorts):
        fams, leftover = mine_bucket(cohorts[bucket], known)
        out["buckets"][bucket] = fams
        out["unassigned"][bucket] = leftover
        print(f"  {bucket}: {len(fams)} families "
              f"({leftover} cohorts unassigned)")
        for fi, fam in enumerate(fams):
            print(f"    F{fi + 1}: {' + '.join(fam['anchor'])} — "
                  f"{fam['cohorts']} cohorts / {fam['orgs']} orgs / "
                  f"{fam['battles']} battles, lift {fam['lift']}, "
                  f"cast {len(fam['cast'])}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"wrote {os.path.relpath(OUT, os.path.join(HERE, os.pardir))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
