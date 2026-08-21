#!/usr/bin/env python3
"""
Build the GEAR catalogue — the equipment half of a loadout, alongside
out/weapon_lines.json (which parse_dumps.py builds for weapons only).

    out/item_stats.json    every equippable line + its authoritative slottype
        │                  (fetch_item_stats.py)
        ▼
    out/gear_lines.json    {KEY: {slot, example_item, name}}

The engine has never known anything but weapons. A loadout needs the other
five worn slots plus the consumables, and several capabilities the templates
already ask for come from GEAR rather than weapons — blackzone_roam.yaml says
so outright about cleanse ("in practice cleanse comes from helms, not
weapons — blap runs three Leather Hood(cleanse) slots and zero cleanse
weapons"). This file is the catalogue; capability curation for gear is a
separate job and deliberately NOT done here.

WHY THIS DERIVES FROM item_stats.json
It used to parse formatted/items.txt and decide what counted as gear from the
NAME ("^T4_(HEAD|ARMOR|...)"). That let 14 Crest items in — CAPEITEM_*_BP —
which are named like capes but are `simpleitem` in the dumps, with no
slottype at all: trophies, not wearables. Reading the game's own `@slottype`
instead of pattern-matching names removes that whole class of mistake, and
classifies a new item by what the game says it is rather than what it is
called.

Keys follow item_stats.json exactly: worn lines drop the tier prefix
(T4_HEAD_PLATE_SET1 -> HEAD_PLATE_SET1) because one line spans T4-T8;
consumables keep it, because T5_POTION_REVIVE and T7_POTION_REVIVE are
different items, not tiers of one. Gear and weapon keys share one namespace
without colliding — weapons are 2H_*/MAIN_*.

MOUNT is excluded on purpose: battlemounts are a real ZvZ factor but
the caller comps (data/published_comps/) already exclude mount slots, so pulling them in
would be catalogue weight nothing reads. Add it when the engine scores mounts.

Usage:  py -3 pipeline/fetch_item_stats.py   (first — builds the source)
        py -3 pipeline/fetch_gear_lines.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SRC = os.path.join(OUT, "item_stats.json")
DEST = os.path.join(OUT, "gear_lines.json")

sys.path.insert(0, HERE)
from provenance import record_derived  # noqa: E402

ADAPTER = "fetch_gear_lines"
ADAPTER_VERSION = "2"

# The worn + consumable slots a loadout has. "mainhand" is a weapon and lives
# in weapon_lines.json; "bag" carries no combat stat worth a slot in the UI.
GEAR_SLOTS = ("head", "armor", "shoes", "cape", "offhand", "potion", "food")


def main():
    if not os.path.exists(SRC):
        sys.exit("out/item_stats.json missing — run: "
                 "py -3 pipeline/fetch_item_stats.py")
    with open(SRC, encoding="utf-8") as f:
        items = json.load(f)["items"]

    gear, unnamed = {}, []
    for key, e in items.items():
        if e.get("slot") not in GEAR_SLOTS:
            continue
        # No localized name means the game never shows this to a player: the
        # dumps carry DEBUG_* and *_PROTOTYPE dev entries with real slottypes.
        # Absence of a name is the game's own signal, so this stays a rule
        # about the data rather than a list of items to exclude by hand.
        if not e.get("name"):
            unnamed.append(key)
            continue
        gear[key] = {"slot": e["slot"],
                     "example_item": e.get("example_item", ""),
                     "name": e["name"]}

    if not gear:
        sys.exit("no gear lines found — item_stats.json may be malformed")

    with open(DEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(gear, f, indent=1, sort_keys=True)
    # gear_lines derives from item_stats.json — inherit its snapshot commit
    # so the release check can prove the whole chain is one snapshot
    with open(SRC, encoding="utf-8") as f:
        src_commit = json.load(f).get("_meta", {}).get("source_commit",
                                                       "local-override")
    record_derived("gear_lines.json", DEST, ADAPTER, ADAPTER_VERSION,
                   src_commit, ["items.json", "formatted/items.txt"])

    counts = {}
    for v in gear.values():
        counts[v["slot"]] = counts.get(v["slot"], 0) + 1
    print(f"gear lines: {len(gear)}")
    for slot in sorted(counts):
        print(f"  {slot:9} {counts[slot]:4}")
    if unnamed:
        print(f"  dropped {len(unnamed)} unnamed dev entries: {unnamed[:6]}")
    print(f"wrote {os.path.relpath(DEST, os.path.join(HERE, os.pardir))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
