#!/usr/bin/env python3
"""
Build the GEAR catalogue — the equipment half of a loadout, alongside
out/weapon_lines.json (which parse_dumps.py builds for weapons only).

    ao-bin-dumps formatted/items.txt   authoritative item list + localized names
        │
        ▼
    out/gear_lines.json    {KEY: {slot, example_item, name}}

The engine has never known anything but weapons. A loadout needs the other
five worn slots plus the consumables, and several capabilities the templates
already ask for come from GEAR rather than weapons — blackzone_roam.yaml says
so outright about cleanse ("in practice cleanse comes from helms, not
weapons — blap runs three Leather Hood(cleanse) slots and zero cleanse
weapons"). This file is step one: the catalogue and its art. Capability
curation for gear is a separate job and deliberately NOT done here.

Gear and weapon keys share one namespace without colliding: weapons are
2H_*/MAIN_*, gear is HEAD_*/ARMOR_*/SHOES_*/CAPE*/OFF_* and T<n>_POTION_*/
T<n>_MEAL_*. Worn keys drop the tier prefix the way weapon keys do
(T4_HEAD_PLATE_SET1 -> HEAD_PLATE_SET1); consumables keep theirs, for the
reason below.

Tiering differs by slot and this matters:
  - WORN slots (head/armor/shoes/cape/offhand) are one line across T4-T8, so
    T4 is the canonical tier for the render URL, matching weapon_lines.py's
    example_item convention.
  - CONSUMABLES are a DIFFERENT ITEM LINE PER TIER — T5_MEAL_OMELETTE and
    T7_MEAL_ROAST are not tiers of one thing. Restricting them to T4 dropped
    every potion and food a ZvZ actually uses: blap runs Gigantify Potion and
    an Avalonian pork omelette, neither of which exists at T4. So consumables
    are enumerated across all tiers and keep the tier in their key.

@1/@2/@3 enchantment variants share their line's art and are skipped.

Usage:  py -3 pipeline/fetch_gear_lines.py
"""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DEST = os.path.join(OUT, "gear_lines.json")
SRC = ("https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/"
       "formatted/items.txt")
UA = {"User-Agent": "albion-comp-engine gear catalogue "
                    "(github.com/SODIYAL/albion-comp-engine)"}

# "  1234: T4_HEAD_PLATE_SET1        : Adept's Soldier Helmet"
LINE = re.compile(r'^\s*\d+:\s*(\S+)\s*:\s*(.*?)\s*$')
# Worn slots + consumables. MOUNT is deliberately excluded: battlemounts are a
# real ZvZ factor but meta_comps.yaml already excludes mount slots from comps,
# so pulling ~90 mount lines in would be catalogue weight with nothing reading
# it. Add it when the engine actually scores mounts.
WORN = re.compile(r'^T4_(HEAD|ARMOR|SHOES|CAPE|OFF)')
CONSUMABLE = re.compile(r'^T\d_(POTION|MEAL)')


RENAME = {"OFF": "offhand", "MEAL": "food"}


def classify(uid):
    """(slot, catalogue_key) for a unique_name, or None if it is not loadout
    gear. CAPE has no underscore in the plain-cape case (T4_CAPE), hence the
    prefix match rather than a split.

    Worn keys drop the tier prefix (weapons do the same); consumable keys KEEP
    it, because each tier is a distinct item rather than a tier of one line."""
    m = WORN.match(uid)
    if m:
        raw = m.group(1)
        return RENAME.get(raw, raw.lower()), uid[3:]
    m = CONSUMABLE.match(uid)
    if m:
        raw = m.group(1)
        return RENAME.get(raw, raw.lower()), uid
    return None


def main():
    req = urllib.request.Request(SRC, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        text = r.read().decode("utf-8", errors="replace")

    gear, skipped = {}, 0
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        uid, name = m.group(1), m.group(2)
        if "@" in uid:            # enchantment variant — same art, same line
            skipped += 1
            continue
        hit = classify(uid)
        if not hit:
            continue
        slot, key = hit
        if key in gear:           # items.txt repeats lines; first wins
            continue
        gear[key] = {"slot": slot, "example_item": uid, "name": name}

    if not gear:
        sys.exit("no gear lines parsed — items.txt format may have changed")

    with open(DEST, "w", encoding="utf-8") as f:
        json.dump(gear, f, indent=1, sort_keys=True)

    counts = {}
    for v in gear.values():
        counts[v["slot"]] = counts.get(v["slot"], 0) + 1
    print(f"gear lines: {len(gear)} ({skipped} enchant variants skipped)")
    for slot in sorted(counts):
        print(f"  {slot:9} {counts[slot]:4}")
    print(f"wrote {os.path.relpath(DEST, os.path.join(HERE, os.pardir))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
