#!/usr/bin/env python3
"""derive_style_bands contracts (2026-09-10, target is the median).

Script-style, NOT pytest: runs derive() on a fixture evidence board and
exits 0 on pass. The real board needs the raw party cache (harvest
checkout); the fixture pins the convention the script encodes.

    py -3 tests/test_style_bands_derive.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import derive_style_bands as dsb  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name
          + (("\n      " + detail) if detail else ""))
    if not cond:
        FAILS.append(name)


def cell(distinct, supply, ref=12):
    return {"distinct": distinct, "size_ref": ref, "supply": supply}


def stat(p10, p50, p90, zero=0.0):
    return {"n": 100, "p10": p10, "p50": p50, "p90": p90, "zero_share": zero}


board = {
    "kite|10-14": cell(201, {
        "heal_burst": stat(1.2, 5.8, 11.0, zero=0.10),   # >5% zeros, p50 > 0
        "silence":    stat(0.0, 0.0, 4.0, zero=0.60),    # p50 == 0
        "peel":       stat(9.0, 20.0, 50.0),
        "anti_zone":  stat(0.0, 0.0, 0.0),               # p90 == 0 -> no row
    }),
    "balanced|10-14": cell(900, {"heal_burst": stat(2.0, 6.5, 12.0)}),
    "kite|15-19": cell(10, {"heal_burst": stat(5.8, 10.3, 16.4)}),  # thin
}
doc = {"_generated": "2026-09-10", "rosters_total": 1000, "board": board}
lines = dsb.derive(doc)
text = "\n".join(lines)


def row(style, band, cap):
    """The requirement line for `cap` inside `bands: style: "band":`."""
    i = text.find(f"  {style}:\n")
    if i < 0:
        return ""
    j = text.find(f'    "{band}":', i)
    if j < 0:
        return ""
    # the cell ends at the next band (`    "`) or the next style (`  x:`)
    ends = [m.start() for m in re.finditer(r'\n(?:    "|  [a-z_]+:)', text[j + 1:])]
    seg = text[j:(j + 1 + min(ends)) if ends else len(text)]
    for ln in seg.splitlines():
        if ln.strip().startswith(cap + ":"):
            return ln
    return ""


hb = row("kite", "10-14", "heal_burst")
check("D1 target is the median (p50), not 0.9 x p10",
      "target:    5.80" in hb, hb)
check("D1b the row carries the bare minimum (p10) beside the target — the "
      "board's red/orange line, never a scoring input",
      "min:    1.20" in hb, hb)
check("D2 soft cap stays 1.15 x p90", "soft_cap:   12.65" in hb, hb)
check("D3 a >5% zero share no longer suppresses the target",
      "target:" in hb and "no minimum" not in hb, hb)
si = row("kite", "10-14", "silence")
check("D4 p50 == 0 writes the soft cap only, content target stands",
      "target:" not in si and "min:" not in si and "soft_cap:    4.60" in si
      and "most winners field none" in si, si)
check("D5 zero p90 writes no row", row("kite", "10-14", "anti_zone") == "")
check("D6 convention line names p50 and carries no zero-share knob",
      "convention: {target_of_p50: 1.0, soft_of_p90: 1.15, min_distinct: 40}"
      in text)
check("D7 the balanced cell is emitted like any style",
      "target:    6.50" in row("balanced", "10-14", "heal_burst"),
      row("balanced", "10-14", "heal_burst"))
check("D8 a thin cell borrows its nearest filled band",
      'borrowed_from: "kite|10-14"' in text)
check("D9 the row comment keeps p10/p50/p90 for the reader",
      "# p10/p50/p90 1.2/5.8/11.0" in hb)

if FAILS:
    print(f"\n{len(FAILS)} failed: {', '.join(FAILS)}")
    sys.exit(1)
print("\nall derive contracts pass")
sys.exit(0)
