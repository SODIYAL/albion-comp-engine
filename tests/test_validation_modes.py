#!/usr/bin/env python3
"""
Dressed-validation contracts (2026-08-27 hardening pass).

The production engine evaluates DRESSED candidates (weapon + combo +
doctrine kit) while the validation harnesses historically built naked
incumbent parties — an asymmetric comparison (see tests/VALIDATION.md,
dressed-validation section). This suite pins the machinery that makes the
comparison honest in both directions:

  V1  set_dressing(False) — the V3-W enabler: every CANDIDATE evaluates
      naked through the exact same scoring machinery (the identity
      short-circuit into _combo_score), score == naked comp-score delta
      at 1e-9; toggling back restores dressed evaluation bit-identically;
      a fresh engine defaults to dressed. No second scoring formula.

Later sections (added by the same hardening pass) cover the V3 form
parser, the V4 gear join, and the validation metrics.

Run:  py -3 tests/test_validation_modes.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
from engine import Engine  # noqa: E402

LONGBOW, HALLOWFALL, HEAVY_MACE = "2H_LONGBOW", "MAIN_HOLYSTAFF_AVALON", "2H_MACE"
EPS = 1e-9

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if detail:
        print(f"      {detail}")


# ------------------------------------------------------- V1 dressing switch
def t_dressing_switch():
    e = Engine(content="castle_outpost", size=7)
    party = [LONGBOW, HALLOWFALL]

    # Populate the dressed caches first so the toggle must actually clear
    # them (a stale _dressed_cache would hand dressed vectors to the naked
    # path — the exact bug the cache clearing exists to prevent).
    rows_dressed = e.recommend(party, 5)
    any_kit_before = any(r["kit"] for r in rows_dressed)

    e.set_dressing(False)
    rows = e.recommend(party, 5)
    naked_kits = all(not r["kit"] for r in rows)
    worst = 0.0
    base = e.comp_score(party)
    for r in rows:
        combos = [None] * len(party) + [r["combo"]]
        d = e.comp_score(party + [r["weapon"]], combos) - base
        worst = max(worst, abs(d - r["score"]))
    check("V1a dressing off: candidates naked, score == naked comp-score "
          "delta at 1e-9",
          naked_kits and worst < EPS,
          f"kits_empty={naked_kits} worst_delta={worst:.2e}")

    # kit_variants itself reports naked while the switch is off — the same
    # rule every attach point (recommend / swap_review / forge) reads.
    kv = e.kit_variants(LONGBOW)
    check("V1b dressing off: kit_variants collapses to [('v0', None)]",
          kv == [("v0", None)], f"kv={kv}")

    e.set_dressing(True)
    rows_back = e.recommend(party, 5)
    same = ([(r["weapon"], r["combo"], r["kit"]) for r in rows_back]
            == [(r["weapon"], r["combo"], r["kit"]) for r in rows_dressed])
    worst_back = max(abs(a["score"] - b["score"])
                     for a, b in zip(rows_back, rows_dressed))
    check("V1c dressing back on: recommend bit-identical to the pre-toggle "
          "dressed rows (no cache leak either direction)",
          any_kit_before and same and worst_back < EPS,
          f"dressed_kits_seen={any_kit_before} rows_match={same} "
          f"worst={worst_back:.2e}")

    e2 = Engine(content="castle_outpost", size=7)
    check("V1d a fresh engine defaults to dressed candidate evaluation",
          e2.dress_candidates is True
          and any(r["kit"] for r in e2.recommend(party, 5)),
          f"default={getattr(e2, 'dress_candidates', None)}")


# ------------------------------------------------------- V2 V3 form parser
FORM_FIXTURE = """# Tier-2 V3 — fixture

### Case 1
- Party (4/7): Heavy Mace, Hallowfall, Permafrost, Longbow
- PARTY_KEYS: 2H_MACE MAIN_HOLYSTAFF_AVALON 2H_ICECRYSTAL_UNDEAD 2H_LONGBOW
- PRIMARY NEED: Pierce
- BEST PICK: Spirithunter
- OTHER GOOD PICKS: Carving Sword, Realmbreaker
- BAD PICK: Longbow
- CONFIDENCE: High
- REASON: Already enough ranged AoE; needs resistance reduction.

### Case 2
- Party (2/7): Longbow, Witchwork
- PARTY_KEYS: 2H_LONGBOW MAIN_ARCANESTAFF_UNDEAD
- YOUR PICK: Hallowfall

### Case 3
- PARTY_KEYS: 2H_LONGBOW 2H_MACE
- BEST PICK:
- REASON:

### Case 4
- PARTY_KEYS: 2H_MACE 2H_LONGBOW
- GEAR_KEYS: ARMOR_PLATE_KEEPER,HEAD_PLATE_KEEPER ; -
- BEST PICK: Hallowfall
"""


def t_form_parser():
    sys.path.insert(0, HERE)
    import tier2_blindtest as t2
    cases = t2._parse_cases(FORM_FIXTURE)
    c1, c2, c3, c4 = cases
    check("V2a rich case: every field lands",
          c1["party"] == ["2H_MACE", "MAIN_HOLYSTAFF_AVALON",
                          "2H_ICECRYSTAL_UNDEAD", "2H_LONGBOW"]
          and c1["need"] == "Pierce" and c1["best"] == "Spirithunter"
          and c1["good"] == ["Carving Sword", "Realmbreaker"]
          and c1["bad"] == "Longbow" and c1["confidence"] == "high"
          and c1["reason"].startswith("Already enough"),
          f"c1={c1}")
    check("V2b legacy case: YOUR PICK is BEST PICK; empty fields are None",
          c2["best"] == "Hallowfall" and c2["need"] is None
          and c2["good"] == [] and c2["bad"] is None
          and c2["confidence"] is None and c2["gears"] is None,
          f"c2={c2}")
    check("V2c unfilled case parses with best=None (never swallows the "
          "next line — the [ \\t] rule)",
          c3["best"] is None and c3["party"] == ["2H_LONGBOW", "2H_MACE"],
          f"c3={c3}")
    check("V2d GEAR_KEYS: per-member kits, '-' = naked",
          c4["gears"] == [["ARMOR_PLATE_KEEPER", "HEAD_PLATE_KEEPER"], None],
          f"c4={c4}")


# ------------------------------------------------------- V3 metrics
def t_metrics():
    import tier2_blindtest as t2
    rows = [
        {"top1": True, "top3": True, "acceptable": True, "rank": 1,
         "need_hit": True, "bad_in_top3": False, "confidence": "high"},
        {"top1": False, "top3": True, "acceptable": True, "rank": 3,
         "need_hit": False, "bad_in_top3": True, "confidence": "low"},
        {"top1": False, "top3": False, "acceptable": True, "rank": 7,
         "need_hit": None, "bad_in_top3": None, "confidence": None},
    ]
    m = t2._metrics(rows)
    ok = (abs(m["top1"] - 1 / 3) < 1e-12 and abs(m["top3"] - 2 / 3) < 1e-12
          and abs(m["acceptable_top3"] - 1.0) < 1e-12
          and abs(m["mean_rank"] - 11 / 3) < 1e-12 and m["median_rank"] == 3
          and m["rank_n"] == 3 and m["outside_pool"] == 0
          and abs(m["need_agreement"] - 0.5) < 1e-12 and m["need_n"] == 2
          and abs(m["bad_pick_rate"] - 0.5) < 1e-12 and m["bad_n"] == 2
          and abs(m["conf_weighted_top3"] - (1.0 * 1 + 0.3 * 1 + 0.6 * 0)
                  / (1.0 + 0.3 + 0.6)) < 1e-12)
    check("V3a metrics: top1/top3/acceptable/ranks/need/bad/confidence all "
          "hand-checked", ok, f"m={m}")


# ------------------------------------------------------- V4 gear join
def t_gear_join():
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import gear_join
    e = Engine()
    flat = gear_join.load_builds_flat(ROOT)
    blap0 = flat.get("timothy_blap_blackzone_roam_2026_08:blap:0")
    bist0 = flat.get("albioncompo_bist_roam15_2026_01:comp:0")
    check("V4a builds_index join: comp:party:slot keys reach the caller-"
          "sheet and albioncompo records",
          blap0 is not None and bist0 is not None,
          f"blap0={'hit' if blap0 else 'MISS'} bist0={'hit' if bist0 else 'MISS'}")
    gl, resolved, total = gear_join.slot_gears(blap0, e.gear)
    gl2, resolved2, total2 = gear_join.slot_gears(bist0, e.gear)
    check("V4b actual kits resolve into the curated catalog (counts honest, "
          "unresolved never guessed)",
          gl and resolved >= 2 and total >= resolved
          and all(g in e.gear for g in gl)
          and gl2 is not None and resolved2 >= 1
          and all(g in e.gear for g in (gl2 or [])),
          f"blap0={resolved}/{total} {gl} bist0={resolved2}/{total2}")
    check("V4c normalize mirrors build_dataset: exact, unique tier prefix, "
          "else None",
          gear_join.normalize_gear_id("ARMOR_PLATE_KEEPER", e.gear)
          == "ARMOR_PLATE_KEEPER"
          and gear_join.normalize_gear_id("POTION_COOLDOWN", e.gear)
          == "T8_POTION_COOLDOWN"
          and gear_join.normalize_gear_id("no such item", e.gear) is None
          and gear_join.normalize_gear_id("", e.gear) is None,
          "")


if __name__ == "__main__":
    t_dressing_switch()
    t_form_parser()
    t_metrics()
    t_gear_join()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} validation-mode tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
