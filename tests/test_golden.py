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
import glob, os, sys, subprocess

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

# T8/T9 run the 20-size templates against the REAL caller comps, which live
# in data/published_comps/ (the production evidence layer — chapter 2 moved
# them out of tests/). These are fitness-discrimination and floor-sanity
# checks, deliberately NOT leave-one-out reproduction — the 20-size templates
# took role-ratio calibration from these same comps, so reproduction would be
# circular (see the template headers). Weapon slots only; battlemounts excluded.
_COMPS = {}
for _p in sorted(glob.glob(os.path.join(ROOT, "data", "published_comps",
                                        "*.yaml"))):
    with open(_p, encoding="utf-8") as f:
        _doc = yaml.safe_load(f)
    if isinstance(_doc, dict) and _doc.get("kind") == "published_comp":
        _COMPS[_doc["id"]] = _doc


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
    check("T11c effective supply applies the multiplier (clap AoE > raw units)",
          raw > 0 and abs(eff - raw / e_clap.score_unit
                          * e_clap.mech_mults["burst_aoe"]) < 1e-9
          and eff > raw / e_clap.score_unit,
          f"raw={raw:.1f}pts eff={eff:.2f}u unit={e_clap.score_unit:g}")

    # T12 — expert correction 2026-08-13: knockback is NOT clump creation.
    # Great Hammer's Tackle ("knocking back all enemies you pass through")
    # displaces; only drag/pull mechanics create clumps. The true clump
    # engines keep their scores: Hand of Justice's Onslaught (10-enemy drag),
    # Camlann's Vendetta (8m vacuum), Witchwork's Black Hole (radius pull).
    gh = E.caps_of(GREAT_HAMMER)
    check("T12 Great Hammer supplies no clump_create; true pulls still do",
          "clump_create" not in gh and gh.get("knockback_displace", 0) >= 2
          and E.caps_of("2H_MACE_MORGANA").get("clump_create", 0) >= 6
          and E.caps_of(WITCHWORK).get("clump_create", 0) >= 4,
          f"GH caps={sorted(gh)}; camlann={E.caps_of('2H_MACE_MORGANA').get('clump_create', 0)}")

    # T13 — expert magnitude pass 2026-08-13: knockback_displace scores
    # repositioning power, not existence. Ladder pinned within one role
    # family: Quarterstaff (12m CC-resist-ignoring knock-UP kit) = top >
    # Great Holy = Hallowfall = small > Holy Staff / Lifetouch / Redemption
    # (Sacred Pulse self-peel, AA passive) = absent. Owner ruling 2026-08-21:
    # Great Holy's 10m radial shove is self-centred — it only matters when
    # enemies are already on top, so it is peel, not offensive displacement;
    # its knockback_displace dropped 4 -> 2 (the peel 4 carries the E's job).
    kd = lambda w: E.caps_of(w).get("knockback_displace", 0)
    check("T13 displacement magnitude ladder holds",
          kd("2H_QUARTERSTAFF") == 6 and kd("2H_HOLYSTAFF") == 2
          and kd(HALLOWFALL) == 2
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
    # burst_st/execute are devalued in the 20-man templates.
    # FIXTURE REVISED 2026-08-21 (comp-fitted recalibration, owner directive):
    # the old proxy compared Demonfang's vs Dagger Pair's TOTAL scores. After
    # the comp-fitted targets un-saturated catch/mobility, Dagger Pair's total
    # legitimately leads — driven by its CATCH term (0.95), with its ST terms
    # contributing ~14% — so the proxy stopped isolating the ruling it pinned.
    # The pin now asserts the ruling itself: whatever a pure-ST dagger is
    # worth in a rounded 20-man, its kill-damage terms (burst_st + execute)
    # must stay a SMALL fraction of its value and below its utility terms.
    real20 = [HALLOWFALL, GREAT_HOLY, HEAVY_MACE, GREAT_HAMMER, "2H_QUARTERSTAFF",
              "MAIN_ROCKMACE_KEEPER", PERMAFROST, "2H_FIRE_RINGPAIR_AVALON",
              WITCHWORK, LONGBOW, "2H_WARBOW"]
    # (2026-08-23 round 3: the generation-fit gate removed Dagger Pair from
    # the DEFAULT pool at 20 — exactly the ruling's spirit — so its score is
    # read through an explicit candidate pool, the manual-pick path.)
    dp_score = ez.recommend(real20, top_n=1, pool=[DAGGERS])[0]["score"]
    dp_terms = {t["cap"]: t["delta"] for t in ez.explain(real20, DAGGERS)}
    dp_st = dp_terms.get("burst_st", 0.0) + dp_terms.get("execute", 0.0)
    dp_catch = dp_terms.get("catch", 0.0)
    check("T15 single-target weak at scale: a pure-ST dagger's value is utility, not kill damage",
          dp_st < 0.25 * dp_score and dp_st < dp_catch,
          f"DaggerPair ST terms={dp_st:.2f} of {dp_score:.2f} total; catch term={dp_catch:.2f}")

    # T16 — Roads of Avalon size graduation (2026-08-15, the goal behavior):
    # a healer-less trio is a legitimate comp (floors silent, single-target
    # damage BOOSTED below base size by the Q16 physics), but the same
    # weapons read as a 7-man are broken (heal floor armed from 5) and the
    # healer recommendation urgency roughly doubles.
    trio = [BLOODLETTER, "2H_BOW_AVALON", "2H_HARPOON_HELL"]
    er3 = Engine(content="roads", size=3)
    er7 = Engine(content="roads", size=7)
    heal_at = lambda e: max(r["score"] for r in e.recommend(trio, top_n=300)
                            if r["weapon"] in HEALERS)
    check("T16 roads floors arm by size: trio fine at 3, healer urgent at 7",
          er3._floor_penalty("heal_sustain", 0) == 0.0
          and er7._floor_penalty("heal_sustain", 0) > 0.0
          and heal_at(er7) > 1.5 * heal_at(er3)
          and er3.mech_mults["burst_st"] > 1.0 + 1e-9,
          f"floor@3={er3._floor_penalty('heal_sustain', 0):.1f} "
          f"floor@7={er7._floor_penalty('heal_sustain', 0):.1f} "
          f"healer score 3->{heal_at(er3):.2f} 7->{heal_at(er7):.2f} "
          f"st_mult@3={er3.mech_mults['burst_st']:.3f}")

    # T17 — per-member swap advisor (2026-08-15): each member's current
    # weapon is valued exactly as recommend() would value it into the rest of
    # the party, ranked against all alternatives, with better options listed.
    # Pin the directions in a real-shaped roads 7-man: the ZvZ bomb axe
    # (Realmbreaker) must rank far worse than the tank pick (Heavy Mace), a
    # poor fit must come with non-empty upgrade options, and a member's score
    # must equal their weapon's recommend() value into the rest.
    roads7 = [HEAVY_MACE, HALLOWFALL, "2H_CROSSBOWLARGE_MORGANA",
              "2H_HARPOON_HELL", BLOODLETTER, "2H_AXE_AVALON", "2H_BOW_AVALON"]
    rev = er7.swap_review(roads7)
    by_w = {m["weapon"]: m for m in rev}
    rb, hm = by_w["2H_AXE_AVALON"], by_w[HEAVY_MACE]
    rest = [w for w in roads7 if w != "2H_AXE_AVALON"]
    rec_rb = next(r for r in er7.recommend(rest, top_n=300)
                  if r["weapon"] == "2H_AXE_AVALON")
    check("T17 swap advisor: ZvZ axe flagged in roads, options offered, "
          "score consistent with recommend()",
          rb["rank"] > 2 * hm["rank"] and len(rb["options"]) == 3
          and all(o["gain"] > 0 for o in rb["options"])
          and abs(rb["score"] - rec_rb["score"]) < 1e-9,
          f"realmbreaker rank {rb['rank']} vs heavy mace {hm['rank']}; "
          f"options={[o['display_name'] for o in rb['options']]}")

    # T18 — geometric AoE utility (2026-08-20 expert ruling, MECHANICS_TODO):
    # an AoE effect does one target's worth of work PER ENEMY REACHED.
    # Soulscythe's catch is Tornado's 80% slow in a 7m circle; Battleaxe's is
    # a self-only +40% move speed (Adrenaline Boost). Identical ordinal
    # scores (catch 1), so before this layer they tied at every size — the
    # motivating failure. Pinned: at 20-man+, AoE-delivered catch counts
    # ~3x a self-buff catch (reach-capped); in a small gang the gap nearly
    # closes; the flat self-buff never scales.
    SOULSCYTHE, BATTLEAXE = "2H_TWINSCYTHE_HELL", "MAIN_AXE"
    e_big = Engine(content="blackzone_roam", size=20, style="balanced")
    e_small = Engine(content="roads", size=5, style="balanced")
    catch_of = lambda e, w: max(x.get("catch", 0.0) for x in e._combo_extras(w))
    ss_big, ba_big = catch_of(e_big, SOULSCYTHE), catch_of(e_big, BATTLEAXE)
    ss_small, ba_small = catch_of(e_small, SOULSCYTHE), catch_of(e_small, BATTLEAXE)
    check("T18 geometric catch: AoE ~3x self-buff at 20, gap closes small",
          ss_big > 2.5 * ba_big and abs(ba_big - 1.0) < 1e-9
          and ss_small < 0.6 * ss_big and abs(ba_small - 1.0) < 1e-9,
          f"soulscythe@20={ss_big:.2f} battleaxe@20={ba_big:.2f} "
          f"soulscythe@5={ss_small:.2f} battleaxe@5={ba_small:.2f}")

    # T18b — CC-duration escalation composes ON TOP of geometry exactly when
    # the dumps carry a duration factor (extraction pin: Bow's Ray of Light /
    # GROUNDARROW — on the wiki CC list — carries 0.08). The compose itself
    # is pinned with a wide footprint (radius 7 -> reach past the anchor):
    # with the factor the multiplier must exceed the same footprint without
    # it; a small footprint (3m -> reach == anchor) must stay exactly 1.
    bow_root = E.weapons["2H_BOW"].get("cap_delivery", {}).get("root")
    wide = {"radius": 7.0, "escalation": {"duration": 0.08}}
    check("T18b CC escalation: duration factor composes above pure geometry",
          bow_root is not None
          and (bow_root.get("escalation") or {}).get("duration", 0) > 0
          and e_big._geo_mult("root", wide)
          > e_big._geo_mult("root", {"radius": 7.0}) + 1e-9
          and abs(e_big._geo_mult("root", bow_root) - 1.0) < 1e-9,
          f"bow={bow_root} wide={e_big._geo_mult('root', wide):.3f} "
          f"geo_only={e_big._geo_mult('root', {'radius': 7.0}):.3f}")

    # T19 — expert ruling 2026-08-20 (applied via MASTERSHEET tune:sheets):
    # Bedrock Mace over Iron-clad for anti_dive. Primal Slam's 18m
    # CC-resist-ignoring throw leaves a PERSISTENT WALL — fire-and-forget
    # peel on a support-tank kit — while Iron-clad's whirlwind must
    # physically contact the diver while channeling. Raw magnitude alone
    # (18m vs 12m) missed the delivery nuance; the ruling pins it.
    bed = E.caps_of("MAIN_ROCKMACE_KEEPER").get("anti_dive", 0)
    iron = E.caps_of("2H_IRONCLADEDSTAFF").get("anti_dive", 0)
    check("T19 Bedrock wall > Iron-clad contact-spin for anti_dive",
          bed == 6 and iron == 2,
          f"bedrock={bed} ironclad={iron} (mastersheet override)")

    # T20 — full-build members (2026-08-20): person contribution = weapon
    # loadout + helmet/armor/shoes ability + cape + offhand + potion + food.
    # A guild-doctrine brawl support-tank build (1H Mace + Cleric Cowl +
    # Duskweaver Armor + Stalker Shoes + Caitiff Shield + Smuggler Cape +
    # Gigantify + Beef Stew) must add real supply on top of the bare weapon,
    # and the gear layer must flow through the same physics (Cleric Cowl's
    # Force Field carries delivery facts like any weapon AoE).
    BUILD = ["HEAD_CLOTH_SET2", "ARMOR_PLATE_FEY", "SHOES_LEATHER_MORGANA",
             "OFF_SHIELD_HELL", "CAPEITEM_SMUGGLER", "T7_POTION_REVIVE",
             "T8_MEAL_STEW"]
    bare = E.member_extra("MAIN_MACE")
    full = E.build_extra("MAIN_MACE", None, BUILD)
    gained = {c: round(full.get(c, 0) - bare.get(c, 0), 2)
              for c in full if full.get(c, 0) > bare.get(c, 0) + 1e-9}
    f_bare = E.fitness(["MAIN_MACE", HALLOWFALL])
    f_full = E.fitness(["MAIN_MACE", HALLOWFALL], None, [BUILD, None])
    check("T20 full-build member: gear adds supply and fitness",
          full.get("knockback_displace", 0) > bare.get("knockback_displace", 0)
          and full.get("tankiness", 0) > bare.get("tankiness", 0)
          and len(gained) >= 4 and f_full > f_bare + 1e-9
          and E.gear["HEAD_CLOTH_SET2"].get("cap_delivery", {})
                .get("knockback_displace") is not None,
          f"gained={gained} fitness {f_bare:.2f}->{f_full:.2f}")

    # T21 — build-stat coherence (the expert's founding gear example): item
    # stats MODIFY the person. Robe of Purity (+50% damage/heal, thin armor)
    # multiplies a DPS's damage supply by ~1.5x but gives a control tank
    # with no damage caps almost nothing, while Judicator Armor's 287
    # armor+MR adds tankiness either way — "Heavy Mace on cloth defeats its
    # purpose" is now a computable statement.
    CLOTH, PLATE = ["ARMOR_CLOTH_AVALON"], ["ARMOR_PLATE_KEEPER"]
    km = "2H_CLAYMORE_AVALON"
    km_bare = E.member_extra(km).get("burst_aoe", 0.0)
    km_cloth = E.build_extra(km, None, CLOTH).get("burst_aoe", 0.0)
    hm_bare = E.member_extra(HEAVY_MACE)
    hm_cloth = E.build_extra(HEAVY_MACE, None, CLOTH)
    hm_plate = E.build_extra(HEAVY_MACE, None, PLATE)
    dps_gain_cloth = km_cloth - km_bare
    tank_gain_cloth = sum(hm_cloth.get(c, 0) for c in ("burst_aoe", "burst_st"))
    check("T21 build stats modify the person: cloth multiplies DPS, not tanks",
          km_cloth > km_bare * 1.4
          and hm_plate.get("tankiness", 0) > hm_bare.get("tankiness", 0) + 0.5
          and dps_gain_cloth > 0.9 and tank_gain_cloth < 0.5,
          f"Kingmaker burst_aoe {km_bare:.2f}->{km_cloth:.2f} (cloth); "
          f"HeavyMace tankiness {hm_bare.get('tankiness', 0):.2f}->"
          f"{hm_plate.get('tankiness', 0):.2f} (plate), cloth dmg gain "
          f"{tank_gain_cloth:.2f}")

    # T22 — kit advisor (2026-08-20; re-pinned 2026-08-27, owner ruling
    # "search more comps to see what tanks are actually wearing"): the
    # comp-aware tank head must come from the OBSERVED doctrine tier (the
    # weapon's own builds, then the seat's) — never an off-tier piece the
    # exact marginal likes because its caps are scarce in this comp. The
    # full gear catalog made Mercenary Hood / Graveguard Helmet win exactly
    # that way (the owner: nobody fields those on tanks), so comp-aware
    # ranking went doctrine-tier-first. Every slot still returns ranked
    # options with finite values for any weapon.
    e_kit = Engine(content="castle", size=25, style="brawl")
    kit_party = (["2H_MACE", "2H_HAMMER", "MAIN_ROCKMACE_KEEPER",
                  "2H_POLEHAMMER", "MAIN_MACE", "2H_QUARTERSTAFF",
                  HALLOWFALL, "2H_HOLYSTAFF_UNDEAD", "2H_NATURESTAFF_HELL",
                  "2H_NATURESTAFF_KEEPER", "2H_CLEAVER_HELL",
                  "MAIN_SPEAR_KEEPER", "2H_ROCKSTAFF_KEEPER", PERMAFROST,
                  "2H_ARCANESTAFF_HELL", WITCHWORK, "2H_GLAIVE",
                  "2H_DUALAXE_KEEPER", "2H_KNUCKLES_KEEPER",
                  "2H_DUALSICKLE_UNDEAD", BLOODLETTER, "2H_SCYTHE_HELL",
                  LONGBOW, "2H_FIRE_RINGPAIR_AVALON"])
    tank_kit = e_kit.kit_options(HEAVY_MACE, party=kit_party)
    marginal_bait = {"HEAD_LEATHER_SET1", "HEAD_PLATE_UNDEAD"}
    slots_ok = all(tank_kit["options"].get(s)
                   for s in ("head", "armor", "shoes", "offhand",
                             "cape", "potion", "food"))
    check("T22 kit advisor: comp-aware tank head comes from the observed "
          "doctrine tier, never off-tier marginal bait; all slots ranked",
          tank_kit["kit"]["head"]["doctrine"] in ("weapon", "seat")
          and tank_kit["kit"]["head"]["gear"] not in marginal_bait
          and slots_ok,
          f"tank head={tank_kit['kit']['head']['display_name']} "
          f"(doctrine={tank_kit['kit']['head']['doctrine']}); "
          f"slots={sorted(tank_kit['options'])}")

    # T23 — comp identity (V3 round 1 finding F-V3-2, 2026-08-23): what a
    # party is BECOMING, in playstyle vocabulary — descriptive only, no
    # scoring path reads it. Pinned to the style-DECLARED evidence: blap is
    # a brawl ball (Timothy: "(brawl comp)", 90% melee damage); the golden
    # clap10/kite10 fixtures read their own styles; and the V3 case-6 party
    # the expert called "clashing playstyles" reads as a split identity
    # with the melee-minority Battleaxe flagged as the seam.
    id_blap = e_bz.comp_identity(blap)
    id_clap = e_bz.comp_identity(clap10)
    id_kite = e_bz.comp_identity(kite10)
    check("T23 identity: blap reads brawl, clap10 reads clap, kite10 reads kite",
          id_blap["style"] == "brawl" and id_blap["strength"] == "strong"
          and id_clap["style"] == "clap" and id_kite["style"] == "kite",
          f"blap={id_blap['label']} ({id_blap['melee_share']:.0%} melee) "
          f"clap10={id_clap['label']} kite10={id_kite['label']}")
    # v2 verdict for case 6 (2026-08-23, weapon-level identity): Battleaxe
    # derives FLEX (Axe Throw reaches 18m), so the melee-vs-ranged split
    # heuristic no longer fires — instead the comp resolves kite-leaning
    # and Battleaxe is flagged UNFIT by the owner's own ruling ("doesn't
    # fit group play styles bigger than 3"), which names the actual clash
    # more precisely than the v1 split label did.
    case6 = ["MAIN_AXE", "2H_ENIGMATICSTAFF", "2H_SHAPESHIFTER_KEEPER",
             "2H_REPEATINGCROSSBOW_UNDEAD", "2H_DUALHAMMER_HELL"]
    id6 = Engine(content="castle_outpost", size=7).comp_identity(case6)
    check("T23b identity: the expert's 'clashing' case-6 party flags "
          "Battleaxe as unfit at 7 (owner ruling), Battleaxe clean at 3",
          [(c["weapon"], c["kind"]) for c in id6["conflicts"]]
          == [("MAIN_AXE", "unfit")]
          and Engine(content="castle_outpost", size=3).comp_identity(
              case6[:3])["conflicts"] == [],
          f"label={id6['label']} conflicts="
          f"{[(c['display_name'], c['kind']) for c in id6['conflicts']]}")
    check("T23c identity is descriptive only: tiny parties are 'forming', "
          "and computing it never touches fitness",
          Engine(content="roads", size=3).comp_identity(["2H_BOW_AVALON"])["style"] is None
          and abs(e_bz.fitness(blap) - f_blap) < 1e-12,
          f"fitness unchanged at {f_blap:.4f}")
    # T24 — style-aware kits (identity Phase C, owner ruling: "a siegebow
    # or a great axe, or longbow etc playing in brawl comp don't work if
    # they are on cloth armor"): under a DECLARED brawl the kit advisor
    # never SUGGESTS cloth armor for a damage carrier; healers are exempt
    # (their doctrine armor is cloth); balanced declares no intent and
    # keeps the full catalogue.
    e_brl = Engine(content="blackzone_roam", size=20, style="brawl")
    lb_all = [o["gear"] for o in
              e_brl.kit_options(LONGBOW, top_n=300)["options"]["armor"]]
    heal_all = [o["gear"] for o in
                e_brl.kit_options(HALLOWFALL, top_n=300)["options"]["armor"]]
    bal_all = [o["gear"] for o in
               ez.kit_options(LONGBOW, top_n=300)["options"]["armor"]]
    check("T24 brawl kits: no cloth suggested for a ranged carrier; "
          "healers exempt; balanced ungated",
          all("_CLOTH_" not in g for g in lb_all)
          and any("_CLOTH_" in g for g in heal_all)
          and any("_CLOTH_" in g for g in bal_all),
          f"brawl longbow armors={lb_all[:4]}...; healer has cloth="
          f"{any('_CLOTH_' in g for g in heal_all)}")

    # T23d — the all-rounder rule: Realmbreaker (melee stat line, E lands
    # at range -> flex, group-scale) DERIVES as fitting every style and is
    # never flagged inside a ranged core; its member record says so.
    rng_core = ["2H_AXE_AVALON", "2H_LONGBOW", "2H_BOW", "MAIN_FROSTSTAFF",
                HALLOWFALL]
    idr = Engine(content="castle_outpost", size=7).comp_identity(rng_core)
    rb_m = next(m for m in idr["members"] if m["weapon"] == "2H_AXE_AVALON")
    check("T23d Realmbreaker is the all-rounder: flex side, fits, never a "
          "conflict in a ranged core",
          rb_m["side"] == "flex" and rb_m["fit"] == "fits"
          and not any(c["weapon"] == "2H_AXE_AVALON"
                      for c in idr["conflicts"]),
          f"member={rb_m} conflicts={[c['display_name'] for c in idr['conflicts']]}")

    # T23e — label round rulings (owner, 2026-08-23): a near-monoculture
    # ranged burst comp is a BOMB SQUAD — "these guys are normally not part
    # of main party but support main party by doing damage off timers" — a
    # detachment archetype, not an ordinary clap (pinned on the real
    # KroozLT19 6x-Wailing-Bow comp). And the Harpoon ruling: pierce +
    # damage_debuff are group jobs in their own right, so the pierce-bot
    # carries a group slot as 'situational', never 'unfit'. REFINED round 7
    # (owner 2026-08-24): "spirithunter is great in clap and clap kite ...
    # it has a massive pierce that enables the whole dps line" — the clap
    # halves promote to FITS (cited override); brawl/kite keep situational.
    # Battleaxe (the explicit owner override) stays the only weapon barred
    # from every style at group scale.
    bomb = ["2H_BOW_HELL", "MAIN_ARCANESTAFF_UNDEAD", "MAIN_CURSEDSTAFF_UNDEAD",
            "2H_BOW_HELL", "2H_BOW_HELL", "2H_BOW_HELL", "2H_BOW_HELL",
            "2H_BOW_HELL"]
    id_bomb = Engine(content="blackzone_roam", size=8).comp_identity(bomb)
    harpoon_fit = E.weapons["2H_HARPOON_HELL"]["style_fit"]["fit"]
    check("T23e bomb-squad archetype + the Harpoon pierce ruling "
          "(round-7 refinement: clap halves fit, brawl/kite situational)",
          id_bomb.get("archetype") == "bomb_squad"
          and id_bomb["style"] == "clap"
          and "Bomb squad" in id_bomb["label"]
          and all(harpoon_fit[s]["group"] == "situational"
                  for s in ("brawl", "kite", "brawl_clap"))
          and harpoon_fit["clap"]["group"] == "fits"
          and harpoon_fit["clap_kite"]["group"] == "fits",
          f"label={id_bomb['label']} harpoon clap="
          f"{harpoon_fit['clap']['group']} brawl={harpoon_fit['brawl']['group']}")

    # T23f — blind labels 3/4 + the owner's follow-up refinement
    # (2026-08-23): both 20-man comps "have both clap potential and kite
    # potential" — CLAP-KITE is its own playstyle (bomb from range, reset
    # on cooldowns; the ranged twin of brawl-clap). Detection: real bomb
    # share (>=0.40) AND real reset mobility (>=2 evade pts/member) in a
    # ranged core. Also pinned from the round: a pierce-bot (Spirithunter,
    # the Harpoon ruling) never anchors a damage-identity split — that
    # miss is what exposed the 20v20's true read. The pure fixtures stay
    # pure: clap10 has the bombs but not the legs (1.8 evade/m), kite10
    # the legs but not the bombs.
    dh1_id = Engine(content="territory_defense", size=len(dh1)).comp_identity(dh1)
    c20 = _comp_party("albioncompo_20v20_competitive_2026_08", 0)
    c20_id = Engine(content="blackzone_roam", size=len(c20)).comp_identity(c20)
    check("T23f both real 20-man comps read clap-kite (owner refinement); "
          "pure clap10/kite10 stay pure; no pierce-bot split",
          dh1_id["style"] == "clap_kite" and c20_id["style"] == "clap_kite"
          and c20_id["conflicts"] == []
          and id_clap["style"] == "clap" and id_kite["style"] == "kite",
          f"DH={dh1_id['style']} 20v20={c20_id['style']} "
          f"({c20_id['melee_share']:.0%} melee)")

    # T25 — kill pressure (identity Phase D, owner checklist 2026-08-23):
    # "did we bring pierce on the clump, did we give heal cuts, did we do
    # enough damage within a short span to actually kill." The lights are
    # a lens over the comp-fitted targets. Pinned: the real blap comp is
    # ready on all three; the owner's own counter-example — 20 tanks —
    # is lacking on all three ("20 tanks hitting enemy tank will probably
    # not be able to kill"); a burst-only trio shows burst green with
    # pierce/heal-cut red (the checklist separates, not just sums).
    kp_blap = e_bz.kill_pressure(blap)
    kp_tanks = e_bz.kill_pressure([HEAVY_MACE] * 20)
    kp_trio = E.kill_pressure([LONGBOW, WITCHWORK, PERMAFROST])
    check("T25 kill pressure: blap ready on all three lights; 20 Heavy "
          "Maces lacking on all three",
          kp_blap["verdict"] == "ready"
          and all(kp_blap[k]["ok"] for k in ("pierce", "heal_cut", "burst"))
          and kp_tanks["verdict"] == "lacking"
          and not any(kp_tanks[k]["ok"] for k in ("pierce", "heal_cut", "burst")),
          f"blap={kp_blap['verdict']} tanks={kp_tanks['verdict']} "
          f"(tank burst {kp_tanks['burst']['have']:.1f}/"
          f"{kp_tanks['burst']['bar']:.1f})")
    check("T25b kill pressure separates the lights: a burst trio is green "
          "on burst, red on pierce and heal-cut — and none of it scores "
          "(fitness unchanged)",
          kp_trio["burst"]["ok"] and not kp_trio["pierce"]["ok"]
          and not kp_trio["heal_cut"]["ok"]
          and abs(e_bz.fitness(blap) - f_blap) < 1e-12,
          f"trio={{'pierce': {kp_trio['pierce']['ok']}, "
          f"'heal_cut': {kp_trio['heal_cut']['ok']}, "
          f"'burst': {kp_trio['burst']['ok']}}}")

    # T26 — fight chain (roadmap item 1, owner vocabulary): the fight as
    # the playstyle sequences it, graded against the comp-fitted targets.
    # Pinned: the real blap ball reads STRONG on every brawl stage
    # (contact -> pressure -> sustain -> denial -> secure); a healer-less
    # pierce-less brawl five reads weak/missing and the pierce weapon
    # (Carving) connects to the Pressure stage; a healer's value lies
    # OUTSIDE the chain (survival, not a stage) so no connection is
    # claimed; balanced falls back to the detected identity's chain; and
    # computing chains never touches fitness.
    e_brl20 = Engine(content="blackzone_roam", size=20, style="brawl")
    fc_blap = e_brl20.fight_chain(blap)
    brawl5 = [HEAVY_MACE, GREAT_HAMMER, "MAIN_HOLYSTAFF",
              "2H_DUALSCIMITAR_UNDEAD", "2H_CLAYMORE"]
    fc5 = e_brl20.fight_chain(brawl5, candidate="2H_CLEAVER_HELL")
    fc_heal = E.fight_chain([LONGBOW, WITCHWORK, PERMAFROST],
                            candidate=HALLOWFALL)
    fc_bal = ez.fight_chain(clap10)
    check("T26 fight chain: blap all-strong on the brawl sequence; a thin "
          "brawl five grades weak; Carving connects to Pressure",
          fc_blap["style"] == "brawl"
          and all(s["verdict"] == "strong" for s in fc_blap["stages"])
          and any(s["verdict"] in ("weak", "missing") for s in fc5["stages"])
          and (fc5["improves"] or {}).get("stage") == "Pressure",
          f"blap={[s['verdict'] for s in fc_blap['stages']]} "
          f"five={[s['verdict'] for s in fc5['stages']]} "
          f"carving->{(fc5['improves'] or {}).get('stage')}")
    check("T26b chain honesty: a healer claims no chain stage (its value "
          "is survival); balanced uses the detected identity's chain; "
          "fitness untouched",
          fc_heal is not None and fc_heal["improves"] is None
          and fc_bal is not None and fc_bal["style"] == "clap"
          and abs(e_bz.fitness(blap) - f_blap) < 1e-12,
          f"heal_improves={fc_heal['improves']} bal_style={fc_bal['style']}")

    # T26c — stage sources + named improves terms (2026-08-24, from a user
    # not being able to reconcile "strengthens Reset" with gain tiles that
    # led with other capabilities): every graded stage lists the equipped
    # spells that ARE it, each source citing a real spell of that weapon's
    # loadout (or its always-on kit), and the improves claim names the
    # per-cap terms behind its sum.
    con = next(s for s in fc_blap["stages"] if s["name"] == "Contact")

    def cites_real_spell(r):
        if r["spell"] is None:
            return r["slot"] is None   # the weapon's always-on kit
        lo = e_brl20.weapons[r["weapon"]].get("loadout") or {}
        names = lo.get("slot_names") or []
        spells = lo.get("slot_spells") or []
        return r["slot"] in names and \
            r["spell"] in spells[names.index(r["slot"])]
    src_ok = bool(con["sources"]) and all(
        cites_real_spell(r) and r["cap"] in con["caps"] and r["units"] > 0
        for r in con["sources"])
    imp = fc5["improves"] or {}
    check("T26c chain sources: Contact lists the blap ball's real engage/"
          "tank spells; improves names its terms (Carving -> Pressure = "
          "its shred + dps, summed)",
          src_ok and imp.get("terms")
          and set(t["cap"] for t in imp["terms"])
          <= set(next(s["caps"] for s in fc5["stages"]
                      if s["name"] == "Pressure"))
          and abs(sum(t["gain"] for t in imp["terms"]) - imp["gain"]) < 1e-9,
          f"contact_sources={len(con['sources'])} "
          f"imp_terms={[(t['cap'], t['gain']) for t in imp.get('terms') or []]}")

    # T27 — forge-quality blind round (owner rulings 2026-08-23). The
    # engine's darlings were overruled on ECONOMICS and E-identity, with
    # the killboard sample corroborating (Exalted 0/0/5, Forgebark 0/0/2
    # observed small/mid/large): crystal weapons leave the default pools
    # below 30 players ("I wouldn't run it unless there were 30+ people
    # involved"); Great Holy is brawl-only ("it has to stop moving and
    # needs everyone to clump in place to heal with e — that's not good"
    # for clap); a hybrid healer can never be the sole healing foundation
    # ("too expensive to be the only healer ... the weapon needs to have
    # high healing numbers on its e"). Contract details are pinned in
    # tests/test_forge.py F14-F16; this golden pins the expert calls at
    # the suggestion surface where the blind round saw them.
    e_clap10 = Engine(content="blackzone_roam", size=10, style="clap")
    clap_pool = set(e_clap10.suggest_pool())
    e_brawl20 = Engine(content="blackzone_roam", size=20, style="brawl")
    brawl_pool = set(e_brawl20.suggest_pool())
    check("T27 owner rulings: no Exalted/Forgebark below 30, Great Holy "
          "barred from clap suggestions yet kept for brawl",
          "2H_HOLYSTAFF_CRYSTAL" not in clap_pool
          and "MAIN_NATURESTAFF_CRYSTAL" not in clap_pool
          and GREAT_HOLY not in clap_pool
          and HALLOWFALL in clap_pool
          and GREAT_HOLY in brawl_pool
          and "2H_HOLYSTAFF_CRYSTAL" not in brawl_pool,
          f"clap10 has GH={GREAT_HOLY in clap_pool} "
          f"brawl20 has GH={GREAT_HOLY in brawl_pool}")
    check("T27b full-healer split matches the owner's named cases "
          "(Forgebark/Exalted hybrids, Great Holy/Redemption full)",
          E.weapons[GREAT_HOLY]["full_healer"]
          and E.weapons["2H_HOLYSTAFF_UNDEAD"]["full_healer"]
          and E.weapons[HALLOWFALL]["full_healer"]
          and not E.weapons["MAIN_NATURESTAFF_CRYSTAL"]["full_healer"]
          and not E.weapons["2H_HOLYSTAFF_CRYSTAL"]["full_healer"],
          f"full={sorted(k for k, w in E.weapons.items() if w.get('full_healer'))}")
    # T27c — round 2 refinement (owner 2026-08-23): "1 hand holy is full
    # healer but it's not a good group healer for anything larger than 5
    # people. I would use it at 3 people and very rarely at 5 but never
    # above that ... it should all be based on what the weapon does and its
    # effect — I don't want to set custom rules for individual weapons."
    # STRUCTURAL: the E heal's own area facts split group from single
    # (Desperate Prayer heals one ally; Divine Jump / Celestial Sphere heal
    # areas — cited sub-effect fact-corrections in heal_overrides.yaml).
    # Single-scale dedicated heal Es grade gang situational / group unfit
    # — the same E-first ladder as single-scale damage. Druidic's single-
    # target ultimate moves it out of the foundation set by structure alone.
    holy1 = "MAIN_HOLYSTAFF"
    sf_holy = E.weapons[holy1]["style_fit"]["fit"]
    check("T27c heal scale is structural: 1H Holy single (trio fine, group "
          "unfit), Hallowfall/Redemption group via cited fact-override, "
          "Druidic out of the foundation set",
          E.weapons[holy1]["heal_scale"] == "single"
          and not E.weapons[holy1]["full_healer"]
          and all(sf_holy[s]["trio"] == "fits"
                  and sf_holy[s]["gang"] == "situational"
                  and sf_holy[s]["group"] == "unfit"
                  for s in ("brawl", "clap", "kite"))
          and E.weapons[HALLOWFALL]["heal_scale"] == "group"
          and E.weapons["2H_HOLYSTAFF_UNDEAD"]["heal_scale"] == "group"
          and E.weapons["MAIN_NATURESTAFF_KEEPER"]["heal_scale"] == "single"
          and not E.weapons["MAIN_NATURESTAFF_KEEPER"]["full_healer"],
          f"1H_Holy scale={E.weapons[holy1]['heal_scale']} "
          f"group_verdict={sf_holy['brawl']['group']} "
          f"druidic_scale={E.weapons['MAIN_NATURESTAFF_KEEPER']['heal_scale']}")

    # T28 — round 3 gradings (owner 2026-08-23): "faction war comp is bad
    # because it has dagger and boltcaster, both of which can only damage 1
    # person at a time with e and that's not good for anything higher than
    # 3v3, heavy crossbow at least can do damage through people with e."
    # Every weapon the owner killed derived SITUATIONAL for its context;
    # every weapon passed derived FITS — the generation-fit gate makes the
    # forge honor the derivation (F17 pins the mechanics; this pins the
    # expert case at the suggestion surface).
    e_fw = Engine(content="faction_war", size=15)
    fw_pool = set(e_fw.suggest_pool())
    fw_names = {e_fw.weapons[k]["display_name"] for k in fw_pool}
    check("T28 owner ruling: single-target-E dps (Dagger, Boltcasters) "
          "leave 15-man suggestions; Heavy Crossbow's pierce stays",
          "Dagger" not in fw_names and "Boltcasters" not in fw_names
          and "Heavy Crossbow" in fw_names,
          f"dagger_in={'Dagger' in fw_names} bolt_in={'Boltcasters' in fw_names} "
          f"hxbow_in={'Heavy Crossbow' in fw_names}")
    # T28b — round 4 (owner 2026-08-23): "there is no way 1hand holy
    # healer should be in a 15 man party when I said no way above 5 and
    # there is no chance above 9." Single-ally-heal-E healers leave
    # GENERATION at group sizes even under balanced; gang stays open (the
    # Druidic ruling) and trio is untouched.
    e7g = Engine(content="castle_outpost", size=7)
    check("T28b owner ruling: 1H Holy never generated at 10+ (balanced "
          "included); still open at gang sizes",
          "Holy Staff" not in fw_names
          and "Druidic Staff" not in fw_names
          and "MAIN_HOLYSTAFF" in set(e7g.suggest_pool()),
          f"holy_in_15={'Holy Staff' in fw_names} "
          f"holy_at_7={'MAIN_HOLYSTAFF' in set(e7g.suggest_pool())}")

    # T29 — round 4 (owner 2026-08-24): "flex bomber like hellfire, it's
    # usually a brawl-clap weapon and not a clap option. realmbreaker gives
    # multiple things like health cut, range e, easy way to engage followup
    # — that's why it can work in clap." Cited override drops Hellfire's
    # clap verdict to situational; the generation-fit gate keeps it out of
    # DEFAULT clap comps while brawl-clap (its home) and manual picks keep
    # it; Realmbreaker stays a derived clap fit.
    e_c15 = Engine(content="blackzone_roam", size=15, style="clap")
    e_bc15 = Engine(content="blackzone_roam", size=15, style="brawl_clap")
    hell = "2H_KNUCKLES_HELL"
    check("T29 owner ruling: Hellfire out of clap generation, home in "
          "brawl-clap; Realmbreaker keeps its clap slot",
          hell not in set(e_c15.suggest_pool())
          and hell in set(e_bc15.suggest_pool())
          and "2H_AXE_AVALON" in set(e_c15.suggest_pool()),
          f"hell_clap={hell in set(e_c15.suggest_pool())} "
          f"hell_bc={hell in set(e_bc15.suggest_pool())}")

    # T30 — negative recommendations / redundancy warnings (roadmap item 3,
    # 2026-08-24). The verdict layer is a DESCRIPTIVE lens over the exact
    # pick marginal — a scoring-side redundancy penalty was tried and
    # REJECTED (MECHANICS_TODO Q18), so these pins hold the lens honest:
    # the report's terms ARE the score, and computing it changes nothing.
    heal_sat = [HALLOWFALL, GREAT_HOLY, HEAVY_MACE, PERMAFROST]
    rep = E.pick_report(heal_sat, "MAIN_HOLYSTAFF")
    w = E.scoring["weights"]
    recon = (w["alpha"] * rep["d_fitness"] + w["beta"] * rep["d_synergy"]
             + w["delta"] * rep["meta_prior"]
             + w.get("viability", 0.0) * rep["viability"] - rep["dup_penalty"])
    rowsum = sum(r["coverage"] + r["floor_lift"] - r["overstack_cost"]
                 for r in rep["caps"])
    check("T30 pick_report terms reconstruct the exact pick score (1e-9)",
          abs(recon - rep["score"]) < 1e-9
          and abs(rowsum - rep["d_fitness"]) < 1e-9,
          f"score={rep['score']:.4f} recon_err={abs(recon - rep['score']):.1e} "
          f"dfit_err={abs(rowsum - rep['d_fitness']):.1e}")

    # a third healer into a heal-saturated party warns; the same healer into
    # 3 DPS is the engine's own top advice and reads clean
    rep_ok = E.pick_report([LONGBOW, WITCHWORK, PERMAFROST], HALLOWFALL)
    check("T30b verdicts: third healer into saturated heals warns (closes "
          "no gap); healer into 3 DPS reads ok",
          rep["verdict"] in ("redundant", "negative") and rep["caps_gain"] < 0.5
          and rep_ok["verdict"] == "ok" and rep_ok["caps_gain"] > 5
          and any(r["saturated"] for r in rep["caps"]),
          f"sat3rd={rep['verdict']}/{rep['caps_gain']:.2f} "
          f"gapfill={rep_ok['verdict']}/{rep_ok['caps_gain']:.1f}")

    # exact duplicates past the free allowance price in and go negative.
    # RE-PINNED 2026-08-27 (dressed forge, owner ruling): the fixture
    # party wears its own doctrine kits — the real-world case; against a
    # NAKED four-stack the 5th Longbow's kit closes ~28 units of real
    # gaps and the engine honestly says so (pinned below as the model's
    # documented honesty, not a bug).
    lb_kit = dict(E.kit_variants(LONGBOW))["v0"]
    lb4 = [LONGBOW, LONGBOW, LONGBOW, LONGBOW]
    rep_dup = E.pick_report(lb4, LONGBOW, None, [lb_kit] * 4)
    check("T30c a 5th Longbow into a DRESSED four-stack is a negative "
          "recommendation (dup penalty priced, zero gap-closing)",
          rep_dup["verdict"] == "negative" and rep_dup["score"] <= 0
          and rep_dup["dup_penalty"] > 0 and rep_dup["caps_gain"] < 0.05,
          f"score={rep_dup['score']:.3f} dup_pen={rep_dup['dup_penalty']:.2f} "
          f"caps_gain={rep_dup['caps_gain']:.3f}")
    rep_naked = E.pick_report(lb4, LONGBOW)
    check("T30c honesty rider: against a NAKED four-stack the 5th's KIT "
          "closes real gaps and the verdict says so",
          rep_naked["caps_gain"] > 5 and rep_naked["verdict"] != "negative",
          f"score={rep_naked['score']:.3f} "
          f"caps_gain={rep_naked['caps_gain']:.2f}")

    # swap review carries the same lens per member — but its question is
    # "does the REST cover this member's jobs without it?", so with TWO
    # healers neither is redundant (dropping either reopens the gap); a
    # THIRD healer is. analyze carries the saturation band; and none of it
    # touches fitness (descriptive only).
    three_heal = [HALLOWFALL, GREAT_HOLY, "MAIN_HOLYSTAFF", HEAVY_MACE]
    f_before = E.fitness(three_heal)
    sr2 = {m["weapon"]: m for m in E.swap_review(heal_sat)}
    sr3 = {m["weapon"]: m for m in E.swap_review(three_heal)}
    an = E.analyze(heal_sat)
    bands = {x["cap"]: x["band"] for x in an["strengths"]}
    check("T30d swap review: both of 2 healers load-bearing, a 3rd flagged "
          "redundant, the tank clean; analyze bands mark heals overstacked; "
          "fitness untouched by all of it",
          not sr2[GREAT_HOLY]["redundant"]
          and sr3["MAIN_HOLYSTAFF"]["redundant"]
          and not sr3[HEAVY_MACE]["redundant"]
          and bands.get("heal_sustain") == "overstacked"
          and E.fitness(three_heal) == f_before,
          f"2-healer greatholy={sr2[GREAT_HOLY]['verdict']} "
          f"3rd-healer={sr3['MAIN_HOLYSTAFF']['verdict']} "
          f"heavymace={sr3[HEAVY_MACE]['verdict']} "
          f"heal_band={bands.get('heal_sustain')} "
          f"fitness stable at {f_before:.4f}")

    # T31 — round 7 (owner 2026-08-24): the two-prong E rule. Prong facts:
    # Battle Bracers' Falcon Smash DOES damage everyone it lands on (dump
    # text: 264 phys in a 4 radius — the sheet had never scored it; owner:
    # "battle bracers is not single target") -> group scale, back in group
    # pools, matching its 84% share of the observed ZvZ family. Warbow /
    # 1H Fire / Hellspawn are owner-ruled solo-class ("max effective at 3,
    # good/okay at 5, falls off hard"): out of 5+ generation, open at trio.
    # Energy Shaper ("super high damage ... great in large group fights")
    # and Greataxe ("its e can hit everyone in its vicinity ... okay")
    # stay. The weak-group-E derivation (low E damage AND no real E tool)
    # demotes only the scattered-utility class; Heavy-Mace-style utility
    # Es are protected by the AND.
    e20 = Engine(content="blackzone_roam", size=20)
    e5 = Engine(content="blackzone_roam", size=5)
    e3 = Engine(content="blackzone_roam", size=3)
    p20, p5, p3 = (set(e20.suggest_pool()), set(e5.suggest_pool()),
                   set(e3.suggest_pool()))
    solo = ("2H_WARBOW", "MAIN_FIRESTAFF", "2H_SHAPESHIFTER_HELL")
    bb = "2H_KNUCKLES_SET2"
    check("T31 round-7 E rule: Battle Bracers rejoins group pools (group-"
          "scale E, killboard-corroborated); Warbow/1H Fire/Hellspawn "
          "solo-class leave 5+; all open at trio; Energy Shaper/Greataxe "
          "stay",
          bb in p20 and e20.weapons[bb]["style_fit"]["damage_scale"] == "group"
          and all(w not in p20 and w not in p5 and w in p3 for w in solo)
          and "2H_CROSSBOW_CANNON_AVALON" in p20 and "2H_AXE" in p20,
          f"bb_in20={bb in p20} solo_out20={[w not in p20 for w in solo]} "
          f"solo_in3={[w in p3 for w in solo]}")

    # the AND protects utility Es: Heavy Mace (low-damage silence E) and
    # Carrioncaller (heal-cut E) keep their group verdicts; the demotion
    # catches only the no-tool class, and computing any of it never moved
    # a score the goldens above already pinned
    cc = "2H_HALBERD_MORGANA"
    hm_fit = e20.weapons[HEAVY_MACE]["style_fit"]["fit"]["brawl"]["group"]
    cc_fit = e20.weapons[cc]["style_fit"]["fit"]["brawl"]["group"]
    ice = e20.weapons["2H_ICEGAUNTLETS_HELL"]["style_fit"]  # Icicle: caught class
    check("T31b the AND rescues real tools: Heavy Mace + Carrioncaller "
          "keep group slots; the scattered-utility class (Icicle) demotes "
          "to situational, never unfit",
          hm_fit == "fits" and cc_fit == "fits"
          and ice["fit"]["brawl"]["group"] == "situational"
          and ice["fit"]["brawl"]["trio"] == "fits",
          f"heavy_mace={hm_fit} carrioncaller={cc_fit} "
          f"icicle={ice['fit']['brawl']}")

    # T31c — round-7 killboard cases closed (owner 2026-08-24): Spirithunter
    # generates for clap + clap_kite at 20 ("great in clap and clap kite ...
    # massive pierce that enables the whole dps line") while brawl stays
    # gated; Bloodletter stays OUT of group generation — its killboard
    # prominence is battlemount piloting + mobility, not a comp slot
    # ("isn't really used as fighting but as a mounted weapon"), the
    # recorded kill-event sampling bias made real; Galatine Pair stays IN
    # the pools with no special treatment ("great for solo bombs" — a
    # specialist play the templates don't demand, so the forge passing on
    # it is correct, not a gate).
    sp = "2H_HARPOON_HELL"
    e_c20 = Engine(content="blackzone_roam", size=20, style="clap")
    e_ck20 = Engine(content="blackzone_roam", size=20, style="clap_kite")
    e_b20 = Engine(content="blackzone_roam", size=20, style="brawl")
    check("T31c Spirithunter in clap/clap_kite pools at 20, out of brawl; "
          "Bloodletter out (mount-carrier artifact); Galatine Pair pooled",
          sp in set(e_c20.suggest_pool()) and sp in set(e_ck20.suggest_pool())
          and sp not in set(e_b20.suggest_pool())
          and BLOODLETTER not in set(e20.suggest_pool())
          and "2H_DUALSCIMITAR_UNDEAD" in set(e20.suggest_pool()),
          f"sp_clap={sp in set(e_c20.suggest_pool())} "
          f"sp_brawl={sp in set(e_b20.suggest_pool())} "
          f"bloodletter={BLOODLETTER in set(e20.suggest_pool())}")

    # T31d — E-audit follow-up rulings (owner 2026-08-24): Fists of Avalon's
    # purge raised to 4 via MASTERSHEET ("fist of ava purge can be a 4")
    # and it generates at 20 (the 232 area purge-punch, Battle Bracers'
    # sibling fix); Trinity Spear ruled OUT of large-scale generation —
    # "no one is doing auto attack damage usually so its never used in
    # large scale ... only a swap for hitting castle gates or terry
    # walls ... never as the main weapon in party" — group unfit by cited
    # override, gang keeps the derived verdict (the ruling names large
    # scale only), manual picks score as always.
    fists, trident = "2H_KNUCKLES_AVALON", "2H_TRIDENT_UNDEAD"
    e7bz = Engine(content="blackzone_roam", size=7)
    check("T31d E-audit rulings: Fists of Avalon purge 4 + in 20-man pools; "
          "Trinity Spear out of 20-man generation, open at gang",
          E.weapons[fists]["capabilities"].get("purge") == 4
          and fists in set(e20.suggest_pool())
          and trident not in set(e20.suggest_pool())
          and trident in set(e7bz.suggest_pool())
          and e20.weapons[trident]["style_fit"]["fit"]["brawl"]["group"] == "unfit",
          f"purge={E.weapons[fists]['capabilities'].get('purge')} "
          f"fists@20={fists in set(e20.suggest_pool())} "
          f"trident@20={trident in set(e20.suggest_pool())} "
          f"trident@7={trident in set(e7bz.suggest_pool())}")

    # T32 — conditional-payload rule (owner rulings 2026-08-26, the
    # melee-heavy clap radar round): clap wants damage delivered in ONE
    # action. Damage carriers whose E needs ramp (Clarent/Carving consume
    # Heroic Charges) or a held non-ranged channel (Ursine) leave clap
    # generation at 20; RANGED channels stay ("Longbow is nice clap over
    # wall", Energy Shaper "is good damage"), and support/tank seats are
    # untouched (Earthrune "very meta clump tank", Malevolent Locus "good
    # support weapon", Lifecurse/Blight/Enigmatic "fine supportive
    # weapons" — all damage_scale none). Brawl keeps the demoted melee
    # weapons ("clarent and ursine are both nice melee brawl weapons").
    clarent, ursine, carving = ("MAIN_SCIMITAR_MORGANA", "2H_KNUCKLES_KEEPER",
                                "2H_CLEAVER_HELL")
    c_pool, b_pool = set(e_c20.suggest_pool()), set(e_b20.suggest_pool())
    check("T32 conditional-payload: ramp/melee-channel damage Es leave clap-20 "
          "generation; ranged channels and support seats stay; brawl keeps them",
          clarent not in c_pool and ursine not in c_pool
          and carving not in c_pool
          and "2H_LONGBOW" in c_pool
          and clarent in b_pool and ursine in b_pool and carving in b_pool
          and E.weapons[clarent]["style_fit"]["fit"]["clap"]["group"] == "situational"
          and E.weapons["2H_LONGBOW"]["style_fit"]["fit"]["clap"]["group"] == "fits",
          f"clap20 clarent={clarent in c_pool} ursine={ursine in c_pool} "
          f"carving={carving in c_pool} longbow={'2H_LONGBOW' in c_pool}; "
          f"brawl20 keeps: {clarent in b_pool}/{ursine in b_pool}/{carving in b_pool}")

    # T33 — kite extension (owner "ok" 2026-08-26, same session): the
    # melee-heavy kite forge read "split identity" at 65% melee; the one
    # real kite 20-man (ss_kite_20) fields zero ramp/channel bruisers and
    # counts 5 ranged-AoE-core qualifiers. Conditional-payload now demotes
    # at kite too, and kite carries ranged_aoe_core min 5 at 20 (4 at
    # 15-19) — lower than clap's 7 because kite pressure includes curse/
    # sustained ranged damage the burst-AoE predicate does not count.
    e_k20 = Engine(content="blackzone_roam", size=20, style="kite")
    k_pool = set(e_k20.suggest_pool())
    k_rows = ((E.data["styles"].get("kite") or {}).get("constraint_overrides")
              or [])
    k20 = next((r for r in k_rows if r.get("min_size") == 20), {})
    check("T33 kite: conditional-payload demotes there too; ranged-AoE core "
          "min 5 armed at 20",
          clarent not in k_pool and ursine not in k_pool
          and carving not in k_pool
          and "2H_LONGBOW" in k_pool
          and E.weapons[ursine]["style_fit"]["fit"]["kite"]["group"] == "situational"
          and (k20.get("ranged_aoe_core") or {}).get("min") == 5,
          f"kite20 clarent={clarent in k_pool} ursine={ursine in k_pool} "
          f"carving={carving in k_pool} longbow={'2H_LONGBOW' in k_pool} "
          f"core_min={(k20.get('ranged_aoe_core') or {}).get('min')}")

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
