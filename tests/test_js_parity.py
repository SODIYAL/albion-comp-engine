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

from engine import Engine  # noqa: E402

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
        # behind a green 60/60 that way (review 2026-08-15). The variants
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
        # loadout locks (2026-08-18): half the members carry a pinned combo
        # index — the archetype path must agree between engines too
        combos = [rng.randrange(_combo_count(data, w))
                  if rng.random() < 0.5 else None for w in party]
        # full-build members (2026-08-20): a deterministic gear list per
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
    return cases


# swap_review is a full-pool sweep PER MEMBER — cover it on every 6th case
# with the party capped at 6 members so the parity run stays fast.
SWAP_EVERY, SWAP_MAX_PARTY = 6, 6


def swap_case(i, party):
    return party[:SWAP_MAX_PARTY] if i % SWAP_EVERY == 0 else None


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
    # locked_gears (2026-08-27): the same alternation carries the case's
    # gear for the first lock — supplied kits must be preserved verbatim
    # and scored in both ports; [] entries normalize to naked.
    combos = c["combos"][:2] if (i // FORGE_EVERY) % 2 == 0 else []
    lgears = (c["gears"][:2] if (i // FORGE_EVERY) % 2 == 0 else None)
    return {"size": FORGE_SIZE, "locked": c["party"][:2],
            "locked_combos": combos, "pool": c["refine_pool"],
            "locked_gears": lgears}


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
        sp = swap_case(i, c["party"])
        rp = refine_case(i, c["party"])
        fc = forge_case(i, c)
        forged = None
        if fc is not None:
            r = e.forge(fc["size"], locked=fc["locked"],
                        locked_combos=fc["locked_combos"], pool=fc["pool"],
                        locked_gears=fc["locked_gears"])
            forged = {"party": r["party"], "combos": r["combos"],
                      "gears": r["gears"],
                      "score": r["score"], "feasible": r["feasible"],
                      "filler": r["filler"], "held": r["held"]}
        # V3-W parity (2026-08-27): dressing OFF while incumbents keep their
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
            # gear-aware refine (owner ruling 2026-08-27): dressed local
            # search returns {party, gears}; incumbent kits from the case
            "refine_dressed": None if rp is None else e.refine(
                rp, max_passes=REFINE_PASSES, pool=c["refine_pool"],
                fixed=0, gears=c["gears"][:len(rp)]),
            "comp_score": e.comp_score(c["party"]),
            "comp_score_locked": e.comp_score(c["party"], c["combos"]),
            "redundancy": e.redundancy(c["party"]),
            "size_bucket": e.size_bucket(),
            "forge": forged,
            "swap": None if sp is None else [
                {"weapon": m["weapon"], "score": m["score"], "rank": m["rank"],
                 "off_comp": m["off_comp"], "off_style": m["off_style"],
                 "caps_gain": m["caps_gain"], "verdict": m["verdict"],
                 "redundant": m["redundant"],
                 "options": [{"weapon": o["weapon"], "score": o["score"]}
                             for o in m["options"]]}
                for m in e.swap_review(sp)],
            "fitness": e.fitness(c["party"]),
            "fitness_build": (None if not c.get("gears") else
                              e.fitness(c["party"], None, c["gears"])),
            "comp_score_build": (None if not c.get("gears") else
                                 e.comp_score(c["party"], None, c["gears"])),
            "fitness_locked": e.fitness(c["party"], c["combos"]),
            "synergy": e.synergy(c["party"]),
            "synergy_locked": e.synergy(c["party"], c["combos"]),
            "max_fitness": e.max_fitness(),
            "recommend": [{"weapon": r["weapon"], "score": r["score"],
                           "combo": r["combo"], "kit": r["kit"],
                           "caps_gain": r["caps_gain"],
                           "verdict": r["verdict"]}
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
        })
    return out


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
        for k in ("fitness", "synergy", "max_fitness", "comp_score",
                  "comp_score_locked", "fitness_locked", "synergy_locked",
                  "redundancy", "fitness_build", "comp_score_build"):
            if a[k] is None and b.get(k) is None:
                continue
            if a[k] is None or b.get(k) is None or abs(a[k] - b[k]) > EPS:
                errs.append(f"{k}: py={a[k]!r} js={b[k]!r}")
        if a["size_bucket"] != b["size_bucket"]:
            errs.append(f"size_bucket: py={a['size_bucket']} js={b['size_bucket']}")
        if a["forge"] is not None:
            fa, fb = a["forge"], b["forge"] or {}
            if fa["party"] != fb.get("party") or fa["combos"] != fb.get("combos") \
                    or fa["gears"] != fb.get("gears"):
                errs.append(f"forge roster: py={fa['party']}/{fa['gears']} "
                            f"js={fb.get('party')}/{fb.get('gears')}")
            elif abs(fa["score"] - fb.get("score", 1e9)) > EPS \
                    or fa["feasible"] != fb.get("feasible") \
                    or fa["filler"] != fb.get("filler") \
                    or fa["held"] != fb.get("held"):
                errs.append(f"forge result: py={fa} js={fb}")
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
        pa, pb = a["pick_report"], b.get("pick_report")
        if (pa is None) != (pb is None):
            errs.append("pick_report presence differs")
        elif pa is not None:
            pb = pb or {}
            if (pa["verdict"] != pb.get("verdict") or pa["combo"] != pb.get("combo")
                    or pa["kit"] != pb.get("kit")
                    or any(abs(pa[k] - pb.get(k, 9e9)) > EPS
                           for k in ("score", "d_fitness", "d_synergy",
                                     "meta_prior", "viability", "dup_penalty",
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
                # (the blend weights are dataset-global, any engine serves)
                w = data["scoring"]["weights"]
                recon = (w["alpha"] * pa["d_fitness"] + w["beta"] * pa["d_synergy"]
                         + w["delta"] * pa["meta_prior"]
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
        if errs:
            bad += 1
            print(f"CASE {i} ({c['content']}/{c['style']}, party {len(c['party'])}): "
                  + "; ".join(errs))
    print(f"{N_CASES - bad}/{N_CASES} parity cases identical "
          f"(tolerance {EPS}, contents: {sorted(data['templates'])}, "
          f"styles: {sorted(data.get('styles') or {})})")

    # The generated dashboard must embed THIS engine verbatim — a stale
    # build means the public page scores with different math than the source
    # both suites verified (2026-08-18).
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
