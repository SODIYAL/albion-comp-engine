"""Role counts of the typical winner, GENERATED from the committed evidence.

Owner rulings 2026-09-11 (castle_outpost clap 7 kept forging two healers;
"go ahead", then "fix it up all for all party sizes and styles"): a body
beyond the TYPICAL count for its role is generated only when a minimum
only that role can meet still demands it. The composition bands
(templates/composition.yaml) carry min / max per role; this script
supplies the middle line the supply rows got on 2026-09-10 (standing
rule 17, applied to bodies): the harvest p50 at 10+, the median of the
fitted published comps below 10.

Three tables, resolved by the engine in this order (both ports,
`_role_typical`):

  size < 10   comps[content][size]   median role counts of the published
                                     comps the content's targets were fitted
                                     from (dressed_template_audit parties),
                                     where the content has >= MIN_COMPS at
                                     that size (the `stat: median` bar);
                                     healer / frontline / support
              else pooled[size]      HEALER ONLY. Killer parties below 10
                                     are open-world squads: style-labelled
                                     or not, their frontline p50 at 7 is 1
                                     (p90 2) where every published 7-man
                                     comp fields 2-3 and a support in one of
                                     three. Their healer count agrees (one in
                                     67% of 658 at 7; 3/3 comps). Tanks and
                                     supports there are NOT derived from the
                                     harvest.
  size >= 10  styles[style][size]    DECLARED style's cell (party_styles.json
                                     labels, MIN_SIZE 10); `balanced` never
                                     reads a cell (owner 2026-09-08, kits).
                                     A cell pools a +-1 then +-2 size window
                                     until it holds >= MIN_DISTINCT rosters
                                     (`window` stated); a style that never
                                     reaches it at that size has no cell.
              else pooled[size]      every winner at the size, any style;
                                     healer / frontline / support

dps is never gated: it is the residual role, and gating all four could
make a size infeasible (p50s do not sum to the size). A zero p50 writes
nothing ("most winners field none" is not a count). Sizes the harvest does
not reach (21+) carry no harvest row.

Fully-known parties only (known_weapons == size: a party with an unknown
slot cannot vote on a count); role per weapon = Engine.role_of (the one
role read). Reads committed files only; never the raw cache. Explicit step,
never part of a normal build. Rerun order after a harvest: sample_parties
-> audit_style_rosters -> derive_style_bands -> derive_party_styles ->
derive_meta_prior -> derive_role_counts -> build_dataset -> gates.
build_dataset.py refuses a role_counts.json whose recorded artifact hashes
do not match the artifacts on disk.

    py -3 pipeline/derive_role_counts.py
"""
import datetime
import glob
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rosters_io  # noqa: E402  (the gzipped killer-party artifact)
ARTIFACT = rosters_io.path(OUT)
STYLES_ARTIFACT = os.path.join(OUT, "party_styles.json")
AUDIT = os.path.join(OUT, "dressed_template_audit.json")
COMPS_DIR = os.path.join(ROOT, "data", "published_comps")
TARGET = os.path.join(OUT, "role_counts.json")
ROLES = ("healer", "frontline", "support", "dps")
GATED_ROLES = ("healer", "frontline", "support")   # dps is the residual
POOLED_SMALL_ROLES = ("healer",)                    # below 10, harvest heals only
MIN_DISTINCT = 40   # the style_bands convention: fewer rosters, no cell
MIN_COMPS = 3       # the content fit's `stat: median` bar
STYLE_MIN_SIZE = 10
MIN_SIZE = 2
WINDOWS = (0, 1, 2)

sys.path.insert(0, HERE)
import jsonfmt  # noqa: E402


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


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


def _typical(rows_by_role, roles):
    out = {}
    for r in roles:
        p50 = percentile(rows_by_role[r], 0.50)
        if p50 >= 1:
            out[r] = int(round(p50))
    return out


def _count_roles(weapons, role_of):
    counts = {r: 0 for r in ROLES}
    for w in weapons:
        counts[role_of(w)] = counts.get(role_of(w), 0) + 1
    return counts


def derive_harvest(doc, labels, role_of, known):
    """`labels` = {(battle, index): style} from party_styles.json."""
    pooled = {}
    styled = {}
    for p in doc.get("parties") or []:
        size = p.get("size") or 0
        if size < MIN_SIZE or (p.get("known_weapons") or 0) < size:
            continue
        ws = [w for w in (p.get("weapons") or []) if w in known]
        if len(ws) < size:
            continue
        counts = _count_roles(ws, role_of)
        rows = pooled.setdefault(size, {r: [] for r in ROLES})
        for r in ROLES:
            rows[r].append(counts[r])
        st = labels.get((p.get("battle"), p.get("index")))
        if st and size >= STYLE_MIN_SIZE:
            rows = styled.setdefault(st, {}).setdefault(size, {r: [] for r in ROLES})
            for r in ROLES:
                rows[r].append(counts[r])
    sizes, typ_pooled = {}, {}
    for size in sorted(pooled):
        rows = pooled[size]
        n = len(rows[ROLES[0]])
        cell = {"n": n}
        for r in ROLES:
            cell[r] = _stats(rows[r])
        sizes[str(size)] = cell
        if n < MIN_DISTINCT:
            continue
        roles = GATED_ROLES if size >= STYLE_MIN_SIZE else POOLED_SMALL_ROLES
        t = _typical(rows, roles)
        if t:
            typ_pooled[str(size)] = t
    style_cells, typ_styles = {}, {}
    for st in sorted(styled):
        per = styled[st]
        lo, hi = min(per), max(per)
        for size in range(lo, hi + 1):
            picked = None
            for w in WINDOWS:
                rows = {r: [] for r in ROLES}
                for s2 in range(size - w, size + w + 1):
                    for r in ROLES:
                        rows[r].extend((per.get(s2) or {}).get(r) or [])
                if len(rows[ROLES[0]]) >= MIN_DISTINCT:
                    picked = (w, rows)
                    break
            if picked is None:
                continue
            w, rows = picked
            n = len(rows[ROLES[0]])
            cell = {"n": n, "window": w}
            for r in ROLES:
                cell[r] = _stats(rows[r])
            style_cells.setdefault(st, {})[str(size)] = cell
            t = _typical(rows, GATED_ROLES)
            if t:
                typ_styles.setdefault(st, {})[str(size)] = t
    return sizes, style_cells, typ_pooled, typ_styles


def derive_comps(audit, comps, role_of, known):
    """Median role counts of the fitted published comps per content and
    size, where a content has >= MIN_COMPS comps at that size (below 10
    only: at 10+ the harvest rules, standing rule 17)."""
    by = {}
    seen = set()
    for p in audit.get("parties") or []:
        content, size, cid = p.get("content"), p.get("size"), p.get("comp")
        if not content or not size or size >= STYLE_MIN_SIZE:
            continue
        if (content, size, cid) in seen:
            continue
        seen.add((content, size, cid))
        doc = comps.get(cid)
        if not doc:
            continue
        slots = (doc.get("parties") or [{}])[0].get("slots") or []
        ws = [s["weapons"][0] for s in slots
              if s.get("weapons") and s.get("role") != "battlemount"
              and s["weapons"][0] in known]
        counts = _count_roles(ws, role_of)
        rows = by.setdefault(content, {}).setdefault(size, {r: [] for r in ROLES})
        for r in ROLES:
            rows[r].append(counts[r])
        rows.setdefault("_comps", []).append(cid)
    cells, typ = {}, {}
    for content in sorted(by):
        for size in sorted(by[content]):
            rows = by[content][size]
            n = len(rows[ROLES[0]])
            cell = {"n": n, "comps": sorted(rows["_comps"])}
            for r in ROLES:
                cell[r] = _stats(rows[r])
            cells.setdefault(content, {})[str(size)] = cell
            if n < MIN_COMPS:
                continue
            t = _typical(rows, GATED_ROLES)
            if t:
                typ.setdefault(content, {})[str(size)] = t
    return cells, typ


def derive(doc, labels, audit, comps, role_of, known):
    sizes, style_cells, typ_pooled, typ_styles = derive_harvest(
        doc, labels, role_of, known)
    comp_cells, typ_comps = derive_comps(audit, comps, role_of, known)
    return {
        "_source": {"party_rosters_sha256": None,
                    "party_styles_sha256": None,
                    "dressed_template_audit_sha256": None},
        "_unit": ("counts of each role (Engine.role_of) per party; harvest "
                  "rows = fully-known killer parties (known_weapons == "
                  "size), p10/p50/p90 per exact size (pooled) and per "
                  "declared style at 10+ (a cell pools a +-1 then +-2 size "
                  "window until >= _min_distinct rosters; `window` states "
                  "it); comps rows = the published comps the content's "
                  "targets were fitted from, below 10, >= _min_comps"),
        "_typical": ("round(p50) where p50 >= 1; harvest below 10: healer "
                     "only; harvest at 10+ and comps: healer / frontline / "
                     "support; dps never (the residual role). Resolution: "
                     "size < 10 -> comps[content][size] else pooled[size]; "
                     "size >= 10 -> styles[style][size] for a declared "
                     "identity style else pooled[size]"),
        "_min_distinct": MIN_DISTINCT,
        "_min_comps": MIN_COMPS,
        "_style_min_size": STYLE_MIN_SIZE,
        "sizes": sizes,
        "style_cells": style_cells,
        "comp_cells": comp_cells,
        "typical": {"pooled": typ_pooled, "styles": typ_styles,
                    "comps": typ_comps},
    }


def load_comps():
    import yaml
    comps = {}
    for p in sorted(glob.glob(os.path.join(COMPS_DIR, "*.yaml"))):
        with open(p, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if isinstance(doc, dict) and doc.get("kind") == "published_comp":
            comps[doc["id"]] = doc
    return comps


def main():
    for path, hint in ((ARTIFACT, "run sample_parties.py first"),
                       (STYLES_ARTIFACT, "run derive_party_styles.py first"),
                       (AUDIT, "run refit_content_targets.py / the dressed "
                               "audit first")):
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
    with open(AUDIT, encoding="utf-8") as f:
        audit = json.load(f)
    out = derive(doc, labels, audit, load_comps(), e.role_of, set(e.weapons))
    out["_generated"] = datetime.date.today().isoformat()
    out["_source"]["party_rosters_sha256"] = sha256_of(ARTIFACT)
    out["_source"]["party_styles_sha256"] = sha256_of(STYLES_ARTIFACT)
    out["_source"]["dressed_template_audit_sha256"] = sha256_of(AUDIT)
    jsonfmt.dump(out, TARGET)
    t = out["typical"]
    print("  pooled : " + ", ".join(
        f"{s}:" + "/".join(f"{r[0]}{v}" for r, v in row.items())
        for s, row in sorted(t["pooled"].items(), key=lambda kv: int(kv[0]))))
    for st, rows in sorted(t["styles"].items()):
        print(f"  {st:<9}: " + ", ".join(
            f"{s}:" + "/".join(f"{r[0]}{v}" for r, v in row.items())
            for s, row in sorted(rows.items(), key=lambda kv: int(kv[0]))))
    for content, rows in sorted(t["comps"].items()):
        print(f"  comps {content}: " + ", ".join(
            f"{s}:" + "/".join(f"{r[0]}{v}" for r, v in row.items())
            for s, row in sorted(rows.items(), key=lambda kv: int(kv[0]))))
    print(f"role counts -> {os.path.relpath(TARGET, HERE)}")


if __name__ == "__main__":
    main()
