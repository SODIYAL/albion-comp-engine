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
    cases = []
    for i in range(N_CASES):
        content = contents[i % len(contents)]
        size = data["templates"][content]["base_size"]
        n = rng.randint(0, min(size, 12))
        cases.append({"content": content, "size": size,
                      "party": [rng.choice(weapons) for _ in range(n)]})
    return cases


def py_results(cases):
    out = []
    for c in cases:
        e = Engine(content=c["content"], size=c["size"])
        out.append({
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
        if errs:
            bad += 1
            print(f"CASE {i} ({c['content']}, party {len(c['party'])}): " + "; ".join(errs))
    print(f"{N_CASES - bad}/{N_CASES} parity cases identical "
          f"(tolerance {EPS}, contents: {sorted(data['templates'])})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
