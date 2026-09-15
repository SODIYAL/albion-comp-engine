#!/usr/bin/env python3
"""Seat skeletons and copy allowances (owner ruling 2026-09-15, "full
autonomy" on the skeleton-first assessment; spec
notes/specs/2026-09-15-skeleton-first-generation-design.md).

  S1  derive_skeletons.derive on a synthetic harvest: the training split
      is honoured, duplicate rosters vote once, seat typicals are the
      rounded median, copy allowances follow free = round(p50) and
      max = ceil(p90), thin weapons carry no row
  S2  out/skeletons.json contracts: hash chain to the artifacts on disk,
      derived on the training split, every seat a roles.yaml id, every
      typical a positive integer, every copy row's free <= max with the
      evidence floor honoured, the dataset carries exactly these rows
  S3  engine resolution: a declared identity style reads its cell at 10+,
      balanced the pooled row, below 10 nothing; the copy cell is the
      pooled band row under the style row; a size no band covers keeps
      the composition defaults
  S4  forge contracts: no generated seat exceeds its typical unless a
      minimum only its role can meet demanded it or every seat of the
      role the pool supplies already stood at typical (spill); spill
      still fills a role whose typed seats sum below its minimum; every
      identity style and balanced forge a full, feasible roster at
      10 / 12 / 15 / 17 / 20; without a cell the seat gate is off
  S5  build_dataset refuses a hand-set duplication.per_weapon

Script-style: exit 0 = pass.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from engine import Engine  # noqa: E402
import derive_skeletons as ds  # noqa: E402
import rosters_io  # noqa: E402

OUT = os.path.join(ROOT, "pipeline", "out")
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def sha256_of(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ S1
def t_synthetic():
    seat = {"H": "main_healer", "T": "engage_tank", "S": "stopper_tank",
            "D": "ranged_aoe", "X": None}
    known = set(seat)
    parties = []
    # 60 distinct rosters of 10 on the training split: 2 H, 2 T, 6 D in
    # 40 of them, 3 H, 1 T, 1 S, 5 D in the other 20 -> main_healer p50 2
    for i in range(60):
        battle = 1000 + i * 3 + 1          # never % 5 == 0? make explicit below
        if battle % 5 == 0:
            battle += 1
        ws = (["H", "H", "T", "T"] + ["D"] * 6) if i < 40 else \
             (["H", "H", "H", "T", "S"] + ["D"] * 5)
        parties.append({"battle": battle, "index": 0, "size": 10,
                        "known_weapons": 10, "guilds": [f"g{i}"],
                        "weapons": ws})
    # a duplicate roster (same guild set + weapons) must vote once
    parties.append(dict(parties[0], battle=parties[0]["battle"] + 5 * 7))
    # a holdout-slice roster must never vote
    parties.append({"battle": 5000, "index": 0, "size": 10, "known_weapons": 10,
                    "guilds": ["hold"], "weapons": ["H"] * 10})
    # an unknown-slot roster must never vote
    parties.append({"battle": 1001, "index": 1, "size": 10, "known_weapons": 9,
                    "guilds": ["thin"], "weapons": ["H"] * 9})
    labels = {(p["battle"], p["index"]): "brawl" for p in parties}
    out = ds.derive({"parties": parties}, labels, lambda w: seat[w], known)
    check("S1a the training split and distinct-roster rules are honoured "
          "(60 rosters vote: the duplicate, the holdout and the unknown-slot "
          "rosters do not)", out["rosters"] == 60, f"rosters={out['rosters']}")
    typ = out["seats"]["typical"]["pooled"].get("10") or {}
    check("S1b seat typical = round-half-up(p50): main_healer 2, engage_tank 2, "
          "ranged_aoe 6; stopper_tank (p50 0) writes nothing",
          typ == {"main_healer": 2, "engage_tank": 2, "ranged_aoe": 6}, str(typ))
    st = out["seats"]["typical"]["styles"].get("brawl", {}).get("10")
    check("S1c the declared style's cell carries the same rows", st == typ, str(st))
    cp = out["copies"]["pooled"]["10-14"]
    h, d, t = cp.get("H"), cp.get("D"), cp.get("T")
    check("S1d copies: H p50 2 -> free 2, p90 3 -> max 3; D free 6 max 6; "
          "T p50 2 (40 of 60 field two) -> free 2, p90 2 -> max 2",
          h and (h["free"], h["max"]) == (2, 3) and d and (d["free"], d["max"]) == (6, 6)
          and t and (t["free"], t["max"]) == (2, 2), f"H={h} D={d} T={t}")
    check("S1e a weapon under the evidence floor has no row (S in 20 rosters)",
          "S" not in cp, str(sorted(cp)))
    check("S1f the split is recorded", out["_split"]["holdout_mod"] == 5
          and "training split" in out["_split"]["rule"])
    out_all = ds.derive({"parties": parties}, labels, lambda w: seat[w], known,
                        holdout_mod=None)
    check("S1g --all-battles is an audit copy: it votes the holdout roster too",
          out_all["rosters"] == 61 and not out_all["_split"]["holdout_mod"],
          f"rosters={out_all['rosters']}")


# ------------------------------------------------------------------ S2
def t_artifact():
    path = os.path.join(OUT, "skeletons.json")
    check("S2a out/skeletons.json exists", os.path.exists(path))
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    src = doc.get("_source") or {}
    check("S2b hash chain: derived from the party_rosters.json.gz and "
          "party_styles.json on disk",
          src.get("party_rosters_sha256") == sha256_of(rosters_io.path(OUT))
          and src.get("party_styles_sha256") == sha256_of(os.path.join(OUT, "party_styles.json")))
    check("S2c derived on the training split", (doc.get("_split") or {}).get("holdout_mod") == 5)
    import yaml
    with open(os.path.join(ROOT, "pipeline", "roles.yaml"), encoding="utf-8") as f:
        ids = {r["id"] for r in yaml.safe_load(f)["roles"]}
    e = Engine()
    universe = {s for s in (e.seat_of(w) for w in e.weapons) if s}
    check("S2d the seat universe is the catalogue's primary seats, all "
          "roles.yaml ids", set(doc["seat_universe"]) == universe and universe <= ids,
          str(sorted(set(doc["seat_universe"]) ^ universe)))
    typ = doc["seats"]["typical"]
    bad = []
    for label, table in [("pooled", typ["pooled"])] + list(typ["styles"].items()):
        for size, row in table.items():
            if not (size.isdigit() and int(size) >= 10):
                bad.append((label, size))
            for s, n in row.items():
                if s not in universe or type(n) is not int or n < 1:
                    bad.append((label, size, s, n))
    check("S2e every typical row sits at 10+ and is a positive integer per known seat",
          not bad, str(bad[:5]))
    bad = []
    n_rows = 0
    for label, table in [("pooled", doc["copies"]["pooled"])] + list(doc["copies"]["styles"].items()):
        for band, rows in table.items():
            for w, v in rows.items():
                n_rows += 1
                p50, p90 = v["p50"], v["p90"]
                free_ok = v["free"] == max(1, int(p50 + 0.5))
                max_ok = v["max"] == max(v["free"], int(math.ceil(p90 - 1e-9)))
                if not (w in e.weapons and v["n"] >= doc["_min_distinct"] and free_ok and max_ok
                        and 1 <= v["free"] <= v["max"]):
                    bad.append((label, band, w, v))
    check("S2f every copy row: a catalogue weapon, >= 40 rosters, free = round(p50), "
          f"max = ceil(p90), 1 <= free <= max ({n_rows} rows)", not bad and n_rows > 0,
          str(bad[:3]))
    with open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8") as f:
        comp = json.load(f)["composition"]
    sk = comp.get("skeleton") or {}
    cells = (comp.get("duplication") or {}).get("per_weapon_cells") or {}
    check("S2g the dataset carries exactly the artifact's typical rows and copy "
          "allowances, and no hand per_weapon list",
          sk.get("seats") == typ and not (comp.get("duplication") or {}).get("per_weapon")
          and all(cells["pooled"][b] == {w: {"free": v["free"], "max": v["max"]}
                                        for w, v in rows.items()}
                  for b, rows in doc["copies"]["pooled"].items()))
    return doc


# ------------------------------------------------------------------ S3
def t_resolution(doc):
    if not doc:
        return
    typ = doc["seats"]["typical"]
    ek = Engine(content="blackzone_roam", size=20, style="kite")
    row = (typ["styles"].get("kite") or {}).get("20") or typ["pooled"].get("20")
    check("S3a kite 20 reads the kite cell (the pooled row only when kite has none)",
          ek._seat_typ == row, f"{ek._seat_typ} vs {row}")
    eb = Engine(content="blackzone_roam", size=20, style="balanced")
    check("S3b balanced 20 reads the pooled row", eb._seat_typ == typ["pooled"].get("20", {}))
    e7 = Engine(content="castle_outpost", size=7, style="clap")
    check("S3c below 10 no seat row (killer parties under 10 are squads)", e7._seat_typ == {})
    e25 = Engine(content="castle", size=25, style="clap")
    check("S3d a size the harvest does not reach carries no row (unknown stays explicit)",
          e25._seat_typ == ((typ["styles"].get("clap") or {}).get("25") or typ["pooled"].get("25") or {}))
    # copy cell: pooled 20 under the kite 20 row
    pooled = doc["copies"]["pooled"].get("20") or {}
    kite = (doc["copies"]["styles"].get("kite") or {}).get("20") or {}
    ok = True
    for w in set(pooled) | set(kite):
        want = (kite.get(w) or pooled.get(w))
        if ek._dup_free(w) != want["free"] or ek._dup_gen_max(w) != want["max"]:
            ok = False
            break
    check("S3e kite 20: the style row lays over the pooled row for copies "
          f"({len(pooled)} pooled, {len(kite)} kite rows)", ok and pooled)
    h = "MAIN_HOLYSTAFF_AVALON"
    unrowed = sorted(w for w in ek.weapons if w not in pooled and w not in kite)
    perma = "2H_ICECRYSTAL_UNDEAD"
    perma_row = kite.get(perma) or pooled.get(perma) or {"free": 1, "max": 1}
    check("S3f a weapon in no row keeps the defaults (free 1, max 1 at 20); "
          "Permafrost's free second copy stays gone (owner 2026-09-15, now the "
          "harvest's p50 of one copy); Hallowfall keeps its harvest allowance",
          unrowed and all(ek._dup_free(w) == 1 and ek._dup_gen_max(w) == 1
                          for w in unrowed[:10])
          and ek._dup_free(perma) == 1 == perma_row["free"]
          and ek._dup_gen_max(perma) == perma_row["max"]
          and ek._dup_free(h) >= 2,
          f"unrowed {len(unrowed)} perma {perma_row} hallow free {ek._dup_free(h)}")
    e7b = Engine(content="roads", size=7)
    check("S3g below per_weapon_min_size the defaults rule regardless of cells",
          e7b._dup_free(h) == 1 and e7b._dup_gen_max(h) == 1)


# ------------------------------------------------------------------ S4
def _seat_audit(e, party, ctx):
    """Every generated seat over its typical: was spill or a minimum the
    reason? A seat past its typical while a seat of the same role still
    stands under its typical is legal only for bodies that satisfy a
    predicate minimum none of those under-typical seats could meet (the
    engine's exception, evaluated here on the final roster: at least
    n - typical of the seat's members must be such satisfiers). Returns
    the violations."""
    counts = {}
    for w in party:
        s = e.seat_of(w)
        if s:
            counts[s] = counts.get(s, 0) + 1
    bad = []
    for s, n in counts.items():
        t = ctx["seat_typ"].get(s, 0)
        if n <= t:
            continue
        members = [w for w in party if e.seat_of(w) == s]
        r = e.role_of(members[0])
        under = [s2 for s2 in ctx["role_seats"].get(r, ())
                 if counts.get(s2, 0) < ctx["seat_typ"].get(s2, 0)]
        if not under:
            continue                      # spill
        excused = 0
        for w in members:
            for pn in ctx["pred_min"]:
                sats = ctx["pred_sat"].get(pn) or frozenset()
                seats = ctx["pred_seats"].get(pn) or frozenset()
                if w in sats and not any(s2 in seats for s2 in under):
                    excused += 1
                    break
        if excused < n - t:
            bad.append((s, n, t, under, excused))
    return bad


def t_gate_units():
    """The seat branch of _typ_ok on hand-built states."""
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    ctx = e._forge_ctx(e.suggest_pool())
    gh, hf, blight = "2H_HOLYSTAFF", "MAIN_HOLYSTAFF_AVALON", "2H_NATURESTAFF_HELL"
    check("S4f fixture: Great Holy sits the brawl-healer seat, Hallowfall and "
          "Blight the main-healer seat, all three full healers",
          e.seat_of(gh) == "brawl_healer" and e.seat_of(hf) == "main_healer"
          and e.seat_of(blight) == "main_healer"
          and all(w in e.pred_members[e.PRIMARY_HEAL] for w in (gh, hf, blight)))
    ph = e.PRIMARY_HEAL
    contrib_gh = e._pred_possible(gh) | (e._profile_members.get(gh) or frozenset())
    contrib_hf = e._pred_possible(hf) | (e._profile_members.get(hf) or frozenset())
    # an empty healer line: primary_heal unmet, main-healer seat open
    roles, preds = {}, {}
    check("S4g Great Holy (brawl-healer seat, typical 0) may NOT cover an open "
          "primary_heal minimum while the main-healer seat stands under its "
          "typical; Hallowfall (main-healer seat) may",
          ctx["seat_typ"].get("brawl_healer", 0) == 0
          and not e._typ_ok(ctx, roles, preds, gh, contrib_gh)
          and e._typ_ok(ctx, roles, preds, hf, contrib_hf))
    # every main-healer seat filled: the brawl healer spills in
    tm = ctx["seat_typ"]["main_healer"]
    roles = {"healer": tm}
    preds = {"seat:main_healer": tm, ph: tm}
    check("S4h with the main-healer seat at its typical the brawl-healer seat "
          "spills (every typed healer seat is full)",
          e._typ_ok(ctx, roles, preds, gh, contrib_gh)
          if roles["healer"] < max(ctx["role_typ"].get("healer", 0),
                                   ctx["role_min"].get("healer", 0))
          else True)
    # a cross-role minimum lifts the seat gate when no under-typical seat
    # of the role can meet it
    pn = next((p for p in ctx["pred_min"]
               if len(ctx["pred_roles"].get(p) or ()) > 1), None)
    if pn:
        w = next((w for w in ctx["pred_sat"][pn] if e.role_of(w) == "dps"
                  and e.seat_of(w) and ctx["seat_typ"].get(e.seat_of(w), 0) > 0), None)
    if pn and w:
        s = e.seat_of(w)
        other = [s2 for s2 in ctx["role_seats"]["dps"]
                 if s2 != s and ctx["seat_typ"].get(s2, 0) > 0
                 and s2 not in ctx["pred_seats"][pn]]
        roles = {"dps": ctx["seat_typ"][s]}
        preds = {"seat:" + s: ctx["seat_typ"][s]}
        # every other dps seat that COULD meet the minimum stands at its
        # typical; only the seats that cannot stay under theirs
        for s2 in ctx["role_seats"]["dps"]:
            if s2 != s and s2 in ctx["pred_seats"][pn]:
                preds["seat:" + s2] = ctx["seat_typ"].get(s2, 0)
                roles["dps"] += ctx["seat_typ"].get(s2, 0)
        contrib = e._pred_possible(w) | (e._profile_members.get(w) or frozenset())
        ok_when_unmet = e._typ_ok(ctx, roles, preds, w, contrib)
        preds2 = dict(preds)
        preds2[pn] = ctx["pred_min"][pn]
        ok_when_met = e._typ_ok(ctx, roles, preds2, w, contrib)
        check(f"S4i {pn} (cross-role) unmet lifts the {s} seat past its typical "
              f"while {other[:1] or ['no other']} seats that cannot meet it stand "
              f"under theirs; once met the gate closes again",
              (ok_when_unmet if other else True) and (not ok_when_met if other else True),
              f"unmet={ok_when_unmet} met={ok_when_met} other={other}")


def t_forge():
    styles = ("balanced", "brawl", "clap", "kite", "brawl_clap", "clap_kite")
    problems = []
    n_gated = 0
    for st in styles:
        for size in (10, 12, 15, 17, 20):
            e = Engine(content="blackzone_roam", size=size, style=st)
            r = e.forge(size)
            ctx = e._forge_ctx(e.suggest_pool())
            if not (r["feasible"] and len(r["party"]) == size):
                problems.append((st, size, "infeasible", len(r["party"])))
                continue
            if ctx["seat_gate"]:
                n_gated += 1
                bad = _seat_audit(e, r["party"], ctx)
                if bad:
                    problems.append((st, size, bad))
    check(f"S4a every style x size 10/12/15/17/20 forges a full feasible roster and "
          f"no generated seat passes its typical without spill or a minimum "
          f"({n_gated} gated cells)", not problems and n_gated >= 20, str(problems[:4]))
    # spill: typed seats summing below the role minimum still fill it
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    band_min = (e._band.get("healer") or {}).get("min", 0)
    e._seat_typ = {"main_healer": 1}
    r = e.forge(20)
    healers = sum(1 for w in r["party"] if e.role_of(w) == "healer")
    check(f"S4b spill: main_healer typed at 1 against a healer minimum of {band_min} "
          "still forges the minimum (a role's remaining bodies may sit anywhere "
          "once its typed seats are full)", r["feasible"] and healers >= band_min,
          f"healers={healers}")
    # the mix: three frontline seats typed at one each against a frontline
    # minimum of four forces one of each before the fourth spills
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    fmin = (e._band.get("frontline") or {}).get("min", 0)
    e._seat_typ = {"engage_tank": 1, "stopper_tank": 1, "off_tank": 1}
    r = e.forge(20)
    seats = {}
    for w in r["party"]:
        s = e.seat_of(w)
        seats[s] = seats.get(s, 0) + 1
    front = sum(1 for w in r["party"] if e.role_of(w) == "frontline")
    check(f"S4c the seat mix is honoured before spill: engage / stopper / off-tank "
          f"each at least one with frontline >= {fmin}",
          r["feasible"] and front >= fmin and all(seats.get(s, 0) >= 1 for s in
                                                    ("engage_tank", "stopper_tank", "off_tank")),
          f"front={front} seats={seats}")
    # no cell, no gate
    e25 = Engine(content="castle", size=25, style="clap")
    ctx25 = e25._forge_ctx(e25.suggest_pool())
    check("S4d a size without a cell runs with the seat gate off",
          ctx25["seat_gate"] == bool(e25._seat_typ))
    # manual rosters always score
    ek = Engine(content="blackzone_roam", size=20, style="kite")
    party = ["2H_HAMMER_AVALON"] * 5 + ["MAIN_HOLYSTAFF_AVALON"] * 15
    check("S4e a manual roster of five engage tanks still scores",
          isinstance(ek.comp_score(party), float))


# ------------------------------------------------------------------ S6
def t_plan(doc):
    """Plan tools (standoff): the typical count of standoff-tool carriers
    the declared style's winners field is a generation minimum — a kite
    forged without them is not the kite the engine itself would label."""
    if not doc:
        return
    plan = (doc.get("plan") or {}).get("typical") or {}
    check("S6a the artifact carries a plan table keyed on standoff",
          set(plan) == {"pooled", "styles"} and doc.get("plan_keys") == ["standoff"])
    e = Engine()
    standoff = e.pred_members[e.STANDOFF]
    check("S6b the standoff flag predicate is the style_fit.standoff_e set "
          f"({len(standoff)} weapons), combo-independent",
          standoff and all((e.weapons[w].get("style_fit") or {}).get("standoff_e")
                           for w in standoff)
          and all(e.STANDOFF in e._pred_contrib(w, c)
                  for w in list(standoff)[:3]
                  for c in range(len(e._combo_extras(w)))))
    kite_row = (plan["styles"].get("kite") or {}).get("20") or plan["pooled"].get("20") or {}
    ek = Engine(content="blackzone_roam", size=20, style="kite")
    band_min = ((ek._band or {}).get("standoff") or {}).get("min")
    check("S6c kite 20 carries the standoff minimum of its winners "
          f"(typical {kite_row.get('standoff')}; kite winners at 15+ field two "
          "or more in every roster)",
          band_min == kite_row.get("standoff") and (band_min or 0) >= 2,
          f"band min {band_min} row {kite_row}")
    eb = Engine(content="blackzone_roam", size=20, style="brawl")
    brawl_row = (plan["styles"].get("brawl") or {}).get("20") or {}
    check("S6d brawl 20 demands what its winners field of standoff tools "
          "(most field none: no row, no minimum)",
          ((eb._band or {}).get("standoff") or {}).get("min") == brawl_row.get("standoff"))
    r = ek.forge(20)
    n_so = sum(1 for w in r["party"] if w in standoff)
    ident = ek.comp_identity(r["party"])
    check("S6e the forged kite 20 fields its standoff tools and the engine's "
          "own identity read calls it a kiting plan (kite or clap_kite)",
          r["feasible"] and n_so >= (band_min or 0)
          and ident.get("style") in ("kite", "clap_kite"),
          f"standoff={n_so} identity={ident.get('style')} "
          f"party={[ek.weapons[w]['display_name'] for w in r['party']]}")
    party = ["2H_HAMMER_AVALON"] * 5 + ["MAIN_HOLYSTAFF_AVALON"] * 15
    check("S6f a manual kite roster without standoff tools still scores",
          isinstance(ek.comp_score(party), float))


# ------------------------------------------------------------------ S5
def t_refusal():
    import build_dataset
    try:
        build_dataset.refuse_hand_per_weapon({"per_weapon": {"2H_MACE": {"free": 2}}})
        refused = False
    except SystemExit:
        refused = True
    check("S5a a hand-set duplication.per_weapon fails the build", refused)
    try:
        build_dataset.refuse_hand_per_weapon({"per_weapon": {}})
        ok = True
    except SystemExit:
        ok = False
    check("S5b an empty list passes", ok)


t_synthetic()
DOC = t_artifact()
t_resolution(DOC)
t_forge()
t_gate_units()
t_plan(DOC)
t_refusal()
print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
