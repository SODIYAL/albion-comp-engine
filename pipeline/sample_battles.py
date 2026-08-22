#!/usr/bin/env python3
"""
Sample recent AlbionBB battles for equipment prevalence and DISPLAY-ONLY
co-occurrence evidence.

The kill feed does not expose party membership or authoritative sides. We do
not invent either. For affinity, actors are grouped only when the feed itself
identifies the same AllianceId/AllianceName (preferred) or GuildId/GuildName.
These are "observed organization cohorts", not parties. Unguilded/anonymous
players are excluded from cohort analysis. A cohort needs >=2 observed players.

This distinction matters: pair/partial-roster statistics can say "these weapons
were observed together among members of the same named organization in this
fight". They cannot say the players were in one party, that the organization
won, or that the pairing caused success. Nothing in this file feeds scoring.

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


def bucket_of(n):
    return "small" if n < 12 else "mid" if n <= 30 else "large"


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
    if not mh:
        return None
    name = mh.get("Name")
    if name:
        return TIER_RE.sub("", name.split("@")[0])
    t = mh.get("Type")
    return TIER_RE.sub("", t.split("@")[0]) if t else None


def cohort_key(actor):
    """Organization identity stated by the feed; never infer a party/side."""
    if not actor:
        return None
    aid = actor.get("AllianceId") or actor.get("AllianceName")
    if aid:
        return "alliance:" + str(aid)
    gid = actor.get("GuildId") or actor.get("GuildName")
    if gid:
        return "guild:" + str(gid)
    return None


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battles", type=int, default=200)
    ap.add_argument("--min-players", type=int, default=6)
    ap.add_argument("--server", default="us", choices=["us", "eu", "asia"])
    ap.add_argument("--no-topup", action="store_true")
    args = ap.parse_args()
    api = f"https://api.albionbb.com/{args.server}"

    with open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])
    os.makedirs(CACHE, exist_ok=True)

    buckets = {b: {} for b in ("small", "mid", "large")}
    battles_with = {b: {} for b in buckets}
    meta = {b: {"battles": 0, "players_attributed": 0} for b in buckets}
    cohorts = {b: [] for b in buckets}
    cohort_meta = {b: {"cohorts": 0, "players_observed": 0} for b in buckets}
    battles_index = []
    unknown, no_weapon, sampled, swaps = {}, 0, 0, 0
    seen_battles, seen_events = set(), set()

    def ingest(bid, fight_size, start_time):
        nonlocal sampled, no_weapon, swaps
        try:
            events = battle_kills(api, bid)
        except Exception as e:  # noqa: BLE001
            print(f"  battle {bid} kills failed: {e}")
            return

        # player -> weapons + organization labels actually observed in feed
        per_player = {}
        for ev in events:
            eid = ev.get("EventId") or ev.get("Id")
            if eid is not None:
                if eid in seen_events:
                    continue
                seen_events.add(eid)
            for actor in (ev.get("Killer"), ev.get("Victim")):
                if not actor:
                    continue
                pid = actor.get("Id")
                if pid is None:
                    continue
                rec = per_player.setdefault(pid, {"weapons": set(), "cohorts": set()})
                rec["weapons"].add(weapon_key((actor.get("Equipment") or {}).get("MainHand")))
                ck = cohort_key(actor)
                if ck:
                    rec["cohorts"].add(ck)

        bucket = bucket_of(fight_size)
        attributed = 0
        weapons_here = set()
        for rec in per_player.values():
            kits = rec["weapons"]
            kits.discard(None)
            if not kits:
                no_weapon += 1
                continue
            if len(kits) > 1:
                swaps += 1
            for wk in kits:
                if wk in known:
                    buckets[bucket][wk] = buckets[bucket].get(wk, 0) + 1
                    weapons_here.add(wk)
                    attributed += 1
                else:
                    unknown[wk] = unknown.get(wk, 0) + 1
        for wk in weapons_here:
            battles_with[bucket][wk] = battles_with[bucket].get(wk, 0) + 1

        # Organization cohorts are the safest same-group proxy available in
        # kill events. If a player's organization changed/was ambiguous in the
        # observations, exclude that player rather than choosing one.
        org = {}
        for rec in per_player.values():
            valid = {w for w in rec["weapons"] if w in known}
            if not valid or len(rec["cohorts"]) != 1:
                continue
            ck = next(iter(rec["cohorts"]))
            g = org.setdefault(ck, {"players": 0, "weapons": set()})
            g["players"] += 1
            g["weapons"].update(valid)
        for ck, g in org.items():
            if g["players"] < 2 or len(g["weapons"]) < 2:
                continue
            cohorts[bucket].append({
                "battle_id": bid,
                "cohort": ck,
                "observed_players": g["players"],
                "weapons": sorted(g["weapons"]),
            })
            cohort_meta[bucket]["cohorts"] += 1
            cohort_meta[bucket]["players_observed"] += g["players"]

        meta[bucket]["battles"] += 1
        meta[bucket]["players_attributed"] += attributed
        battles_index.append({
            "battle_id": bid, "server": args.server,
            "fight_size": fight_size,
            "observed_roster": len(per_player),
            "party_size": None, "side_size": None,
            "start_time": start_time, "attributed": attributed,
            "organization_cohorts": len(org),
        })
        sampled += 1
        if sampled % 20 == 0:
            print(f"  {sampled} battles (small {meta['small']['battles']} / mid {meta['mid']['battles']} / large {meta['large']['battles']})", flush=True)

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
                if not bid or bid in seen_battles:
                    continue
                seen_battles.add(bid)
                ingest(bid, n_players, b.get("startTime"))

    sweep(args.min_players, args.battles, 60)
    if not args.no_topup and meta["large"]["battles"] < 40:
        print("  topping up the large bucket (minPlayers=31)...", flush=True)
        sweep(31, 40 - meta["large"]["battles"], 20)

    total_attr = sum(m["players_attributed"] for m in meta.values())
    total_unknown = sum(unknown.values())
    coverage = total_attr / max(1, total_attr + no_weapon + total_unknown)
    out = {
        "semantics": ("FIGHT-SIZE EQUIPMENT PREVALENCE plus OBSERVED ORGANIZATION COHORTS. "
                      "Cohorts group actors only by Alliance/Guild identity stated in kill events; "
                      "they are NOT parties or authoritative sides. Party size, selected abilities, "
                      "and win causality are unknown. Display evidence only; never feeds scoring."),
        "sampling_frame": {"axis": "fight_size",
                           "buckets": {"small": "<12", "mid": "12-30", "large": ">30"},
                           "source": "albionbb kill events (killer+victim)",
                           "coverage_is": "combatants, not lurkers"},
        "cohort_semantics": ("Same named AllianceId/AllianceName, else GuildId/GuildName, within one battle; "
                             "minimum 2 observed players. This is an organization-level co-occurrence proxy, not party reconstruction."),
        "abilities": "unknown",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "server": args.server, "battles_sampled": sampled,
        "buckets": buckets,
        "buckets_battles": battles_with,
        "meta": meta,
        "cohorts": cohorts,
        "cohort_meta": cohort_meta,
        "battles": battles_index,
        "players_with_swaps": swaps,
        "coverage": round(coverage, 3),
        "unknown_keys_top": dict(sorted(unknown.items(), key=lambda kv: -kv[1])[:20]),
    }
    with open(os.path.join(OUT, "weapon_usage_v2.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"sampled {sampled} battles; weapon attribution {coverage:.0%} "
          f"({total_attr} player-weapon pairs, {swaps} players swapped kits, "
          f"{total_unknown} unknown key, {no_weapon} no weapon)")
    print("organization cohorts: " + ", ".join(f"{b}={cohort_meta[b]['cohorts']}" for b in cohort_meta))
    print("wrote out/weapon_usage_v2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
