#!/usr/bin/env python3
"""Re-fit content template TARGETS to the median of their fitted comps.

Owner ruling 2026-09-10 ("the data should come from the harvest median"):
a target is what the TYPICAL good comp fields, not the least any comp got
away with. The hand-fitted content rows were written under "0.9 x the
least" from the dressed audit (audit_dressed_templates.py, person units);
this script reads the same audit, the same comps, and writes the MEDIAN
as `target` and the LEAST as `min` (the board's red/orange line).

The soft cap is only ever RAISED here, to 1.15 x the most any comp
fielded (the harvest's own convention, 1.15 x p90), whenever that sits
above the old cap: the dressed supply has grown since the 2026-08-29
fit (kit doctrine, gear actives) and several medians sat above their
old caps (castle_outpost peel 20.5 vs 7.84) — a target above its cap is
incoherent, and a real comp above the cap is evidence the cap was
tight. It is never LOWERED: three comps cannot
justify tightening a band (1.15 x the heaviest of three would call two
healers in a 7-man over-stacked); caps tighten only from the harvest,
where a cell is hundreds of rosters.

Per content, per capability, over the parties the audit maps to it:
  scales: true  -> supply.dressed * base_size / party size  (per person)
  scales: false -> supply.dressed                            (a threshold)
  min = least, target = median, soft_cap = max(old, 1.15 x most).
Only those numbers move; weights, scales, ramps, optional flags, floors
and every comment stay. A capability whose median is 0 keeps its current
row untouched (never invent a number).
Contents with fewer than MIN_COMPS distinct comps are reported and left
alone — their `fit:` block says `minimum` (or `none`) and the board
labels them.

    py -3 pipeline/refit_content_targets.py            # report only
    py -3 pipeline/refit_content_targets.py --apply    # rewrite the YAML
"""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "out", "dressed_template_audit.json")
TEMPLATES = os.path.join(HERE, "templates")
MIN_COMPS = 3


def load_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def per_cap(parties, tpl):
    """{cap: [per-comp values in the row's units]} — scaled per person
    for scaling rows, raw for threshold rows."""
    base = tpl["base_size"]
    reqs = tpl["requirements"]
    out = {}
    for p in parties:
        for row in p["caps"]:
            cap = row["cap"]
            if cap not in reqs:
                continue
            v = row["supply"]["dressed"]
            if reqs[cap].get("scales"):
                v = v * base / p["size"]
            out.setdefault(cap, []).append(v)
    return out


def rewrite(path, changes):
    """Rewrite only `min`/`target`/`soft_cap` on `  cap: {target: X, ...}`
    lines. A `min:` already present is replaced; otherwise it is inserted
    before `target:`. Everything else on the line — and every other line —
    is left byte-for-byte."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for cap, (lo, new, soft) in changes.items():
        pat = re.compile(r"^(\s+%s:\s*\{)(?:min:\s*[0-9.]+,\s*)?(target:\s*)([0-9.]+)"
                         r"([^\n]*?soft_cap:\s*)([0-9.]+)"
                         % re.escape(cap), re.M)
        text, n = pat.subn(lambda m: (f"{m.group(1)}min: {lo:g}, {m.group(2)}{new:g}"
                                      f"{m.group(4)}{soft:g}"),
                           text, count=1)
        if n != 1:
            sys.exit(f"{os.path.basename(path)}: no single target line for {cap}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    apply = "--apply" in sys.argv[1:]
    with open(AUDIT, encoding="utf-8") as f:
        audit = json.load(f)
    by_content = {}
    for p in audit["parties"]:
        by_content.setdefault(p["content"], []).append(p)
    for content in sorted(by_content):
        parties = by_content[content]
        comps = {p["comp"] for p in parties}
        path = os.path.join(TEMPLATES, content + ".yaml")
        tpl = load_yaml(path)
        if len(comps) < MIN_COMPS:
            print(f"{content}: {len(comps)} comp(s) < {MIN_COMPS} - left alone (fit: minimum)")
            continue
        vals = per_cap(parties, tpl)
        changes = {}
        print(f"{content}: {len(comps)} comps, {len(parties)} parties "
              f"(base {tpl['base_size']})")
        print(f"  {'capability':<20} {'old':>7} {'oldcap':>7}    {'min':>7}  {'median':>7}  {'cap':>7}")
        for cap, r in sorted(tpl["requirements"].items()):
            xs = vals.get(cap) or []
            med = round(statistics.median(xs), 2) if xs else 0.0
            lo = round(min(xs), 2) if xs else 0.0
            old, old_soft = r["target"], r["soft_cap"]
            # never tighten on a handful of comps: raise only past the median
            soft = max(old_soft, round(1.15 * max(xs), 2)) if xs else old_soft
            if med <= 0:
                print(f"  {cap:<20} {old:>7} {old_soft:>7}    keep (median 0)")
                continue
            print(f"  {cap:<20} {old:>7} {old_soft:>7}    {lo:>7}  {med:>7}  {soft:>7}")
            if (abs(med - old) > 1e-9 or abs(lo - r.get("min", -1)) > 1e-9
                    or abs(soft - old_soft) > 1e-9):
                changes[cap] = (lo, med, soft)
        if apply and changes:
            rewrite(path, changes)
            print(f"  wrote {len(changes)} row(s) to {os.path.relpath(path, HERE)}")


if __name__ == "__main__":
    main()
