#!/usr/bin/env python3
"""
Print a curation worksheet for one or more weapons: every equippable spell with
its parsed function flags, target direction, and description text, then the
rows the weapon scores today (its sheet entry composed with the tree pool).

This is the reference the curator reads while assigning structural
capability scores. Nothing here decides scores — it exists so that no score is
ever assigned without its evidence text in view.

Usage:
    py -3 pipeline/curate_helper.py 2H_POLEHAMMER MAIN_HOLYSTAFF_AVALON
    py -3 pipeline/curate_helper.py --top 5        # top N by usage, uncurated first
"""
import argparse
import functools
import glob
import json
import os
import sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import mastersheet  # noqa: E402
import sheets_lib  # noqa: E402

WEAPONS = json.load(open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8"))
SPELLS = json.load(open(os.path.join(OUT, "spell_index.json"), encoding="utf-8"))


def load_usage():
    """Sightings per weapon from weapon_usage_v2.json (derive_usage.py),
    summed across the fight-size buckets, with the per-bucket split kept.
    The v1 file this used to read was a frozen 24-battle sample that
    nothing wrote any more."""
    v2 = json.load(open(os.path.join(OUT, "weapon_usage_v2.json"), encoding="utf-8"))
    out = {}
    for bucket, weapons in (v2.get("buckets") or {}).items():
        for key, n in weapons.items():
            rec = out.setdefault(key, {"count": 0, "buckets": {}})
            rec["count"] += int(n)
            rec["buckets"][bucket] = int(n)
    return out


USAGE = load_usage()

# Optional: recent per-patch spell changes (patch_history.py). Curation context
# only (which patch changed this E, and how) — never evidence for a score.
_PH = os.path.join(OUT, "patch_history.json")
PATCHES = (json.load(open(_PH, encoding="utf-8"))["patches"]
           if os.path.exists(_PH) else [])


# The capabilities the seeder never proposes (seed_sheets.HUMAN_ONLY: the
# magnitude is a curation judgment) plus, derived at runtime, everything in the
# dataset taxonomy the effect layer cannot express at all. Never a hand list
# of the whole taxonomy — a hand copy of that list carried `energy_drain`, a
# documented fabrication. The taxonomy is every capability a built weapon
# record scores (dataset "weapons" -> "capabilities") that a curated row
# carries: a capability the build derives on its own (ranged_presence,
# build_dataset.derive_ranged_presence) sits on no sheet and is never judged.
@functools.lru_cache(maxsize=None)
def structural_caps():
    from seed_sheets import HUMAN_ONLY  # noqa: E402 — sibling script
    from effect_lookup import EffectLookup  # noqa: E402
    ds_path = os.path.join(OUT, "dataset-latest.json")
    taxonomy = set()
    if os.path.exists(ds_path):
        for w in json.load(open(ds_path, encoding="utf-8"))["weapons"].values():
            taxonomy |= set((w.get("capabilities") or {}).keys())
    curated = {c.get("cap") for entry, _ in ENTRIES.values()
               for c in (entry.get("capabilities") or []) if isinstance(c, dict)}
    curated |= {r.get("cap") for rows in POOLS.values() for r in rows}
    taxonomy &= curated
    lookup = EffectLookup()
    expressible = set()
    for sid in SPELLS:
        try:
            expressible |= set(lookup.candidates(sid).keys())
        except Exception:
            pass
    return tuple(sorted(set(HUMAN_ONLY) | (taxonomy - expressible)))


def load_entries():
    """{weapon key: (sheet entry, sheet path)} over the curated sheets: one
    file per weapon tree, sheets/<subcategory>.yaml, each a list of entries.
    The path is relative to the repository root."""
    out = {}
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            docs = yaml.safe_load(f) or []
        rel = os.path.relpath(path, os.path.join(HERE, os.pardir)).replace("\\", "/")
        for entry in docs:
            if isinstance(entry, dict) and entry.get("weapon"):
                out[entry["weapon"]] = (entry, rel)
    return out


ENTRIES = load_entries()
POOLS = sheets_lib.load_pools()
TUNE_SHEETS = mastersheet.load().get("sheets") or {}


def curated_keys():
    return set(ENTRIES)


def current_rows(key, line):
    """The rows the build scores for this weapon today: its sheet entry's own
    rows, then the tree-pool rows it can equip (sheets_lib.compose, the call
    build_dataset makes), each with the slot of its evidence spell, its
    origin, and the MASTERSHEET tune:sheets score where one replaces it."""
    found = ENTRIES.get(key)
    sub = line.get("subcategory")
    if found is None:
        print(f"\n  [CURRENT ROWS]  no curated entry (the tree's sheet is "
              f"pipeline/sheets/{sub}.yaml): the weapon scores nothing")
        return
    entry, rel = found
    own = {(c.get("cap"), c.get("evidence"))
           for c in (entry.get("capabilities") or []) if isinstance(c, dict)}
    slot_of = {}
    for slot, ids in (line.get("spells") or {}).items():
        for sid in ids:
            slot_of.setdefault(sid, slot)      # build_loadout's slot rule
    tune = TUNE_SHEETS.get(key) or {}
    print(f"\n  [CURRENT ROWS]  {rel} entry + pipeline/sheets/pools/{sub}.yaml "
          f"rows it can equip (sheets_lib.compose)")
    for c in sheets_lib.compose(entry, line, POOLS):
        cap, ev = c.get("cap") or "?", c.get("evidence") or "-"
        if ev in slot_of:
            slot = slot_of[ev].upper()
        else:
            slot = "STATS" if ev in sheets_lib.NON_SPELL_EVIDENCE else "?"
        origin = "own" if (c.get("cap"), c.get("evidence")) in own else "pool"
        extra = f"  use: {c['use']}" if c.get("use") else ""
        if cap in tune:
            extra += f"  -> {tune[cap]} (MASTERSHEET tune:sheets)"
        score = str(c.get("score", "-"))
        print(f"    {slot:<8} {cap:<20} {score:>2}  {ev:<30} {origin}{extra}")
    excepts = [x for x in (entry.get("except") or []) if isinstance(x, dict)]
    if excepts:
        print("    except (pool rows this weapon does not take): "
              + ", ".join(f"{x.get('cap')} <- {x.get('evidence')}" for x in excepts))


def worksheet(key, width=104):
    line = WEAPONS.get(key)
    if line is None:
        print(f"!! {key}: not in weapon_lines.json (parser gap? see README TODOs)\n")
        return
    u = USAGE.get(key, {})
    print("=" * width)
    print(f"{key}   {line['name']}")
    split = ", ".join(f"{b} {n}" for b, n in sorted((u.get("buckets") or {}).items()))
    print(f"   usage: {u.get('count', 0)} sightings ({split or 'none'})   "
          f"two_handed: {line.get('two_handed')}")
    print("=" * width)
    for slot in ("e", "q", "w", "passive"):
        ids = line["spells"].get(slot) or []
        if not ids:
            continue
        print(f"\n  [{slot.upper()}]")
        for sid in ids:
            sp = SPELLS.get(sid)
            if not sp:
                print(f"    {sid:<34} (not in spell_index)")
                continue
            flags = ",".join(sp.get("flags", [])) or "-"
            dirs = ",".join(sp.get("directions", [])) or "-"
            tags = ",".join(sp.get("tags", [])) or "-"
            print(f"    {sid:<34} {sp.get('name','')}")
            print(f"      flags[{flags}]  dir[{dirs}]  tags[{tags}]  target={sp.get('target','-')}")
            desc = " ".join((sp.get("description") or "").split())
            for i in range(0, min(len(desc), 260), 92):
                print(f"      | {desc[i:i+92]}")
    if line.get("subcategory") == "shapeshifterstaff":
        # the E transforms the wielder: the form's abilities sit on no
        # equip menu, so the slots above do not carry them
        print("\n  [FORM]  the form's abilities are scored on the E and are not "
              "listed above:\n          py -3 pipeline/audit_form_abilities.py")
    current_rows(key, line)
    rows = [(p["date"], s) for p in PATCHES for s in p["spells"]
            if key in s["lines"] and s.get("balance_relevant", True)]
    cosmetic = sum(1 for p in PATCHES for s in p["spells"]
                   if key in s["lines"] and not s.get("balance_relevant", True))
    if rows or cosmetic:
        print(f"\n  [PATCH HISTORY]  (dumps diff — context, not evidence)")
        for date, s in rows:
            via = "" if s["id"] in s["roots"] else f"  (via {', '.join(s['roots'])})"
            print(f"    {date}  {s['kind']:<8} {s['id']}{via}")
            for c in s["changes"][:4]:
                print(f"      {c['path']}: {c['old']} -> {c['new']}")
            if s["changes_total"] > 4:
                print(f"      ... {s['changes_total'] - 4} more (out/patch_history.json)")
        if cosmetic:
            print(f"    (+{cosmetic} cosmetic-only change(s) — vfx/audio/controller "
                  f"metadata — in out/patch_history.json)")

    print(f"\n  Structural capabilities to judge (never auto-seeded):")
    print(f"    {', '.join(structural_caps())}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weapons", nargs="*")
    ap.add_argument("--top", type=int, help="top N by usage that are not yet curated")
    args = ap.parse_args()

    keys = args.weapons
    if args.top:
        done = curated_keys()
        keys = [k for k, _ in sorted(USAGE.items(), key=lambda kv: -kv[1]["count"])
                if k not in done][:args.top]
        print(f"# top {args.top} uncurated by usage: {keys}\n")
        if not keys:
            print("every weapon seen in the usage sample already has a curated sheet")
            return
    if not keys:
        ap.error("give weapon keys or --top N")
    for k in keys:
        worksheet(k)


if __name__ == "__main__":
    main()
