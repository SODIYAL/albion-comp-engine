#!/usr/bin/env python3
"""
Auto-seed draft capability sheets for the most-used weapons (design doc §6.3 step 1).

For each weapon in the usage ranking, proposes a capability for every effect its
equippable spells actually produce, resolved through the structured effect map
(effect_map.yaml) rather than description keywords.

WHAT CHANGED 2026-08-12. Seeding used to run off 13 prose regexes, which saw a
fraction of the game: 100 weapon lines apply a movespeed debuff and the `slow`
regex matched almost none of them. It also refused to propose structural
capabilities (engage/peel/tankiness/...) on the grounds that they were pure
judgement. That is no longer true for the ones the data can reach: 1H Mace's
Deep Leap resolves to dash + invincibility + five immunities on self, which
grounds engage, disengage, tankiness, mobility and catch mechanically.

Everything is still provisional. Every row carries `review: TODO` and a comment
naming the effect and direction it came from, so a curator can check the
reasoning rather than just the conclusion. Capabilities the effect layer cannot
express — zone_control, burst_aoe, clump_create, heal_burst, anti_dive — are
still never seeded and remain entirely human.

Curation = adjust scores, add what is missing, delete the review flags, move the
sheet to sheets/. Re-running the seeder then skips it and deletes its draft.

Usage:  py -3 pipeline/seed_sheets.py [top_n]     (default 40)
"""
import json, os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from effect_lookup import EffectLookup  # noqa: E402

WEAPONS = json.load(open(os.path.join(HERE, "out", "weapon_lines.json"), encoding="utf-8"))
USAGE = json.load(open(os.path.join(HERE, "out", "weapon_usage.json"), encoding="utf-8"))["weapons"]
LOOKUP = EffectLookup()

# Never auto-seeded: the effect layer cannot express these, so a machine guess
# would be fabrication. They stay a curator's job.
HUMAN_ONLY = {"zone_control", "burst_aoe", "burst_st", "sustained_dps", "execute",
              "clump_create", "heal_burst", "anti_dive", "energy_drain"}


def curated_keys():
    """Weapons that already have a hand-curated sheet in sheets/ — never seed a
    draft for these; a stale draft alongside a curated sheet invites editing the
    wrong file."""
    keys = set()
    for path in glob.glob(os.path.join(HERE, "sheets", "*.yaml")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("- weapon:"):
                    # strip the trailing YAML comment: "- weapon: 2H_MACE  # Heavy Mace"
                    keys.add(line.split(":", 1)[1].split("#")[0].strip())
    return keys


def propose(line):
    """{capability: (score, spell, slot, reasons)} — best evidence per capability."""
    best = {}
    for slot in ("e", "q", "w", "passive"):
        for sid in line["spells"].get(slot) or []:
            cands = LOOKUP.candidates(sid)
            if not cands:
                continue
            # an E defines a weapon; everything else is a build choice
            score = 4 if slot == "e" else 2   # 1-7 scale
            for cap, reasons in cands.items():
                if cap in HUMAN_ONLY:
                    continue
                prev = best.get(cap)
                if prev and (prev[0] > score or (prev[0] == score and prev[2] == "e")):
                    continue
                best[cap] = (score, sid, slot, reasons)
    return best


def seed(top_n):
    out_dir = os.path.join(HERE, "sheets", "draft")
    os.makedirs(out_dir, exist_ok=True)
    ranked = sorted(USAGE.items(), key=lambda kv: -kv[1]["count"])[:top_n]
    missing, written, skipped = [], 0, []
    done = curated_keys()

    for key, u in ranked:
        if key in done:
            skipped.append(key)
            stale = os.path.join(out_dir, f"{key}.yaml")
            if os.path.exists(stale):
                os.remove(stale)
            continue
        line = WEAPONS.get(key)
        if line is None:
            missing.append(key)
            continue

        rows = propose(line)
        out = [
            f"# DRAFT — auto-seeded from the structured effect map. Usage: "
            f"{u['count']} sightings, dominant role: {u['role']}.",
            f"# Every score is provisional; the comment names the effect and target",
            f"# direction it was derived from. Humans: adjust scores, ADD what the",
            f"# effect layer cannot see (zone_control/burst_aoe/clump_create/heal_burst/",
            f"# anti_dive), then move to sheets/.",
            "",
            f"- weapon: {key}",
            f"  # {line['name']}",
            f"  role_hint: {u['role']}",
            f"  capabilities:",
        ]
        for cap, (score, sid, slot, reasons) in sorted(rows.items()):
            name = LOOKUP.spells.get(sid, {}).get("name", sid)
            why = "; ".join(reasons[:2])
            out.append(f"    - {{cap: {cap}, score: {score}, evidence: {sid}, review: TODO}}"
                       f"   # {slot.upper()}: {name} — {why}")
        if not rows:
            out.append("    []   # no resolvable effects; fully manual")

        with open(os.path.join(out_dir, f"{key}.yaml"), "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        written += 1

    total = sum(len(propose(WEAPONS[k])) for k, _ in ranked if k in WEAPONS and k not in done)
    print(f"seeded {written} draft sheets -> sheets/draft/  ({total} proposed capabilities)")
    if skipped:
        print(f"already curated, skipped ({len(skipped)}): {skipped}")
    if missing:
        print(f"NOT in weapon catalog ({len(missing)}): {missing}")


if __name__ == "__main__":
    seed(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
