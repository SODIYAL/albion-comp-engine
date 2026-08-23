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
    # is truthy in JS and falsy in Python; that divergence shipped once)
    combos = c["combos"][:2] if (i // FORGE_EVERY) % 2 == 0 else []
    return {"size": FORGE_SIZE, "locked": c["party"][:2],
            "locked_combos": combos, "pool": c["refine_pool"]}


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
                        locked_combos=fc["locked_combos"], pool=fc["pool"])
            forged = {"party": r["party"], "combos": r["combos"],
                      "score": r["score"], "feasible": r["feasible"],
                      "filler": r["filler"], "held": r["held"]}
        out.append({
            "refine": None if rp is None else e.refine(
                rp, max_passes=REFINE_PASSES, pool=c["refine_pool"]),
            "comp_score": e.comp_score(c["party"]),
            "comp_score_locked": e.comp_score(c["party"], c["combos"]),
            "redundancy": e.redundancy(c["party"]),
            "size_bucket": e.size_bucket(),
            "forge": forged,
            "swap": None if sp is None else [
                {"weapon": m["weapon"], "score": m["score"], "rank": m["rank"],
                 "off_comp": m["off_comp"],
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
                           "combo": r["combo"]}
                          for r in e.recommend(c["party"], 5)],
            "recommend_locked": [{"weapon": r["weapon"], "score": r["score"]}
                                 for r in e.recommend(c["party"], 5,
                                                      combos=c["combos"])],
            "weaknesses": [{"cap": g["cap"], "gap": g["gap"]}
                           for g in e.weaknesses(c["party"], 5)],
            "uncovered": sorted(e.uncovered_caps(c["party"])),
            "identity": e.comp_identity(c["party"], c["combos"]),
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
            if fa["party"] != fb.get("party") or fa["combos"] != fb.get("combos"):
                errs.append(f"forge roster: py={fa['party']} js={fb.get('party')}")
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
                if abs(ra["score"] - rb["score"]) > EPS or ra["combo"] != rb["combo"]:
                    errs.append(f"score {ra['weapon']}: py={ra['score']!r}/{ra['combo']} "
                                f"js={rb['score']!r}/{rb['combo']}")
        if [r["weapon"] for r in a["recommend_locked"]] != \
                [r["weapon"] for r in b["recommend_locked"]]:
            errs.append("locked recommend order differs")
        else:
            for ra, rb in zip(a["recommend_locked"], b["recommend_locked"]):
                if abs(ra["score"] - rb["score"]) > EPS:
                    errs.append(f"locked score {ra['weapon']}: "
                                f"py={ra['score']!r} js={rb['score']!r}")
        if [g["cap"] for g in a["weaknesses"]] != [g["cap"] for g in b["weaknesses"]]:
            errs.append("weakness order differs")
        if a["uncovered"] != b["uncovered"]:
            errs.append(f"uncovered: py={a['uncovered']} js={b['uncovered']}")
        ia, ib = a["identity"], b.get("identity") or {}
        if (ia["style"] != ib.get("style") or ia["label"] != ib.get("label")
                or ia["strength"] != ib.get("strength")
                or ia["carriers"] != ib.get("carriers")
                or [x["weapon"] for x in ia["conflicts"]]
                != [x["weapon"] for x in ib.get("conflicts") or []]):
            errs.append(f"identity: py={ia['label']}/{ia['carriers']} "
                        f"js={ib.get('label')}/{ib.get('carriers')}")
        elif (abs(ia["melee_share"] - ib.get("melee_share", 9)) > EPS
              or abs(ia["posture"] - ib.get("posture", 9)) > EPS
              or any(abs(ia["mode"][k] - (ib.get("mode") or {}).get(k, 9)) > EPS
                     for k in ia["mode"])):
            errs.append(f"identity shares: py={ia} js={ib}")
        if a["swap"] is not None:
            for ma, mb in zip(a["swap"], b["swap"] or []):
                if ma["rank"] != mb["rank"] or abs(ma["score"] - mb["score"]) > EPS \
                        or ma["off_comp"] != mb.get("off_comp"):
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
