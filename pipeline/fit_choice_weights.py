#!/usr/bin/env python3
"""
Capability weights fitted to what killer parties pick. REPORT-ONLY: the
tool prints and records a proposal; a template's weights change only by a
logged decision (tests/VALIDATION.md), written into the template by hand
together with its `weight_fit:` provenance block.

The measurement. Every harvested killer party of --min-size..--max-size
(every weapon known, style = its weapons-only label, the v4h population)
on the TRAINING split (battle % 5 != 0) drops --drops members in turn; for
each drop, every candidate in the engine's suggestion pool (plus the actual
weapon) is priced exactly as `_eval_pick` prices it, and its score is split
into one term per template capability at UNIT base weight, plus synergy,
the meta prior, the duplicate cost and the viability bonus. The split is
checked against the engine's own score for every candidate and the tool
stops (exit 2) on a mismatch above 1e-9: a changed pick formula must update
this tool, never be approximated by it.

The fit. A conditional logit over each drop's candidates: capability
weights (>= 0) and a free coefficient for each non-capability term, so the
duplicate and popularity effects never leak into the weights. A ridge
pulls the weights toward the CURATED weights (the template's
`weight_fit.curated`, else its current weights). THE PULL RULE: the
weakest pull on the grid under which every capability with a curated
weight >= 4 keeps at least half of it; minor capabilities may fall to
zero. Weights are reported rescaled to the curated total, so the balance
between capability and the other score terms stays as committed.

Beside the proposal: the validation-slice likelihood per pull (training
battles with (battle // 5) % 5 == 0), a split-half stability check, and
the feature-level holdout (battle % 5 == 0) ranking of the real pick
under the curated and the fitted weights. The engine run is the real
test: v4h, v4 and the golden suite on a dataset built with the proposal.

What this measures: what winning parties bring, never what makes them
win (standing rule 7; `audit_capability_outcomes.py` is the outcome
side). Content is not recorded on a harvested party, so --content names
the template whose weights and targets the harvest is read against.

Needs numpy (not in requirements.txt: report-only, never in the build or
CI).

    py -3 pipeline/fit_choice_weights.py extract [--content blackzone_roam] [--workers N]
    py -3 pipeline/fit_choice_weights.py fit [--content blackzone_roam]

Out: pipeline/out/choice_fit/<content>_<split>_<i>of<n>.npz (gitignored),
     pipeline/out/choice_weights_<content>.json (the proposal record).
"""
import argparse
import glob
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
SHARDS = os.path.join(OUT, "choice_fit")
HOLDOUT_MOD = 5
SEED = 20260923
KAPPAS = (30.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0)
PULL_FLOOR = 4.0          # the pull rule: curated weights >= this ...
PULL_KEEP = 0.5           # ... keep at least this share
TOLERANCE = 1e-9

try:
    import numpy as np
except ImportError:
    np = None


def _need_numpy():
    if np is None:
        sys.exit("fit_choice_weights.py needs numpy (report-only tool): "
                 "py -3 -m pip install numpy")


def _paths():
    for d in ("engine", "pipeline", "tests"):
        p = os.path.join(ROOT, d)
        if p not in sys.path:
            sys.path.insert(0, p)


# ------------------------------------------------------------ extraction --
def weight_mults(e):
    """Per capability, the factor weight(cap) carries over the base weight:
    the style multiplier and, for the resilience capabilities, the size
    devaluation (Engine.set_content). Defined for a zero base weight too;
    checked against weight(cap) wherever the base weight is nonzero."""
    import engine as E
    out = {}
    for cap, r in e.reqs.items():
        m = e.style_mults.get(cap, 1.0)
        if cap in E.RESILIENCE_CAPS and not e.template.get("st_full_value"):
            m *= e._st_value_mult(e.size)
        if r["weight"] and abs(m * r["weight"] - e.weight(cap)) > TOLERANCE:
            sys.exit(f"weight multiplier for {cap} disagrees with the engine")
        out[cap] = m
    return out


def unit_delta(e, mult, cap, have, gain, have_floor, gain_floor):
    """_marg_fit_from's per-capability delta at base weight 1: coverage and
    headroom at the style-multiplied weight (`mult`), over-stack and the
    hard floor at the base weight."""
    t, soft, g = e.target(cap), e.soft_cap(cap), e.gamma
    cov = min(1.0, (have + gain) / t) ** g - min(1.0, have / t) ** g
    head = 0.0
    if e.headroom > 0.0 and soft > t:
        span = soft - t

        def hb(h):
            return e.headroom * min(max(h - t, 0.0), span) / span
        head = hb(have + gain) - hb(have)
    over = 0.0
    scale = soft if soft > 0 else t

    def ov(h):
        if h <= soft:
            return 0.0
        x = (h - soft) / scale
        return e.overstack_max * x / (1.0 + x)
    over = ov(have + gain) - ov(have)
    floor = 0.0
    f = e.floors.get(cap)
    if f and e.size >= f["min_party_size"]:
        fu, pm = e._floors_eff[cap], f["penalty_mult"]

        def fp(h):
            return pm * (fu - h) / fu if h < fu else 0.0
        floor = fp(have_floor) - fp(have_floor + gain_floor)
    return mult * (cov + head) - over + floor


def price(e, mults, state, w, caps):
    """_eval_pick's search (best combo x kit variant), then the winner's
    per-capability unit deltas and the non-capability terms."""
    extras = e._combo_extras(w)
    dressed = e._dressed_extras(w)
    variants = e.kit_variants(w)
    v0_capped = e._variant_capped(state, w, variants[0][1])
    fallback = e._variant_fallback.get(w) or ()
    best = None
    for vkey, vgears in variants:
        if e._variant_capped(state, w, vgears):
            continue
        if vkey in fallback and not v0_capped:
            continue
        dext = dressed[vkey]
        for i in range(len(extras)):
            val, d_fit, d_syn = e._combo_score_dressed(
                state, w, i, extras[i], dext[i], vkey)
            if best is None or val > best[0]:
                best = (val, d_fit, d_syn, i, vkey)
    phi = {}
    if best is None:
        best = (0.0, 0.0, 0.0, None, "v0")
    else:
        i, vkey = best[3], best[4]
        wextra, dextra = extras[i], dressed[vkey][i]
        s, s_syn = state["s"], state["s_syn"]
        split = s is not s_syn
        if dextra is wextra:
            adj = e._nonstack_adjust(state, w, i, wextra)
            floor_s, floor_g = (s_syn, adj) if split else (s, adj)
        else:
            adj = e._nonstack_adjust(state, w, i, dextra)
            floor_s, floor_g = s_syn, e._nonstack_adjust(state, w, i, wextra)
        for cap, gain in adj.items():
            if cap in e.reqs and gain:
                phi[cap] = unit_delta(e, mults[cap], cap, s.get(cap, 0.0), gain,
                                      floor_s.get(cap, 0.0),
                                      floor_g.get(cap, 0.0))
    score, d_fit, d_syn, meta, _combo = e._pick_tail(state, w, best[:4])
    dup = state["counts"].get(w, 0) + 1 - e._dup_free(w)
    dup = dup if dup > 0 else 0
    viab = e.viability_w * e.viability_of(w)
    base = {c: e.reqs[c]["weight"] for c in e.reqs}
    fit_recon = sum(base[c] * v for c, v in phi.items())
    score_recon = (e.alpha * fit_recon + e.beta * d_syn + e.delta * meta
                   + viab - e.rho * dup)
    err = max(abs(fit_recon - d_fit), abs(score_recon - score))
    row = [phi.get(c, 0.0) for c in caps]
    return row, d_syn, meta, dup, viab, score, err


def extract_shard(task):
    """One worker: the parties of one split whose ordinal % n == shard."""
    _paths()
    content, split, shard, n, drops, lo, hi = task
    from engine import Engine
    import rosters_io
    import tier2_blindtest as T
    doc = rosters_io.load()
    with open(os.path.join(OUT, "party_styles.json"), encoding="utf-8") as f:
        styles = json.load(f)
    probe = Engine(content=content)
    caps = list(probe.data["templates"][content]["requirements"])
    parties = T._harvest_parties(doc, styles, probe, lo, hi, 0)
    del doc
    train = split == "train"
    ps = [p for p in parties if (p["battle"] % HOLDOUT_MOD != 0) == train]
    ps.sort(key=lambda p: (p["battle"], p["index"]))
    ps = ps[shard::n]
    engines = {}
    X, SYN, META, DUP, VIAB, SCORE, CH, SITE = ([] for _ in range(8))
    BATTLE, PARTY, STYLE, SIZE, INPOOL = [], [], [], [], []
    worst = 0.0
    for p in ps:
        # per-party seed: the drops never depend on the sharding
        rng = random.Random(f"{SEED}:{p['battle']}:{p['index']}")
        key = (p["size"], p["style"])
        if key not in engines:
            e = Engine(content=content, size=p["size"], style=p["style"])
            engines[key] = (e, weight_mults(e))
        e, mults = engines[key]
        ws = p["weapons"]
        for i in sorted(rng.sample(range(len(ws)), min(drops, len(ws)))):
            rest, actual = ws[:i] + ws[i + 1:], ws[i]
            state = e.party_state(rest)
            pool = list(e.suggest_pool())
            INPOOL.append(actual in pool)
            if actual not in pool:
                pool.append(actual)
            rows = np.zeros((len(pool), len(caps)), dtype=np.float32)
            for j, w in enumerate(pool):
                row, syn, meta, dup, viab, score, err = price(e, mults, state, w, caps)
                worst = max(worst, err)
                rows[j] = row
                SYN.append(syn); META.append(meta); DUP.append(dup)
                VIAB.append(viab); SCORE.append(score)
                CH.append(w == actual); SITE.append(len(BATTLE))
            X.append(rows)
            BATTLE.append(p["battle"]); PARTY.append(p["index"])
            STYLE.append(p["style"]); SIZE.append(p["size"])
    if worst > TOLERANCE:
        return {"shard": shard, "split": split, "error": worst}
    os.makedirs(SHARDS, exist_ok=True)
    path = os.path.join(SHARDS, f"{content}_{split}_{shard}of{n}.npz")
    np.savez_compressed(
        path, caps=np.array(caps), X=np.vstack(X) if X else np.zeros((0, len(caps))),
        syn=np.array(SYN), meta=np.array(META), dup=np.array(DUP, dtype=np.float64),
        viab=np.array(VIAB), score=np.array(SCORE), choice=np.array(CH, dtype=np.int8),
        site=np.array(SITE, dtype=np.int64), battle=np.array(BATTLE, dtype=np.int64),
        party=np.array(PARTY, dtype=np.int32),
        style=np.array(STYLE), size=np.array(SIZE, dtype=np.int16),
        in_pool=np.array(INPOOL, dtype=bool))
    return {"shard": shard, "split": split, "parties": len(ps),
            "situations": len(BATTLE), "rows": len(CH), "error": worst}


def cmd_extract(args):
    _need_numpy()
    for old in glob.glob(os.path.join(SHARDS, f"{args.content}_*.npz")):
        os.remove(old)
    n_train = max(1, args.workers - max(1, args.workers // 4))
    n_hold = max(1, args.workers - n_train)
    tasks = ([(args.content, "train", i, n_train, args.drops, args.min_size, args.max_size)
              for i in range(n_train)]
             + [(args.content, "hold", i, n_hold, args.drops, args.min_size, args.max_size)
                for i in range(n_hold)])
    t0 = time.time()
    worst = 0.0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(extract_shard, tasks):
            worst = max(worst, r["error"])
            if "parties" in r:
                print(f"  {r['split']}[{r['shard']}]: {r['parties']} parties, "
                      f"{r['situations']} drops, {r['rows']} candidate rows")
    if worst > TOLERANCE:
        print(f"the capability split misses the engine's score by {worst:.2e} "
              f"> {TOLERANCE:g}: the pick formula changed - update price() "
              f"before fitting")
        return 2
    print(f"extracted in {time.time() - t0:.0f}s; largest split error {worst:.1e}")
    return 0


# --------------------------------------------------------------- the fit --
def _load(content, split):
    parts = sorted(glob.glob(os.path.join(SHARDS, f"{content}_{split}_*of*.npz")))
    if not parts:
        sys.exit(f"no {split} shards for {content}: run `extract` first")
    cols = {k: [] for k in ("X", "syn", "meta", "dup", "viab", "score",
                            "choice", "site")}
    per = {k: [] for k in ("battle", "party", "style", "size", "in_pool")}
    off, caps = 0, None
    for f in parts:
        z = np.load(f, allow_pickle=False)
        caps = list(z["caps"])
        for k in cols:
            cols[k].append(z[k] + off if k == "site" else z[k])
        for k in per:
            per[k].append(z[k])
        off += len(z["battle"])
    d = {k: np.concatenate(v) for k, v in cols.items()}
    d.update({k: np.concatenate(v) for k, v in per.items()})
    order = np.argsort(d["site"], kind="stable")
    for k in cols:
        d[k] = d[k][order]
    d["X"] = d["X"].astype(np.float64)
    d["starts"] = np.flatnonzero(np.r_[True, np.diff(d["site"]) != 0])
    return d, caps


def _lse(u, starts):
    mx = np.maximum.reduceat(u, starts)
    counts = np.diff(np.r_[starts, len(u)])
    return mx + np.log(np.add.reduceat(np.exp(u - np.repeat(mx, counts)),
                                       starts)), counts


def _loglik(u, d):
    lse, _ = _lse(u, d["starts"])
    return float(u[d["choice"] == 1].sum() - lse.sum())


def _design(d, nuis):
    return np.hstack([d["X"]] + [d[k][:, None] for k in nuis])


def _fit(A, d, K, b0, prior, kappa, iters=80):
    """Damped Newton on b = [weights (K, >= 0), nuisance (free)], ridge
    `kappa` on the weights toward `prior`."""
    P = A.shape[1]
    b = b0.astype(np.float64).copy()
    pen = np.r_[np.full(K, kappa), np.zeros(P - K)]
    active = np.zeros(P, bool)
    chosen = A[d["choice"] == 1].sum(0)

    def objective(bb):
        lse, _ = _lse(A @ bb, d["starts"])
        return float(chosen @ bb - lse.sum() - 0.5 * (pen * (bb - prior) ** 2).sum())

    def gradient(bb):
        u = A @ bb
        lse, counts = _lse(u, d["starts"])
        p = np.exp(u - np.repeat(lse, counts))
        xbar = np.add.reduceat(A * p[:, None], d["starts"])
        return chosen - xbar.sum(0) - pen * (bb - prior), p, xbar

    f_cur = objective(b)
    for _ in range(iters):
        g, p, xbar = gradient(b)
        H = (A * p[:, None]).T @ A - xbar.T @ xbar + np.diag(pen)
        free = ~active
        step = np.zeros_like(b)
        step[free] = np.linalg.lstsq(H[np.ix_(free, free)], g[free], rcond=None)[0]
        t = 1.0
        while True:
            nb = b + t * step
            nb[:K] = np.maximum(nb[:K], 0.0)
            f_new = objective(nb)
            if f_new >= f_cur - 1e-9 or t < 1e-6:
                break
            t /= 2
        active |= np.r_[nb[:K] <= 0.0, np.zeros(P - K, bool)] & (step < 0)
        done = f_new - f_cur < 1e-7
        b, f_cur = nb, f_new
        if done:
            g, _p, _x = gradient(b)
            release = active & (g > 1e-6)
            if not release.any():
                break
            active &= ~release
    return b


def _temperature(d):
    """P ~ exp(tau * score): the engine's own score as a choice model. The
    likelihood is concave in tau: bracket, then bisect the gradient."""
    s = d["score"]
    chosen = s[d["choice"] == 1].sum()

    def grad(tau):
        lse, counts = _lse(tau * s, d["starts"])
        return chosen - (np.exp(tau * s - np.repeat(lse, counts)) * s).sum()
    lo, hi = 0.0, 1.0
    while grad(hi) > 0 and hi < 1e6:
        lo, hi = hi, hi * 2
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if grad(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def _ranks(u, d):
    """The v4h reading: the real pick's rank among the pool; a pick outside
    the pool (its appended row) is a miss."""
    ends = np.r_[d["starts"][1:], len(u)]
    ranks = []
    for k, (a, b) in enumerate(zip(d["starts"], ends)):
        if not d["in_pool"][k]:
            ranks.append(None)
            continue
        uu = u[a:b]
        c = int(np.flatnonzero(d["choice"][a:b])[0])
        ranks.append(1 + int((uu > uu[c]).sum()))
    inside = np.array([r for r in ranks if r is not None], dtype=float)
    n = len(ranks)
    return {"drops": n, "outside_pool": n - len(inside),
            "mrr": round(float((1 / inside).sum() / n), 4),
            "median_rank": float(np.median(inside)),
            "top3": round(float((inside <= 3).sum() / n), 4),
            "top10": round(float((inside <= 10).sum() / n), 4)}


def _subset(d, mask):
    rows = mask[d["site"]]
    out = {k: d[k][rows] for k in ("X", "syn", "meta", "dup", "viab", "score", "choice")}
    _, out["site"] = np.unique(d["site"][rows], return_inverse=True)
    out["starts"] = np.flatnonzero(np.r_[True, np.diff(out["site"]) != 0])
    for k in ("battle", "party", "style", "size", "in_pool"):
        out[k] = d[k][mask]
    return out


def cmd_fit(args):
    _need_numpy()
    _paths()
    import yaml
    tr, caps = _load(args.content, "train")
    ho, _ = _load(args.content, "hold")
    with open(os.path.join(HERE, "templates", f"{args.content}.yaml"),
              encoding="utf-8") as f:
        tpl = yaml.safe_load(f)
    reqs = tpl["requirements"]
    curated_map = (tpl.get("weight_fit") or {}).get("curated") or {
        c: reqs[c]["weight"] for c in reqs}
    if sorted(curated_map) != sorted(caps):
        sys.exit("the shards' capabilities differ from the template: re-extract")
    with open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8") as f:
        sw = json.load(f)["scoring"]["weights"]
    alpha, beta, delta, rho = sw["alpha"], sw["beta"], sw["delta"], sw["rho"]
    committed = np.array([reqs[c]["weight"] for c in caps], dtype=float)
    curated = np.array([curated_map[c] for c in caps], dtype=float)
    K = len(caps)
    nuis = ["syn", "meta", "dup"] + (["viab"] if np.abs(tr["viab"]).max() > 0 else [])

    def engine_u(d, w):
        return (alpha * d["X"] @ w + beta * d["syn"] + delta * d["meta"]
                - rho * d["dup"] + d["viab"])

    # the unit split reproduces the committed engine exactly
    recon = np.abs(engine_u(tr, committed) - tr["score"]).max()
    if recon > 1e-6:
        sys.exit(f"shards disagree with the committed weights by {recon:.2e}: "
                 "re-extract after any template or scoring change")
    tau = _temperature(tr)
    signs = {"syn": beta, "meta": delta, "dup": -rho, "viab": 1.0}
    b_prior = np.r_[tau * alpha * curated, [tau * signs[k] for k in nuis]]
    A_tr = _design(tr, nuis)
    val_mask = (tr["battle"] // HOLDOUT_MOD) % 5 == 0
    fit_part, val_part = _subset(tr, ~val_mask), _subset(tr, val_mask)
    A_fit, A_val = _design(fit_part, nuis), _design(val_part, nuis)
    n_val = len(val_part["starts"])

    def normalised(theta):
        return theta * curated.sum() / theta.sum()

    def rule_ok(w):
        return all(wi >= PULL_KEEP * ci for wi, ci in zip(w, curated) if ci >= PULL_FLOOR)

    grid, chosen = [], None
    for kappa in KAPPAS:
        b = _fit(A_fit, fit_part, K, b_prior, b_prior, kappa)
        w = normalised(b[:K])
        grid.append({"kappa": kappa,
                     "validation_ll": round(_loglik(A_val @ b, val_part) / n_val, 4),
                     "validation_ranks": _ranks(engine_u(val_part, w), val_part),
                     "pull_rule": rule_ok(w)})
        if chosen is None and rule_ok(w):
            chosen = kappa
    if chosen is None:
        sys.exit("no pull on the grid keeps the curated weights >= "
                 f"{PULL_FLOOR:g} at {PULL_KEEP:.0%}: nothing to propose")
    b = _fit(A_tr, tr, K, b_prior, b_prior, chosen)
    fitted = normalised(b[:K])
    # split-half stability: the same fit on each half of the training battles
    halves = []
    for h in (0, 1):
        part = _subset(tr, (tr["battle"] // HOLDOUT_MOD) % 2 == h)
        bh = _fit(_design(part, nuis), part, K, b_prior, b_prior, chosen)
        halves.append(normalised(bh[:K]))
    half_r = float(np.corrcoef(halves[0], halves[1])[0, 1])
    holdout = {"committed": _ranks(engine_u(ho, committed), ho),
               "curated": _ranks(engine_u(ho, curated), ho),
               "fitted": _ranks(engine_u(ho, np.round(fitted, 1)), ho)}
    uniform = float(-np.log(np.diff(np.r_[val_part["starts"], len(val_part["score"])])).mean())
    record = {
        "content": args.content,
        "split": f"battle % {HOLDOUT_MOD} != 0 (training); holdout scored only",
        "train_parties": int(len(np.unique(np.c_[tr["battle"], tr["party"]], axis=0))),
        "train_drops": int(len(tr["starts"])), "holdout_drops": int(len(ho["starts"])),
        "engine_temperature": round(tau, 5),
        "validation_ll_uniform": round(uniform, 4),
        "validation_ll_committed": round(_loglik(tau * engine_u(val_part, committed),
                                                 val_part) / n_val, 4),
        "pull_rule": f"weakest pull keeping every curated weight >= {PULL_FLOOR:g} "
                     f"at >= {PULL_KEEP:.0%} of it",
        "kappa": chosen, "grid": grid,
        "nuisance": {k: round(float(v / (tau)), 4) for k, v in zip(nuis, b[K:])},
        "split_half_correlation": round(half_r, 4),
        "curated": {c: float(v) for c, v in zip(caps, curated)},
        "committed": {c: float(v) for c, v in zip(caps, committed)},
        "fitted": {c: round(float(v), 1) for c, v in zip(caps, fitted)},
        "holdout": holdout,
        "semantics": ("REPORT-ONLY proposal: weights fitted to what training-"
                      "split killer parties pick (revealed preference), pulled "
                      "toward the curated weights; never what makes a party "
                      "win. A template changes only by a logged decision."),
    }
    path = os.path.join(OUT, f"choice_weights_{args.content}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"Choice-fitted weights - {args.content}: {record['train_drops']} training "
          f"drops, {record['holdout_drops']} holdout drops")
    print(f"  validation LL per drop: uniform {uniform:.4f}, committed "
          f"{record['validation_ll_committed']:.4f}")
    for g in grid:
        vr = g["validation_ranks"]
        print(f"  pull {g['kappa']:>7g}: validation LL {g['validation_ll']:.4f}  "
              f"MRR {vr['mrr']:.3f}  top-10 {vr['top10']:.1%}  "
              f"rule {'ok' if g['pull_rule'] else 'broken'}"
              + ("   <- chosen" if g["kappa"] == chosen else ""))
    print(f"  split-half correlation of the fitted weights: {half_r:.3f}")
    print(f"  {'capability':<19}{'curated':>8}{'fitted':>8}")
    for c in sorted(caps, key=lambda c: -record["fitted"][c]):
        print(f"  {c:<19}{record['curated'][c]:>8g}{record['fitted'][c]:>8g}")
    print("  holdout (feature level; combos as the committed weights choose them):")
    for k, r in holdout.items():
        print(f"    {k:<10} MRR {r['mrr']:.3f}  median rank {r['median_rank']:g}  "
              f"top-3 {r['top3']:.1%}  top-10 {r['top10']:.1%}  outside pool "
              f"{r['outside_pool']}/{r['drops']}")
    print(f"wrote {os.path.relpath(path, ROOT)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("extract", cmd_extract), ("fit", cmd_fit)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--content", default="blackzone_roam")
    ex = sub.choices["extract"]
    ex.add_argument("--drops", type=int, default=2)
    ex.add_argument("--min-size", type=int, default=10)
    ex.add_argument("--max-size", type=int, default=20)
    ex.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
