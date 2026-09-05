#!/usr/bin/env python3
"""
STYLE x SIZE ROSTER EVIDENCE (owner 2026-09-04: "Style-labelled rosters as
the evidence for style x size templates ... this gives thousands").

Report-only audit, never part of a build. Reads the killboard party cache
(out/party_cache/, the official kill-event harvest) and, for every
near-complete killer-party roster of 10+ players:

  1. labels its playstyle with the engine's own comp_identity (the page's
     bottom-up read: brawl / clap / kite / brawl_clap / clap_kite; rosters
     that read "forming" or "split" are set aside and counted);
  2. joins each member's WORN KIT from the same battle by player name, so
     supply is measured DRESSED in the person units the templates speak
     (a member with no kit record is dressed in the seat's doctrine v0 kit
     and counted as assumed);
  3. measures what the forge constrains today: coarse role tally, fine
     seats (detect_role), the combo-aware predicate counts (ranged-AoE
     core, primary heal, pierce, heal-cut ...), carrier chests worn, and
     the full effective capability supply vector.

Output per style x size band (10-14 / 15-19 / 20):
  out/style_roster_evidence.json  - every number below, machine-readable
  docs/superpowers/findings/<date>-style-roster-evidence.md - the board

For each capability the board shows the harvest's 10th / 50th / 90th
percentile beside every content template's CURRENT target and soft cap at
the band's reference size, plus what the standing convention would
produce from the harvest (VALIDATION.md 2026-08-21: target = 0.9 x the
least a good comp fields, soft cap = 1.15 x the most - with thousands of
rosters "least" and "most" are the 10th and 90th percentiles).

HONESTY NOTES the board carries: kill events carry no zone, so the
evidence is content-agnostic; rosters are winner-biased by construction
(a party that killed nobody is never captured); the same guild's standing
comp recurs across nights, so counts are by DISTINCT roster (guild set +
weapon multiset) as well as by sighting; spells are unknown, so supply
uses each weapon's default combo; identity thresholds were calibrated on
six comps and must be validated in a blind round before the numbers are
ruled on (the board ships ten unlabelled rosters for that round).

Anti-circularity: none of these rosters calibrated a template, so they
are admissible evidence - but every proposal here is for the OWNER'S
ruling; nothing in the build reads this file.

Usage: py -3 pipeline/audit_style_rosters.py [--min-size 10] [--min-known 0.8]
"""
import argparse
import datetime
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "party_cache")
FINDINGS = os.path.join(ROOT, "docs", "superpowers", "findings")
sys.path.insert(0, ROOT)
from engine.engine import Engine  # noqa: E402

CONTENT_FOR_SUPPLY = "territory_defense"   # ZvZ default; supply physics are style/size keyed
BANDS = (("10-14", 10, 14, 12), ("15-19", 15, 19, 17), ("20", 20, 99, 20))
KIT_SLOTS = ("Head", "Armor", "Shoes", "Cape", "OffHand", "Potion", "Food")
SEATS = ("engage_tank", "stopper_tank", "off_tank", "shield_support",
         "zone_support", "curse_support", "main_healer", "kite_healer",
         "brawl_healer", "ranged_aoe", "sustained_brawler", "bomb_aoe",
         "dive_cleanup")
PREDS = ("ranged_aoe_core", "primary_heal", "pierce", "anti_heal",
         "engage_tank", "stopper_tank", "shield_support")
# blind round 1 (ten rosters) + round 2 (twenty, 2026-09-04): both graded by
# the owner and pinned in test_golden T34 / T36; never re-sampled into a form
GRADED_BATTLES = [1439261314, 1439270346, 1439324226, 1439336518, 1439380503, 1442341916, 1442399167, 1442450338, 1443149088,
                  1439323062, 1439423672, 1442916379, 1442381572, 1443149032, 1442340579, 1443089499, 1439330397,
                  1439163242, 1442365275, 1442813939, 1443067935, 1443196794, 1442359908, 1442270050, 1442373560,
                  1439247869, 1439330979, 1439276629,
                  # round 3 (2026-09-05, the 10-14 band, rosters 1-11 called)
                  1439331464, 1442240282, 1442879983, 1442360406, 1443108045, 1442343192, 1442339162, 1443074329, 1439338826, 1439172287, 1442358198]


def strip(t):
    return re.sub(r"^T\d+_", "", str(t).split("@")[0]) if t else None


def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)


def stats(xs):
    return {"n": len(xs), "p10": pct(xs, 0.1), "p50": pct(xs, 0.5),
            "p90": pct(xs, 0.9),
            "mean": round(sum(xs) / len(xs), 2) if xs else None}


def load_rosters(known, min_size, min_known):
    """Every killer-party roster of >= min_size with >= min_known of its
    weapons in the catalog, with member kits joined by player name."""
    rosters = []
    for name in sorted(os.listdir(CACHE)):
        with open(os.path.join(CACHE, name), encoding="utf-8") as f:
            rec = json.load(f)
        kits = {}
        for bd in rec.get("builds", []):
            g = bd.get("gear") or {}
            if bd.get("name") and g:
                kits[bd["name"]] = {s: strip(g.get(s)) for s in KIT_SLOTS
                                    if g.get(s)}
        # the cache holds one party snapshot PER KILL EVENT: dedupe by
        # member overlap (> 50% of the smaller set, largest first), exactly
        # as sample_parties.analyze does, so a squad shedding members as
        # the fight goes is one roster, not five
        clusters = []
        for p in sorted(rec.get("parties", []),
                        key=lambda p: -len(p.get("members") or [])):
            names = {m.get("name") for m in (p.get("members") or [])}
            hit = None
            for c in clusters:
                inter = len(names & c["names"])
                if inter and inter / min(len(names), len(c["names"])) > 0.5:
                    hit = c
                    break
            if hit is None:
                clusters.append({"names": set(names), "party": p})
        for c in clusters:
            p = c["party"]
            members = p.get("members") or []
            if len(members) < min_size:
                continue
            ws = [(m.get("weapon"), m.get("name")) for m in members
                  if m.get("weapon") in known]
            if len(ws) < min_known * len(members):
                continue
            rosters.append({
                "battle": rec["battle"],
                "size": len(members),
                "known": len(ws),
                "total_players": rec.get("total_players"),
                "guilds": tuple(sorted({m.get("guild") for m in members
                                        if m.get("guild")})),
                # `name` stays in memory for player-distinct counts (the
                # kit blind rounds); nothing writes it out
                "members": [{"weapon": w, "kit": kits.get(n), "name": n}
                            for w, n in ws],
            })
    return rosters


def band_of(size):
    for key, lo, hi, _ref in BANDS:
        if lo <= size <= hi:
            return key
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-size", type=int, default=10)
    ap.add_argument("--min-known", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=20260904)
    ap.add_argument("--blind-sizes", type=int, nargs=2, default=(15, 99),
                    metavar=("LO", "HI"),
                    help="roster size range the blind form samples from "
                         "(rounds 1-2: 15+; round 3: 10 14)")
    ap.add_argument("--blind-round", type=int, default=3,
                    help="round number printed on the form")
    args = ap.parse_args()
    if not os.path.isdir(CACHE):
        sys.exit("no party cache - run sample_parties.py first")

    e_label = Engine(content=CONTENT_FOR_SUPPLY, size=20)
    known = set(e_label.weapons)
    rosters = load_rosters(known, args.min_size, args.min_known)
    print(f"rosters >= {args.min_size} with >= {args.min_known:.0%} weapons "
          f"known: {len(rosters)}")

    # ---- 1. label every roster with comp_identity (group band for 10+)
    label_counts = {}
    gk = e_label.gear_key
    for r in rosters:
        # the worn chests reach the label (a split is decided by the kits)
        gears = []
        for m in r["members"]:
            kit = m["kit"] or {}
            chest = gk(kit["Armor"]) if kit.get("Armor") else None
            gears.append([chest] if chest and chest in e_label.gear else None)
        ci = e_label.comp_identity([m["weapon"] for m in r["members"]], None,
                                   gears)
        r["style"] = ci.get("style")
        r["strength"] = ci.get("strength")
        r["label"] = ci.get("label")
        r["melee_share"] = ci.get("melee_share")
        key = r["style"] or ("forming" if "forming" in (r["label"] or "")
                             else "split")
        label_counts[key] = label_counts.get(key, 0) + 1
    print("labels:", dict(sorted(label_counts.items())))

    # ---- 2+3. per (size, style): dressed supply + structure
    groups = {}
    for r in rosters:
        if not r["style"]:
            continue
        groups.setdefault((r["size"], r["style"]), []).append(r)
    e = Engine(content=CONTENT_FOR_SUPPLY, size=20)
    for (size, style), rs in sorted(groups.items()):
        e.set_content(CONTENT_FOR_SUPPLY, size, style)
        gear_key = e.gear_key
        for r in rs:
            party = [m["weapon"] for m in r["members"]]
            gears, assumed, chests = [], 0, []
            for m in r["members"]:
                kit = m["kit"]
                if kit:
                    gl = [gear_key(v) for v in kit.values()]
                    gl = [g for g in gl if g and g in e.gear]
                    if e.weapons[m["weapon"]].get("two_handed"):
                        gl = [g for g in gl if not g.startswith("OFF_")]
                    gears.append(gl or None)
                else:
                    v0 = e.kit_variants(m["weapon"])[0][1]
                    gears.append(list(v0) if v0 else None)
                    assumed += 1
                chest = next((g for g in (gears[-1] or [])
                              if g.startswith("ARMOR_")), None)
                chests.append(chest)
            sup = e.effective_supply(party, None, gears)
            counts, roles, preds, _groups = e._forge_counts(party, None)
            # function coverage from the role book directly (the forge's
            # profile channel only arms at 15+, which read as 0 under 15)
            funcs = {}
            for w in party:
                wd = e.weapons[w]
                menu = set(wd.get("role_menu") or []) | set(
                    wd.get("role_menu_secondary") or [])
                for fn in ("pierce", "anti_heal", "purge", "shield_break"):
                    if fn in menu:
                        funcs[fn] = funcs.get(fn, 0) + 1
            seats = {}
            for m, chest in zip(r["members"], chests):
                d = e.detect_role(m["weapon"], chest)
                if d.get("role"):
                    seats[d["role"]] = seats.get(d["role"], 0) + 1
            carriers = {}
            for g in gears:
                for x in g or []:
                    for eff in e._item_effects.get(x) or []:
                        carriers[eff] = carriers.get(eff, 0) + 1
            r.update({"supply": {c: round(v, 3) for c, v in sup.items()},
                      "roles": roles, "preds": preds, "seats": seats,
                      "funcs": funcs,
                      "carriers": carriers, "assumed_kits": assumed,
                      "weapon_counts": counts})

    # ---- aggregate per style x band, by sighting and by distinct roster
    styles = sorted({r["style"] for r in rosters if r["style"]})
    caps = list(e.reqs)
    board = {}
    for band_key, lo, hi, ref in BANDS:
        for style in styles:
            rs = [r for r in rosters
                  if r["style"] == style and lo <= r["size"] <= hi]
            if not rs:
                continue
            distinct = {}
            for r in rs:
                k = (r["guilds"], tuple(sorted(w for w in
                                               [m["weapon"] for m in r["members"]])))
                distinct.setdefault(k, r)
            drs = list(distinct.values())
            entry = {"rosters": len(rs), "distinct": len(drs),
                     "strong": sum(1 for r in drs if r["strength"] == "strong"),
                     "assumed_kit_share": round(
                         sum(r["assumed_kits"] for r in drs)
                         / max(1, sum(len(r["members"]) for r in drs)), 3),
                     "size_ref": ref}
            entry["roles"] = {k: stats([r["roles"].get(k, 0) for r in drs])
                              for k in ("frontline", "support", "dps", "healer")}
            entry["seats"] = {k: stats([r["seats"].get(k, 0) for r in drs])
                              for k in SEATS
                              if any(r["seats"].get(k) for r in drs)}
            entry["preds"] = {k: stats([r["preds"].get(k, 0) for r in drs])
                              for k in PREDS}
            entry["funcs"] = {k: stats([r["funcs"].get(k, 0) for r in drs])
                              for k in ("pierce", "anti_heal", "purge",
                                        "shield_break")}
            entry["carriers"] = {k: stats([r["carriers"].get(k, 0) for r in drs])
                                 for k in sorted({c for r in drs
                                                  for c in r["carriers"]})}
            entry["supply"] = {c: stats([r["supply"].get(c, 0.0) for r in drs])
                               for c in caps}
            # current templates at the band's reference size, this style
            cur = {}
            for content in sorted(e.data["templates"]):
                e.set_content(content, ref, style)
                cur[content] = {c: {"target": round(e.target(c), 2),
                                    "soft": round(e.soft_cap(c), 2),
                                    "weight": round(e.weight(c), 2)}
                                for c in e.reqs}
            entry["current"] = cur
            entry["proposal"] = {
                c: {"target": round(0.9 * (entry["supply"][c]["p10"] or 0), 2),
                    "soft": round(1.15 * (entry["supply"][c]["p90"] or 0), 2)}
                for c in caps}
            board[f"{style}|{band_key}"] = entry

    # ---- blind-round form: unlabelled rosters, answers kept apart.
    # Sampled from EVERY roster of 15+ in a deterministic order (never from
    # the labelled subset — round 1's form silently re-sampled when the
    # rulings changed the labels, and the pin had to be restored from git).
    # Every graded battle is excluded; the size range is an argument
    # (rounds 1-2 drew from 15+, round 3 from the 10-14 band).
    rng = random.Random(args.seed)
    graded = set(GRADED_BATTLES)
    lo_b, hi_b = args.blind_sizes
    pool = sorted((r for r in rosters if lo_b <= r["size"] <= hi_b
                   and r["battle"] not in graded),
                  key=lambda r: (r["battle"], tuple(sorted(
                      m["weapon"] for m in r["members"]))))
    form = rng.sample(pool, min(20, len(pool)))
    disp = lambda w: e.weapons[w]["display_name"]
    blind = [{"id": i + 1, "size": r["size"],
              "weapons": sorted(disp(m["weapon"]) for m in r["members"])}
             for i, r in enumerate(form)]
    answers = [{"id": i + 1, "style": r["style"], "strength": r["strength"],
                "melee_share": round(r["melee_share"] or 0, 2),
                "battle": r["battle"]} for i, r in enumerate(form)]

    out = {"_generated": datetime.date.today().isoformat(),
           "_source": "out/party_cache (official kill-event killer parties)",
           "_filters": {"min_size": args.min_size, "min_known": args.min_known},
           "_supply_content": CONTENT_FOR_SUPPLY,
           "rosters_total": len(rosters), "labels": label_counts,
           "board": board, "blind_form": blind, "blind_answers": answers}
    with open(os.path.join(OUT, "style_roster_evidence.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")

    # ---- the markdown board
    os.makedirs(FINDINGS, exist_ok=True)
    today = datetime.date.today().isoformat()
    md = [f"# Style x size roster evidence ({today})", "",
          "Report-only (`pipeline/audit_style_rosters.py`). Source: killer-party "
          f"rosters of {args.min_size}+ from the official kill-event harvest, "
          f"{len(rosters)} rosters with >= {args.min_known:.0%} weapons known; "
          "labelled by the engine's `comp_identity`; supply measured DRESSED "
          "(kits joined by player name, doctrine v0 where a member has no kit "
          f"record) under `{CONTENT_FOR_SUPPLY}` physics at the roster's size and "
          "labelled style. Counts below are by DISTINCT roster (guild set + "
          "weapon multiset).", "",
          "**Read before ruling:** kill events carry no zone (content-agnostic "
          "evidence); rosters are winner-biased by construction; spells are "
          "unknown (default combos); identity thresholds were calibrated on six "
          "comps — grade the blind round at the bottom before trusting the "
          "label split. Nothing in the build reads this. Proposals follow the "
          "standing convention (target 0.9 x p10, soft cap 1.15 x p90) and are "
          "for the owner's ruling only (anti-circularity).", "",
          "## Label distribution", "",
          "| label | rosters |", "|---|---|"]
    for k, v in sorted(label_counts.items()):
        md.append(f"| {k} | {v} |")
    md += ["", "## Structure per style x band (distinct rosters; median [p10-p90])", ""]
    md += ["| style | band | n | frontline | support | dps | healer | engage | stopper | shield sup | main healer | ranged-AoE core | pierce carriers | heal-cut carriers | assumed kits |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda s: (f"{s['p50']} [{s['p10']}-{s['p90']}]" if s and s["n"] else "-")
    for key, en in sorted(board.items()):
        style, band = key.split("|")
        se = en["seats"]; pr = en["preds"]; ro = en["roles"]
        md.append("| " + " | ".join([
            style, band, f"{en['distinct']} ({en['rosters']})",
            fmt(ro["frontline"]), fmt(ro["support"]), fmt(ro["dps"]), fmt(ro["healer"]),
            fmt(se.get("engage_tank")), fmt(se.get("stopper_tank")),
            fmt(se.get("shield_support")), fmt(se.get("main_healer")),
            fmt(pr["ranged_aoe_core"]), fmt(en["funcs"]["pierce"]),
            fmt(en["funcs"]["anti_heal"]),
            f"{en['assumed_kit_share']:.0%}"]) + " |")
    md += ["", "## Carrier chests per roster (distinct rosters; median [p10-p90])", "",
           "| style | band | " + " | ".join(sorted({c for en in board.values() for c in en["carriers"]})) + " |"]
    ceffs = sorted({c for en in board.values() for c in en["carriers"]})
    md.append("|---|---|" + "---|" * len(ceffs))
    for key, en in sorted(board.items()):
        style, band = key.split("|")
        md.append(f"| {style} | {band} | " + " | ".join(fmt(en["carriers"].get(c)) for c in ceffs) + " |")
    md += ["", "## Capability supply vs current templates", "",
           "Per style x band: harvest p10 / p50 / p90 (person units, dressed), the "
           "convention's proposal (0.9 x p10 -> 1.15 x p90), and each content "
           "template's CURRENT target -> soft cap at the band's reference size "
           "under that style. `x` = p50 / current target.", ""]
    contents = sorted(e.data["templates"])
    for key, en in sorted(board.items()):
        style, band = key.split("|")
        md += [f"### {style} at {band} (n = {en['distinct']} distinct, ref size {en['size_ref']})", "",
               "| capability | p10 / p50 / p90 | proposal | " + " | ".join(contents) + " |",
               "|---|---|---|" + "---|" * len(contents)]
        for c in caps:
            s = en["supply"][c]
            cells = []
            for content in contents:
                cur = en["current"][content].get(c)
                if not cur or cur["weight"] == 0:
                    cells.append("unscored")
                    continue
                x = (s["p50"] or 0) / cur["target"] if cur["target"] else 0
                cells.append(f"{cur['target']} -> {cur['soft']} (x{x:.1f})")
            md.append(f"| {c} | {s['p10']} / {s['p50']} / {s['p90']} | "
                      f"{en['proposal'][c]['target']} -> {en['proposal'][c]['soft']} | "
                      + " | ".join(cells) + " |")
        md.append("")
    md += [f"## Blind round {args.blind_round} (owner: call the style BEFORE reading the engine's)", "",
           f"Twenty harvested rosters of {lo_b}-{hi_b} players (every graded battle excluded), weapons only. Answers are in "
           "`out/style_roster_evidence.json` under `blind_answers`; do not open "
           "them before calling.", ""]
    for b in blind:
        md.append(f"{b['id']}. ({b['size']} players) " + ", ".join(b["weapons"]))
    with open(os.path.join(FINDINGS, f"{today}-style-roster-evidence.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md) + "\n")
    print(f"board: {len(board)} style x band cells -> out/style_roster_evidence.json "
          f"+ docs/superpowers/findings/{today}-style-roster-evidence.md")


if __name__ == "__main__":
    main()
