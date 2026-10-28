#!/usr/bin/env python3
"""Content tagging in the harvester (pipeline/sample_parties.py): the
KillArea tally, the marker rule (an item only found inside one content,
read off the victim's inventory), the tag a record reads, the kill-feed
record rebuilt as a pure function of its events, the population the
committed artifact keeps, and the battle harvest reading the poll's stored
kills. No network; the harvest runs over a temporary cache.
Script-style: exit 0 = pass."""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import rosters_io  # noqa: E402
import sample_parties as sp  # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"\n      {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


KNOWN = {"2H_HOLYSTAFF", "2H_BOW", "MAIN_FROSTSTAFF"}


def event(eid, killer, victim, group, inv=(), area="OPEN_WORLD", ts="2026-09-27T12:00:00Z",
          victim_gear=None):
    def member(name, weapon, ip=1200):
        return {"Name": name, "GuildName": "G", "AllianceName": None,
                "AverageItemPower": ip,
                "Equipment": {"MainHand": {"Type": f"T8_{weapon}"} if weapon else None,
                              "Armor": {"Type": "T8_ARMOR_CLOTH_SET1"}}}
    v = member(victim, "2H_BOW")
    v["Inventory"] = [None] + [{"Type": t} for t in inv]
    if victim_gear is not None:
        v["Equipment"] = victim_gear
    return {"EventId": eid, "BattleId": 1, "TimeStamp": ts, "KillArea": area,
            "Location": None, "Category": None, "Type": "KILL",
            "Killer": member(killer, "2H_HOLYSTAFF"), "Victim": v,
            "Participants": [member(killer, "2H_HOLYSTAFF")],
            "GroupMembers": [member(n, "2H_HOLYSTAFF" if i == 0 else "MAIN_FROSTSTAFF")
                             for i, n in enumerate(group)]}


# C1 the tag: instanced KillArea first, marker second, open_world last, unknown before the tallies
check("C1a every event OPEN_WORLD and no marker reads open_world",
      sp.content_tag({"OPEN_WORLD": 5}, {}) == "open_world")
check("C1b a marker on any event names the content",
      sp.content_tag({"OPEN_WORLD": 5}, {"ancient_lands": 1}) == "ancient_lands")
check("C1c an instanced KillArea outranks the marker and reads lower-cased",
      sp.content_tag({"OPEN_WORLD": 2, "HELLGATE": 3}, {"ancient_lands": 4}) == "hellgate")
check("C1d a record without tallies reads unknown, marker or not",
      sp.content_tag(None, {"ancient_lands": 1}) == "unknown" and sp.content_tag({}, None) == "unknown")
check("C1e UNKNOWN (a null KillArea) is not an instanced area",
      sp.content_tag({"UNKNOWN": 3}, {}) == "open_world")
check("C1f ties break on the label so the tag is deterministic",
      sp.content_tag({"A": 2, "B": 2}, {}) == "b")

# C2 the marker: the Ancient Bone in the victim's inventory, tier and enchant stripped
check("C2a the Ancient Bone marks ancient_lands at any tier",
      sp.event_marker(event(1, "k", "v", ["k"], inv=["T4_QUESTITEM_TOKEN_DRAGONS"])) == "ancient_lands"
      and sp.event_marker(event(1, "k", "v", ["k"], inv=["QUESTITEM_TOKEN_DRAGONS"])) == "ancient_lands")
check("C2b dragon-named gear and mounts are not markers",
      sp.event_marker(event(1, "k", "v", ["k"], inv=["T6_SHOES_LEATHER_DRAGON@1", "T5_MOUNT_SWAMPDRAGON_FW_THETFORD"])) is None)
check("C2d the Drake shards mark ancient_lands too, and the pair form names the item",
      sp.event_marker(event(1, "k", "v", ["k"], inv=["T6_SHARD_FIRE_DRAGON"])) == "ancient_lands"
      and sp.event_marker(event(1, "k", "v", ["k"], inv=["T7_SHARD_RANDOM_DUNGEON_ELITE_DRAGON_TOKEN"]), item=True)
          == ("ancient_lands", "SHARD_RANDOM_DUNGEON_ELITE_DRAGON_TOKEN"))
check("C2c an empty or null inventory marks nothing",
      sp.event_marker({"Victim": {"Inventory": [None]}}) is None and sp.event_marker({}) is None)

# C3 ingest_event: the tallies, the fuller sighting keeping the party's counts
builds, parties, parts = {}, {}, {}
areas, marks, stamps = collections.Counter(), collections.Counter(), []
e1 = event(10, "a", "x", ["a", "b", "c"], inv=["T4_QUESTITEM_TOKEN_DRAGONS"])
e2 = event(11, "a", "y", ["a", "b", "c"])
e2["GroupMembers"][2]["Equipment"]["MainHand"] = None     # c's weapon unknown this time
for e in (e1, e2):
    sp.ingest_event(e, KNOWN, builds, parties, parts, areas, stamps, marks)
party = parties["a|b|c"]
check("C3a the battle tally counts every event's KillArea, the marker once per marked event, and the item behind it",
      areas == {"OPEN_WORLD": 2} and marks == {"ancient_lands": 1, "ancient_lands:QUESTITEM_TOKEN_DRAGONS": 1},
      f"areas={dict(areas)} marks={dict(marks)}")
check("C3b a party seen twice keeps one record, both sightings counted, the fuller weapons kept",
      party["seen_in_events"] == 2 and party["kill_areas"] == {"OPEN_WORLD": 2}
      and [m["weapon"] for m in party["members"]] == ["2H_HOLYSTAFF", "MAIN_FROSTSTAFF", "MAIN_FROSTSTAFF"],
      f"party={party}")
check("C3c the victim's build carries the event's raw area and its marker",
      builds["x"]["kill_area"] == "OPEN_WORLD" and builds["x"]["content_mark"] == "ancient_lands"
      and builds["y"]["content_mark"] is None)

# C4 the kill-feed record is a pure function of its event set
raw = {e["EventId"]: e for e in (e1, e2)}
r1 = sp.rebuild_poll_record(1, raw, KNOWN)
r2 = sp.rebuild_poll_record(1, dict(reversed(list(raw.items()))), KNOWN)
check("C4a the same events in any order give the same record",
      r1 == r2)
check("C4b the roster is rebuilt from the events: the killer's kills, the victims' deaths, every name once",
      {r["name"]: (r["kills"], r["deaths"]) for r in r1["roster"]}
      == {"a": (2, 0), "b": (0, 0), "c": (0, 0), "x": (0, 1), "y": (0, 1)}
      and r1["total_players"] == 5 and r1["source"] == "events_poll")
check("C4c the record carries both tallies and the tag reads the marker, never the per-item key",
      r1["kill_areas"] == {"OPEN_WORLD": 2}
      and r1["content_marks"] == {"ancient_lands": 1, "ancient_lands:QUESTITEM_TOKEN_DRAGONS": 1}
      and sp.content_tag(r1["kill_areas"], r1["content_marks"]) == "ancient_lands"
      and sp.content_tag({"OPEN_WORLD": 1}, {"ancient_lands:QUESTITEM_TOKEN_DRAGONS": 1}) == "open_world")

# C5 the build artifact keeps what the build reads; every record stays in the full one; both stay local
def battle(bid, source, content, total):
    return {"battle": bid, "total_players": total, "source": source, "content": content,
            "coverage": None, "parties": 1}


BATTLES = [battle(1, "battle_list", "open_world", 30), battle(2, "events_poll", "open_world", 3),
           battle(3, "events_poll", "ancient_lands", 5), battle(4, "battle_list", "unknown", 25)]
PARTIES = [{"battle": b["battle"], "index": 0, "content": b["content"], "size": 2,
            "known_weapons": 2, "weapons": ["2H_BOW", "2H_HOLYSTAFF"]} for b in BATTLES]
BUILDS = [{"battle": b["battle"], "weapon": "2H_BOW", "armour_class": ac, "item_power": 1200.0,
           "slots_filled": 6} for b, ac in zip(BATTLES, ("leather", "cloth", "leather", "plate"))]
check("C5a the build population is every battle-list battle and every Dragon Portal battle; "
      "a record from before the fields existed reads battle-list",
      [b["battle"] for b in BATTLES if rosters_io.build_population(b)] == [1, 3, 4]
      and rosters_io.build_population({"battle": 9}))
keep = {b["battle"] for b in BATTLES if rosters_io.build_population(b)}
full = sp.rosters_doc(BATTLES, PARTIES, BUILDS, "full")
kept = sp.rosters_doc([b for b in BATTLES if b["battle"] in keep], [p for p in PARTIES if p["battle"] in keep],
                      [x for x in BUILDS if x["battle"] in keep], "build")
check("C5b each file carries its own records, summary and armour table: the poll's open-world gank is in the full one alone",
      full["summary"]["battles"] == 4 and kept["summary"]["battles"] == 3
      and kept["summary"]["builds"] == 3 and {p["battle"] for p in kept["parties"]} == keep
      and full["weapon_armour"]["2H_BOW"]["cloth"] == 1 and kept["weapon_armour"]["2H_BOW"]["cloth"] == 0
      and kept["weapon_armour"]["2H_BOW"]["n"] == 3,
      f"full={full['summary']} kept={kept['summary']}")
with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
    ignored = {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}
with open(os.path.join(ROOT, "pipeline", "derive_usage.py"), encoding="utf-8") as f:
    usage_src = f.read()
check("C5c every rosters artifact stays local (.gitignore lists the working, fold and previous copies of both), "
      "the fold's record is committed, and derive_usage reads the full fold copy by default",
      all("pipeline/out/" + n in ignored for n in (rosters_io.NAME, rosters_io.FULL_NAME, rosters_io.FOLD_NAME,
                                                  rosters_io.FULL_FOLD_NAME, rosters_io.PREV_NAME))
      and "pipeline/out/" + rosters_io.RECORD_NAME not in ignored
      and "rosters_io.full_fold_path()" in usage_src)

# C6 the battle harvest: discovery from the poll's records, the official
# roster's band, the poll's stored kills read and the rest off the kill list
import datetime  # noqa: E402
import tempfile  # noqa: E402
import types  # noqa: E402
import party_store  # noqa: E402

FULL = {i: event(i, "a", f"v{i}", ["a", "b"]) for i in (21, 22, 23)}
ROSTER = {"startTime": "2026-09-27T11:59:00.000000000Z", "totalKills": 3,
          "players": {str(i): {"name": n, "guildName": "G", "kills": 0, "deaths": 0}
                      for i, n in enumerate(["a", "b", "v21", "v22", "v23"])}}


def stub_net(calls, roster=ROSTER, listing=()):
    """The network: the battle list (`listing`: one page, None = the page
    fails, or {offset: page or None} for several, an offset past them
    empty), the official roster of battle 7 (404 = the API holds none) and
    its kill list (one page), each request logged in `calls`."""
    def fake_get(url, tries=4, pause=1.5, timeout=30, missing=None):
        calls.append(url)
        if "/battles?offset=" in url:
            if isinstance(listing, dict):
                page = listing.get(int(url.split("offset=")[1].split("&")[0]), [])
                return None if page is None else list(page)
            return None if listing is None else list(listing)
        if url.endswith("/battles/7"):
            return missing if roster == 404 else roster
        if "/events/battle/7?" in url:
            return [FULL[i] for i in (21, 22, 23)]
        return None
    return fake_get


def harvest_once(stored_ids, band=None):
    """One harvest_battle over a fresh temporary cache, the poll's record
    holding `stored_ids` beforehand."""
    sp.CACHE = os.path.join(tempfile.mkdtemp(), "cache.sqlite")
    with party_store.Store(sp.CACHE) as st:
        if stored_ids:
            st.put(7, sp.rebuild_poll_record(7, {i: FULL[i] for i in stored_ids}, KNOWN))
    calls = []
    real_get, sp.get_json = sp.get_json, stub_net(calls)
    try:
        out = sp.harvest_battle(types.SimpleNamespace(max_events=120), KNOWN, 7, band)
    finally:
        sp.get_json = real_get
    with party_store.Store(sp.CACHE) as st:
        return out, calls, st.get(7)


(_s, _line, _k, _e, _r), _calls, _rec = harvest_once([21, 22])
(_s0, _line0, _k0, _e0, _r0), _calls0, _rec0 = harvest_once([])
(_s3, _line3, _k3, _e3, _r3), _calls3, _rec3 = harvest_once([21, 22, 23])
check("C6a a kill the poll stored is read from the cache; the kill list is read for the rest, "
      "and the pass counts what it read",
      _s == "harvested" and sum("/events/battle/7?" in u for u in _calls) == 1
      and (_k, _e, _r) == (3, 3, 2) and "3 events read (2 cached)" in _line, f"{_calls} {_line}")
check("C6b the record equals the one a pass reading every kill off the kill list writes: "
      "the official roster's size and start, every event kept",
      _r0 == 0 and _rec == _rec0 and _rec == _rec3
      and [e["EventId"] for e in _rec["raw_events"]] == [21, 22, 23] and _rec["events_fetched"] == 3
      and _rec["total_players"] == 5 and _rec["kill_events"] == 3
      and _rec["started_at"] == ROSTER["startTime"] and _rec.get("source") is None)
check("C6c a fight whose every kill the poll holds costs its roster request alone",
      _calls3 == [sp.GAMEINFO + "/battles/7"] and _r3 == 3, f"{_calls3}")
(_s4, _line4, *_), _calls4, _rec4 = harvest_once([21, 22], band=(8, 0))
(_s5, *_), _calls5, _rec5 = harvest_once([21, 22], band=(2, 4))
check("C6d a fight the official roster puts outside the band stays the poll's record, unread",
      _s4 == "outside" and _s5 == "outside" and _rec4.get("source") == "events_poll"
      and _rec4["raw_events"] == _rec5["raw_events"] and len(_calls4) == 1, f"{_s4} {_calls4}")


def listed(bid, n, start="2026-09-27T11:59:00.0Z", end="2026-09-27T12:30:00.0Z"):
    """A battle list item: `n` players, its start and end."""
    return {"id": bid, "startTime": start, "endTime": end, "totalKills": 3,
            "players": {str(i): {"name": f"p{i}" if bid != 7 else ["a", "b", "v21", "v22", "v23"][i],
                                 "guildName": "G", "kills": 0, "deaths": 0} for i in range(n)}}


def pass_over(now, roster=ROSTER, since="2026-09-01", listing=(), settle=0,
              stored=(21, 22, 23), extra=()):
    """fetch() over a fresh cache holding battle 7's poll record (the
    `stored` kills, first at 12:00; the official roster holds five
    players), battle 9's (two seen players, under every floor here, so the
    poll's newest write stays the cache's) and the `extra` (id, events)
    records: (problems, requests, battle 7's record after)."""
    sp.CACHE = os.path.join(tempfile.mkdtemp(), "cache.sqlite")
    with party_store.Store(sp.CACHE) as st:
        st.put(7, sp.rebuild_poll_record(7, {i: FULL[i] for i in stored}, KNOWN))
        for bid, evs in extra:
            st.put(bid, sp.rebuild_poll_record(bid, evs, KNOWN))
        st.put(9, sp.rebuild_poll_record(9, {31: event(31, "x", "y", ["x"])}, KNOWN))
    calls = []
    real_get, sp.get_json = sp.get_json, stub_net(calls, roster, listing)
    sp.ERRORS.clear()
    args = types.SimpleNamespace(max_events=120, min_players=4, max_players=0, battles=25,
                                 since=since, since_hours=36, settle_minutes=settle, workers=1)
    try:
        problems = sp.fetch(args, KNOWN, now=now)
    finally:
        sp.get_json = real_get
    with party_store.Store(sp.CACHE) as st:
        return problems, calls, st.get(7)


def asked(calls, part):
    return sum(part in u for u in calls)


_soon = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=1)
_p, _c, _rec7 = pass_over(_soon)
check("C6e a poll record of the floor's seen players the list does not hold is found and "
      "harvested on its official roster",
      _p == [] and _rec7.get("source") is None and _rec7["total_players"] == 5
      and asked(_c, "/battles/7") == 1, f"{_p} {_c}")
_p, _c, _rec7 = pass_over(_soon + datetime.timedelta(minutes=29), settle=60)
check("C6f a record written inside the settle time is left to the poll (the fight may go on)",
      _p == [] and asked(_c, "/battles/7") == 0 and _rec7.get("source") == "events_poll", f"{_p} {_c}")
_p, _c, _rec7 = pass_over(_soon, since="2026-09-28")
check("C6g a record whose first kill is before the window is not read",
      asked(_c, "/battles/7") == 0 and _rec7.get("source") == "events_poll", f"{_c}")
_p, _c, _ = pass_over(_soon + datetime.timedelta(minutes=sp.STALE_POLL_MINUTES + 1))
check("C6h a pass ending with no poll write in STALE_POLL_MINUTES fails loudly",
      len(_p) == 1 and "kill-feed poll has written nothing" in _p[0], f"{_p}")
_p, _c, _rec7 = pass_over(_soon, roster=None)
check("C6i a pass whose roster requests mostly fail fails loudly; the poll record stays",
      len(_p) == 1 and "roster requests failed" in _p[0] and _rec7.get("source") == "events_poll",
      f"{_p}")
_p, _c, _rec7 = pass_over(_soon, roster=404)
check("C6j a fight with no official battle (404) stays the poll's record and is no failure",
      _p == [] and _rec7.get("source") == "events_poll", f"{_p}")
_p, _c, _rec7 = pass_over(_soon, listing=[listed(7, 5)], stored=(21, 22))
check("C6k a listed fight is harvested on the list's own roster: no roster request",
      _p == [] and _rec7.get("source") is None and _rec7["total_players"] == 5
      and asked(_c, "/battles/7") == 0 and asked(_c, "/events/battle/7?") == 1, f"{_p} {_c}")
_p, _c, _rec7 = pass_over(_soon, listing=[listed(7, 3)])
check("C6l a listed fight under the floor costs nothing and stays the poll's record",
      asked(_c, "/battles/7") == 0 and _rec7.get("source") == "events_poll", f"{_c}")
_p, _c, _rec7 = pass_over(_soon, listing=[listed(8, 3, start="2026-09-27T09:00:00.0Z",
                                                   end="2026-09-27T09:10:00.0Z")])
check("C6m a poll record two hours inside the list's reach that the list does not hold is no "
      "official battle of 4+: no request",
      _p == [] and asked(_c, "/battles/7") == 0 and _rec7.get("source") == "events_poll", f"{_c}")
_p, _c, _rec7 = pass_over(_soon, listing=[listed(7, 5, end=_soon.strftime("%Y-%m-%dT%H:%M:%S.0Z"))],
                          settle=60)
check("C6n a listed fight that ended inside the settle time waits for the next pass",
      asked(_c, "/battles/7") == 0 and _rec7.get("source") == "events_poll", f"{_c}")
_p, _c, _rec7 = pass_over(_soon, listing=None)
check("C6o a battle list whose first page fails fails the pass loudly; the poll's records "
      "are still harvested",
      len(_p) == 1 and "first page failed" in _p[0] and _rec7.get("source") is None, f"{_p} {_c}")
_p, _c, _rec7 = pass_over(_soon, stored=(21, 22))
check("C6p a poll record holding fewer than OFFICIAL_MIN_KILLS kills is never asked about "
      "(no official battle holds fewer) and stays the poll's record",
      sp.OFFICIAL_MIN_KILLS == 3 and _p == [] and asked(_c, "/battles/7") == 0
      and _rec7.get("source") == "events_poll", f"{_p} {_c}")
# three pages: the newest read (51 fights at 20:00, under the floor), the
# next failed, the third read (one fight at 05:00); the failed page held
# the starts between 05:00 and 20:00
_late = {i: event(i, "k", f"w{i}", ["k", "m"], ts="2026-09-27T23:30:00Z") for i in (41, 42, 43)}
_p, _c, _rec7 = pass_over(_soon, extra=[(11, _late)], listing={
    0: [listed(1000 + i, 3, start="2026-09-27T20:00:00.0Z", end="2026-09-27T20:30:00.0Z")
        for i in range(51)],
    51: None,
    102: [listed(8, 3, start="2026-09-27T05:00:00.0Z", end="2026-09-27T05:10:00.0Z")]})
check("C6q a failed list page reopens the poll records inside its span alone: the 12:00 fight "
      "is asked about and harvested, the 23:30 fight (inside the reach, outside the span) is not",
      _p == [] and asked(_c, "/battles/7") == 1 and _rec7.get("source") is None
      and asked(_c, "/battles/11") == 0, f"{_p} {_c}")

if FAILURES:
    print(f"\n{len(FAILURES)} content-tag test(s) failed: {', '.join(FAILURES)}")
    sys.exit(1)
print(f"\nall content-tag tests pass")
sys.exit(0)
