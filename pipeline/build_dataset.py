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


def build_loadout(caps, evidence, line, uses=None):
    """Group a weapon's capabilities by the ability SLOT they come from, so the
    engine can enforce one-spell-per-slot (a player equips one Q, one W, one E,
    one passive — not the whole menu). Slot is auto-derived from each
    capability's evidence spell via the weapon's equippable spell list
    (weapon_lines[key]["spells"], keyed q/w/e/passive). Capabilities from base
    stats / auto-attack (evidence WEAPON_STATS, no slot) are "always on".

    A sheet may split ONE spell into mutually exclusive `use:` variants
    (Chillhowl's Frozen Crystal saves an ALLY or freezes an ENEMY — never both
    in the same moment); each (spell, use) pair becomes its own bundle in the
    spell's slot, so the engine scores one use, not the union.

    Returns {"always": {cap: score}, "slots": [[bundle, ...], ...],
             "slot_names": [game slot per entry in slots],
             "slot_spells": [[spell id per bundle], ...]} where each bundle is
    one spell-use's {cap: score} and each inner list is the mutually-exclusive
    choices for one slot. slot_names/slot_spells let the dashboard map a
    player's actual Q/W/passive picks onto the scored bundles. Measured
    2026-08-14: 1278/1319 cap-entries resolve to exactly one slot, 0 span
    multiple slots, 41 are WEAPON_STATS."""
    spell_slot = {}
    for slot, ids in ((line or {}).get("spells", {}) or {}).items():
        for sid in ids:
            spell_slot.setdefault(sid, slot)
    uses = uses or {}
    always, bundles = {}, {}
    for cap, score in caps.items():
        slot_spell = next(((spell_slot[sp], sp) for sp in evidence.get(cap, [])
                           if sp in spell_slot), None)
        if slot_spell:
            key = slot_spell + (uses.get(cap),)
            bundles.setdefault(key, {})[cap] = score
        else:
            always[cap] = score
    slots, spells = {}, {}
    for (slot, sp, _use), b in bundles.items():
        slots.setdefault(slot, []).append(b)
        spells.setdefault(slot, []).append(sp)
    names = list(slots)
    return {"always": always, "slots": [slots[n] for n in names],
            "slot_names": names, "slot_spells": [spells[n] for n in names]}


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
            caps, evidence, uses = {}, {}, {}
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
                # `use:` marks mutually exclusive uses of ONE spell — the
                # capability lands in a use-specific loadout bundle
                if c.get("use"):
                    uses[cap] = c["use"]
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
                "loadout": build_loadout(caps, evidence, line, uses),
            }
            sources[key] = os.path.relpath(path, HERE).replace("\\", "/")

    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "illustrative", "*.yaml"))):
        ingest(path, "illustrative")
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        ingest(path, "curated")

    for key, src in sources.items():
        weapons[key]["source"] = src
    return weapons


# Positioning capability (2026-08-18). The capability model had no notion of
# WHERE damage comes from, so a Galatine spin at 3m and a Frost bomb at 20m
# supplied identical `burst_aoe`. Consequence: asking for a "clap" (stack them,
# bomb them from range) returned a comp with 10 frontline bodies and one real
# ranged bomb — structurally a brawl comp wearing a clap label.
#
# This was first derived from the curated `role_hint` and shipped marked
# PROVISIONAL. It now reads the GAME'S OWN NUMBERS (fetch_item_stats.py):
# `attackrange`, plus whether the weapon supplies any damage at all.
#
# The threshold is measured, not chosen: across the curated set attackrange
# clusters at 1.5/2/3/4 and then 9/11/13, with NOTHING in between. 9 is the
# floor of the upper cluster, so the split falls in a real gap rather than on
# a number someone liked.
#
# BOTH conditions are required, and each fixes a different error the role_hint
# version made. Range alone would count every healer (Great Holy, Hallowfall —
# range 9, no damage): they stand at range but put nothing on the clump, and
# counting them would make the capability meaningless since every comp has
# healers. Damage alone would count melee cleave. Requiring both took the
# qualifying set from 35 weapons to 57, and everything it added is real ranged
# damage that `role_hint: support` was hiding — Damnation, Great Cursed,
# Occult, Enigmatic, Malevolent Locus, Demonic and Great Arcane. Nothing the
# old rule counted was lost.
RANGED_MIN_ATTACKRANGE = 9
DAMAGE_CAPS = ("burst_aoe", "burst_st", "sustained_dps")


def inject_positioning(weapons, item_stats):
    """Add `ranged_presence: 1` to every weapon that can put damage on a clump
    from outside it, in BOTH the flat capability map (display + base-party
    supply) and `loadout.always` (the loadout-aware scoring path). It goes in
    `always`, never a slot: a weapon's range is not a spell choice the player
    trades against another."""
    tagged = 0
    for key, w in weapons.items():
        stats = (item_stats.get(key) or {}).get("stats") or {}
        rng = stats.get("attackrange")
        if not isinstance(rng, (int, float)) or rng < RANGED_MIN_ATTACKRANGE:
            continue
        if not any(w["capabilities"].get(c) for c in DAMAGE_CAPS):
            continue
        w["capabilities"]["ranged_presence"] = 1
        lo = w.setdefault("loadout", {})
        lo.setdefault("always", {})["ranged_presence"] = 1
        tagged += 1
    return tagged


def load_templates():
    templates, scoring, styles, mechanics, composition = {}, {}, {}, {}, {}
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
        elif base == "composition.yaml":
            composition = doc
        else:
            templates[doc["content"]] = doc
    return templates, scoring, styles, mechanics, composition


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
    templates, scoring, styles, mechanics, composition = load_templates()
    stats_path = os.path.join(OUT, "item_stats.json")
    item_stats = {}
    if os.path.exists(stats_path):
        with open(stats_path, encoding="utf-8") as f:
            item_stats = json.load(f).get("items", {})
    n_ranged = inject_positioning(weapons, item_stats)

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
        # Item stats bank (fetch_item_stats.py) — the game's own numbers for
        # every weapon and worn item. Optional so a checkout without it still
        # builds. REFERENCE DATA: nothing in the scoring path reads it, the
        # same rule gear capabilities follow. It is here so the engine and the
        # dossier read one source instead of two.
        "item_stats": item_stats,
        "templates": templates,
        "scoring": scoring,
        "styles": styles,
        "mechanics": mechanics,
        # Composition constraints + viability + size physics (composition.yaml)
        # — what the FORGE may generate; never a bar to scoring a manual party.
        "composition": composition,
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
