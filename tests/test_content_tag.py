#!/usr/bin/env python3
"""Content tagging in the harvester (pipeline/sample_parties.py): the
KillArea tally, the marker rule (an item only found inside one content,
read off the victim's inventory), the tag a record reads, and the
kill-feed record rebuilt as a pure function of its events. Pure
functions, no network, no cache. Script-style: exit 0 = pass."""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
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
check("C3a the battle tally counts every event's KillArea and the marker once per marked event",
      areas == {"OPEN_WORLD": 2} and marks == {"ancient_lands": 1}, f"areas={dict(areas)} marks={dict(marks)}")
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
check("C4c the record carries both tallies and the tag reads the marker",
      r1["kill_areas"] == {"OPEN_WORLD": 2} and r1["content_marks"] == {"ancient_lands": 1}
      and sp.content_tag(r1["kill_areas"], r1["content_marks"]) == "ancient_lands")

if FAILURES:
    print(f"\n{len(FAILURES)} content-tag test(s) failed: {', '.join(FAILURES)}")
    sys.exit(1)
print(f"\nall content-tag tests pass")
sys.exit(0)
