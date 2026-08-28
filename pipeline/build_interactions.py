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
# interrupt facts the descriptions state outright: a channel that "can't be
# interrupted", or an ability that "interrupts the target's spell casting"
UNINTERRUPTIBLE_RE = re.compile(r"[^.\n]*\((?:cannot|can't|can not) be "
                                r"interrupted[^)\n]*\)[^.\n]*\.?", re.I)
INTERRUPTS_RE = re.compile(r"[^.\n]*interrupt(?:s|ing)\b[^.\n]*"
                           r"(?:cast|channel)[^.\n]*\.?", re.I)


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
    # tree-pool rows (sheets/pools/) — same spell->cap evidence, shared per line
    for path in glob.glob(os.path.join(HERE, "sheets", "pools", "*.yaml")):
        doc = yaml.safe_load(open(path, encoding="utf-8")) or {}
        for c in doc.get("capabilities", []):
            if isinstance(c, dict) and c.get("evidence") and c.get("cap"):
                caps_by_spell.setdefault(c["evidence"], set()).add(c["cap"])

    equippable_on = {}
    for wk, line in weapon_lines.items():
        for pool in (line.get("spells") or {}).values():
            for sid in pool:
                equippable_on.setdefault(sid, []).append(wk)
    # GEAR equippability (2026-08-28): this layer was weapon-only "until gear
    # records exist" — they do now (the first is Demon Armor's group reflect
    # aura), so a gear ability is a legal record subject. Kept as its own map
    # so the curation-backlog split below stays weapon-vs-gear.
    gear_equippable_on = {}
    with open(os.path.join(OUT, "gear_spells.json"), encoding="utf-8") as f:
        gear_spells_db = json.load(f)
    for gk, line in gear_spells_db.items():
        for kind in ("actives", "passives"):
            for sid in (line.get(kind) or []):
                gear_equippable_on.setdefault(sid, []).append(gk)

    entries = yaml.safe_load(open(SRC, encoding="utf-8")) or []
    errors, spells = [], {}
    for e in entries:
        sid = e.get("spell")
        where = f"interactions[{sid}]"
        if not sid or sid not in spell_index:
            errors.append(f"{where}: unknown spell (not in spell_index)")
            continue
        weapons = sorted(equippable_on.get(sid, []))
        gear_items = sorted(gear_equippable_on.get(sid, []))
        if not weapons and not gear_items:
            errors.append(f"{where}: spell is equippable on nothing "
                          "(no weapon line, no gear piece)")
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
        # interrupt facts (spec §4): derived from the description's own words;
        # a curated `interrupt:` block on the entry overrides/extends
        int_stmts = ([m.group(0).strip() for m in
                      UNINTERRUPTIBLE_RE.finditer(desc)]
                     + [m.group(0).strip() for m in
                        INTERRUPTS_RE.finditer(desc)])
        interrupt = dict(e.get("interrupt") or {})
        if "uninterruptible" not in interrupt:
            interrupt["uninterruptible"] = (
                True if any(UNINTERRUPTIBLE_RE.search(x) for x in int_stmts)
                else None)
        if "can_interrupt" not in interrupt:
            interrupt["can_interrupt"] = (
                True if any(INTERRUPTS_RE.search(x)
                            and not UNINTERRUPTIBLE_RE.search(x)
                            for x in int_stmts) else None)
        for field in ("uninterruptible", "can_interrupt"):
            if interrupt.get(field) not in (True, False, None):
                errors.append(f"{where}: interrupt.{field} must be true/"
                              f"false/null, got {interrupt[field]!r}")
        claims_nr = any(c.get("reflect") == "non_reflectable" for c in comps)
        if claims_nr and conf == "verified" and not statements \
                and "description" in (e.get("source") or "").lower():
            errors.append(
                f"{where}: verified non_reflectable cites the description, "
                "but the description carries no reflect statement")

        # SUPER-ADDITIVE DUPLICATES (2026-08-28) — the mirror of
        # nonstacking_caps, and held to the same bar. `self_cost_offset_min_
        # copies: N` says that once N members equip this spell, the item's
        # curated self_costs stop being charged, because the copies cover
        # each other (Demon Armor: each wearer stands in the others' aura).
        # It can only ever CANCEL A COST — it never adds supply — so a
        # duplicate still cannot out-earn two independent first copies.
        # Owner 2026-08-28: "duplicate is worth more only in special cases
        # like demon armor", so this is verified-only and must justify
        # itself in a scoring_note like every other scoring coupling.
        off = e.get("self_cost_offset_min_copies")
        if off is not None:
            if conf != "verified":
                errors.append(f"{where}: self_cost_offset_min_copies requires "
                              f"confidence verified (is {conf}) — unknown "
                              "never changes a score")
            if not isinstance(off, int) or off < 2:
                errors.append(f"{where}: self_cost_offset_min_copies must be an "
                              f"int >= 2 (is {off!r}) — offsetting at one copy "
                              "would just be deleting the cost")
            if not (e.get("scoring_note") or "").strip():
                errors.append(f"{where}: self_cost_offset_min_copies requires a "
                              "scoring_note explaining why copies cover "
                              "each other")

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
        if interrupt.get("uninterruptible"):
            badges.append("UNINTERRUPTIBLE")
        if interrupt.get("can_interrupt"):
            badges.append("INTERRUPT")
        badges.append(f"DUPLICATE:{str(dup).upper()}")

        spells[sid] = {
            "name": spell_index[sid].get("name"),
            "effect_name": e.get("effect_name"),
            "weapons": weapons,
            "gear_items": gear_items,
            "duplicate": dup,
            "reflect": reflect,
            "components": comps,
            "cc_types": sorted({c["cc_type"] for c in comps
                                if c.get("kind") == "cc" and c.get("cc_type")}),
            "badges": badges,
            "nonstacking_caps": sorted(ns),
            "self_cost_offset_min_copies": off,
            "scoring_note": (e.get("scoring_note") or "").strip() or None,
            "confidence": conf,
            "source": (e.get("source") or "").strip(),
            "as_of": str(e.get("as_of") or ""),
            "verified_patch": str(e.get("verified_patch") or ""),
            "structural_reflect_statements": statements,
            "interrupt": interrupt,
            "structural_interrupt_statements": int_stmts,
            "notes": (e.get("notes") or "").strip() or None,
        }

    # curation backlog: WEAPON-equippable spells whose descriptions state
    # reflect facts but have no curated interaction record yet. Gear spells
    # (in spell_index since parse_dumps v3) are out of the interaction
    # layer's scope until gear records exist — listed separately, never
    # silently dropped.
    unclaimed = sorted(
        sid for sid, s in spell_index.items()
        if sid not in spells and sid in equippable_on
        and NON_REFLECT_RE.search(s.get("description") or ""))
    gear_unclaimed = sorted(
        sid for sid, s in spell_index.items()
        if sid not in spells and sid not in equippable_on
        and NON_REFLECT_RE.search(s.get("description") or ""))

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
            "with_self_cost_offset": sum(
                1 for s in spells.values()
                if s.get("self_cost_offset_min_copies")),
            "structural_unclaimed": unclaimed,
            "structural_unclaimed_gear": gear_unclaimed,
            "note": ("Spell-keyed PvP interaction records. Scoring reads ONLY "
                     "verified nonstacking_caps; everything else is display/"
                     "analysis. unknown is a stored answer, never a guess."),
        },
        "spells": dict(sorted(spells.items())),
    }
    with open(DEST, "w", encoding="utf-8", newline="\n") as f:
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
