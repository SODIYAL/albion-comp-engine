#!/usr/bin/env python3
"""
Shared gear-evidence join helpers (dressed validation, 2026-08-27).

Published-comp slots carry the gear their sources actually recorded
(data/published_comps: 201/201 slots have a gear: block), and
pipeline/out/builds_index.json holds the normalized per-slot records.
These helpers reconstruct per-member ACTUAL kits from that evidence so
the validation harnesses (tests/tier2_blindtest.py) and the dressed
audits (pipeline/audit_*.py) can price incumbent parties in real gear
instead of pretending everyone is naked.

Join key: build_id == f"{comp_id}:{party_name}:{slot_index}" where
slot_index enumerates the party's FULL slots list — battlemount and
weaponless slots included — mirroring build_builds.py record ids.

Normalization mirrors build_dataset._normalize_gear_id (conservative:
exact catalog key, else a UNIQUE T4..T8_ tier prefix away; anything
else stays unknown — never guessed). Unresolved pieces are COUNTED and
reported by callers, never silently doctrine-filled: an uncurated or
unmatched piece contributes nothing and says so.

Evidence-layer helpers only — nothing here is a scoring input beyond
handing the engine's own comp_score/recommend the gears parameter it
already accepts.
"""
import json
import os

SLOT_ORDER = ("head", "armor", "shoes", "cape", "offhand", "potion", "food")


def normalize_gear_id(v, gear):
    """Conservative raw-id -> curated-catalog-id (mirrors
    build_dataset._normalize_gear_id): exact, else a unique tier prefix
    away. Anything else stays unknown (never guessed)."""
    v = (v or "").split("@")[0].strip()
    if not v:
        return None
    if v in gear:
        return v
    cands = {k for k in gear
             for n in (4, 5, 6, 7, 8) if k == f"T{n}_{v}"}
    return cands.pop() if len(cands) == 1 else None


def load_builds_flat(root):
    """builds_index.json flattened to {build_id: record}. A build_id can
    appear under several contents (content_covers fan-out); the record is
    identical — first one wins deterministically (sorted content walk)."""
    path = os.path.join(root, "pipeline", "out", "builds_index.json")
    with open(path, encoding="utf-8") as f:
        idx = json.load(f)
    flat = {}
    for content in sorted(idx.get("by_content", {})):
        for weapon in sorted(idx["by_content"][content]):
            for rec in idx["by_content"][content][weapon]:
                flat.setdefault(rec["build_id"], rec)
    return flat


def slot_gears(rec, gear_catalog):
    """One slot record -> (gear_list_or_None, resolved, recorded).

    Merges the record's un-matched `raw` text under its catalog-matched
    `gear` ids (the same precedence derive_kit_doctrine uses), normalizes
    each piece against the CURATED catalog, and returns the resolved kit
    in fixed slot order. `recorded` counts slots the source filled at
    all; `resolved` counts pieces that normalized into the curated
    catalog (the only ones that can contribute supply). None when the
    record resolves nothing — an honest naked member, not a guess."""
    if not rec:
        return None, 0, 0
    merged = dict(rec.get("raw") or {})
    merged.update({k: v for k, v in (rec.get("gear") or {}).items() if v})
    out, resolved, recorded = [], 0, 0
    for slot in SLOT_ORDER:
        v = merged.get(slot)
        if not v:
            continue
        recorded += 1
        gid = normalize_gear_id(v, gear_catalog)
        if gid is not None:
            out.append(gid)
            resolved += 1
    return (out or None), resolved, recorded


def doctrine_gears(engine, party):
    """Per-member doctrine kits (kit_variants v0) — the engine's own
    inferred dressing for members with no recorded gear. None where the
    weapon has no doctrine kit (dressed == naked)."""
    return [dict(engine.kit_variants(w)).get("v0") for w in party]
