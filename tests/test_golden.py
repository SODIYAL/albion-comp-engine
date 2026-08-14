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

    # T10 — playstyles must actually discriminate. Same tanks + healers;
    # clap-flavored core (drags + AoE bombs) vs kite-flavored core (mobile
    # ranged chip). Absolute fitness depends on overall comp quality, so the
    # assertion is on the DIRECTION of the style effect: switching the style
    # from kite to clap must shift preference toward the clap comp (and
    # balanced must sit between the two), in the unsaturated regime (10
    # bodies against 20-man targets) where weights, not caps, decide.
    core = [GREAT_HAMMER, "MAIN_ROCKMACE_KEEPER", HALLOWFALL, GREAT_HOLY]
    clap10 = core + [PERMAFROST, PERMAFROST, WITCHWORK, "2H_ARCANESTAFF_HELL",
                     "2H_FIRE_RINGPAIR_AVALON", "2H_INFERNOSTAFF_MORGANA"]
    kite10 = core + [LONGBOW, "2H_WARBOW", "2H_BOW", "MAIN_FROSTSTAFF",
                     "MAIN_SPEAR_LANCE_AVALON", "2H_BOW_AVALON"]
    prefs = {}
    for st in ("clap", "balanced", "kite"):
        e_st = Engine(content="blackzone_roam", size=20, style=st)
        prefs[st] = e_st.fitness(clap10) - e_st.fitness(kite10)
    check("T10 clap style shifts preference toward the clap comp (margin >1)",
          prefs["clap"] > prefs["kite"] + 1.0,
          f"pref clap_style={prefs['clap']:.2f} kite_style={prefs['kite']:.2f}")
    check("T10b balanced sits between the style extremes",
          prefs["kite"] <= prefs["balanced"] <= prefs["clap"],
          f"kite={prefs['kite']:.2f} balanced={prefs['balanced']:.2f} clap={prefs['clap']:.2f}")

    # T11 — mechanics physics (MECHANICS_TODO.md, wired 2026-08-13): AoE
    # Escalation and Focus Fire/Resilience move EFFECTIVE supply, normalized
    # so balanced is the identity. Directions pinned by the wiki curves:
    # clap (7 targets) escalates AoE above balanced (4); brawl (3 targets)
    # sits below; fewer focus attackers (3 vs 4) means less Resilience tax,
    # so brawl/clap ST damage lands MORE than balanced's.
    e_bal = Engine(content="blackzone_roam", size=20, style="balanced")
    e_clap = Engine(content="blackzone_roam", size=20, style="clap")
    e_brawl = Engine(content="blackzone_roam", size=20, style="brawl")
    check("T11 AoE escalation direction: clap > balanced(=1) > brawl",
          e_clap.mech_mults["burst_aoe"] > 1.0 + 1e-9
          and abs(e_bal.mech_mults["burst_aoe"] - 1.0) < 1e-9
          and e_brawl.mech_mults["burst_aoe"] < 1.0 - 1e-9,
          f"clap={e_clap.mech_mults['burst_aoe']:.3f} "
          f"bal={e_bal.mech_mults['burst_aoe']:.3f} "
          f"brawl={e_brawl.mech_mults['burst_aoe']:.3f}")
    check("T11b Resilience direction: 3 focus attackers beat balanced's 4",
          e_brawl.mech_mults["burst_st"] > 1.0 + 1e-9
          and abs(e_bal.mech_mults["burst_st"] - 1.0) < 1e-9,
          f"brawl={e_brawl.mech_mults['burst_st']:.3f} "
          f"bal={e_bal.mech_mults['burst_st']:.3f}")
    aoe_party = [PERMAFROST, WITCHWORK, "2H_FIRE_RINGPAIR_AVALON"]
    raw = e_clap.supply(aoe_party).get("burst_aoe", 0)
    eff = e_clap.effective_supply(aoe_party).get("burst_aoe", 0)
    check("T11c effective supply applies the multiplier (clap AoE > raw)",
          raw > 0 and abs(eff - raw * e_clap.mech_mults["burst_aoe"]) < 1e-9
          and eff > raw,
          f"raw={raw:.1f} eff={eff:.2f}")

    # T12 — expert correction 2026-08-13: knockback is NOT clump creation.
    # Great Hammer's Tackle ("knocking back all enemies you pass through")
    # displaces; only drag/pull mechanics create clumps. The true clump
    # engines keep their scores: Hand of Justice's Onslaught (10-enemy drag),
    # Camlann's Vendetta (8m vacuum), Witchwork's Black Hole (radius pull).
    gh = E.caps_of(GREAT_HAMMER)
    check("T12 Great Hammer supplies no clump_create; true pulls still do",
          "clump_create" not in gh and gh.get("knockback_displace", 0) >= 1
          and E.caps_of("2H_MACE_MORGANA").get("clump_create", 0) >= 3
          and E.caps_of(WITCHWORK).get("clump_create", 0) >= 2,
          f"GH caps={sorted(gh)}; camlann={E.caps_of('2H_MACE_MORGANA').get('clump_create', 0)}")

    # T13 — expert magnitude pass 2026-08-13: knockback_displace scores
    # repositioning power, not existence. Ladder pinned within one role
    # family: Quarterstaff (12m CC-resist-ignoring kit) = 3 > Great Holy
    # (10m real AoE shove) = 2 > Hallowfall (air-throw, no travel) = 1 >
    # Holy Staff / Lifetouch / Redemption (Sacred Pulse self-peel, AA
    # passive) = absent.
    kd = lambda w: E.caps_of(w).get("knockback_displace", 0)
    check("T13 displacement magnitude ladder holds",
          kd("2H_QUARTERSTAFF") == 3 and kd("2H_HOLYSTAFF") == 2
          and kd(HALLOWFALL) == 1
          and all("knockback_displace" not in E.caps_of(w)
                  for w in ("MAIN_HOLYSTAFF", "MAIN_HOLYSTAFF_MORGANA",
                            "2H_HOLYSTAFF_UNDEAD")),
          f"qs={kd('2H_QUARTERSTAFF')} great_holy={kd('2H_HOLYSTAFF')} "
          f"hallowfall={kd(HALLOWFALL)} holy_staff={kd('MAIN_HOLYSTAFF')}")

    # T14 — one-spell-per-slot loadout model (2026-08-14): a weapon's sheet
    # lists caps across all its Q/W/E/passive options, but a player equips one
    # per slot. Dagger Pair's W is Shadow Edge (catch/stun/peel) OR Dash
    # (disengage); its Q is Deadly Swipe (mobility) OR Sunder Armor
    # (resist_shred). The flat union has all of them; the scored loadout must
    # never count both alternatives of a slot at once.
    ez = Engine(content="blackzone_roam", size=20)
    _df, _ds, extra = ez.best_loadout(ez.effective_supply([]), 0.0, DAGGERS)
    flat = E.caps_of(DAGGERS)
    check("T14 one-spell-per-slot: DP loadout never counts both W (or both Q) picks",
          not ("catch" in extra and "disengage" in extra)
          and not ("mobility" in extra and "resist_shred" in extra)
          and {"catch", "disengage", "mobility", "resist_shred"} <= set(flat),
          f"loadout extra={sorted(extra)} (flat union has all four)")

    # T15 — expert ruling 2026-08-14: single-target damage is WEAK in 20-man
    # group content (enemy heals + Resilience overpower focused damage), so
    # burst_st/execute are devalued in the 20-man templates. Consequence: a
    # clump-damage dagger (Demonfang, burst_aoe) out-scores a pure single-
    # target dagger (Dagger Pair) in a rounded party — the reverse of before.
    real20 = [HALLOWFALL, GREAT_HOLY, HEAVY_MACE, GREAT_HAMMER, "2H_QUARTERSTAFF",
              "MAIN_ROCKMACE_KEEPER", PERMAFROST, "2H_FIRE_RINGPAIR_AVALON",
              WITCHWORK, LONGBOW, "2H_WARBOW"]
    scored = {r["weapon"]: r["score"] for r in ez.recommend(real20, top_n=300)}
    check("T15 single-target weak at scale: AoE dagger out-scores pure-ST dagger",
          scored["MAIN_DAGGER_HELL"] > scored[DAGGERS],
          f"Demonfang={scored['MAIN_DAGGER_HELL']:.3f} > DaggerPair={scored[DAGGERS]:.3f}")

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
