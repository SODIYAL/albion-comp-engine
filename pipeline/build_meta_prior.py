#!/usr/bin/env python3
"""
Build a USAGE-DERIVED, SIZE-BUCKETED meta prior from real battle data
(out/weapon_usage_v2.json) — the data-grounded replacement for the hand-set
placeholder values in templates/scoring.yaml (design doc §4.1, Q17).

For each size bucket (small <12, mid 12-30, large >30 players — the same
buckets sample_battles.py uses), a weapon's prior is its share of players in
that bucket, SHRUNK toward zero by its own sample count, then normalized so
the most-played weapon in the bucket is 1.0:

    share_w   = players_w / total_players_in_bucket
    shrunk_w  = share_w * n_w / (n_w + K)      # rarity shrinks toward neutral
    prior_w   = min(1, shrunk_w / max_shrunk)  # top-played -> 1.0, unplayed -> 0

Shrinking by n_w (not battle count) is the guard against the Bridled Fury
trap: a weapon seen rarely is pulled toward 0 rather than trusted. A 0 prior
means "no signal" (neutral), never "bad" — absence is not evidence.

OUTPUT: out/meta_prior_usage.json (reviewable). This is NOT auto-wired into
scoring: the project rule is battle data stays display-only until validation
admits it. To admit it, replace scoring.yaml's `meta_prior:` with this file's
contents (the engine detects the bucketed shape automatically) and re-run the
V4 A/B + golden + parity.

NOTE (measured 2026-08-14): at the current meta weight delta=0.15 this prior
does not change rankings or V4 — the meta term is far weaker than the fitness
term. It is a data-quality improvement (size-aware, grounded), not the fix for
the Dagger-Pair-at-scale over-ranking; that needs a fitness/physics change (Q16).

Usage:  py -3 pipeline/build_meta_prior.py [--k 8] [--min 0.05]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
BUCKETS = ("small", "mid", "large")


def build(k, min_prior):
    usage = json.load(open(os.path.join(OUT, "weapon_usage_v2.json"), encoding="utf-8"))
    dataset = json.load(open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8"))
    curated = set(dataset["weapons"])

    prior = {}
    for b in BUCKETS:
        counts = usage["buckets"].get(b, {})
        total = sum(counts.values())
        if not total:
            prior[b] = {}
            continue
        shrunk = {w: (n / total) * (n / (n + k))
                  for w, n in counts.items() if w in curated}
        top = max(shrunk.values()) if shrunk else 0.0
        prior[b] = {w: round(min(1.0, s / top), 3)
                    for w, s in shrunk.items() if top and s / top >= min_prior}
    meta = {b: (usage.get("meta") or {}).get(b, {}) for b in BUCKETS}
    return prior, meta, dataset["weapons"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=float, default=8.0, help="per-weapon shrinkage constant")
    ap.add_argument("--min", type=float, default=0.05, help="drop priors below this")
    args = ap.parse_args()

    prior, meta, weapons = build(args.k, args.min)
    out_path = os.path.join(OUT, "meta_prior_usage.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"meta_prior": prior,
                   "_source": "weapon_usage_v2.json",
                   "_shrinkage_k": args.k, "_min_prior": args.min,
                   "_note": "size-bucketed; NOT auto-wired — see build_meta_prior.py"},
                  f, indent=1, sort_keys=True)

    for b in BUCKETS:
        p = prior[b]
        m = meta[b]
        print(f"\n[{b}]  {m.get('battles','?')} battles / "
              f"{m.get('players_attributed','?')} players  ->  {len(p)} weapons")
        for w, v in sorted(p.items(), key=lambda x: -x[1])[:8]:
            print(f"   {v:.3f}  {weapons.get(w, {}).get('display_name', w)}")
    print(f"\nwrote {os.path.relpath(out_path, HERE)}  (reviewable; not wired into scoring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
