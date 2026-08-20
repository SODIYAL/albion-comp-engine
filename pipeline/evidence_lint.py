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

Additionally, if out/patch_history.json exists (patch_history.py), a WARNING
is raised for any cited evidence spell that a game patch touched after the
sheet's `curated_as_of` date — the scores resting on it need a re-read.

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
import sheets_lib  # noqa: E402

WEAPONS = json.load(open(os.path.join(HERE, "out", "weapon_lines.json"), encoding="utf-8"))
POOLS = sheets_lib.load_pools()

# Evidence values that are not spells (base item stats, e.g. tankiness from
# armour value; GEAR_STATS = statless gear items — capes, offhands,
# potions, food). Exempt from rule 3 — there is no spell to check.
NON_SPELL_EVIDENCE = {"WEAPON_STATS", "GEAR_STATS"}

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

# ---- patch staleness (warning only, never blocks) ---------------------------
# out/patch_history.json (built by patch_history.py from ao-bin-dumps git
# history) records which spells each game patch touched, keyed back to the
# equippable root spells sheets cite. A sheet declares `curated_as_of:
# YYYY-MM-DD`; if a cited evidence spell changed in a LATER patch, the scores
# resting on it need a re-read. Absent file or absent date = check is silent —
# drafts and illustrative sheets carry no curation date to be stale against.


def load_patch_index(path=os.path.join(HERE, "out", "patch_history.json")):
    """{equippable root spell: [patch dates it changed in]}, newest last."""
    if not os.path.exists(path):
        return {}
    idx = {}
    for p in json.load(open(path, encoding="utf-8")).get("patches", []):
        for s in p.get("spells", []):
            # VFX/audio/controller-metadata churn can't move a score; a
            # missing flag (older file) conservatively counts as relevant
            if not s.get("balance_relevant", True):
                continue
            for root in s.get("roots", [s["id"]]):
                idx.setdefault(root, set()).add(p["date"])
    return {k: sorted(v) for k, v in idx.items()}


PATCH_INDEX = load_patch_index()


def stale_evidence(curated_as_of, spell_ids, index=None):
    """[(spell_id, [dates])] for cited spells patched after the curation date.
    Dates are ISO strings, so string comparison is date comparison."""
    index = PATCH_INDEX if index is None else index
    if not curated_as_of:
        return []
    d0 = str(curated_as_of)
    out = []
    for sid in sorted(set(spell_ids)):
        dates = [d for d in index.get(sid, []) if d > d0]
        if dates:
            out.append((sid, dates))
    return out


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
        cited = set()
        # composed rows: the weapon's own + applicable tree-pool rows, so a
        # pool row that stops being equippable after a patch still FAILS here
        for c in sheets_lib.compose(entry, line, POOLS):
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
            cited.add(ev)
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
        for sid, dates in stale_evidence(entry.get("curated_as_of"), cited):
            warnings.append(
                f"{wkey}: evidence spell '{sid}' changed in patch(es) "
                f"{', '.join(dates)}, after curated_as_of "
                f"{entry['curated_as_of']} — re-verify the scores citing it "
                f"(details in out/patch_history.json)")
    return errors, warnings


def lint_pools():
    """Pool files: every row must actually APPLY somewhere and ground its cap.

    compose() applies a pool row only where the evidence spell is equippable,
    so a typo'd or patch-removed spell would silently apply to NOBODY — this
    check makes that an ERROR instead."""
    errors, warnings = [], []
    tree = {}
    for wk, line in WEAPONS.items():
        tree.setdefault(line.get("subcategory"), []).append(wk)
    for sub, rows in sorted(POOLS.items()):
        members = tree.get(sub, [])
        if not members:
            errors.append(f"pools/{sub}: no weapon line has this subcategory")
            continue
        for r in rows:
            cap, score, ev = r.get("cap"), r.get("score", 0), r.get("evidence")
            where = f"pools/{sub}.{cap}"
            if not score:
                errors.append(f"{where}: pool row without a nonzero score")
                continue
            if not ev:
                errors.append(f"{where}: pool row without evidence")
                continue
            if ev in NON_SPELL_EVIDENCE:
                continue
            holders = [w for w in members
                       if ev in {s for sl in WEAPONS[w]["spells"].values()
                                 for s in sl}]
            if not holders:
                errors.append(
                    f"{where}: evidence spell '{ev}' is equippable on NO "
                    f"{sub} weapon — the row applies to nobody")
                continue
            if cap in CHECKABLE and cap not in LOOKUP.candidates(ev):
                name = LOOKUP.spells.get(ev, {}).get("name", ev)
                if not LOOKUP.has_structured(ev) and not LOOKUP.spells.get(ev, {}).get("flags"):
                    warnings.append(
                        f"{where}: '{name}' has no structured effects and no "
                        f"prose flags — cannot verify, review by hand")
                else:
                    offer = ", ".join(sorted(LOOKUP.candidates(ev))) or "nothing"
                    errors.append(
                        f"{where}: '{name}' cannot ground {cap}. "
                        f"Its effects support: {offer}")
    return errors, warnings


GEAR_SPELLS = {}
_gs_path = os.path.join(HERE, "out", "gear_spells.json")
if os.path.exists(_gs_path):
    GEAR_SPELLS = json.load(open(_gs_path, encoding="utf-8"))


def lint_gear():
    """Gear sheets (sheets/gear/): every nonzero score cites either the
    GEAR_STATS sentinel or an ability actually ON the item's menu, and the
    cited ability must be able to ground the claimed capability."""
    errors, warnings = [], []
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "gear", "*.yaml"))):
        for entry in (yaml.safe_load(open(path, encoding="utf-8")) or []):
            gkey = entry.get("gear")
            if not gkey:
                continue
            menu = GEAR_SPELLS.get(gkey) or {}
            equippable = set(menu.get("actives") or []) | set(menu.get("passives") or [])
            for c in entry.get("capabilities", []):
                cap, score, ev = c.get("cap"), c.get("score", 0), c.get("evidence")
                where = f"gear/{gkey}.{cap}"
                if not score:
                    continue
                if not ev:
                    errors.append(f"{where}: nonzero score with no evidence")
                    continue
                if ev in NON_SPELL_EVIDENCE:
                    continue
                if ev not in equippable:
                    errors.append(
                        f"{where}: ability '{ev}' is NOT on this item's menu")
                    continue
                if cap in CHECKABLE and cap not in LOOKUP.candidates(ev):
                    name = LOOKUP.spells.get(ev, {}).get("name", ev)
                    if not LOOKUP.has_structured(ev) and not LOOKUP.spells.get(ev, {}).get("flags"):
                        warnings.append(
                            f"{where}: '{name}' has no structured effects and "
                            f"no prose flags — cannot verify, review by hand")
                    else:
                        offer = ", ".join(sorted(LOOKUP.candidates(ev))) or "nothing"
                        errors.append(
                            f"{where}: '{name}' cannot ground {cap}. "
                            f"Its effects support: {offer}")
    return errors, warnings


def main(paths):
    total_err = 0
    for label, fn in (("sheets/pools/", lint_pools), ("sheets/gear/", lint_gear)):
        errors, warnings = fn()
        status = "FAIL" if errors else "OK"
        print(f"[{status}] {label}  ({len(errors)} errors, {len(warnings)} warnings)")
        for e in errors:
            print(f"   ERROR  {e}")
        for w in warnings:
            print(f"   warn   {w}")
        total_err += len(errors)
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
