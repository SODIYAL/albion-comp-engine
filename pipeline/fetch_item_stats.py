#!/usr/bin/env python3
"""
Item stats bank — the NUMBERS on every weapon and every worn item.

    ao-bin-dumps items.json      authoritative item stats (16.8 MB, cached)
    ao-bin-dumps items.txt       localized display names
        │
        ▼
    out/dumps_cache/items.json   gitignored download cache
    out/item_stats.json          {key: {slot, category, name, ip, stats, by_tier}}

WHAT THIS IS AND IS NOT
The dumps store BASE stats that are byte-identical across every tier of a
line — T4 and T8 Leather Armor both read physicalarmor 108; only `itempower`
moves (700 -> 1100). The number a player sees in game is
    base x f(itempower, quality, enchantment)
and that progression function is NOT in the dumps. So this file is honest
about what it holds: exact base stats plus the exact item power per tier. It
does not claim to be the tooltip value, because deriving that would mean
inventing the scaling curve.

The tier-invariance is VERIFIED, not assumed: any stat that does vary across
a line's tiers is moved into `by_tier` and reported, so a wrong assumption
shows up as data rather than as a silently averaged number.

Coverage is every tiered entry in the dumps' `weapon`, `transformationweapon`,
`equipmentitem` and `consumableitem` categories — mainhand, offhand, head,
armor, shoes, cape, bag, potion, food — not just the lines the comp engine
currently curates. `transformationweapon` is its own category and is easy to
miss: every shapeshifter (Earthrune Staff, Prowling Staff …) lives there, and
several are in real ZvZ comps.

Usage:  py -3 pipeline/fetch_item_stats.py [--refresh]
"""
import argparse, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "dumps_cache")
DEST = os.path.join(OUT, "item_stats.json")
RAW = "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/"
UA = {"User-Agent": "albion-comp-engine item stats "
                    "(github.com/SODIYAL/albion-comp-engine)"}

TIER = re.compile(r"^T(\d)_")
NAME_LINE = re.compile(r"^\s*\d+:\s*(\S+)\s*:\s*(.*?)\s*$")

# Combat-relevant only. Crafting, audio, UI sprites, durability-loss rates and
# fx bone offsets are deliberately dropped — they are noise for a comp tool.
WEAPON_STATS = [
    "attackdamage", "attackspeed", "attackrange", "attacktype", "twohanded",
    "abilitypower", "activespellslots", "passivespellslots",
    "physicalspelldamagebonus", "magicspelldamagebonus",
    "physicalattackdamagebonus", "magicattackdamagebonus",
    "healmodifier", "masterymodifier", "focusfireprotectionpenetration",
    "hitpointsmax", "hitpointsregenerationbonus", "weight", "durability",
]
GEAR_STATS = [
    "physicalarmor", "magicresistance", "crowdcontrolresistance",
    "hitpointsmax", "hitpointsregenerationbonus",
    "energymax", "energyregenerationbonus", "energycostreduction",
    "movespeed", "movespeedbonus", "attackspeedbonus",
    "magiccooldownreduction", "magiccasttimereduction",
    "healbonus", "threatbonus", "abilitypower", "maxload",
    "physicalspelldamagebonus", "magicspelldamagebonus",
    "physicalattackdamagebonus", "magicattackdamagebonus",
    "bonusccdurationvsplayers", "bonusdefensevsplayers",
    "weight", "durability",
]
# Consumables carry their effect as a SPELL id (@consumespell) rather than
# numbers — the magnitudes live in that spell, not on the item.
CONSUMABLE_STATS = [
    "abilitypower", "dummyitempower", "nutrition", "weight", "consumespell",
]

# Descriptive, not numeric — kept out of the tier-variance check.
FLAT = {"attacktype", "twohanded", "consumespell"}

# Consumables are a distinct item line per tier (T5_POTION_REVIVE is not a
# tier of T7_POTION_REVIVE), so their keys keep the prefix — matching
# fetch_gear_lines.py. Everything else is one line across tiers.
KEEP_TIER = {"consumableitem"}

# Vanity fireworks are `consumableitem` with slottype "potion" — they occupy a
# real slot but are a party trick, not a combat consumable, and the render
# service has no art for them. The game separates them itself: every genuine
# potion is shopsubcategory1 "potions" and every meal "food" or "fish", while
# the 8 fireworks are the only "other". Filtering on the game's own
# subcategory keeps this a rule about the data, not a list of item names.
CONSUMABLE_SUBCATEGORIES = {"potions", "food", "fish"}


def fetch(name, dest):
    if os.path.exists(dest):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(RAW + name, headers=UA)
    print(f"  downloading {name} …")
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def num(v):
    """'0.8' -> 0.8, '37' -> 37, 'ranged' -> 'ranged'."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f == int(f) else f


def load_names(path):
    names = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = NAME_LINE.match(line)
            if m and "@" not in m.group(1):
                names.setdefault(m.group(1), m.group(2))
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-download the dumps even if cached")
    args = ap.parse_args()

    items_path = os.path.join(CACHE, "items.json")
    names_path = os.path.join(CACHE, "items.txt")
    if args.refresh:
        for p in (items_path, names_path):
            if os.path.exists(p):
                os.remove(p)
    fetch("items.json", items_path)
    fetch("formatted/items.txt", names_path)

    with open(items_path, encoding="utf-8") as f:
        dump = json.load(f)["items"]
    names = load_names(names_path)

    # line key -> {slot, category, ip:{tier:ip}, seen:{stat:{tier:value}}}
    acc = {}
    for category, fields in (("weapon", WEAPON_STATS),
                             ("transformationweapon", WEAPON_STATS),
                             ("equipmentitem", GEAR_STATS),
                             ("consumableitem", CONSUMABLE_STATS)):
        for e in dump.get(category, []):
            uid = e.get("@uniquename", "")
            m = TIER.match(uid)
            if not m:
                continue
            if (category == "consumableitem"
                    and e.get("@shopsubcategory1") not in CONSUMABLE_SUBCATEGORIES):
                continue
            tier = m.group(1)
            key = uid if category in KEEP_TIER else TIER.sub("", uid)
            rec = acc.setdefault(key, {
                "slot": e.get("@slottype") or "", "category": category,
                "name": "", "ip": {}, "seen": {}, "example_item": uid,
            })
            if not rec["name"]:
                rec["name"] = names.get(uid, "")
            ip = num(e.get("@itempower"))
            if ip is not None:
                rec["ip"][tier] = ip
            for stat in fields:
                v = num(e.get("@" + stat))
                if v is None or v == 0:
                    continue
                rec["seen"].setdefault(stat, {})[tier] = v

    # Collapse: a stat identical on every tier it appears becomes a single
    # base value; anything that genuinely varies is kept per tier and named.
    out, varying = {}, {}
    for key, rec in acc.items():
        stats, by_tier = {}, {}
        for stat, per_tier in rec["seen"].items():
            vals = set(per_tier.values())
            if len(vals) == 1:
                stats[stat] = next(iter(vals))
            else:
                by_tier[stat] = per_tier
                if stat not in FLAT:
                    varying.setdefault(stat, 0)
                    varying[stat] += 1
        entry = {"slot": rec["slot"], "category": rec["category"],
                 "name": rec["name"], "example_item": rec["example_item"],
                 "tiers": sorted(int(t) for t in rec["ip"]),
                 "ip": {t: v for t, v in sorted(rec["ip"].items())},
                 "stats": dict(sorted(stats.items()))}
        if by_tier:
            entry["by_tier"] = {k: dict(sorted(v.items()))
                                for k, v in sorted(by_tier.items())}
        out[key] = entry

    payload = {
        "_meta": {
            "source": "ao-data/ao-bin-dumps items.json + formatted/items.txt",
            "lines": len(out),
            "note": ("BASE stats. The dumps are tier-invariant per line — the "
                     "in-game value is base x f(itempower, quality, "
                     "enchantment) and that curve is NOT in the dumps. `ip` "
                     "carries the exact item power per tier; `by_tier` holds "
                     "any stat that genuinely varies."),
        },
        "items": dict(sorted(out.items())),
    }
    with open(DEST, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), sort_keys=True)

    slots = {}
    for e in out.values():
        slots[e["slot"] or "?"] = slots.get(e["slot"] or "?", 0) + 1
    print(f"item stats: {len(out)} lines, {os.path.getsize(DEST) // 1024} KB")
    for s in sorted(slots):
        print(f"  {s:12} {slots[s]:4}")
    if varying:
        print("  stats that VARY across tiers (kept per tier):")
        for s, n in sorted(varying.items(), key=lambda kv: -kv[1]):
            print(f"    {s:32} {n} lines")
    else:
        print("  tier-invariance holds for every numeric stat")
    print(f"wrote {os.path.relpath(DEST, os.path.join(HERE, os.pardir))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
