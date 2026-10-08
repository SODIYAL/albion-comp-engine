"""Shared sheet composition — weapon entries + tree-level spell pools.

Restructure (spell-level curation, step 2 of the geometric-AoE
plan): the Q/W/passive spells a weapon tree shares are curated ONCE in
sheets/pools/<subcategory>.yaml instead of being copy-pasted into every
line-mate's sheet (the copy-paste drift this kills: 16 same-spell-
different-score groups in the magnitude audit). The E spell — the actual
differentiator — stays on the weapon entry.

POOL SEMANTICS
  - A pool row {cap, score, evidence} applies to every weapon of the pool's
    subcategory (weapon_lines.json) that can EQUIP the evidence spell in any
    slot. Evidence WEAPON_STATS (base item stats, no spell) applies tree-wide.
  - A weapon whose own tree's pool reaches none of its menu spells takes
    the spell rows of every pool whose spells it equips (Black Hands: the
    knuckles subcategory, the dagger Q/W/passive menu). Base-stat rows stay
    with the weapon's own tree. pool_rows_for() is the one reading of this.
  - A weapon entry may list `except: [{cap, evidence}, ...]` — deliberate
    non-takes: a shared row this weapon does not receive.
  - A weapon's own row with the same (cap, evidence) pair OVERRIDES the pool
    row: that weapon's deliberate score for the shared spell.

Composed row order: the weapon's own rows first (sheet order), then
applicable pool rows in pool-file order. Every row scores on its own
spell (build_dataset.build_loadout), and two rows of one capability merge
by the maximum (engine._merge_max), so the order carries no semantics.

The consumers of per-weapon capability rows go through compose() —
build_dataset, evidence_lint, build_magnitude_review, build_stat_chart —
so the pool layer cannot half-apply to a score. (build_interactions.py
walks the sheets itself to build the spell -> capability DOMAIN for
nonstacking_caps; that walk yields a superset and never scores.)

GEAR POOLS (sheets/gear/pools/<tree>.yaml) are the same structure one
layer over: the two actives every item of an armor tree x slot shares
(every plate helmet carries Energizing Shield and Stone Skin; its third
active is its own) are curated once per tree and composed into every
item of the tree whose dumps menu carries the spell. An item's own row
with the same (cap, evidence) pair overrides the pool row; `except:`
marks a deliberate non-take. Consumers: load_gear_sheets, lint_gear,
build_stat_chart — through compose_gear().
"""
import glob
import json
import os

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
POOL_DIR = os.path.join(HERE, "sheets", "pools")

# Evidence values that are not spells (base item stats). They cannot be
# equippability-tested; a pool row citing one applies to the whole tree.
NON_SPELL_EVIDENCE = {"WEAPON_STATS"}


def load_pools(pool_dir=POOL_DIR):
    """{subcategory: [row, ...]} from sheets/pools/*.yaml.

    Each pool file is one document: {subcategory: str, capabilities: [rows]}.
    """
    pools = {}
    for path in sorted(glob.glob(os.path.join(pool_dir, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        sub = doc.get("subcategory")
        rows = [r for r in (doc.get("capabilities") or [])
                if isinstance(r, dict) and r.get("cap")]
        if sub and rows:
            pools.setdefault(sub, []).extend(rows)
    return pools


def equippable(line):
    """All spell ids a weapon can equip, any slot."""
    return {s for ids in ((line or {}).get("spells") or {}).values()
            for s in ids}


def pool_rows_for(line, pools):
    """The shared rows a weapon can receive, before its own rows and
    excepts: its tree pool (subcategory), or — when that pool reaches none
    of its menu spells — the spell rows of every pool whose spells it
    equips. Base-stat rows (WEAPON_STATS) come from its own tree only."""
    if line is None:
        return []
    sub = line.get("subcategory")
    own_pool = pools.get(sub, [])
    equip = equippable(line)
    if any(r.get("evidence") in equip for r in own_pool):
        return list(own_pool)
    borrowed = [r for s, rows in sorted(pools.items()) if s != sub
                for r in rows
                if r.get("evidence") not in NON_SPELL_EVIDENCE
                and r.get("evidence") in equip]
    return list(own_pool) + borrowed


def compose(entry, line, pools):
    """The weapon's full capability row list: own rows + applicable pool rows.

    entry: one sheet document ({weapon, capabilities, except, ...}).
    line:  weapon_lines.json[weapon] (None for unknown weapons — pool rows
           then cannot be equippability-tested and are not applied).
    pools: load_pools() result.
    """
    own = [c for c in (entry.get("capabilities") or []) if isinstance(c, dict)]
    pool_rows = pool_rows_for(line, pools)
    if not pool_rows:
        return list(own)
    equip = equippable(line)
    taken = {(c.get("cap"), c.get("evidence")) for c in own}
    excepts = {(x.get("cap"), x.get("evidence"))
               for x in (entry.get("except") or []) if isinstance(x, dict)}
    out = list(own)
    for r in pool_rows:
        key = (r.get("cap"), r.get("evidence"))
        if key in taken or key in excepts:
            continue                      # weapon override / deliberate non-take
        ev = r.get("evidence")
        if ev in NON_SPELL_EVIDENCE or ev in equip:
            out.append(r)
    return out


GEAR_POOL_DIR = os.path.join(HERE, "sheets", "gear", "pools")


def load_gear_pools(pool_dir=GEAR_POOL_DIR):
    """{tree: [row, ...]} from sheets/gear/pools/*.yaml.

    Each pool file is one document: {tree: str, capabilities: [rows]}. The
    tree is the item-key prefix the pool applies to (HEAD_PLATE,
    ARMOR_CLOTH, SHOES_LEATHER ...): the slot and the armor class."""
    pools = {}
    for path in sorted(glob.glob(os.path.join(pool_dir, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        tree = doc.get("tree")
        rows = [r for r in (doc.get("capabilities") or [])
                if isinstance(r, dict) and r.get("cap")]
        if tree and rows:
            pools.setdefault(tree, []).extend(rows)
    return pools


def gear_tree(key):
    """The pool tree of a gear key: its first two segments (HEAD_PLATE_SET2
    -> HEAD_PLATE). Unique and tiered keys follow the same shape."""
    parts = str(key).split("_")
    return "_".join(parts[:2]) if len(parts) >= 3 else None


def compose_gear(entry, menu, pools):
    """A gear item's full capability row list: own rows + the tree pool rows
    whose evidence spell sits on the item's dumps menu.

    entry: one gear sheet document ({gear, capabilities, except, ...}).
    menu:  gear_spells.json[gear] (None for an item the dumps do not carry
           — pool rows then cannot be menu-tested and are not applied).
    pools: load_gear_pools() result.
    """
    own = [c for c in (entry.get("capabilities") or []) if isinstance(c, dict)]
    pool_rows = pools.get(gear_tree(entry.get("gear")), []) if menu is not None else []
    if not pool_rows:
        return list(own)
    equip = (set((menu or {}).get("actives") or []) | set((menu or {}).get("passives") or [])
             | set((menu or {}).get("consume") or []))
    taken = {(c.get("cap"), c.get("evidence")) for c in own}
    excepts = {(x.get("cap"), x.get("evidence"))
               for x in (entry.get("except") or []) if isinstance(x, dict)}
    out = list(own)
    for r in pool_rows:
        key = (r.get("cap"), r.get("evidence"))
        if key in taken or key in excepts:
            continue                      # item override / deliberate non-take
        if r.get("evidence") in equip:
            out.append(r)
    return out


def load_weapon_lines(out_dir=os.path.join(HERE, "out")):
    with open(os.path.join(out_dir, "weapon_lines.json"), encoding="utf-8") as f:
        return json.load(f)
