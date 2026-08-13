#!/usr/bin/env python3
"""
Golden regression suite — the permanent version of the 9 cases that
tests/prototype_engine.py validated on 2026-08-12.

Difference from the prototype: this runs against engine/engine.py reading the
BUILT DATASET, so it regression-tests curated sheet changes, template tuning,
and scoring refactors all at once. The prototype kept its numbers in inline
Python dicts and could not.

Add a case whenever a human expert corrects the engine (VALIDATION.md).

Run:  py -3 tests/test_golden.py        (Windows)
      python3 tests/test_golden.py
"""
import os, sys, subprocess

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))

DATASET = os.path.join(ROOT, "pipeline", "out", "dataset-latest.json")
if not os.path.exists(DATASET):
    print("dataset missing — building it first")
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "build_dataset.py")],
                   check=False)

from engine import Engine  # noqa: E402

E = Engine(content="castle_outpost", size=7)

# T8/T9 run the 20-size templates against the REAL comps in meta_comps.yaml.
# These are fitness-discrimination and floor-sanity checks, deliberately NOT
# leave-one-out reproduction — the 20-size templates took role-ratio
# calibration from these same comps, so reproduction would be circular
# (see the template headers). Weapon slots only; battlemount slots excluded.
with open(os.path.join(HERE, "meta_comps.yaml"), encoding="utf-8") as f:
    _COMPS = {c["id"]: c for c in yaml.safe_load(f)["comps"]}


def _comp_party(comp_id, party_idx, drop_role=None):
    slots = _COMPS[comp_id]["parties"][party_idx]["slots"]
    return [s["weapons"][0] for s in slots
            if s["weapons"] and s["role"] != "battlemount"
            and (drop_role is None or s["role"] != drop_role)]
ROLES = E.scoring["role_sets"]
HEALERS, FRONTLINE, PURE_DPS = (set(ROLES["healers"]), set(ROLES["frontline"]),
                                set(ROLES["pure_dps"]))

LONGBOW, WITCHWORK, PERMAFROST = "2H_LONGBOW", "MAIN_ARCANESTAFF_UNDEAD", "2H_ICECRYSTAL_UNDEAD"
HALLOWFALL, GREAT_HOLY, HEAVY_MACE = "MAIN_HOLYSTAFF_AVALON", "2H_HOLYSTAFF", "2H_MACE"
GREAT_HAMMER, DAGGERS, BLOODLETTER = "2H_HAMMER", "2H_DAGGERPAIR", "MAIN_RAPIER_MORGANA"

results = []


def check(name, cond, detail):
    results.append((name, bool(cond), detail))


def names(recs):
    return [r["display_name"] for r in recs]


def run():
    # T1 — the worked example: 3 DPS must pull a healer
    party = [LONGBOW, WITCHWORK, PERMAFROST]
    recs = E.recommend(party)
    check("T1  3-DPS party -> top rec is a healer",
          recs[0]["weapon"] in HEALERS, f"top4={names(recs)}")

    weak = E.weaknesses(party)
    check("T1b weaknesses lead with healing",
          weak[0]["cap"] in ("heal_sustain", "heal_burst"),
          f"weaknesses={[w['cap'] for w in weak]}")

    # T2 — after the healer joins, priority must flip to frontline
    recs2 = E.recommend(party + [recs[0]["weapon"]])
    check("T2  +healer -> top rec is frontline",
          recs2[0]["weapon"] in FRONTLINE, f"top4={names(recs2)}")

    # T3 — empty party: first pick must not be pure DPS
    recs3 = E.recommend([])
    check("T3  empty party -> first pick not pure DPS",
          recs3[0]["weapon"] not in PURE_DPS, f"top4={names(recs3)}")

    # T4 — healing already saturated: no third healer in the top 3
    recs4 = E.recommend([HALLOWFALL, GREAT_HOLY, HEAVY_MACE, PERMAFROST])
    check("T4  2 healers in 4 -> no healer in top-3 recs",
          all(r["weapon"] not in HEALERS for r in recs4[:3]), f"top4={names(recs4)}")

    # T5 — 6 DPS, one slot left
    party5 = [LONGBOW, LONGBOW, WITCHWORK, PERMAFROST, DAGGERS, BLOODLETTER]
    recs5 = E.recommend(party5)
    check("T5  6-DPS last slot -> recommends healer",
          recs5[0]["weapon"] in HEALERS, f"top4={names(recs5)}")
    unc = E.uncovered_caps(party5)
    check("T5b lookahead flags >=3 uncovered important caps (greedy trap)",
          len(unc) >= 3, f"uncovered={unc}")

    # T6 — discrimination: meta comp must clearly beat a troll comp
    meta7 = [HEAVY_MACE, GREAT_HAMMER, HALLOWFALL, GREAT_HOLY, PERMAFROST, LONGBOW, WITCHWORK]
    troll7 = [LONGBOW, LONGBOW, LONGBOW, DAGGERS, BLOODLETTER, WITCHWORK, PERMAFROST]
    f_meta, f_troll = E.fitness(meta7), E.fitness(troll7)
    check("T6  meta comp outscores troll comp by >25%",
          f_meta > 1.25 * f_troll, f"meta={f_meta:.1f} troll={f_troll:.1f}")

    # T7 — explainability: the "why" must lead with the right capability
    terms = E.explain(party, recs[0]["weapon"])
    check("T7  top reason term for T1 rec is a heal capability",
          terms and terms[0]["cap"] in ("heal_sustain", "heal_burst"),
          f"terms={[(t['delta'], t['cap']) for t in terms[:3]]}")

    # T8/T9 — the 20-size content templates against the real comps
    e_bz = Engine(content="blackzone_roam", size=20)
    e_td = Engine(content="territory_defense", size=20)
    troll20 = [LONGBOW] * 7 + [DAGGERS] * 7 + [BLOODLETTER] * 6

    blap = _comp_party("timothy_blap_blackzone_roam_2026_08", 0)
    f_blap, f_troll_bz = e_bz.fitness(blap), e_bz.fitness(troll20)
    check("T8  blackzone_roam: real blap comp outscores troll 20 by >25%",
          f_blap > 1.25 * f_troll_bz, f"blap={f_blap:.1f} troll={f_troll_bz:.1f}")

    blap_nh = _comp_party("timothy_blap_blackzone_roam_2026_08", 0, drop_role="healer")
    recs8 = e_bz.recommend(blap_nh)
    check("T8b blackzone_roam: blap minus healers -> top rec is a healer",
          recs8[0]["weapon"] in HEALERS, f"top4={names(recs8)}")

    dh1 = _comp_party("deadlyhooker_large_scale_2026_08", 0)
    f_dh1, f_troll_td = e_td.fitness(dh1), e_td.fitness(troll20)
    check("T9  territory_defense: real Deadlyhooker P1 outscores troll 20 by >25%",
          f_dh1 > 1.25 * f_troll_td, f"dh1={f_dh1:.1f} troll={f_troll_td:.1f}")

    dh1_nh = _comp_party("deadlyhooker_large_scale_2026_08", 0, drop_role="healer")
    recs9 = e_td.recommend(dh1_nh)
    check("T9b territory_defense: DH P1 minus healers -> top rec is a healer",
          recs9[0]["weapon"] in HEALERS, f"top4={names(recs9)}")

    print("=" * 74)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL':4}  {name}\n      {detail}")
    print("=" * 74)
    meta = E.data["_meta"]
    print(f"{passed}/{len(results)} golden tests passed   "
          f"[dataset v{meta['version']}: {meta['weapons_curated']} curated, "
          f"{meta['weapons_illustrative']} illustrative]")
    if meta["weapons_illustrative"]:
        print("NOTE: illustrative sheets present — these tests validate model "
              "SHAPE, not recommendation quality. Quality is Tier-2 (V3/V4).")
    return passed, len(results)


if __name__ == "__main__":
    p, n = run()
    sys.exit(0 if p == n else 1)
