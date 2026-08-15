#!/usr/bin/env python3
"""
JS/Python engine parity — pipeline/app_scoring.js must produce the SAME
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
SCORING_JS = os.path.join(ROOT, "pipeline", "app_scoring.js")
RUNNER = os.path.join(HERE, "js_parity_runner.js")
EPS = 1e-9
N_CASES = 60
SEED = 20260812


def make_cases(data):
    rng = random.Random(SEED)
    weapons = sorted(data["weapons"])
    contents = sorted(data["templates"])
    styles = sorted(data.get("styles") or {"balanced": {}})
    cases = []
    for i in range(N_CASES):
        content = contents[i % len(contents)]
        size = data["templates"][content]["base_size"]
        n = rng.randint(0, min(size, 12))
        cases.append({"content": content, "size": size,
                      "style": styles[i % len(styles)],
                      "party": [rng.choice(weapons) for _ in range(n)]})
    return cases


# swap_review is a full-pool sweep PER MEMBER — cover it on every 6th case
# with the party capped at 6 members so the parity run stays fast.
SWAP_EVERY, SWAP_MAX_PARTY = 6, 6


def swap_case(i, party):
    return party[:SWAP_MAX_PARTY] if i % SWAP_EVERY == 0 else None


def py_results(cases):
    out = []
    for i, c in enumerate(cases):
        e = Engine(content=c["content"], size=c["size"], style=c["style"])
        sp = swap_case(i, c["party"])
        out.append({
            "swap": None if sp is None else [
                {"weapon": m["weapon"], "score": m["score"], "rank": m["rank"],
                 "options": [{"weapon": o["weapon"], "score": o["score"]}
                             for o in m["options"]]}
                for m in e.swap_review(sp)],
            "fitness": e.fitness(c["party"]),
            "synergy": e.synergy(c["party"]),
            "max_fitness": e.max_fitness(),
            "recommend": [{"weapon": r["weapon"], "score": r["score"]}
                          for r in e.recommend(c["party"], 5)],
            "weaknesses": [{"cap": g["cap"], "gap": g["gap"]}
                           for g in e.weaknesses(c["party"], 5)],
            "uncovered": sorted(e.uncovered_caps(c["party"])),
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
            proc = subprocess.run(["node", RUNNER, SCORING_JS, DATASET, cases_path],
                                  capture_output=True, text=True, timeout=120)
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
        for k in ("fitness", "synergy", "max_fitness"):
            if abs(a[k] - b[k]) > EPS:
                errs.append(f"{k}: py={a[k]!r} js={b[k]!r}")
        if [r["weapon"] for r in a["recommend"]] != [r["weapon"] for r in b["recommend"]]:
            errs.append(f"recommend order: py={[r['weapon'] for r in a['recommend']]} "
                        f"js={[r['weapon'] for r in b['recommend']]}")
        else:
            for ra, rb in zip(a["recommend"], b["recommend"]):
                if abs(ra["score"] - rb["score"]) > EPS:
                    errs.append(f"score {ra['weapon']}: py={ra['score']!r} js={rb['score']!r}")
        if [g["cap"] for g in a["weaknesses"]] != [g["cap"] for g in b["weaknesses"]]:
            errs.append("weakness order differs")
        if a["uncovered"] != b["uncovered"]:
            errs.append(f"uncovered: py={a['uncovered']} js={b['uncovered']}")
        if a["swap"] is not None:
            for ma, mb in zip(a["swap"], b["swap"] or []):
                if ma["rank"] != mb["rank"] or abs(ma["score"] - mb["score"]) > EPS:
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
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
