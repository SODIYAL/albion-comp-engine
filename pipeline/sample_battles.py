#!/usr/bin/env python3
"""
Sample recent battles and count which weapons real players actually brought,
bucketed by fight size (VALIDATION V7 — the proper ~200-battle re-run of the
original 24-battle eyeball sample).

Source: the albionbb API (api.albionbb.com) — the same community killboard
the original V2 spike used. The official gameinfo events endpoint 504s too
often to sample at scale (verified 2026-08-13); albionbb serves the same
kill-event data reliably. Weapons come from kill events (killer + victim),
so coverage is combatants, not lurkers — the same limitation V2 measured.

Public killboards do NOT record content type, only the fight — so the honest
bucketing is by size: small (<12 players), mid (12–30), large (>30). The
dashboard maps the user's party size to a bucket and shows "seen on X% of
players in fights your size". Display evidence only: nothing here feeds the
scoring engine until validation says it may (design doc §8, Phase 3).

    /us/battles?minPlayers=N&page=P      20 battles per page, recent first
    /us/battles/kills?ids=<battleId>     kill events with Equipment.MainHand
        │
        ▼
    out/battles_cache/<id>.json          per-battle cache (gitignored)
    out/weapon_usage_v2.json             {buckets, meta, coverage}

MainHand Type "T5_2H_SHAPESHIFTER_MORGANA@4" -> catalog key
"2H_SHAPESHIFTER_MORGANA". Unknown keys are tallied for the coverage stat.

Usage:  py -3 pipeline/sample_battles.py [--battles 200] [--min-players 6]
                                         [--server us]
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "battles_cache")
UA = {"User-Agent": "albion-comp-engine usage sample (github.com/SODIYAL/albion-comp-engine)"}
SLEEP = 0.5
TIER_RE = re.compile(r"^T\d+_")


def get_json(url, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            code = getattr(e, "code", None)
            if attempt == tries - 1:
                raise
            time.sleep(10 if code == 429 else 3 * (attempt + 1))
    return None


def weapon_key(mh):
    """Prefer the pre-normalized Name; fall back to stripping the Type."""
    if not mh:
        return None
    name = mh.get("Name")
    if name:
        return TIER_RE.sub("", name.split("@")[0])
    t = mh.get("Type")
    return TIER_RE.sub("", t.split("@")[0]) if t else None


def battle_kills(api, battle_id):
    path = os.path.join(CACHE, f"{battle_id}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    events = get_json(f"{api}/battles/kills?ids={battle_id}") or []
    time.sleep(SLEEP)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f)
    return events


def bucket_of(n):
    return "small" if n < 12 else "mid" if n <= 30 else "large"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battles", type=int, default=200)
    ap.add_argument("--min-players", type=int, default=6)
    ap.add_argument("--server", default="us", choices=["us", "eu", "asia"])
    ap.add_argument("--no-topup", action="store_true",
                    help="skip the large-bucket top-up sweep (e.g. when the API is throttling)")
    args = ap.parse_args()
    api = f"https://api.albionbb.com/{args.server}"

    with open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])
    os.makedirs(CACHE, exist_ok=True)

    buckets = {b: {} for b in ("small", "mid", "large")}
    meta = {b: {"battles": 0, "players_attributed": 0} for b in buckets}
    unknown, no_weapon, sampled, seen_ids = {}, 0, 0, set()

    def ingest(bid, n_players):
        nonlocal sampled, no_weapon
        try:
            events = battle_kills(api, bid)
        except Exception as e:  # noqa: BLE001
            print(f"  battle {bid} kills failed: {e}")
            return
        per_player = {}
        for ev in events:
            for a in (ev.get("Killer"), ev.get("Victim")):
                if not a or a.get("Id") in per_player:
                    continue
                per_player[a.get("Id")] = weapon_key((a.get("Equipment") or {}).get("MainHand"))
        bucket = bucket_of(n_players)
        attributed = 0
        for wk in per_player.values():
            if wk is None:
                no_weapon += 1
            elif wk in known:
                buckets[bucket][wk] = buckets[bucket].get(wk, 0) + 1
                attributed += 1
            else:
                unknown[wk] = unknown.get(wk, 0) + 1
        meta[bucket]["battles"] += 1
        meta[bucket]["players_attributed"] += attributed
        sampled += 1
        if sampled % 20 == 0:
            print(f"  {sampled} battles "
                  f"(small {meta['small']['battles']} / mid {meta['mid']['battles']} "
                  f"/ large {meta['large']['battles']})", flush=True)

    def sweep(min_players, want, page_cap):
        page = 1
        start = sampled
        while sampled - start < want and page <= page_cap:
            try:
                listing = get_json(f"{api}/battles?minPlayers={min_players}&page={page}")
            except Exception as e:  # noqa: BLE001
                print(f"  battle list page {page} failed: {e}")
                break
            time.sleep(SLEEP)
            page += 1
            if not listing:
                break
            for b in listing:
                if sampled - start >= want:
                    break
                bid, n_players = b.get("albionId"), b.get("totalPlayers", 0)
                if not bid or bid in seen_ids:
                    continue
                seen_ids.add(bid)
                ingest(bid, n_players)

    # phase 1: the general sweep; phase 2: top up the large bucket, which
    # recent-battle listings underrepresent (big fights are rare)
    sweep(args.min_players, args.battles, 60)
    if not args.no_topup and meta["large"]["battles"] < 40:
        print("  topping up the large bucket (minPlayers=31)...", flush=True)
        sweep(31, 40 - meta["large"]["battles"], 20)

    total_attr = sum(m["players_attributed"] for m in meta.values())
    total_unknown = sum(unknown.values())
    coverage = total_attr / max(1, total_attr + no_weapon + total_unknown)
    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "server": args.server, "battles_sampled": sampled,
        "buckets": buckets, "meta": meta,
        "coverage": round(coverage, 3),
        "unknown_keys_top": dict(sorted(unknown.items(), key=lambda kv: -kv[1])[:20]),
    }
    with open(os.path.join(OUT, "weapon_usage_v2.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"sampled {sampled} battles; weapon attribution {coverage:.0%} "
          f"({total_attr} players known-weapon, {total_unknown} unknown key, "
          f"{no_weapon} no weapon)")
    print("wrote out/weapon_usage_v2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
