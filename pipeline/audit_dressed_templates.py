#!/usr/bin/env python3
"""
Dressed template audit (Phase 3, 2026-08-27). REPORT-ONLY.

For every published comp party that maps onto a fitted template, compute
each template capability's supply under four evaluation states:

  weapon      weapon-only, static default combos
  combo       weapons + the members' RECORDED spell picks where the
              builds evidence carries them (combo_from_picks)
  dressed     combo + the gear the source actually records for each
              member (builds_index join — the actual_gear class)
  doctrine    combo + kit_variants v0 per member (the engine's own
              inferred dressing, for comparison)

and report, per capability: target, soft cap, hard-floor state, coverage
under each state, the difference gear causes, and the Phase-3A flags —
whether gear ALONE moves the capability from deficient to covered, above
its soft cap, or across a hard floor, and whether the change is
suspiciously large (>= LARGE_DELTA of target, PROVISIONAL).

Nothing here scores, tunes, or gates. The output feeds the dressed
template audit report and the tankiness/frontline finding; template
retunes require the owner's ruling (anti-circularity, VALIDATION.md).

Run:  py -3 pipeline/audit_dressed_templates.py
Out:  pipeline/out/dressed_template_audit.json
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from engine import Engine  # noqa: E402
import gear_join  # noqa: E402

OUT = os.path.join(HERE, "out", "dressed_template_audit.json")

# Comp content -> fitted template. The 4 direct template contents map to
# themselves; the rest follow builds_index _meta content_covers (first
# entry). Display/audit mapping only — never a gate or scoring input.
CONTENT_MAP = {
    "large_scale_zvz": "territory_defense",
    "zvz_20man": "blackzone_roam",
    "zvz_20v20": "territory_defense",
    "zvz_7man": "castle_outpost",
}

# Phase-3A watch list: capabilities where ordinary gear saturating the
# template would matter most.
WATCH_CAPS = ("tankiness", "purge", "cleanse", "heal_reduction",
              "resist_shred", "peel", "mobility", "heal_sustain",
              "heal_burst", "damage_debuff")

LARGE_DELTA = 0.5   # gear delta >= 50% of target flags "large" (PROVISIONAL)


def party_states(e, comp_id, party, flat):
    all_slots = party.get("slots", [])
    slots = [(j, s) for j, s in enumerate(all_slots)
             if s.get("weapons") and s.get("role") != "battlemount"]
    members = [s["weapons"][0] for _, s in slots]
    combos, actual, res_n, rec_n = [], [], 0, 0
    for j, _s in slots:
        bid = f"{comp_id}:{party.get('name','?')}:{j}"
        rec = flat.get(bid)
        gl, res, rec_ct = gear_join.slot_gears(rec, e.gear)
        actual.append(gl)
        res_n += res
        rec_n += rec_ct
        spells = (rec or {}).get("spells") or {}
        w = members[len(combos)]
        combos.append(e.combo_from_picks(w, spells) if spells else None)
    return members, combos, actual, res_n, rec_n


def audit_party(e, members, combos, actual):
    doctrine = gear_join.doctrine_gears(e, members)
    s = {
        "weapon": e.effective_supply(members),
        "combo": e.effective_supply(members, combos),
        "dressed": e.effective_supply(members, combos, actual),
        "doctrine": e.effective_supply(members, combos, doctrine),
    }
    fit = {
        "weapon": e.fitness(members),
        "combo": e.fitness(members, combos),
        "dressed": e.fitness(members, combos, actual),
        "doctrine": e.fitness(members, combos, doctrine),
    }
    rows = []
    for cap in sorted(e.reqs):
        tgt, soft = e.target(cap), e.soft_cap(cap)
        f = e.floors.get(cap)
        floor_eff = e._floors_eff.get(cap)
        armed = bool(f) and e.size >= f["min_party_size"]
        sw, sc = s["weapon"].get(cap, 0.0), s["combo"].get(cap, 0.0)
        sd, sdoc = s["dressed"].get(cap, 0.0), s["doctrine"].get(cap, 0.0)
        delta = sd - sc
        rows.append({
            "cap": cap,
            "target": round(tgt, 6), "soft_cap": round(soft, 6),
            "floor": (None if not f else
                      {"units_eff": round(floor_eff, 6), "armed": armed,
                       "penalty_mult": f["penalty_mult"]}),
            "supply": {"weapon": round(sw, 6), "combo": round(sc, 6),
                       "dressed": round(sd, 6), "doctrine": round(sdoc, 6)},
            "coverage": {"combo": round(sc / tgt, 4) if tgt else None,
                         "dressed": round(sd / tgt, 4) if tgt else None},
            "soft_coverage": {"combo": round(sc / soft, 4) if soft else None,
                              "dressed": round(sd / soft, 4) if soft else None},
            "gear_delta": round(delta, 6),
            "gear_delta_vs_target": round(delta / tgt, 4) if tgt else None,
            "gear_flips_target": bool(sc < tgt <= sd),
            "gear_breaks_soft": bool(sc <= soft < sd),
            "gear_clears_floor": bool(armed and floor_eff is not None
                                      and sc < floor_eff <= sd),
            "gear_delta_large": bool(tgt and delta / tgt >= LARGE_DELTA),
        })
    return rows, fit


def main():
    try:
        import yaml
    except ImportError:
        sys.exit("pip install pyyaml")
    probe = Engine()
    templates = set(probe.data["templates"])
    flat = gear_join.load_builds_flat(ROOT)

    parties_out, skipped = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "data",
                                              "published_comps", "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if not (isinstance(doc, dict) and doc.get("kind") == "published_comp"):
            continue
        raw_content = doc.get("content")
        content = raw_content if raw_content in templates \
            else CONTENT_MAP.get(raw_content)
        if content is None:
            skipped.append({"comp": doc.get("id", "?"),
                            "content": raw_content})
            continue
        style = doc.get("style", "balanced")
        for party in doc.get("parties", []):
            members0 = [s["weapons"][0] for s in party.get("slots", [])
                        if s.get("weapons") and s.get("role") != "battlemount"]
            if not members0:
                continue
            e = Engine(content=content, size=len(members0), style=style)
            members, combos, actual, res_n, rec_n = party_states(
                e, doc.get("id", "?"), party, flat)
            rows, fit = audit_party(e, members, combos, actual)
            parties_out.append({
                "comp": doc.get("id", "?"),
                "party": party.get("name", "?"),
                "content": content, "mapped_from": raw_content,
                "style": style, "size": len(members),
                "gear_resolution": {"resolved": res_n, "recorded": rec_n,
                                    "members_dressed":
                                        sum(1 for a in actual if a)},
                "fitness": {k: round(v, 6) for k, v in fit.items()},
                "caps": rows,
            })

    # ---------------- aggregates: per template x capability
    agg = {}
    for p in parties_out:
        for row in p["caps"]:
            key = (p["content"], row["cap"])
            a = agg.setdefault(key, {
                "template": p["content"], "cap": row["cap"], "parties": 0,
                "target_met_dressed": 0, "target_met_combo": 0,
                "soft_exceeded_dressed": 0, "gear_flips_target": 0,
                "gear_breaks_soft": 0, "gear_clears_floor": 0,
                "gear_delta_large": 0, "delta_vs_target_sum": 0.0,
            })
            a["parties"] += 1
            a["target_met_dressed"] += row["coverage"]["dressed"] is not None \
                and row["coverage"]["dressed"] >= 1.0
            a["target_met_combo"] += row["coverage"]["combo"] is not None \
                and row["coverage"]["combo"] >= 1.0
            a["soft_exceeded_dressed"] += row["soft_coverage"]["dressed"] \
                is not None and row["soft_coverage"]["dressed"] > 1.0
            for flag in ("gear_flips_target", "gear_breaks_soft",
                         "gear_clears_floor", "gear_delta_large"):
                a[flag] += row[flag]
            a["delta_vs_target_sum"] += row["gear_delta_vs_target"] or 0.0

    agg_rows = []
    for key in sorted(agg):
        a = agg[key]
        n = a.pop("parties")
        a["parties"] = n
        a["mean_delta_vs_target"] = round(
            a.pop("delta_vs_target_sum") / n, 4)
        # Phase-3A suspicion: gear routinely flips/saturates this cap
        a["suspicious"] = bool(
            a["cap"] in WATCH_CAPS
            and (a["gear_flips_target"] * 2 > n
                 or a["gear_breaks_soft"] * 2 > n
                 or a["gear_clears_floor"] > 0
                 or a["gear_delta_large"] * 2 > n))
        agg_rows.append(a)

    out = {
        "kind": "dressed_template_audit",
        "large_delta_threshold": LARGE_DELTA,
        "watch_caps": list(WATCH_CAPS),
        "skipped_comps": skipped,
        "parties": parties_out,
        "aggregate": agg_rows,
    }
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)

    print(f"audited {len(parties_out)} parties "
          f"({len(skipped)} comps skipped, no template mapping)")
    sus = [a for a in agg_rows if a["suspicious"]]
    print(f"suspicious watch-cap rows (template x cap): {len(sus)}")
    for a in sus:
        print(f"  {a['template']:<18} {a['cap']:<15} "
              f"flips_target {a['gear_flips_target']}/{a['parties']}  "
              f"breaks_soft {a['gear_breaks_soft']}/{a['parties']}  "
              f"clears_floor {a['gear_clears_floor']}/{a['parties']}  "
              f"mean_delta {a['mean_delta_vs_target']:+.0%} of target")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
