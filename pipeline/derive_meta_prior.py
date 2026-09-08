"""Observed relevance: the GENERATED meta prior, from the COMMITTED harvest.

Owner ruling 2026-09-08 ("sure" to "one harvest prior replacing both hand
lists, tiebreak-sized, capped at the current 0.15"): the seven-weapon
hand-set `meta_prior` in templates/scoring.yaml and the hand-listed
viability `core` in templates/composition.yaml are retired. In their place
this script reads the committed killer-party artifact (out/party_rosters.json
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

Explicit step, never part of a normal build; re-derive after every harvest
refresh. Order: sample_parties -> audit_style_rosters -> derive_style_bands
-> derive_party_styles -> derive_meta_prior -> build_dataset -> gates.

    py -3 pipeline/derive_meta_prior.py
"""
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ARTIFACT = os.path.join(OUT, "party_rosters.json")
TARGET = os.path.join(OUT, "meta_prior.json")
BUCKETS = ("small", "mid", "large")
K = 8.0            # shrinkage mass in PLAYERS (build_meta_prior's k; PROVISIONAL)
MIN_PRIOR = 0.05   # below this a weapon carries no signal (row omitted)

sys.path.insert(0, HERE)
import jsonfmt  # noqa: E402


def bucket_of(party_size):
    """Mirror of Engine.size_bucket for a known party size: the engine maps
    roster size to a participant axis (2 x size) and cuts at 12 / 30, so a
    party of 2-5 is small, 6-15 mid, 16+ large."""
    n = 2 * party_size
    return "small" if n < 12 else "mid" if n <= 30 else "large"


def derive(doc, k=K, min_prior=MIN_PRIOR):
    voters = {b: {} for b in BUCKETS}
    for b in doc.get("builds") or []:
        size, player, weapon = b.get("party_size"), b.get("player"), b.get("weapon")
        if not size or size < 2 or not player or not weapon:
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
    return {
        "_source": {"party_rosters_sha256": None},
        "_unit": ("distinct players per weapon per bucket (one player, one "
                  "vote); share of the bucket's voters, shrunk n/(n+K), "
                  "normalized so the bucket's top weapon is 1.0; rows under "
                  "min_prior omitted (no signal, never a penalty)"),
        "_bucket_rule": ("Engine.size_bucket on the party size: 2-5 small, "
                         "6-15 mid, 16+ large (participant axis 2 x size, "
                         "cuts at 12 / 30)"),
        "_k": k, "_min_prior": min_prior,
        "meta_prior": prior, "players": players,
    }


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    if not os.path.exists(ARTIFACT):
        sys.exit("no out/party_rosters.json -- run sample_parties.py first")
    with open(ARTIFACT, encoding="utf-8") as f:
        doc = json.load(f)
    out = derive(doc)
    out["_generated"] = datetime.date.today().isoformat()
    out["_source"]["party_rosters_sha256"] = sha256_of(ARTIFACT)
    jsonfmt.dump(out, TARGET)
    for bk in BUCKETS:
        rows = out["meta_prior"][bk]
        top = sorted(rows.items(), key=lambda kv: -kv[1])[:3]
        print(f"  {bk:<5} {len(rows):>3} weapons  top: "
              + ", ".join(f"{w} {v}" for w, v in top))
    print(f"meta prior -> {os.path.relpath(TARGET, HERE)}")


if __name__ == "__main__":
    main()
