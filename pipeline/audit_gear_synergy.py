#!/usr/bin/env python3
"""
Gear-synergy semantics audit (Phase 5, 2026-08-27). REPORT-ONLY.

The scoring seam is deliberate (dressed-forge design): FITNESS prices
weapon + gear, SYNERGY prices weapons only (`synergy()` never receives
gears). Consequence: a gear-sourced capability — Hood of Tenacity's
heal cut, a Judicator wearer's engage — can never trigger
`heal_reduction x sustained_dps` or any other pair.

For each configured synergy pair this audit measures three minimal
constructions on a template where the pair is active:

  1. weapon A + weapon B          (both sides weapon-supplied)
  2. gear A  + weapon B           (side A ONLY from a worn item on an
                                   otherwise cap-neutral weapon)
  3. weapon A + gear B            (mirrored)

reporting actual engine synergy/comp_score and a LABELED HYPOTHETICAL:
what the pair would pay if gear participated, computed with the
engine's own published rule (sides capped at target, minus the largest
single member's joint supply J — here over DRESSED member vectors).
The hypothetical is analysis output only; no scoring path computes it.

A real-comp practice check runs the same hypothetical over the
published blap party in its recorded gear.

Run:  py -3 pipeline/audit_gear_synergy.py
Out:  pipeline/out/gear_synergy_audit.json
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

OUT = os.path.join(HERE, "out", "gear_synergy_audit.json")
CONTENT, SIZE, STYLE = "blackzone_roam", 10, "balanced"  # all pairs active


def best_weapon_for(e, cap, avoid=()):
    """Deterministic: the pool weapon with the highest default-combo supply
    of `cap` (ties by key), skipping `avoid`."""
    best = None
    for w in sorted(e.pool):
        if w in avoid:
            continue
        v = e.member_extra(w, None).get(cap, 0.0)
        if v > 0 and (best is None or v > best[1]):
            best = (w, v)
    return best


def neutral_weapon(e, cap_a, cap_b):
    """Deterministic: the first pool weapon supplying NEITHER side."""
    for w in sorted(e.pool):
        m = e.member_extra(w, None)
        if m.get(cap_a, 0.0) == 0.0 and m.get(cap_b, 0.0) == 0.0:
            return w
    return None


def best_gear_for(e, cap):
    """Deterministic: the curated item with the highest score on `cap`
    (ties by key). Dataset gear records carry capabilities as a flat
    {cap: score} map."""
    best = None
    for gid in sorted(e.gear):
        v = (e.gear[gid].get("capabilities") or {}).get(cap, 0)
        if v > 0 and (best is None or v > best[1]):
            best = (gid, v)
    return best


def hypothetical_pair(e, party, combos, gears, a, b, bonus):
    """The pair's value IF gear participated — engine's own rule mirrored
    over dressed supply and dressed member vectors. Analysis only."""
    s = e.effective_supply(party, combos, gears)
    j = 0.0
    for i, w in enumerate(party):
        gl = gears[i] if gears else None
        m = (e.build_extra(w, (combos[i] if combos else None)
                           if combos and combos[i] is not None
                           else e.default_combo(w), gl)
             if gl else e.member_extra(w, combos[i] if combos else None))
        j = max(j, min(m.get(a, 0.0), m.get(b, 0.0)))
    va = min(s.get(a, 0.0), e.target(a)) if a in e.reqs else s.get(a, 0.0)
    vb = min(s.get(b, 0.0), e.target(b)) if b in e.reqs else s.get(b, 0.0)
    v = min(va, vb) - j
    return bonus * v if v > 0 else 0.0


def measure_pair(e, a, b, bonus):
    wa = best_weapon_for(e, a)
    wb = best_weapon_for(e, b, avoid={wa[0]} if wa else ())
    ga, gb = best_gear_for(e, a), best_gear_for(e, b)
    wn = neutral_weapon(e, a, b)
    if not (wa and wb and wn):
        return {"pair": [a, b], "bonus": bonus,
                "skipped": "no weapon/neutral carrier found"}

    def case(label, party, gears):
        syn = e.synergy(party)                       # engine truth (weapon-only)
        cs_naked = e.comp_score(party)
        cs_dressed = e.comp_score(party, None, gears)
        hyp = hypothetical_pair(e, party, None, gears, a, b, bonus)
        actual = hypothetical_pair(e, party, None, None, a, b, bonus)
        return {
            "label": label, "party": party,
            "gears": gears,
            "synergy_engine": round(syn, 6),
            "comp_score_naked": round(cs_naked, 6),
            "comp_score_dressed": round(cs_dressed, 6),
            "pair_value_weapon_only": round(actual, 6),
            "pair_value_if_gear_counted": round(hyp, 6),
            "forgone": round(hyp - actual, 6),
        }

    cases = [
        case("1_weaponA_weaponB", [wa[0], wb[0]], None),
        case("2_gearA_weaponB", [wn, wb[0]], [[ga[0]], None] if ga else None)
        if ga else {"label": "2_gearA_weaponB",
                    "skipped": f"no curated gear supplies {a}"},
        case("3_weaponA_gearB", [wa[0], wn], [None, [gb[0]]] if gb else None)
        if gb else {"label": "3_weaponA_gearB",
                    "skipped": f"no curated gear supplies {b}"},
    ]
    return {"pair": [a, b], "bonus": bonus,
            "carriers": {"weapon_a": wa, "weapon_b": wb, "neutral": wn,
                         "gear_a": ga, "gear_b": gb},
            "cases": cases}


def blap_practice_check(probe):
    """How much pair value do the four pairs forgo on a real dressed comp?"""
    try:
        import yaml
    except ImportError:
        return {"skipped": "pyyaml missing"}
    path = os.path.join(ROOT, "data", "published_comps",
                        "timothy_blap_blackzone_roam_2026_08.yaml")
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    party_doc = doc["parties"][0]
    slots = [(j, s) for j, s in enumerate(party_doc["slots"])
             if s.get("weapons") and s.get("role") != "battlemount"]
    members = [s["weapons"][0] for _, s in slots]
    e = Engine(content="blackzone_roam", size=len(members), style="brawl")
    flat = gear_join.load_builds_flat(ROOT)
    gears = []
    for j, _s in slots:
        gl, _r, _t = gear_join.slot_gears(
            flat.get(f"{doc['id']}:{party_doc.get('name','?')}:{j}"), e.gear)
        gears.append(gl)
    rows = []
    for a, b, bonus in e.synergies:
        if a not in e.reqs or b not in e.reqs:
            continue
        actual = hypothetical_pair(e, members, None, None, a, b, bonus)
        hyp = hypothetical_pair(e, members, None, gears, a, b, bonus)
        rows.append({"pair": [a, b], "bonus": bonus,
                     "weapon_only": round(actual, 6),
                     "if_gear_counted": round(hyp, 6),
                     "forgone": round(hyp - actual, 6)})
    return {"comp": doc["id"], "size": len(members),
            "engine_synergy": round(e.synergy(members), 6),
            "beta": e.beta, "pairs": rows,
            "total_forgone_pair_units": round(sum(r["forgone"] for r in rows), 6),
            "total_forgone_score": round(
                e.beta * sum(r["forgone"] for r in rows), 6)}


def main():
    e = Engine(content=CONTENT, size=SIZE, style=STYLE)
    out = {"kind": "gear_synergy_audit",
           "content": CONTENT, "size": SIZE, "style": STYLE,
           "beta": e.beta,
           "pairs": [measure_pair(e, a, b, bonus)
                     for a, b, bonus in e.synergies],
           "blap_practice_check": blap_practice_check(e)}
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)

    for p in out["pairs"]:
        if "skipped" in p:
            print(f"{'x'.join(p['pair'])}: {p['skipped']}")
            continue
        print(f"pair {p['pair'][0]} x {p['pair'][1]} (bonus {p['bonus']}):")
        for c in p["cases"]:
            if "skipped" in c:
                print(f"  {c['label']}: {c['skipped']}")
            else:
                print(f"  {c['label']:<20} engine_syn={c['synergy_engine']:<8} "
                      f"weapon-only pair={c['pair_value_weapon_only']:<8} "
                      f"if-gear={c['pair_value_if_gear_counted']:<8} "
                      f"forgone={c['forgone']}")
    b = out["blap_practice_check"]
    if "pairs" in b:
        print(f"blap practice check: total forgone pair units "
              f"{b['total_forgone_pair_units']} -> score "
              f"{b['total_forgone_score']} (beta {b['beta']})")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
