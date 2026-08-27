#!/usr/bin/env python3
"""
Tankiness / frontline-floor adversarial audit (Phase 4, 2026-08-27).
REPORT-ONLY — feeds docs/superpowers/findings/ and the owner ruling on
whether ordinary worn armor may satisfy a structural frontline demand.

Three realistic dressed parties at castle_outpost size 7 (tankiness
hard floor armed at 5+, floor 1.7u, target 3.5 scaled):

  A  no genuine frontline weapon (healer, 2x ranged DPS, melee DPS,
     2x support, DPS) — every member in ordinary DOCTRINE gear.
     Domain expectation: the party still lacks a real frontline.
  B  the same party with one member replaced by a genuine engage tank.
     Domain expectation: the frontline requirement materially improves.
  C  party A with every member in an explicit full-plate defensive kit
     (deliberately off-doctrine — the question is whether PERSONAL
     durability can impersonate frontline structure).
     Domain expectation: personal durability != frontline.

Weapon selection is programmatic and fail-closed: case A/C members are
verified to carry NO tank seat in their role menus; case B's tank is
verified to carry one. Measures per case: tankiness supply and floor
state naked vs dressed, floor penalty, weakness diagnosis, whether a
frontline weapon appears in the dressed top-3, and the descriptive
role_advisory no-engage-tank flag.

Run:  py -3 pipeline/audit_frontline_floor.py
Out:  pipeline/out/frontline_floor_audit.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from engine import Engine  # noqa: E402
import gear_join  # noqa: E402

OUT = os.path.join(HERE, "out", "frontline_floor_audit.json")
TANK_SEATS = {"engage_tank", "stopper_tank", "off_tank"}

# Case A roster — no tank-seat weapon anywhere (verified at runtime):
#   Hallowfall (main healer), Longbow + Permafrost (ranged DPS),
#   Carving Sword (melee DPS), Great Arcane + 1H Arcane (supports),
#   Greataxe (DPS)
CASE_A = ["MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW", "2H_ICECRYSTAL_UNDEAD",
          "2H_DUALSWORD", "2H_ARCANESTAFF_HELL", "MAIN_ARCANESTAFF",
          "2H_AXE"]
TANK_FOR_B = "2H_MACE"       # Heavy Mace, engage tank
REPLACE_AT = 5               # 1H Arcane support makes way for the tank
CONTENT, SIZE, STYLE = "castle_outpost", 7, "balanced"


def tank_seats_of(e, w):
    d = e.weapons[w]
    menus = list(d.get("role_menu") or []) + list(d.get("role_menu_secondary")
                                                  or [])
    return sorted(TANK_SEATS.intersection(menus))


def plate_kit(e):
    """A deterministic full defensive kit from the curated catalog: first
    plate piece per slot (sorted key order) + no potion/food."""
    kit = []
    for prefix in ("HEAD_PLATE_", "ARMOR_PLATE_", "SHOES_PLATE_"):
        ids = sorted(k for k in e.gear if k.startswith(prefix))
        if not ids:
            sys.exit(f"no curated {prefix}* piece — cannot build case C")
        kit.append(ids[0])
    return kit


def frontline_pool(e):
    pool = set(e.scoring.get("role_sets", {}).get("frontline", []))
    for w, d in e.weapons.items():
        if TANK_SEATS.intersection(d.get("role_menu") or []):
            pool.add(w)
    return pool


def measure(e, label, party, gears, front):
    cap = "tankiness"
    s_n = e.effective_supply(party)
    s_d = e.effective_supply(party, None, gears)
    have_n, have_d = s_n.get(cap, 0.0), s_d.get(cap, 0.0)
    fl = e.floors.get(cap) or {}
    weak_n = [g["cap"] for g in e.weaknesses(party, 3)]
    weak_d = [g["cap"] for g in e.weaknesses(party, 3, None, gears)]
    top_n = [r["weapon"] for r in e.recommend(party, 3)]
    top_d = [r["weapon"] for r in e.recommend(party, 3, gears=gears)]
    chests = {i: next((g for g in (gl or []) if g.startswith("ARMOR_")), None)
              for i, gl in enumerate(gears or [])}
    chests = {i: c for i, c in chests.items() if c}
    adv = e.role_advisory(party, chests)
    flags = [f.get("kind") or f.get("flag") or str(f) for f in
             (adv.get("flags") or adv.get("advisories") or [])] \
        if isinstance(adv, dict) else [str(a.get("kind", a)) for a in adv]
    return {
        "case": label, "party": party,
        "tankiness": {
            "target": round(e.target(cap), 4),
            "floor_units_eff": round(e._floors_eff.get(cap, 0.0), 4),
            "floor_armed_at_size": bool(fl) and e.size >= fl.get(
                "min_party_size", 10 ** 9),
            "naked": round(have_n, 4), "dressed": round(have_d, 4),
            "below_floor_naked": e.floor_armed(cap, have_n),
            "below_floor_dressed": e.floor_armed(cap, have_d),
            "floor_penalty_naked": round(e._floor_penalty(cap, have_n), 4),
            "floor_penalty_dressed": round(e._floor_penalty(cap, have_d), 4),
        },
        "weak_top3_naked": weak_n, "weak_top3_dressed": weak_d,
        "tankiness_in_weak_naked": cap in weak_n,
        "tankiness_in_weak_dressed": cap in weak_d,
        "recommend_top3_naked": top_n, "recommend_top3_dressed": top_d,
        "frontline_in_top3_naked": any(w in front for w in top_n),
        "frontline_in_top3_dressed": any(w in front for w in top_d),
        "role_advisory_flags": flags,
        "fitness_naked": round(e.fitness(party), 4),
        "fitness_dressed": round(e.fitness(party, None, gears), 4),
    }


def main():
    e = Engine(content=CONTENT, size=SIZE, style=STYLE)
    for w in CASE_A:
        seats = tank_seats_of(e, w)
        if seats:
            sys.exit(f"case A weapon {w} carries tank seats {seats} — "
                     "fix the roster (fail closed)")
    if not tank_seats_of(e, TANK_FOR_B):
        sys.exit(f"case B tank {TANK_FOR_B} carries no tank seat")

    front = frontline_pool(e)
    doc_a = gear_join.doctrine_gears(e, CASE_A)
    case_b = CASE_A[:REPLACE_AT] + [TANK_FOR_B] + CASE_A[REPLACE_AT + 1:]
    doc_b = gear_join.doctrine_gears(e, case_b)
    plate = plate_kit(e)
    gears_c = [plate for _ in CASE_A]

    out = {
        "kind": "frontline_floor_audit",
        "content": CONTENT, "size": SIZE, "style": STYLE,
        "tank_seats": sorted(TANK_SEATS),
        "case_c_kit": plate,
        "cases": [
            measure(e, "A_no_frontline_doctrine_gear", CASE_A, doc_a, front),
            measure(e, "B_one_real_tank", case_b, doc_b, front),
            measure(e, "C_dps_in_full_plate", CASE_A, gears_c, front),
        ],
    }
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)

    for c in out["cases"]:
        t = c["tankiness"]
        print(f"[{c['case']}]")
        print(f"  tankiness naked {t['naked']:.2f} -> dressed "
              f"{t['dressed']:.2f}  (target {t['target']}, floor "
              f"{t['floor_units_eff']}, armed={t['floor_armed_at_size']})")
        print(f"  below floor: naked={t['below_floor_naked']} "
              f"dressed={t['below_floor_dressed']}   penalty "
              f"{t['floor_penalty_naked']:.2f} -> "
              f"{t['floor_penalty_dressed']:.2f}")
        print(f"  tankiness in weakness top-3: naked="
              f"{c['tankiness_in_weak_naked']} dressed="
              f"{c['tankiness_in_weak_dressed']}")
        print(f"  frontline weapon in top-3: naked="
              f"{c['frontline_in_top3_naked']} dressed="
              f"{c['frontline_in_top3_dressed']}   advisory flags: "
              f"{c['role_advisory_flags'] or ['-']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
