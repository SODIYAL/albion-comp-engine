#!/usr/bin/env python3
"""Dragon Portal stats (pipeline/build_portal_stats.py): the display
artifact behind dashboard/portal.html. Contracts on the builder over a
synthetic artifact (no network, no cache) and on the committed artifact
and page. Script-style: exit 0 = pass."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import build_portal_stats as bps  # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"\n      {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def party(battle, idx, weapons, kills, deaths, known=None):
    return {"battle": battle, "index": idx, "size": len(weapons), "weapons": sorted(weapons),
            "known_weapons": len(weapons) if known is None else known,
            "kills": kills, "deaths": deaths, "content": "ancient_lands"}


def build(battle, idx, weapon, player, seen_as="killer", armor="ARMOR_LEATHER_SET1", ip=1250):
    return {"battle": battle, "party": idx, "weapon": weapon, "player": player, "seen_as": seen_as,
            "slots_filled": 6, "item_power": ip,
            "gear": {"MainHand": weapon, "Armor": armor, "Head": "HEAD_LEATHER_SET1"}}


doc = {
    "battles": [{"battle": b, "first_event_at": f"2026-09-27T1{b}:00:00Z"} for b in (1, 2, 3, 4)],
    "parties": [
        party(1, 0, ["2H_BOW"], 2, 0),                       # solo, dominant
        party(2, 0, ["2H_BOW"], 1, 1),                       # solo, traded
        party(3, 0, ["2H_BOW", "2H_HOLYSTAFF", "2H_CLAWS"], 4, 0),   # trio, dominant
        party(4, 0, ["2H_BOW", "2H_HOLYSTAFF", "2H_CLAWS"], 3, 2),   # same trio comp, traded
        party(4, 1, ["2H_HOLYSTAFF", "MAIN_MACE"], None, None, known=1),  # unknown member: no comp row
    ],
    "builds": [
        build(1, 0, "2H_BOW", "p1"), build(2, 0, "2H_BOW", "p1", armor="ARMOR_CLOTH_SET1"),
        build(3, 0, "2H_BOW", "p2"), build(4, 0, "2H_BOW", "p3"),
        build(3, 0, "2H_HOLYSTAFF", "p4"), build(4, 0, "2H_HOLYSTAFF", "p4"),
        build(1, None, "2H_BOW", "v1", seen_as="victim", armor="ARMOR_PLATE_SET1"),
    ],
}
weapons_meta = {"2H_BOW": {"display_name": "Bow"}, "2H_HOLYSTAFF": {"display_name": "Holy Staff"},
                "2H_CLAWS": {"display_name": "Claws"}, "MAIN_MACE": {"display_name": "Mace"}}
gear_meta = {"ARMOR_LEATHER_SET1": {"display_name": "Mercenary Jacket"}}
out = bps.build(doc, weapons_meta, gear_meta, {"2H_BOW": "T6_2H_BOW"})
solo, trio = out["pools"]["solo"], out["pools"]["trio"]

check("P1 pools split by party size and count killer parties",
      solo["parties"] == 2 and trio["parties"] == 3 and out["pools"]["five"]["parties"] == 0,
      f"solo={solo['parties']} trio={trio['parties']}")
bow_solo = next(w for w in solo["weapons"] if w["id"] == "2H_BOW")
check("P2 a weapon row carries parties, share, distinct players, dominant share and K/D from the party tallies",
      bow_solo["parties"] == 2 and bow_solo["share"] == 1.0 and bow_solo["players"] == 1
      and bow_solo["dominant_share"] == 0.5 and bow_solo["kd"] == 3.0 and bow_solo["icon"] == "T6_2H_BOW",
      json.dumps(bow_solo)[:300])
check("P3 a party without kills and deaths counts as prevalence, never as scored",
      any(w["id"] == "MAIN_MACE" and w["scored"] == 0 and w["dominant_share"] is None for w in trio["weapons"]))
bow_trio = next(w for w in trio["weapons"] if w["id"] == "2H_BOW")
check("P4 the winning build is the modal item per slot over winning players, one player one vote, "
      "from the vote floor, victims excluded",
      bow_solo["build"] == {} and bow_trio["build"] == {}
      and out["thresholds"]["slot_votes"] == 3,
      f"solo build={bow_solo['build']} trio build={bow_trio['build']}")
# three players on Bow across pools would clear the floor within one pool:
doc2 = dict(doc)
doc2["parties"] = doc["parties"] + [party(5, 0, ["2H_BOW"], 1, 0), party(6, 0, ["2H_BOW"], 1, 0)]
doc2["builds"] = doc["builds"] + [build(5, 0, "2H_BOW", "p5"), build(6, 0, "2H_BOW", "p6", armor="ARMOR_CLOTH_SET1")]
doc2["battles"] = doc["battles"] + [{"battle": 5}, {"battle": 6}]
out2 = bps.build(doc2, weapons_meta, gear_meta, {})
bow2 = next(w for w in out2["pools"]["solo"]["weapons"] if w["id"] == "2H_BOW")
check("P4b at the vote floor the modal armor shows with its votes and share, named from the catalogue",
      bow2["build"].get("armor") == {"id": "ARMOR_LEATHER_SET1", "name": "Mercenary Jacket", "votes": 2, "share": 0.667, "of": 3}
      and bow2["players"] == 3 and bow2["icon"] == "T6_2H_BOW",
      json.dumps(bow2["build"]))
check("P5 comps need every member's weapon known and the sighting floor; rows carry seen, dominant share and K/D",
      len(trio["comps"]) == 1 and [w["id"] for w in trio["comps"][0]["weapons"]] == ["2H_BOW", "2H_CLAWS", "2H_HOLYSTAFF"]
      and trio["comps"][0]["n"] == 2 and trio["comps"][0]["dominant_share"] == 0.5 and trio["comps"][0]["kd"] == 3.5,
      json.dumps(trio["comps"])[:300])
check("P6 the window reads the battle stamps and the artifact names its unit",
      out["window"] == {"first": "2026-09-27T11:00", "last": "2026-09-27T14:00"}
      and out["kind"] == "portal_stats" and "never a scoring input" in out["source"])
check("P7 rows are ordered by parties, then dominant share, then name (deterministic)",
      [w["id"] for w in trio["weapons"]] == ["2H_HOLYSTAFF", "2H_BOW", "2H_CLAWS", "MAIN_MACE"],
      str([w["id"] for w in trio["weapons"]]))

# the committed artifact and page
path = os.path.join(ROOT, "pipeline", "out", "portal_stats.json")
check("P8 the committed artifact exists, is LF and carries every pool",
      os.path.exists(path) and b"\r\n" not in open(path, "rb").read()
      and set(json.load(open(path, encoding="utf-8"))["pools"]) == {"solo", "trio", "five", "seven", "large"})
page = os.path.join(ROOT, "dashboard", "portal.html")
docs_page = os.path.join(ROOT, "docs", "portal.html")
src = open(os.path.join(ROOT, "dashboard", "_portal.html"), encoding="utf-8").read()
check("P9 the generated page embeds the artifact and the docs copy is byte-identical",
      os.path.exists(page) and os.path.exists(docs_page)
      and "const PORTAL_STATS = " in open(page, encoding="utf-8").read()
      and open(page, "rb").read() == open(docs_page, "rb").read())
check("P10 the page is display only: no engine, no scoring, no dataset embed",
      "CompEngine" not in src and "DATASET" not in src and "fitness" not in src
      and "app_scoring" not in src)
check("P11 the page states the unit, dominance and the marker rule for the reader",
      "Ancient Bone" in src and "Dominant" in src and "one player one vote" in src
      and "do not read it" in src)

if FAILURES:
    print(f"\n{len(FAILURES)} portal-stats test(s) failed: {', '.join(FAILURES)}")
    sys.exit(1)
print("\nall portal-stats tests pass")
sys.exit(0)
