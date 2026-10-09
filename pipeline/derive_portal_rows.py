#!/usr/bin/env python3
"""Dragon Portal rows from the portal harvest: templates/ancient_lands.yaml.

The content template judges a comp against rows of targets and soft caps.
The Dragon Portal rows were BORROWED from the Roads of Avalon template
until the kill-feed poll had filled the portal pools (the template's
`fit:` block said so and the page showed the notice). This step derives
them from the harvest under the standing convention every harvest row
follows (target is the median, soft cap 1.15 x p90, min the p10; person
units for scaling rows), and writes the template.

THE EVIDENCE UNIT for the small pools (the decision the BACKLOG carried):
a killer party inside the Ancient Lands (the kill-feed record's content
tag, set by the Ancient Bone marker) of the pool's size, every weapon
known and in the catalog, DOMINANT in its battle (no deaths, at least one
kill), on the TRAINING split (battle % 5 != 0; % 5 == 0 is the holdout
tests/tier2_blindtest.py v4h evaluates). The floor is 40 distinct
rosters per pool; a pool under it keeps the rows the other pools fit
(below 10) or the style x size rows (at 10+).

THE BASE ROWS are fitted on the 4-5 pool, the template's base size (5,
the size the scaling rows are stated at). The 2-3, 6-7 and 15-20 pools
carry ROWS OF THEIR OWN (`pool_rows`, read by both engine ports at a size
inside the pool, scaled from the pool's ref_size): a matchmade pool is a
population of its own, and what a trio fields is not three fifths of
what a five fields (a 4-5 threshold row read at 3 demanded twice the
engage and disengage trio winners carry). The 15-20 pool's rows outrank
the style x size rows inside the pool: measured at the floor, its
winners field a quarter more sustained damage and a third fewer ally
buffs than open-world winners of 20 (tests/VALIDATION.md). The supply is DRESSED in the
engine's own doctrine kits (gear_join.doctrine_gears), the unit the
style x size rows and the content re-fit use, measured on the dataset
the step runs against. A row whose median winner fields NONE is no
requirement at that pool: in the base rows it is a DEMAND RAMP (none
through 5 and the 6-7 median at 7 where that pool fields it, else none
through 7 and the former Roads value at 10, where the style x size rows
take over). In the rows of the 4-5, 6-7 and 15-20 pools (OPTIONAL_POOLS)
it is an OPTIONAL row where a minority of the pool's winners field it (the p90
winner does: `optional_row`, target and soft cap read over the parties
that field it, no minimum) and `none` below that. A `none` row pays a
weapon nothing for bringing the capability; at 4-5 that priced the
silence of the pool's most fielded frontline at zero (a fifth of
dominant fives field silence). The fitted pool reads the base rows and
carries only its optional rows under `pool_rows`. The 2-3 pool keeps
`none`: measured on the holdout, optional rows there took the hidden
weapon's top-3 from 11% to 8% (MRR 0.136 to 0.104), where at 4-5 and
6-7 the role read rises seven points and the weapon's reciprocal rank
holds or rises (0.142 to 0.143, 0.106 to 0.125). The
role counts of the same pools (derive_role_counts.py `pools`) keep
generation to the winners' shape. Never a number invented to fill a
hole.

THE FIELDED WEAPONS (`pool_fielded`, read by both engine ports as a
suggestion gate at a size inside the pool): per pool at the floor, the
weapons its dominant winners field. A weapon is listed when it stands in
at least MIN_FIELDED_ROSTERS distinct rosters across at least
MIN_FIELDED_ORGS distinct guild-sets (the honesty gate the pair prior and
the cohort families use) and in at least SIGNAL_OF_TOP of the rosters of
the pool's most fielded weapon (the meta prior's signal floor: below it a
weapon carries no signal). The capability score ranks a wide sheet first
whether or not any winner fields the weapon; the list keeps default comps
inside what the pool's winners bring. A gate on suggestions and
generation only: a manual pick always scores.

WEIGHTS are not fitted here: this step carries the template's weights
and its `weight_fit` block through unchanged (a weight changes by a
logged decision; pipeline/fit_choice_weights.py is the measurement, and
the portal's weights are fitted to the picks of the same population,
pulled toward the Roads weights it started from). Hard floors stay content
facts (weapon units) and are kept; the report prints the share of
winners fielding each role so a floor can be checked against it.

Explicit step, never part of a normal build (like the samplers): the
fold runs it after derive_style_bands, then build_dataset and the gates.
Reads the COMMITTED roster artifact (pipeline/out/party_rosters.json.gz;
`--rosters` names another file, for a run against a git-shown copy while
the poll rewrites the working file).

    py -3 pipeline/derive_portal_rows.py            # report only
    py -3 pipeline/derive_portal_rows.py --apply    # write the template
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
TEMPLATE = os.path.join(HERE, "templates", "ancient_lands.yaml")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
import rosters_io  # noqa: E402
import party_link  # noqa: E402
import gear_join  # noqa: E402
from engine import Engine  # noqa: E402

CONTENT = "ancient_lands"
HOLDOUT_MOD = 5
FLOOR = 40            # distinct rosters a pool needs to carry numbers
CAP_OVER_P90 = 1.15   # the standing soft-cap convention
POOLS = (("trio", 2, 3), ("five", 4, 5), ("seven", 6, 7), ("large", 15, 20))
FIT_POOL = "five"
RAMP_POOL = "seven"
OWN_POOLS = ("trio", "seven", "large")   # the pools that carry rows of their own (the base rows are the 4-5 pool's)
OPTIONAL_POOLS = ("five", "seven", "large")   # the pools whose minority-fielded capabilities carry an optional row
RAMP_TAKEOVER = 10    # where the style x size rows carry the targets
# The pools that carry a fielded list (at the floor). The 15-20 pool
# carries none until it holds LARGE_SHAPE_AT distinct rosters: a list of
# the weapons in five of 40 rosters would gate generation at 20 on thin
# evidence. At the threshold its fielded list and role counts of its own
# are due (maintainer decision; this step and the fold report say so).
FIELDED_POOLS = ("trio", "five", "seven")
LARGE_SHAPE_AT = 200
MIN_FIELDED_ROSTERS = 5   # distinct rosters (derive_meta_prior MIN_PAIR_PARTIES, the honesty gate)
MIN_FIELDED_ORGS = 3      # ...across this many distinct guild-sets (MIN_PAIR_ORGS)
SIGNAL_OF_TOP = 0.05      # share of the top weapon's rosters (derive_meta_prior MIN_PRIOR)


def load_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def in_split(battle, all_battles):
    if all_battles:
        return True
    try:
        return int(battle) % HOLDOUT_MOD != 0
    except (TypeError, ValueError):
        return False


def select_parties(doc, catalog, all_battles):
    """Dominant, fully-known portal killer parties by pool, training split."""
    by_battle = party_link.parties_by_battle(doc)
    stamps = {b.get("battle"): b.get("started_at") or b.get("first_event_at") for b in doc.get("battles") or []}
    pools = {name: [] for name, _lo, _hi in POOLS}
    for battle in sorted(by_battle):
        if not in_split(battle, all_battles):
            continue
        for p in by_battle[battle]:
            n = p.get("size") or 0
            ws = p.get("weapons") or []
            if p.get("known_weapons") != n or len(ws) != n or any(w not in catalog for w in ws):
                continue
            if not ((p.get("deaths") or 0) == 0 and (p.get("kills") or 0) > 0):
                continue
            for name, lo, hi in POOLS:
                if lo <= n <= hi:
                    pools[name].append({"battle": battle, "size": n, "weapons": list(ws),
                                        "guilds": tuple(sorted(p.get("guilds") or [])),
                                        "at": stamps.get(battle)})
    return pools


def fielded(parties):
    """The weapons a pool's dominant winners field: distinct rosters and
    distinct guild-sets per weapon, kept at the honesty gate and the
    signal floor (module docstring). Returns (sorted keys, the top
    weapon's roster count, {weapon: rosters})."""
    rosters = collections.defaultdict(set)
    orgs = collections.defaultdict(set)
    for p in parties:
        key = tuple(sorted(p["weapons"]))
        for w in set(p["weapons"]):
            rosters[w].add(key)
            orgs[w].add(p.get("guilds") or ())
    if not rosters:
        return [], 0, {}
    top = max(len(v) for v in rosters.values())
    keep = sorted(w for w, v in rosters.items()
                  if len(v) >= MIN_FIELDED_ROSTERS and len(v) >= SIGNAL_OF_TOP * top
                  and len(orgs[w]) >= MIN_FIELDED_ORGS)
    return keep, top, {w: len(v) for w, v in rosters.items()}


def measure(parties, engines, reqs, base):
    """Per capability: dressed and weapon-only supply of every party in the
    row's units (person units at `base` for scaling rows), plus the role
    shares. `base` is the size the rows are stated at: the template's
    base size for the base rows, the pool's ref_size for its own rows."""
    dressed = collections.defaultdict(list)
    naked = collections.defaultdict(list)
    roles = collections.Counter()
    with_role = collections.Counter()
    for p in parties:
        e = engines(p["size"])
        ws = p["weapons"]
        s_wo = e.effective_supply(ws)
        s_dr = e.effective_supply(ws, gears=gear_join.doctrine_gears(e, ws))
        for cap, row in reqs.items():
            k = base / p["size"] if row.get("scales") else 1.0
            naked[cap].append(s_wo.get(cap, 0.0) * k)
            dressed[cap].append(s_dr.get(cap, 0.0) * k)
        rc = collections.Counter(e.role_of(w) for w in ws)
        for r, k in rc.items():
            roles[r] += k
            with_role[r] += 1
    return {"dressed": dressed, "naked": naked, "roles": roles, "with_role": with_role, "n": len(parties)}


def stats(values):
    return {"p10": pct(values, .1), "p50": pct(values, .5), "p90": pct(values, .9),
            "share": (sum(v > 0 for v in values) / len(values)) if values else 0.0}


def fit_rows(reqs, base, m_fit, m_ramp, ramp_ok):
    """The new requirement rows and, per row, how it was fitted."""
    rows, how = {}, {}
    for cap, old in reqs.items():
        s5 = stats(m_fit["dressed"][cap])
        keep = {k: v for k, v in old.items() if k in ("weight", "optional")}
        if s5["p50"] > 0:
            soft = max(s5["p50"], CAP_OVER_P90 * s5["p90"])
            rows[cap] = dict(keep, min=round(s5["p10"], 2), target=round(s5["p50"], 2),
                             soft_cap=round(soft, 2), scales=bool(old.get("scales")))
            how[cap] = "fitted"
            continue
        s7 = stats(m_ramp["dressed"][cap]) if ramp_ok else None
        if s7 and s7["p50"] > 0:
            mult = 7 / base if old.get("scales") else 1.0      # absolute at full_at
            soft = max(s7["p50"], CAP_OVER_P90 * s7["p90"]) * mult
            rows[cap] = dict(keep, min=round(s7["p10"] * mult, 2), target=round(s7["p50"] * mult, 2),
                             soft_cap=round(soft, 2), ramp={"none_until": 5, "full_at": 7}, scales=False)
            how[cap] = "ramp 5-7"
            continue
        mult = RAMP_TAKEOVER / base if old.get("scales") else 1.0
        rows[cap] = dict(keep, min=round(old.get("min", old["target"]) * mult, 2),
                         target=round(old["target"] * mult, 2), soft_cap=round(old["soft_cap"] * mult, 2),
                         ramp={"none_until": 7, "full_at": RAMP_TAKEOVER}, scales=False)
        how[cap] = "ramp 7-10 (former row at 10)"
    return rows, how


def optional_row(values, old):
    """The row of a capability a MINORITY of a pool's winners field, or None.

    The median winner fields none, so the capability is no requirement;
    but where the p90 winner fields it (at least one winning party in
    ten) it is a real choice the pool's winners make, and the weapons
    that bring it earn nothing for it under a `none` row (the 4-5 pool:
    a fifth of dominant fives field silence, and the pool's most fielded
    frontline is the one that brings it). Such a capability carries an
    OPTIONAL row read over the parties that field it: the target is their
    median (what a comp that brings it brings), the soft cap the standing
    1.15 x their p90, and no minimum. Optional is the engine's own rule
    (Engine.optional): bringing it earns its coverage, not bringing it
    is not a hole."""
    st = stats(values)
    if st["p50"] > 0 or st["p90"] <= 0:
        return None
    fielders = [v for v in values if v > 0]
    return {"min": 0.0, "target": round(pct(fielders, .5), 2),
            "soft_cap": round(CAP_OVER_P90 * pct(fielders, .9), 2),
            "scales": bool(old.get("scales")), "optional": True}


def pool_rows(reqs, m, optional=True):
    """A pool's own rows: the median where the median winner fields the
    capability; an optional row where only a minority does (optional_row,
    in the pools of OPTIONAL_POOLS); `none` otherwise. Scales as the base
    row says."""
    rows = {}
    for cap, old in reqs.items():
        st = stats(m["dressed"][cap])
        if st["p50"] > 0:
            rows[cap] = {"min": round(st["p10"], 2), "target": round(st["p50"], 2),
                         "soft_cap": round(CAP_OVER_P90 * st["p90"], 2), "scales": bool(old.get("scales"))}
        else:
            rows[cap] = (optional_row(m["dressed"][cap], old) if optional else None) or {"none": True}
    return rows


def fit_pool_optional(reqs, how, m):
    """The fitted pool's optional rows: the capabilities its base row
    ramps in from none (the median winner of the pool fields none) and a
    minority of its winners field. They sit under `pool_rows` for the
    fitted pool, where a base ramp gives way; every other capability of
    the pool reads its base row."""
    rows = {}
    for cap, old in reqs.items():
        if how.get(cap, "").startswith("ramp"):
            row = optional_row(m["dressed"][cap], old)
            if row:
                rows[cap] = row
    return rows


def fmt_pool_row(cap, row):
    if row.get("none"):
        return f"      {cap + ':':<20}{{none: true}}"
    return (f"      {cap + ':':<20}{{min: {row['min']:g}, target: {row['target']:g}, "
            f"soft_cap: {row['soft_cap']:g}, scales: {'true' if row['scales'] else 'false'}"
            f"{', optional: true' if row.get('optional') else ''}}}")


def fmt_row(cap, row):
    parts = []
    for k in ("min", "target", "weight", "soft_cap"):
        v = row[k]
        parts.append(f"{k}: {v:g}" if isinstance(v, float) else f"{k}: {v}")
    if row.get("ramp"):
        parts.append("ramp: {none_until: %d, full_at: %d}" % (row["ramp"]["none_until"], row["ramp"]["full_at"]))
    parts.append("scales: %s" % ("true" if row.get("scales") else "false"))
    if row.get("optional"):
        parts.append("optional: true")
    return f"  {cap + ':':<20}{{{', '.join(parts)}}}"


HEADER = """# Content template — Dragon Portal (the Ancient Lands).
#
# The Ancient Lands are reached through open-world portals and fought in
# matchmaking pools: solo, 2-3, 4-5, 5-7 and 15-20 players, each pool
# matched against groups of the same pool. Partial-loot instances open
# from yellow zones, full-loot instances from red and black zones; both
# are one content here, the loot type is recorded per party where the
# harvest can see it. A 1200 item-power soft cap applies. Knockdowns go
# through a bleedout state with revives before a death registers, so kill
# counts undercount fights that ended in revives.
#
# EVIDENCE: the requirement rows and the pool rows are GENERATED by
# pipeline/derive_portal_rows.py from the portal harvest (the kill-feed
# poll's records tagged with this content, pipeline/out/
# party_rosters.json.gz) and are never edited by hand. The unit is the
# dominant killer party of the pool's size (no deaths, a kill, every
# weapon known) on the training split. The base rows are fitted on the
# 4-5 pool, the template's base size; the 2-3, 6-7 and 15-20 pools carry
# rows of their own under `pool_rows`, read by both engine ports at a size
# inside the pool and scaled from the pool's ref_size (inside the 15-20
# pool they outrank the style x size rows). Target is the median,
# soft cap 1.15 x p90, min the p10, of the supply dressed in the engine's
# doctrine kits. A row the median winner does not field is no requirement:
# in the base rows a DEMAND RAMP (none through 5 and the 6-7 median at 7
# where that pool fields it, else none through 7 and the former Roads
# value at 10, where the style x size rows carry the targets); in the
# rows of the 4-5, 6-7 and 15-20 pools an OPTIONAL row where the p90 winner
# fields it (at least one winning party in ten: over the parties fielding
# it, target their median and soft cap 1.15 x their p90, no minimum;
# bringing it earns its coverage, not bringing it is not a hole) and
# `none` below that; in the 2-3 pool `none` (optional rows there cost the
# holdout read of the hidden weapon three points). The fitted 4-5 pool
# reads the base rows and carries its optional rows alone under
# `pool_rows`. The `fit:` block records the pools, the floor and the window.
# Weights apply at every pool and are fitted to what the same winners
# pick (`weight_fit`, pipeline/fit_choice_weights.py: a conditional logit
# pulled toward the Roads weights the template started from, every
# curated weight of 4 or more keeping at least half); a weight changes by
# a logged decision, never in this step.
#
# `pool_fielded` lists, per pool at the floor, the weapons its dominant
# winners field (at least 5 distinct rosters across 3 guild-sets and 5%
# of the rosters of the pool's most fielded weapon). Both engine ports
# read it as a suggestion gate at a size inside the pool: a weapon
# outside the list is never suggested or generated there, and always
# scores when picked by hand.
#
# validated_sizes is EMPTY: no blind validation round has covered a pool
# yet, so the page flags every size as extrapolated. size_prompt lists
# the pools the page asks for before it forges.

"""

FOOTER = """
# Floors arm by size, as on roads: a trio without a healer is a gap to
# know about, a 6-7 without one is broken. The share of dominant winners
# fielding the role per pool, from the derive step's run (healer: %(h3)s
# at 2-3, %(h5)s at 4-5, %(h7)s at 6-7; frontline: %(f3)s, %(f5)s, %(f7)s)
# is the evidence the floors stand on.
hard_floors:
  heal_sustain: {min_party_size: 5, floor_units: 1.7, penalty_mult: 2.0}
  tankiness:    {min_party_size: 6, floor_units: 1.7, penalty_mult: 1.0}
"""


def render(tpl, rows, fit, shares, pools_out, fielded_out):
    lines = [HEADER.rstrip("\n"), "",
             f"content: {tpl['content']}", f"name: {tpl['name']}", f"base_size: {tpl['base_size']}",
             "validated_sizes: []", f"max_size: {tpl['max_size']}", "size_prompt:"]
    sp = tpl["size_prompt"]
    lines.append(f"  question: \"{sp['question']}\"")
    lines.append("  sizes: [%s]" % ", ".join(str(s) for s in sp["sizes"]))
    lines.append("  labels: {%s}" % ", ".join(f"{k}: \"{v}\"" for k, v in sp["labels"].items()))
    lines.append("fit: " + json.dumps(fit, separators=(", ", ": ")))
    lines.append("# Small-scale kill pressure keeps full single-target value at every size")
    lines.append("# (the roads rule: composition.yaml st_value_mult would tax it at 6-7). The")
    lines.append("# generation-fit gate reads the same flag: a single-scale carry's")
    lines.append("# situational verdict at 4-9 earns a default slot in this content.")
    lines.append("st_full_value: true")
    lines.append("")
    lines.append("requirements:")
    for cap, row in rows.items():
        lines.append(fmt_row(cap, row))
    if tpl.get("weight_fit"):
        lines.append("weight_fit: " + json.dumps(tpl["weight_fit"], separators=(", ", ": ")))
    if pools_out:
        lines.append("")
        lines.append("# The pools' own rows: fitted on the pool's dominant winners (ref_size is")
        lines.append("# the size the rows are stated at, comps its distinct rosters). An `optional`")
        lines.append("# row: a minority of the pool's winners field it; a `none` row: under one in")
        lines.append("# ten does, no requirement at this pool. Weights are the base rows'.")
        lines.append("pool_rows:")
        for key, pool in pools_out.items():
            lines.append(f"  \"{key}\":")
            lines.append("    sizes: [%d, %d]" % tuple(pool["sizes"]))
            lines.append(f"    ref_size: {pool['ref_size']}")
            lines.append(f"    comps: {pool['comps']}")
            lines.append("    requirements:")
            for cap, row in pool["requirements"].items():
                lines.append(fmt_pool_row(cap, row))
    if fielded_out:
        lines.append("")
        lines.append("# The weapons each pool's dominant winners field (`rosters`: the pool's")
        lines.append("# distinct rosters). The suggestion gate at a size inside the pool.")
        lines.append("pool_fielded:")
        for key, pool in fielded_out.items():
            lines.append(f"  \"{key}\":")
            lines.append("    sizes: [%d, %d]" % tuple(pool["sizes"]))
            lines.append(f"    rosters: {pool['rosters']}")
            lines.append("    weapons:")
            for w in pool["weapons"]:
                lines.append(f"      - {w}")
    lines.append((FOOTER % shares).rstrip("\n"))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rosters", default=None, help="the roster artifact (default: pipeline/out/party_rosters.json.gz)")
    ap.add_argument("--all-battles", action="store_true", help="AUDIT ONLY: ignore the training split")
    ap.add_argument("--apply", action="store_true", help="write templates/ancient_lands.yaml")
    args = ap.parse_args()

    tpl = load_yaml(TEMPLATE)
    reqs = tpl["requirements"]
    base = tpl["base_size"]
    path = args.rosters or rosters_io.path(OUT)
    doc = rosters_io.load(path, source="all", content=CONTENT)
    engines_cache = {}

    def engines(size):
        e = engines_cache.get(size)
        if e is None:
            e = engines_cache[size] = Engine(content=CONTENT, size=size, style="balanced")
        return e

    catalog = set(engines(base).weapons)
    pools = select_parties(doc, catalog, args.all_battles)
    measured, distinct, own = {}, {}, {}
    for name, lo, hi in POOLS:
        ps = pools[name]
        distinct[name] = len({tuple(sorted(p["weapons"])) for p in ps})
        measured[name] = measure(ps, engines, reqs, base) if ps else None
        # a pool's own rows are stated at its top size
        own[name] = measure(ps, engines, reqs, hi) if ps and name in OWN_POOLS else None
        m = measured[name]
        roles = ""
        if m:
            roles = ", ".join(f"{r} {m['with_role'][r] / m['n']:.0%}" for r in ("healer", "frontline", "support"))
        print(f"{name:<6} parties {len(ps):>5}  distinct rosters {distinct[name]:>5}  with a {roles}")
    print(("DUE: the 15-20 pool's fielded list and role counts (BACKLOG): " if distinct["large"] >= LARGE_SHAPE_AT
           else "the 15-20 pool's fielded list and role counts wait for ")
          + f"{LARGE_SHAPE_AT} distinct rosters; it holds {distinct['large']}")
    if distinct[FIT_POOL] < FLOOR:
        sys.exit(f"the {FIT_POOL} pool holds {distinct[FIT_POOL]} distinct rosters, under the floor of {FLOOR}: nothing to fit")
    ramp_ok = distinct[RAMP_POOL] >= FLOOR
    rows, how = fit_rows(reqs, base, measured[FIT_POOL], measured[RAMP_POOL], ramp_ok)

    print(f"\n{'capability':<20}{'w':>3} {'old target':>11}{'old cap':>9} -> {'min':>7}{'target':>8}{'cap':>8}  {'4-5 p50/p90/share (dressed)':<30} {'how'}")
    m5 = measured[FIT_POOL]
    for cap, row in rows.items():
        old = reqs[cap]
        s5 = stats(m5["dressed"][cap])
        print(f"{cap:<20}{row['weight']:>3} {old['target']:>11.2f}{old['soft_cap']:>9.2f} -> {row['min']:>7.2f}{row['target']:>8.2f}{row['soft_cap']:>8.2f}  "
              f"{s5['p50']:>6.2f}/{s5['p90']:>6.2f}/{s5['share']:>4.0%}{'':<13} {how[cap]}")

    pools_out = {}
    for name, lo, hi in POOLS:
        if name in OWN_POOLS and distinct[name] >= FLOOR:
            pools_out[f"{lo}-{hi}"] = {"sizes": [lo, hi], "ref_size": hi, "comps": distinct[name],
                                       "requirements": pool_rows(reqs, own[name], name in OPTIONAL_POOLS)}
        elif name == FIT_POOL:
            # the fitted pool reads the base rows; only its optional rows
            # (the minority-fielded capabilities) sit here, at the base size
            opt = fit_pool_optional(reqs, how, measured[name])
            if opt:
                pools_out[f"{lo}-{hi}"] = {"sizes": [lo, hi], "ref_size": base, "comps": distinct[name],
                                           "requirements": opt}
    for key, pool in pools_out.items():
        none = sorted(c for c, r in pool["requirements"].items() if r.get("none"))
        opt = sorted(c for c, r in pool["requirements"].items() if r.get("optional"))
        print(f"\npool rows {key} (ref {pool['ref_size']}, {pool['comps']} distinct rosters): "
              f"{len(pool['requirements']) - len(none)} rows, none: {', '.join(none) or '-'}; "
              f"optional: " + (", ".join(f"{c} {pool['requirements'][c]['target']:g}" for c in opt) or "-"))
    role_of = engines(base).role_of
    names = engines(base).weapons
    fielded_out = {}
    for name, lo, hi in POOLS:
        if name in FIELDED_POOLS and distinct[name] >= FLOOR:
            keep, top, counts = fielded(pools[name])
            fielded_out[f"{lo}-{hi}"] = {"sizes": [lo, hi], "rosters": distinct[name], "weapons": keep}
            by_role = collections.Counter(role_of(w) for w in keep)
            cut = sorted((w for w in counts if w not in keep), key=lambda w: -counts[w])
            print(f"\nfielded {lo}-{hi}: {len(keep)} of {len(counts)} weapons seen "
                  f"(top weapon in {top} rosters, signal floor {SIGNAL_OF_TOP * top:.1f}); "
                  + ", ".join(f"{r} {by_role[r]}" for r in ("healer", "frontline", "support", "dps"))
                  + "; nearest cut: " + ", ".join(f"{names[w]['display_name']} {counts[w]}" for w in cut[:5]))
    stamps = sorted(p["at"] for name in pools for p in pools[name] if p.get("at"))
    fit = {
        "comps": distinct[FIT_POOL], "stat": "median", "source": "harvest",
        "unit": "dominant killer party in the Ancient Lands, every weapon known, training split",
        "fitted_pool": "4-5", "dressed": "doctrine", "floor": FLOOR,
        "fielded": {"min_rosters": MIN_FIELDED_ROSTERS, "min_guild_sets": MIN_FIELDED_ORGS,
                    "share_of_top": SIGNAL_OF_TOP},
        "pools": {name: {"parties": len(pools[name]), "distinct": distinct[name]} for name, _lo, _hi in POOLS},
        "split": "battle % 5 != 0" if not args.all_battles else "all battles (audit only)",
        "window": {"first": stamps[0][:16] if stamps else None, "last": stamps[-1][:16] if stamps else None},
    }
    def share(name, role):
        m = measured.get(name)
        return f"{m['with_role'][role] / m['n']:.0%}" if m else "n/a"
    shares = {"h3": share("trio", "healer"), "h5": share("five", "healer"), "h7": share("seven", "healer"),
              "f3": share("trio", "frontline"), "f5": share("five", "frontline"), "f7": share("seven", "frontline")}
    text = render(tpl, rows, fit, shares, pools_out, fielded_out)
    if args.all_battles:
        print("\n--all-battles is audit only: the template is never written from it")
        return
    if args.apply:
        with open(TEMPLATE, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"\nwrote {os.path.relpath(TEMPLATE, ROOT)} ({sum(1 for h in how.values() if h == 'fitted')} fitted rows, "
              f"{sum(1 for h in how.values() if h.startswith('ramp'))} ramp rows, pools of their own: {', '.join(pools_out) or 'none'}, fielded lists: {', '.join(fielded_out) or 'none'})")
    else:
        print("\nreport only; --apply writes the template")


if __name__ == "__main__":
    main()
