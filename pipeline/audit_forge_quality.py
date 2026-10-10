#!/usr/bin/env python3
"""
FORGE QUALITY SWEEP: what the engine fields when it builds a whole comp.

Report-only audit, never part of a build. The quality gates measure the
NEXT PICK (`tests/tier2_blindtest.py v4`: published comps minus one member;
`v4h`: the same over the harvest, report-only); neither reads a FORGED
roster as a whole. This sweep does: for every content x size x style cell
of the grid below it runs the production forge (`Engine.forge(size)`,
dressed, the default suggestion pool, no locks: the planner's forge
button) and grades the roster it returns, plus the NEXT-BEST alternatives
the refresh button walks (`forge(avoid=)` over every roster already
shown), against evidence the build already carries.

Grades per forged roster (all descriptive; nothing here scores):

  structure  the forge's honesty flags (feasible / filler / held); the role
             tally (`Engine.role_of`) against the role-count cell the
             forge's own typical row comes from (out/role_counts.json p10 /
             p50 / p90: a matchmaking pool's cell, else the published comps
             below 10, the declared style's cell at 10+, the pooled row for
             balanced; a pooled row below 10 grades the healer only, the
             derivation's rule); at 10+ the primary seats (`Engine.seat_of`)
             against the seat skeleton's cell and the standoff tools against
             the plan cell (out/skeletons.json). A count outside [p10, p90]
             is a structure the typical winner does not field.
  identity   comp_identity's read of the forged roster on its own kits
             against the style it was forged FOR; the kill checklist
             (kill_pressure) and the fight chain's weak stages.
  supply     the capability board on the roster's own kits: rows under the
             bare minimum (red), between minimum and typical (orange), at
             typical (green), past the soft cap (purple, with the members
             carrying the most of it), armed floors.
  evidence   how much of the roster winners field: per slot, the weapon's
             share of the distinct rosters in the harvest cell (battle-list
             killer parties of the same size +-2 and, at 10+, the same
             identity label; inside a Dragon Portal pool the pool's
             dominant parties, the unit its rows and fielded list are fitted
             on), the share of forged weapon PAIRS seen together in at
             least PAIR_MIN rosters of the cell, and the nearest harvested
             roster (multiset Jaccard). The cell is the HOLDOUT slice
             (battle % 5 == 0, which no shipped table learns from) where it
             holds HOLDOUT_MIN rosters, else every battle (labelled).
  hygiene    copies past the penalty-free allowance, unseated weapons, and
             members a suggestion gate bars (viability exclusion, style
             unfit, generation situational, unfielded in a pool): a
             generated slot carries none of the gated kinds.

Killer parties are win-conditioned evidence of what is FIELDED, never a
verdict; prevalence is popularity, not effectiveness (standing rule 7); a
forged weapon nobody fields is a question, never an error. The harvest's
style labels come from comp_identity on weapons only. Nothing in the build
reads these outputs; every line is a hypothesis (standing rule 1).

Outputs (default `review/forge_quality/`, gitignored; `--out` moves them):
  forge_quality_report.json   every number, machine-readable
  forge_quality_board.md      the aggregates and every cell
  forge_grading_form.md       a validation round's form: display names
                              only, no engine numbers
  evidence.json.gz            the harvest parties the grades read, keyed by
                              the SHA-256 of the roster artifact and of
                              party_styles.json; a later run on the same
                              artifacts reads it instead of the artifact

Building the evidence parses the roster artifact (several GB of memory at
peak); every later run on the same artifacts is engine-only. The same
commit and artifacts write the same report, board and form (the `--date`
stamp aside).

Usage: py -3 pipeline/audit_forge_quality.py [--alts 2] [--out DIR]
       [--grid all|base|portal] [--cells content:size:style,...]
       [--rebuild-evidence] [--date YYYY-MM-DD]
"""
import argparse
import datetime
import gc
import gzip
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
OUT = os.path.join(HERE, "out")
DEFAULT_DIR = os.path.join(ROOT, "review", "forge_quality")
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from engine import DATASET, Engine  # noqa: E402

IDENTITY_STYLES = Engine.IDENTITY_STYLES
HOLDOUT_MOD = 5          # tests/tier2_blindtest.py v4h, derive_meta_prior.py
HOLDOUT_MIN = 40         # rosters a holdout cell needs before it stands alone
SIZE_WINDOW = 2          # evidence cell = size +- this
HARVEST_MAX = 20         # killer parties stop at one in-game party
PAIR_MIN = 3             # a pair "seen" needs this many rosters
RARE = 0.02              # a slot under this prevalence is "rare"
MIN_EVIDENCE_SIZE = 3    # the smallest party the base grid's windows reach
STYLE_MIN_SIZE = 10      # identity labels, style cells and the skeleton start here
PORTAL = "ancient_lands"
EVIDENCE_FORMAT = 1
ROLES = ("healer", "frontline", "support", "dps")

# The planner's grid. Sizes per content: the template's base size and the
# sizes the harvest bands cover (10 / 15 / 20), at most 20: one party caps
# at 20 and the forge refuses a party past it (a zerg forges party by
# party). Sub-10 cells run balanced and the three primary styles; 10+ cells
# run every style. The Dragon Portal grid forges each matchmaking pool at
# its top size.
GRID = [
    ("castle_outpost", 5), ("castle_outpost", 7),
    ("roads", 7),
    ("faction_war", 10), ("faction_war", 15),
    ("blackzone_roam", 10), ("blackzone_roam", 15), ("blackzone_roam", 20),
    ("territory_defense", 15), ("territory_defense", 20),
    ("castle", 20),
]
PORTAL_GRID = [(PORTAL, 3), (PORTAL, 5), (PORTAL, 7), (PORTAL, 20)]
STYLES_SMALL = ("balanced", "brawl", "clap", "kite")
STYLES_LARGE = ("balanced", "brawl", "clap", "kite", "brawl_clap", "clap_kite")
# style pairs whose rank-0 rosters are compared slot for slot at 10+
OVERLAP_PAIRS = (("kite", "clap"), ("clap_kite", "clap"), ("kite", "clap_kite"),
                 ("brawl_clap", "brawl"), ("brawl", "clap"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _jaccard(a, b):
    """Multiset Jaccard of two weapon lists."""
    ca, cb = Counter(a), Counter(b)
    inter = sum((ca & cb).values())
    union = sum((ca | cb).values())
    return inter / union if union else 0.0


def _median(xs):
    return statistics.median(xs) if xs else None


# ------------------------------------------------------------------ evidence
def build_evidence(rosters_path, styles_path):
    """The parties the grades read, from the roster artifact: battle-list
    killer parties of MIN_EVIDENCE_SIZE+ with every weapon known (the
    population every shipped table is fitted on), each with its
    party_styles.json label; and the Dragon Portal's dominant parties (no
    deaths, a kill, every weapon known: derive_portal_rows.py's unit)."""
    import party_link
    import rosters_io
    doc = rosters_io.load(rosters_path, source="all")
    with open(styles_path, encoding="utf-8") as f:
        labels = {(r["battle"], r["index"]): r["style"]
                  for r in json.load(f)["parties"] if r.get("style")}
    main, portal = [], []
    by = party_link.parties_by_battle(rosters_io.select(doc, source="battle_list"))
    for battle in sorted(by):
        for p in by[battle]:
            n = p.get("size") or 0
            ws = list(p.get("weapons") or [])
            if n < MIN_EVIDENCE_SIZE or p.get("known_weapons") != n or len(ws) != n:
                continue
            main.append({"battle": battle, "size": n, "weapons": ws,
                         "style": labels.get((battle, p["index"])),
                         "guilds": sorted(p.get("guilds") or [])})
    by = party_link.parties_by_battle(
        rosters_io.select(doc, source="all", content=PORTAL))
    for battle in sorted(by):
        for p in by[battle]:
            n = p.get("size") or 0
            ws = list(p.get("weapons") or [])
            if n < 2 or p.get("known_weapons") != n or len(ws) != n:
                continue
            if not ((p.get("deaths") or 0) == 0 and (p.get("kills") or 0) > 0):
                continue
            portal.append({"battle": battle, "size": n, "weapons": ws,
                           "guilds": sorted(p.get("guilds") or [])})
    return {"main": main, "portal": portal}


def load_evidence(out_dir, rosters_path, styles_path, rebuild=False):
    """The evidence parties, from the cache when its key matches the
    artifacts on disk, else built from the artifact and cached."""
    key = {"format": EVIDENCE_FORMAT,
           "party_rosters_sha256": sha256_file(rosters_path),
           "party_styles_sha256": sha256_file(styles_path)}
    path = os.path.join(out_dir, "evidence.json.gz")
    if not rebuild and os.path.exists(path):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("_key") == key:
            return doc, "cache"
    doc = build_evidence(rosters_path, styles_path)
    gc.collect()
    doc["_key"] = key
    os.makedirs(out_dir, exist_ok=True)
    text = json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n"
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0,
                           compresslevel=6) as g:
            g.write(text.encode("utf-8"))
    return doc, "artifact"


class Cell:
    """The evidence cell one forged roster is graded against."""

    def __init__(self, rosters, split):
        self.rosters, self.split = rosters, split
        self.n = len(rosters)
        # distinct rosters (guild set + weapon multiset), the audit's unit
        distinct = {}
        for p in rosters:
            distinct[(tuple(p["guilds"]), tuple(sorted(p["weapons"])))] = p
        self.distinct = list(distinct.values())
        self.nd = len(self.distinct)
        self.prev, self.pairs = Counter(), Counter()
        for p in self.distinct:
            ws = sorted(set(p["weapons"]))
            self.prev.update(ws)
            for i in range(len(ws)):
                for j in range(i + 1, len(ws)):
                    self.pairs[(ws[i], ws[j])] += 1

    def prevalence(self, w):
        return self.prev.get(w, 0) / self.nd if self.nd else 0.0

    def pair_seen(self, a, b):
        k = (a, b) if a <= b else (b, a)
        return self.pairs.get(k, 0) >= PAIR_MIN

    def nearest(self, party):
        best, bj = None, 0.0
        for p in self.distinct:
            j = _jaccard(party, p["weapons"])
            if j > bj:
                best, bj = p, j
        return best, bj


def evidence_cell(ev, e, size, style):
    """Inside a matchmaking pool: the pool's dominant parties at the pool's
    sizes, every weapon in the catalog (portal parties carry no style
    label). Elsewhere: battle-list parties of size +- SIZE_WINDOW around
    min(size, HARVEST_MAX), the same identity label at 10+. Holdout slice
    where it holds HOLDOUT_MIN rosters, else every battle."""
    pool = None
    for key, row in (e.template.get("pool_rows") or {}).items():
        lo, hi = row["sizes"]
        if lo <= size <= hi:
            pool = (key, lo, hi)
            break
    if pool:
        key, lo, hi = pool
        cand = [p for p in ev["portal"] if lo <= p["size"] <= hi
                and all(w in e.weapons for w in p["weapons"])]
        where = f"pool {key} dominant, any style"
    else:
        ref = min(size, HARVEST_MAX)
        styled = style in IDENTITY_STYLES and size >= STYLE_MIN_SIZE
        cand = [p for p in ev["main"] if abs(p["size"] - ref) <= SIZE_WINDOW
                and (not styled or p["style"] == style)]
        where = (f"{ref - SIZE_WINDOW}-{min(ref + SIZE_WINDOW, HARVEST_MAX)}"
                 + (f" {style}" if styled else " any style"))
    hold = [p for p in cand if p["battle"] % HOLDOUT_MOD == 0]
    if len(hold) >= HOLDOUT_MIN:
        return Cell(hold, f"holdout, {where}")
    return Cell(cand, f"all, {where}")


# ------------------------------------------------------- structural evidence
def role_cell(rc, content, size, style):
    """The role-count row the forge's typical row resolves from (the
    engine's `_role_typical` order), as ({role: {p10, p50, p90}}, source,
    roles graded)."""
    s = str(size)
    if size < STYLE_MIN_SIZE:
        pc = ((rc.get("pool_cells") or {}).get(content) or {}).get(s)
        if pc:
            return pc, f"pools[{content}][{s}] (n={pc.get('n')})", ROLES
        cc = ((rc.get("comp_cells") or {}).get(content) or {}).get(s)
        if cc:
            return cc, f"comps[{content}][{s}] (n={cc.get('n')})", ROLES
        pooled = (rc.get("sizes") or {}).get(s)
        if pooled:
            return pooled, f"pooled[{s}] (healer only below 10)", ("healer",)
        return None, "none", ()
    if style in IDENTITY_STYLES:
        sc = ((rc.get("style_cells") or {}).get(style) or {}).get(s)
        if sc:
            return sc, f"styles[{style}][{s}] (n={sc.get('n')})", ROLES
    pooled = (rc.get("sizes") or {}).get(s)
    if pooled:
        return pooled, f"pooled[{s}] (n={pooled.get('n')})", ROLES
    return None, "none", ()


def skeleton_cell(table, size, style):
    """A skeletons.json cell (seats or plan) for the style and size, the
    `_seat_typical` order: the declared style's cell at 10+, else pooled."""
    if size < STYLE_MIN_SIZE:
        return None, "none"
    s = str(size)
    if style in IDENTITY_STYLES:
        c = ((table.get("styles") or {}).get(style) or {}).get(s)
        if c:
            return c, f"styles[{style}][{s}] (n={c.get('n')})"
    c = (table.get("pooled") or {}).get(s)
    if c:
        return c, f"pooled[{s}] (n={c.get('n')})"
    return None, "none"


def _band(have, row):
    return "under" if have < row["p10"] else "over" if have > row["p90"] else "in"


# ------------------------------------------------------------------- grading
def grade_roster(e, r, cell, rctx, declared):
    party, combos = r["party"], r["combos"]
    gears = r.get("gears") or [None] * len(party)
    names = [e.weapons[w]["display_name"] for w in party]
    # --- structure: roles
    roles = Counter(e.role_of(w) for w in party)
    role_grade = {}
    rcell, _rsrc, graded = rctx["role"]
    for role in graded:
        row = (rcell or {}).get(role)
        if not row:
            continue
        have = roles.get(role, 0)
        role_grade[role] = {"have": have, "p10": row["p10"], "p50": row["p50"],
                            "p90": row["p90"], "verdict": _band(have, row)}
    # --- structure: seats and plan tools (the seat skeleton, 10+)
    seats = Counter(s for s in (e.seat_of(w) for w in party) if s is not None)
    seat_grade = {}
    scell = rctx["seat"][0]
    if scell:
        for s in sorted(set(seats) | {k for k, v in scell.items() if isinstance(v, dict)}):
            row = scell.get(s)
            have = seats.get(s, 0)
            if not isinstance(row, dict):
                seat_grade[s] = {"have": have, "verdict": "no cell row"}
                continue
            seat_grade[s] = {"have": have, "p10": row["p10"], "p50": row["p50"],
                             "p90": row["p90"], "typical": e._seat_typ.get(s),
                             "verdict": _band(have, row)}
    standoff = sum(1 for w in party if w in e.pred_members.get(e.STANDOFF, ()))
    plan = {"standoff": standoff, "minimum": e._plan_typical().get("standoff")}
    pcell = rctx["plan"][0]
    if pcell and isinstance(pcell.get("standoff"), dict):
        row = pcell["standoff"]
        plan.update({"p10": row["p10"], "p50": row["p50"], "p90": row["p90"],
                     "verdict": _band(standoff, row)})
    # --- identity
    ident = e.comp_identity(party, combos, gears)
    style_read = ident.get("style")
    if style_read is None:
        # the gank read names its archetype, never a style
        style_read = (ident.get("archetype")
                      or ("split" if "split" in (ident.get("label") or "") else "forming"))
    kp = e.kill_pressure(party, combos, gears)
    chain = e.fight_chain(party, combos, gears)
    weak_stages = [f"{st.get('name')}:{st['verdict']}"
                   for st in (chain or {}).get("stages") or []
                   if st.get("verdict") in ("weak", "missing")]
    # --- supply board on the roster's own kits
    s = e.effective_supply(party, combos, gears)
    sf = e.effective_supply(party, combos)
    board = {"red": [], "orange": [], "green": [], "purple": [], "floors": [],
             "optional_short": []}
    purple_detail = {}
    for cap in e.reqs:
        have = s.get(cap, 0.0)
        mn, tg, sc = e.target_min(cap), e.target(cap), e.soft_cap(cap)
        if have > sc:
            board["purple"].append(cap)
            top = []
            for i, w in enumerate(party):
                v = e.effective_supply([w], [combos[i]], [gears[i]]).get(cap, 0.0)
                if v > 0:
                    top.append((v, i))
            top.sort(key=lambda t: (-t[0], t[1]))
            purple_detail[cap] = {"have": round(have, 2), "target": round(tg, 2),
                                  "soft_cap": round(sc, 2),
                                  "top": [[names[i], round(v, 2)] for v, i in top[:4]]}
        elif have >= tg:
            board["green"].append(cap)
        elif cap in e.optional:
            board["optional_short"].append(cap)   # denominator-only rows
        elif have >= mn:
            board["orange"].append(cap)
        else:
            board["red"].append(cap)
        if e.floor_armed(cap, sf.get(cap, 0.0)):
            board["floors"].append(cap)
    # --- evidence
    slots = [{"weapon": w, "prevalence": round(cell.prevalence(w), 3)} for w in party]
    never = [x["weapon"] for x in slots if cell.prev.get(x["weapon"], 0) == 0]
    rare = [x["weapon"] for x in slots
            if cell.prev.get(x["weapon"], 0) > 0 and cell.prevalence(x["weapon"]) < RARE]
    distinct = sorted(set(party))
    pairs_total = pairs_seen = 0
    unseen_pairs = []
    for i in range(len(distinct)):
        for j in range(i + 1, len(distinct)):
            pairs_total += 1
            if cell.pair_seen(distinct[i], distinct[j]):
                pairs_seen += 1
            else:
                unseen_pairs.append([distinct[i], distinct[j]])
    near, nj = cell.nearest(party)
    # --- hygiene
    copies = {}
    for w, c in sorted(Counter(party).items()):
        if c > 1:
            copies[w] = {"count": c, "free": e._dup_free(w), "max": e._dup_gen_max(w)}
    gated = {
        "excluded": [w for w in party if e.is_excluded(w)],
        "style_unfit": [w for w in party if e.is_style_unfit(w)],
        "gen_situational": [w for w in party if w in e._gen_situational],
        "unfielded": [w for w in party if e.is_unfielded(w)],
    }
    return {
        "party": party, "names": names, "combos": combos,
        "kits": [list(g) if g else None for g in gears],
        # the carrier floors the forge dressed to (each with the wearers
        # the roster holds) and the slots it re-dressed
        "floors": r.get("floors") or {},
        "floor_dressed": sorted(int(i) for i, k in (r.get("kits") or {}).items()
                                if k.get("variant") == "floor"),
        "score": round(r["score"], 4), "feasible": r["feasible"],
        "filler": r["filler"], "held": r["held"],
        "exhausted": bool(r.get("exhausted")),
        "roles": {k: roles.get(k, 0) for k in ROLES}, "role_grade": role_grade,
        "seats": dict(sorted(seats.items())), "seat_grade": seat_grade, "plan": plan,
        "identity": {"style": style_read, "strength": ident.get("strength"),
                     "archetype": ident.get("archetype"), "label": ident.get("label"),
                     "kite_tools": ident.get("kite_tools"),
                     "kite_tools_min": ident.get("kite_tools_min"),
                     "matches": (style_read == declared
                                 if declared in IDENTITY_STYLES else None),
                     "conflicts": [c.get("weapon") if isinstance(c, dict) else c
                                   for c in (ident.get("conflicts") or [])]},
        "kill_pressure": (kp or {}).get("verdict"),
        "kill_lights": ({k: kp[k]["ok"] for k in ("pierce", "heal_cut", "burst")}
                        if kp else None),
        "weak_stages": weak_stages,
        "board": board, "purple_detail": purple_detail,
        "evidence": {"cell_n": cell.n, "cell_distinct": cell.nd, "split": cell.split,
                     "slots": slots, "never_fielded": never, "rare": rare,
                     "pairs_seen": pairs_seen, "pairs_total": pairs_total,
                     "pair_share": (round(pairs_seen / pairs_total, 3)
                                    if pairs_total else None),
                     "unseen_pairs": unseen_pairs[:12],
                     "nearest_jaccard": round(nj, 3),
                     "nearest": (near["weapons"] if near else None),
                     "nearest_size": (near["size"] if near else None)},
        "copies": copies,
        "unseated": [w for w in party if e._primary_seat_class(w) is None],
        "gated": gated,
    }


def run_cell(ev, rc, sk, content, size, style, alts, grid):
    e = Engine(content=content, size=size, style=style)
    cell = evidence_cell(ev, e, size, style)
    rctx = {"role": role_cell(rc, content, size, style),
            "seat": skeleton_cell(sk["seats"]["cells"], size, style),
            "plan": skeleton_cell(sk["plan"]["cells"], size, style)}
    rosters, avoid = [], []
    for k in range(1 + alts):
        # the refresh button hands the forge every roster already shown
        r = e.forge(size, avoid=[list(p) for p in avoid] or None)
        g = grade_roster(e, r, cell, rctx, style)
        g["rank"] = k
        rosters.append(g)
        if r.get("exhausted"):
            break
        avoid.append(list(r["party"]))
    first = rosters[0]
    for g in rosters[1:]:
        g["diff_from_first"] = sum((Counter(g["party"]) - Counter(first["party"])).values())
        g["outscores_first"] = g["score"] > first["score"] + 1e-6
        g["gap_share"] = (round((g["score"] - first["score"]) / abs(first["score"]), 6)
                          if first["score"] else None)
    return {"grid": grid, "content": content, "size": size, "style": style,
            "template": e.template["name"], "rosters": rosters,
            "role_source": rctx["role"][1], "seat_source": rctx["seat"][1],
            "plan_source": rctx["plan"][1],
            "pool": e.pool_key,
            # the generation rules the forge ran under: role and predicate
            # minima / maxima / typicals, and the seat typicals
            "band": {k: v for k, v in sorted((e._band or {}).items()) if isinstance(v, dict)},
            "seat_typical": dict(sorted(e._seat_typ.items())),
            "evidence_cell": {"n": cell.n, "distinct": cell.nd, "split": cell.split}}


# --------------------------------------------------------------- aggregates
def summarize(results):
    """The aggregate numbers over a set of cells (rank-0 rosters unless
    stated). `evidenced` = cells at or under HARVEST_MAX (evidence at the
    cell's own size)."""
    r0 = [c["rosters"][0] for c in results]
    out = {"cells": len(results),
           "infeasible": sum(1 for g in r0 if not g["feasible"]),
           "with_filler": sum(1 for g in r0 if g["filler"]),
           "with_held": sum(1 for g in r0 if g["held"]),
           "short": [f"{c['content']}/{c['size']}/{c['style']}: {len(c['rosters'][0]['party'])}"
                     for c in results if len(c["rosters"][0]["party"]) < c["size"]]}
    # the carrier floors: cells with any floor, cells whose every floor
    # is worn, the slots re-dressed, each effect's floored and met cells
    fl = [g for g in r0 if g.get("floors")]
    out["floors"] = {
        "cells": len(fl),
        "all_met": sum(1 for g in fl
                       if all(v["worn"] >= v["floor"] for v in g["floors"].values())),
        "redressed": sum(len(g.get("floor_dressed") or []) for g in r0),
        "by_effect": {eff: [sum(1 for g in fl if eff in g["floors"]),
                            sum(1 for g in fl if eff in g["floors"]
                                and g["floors"][eff]["worn"] >= g["floors"][eff]["floor"])]
                      for eff in sorted({k for g in fl for k in g["floors"]})}}
    # identity
    conf = {}
    for c in results:
        g = c["rosters"][0]
        if g["identity"]["matches"] is None:
            continue
        conf.setdefault(c["style"], Counter())[g["identity"]["style"]] += 1
    out["identity_styled"] = sum(sum(v.values()) for v in conf.values())
    out["identity_agree"] = sum(v.get(k, 0) for k, v in conf.items())
    out["identity_by_style"] = {k: dict(v.most_common()) for k, v in sorted(conf.items())}
    out["kill"] = dict(sorted(Counter(str(g["kill_pressure"]) for g in r0).items()))
    # roles
    with_roles = [(c, c["rosters"][0]) for c in results if c["rosters"][0]["role_grade"]]
    out["role_cells"] = len(with_roles)
    out["role_cells_all_in"] = sum(1 for _c, g in with_roles
                                   if all(v["verdict"] == "in" for v in g["role_grade"].values()))
    role_out = Counter()
    role_out_cells = []
    for c, g in with_roles:
        bad = [f"{k} {v['verdict']} ({v['have']} vs p10 {v['p10']:g} / p90 {v['p90']:g})"
               for k, v in g["role_grade"].items() if v["verdict"] != "in"]
        for k, v in g["role_grade"].items():
            if v["verdict"] != "in":
                role_out[f"{k} {v['verdict']}"] += 1
        if bad:
            role_out_cells.append(f"{c['content']}/{c['size']}/{c['style']}: " + "; ".join(bad))
    out["role_out"] = dict(role_out.most_common())
    out["role_out_cells"] = role_out_cells
    # seats and plan tools
    with_seats = [(c, c["rosters"][0]) for c in results if c["rosters"][0]["seat_grade"]]
    out["seat_cells"] = len(with_seats)
    out["seat_cells_all_in"] = sum(1 for _c, g in with_seats
                                   if all(v["verdict"] == "in" for v in g["seat_grade"].values()))
    seat_out = Counter()
    for _c, g in with_seats:
        for k, v in g["seat_grade"].items():
            if v["verdict"] != "in":
                seat_out[f"{k} {v['verdict']}"] += 1
    out["seat_out"] = dict(seat_out.most_common())
    out["standoff"] = {f"{c['content']}/{c['size']}/{c['style']}":
                       [c["rosters"][0]["plan"]["standoff"], c["rosters"][0]["plan"]["minimum"]]
                       for c in results if c["rosters"][0]["plan"]["minimum"]}
    # board
    ev_cells = [c for c in results if c["size"] <= HARVEST_MAX]
    out["evidenced_cells"] = len(ev_cells)

    def rng(key):
        v = [len(c["rosters"][0]["board"][key]) for c in ev_cells]
        return [min(v), max(v)] if v else None
    out["board_ranges"] = {"red": rng("red"), "orange": rng("orange"),
                           "green": rng("green"), "purple": rng("purple")}
    out["at_or_above_typical_range"] = (
        [min(len(c["rosters"][0]["board"]["green"]) + len(c["rosters"][0]["board"]["purple"])
             for c in ev_cells),
         max(len(c["rosters"][0]["board"]["green"]) + len(c["rosters"][0]["board"]["purple"])
             for c in ev_cells)] if ev_cells else None)
    reds, purples, floors = Counter(), Counter(), Counter()
    for g in r0:
        reds.update(g["board"]["red"])
        purples.update(g["board"]["purple"])
        floors.update(g["board"]["floors"])
    out["red_most"] = dict(reds.most_common(10))
    out["purple_most"] = dict(purples.most_common(10))
    out["floors_armed"] = dict(floors.most_common())
    out["cells_with_red"] = sum(1 for g in r0 if g["board"]["red"])
    # evidence (cells at their own size)
    tot = sum(len(c["rosters"][0]["party"]) for c in ev_cells)
    never = sum(len(c["rosters"][0]["evidence"]["never_fielded"]) for c in ev_cells)
    rare = sum(len(c["rosters"][0]["evidence"]["rare"]) for c in ev_cells)
    out["evidence"] = {"slots": tot, "never": never, "rare": rare,
                       "never_share": round(never / tot, 3) if tot else None,
                       "rare_share": round(rare / tot, 3) if tot else None}
    by_style = {}
    for c in ev_cells:
        g = c["rosters"][0]
        b = by_style.setdefault(c["style"], [0, 0, 0])
        b[0] += len(g["party"])
        b[1] += len(g["evidence"]["never_fielded"])
        b[2] += len(g["evidence"]["rare"])
    out["evidence_by_style"] = {k: {"slots": v[0], "never": v[1], "rare": v[2],
                                    "never_share": round(v[1] / v[0], 3),
                                    "rare_share": round(v[2] / v[0], 3)}
                                for k, v in sorted(by_style.items())}
    ps = [c["rosters"][0]["evidence"]["pair_share"] for c in ev_cells
          if c["rosters"][0]["evidence"]["pair_share"] is not None]
    nj = [c["rosters"][0]["evidence"]["nearest_jaccard"] for c in ev_cells]
    out["median_pair_share"] = _median(ps)
    out["median_nearest_jaccard"] = _median(nj)
    out["evidence_splits"] = dict(Counter(c["evidence_cell"]["split"].split(",")[0]
                                          for c in ev_cells))
    # the weapons the forge reaches for, at 10+ (every cell's own evidence)
    big = [c for c in results if c["size"] >= STYLE_MIN_SIZE]
    out["cells_10_plus"] = len(big)
    reach = {}
    for c in big:
        g = c["rosters"][0]
        for slot in g["evidence"]["slots"]:
            w = slot["weapon"]
            rec = reach.setdefault(w, {"name": None, "cells": set(), "max_prev": 0.0,
                                       "zero_cells": set(), "slots": 0})
            rec["slots"] += 1
            key = (c["content"], c["size"], c["style"])
            rec["cells"].add(key)
            rec["max_prev"] = max(rec["max_prev"], slot["prevalence"])
            if w in g["evidence"]["never_fielded"]:
                rec["zero_cells"].add(key)
        for w, nm in zip(g["party"], g["names"]):
            reach[w]["name"] = nm
    out["reach_10_plus"] = sorted(
        ({"weapon": w, "name": v["name"], "cells": len(v["cells"]), "slots": v["slots"],
          "max_prevalence": round(v["max_prev"], 3), "zero_cells": len(v["zero_cells"])}
         for w, v in reach.items()),
        key=lambda d: (-d["cells"], -d["slots"], d["weapon"]))
    nev = Counter()
    names = {}
    for c in results:
        g = c["rosters"][0]
        nev.update(g["evidence"]["never_fielded"])
        names.update(zip(g["party"], g["names"]))
    out["never_by_weapon"] = [[names[w], n] for w, n in nev.most_common(15)]
    # hygiene
    gated = Counter()
    for g in r0:
        for k, v in g["gated"].items():
            gated[k] += len(v)
    out["gated_members"] = dict(sorted(gated.items()))
    out["unseated_members"] = sum(len(g["unseated"]) for g in r0)
    out["charged_copies"] = sum(1 for g in r0 for v in g["copies"].values()
                                if v["count"] > v["free"])
    out["copies_past_max"] = sum(1 for g in r0 for v in g["copies"].values()
                                 if v["count"] > v["max"])
    # refresh alternatives
    alts = [(c, g) for c in results for g in c["rosters"][1:]]
    beaten = [c for c in results if any(g.get("outscores_first") for g in c["rosters"][1:])]
    gaps = [g["gap_share"] for _c, g in alts if g.get("outscores_first")]
    best_gap = []
    for c in beaten:
        best_gap.append(max(g["gap_share"] for g in c["rosters"][1:] if g.get("outscores_first")))
    out["refresh"] = {
        "alternatives": len(alts),
        "exhausted": sum(1 for _c, g in alts if g["exhausted"]),
        "cells_beaten": len(beaten),
        "beaten": [f"{c['content']}/{c['size']}/{c['style']}" for c in beaten],
        "alternatives_beating": len(gaps),
        "median_gap_share": _median(best_gap),
        "max_gap_share": max(best_gap) if best_gap else None,
        "diff_slots": dict(sorted(Counter(g["diff_from_first"] for _c, g in alts).items())),
    }
    # how alike the rank-0 rosters of two styles are at one content and size
    by_cs = {}
    for c in big:
        by_cs.setdefault((c["content"], c["size"]), {})[c["style"]] = c["rosters"][0]["party"]
    overlap = {}
    for a, b in OVERLAP_PAIRS:
        rows = []
        for (content, size), st in sorted(by_cs.items()):
            if a in st and b in st:
                shared = sum((Counter(st[a]) & Counter(st[b])).values())
                rows.append([f"{content}/{size}", shared, size])
        if rows:
            overlap[f"{a}~{b}"] = {"rows": rows,
                                   "mean_share": round(sum(r[1] / r[2] for r in rows) / len(rows), 3)}
    out["style_overlap"] = overlap
    return out


def fmt_pct(v):
    return "-" if v is None else f"{100 * v:.0f}%"


def summary_lines(title, s):
    L = [f"## {title}", ""]
    L.append(f"- cells: {s['cells']}; infeasible: {s['infeasible']}; with filler slots: "
             f"{s['with_filler']}; with held slots: {s['with_held']}"
             + (f"; short rosters: {', '.join(s['short'])}" if s["short"] else ""))
    f = s.get("floors") or {}
    if f.get("cells"):
        L.append(f"- carrier floors: {f['all_met']}/{f['cells']} floored cells wear every "
                 f"floor; {f['redressed']} slots re-dressed to a floor; met per effect: "
                 + ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in f["by_effect"].items()))
    L.append(f"- identity agrees with the forged-for style: {s['identity_agree']}/"
             f"{s['identity_styled']} styled cells")
    for st, reads in s["identity_by_style"].items():
        n = sum(reads.values())
        L.append(f"  - forged for {st} ({n}): " + ", ".join(f"{k} {v}" for k, v in reads.items()))
    L.append("- kill checklist: " + ", ".join(f"{k} {v}" for k, v in s["kill"].items()))
    L.append(f"- roles inside the cell's [p10, p90]: {s['role_cells_all_in']}/{s['role_cells']} "
             "cells with a role row; outside: "
             + (", ".join(f"{k} x{v}" for k, v in s["role_out"].items()) or "none"))
    for row in s["role_out_cells"]:
        L.append(f"  - {row}")
    if s["seat_cells"]:
        L.append(f"- seats inside the skeleton cell's [p10, p90]: {s['seat_cells_all_in']}/"
                 f"{s['seat_cells']} cells; outside: "
                 + (", ".join(f"{k} x{v}" for k, v in s["seat_out"].items()) or "none"))
    if s["standoff"]:
        L.append("- standoff tools forged vs the plan minimum: " + ", ".join(
            f"{k} {v[0]}/{v[1]}" for k, v in s["standoff"].items()))
    br = s["board_ranges"]
    if br["red"]:
        L.append(f"- board over the {s['evidenced_cells']} cells at <= {HARVEST_MAX}: rows at or "
                 f"above typical {s['at_or_above_typical_range'][0]}-"
                 f"{s['at_or_above_typical_range'][1]}, between min and typical "
                 f"{br['orange'][0]}-{br['orange'][1]}, under the bare minimum "
                 f"{br['red'][0]}-{br['red'][1]} (cells with any: {s['cells_with_red']}), "
                 f"past the soft cap {br['purple'][0]}-{br['purple'][1]}")
    L.append("- rows under the bare minimum most often: " + (", ".join(
        f"{k} x{v}" for k, v in s["red_most"].items()) or "none"))
    L.append("- rows past the soft cap most often: " + (", ".join(
        f"{k} x{v}" for k, v in s["purple_most"].items()) or "none"))
    L.append("- armed floors: " + (", ".join(
        f"{k} x{v}" for k, v in s["floors_armed"].items()) or "none"))
    ev = s["evidence"]
    if ev["slots"]:
        L.append(f"- slots at <= {HARVEST_MAX}: {ev['slots']}; never fielded in the cell: "
                 f"{ev['never']} ({fmt_pct(ev['never_share'])}); rare (< {RARE:.0%}): "
                 f"{ev['rare']} ({fmt_pct(ev['rare_share'])}); evidence splits "
                 + ", ".join(f"{k} {v}" for k, v in s["evidence_splits"].items()))
        L.append("  - by style: " + "; ".join(
            f"{k} never {fmt_pct(v['never_share'])} rare {fmt_pct(v['rare_share'])}"
            for k, v in s["evidence_by_style"].items()))
        L.append(f"- median pair share {fmt_pct(s['median_pair_share'])}; median nearest-roster "
                 f"Jaccard {s['median_nearest_jaccard']:.2f}")
    if s["reach_10_plus"]:
        L.append(f"- weapons the forge reaches for at 10+ (cells containing it of "
                 f"{s['cells_10_plus']}; its highest prevalence in those cells' evidence; "
                 "cells whose evidence never fields it): "
                 + ", ".join(
                     f"{d['name']} {d['cells']} (max {fmt_pct(d['max_prevalence'])}, zero in "
                     f"{d['zero_cells']})" for d in s["reach_10_plus"][:15]))
    L.append("- forged but never fielded in its cell, by weapon: " + (", ".join(
        f"{n} x{v}" for n, v in s["never_by_weapon"]) or "none"))
    L.append("- hygiene: gated members " + ", ".join(
        f"{k} {v}" for k, v in s["gated_members"].items())
        + f"; unseated {s['unseated_members']}; charged copies {s['charged_copies']}; "
        f"copies past the forge's cap {s['copies_past_max']}")
    rf = s["refresh"]
    L.append(f"- refresh alternatives: {rf['alternatives']} ({rf['exhausted']} exhausted); "
             f"cells where one OUTSCORES the button's roster: {rf['cells_beaten']}"
             + (f" (best gap median {100 * rf['median_gap_share']:.2f}%, max "
                f"{100 * rf['max_gap_share']:.2f}% of comp_score)" if rf["cells_beaten"] else "")
             + "; slots differing from the button's roster: "
             + ", ".join(f"{k}: {v}" for k, v in rf["diff_slots"].items()))
    if rf["beaten"]:
        L.append("  - " + ", ".join(rf["beaten"]))
    for pair, v in s["style_overlap"].items():
        a, b = pair.split("~")
        L.append(f"- {a} vs {b} rank-0 rosters share {fmt_pct(v['mean_share'])} of their "
                 "slots on average: " + ", ".join(f"{r[0]} {r[1]}/{r[2]}" for r in v["rows"]))
    L.append("")
    return L


def write_board(results, summaries, meta, path):
    L = [f"# Forge quality sweep ({meta['date']})", ""]
    L.append("Report-only (`pipeline/audit_forge_quality.py`). Every cell is the production "
             "forge (`Engine.forge(size)`, dressed, default pool, no locks: the planner's "
             "forge button) graded against evidence the build already carries. Rank 0 is "
             "the roster the button returns; ranks 1+ are what refresh walks "
             "(`forge(avoid=)` over every roster shown).")
    L.append("")
    L.append(f"Commit `{meta['commit']}`; dataset SHA-256 `{meta['dataset_sha256']}`; roster "
             f"artifact SHA-256 `{meta['party_rosters_sha256']}`; evidence read from the "
             f"{meta['evidence_from']}.")
    L.append("")
    L.append("Read before deciding anything: the evidence cell is killer parties of the same "
             "size (+-2) and, at 10+, the same identity label (inside a Dragon Portal pool: "
             "the pool's dominant parties); it is win-conditioned evidence of what is "
             "FIELDED, and prevalence is popularity, not effectiveness. A forged weapon "
             "nobody fields is a question, never an error. `holdout` cells read only battles "
             "with `id % 5 == 0` (the slice no shipped table learns from); `all` cells were "
             "too thin for that. Nothing in the build reads this file.")
    L.append("")
    for title, key in (("Aggregates: the planner grid (rank-0 rosters)", "base"),
                       ("Aggregates: the Dragon Portal pools (rank-0 rosters)", "portal")):
        if summaries.get(key):
            L.extend(summary_lines(title, summaries[key]))
    L.append("## Summary board (rank-0 roster per cell)")
    L.append("")
    L.append("| content | size | style | feasible | filler/held | roles H/F/S/D | roles vs cell | "
             "seats out | standoff | identity read | kill | weak stages | board R/O/G/P | "
             "floors | never | rare | pairs seen | nearest | cell (distinct, split) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in results:
        g = c["rosters"][0]
        ro = g["roles"]
        rv = ",".join(f"{k[0].upper()}:{v['verdict']}" for k, v in g["role_grade"].items()
                      if v["verdict"] != "in") or ("all in" if g["role_grade"] else "-")
        so = [k for k, v in g["seat_grade"].items() if v["verdict"] != "in"]
        seats_out = (", ".join(so) if so else "none") if g["seat_grade"] else "-"
        pl = g["plan"]
        standoff = f"{pl['standoff']}" + (f"/{pl['minimum']}" if pl["minimum"] else "")
        ident = g["identity"]
        iread = ident["style"] if ident["matches"] is not False else f"**{ident['style']}**"
        if ident.get("archetype"):
            iread += f" ({ident['archetype']})"
        b = g["board"]
        ev = g["evidence"]
        L.append(
            f"| {c['content']} | {c['size']} | {c['style']} | "
            f"{'yes' if g['feasible'] else '**NO**'} | {len(g['filler'])}/{len(g['held'])} | "
            f"{ro['healer']}/{ro['frontline']}/{ro['support']}/{ro['dps']} | {rv} | "
            f"{seats_out} | {standoff} | {iread} | {g['kill_pressure'] or '-'} | "
            f"{len(g['weak_stages'])} | "
            f"{len(b['red'])}/{len(b['orange'])}/{len(b['green'])}/{len(b['purple'])} | "
            f"{len(b['floors'])} | {len(ev['never_fielded'])} | {len(ev['rare'])} | "
            f"{fmt_pct(ev['pair_share'])} | {ev['nearest_jaccard']:.2f} | "
            f"{ev['cell_distinct']}, {ev['split']} |")
    L.append("")
    L.append("Columns: roles = healer / frontline / support / dps by `role_of`; roles vs cell = "
             "roles outside the role-count cell's [p10, p90] (H/F/S/D:under|over); seats out = "
             "primary seats outside the skeleton cell's [p10, p90]; standoff = standoff tools "
             "forged / the plan minimum; identity read = `comp_identity` on the forged roster's "
             "kits (bold = disagrees with the style forged for); board = capability rows under "
             "the bare minimum / under typical / at typical / past the soft cap; never = forged "
             f"weapons with no roster in the evidence cell; rare = under {RARE:.0%} of the "
             f"cell's distinct rosters; pairs seen = share of distinct forged weapon pairs in "
             f">= {PAIR_MIN} rosters; nearest = multiset Jaccard to the closest harvested "
             "roster.")
    L.append("")
    L.append("## Cells")
    L.append("")
    for c in results:
        L.append(f"### {c['template']} - {c['size']} - {c['style']}")
        L.append("")
        L.append(f"Evidence cell: {c['evidence_cell']['distinct']} distinct rosters "
                 f"({c['evidence_cell']['n']} sightings, {c['evidence_cell']['split']}); role row "
                 f"`{c['role_source']}`; seat row `{c['seat_source']}`; plan row "
                 f"`{c['plan_source']}`" + (f"; pool `{c['pool']}`" if c["pool"] else "") + ".")
        L.append("")
        L.append("Generation rules: " + "; ".join(
            f"{k} " + ", ".join(f"{rk} {rv}" for rk, rv in sorted(v.items()))
            for k, v in c["band"].items()) + ".")
        L.append("")
        for g in c["rosters"]:
            ev = g["evidence"]
            tag = ("rank 0 (the button)" if g["rank"] == 0 else
                   f"rank {g['rank']} (refresh, {g.get('diff_from_first', 0)} slots differ"
                   f"{', OUTSCORES rank 0' if g.get('outscores_first') else ''}"
                   f"{', exhausted' if g['exhausted'] else ''})")
            L.append(f"**{tag}** - score {g['score']}, feasible {g['feasible']}, "
                     f"filler {g['filler']}, held {g['held']}")
            L.append("")
            L.append("- roster: " + ", ".join(
                f"{nm} [{ev['slots'][i]['prevalence'] * 100:.0f}%]"
                for i, nm in enumerate(g["names"])))
            rg = "; ".join(f"{k} {v['have']} (p10 {v['p10']:g} / p50 {v['p50']:g} / p90 "
                           f"{v['p90']:g}) {v['verdict']}" for k, v in g["role_grade"].items())
            L.append(f"- roles: {rg or 'no evidence row'}")
            if g["seat_grade"]:
                L.append("- seats: " + "; ".join(
                    f"{k} {v['have']}"
                    + (f" (p10 {v['p10']:g} / p50 {v['p50']:g} / p90 {v['p90']:g}, typical "
                       f"{v['typical']}) {v['verdict']}" if "p10" in v else f" {v['verdict']}")
                    for k, v in g["seat_grade"].items() if v["have"] or v["verdict"] != "in"))
            idn = g["identity"]
            L.append(f"- identity: {idn['style']} ({idn['strength']}"
                     f"{', ' + idn['archetype'] if idn.get('archetype') else ''}; kite tools "
                     f"{idn['kite_tools']}, hybrid floor {idn['kite_tools_min']})"
                     f"{' - DISAGREES with ' + c['style'] if idn['matches'] is False else ''}"
                     f"{'; conflicts: ' + ', '.join(map(str, idn['conflicts'])) if idn['conflicts'] else ''}")
            kl = g["kill_lights"] or {}
            L.append(f"- kill checklist: {g['kill_pressure']} (pierce {kl.get('pierce')}, "
                     f"heal-cut {kl.get('heal_cut')}, burst {kl.get('burst')})"
                     f"{'; weak stages: ' + ', '.join(g['weak_stages']) if g['weak_stages'] else ''}")
            b = g["board"]
            L.append(f"- board: red {', '.join(b['red']) or '-'}; orange "
                     f"{', '.join(b['orange']) or '-'}; purple {', '.join(b['purple']) or '-'}"
                     f"{'; optional short ' + ', '.join(b['optional_short']) if b['optional_short'] else ''}"
                     f"{'; ARMED FLOORS ' + ', '.join(b['floors']) if b['floors'] else ''}")
            for cap, d in g["purple_detail"].items():
                L.append(f"  - {cap} {d['have']:g} (target {d['target']:g}, soft cap "
                         f"{d['soft_cap']:g}): " + ", ".join(f"{n} {v:g}" for n, v in d["top"]))
            L.append(f"- evidence: never fielded {', '.join(ev['never_fielded']) or '-'}; "
                     f"rare {', '.join(ev['rare']) or '-'}; pairs seen "
                     f"{ev['pairs_seen']}/{ev['pairs_total']}; nearest roster Jaccard "
                     f"{ev['nearest_jaccard']:.2f} (size {ev['nearest_size']})")
            hy = []
            if g["copies"]:
                hy.append("copies " + ", ".join(
                    f"{k} x{v['count']} (free {v['free']}, max {v['max']})"
                    for k, v in g["copies"].items()))
            if g["unseated"]:
                hy.append("unseated " + ", ".join(g["unseated"]))
            for k, v in g["gated"].items():
                if v:
                    hy.append(f"GATED {k} " + ", ".join(v))
            if hy:
                L.append("- hygiene: " + "; ".join(hy))
            L.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def write_form(results, date, path):
    """A validation round's form: each rank-0 roster in display names, in
    roster order, with no engine number beside it."""
    L = [f"# Forge grading form ({date})", "",
         "One roster per cell, exactly what the forge button returns for that content / "
         "size / style. Grade each 1-5 (1 = would never field, 3 = playable with swaps, "
         "5 = would call it as is), name the slots to swap and what for, and give the "
         "comp's playstyle in plain words. No engine numbers are shown here on purpose; "
         "the board with the numbers sits beside this form and is read after it. Every "
         "disagreement becomes a rule change, a cited override or a golden pin the same "
         "day (tests/VALIDATION.md, the method).", ""]
    for i, c in enumerate(results, 1):
        g = c["rosters"][0]
        L.append(f"## {i}. {c['template']} - {c['size']} players - {c['style']}")
        L.append("")
        for j, nm in enumerate(g["names"], 1):
            L.append(f"{j}. {nm}")
        L.append("")
        L.append("- grade (1-5): ")
        L.append("- swaps (slot -> weapon, why): ")
        L.append("- playstyle: ")
        L.append("- notes: ")
        L.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="Report-only forge quality sweep: forge every grid cell and grade "
                    "the rosters against the harvest (module docstring).")
    ap.add_argument("--alts", type=int, default=2, help="refresh alternatives per cell")
    ap.add_argument("--out", default=DEFAULT_DIR,
                    help="output directory (default: review/forge_quality, gitignored)")
    ap.add_argument("--grid", choices=("all", "base", "portal"), default="all",
                    help="the planner grid, the Dragon Portal pools, or both")
    ap.add_argument("--cells", default=None,
                    help="comma list of content:size:style to run instead of the grid")
    ap.add_argument("--rebuild-evidence", action="store_true",
                    help="parse the roster artifact even when the evidence cache matches")
    ap.add_argument("--date", default=datetime.date.today().isoformat(),
                    help="the stamp on the board and the form")
    args = ap.parse_args()

    rosters_path = os.path.join(OUT, "party_rosters.json.gz")
    styles_path = os.path.join(OUT, "party_styles.json")
    t0 = time.time()
    ev, source = load_evidence(args.out, rosters_path, styles_path, args.rebuild_evidence)
    print(f"evidence from the {source}: {len(ev['main'])} parties, {len(ev['portal'])} "
          f"portal parties ({time.time() - t0:.0f}s)", flush=True)
    with open(os.path.join(OUT, "role_counts.json"), encoding="utf-8") as f:
        rc = json.load(f)
    with open(os.path.join(OUT, "skeletons.json"), encoding="utf-8") as f:
        sk = json.load(f)
    cells = []
    if args.cells:
        for spec in args.cells.split(","):
            ct, sz, st = spec.split(":")
            cells.append((ct, int(sz), st, "portal" if ct == PORTAL else "base"))
    else:
        grids = (("base", GRID), ("portal", PORTAL_GRID))
        for name, grid in grids:
            if args.grid not in ("all", name):
                continue
            for content, size in grid:
                for style in (STYLES_SMALL if size < STYLE_MIN_SIZE else STYLES_LARGE):
                    cells.append((content, size, style, name))
    results = []
    for content, size, style, grid in cells:
        t = time.time()
        results.append(run_cell(ev, rc, sk, content, size, style, args.alts, grid))
        g = results[-1]["rosters"][0]
        print(f"forged {content} {size} {style}: score {g['score']}, identity "
              f"{g['identity']['style']} ({time.time() - t:.1f}s)", flush=True)
    summaries = {k: summarize([c for c in results if c["grid"] == k])
                 for k in ("base", "portal") if any(c["grid"] == k for c in results)}
    meta = {"date": args.date, "commit": git_head(),
            "dataset_sha256": sha256_file(DATASET),
            "party_rosters_sha256": ev["_key"]["party_rosters_sha256"],
            "party_styles_sha256": ev["_key"]["party_styles_sha256"],
            "evidence_from": "evidence cache" if source == "cache" else "roster artifact"}
    os.makedirs(args.out, exist_ok=True)
    report = os.path.join(args.out, "forge_quality_report.json")
    with open(report, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"_meta": {k: v for k, v in meta.items() if k != "evidence_from"},
                   "_holdout_mod": HOLDOUT_MOD, "_holdout_min": HOLDOUT_MIN,
                   "_size_window": SIZE_WINDOW, "_pair_min": PAIR_MIN, "_rare": RARE,
                   "summaries": summaries, "cells": results}, f, indent=1, sort_keys=True)
        f.write("\n")
    board = os.path.join(args.out, "forge_quality_board.md")
    write_board(results, summaries, meta, board)
    form = os.path.join(args.out, "forge_grading_form.md")
    write_form(results, args.date, form)
    print(f"{len(results)} cells in {time.time() - t0:.0f}s\nwrote {report}\n      {board}\n"
          f"      {form}")


if __name__ == "__main__":
    main()
