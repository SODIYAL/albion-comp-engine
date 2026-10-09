#!/usr/bin/env python3
"""
Dressed-validation contracts.

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

  V8  harvest-seeded V3 forms (tier2_blindtest.py generate): every case
      is a killer party of exactly the form's size, every weapon known,
      on the training split only, never from a holdout, graded or
      earlier-round battle, one case per distinct roster, 2..size-1
      members shown, deterministic for a seed; the form carries the shown
      members alone and the answer key everything else; `score` finds the
      key, reports harvest agreement, and scores a Dragon Portal form in
      its own content and pool in both modes. On a synthetic artifact:
      the real one is never loaded here.

  V9  the style-labelling form (pipeline/style_blind_round.py): the
      committed round-1 form and its key exist, the form holds 20 cases,
      8 of them forged and the harvested ones at the forged sizes, each
      showing its size and weapons alone (the key's sources and engine
      reads never on it), and `score` reads a filled copy per source and
      size. Reads the committed files: no artifact, no engine.

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
    # A worn item with no combat effect is catalogued with no rows (the
    # plain Cape, Cabbage Soup, Pork Pie): the join resolves the harvest's
    # tierless id, the engine maps a fielded id at any tier, and wearing
    # one supplies nothing.
    norow = {"CAPE": "CAPE", "MEAL_SOUP": "T5_MEAL_SOUP",
             "MEAL_PIE": "T7_MEAL_PIE"}
    fielded = {"T4_CAPE@2": "CAPE", "T3_MEAL_SOUP": "T5_MEAL_SOUP",
               "T5_MEAL_PIE@1": "T7_MEAL_PIE"}
    bare = e.member_extra(LONGBOW, None)
    check("V4d an item with no combat effect resolves and supplies nothing: "
          "the join and the engine reach its one entry, which has no rows "
          "and no stats",
          all(gear_join.normalize_gear_id(raw, e.gear) == key
              for raw, key in norow.items())
          and all(e.gear_key(raw) == key for raw, key in fielded.items())
          and all(not e.gear[k]["capabilities"] and not e.gear[k]["stats"]
                  and e.build_extra(LONGBOW, None, [k]) == bare
                  for k in norow.values()),
          f"join={[gear_join.normalize_gear_id(r, e.gear) for r in norow]} "
          f"engine={[e.gear_key(r) for r in fielded]}")
    # the kit doctrine counts it like any worn piece: the plain Cape is
    # mined into the seat pools, and a kit that ranks it first wears it
    e20 = Engine(content="castle", size=20)
    pooled = sorted(r for r, rec in e20.roles.items()
                    if "CAPE" in ((rec.get("kit") or {}).get("cape") or []))
    named = [w for w in e20.pool
             if "CAPE" in (dict(e20.kit_variants(w)).get("v0") or [])]
    same = all(e20.build_extra(w, None, dict(e20.kit_variants(w))["v0"])
               == e20.build_extra(w, None, [g for g in dict(
                   e20.kit_variants(w))["v0"] if g != "CAPE"])
               for w in named)
    check("V4e the doctrine names the plain Cape where winners wear it: it "
          "sits in the mined cape pools, a v0 kit that ranks it first wears "
          "it, and the kit supplies what it supplies without it",
          pooled and named and same,
          f"seats={len(pooled)} weapons={len(named)} same={same}")


# ------------------------------------------- V5 Option C structural floors
# Option C (standing rule 10): STRUCTURAL hard floors read the weapon+loadout
# supply only — ordinary worn gear improves coverage/headroom/overstack but
# can never satisfy a structural floor (the pseudo-tankiness rule extended
# to the gear stat channel).
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
    """styles.yaml `target_mults`: the per-style REQUIREMENT
    overlay. Weight multipliers say what a style values; these say how much
    of it the style needs. Contract: target and soft cap scale TOGETHER,
    unlisted capabilities are untouched, hard floors never scale, and the
    shipped set is exactly the recorded values (V6).

    The mechanism cases inject into BRAWL, which ships no multipliers, so
    the baseline is a true identity. (They used to inject into kite; once
    kite gained its own recorded values the baseline stopped being 1.0 and
    the cases failed — correctly.)"""
    import json, tempfile
    base = Engine(content="blackzone_roam", size=20, style="brawl")

    # The shipped set is PINNED: every value present must be a recorded
    # value (tests/VALIDATION.md V6), so an accidental or undocumented one
    # fails here. Only the ranged_aoe_core -> burst_aoe derivation survived
    # validation; the healing and tankiness derivations were run the same
    # way and REJECTED because they widened coverage spread instead of
    # tightening it. balanced and brawl are the reference and stay empty.
    RECORDED = {"balanced": {}, "brawl": {}, "brawl_clap": {},
             "clap": {"burst_aoe": 1.71},
             "kite": {"burst_aoe": 1.29, "peel": 1.25, "disengage": 1.2},
             "clap_kite": {"burst_aoe": 1.71, "peel": 1.25}}
    styles = base.data.get("styles") or {}
    shipped = {s: (v or {}).get("target_mults") or {}
               for s, v in styles.items()}
    check("V6a shipped target_mults are exactly the recorded values "
          "(an undocumented value fails here)",
          shipped == RECORDED, f"shipped={shipped}")
    check("V6a2 balanced is empty — it is the reference the others scale "
          "against", not shipped.get("balanced"))

    d = json.loads(json.dumps(base.data))
    d["styles"]["brawl"]["target_mults"] = {"disengage": 2.0, "peel": 0.5}
    # The style x size rows (style_bands, golden T37)
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
    check("V6f balanced stays the identity even when another style "
          "carries multipliers",
          not (d["styles"]["balanced"].get("target_mults") or {}))


def t_median_rows():
    """V7 (target is the median, standing rule 17, replacing the
    zero-share pin it retires): the data comes from the harvest median —
    every style x band row on the SHIPPED file is the harvest's p50 as
    target, p10 as min and 1.15 x p90 as soft cap for the cell it names; a
    capability most winners field none of (p50 == 0) ships soft-cap-only
    with the content target standing; the convention line says so. The
    old rule (a twentieth of winners skipping it means no minimum)
    guarded p10 thrashing on the zero mass; the median does not thrash
    there, so the guard went with the convention."""
    import json, yaml
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import derive_style_bands as dsb
    with open(os.path.join(ROOT, "pipeline", "templates", "style_bands.yaml"),
              encoding="utf-8") as fh:
        bands = yaml.safe_load(fh)
    with open(os.path.join(ROOT, "pipeline", "out", "style_roster_evidence.json"),
              encoding="utf-8") as fh:
        board = json.load(fh)["board"]
    conv = bands.get("convention") or {}
    wrong, rows, soft_only = [], 0, 0
    for style, per_band in (bands.get("bands") or {}).items():
        for band_key, cell in (per_band or {}).items():
            src = cell.get("borrowed_from") or f"{style}|{band_key}"
            supply = (board.get(src) or {}).get("supply") or {}
            for cap, row in (cell.get("requirements") or {}).items():
                s = supply.get(cap) or {}
                p10, p50, p90 = (s.get("p10") or 0.0, s.get("p50") or 0.0,
                                 s.get("p90") or 0.0)
                rows += 1
                if "target" in row:
                    if (abs(row["target"] - round(dsb.TARGET_OF_P50 * p50, 2)) > 1e-9
                            or abs(row.get("min", -1) - round(p10, 2)) > 1e-9
                            or abs(row["soft_cap"] - round(dsb.SOFT_OF_P90 * p90, 2)) > 1e-9):
                        wrong.append(f"{src}:{cap} {row} vs p10/p50/p90 {p10}/{p50}/{p90}")
                else:
                    soft_only += 1
                    if p50 > 0:
                        wrong.append(f"{src}:{cap} soft-cap-only with p50 {p50}")
    check("V7 median rows: every shipped target is its cell's p50 (min p10, "
          "soft cap 1.15 x p90); soft-cap-only rows are exactly the p50 == 0 "
          "ones; the convention names p50 and no zero-share knob",
          rows >= 200 and not wrong and soft_only >= 1
          and abs((conv.get("target_of_p50") or 0) - dsb.TARGET_OF_P50) < 1e-9
          and "zero_share_max" not in conv
          and not hasattr(dsb, "ZERO_SHARE_MAX"),
          f"rows={rows} soft_only={soft_only} wrong={wrong[:3]}")


# ------------------------------------------------ V8 harvest-seeded forms
def _synthetic_harvest(t2, e):
    """A small roster artifact in the shape rosters_io.load returns.
    Eligible: 24 distinct trios and 16 distinct fives, dominant, each in a
    training battle (id % 5 != 0), the first trio's roster sighted again in
    a later battle. Beside them one party per rule that keeps a party off
    a form, each in a battle of its own. Returns (doc, weapons, never):
    `never` maps each such battle to the rule."""
    import itertools
    W = sorted(e.weapons)[:9]
    trios = [list(c) for c in itertools.combinations(W, 3)][:24]
    fives = [list(c) for c in itertools.combinations(W, 5)][:16]
    parties = []

    def add(battle, weapons, **kw):
        p = {"battle": battle, "index": 0, "size": len(weapons),
             "known_weapons": len(weapons), "weapons": sorted(weapons),
             "kills": 2, "deaths": 0, "guilds": []}
        p.update(kw)
        parties.append(p)

    train = (b for b in itertools.count(5001) if b % 5)
    for ws in trios + fives:
        add(next(train), ws)
    add(next(train), trios[0])                      # a second sighting
    never = {6000: "holdout", 6005: "holdout",
             t2.GRADED_BATTLES[0]: "graded", 7001: "earlier form",
             7002: "size 4", 7003: "a weapon unknown",
             7004: "a weapon outside the catalog", 7006: "took a death",
             7007: "no kill"}
    add(6000, [W[0], W[4], W[8]])
    add(6005, [W[1], W[5], W[8]])
    add(t2.GRADED_BATTLES[0], [W[2], W[6], W[8]])
    add(7001, [W[3], W[7], W[8]])
    add(7002, [W[0], W[1], W[2], W[8]])
    add(7003, [W[0], W[2], W[7]], known_weapons=2)
    add(7004, [W[0], W[3], "NOT_A_CATALOG_WEAPON"])
    add(7006, [W[1], W[2], W[7]], deaths=1)
    add(7007, [W[1], W[3], W[7]], kills=0)
    battles = sorted({p["battle"] for p in parties})
    doc = {"battles": [{"battle": b, "content": "ancient_lands",
                        "source": "events_poll"} for b in battles],
           "parties": parties, "builds": []}
    return doc, W, never


def t_harvest_forms():
    import json, re, shutil, tempfile
    import tier2_blindtest as t2
    e = Engine(content="ancient_lands", size=3)
    doc, W, never = _synthetic_harvest(t2, e)
    cat = set(e.weapons)
    excl = {"graded_battles": set(t2.GRADED_BATTLES), "earlier_forms": {7001}}
    eligible = {}
    for p in doc["parties"]:
        if p["battle"] not in never:
            eligible.setdefault(tuple(p["weapons"]), []).append(p["battle"])

    cases, counts = t2.harvest_cases(doc, cat, 3, 100, 11, dominant=True, excluded=excl)
    bad = [(c["battle"], never[c["battle"]]) for c in cases if c["battle"] in never]
    check("V8a training split only: no case from a holdout, graded or "
          "earlier-round battle, and the counts name each reason",
          cases and not bad and all(c["battle"] % 5 for c in cases)
          and counts["parties"] == 29 and counts["not_training"] == 2
          and counts["graded_battles"] == 1 and counts["earlier_forms"] == 1
          and counts["eligible"] == 25 and counts["rosters"] == 24,
          f"bad={bad} counts={counts}")

    harvest = t2._harvest_parties(doc, {}, e, 3, 3, 0, dominant=True)
    check("V8b size exact, every weapon known and in the catalog, dominant: "
          "the one eligibility rule v4h reads too",
          all(tuple(sorted(c["shown"] + c["removed"])) in eligible for c in cases)
          and len(harvest) == counts["parties"]
          and t2.harvest_cases(doc, cat, 3, 100, 11, dominant=False,
                               excluded=excl)[1]["eligible"] == 27,
          f"v4h reads {len(harvest)} of {counts['parties']}")

    five, _c5 = t2.harvest_cases(doc, cat, 5, 100, 11, dominant=True, excluded=excl)
    kept = sorted({len(c["shown"]) for c in five})
    check("V8c each case keeps 2..size-1 of its party's members, the rest "
          "removed (one at size 3), shown + removed = the party",
          all(len(c["shown"]) == 2 and len(c["removed"]) == 1 for c in cases)
          and five and set(kept) <= {2, 3, 4} and len(kept) > 1
          and all(len(c["shown"]) + len(c["removed"]) == 5 for c in five),
          f"kept at size 5: {kept}")

    def distinct(cs):
        full = [tuple(sorted(c["shown"] + c["removed"])) for c in cs]
        shown = [tuple(sorted(c["shown"])) for c in cs]
        return len(set(full)) == len(full) and len(set(shown)) == len(shown)
    src_ok = all(c["sightings"] == len(eligible[tuple(sorted(c["shown"] + c["removed"]))])
                 and c["battle"] in eligible[tuple(sorted(c["shown"] + c["removed"]))]
                 for c in cases)
    check("V8d one case per distinct roster, no partial party shown twice in "
          "a form, each case sourced from an eligible party fielding its roster",
          distinct(cases) and distinct(five) and src_ok,
          f"{len(cases)} cases at 3, {len(five)} at 5")

    a, _ = t2.harvest_cases(doc, cat, 3, 12, 11, dominant=True, excluded=excl)
    b, _ = t2.harvest_cases(doc, cat, 3, 12, 11, dominant=True, excluded=excl)
    other, _ = t2.harvest_cases(doc, cat, 3, 12, 12, dominant=True, excluded=excl)
    text_a = "\n".join(t2.form_lines(e, "ancient_lands", 3, "balanced", 11, [c["shown"] for c in a]))
    text_b = "\n".join(t2.form_lines(e, "ancient_lands", 3, "balanced", 11, [c["shown"] for c in b]))
    check("V8e deterministic for a seed: the same seed, the same cases and "
          "form; another seed, another draw",
          len(a) == 12 and a == b and text_a == text_b and other != a)

    name = t2._display_names(e)
    blocks = re.split(r"(?m)^### Case \d+$", text_a)[1:]
    leaks = []
    for c, block in zip(a, blocks):
        keys = re.search(r"(?m)^- PARTY_KEYS: (.*)$", block).group(1).split()
        names = re.search(r"(?m)^- Party \(\d+/\d+\): (.*)$", block).group(1).split(", ")
        others = [ln for ln in block.splitlines()
                  if ln.strip() and not ln.startswith(("- Party (", "- PARTY_KEYS:"))
                  and not re.match(r"^- [A-Z ]+: ?$", ln)]
        if keys != c["shown"] or names != [name[w] for w in c["shown"]] or others:
            leaks.append((keys, names, others))
    ids = [str(c["battle"]) for c in a if str(c["battle"]) in text_a]
    check("V8f the form shows each case's kept members alone: no battle, "
          "no party index, no removed member",
          len(blocks) == len(a) and not leaks and not ids
          and not re.search(r"(?im)^- *(removed|battle|party index|sightings)\b", text_a),
          f"leaks={leaks[:2]} ids={ids[:3]}")

    tmp = tempfile.mkdtemp(prefix="bion_v8_")
    try:
        def key_file(path, rnd, battles):
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"round": rnd, "cases": [{"battle": x} for x in battles]}, fh)
        key_file(os.path.join(tmp, "tier2_form_r2_a.key.json"), 2, [111])
        key_file(os.path.join(tmp, "tier2_form_r3_a.key.json"), 3, [222])
        key_file(os.path.join(tmp, "tier2_form_r3_b.key.json"), 3, [333])
        key_file(os.path.join(tmp, "tier2_form_old.key.json"), None, [444])
        r3, used3 = t2.form_key_battles(3, (tmp,))
        r4, _u4 = t2.form_key_battles(4, (tmp,), skip=(os.path.join(tmp, "tier2_form_r3_b.key.json"),))
        check("V8g a form excludes the battles every EARLIER round's key "
              "records (a key without a round counts as earlier); its own "
              "round's keys are not read",
              r3 == {111, 444} and r4 == {111, 222, 444} and len(used3) == 2,
              f"round 3 reads {sorted(r3)}, round 4 {sorted(r4)}")

        # a size-5 Dragon Portal form, two cases answered, with its key
        e5 = Engine(content="ancient_lands", size=5)
        cases5 = sorted(five, key=lambda c: -len(c["removed"]))[:2]
        lines = t2.form_lines(e5, "ancient_lands", 5, "balanced", 11,
                              [c["shown"] for c in cases5])
        text5 = "\n".join(lines)
        text5 = text5.replace("- BEST PICK: ", f"- BEST PICK: {name[cases5[0]['removed'][0]]}", 1)
        outsider = next(w for w in W if w not in cases5[1]["removed"]
                        and w not in cases5[1]["shown"])
        i2 = text5.index("### Case 2")
        tail = (text5[i2:].replace("- BEST PICK: ", f"- BEST PICK: {name[outsider]}", 1)
                .replace("- OTHER GOOD PICKS: ", f"- OTHER GOOD PICKS: {name[cases5[1]['removed'][0]]}", 1))
        text5 = text5[:i2] + tail
        form5 = os.path.join(tmp, "tier2_form_r9_portal5.md")
        with open(form5, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text5)
        key5 = {"round": 9, "cases": [dict(c, case=i) for i, c in enumerate(cases5, 1)]}
        with open(os.path.splitext(form5)[0] + ".key.json", "w", encoding="utf-8", newline="\n") as fh:
            json.dump(key5, fh)
        copy5 = os.path.join(tmp, "answers_copy.md")
        shutil.copy(form5, copy5)
        parsed = t2._parse_cases(text5)
        sib_path, sib = t2.form_key(form5, parsed)
        copy_path, copy_key = t2.form_key(copy5, parsed)
        wrong = os.path.join(tmp, "wrong.key.json")
        with open(wrong, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"round": 9, "cases": [{"shown": c["shown"]} for c in cases5[::-1]]}, fh)
        try:
            t2.form_key(form5, parsed, wrong)
            refused = False
        except SystemExit:
            refused = True
        removed = [c["removed"] for c in sib["cases"]] if sib else None
        rows_w, _u, _l = t2._score_mode(e5, parsed, "w", removed)
        rows_d, _u, _l = t2._score_mode(e5, parsed, "d", removed)
        m = t2._metrics(rows_d)
        check("V8h score finds the form's key (beside it, or by its parties for "
              "a renamed copy), refuses another form's key, and reports how "
              "often the grader's picks name a removed member",
              sib is not None and copy_key == sib and refused
              and [r["harvest_hit"] for r in rows_w] == [True, False]
              and [r["harvest_acceptable"] for r in rows_d] == [True, True]
              and m["harvest_agreement"] == 0.5 and m["harvest_acceptable"] == 1.0
              and m["harvest_n"] == 2,
              f"sibling={sib_path} copy={copy_path} rows={[(r['harvest_hit'], r['harvest_acceptable']) for r in rows_d]}")

        e_ctx, ctx = t2.form_engine(text5)
        rows_cw, _u, _l = t2._score_mode(e_ctx, parsed, "w", removed)
        rows_cd, _u, _l = t2._score_mode(e_ctx, parsed, "d", removed)
        in_pool = all(not e_ctx.is_unfielded(w) for r in rows_cw + rows_cd
                      for w in r["engine_top3"])
        check("V8i a Dragon Portal form scores in its own FORM_CONTEXT: "
              "ancient_lands at 5, the 4-5 pool's rows and fielded list, in "
              "both modes",
              ctx == {"content": "ancient_lands", "size": 5, "style": "balanced"}
              and e_ctx.content == "ancient_lands" and e_ctx.size == 5
              and e_ctx.pool_key == "4-5" and len(rows_cw) == len(rows_cd) == 2
              and in_pool and e_ctx.dress_candidates is True,
              f"ctx={ctx} pool={e_ctx.pool_key} rows={len(rows_cw)}/{len(rows_cd)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------ V9 style-labelling forms
STYLE_FORM = os.path.join(HERE, "style_form_r1_kite.md")


def t_style_forms():
    import collections, json, re
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import style_blind_round as sbr
    from graded_battles import GRADED_BATTLES
    key_path = os.path.splitext(STYLE_FORM)[0] + ".key.json"
    if not (os.path.exists(STYLE_FORM) and os.path.exists(key_path)):
        check("V9a the style-labelling form and its key exist", False,
              f"missing: {[p for p in (STYLE_FORM, key_path) if not os.path.exists(p)]}")
        return
    with open(STYLE_FORM, encoding="utf-8") as f:
        text = f.read()
    with open(key_path, encoding="utf-8") as f:
        key = json.load(f)
    cases = sbr.parse_form(text)
    kc = sorted(key["cases"], key=lambda c: c["case"])
    forged = [c for c in kc if c["source"] == "forged"]
    harvest = [c for c in kc if c["source"] == "harvest"]
    cells = sorted((c["content"], c["forge_size"], c["style"]) for c in forged)
    want_cells = sorted((ct, n, "kite") for ct in ("blackzone_roam", "territory_defense")
                        for n in (10, 15, 20, 25))
    sizes = collections.Counter(c["size"] for c in harvest)
    # the per-size mix is the dealt plan, moved only by a recorded substitution
    plan = {int(n): collections.Counter(v) for n, v in key["harvest"]["plan"].items()}
    want = {n: collections.Counter(v) for n, v in plan.items()}
    for s in key["harvest"]["substitutions"]:
        want[s["size"]][s["wanted"]] -= 1
        want[s["size"]][s["took"]] += 1
    have = {n: collections.Counter(c["engine"]["style"] for c in harvest if c["size"] == n)
            for n in plan}
    mix_ok = (all(+want[n] == have[n] for n in plan)
              and sum(plan.values(), collections.Counter()) == {"kite": 4, "clap_kite": 4,
                                                                 "clap": 2, "brawl": 2})
    rosters = [tuple(sorted(c["weapons"])) for c in harvest]
    forged_rosters = {tuple(sorted(c["weapons"])) for c in forged}
    sources_ok = (all(c["battle"] % 5 and c["battle"] not in GRADED_BATTLES for c in harvest)
                  and len(set(rosters)) == len(rosters)
                  and not forged_rosters & set(rosters))
    blank = all(not c["style"] and not c["confidence"] for c in cases)
    check("V9a the style-labelling form and its key exist: 20 cases, 8 forged for "
          "kite (Blackzone Roam and Territory Defense at 10, 15, 20, 25) and 12 "
          "harvested killer parties, four each of exactly 10, 15 and 20 players (no size "
          "a killer party reaches belongs to one source alone), the engine reading 4 "
          "kite, 4 clap_kite, 2 clap and 2 brawl as dealt across the sizes, a size's "
          "shortfall a recorded substitution; each on the training split, in no graded "
          "battle and a roster of its own; the form shows every case's size and weapons "
          "as the key records them, every answer blank",
          len(cases) == 20 and len(kc) == 20 and len(forged) == 8 and len(harvest) == 12
          and cells == want_cells and sizes == {10: 4, 15: 4, 20: 4}
          and key["harvest"]["sizes"] == [10, 15, 20] and mix_ok
          and sources_ok and sbr.match_key(cases, key) and blank
          and key.get("form") == "tests/style_form_r1_kite.md",
          f"cases={len(cases)} forged={len(forged)} sizes={dict(sizes)} "
          f"mix={ {n: dict(v) for n, v in have.items()} } sources_ok={sources_ok} "
          f"blank={blank}")

    blocks = re.split(r"(?m)^### Case \d+$", text)[1:]
    extra = [ln for b in blocks for ln in b.splitlines()
             if ln.strip() and not re.match(r"^- (size: \d+|weapons: .+|style:|confidence \(1-3\):)$", ln)]
    ids = [str(c["battle"]) for c in harvest if str(c["battle"]) in text]
    # the prose around the weapons (weapon names carry such words: Forge
    # Hammers, Battle Bracers)
    prose = "\n".join(ln for ln in text.splitlines() if not ln.startswith("- weapons:"))
    words = re.findall(r"(?i)\b(?:forged?|harvest\w*|battles?|engine|blackzone|territory|"
                       r"sightings|melee|strength|leaning|key\.json)\b", prose)
    check("V9b the key never appears in the form: no key file, battle id, source, content "
          "or engine read on it, and each case carries its size, its weapons and the two "
          "blank fields alone",
          len(blocks) == 20 and not extra and not ids and not words
          and os.path.basename(key_path) not in text,
          f"extra={extra[:2]} ids={ids[:2]} words={sorted(set(words))[:5]}")

    # a filled copy: every case labelled as the engine reads it, typed the
    # way a labeller types (capitals, hyphens), confidence 3
    def typed(style):
        return sbr.vocab(style).replace("_", "-").title()
    by_case = {c["case"]: c for c in kc}
    parts = re.split(r"(?m)^(### Case (\d+))$", text)
    filled = parts[0]
    for head, num, body in zip(parts[1::3], parts[2::3], parts[3::3]):
        label = typed(by_case[int(num)]["engine"]["style"])
        body = re.sub(r"(?m)^- style:$", f"- style: {label}", body, count=1)
        body = re.sub(r"(?m)^- confidence \(1-3\):$", "- confidence (1-3): 3", body, count=1)
        filled += head + body
    res = sbr.evaluate(sbr.parse_form(filled), key)
    g = res["groups"]
    not_kite = sorted(c["case"] for c in forged if sbr.vocab(c["engine"]["style"]) != "kite")
    shuffled = dict(key, cases=[dict(c, case=len(kc) + 1 - c["case"]) for c in kc])
    check("V9c score reads a filled copy: labels in any case and with hyphens, "
          "agreement per source and size, the forged rosters not called kite listed; a "
          "key showing other rosters is refused",
          res["answered"] == 20 and not res["unresolved"]
          and g[("all", "all")] == {"cases": 20, "answered": 20, "agree": 20}
          and [k for k in g if k[0] == "forged"] == [("forged", "10"), ("forged", "15"),
                                                    ("forged", "20"), ("forged", "25"),
                                                    ("forged", "all")]
          and all(g[("forged", s)]["cases"] == 2 for s in ("10", "15", "20", "25"))
          and [k for k in g if k[0] == "harvest"] == [("harvest", "10"), ("harvest", "15"),
                                                     ("harvest", "20"), ("harvest", "all")]
          and all(g[("harvest", s)]["cases"] == 4 for s in ("10", "15", "20"))
          and g[("harvest", "all")]["cases"] == 12
          and sorted(r["case"] for r in res["missed"]) == not_kite
          and all(r["confidence"] == 3 for r in res["rows"])
          and not sbr.match_key(sbr.parse_form(filled), shuffled),
          f"groups={dict(g)} missed={[r['case'] for r in res['missed']]} want={not_kite}")


if __name__ == "__main__":
    t_dressing_switch()
    t_form_parser()
    t_metrics()
    t_gear_join()
    t_structural_floors()
    t_target_mults()
    t_median_rows()
    t_harvest_forms()
    t_style_forms()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} validation-mode tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
