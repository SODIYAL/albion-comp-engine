#!/usr/bin/env python3
"""
Validation-asymmetry probe (dressed validation Phase 1A/2, 2026-08-27).

Report-only. Measures how recommendations change between the three
incumbent-gear regimes the validation harness can run:

  legacy   naked incumbents, DRESSED candidates — what V3/V4 historically
           measured (the asymmetric hybrid; golden T30c's honesty rider
           documents the per-candidate effect)
  v3w      symmetric weapon-only (set_dressing(False), no gears)
  dressed  incumbents in real/doctrine kits, candidates dressed — the
           production regime (the page passes LOADOUT gear to every call)

Two case families:
  A. The seed-20260812 V3 blind-form parties (regenerated exactly), each
     dressed by doctrine (kit_variants v0) for the dressed regime.
  B. Every published-comp leave-one-out ROLE slot (V4's role metric),
     dressed from the comp's own recorded gear (builds_index join) —
     flags each slot whose role-level hit flips between regimes.

Output: pipeline/out/validation_asymmetry_probe.json (deterministic,
LF). Nothing here scores, tunes, or gates — evidence for the dressed
validation report and the tankiness/frontline finding.

Run:  py -3 pipeline/audit_validation_asymmetry.py
"""
import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from engine import Engine  # noqa: E402
import gear_join  # noqa: E402

SEED, N_CASES, SIZE = 20260812, 12, 7
TOP_N = 3
V4_CONTENT_MAP = {"large_scale_zvz": "territory_defense"}
OUT = os.path.join(HERE, "out", "validation_asymmetry_probe.json")


def seed_parties(e):
    """Regenerate the V3 blind-form parties byte-for-byte (the same RNG
    walk tier2_blindtest.generate performs)."""
    pool = sorted(e.weapons)
    rng = random.Random(SEED)
    parties = []
    while len(parties) < N_CASES:
        k = rng.randint(2, max(2, SIZE - 1))
        p = rng.sample(pool, k)
        if p not in parties:
            parties.append(p)
    return parties


def top3(e, party, gears):
    return [r["weapon"] for r in e.recommend(party, TOP_N, gears=gears)]


def probe_v3(out):
    e = Engine(size=SIZE)
    cases = []
    for i, party in enumerate(seed_parties(e), 1):
        legacy = top3(e, party, None)
        e.set_dressing(False)
        v3w = top3(e, party, None)
        e.set_dressing(True)
        doc = gear_join.doctrine_gears(e, party)
        dressed = top3(e, party, doc)
        cases.append({
            "case": i, "party": party,
            "top3": {"legacy": legacy, "v3w": v3w, "dressed": dressed},
            "legacy_vs_v3w_differs": legacy != v3w,
            "legacy_vs_dressed_differs": legacy != dressed,
        })
    out["v3_seed_cases"] = cases
    out["v3_summary"] = {
        "n": len(cases),
        "legacy_vs_v3w_differs": sum(c["legacy_vs_v3w_differs"] for c in cases),
        "legacy_vs_dressed_differs": sum(c["legacy_vs_dressed_differs"]
                                         for c in cases),
    }


def probe_v4_roles(out):
    try:
        import yaml
    except ImportError:
        sys.exit("pip install pyyaml")
    probe = Engine()
    rs = probe.scoring.get("role_sets", {})
    pools = {"healer": set(rs.get("healers", [])),
             "tank": set(rs.get("frontline", [])),
             "main_tank": set(rs.get("frontline", []))}
    flat = gear_join.load_builds_flat(ROOT)
    rows, tally = [], {"slots": 0, "flip_hit_to_miss": 0, "flip_miss_to_hit": 0}
    for path in sorted(glob.glob(os.path.join(ROOT, "data",
                                              "published_comps", "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if not (isinstance(doc, dict) and doc.get("kind") == "published_comp"):
            continue
        content = V4_CONTENT_MAP.get(doc.get("content"), doc.get("content"))
        if content not in probe.data["templates"]:
            continue
        style = doc.get("style", "balanced")
        for party in doc.get("parties", []):
            all_slots = party.get("slots", [])
            slots = [(j, s) for j, s in enumerate(all_slots)
                     if s.get("weapons") and s.get("role") != "battlemount"]
            members = [s["weapons"][0] for _, s in slots]
            e = Engine(content=content, size=len(members), style=style)
            actual = []
            for j, _s in slots:
                bid = f"{doc.get('id','?')}:{party.get('name','?')}:{j}"
                gl, _res, _rec = gear_join.slot_gears(flat.get(bid), e.gear)
                actual.append(gl)
            for i, (_j, slot) in enumerate(slots):
                pool = pools.get(slot.get("role"))
                if not pool:
                    continue
                rest = members[:i] + members[i + 1:]
                naked = top3(e, rest, None)
                dressed = top3(e, rest, actual[:i] + actual[i + 1:])
                nh = any(w in pool for w in naked)
                dh = any(w in pool for w in dressed)
                tally["slots"] += 1
                tally["flip_hit_to_miss"] += nh and not dh
                tally["flip_miss_to_hit"] += dh and not nh
                if nh != dh:
                    rows.append({
                        "comp": doc.get("id", "?"),
                        "party": party.get("name", "?"),
                        "dropped": slot.get("raw", "?"),
                        "role": slot.get("role"),
                        "naked_hit": nh, "dressed_hit": dh,
                        "naked_top3": naked, "dressed_top3": dressed,
                    })
    out["v4_role_flips"] = rows
    out["v4_role_summary"] = tally


def main():
    out = {"kind": "validation_asymmetry_probe", "seed": SEED}
    probe_v3(out)
    probe_v4_roles(out)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    s3, s4 = out["v3_summary"], out["v4_role_summary"]
    print(f"V3 seed cases: {s3['legacy_vs_dressed_differs']}/{s3['n']} top-3 "
          f"change when incumbents dress "
          f"({s3['legacy_vs_v3w_differs']}/{s3['n']} vs symmetric naked)")
    print(f"V4 role slots: {s4['flip_hit_to_miss']}/{s4['slots']} role hits "
          f"LOST when incumbents dress, {s4['flip_miss_to_hit']} gained")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
