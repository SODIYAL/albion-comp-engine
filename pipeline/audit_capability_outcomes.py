#!/usr/bin/env python3
"""
Capability outcomes: do the template weights separate winning parties from
losing ones? REPORT-ONLY — a measurement for notes/findings/, never a
scoring input. A weight change it suggests is a logged decision in
tests/VALIDATION.md, made by hand, never written by this script.

The template weights are curation judgment, or fitted to what killer
parties pick (a template's `weight_fit` block, pipeline/fit_choice_weights.py).
The targets are measured from winners; the weights say how much each
capability matters, and neither source measures them against winning.
This audit measures them against OUTCOMES: the harvested killer
parties carry each party's kills and deaths (sample_parties.py analyze,
summed over the members the official battle roster places in the fight).

Per eligible party (size --min-size..--max-size, every weapon known, at
least half the members in the fight) the engine at the party's size,
balanced style, under --content, measures each capability's coverage
exactly as fitness() values it: min(1, supply / target) ^ gamma, naked
(weapon supply, the unit the hard floors read). The label:

  win   kills >= 2 x deaths (the artifact's "dominant" definition)
  loss  kills <  deaths
  the traded-even middle is left out.

Three measurements:

  1. Univariate: per capability, mean coverage in winners vs losers and
     the capability's own AUC (0.5 = no separation).
  2. Fitted weights: an L2 logistic regression of win on the coverage
     vector (+ party size), fitted on the TRAINING split (battle % M != 0,
     the split every harvest-derived table learns from), coefficients in
     coverage units so they read beside the template weights; a cluster
     bootstrap over battles gives each coefficient's 90% interval.
  3. Holdout check (battle % M == 0): the AUC of the template's own
     fitness() score against the AUC of the fitted model. If the template
     already separates as well as the fit, the weights are not the gap.

CAVEATS, printed with the report:
  * The inclusion filter is "scored at least one kill", so the worst
    losers never enter; losses here are parties that traded and lost.
  * Outcome is confounded with numbers, item power and skill; nothing
    here controls for the enemy. A coefficient is association, not cause.
  * A killer party is not a comp: large battles are coalitions.
  * Content is not recorded on a harvested party; --content sets whose
    weights and targets are tested (default blackzone_roam, as v4h).

Run:  py -3 pipeline/audit_capability_outcomes.py [--content C] [--boot N]
Out:  pipeline/out/capability_outcomes.json
Needs the outcome fields (in_fight / kills / deaths) on the party records:
rerun `sample_parties.py --pages 0` on the harvest machine (the fold does
this) if the artifact predates them.
"""
import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from engine import Engine  # noqa: E402
import rosters_io  # noqa: E402

OUT = os.path.join(HERE, "out", "capability_outcomes.json")


# ------------------------------------------------------------ labelling --
def label(p):
    """1 win, 0 loss, None for the traded-even middle or no outcome."""
    k, d = p.get("kills"), p.get("deaths")
    if k is None or d is None:
        return None
    if k >= 2 * d and k > 0:
        return 1
    if k < d:
        return 0
    return None


def eligible(p, lo, hi, known):
    n = p.get("size") or 0
    if not (lo <= n <= hi) or p.get("known_weapons") != n:
        return False
    if (p.get("in_fight") or 0) * 2 < n:
        return False
    return all(w in known for w in p.get("weapons") or [])


# ------------------------------------------------------------- features --
def coverage_row(e, caps, weapons):
    s = e.effective_supply(weapons)
    return [min(1.0, s.get(c, 0.0) / e.target(c)) ** e.gamma
            if e.target(c) > 0 else 0.0 for c in caps]


# ------------------------------------------------------ small linear alg --
def _solve(a, b):
    """Gaussian elimination with partial pivoting; a is n x n, b length n."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ArithmeticError("singular system")
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _sigmoid(z):
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def fit_logistic(x, y, l2=1.0, iters=25):
    """L2-penalised logistic regression by Newton's method. x rows carry
    no intercept column (one is added, unpenalised). Returns
    [intercept] + coefficients."""
    p = len(x[0]) + 1
    beta = [0.0] * p
    for _ in range(iters):
        g = [0.0] * p
        h = [[0.0] * p for _ in range(p)]
        for xi, yi in zip(x, y):
            row = [1.0] + xi
            mu = _sigmoid(sum(b * v for b, v in zip(beta, row)))
            w = mu * (1.0 - mu)
            for a in range(p):
                g[a] += (yi - mu) * row[a]
                ra = w * row[a]
                for b in range(a, p):
                    h[a][b] += ra * row[b]
        for a in range(p):
            for b in range(a):
                h[a][b] = h[b][a]
        for a in range(1, p):
            g[a] -= l2 * beta[a]
            h[a][a] += l2
        step = _solve(h, g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-8:
            break
    return beta


def auc(scores, y):
    """Mann-Whitney AUC with average ranks for ties."""
    pairs = sorted(zip(scores, y))
    ranks, i = [0.0] * len(pairs), 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2.0 + 1.0
        i = j + 1
    pos = sum(1 for _, t in pairs if t == 1)
    neg = len(pairs) - pos
    if not pos or not neg:
        return None
    rs = sum(r for r, (_, t) in zip(ranks, pairs) if t == 1)
    return (rs - pos * (pos + 1) / 2.0) / (pos * neg)


def spearman(a, b):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else None


# ------------------------------------------------------------ the audit --
def standardise(rows):
    cols = list(zip(*rows))
    mu = [sum(c) / len(c) for c in cols]
    sd = [math.sqrt(sum((v - m) ** 2 for v in c) / len(c)) or 1.0
          for c, m in zip(cols, mu)]
    return mu, sd


def apply_std(rows, mu, sd):
    return [[(v - m) / s for v, m, s in zip(r, mu, sd)] for r in rows]


def fit_raw(rows, y, l2):
    """Fit on standardised features, return coefficients in RAW units
    (per unit of coverage / per player) plus the scaler."""
    mu, sd = standardise(rows)
    beta = fit_logistic(apply_std(rows, mu, sd), y, l2)
    return [b / s for b, s in zip(beta[1:], sd)], (beta, mu, sd)


def predict(model, rows):
    beta, mu, sd = model
    return [sum(b * v for b, v in zip(beta, [1.0] + r))
            for r in apply_std(rows, mu, sd)]


def run(doc, content, lo, hi, mod, boot, l2, seed):
    probe = Engine(content=content)
    known = set(probe.weapons)
    caps = list(probe.reqs)
    engines, rows = {}, []
    skipped = {"no_outcome": 0, "even": 0, "ineligible": 0}
    for p in doc.get("parties", []):
        if not eligible(p, lo, hi, known):
            skipped["ineligible"] += 1
            continue
        y = label(p)
        if y is None:
            skipped["no_outcome" if p.get("kills") is None else "even"] += 1
            continue
        n = p["size"]
        e = engines.get(n)
        if e is None:
            e = engines[n] = Engine(content=content, size=n, style="balanced")
        rows.append({"battle": p["battle"], "y": y, "size": n,
                     "cov": coverage_row(e, caps, p["weapons"]),
                     "fit": e.fitness(p["weapons"])})
    train = [r for r in rows if not mod or r["battle"] % mod != 0]
    hold = [r for r in rows if mod and r["battle"] % mod == 0]
    if len(train) < 50 or len({r["y"] for r in train}) < 2:
        sys.exit(f"too few labelled training parties ({len(train)}); "
                 f"skipped {skipped} — does the artifact carry kills/deaths?")

    # 1. univariate
    uni = {}
    for j, c in enumerate(caps):
        w_ = [r["cov"][j] for r in train if r["y"] == 1]
        l_ = [r["cov"][j] for r in train if r["y"] == 0]
        uni[c] = {"win_mean": round(sum(w_) / len(w_), 4),
                  "loss_mean": round(sum(l_) / len(l_), 4),
                  "auc": round(auc([r["cov"][j] for r in train],
                                   [r["y"] for r in train]) or 0.5, 4)}

    # 2. fitted weights (+ size control), cluster bootstrap over battles
    def x_of(rs):
        return [r["cov"] + [r["size"]] for r in rs]
    y_tr = [r["y"] for r in train]
    coef, model = fit_raw(x_of(train), y_tr, l2)
    boots = []
    if boot:
        rng = random.Random(seed)
        by_b = {}
        for r in train:
            by_b.setdefault(r["battle"], []).append(r)
        keys = sorted(by_b)
        for _ in range(boot):
            sample = [r for k in (rng.choice(keys) for _ in keys)
                      for r in by_b[k]]
            if len({r["y"] for r in sample}) < 2:
                continue
            try:
                boots.append(fit_raw(x_of(sample), [r["y"] for r in sample],
                                     l2)[0])
            except ArithmeticError:
                continue

    def interval(j):
        if len(boots) < 10:
            return None
        v = sorted(b[j] for b in boots)
        return [round(v[int(0.05 * (len(v) - 1))], 4),
                round(v[int(0.95 * (len(v) - 1))], 4)]

    weights = [probe.weight(c) for c in caps]
    fitted = {}
    for j, c in enumerate(caps):
        fitted[c] = {"template_weight": weights[j],
                     "coef": round(coef[j], 4), "ci90": interval(j),
                     **uni[c]}
    size_coef = round(coef[len(caps)], 4)

    # 3. holdout: template fitness vs the fitted model
    held = None
    if len(hold) >= 30 and len({r["y"] for r in hold}) == 2:
        y_h = [r["y"] for r in hold]
        held = {"parties": len(hold), "wins": sum(y_h),
                "auc_template_fitness": round(auc([r["fit"] for r in hold], y_h), 4),
                "auc_fitted_model": round(auc(predict(model, x_of(hold)), y_h), 4),
                "auc_size_only": round(auc([r["size"] for r in hold], y_h), 4)}

    return {
        "content": content, "style": "balanced", "sizes": [lo, hi],
        "holdout_mod": mod, "l2": l2, "bootstrap": len(boots),
        "labelled": len(rows), "train": len(train),
        "train_wins": sum(y_tr), "skipped": skipped,
        "size_coef": size_coef,
        "rank_agreement_spearman": round(spearman(weights, coef[:len(caps)]), 4),
        "train_auc_template_fitness": round(
            auc([r["fit"] for r in train], y_tr), 4),
        "capabilities": fitted, "holdout": held,
        "semantics": ("REPORT-ONLY. win = kills >= 2 x deaths, loss = "
                      "kills < deaths, over the members the battle roster "
                      "places in the fight; coverage = min(1, supply/target)"
                      "^gamma, naked, balanced style; coefficients are "
                      "association, not cause, and never a scoring input."),
    }


def report(r):
    print(f"Capability outcomes — {r['content']}, balanced, sizes "
          f"{r['sizes'][0]}-{r['sizes'][1]}, training split battle%"
          f"{r['holdout_mod']}!=0")
    print(f"  {r['train']} labelled training parties ({r['train_wins']} wins, "
          f"{r['train'] - r['train_wins']} losses); skipped {r['skipped']}")
    print(f"  {'capability':<16} {'weight':>6} {'coef':>8} {'90% CI':>18} "
          f"{'win':>6} {'loss':>6} {'AUC':>6}")
    order = sorted(r["capabilities"].items(), key=lambda kv: -kv[1]["coef"])
    for c, v in order:
        ci = (f"[{v['ci90'][0]:+.2f}, {v['ci90'][1]:+.2f}]"
              if v["ci90"] else "n/a")
        print(f"  {c:<16} {v['template_weight']:>6g} {v['coef']:>+8.3f} "
              f"{ci:>18} {v['win_mean']:>6.3f} {v['loss_mean']:>6.3f} "
              f"{v['auc']:>6.3f}")
    print(f"  party size coefficient {r['size_coef']:+.3f} per player")
    print(f"  rank agreement template weight vs fitted coef (Spearman): "
          f"{r['rank_agreement_spearman']}")
    print(f"  training AUC of the template's fitness(): "
          f"{r['train_auc_template_fitness']}")
    h = r["holdout"]
    if h:
        print(f"  HOLDOUT ({h['parties']} parties, {h['wins']} wins): AUC "
              f"template fitness {h['auc_template_fitness']}, fitted model "
              f"{h['auc_fitted_model']}, size alone {h['auc_size_only']}")
    else:
        print("  holdout: too few labelled parties to score")
    print("  caveat: parties with no kill are never recorded, so losses are "
          "parties that traded and lost; outcome is confounded with "
          "numbers, item power and skill; association, not cause.")
    print("  REPORT-ONLY: a weight change is a logged decision "
          "(tests/VALIDATION.md), never written by this script.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--content", default="blackzone_roam")
    ap.add_argument("--min-size", type=int, default=10)
    ap.add_argument("--max-size", type=int, default=20)
    ap.add_argument("--holdout-mod", type=int, default=5)
    ap.add_argument("--boot", type=int, default=50,
                    help="cluster-bootstrap resamples over battles (0 = off)")
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--json", default=OUT)
    args = ap.parse_args()
    if not rosters_io.exists():
        sys.exit("out/party_rosters.json.gz missing — run the harvest fold")
    doc = rosters_io.load()
    if not any("kills" in p for p in doc.get("parties", [])):
        sys.exit("the party artifact carries no outcome fields (kills / "
                 "deaths / in_fight): rerun `py -3 pipeline/sample_parties.py "
                 "--pages 0` on the harvest machine, then this audit")
    r = run(doc, args.content, args.min_size, args.max_size,
            args.holdout_mod, args.boot, args.l2, args.seed)
    report(r)
    with open(args.json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(r, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"wrote {os.path.relpath(args.json, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
