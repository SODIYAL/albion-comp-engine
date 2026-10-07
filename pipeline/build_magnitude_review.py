#!/usr/bin/env python3
"""
Generate the capability MAGNITUDE review page.

Standing rule (born from the knockback_displace curation pass):
every capability score encodes IMPACT MAGNITUDE, not existence. This page
lays out, per capability, every weapon's score side by side with the sheet
comment and the evidence spell's dumps text (which carries the real numbers:
meters, seconds, targets, percentages) so magnitude outliers pop out.

REVIEW-BY-EXCEPTION, like review/effects.html: the curator scans a capability
board and flags rows whose score does not match the dumps numbers around it.
Every correction goes through the sheet (+ golden case when it changes a
recorded call), never through this page.

Auto-flags (also printed to console):
  RULE  same evidence spell (and `use:`) grounding the same capability at
        different scores — violates the line-consistency rule, always a bug
  PASV  PASSIVE_*/WEAPON_STATS evidence grounding score >= 4 (1-7 scale) — passives are
        usually minor; each one needs an explicit justification
  TOP   score >= 6 — the top of every ladder is reviewed first

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

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

sys.path.insert(0, HERE)
import sheets_lib  # noqa: E402

WEAPON_RE = re.compile(r"^-\s*weapon:\s*(\w+)")


def row_comments(path):
    """{(weapon, cap, evidence, use): comment} for the scored rows of one
    sheet or pool file (weapon is None in a pool file).

    YAML drops comments, so the ROWS come from yaml + sheets_lib.compose and
    only the comment text (the curation 'why') is read here: a `- {...}`
    flow row is parsed by yaml whatever keys it carries (`use:` included),
    the text after its closing brace is its comment, and comment-only lines
    whose `#` sits in the same column continue that comment. A row without
    a score (an `except:` entry) carries no comment."""
    out = {}
    weapon, last = None, None          # last: (key, column of its '#')
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            m = WEAPON_RE.match(stripped)
            if m:
                weapon, last = m.group(1), None
                continue
            if stripped.startswith("#"):
                if last and line.index("#") == last[1]:
                    out[last[0]] += " " + stripped.lstrip("#").strip()
                else:
                    last = None
                continue
            last = None
            if not stripped.startswith("- {"):
                continue
            close = stripped.find("}")
            if close < 0:
                continue
            try:
                row = yaml.safe_load(stripped[2:close + 1])
            except yaml.YAMLError:
                continue
            if not isinstance(row, dict) or "score" not in row:
                continue
            key = (weapon, row.get("cap"), row.get("evidence"), row.get("use"))
            rest = stripped[close + 1:]
            out[key] = rest.split("#", 1)[1].strip() if "#" in rest else ""
            if "#" in rest:
                last = (key, line.index("#", line.index("}")))
    return out


def parse_sheets():
    """Every row the build composes, per weapon: yaml + sheets_lib.compose
    over the weapon entries (sheets/<tree>.yaml, one file per weapon tree),
    so a row the build reads is a row the board shows, `use:` variants
    included. Tree-pool rows (sheets/pools/) are EXPANDED to every weapon
    they apply to, so the boards show the full per-weapon picture; their
    comment and file are the pool's."""
    lines_db = sheets_lib.load_weapon_lines(OUT)
    pools = sheets_lib.load_pools()
    pool_comment = {}
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "pools", "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        sub = doc.get("subcategory") or os.path.splitext(os.path.basename(path))[0]
        for (_, cap, ev, use), text in row_comments(path).items():
            pool_comment[(sub, cap, ev, use)] = text
    rows = []
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        sheet = os.path.basename(path)
        comments = row_comments(path)
        with open(path, encoding="utf-8") as f:
            entries = yaml.safe_load(f) or []
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("weapon"):
                continue
            wkey = entry["weapon"]
            own = {(c.get("cap"), c.get("evidence"))
                   for c in (entry.get("capabilities") or []) if isinstance(c, dict)}
            line = lines_db.get(wkey)
            sub = (line or {}).get("subcategory")
            for c in sheets_lib.compose(entry, line, pools):
                cap, ev, use = c.get("cap"), c.get("evidence"), c.get("use")
                if not cap:
                    continue
                if (cap, ev) in own:
                    comment, src = comments.get((wkey, cap, ev, use), ""), sheet
                else:
                    comment = pool_comment.get((sub, cap, ev, use), "")
                    src = f"pools/{sub}.yaml"
                rows.append({"weapon": wkey, "cap": cap,
                             "score": int(c.get("score") or 0),
                             "evidence": ev or "-", "use": use,
                             "comment": comment, "sheet": src})
    return rows


def main():
    dataset = json.load(open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8"))
    spells = json.load(open(os.path.join(OUT, "spell_index.json"), encoding="utf-8"))
    names = {k: w["display_name"] for k, w in dataset["weapons"].items()}
    rows = parse_sheets()

    by_cap = defaultdict(list)
    for r in rows:
        by_cap[r["cap"]].append(r)

    # RULE flag: same (cap, evidence, use) at different scores. WEAPON_STATS
    # is exempt — it is a per-weapon stat citation, not a shared spell, so
    # scores legitimately differ. Two `use:` variants of one spell are
    # mutually exclusive uses, each its own row and loadout bundle, so a use
    # is compared only with the same use. CAVEAT for triage: a flagged pair
    # can be legitimate when the higher score's total includes an
    # E-supplement on top of the shared QW spell — but then the comment MUST
    # say so; a flagged pair with no such comment is a bug.
    rule_flags = set()
    for cap, rs in by_cap.items():
        by_ev = defaultdict(set)
        for r in rs:
            if r["evidence"] != "WEAPON_STATS":
                by_ev[(r["evidence"], r.get("use"))].add(r["score"])
        for (ev, use), scores in by_ev.items():
            if len(scores) > 1:
                rule_flags.add((cap, ev, use))

    def flags_of(r):
        f = []
        if (r["cap"], r["evidence"], r.get("use")) in rule_flags:
            f.append("RULE")
        if (r["evidence"].startswith("PASSIVE") or r["evidence"] == "WEAPON_STATS") \
                and r["score"] >= 4:
            f.append("PASV")
        if r["score"] >= 6:
            f.append("TOP")
        return f

    n_rule = sum(1 for r in rows if "RULE" in flags_of(r))
    n_pasv = sum(1 for r in rows if "PASV" in flags_of(r))
    n_top = sum(1 for r in rows if r["score"] >= 6)

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
            ev = html.escape(r["evidence"])
            if r.get("use"):                       # one use of a split spell
                ev += "<br><small>use: %s</small>" % html.escape(str(r["use"]))
            body.append(
                '<tr class="%s"><td class="s">%d</td><td>%s</td>'
                '<td class="ev">%s</td><td class="fl">%s</td>'
                '<td class="cm">%s <small>(%s)</small></td>'
                '<td class="dx">%s</td></tr>' % (
                    cls, r["score"], html.escape(names.get(r["weapon"], r["weapon"])),
                    ev, " ".join(fl), html.escape(r["comment"]),
                    html.escape(r["sheet"]), spell_cell(r["evidence"])))
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
<p class="legend">Rule: scores encode impact MAGNITUDE, not existence
(sheet scores, 1&ndash;7). %d rows · flags: %d RULE (same spell and use, same
cap, different scores — always a bug) · %d PASV (passive/stat evidence at 4+) ·
%d TOP (score 6+, the ladder tops, review first). Corrections go through the
sheets, never this page.</p>
<p>%s</p>
%s""" % (len(rows), n_rule, n_pasv, n_top, toc, "".join(sections))

    outdir = os.path.join(ROOT, "review")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "magnitude.html")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    print("wrote review/magnitude.html — %d rows across %d capabilities" %
          (len(rows), len(by_cap)))
    print("  flags: %d RULE, %d PASV, %d TOP (score 6+)" % (n_rule, n_pasv, n_top))
    for cap, ev, use in sorted(rule_flags,
                               key=lambda t: (t[0], t[1], t[2] or "")):
        same = [r for r in by_cap[cap]
                if r["evidence"] == ev and r.get("use") == use]
        scores = sorted({r["score"] for r in same})
        who = sorted(names.get(r["weapon"], r["weapon"]) for r in same)
        label = ev + (" use %s" % use if use else "")
        print("  RULE  %-18s %-28s scores %s  (%s)" %
              (cap, label, scores, ", ".join(who)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
