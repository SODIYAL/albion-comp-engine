#!/usr/bin/env python3
"""
Print a curation worksheet for one or more weapons: every equippable spell with
its parsed function flags, target direction, and description text.

This is the reference a human (or Claude) reads while assigning structural
capability scores. Nothing here decides scores — it exists so that no score is
ever assigned without its evidence text in front of you.

Usage:
    py -3 pipeline/curate_helper.py 2H_POLEHAMMER MAIN_HOLYSTAFF_AVALON
    py -3 pipeline/curate_helper.py --top 5        # top N by usage, uncurated first
"""
import json, os, glob, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

WEAPONS = json.load(open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8"))
SPELLS = json.load(open(os.path.join(OUT, "spell_index.json"), encoding="utf-8"))


def load_usage():
    """Sightings per weapon from weapon_usage_v2.json (sample_battles.py),
    summed across the fight-size buckets, with the per-bucket split kept.
    The v1 file this used to read was a frozen 24-battle sample from
    2026-08-12 that nothing wrote any more."""
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
# only — "this E was nerfed on 2026-05-26" — never evidence for a score.
_PH = os.path.join(OUT, "patch_history.json")
PATCHES = (json.load(open(_PH, encoding="utf-8"))["patches"]
           if os.path.exists(_PH) else [])

# The capabilities the seeder never proposes (seed_sheets.HUMAN_ONLY: the
# magnitude is a human call) plus, derived at runtime, everything in the
# dataset taxonomy the effect layer cannot express at all. Never a hand list
# of the whole taxonomy — the 2026-08 copy of that list still carried
# `energy_drain`, a documented fabrication.
def structural_caps():
    from seed_sheets import HUMAN_ONLY  # noqa: E402 — sibling script
    from effect_lookup import EffectLookup  # noqa: E402
    ds_path = os.path.join(OUT, "dataset-latest.json")
    taxonomy = set()
    if os.path.exists(ds_path):
        for w in json.load(open(ds_path, encoding="utf-8"))["weapons"].values():
            taxonomy |= set((w.get("caps") or {}).keys())
    lookup = EffectLookup()
    expressible = set()
    for sid in SPELLS:
        try:
            expressible |= set(lookup.candidates(sid).keys())
        except Exception:
            pass
    return sorted(set(HUMAN_ONLY) | (taxonomy - expressible))


def curated_keys():
    keys = set()
    for path in glob.glob(os.path.join(HERE, "sheets", "*.yaml")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("- weapon:"):
                    # strip the trailing YAML comment: "- weapon: 2H_MACE  # Heavy Mace"
                    keys.add(line.split(":", 1)[1].split("#")[0].strip())
    return keys


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
