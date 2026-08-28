#!/usr/bin/env python3
"""
Calibration sensitivity harness (Phases 8-10/12 scaffolding, 2026-08-27).

Evaluates the engine over the expert calibration set (calibration/)
under bounded parameter sweeps and writes
pipeline/out/calibration_report.json. IT CHANGES NOTHING: every
coefficient keeps its shipped value; the report is a SENSITIVITY MAP
plus generated discrimination cases for future expert rounds.

HONESTY CLAUSE (printed into the report): with the current calibration
set (4 train cases from one owner round, empty validation/holdout — see
calibration/README.md) no sweep result licenses a coefficient change.
The work-order rule stands: only genuine calibration disagreements
(category 5), demonstrated on validation data and confirmed on unseen
holdout, may ever move a number — and stable REGIONS are reported,
never argmax points.

Mechanics:
- Outer-blend overrides are applied as engine attributes (read at
  scoring time); a SELF-CHECK proves each override actually took effect
  (comp_score identity at 1e-9, and attr-vs-set_content equivalence for
  curve parameters so no precompute table silently bakes a value).
- Synergy-bonus overrides mutate e.synergies + set_content (rebuilds
  the active-pair table).
- Golden regressions per sweep point run tests/test_golden.py against a
  PATCHED COPY of the dataset via the BION_DATASET path override — the
  real dataset is never touched.

Run:  py -3 pipeline/calibrate_scoring.py [--golden] [--quick]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from engine import Engine  # noqa: E402
import gear_join  # noqa: E402

OUT = os.path.join(HERE, "out", "calibration_report.json")
EPS = 1e-9
FULL_RANK = 10 ** 6

OUTER_PARAMS = ("alpha", "beta", "delta", "rho", "viability_w")
CURVE_PARAMS = ("gamma", "headroom", "overstack_max")
ATTR_TO_YAML = {"viability_w": "viability"}   # dataset key differs

SWEEPS = {
    "alpha": [round(0.30 + 0.05 * i, 2) for i in range(11)],
    "beta": [round(0.00 + 0.05 * i, 2) for i in range(11)],
    "delta": [round(0.00 + 0.05 * i, 2) for i in range(7)],
    "rho": [round(0.125 * i, 3) for i in range(7)],
    "viability_w": [round(0.05 * i, 2) for i in range(7)],
}
SYNERGY_LADDER = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
CURVE_CAPS = ("purge", "heal_sustain", "engage", "peel", "clump_create",
              "heal_reduction", "resist_shred", "sustained_dps")


# ------------------------------------------------------------ case loading
def load_cases():
    import yaml
    with open(os.path.join(ROOT, "calibration", "cases.yaml"),
              encoding="utf-8") as f:
        cases = {c["id"]: c for c in (yaml.safe_load(f) or [])}

    def split(name):
        with open(os.path.join(ROOT, "calibration", name),
                  encoding="utf-8") as f:
            return [cid for cid in (yaml.safe_load(f) or [])]
    return cases, {"train": split("train_cases.yaml"),
                   "validation": split("validation_cases.yaml"),
                   "holdout": split("holdout_cases.yaml")}


# ------------------------------------------------------------ overrides
def current_values(e):
    return {p: getattr(e, p) for p in OUTER_PARAMS + CURVE_PARAMS}


def apply_overrides(e, overrides):
    for k, v in overrides.items():
        setattr(e, k, v)


def self_check(e):
    """Prove overrides take effect through the real scoring path."""
    party = sorted(e.pool)[:4]
    saved = current_values(e)
    problems = []
    # 1) blend identity: comp_score == alpha*f + beta*s + delta*m + vw*v - rho*r
    f, s = e.fitness(party), e.synergy(party)
    m = sum(e.meta_of(w) for w in party)
    v = sum(e.viability_of(w) for w in party)
    r = e.redundancy(party)
    for k in OUTER_PARAMS:
        apply_overrides(e, {k: saved[k] + 0.11})
        got = e.comp_score(party)
        want = (e.alpha * f + e.beta * s + e.delta * m
                + e.viability_w * v - e.rho * r)
        if abs(got - want) > EPS:
            problems.append(f"{k}: blend identity broke ({got} vs {want})")
        apply_overrides(e, {k: saved[k]})
    # 2) curve params: attr override == set_content-refreshed engine (no
    #    precompute table may bake the value)
    for k in CURVE_PARAMS:
        apply_overrides(e, {k: saved[k] * 0.5 + 0.05})
        f1 = e.fitness(party)
        e.set_content(e.content, e.size, e.style)
        f2 = e.fitness(party)
        if abs(f1 - f2) > EPS:
            problems.append(f"{k}: value baked into a set_content table "
                            f"({f1} vs {f2})")
        if abs(f1 - f) < EPS and k != "headroom":
            # gamma/overstack must actually move fitness on a partial party
            problems.append(f"{k}: override did not change fitness")
        apply_overrides(e, {k: saved[k]})
    e.set_content(e.content, e.size, e.style)
    return problems


# ------------------------------------------------------------ evaluation
class Evaluator:
    def __init__(self):
        self._engines = {}

    def engine(self, content, size, style):
        key = (content, size, style)
        if key not in self._engines:
            self._engines[key] = Engine(content=content, size=size,
                                        style=style)
        return self._engines[key]

    def eval_case(self, case, mode, overrides):
        e = self.engine(case["content"], case["size"],
                        case.get("style", "balanced"))
        saved = current_values(e)
        apply_overrides(e, overrides)
        e.set_dressing(mode == "d")
        try:
            party = case["party"]
            gl = None
            if mode == "d":
                gl = (case.get("gears")
                      or gear_join.doctrine_gears(e, party))
            full = e.recommend(party, FULL_RANK, gears=gl)
            order = [r["weapon"] for r in full]
            best = case["expert"]["best"]
            good = set(case["expert"].get("good") or [])
            top3 = order[:3]
            rank = order.index(best) + 1 if best in order else None
            return {
                "case": case["id"], "rank": rank,
                "top1": order[:1] == [best], "top3": best in top3,
                "acceptable": any(k in top3 for k in ({best} | good)),
                "bad_in_top3": (case["expert"].get("bad") in top3)
                               if case["expert"].get("bad") else None,
                "need_hit": None,
                "confidence": case["expert"].get("confidence"),
            }
        finally:
            e.set_dressing(True)
            apply_overrides(e, saved)

    def metrics(self, cases, ids, mode, overrides):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import tier2_blindtest as t2
        rows = [self.eval_case(cases[cid], mode, overrides) for cid in ids]
        return t2._metrics(rows)


# ------------------------------------------------------------ golden counter
def golden_regressions(overrides, scratch):
    """Run the golden suite against a PATCHED dataset copy. Returns
    (failures, total) — counted, never auto-fixed."""
    src = os.path.join(HERE, "out", "dataset-latest.json")
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    w = data["scoring"]["weights"]
    for k, v in overrides.items():
        w[ATTR_TO_YAML.get(k, k)] = v
    patched = os.path.join(scratch, "dataset-patched.json")
    with open(patched, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f)
    env = dict(os.environ, BION_DATASET=patched)
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tests",
                                                     "test_golden.py")],
                       capture_output=True, text=True, env=env, timeout=600)
    m = re.search(r"(\d+)/(\d+) golden tests passed", p.stdout or "")
    if not m:
        return None, None
    passed, total = int(m.group(1)), int(m.group(2))
    return total - passed, total


# ------------------------------------------------------------ synergy flips
def synergy_flip_points(quick=False):
    """Per pair: a discrimination party (strong side-A) and two candidates
    (B-specialist vs the best generic pick) — at which bonus does the
    specialist overtake? These are the Phase-9 expert questions plus the
    engine's current flip map."""
    e = Engine(content="blackzone_roam", size=10, style="balanced")
    out = []
    for pi, (a, b, bonus0) in enumerate(list(e.synergies)):
        if a not in e.reqs or b not in e.reqs:
            continue
        suppliers_a = sorted(
            (w for w in e.pool if e.member_extra(w, None).get(a, 0) > 0),
            key=lambda w: (-e.member_extra(w, None).get(a, 0), w))[:2]
        supplier_b = max(
            (w for w in e.pool if e.member_extra(w, None).get(b, 0) > 0
             and w not in suppliers_a),
            key=lambda w: (e.member_extra(w, None).get(b, 0), w),
            default=None)
        if len(suppliers_a) < 2 or supplier_b is None:
            continue
        party = suppliers_a
        generic = next((r["weapon"] for r in e.recommend(party, 5)
                        if r["weapon"] != supplier_b
                        and e.member_extra(r["weapon"], None).get(b, 0) == 0),
                       None)
        if generic is None:
            continue
        ladder = SYNERGY_LADDER[::3] if quick else SYNERGY_LADDER
        points = []
        for v in ladder:
            e.synergies[pi] = (a, b, v)
            e.set_content(e.content, e.size, e.style)
            top = e.recommend(party, 1, pool=[generic, supplier_b])
            points.append({"bonus": v, "winner": top[0]["weapon"],
                           "specialist_wins":
                               top[0]["weapon"] == supplier_b})
        e.synergies[pi] = (a, b, bonus0)
        e.set_content(e.content, e.size, e.style)
        flip = next((p["bonus"] for p in points if p["specialist_wins"]),
                    None)
        out.append({
            "pair": [a, b], "current_bonus": bonus0,
            "party": party, "specialist": supplier_b, "generic": generic,
            "flip_bonus": flip, "points": points,
            "expert_question": (
                f"Party already strong on {a} ({party}). Next pick: "
                f"{generic} (better general coverage) or {supplier_b} "
                f"(excellent {b} follow-up)?"),
        })
    return out


# ------------------------------------------------------------ curve probes
def curve_probes():
    """Phase-10 discrimination ladders: 0/1/2/3 distinct sources of a
    capability — the engine's current marginal fitness of the next
    source, recorded beside the question for experts."""
    e = Engine(content="blackzone_roam", size=10, style="balanced")
    out = []
    for cap in CURVE_CAPS:
        if cap not in e.reqs:
            continue
        suppliers = sorted(
            (w for w in e.pool if e.member_extra(w, None).get(cap, 0) > 0),
            key=lambda w: (-e.member_extra(w, None).get(cap, 0), w))[:3]
        if len(suppliers) < 3:
            continue
        steps = []
        for k in range(4):
            party = suppliers[:k]
            f = e.fitness(party)
            steps.append({
                "sources": k, "party": list(party),
                "supply": round(e.effective_supply(party).get(cap, 0.0), 4),
                "fitness": round(f, 6),
                "marginal_fitness": None if k == 0 else
                    round(f - steps[-1]["fitness"], 6),
            })
        out.append({
            "cap": cap, "target": round(e.target(cap), 4),
            "soft_cap": round(e.soft_cap(cap), 4), "ladder": steps,
            "expert_question": (
                f"Parties with 0/1/2/3 meaningful {cap} sources "
                f"({', '.join(suppliers)}) — how valuable is EACH next "
                f"source, relative to the previous one?"),
        })
    return out


# ------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", action="store_true",
                    help="count golden regressions per sweep point (slow)")
    ap.add_argument("--quick", action="store_true",
                    help="thin ladders (smoke run)")
    args = ap.parse_args()

    cases, splits = load_cases()
    ev = Evaluator()
    probe = Engine()
    current = current_values(probe)
    checks = self_check(probe)
    if checks:
        for c in checks:
            print(f"SELF-CHECK FAIL: {c}")
        sys.exit(2)
    print("self-check: overrides verified through the real scoring path")

    base_metrics = {mode: ev.metrics(cases, splits["train"], mode, {})
                    for mode in ("w", "d")}

    sweeps = {}
    scratch = tempfile.mkdtemp(prefix="bion_calib_")
    for param, values in SWEEPS.items():
        if args.quick:
            values = values[::max(1, len(values) // 3)]
        rows = []
        for v in values:
            o = {param: v}
            row = {"value": v,
                   "train_w": ev.metrics(cases, splits["train"], "w", o),
                   "train_d": ev.metrics(cases, splits["train"], "d", o)}
            if args.golden:
                fails, total = golden_regressions(o, scratch)
                row["golden_regressions"] = fails
                row["golden_total"] = total
            rows.append(row)
            print(f"  {param}={v}: train-d top3 "
                  f"{row['train_d']['top3']:.2f} rank "
                  f"{row['train_d']['mean_rank']}"
                  + (f" golden-regressions {row.get('golden_regressions')}"
                     if args.golden else ""))
        sweeps[param] = {"current": current[param], "points": rows}

    report = {
        "kind": "calibration_report",
        "honesty": (
            "SENSITIVITY MAP, NOT A CALIBRATION. Train n="
            f"{len(splits['train'])} (one expert, one content, legacy-"
            "harness answers); validation and holdout are EMPTY. No "
            "coefficient may move on this evidence — every value below "
            "remains PROVISIONAL at its shipped setting until expert "
            "rounds populate validation/holdout (calibration/README.md)."),
        "current_values": current,
        "splits": {k: len(v) for k, v in splits.items()},
        "baseline_train_metrics": base_metrics,
        "sweeps": sweeps,
        "synergy_flip_points": synergy_flip_points(args.quick),
        "curve_probes": curve_probes(),
        "style_multipliers": {
            "status": ("directional hypotheses (styles.yaml); no style-"
                       "specific expert picks exist yet — Phase 12 waits "
                       "for styled expert rounds"),
        },
    }
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    print(f"\nwrote {OUT}")
    print(report["honesty"])


if __name__ == "__main__":
    main()
