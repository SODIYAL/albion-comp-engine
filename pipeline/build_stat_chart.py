#!/usr/bin/env python3
"""
STAT CHART — real game numbers per (weapon, capability), ranked.

The expert's ask (2026-08-20): "find full stats — damage or CC numbers —
based on real stats and create that chart, which is then used to rank each
weapon for its purpose." This builder extracts structured MAGNITUDES from
the pinned dumps for every curated evidence spell and lays them out per
capability, sorted by the measured number, with the curated ordinal score
beside — so magnitude outliers (a '2' outperforming a '3') pop out.
It feeds rubric question 1 (raw magnitude) of the 1-7 rescore.

IP note: dump values are every spell's BASE numbers — the same reference
for all weapons, and ability scaling by item power applies one global curve
on top. Comparing base numbers IS comparing at equal IP.

KNOWN EXTRACTION GAPS (honest under-measurement, never over):
  - area-pulse ticks: a channel that re-applies its area damage every N
    seconds (Rain of Arrows) is counted ONCE — multi-tick totals need the
    spelleffectarea pulse encoding, not yet parsed
  - auto-attack amplifier windows are ranked as their own type (xAA) but
    not converted to expected damage (needs item_stats AA DPS x uptime)

What is extracted per spell (walking the full reference chain, same
registry discipline as effect_catalogue.py; absent = the data doesn't
state it, never a guess):
  damage   direct health reductions per cast (+ DoT totals where the node
           states change-per-interval over a duration)
  heals    direct health increases per cast (+ HoT totals)
  cc       stun/root/silence durations; knockback distance + the
           ignore-CC-resistance flag; forced_movement records
  mods     typed buffs/debuffs (@type vocabulary) with value and duration
  economy  cooldown, cast time, stand time, cast range (from the root)

Outputs:
  out/stat_chart.json       {spell: records} + per-capability board data
  review/stat_chart.html    the chart, one board per capability

Usage:  py -3 pipeline/build_stat_chart.py
"""
import glob
import html
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")

sys.path.insert(0, HERE)
import mastersheet  # noqa: E402
import sheets_lib  # noqa: E402
from effect_catalogue import (spell_registry, CONDITION_PREFIX,  # noqa: E402
                              GUARD_NODES, NON_EFFECT_TYPE)
from provenance import snapshot_dir  # noqa: E402
import jsonfmt  # noqa: E402

MAX_DEPTH = 6

CC_NODES = ("stun", "root", "silence")


def fnum(v):
    """float or None; keyframed values take the max keyframe."""
    if v is None:
        return None
    s = str(v).strip()
    if s.startswith("A "):
        vals = []
        for part in s[2:].split(";"):
            bits = part.split(":")
            if len(bits) == 2:
                try:
                    vals.append(float(bits[1]))
                except ValueError:
                    pass
        return max(vals) if vals else None
    try:
        return float(s)
    except ValueError:
        return None


def extract(sid, reg):
    """Structured magnitude records for one spell, following references.

    Beyond magnitudes, the rubric's ◆ facts (MASTERSHEET §7) are read
    here: persistence (longest ground-area lifetime — Primal Slam's wall
    is spelleffectarea @time 4), delivery (root target kind + channel),
    cast position (cast range), and counter-immunity flags
    (@ignorecrowdcontrolresistance anywhere in the tree)."""
    rec = {"damage": [], "heals": [], "cc": [], "mods": [],
           "persist_s": None, "ignores_ccr": False, "channeled": False,
           "ignores_ap": False}
    visited = set()

    def health_record(node, out_pos, out_neg):
        val = fnum(node.get("@change")) or fnum(node.get("@value"))
        if val is None:
            return
        entry = {"value": abs(val), "target": node.get("@target", "?")}
        # change-per-interval over a duration = DoT/HoT total
        interval = fnum(node.get("@interval"))
        duration = fnum(node.get("@duration")) or fnum(node.get("@time"))
        if interval and duration and interval > 0:
            entry["total"] = round(abs(val) * duration / interval, 1)
            entry["over_seconds"] = duration
        if node.get("@targetcountvaluebonusfactor"):
            entry["escalates"] = True
        (out_neg if val < 0 else out_pos).append(entry)

    def walk(key, node, depth, guarded):
        if depth > MAX_DEPTH:
            return
        if isinstance(node, list):
            for item in node:
                walk(key, item, depth, guarded)
            return
        if not isinstance(node, dict):
            return
        if key and CONDITION_PREFIX.match(key):
            return                          # predicate context, not an effect
        guarded = GUARD_NODES.get(key, guarded)
        if node.get("@ignorecrowdcontrolresistance") == "true":
            rec["ignores_ccr"] = True
        if node.get("@ignoreabilitypowerscaling") == "true":
            rec["ignores_ap"] = True
        if key == "channelingspell":
            rec["channeled"] = True
        if key == "spelleffectarea":
            t = fnum(node.get("@time"))
            if t and (rec["persist_s"] is None or t > rec["persist_s"]):
                rec["persist_s"] = t
        if not guarded:
            if node.get("@attribute") == "health":
                health_record(node, rec["heals"], rec["damage"])
            if key in CC_NODES:
                d = fnum(node.get("@duration")) or fnum(node.get("@time"))
                rec["cc"].append({"type": key, "duration": d,
                                  "target": node.get("@target", "?")})
            elif key == "knockback":
                rec["cc"].append({
                    "type": "knockback",
                    "distance": fnum(node.get("@distance")),
                    "target": node.get("@target", "?"),
                    "ignores_ccr":
                        node.get("@ignorecrowdcontrolresistance") == "true"})
            elif key == "forcedmovement":
                rec["cc"].append({"type": "forced_movement",
                                  "target": node.get("@target", "?")})
            t = node.get("@type")
            if (t and not NON_EFFECT_TYPE.match(t)
                    and node.get("@attribute") != "health"):
                val = fnum(node.get("@value")) or fnum(node.get("@change"))
                if val is not None:
                    rec["mods"].append({
                        "type": t, "value": val,
                        "duration": fnum(node.get("@duration"))
                        or fnum(node.get("@time")),
                        "target": node.get("@target", "?")})
        # follow every attribute that names a registered spell (the
        # convention-proof rule from effect_catalogue.collect_refs)
        for k, v in node.items():
            if k.startswith("@"):
                if isinstance(v, str) and v in reg and v not in visited:
                    visited.add(v)
                    walk(None, reg[v], depth + 1, guarded)
            else:
                walk(k, v, depth + 1, guarded)

    node = reg.get(sid)
    if node is None:
        return None
    visited.add(sid)
    walk(None, node, 0, None)
    rec["cooldown"] = fnum(node.get("@recastdelay"))
    rec["cast_time"] = fnum(node.get("@castingtime"))
    rec["stand_time"] = fnum(node.get("@standtime"))
    rec["cast_range"] = fnum(node.get("@castrange"))
    rec["delivery"] = node.get("@target")     # ground / enemy / self / ...
    return rec


def fact_line(rec):
    """The rubric's ◆ facts, one compact string per spell (S2-S6 inputs)."""
    if rec is None:
        return ""
    bits = []
    if rec.get("persist_s") and rec["persist_s"] >= 1:
        bits.append(f"persists {rec['persist_s']:g}s")
    d = rec.get("delivery")
    if d == "ground":
        r = rec.get("cast_range")
        bits.append(f"ground-cast @{r:g}m" if r else "ground-cast")
    elif d == "self":
        bits.append("self/contact")
    elif d:
        r = rec.get("cast_range")
        bits.append(f"targeted {d}" + (f" @{r:g}m" if r else ""))
    if rec.get("channeled"):
        bits.append("channeled")
    if rec.get("ignores_ccr"):
        bits.append("ignores CCR")
    if rec.get("ignores_ap"):
        # honest scoping: a mixed spell (Tornado: CC flagged, damage scales)
        # is only PARTLY tier-flat
        bits.append("tier-flat" if not rec.get("damage")
                    else "CC tier-flat")   # same CC at 4.1 and 8.4
    if rec.get("cooldown"):
        bits.append(f"{rec['cooldown']:g}s CD")
    return " · ".join(bits)


# --------------------------------------------------- capability board metrics
def dmg_per_cast(rec):
    return round(sum(d.get("total", d["value"]) for d in rec["damage"]), 1)


def heal_per_cast(rec):
    return round(sum(h.get("total", h["value"]) for h in rec["heals"]), 1)


def cc_duration(rec, kinds):
    return max((c.get("duration") or 0) for c in rec["cc"]
               if c["type"] in kinds and c.get("target") != "self") \
        if any(c["type"] in kinds and c.get("target") != "self"
               for c in rec["cc"]) else None


def slow_power(rec):
    """largest enemy movespeed reduction x its duration."""
    best = None
    for m in rec["mods"]:
        if m["type"] == "movespeedbonus" and m["value"] < 0:
            p = abs(m["value"]) * (m.get("duration") or 1.0)
            if best is None or p > best:
                best = round(p, 2)
    return best


def kb_distance(rec):
    ds = [c.get("distance") for c in rec["cc"]
          if c["type"] == "knockback" and c.get("distance")]
    return max(ds) if ds else None


def metric_for(cap, rec):
    """(headline number, unit, detail) for one capability — the measured
    fact the board sorts by. None = the data states nothing measurable."""
    if rec is None:
        return None, "", ""
    per = dmg_per_cast(rec)
    cd = rec.get("cooldown") or 0
    def aa_amp():
        """Auto-attack amplifier payload (Bow's Enchanted Quiver: +280% AA
        damage for 8s) — a damage PROFILE direct cast damage misses; ranked
        as its own type, never against dmg/cast."""
        dmg = spd = dur = None
        for m in rec["mods"]:
            if m["value"] <= 0:
                continue
            if m["type"] in ("physicalattackdamagebonus",
                             "magicattackdamagebonus"):
                if dmg is None or m["value"] > dmg:
                    dmg, dur = m["value"], m.get("duration")
            elif m["type"] == "attackspeedbonus":
                spd = m["value"]
        if dmg is None:
            return None, ""
        det = f"+{dmg * 100:.0f}% AA dmg" + (f" for {dur:g}s" if dur else "")
        if spd:
            det += f", +{spd * 100:.0f}% attack speed"
        return dmg, det

    if cap in ("burst_aoe", "burst_st", "execute", "sustained_dps"):
        if not per:
            amp, det = aa_amp()
            if amp is not None:
                return amp, "×AA", det
        dps = round(per / cd, 1) if per and cd else None
        if cap == "sustained_dps":
            return (dps or per or None), ("dmg/s" if dps else "dmg/cast"), ""
        return (per or None), "dmg/cast", (f"{dps}/s over {cd:.0f}s CD" if dps else "")
    if cap in ("stun", "silence", "root"):
        d = cc_duration(rec, (cap,))
        return d, "s", ""
    if cap in ("catch", "slow", "peel", "anti_dive"):
        sp = slow_power(rec)
        d = cc_duration(rec, CC_NODES)
        kb = kb_distance(rec)
        bits = []
        if sp:
            bits.append(f"slow-power {sp}")
        if d:
            bits.append(f"hard CC {d}s")
        if kb:
            bits.append(f"knockback {kb}m")
        return (sp or d or kb), ("slow%·s" if sp else "s" if d else "m"), "; ".join(bits)
    if cap == "knockback_displace":
        kb = kb_distance(rec)
        ccr = any(c.get("ignores_ccr") for c in rec["cc"])
        return kb, "m", ("ignores CC resistance" if ccr else "")
    if cap in ("heal_burst", "heal_sustain", "self_sustain"):
        h = heal_per_cast(rec)
        cd2 = rec.get("cooldown") or 0
        hps = round(h / cd2, 1) if h and cd2 else None
        return (h or None), "heal/cast", (f"{hps}/s over {cd2:.0f}s CD" if hps else "")
    if cap in ("resist_shred", "tankiness", "buff_allies", "damage_debuff",
               "heal_reduction"):
        best = None
        det = ""
        for m in rec["mods"]:
            p = abs(m["value"]) * ((m.get("duration") or 1.0))
            if best is None or p > best:
                best, det = round(p, 1), (
                    f"{m['type']} {m['value']:+g}"
                    + (f" for {m['duration']:g}s" if m.get("duration") else ""))
        return best, "value·s", det
    return None, "", ""


def family_ability_power(dump_dir, weapon_keys):
    """{weapon_key: @abilitypower} from the T4 item entry — the FAMILY
    COEFFICIENT (flat across tiers): how strongly the item converts item
    power into spell magnitude. Axes 138, Iron-clad 126, most staves/bows
    120, shields 100 — a real cross-weapon comparability factor."""
    path = os.path.join(dump_dir, "items.json")
    raw = json.load(open(path, encoding="utf-8"))
    want = {f"T4_{k}": k for k in weapon_keys}
    out = {}

    def walk(node):
        if isinstance(node, dict):
            un = node.get("@uniquename")
            if un in want and node.get("@abilitypower"):
                out[want[un]] = int(float(node["@abilitypower"]))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(raw)
    return out


def main():
    reg = spell_registry(snapshot_dir())
    lines_db = sheets_lib.load_weapon_lines(OUT)
    pools = sheets_lib.load_pools()
    dataset = json.load(open(os.path.join(OUT, "dataset-latest.json"),
                             encoding="utf-8"))
    names = {k: w["display_name"] for k, w in dataset["weapons"].items()}
    fam_ap = family_ability_power(snapshot_dir(), list(dataset["weapons"]))
    # display name + [AP coeff] when it differs from the modal 120
    for k in names:
        c = fam_ap.get(k)
        if c and c != 120:
            names[k] = f"{names[k]} [AP{c}]"

    # MASTERSHEET tune:sheets overrides apply here too — the judging
    # instrument must show the scores the ENGINE uses, or rulings look
    # unapplied on the very board that motivated them.
    tune_sheets = mastersheet.load().get("sheets", {})
    rows = []                    # (cap, weapon, spell, score)
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        for entry in (yaml.safe_load(open(path, encoding="utf-8")) or []):
            wk = entry.get("weapon")
            if not wk:
                continue
            ov = tune_sheets.get(wk) or {}
            for c in sheets_lib.compose(entry, lines_db.get(wk), pools):
                if not (c.get("cap") and c.get("evidence")):
                    continue
                score = ov.get(c["cap"], c.get("score"))
                if score:
                    rows.append((c["cap"], wk, c["evidence"], score))

    # gear sheets (full-build member model): gear abilities rank on the
    # same boards as weapon spells — a Force Field shove beside the
    # crossbow shove, judged by the same rubric
    gear_names = {k: f"{g['display_name']} [{g.get('slot','gear')}]"
                  for k, g in (dataset.get("gear") or {}).items()}
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "gear", "*.yaml"))):
        for entry in (yaml.safe_load(open(path, encoding="utf-8")) or []):
            gk = entry.get("gear")
            if not gk:
                continue
            for c in entry.get("capabilities", []):
                if isinstance(c, dict) and c.get("cap") and c.get("evidence") and c.get("score"):
                    rows.append((c["cap"], gk, c["evidence"], c["score"]))
    names.update(gear_names)

    spells = sorted({sid for _, _, sid, _ in rows})
    extracted = {sid: extract(sid, reg) for sid in spells}
    n_ok = sum(1 for v in extracted.values() if v)

    # SPELL-keyed boards (expert correction 2026-08-20): the measurement is
    # a property of the SPELL — one row per (capability, spell), with every
    # weapon that cites it listed. Where line-mates score the same spell
    # differently, the row shows the score SPREAD — that is the drift the
    # magnitude audit's RULE queue tracks, visible in place.
    grouped = {}
    for cap, wk, sid, score in rows:
        g = grouped.setdefault((cap, sid), {"weapons": [], "scores": set()})
        g["weapons"].append(names.get(wk, wk))
        g["scores"].add(score)
    # A measured number only ranks against the SAME KIND of effect — meters
    # never sort against seconds (expert correction 2026-08-20: "how is 18m
    # knockback vs 2.5s stasis decided?" — it isn't, by data; the cross-type
    # exchange rate is exactly what the 1-7 rubric's judgment sets). Rows
    # group by unit within each board, sorted within their group only.
    UNIT_GROUP = {"m": "displacement (m)", "s": "hard CC (s)",
                  "slow%·s": "slows (strength × duration)",
                  "dmg/cast": "damage per cast", "dmg/s": "damage per second",
                  "×AA": "auto-attack amplifiers (multiplier)",
                  "heal/cast": "healing per cast",
                  "value·s": "stat modifiers (value × duration)"}
    # Cooldown as a first-class factor (expert, 2026-08-20): every per-cast
    # measurement also shows THROUGHPUT — value x 60/CD, "how much of this
    # effect one player supplies per minute". A 2.5s stasis on a 72s CD is
    # 2.1 s/min; a 1s stun on 20s CD is 3 s/min — the ranking question S6
    # judges. Rows still sort by per-cast within their group (the burst
    # window is real); the rate column sits beside it.
    # /min is only meaningful where the effect ACCUMULATES over a fight:
    # damage, healing, seconds-of-CC, slow-time, buff-time. Displacement
    # does not accumulate (39 "meters per minute" is a nonsense unit — the
    # expert caught it): event-answer effects show CASTS/min instead, i.e.
    # how often the spell can answer its job.
    PER_CAST_UNITS = {"s", "slow%·s", "dmg/cast", "heal/cast", "value·s"}
    CASTS_PER_MIN_UNITS = {"m"}
    boards = {}
    for (cap, sid), g in grouped.items():
        rec = extracted.get(sid)
        val, unit, detail = metric_for(cap, rec)
        per_min = casts_min = None
        if val is not None and rec and rec.get("cooldown"):
            if unit in PER_CAST_UNITS:
                per_min = round(val * 60.0 / rec["cooldown"], 1)
            elif unit in CASTS_PER_MIN_UNITS:
                casts_min = round(60.0 / rec["cooldown"], 1)
        boards.setdefault(cap, []).append({
            "spell": sid, "value": val, "unit": unit, "detail": detail,
            "per_min": per_min, "casts_min": casts_min,
            "facts": fact_line(rec),
            "group": (UNIT_GROUP.get(unit, unit) if val is not None
                      else "not measurable — human judgment"),
            "weapons": sorted(g["weapons"]),
            "scores": sorted(g["scores"])})
    group_order = list(UNIT_GROUP.values()) + ["not measurable — human judgment"]
    for cap in boards:
        boards[cap].sort(key=lambda r: (
            group_order.index(r["group"]) if r["group"] in group_order
            else len(group_order),
            -(r["value"] or 0)))

    jsonfmt.dump({"_meta": {
        "spells_extracted": n_ok, "spells_cited": len(spells),
        "note": ("base dump numbers — the same IP reference for every "
                 "weapon; equal-IP comparison equals base comparison"),
        "tier_model": {
            "formula": "effective ~ base * (family_ap/100) * 1.0918^((IP-700)/100)",
            "source": "community-documented (wiki/forum); the dumps carry the per-effect ignoreabilitypowerscaling flags and per-family ability power",
            "does_not_scale": "percentage effects, durations, distances, and records flagged ignoreabilitypowerscaling (tier-flat in the fact line)"},
        "family_ability_power": fam_ap},
        "spells": extracted, "boards": boards},
        os.path.join(OUT, "stat_chart.json"))

    # ------------------------------------------------------------- HTML chart
    def esc(s):
        return html.escape(str(s))

    parts = ["""<!doctype html><meta charset="utf-8">
<title>Stat chart — real numbers per capability</title>
<style>
body{font:14px/1.5 system-ui,sans-serif;background:#111;color:#ddd;
     max-width:1080px;margin:24px auto;padding:0 16px}
h1{font-size:20px} h2{font-size:16px;margin:28px 0 6px;color:#f0c674}
table{border-collapse:collapse;width:100%}
td,th{padding:3px 10px;text-align:left;border-bottom:1px solid #2a2a2a}
th{color:#888;font-weight:normal} .n{text-align:right;font-variant-numeric:tabular-nums}
.s7,.s6{color:#f0c674}.s5,.s4{color:#8abeb7}.s3,.s2,.s1{color:#777}
.drift{color:#cc6666;font-weight:bold}
.grp{color:#b294bb;font-size:12px;padding-top:12px;border-bottom:1px solid #444}
.none{color:#555} .d{color:#888;font-size:12px}
p.note{color:#999;font-size:13px}
</style>
<h1>Stat chart — the real numbers behind every capability score</h1>
<p class="note">Measured from the pinned game files, per evidence spell,
sorted by the number. Base dump values are the same item-power reference
for every weapon — comparing them IS comparing at equal IP. The curated
0&ndash;3 score sits beside each row: a low score above a high score is a
magnitude outlier for the 1&ndash;7 rescore. &ldquo;&mdash;&rdquo; = the
data states no measurable number for this capability (human judgment
stays).</p>
<h2>Tier lens</h2>
<p class="note">Magnitudes scale &times;1.0918 per 100 item power
(compounding). Percentage effects, durations, distances, and rows tagged
<b>tier-flat</b> do NOT scale &mdash; an 18m wall is 18m at 4.1 and at 8.4,
which is what makes flagged utility the cost-efficient pick. Weapons whose
family converts item power unusually well carry an [AP&nbsp;] tag (most are
120; shields 100). Multiplier vs tier-4 flat (700 IP):</p>
<table style="max-width:640px">
<tr><th>IP</th><td class="n">700</td><td class="n">800</td><td class="n">900</td><td class="n">1000</td><td class="n">1100</td><td class="n">1200</td><td class="n">1300</td><td class="n">1400</td><td class="n">1500</td></tr>
<tr><th>gear</th><td class="d">4.0</td><td class="d">4.1 / 5.0</td><td class="d">4.2 / 6.0</td><td class="d">4.3 / 7.0</td><td class="d">4.4 / 7.1 / 8.0</td><td class="d">7.2 / 8.1</td><td class="d">7.3 / 8.2</td><td class="d">7.4 / 8.3</td><td class="d">8.4</td></tr>
<tr><th>&times;</th><td class="n">1.00</td><td class="n">1.09</td><td class="n">1.19</td><td class="n">1.30</td><td class="n">1.42</td><td class="n">1.55</td><td class="n">1.69</td><td class="n">1.85</td><td class="n">2.02</td></tr>
</table>"""]
    for cap in sorted(boards):
        rows_c = boards[cap]
        measured = sum(1 for r in rows_c if r["value"] is not None)
        parts.append(f"<h2>{esc(cap)} <span class='d'>({measured}/{len(rows_c)} spells measured)</span></h2>")
        parts.append("<table><tr><th>spell</th>"
                     "<th class='n'>measured</th><th>unit</th>"
                     "<th class='n'>/min</th>"
                     "<th class='n'>curated</th><th>detail</th>"
                     "<th>rubric facts (S2–S6)</th>"
                     "<th>weapons citing it</th></tr>")
        last_group = None
        for r in rows_c:
            if r["group"] != last_group:
                last_group = r["group"]
                parts.append(f"<tr><td colspan='7' class='grp'>{esc(last_group)}</td></tr>")
            v = "—" if r["value"] is None else f"{r['value']:g}"
            cls = "none" if r["value"] is None else "n"
            scores = r["scores"]
            if len(scores) == 1:
                sc = f"<span class='s{scores[0]}'>{scores[0]}</span>"
            else:                          # same spell, different scores: DRIFT
                sc = ("<span class='drift'>"
                      + "–".join(str(s) for s in scores) + " drift</span>")
            weapons = ", ".join(r["weapons"])
            pm = ("" if r.get("per_min") is None else f"{r['per_min']:g}")
            if not pm and r.get("casts_min") is not None:
                pm = f"{r['casts_min']:g} casts"
            parts.append(
                f"<tr><td>{esc(r['spell'])}</td>"
                f"<td class='{cls} n'>{v}</td><td class='d'>{esc(r['unit'])}</td>"
                f"<td class='d n'>{pm}</td>"
                f"<td class='n'>{sc}</td>"
                f"<td class='d'>{esc(r['detail'])}</td>"
                f"<td class='d'>{esc(r['facts'])}</td>"
                f"<td class='d'>{esc(weapons)}</td></tr>")
        parts.append("</table>")
    out_html = os.path.join(ROOT, "review", "stat_chart.html")
    with open(out_html, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts))

    print(f"extracted {n_ok}/{len(spells)} cited spells; "
          f"{len(boards)} capability boards -> review/stat_chart.html "
          f"+ out/stat_chart.json")


if __name__ == "__main__":
    main()
