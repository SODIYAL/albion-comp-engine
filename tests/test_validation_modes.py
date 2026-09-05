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


# ------------------------------------------- V5 Option C structural floors
# Owner ruling 2026-08-27: STRUCTURAL hard floors read the weapon+loadout
# supply only — ordinary worn gear improves coverage/headroom/overstack but
# can never satisfy a structural floor (the 2026-08-12 pseudo-tankiness
# ruling extended to the gear stat channel).
CASE_A = ["MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW", "2H_ICECRYSTAL_UNDEAD",
          "2H_DUALSWORD", "2H_ARCANESTAFF_HELL", "MAIN_ARCANESTAFF",
          "2H_AXE"]   # 7-man, zero frontline-seat weapons (audit case A)


def _fitness_option_c(e, party, gears):
    """Fitness recomputed from the engine's own primitives with Option C
    semantics: coverage/headroom/overstack over the DRESSED supply, floor
    penalties at the WEAPON+LOADOUT supply. The test's independent sum."""
    s = e.effective_supply(party, None, gears)
    sf = e.effective_supply(party)
    want = 0.0
    for c in e.reqs:
        have, t, soft = s.get(c, 0.0), e.target(c), e.soft_cap(c)
        want += e.weight(c) * min(1.0, have / t) ** e.gamma
        want += e._headroom_bonus(c, have, t, soft)
        want -= e._overstack(c, have, t, soft)
        want -= e._floor_penalty(c, sf.get(c, 0.0))
    return want


def t_structural_floors():
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import gear_join
    e = Engine(content="castle_outpost", size=7)
    cap = "tankiness"
    doc = gear_join.doctrine_gears(e, CASE_A)
    naked = e.effective_supply(CASE_A)
    dressed = e.effective_supply(CASE_A, None, doc)
    fl = e._floors_eff[cap]
    check("V5a preconditions: no-frontline party below the floor naked, "
          "gear-only supply would clear it",
          naked.get(cap, 0.0) < fl <= dressed.get(cap, 0.0),
          f"naked={naked.get(cap, 0.0):.2f} floor={fl} "
          f"dressed={dressed.get(cap, 0.0):.2f}")

    got = e.fitness(CASE_A, None, doc)
    want = _fitness_option_c(e, CASE_A, doc)
    check("V5b Option C: dressed fitness == dressed coverage minus "
          "naked-basis floor penalties (armor never buys floor relief)",
          abs(got - want) < EPS, f"got={got!r} want={want!r}")

    pen = e._floor_penalty(cap, naked.get(cap, 0.0))
    check("V5c the no-frontline party still pays the full tankiness floor "
          "penalty when dressed", pen > 5.0, f"penalty={pen:.2f}")

    # case C: every member in explicit full plate — same rule, harder case
    plate = (sorted(k for k in e.gear if k.startswith("ARMOR_PLATE_"))[:1]
             + sorted(k for k in e.gear if k.startswith("HEAD_PLATE_"))[:1]
             + sorted(k for k in e.gear if k.startswith("SHOES_PLATE_"))[:1])
    gears_c = [list(plate) for _ in CASE_A]
    got_c = e.fitness(CASE_A, None, gears_c)
    want_c = _fitness_option_c(e, CASE_A, gears_c)
    check("V5d all-plate DPS never clear the structural floor either",
          abs(got_c - want_c) < EPS
          and e.floor_armed(cap, e.effective_supply(CASE_A).get(cap, 0.0)),
          f"got={got_c!r} want={want_c!r}")

    # case B: one genuine frontline weapon materially repairs the floor
    case_b = CASE_A[:5] + [HEAVY_MACE] + CASE_A[6:]
    naked_b = e.effective_supply(case_b)
    check("V5e a genuine frontline weapon clears the structural floor",
          not e.floor_armed(cap, naked_b.get(cap, 0.0))
          and e._floor_penalty(cap, naked_b.get(cap, 0.0)) == 0.0,
          f"naked_b={naked_b.get(cap, 0.0):.2f} floor={fl}")

    # the exact-marginal invariant survives the split: a dressed pick's
    # score == comp_score-with-gears delta on a DRESSED party (F1's
    # gears twin, post-Option-C)
    r = e.recommend(CASE_A, 1, gears=doc)[0]
    combos = [None] * len(CASE_A) + [r["combo"]]
    delta = (e.comp_score(CASE_A + [r["weapon"]], combos,
                          doc + [r["kit"] or None])
             - e.comp_score(CASE_A, None, doc))
    check("V5f pick score == dressed comp_score delta at 1e-9 under "
          "Option C floors", abs(delta - r["score"]) < EPS,
          f"score={r['score']!r} delta={delta!r} pick={r['weapon']}")


# ------------------------------------------- V6 per-style target modifiers
def t_target_mults():
    """styles.yaml `target_mults` (2026-08-28): the per-style REQUIREMENT
    overlay. Weight multipliers say what a style values; these say how much
    of it the style needs. Contract: target and soft cap scale TOGETHER,
    unlisted capabilities are untouched, hard floors never scale, and the
    shipped set is exactly the recorded rulings.

    The mechanism cases inject into BRAWL, which ships no multipliers, so
    the baseline is a true identity. (They used to inject into kite; once
    kite gained its own ruled values the baseline stopped being 1.0 and the
    cases failed — correctly.)"""
    import json, tempfile
    base = Engine(content="blackzone_roam", size=20, style="brawl")

    # The shipped set is PINNED: every value present must be a recorded
    # ruling, so an accidental or undocumented one fails here. Only the
    # ranged_aoe_core -> burst_aoe derivation survived validation
    # (2026-08-28); the healing and tankiness derivations were run the same
    # way and REJECTED because they widened coverage spread instead of
    # tightening it. balanced and brawl are the reference and stay empty.
    RULED = {"balanced": {}, "brawl": {}, "brawl_clap": {},
             "clap": {"burst_aoe": 1.71},
             "kite": {"burst_aoe": 1.29, "peel": 1.25, "disengage": 1.2},
             "clap_kite": {"burst_aoe": 1.71, "peel": 1.25}}
    styles = base.data.get("styles") or {}
    shipped = {s: (v or {}).get("target_mults") or {}
               for s, v in styles.items()}
    check("V6a shipped target_mults are exactly the recorded rulings "
          "(an undocumented value fails here)",
          shipped == RULED, f"shipped={shipped}")
    check("V6a2 balanced is empty — it is the reference the others scale "
          "against", not shipped.get("balanced"))

    d = json.loads(json.dumps(base.data))
    d["styles"]["brawl"]["target_mults"] = {"disengage": 2.0, "peel": 0.5}
    # The style x size rows (style_bands, owner 2026-09-04, golden T37)
    # supersede target_mults for a declared style at 10+ — the rows are
    # measured per style, so a multiplier would double-count. V6 tests the
    # multiplier MECHANISM on its own, so the synthetic dataset carries no
    # band rows (base below keeps its own; the ratio is what is checked).
    d.pop("style_bands", None)
    base.data.pop("style_bands", None)
    base.set_content("blackzone_roam", 20, "brawl")   # same footing: no band rows
    tmp = os.path.join(tempfile.gettempdir(), "bion_target_mults.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    e = Engine(dataset_path=tmp, content="blackzone_roam", size=20,
               style="brawl")

    check("V6b target and soft cap scale together (>1)",
          abs(e.target("disengage") - 2.0 * base.target("disengage")) < EPS
          and abs(e.soft_cap("disengage")
                  - 2.0 * base.soft_cap("disengage")) < EPS,
          f"target {base.target('disengage')} -> {e.target('disengage')}, "
          f"soft {base.soft_cap('disengage')} -> {e.soft_cap('disengage')}")
    check("V6c a multiplier below 1 lowers the requirement",
          abs(e.target("peel") - 0.5 * base.target("peel")) < EPS
          and abs(e.soft_cap("peel") - 0.5 * base.soft_cap("peel")) < EPS,
          f"target {base.target('peel')} -> {e.target('peel')}")
    check("V6d unlisted capabilities are untouched",
          abs(e.target("tankiness") - base.target("tankiness")) < EPS
          and abs(e.target("stun") - base.target("stun")) < EPS)
    check("V6e HARD FLOORS DO NOT SCALE — a style may not lower what keeps "
          "the party alive",
          all(abs(e._floors_eff.get(c, 0.0) - base._floors_eff.get(c, 0.0))
              < EPS for c in set(base._floors_eff) | set(e._floors_eff)),
          f"base={base._floors_eff} styled={e._floors_eff}")
    # the JS port reads the same key the same way; parity covers it the
    # moment a real value ships (both ports currently see {}).
    check("V6f balanced stays the identity even when another style is ruled",
          not (d["styles"]["balanced"].get("target_mults") or {}))


if __name__ == "__main__":
    t_dressing_switch()
    t_form_parser()
    t_metrics()
    t_gear_join()
    t_structural_floors()
    t_target_mults()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} validation-mode tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
