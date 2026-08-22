#!/usr/bin/env python3
"""In-game Armory system config -> out/armory_activities.json.

The Armory (Radiant Wilds update) is the game's own suggested-builds
feature. Its BUILDS are computed server-side from qualifying player
sessions and never appear in ao-bin-dumps — but `armory.json` ships the
official vocabulary they hang on: the activity taxonomy, the tag groups
(group size, activity type), the per-activity dataset requirements (what a
player session must be to count as evidence), and the aggregation settings
(confidence floor, popularity weight).

This parser normalizes that vocabulary so the evidence layer can speak it:

  - `data/armory_imports/*.yaml` records must cite an activity the Armory
    actually has (build_builds.py validates against this file), and
  - content-mapping rulings can cite SBI's own activity definitions
    instead of guesswork.

`planner_content_hints` is PROVISIONAL, owner-reviewable guidance only —
nothing downstream maps content through it automatically.

Usage:  py -3 pipeline/parse_armory.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
from provenance import record_derived, snapshot_commit, snapshot_dir  # noqa: E402

ADAPTER = "parse_armory"
ADAPTER_VERSION = "1"

# PROVISIONAL activity -> planner-content hints (owner 2026-08-21). Cited
# from the activity's own name/tags; empty list = no planner counterpart
# yet. The zvz / crystalleague20v20 rows mirror the CONTENT_COVERS rulings
# in build_builds.py so the two vocabularies stay consistent.
PLANNER_CONTENT_HINTS = {
    "castle": ["castle"],
    "factionwarfare": ["faction_war"],
    "avalonianroads": ["roads"],
    "fortification": ["territory_defense"],
    "zvz": ["castle", "territory_defense", "faction_war"],
    "openworldlargegroup": ["blackzone_roam"],
    "crystalleague20v20": ["territory_defense", "faction_war"],
}


def as_list(x):
    return x if isinstance(x, list) else [x] if x is not None else []


def cond_str(d):
    """One AND-joined condition group from a datasetrequirements node."""
    bits = []
    for dur in as_list(d.get("duration")):
        bits.append(f">={dur.get('@mindurationminutes', '?')}min")
    for m in as_list(d.get("metric")):
        bits.append(f"{m.get('@name', '?')}>={m.get('@minvalue', '?')}")
    for sub in as_list(d.get("and")):
        if isinstance(sub, dict):
            bits.append("(" + cond_str(sub) + ")")
    return " AND ".join(bits) if bits else "?"


def requirement_branches(reqs):
    """The OR-branches of an activity's dataset requirements, as text."""
    if not isinstance(reqs, dict):
        return []
    if "or" in reqs:
        o = reqs["or"]
        subs = as_list(o.get("and")) if isinstance(o, dict) and "and" in o \
            else as_list(o)
        return [cond_str(s) for s in subs if isinstance(s, dict)]
    return [cond_str(reqs)] if reqs else []


def load_localization(cache):
    """@ARMORY_* localization keys -> EN-US text (one pass, keys are few)."""
    path = os.path.join(cache, "localization.json")
    with open(path, encoding="utf-8") as f:
        tus = json.load(f)["tmx"]["body"]["tu"]
    loca = {}
    for tu in tus:
        tuid = tu.get("@tuid") or ""
        if not tuid.startswith("@ARMORY"):
            continue
        for tuv in as_list(tu.get("tuv")):
            if tuv.get("@xml:lang") == "EN-US":
                loca[tuid] = tuv.get("seg")
                break
    return loca


def main():
    commit = snapshot_commit()
    cache = snapshot_dir()
    if not commit or not cache or not os.path.isdir(cache):
        sys.exit("pinned snapshot missing — run: py -3 pipeline/fetch_snapshot.py")
    src = os.path.join(cache, "armory.json")
    if not os.path.exists(src):
        sys.exit("armory.json missing from the snapshot — run: "
                 "py -3 pipeline/fetch_snapshot.py")

    with open(src, encoding="utf-8") as f:
        arm = json.load(f)["armory"]
    loca = load_localization(cache)

    taggroups = {}
    for tg in as_list((arm.get("tagdefinitions") or {}).get("taggroup")):
        taggroups[tg.get("@id")] = [
            {"id": t.get("@id"),
             "name": loca.get(t.get("@name"), t.get("@id")),
             "short": loca.get(t.get("@shortname"))}
            for t in as_list(tg.get("tag"))]

    activities = []
    for a in as_list((arm.get("activities") or {}).get("activity")):
        un = a.get("@uniquename")
        activities.append({
            "uniquename": un,
            "name": loca.get(f"@ARMORY_ACTIVITY_{un.upper()}_NAME", un),
            "desc": loca.get(f"@ARMORY_ACTIVITY_{un.upper()}_DESC"),
            "tags": [t.get("@ref") for t in as_list((a.get("tags") or {}).get("tag"))],
            "session_qualifies_when": requirement_branches(
                a.get("datasetrequirements") or {}),
            "image": a.get("@image"),
            "planner_content_hints": PLANNER_CONTENT_HINTS.get(un, []),
        })

    settings = arm.get("settings") or {}
    doc = {
        "_meta": {
            "note": ("Official in-game Armory vocabulary (activity taxonomy, "
                     "tag groups, session qualification rules). The suggested "
                     "BUILDS are server-computed and not in the dumps; "
                     "planner_content_hints are PROVISIONAL owner guidance, "
                     "never an automatic mapping."),
            "snapshot_commit": commit,
        },
        "settings": {
            "confidence_floor": float(settings.get("@confidencefloor", 0) or 0),
            "popularity_weight": float(settings.get("@popularityweight", 0) or 0),
        },
        "taggroups": taggroups,
        "activities": sorted(activities, key=lambda x: x["uniquename"]),
    }

    dest = os.path.join(OUT, "armory_activities.json")
    # newline="\n": hashed-artifact discipline (manifest hashes raw bytes;
    # git normalizes the repo to LF)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    record_derived("armory_activities.json", dest, ADAPTER, ADAPTER_VERSION,
                   commit, ["armory.json", "localization.json"])
    named = sum(1 for x in activities if x["name"] != x["uniquename"])
    print(f"armory activities: {len(activities)} ({named} with localized "
          f"names), tag groups: {len(taggroups)}  @ {commit[:12]}")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
