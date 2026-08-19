#!/usr/bin/env python3
"""
Item stats bank — the NUMBERS on every weapon and every worn item.

    out/dumps_cache/<commit>/items.json          pinned snapshot (fetch_snapshot.py)
    out/dumps_cache/<commit>/formatted/items.txt localized display names
        │
        ▼
    out/item_stats.json   {key: {slot, category, name, tiers, items, ip,
                                 ip_ench, stats, by_tier}}

WHAT THIS IS AND IS NOT
The dumps store BASE stats that are byte-identical across every tier of a
line — T4 and T8 Leather Armor both read physicalarmor 108; only `itempower`
moves (700 -> 1100). The number a player sees in game is
    base x f(itempower, quality, enchantment)
and that progression function is NOT in the dumps. So this file is honest
about what it holds: exact base stats plus the exact item power per tier and
per enchantment level. It does not claim to be the tooltip value, because
deriving that would mean inventing the scaling curve (`_meta.values_are:
"base"` states this machine-readably).

The tier-invariance is VERIFIED, not assumed: any stat that does vary across
a line's tiers is moved into `by_tier` and reported — including a stat that
is zero on some tiers and nonzero on others (a zero is a value, not an
absence; only all-zero stats are dropped as no-signal).

Normalization guarantees (changeschapter2.md §A):
  - tier comes from the dump's own `@tier` attribute, cross-checked against
    the name prefix; disagreements are reported, never silently resolved
  - nested enchantment records are preserved (`ip_ench`: tier -> level -> IP)
  - every tier's raw item UniqueName is kept (`items`: tier -> T5_MAIN_MACE)
  - slot/category must agree across a line's tiers; violations are recorded
    in `_meta.inconsistent` and fail the release check downstream

Coverage is every tiered entry in the dumps' `weapon`, `transformationweapon`,
`equipmentitem` and `consumableitem` categories — mainhand, offhand, head,
armor, shoes, cape, bag, potion, food — not just the lines the comp engine
currently curates. `transformationweapon` is its own category and is easy to
miss: every shapeshifter (Earthrune Staff, Prowling Staff …) lives there, and
several are in real ZvZ comps.

This step is OFFLINE: fetch_snapshot.py is the only network step.

Usage:  py -3 pipeline/fetch_item_stats.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DEST = os.path.join(OUT, "item_stats.json")

sys.path.insert(0, HERE)
from provenance import record_derived, snapshot_commit, snapshot_dir  # noqa: E402

ADAPTER = "fetch_item_stats"
ADAPTER_VERSION = "2"

TIER_PREFIX = re.compile(r"^T(\d+)_")
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
# real slot but are a party trick, not a combat consumable. The game separates
# them itself: every genuine potion is shopsubcategory1 "potions" and every
# meal "food" or "fish", while the 8 fireworks are the only "other". Filtering
# on the game's own subcategory keeps this a rule about the data, not a list
# of item names.
CONSUMABLE_SUBCATEGORIES = {"potions", "food", "fish"}


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


def item_tier(entry, inconsistent):
    """The dump's own `@tier` attribute, cross-checked against the name
    prefix. Structural first, regex only as corroboration — a T10 would break
    a single-digit pattern, a renamed item would break a name-derived tier."""
    uid = entry.get("@uniquename", "")
    attr = num(entry.get("@tier"))
    m = TIER_PREFIX.match(uid)
    prefix = int(m.group(1)) if m else None
    if attr is None and prefix is None:
        return None
    if attr is not None and prefix is not None and int(attr) != prefix:
        inconsistent.append(
            f"{uid}: @tier {attr} != name prefix T{prefix}")
    return str(int(attr)) if attr is not None else str(prefix)


def enchant_ip(entry):
    """{enchantment level: item power} from the nested enchantment records —
    preserved rather than discarded (§A). Level 0 is the base @itempower and
    lives in `ip`, not here."""
    ench = (entry.get("enchantments") or {}).get("enchantment")
    if not ench:
        return {}
    ench = ench if isinstance(ench, list) else [ench]
    out = {}
    for e in ench:
        lvl, ip = e.get("@enchantmentlevel"), num(e.get("@itempower"))
        if lvl is not None and ip is not None:
            out[str(lvl)] = ip
    return out


def main():
    commit = snapshot_commit()
    cache = snapshot_dir()
    if not commit or not cache or not os.path.isdir(cache):
        sys.exit("pinned snapshot missing — run: py -3 pipeline/fetch_snapshot.py")
    items_path = os.path.join(cache, "items.json")
    names_path = os.path.join(cache, "formatted", "items.txt")
    for p in (items_path, names_path):
        if not os.path.exists(p):
            sys.exit(f"{p} missing from snapshot — run fetch_snapshot.py")

    with open(items_path, encoding="utf-8") as f:
        dump = json.load(f)["items"]
    names = load_names(names_path)

    # line key -> {slot, category, ip, ip_ench, items, seen:{stat:{tier:value}}}
    acc, inconsistent = {}, []
    for category, fields in (("weapon", WEAPON_STATS),
                             ("transformationweapon", WEAPON_STATS),
                             ("equipmentitem", GEAR_STATS),
                             ("consumableitem", CONSUMABLE_STATS)):
        for e in dump.get(category, []):
            uid = e.get("@uniquename", "")
            if not TIER_PREFIX.match(uid):
                continue
            # No localized name means the game never shows this to a player:
            # the dumps carry DEBUG_*/*_PROTOTYPE dev entries (with genuinely
            # inconsistent tier metadata) that must not pollute the bank or
            # its consistency report. Same rule fetch_gear_lines.py applies —
            # the game's own signal, not a hand-list of exclusions.
            if not names.get(uid):
                continue
            tier = item_tier(e, inconsistent)
            if tier is None:
                continue
            if (category == "consumableitem"
                    and e.get("@shopsubcategory1") not in CONSUMABLE_SUBCATEGORIES):
                continue
            key = uid if category in KEEP_TIER else TIER_PREFIX.sub("", uid)
            rec = acc.setdefault(key, {
                "slot": e.get("@slottype") or "", "category": category,
                "name": "", "ip": {}, "ip_ench": {}, "items": {}, "seen": {},
                "example_item": uid,
            })
            # cross-tier structural consistency: one line, one slot, one category
            if rec["slot"] != (e.get("@slottype") or ""):
                inconsistent.append(
                    f"{key}: slot {rec['slot']!r} (from {rec['example_item']}) "
                    f"!= {e.get('@slottype')!r} (from {uid})")
            if rec["category"] != category:
                inconsistent.append(
                    f"{key}: category {rec['category']!r} != {category!r} ({uid})")
            if not rec["name"]:
                rec["name"] = names.get(uid, "")
            rec["items"][tier] = uid
            ip = num(e.get("@itempower"))
            if ip is not None:
                rec["ip"][tier] = ip
            ench = enchant_ip(e)
            if ench:
                rec["ip_ench"][tier] = {k: ench[k] for k in sorted(ench)}
            for stat in fields:
                v = num(e.get("@" + stat))
                if v is None:
                    continue
                # zero IS a value: dropping it here would hide a genuine
                # zero-to-nonzero transition across tiers (§A)
                rec["seen"].setdefault(stat, {})[tier] = v

    # Collapse: a stat identical on every tier it appears becomes a single
    # base value; anything that genuinely varies is kept per tier and named.
    # A stat that is zero on EVERY tier carries no signal and is dropped.
    out, varying = {}, {}
    for key, rec in acc.items():
        stats, by_tier = {}, {}
        for stat, per_tier in rec["seen"].items():
            vals = set(per_tier.values())
            if vals == {0}:
                continue
            if len(vals) == 1:
                stats[stat] = next(iter(vals))
            else:
                by_tier[stat] = dict(sorted(per_tier.items()))
                if stat not in FLAT:
                    varying[stat] = varying.get(stat, 0) + 1
        entry = {"slot": rec["slot"], "category": rec["category"],
                 "name": rec["name"], "example_item": rec["example_item"],
                 "tiers": sorted(int(t) for t in rec["ip"] or rec["items"]),
                 "items": dict(sorted(rec["items"].items())),
                 "ip": dict(sorted(rec["ip"].items())),
                 "stats": dict(sorted(stats.items()))}
        if rec["ip_ench"]:
            entry["ip_ench"] = dict(sorted(rec["ip_ench"].items()))
        if by_tier:
            entry["by_tier"] = dict(sorted(by_tier.items()))
        out[key] = entry

    payload = {
        "_meta": {
            "source": "ao-data/ao-bin-dumps items.json + formatted/items.txt",
            "source_commit": commit,
            "adapter": ADAPTER,
            "adapter_version": ADAPTER_VERSION,
            "values_are": "base",
            "lines": len(out),
            "inconsistent": sorted(inconsistent),
            "note": ("BASE stats. The dumps are tier-invariant per line — the "
                     "in-game value is base x f(itempower, quality, "
                     "enchantment) and that curve is NOT in the dumps. `ip` "
                     "carries the exact item power per tier, `ip_ench` per "
                     "enchantment level; `by_tier` holds any stat that "
                     "genuinely varies, zeros included."),
        },
        "items": dict(sorted(out.items())),
    }
    with open(DEST, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), sort_keys=True)
    record_derived("item_stats.json", DEST, ADAPTER, ADAPTER_VERSION, commit,
                   ["items.json", "formatted/items.txt"])

    slots = {}
    for e in out.values():
        slots[e["slot"] or "?"] = slots.get(e["slot"] or "?", 0) + 1
    print(f"item stats: {len(out)} lines @ {commit[:12]}, "
          f"{os.path.getsize(DEST) // 1024} KB")
    for s in sorted(slots):
        print(f"  {s:12} {slots[s]:4}")
    if varying:
        print("  stats that VARY across tiers (kept per tier):")
        for s, n in sorted(varying.items(), key=lambda kv: -kv[1]):
            print(f"    {s:32} {n} lines")
    else:
        print("  tier-invariance holds for every numeric stat")
    if inconsistent:
        print(f"  INCONSISTENT ({len(inconsistent)}) — release check will fail:")
        for line in inconsistent[:10]:
            print(f"    {line}")
    print(f"wrote {os.path.relpath(DEST, os.path.join(HERE, os.pardir))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
