"""Observed relevance: the GENERATED meta prior, from the COMMITTED harvest.

Owner ruling 2026-09-08 ("sure" to "one harvest prior replacing both hand
lists, tiebreak-sized, capped at the current 0.15"): the seven-weapon
hand-set `meta_prior` in templates/scoring.yaml and the hand-listed
viability `core` in templates/composition.yaml are retired. In their place
this script reads the committed killer-party artifact (out/party_rosters.json.gz
-- the killer's party at kill time, winner-biased by construction) and
writes out/meta_prior.json, which build_dataset attaches to the dataset's
`scoring.meta_prior` (hash-gated to the artifact it was derived from; a
hand-set map anywhere in the config fails the build).

The number, per fight-size BUCKET (small / mid / large -- the engine's
size_bucket axis, mirrored by bucket_of() below and pinned equal in the
golden suite):

    voters_w  = distinct players seen on weapon w in parties of that bucket
                (ONE PLAYER, ONE VOTE -- R27; a build with no party record,
                i.e. a victim, carries no party_size and casts no vote)
    share_w   = voters_w / sum over weapons of voters
    shrunk_w  = share_w * voters_w / (voters_w + K)   # thin counts sink toward 0
    prior_w   = shrunk_w / max_w shrunk_w             # the bucket's top weapon = 1.0
    dropped   when prior_w < MIN_PRIOR                # no signal, never a penalty

Absence is not evidence: a weapon with no row reads 0 (neutral). The prior
enters the recommendation score as delta * prior (delta = 0.15 in
scoring.yaml), so it can reorder otherwise-close candidates and nothing
else -- it never buys a floor, a role slot or a suggestion-pool place.

PAIRS (owner ruling 2026-09-11, spec notes/specs/2026-09-11-pair-meta-
prior-design.md): the same artifact's `parties[]` (the killer's party
with its full known weapon list and guilds) yields `meta_pairs`, per
bucket, symmetric:

    ONE PARTY, ONE VOTE per DISTINCT pair it fields (a weapon never pairs
    with itself); a pair carries a row only across >= MIN_PAIR_ORGS
    distinct guild-sets and >= MIN_PAIR_PARTIES parties (the cohort
    families' honesty gate)
    lift  = n_ab * N / (n_a * n_b)                    # over chance
    s     = clamp(log2 lift, 0, LOG_CAP) / LOG_CAP * n_ab / (n_ab + K)
    dropped when s < MIN_PRIOR; lift <= 1 reads 0    # never a penalty

The engine blends it per member: (1 - meta_pair) * solo + meta_pair * best
observed partner on the roster (scoring.yaml weights.meta_pair, 0.5).

HOLDOUT: both tables learn from battles with id % HOLDOUT_MOD != 0 only;
the % 5 == 0 slice is tier2_blindtest v4h's evaluation set and the shipped
prior never sees it (build_dataset refuses an all-battles artifact).

Explicit step, never part of a normal build; re-derive after every harvest
refresh. Order: sample_parties -> audit_style_rosters -> derive_style_bands
-> derive_party_styles -> derive_meta_prior -> build_dataset -> gates.

    py -3 pipeline/derive_meta_prior.py
    py -3 pipeline/derive_meta_prior.py --all-battles   # AUDIT copy ->
        # out/meta_prior-all-battles.json (gitignored), never shipped
"""
import datetime
import hashlib
import itertools
import json
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rosters_io  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ARTIFACT = rosters_io.path(OUT)
TARGET = os.path.join(OUT, "meta_prior.json")
BUCKETS = ("small", "mid", "large")
K = 8.0            # shrinkage mass in PLAYERS (solo) / PARTIES (pairs); PROVISIONAL
MIN_PRIOR = 0.05   # below this a weapon / pair carries no signal (row omitted)
HOLDOUT_MOD = 5    # battles with id % 5 == 0 are tier2_blindtest v4h's holdout
LOG_CAP = 3.0      # log2(lift) saturates at 8x over chance; PROVISIONAL
MIN_PAIR_PARTIES = 5   # honesty gate (mirrors build_cohort_families MIN_COHORTS)
MIN_PAIR_ORGS = 3      # ...across this many distinct guild-sets (MIN_ORGS)

sys.path.insert(0, HERE)
import jsonfmt  # noqa: E402


def bucket_of(party_size):
    """Mirror of Engine.size_bucket for a known party size: the engine maps
    roster size to a participant axis (2 x size) and cuts at 12 / 30, so a
    party of 2-5 is small, 6-15 mid, 16+ large."""
    n = 2 * party_size
    return "small" if n < 12 else "mid" if n <= 30 else "large"


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
    """Spec section 5: lift = n_ab*N/(n_a*n_b); s = clamp(log2 lift, 0, cap)
    / cap * n_ab/(n_ab+k). 0 at or under chance -- never a penalty."""
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


def sha256_of(path):
    return rosters_io.sha256(path)   # the stored (compressed) bytes


def main():
    all_battles = "--all-battles" in sys.argv[1:]
    if not os.path.exists(ARTIFACT):
        sys.exit("no out/party_rosters.json.gz -- run sample_parties.py first")
    doc = rosters_io.load(ARTIFACT)
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


if __name__ == "__main__":
    main()
