#!/usr/bin/env python3
"""
Forge rework regression suite (2026-08-18).

Pins the structural contracts of the reworked engine:
  F1  pick-score invariant: a candidate's reported score EXACTLY equals
      comp_score(party + candidate-with-chosen-combo) - comp_score(party),
      across every content x style, at 1e-9.
  F2  synergy is template-gated: a pair is inactive when either capability
      is absent from the template (castle_outpost cannot value burst_st,
      directly or through resist_shred x burst_st).
  F3  synergy is cross-member: one weapon supplying both sides of a pair
      does not self-trigger it; two distinct suppliers do.
  F4  exact-weapon redundancy: each extra copy beyond the penalty-free
      allowance costs MORE than the previous one (non-saturating), and
      meta-legitimate duplicates (2x Permafrost) stay free.
  F5  size-11 matrix: every large content x style forges a full,
      constraint-satisfying, deterministic roster with no excluded weapon
      and no unheld negative filler.
  F6  viability exclusions bar suggestions, never scoring; swap_review
      flags off-comp members.
  F7  hard floors clamp to the scaled target (a perfect-coverage party is
      never "below floor").
  F8  size physics: no single-target boost above small-gang sizes; the
      small-gang inversion itself survives; ST value is devalued at scale
      unless the content restores it (roads).
  F9  headroom: supply between target and soft cap has positive value,
      which stops growing at the soft cap.
  F10 loadout locks (user spell picks) change scoring consistently.
  F11 forge respects locked members and is deterministic.
  F12 predicate minima are combo-aware: locked non-qualifying kits are kept
      verbatim but never counted toward the ranged-AoE core.
  F13 style gate: unfit weapons leave suggestions/forge only.
  F14 no cost gate (owner ruling 2026-09-07, retiring the 2026-08-23 crystal
      gate): every cost tier sits in every suggest pool, swap_review carries
      no off_budget flag, and the anti_zone rows carry the physics instead —
      no row in the 7-man templates, a DEMAND RAMP elsewhere (nothing
      through 14, the measured value at 25, proportional beyond).
  F15 primary-heal minimum (owner ruling 2026-08-23): a hybrid healer can
      never be the comp's sole healing foundation — every forge fields the
      band's full-healer minimum in addition to the healer role band.
  F16 style role bands (owner ruling 2026-08-23): the declared style
      overrides the brawl-calibrated bands — at 20, brawl 3-4 healers,
      clap one healer per five (floor, no max); kite retains minima only.

Run:  py -3 tests/test_forge.py
"""
import os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
from engine import Engine  # noqa: E402

CONTENTS = ["blackzone_roam", "castle", "castle_outpost", "faction_war",
            "roads", "territory_defense"]
LARGE = ["blackzone_roam", "castle", "faction_war", "territory_defense"]
STYLES = ["balanced", "brawl", "brawl_clap", "clap", "kite"]
EXCLUDED_TRIO = ("MAIN_CURSEDSTAFF", "2H_IRONCLADEDSTAFF", "MAIN_FROSTSTAFF_AVALON")

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if detail:
        print(f"      {detail}")


# ---------------------------------------------------------------- F1 invariant
def t_invariant():
    rng = random.Random(20260818)
    e = Engine()
    worst = 0.0
    checked = 0
    for content in CONTENTS:
        for style in STYLES:
            for size in (7, 11, 20):
                e.set_content(content, size, style)
                pool = e.pool
                party = [pool[rng.randrange(len(pool))]
                         for _ in range(rng.randrange(0, 12))]
                combos = []
                for w in party:
                    n = len(e._combo_extras(w))
                    combos.append(None if rng.random() < 0.5 else rng.randrange(n))
                state = e.party_state(party, combos)
                base = e.comp_score(party, combos)
                for _ in range(6):
                    cand = pool[rng.randrange(len(pool))]
                    # dressed forge 2026-08-27: the invariant now covers
                    # the chosen kit variant — the delta includes vgears
                    score, _df, _ds, _meta, combo, _var, vg = \
                        e._eval_pick(state, cand)
                    actual = e.comp_score(
                        party + [cand], combos + [combo],
                        [None] * len(party) + [vg]) - base
                    diff = abs(score - actual)
                    worst = max(worst, diff)
                    checked += 1
    check("F1 pick score == comp_score delta (all contents x styles, 1e-9)",
          worst < 1e-9, f"{checked} candidate evaluations, worst |diff| = {worst:.2e}")


# ------------------------------------------------------- F2 template gating
def t_synergy_gating():
    e = Engine(content="castle_outpost", size=7)
    active = [(a, b) for a, b, _ in e._active_syn]
    gate = ("resist_shred", "burst_st") not in active
    # behavior: a party stacking both sides of the absent pair earns nothing
    # from it — synergy equals the sum over ACTIVE pairs only, recomputed
    party = ["MAIN_CURSEDSTAFF", "2H_DAGGERPAIR", "MAIN_CURSEDSTAFF"]
    s, J = e._syn_state(party)
    manual = 0.0
    for p in range(len(e._active_syn)):
        a, b, _bonus = e._active_syn[p]
        manual += e._pair_value(p, s.get(a, 0.0), s.get(b, 0.0), J[p])
    et = Engine(content="territory_defense", size=20)
    active_t = [(a, b) for a, b, _ in et._active_syn]
    check("F2 castle_outpost cannot value burst_st through synergy",
          gate and abs(e.synergy(party) - manual) < 1e-12
          and ("resist_shred", "burst_st") in active_t,
          f"castle_outpost active pairs: {active}")


# ------------------------------------------------------- F3 no self-trigger
def t_self_synergy():
    e = Engine(content="territory_defense", size=20)
    idx = next(p for p, (a, b, _) in enumerate(e._active_syn)
               if (a, b) == ("resist_shred", "burst_st"))
    s1, J1 = e._syn_state(["MAIN_CURSEDSTAFF"])
    solo = e._pair_value(idx, s1.get("resist_shred", 0.0), s1.get("burst_st", 0.0), J1[idx])
    # distinct second supplier: Longbow's shred is a PASSIVE (in every combo)
    # and it has zero burst_st — the cross-member pair must now pay
    duo_party = ["MAIN_CURSEDSTAFF", "2H_LONGBOW"]
    s2, J2 = e._syn_state(duo_party)
    duo = e._pair_value(idx, s2.get("resist_shred", 0.0), s2.get("burst_st", 0.0), J2[idx])
    check("F3 1H Cursed cannot self-trigger resist_shred x burst_st",
          solo == 0.0 and duo > 0.0,
          f"solo pair value {solo:.3f}, cross-member pair value {duo:.3f}")


# ---------------------------------------------------------- F4 redundancy
def t_redundancy():
    e = Engine(content="territory_defense", size=20)
    b = "2H_AXE"  # ordinary weapon, default allowance 1
    r1 = e.redundancy([b])
    r2 = e.redundancy([b, b])
    r3 = e.redundancy([b, b, b])
    r4 = e.redundancy([b, b, b, b])
    growing = (r1 == 0.0 and r2 - r1 == 1.0 and r3 - r2 == 2.0 and r4 - r3 == 3.0)
    p = "2H_ICECRYSTAL_UNDEAD"  # Permafrost: free 2 (Deadlyhooker P1)
    free_ok = (e.redundancy([p, p]) == 0.0 and e.redundancy([p, p, p]) == 1.0)
    h = "MAIN_HOLYSTAFF_AVALON"  # Hallowfall: free 3
    hall_ok = (e.redundancy([h, h, h]) == 0.0 and e.redundancy([h, h, h, h]) == 1.0)
    check("F4 duplicate marginal cost grows; meta duplicates stay free",
          growing and free_ok and hall_ok,
          f"2H_AXE copies cost {r2 - r1}/{r3 - r2}/{r4 - r3}; "
          f"2x Permafrost {e.redundancy([p, p])}, 3x Hallowfall {e.redundancy([h, h, h])}")


# ------------------------------------------------------- F5 size-11 matrix
def t_size11_matrix():
    ok = True
    lines = []
    for content in LARGE:
        for style in STYLES:
            e = Engine(content=content, size=11, style=style)
            r = e.forge(11)
            r2 = e.forge(11)
            party = r["party"]
            problems = []
            if not r["feasible"]:
                problems.append("infeasible")
            if len(party) != 11:
                problems.append(f"size {len(party)}")
            if r["filler"]:
                # Saturation filler is legal ONLY when irreducible: the
                # owner rulings that shrink group-band pools (F19) can
                # leave a matrix cell where EVERY remaining candidate is
                # negative — the forge must field the least-bad body and
                # surface it (the docstring's "structural saturation").
                # A filler slot with a strictly better legal replacement
                # is still a refinement failure.
                for fi in r["filler"]:
                    # dressed forge 2026-08-27: the forge audits DRESSED —
                    # this checker prices the same rosters with gears, and
                    # 'better pick available' means a LEGAL one (the
                    # comment always said legal): a replacement _add_ok
                    # rejects (dup/group/role/seat caps) or whose combos
                    # cannot keep the minima is not a refinement failure.
                    sub = party[:fi] + party[fi + 1:]
                    sub_c = r["combos"][:fi] + r["combos"][fi + 1:]
                    sub_g = r["gears"][:fi] + r["gears"][fi + 1:]
                    held_val = e.comp_score(party, r["combos"], r["gears"]) \
                        - e.comp_score(sub, sub_c, sub_g)
                    st = e.party_state(sub, sub_c, sub_g)
                    fctx = e._forge_ctx(list(e.suggest_pool()))
                    cnt_r, rl_r, pd_r, gr_r = e._forge_counts(sub, sub_c)
                    beam = {"state": st, "roles": rl_r, "preds": pd_r}
                    best = None
                    for w in e.suggest_pool():
                        if not e._add_ok(fctx, cnt_r, rl_r, pd_r, gr_r, w):
                            continue
                        pk = e._forge_eval_pick(fctx, beam, w, 0)
                        if pk is not None and (best is None or pk[0] > best):
                            best = pk[0]
                    if best is not None and best > held_val + 1e-9:
                        problems.append(
                            f"reducible filler slot {fi} "
                            f"({party[fi]} {held_val:+.4f}, "
                            f"better pick available {best:+.4f})")
            if [tuple(x) for x in (r2["party"],)] != [tuple(party)]:
                problems.append("nondeterministic")
            hit = [w for w in party if w in EXCLUDED_TRIO]
            if hit:
                problems.append(f"excluded weapon {hit}")
            # Validate against the engine's EFFECTIVE band — the base
            # composition.yaml row merged with the declared style's
            # constraint_overrides (2026-08-23: bands are style-aware, so
            # the old hardcoded 2-3 healers no longer holds for every
            # style; F16 pins the owner-ruled style values explicitly).
            roles = {}
            for w in party:
                roles[e.role_of(w)] = roles.get(e.role_of(w), 0) + 1
            for key, rule in (e._band or {}).items():
                if key in ("min_size", "max_size") or not isinstance(rule, dict):
                    continue
                if key in e.pred_defs or key == e.PRIMARY_HEAL:
                    # COMBO-AWARE (review 2026-08-19): a member counts only
                    # if the spell combination the forge actually SELECTED
                    # supplies the minima.
                    have = sum(1 for w, c in zip(party, r["combos"])
                               if key in e._pred_contrib(w, c))
                else:
                    have = roles.get(key, 0)
                if "min" in rule and have < rule["min"]:
                    problems.append(f"{key} {have} < min {rule['min']}")
                if "max" in rule and have > rule["max"]:
                    problems.append(f"{key} {have} > max {rule['max']}")
            counts = {}
            for w in party:
                counts[w] = counts.get(w, 0) + 1
            over = {w: c for w, c in counts.items() if c > e._dup_gen_max(w)}
            if over:
                problems.append(f"copy limit {over}")
            # every held slot must genuinely be constraint-mandated
            for i in r["held"]:
                sub = party[:i] + party[i + 1:]
                sub_c = r["combos"][:i] + r["combos"][i + 1:]
                _c, rr, pp, _g = e._forge_counts(sub, sub_c)
                ctx = e._forge_ctx(list(e.suggest_pool()))
                needed = any(rr.get(role, 0) < mn for role, mn in ctx["role_min"].items()) \
                    or any(pp.get(pn, 0) < mn for pn, mn in ctx["pred_min"].items())
                if not needed:
                    problems.append(f"held slot {i} not constraint-mandated")
            if problems:
                ok = False
                lines.append(f"{content}/{style}: {'; '.join(problems)}")
    check("F5 size-11 matrix: full, legal, deterministic, no excluded trio, no filler",
          ok, "; ".join(lines) or "20/20 forges clean")


# ------------------------------------------------- F6 exclusions vs scoring
def t_exclusions():
    e = Engine(content="territory_defense", size=11)
    offered = set(e.suggest_pool())
    barred = all(w not in offered for w in EXCLUDED_TRIO)
    recs = {r["weapon"] for r in e.recommend([], top_n=200)}
    not_recommended = all(w not in recs for w in EXCLUDED_TRIO)
    # manual party containing an excluded weapon still loads and scores...
    party = ["MAIN_CURSEDSTAFF", "MAIN_HOLYSTAFF_AVALON", "2H_MACE"]
    score = e.comp_score(party)
    scoreable = score == score and score != 0.0
    # ...and is flagged off-comp with replacement advice
    review = e.swap_review(party)
    flagged = review[0]["off_comp"] and not review[1]["off_comp"]
    # small content does not exclude them
    e7 = Engine(content="castle_outpost", size=7)
    small_ok = all(w in set(e7.suggest_pool()) for w in EXCLUDED_TRIO)
    check("F6 exclusions bar suggestions only; manual members score, flagged off-comp",
          barred and not_recommended and scoreable and flagged and small_ok,
          f"score={score:.3f}, off_comp flags: {[m['off_comp'] for m in review]}")


# ---------------------------------------------------------- F7 floor clamp
def t_floor_clamp():
    # Below the band's min_size the content row scales with size and sits
    # under territory's 4.2-unit absolute heal floor, so the floor clamps
    # to the target it guards (2026-08-18). Re-pinned 2026-09-11 at size 9:
    # at 10+ `balanced` now reads the POOLED harvest cell (owner
    # 2026-09-10) and the median heal_sustain of every winner at 10-14 sits
    # ABOVE the raw floor, which is the other branch — the floor stays raw.
    # The floor arms at 10, where balanced now reads the pooled cell; the
    # clamp is shown on a bands-free copy of the dataset (the content row
    # scaled to 10 sits under 4.2) and the raw branch on the real one.
    import json as _j7, tempfile as _t7
    e_real = Engine(content="territory_defense", size=10)
    d7 = _j7.loads(_j7.dumps(e_real.data))
    d7.pop("style_bands", None)
    tmp7 = os.path.join(_t7.gettempdir(), "bion_f7_content_only.json")
    with open(tmp7, "w", encoding="utf-8") as fh7:
        _j7.dump(d7, fh7)
    e = Engine(dataset_path=tmp7, content="territory_defense", size=10)
    t = e.target("heal_sustain")             # content row x 10/20, under 4.2
    raw_floor = e.floors["heal_sustain"]["floor_units"]   # 4.2 absolute
    clamped = e._floors_eff["heal_sustain"]
    at_target_ok = not e.floor_armed("heal_sustain", t)
    below_armed = e.floor_armed("heal_sustain", 0.0)
    e10 = e_real
    t10 = e10.target("heal_sustain")
    raw_kept = (e10.band_key is not None and t10 > raw_floor
                and e10._floors_eff["heal_sustain"] == raw_floor
                and e10.floor_armed("heal_sustain", raw_floor - 0.01)
                and not e10.floor_armed("heal_sustain", raw_floor))
    check("F7 hard floor clamps to the scaled target below it, and stays raw "
          "under a harvest target above it",
          raw_floor > t and clamped == t and at_target_ok and below_armed
          and raw_kept,
          f"content-only at 10: target {t:.2f}, raw floor {raw_floor}, effective {clamped:.2f}; "
          f"pooled at 10: target {t10:.2f}, effective "
          f"{e10._floors_eff['heal_sustain']:.2f}")


# --------------------------------------------------------- F8 size physics
def t_size_physics():
    e11 = Engine(content="territory_defense", size=11)
    no_boost = e11.mech_mults["burst_st"] <= 1.0 + 1e-12
    e3 = Engine(content="roads", size=3)
    small_boost = e3.mech_mults["burst_st"] > 1.0
    # ST value devaluation: styled weight of burst_st sits well under base
    ez = Engine(content="blackzone_roam", size=20)
    devalued = ez.weight("burst_st") < ez.reqs["burst_st"]["weight"] * 0.5
    er = Engine(content="roads", size=7)
    restored = er.weight("burst_st") == er.reqs["burst_st"]["weight"]
    check("F8 no ST boost at 11-in-a-20-template; small-gang inversion and "
          "content restoration intact",
          no_boost and small_boost and devalued and restored,
          f"mult@11={e11.mech_mults['burst_st']:.3f} mult@3={e3.mech_mults['burst_st']:.3f} "
          f"w20={ez.weight('burst_st'):.2f}/base {ez.reqs['burst_st']['weight']} "
          f"roads w={er.weight('burst_st'):.1f}")


# ------------------------------------------------------------- F9 headroom
def t_headroom():
    e = Engine(content="territory_defense", size=20)
    cap = "heal_sustain"
    t, soft = e.target(cap), e.soft_cap(cap)
    at_t = e._headroom_bonus(cap, t, t, soft)
    mid = e._headroom_bonus(cap, (t + soft) / 2, t, soft)
    at_soft = e._headroom_bonus(cap, soft, t, soft)
    past = e._headroom_bonus(cap, soft + 5, t, soft)
    check("F9 headroom: positive between target and soft cap, capped at soft",
          at_t == 0.0 and 0.0 < mid < at_soft and past == at_soft,
          f"at_target {at_t}, mid {mid:.3f}, at_soft {at_soft:.3f}, past {past:.3f}")


# ---------------------------------------------------- F30 target provenance
def t_target_source():
    """Target is the median (owner 2026-09-10). At 10+ a style reads the
    harvest cell (balanced its pooled cell, once the board carries one);
    every row says where its target came from and carries the bare
    minimum beside it — display provenance for the board's four stages
    (red < min < orange < typical < green < soft cap < purple), never a
    scoring input."""
    e = Engine(content="castle_outpost", size=15, style="kite")
    srcs = {c: e.target_source(c) for c in e.reqs}
    check("F30a a harvest-targeted row reports 'harvest'",
          srcs.get("heal_burst") == "harvest", str(srcs.get("heal_burst")))
    fit = (e.template.get("fit") or {}).get("stat")
    want = "content" if fit == "median" else "content_min"
    soft_only = [c for c, v in e.band_row["requirements"].items()
                 if v.get("target") is None and c in e.reqs]
    check("F30b a soft-cap-only harvest row keeps the content row's provenance",
          all(e.target_source(c) == want for c in soft_only),
          f"{soft_only[:3]} -> {[e.target_source(c) for c in soft_only[:3]]}")
    check("F30c every source is one of the four words",
          all(v in ("harvest", "harvest_borrowed", "content", "content_min")
              for v in srcs.values()), str(srcs))
    eb = Engine(content="castle_outpost", size=15, style="balanced")
    has_pool = "balanced" in ((eb.data.get("style_bands") or {}).get("bands") or {})
    check("F30d balanced reads its pooled band iff the board carries one",
          (eb.band_row is not None) == has_pool,
          f"has_pool={has_pool} band_key={eb.band_key}")
    es = Engine(content="castle_outpost", size=7, style="kite")
    check("F30e below min_size every row is content-sourced",
          es.band_row is None and all(
              es.target_source(c) in ("content", "content_min") for c in es.reqs))
    check("F30f kite at 15 asks for more than one healer's heal_burst",
          e.target("heal_burst") > 8.0, f"{e.target('heal_burst'):.2f}")
    # the four stages: min <= target <= soft on every row, in every context
    bad = []
    for content in CONTENTS:
        for style in STYLES:
            for size in (5, 7, 12, 17, 25):
                ex = Engine(content=content, size=size, style=style)
                for c in ex.reqs:
                    lo, t, hi = ex.target_min(c), ex.target(c), ex.soft_cap(c)
                    if not (0.0 <= lo <= t + 1e-9 and t <= hi + 1e-9):
                        bad.append((content, style, size, c, lo, t, hi))
    check("F30g bare minimum <= typical <= soft cap on every row",
          not bad, str(bad[:4]))
    row = e.band_row["requirements"]["heal_burst"]
    check("F30h a harvest row's minimum is its p10 scaled like the target",
          abs(e.target_min("heal_burst") - row["min"] * 15 / e.band_row["ref_size"]) < 1e-9,
          f"{e.target_min('heal_burst'):.3f} vs min {row['min']} @ref {e.band_row['ref_size']}")


# ------------------------------------------------------------- F10 locks
def t_locks():
    e = Engine(content="territory_defense", size=11)
    w = "MAIN_CURSEDSTAFF"   # W slot: Cursed Beam (sustained_dps) vs Area of Decay
    lo = e.weapons[w]["loadout"]
    slot = lo["slot_names"].index("w")
    picks_a = {"w": lo["slot_spells"][slot][0]}
    picks_b = {"w": lo["slot_spells"][slot][1]}
    ca = e.combo_from_picks(w, picks_a)
    cb = e.combo_from_picks(w, picks_b)
    party = [w, "MAIN_HOLYSTAFF_AVALON"]
    sa = e.comp_score(party, [ca, None])
    sb = e.comp_score(party, [cb, None])
    supply_differs = e.member_extra(w, ca) != e.member_extra(w, cb)
    check("F10 spell-pick locks change scoring consistently",
          ca != cb and supply_differs and abs(sa - sb) > 1e-9,
          f"combo {ca} score {sa:.4f} vs combo {cb} score {sb:.4f}")


# ------------------------------------------------------- F11 locked members
def t_locked_forge():
    e = Engine(content="territory_defense", size=11)
    locked = ["MAIN_CURSEDSTAFF", "2H_MACE"]   # incl. an off-comp manual pick
    r = e.forge(11, locked=locked)
    kept = r["party"][:2] == locked and r["locked"] == 2
    full = len(r["party"]) == 11
    regen = [w for w in r["party"][2:] if w in EXCLUDED_TRIO]
    check("F11 forge keeps locked members verbatim, never generates excluded ones",
          kept and full and not regen,
          f"party head {r['party'][:3]}, generated excluded: {regen}")


def t_pred_combo_aware():
    """Review 2026-08-19: the ranged-AoE minimum must be met by the spell
    combinations the forge actually SELECTS — the flat sheet count marked a
    member as core even when its equipped kit supplied nothing. A member
    locked with a non-qualifying spell pick must not count, and the forge
    must still deliver the minimum with real kits (or report infeasible)."""
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    need = 4   # constraint_bands 20-29: ranged_aoe_core min 4
    # lock core-capable weapons with spell kits that do NOT qualify
    locked, lcs = [], []
    for w in sorted(e.pred_members["ranged_aoe_core"]):
        bad = next((c for c in range(len(e._combo_extras(w)))
                    if "ranged_aoe_core" not in e._pred_contrib(w, c)), None)
        if bad is not None:
            locked.append(w)
            lcs.append(bad)
        if len(locked) == 2:
            break
    check("F12a a non-qualifying combo exists to lock (fixture sanity)",
          len(locked) >= 1, str(list(zip(locked, lcs))))
    r = e.forge(20, locked, lcs)
    sel = sum(1 for w, c in zip(r["party"], r["combos"])
              if "ranged_aoe_core" in e._pred_contrib(w, c))
    locked_kept = all(r["combos"][i] == lcs[i] for i in range(len(locked)))
    check("F12b locked non-AoE picks kept verbatim; SELECTED kits still meet "
          "the ranged-AoE minimum; forge honest about feasibility",
          locked_kept and r["feasible"] and sel >= need,
          f"selected core {sel}/{need}, locked kept {locked_kept}, "
          f"feasible {r['feasible']}")
    # the locked members' own kits must NOT be counted toward the minimum
    _c, _r, preds, _g = e._forge_counts(locked, lcs)
    check("F12c a locked member with a non-qualifying kit is not counted",
          preds.get("ranged_aoe_core", 0) == 0, str(preds))


def t_style_gate():
    """F13 (identity Phase C, owner ruling 2026-08-23): a weapon UNFIT for
    the declared style at this size band leaves suggestions and generation
    exactly like a viability exclusion — manual and locked picks still
    score, swap_review flags off_style, and trio sizes gate nothing.
    REVISED same day (round 3, generation-fit gate): balanced still
    declares no style intent, but a dps weapon that fits NOTHING at this
    band (Battleaxe at 20 — "doesn't fit in most group play styles bigger
    than 3") now leaves balanced generation too: that is size fitness,
    not style intent. Trio remains fully open."""
    e = Engine(content="blackzone_roam", size=20, style="clap")
    barred = "MAIN_AXE" not in set(e.suggest_pool())
    not_rec = all(r["weapon"] != "MAIN_AXE"
                  for r in e.recommend([], top_n=300))
    party = ["MAIN_AXE", "2H_MACE", "MAIN_HOLYSTAFF_AVALON"]
    score = e.comp_score(party)
    scoreable = score == score and score != 0.0
    review = e.swap_review(party)
    flagged = review[0]["off_style"] and not review[1]["off_style"]
    forged = e.forge(11)
    forge_clean = "MAIN_AXE" not in forged["party"]
    locked = e.forge(11, locked=["MAIN_AXE"])
    locked_kept = locked["party"][0] == "MAIN_AXE"
    bal_gated = "MAIN_AXE" not in set(
        Engine(content="blackzone_roam", size=20).suggest_pool())
    trio_open = "MAIN_AXE" in set(
        Engine(content="roads", size=3, style="clap").suggest_pool())
    check("F13 style gate: unfit weapons leave suggestions/forge only; "
          "manual+locked score; fits-nothing gates balanced too; trio open",
          barred and not_rec and scoreable and flagged and forge_clean
          and locked_kept and bal_gated and trio_open,
          f"score={score:.3f}, off_style={[m['off_style'] for m in review]}, "
          f"balanced_gated={bal_gated}, trio_open={trio_open}")


def t_cost_gate():
    """F14 (owner ruling 2026-09-07, retiring the 2026-08-23 crystal gate):
    "remove the cost gate for weapons ... a better ruling might be that
    that type of cleanse is not as important in small groups as the engine
    values. this would follow in line with us not restricting weapons but
    rather focusing on mechanics." No cost tier is barred anywhere;
    swap_review carries no off_budget flag; the Exalted Staff (sole
    anti_zone supplier) is judged by the anti_zone rows — none in the
    7-man templates, and a DEMAND RAMP in the rest (owner, same day:
    "don't really need it at 10-14 and then need grows slightly as
    numbers grows and then becomes a good requirement at like 25+")."""
    CRYSTAL = ("2H_HOLYSTAFF_CRYSTAL", "MAIN_NATURESTAFF_CRYSTAL",
               "2H_DUALCROSSBOW_CRYSTAL")
    pools = [set(Engine(content=c, size=n).suggest_pool())
             for c, n in (("castle_outpost", 7), ("roads", 7),
                          ("blackzone_roam", 10), ("blackzone_roam", 20))]
    admitted = all(w in p for p in pools for w in CRYSTAL)
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    review = e.swap_review(["2H_HOLYSTAFF_CRYSTAL", "2H_MACE", "MAIN_HOLYSTAFF_AVALON"])
    no_flag = all("off_budget" not in m for m in review)
    e7 = Engine(content="castle_outpost", size=7)
    no_row_7 = ("anti_zone" not in e7.reqs
                and "anti_zone" not in Engine(content="roads", size=7).reqs)
    e14 = Engine(content="blackzone_roam", size=14)
    e25 = Engine(content="castle", size=25)
    e30 = Engine(content="blackzone_roam", size=30)
    ramp = ("anti_zone" not in e14.reqs
            and abs(e._targets["anti_zone"] - 1.8 * 6 / 11) < 1e-9
            and abs(e25._targets["anti_zone"] - 1.8) < 1e-9
            and abs(e30._targets["anti_zone"] - 1.8 * 30 / 25) < 1e-9)
    check("F14 no cost gate: crystal in every suggest pool, no off_budget "
          "flag, anti_zone has no row through 14, ramps to its measured "
          "value at 25 and grows beyond",
          admitted and no_flag and no_row_7 and ramp,
          f"admitted={admitted} no_flag={no_flag} no_row_7={no_row_7} "
          f"t14={e14._targets.get('anti_zone')} t20={e._targets.get('anti_zone')} "
          f"t25={e25._targets.get('anti_zone')} t30={e30._targets.get('anti_zone')}")


def t_primary_heal():
    """F15 (owner ruling 2026-08-23): "[Forgebark] is too expensive to be
    the only healer ... it's not which line but which weapon — the weapon
    needs to have high healing numbers on its E." The primary_heal band
    minimum counts only full healers (dataset full_healer flag); a locked
    hybrid healer is kept verbatim but never satisfies it alone."""
    e = Engine(content="castle_outpost", size=7)
    ironroot = next(k for k, w in e.weapons.items()
                    if w["display_name"] == "Ironroot Staff")
    fixture_ok = (not e.weapons[ironroot].get("full_healer")
                  and e.role_of(ironroot) == "healer"
                  and e.weapons["2H_HOLYSTAFF"].get("full_healer"))
    r = e.forge(7)
    full = sum(1 for w in r["party"] if e.weapons[w].get("full_healer"))
    r2 = e.forge(7, locked=[ironroot])
    full2 = sum(1 for w in r2["party"] if e.weapons[w].get("full_healer"))
    healers2 = sum(1 for w in r2["party"] if e.role_of(w) == "healer")
    check("F15 primary-heal: every forge fields a full healer; a locked "
          "hybrid healer never satisfies the minimum alone",
          fixture_ok and r["feasible"] and full >= 1
          and r2["feasible"] and r2["party"][0] == ironroot and full2 >= 1
          and healers2 <= 2,
          f"full={full}, locked-hybrid forge: full={full2}, "
          f"healers={healers2}, feasible={r2['feasible']}")


def t_style_bands():
    """F16: one healer per five members, floor-rounded MINIMUM, no maximum
    (owner 2026-09-08; extended the same day to brawl and both hybrids -
    "sure on healers at 25"). Kite keeps its lower minima without a cap;
    balanced keeps the base band."""
    ok = True
    lines = []
    for style, lo, hi in (("brawl", 4, 20), ("clap", 4, 20), ("kite", 2, 20),
                          ("clap_kite", 4, 20)):
        e = Engine(content="blackzone_roam", size=20, style=style)
        r = e.forge(20)
        healers = sum(1 for w in r["party"] if e.role_of(w) == "healer")
        front = sum(1 for w in r["party"] if e.role_of(w) == "frontline")
        if not r["feasible"]:
            ok = False
            lines.append(f"{style}: infeasible")
        if not (lo <= healers <= hi):
            ok = False
            lines.append(f"{style}: healers {healers} not in {lo}-{hi}")
        if style == "brawl" and front > 5:
            ok = False
            lines.append(f"brawl frontline {front} > 5")
        lines.append(f"{style}: {healers}h/{front}f")
    ek = Engine(content="roads", size=7, style="kite")
    rk = ek.forge(7)
    kite7 = sum(1 for w in rk["party"] if ek.role_of(w) == "healer")
    if kite7 < 1 or not rk["feasible"] or "max" in ek._band["healer"]:
        ok = False
        lines.append(f"kite@7 healers {kite7}")
    for size, minimum in ((5, 1), (9, 1), (10, 2), (19, 3), (20, 4),
                          (21, 4), (24, 4), (25, 5), (29, 5), (30, 6), (60, 12)):
        ec = Engine(content="castle", size=size, style="clap")
        # `typical` (2026-09-11) rides beside the minimum and is not a
        # cap: minima always override it. The ruling pins min and no max.
        if ec._band["healer"].get("min") != minimum                 or "max" in ec._band["healer"]:
            ok = False
            lines.append(f"clap@{size}: {ec._band['healer']}")
    ec25 = Engine(content="castle", size=25, style="clap")
    rc25 = ec25.forge(25)
    hc25 = sum(ec25.role_of(w) == "healer" for w in rc25["party"])
    if not rc25["feasible"] or len(rc25["party"]) != 25 or hc25 < 5:
        ok = False
    lines.append(f"castle clap@25: {hc25}h, feasible={rc25['feasible']}")
    # the per-five minimum on brawl and both hybrids (owner 2026-09-08)
    for st in ("brawl", "brawl_clap", "clap_kite"):
        for size, minimum in ((20, 4), (24, 4), (25, 5)):
            band = Engine(content="castle", size=size, style=st)._band["healer"]
            if band.get("min") != minimum or "max" in band:
                ok = False
                lines.append(f"{st}@{size}: {band}")
        eb25 = Engine(content="castle", size=25, style=st)
        rb25 = eb25.forge(25)
        hb25 = sum(eb25.role_of(w) == "healer" for w in rb25["party"])
        if not rb25["feasible"] or hb25 < 5:
            ok = False
        lines.append(f"castle {st}@25: {hb25}h")
    eb = Engine(content="castle", size=25)
    if {k: v for k, v in eb._band["healer"].items() if k != "typical"}             != {"min": 3, "max": 5}:
        ok = False
        lines.append(f"balanced@25 band changed: {eb._band['healer']}")
    check("F16 one healer per five as a minimum on clap, brawl and both "
          "hybrids (4 at 20-24, 5 at 25-29, no cap); kite keeps its minima; "
          "balanced keeps the base band; full 25-person castle forges", ok,
          "; ".join(lines))


def t_double_bladed_gank():
    """F27 (owner 2026-09-08: "double bladed is a good ganking weapon but
    not a good brawl weapon. but you need to check the actual stats").
    Checked against the killer-party harvest the same day: 24 parties of
    10+ field it, 9 of them gank/dive squads, the rest carrying ONE inside
    a clap roster; 11 distinct wearers at 10+ (gank kits: Hunter Shoes,
    Graveguard), none at 20+. The exclusion (composition.yaml, evidence-
    gated) bars 10+ generation; the gang band stays open (1.6% of 4-9 man
    killer parties); manual picks still score."""
    dbs = "2H_DOUBLEBLADEDSTAFF"
    e25 = Engine(content="castle", size=25, style="brawl")
    r = e25.forge(25)
    e10 = Engine(content="blackzone_roam", size=10)
    e7 = Engine(content="castle_outpost", size=7)
    manual = e25.comp_score(["MAIN_HOLYSTAFF_AVALON", "2H_MACE", dbs])
    check("F27 Double Bladed is barred from 10+ generation (gank weapon, "
          "owner 2026-09-08 + harvest audit), open at 7; the castle-25 brawl "
          "forge fields none; a manual Double Bladed still scores",
          dbs not in set(e25.suggest_pool()) and dbs not in set(e10.suggest_pool())
          and dbs in set(e7.suggest_pool()) and dbs not in r["party"]
          and r["feasible"] and manual == manual and manual != 0.0,
          f"in forge={dbs in r['party']} feasible={r['feasible']} "
          f"manual={manual:.3f}")


def t_generation_fit():
    """F17 (owner ruling 2026-08-23, round 3 gradings): a DEFAULT generated
    comp fields damage picks the derivation says FIT. "faction war comp is
    bad because it has dagger and boltcaster, both of which can only damage
    1 person at a time with e and that's not good for anything higher than
    3v3, heavy crossbow at least can do damage through people with e" —
    and the 25-brawl's Permafrost/Wailing/single-target tail. Situational
    damage picks stay manual (score normally, never flagged off_style);
    healers/frontline/support keep their standing rules; trio gates
    nothing."""
    def by_name(e, name):
        return next(k for k, w in e.weapons.items()
                    if w["display_name"] == name)
    e = Engine(content="faction_war", size=15)
    dagger, bolt = by_name(e, "Dagger"), by_name(e, "Boltcasters")
    hxbow = by_name(e, "Heavy Crossbow")
    pool = set(e.suggest_pool())
    bal_ok = dagger not in pool and bolt not in pool and hxbow in pool
    # situational is manual territory: scores, and is NOT flagged off_style
    party = [dagger, "2H_MACE", "MAIN_HOLYSTAFF_AVALON"]
    score = e.comp_score(party)
    review = e.swap_review(party)
    manual_ok = score != 0.0 and not review[0]["off_style"]
    # declared brawl: ranged bombs are situational -> out of generation;
    # the same weapons FIT clap and stay in a clap pool
    eb = Engine(content="castle", size=25, style="brawl")
    perma, wail = "2H_ICECRYSTAL_UNDEAD", by_name(eb, "Wailing Bow")
    brawl_pool = set(eb.suggest_pool())
    ec = Engine(content="blackzone_roam", size=15, style="clap")
    clap_pool = set(ec.suggest_pool())
    style_ok = (perma not in brawl_pool and wail not in brawl_pool
                and perma in clap_pool and wail in clap_pool)
    r = eb.forge(25)
    named_bad = {dagger, bolt, perma, wail, by_name(eb, "Whispering Bow"),
                 by_name(eb, "Light Crossbow"), by_name(eb, "Glaive")}
    forge_ok = not (named_bad & set(r["party"]))
    # trio open; healers untouched (Druidic keeps its gang slot — the
    # "leave it, keep everything consistent" ruling)
    trio_ok = dagger in set(Engine(content="roads", size=3).suggest_pool())
    e7 = Engine(content="castle_outpost", size=7)
    druidic_ok = by_name(e7, "Druidic Staff") in set(e7.suggest_pool())
    check("F17 generation-fit gate: situational dps leave generation "
          "(balanced needs fits-somewhere), manual scores unflagged, "
          "style-fits kept, trio + healers untouched",
          bal_ok and manual_ok and style_ok and forge_ok and trio_ok
          and druidic_ok,
          f"bal_ok={bal_ok} manual_ok={manual_ok} style_ok={style_ok} "
          f"forge_ok={forge_ok} trio_ok={trio_ok} druidic_ok={druidic_ok}")


def t_dup_and_clump():
    """F18 (owner ruling 2026-08-24, round 4): "I don't see the value in
    adding 2 earthrunes along with hand of justice." A duplicate must EARN
    its place — the generation default is 1 copy at every size; a second
    copy comes only from a per-weapon allowance citing a real comp. And
    the derived clump_core group (clump_create >= 4 on the flat sheet:
    HoJ, Camlann, Witchwork) caps generated clump tools at 2 — one
    primary plus at most one backup."""
    e = Engine(content="faction_war", size=15)
    dup_ok = (e._dup_gen_max("2H_SHAPESHIFTER_KEEPER") == 1
              and e._dup_gen_max("2H_ICECRYSTAL_UNDEAD") == 3)
    r = e.forge(15)
    allowed = set(e.dup_per_weapon)
    counts = {}
    for w in r["party"]:
        counts[w] = counts.get(w, 0) + 1
    dupes = {w: c for w, c in counts.items() if c > 1 and w not in allowed}
    grp = next((g for g in e.groups if g.get("name") == "clump_core"), None)
    grp_ok = (grp is not None and grp.get("max") == 2
              and set(grp.get("weapons", [])) == {
                  "2H_HAMMER_AVALON", "2H_MACE_MORGANA",
                  "MAIN_ARCANESTAFF_UNDEAD"})
    e20 = Engine(content="blackzone_roam", size=20, style="brawl")
    r2 = e20.forge(20, locked=["2H_HAMMER_AVALON", "2H_MACE_MORGANA"])
    gen_clump = [w for w in r2["party"][2:]
                 if w in set(grp["weapons"])] if grp else ["?"]
    check("F18 duplicates earn their place (default 1, allowances cited); "
          "clump_core capped at 2 (locked pair blocks a generated third)",
          dup_ok and not dupes and grp_ok and r2["party"][:2] ==
          ["2H_HAMMER_AVALON", "2H_MACE_MORGANA"] and not gen_clump,
          f"dupes={dupes}, group={grp and grp['weapons']}, "
          f"generated_clump={gen_clump}")
    # F18b (round 5): "usually 2 curse is max in a 25 man party" — the
    # curse_pressure group is the whole cursed line, derived from the
    # shared Q pool the CURSEDOT record prices, capped at 2 generated.
    cg = next((g for g in e.groups if g.get("name") == "curse_pressure"),
              None)
    e25 = Engine(content="castle", size=25, style="brawl")
    r25 = e25.forge(25)
    curse_ct = sum(1 for w in r25["party"]
                   if cg and w in set(cg["weapons"]))
    check("F18b curse budget: cursed line derived (8 members), max 2 "
          "generated at castle 25",
          cg is not None and cg.get("max") == 2
          and len(cg.get("weapons", [])) == 8 and curse_ct <= 2,
          f"members={len(cg['weapons']) if cg else 0}, "
          f"forged_curse={curse_ct}")


# ---------------------------------------------- F19 curse slots are earned
def t_curse_slot_earned():
    # Owner ruling 2026-08-25: "the only weapon i see in any party bigger
    # than 15 people is the lifecurse, damnation, or rotcaller" — within a
    # non-stacking budget (the cursed line, its shared Q priced count-once)
    # a GROUP-band slot is earned by the E's enemy-DEBUFF tool
    # (pierce/purge/heal-cut at the tool bar). Fear is displacement, not a
    # debuff: "demonic staff is not a true brawl weapon at larger than 7
    # people". Derived structurally from the sheets — no hand list.
    DEBUFF_E = {"2H_CURSEDSTAFF_MORGANA",      # Damnation — pierce aura
                "MAIN_CURSEDSTAFF_UNDEAD",     # Lifecurse — purge blades
                "MAIN_CURSEDSTAFF_CRYSTAL"}    # Rotcaller — heal negate
    DAMAGE_E = {"2H_CURSEDSTAFF", "2H_DEMONICSTAFF", "2H_SKULLORB_HELL",
                "MAIN_CURSEDSTAFF", "MAIN_CURSEDSTAFF_AVALON"}
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    sf = {w: (e.weapons[w].get("style_fit") or {}) for w in DEBUFF_E | DAMAGE_E}
    demoted = all(((sf[w].get("fit") or {}).get(s) or {}).get("group")
                  == "situational"
                  for w in DAMAGE_E for s in ("brawl", "clap", "kite"))
    earned = all(((sf[w].get("fit") or {}).get("brawl") or {}).get("group")
                 == "fits" for w in DEBUFF_E)
    pool20 = set(e.suggest_pool())
    barred20 = not (DAMAGE_E & pool20)
    offered20 = ("2H_CURSEDSTAFF_MORGANA" in pool20
                 and "MAIN_CURSEDSTAFF_UNDEAD" in pool20)
    barred_bal = not (DAMAGE_E & set(
        Engine(content="blackzone_roam", size=20).suggest_pool()))
    gang = set(Engine(content="blackzone_roam", size=7,
                      style="brawl").suggest_pool())
    open_gang = ("2H_SKULLORB_HELL" in gang
                 and "MAIN_CURSEDSTAFF_AVALON" in gang)
    # a damage-E curse stays a legitimate MANUAL pick: scores, never flagged
    s = e.comp_score(["2H_SKULLORB_HELL", "MAIN_HOLYSTAFF", "2H_MACE"])
    scores = s == s and s != 0.0 and not e.is_style_unfit("2H_SKULLORB_HELL")
    e25 = Engine(content="castle", size=25, style="brawl")
    cg = next((g for g in e25.groups if g.get("name") == "curse_pressure"),
              None)
    gen_curse = [w for w in e25.forge(25)["party"]
                 if cg and w in set(cg["weapons"])]
    forged_ok = bool(gen_curse) and all(w in DEBUFF_E for w in gen_curse)
    check("F19 curse slots are earned: damage-E curses situational at group "
          "(all styles), out of 10+ pools (balanced included), gang and "
          "manual intact; castle 25 brawl fields only debuff-E curses",
          demoted and earned and barred20 and offered20 and barred_bal
          and open_gang and scores and forged_ok,
          f"demoted={demoted} earned={earned} barred20={barred20} "
          f"offered20={offered20} bal={barred_bal} gang={open_gang} "
          f"scores={scores} forged={gen_curse}")


# ---------------------------------------------- F20 resilience penetration
def t_resil_pen():
    # Owner ruling 2026-08-25: "single target is just a non pick at 20+
    # usually because enemy will have too many defensives ... you can wire
    # it as partial rebate" — per-weapon Resilience Penetration (wiki
    # post-Realm-Divided table, cited in pipeline/resilience_penetration
    # .yaml; a melee-only stat, ranged/magic weapons carry none) rebates
    # the weapon's burst_st/execute SUPPLY by the physics ratio
    # (1 - DR*(1-pen)) / (1 - DR) at the style's grown focus count. The
    # global st_value weight devaluation still applies — high-pen ST is
    # less taxed, never good.
    e = Engine(content="blackzone_roam", size=20)
    pen_dp = e.weapons["2H_DAGGERPAIR"].get("resil_pen")
    pen_hm = e.weapons["2H_MACE"].get("resil_pen")
    pen_gh = e.weapons["2H_HOLYSTAFF"].get("resil_pen", 0.0)
    stamped = pen_dp == 0.40 and pen_hm == 0.10 and not pen_gh
    bundle = {"burst_st": 4}
    dp20 = e._eff(bundle, None, pen_dp or 0.0)["burst_st"]
    hm20 = e._eff(bundle, None, pen_hm or 0.0)["burst_st"]
    z20 = e._eff(bundle, None, 0.0)["burst_st"]
    ordered = dp20 > hm20 > z20      # more pen -> more ST survives at 20
    e7 = Engine(content="castle_outpost", size=7)
    dp7 = e7._eff(bundle, None, 0.40)["burst_st"]
    z7 = e7._eff(bundle, None, 0.0)["burst_st"]
    # the rebate grows with scale (deeper Resilience -> more to ignore)
    monotone = (dp20 / z20) > (dp7 / z7) > 1.0
    check("F20 resilience penetration: cited per-weapon stat (dagger .40 / "
          "mace .10 / staff none) rebates ST supply, growing with scale",
          stamped and ordered and monotone,
          f"pens=({pen_dp},{pen_hm},{pen_gh}) "
          f"rebate20={dp20 / z20 if z20 else 0:.4f} "
          f"rebate7={dp7 / z7 if z7 else 0:.4f}")


# ---------------------------------------------- F21 need profiles (incr. 3)
def t_need_profiles():
    # Owner-ruled 2026-08-26 (blind round + 139 killboard rosters +
    # 8 curated comps + Wardergrip): fine-seat bands + function coverage
    # gate GENERATION at 15+ — engage-leaning default (engage 2-3 /
    # stopper 1-2), stopper-heavy is the territory-defense shape, zone
    # and off-tank capped, pierce + heal-cut always fielded. Below
    # min_size nothing arms; manual parties always score.
    def mix(e, party):
        seats, funcs = {}, {"pierce": 0, "anti_heal": 0}
        for w in party:
            menu = e.weapons[w].get("role_menu") or []
            sec = e.weapons[w].get("role_menu_secondary") or []
            if menu:
                seats[menu[0]] = seats.get(menu[0], 0) + 1
            for f in funcs:
                if f in menu or f in sec:
                    funcs[f] += 1
        return seats, funcs

    e = Engine(content="blackzone_roam", size=20, style="brawl")
    f = e.forge(20)
    s, fn = mix(e, f["party"])
    bz_ok = (f["feasible"]
             and 2 <= s.get("engage_tank", 0) <= 3
             and 1 <= s.get("stopper_tank", 0) <= 2
             and s.get("off_tank", 0) <= 1
             and 1 <= s.get("shield_support", 0) <= 3
             and s.get("zone_support", 0) <= 1
             and fn["pierce"] >= 1 and fn["anti_heal"] >= 1)
    et = Engine(content="territory_defense", size=20, style="brawl")
    ft = et.forge(20)
    st, _fnt = mix(et, ft["party"])
    terry_ok = ft["feasible"] and 2 <= st.get("stopper_tank", 0) <= 4
    # owner-ruled 2026-08-26 follow-up: ranged styles at 20 field a
    # 7-strong ranged-AoE core (combo-aware — the members' SELECTED
    # spells deliver it), killing the melee-heavy clap_kite defect
    ek = Engine(content="blackzone_roam", size=20, style="clap_kite")
    fk = ek.forge(20)
    _c, _r, pk, _g = ek._forge_counts(fk["party"], fk["combos"])
    ranged_ok = fk["feasible"] and pk.get("ranged_aoe_core", 0) >= 7
    e7 = Engine(content="blackzone_roam", size=7)
    unarmed = not e7._profile_min and not e7._profile_max \
        and e7.forge(7)["feasible"]
    # a locked engage tank counts toward the minimum like any member
    fl = e.forge(20, locked=["2H_HAMMER_AVALON"])
    sl, _ = mix(e, fl["party"])
    locked_ok = fl["party"][0] == "2H_HAMMER_AVALON" \
        and 2 <= sl.get("engage_tank", 0) <= 3
    check("F21 need profiles: engage-leaning default bands + function "
          "coverage at 20, stopper-heavy terry, clap_kite ranged core 7, "
          "unarmed below 15, locked members count",
          bz_ok and terry_ok and ranged_ok and unarmed and locked_ok,
          f"bz={s} funcs={fn} terry_stoppers={st.get('stopper_tank', 0)} "
          f"ck_ranged_core={pk.get('ranged_aoe_core', 0)} "
          f"locked_engage={sl.get('engage_tank', 0)}")


def t_dressed_state():
    """F22a — party_state gears plumbing (dressed forge Task 2): the fit
    marginal against a dressed party equals the exact fitness delta, and
    gears=None stays bit-identical to the legacy call shape."""
    e = Engine(content="castle", size=25, style="brawl")
    p = ["2H_MACE", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW"]
    g = [["ARMOR_PLATE_SET2"], None, ["ARMOR_LEATHER_SET2"]]
    st_naked = e.party_state(p)
    st_old = e.party_state(p, None)          # legacy call shape
    check("F22a party_state(gears=None) is unchanged and s_syn aliases s",
          st_naked["s"] == st_old["s"] and st_naked["s_syn"] == st_old["s"])
    st = e.party_state(p, None, g)
    extra = e.member_extra("2H_HAMMER")
    # Option C (owner ruling 2026-08-27): on a dressed party the floor
    # terms read the weapon+loadout basis — the marginal helper takes the
    # naked supply and the candidate's weapon-only gains, exactly as
    # _combo_score calls it.
    d_fit = e._marg_fit_from(st["s"], extra, st["s_syn"], extra)
    exact = (e.fitness(p + ["2H_HAMMER"], None, g + [None])
             - e.fitness(p, None, g))
    check("F22a dressed-party fit marginal == exact fitness delta (1e-9)",
          abs(d_fit - exact) < 1e-9, f"{d_fit} vs {exact}")


def t_kit_variants():
    """F24 — kit variants (dressed forge Task 3): deterministic, capped
    at 3, doctrine-bounded, single naked variant for menu-less weapons,
    dressed extras parallel to the combo extras per variant."""
    e = Engine(content="castle", size=25, style="brawl")
    v_mace = e.kit_variants("2H_MACE")
    v_mace2 = e.kit_variants("2H_MACE")
    check("F24 variants deterministic + capped at 3 + v0 first",
          v_mace == v_mace2 and 1 <= len(v_mace) <= 3
          and v_mace[0][0] == "v0", str(v_mace))
    gear_keys = set(e.gear)
    check("F24 every variant piece is curated gear",
          all(k in gear_keys for _v, gl in v_mace for k in (gl or [])),
          str(v_mace))
    no_menu = next(w for w in sorted(e.weapons)
                   if not (e.weapons[w].get("role_menu") or []))
    check("F24 menu-less weapon -> single naked variant",
          e.kit_variants(no_menu) == [("v0", None)],
          f"{no_menu}: {e.kit_variants(no_menu)}")
    de = e._dressed_extras("2H_MACE")
    check("F24 dressed extras parallel combos per variant",
          set(de) == {v for v, _g in v_mace}
          and all(len(de[v]) == len(e._combo_extras("2H_MACE"))
                  for v in de),
          f"variants={sorted(de)}")
    naked = e.kit_variants(no_menu)
    dn = e._dressed_extras(no_menu)
    check("F24 naked variant's dressed extras ARE the combo extras",
          all(dn["v0"][i] is e._combo_extras(no_menu)[i]
              for i in range(len(dn["v0"]))))


def t_dressed_eval():
    """F22b/F23 — dressed evaluation (dressed forge Task 4): the reported
    pick score is the exact comp_score delta INCLUDING the chosen
    variant's gears against a dressed party; manual parties score
    bit-identically regardless of the forge; forge returns gears/kits."""
    e = Engine(content="castle", size=25, style="brawl")
    p = ["2H_MACE", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW"]
    g = [["ARMOR_PLATE_SET2"], None, None]
    st = e.party_state(p, None, g)
    worst = 0.0
    pool = sorted(e.suggest_pool())[:20]
    for w in pool:
        sc, _df, _ds, _m, combo, _var, vg = e._eval_pick(st, w)
        exact = (e.comp_score(p + [w], [None] * 3 + [combo], g + [vg])
                 - e.comp_score(p, None, g))
        if abs(sc - exact) > worst:
            worst = abs(sc - exact)
    check("F22b dressed pick score == exact comp_score delta (1e-9)",
          worst < 1e-9, f"worst {worst}")

    manual = ["2H_MACE", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW",
              "2H_POLEHAMMER", "2H_ARCANESTAFF_HELL", "2H_HALBERD",
              "2H_HOLYSTAFF"]
    check("F23 manual party scores bit-identically with explicit no-gears",
          e.comp_score(manual) == e.comp_score(manual, None, None))
    r = e.forge(9, locked=manual)
    check("F23 forge returns gears/kits; locked slots keep gears None",
          "gears" in r and "kits" in r
          and len(r["gears"]) == len(r["party"])
          and all(r["gears"][i] is None for i in range(len(manual))),
          f"keys={sorted(r)} gears={r.get('gears')}")
    r2 = e.forge(9, locked=manual)
    check("F23 dressed forge is deterministic",
          r["party"] == r2["party"] and r["gears"] == r2["gears"]
          and r["score"] == r2["score"])


def t_locked_gears():
    """F25 (owner ruling 2026-08-27): a locked member supplied with
    explicit gear keeps EXACTLY that gear — scored with it, never
    re-dressed; a locked member without gear stays naked (no invented
    kit). Existing `locked` calls are untouched (F23 still pins the
    no-gears shape)."""
    e = Engine(content="castle_outpost", size=7)
    kit = ["HEAD_PLATE_SET2", "ARMOR_PLATE_KEEPER"]
    r = e.forge(7, locked=["2H_MACE", "2H_LONGBOW"], locked_combos=[],
                locked_gears=[kit, None])
    preserved = r["gears"][0] == kit and r["gears"][1] is None
    exact = abs(r["score"] - e.comp_score(r["party"], r["combos"],
                                          r["gears"])) < 1e-9
    r2 = e.forge(7, locked=["2H_MACE", "2H_LONGBOW"], locked_combos=[],
                 locked_gears=[kit, None])
    det = r["party"] == r2["party"] and r["gears"] == r2["gears"] \
        and r["score"] == r2["score"]
    rb = e.forge(7, locked=["2H_MACE", "2H_LONGBOW"], locked_combos=[])
    back = rb["gears"][0] is None and rb["gears"][1] is None
    check("F25 locked_gears: supplied kit preserved verbatim, naked lock "
          "stays naked, score == dressed comp_score, deterministic, "
          "legacy calls unchanged",
          preserved and exact and det and back,
          f"gears={r['gears'][:2]} score={r['score']:.4f} "
          f"exact={exact} back={back}")


def t_refine_gears():
    """F26 (owner ruling 2026-08-27): refine() is gear-aware. With gears,
    it optimizes the SAME dressed comp_score everything else uses —
    incumbent kits preserved, replacements arrive in their best doctrine
    variant, result returns {party, gears}, converged output admits no
    further improving dressed swap. gears=None keeps the legacy
    weapon-only list return."""
    e = Engine(content="castle_outpost", size=7)
    p = ["2H_LONGBOW", "2H_LONGBOW", "MAIN_HOLYSTAFF_AVALON", "2H_MACE"]
    pool = e.pool[:12]
    legacy = e.refine(p, max_passes=2, pool=pool)
    check("F26a legacy refine returns a plain list (weapon-only path "
          "unchanged)", isinstance(legacy, list) and len(legacy) == len(p),
          f"type={type(legacy).__name__}")
    g = [None, None, dict(e.kit_variants("MAIN_HOLYSTAFF_AVALON"))["v0"],
         None]
    r = e.refine(p, max_passes=8, pool=pool, fixed=0, gears=g)
    shape = (isinstance(r, dict)
             and len(r["party"]) == len(r["gears"]) == len(p))
    base = e.comp_score(p, None, g)
    final = e.comp_score(r["party"], None, r["gears"])
    monotone = final >= base - 1e-9
    # converged: no single (weapon x kit-variant) swap over the pool
    # still improves the dressed comp_score
    improvable = False
    for i in range(len(r["party"])):
        for w in pool:
            if w == r["party"][i]:
                continue
            for _vk, vg in e.kit_variants(w):
                cand = r["party"][:i] + [w] + r["party"][i + 1:]
                cg = r["gears"][:i] + [vg] + r["gears"][i + 1:]
                if e.comp_score(cand, None, cg) - final > 1e-9:
                    improvable = True
    r_fix = e.refine(p, max_passes=2, pool=pool, fixed=3, gears=g)
    fixed_ok = (r_fix["party"][:3] == p[:3]
                and r_fix["gears"][:3] == g[:3])
    det = e.refine(p, max_passes=8, pool=pool, fixed=0, gears=g) == r
    check("F26 dressed refine: dict result, monotone dressed comp_score, "
          "converged (no improving dressed swap left), fixed slots + "
          "supplied gear preserved, deterministic",
          shape and monotone and not improvable and fixed_ok and det,
          f"base={base:.4f} final={final:.4f} improvable={improvable} "
          f"fixed_ok={fixed_ok}")


def t_forge_every_band_size():
    """F28 (2026-09-10): every declared style forges a full, feasible roster
    at every size the bands cover, including the band EDGES. The forge's
    minimum-need precheck used to sum seat minima on top of the role bands
    they sit inside and cross-role predicates on top of the bodies that
    carry them; at the clap 15-19 band it read 19 bodies for a roster
    twelve satisfy, and clap / clap_kite forged NOTHING at exactly 15 (16
    fit) on every content - both ports agreed, no gate covered 15. The
    bound is admissible now; this pins it at the edges."""
    ok = True
    lines = []
    for content, style, size in (
            ("blackzone_roam", "clap", 15), ("blackzone_roam", "clap_kite", 15),
            ("castle", "clap", 15), ("territory_defense", "clap_kite", 15),
            ("blackzone_roam", "brawl", 15), ("blackzone_roam", "kite", 15),
            ("blackzone_roam", "brawl_clap", 15), ("blackzone_roam", "clap", 10),
            ("blackzone_roam", "clap", 14), ("blackzone_roam", "clap", 16),
            ("blackzone_roam", "clap", 19), ("blackzone_roam", "clap", 20),
            ("blackzone_roam", "clap_kite", 20), ("blackzone_roam", "kite", 10),
            ("blackzone_roam", "brawl", 20), ("castle", "clap", 25)):
        e = Engine(content=content, size=size, style=style)
        r = e.forge(size)
        n = len(r.get("party") or [])
        if not r.get("feasible") or n != size:
            ok = False
            lines.append(f"{content}/{style}@{size}: feasible={r.get('feasible')} party={n}")
    check("F28 every style forges a full roster at every band edge (10 / 14 / "
          "15 / 16 / 19 / 20 / 25): the minimum-need precheck is admissible - "
          "nested seats count inside their role band, cross-role predicates "
          "beyond the counted bodies only", ok,
          "; ".join(lines) if lines else "all full")


def t_min_need_disjoint_seats():
    """F29 (2026-09-10): the minimum-need bound may discount a CROSS-ROLE
    predicate against bodies already counted in a role only where those
    bodies could actually carry it. The 2026-09-10 bound subtracted the
    whole of a role's counted need, including bodies committed to a nested
    SEAT minimum whose satisfiers cannot satisfy the predicate at all: at
    territory_defense no stopper tank delivers ranged AoE, so a state
    needing one more stopper AND one more ranged-AoE body reads 1 instead
    of 2, the beam commits its last slot, and the roster dies one short.
    Admissible means never MORE than a legal completion needs - it must
    still never be LESS."""
    e = Engine(content="territory_defense", size=20, style="brawl")
    pool = e.suggest_pool()
    ctx = e._forge_ctx(pool)

    def sat(pn, w):
        return pn in (e._pred_possible(w)
                      | (e._profile_members.get(w) or frozenset()))
    stoppers = [w for w in pool if e._profile_primary.get(w) == "stopper_tank"]
    # the premise the arithmetic turns on, asserted rather than assumed
    premise = bool(stoppers) and not any(sat("ranged_aoe_core", w)
                                         for w in stoppers)
    # a roster one body short on TWO minima no single body can cover: the
    # frontline band is already met, so the stopper is a nested seat need
    roles = {"frontline": 4, "healer": 4, "dps": 8, "support": 2}
    preds = {"stopper_tank": 1, "ranged_aoe_core": 3, "engage_tank": 3,
             "shield_support": 1, "pierce": 1, "anti_heal": 1,
             "primary_heal": 2}
    probe = next(w for w in pool if e.role_of(w) == "healer")
    need = e._forge_min_need(ctx, roles, preds, probe, frozenset())
    f = e.forge(20)
    full = bool(f.get("feasible")) and len(f.get("party") or []) == 20
    check("F29 minimum-need bound stays a LOWER bound: a cross-role "
          "predicate is not discounted against bodies committed to a seat "
          "minimum its satisfiers cannot fill; territory_defense brawl "
          "forges a full roster at 20",
          premise and need >= 2 and full,
          f"premise={premise} need={need} (two bodies required) "
          f"feasible={f.get('feasible')} party={len(f.get('party') or [])}")


def t_role_typical():
    """F31 (2026-09-11, owner: "go ahead"): a body beyond the TYPICAL
    count for its role is generated only when a minimum only that role
    can meet still demands it. The typical count is GENERATED from the
    committed harvest (derive_role_counts.py: p50 of fully-known killer
    parties per size; healer only - the pooled harvest agrees with the
    published comps for healers, size 7 = 1 in 67% of 658, and not for
    the other roles). Before: castle_outpost clap at 7 with a Nature
    Staff locked forged a SECOND healer (heal_sustain target 4.5 is one
    dressed Redemption Staff; a 2.9 healer left a gap only another healer
    body could close, riders tipped it, no overstack cost) and the roster
    left burst_aoe at 15 of 22. Manual parties still score anything."""
    e = Engine(content="castle_outpost", size=7, style="clap")
    typ = ((e._band or {}).get("healer") or {}).get("typical")
    check("F31a castle_outpost 7 carries a healer typical of 1 (the fitted "
          "comps' median, agreeing with the harvest)",
          typ == 1, f"band healer = {(e._band or {}).get('healer')}")
    ns = next(k for k, w in e.weapons.items()
              if w["display_name"] == "Nature Staff")
    hf = next(k for k, w in e.weapons.items()
              if w["display_name"] == "Hallowfall")
    lines, ok = [], True
    for lock in (ns, hf):
        r = e.forge(7, locked=[lock])
        n = sum(1 for w in r["party"] if e.role_of(w) == "healer")
        full = r["feasible"] and len(r["party"]) == 7
        if n != 1 or not full:
            ok = False
        lines.append(f"{e.weapons[lock]['display_name']}: healers={n} "
                     f"feasible={r['feasible']} party={len(r['party'])}")
    check("F31b castle_outpost clap 7 with a full healer locked forges ONE "
          "healer and a full roster", ok, "; ".join(lines))
    # a locked HYBRID (not a full healer) still pulls the full healer the
    # primary_heal minimum demands - the typical count yields to a minimum
    # only healers can meet
    hybrid = next(k for k, w in e.weapons.items()
                  if e.role_of(k) == "healer" and not w.get("full_healer")
                  and k in e.suggest_pool())
    r = e.forge(7, locked=[hybrid])
    n = sum(1 for w in r["party"] if e.role_of(w) == "healer")
    full_h = sum(1 for w in r["party"] if e.weapons[w].get("full_healer"))
    check("F31c a locked hybrid healer still gets the full healer primary_heal "
          "demands (typical yields to a minimum only that role can meet)",
          r["feasible"] and len(r["party"]) == 7 and n == 2 and full_h >= 1,
          f"{e.weapons[hybrid]['display_name']} locked: healers={n} "
          f"full={full_h} feasible={r['feasible']} party={len(r['party'])}")
    # two locked full healers are the caller's: kept verbatim, scored,
    # nothing generated beyond
    r = e.forge(7, locked=[ns, hf])
    n = sum(1 for w in r["party"] if e.role_of(w) == "healer")
    check("F31d two locked healers stay (manual picks always score), the "
          "forge adds no third", r["feasible"] and n == 2
          and len(r["party"]) == 7,
          f"healers={n} feasible={r['feasible']} party={len(r['party'])}")
    # sizes the harvest does not cover carry no typical (never invented)
    e25 = Engine(content="castle", size=25, style="clap")
    check("F31e no harvest rows at 25 -> no typical on the band (unknown "
          "stays explicit)",
          "typical" not in ((e25._band or {}).get("healer") or {}),
          f"band healer = {(e25._band or {}).get('healer')}")

    # --- tanks and supports, every size and style (owner 2026-09-11:
    # "fix it up all for all party sizes and styles not just 7s")
    # Below 10 the row is the content's fitted-comps median (rule 17):
    # castle_outpost 7 = 2 frontline (2/2/3), support p50 0 -> no row;
    # roads (1 comp) has none, so it reads the pooled harvest row: healer
    # only, never a tank count the open-world squads would set to 1.
    fr = ((e._band or {}).get("frontline") or {}).get("typical")
    sp = (e._band or {}).get("support") or {}
    er = Engine(content="roads", size=7, style="clap")
    er_row = {k: v.get("typical") for k, v in (er._band or {}).items()
              if isinstance(v, dict) and "typical" in v}
    check("F31f below 10 the typical row is the content's comps median: "
          "castle_outpost 7 frontline 2, no support row (p50 0); roads 7 "
          "(one comp) reads the harvest healer row only",
          fr == 2 and "typical" not in sp and er_row == {"healer": 1},
          f"castle_outpost frontline={fr} support={sp} roads={er_row}")
    hm = next(k for k, w in e.weapons.items() if w["display_name"] == "Heavy Mace")
    hoj = next(k for k, w in e.weapons.items()
               if w["display_name"] == "Hand of Justice")
    ph = next(k for k, w in e.weapons.items() if w["display_name"] == "Polehammer")
    lines, ok = [], True
    for label, lock in (("Heavy Mace", [hm]), ("HM+HoJ", [hm, hoj])):
        r = e.forge(7, locked=lock)
        f = sum(1 for w in r["party"] if e.role_of(w) == "frontline")
        if f != 2 or not r["feasible"] or len(r["party"]) != 7:
            ok = False
        lines.append(f"{label}: frontline={f} feasible={r['feasible']}")
    r3 = e.forge(7, locked=[hm, hoj, ph])
    f3 = sum(1 for w in r3["party"] if e.role_of(w) == "frontline")
    h3 = sum(1 for w in r3["party"] if e.role_of(w) == "healer")
    if f3 != 3 or h3 != 1 or not r3["feasible"]:
        ok = False
    lines.append(f"three locked tanks: frontline={f3} healers={h3} "
                 f"feasible={r3['feasible']}")
    check("F31g a locked tank at 7 no longer pulls a third (2 typical); "
          "three locked tanks stay and get ONE full healer", ok,
          "; ".join(lines))
    # the typical slots carry the role's exclusive minima: the one healer
    # slot is never spent on a hybrid that would force a second, full
    # healer on top (balanced at 7 used to forge Great Nature + Fallen)
    eb = Engine(content="castle_outpost", size=7, style="balanced")
    rb = eb.forge(7)
    hb = [w for w in rb["party"] if eb.role_of(w) == "healer"]
    check("F31h the one typical healer slot goes to a FULL healer (the slot "
          "must carry primary_heal), never a hybrid plus a forced second",
          len(hb) == 1 and eb.weapons[hb[0]].get("full_healer") is True
          and rb["feasible"],
          f"healers={[eb.weapons[w]['display_name'] for w in hb]}")
    # 10+: the declared style's harvest cell per exact size; balanced and
    # a style too thin for a cell (brawl_clap) read the pooled row
    def row(content, style, size):
        b = Engine(content=content, size=size, style=style)._band or {}
        return {k: v["typical"] for k, v in b.items()
                if isinstance(v, dict) and "typical" in v}
    b12 = row("blackzone_roam", "brawl", 12)
    c20 = row("castle", "clap", 20)
    bal20 = row("castle", "balanced", 20)
    bc20 = row("castle", "brawl_clap", 20)
    pooled20 = row("castle", "balanced", 20)
    # (2026-09-11, Exalted re-seated as a healer: the harvest counts it as
    # one now — clap 20 reads 4/5/3, the pooled 20 row 4/5/3)
    check("F31i at 10+ the band carries healer / frontline / support from "
          "the declared style's cell (brawl 12: 2/2/1; clap 20: 4/5/3); "
          "balanced and thin brawl_clap read the pooled row (20: 4/5/3)",
          b12 == {"healer": 2, "frontline": 2, "support": 1}
          and c20 == {"healer": 4, "frontline": 5, "support": 3}
          and bal20 == {"healer": 4, "frontline": 5, "support": 3}
          and bc20 == pooled20 and "dps" not in c20,
          f"brawl12={b12} clap20={c20} balanced20={bal20} brawl_clap20={bc20}")
    eb12 = Engine(content="blackzone_roam", size=12, style="brawl")
    rb12 = eb12.forge(12)
    f12 = sum(1 for w in rb12["party"] if eb12.role_of(w) == "frontline")
    check("F31j brawl 12 forges the typical two tanks (it fielded four, the "
          "cell's p90) and a full roster",
          f12 == 2 and rb12["feasible"] and len(rb12["party"]) == 12,
          f"frontline={f12} feasible={rb12['feasible']} n={len(rb12['party'])}")
    # every declared style forges a full, feasible roster with the rows on
    lines, ok = [], True
    for content, style, size in (("blackzone_roam", "brawl", 11),
                                 ("blackzone_roam", "clap", 13),
                                 ("castle", "clap_kite", 16),
                                 ("castle", "kite", 18),
                                 ("territory_defense", "brawl_clap", 20),
                                 ("castle_outpost", "kite", 5),
                                 ("roads", "brawl", 9)):
        ex = Engine(content=content, size=size, style=style)
        rx = ex.forge(size)
        if not rx["feasible"] or len(rx["party"]) != size:
            ok = False
            lines.append(f"{content}/{style}@{size}: feasible={rx['feasible']} "
                         f"n={len(rx['party'])}")
    check("F31k every style forges a full, feasible roster under its typical "
          "rows at 5 / 9 / 11 / 13 / 16 / 18 / 20", ok,
          "; ".join(lines) if lines else "all full")


def t_forge_avoid():
    """F32 (2026-09-11, owner: "a different viable comp each press"): the
    forge takes an `avoid` list of rosters already shown and returns the
    best roster NOT among them - deterministic, never random. The page
    passes every roster shown under the current locks / content / style
    / size (the one on screen included), so a refresh always moves. When
    every complete roster the search can reach is avoided the result
    carries `exhausted` and the page says so instead of repeating."""
    e = Engine(content="castle_outpost", size=7, style="clap")
    ns = next(k for k, w in e.weapons.items() if w["display_name"] == "Nature Staff")
    key = lambda p: "|".join(sorted(p))
    shown, results = [], []
    ok, lines = True, []
    for press in range(3):
        r = e.forge(7, locked=[ns], avoid=shown)
        k = key(r["party"])
        if k in {key(p) for p in shown} or not r["feasible"]                 or len(r["party"]) != 7 or r["party"][0] != ns                 or r.get("exhausted"):
            ok = False
        if results and r["score"] > results[-1]["score"] + 1e-9:
            ok = False      # next-best: never better than what was avoided
        healers = sum(1 for w in r["party"] if e.role_of(w) == "healer")
        if healers != 1:
            ok = False      # the typical gate holds on every alternative
        lines.append(f"press {press + 1}: {round(r['score'], 3)} healers={healers}")
        shown.append(list(r["party"]))
        results.append(r)
    # determinism: the same avoid list gives the same roster
    again = e.forge(7, locked=[ns], avoid=shown[:2])
    check("F32a three refreshes give three distinct, feasible, non-improving "
          "rosters under the same locks (next-best, not random), every one "
          "on one healer; the same avoid list reproduces the same roster",
          ok and key(again["party"]) == key(results[2]["party"]),
          "; ".join(lines) + f"; replay={key(again['party']) == key(results[2]['party'])}")
    # a locked-out search: avoid EVERY roster the final beam can offer by
    # locking six of seven and avoiding the only completion's alternatives
    r0 = e.forge(7, locked=[ns])
    six = r0["party"][:6]
    pool = [w for w in e.suggest_pool()]
    seen, ex = [], None
    for _ in range(len(pool) + 1):
        rr = e.forge(7, locked=six, avoid=seen)
        if rr.get("exhausted"):
            ex = rr
            break
        seen.append(list(rr["party"]))
    check("F32b when every reachable completion is avoided the forge says "
          "`exhausted` (and still returns a full roster) instead of "
          "repeating silently",
          ex is not None and ex["feasible"] and len(ex["party"]) == 7,
          f"alternatives before exhaustion: {len(seen)}")


def t_replace_options():
    """F33 (2026-09-11, owner: "show ranked alternatives, I pick"): the
    replacements for ONE slot are a one-slot forge - every candidate is
    scored as a dressed pick into the rest of the comp and passes the
    forge's own gates (role bands, typical counts, dup caps, minima), so
    the list never offers what the forge would refuse: a second healer
    into a 7-man on one, or a dps for the only full healer."""
    e = Engine(content="castle_outpost", size=7, style="clap")
    ns = next(k for k, w in e.weapons.items() if w["display_name"] == "Nature Staff")
    r = e.forge(7, locked=[ns])
    party = r["party"]
    idx_dps = next(i for i, w in enumerate(party) if e.role_of(w) == "dps")
    opts = e.replace_options(party, idx_dps, r["combos"], r["gears"], top_n=5)
    roles = [e.role_of(o["weapon"]) for o in opts]
    ok = (0 < len(opts) <= 5
          and all(o["weapon"] != party[idx_dps] for o in opts)
          and "healer" not in roles
          and all(opts[i]["score"] >= opts[i + 1]["score"] - 1e-9
                  for i in range(len(opts) - 1))
          and all(set(o) >= {"weapon", "display_name", "score", "delta",
                             "combo", "kit"} for o in opts))
    check("F33a replacing a dps in a one-healer 7-man offers no healer (the "
          "typical gate), never the same weapon, ranked by the exact "
          "dressed marginal into the rest", ok,
          f"{[(o['display_name'], round(o['delta'], 2)) for o in opts]}")
    opts_h = e.replace_options(party, 0, r["combos"], r["gears"], top_n=5)
    ok_h = bool(opts_h) and all(e.weapons[o["weapon"]].get("full_healer")
                                for o in opts_h)
    check("F33b replacing the only full healer offers only full healers "
          "(primary_heal minimum must stay met with no slot to spare)",
          ok_h, f"{[o['display_name'] for o in opts_h]}")
    # delta is the score change of the swap: applying the top option
    # changes comp_score by exactly that much (dressed, 1e-9)
    top = opts[0]
    p2 = list(party); c2 = list(r["combos"]); g2 = list(r["gears"])
    p2[idx_dps], c2[idx_dps], g2[idx_dps] = top["weapon"], top["combo"], top["kit"]
    d = e.comp_score(p2, c2, g2) - e.comp_score(party, r["combos"], r["gears"])
    check("F33c an option's delta IS the comp-score change of applying it",
          abs(d - top["delta"]) < 1e-9, f"delta={top['delta']:.6f} applied={d:.6f}")


if __name__ == "__main__":
    t_invariant()
    t_synergy_gating()
    t_self_synergy()
    t_redundancy()
    t_size11_matrix()
    t_exclusions()
    t_floor_clamp()
    t_size_physics()
    t_headroom()
    t_locks()
    t_locked_forge()
    t_pred_combo_aware()
    t_style_gate()
    t_cost_gate()
    t_primary_heal()
    t_style_bands()
    t_forge_every_band_size()
    t_double_bladed_gank()
    t_generation_fit()
    t_dup_and_clump()
    t_curse_slot_earned()
    t_resil_pen()
    t_need_profiles()
    t_dressed_state()
    t_kit_variants()
    t_dressed_eval()
    t_locked_gears()
    t_refine_gears()
    t_min_need_disjoint_seats()
    t_target_source()
    t_role_typical()
    t_forge_avoid()
    t_replace_options()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} forge regression tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
