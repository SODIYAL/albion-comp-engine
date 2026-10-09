#!/usr/bin/env python3
"""
JS/Python engine parity — engine/app_scoring.js must produce the SAME
numbers and the SAME rankings as engine/engine.py, or the app is quietly
lying to its users while the golden suite stays green.

Seeded random parties across every content template; compares fitness,
synergy, top-5 recommendation order + scores, weakness order, and the
greedy-trap capability set. Exits 0 with a SKIP note when node is absent.

Run:  py -3 tests/test_js_parity.py
"""
import json, os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))

from engine import PARTY_CAP, Engine, party_cap_message  # noqa: E402

DATASET = os.path.join(ROOT, "pipeline", "out", "dataset-latest.json")
SCORING_JS = os.path.join(ROOT, "engine", "app_scoring.js")
RUNNER = os.path.join(HERE, "js_parity_runner.js")
EPS = 1e-9
N_CASES = 60
SEED = 20260812


def _combo_count(data, weapon):
    """Number of one-spell-per-slot combos, from the dataset alone (both
    engines derive the same enumeration from the same loadout record)."""
    lo = data["weapons"][weapon].get("loadout") or {}
    n = 1
    for slot in lo.get("slots") or []:
        if slot:
            n *= len(slot)
    return n


def make_cases(data):
    rng = random.Random(SEED)
    weapons = sorted(data["weapons"])
    contents = sorted(data["templates"])
    styles = sorted(data.get("styles") or {"balanced": {}})
    cases = []
    for i in range(N_CASES):
        content = contents[i % len(contents)]
        base = data["templates"][content]["base_size"]
        # Sizes must LEAVE base_size: at base the mechanics growth is the
        # identity and target scaling is a no-op, so an all-base suite is
        # blind to the whole size path — a real rounding divergence shipped
        # behind a green 60/60 that way. The variants
        # cover shrunk/grown scaling, the piecewise size-physics breakpoints
        # (10/14), and >30 for the large meta-prior bucket.
        size_opts = [base, max(2, base // 2), base + base // 2,
                     2 * base + 1, 10, 14]
        size = size_opts[(i // len(contents)) % len(size_opts)]
        n = rng.randint(0, min(size, 12))
        # refine() is a full-pool sweep PER SLOT PER PASS — far too slow to
        # run over all 137 weapons on every case, so each case carries a
        # deterministic pool subset that BOTH engines use. Steepest-descent
        # resolves ties by iteration order, so the pool must be an ordered
        # list, identical on both sides, not a set.
        pool = weapons[(i % 7)::11]
        party = [rng.choice(weapons) for _ in range(n)]
        # loadout locks: half the members carry a pinned combo
        # index — the archetype path must agree between engines too
        combos = [rng.randrange(_combo_count(data, w))
                  if rng.random() < 0.5 else None for w in party]
        # full-build members: a deterministic gear list per
        # member so the gear composition path is parity-tested too
        gear_keys = sorted(data.get("gear") or {})
        gears = None
        if gear_keys:
            gears = [[gear_keys[(i + j + k) % len(gear_keys)]
                      for k in range(3)] if j % 2 == 0 else []
                     for j in range(n)]
        cases.append({"content": content, "size": size,
                      "style": styles[i % len(styles)],
                      "party": party, "combos": combos, "gears": gears,
                      "refine_pool": pool})
    # the self-cost offset (Demon Armor, F1d): one wearer (a candidate
    # completing the pair earns the refund) and two (the candidate's own
    # cost is waived) — both ports must price the same exact marginal
    demon = ["HEAD_PLATE_SET3", "ARMOR_PLATE_HELL", "SHOES_PLATE_SET1"]
    if "ARMOR_PLATE_HELL" in (data.get("gear") or {}):
        # and a gears tail past the party, read as cut at its end (F38c)
        for party, gears in ((["2H_CURSEDSTAFF"], [demon]),
                             (["2H_CURSEDSTAFF", "2H_CURSEDSTAFF"], [demon, demon]),
                             (["2H_CURSEDSTAFF"], [demon, demon])):
            cases.append({"content": "blackzone_roam", "size": 20, "style": "balanced",
                          "party": party, "combos": [None] * len(party),
                          "gears": gears, "refine_pool": weapons[3::11]})
    # a matchmaking pool at 10+ (the Dragon Portal's 15-20 pool, F34j): the
    # pool's own rows outrank the style x size rows, and the size variants
    # above never reach a pool past 10 — both ports must read the same
    # targets there
    if "15-20" in ((data["templates"].get("ancient_lands") or {}).get("pool_rows") or {}):
        for size, style in ((15, "brawl"), (18, "clap"), (20, "balanced")):
            party = [rng.choice(weapons) for _ in range(10)]
            cases.append({"content": "ancient_lands", "size": size, "style": style,
                          "party": party, "combos": [None] * len(party),
                          "gears": None, "refine_pool": weapons[5::11]})
    # dressed members on the paths the random gear lists rarely reach (the
    # kits are the engine's doctrine variants, handed to both ports as
    # data): two count-once carriers in their kits on the shared spell
    # (F40) with a third candidate in the pool; clap10 with leather dps,
    # which the kits turn into a brawl (T26d); short per-member lists,
    # read as padded with None (F38)
    ek = Engine(content="castle_outpost", size=7)
    carriers = [w for w in weapons
                if any(ek._nonstack_contrib(w, i)
                       for i in range(len(ek._combo_extras(w))))]
    if len(carriers) >= 2:
        a, b = carriers[0], carriers[1]
        ca = next(i for i in range(len(ek._combo_extras(a)))
                  if ek._nonstack_contrib(a, i))
        cb = next(i for i in range(len(ek._combo_extras(b)))
                  if ek._nonstack_contrib(b, i))
        cases.append({"content": "castle_outpost", "size": 7, "style": "balanced",
                      "party": [a, b, "MAIN_HOLYSTAFF_AVALON"],
                      "combos": [ca, cb, None],
                      "gears": [dict(ek.kit_variants(a))["v0"],
                                dict(ek.kit_variants(b))["v0"], None],
                      "refine_pool": carriers, "swap": True})
    clap10 = ["2H_HAMMER", "MAIN_ROCKMACE_KEEPER", "MAIN_HOLYSTAFF_AVALON",
              "2H_HOLYSTAFF", "2H_ICECRYSTAL_UNDEAD", "2H_ICECRYSTAL_UNDEAD",
              "MAIN_ARCANESTAFF_UNDEAD", "2H_ARCANESTAFF_HELL",
              "2H_FIRE_RINGPAIR_AVALON", "2H_INFERNOSTAFF_MORGANA"]
    if all(w in data["weapons"] for w in clap10) \
            and "ARMOR_LEATHER_SET3" in (data.get("gear") or {}):
        cases.append({"content": "blackzone_roam", "size": 10, "style": "balanced",
                      "party": clap10, "combos": [None] * len(clap10),
                      "gears": [["ARMOR_LEATHER_SET3"]
                                if ek.role_of(w) == "dps" else None
                                for w in clap10],
                      "refine_pool": weapons[2::11]})
    # the gank read (validation round 4, rosters 3 and 18; T43b): at 10
    # members under balanced and at 13 under a declared brawl, so both
    # ports read the same label, catch counts and member verdicts there
    gank3 = ["2H_ARCANESTAFF_CRYSTAL", "2H_DUALAXE_KEEPER", "2H_DUALAXE_KEEPER",
             "2H_HALBERD_MORGANA", "2H_DUALSICKLE_UNDEAD", "2H_DUALSCIMITAR_UNDEAD",
             "2H_DUALSCIMITAR_UNDEAD", "MAIN_HOLYSTAFF_AVALON", "2H_SCYTHE_HELL",
             "2H_KNUCKLES_KEEPER"]
    gank18 = ["2H_DUALAXE_KEEPER", "2H_DUALAXE_KEEPER", "2H_BOW_KEEPER", "2H_CLAWPAIR",
              "2H_CLAWPAIR", "2H_DAGGERPAIR", "2H_KNUCKLES_AVALON",
              "MAIN_NATURESTAFF_CRYSTAL", "MAIN_HOLYSTAFF_AVALON", "2H_ICECRYSTAL_UNDEAD",
              "2H_HOLYSTAFF_UNDEAD", "2H_ROCKSTAFF_KEEPER", "2H_LONGBOW_UNDEAD"]
    # a frontline counts melee by its seat (T43d): round 4's roster 11,
    # its Witchwork Staff an engage tank beside two flex bombs
    front11 = ["2H_KNUCKLES_SET2", "2H_NATURESTAFF_HELL", "2H_BOW", "2H_ENIGMATICSTAFF",
               "2H_DUALSCIMITAR_UNDEAD", "2H_AXE", "MAIN_SPEAR_KEEPER", "MAIN_MACE",
               "2H_AXE_AVALON", "MAIN_ARCANESTAFF_UNDEAD"]
    for party, style in ((gank3, "balanced"), (gank18, "brawl"),
                         (front11, "balanced")):
        if all(w in data["weapons"] for w in party) and style in styles:
            cases.append({"content": "territory_defense", "size": len(party),
                          "style": style, "party": party,
                          "combos": [None] * len(party), "gears": None,
                          "refine_pool": weapons[4::11]})
    multi = [w for w in weapons if _combo_count(data, w) > 1]
    gk = sorted(data.get("gear") or {})
    short_party = [multi[(13 * k) % len(multi)] for k in range(5)]
    cases.append({"content": "blackzone_roam", "size": 20, "style": "clap",
                  "party": short_party,
                  "combos": [_combo_count(data, short_party[0]) - 1, None],
                  "gears": [gk[:3]] if gk else [],
                  "refine_pool": weapons[3::11], "swap": True})
    # inside each matchmaking pool that carries a prior of its own (the
    # Dragon Portal's 2-3, 4-5, 6-7): the meta term reads the pool's solo
    # and pair tables at pool_delta_x x delta. The random cases above reach
    # one size per pool with random weapons; these draw the party from the
    # pool's fielded list so its pair rows fire, at both ends of the pool
    al = data["templates"].get("ancient_lands") or {}
    for pk, pool in sorted(((data["scoring"].get("meta_pools") or {})
                            .get("ancient_lands") or {}).items()):
        listed = sorted(((al.get("pool_fielded") or {}).get(pk) or {}).get("weapons") or [])
        if not listed:
            continue
        for size, style in ((pool["sizes"][0], "balanced"), (pool["sizes"][1], "brawl")):
            party = [rng.choice(listed) for _ in range(size - 1)]
            cases.append({"content": "ancient_lands", "size": size, "style": style,
                          "party": party, "combos": [None] * len(party),
                          "gears": [], "refine_pool": listed[::3], "swap": True})
    return cases


# swap_review is a full-pool sweep PER MEMBER — cover it on every 6th case
# with the party capped at 6 members so the parity run stays fast.
SWAP_EVERY, SWAP_MAX_PARTY = 6, 6


def swap_case(i, party, c=None):
    # a case flagged "swap" (the dressed and short-list cases) always runs it
    return (party[:SWAP_MAX_PARTY]
            if i % SWAP_EVERY == 0 or (c or {}).get("swap") else None)


# refine() is the other full-pool sweep — same sampling deal as swap_review.
# Two passes is enough to catch a divergence: if the engines disagree at all
# they disagree on the FIRST move, and each pass is a full steepest-descent
# sweep over every slot.
REFINE_EVERY, REFINE_MAX_PARTY, REFINE_PASSES = 6, 6, 2


def refine_case(i, party):
    return party[:REFINE_MAX_PARTY] if i % REFINE_EVERY == 0 else None


# forge() runs beam search + refinement — the heaviest call in either
# engine. Every 10th case forges a small roster with the case's first two
# party members locked, over the case's deterministic refine_pool. Sizes
# stay modest so the parity run keeps its budget.
FORGE_EVERY, FORGE_SIZE = 10, 8


def forge_case(i, c):
    if i % FORGE_EVERY != 0:
        return None
    # every second forge case passes an EMPTY locked_combos list — the
    # engines must both pad it to len(locked) with defaults (an empty array
    # is truthy in JS and falsy in Python; that divergence shipped once).
    # locked_gears: the same alternation carries the case's
    # gear for the first lock — supplied kits must be preserved verbatim
    # and scored in both ports; [] entries normalize to naked.
    combos = c["combos"][:2] if (i // FORGE_EVERY) % 2 == 0 else []
    lgears = (c["gears"][:2] if (i // FORGE_EVERY) % 2 == 0 else None)
    return {"size": FORGE_SIZE, "locked": c["party"][:2],
            "locked_combos": combos, "pool": c["refine_pool"],
            "locked_gears": lgears}


def _refusal(fn):
    """The refusal message a call raises, else "no refusal"."""
    try:
        fn()
    except ValueError as err:
        return str(err)
    return "no refusal"


def forge_cap_results(e, pool):
    """One party caps at PARTY_CAP: forging one more, forging with one
    more locked, and replacing or refining in a party of one more each
    refuse with the cap message, before any search (mirrors
    js_parity_runner.js forgeCapResults)."""
    over = PARTY_CAP + 1
    party = [pool[0]] * over
    return {"forge": _refusal(lambda: e.forge(over, pool=pool)),
            "locked": _refusal(lambda: e.forge(PARTY_CAP, locked=party, pool=pool)),
            "replace": _refusal(lambda: e.replace_options(party, 0, pool=pool)),
            "refine": _refusal(lambda: e.refine(party, max_passes=1, pool=[]))}


# kit_options is a full-catalog sweep (comp-aware = one fitness call per
# item) — cover it on every 6th case, offset from the swap/refine cadence,
# with the rest-of-party capped. Both modes ride: comp-aware (exact
# marginal first) and context-free (doctrine tier first) — increment 2.
KIT_EVERY, KIT_OFFSET, KIT_MAX_REST = 6, 3, 5


def _kit_ser(ko):
    return {s: [{"gear": o["gear"], "value": o["value"],
                 "doctrine": o["doctrine"], "carries": o["carries"],
                 "passive": o["passive"]["id"] if o["passive"] else None}
                for o in opts]
            for s, opts in ko["options"].items()}


def py_results(cases):
    out = []
    for i, c in enumerate(cases):
        e = Engine(content=c["content"], size=c["size"], style=c["style"])
        sp = swap_case(i, c["party"], c)
        gl = c["gears"] or []
        rp = refine_case(i, c["party"])
        fc = forge_case(i, c)
        forged = None
        forge_cap = None if fc is None else forge_cap_results(e, fc["pool"])
        if fc is not None:
            r = e.forge(fc["size"], locked=fc["locked"],
                        locked_combos=fc["locked_combos"], pool=fc["pool"],
                        locked_gears=fc["locked_gears"])
            # the next-best alternative (`avoid`): the roster
            # just forged is avoided; both ports must walk to the same one
            r2 = e.forge(fc["size"], locked=fc["locked"],
                         locked_combos=fc["locked_combos"], pool=fc["pool"],
                         locked_gears=fc["locked_gears"], avoid=[r["party"]])
            forged = {"party": r["party"], "combos": r["combos"],
                      "gears": r["gears"],
                      "score": r["score"], "feasible": r["feasible"],
                      "filler": r["filler"], "held": r["held"],
                      "exhausted": r["exhausted"],
                      "next": {"party": r2["party"], "gears": r2["gears"],
                               "score": r2["score"], "exhausted": r2["exhausted"]}}
        # V3-W parity: dressing OFF while incumbents keep their
        # case gears — candidates must evaluate naked through the identity
        # short-circuit; the toggle restores dressed state bit-identically.
        e.set_dressing(False)
        naked_rec = [{"weapon": r["weapon"], "score": r["score"],
                      "combo": r["combo"], "kit": r["kit"]}
                     for r in e.recommend(c["party"], 5, None,
                                          c["combos"], c["gears"])]
        e.set_dressing(True)
        out.append({
            "recommend_naked_cand": naked_rec,
            "refine": None if rp is None else e.refine(
                rp, max_passes=REFINE_PASSES, pool=c["refine_pool"]),
            # gear-aware refine (F25/F26): dressed local
            # search returns {party, gears}; incumbent kits from the case
            "refine_dressed": None if rp is None else e.refine(
                rp, max_passes=REFINE_PASSES, pool=c["refine_pool"],
                fixed=0, gears=c["gears"][:len(rp)]),
            "comp_score": e.comp_score(c["party"]),
            # the meta term's weight at this case's context (pool_delta_x x
            # delta inside a pool with a prior of its own); the pick
            # report's reconstruction reads it
            "delta": e.delta,
            "comp_score_locked": e.comp_score(c["party"], c["combos"]),
            "redundancy": e.redundancy(c["party"]),
            "size_bucket": e.size_bucket(),
            # target provenance + the four-stage minimum (rule 17, L20):
            # display reads, parity-carried like every descriptive layer
            "target_source": {cap: e.target_source(cap) for cap in e.reqs},
            "target_min": {cap: e.target_min(cap) for cap in e.reqs},
            "constraint_band": e._band,
            "forge": forged,
            # one party caps at 20 (forges stop at 20), on the forge cadence
            "forge_cap": forge_cap,
            # replace_options: the one-slot forge on the
            # swap cadence, slot 0 of the swap party, over the case pool
            "replace": None if sp is None or len(sp) < 2 else [
                {"weapon": o["weapon"], "score": o["score"],
                 "delta": o["delta"], "combo": o["combo"], "kit": o["kit"]}
                for o in e.replace_options(sp, 0, c["combos"][:len(sp)],
                                           c["gears"][:len(sp)], 5,
                                           pool=c["refine_pool"])],
            "swap": None if sp is None else [
                {"weapon": m["weapon"], "score": m["score"], "rank": m["rank"],
                 "off_comp": m["off_comp"], "off_style": m["off_style"],
                 "caps_gain": m["caps_gain"], "verdict": m["verdict"],
                 "redundant": m["redundant"],
                 "options": [{"weapon": o["weapon"], "score": o["score"]}
                             for o in m["options"]]}
                for m in e.swap_review(sp)],
            "fitness": e.fitness(c["party"]),
            # the gear-active doctrine's default pick per item, at this
            # case's content and size (the band may move the pick)
            "gear_choice": {k: [e.default_gear_choice(k), e.gear_choice_source(k),
                                e.gear_active_spell(k)]
                            for k in sorted(e.gear)},
            "fitness_build": (None if not c.get("gears") else
                              e.fitness(c["party"], None, c["gears"])),
            "comp_score_build": (None if not c.get("gears") else
                                 e.comp_score(c["party"], None, c["gears"])),
            "fitness_locked": e.fitness(c["party"], c["combos"]),
            "synergy": e.synergy(c["party"]),
            "synergy_locked": e.synergy(c["party"], c["combos"]),
            "max_fitness": e.max_fitness(),
            # party-aware supremum (the optional-capability rule): optional
            # capabilities the party fields none of leave the denominator
            "max_fitness_party": e.max_fitness(c["party"], c["combos"],
                                               c["gears"]),
            "recommend": [{"weapon": r["weapon"], "score": r["score"],
                           "combo": r["combo"], "kit": r["kit"],
                           "caps_gain": r["caps_gain"],
                           "verdict": r["verdict"],
                           "meta_prior": r["meta_prior"],
                           "meta_solo": r["meta_solo"], "meta_pair": r["meta_pair"],
                           "meta_partner": r["meta_partner"],
                           "meta_raise": r["meta_raise"]}
                          for r in e.recommend(c["party"], 5)],
            "pick_report": (e.pick_report(c["party"], c["refine_pool"][0],
                                          c["combos"])
                            if c["refine_pool"] else None),
            "analyze_bands": (lambda a: {
                "strengths": [{"cap": x["cap"], "have": x["have"],
                               "band": x["band"], "soft_cap": x["soft_cap"]}
                              for x in a["strengths"]],
                "missing": [{"cap": x["cap"], "have": x["have"],
                             "band": x["band"], "soft_cap": x["soft_cap"]}
                            for x in a["missing_capabilities"]],
            })(e.analyze(c["party"], c["combos"])),
            "recommend_locked": [{"weapon": r["weapon"], "score": r["score"]}
                                 for r in e.recommend(c["party"], 5,
                                                      combos=c["combos"])],
            "weaknesses": [{"cap": g["cap"], "gap": g["gap"]}
                           for g in e.weaknesses(c["party"], 5, None,
                                                 c["gears"])],
            "uncovered": sorted(e.uncovered_caps(c["party"])),
            "identity": e.comp_identity(c["party"], c["combos"]),
            "kill_pressure": e.kill_pressure(c["party"], c["combos"]),
            "fight_chain": e.fight_chain(
                c["party"], c["combos"],
                candidate=(c["party"][0] if c["party"] else None)),
            # role layer (roles-design.md): chest per member = first
            # ARMOR_ item in the case's gear list (mirrors the runner)
            "role_advisory": e.role_advisory(c["party"], {
                j: next((x for x in (g or [])
                         if str(x).startswith("ARMOR_")), None)
                for j, g in enumerate(c.get("gears") or [])
                if any(str(x).startswith("ARMOR_") for x in (g or []))}),
            "kit": (None if (i % KIT_EVERY != KIT_OFFSET
                             or not c["party"]) else {
                "comp": _kit_ser(e.kit_options(
                    c["party"][0], party=c["party"][1:1 + KIT_MAX_REST])),
                "free": _kit_ser(e.kit_options(c["party"][0]))}),
            # the dressed paths: every reader handed the case's own combos
            # and kits (F38-F42, T26d, T54, T55)
            **_dressed_results(e, c, sp, rp, i, gl),
        })
    return out


def _dressed_results(e, c, sp, rp, i, gl):
    """The dressed and empty-pool outputs, serialized to the fields both
    ports must agree on (the runner's dressedResults mirrors this)."""
    party, combos = c["party"], c["combos"]
    gears = c["gears"]
    cand = party[0] if party else None
    pool0 = c["refine_pool"][0] if c["refine_pool"] else None
    return {
        "identity_dressed": _ser_identity(e.comp_identity(party, combos, gears)),
        "fight_chain_dressed": _ser_chain(e.fight_chain(party, combos, gears,
                                                        candidate=cand)),
        "kill_pressure_dressed": _ser_kp(e.kill_pressure(party, combos, gears)),
        "uncovered_dressed": sorted(e.uncovered_caps(party, combos, gears)),
        "explain_dressed": (None if pool0 is None else _ser_explain(
            e.explain(party, pool0, combos, gears))),
        "pick_report_dressed": (None if pool0 is None else _ser_report(
            e.pick_report(party, pool0, combos, gears))),
        "swap_dressed": (None if sp is None else _ser_swap(e.swap_review(
            sp, 3, None, combos[:len(sp)], gl[:len(sp)]))),
        # an explicit empty pool is no candidates in every entry point
        # that takes one (F37)
        "empty_pool": {
            "recommend": [r["weapon"] for r in e.recommend(party, 4, pool=[])],
            "swap": None if sp is None else [
                [m["rank"], [o["weapon"] for o in m["options"]]]
                for m in e.swap_review(sp, pool=[])],
            "refine": None if rp is None else e.refine(
                rp, max_passes=REFINE_PASSES, pool=[])},
        # the kit advisor with the rest as equipped (F42), on the kit cadence
        "kit_rest": (None if (i % KIT_EVERY != KIT_OFFSET or not party) else
                     _kit_ser(e.kit_options(
                         party[0], combos[0] if combos else None,
                         party[1:1 + KIT_MAX_REST], 3, "auto",
                         combos[1:1 + KIT_MAX_REST],
                         gl[1:1 + KIT_MAX_REST]))),
    }


def _ser_identity(ia):
    return {"style": ia["style"], "label": ia["label"],
            "strength": ia["strength"], "band": ia["band"],
            "carriers": ia["carriers"], "kit_lean": ia.get("kit_lean"),
            "archetype": ia.get("archetype"),
            "core_catch": ia["core_catch"], "line_catch": ia["line_catch"],
            "conflicts": [[x["weapon"], x["kind"]] for x in ia["conflicts"]],
            "members": [[m["weapon"], m["role"], m["side"], m["fit"]]
                        for m in ia["members"]],
            "melee_share": ia["melee_share"], "posture": ia["posture"],
            "mode": ia["mode"]}


def _ser_chain(fc):
    if fc is None:
        return None
    imp = fc["improves"]
    return {"style": fc["style"],
            "stages": [[s["name"], s["verdict"], s["caps"], s["have"], s["bar"],
                        s["min"],
                        [[r["cap"], r["member"], r["weapon"], r["slot"],
                          r["spell"], r["units"]] for r in s["sources"]]]
                       for s in fc["stages"]],
            "improves": None if imp is None else [
                imp["stage"], imp["gain"],
                [[t["cap"], t["gain"]] for t in imp["terms"]]]}


def _ser_kp(kp):
    if kp is None:
        return None
    out = {"verdict": kp["verdict"]}
    for k in ("pierce", "heal_cut", "burst"):
        out[k] = [kp[k]["ok"], kp[k]["have"], kp[k]["bar"]]
    return out


def _ser_explain(terms):
    return [[t["cap"], t["delta"], t["before"], t["after"], t["target"]]
            for t in terms]


def _ser_report(pr):
    return [pr["verdict"], pr["combo"], pr["kit"], pr["score"],
            pr["d_fitness"], pr["d_synergy"], pr["caps_gain"],
            [[r["cap"], r["gain"], r["coverage"], r["floor_lift"],
              r["overstack_cost"], r["delta"]] for r in pr["caps"]],
            [[n["spell"], n["lost"]] for n in pr["nonstack"]]]


def _ser_swap(rev):
    return [[m["weapon"], m["score"], m["rank"], m["built_score"],
             m["build_gap"], m["combo"], m["kit"], m["caps_gain"],
             m["verdict"],
             [[o["weapon"], o["score"], o["gain"], o["delta"], o["combo"],
               o["kit"]] for o in m["options"]]]
            for m in rev]


def _close(a, b, eps=EPS):
    """Deep equality at the parity tolerance: numbers within eps, lists
    and tuples alike (JSON has no tuples), every other value exact."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= eps
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_close(a[k], b[k], eps) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_close(x, y, eps)
                                        for x, y in zip(a, b))
    return a == b


SCRATCH_RUNNER = os.path.join(HERE, "js_parity_scratch.js")


def scratch_pass(data):
    """The latent splits the shipped dataset never reaches, read by both
    ports on a scratch copy of it (tests/js_parity_scratch.js is the node
    half): every gear piece costs its wearer the floored capabilities, so
    a dressed candidate carries one at zero while its weapon supplies it
    (F44); one weapon's loadout is an empty `always` with no slots (the
    flat-sheet fallback); one seat's gang band is empty and its clap cell
    carries an empty kit_build, another seat's clap cell is empty (each
    read as absent); and top_n is an explicit null (the default, F45).
    Returns the mismatch lines; empty means both ports agree."""
    d = json.loads(json.dumps(data))
    probe = Engine(content="castle_outpost", size=7)
    floored = sorted(c for c, row in probe._cap_tab.items() if row[4] is not None)
    floor_cases = []
    for cap in floored:
        cand = next((w for w in sorted(probe.weapons)
                     if not probe.weapons[w].get("removed")
                     and dict(probe.kit_variants(w)).get("v0")
                     and all(x.get(cap, 0.0) > 0 for x in probe._combo_extras(w))),
                    None)
        if cand:
            floor_cases.append([cap, cand])
    for g in d["gear"].values():
        costs = dict(g.get("self_costs") or {})
        for cap in floored:
            costs[cap] = 99
        g["self_costs"] = costs
    flat = next(w for w in sorted(d["weapons"])
                if d["weapons"][w].get("capabilities")
                and not d["weapons"][w].get("removed"))
    d["weapons"][flat]["loadout"] = {"slots": [], "always": {}}
    seats = [r for r in d["roles"] if (r.get("kit_bands") or {}).get("gang")
             and (r.get("kit_styles") or {}).get("clap")]
    seats[0]["kit_bands"]["gang"] = {}
    seats[0]["kit_styles"]["clap"] = {"kit": dict(seats[0]["kit_styles"]["clap"].get("kit") or {}),
                                      "kit_build": []}
    seats[1]["kit_styles"]["clap"] = {}
    spec = {"floor": floor_cases, "flat_weapon": flat, "style": "clap",
            "seat_gang": seats[0]["id"], "seat_cell": seats[1]["id"],
            "party": ["2H_HAMMER_AVALON", "2H_MACE", "2H_LONGBOW"]}
    paths = []
    try:
        for obj in (d, spec):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                             encoding="utf-8") as tf:
                json.dump(obj, tf)
                paths.append(tf.name)
        proc = subprocess.run(["node", SCRATCH_RUNNER, SCORING_JS] + paths,
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=120)
        if proc.returncode != 0:
            return ["scratch runner crashed: " + proc.stderr[-600:]]
        js = json.loads(proc.stdout)
        e7 = Engine(paths[0], content="castle_outpost", size=7)
        gang = Engine(paths[0], content="castle_outpost", size=7, style="clap")
        cell = Engine(paths[0], content="blackzone_roam", size=20, style="clap")
    finally:
        for p in paths:
            os.unlink(p)
    names = lambda rows: [r["weapon"] for r in rows]
    party = spec["party"]
    py = {"floor": [], "raw": e7._raw_member_caps(flat),
          "seat_gang": json.loads(json.dumps(gang._seat_kit(gang.roles[spec["seat_gang"]]))),
          "seat_cell": json.loads(json.dumps(cell._seat_kit(cell.roles[spec["seat_cell"]]))),
          "top_null": {
              "recommend": names(e7.recommend(party, None)),
              "weaknesses": [g["cap"] for g in e7.weaknesses(party, None)],
              "swap": [names(m["options"]) for m in e7.swap_review(party, None)],
              "replace": names(e7.replace_options(party, 0, None, None, None)),
              "kit": {s: [o["gear"] for o in opts] for s, opts in
                      e7.kit_options(party[0], None, None, None)["options"].items()}}}
    for _cap, cand in floor_cases:
        pr = e7.pick_report([], cand)
        py["floor"].append({
            "score": pr["score"], "d_fitness": pr["d_fitness"], "combo": pr["combo"],
            "kit": pr["kit"],
            "rows": [[r["cap"], r["gain"], r["floor_lift"], r["delta"]] for r in pr["caps"]],
            "actual": e7.comp_score([cand], [pr["combo"]], [pr["kit"]]) - e7.comp_score([])})
    errs = []
    for k in ("floor", "raw", "seat_gang", "seat_cell", "top_null"):
        if not _close(py[k], js.get(k)):
            errs.append(f"scratch {k}: py={str(py[k])[:240]} js={str(js.get(k))[:240]}")
    for f in py["floor"] + js.get("floor", []):
        if abs(f["score"] - f["actual"]) > EPS:
            errs.append(f"scratch floor: pick score {f['score']!r} is not the "
                        f"comp_score delta {f['actual']!r}")
    if not floor_cases:
        errs.append("scratch floor: no candidate supplies a floored capability")
    return errs


def main():
    with open(DATASET, encoding="utf-8") as f:
        data = json.load(f)
    cases = make_cases(data)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as tf:
        json.dump(cases, tf)
        cases_path = tf.name
    try:
        try:
            # encoding pinned: node writes UTF-8; text=True alone decodes
            # with the Windows locale codepage and mangles any non-ASCII
            # in the payload (the identity labels carry an em-dash)
            proc = subprocess.run(["node", RUNNER, SCORING_JS, DATASET, cases_path],
                                  capture_output=True, text=True,
                                  encoding="utf-8", timeout=120)
        except FileNotFoundError:
            print("SKIP: node not found — JS parity not verified on this machine")
            return 0
        if proc.returncode != 0:
            print("FAIL: node runner crashed\n" + proc.stderr)
            return 1
        js = json.loads(proc.stdout)
    finally:
        os.unlink(cases_path)

    py = py_results(cases)
    bad = 0
    for i, (a, b, c) in enumerate(zip(py, js, cases)):
        errs = []
        if a["refine"] is not None and a["refine"] != b["refine"]:
            errs.append(f"refine: py={a['refine']} js={b['refine']}")
        if a["refine_dressed"] is not None \
                and a["refine_dressed"] != b.get("refine_dressed"):
            errs.append(f"refine_dressed: py={a['refine_dressed']} "
                        f"js={b.get('refine_dressed')}")
        for k in ("fitness", "synergy", "max_fitness", "max_fitness_party",
                  "comp_score", "delta", "comp_score_locked", "fitness_locked",
                  "synergy_locked", "redundancy", "fitness_build",
                  "comp_score_build"):
            if a[k] is None and b.get(k) is None:
                continue
            if a[k] is None or b.get(k) is None or abs(a[k] - b[k]) > EPS:
                errs.append(f"{k}: py={a[k]!r} js={b[k]!r}")
        if a["size_bucket"] != b["size_bucket"]:
            errs.append(f"size_bucket: py={a['size_bucket']} js={b['size_bucket']}")
        gb = b.get("gear_choice") or {}
        for k, v in a["gear_choice"].items():
            if gb.get(k) != v:
                errs.append(f"gear_choice {k}: py={v} js={gb.get(k)}")
                break
        if a["target_source"] != b.get("target_source"):
            errs.append(f"target_source: py={a['target_source']} "
                        f"js={b.get('target_source')}")
        bm = b.get("target_min") or {}
        for cap, v in a["target_min"].items():
            if cap not in bm or abs(v - bm[cap]) > EPS:
                errs.append(f"target_min {cap}: py={v!r} js={bm.get(cap)!r}")
        if a["constraint_band"] != b.get("constraint_band"):
            errs.append(f"constraint_band: py={a['constraint_band']} "
                        f"js={b.get('constraint_band')}")
        if a["forge"] is not None:
            fa, fb = a["forge"], b["forge"] or {}
            if fa["party"] != fb.get("party") or fa["combos"] != fb.get("combos") \
                    or fa["gears"] != fb.get("gears"):
                errs.append(f"forge roster: py={fa['party']}/{fa['gears']} "
                            f"js={fb.get('party')}/{fb.get('gears')}")
            elif abs(fa["score"] - fb.get("score", 1e9)) > EPS \
                    or fa["feasible"] != fb.get("feasible") \
                    or fa["filler"] != fb.get("filler") \
                    or fa["held"] != fb.get("held") \
                    or fa["exhausted"] != fb.get("exhausted"):
                errs.append(f"forge result: py={fa} js={fb}")
            na, nb = fa["next"], fb.get("next") or {}
            if na["party"] != nb.get("party") or na["gears"] != nb.get("gears") \
                    or abs(na["score"] - nb.get("score", 1e9)) > EPS \
                    or na["exhausted"] != nb.get("exhausted"):
                errs.append(f"forge next-best (avoid): py={na} js={nb}")
        if a.get("forge_cap") is not None:
            want = party_cap_message(PARTY_CAP + 1)
            if a["forge_cap"] != b.get("forge_cap") \
                    or any(v != want for v in a["forge_cap"].values()):
                errs.append(f"forge_cap: py={a['forge_cap']} "
                            f"js={b.get('forge_cap')} want={want!r}")
        if a.get("replace") is not None:
            ra_, rb_ = a["replace"], b.get("replace") or []
            if [o["weapon"] for o in ra_] != [o["weapon"] for o in rb_]:
                errs.append(f"replace_options order: py={[o['weapon'] for o in ra_]} "
                            f"js={[o['weapon'] for o in rb_]}")
            else:
                for oa, ob in zip(ra_, rb_):
                    if abs(oa["score"] - ob["score"]) > EPS \
                            or abs(oa["delta"] - ob["delta"]) > EPS \
                            or oa["combo"] != ob["combo"] or oa["kit"] != ob["kit"]:
                        errs.append(f"replace_options {oa['weapon']}: py={oa} js={ob}")
        if [r["weapon"] for r in a["recommend"]] != [r["weapon"] for r in b["recommend"]]:
            errs.append(f"recommend order: py={[r['weapon'] for r in a['recommend']]} "
                        f"js={[r['weapon'] for r in b['recommend']]}")
        else:
            for ra, rb in zip(a["recommend"], b["recommend"]):
                if abs(ra["score"] - rb["score"]) > EPS or ra["combo"] != rb["combo"] \
                        or ra["kit"] != rb.get("kit"):
                    errs.append(f"score {ra['weapon']}: "
                                f"py={ra['score']!r}/{ra['combo']}/{ra['kit']} "
                                f"js={rb['score']!r}/{rb['combo']}/{rb.get('kit')}")
                elif ra["verdict"] != rb.get("verdict") \
                        or abs(ra["caps_gain"] - rb.get("caps_gain", 9e9)) > EPS:
                    errs.append(f"rec verdict {ra['weapon']}: "
                                f"py={ra['verdict']}/{ra['caps_gain']!r} "
                                f"js={rb.get('verdict')}/{rb.get('caps_gain')!r}")
                elif any(abs(ra[k] - rb.get(k, 9e9)) > EPS
                         for k in ("meta_prior", "meta_solo", "meta_pair", "meta_raise"))                         or ra["meta_partner"] != rb.get("meta_partner"):
                    # pair-aware prior: the four descriptive
                    # meta fields ride the same parity contract
                    errs.append(f"rec meta {ra['weapon']}: "
                                f"py={ra['meta_prior']!r}/{ra['meta_solo']!r}/{ra['meta_pair']!r}/"
                                f"{ra['meta_partner']}/{ra['meta_raise']!r} "
                                f"js={rb.get('meta_prior')!r}/{rb.get('meta_solo')!r}/"
                                f"{rb.get('meta_pair')!r}/{rb.get('meta_partner')}/{rb.get('meta_raise')!r}")
        pa, pb = a["pick_report"], b.get("pick_report")
        if (pa is None) != (pb is None):
            errs.append("pick_report presence differs")
        elif pa is not None:
            pb = pb or {}
            if (pa["verdict"] != pb.get("verdict") or pa["combo"] != pb.get("combo")
                    or pa["kit"] != pb.get("kit")
                    or pa["meta_partner"] != pb.get("meta_partner")
                    or any(abs(pa[k] - pb.get(k, 9e9)) > EPS
                           for k in ("score", "d_fitness", "d_synergy",
                                     "meta_prior", "meta_solo", "meta_pair",
                                     "meta_raise", "viability", "dup_penalty",
                                     "caps_gain"))):
                errs.append(f"pick_report head: py={pa['verdict']}/{pa['score']!r} "
                            f"js={pb.get('verdict')}/{pb.get('score')!r}")
            elif ([(r["cap"], r["saturated"]) for r in pa["caps"]]
                    != [(r.get("cap"), r.get("saturated"))
                        for r in pb.get("caps") or []]
                    or any(abs(ra[k] - rb.get(k, 9e9)) > EPS
                           for ra, rb in zip(pa["caps"], pb.get("caps") or [])
                           for k in ("gain", "before", "coverage", "floor_lift",
                                     "overstack_cost", "delta"))):
                errs.append("pick_report caps rows differ")
            elif [(n["spell"], n["lost"]) for n in pa["nonstack"]] \
                    != [(n.get("spell"), n.get("lost"))
                        for n in pb.get("nonstack") or []]:
                errs.append("pick_report nonstack lines differ")
            else:
                # the decomposition must reconstruct the score EXACTLY —
                # the report is the same math that ranked the pick, or the
                # why-not panel is a second scoring system in disguise
                # (alpha, beta and viability are dataset-global; delta is the
                # case engine's, pool_delta_x x delta inside a pool's prior)
                w = data["scoring"]["weights"]
                recon = (w["alpha"] * pa["d_fitness"] + w["beta"] * pa["d_synergy"]
                         + a["delta"] * pa["meta_prior"]
                         + w.get("viability", 0.0) * pa["viability"]
                         - pa["dup_penalty"])
                rowsum = sum(r["coverage"] + r["floor_lift"] - r["overstack_cost"]
                             for r in pa["caps"])
                if abs(recon - pa["score"]) > EPS:
                    errs.append(f"pick_report terms do not sum to score: "
                                f"{recon!r} vs {pa['score']!r}")
                if abs(rowsum - pa["d_fitness"]) > EPS:
                    errs.append(f"pick_report caps do not sum to d_fitness: "
                                f"{rowsum!r} vs {pa['d_fitness']!r}")
        ba, bb = a["analyze_bands"], b.get("analyze_bands") or {}
        for sec in ("strengths", "missing"):
            if [(x["cap"], x["band"]) for x in ba[sec]] \
                    != [(x.get("cap"), x.get("band")) for x in bb.get(sec) or []]:
                errs.append(f"analyze {sec} bands: py={ba[sec]} js={bb.get(sec)}")
            elif any(abs(x["have"] - y.get("have", 9e9)) > EPS
                     or abs(x["soft_cap"] - y.get("soft_cap", 9e9)) > EPS
                     for x, y in zip(ba[sec], bb.get(sec) or [])):
                errs.append(f"analyze {sec} numbers differ")
        if [r["weapon"] for r in a["recommend_locked"]] != \
                [r["weapon"] for r in b["recommend_locked"]]:
            errs.append("locked recommend order differs")
        else:
            for ra, rb in zip(a["recommend_locked"], b["recommend_locked"]):
                if abs(ra["score"] - rb["score"]) > EPS:
                    errs.append(f"locked score {ra['weapon']}: "
                                f"py={ra['score']!r} js={rb['score']!r}")
        if [r["weapon"] for r in a["recommend_naked_cand"]] != \
                [r["weapon"] for r in (b.get("recommend_naked_cand") or [])]:
            errs.append("naked-candidate recommend order differs")
        else:
            for ra, rb in zip(a["recommend_naked_cand"],
                              b.get("recommend_naked_cand") or []):
                if abs(ra["score"] - rb["score"]) > EPS \
                        or ra["combo"] != rb.get("combo") \
                        or ra["kit"] != rb.get("kit") or ra["kit"]:
                    errs.append(f"naked-cand {ra['weapon']}: "
                                f"py={ra['score']!r}/{ra['combo']}/{ra['kit']} "
                                f"js={rb['score']!r}/{rb.get('combo')}/{rb.get('kit')}")
        if [g["cap"] for g in a["weaknesses"]] != [g["cap"] for g in b["weaknesses"]]:
            errs.append("weakness order differs")
        if a["uncovered"] != b["uncovered"]:
            errs.append(f"uncovered: py={a['uncovered']} js={b['uncovered']}")
        ia, ib = a["identity"], b.get("identity") or {}
        if (ia["style"] != ib.get("style") or ia["label"] != ib.get("label")
                or ia.get("archetype") != ib.get("archetype")
                or (ia["core_catch"], ia["line_catch"])
                != (ib.get("core_catch"), ib.get("line_catch"))
                or ia["strength"] != ib.get("strength")
                or ia["band"] != ib.get("band")
                or ia["carriers"] != ib.get("carriers")
                or [(x["weapon"], x["kind"]) for x in ia["conflicts"]]
                != [(x.get("weapon"), x.get("kind"))
                    for x in ib.get("conflicts") or []]
                or [(m["weapon"], m["role"], m["side"], m["fit"])
                    for m in ia["members"]]
                != [(m.get("weapon"), m.get("role"), m.get("side"),
                     m.get("fit")) for m in ib.get("members") or []]):
            errs.append(f"identity: py={ia['label']}/{ia['carriers']} "
                        f"js={ib.get('label')}/{ib.get('carriers')}")
        elif (abs(ia["melee_share"] - ib.get("melee_share", 9)) > EPS
              or abs(ia["posture"] - ib.get("posture", 9)) > EPS
              or any(abs(ia["mode"][k] - (ib.get("mode") or {}).get(k, 9)) > EPS
                     for k in ia["mode"])):
            errs.append(f"identity shares: py={ia} js={ib}")
        fa, fb = a["fight_chain"], b.get("fight_chain")
        if (fa is None) != (fb is None):
            errs.append("fight_chain presence differs")
        elif fa is not None:
            sa = [(x["name"], x["verdict"], x["caps"]) for x in fa["stages"]]
            sb = [(x.get("name"), x.get("verdict"), x.get("caps"))
                  for x in (fb.get("stages") or [])]
            ia_, ib_ = fa["improves"], fb.get("improves")
            if (fa["style"] != fb.get("style") or sa != sb
                    or (ia_ is None) != (ib_ is None)
                    or (ia_ is not None
                        and (ia_["stage"] != ib_.get("stage")
                             or abs(ia_["gain"] - ib_.get("gain", 9e9)) > EPS
                             or [(t["cap"],) for t in ia_["terms"]]
                             != [(t.get("cap"),)
                                 for t in ib_.get("terms") or []]
                             or any(abs(ta["gain"] - tb.get("gain", 9e9)) > EPS
                                    for ta, tb in zip(ia_["terms"],
                                                      ib_.get("terms") or []))))
                    or any(abs(x["have"] - y.get("have", 9e9)) > EPS
                           or abs(x["bar"] - y.get("bar", 9e9)) > EPS
                           for x, y in zip(fa["stages"],
                                           fb.get("stages") or []))):
                errs.append(f"fight_chain: py={fa} js={fb}")
            else:
                for x, y in zip(fa["stages"], fb.get("stages") or []):
                    xs = [(r["cap"], r["member"], r["weapon"], r["slot"],
                           r["spell"]) for r in x["sources"]]
                    ys = [(r.get("cap"), r.get("member"), r.get("weapon"),
                           r.get("slot"), r.get("spell"))
                          for r in y.get("sources") or []]
                    if xs != ys or any(
                            abs(ra["units"] - rb.get("units", 9e9)) > EPS
                            for ra, rb in zip(x["sources"],
                                              y.get("sources") or [])):
                        errs.append(f"fight_chain sources ({x['name']}): "
                                    f"py={xs[:4]} js={ys[:4]}")
                        break
        ka, kb = a["kill_pressure"], b.get("kill_pressure")
        if (ka is None) != (kb is None):
            errs.append("kill_pressure presence differs")
        elif ka is not None:
            if ka["verdict"] != kb.get("verdict") or any(
                    ka[k]["ok"] != (kb.get(k) or {}).get("ok")
                    or abs(ka[k]["have"] - (kb.get(k) or {}).get("have", 9e9)) > EPS
                    or abs(ka[k]["bar"] - (kb.get(k) or {}).get("bar", 9e9)) > EPS
                    for k in ("pierce", "heal_cut", "burst")):
                errs.append(f"kill_pressure: py={ka} js={kb}")
        if a["swap"] is not None:
            for ma, mb in zip(a["swap"], b["swap"] or []):
                if ma["rank"] != mb["rank"] or abs(ma["score"] - mb["score"]) > EPS \
                        or ma["off_comp"] != mb.get("off_comp") \
                        or ma["off_style"] != mb.get("off_style"):
                    errs.append(f"swap {ma['weapon']}: py rank {ma['rank']} "
                                f"score {ma['score']!r} vs js rank {mb['rank']} "
                                f"score {mb['score']!r}")
                elif [o["weapon"] for o in ma["options"]] != \
                        [o["weapon"] for o in mb["options"]]:
                    errs.append(f"swap {ma['weapon']} option order differs")
                elif any(abs(oa["score"] - ob["score"]) > EPS for oa, ob
                         in zip(ma["options"], mb["options"])):
                    errs.append(f"swap {ma['weapon']} option scores differ")
            if len(a["swap"]) != len(b["swap"] or []):
                errs.append("swap member count differs")
        # the dressed and empty-pool outputs compare whole serializations
        for k in ("identity_dressed", "fight_chain_dressed",
                  "kill_pressure_dressed", "uncovered_dressed",
                  "explain_dressed", "pick_report_dressed", "swap_dressed",
                  "empty_pool", "kit_rest"):
            if not _close(a.get(k), b.get(k)):
                errs.append(f"{k}: py={str(a.get(k))[:240]} "
                            f"js={str(b.get(k))[:240]}")
        if errs:
            bad += 1
            print(f"CASE {i} ({c['content']}/{c['style']}, party {len(c['party'])}): "
                  + "; ".join(errs))
    print(f"{len(cases) - bad}/{len(cases)} parity cases identical "
          f"(tolerance {EPS}, contents: {sorted(data['templates'])}, "
          f"styles: {sorted(data.get('styles') or {})})")
    scratch = scratch_pass(data)
    for line in scratch:
        print(line)
    if scratch:
        bad += 1
    else:
        print("scratch pass identical: a zeroed floored gain, an empty always, "
              "empty doctrine cells and a null top_n read the same in both ports")

    # The generated dashboard must embed THIS engine verbatim — a stale
    # build means the public page scores with different math than the source
    # both suites verified.
    with open(SCORING_JS, encoding="utf-8") as f:
        engine_src = f.read()
    for page in (os.path.join(ROOT, "dashboard", "index.html"),
                 os.path.join(ROOT, "docs", "index.html")):
        if not os.path.exists(page):
            continue
        with open(page, encoding="utf-8") as f:
            if engine_src not in f.read():
                print(f"FAIL: {os.path.relpath(page, ROOT)} does not embed the "
                      "current app_scoring.js — rerun dashboard/build.py")
                bad += 1
        # the check needs the raw source in the page; dashboard/build.py
        # inlines it unminified precisely so this comparison stays byte-exact
    if not bad:
        print("dashboard embed check: generated pages carry the verified engine")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
