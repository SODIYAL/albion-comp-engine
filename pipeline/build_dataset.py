#!/usr/bin/env python3
"""
Build the versioned dataset the engine and the SPA both consume
(design doc §6.3 step 5).

    sheets/*.yaml              curated, evidence-linted        (authoritative)
    sheets/illustrative/*.yaml design-doc §2.3 placeholders    (NOT a release;
                               empty since 2026-08-12 — all weapons curated,
                               the file is a tombstone record)
    templates/*.yaml           content templates + scoring config
        │
        ▼
    out/dataset-<version>.json + out/dataset-latest.json

Why this exists: before it, capability numbers lived in BOTH a Python dict
inside the prototype and the curated YAML sheets, and they had already
diverged (Longbow resist_shred was 2 in the prototype, 1 in the curated
sheet). One source of truth, one export, both consumers read the export.

Precedence: a curated sheet always shadows an illustrative entry for the same
weapon. `release_clean` is true only when zero illustrative sheets are present
AND the evidence lint passes.

Usage:  python3 build_dataset.py [--version 2026.08.1]
"""
import json, os, glob, argparse, subprocess, sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DEFAULT_VERSION = "2026.08.1"


def _load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def load_weapon_lines():
    with open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8") as f:
        return json.load(f)


def display_name(line, key):
    """Game data names are tier-prefixed ("Adept's Heavy Mace"); strip it."""
    name = (line or {}).get("name", key)
    for prefix in ("Adept's ", "Novice's ", "Journeyman's ", "Expert's ",
                   "Master's ", "Grandmaster's ", "Elder's "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def build_loadout(caps, evidence, line):
    """Group a weapon's capabilities by the ability SLOT they come from, so the
    engine can enforce one-spell-per-slot (a player equips one Q, one W, one E,
    one passive — not the whole menu). Slot is auto-derived from each
    capability's evidence spell via the weapon's equippable spell list
    (weapon_lines[key]["spells"], keyed q/w/e/passive). Capabilities from base
    stats / auto-attack (evidence WEAPON_STATS, no slot) are "always on".

    Returns {"always": {cap: score}, "slots": [[bundle, ...], ...]} where each
    bundle is one spell's {cap: score} and each inner list is the mutually-
    exclusive choices for one slot. Measured 2026-08-14: 1278/1319 cap-entries
    resolve to exactly one slot, 0 span multiple slots, 41 are WEAPON_STATS."""
    spell_slot = {}
    for slot, ids in ((line or {}).get("spells", {}) or {}).items():
        for sid in ids:
            spell_slot.setdefault(sid, slot)
    always, bundles = {}, {}
    for cap, score in caps.items():
        slot_spell = next(((spell_slot[sp], sp) for sp in evidence.get(cap, [])
                           if sp in spell_slot), None)
        if slot_spell:
            bundles.setdefault(slot_spell, {})[cap] = score
        else:
            always[cap] = score
    slots = {}
    for (slot, _sp), b in bundles.items():
        slots.setdefault(slot, []).append(b)
    return {"always": always, "slots": list(slots.values())}


def load_sheets(weapon_lines):
    """Curated sheets win over illustrative ones for the same weapon key."""
    weapons, sources = {}, {}

    def ingest(path, status):
        for entry in _load_yaml(path):
            key = entry.get("weapon")
            if not key:
                continue
            # curated always wins; never let illustrative overwrite it
            if weapons.get(key, {}).get("status") == "curated" and status != "curated":
                continue
            caps, evidence = {}, {}
            for c in entry.get("capabilities", []):
                if not isinstance(c, dict):
                    continue
                cap, score = c.get("cap"), c.get("score", 0)
                if not cap or not score:
                    continue
                # a sheet may cite several spells for one capability; the score
                # is the capability's total, not a per-spell increment
                caps[cap] = max(caps.get(cap, 0), score)
                if c.get("evidence"):
                    evidence.setdefault(cap, [])
                    if c["evidence"] not in evidence[cap]:
                        evidence[cap].append(c["evidence"])
            line = weapon_lines.get(key)
            weapons[key] = {
                "unique_name": key,
                "display_name": display_name(line, key),
                "status": status,
                "in_game_data": line is not None,
                "role_hint": entry.get("role_hint"),
                # retired by the game: still scoreable (old permalinks must
                # load) but never recommended — see Engine.pool
                "removed": bool(entry.get("removed")),
                # YAML parses the unquoted date; keep it a plain string in JSON
                "curated_as_of": (str(entry["curated_as_of"])
                                  if entry.get("curated_as_of") else None),
                "capabilities": caps,
                "evidence": evidence,
                # one-spell-per-slot decomposition for loadout-aware scoring
                # (engine reads this; flat `capabilities` stays for display +
                # base-party supply). Auto-derived from evidence spell -> slot.
                "loadout": build_loadout(caps, evidence, line),
            }
            sources[key] = os.path.relpath(path, HERE).replace("\\", "/")

    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "illustrative", "*.yaml"))):
        ingest(path, "illustrative")
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        ingest(path, "curated")

    for key, src in sources.items():
        weapons[key]["source"] = src
    inject_positioning(weapons)
    return weapons


# Positioning capability (2026-08-18, PROVISIONAL). The capability model had
# no notion of WHERE damage comes from, so a Galatine spin at 3m and a Frost
# bomb at 20m supplied identical `burst_aoe`. Consequence: asking for a "clap"
# (stack them, bomb them from range) returned a comp with 10 frontline bodies
# and one real ranged bomb — structurally a brawl comp wearing a clap label,
# because melee AoE satisfied the clap weights just as well.
#
# This is a SHAPE constraint, not true per-spell range modelling: it is derived
# from the curated `role_hint`, so it costs no new curation and cites no
# evidence spell (hence injected post-lint, here, rather than in the sheets).
# Real range modelling would need a per-spell radius/cast-range read — see
# MECHANICS_TODO.md. Only role_hint "range" counts: the question it answers is
# "can this comp put damage on a clump from outside it", so healers and
# supports (also back-line, but not damage) are deliberately excluded.
RANGED_ROLE_HINTS = ("range",)


def inject_positioning(weapons):
    """Add `ranged_presence: 1` to every ranged weapon, in BOTH the flat
    capability map (display + base-party supply) and `loadout.always` (the
    loadout-aware scoring path). It goes in `always`, never a slot: a weapon's
    range is not a spell choice the player trades against another."""
    for w in weapons.values():
        if w.get("role_hint") not in RANGED_ROLE_HINTS:
            continue
        w["capabilities"]["ranged_presence"] = 1
        lo = w.setdefault("loadout", {})
        lo.setdefault("always", {})["ranged_presence"] = 1


def load_templates():
    templates, scoring, styles, mechanics = {}, {}, {}, {}
    for path in sorted(glob.glob(os.path.join(HERE, "templates", "*.yaml"))):
        doc = _load_yaml(path)
        if not isinstance(doc, dict):
            continue
        base = os.path.basename(path)
        if base == "scoring.yaml":
            scoring = doc
        elif base == "styles.yaml":
            styles = doc.get("styles", {})
        elif base == "mechanics.yaml":
            mechanics = doc
        else:
            templates[doc["content"]] = doc
    return templates, scoring, styles, mechanics


def run_lint():
    """Run the evidence lint over curated sheets only. Illustrative sheets are
    deliberately excluded — they have no evidence and would always fail."""
    paths = sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml")))
    if not paths:
        return True, "no curated sheets to lint"
    proc = subprocess.run([sys.executable, os.path.join(HERE, "evidence_lint.py")] + paths,
                          capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--skip-lint", action="store_true")
    args = ap.parse_args()

    weapon_lines = load_weapon_lines()
    weapons = load_sheets(weapon_lines)
    templates, scoring, styles, mechanics = load_templates()

    lint_ok, lint_out = (True, "skipped") if args.skip_lint else run_lint()

    curated = sorted(k for k, w in weapons.items() if w["status"] == "curated")
    illustrative = sorted(k for k, w in weapons.items() if w["status"] == "illustrative")
    unknown = sorted(k for k, w in weapons.items() if not w["in_game_data"])

    dataset = {
        "_meta": {
            "version": args.version,
            "weapons_total": len(weapons),
            "weapons_curated": len(curated),
            "weapons_illustrative": len(illustrative),
            "templates": sorted(templates),
            "lint_passed": lint_ok,
            "release_clean": bool(lint_ok and not illustrative and not unknown),
            "note": ("NOT A RELEASE — contains illustrative placeholder sheets."
                     if illustrative else "release candidate"),
            "illustrative_weapons": illustrative,
            "unknown_to_game_data": unknown,
        },
        "weapons": weapons,
        "templates": templates,
        "scoring": scoring,
        "styles": styles,
        "mechanics": mechanics,
    }

    os.makedirs(OUT, exist_ok=True)
    for name in (f"dataset-{args.version}.json", "dataset-latest.json"):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=1, sort_keys=True)

    print(f"dataset v{args.version}: {len(weapons)} weapons "
          f"({len(curated)} curated, {len(illustrative)} illustrative), "
          f"{len(templates)} template(s)")
    print(f"  evidence lint : {'PASS' if lint_ok else 'FAIL'}")
    if not lint_ok:
        print("   " + lint_out.replace("\n", "\n   "))
    if unknown:
        print(f"  NOT in game data: {unknown}")
    print(f"  release_clean : {dataset['_meta']['release_clean']}"
          + ("" if dataset["_meta"]["release_clean"]
             else f"  (blocked by {len(illustrative)} illustrative sheet(s))"))
    print(f"  wrote out/dataset-{args.version}.json + out/dataset-latest.json")
    return 0 if lint_ok else 1


if __name__ == "__main__":
    sys.exit(main())
