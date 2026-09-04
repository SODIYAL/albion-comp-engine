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
  * THE FILTER IS "SCORED AT LEAST ONE KILL", NOT "WON" — and it was
    MEASURED (2026-08-29) rather than assumed, because "winner-biased"
    overstates it. Of 354 captured parties: 61% dominant (2x+ K/D), 19%
    traded roughly even, and 20% took MORE DEATHS THAN KILLS. Losing
    parties are well represented; they only had to kill someone first.
    What drops out is the 10% of players in no captured party at all, whose
    combined record is 34 kills against 475 deaths (K/D 0.07) — they died
    about once each and killed almost nothing. OWNER RULING 2026-08-29:
    "it's okay if the losing party couldn't get a single kill it's not
    worth having their party information." Coverage is 90% of all players
    across the sampled battles. Prevalence is still not effectiveness —
    that standing rule is unchanged.
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
                # schema 1 cached weapons only — re-fetch it for the builds
                try:
                    with open(path, encoding="utf-8") as fh:
                        if (json.load(fh) or {}).get("schema", 1) >= 2:
                            seen_battles += 1
                            continue
                except Exception:
                    pass

            # step 2 — the full roster (denominator)
            detail = get_json(f"{GAMEINFO}/battles/{bid}")
            roster = list((detail or {}).get("players", {}).values())

            # step 3 — per-kill parties
            kills = get_json(
                f"https://api.albionbb.com/{server}/battles/kills?ids={bid}"
            ) or []
            parties, participants, ev_ok = {}, {}, 0
            builds = {}
            for x in kills[:args.max_events]:
                eid = x.get("EventId")
                if not eid:
                    continue
                d = get_json(f"{GAMEINFO}/events/{eid}", tries=2)
                if not d:
                    continue
                ev_ok += 1
                # FULL BUILDS come from Killer / Victim / Participants, which
                # carry 7 of 8 equipment slots plus item power. GroupMembers
                # does NOT: measured 2026-08-29, it fills MainHand only and
                # reports AverageItemPower 0. So party STRUCTURE comes from
                # GroupMembers and BUILDS come from the combat roles; a member
                # who never killed, died or dealt damage yields a weapon and
                # nothing else, and is recorded that way rather than guessed.
                pool = [("killer", d.get("Killer")),
                        ("victim", d.get("Victim"))]
                pool += [("participant", m) for m in (d.get("Participants")
                                                      or [])]
                for how, m in pool:
                    if not isinstance(m, dict) or not m.get("Name"):
                        continue
                    eq = m.get("Equipment") or {}
                    gear = {}
                    for slot in ("MainHand", "OffHand", "Head", "Armor",
                                 "Shoes", "Cape", "Potion", "Food"):
                        v = eq.get(slot)
                        gear[slot] = (v or {}).get("Type") if isinstance(
                            v, dict) else None
                    n_filled = sum(1 for v in gear.values() if v)
                    prev = builds.get(m["Name"])
                    if prev is None or n_filled > prev["slots_filled"]:
                        builds[m["Name"]] = {
                            "name": m["Name"],
                            "guild": m.get("GuildName") or None,
                            "alliance": m.get("AllianceName") or None,
                            "item_power": m.get("AverageItemPower"),
                            "seen_as": how,
                            "slots_filled": n_filled,
                            "gear": gear}
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
                "schema": 2,          # 2 = carries full builds; 1 did not
                "battle": bid,
                "builds": list(builds.values()),
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
    # OBSERVED BUILDS — full kits, and the weapon -> armour-class evidence
    # that role assignment can actually be tested against. Armour class is
    # the owner's own role tell ("cloth wearing is a very good indicator"),
    # and unlike the hand-curated role menus it is measurable.
    strip = lambda t: (re.sub(r"^T\d+_", "", str(t).split("@")[0])
                       if t else None)
    def armour_class(t):
        k = (strip(t) or "").upper()
        for cls in ("CLOTH", "LEATHER", "PLATE"):
            if f"ARMOR_{cls}" in k:
                return cls.lower()
        return None
    builds, by_weapon = [], {}
    for name in sorted(os.listdir(CACHE)):
        with open(os.path.join(CACHE, name), encoding="utf-8") as f:
            rec = json.load(f)
        # PARTY SIZE per build (2026-09-03, the Grailseeker case): the
        # battle floor admits 2-8 man gank parties fighting inside a
        # 20+ battle, and their kits (Hunter Shoes, Demon Cape, Poison
        # Potion) were being mined as ZvZ doctrine. The party the killer
        # belonged to is the real evidence unit; a build inherits the
        # size of the largest deduped party carrying its player name in
        # this battle. Victims are in no party record -> None (honest:
        # unknown, never guessed).
        size_by_name = {}
        for p in rec.get("parties", []):
            n_members = len(p.get("members") or [])
            for m in p.get("members") or []:
                nm = m.get("name")
                if nm:
                    size_by_name[nm] = max(size_by_name.get(nm, 0),
                                           n_members)
        for bd in rec.get("builds", []):
            g = bd.get("gear") or {}
            w = strip(g.get("MainHand"))
            if not w or w not in known:
                continue
            ac = armour_class(g.get("Armor"))
            builds.append({
                "battle": rec["battle"], "weapon": w,
                "armour_class": ac,
                "item_power": bd.get("item_power"),
                "seen_as": bd.get("seen_as"),
                "party_size": size_by_name.get(bd.get("name")),
                "slots_filled": bd.get("slots_filled"),
                "gear": {s: strip(v) for s, v in g.items() if v}})
            e = by_weapon.setdefault(w, {"n": 0, "cloth": 0, "leather": 0,
                                         "plate": 0, "ip_sum": 0.0,
                                         "ip_n": 0})
            e["n"] += 1
            if ac:
                e[ac] += 1
            if bd.get("item_power"):
                e["ip_sum"] += bd["item_power"]
                e["ip_n"] += 1
    for w, e in by_weapon.items():
        seen_ac = e["cloth"] + e["leather"] + e["plate"]
        e["armour_majority"] = (max(("cloth", "leather", "plate"),
                                    key=lambda c: e[c]) if seen_ac else None)
        e["armour_majority_share"] = (round(max(e["cloth"], e["leather"],
                                                e["plate"]) / seen_ac, 3)
                                      if seen_ac else None)
        e["mean_item_power"] = (round(e["ip_sum"] / e["ip_n"], 1)
                                if e["ip_n"] else None)
        e.pop("ip_sum", None)

    out = {
        "kind": "party_rosters",
        "builds": sorted(builds, key=lambda b: (b["weapon"], b["battle"])),
        "weapon_armour": dict(sorted(by_weapon.items())),
        "semantics": (
            "GroupMembers from official gameinfo kill events: the KILLER'S "
            "PARTY at kill time, deduplicated per battle by member OVERLAP "
            "(>50% of the smaller set) so one squad shedding members as they "
            "die is not counted several times. INCLUSION FILTER: the party "
            "scored at least one kill — measured 2026-08-29, not assumed: "
            "61% of captured parties are dominant, 19% traded even, 20% took "
            "more deaths than kills, so losing parties ARE represented; the "
            "10% of players in no captured party hold 34 kills against 475 "
            "deaths between them. Owner ruling 2026-08-29: a party that could "
            "not get a single kill is not worth recording. Coverage 90% of "
            "players across sampled battles. A party is NOT a comp: a large "
            "battle is a coalition of parties. Prevalence is not "
            "effectiveness. DISPLAY/EVIDENCE ONLY, never a scoring input."),
        "battles": sorted(battles, key=lambda b: -(b["total_players"] or 0)),
        "parties": sorted(parties, key=lambda p: -p["size"]),
        "summary": {
            "battles": len(battles),
            "parties": len(parties),
            "parties_5plus": sum(1 for p in parties if p["size"] >= 5),
            "parties_full_gear": sum(1 for p in parties
                                     if p["size"] and
                                     p["known_weapons"] == p["size"]),
            "builds": len(builds),
            "builds_full_kit": sum(1 for b in builds
                                   if (b["slots_filled"] or 0) >= 6),
            "weapons_with_armour_evidence": sum(
                1 for e in by_weapon.values() if e["armour_majority"]),
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
    print(f"{s['builds']} observed BUILDS ({s['builds_full_kit']} with 6+ "
          f"equipment slots), armour evidence on "
          f"{s['weapons_with_armour_evidence']} weapons")
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
