"""Seat skeletons and copy allowances of the typical winner, GENERATED
from the committed evidence (owner ruling 2026-09-15, "full autonomy" on
the skeleton-first assessment; spec
notes/specs/2026-09-15-skeleton-first-generation-design.md).

Two tables the forge reads, both from the TRAINING split only (battles
with id % HOLDOUT_MOD != 0 — the meta prior's rule; the % 5 == 0 slice is
tier2_blindtest v4h's holdout and nothing shipped learns from it):

  seats     per exact size at 10+, pooled (every winner at the size) and
            per DECLARED style (party_styles.json labels): the p10 / p50 /
            p90 count of every PRIMARY SEAT — Engine.seat_of, the weapon's
            role_menu[0], the one role read (CLAUDE.md invariant: never a
            second classification). A cell pools a +-1 then +-2 size
            window until it holds >= MIN_DISTINCT rosters (`window`
            stated); a size that never reaches it has no cell. `typical` =
            round-half-up(p50) where p50 >= 1; a seat most winners field
            none of writes nothing ("most field none" is not a count).
            Below 10 no row exists: killer parties below 10 are open-world
            squads (standing rule 18), and the published comps are too few
            to take a seat median. Unknown stays explicit.
  copies    per style x band (10-14 / 15-19 / 20+) and pooled, for every
            weapon fielded in >= MIN_DISTINCT rosters of the cell: rosters
            fielding it, copies p50 / p90, the share with 2+ and 3+ copies,
            and the allowance the forge reads — free = round-half-up(p50)
            (never below 1), max = ceil(p90) (never below free). A weapon
            under the floor has no row and keeps the composition defaults.
            This REPLACES the hand-kept composition.yaml `per_weapon` list
            (build_dataset refuses a hand-set one since 2026-09-15).
  distinct  per style x band: distinct weapons per roster (p10/p50/p90) —
            a report line, nothing reads it.

Vote unit: one DISTINCT roster (guild set + weapon multiset) one vote, the
style-board convention — the same guild's standing comp recurring across
nights is one roster. Fully-known parties only (known_weapons == size and
every weapon in the catalogue).

Reads committed files only; never the raw cache. Explicit step, never part
of a normal build. Rerun order after a harvest: sample_parties ->
audit_style_rosters -> derive_style_bands -> derive_party_styles ->
derive_meta_prior -> derive_role_counts -> derive_skeletons ->
build_dataset -> gates. build_dataset.py refuses a skeletons.json whose
recorded artifact hashes do not match the artifacts on disk or that was
not derived on the training split.

    py -3 pipeline/derive_skeletons.py
"""
import datetime
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import rosters_io  # noqa: E402
import jsonfmt  # noqa: E402

ARTIFACT = rosters_io.path(OUT)
STYLES_ARTIFACT = os.path.join(OUT, "party_styles.json")
TARGET = os.path.join(OUT, "skeletons.json")

BANDS = {"10-14": (10, 14), "15-19": (15, 19), "20": (20, 99)}
MIN_DISTINCT = 40      # the style-band / role-count convention
STYLE_MIN_SIZE = 10
WINDOWS = (0, 1, 2)
HOLDOUT_MOD = 5        # battles with id % 5 == 0 are tier2_blindtest v4h's holdout


def in_split(battle, holdout_mod):
    """Training-split membership (derive_meta_prior.in_split)."""
    if not holdout_mod:
        return True
    try:
        return int(battle) % holdout_mod != 0
    except (TypeError, ValueError):
        return False


def half_up(x):
    return int(x + 0.5)


def percentile(values, q):
    """Linear-interpolated percentile (numpy default) on a sorted copy."""
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(v[lo])
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def _stats(rows):
    return {"p10": round(percentile(rows, 0.10), 2),
            "p50": round(percentile(rows, 0.50), 2),
            "p90": round(percentile(rows, 0.90), 2)}


def band_of(size):
    for key, (lo, hi) in BANDS.items():
        if lo <= size <= hi:
            return key
    return None


def distinct_rosters(doc, labels, known, holdout_mod, min_size=STYLE_MIN_SIZE):
    """Yield one record per DISTINCT fully-known killer roster of
    `min_size`+ on the training split: {size, style, weapons}."""
    seen = set()
    for p in doc.get("parties") or []:
        size = p.get("size") or 0
        if size < min_size or (p.get("known_weapons") or 0) < size:
            continue
        if not in_split(p.get("battle"), holdout_mod):
            continue
        ws = [w for w in (p.get("weapons") or []) if w in known]
        if len(ws) < size:
            continue
        key = (tuple(sorted(p.get("guilds") or [])), tuple(sorted(ws)))
        if key in seen:
            continue
        seen.add(key)
        yield {"size": size,
               "style": labels.get((p.get("battle"), p.get("index"))),
               "weapons": ws}


def _seat_counts(weapons, seat_of, universe):
    counts = {s: 0 for s in universe}
    for w in weapons:
        s = seat_of(w)
        if s is not None:
            counts[s] = counts.get(s, 0) + 1
    return counts


def _seat_cells(by_size, universe):
    """Per exact size, the windowed cell and its typical row."""
    cells, typical = {}, {}
    if not by_size:
        return cells, typical
    lo, hi = min(by_size), max(by_size)
    for size in range(lo, hi + 1):
        picked = None
        for w in WINDOWS:
            rows = []
            for s2 in range(size - w, size + w + 1):
                rows.extend(by_size.get(s2) or [])
            if len(rows) >= MIN_DISTINCT:
                picked = (w, rows)
                break
        if picked is None:
            continue
        w, rows = picked
        cell = {"n": len(rows), "window": w}
        typ = {}
        for seat in sorted(universe):
            vals = [r.get(seat, 0) for r in rows]
            cell[seat] = _stats(vals)
            p50 = percentile(vals, 0.5)
            if p50 >= 1:
                typ[seat] = half_up(p50)
        cells[str(size)] = cell
        # a cell that exists always writes its typical row, EMPTY when the
        # style's winners field none of anything counted — the engine must
        # tell "this style fields none" (no demand) from "no cell" (fall
        # back to the pooled row); brawl 20 fell through to the pooled
        # standoff minimum before this distinction existed
        typical[str(size)] = typ
    return cells, typical


def _copy_cell(rosters):
    """Per weapon fielded in >= MIN_DISTINCT rosters of the cell: the copy
    distribution and the allowance the forge reads."""
    per = {}
    for r in rosters:
        counts = {}
        for w in r["weapons"]:
            counts[w] = counts.get(w, 0) + 1
        for w, c in counts.items():
            per.setdefault(w, []).append(c)
    out = {}
    for w, copies in sorted(per.items()):
        if len(copies) < MIN_DISTINCT:
            continue
        p50 = percentile(copies, 0.5)
        p90 = percentile(copies, 0.9)
        free = max(1, half_up(p50))
        mx = max(free, int(math.ceil(p90 - 1e-9)))
        out[w] = {"n": len(copies), "p50": round(p50, 2), "p90": round(p90, 2),
                  "share2": round(sum(c >= 2 for c in copies) / len(copies), 2),
                  "share3": round(sum(c >= 3 for c in copies) / len(copies), 2),
                  "free": free, "max": mx}
    return out


def _distinct_cell(rosters):
    vals = [len(set(r["weapons"])) for r in rosters]
    if len(vals) < MIN_DISTINCT:
        return None
    d = _stats(vals)
    d["n"] = len(vals)
    return d


PLAN_KEYS = ("standoff",)   # plan tools counted per roster, see derive()


def derive(doc, labels, seat_of, known, holdout_mod=HOLDOUT_MOD, universe=None,
           plan_of=None):
    """`labels` = {(battle, index): style}; `seat_of(weapon)` -> primary seat
    id or None; `known` = catalogue weapon ids; `universe` = every seat id
    a catalogue weapon can carry (derived from `known` when omitted);
    `plan_of(weapon)` -> the set of PLAN tools the weapon is (today only
    `standoff`: the E is a standoff tool, style_fit.standoff_e — the fact
    the identity read defines a kiting plan by). The plan table is the
    same windowed typical per style x size as the seats: what a style's
    winners field of each tool. The forge reads it as a generation
    MINIMUM (a kite forged without its standoff tools is not the kite the
    engine itself would label), so a style whose winners field none
    carries no row and demands nothing."""
    if universe is None:
        universe = sorted({s for s in (seat_of(w) for w in known) if s})
    plan_of = plan_of or (lambda w: frozenset())
    rosters = list(distinct_rosters(doc, labels, known, holdout_mod))
    pooled_by_size, styled_by_size = {}, {}
    plan_pooled, plan_styled = {}, {}
    pooled_band, styled_band = {}, {}
    for r in rosters:
        sc = _seat_counts(r["weapons"], seat_of, universe)
        pc = {k: 0 for k in PLAN_KEYS}
        for w in r["weapons"]:
            for k in plan_of(w):
                if k in pc:
                    pc[k] += 1
        pooled_by_size.setdefault(r["size"], []).append(sc)
        plan_pooled.setdefault(r["size"], []).append(pc)
        band = band_of(r["size"])
        pooled_band.setdefault(band, []).append(r)
        if r["style"]:
            styled_by_size.setdefault(r["style"], {}).setdefault(
                r["size"], []).append(sc)
            plan_styled.setdefault(r["style"], {}).setdefault(
                r["size"], []).append(pc)
            styled_band.setdefault(r["style"], {}).setdefault(
                band, []).append(r)
    seat_cells, seat_typ = _seat_cells(pooled_by_size, universe)
    seats = {"cells": {"pooled": seat_cells, "styles": {}},
             "typical": {"pooled": seat_typ, "styles": {}}}
    for st in sorted(styled_by_size):
        c, t = _seat_cells(styled_by_size[st], universe)
        if c:
            seats["cells"]["styles"][st] = c
        if t:
            seats["typical"]["styles"][st] = t
    plan_cells, plan_typ = _seat_cells(plan_pooled, list(PLAN_KEYS))
    plan = {"cells": {"pooled": plan_cells, "styles": {}},
            "typical": {"pooled": plan_typ, "styles": {}}}
    for st in sorted(plan_styled):
        c, t = _seat_cells(plan_styled[st], list(PLAN_KEYS))
        if c:
            plan["cells"]["styles"][st] = c
        if t:
            plan["typical"]["styles"][st] = t
    copies = {"pooled": {}, "styles": {}}
    distinct = {"pooled": {}, "styles": {}}
    for band in BANDS:
        rows = pooled_band.get(band) or []
        cell = _copy_cell(rows)
        if cell:
            copies["pooled"][band] = cell
        dc = _distinct_cell(rows)
        if dc:
            distinct["pooled"][band] = dc
    for st in sorted(styled_band):
        for band in BANDS:
            rows = styled_band[st].get(band) or []
            cell = _copy_cell(rows)
            if cell:
                copies["styles"].setdefault(st, {})[band] = cell
            dc = _distinct_cell(rows)
            if dc:
                distinct["styles"].setdefault(st, {})[band] = dc
    return {
        "_source": {"party_rosters_sha256": None,
                    "party_styles_sha256": None},
        "_split": {"holdout_mod": holdout_mod,
                   "rule": (f"battle % {holdout_mod} != 0 (training split; "
                            f"% {holdout_mod} == 0 is the v4h holdout)"
                            if holdout_mod else
                            "all battles (AUDIT ONLY, never shipped)")},
        "_unit": ("one DISTINCT fully-known killer roster (guild set + "
                  "weapon multiset) of 10+, one vote; pooled = every "
                  "winner at the size, styles = the party_styles.json "
                  "label; seat cells per exact size pool a +-1 then +-2 "
                  "window until >= _min_distinct rosters (`window`); copy "
                  "and distinct cells per band"),
        "_seat_read": ("Engine.seat_of: the weapon's primary seat "
                       "(role_menu[0]) — the one role read; a menu-less "
                       "weapon counts toward no seat"),
        "_typical": ("seats: round-half-up(p50) where p50 >= 1; copies: "
                     "free = round-half-up(p50) (>= 1), max = ceil(p90) "
                     "(>= free); a weapon under the floor has no row"),
        "_min_distinct": MIN_DISTINCT,
        "_style_min_size": STYLE_MIN_SIZE,
        "bands": {k: list(v) for k, v in BANDS.items()},
        "rosters": len(rosters),
        "seat_universe": list(universe),
        "plan_keys": list(PLAN_KEYS),
        "seats": seats,
        "plan": plan,
        "copies": copies,
        "distinct": distinct,
    }


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    for path, hint in ((ARTIFACT, "run sample_parties.py first"),
                       (STYLES_ARTIFACT, "run derive_party_styles.py first")):
        if not os.path.exists(path):
            sys.exit(f"no {os.path.relpath(path, HERE)} -- {hint}")
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    from engine import Engine  # noqa: E402
    e = Engine()
    doc = rosters_io.load(ARTIFACT)
    with open(STYLES_ARTIFACT, encoding="utf-8") as f:
        ps = json.load(f)
    if (ps.get("_source") or {}).get("party_rosters_sha256") != sha256_of(ARTIFACT):
        sys.exit("party_styles.json was derived from a different "
                 "party_rosters.json.gz -- rerun derive_party_styles.py")
    labels = {(r["battle"], r["index"]): r.get("style")
              for r in ps.get("parties") or [] if r.get("style")}
    standoff = e.pred_members[e.STANDOFF]
    out = derive(doc, labels, e.seat_of, set(e.weapons),
                 plan_of=lambda w: frozenset(["standoff"]) if w in standoff
                 else frozenset())
    out["_generated"] = datetime.date.today().isoformat()
    out["_source"]["party_rosters_sha256"] = sha256_of(ARTIFACT)
    out["_source"]["party_styles_sha256"] = sha256_of(STYLES_ARTIFACT)
    jsonfmt.dump(out, TARGET)
    print(f"  rosters      : {out['rosters']} distinct on the training split")
    typ = out["seats"]["typical"]
    for label, rows in [("pooled", typ["pooled"])] + sorted(typ["styles"].items()):
        for size in ("10", "15", "20"):
            row = rows.get(size)
            if row:
                print(f"  seats {label:<10} {size:>2}: "
                      + ", ".join(f"{s} {n}" for s, n in sorted(row.items())))
    for label, cells in [("pooled", out["copies"]["pooled"])] \
            + sorted(out["copies"]["styles"].items()):
        cell = cells.get("20") or {}
        stacked = sorted(((w, v) for w, v in cell.items() if v["free"] > 1),
                         key=lambda kv: -kv[1]["share2"])
        if stacked:
            print(f"  copies {label:<9} 20: "
                  + ", ".join(f"{w} free {v['free']} max {v['max']} "
                              f"({int(v['share2'] * 100)}% x2)"
                              for w, v in stacked[:6]))
    for label, cells in [("pooled", out["distinct"]["pooled"])] \
            + sorted(out["distinct"]["styles"].items()):
        d = cells.get("20")
        if d:
            print(f"  distinct {label:<8} 20: {d['p10']} / {d['p50']} / {d['p90']} "
                  f"(n {d['n']})")
    print(f"skeletons ({out['_split']['rule']}) -> {os.path.relpath(TARGET, HERE)}")


if __name__ == "__main__":
    main()
