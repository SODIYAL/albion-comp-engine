#!/usr/bin/env python3
"""
Compile + validate the PvP interaction records ("new prompt" spec §1-§4).

    pipeline/interactions.yaml    curated, spell-keyed interaction records
    out/spell_index.json          pinned-snapshot spell facts (descriptions)
    out/weapon_lines.json         equippability
    sheets/*.yaml                 capability evidence (for nonstacking_caps)
        │
        ▼
    out/interactions.json         {spells: {SID: record}} — embedded in the
                                  dataset like item_stats; the engine reads
                                  nonstacking_caps, the dashboard the badges

Structural pre-pass: the snapshot's own spell descriptions state some facts
outright ("cannot be reflected", charge language). Those sentences are
extracted as structural evidence; a curated `verified` non-reflect claim on a
spell whose description carries no such sentence must cite its source
explicitly. Spells with structural reflect statements but NO curated entry
are listed in `_meta.structural_unclaimed` — the curation backlog, visible
instead of silently missing.

Scoring coupling: ONLY `nonstacking_caps` on a `confidence: verified` entry
ever reaches the engines (party supply counts that spell's listed caps once
across members equipping it). unknown/likely/community_reported never change
a score (§12).

Usage:  py -3 pipeline/build_interactions.py
"""
import glob
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SRC = os.path.join(HERE, "interactions.yaml")
DEST = os.path.join(OUT, "interactions.json")

sys.path.insert(0, HERE)
from provenance import record_derived, snapshot_commit  # noqa: E402

ADAPTER = "build_interactions"
ADAPTER_VERSION = "1"

DUP_ENUM = {"full", "damage_only", "refresh", "override", "shared_stack",
            "unique_effect_only", "partial", "does_not_stack", "unknown"}
REFLECT_ENUM = {"reflectable", "non_reflectable", "partial",
                "not_applicable", "unknown"}
PURGE_ENUM = {"purgeable", "unpurgeable", "partial", "not_applicable",
              "unknown"}
CLEANSE_ENUM = {"cleanseable", "uncleanseable", "partial", "not_applicable",
                "unknown"}
KIND_ENUM = {"damage", "dot", "ground_dot", "buff", "debuff", "cc"}
CC_TYPES = {"stun", "root", "silence", "slow", "fear", "knockback", "knockup",
            "pull", "displacement", "sleep", "freeze"}
CONFIDENCE = {"verified", "likely", "community_reported", "unknown"}

NON_REFLECT_RE = re.compile(r"[^.\n]*(?:cannot|can't|can not) be "
                            r"reflected[^.\n]*\.?", re.I)


def rollup_reflect(components):
    """Spell-level reflect from components: uniform known status -> that;
    nothing known -> unknown; anything mixed (including known + unknown) ->
    partial — 'parts of this ability behave differently or are not uniformly
    verified' (spec §3)."""
    seen = {c.get("reflect", "unknown") for c in components
            if c.get("reflect", "unknown") != "not_applicable"}
    if not seen:
        return "not_applicable"
    if len(seen) == 1:
        return next(iter(seen))
    if seen == {"unknown"}:
        return "unknown"
    return "partial"


def main():
    with open(os.path.join(OUT, "spell_index.json"), encoding="utf-8") as f:
        spell_index = json.load(f)
    with open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8") as f:
        weapon_lines = json.load(f)
    # capability evidence per spell (curated sheets): which caps a spell
    # grounds — the legal domain of nonstacking_caps
    caps_by_spell = {}
    for path in glob.glob(os.path.join(HERE, "sheets", "*.yaml")):
        for entry in (yaml.safe_load(open(path, encoding="utf-8")) or []):
            for c in entry.get("capabilities", []):
                if isinstance(c, dict) and c.get("evidence") and c.get("cap"):
                    caps_by_spell.setdefault(c["evidence"], set()).add(c["cap"])

    equippable_on = {}
    for wk, line in weapon_lines.items():
        for pool in (line.get("spells") or {}).values():
            for sid in pool:
                equippable_on.setdefault(sid, []).append(wk)

    entries = yaml.safe_load(open(SRC, encoding="utf-8")) or []
    errors, spells = [], {}
    for e in entries:
        sid = e.get("spell")
        where = f"interactions[{sid}]"
        if not sid or sid not in spell_index:
            errors.append(f"{where}: unknown spell (not in spell_index)")
            continue
        weapons = sorted(equippable_on.get(sid, []))
        if not weapons:
            errors.append(f"{where}: spell is not equippable on any weapon")
        conf = e.get("confidence")
        if conf not in CONFIDENCE:
            errors.append(f"{where}: confidence {conf!r} not in {sorted(CONFIDENCE)}")
        if conf != "unknown" and not (e.get("source") or "").strip():
            errors.append(f"{where}: confidence {conf} requires a source")
        dup = e.get("duplicate", "unknown")
        if dup not in DUP_ENUM:
            errors.append(f"{where}: duplicate {dup!r} not in enum")
        comps = e.get("components") or []
        for c in comps:
            cw = f"{where}.{c.get('id', '?')}"
            if c.get("kind") not in KIND_ENUM:
                errors.append(f"{cw}: kind {c.get('kind')!r} not in {sorted(KIND_ENUM)}")
            for field, enum in (("reflect", REFLECT_ENUM), ("purge", PURGE_ENUM),
                                ("cleanse", CLEANSE_ENUM), ("duplicate", DUP_ENUM)):
                v = c.get(field)
                if v is not None and v not in enum:
                    errors.append(f"{cw}: {field} {v!r} not in enum")
            if c.get("kind") == "cc" and c.get("cc_type") not in CC_TYPES:
                errors.append(f"{cw}: cc_type {c.get('cc_type')!r} not in "
                              f"{sorted(CC_TYPES)}")

        # structural cross-check: a verified non-reflect claim either matches
        # a description statement or must say where it comes from
        desc = (spell_index[sid].get("description") or "")
        statements = [m.group(0).strip() for m in NON_REFLECT_RE.finditer(desc)]
        claims_nr = any(c.get("reflect") == "non_reflectable" for c in comps)
        if claims_nr and conf == "verified" and not statements \
                and "description" in (e.get("source") or "").lower():
            errors.append(
                f"{where}: verified non_reflectable cites the description, "
                "but the description carries no reflect statement")

        ns = e.get("nonstacking_caps") or []
        if ns:
            if conf != "verified":
                errors.append(f"{where}: nonstacking_caps requires "
                              f"confidence verified (is {conf}) — unknown "
                              "never changes a score")
            if not (e.get("scoring_note") or "").strip():
                errors.append(f"{where}: nonstacking_caps requires a "
                              "scoring_note explaining the count-once rule")
            legal = caps_by_spell.get(sid, set())
            for cap in ns:
                if cap not in legal:
                    errors.append(
                        f"{where}: nonstacking cap {cap!r} is not a curated "
                        f"capability grounded by {sid} (has: {sorted(legal)})")

        reflect = rollup_reflect(comps)
        badges = list(e.get("badges") or [])
        if reflect == "non_reflectable":
            badges.append("NON-REFLECTABLE")
        elif reflect == "partial":
            badges.append("PARTIAL REFLECT")
        for c in comps:
            if c.get("kind") == "cc" and c.get("cc_type"):
                b = c["cc_type"].upper()
                if b not in badges:
                    badges.append(b)
        badges.append(f"DUPLICATE:{str(dup).upper()}")

        spells[sid] = {
            "name": spell_index[sid].get("name"),
            "effect_name": e.get("effect_name"),
            "weapons": weapons,
            "duplicate": dup,
            "reflect": reflect,
            "components": comps,
            "cc_types": sorted({c["cc_type"] for c in comps
                                if c.get("kind") == "cc" and c.get("cc_type")}),
            "badges": badges,
            "nonstacking_caps": sorted(ns),
            "scoring_note": (e.get("scoring_note") or "").strip() or None,
            "confidence": conf,
            "source": (e.get("source") or "").strip(),
            "as_of": str(e.get("as_of") or ""),
            "verified_patch": str(e.get("verified_patch") or ""),
            "structural_reflect_statements": statements,
            "notes": (e.get("notes") or "").strip() or None,
        }

    # curation backlog: spells whose descriptions state reflect facts but
    # have no curated interaction record yet
    unclaimed = sorted(
        sid for sid, s in spell_index.items()
        if sid not in spells and NON_REFLECT_RE.search(s.get("description") or ""))

    payload = {
        "_meta": {
            "adapter": ADAPTER,
            "adapter_version": ADAPTER_VERSION,
            "source_commit": snapshot_commit(),
            "entries": len(spells),
            "verified": sum(1 for s in spells.values()
                            if s["confidence"] == "verified"),
            "with_nonstacking_caps": sum(1 for s in spells.values()
                                         if s["nonstacking_caps"]),
            "structural_unclaimed": unclaimed,
            "note": ("Spell-keyed PvP interaction records. Scoring reads ONLY "
                     "verified nonstacking_caps; everything else is display/"
                     "analysis. unknown is a stored answer, never a guess."),
        },
        "spells": dict(sorted(spells.items())),
    }
    with open(DEST, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
    record_derived("interactions.json", DEST, ADAPTER, ADAPTER_VERSION,
                   snapshot_commit() or "local-override",
                   ["spells.json (via spell_index)", "interactions.yaml"])

    print(f"interactions: {len(spells)} spells "
          f"({payload['_meta']['verified']} verified, "
          f"{payload['_meta']['with_nonstacking_caps']} with scoring caps), "
          f"{len(unclaimed)} spells with structural reflect facts awaiting "
          "curation")
    for err in errors:
        print(f"  ERROR {err}")
    print(f"wrote {os.path.relpath(DEST, os.path.join(HERE, os.pardir))}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
