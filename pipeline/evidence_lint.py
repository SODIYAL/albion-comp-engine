#!/usr/bin/env python3
"""
Evidence lint — CI gate for capability sheets (design doc §6.3 step 4).

Every nonzero capability score must cite an evidence spell. The lint verifies:
  1. the weapon line exists in the parsed game data
  2. the cited spell is actually equippable on that weapon (any Q/W/E/passive
     slot) — gear capabilities belong on gear sheets, not weapons
  3. the spell can actually GROUND the claimed capability, checked against the
     structured effect map (effect_map.yaml) rather than description keywords

Rule 3 changed 2026-08-12. It used to require a prose regex flag matching the
capability class, which missed most of the game: 100 weapon lines apply a
movespeed debuff and the `slow` regex saw almost none of them. It now resolves
the spell's structured effects, applies the direction-aware effect map, and
checks the claimed capability is among the CANDIDATES — with the old prose
flags kept as a fallback, because neither source is complete alone.

Capabilities the effect layer cannot express (zone_control, burst_aoe,
clump_create, heal_burst, anti_dive, engage-by-range ...) remain pure human
judgement and get checks 1-2 only. That boundary is computed, not hardcoded:
a capability is checked iff the effect map can produce it at all.

Exit code 1 on any ERROR — blocks the data release.

Usage:  py -3 pipeline/evidence_lint.py [sheets/*.yaml]
"""
import json, sys, os, glob

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from effect_lookup import EffectLookup  # noqa: E402

WEAPONS = json.load(open(os.path.join(HERE, "out", "weapon_lines.json"), encoding="utf-8"))

# Evidence values that are not spells (base item stats, e.g. tankiness from
# armour value). Exempt from rule 3 — there is no spell to check.
NON_SPELL_EVIDENCE = {"WEAPON_STATS"}

LOOKUP = EffectLookup()

# Every capability the effect map is capable of producing. A claim outside this
# set is a judgement call the data cannot adjudicate, so we do not try.
CHECKABLE = set()
for _rule in LOOKUP.map.values():
    if isinstance(_rule, dict):
        for _d, _caps in _rule.items():
            if _d not in ("note", "ignore") and isinstance(_caps, list):
                CHECKABLE.update(_caps)
from effect_lookup import PROSE_FALLBACK  # noqa: E402
for _caps in PROSE_FALLBACK.values():
    CHECKABLE.update(_caps)

# Raw damage is NOT part of the structured effect vocabulary — it is a plain
# health `directattributechange`, not a typed effect — so the effect layer can
# never confirm or deny a damage claim. The map only reaches these capabilities
# via damage-BUFF effects, which would wrongly demand that every damage score
# trace to a buff. Damage stays human judgement, like zone_control.
CHECKABLE -= {"burst_st", "burst_aoe", "sustained_dps", "execute"}


def lint_sheet(path):
    errors, warnings = [], []
    docs = yaml.safe_load(open(path, encoding="utf-8")) or []
    for entry in docs:
        wkey = entry.get("weapon")
        line = WEAPONS.get(wkey)
        if line is None:
            errors.append(f"{wkey}: unknown weapon line (not in game data)")
            continue
        equippable = {s for slot in line["spells"].values() for s in slot}
        for c in entry.get("capabilities", []):
            cap, score, ev = c.get("cap"), c.get("score", 0), c.get("evidence")
            where = f"{wkey}.{cap}"
            if not score:
                continue
            if not ev:
                errors.append(f"{where}: nonzero score with no evidence")
                continue
            if ev in NON_SPELL_EVIDENCE:
                continue
            if ev not in equippable:
                errors.append(
                    f"{where}: evidence spell '{ev}' is NOT equippable on {wkey} "
                    f"(if a gear item provides this, it belongs on that item's sheet)")
                continue
            if cap not in CHECKABLE:
                continue                      # structural — human judgement
            cands = LOOKUP.candidates(ev)
            if cap in cands:
                continue
            name = LOOKUP.spells.get(ev, {}).get("name", ev)
            if not LOOKUP.has_structured(ev) and not LOOKUP.spells.get(ev, {}).get("flags"):
                warnings.append(
                    f"{where}: '{name}' has no structured effects and no prose "
                    f"flags — cannot verify, review by hand")
                continue
            offer = ", ".join(sorted(cands)) or "nothing"
            errors.append(
                f"{where}: '{name}' cannot ground {cap}. Its effects support: {offer}")
    return errors, warnings


def main(paths):
    total_err = 0
    for path in paths:
        errors, warnings = lint_sheet(path)
        status = "FAIL" if errors else "OK"
        print(f"[{status}] {os.path.basename(path)}  "
              f"({len(errors)} errors, {len(warnings)} warnings)")
        for e in errors:
            print(f"   ERROR  {e}")
        for w in warnings:
            print(f"   warn   {w}")
        total_err += len(errors)
    sys.exit(1 if total_err else 0)


if __name__ == "__main__":
    args = sys.argv[1:] or glob.glob(os.path.join(HERE, "sheets", "*.yaml"))
    main(args)
