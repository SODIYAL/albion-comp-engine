#!/usr/bin/env python3
"""
Generate the capability MAGNITUDE review page.

Standing rule (expert, 2026-08-13, born from the knockback_displace pass):
every capability score encodes IMPACT MAGNITUDE, not existence. This page
lays out, per capability, every weapon's score side by side with the sheet
comment and the evidence spell's dumps text (which carries the real numbers:
meters, seconds, targets, percentages) so magnitude outliers pop out.

REVIEW-BY-EXCEPTION, like review/effects.html: the expert scans a capability
board and flags rows whose score does not match the dumps numbers around it.
Every correction goes through the sheet (+ golden case when it changes a
ruling), never through this page.

Auto-flags (also printed to console):
  RULE  same evidence spell grounding the same capability at different
        scores — violates the line-consistency rule, always a bug
  PASV  PASSIVE_*/WEAPON_STATS evidence grounding score >= 2 — passives are
        usually minor; each one needs an explicit justification
  TOP   score 3 — the top of every ladder is reviewed first

Usage:  py -3 pipeline/build_magnitude_review.py   ->  review/magnitude.html
"""
import glob
import html
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")

CAP_RE = re.compile(
    r"-\s*\{cap:\s*(\w+),\s*score:\s*(\d+),\s*evidence:\s*(\w+)\s*\}"
    r"(?:\s*#\s*(.*))?")
WEAPON_RE = re.compile(r"^-\s*weapon:\s*(\w+)")


def parse_sheets():
    """Raw-text parse so the inline # comments (the curation 'why') survive.

    Tree-pool rows (sheets/pools/) are EXPANDED to every weapon they apply to
    via sheets_lib.compose, so the boards still show the full per-weapon
    picture; their comments come from the pool file."""
    sys.path.insert(0, HERE)
    import yaml
    import sheets_lib
    rows = []
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        weapon = None
        for line in open(path, encoding="utf-8"):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            m = WEAPON_RE.match(stripped)
            if m:
                weapon = m.group(1)
                continue
            m = CAP_RE.search(stripped)
            if m and weapon:
                cap, score, evidence, comment = m.groups()
                rows.append({"weapon": weapon, "cap": cap, "score": int(score),
                             "evidence": evidence, "comment": (comment or "").strip(),
                             "sheet": os.path.basename(path)})
    # pool comments, keyed (subcategory, cap, evidence)
    pool_comment = {}
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "pools", "*.yaml"))):
        sub = os.path.splitext(os.path.basename(path))[0]
        for line in open(path, encoding="utf-8"):
            m = CAP_RE.search(line.strip())
            if m:
                cap, _, evidence, comment = m.groups()
                pool_comment[(sub, cap, evidence)] = (comment or "").strip()
    lines_db = sheets_lib.load_weapon_lines(OUT)
    pools = sheets_lib.load_pools()
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        for entry in (yaml.safe_load(open(path, encoding="utf-8")) or []):
            wkey = entry.get("weapon")
            if not wkey:
                continue
            own = {(c.get("cap"), c.get("evidence"))
                   for c in entry.get("capabilities", []) if isinstance(c, dict)}
            line = lines_db.get(wkey)
            sub = (line or {}).get("subcategory")
            for c in sheets_lib.compose(entry, line, pools):
                key = (c.get("cap"), c.get("evidence"))
                if key in own:
                    continue                       # already parsed with comment
                rows.append({"weapon": wkey, "cap": c["cap"],
                             "score": int(c.get("score", 0)),
                             "evidence": c.get("evidence"),
                             "comment": pool_comment.get((sub,) + key, ""),
                             "sheet": f"pools/{sub}.yaml"})
    return rows


def main():
    dataset = json.load(open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8"))
    spells = json.load(open(os.path.join(OUT, "spell_index.json"), encoding="utf-8"))
    names = {k: w["display_name"] for k, w in dataset["weapons"].items()}
    rows = parse_sheets()

    by_cap = defaultdict(list)
    for r in rows:
        by_cap[r["cap"]].append(r)

    # RULE flag: same (cap, evidence) at different scores. WEAPON_STATS is
    # exempt — it is a per-weapon stat citation, not a shared spell, so
    # scores legitimately differ. CAVEAT for triage: a flagged pair can be
    # legitimate when the higher score's total includes an E-supplement on
    # top of the shared QW spell — but then the comment MUST say so; a
    # flagged pair with no such comment is a bug.
    rule_flags = set()
    for cap, rs in by_cap.items():
        by_ev = defaultdict(set)
        for r in rs:
            if r["evidence"] != "WEAPON_STATS":
                by_ev[r["evidence"]].add(r["score"])
        for ev, scores in by_ev.items():
            if len(scores) > 1:
                rule_flags.add((cap, ev))

    def flags_of(r):
        f = []
        if (r["cap"], r["evidence"]) in rule_flags:
            f.append("RULE")
        if (r["evidence"].startswith("PASSIVE") or r["evidence"] == "WEAPON_STATS") \
                and r["score"] >= 2:
            f.append("PASV")
        if r["score"] == 3:
            f.append("TOP")
        return f

    n_rule = sum(1 for r in rows if "RULE" in flags_of(r))
    n_pasv = sum(1 for r in rows if "PASV" in flags_of(r))
    n_top = sum(1 for r in rows if r["score"] == 3)

    def spell_cell(ev):
        s = spells.get(ev)
        if not s:
            return "<em>not in spell index</em>"
        bits = []
        if s.get("cooldown"):
            bits.append("CD %ss" % s["cooldown"])
        if s.get("cast_range") and s["cast_range"] not in ("0", ""):
            bits.append("range %s" % s["cast_range"])
        desc = (s.get("description") or "").replace("\n", " ")
        if len(desc) > 260:
            desc = desc[:260] + "…"
        head = " · ".join(bits)
        return "%s%s" % ("<b>%s</b> — " % head if head else "", html.escape(desc))

    caps_sorted = sorted(by_cap, key=lambda c: (-len(by_cap[c]), c))
    toc = " ".join('<a href="#%s">%s <small>(%d)</small></a>' % (c, c, len(by_cap[c]))
                   for c in caps_sorted)

    sections = []
    for cap in caps_sorted:
        rs = sorted(by_cap[cap], key=lambda r: (-r["score"], names.get(r["weapon"], r["weapon"])))
        hist = defaultdict(int)
        for r in rs:
            hist[r["score"]] += 1
        histtxt = "  ".join("%d×score %d" % (hist[s], s) for s in sorted(hist, reverse=True))
        body = []
        for r in rs:
            fl = flags_of(r)
            cls = " ".join(f.lower() for f in fl)
            body.append(
                '<tr class="%s"><td class="s">%d</td><td>%s</td>'
                '<td class="ev">%s</td><td class="fl">%s</td>'
                '<td class="cm">%s</td><td class="dx">%s</td></tr>' % (
                    cls, r["score"], html.escape(names.get(r["weapon"], r["weapon"])),
                    html.escape(r["evidence"]), " ".join(fl),
                    html.escape(r["comment"]), spell_cell(r["evidence"])))
        sections.append(
            '<h2 id="%s">%s <small>%d weapons · %s</small></h2>'
            '<table><tr><th>score</th><th>weapon</th><th>evidence</th>'
            '<th>flags</th><th>sheet comment</th><th>dumps text (the numbers)</th></tr>'
            "%s</table>" % (cap, cap, len(rs), histtxt, "".join(body)))

    page = """<!doctype html><meta charset="utf-8">
<title>Capability magnitude review</title>
<style>
 body{background:#14161b;color:#d5d9e0;font:14px/1.45 system-ui;margin:24px}
 a{color:#7fb3ff;text-decoration:none;margin-right:10px}
 table{border-collapse:collapse;width:100%%;margin:8px 0 28px}
 th,td{border:1px solid #2a2e36;padding:4px 8px;text-align:left;vertical-align:top}
 th{background:#1c1f26} small{color:#8a92a0;font-weight:normal}
 td.s{font-weight:bold;text-align:center} td.ev{font-family:monospace;font-size:12px}
 td.cm{color:#aab2c0;font-size:13px} td.dx{color:#8a92a0;font-size:12px}
 tr.top td.s{color:#ffd479} tr.rule td{background:#3a2226}
 tr.pasv td{background:#332b1d} td.fl{color:#ff9a9a;font-size:11px}
 .legend{color:#8a92a0;margin-bottom:16px}
</style>
<h1>Capability magnitude review</h1>
<p class="legend">Rule: scores encode impact MAGNITUDE, not existence.
%d rows · flags: %d RULE (same spell, same cap, different scores — always a
bug) · %d PASV (passive/stat evidence at 2+) · %d TOP (score-3 ladder tops,
review first). Corrections go through the sheets, never this page.</p>
<p>%s</p>
%s""" % (len(rows), n_rule, n_pasv, n_top, toc, "".join(sections))

    outdir = os.path.join(ROOT, "review")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "magnitude.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)

    print("wrote review/magnitude.html — %d rows across %d capabilities" %
          (len(rows), len(by_cap)))
    print("  flags: %d RULE, %d PASV, %d TOP(score-3)" % (n_rule, n_pasv, n_top))
    for cap, ev in sorted(rule_flags):
        scores = sorted({r["score"] for r in by_cap[cap] if r["evidence"] == ev})
        who = sorted(names.get(r["weapon"], r["weapon"]) for r in by_cap[cap]
                     if r["evidence"] == ev)
        print("  RULE  %-18s %-28s scores %s  (%s)" %
              (cap, ev, scores, ", ".join(who)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
