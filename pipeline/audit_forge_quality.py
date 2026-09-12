#!/usr/bin/env python3
"""
FORGE QUALITY SWEEP - what the engine fields when it builds a whole comp.

Report-only audit, never part of a build (2026-09-12). The two existing
quality measurements are next-pick metrics: `tests/tier2_blindtest.py v4`
(published comps minus one member, the gate) and `v4h` (the same over
the harvest, report-only). Neither looks at a FORGED roster as a whole.
This sweep does: for every content x style x size cell the planner
offers it runs the production forge (`Engine.forge`, dressed, default
pool, no locks - exactly the page's "forge" button) and grades the roster
it returns against evidence the build already carries, plus the
NEXT-BEST alternatives the refresh button would walk (`forge(avoid=)`).

Grades per forged roster (all descriptive, nothing here scores):

  structure   the forge's own honesty flags (feasible / filler / held) and
              the role tally (Engine.role_of) against the harvest's
              role-count cell for the declared style at that size
              (out/role_counts.json: p10 / p50 / p90; the pooled row for
              balanced, the comps cell below 10) - a role outside
              [p10, p90] is a structure the typical winner does not field
  identity    comp_identity's read of the forged roster against the style
              it was forged FOR (kit-aware, the page's label); the kill
              checklist (kill_pressure) and the fight chain's weak stages
  supply      the capability board on the roster's own kits: rows under
              the bare minimum (red), between min and typical (orange),
              at typical (green), past the soft cap (purple), armed floors
  evidence    how much of the roster winners actually field - per slot,
              the weapon's roster prevalence in the harvest cell (killer
              parties of the same size +-2, same identity label at 10+),
              the share of forged weapon PAIRS ever seen together in that
              cell, and the nearest harvested roster (multiset Jaccard).
              The evidence cell is the HOLDOUT slice (battle % 5 == 0)
              where it holds >= 40 rosters, else every battle (labelled),
              so a number here is not the meta prior grading itself.
  hygiene     duplicates, unseated weapons, style-unfit or excluded
              members in generated slots (should be none - the pool gates
              bar them), the roster's own comp_score

Honesty notes: killer parties are win-conditioned evidence of what is
FIELDED, never a ruling; prevalence is popularity, not effectiveness
(standing rule 7); a forged weapon nobody fields is a question for the
owner, never an error; style labels on the harvest come from
comp_identity (weapons only) and were validated in four blind rounds.
Anti-circularity: nothing in the build reads this file; every line is a
hypothesis for the owner.

Outputs:
  out/forge_quality_report.json                 every number, machine-readable
  notes/findings/<date>-forge-quality-sweep.md   the board
  tests/forge_grading_<date>.md                  the owner's grading form
                                                 (display names, blank grades)

Usage: py -3 pipeline/audit_forge_quality.py [--alts 2] [--date YYYY-MM-DD]
       [--cells content:size:style,...]
"""
import argparse
import datetime
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from engine import Engine  # noqa: E402
import rosters_io  # noqa: E402

OUT = os.path.join(HERE, "out")
HOLDOUT_MOD = 5          # tests/tier2_blindtest.py v4h, derive_meta_prior.py
HOLDOUT_MIN = 40         # rosters a holdout cell needs before it stands alone
SIZE_WINDOW = 2          # evidence cell = size +- this
PAIR_MIN = 3             # a pair "seen" needs this many rosters
IDENTITY_STYLES = ("brawl", "clap", "kite", "brawl_clap", "clap_kite")

# The planner's grid. Sizes per content: the template's base size plus the
# sizes the harvest bands cover (10 / 15 / 20) and the 25 the owner forges
# castle at (BACKLOG: castle 25 healers). Sub-10 cells run balanced and
# the three primary styles; 10+ cells run every style.
GRID = [
    ("castle_outpost", 5), ("castle_outpost", 7),
    ("roads", 7),
    ("faction_war", 10), ("faction_war", 15),
    ("blackzone_roam", 10), ("blackzone_roam", 15), ("blackzone_roam", 20),
    ("territory_defense", 15), ("territory_defense", 20), ("territory_defense", 25),
    ("castle", 20), ("castle", 25),
]
STYLES_SMALL = ("balanced", "brawl", "clap", "kite")
STYLES_LARGE = ("balanced",) + IDENTITY_STYLES


def _jaccard(a, b):
    """Multiset Jaccard of two weapon lists."""
    ca, cb = Counter(a), Counter(b)
    inter = sum((ca & cb).values())
    union = sum((ca | cb).values())
    return inter / union if union else 0.0


def load_harvest():
    doc = rosters_io.load()
    ps_path = os.path.join(OUT, "party_styles.json")
    labels = {}
    if os.path.exists(ps_path):
        with open(ps_path, encoding="utf-8") as f:
            for p in json.load(f)["parties"]:
                labels[(p["battle"], p["index"])] = p["style"]
    parties = []
    for p in doc["parties"]:
        if p.get("known_weapons") != p.get("size") or p["size"] < 5:
            continue
        parties.append({
            "battle": p["battle"], "size": p["size"],
            "weapons": list(p["weapons"]),
            "style": labels.get((p["battle"], p["index"])),
            "holdout": p["battle"] % HOLDOUT_MOD == 0,
            "guilds": tuple(sorted(p.get("guilds") or [])),
        })
    return parties


class Cell:
    """The evidence cell one forged roster is graded against."""

    def __init__(self, parties, size, style):
        def pick(pool):
            out = []
            for p in pool:
                if abs(p["size"] - size) > SIZE_WINDOW and not (
                        size >= 21 and p["size"] >= 21):
                    continue
                if style in IDENTITY_STYLES and size >= 10 \
                        and p["style"] != style:
                    continue
                out.append(p)
            return out
        hold = pick([p for p in parties if p["holdout"]])
        if len(hold) >= HOLDOUT_MIN:
            self.rosters, self.split = hold, "holdout"
        else:
            self.rosters, self.split = pick(parties), "all"
        self.n = len(self.rosters)
        # distinct rosters (guild set + weapon multiset), the audit's unit
        distinct = {}
        for p in self.rosters:
            distinct[(p["guilds"], tuple(sorted(p["weapons"])))] = p
        self.distinct = list(distinct.values())
        self.prev = Counter()
        self.pairs = Counter()
        for p in self.distinct:
            ws = sorted(set(p["weapons"]))
            self.prev.update(ws)
            for i in range(len(ws)):
                for j in range(i + 1, len(ws)):
                    self.pairs[(ws[i], ws[j])] += 1
        self.nd = len(self.distinct)

    def prevalence(self, w):
        return self.prev.get(w, 0) / self.nd if self.nd else 0.0

    def pair_seen(self, a, b):
        k = (a, b) if a <= b else (b, a)
        return self.pairs.get(k, 0) >= PAIR_MIN

    def nearest(self, party):
        best, bj = None, -1.0
        for p in self.distinct:
            j = _jaccard(party, p["weapons"])
            if j > bj:
                best, bj = p, j
        return best, bj


def role_cell(rc, content, size, style):
    """The role-count evidence row the forge itself reads (typical rows
    resolve the same way: comps below 10, styles at 10+, pooled for
    balanced / thin), returned as {role: {p10, p50, p90}} plus provenance."""
    s = str(size)
    if size < 10:
        cc = (rc.get("comp_cells") or {}).get(content, {}).get(s)
        if cc:
            return cc, f"comps[{content}][{s}]"
        pooled = (rc.get("sizes") or {}).get(s)
        return (pooled, f"pooled[{s}] (harvest, healer row only below 10)") \
            if pooled else (None, "none")
    if style in IDENTITY_STYLES:
        sc = (rc.get("style_cells") or {}).get(style, {}).get(s)
        if sc:
            return sc, f"styles[{style}][{s}]"
    pooled = (rc.get("sizes") or {}).get(s)
    return (pooled, f"pooled[{s}]") if pooled else (None, "none")


def grade_roster(e, r, cell, rcell, rsrc, declared_style):
    party, combos, gears = r["party"], r["combos"], r["gears"]
    names = [e.weapons[w]["display_name"] for w in party]
    # --- structure
    roles = Counter(e.role_of(w) for w in party)
    role_grade = {}
    if rcell:
        for role in ("healer", "frontline", "support", "dps"):
            row = rcell.get(role)
            if not row:
                continue
            have = roles.get(role, 0)
            verdict = ("under" if have < row["p10"]
                       else "over" if have > row["p90"] else "in")
            role_grade[role] = {"have": have, "p10": row["p10"],
                                "p50": row["p50"], "p90": row["p90"],
                                "verdict": verdict}
    # --- identity
    ident = e.comp_identity(party, combos, gears)
    kp = e.kill_pressure(party, combos, gears)
    chain = e.fight_chain(party, combos, gears)
    weak_stages = []
    if chain:
        for st in chain["stages"]:
            if st.get("verdict") in ("weak", "missing"):
                weak_stages.append(f"{st.get('stage') or st.get('name')}:{st['verdict']}")
    # --- supply board on the roster's own kits
    s = e.effective_supply(party, combos, gears)
    sf = e.effective_supply(party, combos)
    board = {"red": [], "orange": [], "green": [], "purple": [], "floors": [],
             "optional_short": []}
    for cap in e.reqs:
        have = s.get(cap, 0.0)
        mn, tg, sc = e.target_min(cap), e.target(cap), e.soft_cap(cap)
        optional = bool(e.reqs[cap].get("optional"))
        if have > sc:
            board["purple"].append(cap)
        elif have >= tg:
            board["green"].append(cap)
        elif optional:
            board["optional_short"].append(cap)   # denominator-only rows
        elif have >= mn:
            board["orange"].append(cap)
        else:
            board["red"].append(cap)
        if e.floor_armed(cap, sf.get(cap, 0.0)):
            board["floors"].append(cap)
    # --- evidence
    slots = []
    for w in party:
        slots.append({"weapon": w, "prevalence": round(cell.prevalence(w), 3)})
    never = [x["weapon"] for x in slots if cell.prev.get(x["weapon"], 0) == 0]
    rare = [x["weapon"] for x in slots
            if 0 < cell.prev.get(x["weapon"], 0) and x["prevalence"] < 0.02]
    distinct = sorted(set(party))
    pairs_total = pairs_seen = 0
    unseen_pairs = []
    for i in range(len(distinct)):
        for j in range(i + 1, len(distinct)):
            pairs_total += 1
            if cell.pair_seen(distinct[i], distinct[j]):
                pairs_seen += 1
            else:
                unseen_pairs.append((distinct[i], distinct[j]))
    near, nj = cell.nearest(party)
    # --- hygiene
    dups = {w: c for w, c in Counter(party).items() if c > 1}
    unseated = [w for w in party if e._primary_seat_class(w) is None]
    unfit = [w for w in party if e.is_style_unfit(w)]
    excluded = [w for w in party if e.is_excluded(w)]
    return {
        "party": party, "names": names, "combos": combos,
        "score": round(r["score"], 3), "feasible": r["feasible"],
        "filler": r["filler"], "held": r["held"], "exhausted": r.get("exhausted", False),
        "roles": dict(roles), "role_grade": role_grade, "role_source": rsrc,
        "identity": {"style": ident.get("style"), "strength": ident.get("strength"),
                     "archetype": ident.get("archetype"), "label": ident.get("label"),
                     "matches": (ident.get("style") == declared_style
                                 if declared_style in IDENTITY_STYLES else None),
                     "conflicts": [c.get("weapon") if isinstance(c, dict) else c
                                   for c in (ident.get("conflicts") or [])]},
        "kill_pressure": (kp or {}).get("verdict"),
        "kill_lights": {k: (kp[k]["ok"] if kp else None)
                        for k in ("pierce", "heal_cut", "burst")} if kp else None,
        "weak_stages": weak_stages,
        "board": board,
        "evidence": {"cell_n": cell.n, "cell_distinct": cell.nd, "split": cell.split,
                     "slots": slots, "never_fielded": never, "rare": rare,
                     "pairs_seen": pairs_seen, "pairs_total": pairs_total,
                     "pair_share": round(pairs_seen / pairs_total, 3) if pairs_total else None,
                     "unseen_pairs": unseen_pairs[:12],
                     "nearest_jaccard": round(nj, 3),
                     "nearest": (near["weapons"] if near else None),
                     "nearest_size": (near["size"] if near else None)},
        "duplicates": dups, "unseated": unseated,
        "style_unfit": unfit, "excluded": excluded,
    }


def run_cell(content, size, style, parties, rc, alts):
    e = Engine(content=content, size=size, style=style)
    cell = Cell(parties, size, style)
    rcell, rsrc = role_cell(rc, content, size, style)
    rosters, avoid = [], []
    for k in range(1 + alts):
        r = e.forge(size, avoid=avoid or None)
        g = grade_roster(e, r, cell, rcell, rsrc, style)
        g["rank"] = k
        rosters.append(g)
        if r.get("exhausted"):
            break
        avoid.append(list(r["party"]))
    # how different the alternatives are from the first roster, and whether
    # one of them OUTSCORES it - next-best is meant to be exact, so a
    # higher-scoring alternative means the first search missed it
    for g in rosters[1:]:
        g["diff_from_first"] = sum((Counter(g["party"]) - Counter(rosters[0]["party"])).values())
        g["outscores_first"] = g["score"] > rosters[0]["score"] + 1e-6
    return {"content": content, "size": size, "style": style,
            "template": e.template["name"], "rosters": rosters,
            "role_source": rsrc, "evidence_cell": {"n": cell.n, "distinct": cell.nd,
                                                  "split": cell.split}}


def fmt_pct(v):
    return "-" if v is None else f"{100 * v:.0f}%"


def write_board(results, date, path):
    L = [f"# Forge quality sweep ({date})", ""]
    L.append("Report-only (`pipeline/audit_forge_quality.py`). Every cell below is "
             "the production forge - `Engine.forge(size)`, dressed, default "
             "pool, no locks, the page's forge button - graded against evidence "
             "the build already carries. Rank 0 is the roster the button "
             "returns; ranks 1+ are what refresh walks (`forge(avoid=)`).")
    L.append("")
    L.append("**Read before ruling:** the evidence cell is killer parties of the "
             "same size (+-2) and, at 10+, the same identity label; it is "
             "win-conditioned evidence of what is FIELDED, never a ruling, and "
             "prevalence is popularity, not effectiveness. A forged weapon nobody "
             "fields is a question, never an error. `holdout` cells use only "
             "battles with `id % 5 == 0` (the slice the meta prior never saw); "
             "`all` cells were too thin for that and use every battle. Nothing "
             "in the build reads this file.")
    L.append("")
    # summary board
    L.append("## Summary board (rank-0 roster per cell)")
    L.append("")
    L.append("| content | size | style | feasible | filler/held | roles H/F/S/D | "
             "roles vs cell | identity read | kill | weak stages | board R/O/G/P | "
             "floors | never fielded | rare | pairs seen | nearest | cell (n, split) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in results:
        g = c["rosters"][0]
        ro = g["roles"]
        rv = ",".join(f"{k[0].upper()}:{v['verdict']}" for k, v in g["role_grade"].items()
                      if v["verdict"] != "in") or "all in"
        ident = g["identity"]
        iread = f"{ident['style']}"
        if ident["matches"] is False:
            iread = f"**{ident['style']}**"
        if ident.get("archetype"):
            iread += f" ({ident['archetype']})"
        b = g["board"]
        ev = g["evidence"]
        L.append(
            f"| {c['content']} | {c['size']} | {c['style']} | "
            f"{'yes' if g['feasible'] else '**NO**'} | "
            f"{len(g['filler'])}/{len(g['held'])} | "
            f"{ro.get('healer', 0)}/{ro.get('frontline', 0)}/{ro.get('support', 0)}/{ro.get('dps', 0)} | "
            f"{rv} | {iread} | {g['kill_pressure'] or '-'} | "
            f"{len(g['weak_stages'])} | "
            f"{len(b['red'])}/{len(b['orange'])}/{len(b['green'])}/{len(b['purple'])} | "
            f"{len(b['floors'])} | {len(ev['never_fielded'])} | {len(ev['rare'])} | "
            f"{fmt_pct(ev['pair_share'])} | {ev['nearest_jaccard']:.2f} | "
            f"{ev['cell_distinct']}, {ev['split']} |")
    L.append("")
    L.append("Columns: roles = healer / frontline / support / dps by `role_of`; "
             "roles vs cell = roles outside the harvest [p10, p90] for that "
             "style x size (H/F/S/D:under|over); identity read = "
             "`comp_identity` on the forged roster (bold = disagrees with the "
             "style forged for); board = capability rows under min / under "
             "typical / at typical / past soft cap; never fielded = forged "
             "weapons with zero rosters in the evidence cell; rare = under 2% "
             "of the cell's distinct rosters; pairs seen = share of distinct "
             "forged weapon pairs seen together in >= 3 rosters; nearest = "
             "multiset Jaccard to the closest harvested roster.")
    L.append("")
    # aggregate
    n = len(results)
    r0 = [c["rosters"][0] for c in results]
    L.append("## Aggregates over rank-0 rosters")
    L.append("")
    L.append(f"- cells: {n}; infeasible: {sum(1 for g in r0 if not g['feasible'])}; "
             f"with filler slots: {sum(1 for g in r0 if g['filler'])}; "
             f"with held slots: {sum(1 for g in r0 if g['held'])}")
    ident_cells = [g for g in r0 if g["identity"]["matches"] is not None]
    L.append(f"- identity agrees with the forged-for style: "
             f"{sum(1 for g in ident_cells if g['identity']['matches'])}/{len(ident_cells)} "
             f"styled cells")
    L.append(f"- kill checklist: " + ", ".join(
        f"{k} {v}" for k, v in sorted(Counter(g["kill_pressure"] for g in r0).items(),
                                       key=lambda kv: str(kv[0]))))
    tot_slots = sum(len(g["party"]) for g in r0)
    never = sum(len(g["evidence"]["never_fielded"]) for g in r0)
    rare = sum(len(g["evidence"]["rare"]) for g in r0)
    L.append(f"- slots: {tot_slots}; never fielded in the cell: {never} "
             f"({100 * never / tot_slots:.0f}%); rare (< 2%): {rare} "
             f"({100 * rare / tot_slots:.0f}%)")
    ps = [g["evidence"]["pair_share"] for g in r0 if g["evidence"]["pair_share"] is not None]
    nj = [g["evidence"]["nearest_jaccard"] for g in r0]
    L.append(f"- median pair share {100 * sorted(ps)[len(ps) // 2]:.0f}%; "
             f"median nearest-roster Jaccard {sorted(nj)[len(nj) // 2]:.2f}")
    role_out = Counter()
    for g in r0:
        for k, v in g["role_grade"].items():
            if v["verdict"] != "in":
                role_out[f"{k} {v['verdict']}"] += 1
    beaten = [c for c in results if any(g.get("outscores_first") for g in c["rosters"][1:])]
    L.append(f"- cells where a refresh alternative OUTSCORES the button's roster: "
             f"{len(beaten)}" + (" (" + ", ".join(
                 f"{c['content']}/{c['size']}/{c['style']}" for c in beaten) + ")" if beaten else ""))
    L.append("- roles outside the cell's [p10, p90]: " + (", ".join(
        f"{k} x{v}" for k, v in role_out.most_common()) or "none"))
    reds = Counter()
    purples = Counter()
    for g in r0:
        reds.update(g["board"]["red"])
        purples.update(g["board"]["purple"])
    L.append("- rows under the bare minimum most often: " + (", ".join(
        f"{k} x{v}" for k, v in reds.most_common(8)) or "none"))
    L.append("- rows past the soft cap most often: " + (", ".join(
        f"{k} x{v}" for k, v in purples.most_common(8)) or "none"))
    wcount = Counter()
    for g in r0:
        wcount.update(set(g["party"]))
    L.append("- weapons the forge reaches for most (cells containing it): " + ", ".join(
        f"{k} x{v}" for k, v in wcount.most_common(15)))
    nev = Counter()
    for g in r0:
        nev.update(g["evidence"]["never_fielded"])
    L.append("- forged but never fielded in its cell, by weapon: " + (", ".join(
        f"{k} x{v}" for k, v in nev.most_common(15)) or "none"))
    L.append("")
    # per-cell detail
    L.append("## Cells")
    L.append("")
    for c in results:
        L.append(f"### {c['template']} - {c['size']} - {c['style']}")
        L.append("")
        L.append(f"Evidence cell: {c['evidence_cell']['distinct']} distinct rosters "
                 f"({c['evidence_cell']['n']} sightings, {c['evidence_cell']['split']}); "
                 f"role row: `{c['role_source']}`.")
        L.append("")
        for g in c["rosters"]:
            ev = g["evidence"]
            tag = "rank 0 (the button)" if g["rank"] == 0 else \
                f"rank {g['rank']} (refresh, {g.get('diff_from_first', 0)} slots differ" \
                f"{', OUTSCORES rank 0' if g.get('outscores_first') else ''})"
            L.append(f"**{tag}** - score {g['score']}, feasible {g['feasible']}, "
                     f"filler {g['filler']}, held {g['held']}")
            L.append("")
            L.append("- roster: " + ", ".join(
                f"{nm} [{ev['slots'][i]['prevalence'] * 100:.0f}%]"
                for i, nm in enumerate(g["names"])))
            rg = "; ".join(f"{k} {v['have']} (p10 {v['p10']:g} / p50 {v['p50']:g} / p90 {v['p90']:g}) {v['verdict']}"
                           for k, v in g["role_grade"].items())
            L.append(f"- roles: {rg or 'no evidence row'}")
            idn = g["identity"]
            L.append(f"- identity: {idn['style']} ({idn['strength']}"
                     f"{', ' + idn['archetype'] if idn.get('archetype') else ''})"
                     f"{' - DISAGREES with ' + c['style'] if idn['matches'] is False else ''}"
                     f"{'; conflicts: ' + ', '.join(map(str, idn['conflicts'])) if idn['conflicts'] else ''}")
            kl = g["kill_lights"] or {}
            L.append(f"- kill checklist: {g['kill_pressure']} "
                     f"(pierce {kl.get('pierce')}, heal-cut {kl.get('heal_cut')}, burst {kl.get('burst')})"
                     f"{'; weak stages: ' + ', '.join(g['weak_stages']) if g['weak_stages'] else ''}")
            b = g["board"]
            L.append(f"- board: red {', '.join(b['red']) or '-'}; orange "
                     f"{', '.join(b['orange']) or '-'}; purple {', '.join(b['purple']) or '-'}"
                     f"{'; optional short ' + ', '.join(b['optional_short']) if b['optional_short'] else ''}"
                     f"{'; ARMED FLOORS ' + ', '.join(b['floors']) if b['floors'] else ''}")
            L.append(f"- evidence: never fielded {', '.join(ev['never_fielded']) or '-'}; "
                     f"rare {', '.join(ev['rare']) or '-'}; pairs seen "
                     f"{ev['pairs_seen']}/{ev['pairs_total']}; nearest roster Jaccard "
                     f"{ev['nearest_jaccard']:.2f} (size {ev['nearest_size']})")
            hy = []
            if g["duplicates"]:
                hy.append("duplicates " + ", ".join(f"{k} x{v}" for k, v in g["duplicates"].items()))
            if g["unseated"]:
                hy.append("unseated " + ", ".join(g["unseated"]))
            if g["style_unfit"]:
                hy.append("STYLE-UNFIT " + ", ".join(g["style_unfit"]))
            if g["excluded"]:
                hy.append("EXCLUDED " + ", ".join(g["excluded"]))
            if hy:
                L.append("- hygiene: " + "; ".join(hy))
            L.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def write_form(results, date, path):
    """The human part: the owner grades each rank-0 roster blind to every
    number above (display names only, in roster order)."""
    L = [f"# Forge grading form ({date})", "",
         "One roster per cell, exactly what the forge button returns for that "
         "content / size / style. Grade each 1-5 (1 = would never field, 3 = "
         "playable with swaps, 5 = would call it as is), name the slots you "
         "would swap and what for, and give the comp's playstyle in your own "
         "words. No engine numbers are shown here on purpose; the board with "
         f"the numbers is `notes/findings/{date}-forge-quality-sweep.md` - "
         "fill this first. Score with the round's ruling pass: every "
         "disagreement becomes a ruling, an override or a golden pin the same "
         "day (VALIDATION.md, the method).", ""]
    for i, c in enumerate(results, 1):
        g = c["rosters"][0]
        L.append(f"## {i}. {c['template']} - {c['size']} players - {c['style']}")
        L.append("")
        for j, nm in enumerate(g["names"], 1):
            L.append(f"{j}. {nm}")
        L.append("")
        L.append("- grade (1-5): ")
        L.append("- swaps (slot -> weapon, why): ")
        L.append("- playstyle in your words: ")
        L.append("- notes: ")
        L.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alts", type=int, default=2, help="next-best rosters per cell")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--cells", default=None,
                    help="comma list of content:size:style to run instead of the grid")
    args = ap.parse_args()

    parties = load_harvest()
    with open(os.path.join(OUT, "role_counts.json"), encoding="utf-8") as f:
        rc = json.load(f)
    cells = []
    if args.cells:
        for spec in args.cells.split(","):
            ct, sz, st = spec.split(":")
            cells.append((ct, int(sz), st))
    else:
        for content, size in GRID:
            for style in (STYLES_SMALL if size < 10 else STYLES_LARGE):
                cells.append((content, size, style))
    results = []
    for content, size, style in cells:
        print(f"forging {content} {size} {style} ...", flush=True)
        results.append(run_cell(content, size, style, parties, rc, args.alts))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "forge_quality_report.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"_generated": args.date, "_holdout_mod": HOLDOUT_MOD,
                   "_size_window": SIZE_WINDOW, "_pair_min": PAIR_MIN,
                   "cells": results}, f, indent=1, sort_keys=True)
        f.write("\n")
    board = os.path.join(ROOT, "notes", "findings", f"{args.date}-forge-quality-sweep.md")
    write_board(results, args.date, board)
    form = os.path.join(ROOT, "tests", f"forge_grading_{args.date}.md")
    write_form(results, args.date, form)
    print(f"wrote {board}\n      {form}\n      out/forge_quality_report.json")


if __name__ == "__main__":
    main()
