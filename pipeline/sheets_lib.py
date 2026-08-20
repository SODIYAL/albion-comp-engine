"""Shared sheet composition — weapon entries + tree-level spell pools.

Restructure 2026-08-20 (spell-level curation, step 2 of the geometric-AoE
plan): the Q/W/passive spells a weapon tree shares are curated ONCE in
sheets/pools/<subcategory>.yaml instead of being copy-pasted into every
line-mate's sheet (the copy-paste drift this kills: 16 same-spell-
different-score groups in the magnitude audit). The E spell — the actual
differentiator — stays on the weapon entry.

POOL SEMANTICS
  - A pool row {cap, score, evidence} applies to every weapon of the pool's
    subcategory (weapon_lines.json) that can EQUIP the evidence spell in any
    slot. Evidence WEAPON_STATS (base item stats, no spell) applies tree-wide.
  - A weapon entry may list `except: [{cap, evidence}, ...]` — deliberate
    non-takes. Previously "this weapon doesn't play that spell that way" was
    indistinguishable from an oversight; now it is explicit and greppable.
  - A weapon's own row with the same (cap, evidence) pair OVERRIDES the pool
    row — this is where score drift lives until the expert adjudicates it
    (magnitude audit RULE queue), visible instead of scattered.

Composed row order: the weapon's own rows first (sheet order), then
applicable pool rows in pool-file order. Measured 2026-08-20: no weapon has
two evidence rows for one capability, so order carries no semantics.

Every consumer of per-weapon capability rows goes through compose() —
build_dataset, evidence_lint, build_magnitude_review, build_interactions —
so the pool layer cannot half-apply.
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


def compose(entry, line, pools):
    """The weapon's full capability row list: own rows + applicable pool rows.

    entry: one sheet document ({weapon, capabilities, except, ...}).
    line:  weapon_lines.json[weapon] (None for unknown weapons — pool rows
           then cannot be equippability-tested and are not applied).
    pools: load_pools() result.
    """
    own = [c for c in (entry.get("capabilities") or []) if isinstance(c, dict)]
    sub = (line or {}).get("subcategory")
    pool_rows = pools.get(sub, []) if line is not None else []
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


def load_weapon_lines(out_dir=os.path.join(HERE, "out")):
    with open(os.path.join(out_dir, "weapon_lines.json"), encoding="utf-8") as f:
        return json.load(f)
