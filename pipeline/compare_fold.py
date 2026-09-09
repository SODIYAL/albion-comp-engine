"""Before/after report for a harvest fold (2026-09-09, owner: "set it up").

Compares the artifacts in the working tree (the fold just derived) with
the ones at a git revision (default HEAD - the previous fold) and writes
the tables the owner reads before committing: style-board cell sizes,
style-band target movement, kit churn split by how thin the evidence was,
weapons crossing the uniform-extension line, meta-prior rows, pooled
slots. REPORT ONLY - nothing here feeds a build or a score; it answers
"did this fold give better information" with the same measurements used
on 2026-09-09 (VALIDATION.md). Usage:

    py -3 pipeline/compare_fold.py [--base HEAD] [--out notes/findings/<date>-fold-report.md]
"""
import argparse
import collections
import datetime
import json
import os
import statistics
import subprocess
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARTIFACTS = {
    "rosters": "pipeline/out/party_rosters.json",
    "dataset": "pipeline/out/dataset-latest.json",
    "bands": "pipeline/templates/style_bands.yaml",
    "prior": "pipeline/out/meta_prior.json",
    "board": "pipeline/out/style_roster_evidence.json",
}
UNIFORM_VOTERS = 35   # KB_UNI_MIN in build_dataset.py (voters, 2026-09-04)

KIT_DUMP = r'''
import sys, json
sys.path.insert(0, sys.argv[2])
from engine import Engine
out = {}
for size, st in ((20, "balanced"), (20, "clap"), (7, "balanced")):
    e = Engine(content="blackzone_roam", size=size, style=st)
    for w in sorted(e.weapons):
        kit = e.kit_options(w).get("kit") or {}
        out[f"{size}|{st}|{w}"] = {s: [v.get("gear"), bool(v.get("pooled")),
                                       (v.get("doctrine_n") or [0, 0])[0]]
                                   for s, v in kit.items()}
json.dump(out, open(sys.argv[1], "w"))
'''


def git_show(rev, path, dest):
    with open(dest, "wb") as fh:
        subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT,
                       stdout=fh, check=True)


def load_json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def leaves(x, path=()):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from leaves(v, path + (str(k),))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from leaves(v, path + (str(i),))
    else:
        yield path, x


def group_voters(rosters):
    v = collections.defaultdict(set)
    for b in rosters.get("builds") or []:
        if (b.get("party_size") or 0) >= 10:
            v[b["weapon"]].add(b.get("player"))
    return {w: len(s) for w, s in v.items()}


def dump_kits(dataset_path, dest):
    env = dict(os.environ)
    env["BION_DATASET"] = dataset_path
    script = os.path.join(tempfile.gettempdir(), "compare_fold_kits.py")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(KIT_DUMP)
    subprocess.run([sys.executable, script, dest,
                    os.path.join(ROOT, "engine")], env=env, check=True,
                   cwd=ROOT)
    return load_json(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD",
                    help="git revision holding the previous fold's artifacts")
    ap.add_argument("--out", default=None,
                    help="markdown report path (default notes/findings/"
                         "<date>-fold-report.md)")
    args = ap.parse_args()
    stamp = datetime.date.today().isoformat()
    out_path = args.out or os.path.join(
        ROOT, "notes", "findings", f"{stamp}-fold-report.md")

    tmp = tempfile.mkdtemp(prefix="fold_")
    old = {}
    for key, rel in ARTIFACTS.items():
        dest = os.path.join(tmp, os.path.basename(rel))
        git_show(args.base, rel, dest)
        old[key] = dest
    new = {key: os.path.join(ROOT, rel) for key, rel in ARTIFACTS.items()}

    lines = [f"# Fold report {stamp} - working tree vs `{args.base}`", ""]

    # ---- corpus ----
    ro, rn = load_json(old["rosters"]), load_json(new["rosters"])
    so, sn = ro["summary"], rn["summary"]
    lines += ["## Corpus", "",
              "| unit | before | after |", "|---|---|---|"]
    for k, label in (("battles", "battles"), ("parties", "killer parties"),
                     ("builds", "observed builds"),
                     ("builds_full_kit", "builds with a full kit"),
                     ("median_coverage", "median gear coverage")):
        lines.append(f"| {label} | {so.get(k)} | {sn.get(k)} |")
    lines.append("")

    # ---- style board ----
    bo, bn = load_json(old["board"]), load_json(new["board"])
    lines += ["## Style board (rosters of 10+ per style x band cell; floor 40)", "",
              f"labelled rosters {bo.get('rosters_total')} -> {bn.get('rosters_total')}; "
              f"labels {bo.get('labels')} -> {bn.get('labels')}", "",
              "| cell | before | after | status |", "|---|---|---|---|"]
    for k in sorted(bn["board"]):
        a = (bo["board"].get(k) or {}).get("distinct", 0)
        b = bn["board"][k].get("distinct", 0)
        lines.append(f"| {k} | {a} | {b} | {'ok' if b >= 40 else 'UNDER FLOOR (borrows)'} |")
    lines.append("")

    # ---- style bands ----
    with open(old["bands"], encoding="utf-8") as fh:
        yo = yaml.safe_load(fh)
    with open(new["bands"], encoding="utf-8") as fh:
        yn = yaml.safe_load(fh)
    lo, ln = dict(leaves(yo)), dict(leaves(yn))
    tgt = [(p, lo[p], ln[p]) for p in ln
           if p in lo and p[-1] in ("target", "soft_cap")
           and isinstance(ln[p], (int, float)) and isinstance(lo[p], (int, float))]
    rel = [abs(b - a) / a for _p, a, b in tgt if a]
    moved = sum(1 for _p, a, b in tgt if a != b)
    lines += ["## Style-band rows (target / soft cap)", ""]
    if rel:
        rel_s = sorted(rel)
        lines.append(f"{len(tgt)} rows compared, {moved} moved; median |relative move| "
                     f"{statistics.median(rel):.3f}, p90 {rel_s[int(0.9 * (len(rel_s) - 1))]:.3f}")
        lines += ["", "| row | before | after |", "|---|---|---|"]
        for p, a, b in sorted(tgt, key=lambda t: - abs(t[2] - t[1]) / (t[1] or 1))[:10]:
            lines.append(f"| {'/'.join(p[1:])} | {a} | {b} |")
    lines.append("")

    # ---- kits ----
    ko = dump_kits(old["dataset"], os.path.join(tmp, "kits_old.json"))
    kn = dump_kits(new["dataset"], os.path.join(tmp, "kits_new.json"))
    lines += ["## Generated kits (blackzone_roam; slots changed, by the evidence behind the old pick)", ""]
    for ss in ("20|balanced", "20|clap", "7|balanced"):
        cat = collections.Counter()
        ex = collections.defaultdict(list)
        pooled_o = pooled_n = 0
        for k in kn:
            if not k.startswith(ss + "|"):
                continue
            w = k.split("|")[2]
            oo, nn = ko.get(k) or {}, kn[k]
            pooled_o += sum(1 for v in oo.values() if v[1])
            pooled_n += sum(1 for v in nn.values() if v[1])
            for s in set(oo) | set(nn):
                a, b = oo.get(s), nn.get(s)
                if (a or [None])[0] == (b or [None])[0]:
                    continue
                if a and a[1]:
                    c = ("was pooled (thin) -> own evidence" if b and not b[1]
                         else "pooled -> pooled")
                elif not a:
                    c = "slot appeared"
                elif a[2] < 10:
                    c = "own evidence under 10 votes"
                elif a[2] < 30:
                    c = "own evidence 10-29 votes"
                else:
                    c = "own evidence 30+ votes (meta shift or noise)"
                cat[c] += 1
                ex[c].append(f"{w}:{s} {a[0] if a else None}({a[2] if a else 0})"
                             f"->{b[0] if b else None}({b[2] if b else 0})")
        lines.append(f"**{ss}** - pooled slots {pooled_o} -> {pooled_n}, "
                     f"{sum(cat.values())} slots changed")
        lines.append("")
        for c, v in cat.most_common():
            lines.append(f"- {v} {c}, e.g. {', '.join(ex[c][:2])}")
        lines.append("")

    # ---- voters ----
    vo, vn = group_voters(ro), group_voters(rn)
    ws = list(load_json(new["dataset"])["weapons"])
    crossed = sorted(w for w in ws if vo.get(w, 0) < UNIFORM_VOTERS <= vn.get(w, 0))
    under = sorted((w for w in ws if vn.get(w, 0) < UNIFORM_VOTERS),
                   key=lambda w: vn.get(w, 0))
    stalled = [w for w in under if vn.get(w, 0) - vo.get(w, 0) <= 2]
    lines += [f"## Group voters (uniform extension needs {UNIFORM_VOTERS})", "",
              f"- crossed the line this fold: {len(crossed)} - {', '.join(crossed) or 'none'}",
              f"- still under: {len(under)}; gained two or fewer voters: {len(stalled)} "
              f"({', '.join(stalled[:12])}{'...' if len(stalled) > 12 else ''})",
              ""]

    # ---- meta prior ----
    po, pn = load_json(old["prior"])["meta_prior"], load_json(new["prior"])["meta_prior"]
    lines += ["## Meta prior rows per bucket", "",
              "| bucket | before | after | entered | left |", "|---|---|---|---|---|"]
    for b in ("small", "mid", "large"):
        a, c = po.get(b) or {}, pn.get(b) or {}
        lines.append(f"| {b} | {len(a)} | {len(c)} | {', '.join(sorted(set(c) - set(a))) or '-'} "
                     f"| {', '.join(sorted(set(a) - set(c))) or '-'} |")
    lines.append("")

    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    # the console may be cp1252 (a Git-Bash-spawned Windows console)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.stdout.write(text)
    try:
        shown = os.path.relpath(out_path, ROOT)
    except ValueError:          # the report lives on another drive
        shown = out_path
    print(f"wrote {shown}")


if __name__ == "__main__":
    main()
