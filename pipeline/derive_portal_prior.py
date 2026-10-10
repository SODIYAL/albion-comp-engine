"""The Dragon Portal pools' own meta prior, from the COMMITTED harvest.

The meta prior (derive_meta_prior.py) buckets the battle-list harvest by
size alone, so inside a Dragon Portal pool the engine read the open-world
small (2-5) or mid (6-15) bucket: what open-world killer parties field,
not what the pool's winners field. This step derives, per matchmaking
pool, the same two tables on the pool's own evidence unit (the unit of
derive_portal_rows.py): the dominant killer party of the pool's size
inside the Ancient Lands (no deaths, a kill, every weapon known and in
the catalog), on the TRAINING split (battle % 5 != 0; % 5 == 0 is the
holdout tests/tier2_blindtest.py v4h evaluates).

    solo   ONE PLAYER, ONE VOTE: distinct players seen on weapon w in the
           pool's dominant parties (a build joins its party by the
           analyzer's party index); share of the pool's voters, shrunk
           n/(n+K), normalized so the pool's top weapon is 1.0, rows under
           MIN_PRIOR omitted (no signal, never a penalty)
    pairs  ONE PARTY, ONE VOTE per distinct pair it fields; a pair needs
           MIN_PAIR_PARTIES parties across MIN_PAIR_ORGS guild-sets;
           s = clamp(log2 lift, 0, LOG_CAP)/LOG_CAP * n/(n+K), lift <= 1
           reads 0 (anti-affinity is never a penalty)

The constants and formulas are derive_meta_prior's. A pool carries a
prior where it carries a fielded list today (2-3, 4-5, 6-7) and holds the
floor of distinct rosters; the 15-20 pool's prior waits with its list for
200 rosters (BACKLOG "The Dragon Portal's 15-20 pool at 200 rosters").

build_dataset attaches the pools to `scoring.meta_pools` (hash-gated to
the artifact, refused when not derived on the training split, a hand-set
map refused). Both engine ports read a pool's tables in place of the size
bucket's at a size inside the pool, weighted `weights.pool_delta_x` x
`delta` (tests/VALIDATION.md, The Dragon Portal pools read their own
prior). Everywhere else the size bucket's prior stands at `delta`.

Explicit step, never part of a normal build; the fold runs it after
derive_meta_prior. Reads the COMMITTED roster artifact (`--rosters` names
another file, for a run against a git-shown copy while the harvest
rewrites the working file) and the dataset's weapon catalog.

    py -3 pipeline/derive_portal_prior.py
"""
import argparse
import collections
import datetime
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
TARGET = os.path.join(OUT, "portal_prior.json")
sys.path.insert(0, HERE)
import jsonfmt  # noqa: E402
import party_link  # noqa: E402
import rosters_io  # noqa: E402
from derive_meta_prior import (HOLDOUT_MOD, K, LOG_CAP, MIN_PAIR_ORGS,  # noqa: E402
                               MIN_PAIR_PARTIES, MIN_PRIOR, in_split, pair_score)

CONTENT = "ancient_lands"
# (key, lo, hi): the matchmaking pools that carry a prior of their own,
# keyed as derive_portal_rows.py keys `pool_rows` and `pool_fielded`
POOLS = (("2-3", 2, 3), ("4-5", 4, 5), ("6-7", 6, 7))
FLOOR = 40   # distinct rosters a pool needs (derive_portal_rows.FLOOR)


def dominant_parties(doc, catalog, holdout_mod=HOLDOUT_MOD):
    """{pool key: [party]}: the dominant, fully known killer parties of
    each pool's sizes on the training split (derive_portal_rows'
    select_parties unit), and the battle -> parties map."""
    by_battle = party_link.parties_by_battle(doc)
    out = {key: [] for key, _lo, _hi in POOLS}
    for battle in sorted(by_battle, key=lambda b: (type(b).__name__, b)):
        if not in_split(battle, holdout_mod):
            continue
        for p in by_battle[battle]:
            n = p.get("size") or 0
            ws = p.get("weapons") or []
            if p.get("known_weapons") != n or len(ws) != n or any(w not in catalog for w in ws):
                continue
            if not ((p.get("deaths") or 0) == 0 and (p.get("kills") or 0) > 0):
                continue
            for key, lo, hi in POOLS:
                if lo <= n <= hi:
                    out[key].append(p)
    return out, by_battle


def derive(doc, catalog, k=K, min_prior=MIN_PRIOR, holdout_mod=HOLDOUT_MOD,
           log_cap=LOG_CAP, min_pair_parties=MIN_PAIR_PARTIES,
           min_pair_orgs=MIN_PAIR_ORGS, floor=FLOOR):
    pools, by_battle = dominant_parties(doc, catalog, holdout_mod)
    member = {}
    for key, ps in pools.items():
        for p in ps:
            member[(p["battle"], p["index"])] = key
    # ---- solo: distinct players per weapon per pool (one player, one vote)
    voters = {key: collections.defaultdict(set) for key, _lo, _hi in POOLS}
    linked = collections.Counter()
    for b in doc.get("builds") or []:
        if not b.get("player") or not b.get("weapon"):
            continue
        idx = party_link.link_build(b, by_battle)
        key = member.get((b.get("battle"), idx)) if idx is not None else None
        if key is None:
            continue
        linked[key] += 1
        voters[key][b["weapon"]].add(b["player"])
    out = {}
    for key, lo, hi in POOLS:
        ps = pools[key]
        rosters = len({tuple(sorted(p["weapons"])) for p in ps})
        if rosters < floor:
            continue          # under the floor: the pool reads the size bucket
        counts = {w: len(s) for w, s in voters[key].items()}
        total = sum(counts.values())
        shrunk = {w: (n / total) * (n / (n + k)) for w, n in counts.items()} if total else {}
        top = max(shrunk.values()) if shrunk else 1.0
        rows = {w: round(s / top, 3) for w, s in shrunk.items()}
        solo = {w: v for w, v in sorted(rows.items()) if v >= min_prior}
        # ---- pairs: one party, one vote per distinct pair it fields
        n_w, n_ab = collections.Counter(), collections.Counter()
        orgs = collections.defaultdict(set)
        for p in ps:
            ws = sorted(set(p.get("weapons") or []))
            for w in ws:
                n_w[w] += 1
            org = tuple(sorted(p.get("guilds") or []))
            for a, b2 in itertools.combinations(ws, 2):
                n_ab[(a, b2)] += 1
                if org:      # an unknown guild-set casts no org vote
                    orgs[(a, b2)].add(org)
        pairs, support = {}, {}
        for (a, b2), n in sorted(n_ab.items()):
            if n < min_pair_parties or len(orgs.get((a, b2), ())) < min_pair_orgs:
                continue
            s = round(pair_score(n, n_w[a], n_w[b2], len(ps), k, log_cap), 3)
            if s < min_prior:
                continue
            pairs.setdefault(a, {})[b2] = s
            pairs.setdefault(b2, {})[a] = s
            support[f"{a}|{b2}"] = n
        out[key] = {"sizes": [lo, hi], "parties": len(ps), "rosters": rosters,
                    "linked_builds": linked[key], "voters": total,
                    "solo": solo, "players": {w: counts[w] for w in solo},
                    "pairs": {w: dict(sorted(r.items())) for w, r in sorted(pairs.items())},
                    "pairs_n": support}
    return {
        "_source": {"party_rosters_sha256": None},
        "_content": CONTENT,
        "_unit": ("the dominant killer party of the pool's size in the content (no "
                  "deaths, a kill, every weapon known and in the catalog); solo: "
                  "distinct players per weapon (one player, one vote), share of the "
                  "pool's voters, shrunk n/(n+K), normalized so the pool's top weapon "
                  "is 1.0, rows under min_prior omitted (no signal, never a penalty)"),
        "_pair_unit": ("one dominant PARTY, one vote per distinct weapon pair it "
                       "fields; a pair needs min_pair_parties parties across "
                       "min_pair_orgs distinct guild-sets; s = clamp(log2 lift, 0, "
                       "log_cap)/log_cap * n/(n+K); lift <= 1 reads 0"),
        "_split": {"holdout_mod": holdout_mod,
                   "rule": (f"battle % {holdout_mod} != 0 (training split; "
                            f"% {holdout_mod} == 0 is the v4h holdout)"
                            if holdout_mod else "all battles (AUDIT ONLY, never shipped)")},
        "_params": {"k": k, "min_prior": min_prior, "log_cap": log_cap,
                    "min_pair_parties": min_pair_parties,
                    "min_pair_orgs": min_pair_orgs, "floor": floor},
        "pools": out,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rosters", default=None,
                    help="the roster artifact (default: pipeline/out/party_rosters.json.gz)")
    ap.add_argument("--dataset", default=os.path.join(OUT, "dataset-latest.json"),
                    help="the dataset whose weapon catalog a party must stay inside")
    args = ap.parse_args()
    path = args.rosters or rosters_io.path(OUT)
    if not os.path.exists(path):
        sys.exit(f"{path} missing -- run sample_parties.py first")
    doc = rosters_io.load(path, source="all", content=CONTENT)
    with open(args.dataset, encoding="utf-8") as f:
        data = json.load(f)
    catalog = set(data["weapons"])
    out = derive(doc, catalog)
    out["_generated"] = datetime.date.today().isoformat()
    out["_source"]["party_rosters_sha256"] = rosters_io.sha256(path)
    jsonfmt.dump(out, TARGET)
    names = {k: w["display_name"] for k, w in data["weapons"].items()}
    for key, _lo, _hi in POOLS:
        p = out["pools"].get(key)
        if p is None:
            print(f"  pool {key}: under the floor of {FLOOR} distinct rosters, no prior")
            continue
        npairs = sum(len(r) for r in p["pairs"].values()) // 2
        top = sorted(p["solo"].items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        print(f"  pool {key}: {p['parties']} dominant parties ({p['rosters']} rosters), "
              f"{p['voters']} player votes, {len(p['solo'])} weapons, {npairs} pairs; top: "
              + ", ".join(f"{names.get(w, w)} {v}" for w, v in top))
    print(f"portal prior ({out['_split']['rule']}) -> {os.path.relpath(TARGET, HERE)}")


if __name__ == "__main__":
    main()
