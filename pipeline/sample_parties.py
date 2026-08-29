#!/usr/bin/env python3
"""
Sample REAL PARTY COMPOSITIONS from the killboard.

WHY THIS EXISTS. Every other evidence layer in this project sees weapons but
not parties. `sample_battles.py` counts weapons from kill events (killer +
victim), so a player who neither killed nor died is invisible, and nothing
groups players into the squads they actually fought in. `sample_rosters.py`
reconstructs alliance-level roster MIXES but stores seat labels, not
weapons. Meanwhile the comp corpus is 36 published compositions — plans
people wrote down, not parties that fought.

The official gameinfo API carries `GroupMembers` on every kill event: the
KILLER'S PARTY at the moment of the kill, each member with their equipment.
That is a real party roster, which is exactly the unit the engine models.
albionbb strips the field; the official API keeps it (verified 2026-08-29 —
note that CLAUDE.md's "the official gameinfo events endpoint 504s
constantly" was true on 2026-08-13 but does NOT hold today: every endpoint
tested, list and detail, answered 200 in under a second).

THREE-STEP PIPELINE (each step exists because the one before it cannot
answer the question):

  1. DISCOVERY   albionbb /battles?minPlayers=N   — the only source with a
                 size filter, so large fights can be found without crawling
                 everything. Gives `totalPlayers`, the stated fight size.
  2. ROSTER      official /battles/{id}           — EVERY player in the
                 fight (name, guild, alliance, kills, deaths). No equipment,
                 but it is the honest DENOMINATOR: coverage becomes measured
                 rather than assumed.
  3. PARTIES     official /events/{id} per kill   — `GroupMembers` (the
                 killer's party, with equipment) and `Participants` (who
                 damaged the victim, with equipment).

WHAT THIS DATA IS — AND IS NOT.
  * A party here is a GroupMembers set: players grouped in-game at kill
    time. It is NOT a comp. A 300-player battle is a coalition of many
    parties; this samples the parties, which is the useful unit.
  * WINNER-BIASED BY CONSTRUCTION: only parties that got a kill appear.
    A party that was wiped without killing anyone is invisible here. Do not
    read prevalence as effectiveness — the same standing rule as every other
    observed layer.
  * DEDUPLICATED per battle by member-name set. A party that gets 20 kills
    emits 20 identical GroupMembers arrays; counting those as 20 parties
    would multiply whatever that squad ran by its kill count, which is the
    exact bias this data exists to remove.
  * Equipment is as recorded at that event. Players who swap mid-fight can
    appear under two weapons; the party is keyed on names, not gear.
  * DISPLAY / EVIDENCE ONLY. Nothing here feeds scoring. Like every observed
    layer, it may inform owner rulings; it never becomes a scoring input on
    its own.

Usage:  py -3 pipeline/sample_parties.py [--battles 25] [--min-players 25]
                                         [--max-events 120] [--server us]
        py -3 pipeline/sample_parties.py --pages 0     (offline re-analysis)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "party_cache")
UA = {"User-Agent": "bion-comp-engine/sample_parties (albion comp research)"}
GAMEINFO = "https://gameinfo.albiononline.com/api/gameinfo"


def get_json(url, tries=4, pause=1.5):
    """One request with backoff. Returns None rather than raising — the
    gameinfo API returns intermittent 502s and a single miss must not kill
    a long harvest."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as ex:
            if ex.code in (429, 502, 503, 504):
                time.sleep(pause * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(pause * (attempt + 1))
    return None


def weapon_key(t, known):
    """Item id -> catalogue key, tier and enchant stripped."""
    if not t:
        return None
    k = str(t).split("@")[0]
    k = re.sub(r"^T\d+_", "", k)
    return k if k in known else None


def fetch(args, known):
    os.makedirs(CACHE, exist_ok=True)
    server = args.server
    seen_battles = 0
    page = 1
    while seen_battles < args.battles and page <= 40:
        url = (f"https://api.albionbb.com/{server}/battles"
               f"?minPlayers={args.min_players}&page={page}")
        lst = get_json(url) or []
        if not lst:
            break
        for b in lst:
            if seen_battles >= args.battles:
                break
            bid = b.get("albionId")
            total = b.get("totalPlayers") or 0
            if not bid or total < args.min_players:
                continue
            path = os.path.join(CACHE, f"{bid}.json")
            if os.path.exists(path):
                seen_battles += 1
                continue

            # step 2 — the full roster (denominator)
            detail = get_json(f"{GAMEINFO}/battles/{bid}")
            roster = list((detail or {}).get("players", {}).values())

            # step 3 — per-kill parties
            kills = get_json(
                f"https://api.albionbb.com/{server}/battles/kills?ids={bid}"
            ) or []
            parties, participants, ev_ok = {}, {}, 0
            for x in kills[:args.max_events]:
                eid = x.get("EventId")
                if not eid:
                    continue
                d = get_json(f"{GAMEINFO}/events/{eid}", tries=2)
                if not d:
                    continue
                ev_ok += 1
                for field, sink in (("GroupMembers", parties),
                                    ("Participants", participants)):
                    members = d.get(field) or []
                    if not members:
                        continue
                    named = []
                    for m in members:
                        nm = m.get("Name")
                        if not nm:
                            continue
                        w = weapon_key(
                            ((m.get("Equipment") or {}).get("MainHand")
                             or {}).get("Type"), known)
                        named.append({
                            "name": nm, "weapon": w,
                            "guild": m.get("GuildName") or None,
                            "alliance": m.get("AllianceName") or None})
                    if not named:
                        continue
                    # DEDUPE: a party that gets 20 kills must count ONCE
                    key = "|".join(sorted(m["name"] for m in named))
                    prev = sink.get(key)
                    if prev is None or sum(
                            1 for m in named if m["weapon"]) > sum(
                            1 for m in prev["members"] if m["weapon"]):
                        sink[key] = {"members": named,
                                     "seen_in_events": 0}
                    sink[key]["seen_in_events"] += 1

            rec = {
                "battle": bid,
                "started_at": b.get("startedAt"),
                "total_players": total,
                "total_kills": b.get("totalKills"),
                "roster": [{"name": p.get("name"),
                            "guild": p.get("guildName") or None,
                            "alliance": p.get("allianceName") or None,
                            "kills": p.get("kills"), "deaths": p.get("deaths")}
                           for p in roster],
                "kill_events": len(kills),
                "events_fetched": ev_ok,
                "parties": list(parties.values()),
                "participant_sets": list(participants.values()),
            }
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(rec, f, indent=1, sort_keys=True)
            seen_battles += 1
            print(f"  battle {bid}: {total} players, {len(kills)} kills, "
                  f"{ev_ok} events fetched, {len(parties)} distinct parties",
                  flush=True)
        page += 1
    print(f"cache holds {len(os.listdir(CACHE))} battles", flush=True)


def analyze(known):
    if not os.path.isdir(CACHE) or not os.listdir(CACHE):
        sys.exit("no cache — run without --pages 0 first")
    battles, parties = [], []
    for name in sorted(os.listdir(CACHE)):
        with open(os.path.join(CACHE, name), encoding="utf-8") as f:
            rec = json.load(f)
        total = rec.get("total_players") or 0
        seen = {m["name"] for p in rec.get("parties", [])
                for m in p["members"]}
        seen |= {m["name"] for p in rec.get("participant_sets", [])
                 for m in p["members"]}
        # COVERAGE IS AGAINST THE OFFICIAL ROSTER, NOT totalPlayers.
        # GroupMembers reports the killer's WHOLE party, including members
        # who were not at this battle — a 20-man party with 8 people here
        # still lists 20. Dividing by totalPlayers therefore produced
        # coverage above 1.0 (measured 1.061 on the first run). The official
        # battle roster is the only ground truth for who was actually in the
        # fight, so the seen set is intersected with it, and the leftovers
        # are reported separately rather than silently inflating the number.
        roster_names = {p["name"] for p in (rec.get("roster") or [])
                        if p.get("name")}
        in_fight = seen & roster_names if roster_names else set()
        outside = seen - roster_names if roster_names else set()
        battles.append({
            "battle": rec["battle"], "total_players": total,
            "roster_known": len(roster_names),
            "players_with_gear": len(in_fight),
            "coverage": (round(len(in_fight) / len(roster_names), 3)
                         if roster_names else None),
            "party_members_not_in_this_battle": len(outside),
            "kill_events": rec.get("kill_events"),
            "events_fetched": rec.get("events_fetched"),
            "parties": len(rec.get("parties") or [])})
        # SECOND DEDUPE — by MEMBER OVERLAP, not exact set. Keying on the
        # exact name-set is not enough: a squad loses members as they die,
        # so one 19-man party emits 19/18/15/14/13-member arrays across a
        # battle and reads as five distinct parties. Every size statistic
        # built on that would be wrong, and the same squad's weapons would
        # be counted five times. Sets sharing more than half their members
        # are the same squad; the LARGEST observation wins, being the
        # fullest view of it.
        raw = sorted(rec.get("parties", []),
                     key=lambda p: -len(p["members"]))
        clusters = []
        for p in raw:
            names = {m["name"] for m in p["members"]}
            for c in clusters:
                inter = len(names & c["names"])
                if inter and inter / min(len(names), len(c["names"])) > 0.5:
                    c["events"] += p.get("seen_in_events", 1)
                    break
            else:
                clusters.append({"names": names, "party": p,
                                 "events": p.get("seen_in_events", 1)})
        for c in clusters:
            p = c["party"]
            ws = [m["weapon"] for m in p["members"] if m["weapon"]]
            parties.append({
                "battle": rec["battle"],
                "size": len(p["members"]),
                "known_weapons": len(ws),
                "weapons": sorted(ws),
                "guilds": sorted({m["guild"] for m in p["members"]
                                  if m["guild"]}),
                "seen_in_events": c["events"]})
    out = {
        "kind": "party_rosters",
        "semantics": (
            "GroupMembers from official gameinfo kill events: the KILLER'S "
            "PARTY at kill time, deduplicated per battle by member-name set. "
            "WINNER-BIASED — a party that killed nobody never appears. "
            "A party is not a comp: a large battle is a coalition of parties. "
            "DISPLAY/EVIDENCE ONLY, never a scoring input."),
        "battles": sorted(battles, key=lambda b: -(b["total_players"] or 0)),
        "parties": sorted(parties, key=lambda p: -p["size"]),
        "summary": {
            "battles": len(battles),
            "parties": len(parties),
            "parties_5plus": sum(1 for p in parties if p["size"] >= 5),
            "parties_full_gear": sum(1 for p in parties
                                     if p["size"] and
                                     p["known_weapons"] == p["size"]),
            "median_coverage": (sorted(
                b["coverage"] for b in battles if b["coverage"] is not None)
                [len(battles) // 2] if battles else None),
        },
    }
    path = os.path.join(OUT, "party_rosters.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    s = out["summary"]
    print(f"\n{s['battles']} battles, {s['parties']} distinct parties "
          f"({s['parties_5plus']} of size 5+, {s['parties_full_gear']} with "
          f"every member's weapon known)")
    print(f"median per-battle gear coverage: {s['median_coverage']}")
    print(f"wrote out/party_rosters.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battles", type=int, default=25)
    ap.add_argument("--min-players", type=int, default=25)
    ap.add_argument("--max-events", type=int, default=120,
                    help="cap per battle; a 300-man fight has ~180 kills")
    ap.add_argument("--server", default="us", choices=["us", "eu", "asia"])
    ap.add_argument("--pages", type=int, default=None,
                    help="0 = offline re-analysis, no network")
    args = ap.parse_args()

    ds = os.path.join(OUT, "dataset-latest.json")
    with open(ds, encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])

    if args.pages != 0:
        fetch(args, known)
    analyze(known)


if __name__ == "__main__":
    main()
