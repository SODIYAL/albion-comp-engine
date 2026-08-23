#!/usr/bin/env python3
"""
Build the builds index — the generated, validated view of the evidence layer
(changeschapter2.md §C-§F).

    data/published_comps/*.yaml     caller comps (verbatim slots + provenance)
    data/published_builds/*.yaml    adapter imports (MetaBattle …), candidate
    data/armory_imports/*.yaml      manual official-Armory imports
    data/canonical_builds/*.yaml    manual canonical pins (optional)
    out/weapon_lines.json           game facts (pinned snapshot)
    out/spell_index.json
    out/gear_lines.json
        │
        ▼
    out/builds_index.json           {by_content: {content: {weapon: [variant]}}}
                                    ordered by §F selection criteria, canonical
                                    defaults flagged with their basis
    out/builds_validation.json      the validation_result record: problems,
                                    quarantined fields, unresolved mappings,
                                    promotion decisions

Variants keep the legacy dashboard fields (q/w/p 1-based, gear, caller, role)
and add full provenance: source, patch, approval, freshness, confidence by
dimension, structured alternatives, explicit unknowns.

Popularity/observation data NEVER enters this index — it has its own files
and its own display, and nothing here feeds Forge scoring (§E/§F: gear and
imported builds stay non-scoring until a validated gear-capability model
exists).

Usage:  py -3 pipeline/build_builds.py
"""
import glob
import json
import os
import re
import sys


def _norm_label(s):
    """Forgiving label match: 'Crystal League 20v20' == crystalleague20v20."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")
DATA = os.path.join(ROOT, "data")

sys.path.insert(0, HERE)
import builds_lib as bl  # noqa: E402

# A comp/build tagged with a broader-than-template content is offered under
# the templates it covers, ALWAYS marked as a fallback (§F: "If falling back
# to a broader context, show that fallback explicitly"). The mapping states
# which template contents each broad tag covers — from the sources' own words
# ("castle, territory, mass alliance roam"; MetaBattle "ZvZ").
CONTENT_COVERS = {
    "large_scale_zvz": ["castle", "territory_defense", "faction_war"],
    "zvz": ["castle", "territory_defense", "faction_war"],
    # Size-matched extensions (owner 2026-08-21): a 7-man fight comp is
    # evidence for the 7-man templates; 20-man roam/organized comps are
    # evidence for the 20-size templates. Displayed builds always carry
    # fallback_from, so the borrow stays visible (§F).
    "zvz_7man": ["castle_outpost", "roads"],
    "zvz_20man": ["blackzone_roam", "territory_defense"],
    "zvz_20v20": ["territory_defense", "faction_war"],
}


def load_game_facts():
    def _load(name):
        with open(os.path.join(OUT, name), encoding="utf-8") as f:
            return json.load(f)
    return _load("weapon_lines.json"), _load("spell_index.json"), \
        _load("gear_lines.json")


def load_docs(subdir, kind):
    docs = []
    for path in sorted(glob.glob(os.path.join(DATA, subdir, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if not isinstance(doc, dict):
            continue
        if doc.get("example"):
            continue                     # format examples never become data
        doc["_path"] = os.path.relpath(path, ROOT).replace("\\", "/")
        if doc.get("kind") != kind:
            doc["_kind_problem"] = (
                f"{doc['_path']}: kind {doc.get('kind')!r} != {kind!r}")
        docs.append(doc)
    return docs


def comp_records(comp, weapon_lines, spell_index, gear_lines):
    """Normalized build records for every weapon slot of a published comp."""
    records = []
    for party in comp.get("parties", []) or []:
        for i, slot in enumerate(party.get("slots", []) or []):
            slot = dict(slot)
            slot["_slot_id"] = f"{party.get('name', 'party')}:{i}"
            rec = bl.normalize_slot(slot, comp, weapon_lines, gear_lines,
                                    spell_index)
            if rec:
                rec["skills_raw"] = slot.get("skills")
                records.append(rec)
    return records


def import_records(doc, weapon_lines, spell_index, gear_lines, problems):
    """Records from an adapter batch (data/published_builds/*.yaml). The
    adapter already resolved names -> UniqueNames; re-validate equippability
    here so a stale import fails closed instead of shipping (§C)."""
    out = []
    for b in doc.get("builds", []) or []:
        rec = dict(b)
        rec.setdefault("source", doc.get("source"))
        rec.setdefault("patch", doc.get("patch"))
        rec.setdefault("snapshot_commit", doc.get("snapshot_commit"))
        rec.setdefault("approval", {"status": rec.get("status", "candidate")})
        w = rec.get("weapon")
        if w and w not in weapon_lines:
            problems.append(f"{rec.get('build_id','?')}: weapon {w} not in "
                            "game data")
            rec["status"] = "quarantined"
        src_kind = (rec.get("source") or {}).get("kind")
        ps = rec.get("party_size") or {}
        if src_kind in bl.ONE_V_ONE_KINDS and \
                (ps.get("max") or 0) > bl.ONE_V_ONE_MAX_SIZE:
            problems.append(
                f"{rec.get('build_id','?')}: {src_kind} evidence is "
                f"solo/1v1-only — party_size.max {ps.get('max')} > "
                f"{bl.ONE_V_ONE_MAX_SIZE}")
            rec["status"] = "quarantined"
        pools = ((weapon_lines.get(w) or {}).get("spells") or {})
        for slot, sid in (rec.get("spells") or {}).items():
            if sid and sid not in (pools.get(slot) or []):
                problems.append(
                    f"{rec.get('build_id','?')}: spell {sid} is not "
                    f"equippable in {w}.{slot} at the attributed snapshot")
                rec["status"] = "quarantined"
        out.append(rec)
    return out


def variant_of(rec):
    """The dashboard-embed variant: legacy prefill fields + provenance."""
    picks = bl.parse_skills(rec.get("skills_raw") or rec.get("spells_raw"))
    v = {
        "build_id": rec.get("build_id"),
        "caller": (rec.get("source") or {}).get("author") or
                  (rec.get("source") or {}).get("kind"),
        "role": rec.get("role_raw") or rec.get("role") or "",
        "spells": rec.get("spells"),
        "gear": {k: v for k, v in (rec.get("gear") or {}).items() if v},
        "raw": rec.get("gear_raw") or {},
        "alternatives": {
            "weapons": rec.get("weapon_alternatives") or [],
            "gear": rec.get("gear_alternatives") or {},
        },
        "unknowns": rec.get("unknowns") or [],
        "quarantined_fields": rec.get("quarantined_fields") or [],
        "status": rec.get("status"),
        "source": {k: (rec.get("source") or {}).get(k)
                   for k in ("kind", "family", "author", "url", "record")},
        "published": rec.get("published"),
        "patch": rec.get("patch"),
        "party_size": rec.get("party_size"),
        "style": rec.get("style"),
        "approval": (rec.get("approval") or {}).get("status"),
        "approval_basis": (rec.get("approval") or {}).get("basis"),
        "confidence": rec.get("confidence"),
        "note": rec.get("note"),
    }
    if picks:
        v.update(picks)                  # legacy 1-based q/w/p prefill fields
    return v


def main():
    weapon_lines, spell_index, gear_lines = load_game_facts()
    problems, quarantined = [], []

    comps = load_docs("published_comps", "published_comp")
    imports = load_docs("published_builds", "published_build_batch")
    armory = load_docs("armory_imports", "armory_import")
    pins = load_docs("canonical_builds", "canonical_build")

    records = []
    for comp in comps:
        problems += [p for p in (comp.pop("_kind_problem", None),) if p]
        problems += bl.validate_comp_doc(comp, weapon_lines)
        records += comp_records(comp, weapon_lines, spell_index, gear_lines)
    for doc in imports:
        problems += [p for p in (doc.pop("_kind_problem", None),) if p]
        records += import_records(doc, weapon_lines, spell_index, gear_lines,
                                  problems)
    # Armory activity labels must be the game's own (out/armory_activities
    # .json, parse_armory.py) — a label the Armory does not have is a
    # mis-transcription, not a new category.
    armory_tax = set()
    tax_path = os.path.join(OUT, "armory_activities.json")
    if os.path.exists(tax_path):
        with open(tax_path, encoding="utf-8") as f:
            for a in json.load(f).get("activities", []):
                armory_tax.add(_norm_label(a.get("uniquename") or ""))
                armory_tax.add(_norm_label(a.get("name") or ""))
        armory_tax.discard("")
    for doc in armory:
        problems += [p for p in (doc.pop("_kind_problem", None),) if p]
        problems += bl.validate_comp_doc(doc, weapon_lines) \
            if doc.get("parties") else []
        if armory_tax:
            for b in (doc.get("builds") or []):
                act = b.get("activity")
                if act and _norm_label(act) not in armory_tax:
                    problems.append(
                        f"{doc.get('id', '?')}/{b.get('build_id', '?')}: "
                        f"activity {act!r} is not an official Armory "
                        "activity (see out/armory_activities.json)")
        records += import_records(doc, weapon_lines, spell_index, gear_lines,
                                  problems) if doc.get("builds") else []

    for rec in records:
        if rec.get("quarantined_fields"):
            quarantined.append({"build_id": rec["build_id"],
                                "fields": rec["quarantined_fields"]})

    # manual canonical pins win the ordering for their exact context
    pinned = {}
    for pin in pins:
        key = (pin.get("weapon"), pin.get("content"))
        pinned[key] = pin

    # group by (content, weapon), order by §F criteria, flag canonicals
    by_content = {}
    for rec in records:
        ct, w = rec.get("content"), rec.get("weapon")
        if not ct or not w:
            continue
        by_content.setdefault(ct, {}).setdefault(w, []).append(rec)

    index = {}
    promotions = []
    for ct, by_weapon in sorted(by_content.items()):
        for w, group in sorted(by_weapon.items()):
            ordered = bl.selection_order(group)
            pin = pinned.get((w, ct))
            if pin and pin.get("build_id"):
                ordered.sort(key=lambda r: r.get("build_id") != pin["build_id"])
            ok, basis = bl.canonical_eligible(ordered)
            variants = [variant_of(r) for r in ordered]
            # the default is the first PROMOTABLE record — a quarantined
            # record is never a default, no matter its comp-level approval
            # (review 2026-08-19: the Enigmatic p5 build shipped as
            # canonical through exactly this gap). A pin cannot rescue a
            # quarantined record either.
            first_ok = next((i for i, r in enumerate(ordered)
                             if bl.promotable(r)), None)
            if ok and first_ok is not None:
                variants[first_ok]["canonical"] = True
                variants[first_ok]["canonical_basis"] = (
                    "manual canonical pin"
                    if pin and ordered[first_ok].get("build_id") ==
                    pin.get("build_id") else basis)
                promotions.append({"weapon": w, "content": ct,
                                   "build_id": variants[first_ok]["build_id"],
                                   "basis": variants[first_ok]["canonical_basis"]})
            else:
                promotions.append({"weapon": w, "content": ct,
                                   "build_id": None, "basis": basis})
            index.setdefault(ct, {})[w] = variants

    # Content fallbacks are NOT baked in as copies: the index stores each
    # build once under its home content, plus the content_covers map. The
    # dashboard derives fallback offerings at runtime and labels them
    # explicitly (§F) — no silent merging, no payload duplication.
    # Evidence gate for composition exclusions (§F): an excluded weapon that
    # gains a CURRENT approved canonical large-group build is surfaced so the
    # owner can lift the entry — eligibility follows the evidence, the code
    # never hardcodes the ban's fate.
    comp_path = os.path.join(HERE, "templates", "composition.yaml")
    gate_notes = []
    if os.path.exists(comp_path):
        with open(comp_path, encoding="utf-8") as f:
            comp_cfg = yaml.safe_load(f) or {}
        for excl in ((comp_cfg.get("viability") or {}).get("exclusions") or []):
            min_size = excl.get("min_size", 10)
            for w in excl.get("weapons", []):
                for p in promotions:
                    if p["weapon"] != w or not p["build_id"]:
                        continue
                    rec = next((r for r in records
                                if r.get("build_id") == p["build_id"]), {})
                    ps = rec.get("party_size") or {}
                    if (ps.get("min") or 0) >= min_size:
                        gate_notes.append(
                            f"exclusion gate: {w} now has an approved "
                            f"canonical large-group build "
                            f"({p['build_id']}) — review the composition "
                            "exclusion")
    counts = {
        "records": len(records),
        "approved": sum(1 for r in records
                        if (r.get("approval") or {}).get("status") == "approved"),
        "candidate": sum(1 for r in records
                         if (r.get("approval") or {}).get("status") == "candidate"),
        "quarantined_records": sum(1 for r in records
                                   if r.get("status") == "quarantined"),
        "quarantined_fields": sum(len(q["fields"]) for q in quarantined),
        "canonical_defaults": sum(1 for p in promotions if p["build_id"]),
    }
    with open(os.path.join(OUT, "builds_index.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump({"_meta": {"counts": counts,
                             "content_covers": CONTENT_COVERS},
                   "by_content": {k: dict(sorted(v.items()))
                                  for k, v in sorted(index.items())}},
                  f, indent=1, sort_keys=True)
    with open(os.path.join(OUT, "builds_validation.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"kind": "validation_result",
                   "problems": sorted(problems),
                   "quarantined": sorted(quarantined,
                                         key=lambda q: q["build_id"]),
                   "promotions": sorted(promotions,
                                        key=lambda p: (p["content"],
                                                       p["weapon"])),
                   "exclusion_gate": sorted(gate_notes),
                   "counts": counts},
                  f, indent=1, sort_keys=True)

    print(f"builds index: {counts['records']} records "
          f"({counts['approved']} approved, {counts['candidate']} candidate, "
          f"{counts['quarantined_records']} quarantined records, "
          f"{counts['quarantined_fields']} quarantined fields), "
          f"{counts['canonical_defaults']} canonical defaults")
    for q in quarantined:
        print(f"  QUARANTINED {q['build_id']}: {'; '.join(q['fields'])}")
    if problems:
        print(f"  {len(problems)} validation problem(s):")
        for p in sorted(problems):
            print(f"   ERROR {p}")
    print("wrote out/builds_index.json, out/builds_validation.json")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
