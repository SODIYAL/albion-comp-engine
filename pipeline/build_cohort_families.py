#!/usr/bin/env python3
"""
Recurring observed composition families (roadmap item 7).

Reads the committed cohort sample (out/weapon_usage_v2.json, written by
derive_usage.py: killer parties, bucketed by party size) and mines the
recurring weapon CORES per bucket into out/cohort_families.json.

A family is an anchor pair, not a roster cluster:

  anchor  — the strongest remaining recurring PAIR (support gates below),
  cohorts — every remaining cohort containing BOTH anchor weapons,
  cast    — weapons observed in >= CAST_SHARE of those cohorts (with their
            observed shares; descriptive, never a membership claim).

Pairs are the largest itemset with support in every bucket: two random
killer parties share little (Jaccard over distinct weapons, measured on
the sample: median 0.00 / p90 0.17 at 2-5, 0.07 / 0.19 at 6-15, 0.22 /
0.41 at 16+). Whole-roster clustering was measured and rejected on the
earlier partial-basket sample; on full parties it is untested.

Families are extracted greedily and DISJOINT (a family's cohorts leave the
pool before the next anchor is mined), so cohort counts never double-count
and one ubiquitous weapon cannot anchor everything. Deterministic: pure
counting, lexicographic tie-breaks, no randomness, LF-only output.

Honesty gates: an anchor needs max(MIN_COHORTS, MIN_SHARE of the bucket's
usable cohorts) cohorts, MIN_ORGS distinct organizations and MIN_BATTLES
distinct battles (one squad fielding one lineup night after night, or one
battle observed many times, is not a "recurring family"), plus
popularity-corrected pair lift >= MIN_LIFT (two globally common weapons
co-occurring at chance rate are not a core). Weapon keys are filtered
against the built dataset so retired keys can never anchor a family — run
AFTER build_dataset.py.

DISTINCT ORGANIZATIONS. A killer party lists the guilds of its members.
Two cohorts sharing any guild are one organization, transitively: the
count is the number of guild-linked groups among the anchor's cohorts. A
guild fielding its lineup with different guests each night is one group,
not several. A party with no guild adds a cohort and no organization.

The output carries COUNTS only: guild names and battle ids stay in
weapon_usage_v2.json for audit and never enter this artifact or the
page. DISPLAY EVIDENCE ONLY — nothing here feeds scoring, suggestion
pools, or the forge (KILLBOARD_AFFINITY.md; empirical scoring stays
parked behind a maintainer decision).

Run:  py -3 pipeline/build_cohort_families.py
"""
import collections
import itertools
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
USAGE = os.path.join(HERE, "out", "weapon_usage_v2.json")
DATASET = os.path.join(HERE, "out", "dataset-latest.json")
OUT = os.path.join(HERE, "out", "cohort_families.json")

# PROVISIONAL thresholds (curation judgment, by inspection of the sample).
# The cohort floor is a SHARE of the bucket so the gate holds its meaning
# when the sample grows: at 1,000 cohorts a bucket an absolute floor of 5
# admits 44 / 40 / 15 families (2-5 / 6-15 / 16+), most of them noise.
# Revisit with the sample, never by loosening gates until families appear.
MIN_COHORTS = 5    # anchor pair must recur in this many cohorts ...
MIN_SHARE = 0.02   # ... and in this share of the bucket's usable cohorts
MIN_ORGS = 3       # ...across this many distinct organizations
MIN_BATTLES = 3    # ...and this many distinct battles
MIN_LIFT = 1.2     # pair lift both*N/(cA*cB): >= 20% over chance
CAST_SHARE = 0.4   # cast = weapons in >= this share of the family's cohorts


def org_groups(guild_lists):
    """Distinct organizations among cohorts: groups linked by a shared
    guild (union-find over guild names). Unguilded cohorts add none."""
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for guilds in guild_lists:
        if not guilds:
            continue
        for g in guilds:
            parent.setdefault(g, g)
        root = find(guilds[0])
        for g in guilds[1:]:
            parent[find(g)] = root
    return len({find(g) for g in parent})


def cohort_floor(usable):
    """The cohort count an anchor needs in a bucket of `usable` cohorts."""
    return max(MIN_COHORTS, math.ceil(MIN_SHARE * usable))


def mine_bucket(rows, known):
    """Greedy disjoint anchor-pair families for one bucket."""
    remaining = [(frozenset(w for w in (r.get("weapons") or []) if w in known),
                  tuple(r.get("guilds") or ()), r["battle_id"]) for r in rows]
    remaining = [x for x in remaining if len(x[0]) >= 2]
    floor_n = cohort_floor(len(remaining))
    families = []
    while len(remaining) >= floor_n:
        n_total = len(remaining)
        count = collections.Counter()
        for ws, _, _ in remaining:
            for w in ws:
                count[w] += 1
        stats = collections.defaultdict(lambda: [0, [], set()])
        for ws, guilds, bid in remaining:
            for p in itertools.combinations(sorted(ws), 2):
                st = stats[p]
                st[0] += 1
                st[1].append(guilds)
                st[2].add(bid)
        best = None
        for p in sorted(stats):   # lexicographic tie-break, deterministic
            n, guild_lists, bats = stats[p]
            if n < floor_n or len(bats) < MIN_BATTLES:
                continue
            lift = n * n_total / (count[p[0]] * count[p[1]])
            if lift < MIN_LIFT:
                continue
            n_orgs = org_groups(guild_lists)
            if n_orgs < MIN_ORGS:
                continue
            key = (n, n_orgs, len(bats))
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
        taken = {id(x) for x in members}
        remaining = [x for x in remaining if id(x) not in taken]
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
              "derive_usage.py before mining families")
        return 2
    out = {
        "generated_from": (usage.get("window") or {}).get("to"),
        "semantics": (
            "Recurring observed cores mined from killer-party cohorts: an "
            "anchor pair fielded together across multiple organizations "
            "and battles, with the weapons frequently fielded alongside. "
            "A cohort is one killer party as the kill event lists it; an "
            "organization is a group of parties linked by a shared guild. "
            "Counts only, no identifiers; display evidence only — never a "
            "scoring input."),
        "params": {"min_cohorts": MIN_COHORTS, "min_share": MIN_SHARE,
                   "min_orgs": MIN_ORGS, "min_battles": MIN_BATTLES,
                   "min_lift": MIN_LIFT, "cast_share": CAST_SHARE},
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
