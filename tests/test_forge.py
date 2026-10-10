#!/usr/bin/env python3
"""
Forge rework regression suite.

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
  F14 no cost gate (retiring the crystal gate): every cost tier sits in
      every suggest pool, swap_review carries no off_budget flag, and the
      anti_zone rows carry the physics instead — no row in the 7-man
      templates, a DEMAND RAMP elsewhere (nothing through 14, the
      measured value at 25, proportional beyond).
  F15 primary-heal minimum: a hybrid healer can never be the comp's sole
      healing foundation — every forge fields the band's full-healer
      minimum in addition to the healer role band.
  F16 style role bands: the declared style overrides the brawl-calibrated
      bands — at 20, brawl 3-4 healers, clap one healer per five (floor,
      no max); kite retains minima only.

Run:  py -3 tests/test_forge.py
"""
import os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
from engine import Engine  # noqa: E402

CONTENTS = ["ancient_lands", "blackzone_roam", "castle", "castle_outpost",
            "faction_war", "roads", "territory_defense"]
LARGE = ["blackzone_roam", "castle", "faction_war", "territory_defense"]
STYLES = ["balanced", "brawl", "brawl_clap", "clap", "kite"]
# Chillhowl left the hand exclusion: at 10+ the fielded gate decides it (F6b)
EXCLUDED_PAIR = ("MAIN_CURSEDSTAFF", "2H_IRONCLADEDSTAFF")

RESULTS = []
_UG = []


def ungated(**kw):
    """An engine on a dataset copy without the fielded lists at 10+: the
    pins on the style, generation-fit and cost rules read the pools those
    rules leave (the fielded gate is its own layer, S8)."""
    if not _UG:
        import json as _j, tempfile as _t
        e0 = Engine()
        d = _j.loads(_j.dumps(e0.data))
        d["composition"]["skeleton"]["fielded"] = {}
        path = os.path.join(_t.gettempdir(), "bion_forge_no_fielded.json")
        with open(path, "w", encoding="utf-8") as fh:
            _j.dump(d, fh)
        _UG.append(path)
    return Engine(dataset_path=_UG[0], **kw)


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
                    # dressed forge: the invariant now covers
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
    # F1d — the ONE super-additive duplicate (self_cost_offset_min_copies,
    # Demon Armor): a candidate whose kit completes the pair refunds the
    # existing wearer's self-cost and waives its own; a party past the
    # count waives the candidate's; both ride the pick score, which stays
    # the exact comp_score delta. Worn keys count in their curated form:
    # a tiered key and a (key, choice) pair are the same item.
    e = Engine(content="blackzone_roam", size=20)
    w0, cand = "2H_CURSEDSTAFF", "2H_DUALMACE_AVALON"
    demon = ["HEAD_PLATE_SET3", "ARMOR_PLATE_HELL", "SHOES_PLATE_SET1"]
    vg0 = dict(e.kit_variants(cand))["v0"]
    worst_d, seen = 0.0, []
    for party, gears in (([w0], [demon]), ([w0, w0], [demon, demon]),
                         ([w0], [["T8_ARMOR_PLATE_HELL@2"]]),
                         ([w0], [[("ARMOR_PLATE_HELL", 0)]])):
        state = e.party_state(party, None, gears)
        score, d_fit, _ds, _m, combo, _var, vg = e._eval_pick(state, cand)
        actual = e.comp_score(party + [cand], [None] * len(party) + [combo],
                              gears + [vg]) - e.comp_score(party, None, gears)
        rows, _cg = e._pick_caps(state, cand, combo, vg)
        worst_d = max(worst_d, abs(score - actual),
                      abs(sum(r["delta"] for r in rows) - d_fit))
        seen.append((sorted(state["pending"]), sorted(state["waived"])))
    check("F1d the self-cost offset rides the pick score: a pair-completing "
          "kit refunds the wearer and waives its own cost, a waived party "
          "waives the candidate's, tiered and pair-form keys count (1e-9)",
          worst_d < 1e-9 and "ARMOR_PLATE_HELL" in vg0
          and seen[0] == (["ARMOR_PLATE_HELL"], []) and seen[1] == ([], ["ARMOR_PLATE_HELL"])
          and seen[2] == seen[0] and seen[3] == seen[0],
          f"worst |diff| = {worst_d:.2e} pending/waived per case = {seen}")
    check("F1e gear_key resolves a tiered key to its tierless curated item "
          "and the carrier quota reads a (key, choice) pair",
          e.gear_key("T8_ARMOR_PLATE_HELL") == "ARMOR_PLATE_HELL"
          and e.gear_key("T5_POTION_REVIVE") == "T7_POTION_REVIVE"
          and e._carrier_counts([w0], [[("ARMOR_PLATE_HELL", 0)]])
              == e._carrier_counts([w0], [["ARMOR_PLATE_HELL"]])
          and e.comp_identity([w0, w0], None, [[("ARMOR_PLATE_HELL", 0)], ["ARMOR_PLATE_HELL"]]) is not None,
          f"carriers={e._carrier_counts([w0], [[('ARMOR_PLATE_HELL', 0)]])}")


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
    # Allowances are GENERATED per style x band (derive_skeletons.py,
    # free = round(p50 copies) of the rosters fielding the weapon at the
    # band). The hand list is retired: Great Arcane's free 2 (one
    # Deadlyhooker party) reads 1 at 20 (9% of winners double it),
    # Hallowfall keeps a free second copy (88% double it), and
    # Permafrost's free 2 — already removed — stays gone (p50 one copy).
    # Every copy beyond `free` pays rho.
    p = "2H_ARCANESTAFF"
    free_ok = (e._dup_free(p) == 1 and e.redundancy([p, p]) == 1.0
               and e.redundancy([p, p, p]) == 3.0)
    pf = "2H_ICECRYSTAL_UNDEAD"
    perma_ok = (e._dup_free(pf) == 1 and e.redundancy([pf, pf]) == 1.0
                and e.rho == 0.5)
    h = "MAIN_HOLYSTAFF_AVALON"
    fh = e._dup_free(h)
    hall_ok = (fh >= 2 and fh == e.dup_per_weapon[h]["free"]
               and e.redundancy([h] * fh) == 0.0
               and e.redundancy([h] * (fh + 1)) == 1.0)
    check("F4 duplicate marginal cost grows; generated allowances: "
          "Great Arcane free 1, Hallowfall's free second copy from the harvest, "
          "Permafrost pays (rho 0.5)",
          growing and free_ok and hall_ok and perma_ok,
          f"2H_AXE copies cost {r2 - r1}/{r3 - r2}/{r4 - r3}; "
          f"Great Arcane free {e._dup_free(p)}, Permafrost free {e._dup_free(pf)}, "
          f"Hallowfall free {fh}")


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
                # rules that shrink group-band pools (F19) can
                # leave a matrix cell where EVERY remaining candidate is
                # negative — the forge must field the least-bad body and
                # surface it (the docstring's "structural saturation").
                # A filler slot with a strictly better legal replacement
                # is still a refinement failure.
                for fi in r["filler"]:
                    # dressed forge: the forge audits DRESSED —
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
            hit = [w for w in party if w in EXCLUDED_PAIR]
            if hit:
                problems.append(f"excluded weapon {hit}")
            # Validate against the engine's EFFECTIVE band — the base
            # composition.yaml row merged with the declared style's
            # constraint_overrides (bands are style-aware, so
            # the old hardcoded 2-3 healers no longer holds for every
            # style; F16 pins the style values explicitly).
            roles = {}
            for w in party:
                roles[e.role_of(w)] = roles.get(e.role_of(w), 0) + 1
            for key, rule in (e._band or {}).items():
                if key in ("min_size", "max_size") or not isinstance(rule, dict):
                    continue
                if key in e.pred_defs or key in (e.PRIMARY_HEAL, e.STANDOFF):
                    # COMBO-AWARE (F12): a member counts only
                    # if the spell combination the forge actually SELECTED
                    # supplies the minima. `standoff` is the
                    # plan-tool flag predicate, combo-independent like
                    # primary_heal.
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
    check("F5 size-11 matrix: full, legal, deterministic, no excluded weapon, no filler",
          ok, "; ".join(lines) or "20/20 forges clean")


# ------------------------------------------------- F6 exclusions vs scoring
def t_exclusions():
    e = Engine(content="territory_defense", size=11)
    offered = set(e.suggest_pool())
    barred = all(w not in offered for w in EXCLUDED_PAIR)
    recs = {r["weapon"] for r in e.recommend([], top_n=200)}
    not_recommended = all(w not in recs for w in EXCLUDED_PAIR)
    # manual party containing an excluded weapon still loads and scores...
    party = ["MAIN_CURSEDSTAFF", "MAIN_HOLYSTAFF_AVALON", "2H_MACE"]
    score = e.comp_score(party)
    scoreable = score == score and score != 0.0
    # ...and is flagged off-comp with replacement advice
    review = e.swap_review(party)
    flagged = review[0]["off_comp"] and not review[1]["off_comp"]
    # small content does not exclude them
    e7 = Engine(content="castle_outpost", size=7)
    small_ok = all(w in set(e7.suggest_pool()) for w in EXCLUDED_PAIR)
    check("F6 exclusions bar suggestions only; manual members score, flagged off-comp",
          barred and not_recommended and scoreable and flagged and small_ok,
          f"score={score:.3f}, off_comp flags: {[m['off_comp'] for m in review]}")
    # F6b Chillhowl carries no hand exclusion: at 10+ it is in the
    # suggestion pool exactly where the declared style's fielded list
    # (balanced: the pooled list) carries it, and a manual pick scores
    chill = "MAIN_FROSTSTAFF_AVALON"
    fl = (e.data["composition"].get("skeleton") or {}).get("fielded") or {}
    bad, offered_in = [], []
    for st in ("balanced", "brawl", "clap", "kite", "brawl_clap", "clap_kite"):
        for size in (10, 15, 20):
            ex = Engine(content="blackzone_roam", size=size, style=st)
            band = next((bk for bk, lim in (fl.get("bands") or {}).items()
                         if lim[0] <= size <= lim[1]), None)
            row = ((fl.get("pooled") or {}).get(band) if st == "balanced"
                   else ((fl.get("styles") or {}).get(st) or {}).get(band))
            got = chill in set(ex.suggest_pool())
            if got:
                offered_in.append(f"{st}/{size}")
            if row is not None and got != (chill in row) and chill not in ex._gen_situational:
                bad.append(f"{st}/{size}")
    sc = Engine(content="blackzone_roam", size=20).comp_score(
        [chill, "MAIN_HOLYSTAFF_AVALON", "2H_MACE"])
    check("F6b Chillhowl has no hand exclusion at 10+: the fielded gate decides "
          "it per style x band, and a manual Chillhowl scores",
          not bad and sc == sc and sc != 0.0,
          f"offered at {offered_in or 'none'}; mismatches {bad}")


# ---------------------------------------------------------- F7 floor clamp
def t_floor_clamp():
    # Below the band's min_size the content row scales with size and sits
    # under territory's 4.2-unit absolute heal floor, so the floor clamps
    # to the target it guards. Re-pinned at size 9: at 10+ `balanced` now
    # reads the POOLED harvest cell (target is the median, F30) and the
    # median heal_sustain of every winner at 10-14 sits ABOVE the raw
    # floor, which is the other branch — the floor stays raw.
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
    # ST value devaluation at 20: the size multiplier sits well under 1 and
    # the styled weight is exactly base x multiplier. Read on the multiplier,
    # not on one template's weight: a fitted base weight may be zero
    # (blackzone_roam's burst_st under its weight_fit).
    ez = Engine(content="blackzone_roam", size=20)
    stv = ez._st_value_mult(20)
    devalued = (stv < 0.5 and abs(ez.weight("burst_st")
                                  - ez.reqs["burst_st"]["weight"] * stv) < 1e-12)
    er = Engine(content="roads", size=7)
    restored = er.weight("burst_st") == er.reqs["burst_st"]["weight"]
    check("F8 no ST boost at 11-in-a-20-template; small-gang inversion and "
          "content restoration intact",
          no_boost and small_boost and devalued and restored,
          f"mult@11={e11.mech_mults['burst_st']:.3f} mult@3={e3.mech_mults['burst_st']:.3f} "
          f"st_value@20={stv:.3f} w20={ez.weight('burst_st'):.2f}/base "
          f"{ez.reqs['burst_st']['weight']} roads w={er.weight('burst_st'):.1f}")


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
    """Target is the median (the typical winner, p50). At 10+ a style
    reads the harvest cell (balanced its pooled cell, once the board
    carries one); every row says where its target came from and carries
    the bare minimum beside it — display provenance for the board's four
    stages (red < min < orange < typical < green < soft cap < purple),
    never a scoring input."""
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
    regen = [w for w in r["party"][2:] if w in EXCLUDED_PAIR]
    check("F11 forge keeps locked members verbatim, never generates excluded ones",
          kept and full and not regen,
          f"party head {r['party'][:3]}, generated excluded: {regen}")


def t_pred_combo_aware():
    """F12: the ranged-AoE minimum must be met by the spell
    combinations the forge actually SELECTS — the flat sheet count marked a
    member as core even when its equipped kit supplied nothing. A member
    locked with a non-qualifying spell pick must not count, and the forge
    must still deliver the minimum with real kits (or report infeasible)."""
    # balanced reads the pooled generated ranged_aoe_core minimum at 20
    # (skeleton minima, S7; brawl's winners field none, so brawl carries
    # none)
    e = Engine(content="blackzone_roam", size=20, style="balanced")
    need = (e._band.get("ranged_aoe_core") or {}).get("min", 0)
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
    check("F12a a non-qualifying combo exists to lock and the band carries a "
          "minimum (fixture sanity)",
          len(locked) >= 1 and need >= 1, f"{list(zip(locked, lcs))}, need {need}")
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
    """F13 (identity Phase C): a weapon UNFIT for the declared style at
    this size band leaves suggestions and generation exactly like a
    viability exclusion — manual and locked picks still score,
    swap_review flags off_style, and trio sizes gate nothing.
    REVISED at validation round 3 (generation-fit gate): balanced still
    declares no style intent, but a dps weapon that fits NOTHING at this
    band (Battleaxe at 20 fits no group playstyle above 3) now leaves
    balanced generation too: that is size fitness, not style intent.
    Trio remains fully open."""
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
    """F14 (retiring the crystal cost gate): weapons are never restricted
    by cost; the better rule is that this type of cleanse matters less in
    small groups than the engine valued it — mechanics, not weapon
    restrictions (curation judgment). No cost tier is barred anywhere;
    swap_review carries no off_budget flag; the Exalted Staff (sole
    anti_zone supplier) is judged by the anti_zone rows — none in the
    7-man templates, and a DEMAND RAMP in the rest (not needed at 10-14,
    a need that grows slightly with numbers and becomes a real
    requirement at 25+)."""
    CRYSTAL = ("2H_HOLYSTAFF_CRYSTAL", "MAIN_NATURESTAFF_CRYSTAL",
               "2H_DUALCROSSBOW_CRYSTAL")
    # RE-PINNED as recorded (V: 10, The fielded gate at 10+): no COST rule
    # bars a crystal weapon, so at 10+ the pools read are those without the
    # fielded lists; the fielded gate may bar one where winners do not
    # field it, recorded in the detail line
    pools = [set(ungated(content=c, size=n).suggest_pool())
             for c, n in (("castle_outpost", 7), ("roads", 7),
                          ("blackzone_roam", 10), ("blackzone_roam", 20))]
    admitted = all(w in p for p in pools for w in CRYSTAL)
    fielded_bars = sorted({f"{w}@{n}" for n in (10, 20) for w in CRYSTAL
                           if Engine(content="blackzone_roam", size=n).is_unfielded(w)})
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
    check("F14 no cost gate: crystal in every suggest pool the cost rules "
          "leave, no off_budget flag, anti_zone has no row through 14, ramps "
          "to its measured value at 25 and grows beyond",
          admitted and no_flag and no_row_7 and ramp,
          f"admitted={admitted} fielded gate bars {fielded_bars or 'none'} "
          f"no_flag={no_flag} no_row_7={no_row_7} "
          f"t14={e14._targets.get('anti_zone')} t20={e._targets.get('anti_zone')} "
          f"t25={e25._targets.get('anti_zone')} t30={e30._targets.get('anti_zone')}")


def t_primary_heal():
    """F15: Forgebark is too expensive to be the only healer — it is not
    the line but the weapon that decides, and the weapon needs high
    healing numbers on its E (curation judgment). The primary_heal band
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
    (extended to brawl and both hybrids; five healers at 25). Kite keeps
    its lower minima without a cap; balanced keeps the base band."""
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
        # `typical` (F31) rides beside the minimum and is not a
        # cap: minima always override it. The rule pins min and no max.
        if ec._band["healer"].get("min") != minimum                 or "max" in ec._band["healer"]:
            ok = False
            lines.append(f"clap@{size}: {ec._band['healer']}")
    # a single party caps at 20 (forges stop at 20): the full castle party
    # forges at 20 with the per-five minimum's 4 healers; the band rule at
    # 25 still stands for a manual roster's reads
    ec20 = Engine(content="castle", size=20, style="clap")
    rc20 = ec20.forge(20)
    hc20 = sum(ec20.role_of(w) == "healer" for w in rc20["party"])
    if not rc20["feasible"] or len(rc20["party"]) != 20 or hc20 < 4:
        ok = False
    lines.append(f"castle clap@20: {hc20}h, feasible={rc20['feasible']}")
    # the per-five minimum on brawl and both hybrids
    for st in ("brawl", "brawl_clap", "clap_kite"):
        for size, minimum in ((20, 4), (24, 4), (25, 5)):
            band = Engine(content="castle", size=size, style=st)._band["healer"]
            if band.get("min") != minimum or "max" in band:
                ok = False
                lines.append(f"{st}@{size}: {band}")
        eb20 = Engine(content="castle", size=20, style=st)
        rb20 = eb20.forge(20)
        hb20 = sum(eb20.role_of(w) == "healer" for w in rb20["party"])
        if not rb20["feasible"] or hb20 < 4:
            ok = False
        lines.append(f"castle {st}@20: {hb20}h")
    eb = Engine(content="castle", size=25)
    if {k: v for k, v in eb._band["healer"].items() if k != "typical"}             != {"min": 3, "max": 5}:
        ok = False
        lines.append(f"balanced@25 band changed: {eb._band['healer']}")
    check("F16 one healer per five as a minimum on clap, brawl and both "
          "hybrids (4 at 20-24, 5 at 25-29, no cap); kite keeps its minima; "
          "balanced keeps the base band; full 20-person castle forges", ok,
          "; ".join(lines))


def t_double_bladed_gank():
    """F27: Double Bladed is a ganking weapon, not a brawl weapon
    (curation judgment, checked against the killer-party harvest): 24
    parties of 10+ field it, 9 of them gank/dive squads, the rest
    carrying ONE inside a clap roster; 11 distinct wearers at 10+ (gank
    kits: Hunter Shoes, Graveguard), none at 20+. The exclusion
    (composition.yaml, evidence-gated) bars 10+ generation; the gang band
    stays open (1.6% of 4-9 man killer parties); manual picks still
    score."""
    dbs = "2H_DOUBLEBLADEDSTAFF"
    e20 = Engine(content="castle", size=20, style="brawl")
    r = e20.forge(20)
    e10 = Engine(content="blackzone_roam", size=10)
    e7 = Engine(content="castle_outpost", size=7)
    manual = e20.comp_score(["MAIN_HOLYSTAFF_AVALON", "2H_MACE", dbs])
    check("F27 Double Bladed is barred from 10+ generation (gank weapon, "
          "harvest audit), open at 7; the castle-20 brawl "
          "forge fields none; a manual Double Bladed still scores",
          dbs not in set(e20.suggest_pool()) and dbs not in set(e10.suggest_pool())
          and dbs in set(e7.suggest_pool()) and dbs not in r["party"]
          and r["feasible"] and manual == manual and manual != 0.0,
          f"in forge={dbs in r['party']} feasible={r['feasible']} "
          f"manual={manual:.3f}")


def t_generation_fit():
    """F17 (validation round 3): a DEFAULT generated comp fields damage
    picks the derivation says FIT. The faction-war comp failed on Dagger
    and Boltcasters, whose E damages one person at a time — no use above
    3v3, where Heavy Crossbow at least damages through people with its E
    — and the 25-brawl's Permafrost/Wailing/single-target tail.
    Situational damage picks stay manual (score normally, never flagged
    off_style); healers/frontline/support keep their standing rules; trio
    gates nothing."""
    def by_name(e, name):
        return next(k for k, w in e.weapons.items()
                    if w["display_name"] == name)
    e = Engine(content="faction_war", size=15)
    dagger, bolt = by_name(e, "Dagger"), by_name(e, "Boltcasters")
    hxbow = by_name(e, "Heavy Crossbow")
    # RE-PINNED as recorded (V: 10, The fielded gate at 10+): the
    # generation-fit gate's pool, without the fielded lists; the fielded
    # gate bars Heavy Crossbow at 15 balanced (the pooled list)
    pool = set(ungated(content="faction_war", size=15).suggest_pool())
    bal_ok = dagger not in pool and bolt not in pool and hxbow in pool
    # situational is manual territory: scores, and is NOT flagged off_style
    party = [dagger, "2H_MACE", "MAIN_HOLYSTAFF_AVALON"]
    score = e.comp_score(party)
    review = e.swap_review(party)
    manual_ok = score != 0.0 and not review[0]["off_style"]
    # declared brawl: ranged bombs are situational -> out of generation;
    # the same weapons FIT clap and stay in a clap pool
    eb = Engine(content="castle", size=20, style="brawl")
    perma, wail = "2H_ICECRYSTAL_UNDEAD", by_name(eb, "Wailing Bow")
    brawl_pool = set(eb.suggest_pool())
    ec = Engine(content="blackzone_roam", size=15, style="clap")
    clap_pool = set(ec.suggest_pool())
    style_ok = (perma not in brawl_pool and wail not in brawl_pool
                and perma in clap_pool and wail in clap_pool)
    r = eb.forge(20)
    named_bad = {dagger, bolt, perma, wail, by_name(eb, "Whispering Bow"),
                 by_name(eb, "Light Crossbow"), by_name(eb, "Glaive")}
    forge_ok = not (named_bad & set(r["party"]))
    # trio open; healers untouched (Druidic keeps its gang slot — left
    # as is, so the gang band stays consistent)
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
    """F18 (validation round 4): two Earthrunes beside a Hand of Justice
    add nothing. A duplicate must EARN its place — the generation default
    is 1 copy at every size; a second copy comes only from a per-weapon
    allowance citing a real comp. And the derived clump_core group
    (clump_create >= 4 on the flat sheet: HoJ, Camlann, Witchwork) caps
    generated clump tools at 2 — one primary plus at most one backup."""
    e = Engine(content="faction_war", size=15)
    # generated allowances: the forge cap is ceil(p90 copies)
    # of the rosters fielding the weapon at the band, the free copies
    # round(p50) — Earthrune keeps the default, Great Arcane's hand cap of
    # 3 (one Deadlyhooker party) falls to what winners at 15-19 field,
    # Permafrost's free second copy stays gone
    ga = e.dup_per_weapon.get("2H_ARCANESTAFF") or {}
    dup_ok = (e._dup_gen_max("2H_SHAPESHIFTER_KEEPER") == 1
              and e._dup_gen_max("2H_ARCANESTAFF") == ga.get("max", 1) < 3
              and e._dup_free("2H_ARCANESTAFF") == ga.get("free", 1) == 1
              and e._dup_free("2H_ICECRYSTAL_UNDEAD") == 1)
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
    # F18b (validation round 5): two curses are the usual maximum in a
    # 25-man party — the curse_pressure group is the whole cursed line,
    # derived from the shared Q pool the CURSEDOT record prices, capped
    # at 2 generated (a single party forges at 20 at most: castle 20)
    cg = next((g for g in e.groups if g.get("name") == "curse_pressure"),
              None)
    e20c = Engine(content="castle", size=20, style="brawl")
    r20c = e20c.forge(20)
    curse_ct = sum(1 for w in r20c["party"]
                   if cg and w in set(cg["weapons"]))
    check("F18b curse budget: cursed line derived (8 members), max 2 "
          "generated at castle 20",
          cg is not None and cg.get("max") == 2
          and len(cg.get("weapons", [])) == 8 and curse_ct <= 2,
          f"members={len(cg['weapons']) if cg else 0}, "
          f"forged_curse={curse_ct}")


# ---------------------------------------------- F19 curse slots are earned
def t_curse_slot_earned():
    # The only curses seen in parties above 15 are Lifecurse, Damnation
    # and Rotcaller (curation judgment) — within a non-stacking budget
    # (the cursed line, its shared Q priced count-once) a GROUP-band slot
    # is earned by the E's enemy-DEBUFF tool (pierce/purge/heal-cut at
    # the tool bar). Fear is displacement, not a debuff: Demonic Staff is
    # not a true brawl weapon above 7 people. Derived structurally from
    # the sheets — no hand list.
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
    e20c = Engine(content="castle", size=20, style="brawl")
    cg = next((g for g in e20c.groups if g.get("name") == "curse_pressure"),
              None)
    gen_curse = [w for w in e20c.forge(20)["party"]
                 if cg and w in set(cg["weapons"])]
    forged_ok = bool(gen_curse) and all(w in DEBUFF_E for w in gen_curse)
    check("F19 curse slots are earned: damage-E curses situational at group "
          "(all styles), out of 10+ pools (balanced included), gang and "
          "manual intact; castle 20 brawl fields only debuff-E curses",
          demoted and earned and barred20 and offered20 and barred_bal
          and open_gang and scores and forged_ok,
          f"demoted={demoted} earned={earned} barred20={barred20} "
          f"offered20={offered20} bal={barred_bal} gang={open_gang} "
          f"scores={scores} forged={gen_curse}")


# ---------------------------------------------- F20 resilience penetration
def t_resil_pen():
    # Single target is a non-pick at 20+, since the enemy fields too many
    # defensives; penetration is wired as a partial rebate (curation
    # judgment) — a weapon's Resilience Penetration, the pinned snapshot's
    # own item stat (items.json @focusfireprotectionpenetration, read into
    # out/item_stats.json), rebates its burst_st/execute SUPPLY by the
    # physics ratio (1 - DR*(1-pen)) / (1 - DR) at the style's grown focus
    # count. The global st_value weight devaluation still applies —
    # high-pen ST is less taxed, never good. The pinned snapshot sets the
    # stat to zero on every item (it sits on equipment traits, which the
    # model does not read), so every stamp is checked against the snapshot
    # and the physics on stated values.
    import json
    e = Engine(content="blackzone_roam", size=20)
    with open(os.path.join(ROOT, "pipeline", "out", "item_stats.json"), encoding="utf-8") as f:
        bank = json.load(f).get("items", {})

    def snap(k):
        return float(((bank.get(k) or {}).get("stats") or {})
                     .get("focusfireprotectionpenetration") or 0.0)
    off = [k for k, w in e.weapons.items()
           if abs((w.get("resil_pen") or 0.0) - snap(k)) > 1e-12]
    stamped = not off
    bundle = {"burst_st": 4}
    dp20 = e._eff(bundle, None, 0.40)["burst_st"]
    hm20 = e._eff(bundle, None, 0.10)["burst_st"]
    z20 = e._eff(bundle, None, 0.0)["burst_st"]
    ordered = dp20 > hm20 > z20      # more pen -> more ST survives at 20
    e7 = Engine(content="castle_outpost", size=7)
    dp7 = e7._eff(bundle, None, 0.40)["burst_st"]
    z7 = e7._eff(bundle, None, 0.0)["burst_st"]
    # the rebate grows with scale (deeper Resilience -> more to ignore)
    monotone = (dp20 / z20) > (dp7 / z7) > 1.0
    carried = sum(1 for w in e.weapons.values() if w.get("resil_pen"))
    check("F20 resilience penetration: each weapon's stamp is the pinned "
          "snapshot's own item stat; a pen rebates ST supply (.40 above .10 "
          "above none), growing with scale",
          stamped and ordered and monotone,
          f"off={off[:4]} carried={carried} "
          f"rebate20={dp20 / z20 if z20 else 0:.4f} "
          f"rebate7={dp7 / z7 if z7 else 0:.4f}")


# ---------------------------------------------- F21 need profiles (incr. 3)
def t_need_profiles():
    # Validation round (139 killboard rosters + 8 curated comps +
    # Wardergrip): fine-seat bands + function coverage
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
    # follow-up rule: ranged styles at 20 field a ranged-AoE core
    # (combo-aware — the members' SELECTED spells deliver it), killing the
    # melee-heavy clap_kite defect; its size is the GENERATED minimum of
    # clap_kite's winners at 20 (skeleton minima, S7)
    ek = Engine(content="blackzone_roam", size=20, style="clap_kite")
    fk = ek.forge(20)
    _c, _r, pk, _g = ek._forge_counts(fk["party"], fk["combos"])
    ck_min = ((ek._band or {}).get("ranged_aoe_core") or {}).get("min", 0)
    ranged_ok = (fk["feasible"] and ck_min >= 1
                 and pk.get("ranged_aoe_core", 0) >= ck_min)
    e7 = Engine(content="blackzone_roam", size=7)
    unarmed = not e7._profile_min and not e7._profile_max \
        and e7.forge(7)["feasible"]
    # a locked engage tank counts toward the minimum like any member
    fl = e.forge(20, locked=["2H_HAMMER_AVALON"])
    sl, _ = mix(e, fl["party"])
    locked_ok = fl["party"][0] == "2H_HAMMER_AVALON" \
        and 2 <= sl.get("engage_tank", 0) <= 3
    check("F21 need profiles: engage-leaning default bands + function "
          "coverage at 20, stopper-heavy terry, clap_kite ranged core at its "
          "generated minimum, unarmed below 15, locked members count",
          bz_ok and terry_ok and ranged_ok and unarmed and locked_ok,
          f"bz={s} funcs={fn} terry_stoppers={st.get('stopper_tank', 0)} "
          f"ck_ranged_core={pk.get('ranged_aoe_core', 0)}/{ck_min} "
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
    # Option C (source-aware floors): on a dressed party the floor
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
    """F25 (locked gears): a locked member supplied with
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
    """F26: refine() is gear-aware. With gears,
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
    """F28: every declared style forges a full, feasible roster
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
            ("blackzone_roam", "brawl", 20), ("castle", "clap", 20)):
        e = Engine(content=content, size=size, style=style)
        r = e.forge(size)
        n = len(r.get("party") or [])
        if not r.get("feasible") or n != size:
            ok = False
            lines.append(f"{content}/{style}@{size}: feasible={r.get('feasible')} party={n}")
    check("F28 every style forges a full roster at every band edge (10 / 14 / "
          "15 / 16 / 19 / 20; a single party stops at 20): the minimum-need "
          "precheck is admissible - "
          "nested seats count inside their role band, cross-role predicates "
          "beyond the counted bodies only", ok,
          "; ".join(lines) if lines else "all full")


def t_min_need_disjoint_seats():
    """F29: the minimum-need bound may discount a CROSS-ROLE
    predicate against bodies already counted in a role only where those
    bodies could actually carry it. The earlier bound subtracted the
    whole of a role's counted need, including bodies committed to a nested
    SEAT minimum whose satisfiers cannot satisfy the predicate at all: at
    territory_defense no stopper tank delivers ranged AoE, so a state
    needing one more stopper AND one more ranged-AoE body reads 1 instead
    of 2, the beam commits its last slot, and the roster dies one short.
    Admissible means never MORE than a legal completion needs - it must
    still never be LESS. Balanced reads the pooled generated ranged_aoe_core
    minimum (skeleton minima, S7; brawl carries none); the state stands one
    ranged-AoE body under it."""
    e = Engine(content="territory_defense", size=20, style="balanced")
    pool = e.suggest_pool()
    ctx = e._forge_ctx(pool)
    core_min = ctx["pred_min"].get("ranged_aoe_core", 0)

    def sat(pn, w):
        return pn in (e._pred_possible(w)
                      | (e._profile_members.get(w) or frozenset()))
    stoppers = [w for w in pool if e._profile_primary.get(w) == "stopper_tank"]
    # the premise the arithmetic turns on, asserted rather than assumed
    premise = bool(stoppers) and core_min >= 1 \
        and not any(sat("ranged_aoe_core", w) for w in stoppers)
    # a roster one body short on TWO minima no single body can cover: the
    # frontline band is already met, so the stopper is a nested seat need
    roles = {"frontline": 4, "healer": 4, "dps": 8, "support": 2}
    preds = {"stopper_tank": 1, "ranged_aoe_core": core_min - 1,
             "engage_tank": 3, "shield_support": 1, "pierce": 1,
             "anti_heal": 1, "primary_heal": 2}
    probe = next(w for w in pool if e.role_of(w) == "healer")
    need = e._forge_min_need(ctx, roles, preds, probe, frozenset())
    f = e.forge(20)
    full = bool(f.get("feasible")) and len(f.get("party") or []) == 20
    check("F29 minimum-need bound stays a LOWER bound: a cross-role "
          "predicate is not discounted against bodies committed to a seat "
          "minimum its satisfiers cannot fill; territory_defense balanced "
          "forges a full roster at 20",
          premise and need >= 2 and full,
          f"premise={premise} need={need} (two bodies required; ranged-AoE "
          f"core minimum {core_min}) "
          f"feasible={f.get('feasible')} party={len(f.get('party') or [])}")


def t_role_typical():
    """F31 typical role count: a body beyond the TYPICAL
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

    # --- tanks and supports, every size and style (the typical rows
    # cover every party size and style, not just 7s)
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
    # The typicals are GENERATED (derive_role_counts.py, training split):
    # the contract is where each cell reads from, never the numbers. A
    # declared style reads its own cell at the exact size when the table
    # carries one (brawl_clap 20 does at 20,718 battles; it read the
    # pooled row while thin), balanced reads the pooled row, and dps
    # carries a typical at 10+ only (V: 10, dps carries a typical at 10+;
    # below 10 it is the residual role).
    import json as _json
    with open(os.path.join(ROOT, "pipeline", "out", "role_counts.json"),
              encoding="utf-8") as fh:
        _typ = _json.load(fh)["typical"]
    def expect(style, size):
        own = _typ["styles"].get(style, {}).get(str(size))
        return own if own else _typ["pooled"][str(size)]
    check("F31i at 10+ the band carries healer / frontline / support / dps "
          "from the declared style's generated cell at the exact size; "
          "balanced reads the pooled row; a style without a cell reads "
          "pooled; below 10 dps carries none",
          b12 == expect("brawl", 12) and c20 == expect("clap", 20)
          and bal20 == _typ["pooled"]["20"] and bc20 == expect("brawl_clap", 20)
          and "dps" in c20
          and "dps" not in {k for k, v in (e._band or {}).items()
                            if isinstance(v, dict) and "typical" in v},
          f"brawl12={b12} clap20={c20} balanced20={bal20} brawl_clap20={bc20}")
    # RE-PINNED as recorded (V: 10, dps carries a typical at 10+): with dps
    # typed the role typicals sum to 11 at brawl 12, so one body spills
    # past every role's typical and sits where the score puts it (a third
    # tank today); never more tanks than the typical plus the spill, and
    # never the four it fielded before the typical (the cell's p90)
    eb12 = Engine(content="blackzone_roam", size=12, style="brawl")
    rb12 = eb12.forge(12)
    f12 = sum(1 for w in rb12["party"] if eb12.role_of(w) == "frontline")
    typ12 = eb12._role_typical()
    spill12 = max(0, 12 - sum(typ12.values()))
    check("F31j brawl 12 forges at most the typical two tanks plus the bodies "
          "that spill past every role's typical (it fielded four, the cell's "
          "p90), and a full roster",
          typ12.get("frontline") == 2 and f12 <= 2 + spill12 and f12 < 4
          and rb12["feasible"] and len(rb12["party"]) == 12,
          f"frontline={f12} typical={typ12} spill={spill12} "
          f"feasible={rb12['feasible']} n={len(rb12['party'])}")
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
    # A MATCHMAKING POOL'S OWN COUNTS (derive_role_counts.py `pools`): the
    # Dragon Portal's dominant winners at the exact size, the unit its
    # requirement rows are fitted on. A pool's row may state ZERO (the
    # p75 winner fields none of the role), which the open-world rows
    # never do.
    import json as _json
    with open(os.path.join(ROOT, "pipeline", "out", "role_counts.json"), encoding="utf-8") as f:
        rc = _json.load(f)
    pools = (rc.get("typical") or {}).get("pools", {}).get("ancient_lands") or {}
    cells = (rc.get("pool_cells") or {}).get("ancient_lands") or {}
    check("F31l the portal pools carry role counts of their own at 2-7, each from at least 40 "
          "distinct dominant rosters on the training split: a trio is a healer and no frontline, "
          "four to seven one healer and one frontline, no support through five",
          pools.get("3") == {"healer": 1, "frontline": 0, "support": 0}
          and pools.get("5") == {"healer": 1, "frontline": 1, "support": 0}
          and pools.get("7", {}).get("frontline") == 1 and pools.get("7", {}).get("healer") == 1
          and all(cells[s]["distinct"] >= 40 for s in pools)
          and (rc.get("_split") or {}).get("holdout_mod") == 5,
          str(pools))
    check("F31m a zero is written only where the p75 winner fields none; a role a quarter of the "
          "winners field has no row (the support at 6 and 7)",
          all(cells[s][r]["p75"] == 0 for s, row in pools.items() for r, n in row.items() if n == 0)
          and "support" not in pools.get("7", {}) and cells["7"]["support"]["p75"] > 0,
          str({s: cells[s]["support"] for s in ("5", "7")}))
    e3 = Engine(content="ancient_lands", size=3)
    e5 = Engine(content="ancient_lands", size=5)
    check("F31n inside the portal the engine reads the pool's row before any other table, zero "
          "included; another content at the same size does not",
          e3._role_typical() == pools["3"] and e5._role_typical() == pools["5"]
          and e3._band["frontline"]["typical"] == 0
          and Engine(content="roads", size=5)._role_typical() != pools["5"],
          f"{e3._role_typical()} {e5._role_typical()}")
    shapes = {}
    for st in STYLES:
        for n in (3, 5, 7):
            ex = Engine(content="ancient_lands", size=n, style=st)
            rx = ex.forge(n)
            roles = [ex.role_of(w) for w in rx["party"]]
            shapes[(st, n)] = (rx["feasible"] and len(rx["party"]) == n, roles.count("frontline"), roles.count("healer"))
    bad = {k: v for k, v in shapes.items()
           if not v[0] or v[1] > (0 if k[1] == 3 else 1) or v[2] > 1}
    check("F31o in every style a forged portal trio fields no frontline, a five and a seven at most "
          "one, and each at most one healer (the pool's winners' shape), full and feasible",
          not bad, str(bad))


def t_forge_avoid():
    """F32 (a different viable comp on each press): the
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


def t_portal_rows():
    """F34 — the Dragon Portal rows come from the portal harvest
    (pipeline/derive_portal_rows.py), and a content that keeps full
    single-target value admits single-scale carries at the gang band."""
    import yaml
    with open(os.path.join(ROOT, "pipeline", "templates", "ancient_lands.yaml"), encoding="utf-8") as f:
        tpl = yaml.safe_load(f)
    fit = tpl.get("fit") or {}
    check("F34a the Dragon Portal rows are fitted on the portal harvest: median, "
          "at least 40 distinct rosters, training split",
          fit.get("stat") == "median" and fit.get("source") == "harvest"
          and fit.get("comps", 0) >= 40 and "% 5 != 0" in str(fit.get("split")), str(fit)[:160])
    ramps = {c: r for c, r in tpl["requirements"].items() if r.get("ramp")}
    check("F34b a ramp row carries no scales and ends where the 6-7 pool or the style rows begin",
          bool(ramps) and all(not r.get("scales") and r["ramp"]["full_at"] in (7, 10)
                              for r in ramps.values()), str(sorted(ramps)))
    fitted = {c: r for c, r in tpl["requirements"].items() if not r.get("ramp")}
    check("F34c every fitted row carries min <= target <= soft cap with a target above zero",
          all(0 < r["target"] <= r["soft_cap"] and r.get("min", 0) <= r["target"] for r in fitted.values()),
          str([c for c, r in fitted.items() if not (0 < r["target"] <= r["soft_cap"])]))
    bow = "2H_BOW"
    e5 = Engine(content="ancient_lands", size=5)
    e7 = Engine(content="ancient_lands", size=7)
    e10 = Engine(content="ancient_lands", size=10)
    r5 = Engine(content="roads", size=5)
    c5 = Engine(content="castle_outpost", size=5)
    check("F34d st_full_value admits a single-scale carry at the gang band (the Bow at 4-5 and 6-7, "
          "on the portal and on roads), never at group, and a content without the flag keeps barring it",
          bow in set(e5.suggest_pool()) and bow in set(e7.suggest_pool()) and bow in set(r5.suggest_pool())
          and bow not in set(e10.suggest_pool()) and bow not in set(c5.suggest_pool())
          and not e5.is_excluded(bow) and not e5.is_style_unfit(bow),
          f"portal5={bow in set(e5.suggest_pool())} portal7={bow in set(e7.suggest_pool())} "
          f"roads5={bow in set(r5.suggest_pool())} portal10={bow in set(e10.suggest_pool())} "
          f"castle_outpost5={bow in set(c5.suggest_pool())}")
    pools = tpl.get("pool_rows") or {}
    opt5 = {c: r for c, r in pools.get("4-5", {}).get("requirements", {}).items() if r.get("optional")}
    check("F34e at 4-5 a ramped row is no REQUIREMENT: a capability a minority of the pool's winners "
          "field is an optional row (silence, cleanse), one under one winner in ten fields is no row "
          "(execute); the fitted rows are requirements, and past the pools the base ramp stands",
          "silence" in opt5 and "cleanse" in opt5 and "execute" not in e5.reqs
          and all(c in e5.reqs and c in e5.optional for c in opt5)
          and "tankiness" in e5.reqs and "tankiness" not in e5.optional
          and "clump_create" in e7.reqs and "silence" in e10.reqs and "silence" not in e10.optional,
          f"optional5={sorted(opt5)} absent5={sorted(set(tpl['requirements']) - set(e5.reqs))}")
    check("F34f the 2-3, 6-7 and 15-20 pools carry rows of their own and the fitted 4-5 pool its "
          "optional rows alone, each at least 40 distinct rosters, every row none or 0 <= min <= "
          "target < soft cap over the base capabilities",
          set(pools) == {"2-3", "4-5", "6-7", "15-20"}
          and all(r.get("optional") for r in pools["4-5"]["requirements"].values())
          and all(p["comps"] >= 40 and p["ref_size"] == p["sizes"][1]
                  and all(c in tpl["requirements"] for c in p["requirements"])
                  and all(r.get("none") or 0 <= r.get("min", r["target"]) <= r["target"] < r["soft_cap"]
                          for r in p["requirements"].values())
                  for p in pools.values()), str(sorted(pools)))
    e3 = Engine(content="ancient_lands", size=3)
    t3 = pools.get("2-3", {}).get("requirements", {}).get("tankiness") or {}
    check("F34g inside a pool the engine reads the pool's row at its ref size as a harvest median; "
          "at the base size a capability without a pool row reads the base row, and between the pools "
          "(10) no pool is read",
          e3.pool_key == "2-3" and e7.pool_key == "6-7" and e5.pool_key == "4-5"
          and Engine(content="ancient_lands", size=20).pool_key == "15-20"
          and e10.pool_key is None
          and t3 and abs(e3.target("tankiness") - t3["target"]) < 1e-9
          and e3.target_source("tankiness") == "harvest" and e5.target_source("tankiness") == "content",
          f"pool3={e3.pool_key} t3={e3.target('tankiness'):.2f} row={t3} src={e3.target_source('tankiness')}")
    none3 = sorted(c for c, r in pools.get("2-3", {}).get("requirements", {}).items() if r.get("none"))
    check("F34h a pool's none rows are no requirement at that pool, and its fitted rows all are",
          bool(none3) and all(c not in e3.reqs for c in none3)
          and all(c in e3.reqs for c, r in pools["2-3"]["requirements"].items() if not r.get("none")),
          str(none3))
    # an optional row pays for what is brought and asks for nothing: the
    # silence of a Heavy Mace earns coverage at 5, and a five without
    # silence is not short of it (the row leaves that party's supremum)
    core = ["MAIN_HOLYSTAFF", "2H_BOW", "2H_DUALSWORD", "2H_LONGBOW"]
    rep = e5.pick_report(core, "2H_MACE")
    sil = next((x for x in rep["caps"] if x["cap"] == "silence"), None)
    row = opt5.get("silence") or {}
    rep_h = e5.pick_report(core, "2H_HAMMER")
    check("F34i an optional pool row pays the weapon that brings it and charges nobody: the Heavy "
          "Mace's silence earns coverage at 5 against the fielders' median, with no minimum; a "
          "frontline without silence carries no silence term",
          sil is not None and sil["delta"] > 0 and row.get("min") == 0
          and abs(e5.target("silence") - row["target"]) < 1e-9
          and not any(x["cap"] == "silence" for x in rep_h["caps"]),
          f"silence={sil} row={row}")
    # F34j - the 15-20 pool's own rows outrank the style x size rows: a
    # large portal party is judged against what that pool's winners field
    # (tests/VALIDATION.md, the 15-20 portal pool). Every other context
    # of 10+ keeps the style x size rows.
    large = pools.get("15-20", {}).get("requirements", {})
    ok, detail = bool(large), []
    for style in ("balanced", "brawl", "clap", "kite", "brawl_clap", "clap_kite"):
        for size in (15, 18, 20):
            e = Engine(content="ancient_lands", size=size, style=style)
            for c, r in large.items():
                if r.get("none"):
                    good = c not in e.reqs
                else:
                    want = (r["target"] * e.target_mults.get(c, 1.0)
                            * (size / 20.0 if r.get("scales") else 1.0))
                    good = (c in e.reqs and abs(e.target(c) - want) < 1e-9
                            and e.target_source(c) == "harvest")
                if not good:
                    ok = False
                    detail.append(f"{style}/{size}/{c}")
    e12 = Engine(content="ancient_lands", size=12, style="clap")
    r20 = Engine(content="roads", size=20, style="clap")
    band = lambda e: [c for c, v in e.band_row["requirements"].items()   # noqa: E731
                      if c in e.reqs and v.get("target") is not None
                      and abs(e.target(c) - v["target"] * e.size / e.band_row["ref_size"]) < 1e-9]
    check("F34j inside the 15-20 pool every capability reads the pool's own row in every style "
          "(a none row is no requirement), never the style x size row; the portal at 12 and "
          "another content at 20 keep the style x size rows",
          ok and e12.pool_key is None and e12.band_row is not None and len(band(e12)) >= 10
          and r20.band_row is not None and len(band(r20)) >= 10,
          "; ".join(detail[:6]) or f"{len(large)} pool rows x 6 styles x 3 sizes; "
          f"band rows read at portal 12: {len(band(e12))}, roads 20: {len(band(r20))}")


def t_portal_fielded():
    """F35 — the pool-fielded gate: inside a Dragon Portal pool the
    suggestion pool holds only weapons the pool's dominant winners field
    (`pool_fielded`, pipeline/derive_portal_rows.py). Suggestions and
    generation only; a manual pick always scores."""
    import yaml
    with open(os.path.join(ROOT, "pipeline", "templates", "ancient_lands.yaml"), encoding="utf-8") as f:
        tpl = yaml.safe_load(f)
    pf = tpl.get("pool_fielded") or {}
    th = (tpl.get("fit") or {}).get("fielded") or {}
    e5 = Engine(content="ancient_lands", size=5)
    cat = e5.weapons
    check("F35a the 2-3, 4-5 and 6-7 pools each list their fielded weapons: at least 40 distinct "
          "rosters, catalog keys listed once, under the honesty gate (5 rosters, 3 guild-sets) "
          "and the signal floor (5% of the top weapon's rosters)",
          set(pf) == {"2-3", "4-5", "6-7"}
          and all(p["rosters"] >= 40 and p["weapons"] and len(set(p["weapons"])) == len(p["weapons"])
                  and all(w in cat for w in p["weapons"]) for p in pf.values())
          and th == {"min_rosters": 5, "min_guild_sets": 3, "share_of_top": 0.05},
          f"{ {k: len(p['weapons']) for k, p in pf.items()} } thresholds={th}")
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import derive_portal_rows as dpr
    large_n = ((tpl.get("fit") or {}).get("pools") or {}).get("large", {}).get("distinct", 0)
    check("F35a2 the 15-20 pool carries no fielded list until it holds 200 distinct dominant rosters "
          "(the derive step and the fold report count it against the threshold)",
          dpr.LARGE_SHAPE_AT == 200 and "large" not in dpr.FIELDED_POOLS and "15-20" not in pf,
          f"threshold={dpr.LARGE_SHAPE_AT} large pool={large_n} distinct rosters")
    classes = lambda ws: {e5.role_of(w) for w in ws}
    check("F35b every list keeps a healer, a frontline and a damage dealer (the roles the pool's rows ask for)",
          all({"healer", "frontline", "dps"} <= classes(p["weapons"]) for p in pf.values()),
          str({k: sorted(classes(p["weapons"])) for k, p in pf.items()}))
    ok, detail = True, []
    for key, size in (("2-3", 3), ("4-5", 5), ("6-7", 7)):
        listed = set(pf[key]["weapons"])
        for style in ("balanced", "brawl", "clap", "kite", "brawl_clap", "clap_kite"):
            e = Engine(content="ancient_lands", size=size, style=style)
            sp = set(e.suggest_pool())
            r = e.forge(size)
            good = (sp <= listed and bool(sp) and r["feasible"] and not r["filler"]
                    and len(r["party"]) == size and set(r["party"]) <= listed
                    and all(e.is_unfielded(w) == (w not in listed) for w in e.pool))
            ok = ok and good
            if not good:
                detail.append(f"{key}/{style}: feasible={r['feasible']} filler={r['filler']} "
                              f"outside={[cat[w]['display_name'] for w in r['party'] if w not in listed]}")
    check("F35c inside a pool, in every style, the suggestion pool sits inside the pool's list and "
          "a forged comp is feasible, complete and fields listed weapons only",
          ok, "; ".join(detail) or "3 pools x 6 styles")
    e7 = Engine(content="ancient_lands", size=7, style="clap")
    # The example is read from the generated list, never named: the list
    # grows with the pool (Claws, 1 of 162 dominant 6-7 parties when the
    # gate landed, is listed once the pool holds 284 distinct rosters).
    listed7 = set(pf["6-7"]["weapons"])
    outside = next(w for w in sorted(e7.pool) if w not in listed7)
    base = e7.forge(7)
    party = base["party"][:6]
    rec = e7.recommend(party, 1, pool=[outside])
    check("F35d a weapon outside the list is barred from suggestions only: the first catalog weapon "
          "the 6-7 list does not carry is unfielded at 7, never in the pool, and still scores as a "
          "manual pick",
          e7.is_unfielded(outside) and outside not in set(e7.suggest_pool())
          and len(rec) == 1 and rec[0]["weapon"] == outside
          and abs(e7.comp_score(party + [outside]) - e7.comp_score(party)) > 1e-9,
          f"weapon={cat[outside]['display_name']} unfielded={e7.is_unfielded(outside)} "
          f"manual={rec[0]['score'] if rec else None}")
    e10 = Engine(content="ancient_lands", size=10)
    e20 = Engine(content="ancient_lands", size=20)
    r5 = Engine(content="roads", size=5)
    # at 10+ the fielded gate every content reads (S8): balanced reads the
    # pooled band list of the killer parties of 10+
    ofl = (e5.data["composition"].get("skeleton") or {}).get("fielded") or {}

    def pooled_list(size):
        for bk, lim in (ofl.get("bands") or {}).items():
            if lim[0] <= size <= lim[1]:
                return set((ofl.get("pooled") or {}).get(bk) or [])
        return set()
    open10 = e10._unfielded == {w for w in e10.pool if w not in pooled_list(10)}
    open20 = e20._unfielded == {w for w in e20.pool if w not in pooled_list(20)}
    check("F35e outside every listed pool the pool lists gate nothing: below 10 a content without "
          "lists keeps its suggestion pool; at 10+ the portal reads the fielded gate every content "
          "reads (balanced: the pooled band list, S8)",
          not r5._unfielded and not any(r5.is_unfielded(w) for w in r5.pool)
          and open10 and open20 and bool(e10._unfielded) and bool(e20._unfielded),
          f"portal10={len(e10._unfielded)} portal20={len(e20._unfielded)} roads5={len(r5._unfielded)}")


def t_replace_options():
    """F33 (ranked alternatives to pick from): the
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


def t_gear_active_doctrine():
    """F36: the gear-active doctrine — a piece's default active is the one
    people equip (builds_index `gear_spells` votes), else the item's own
    active; never the template-weighted argmax across the tree-shared
    pool (sheets/gear/pools/)."""
    e = Engine()
    e.set_content("blackzone_roam", 20)
    g = e.gear
    # the pools compose: every cloth head now carries the Force Field
    # bundle beside its own active
    cowl = g["HEAD_CLOTH_SET2"]["loadout"]
    ai = cowl["slot_names"].index("active")
    check("F36a the tree pool composes into the item's loadout: Cleric Cowl offers Ice Block AND Force Field",
          set(cowl["slot_spells"][ai]) >= {"ICEBLOCK2", "PBAOE_KNOCKBACK"},
          str(cowl["slot_spells"][ai]))
    da = g["HEAD_CLOTH_SET2"].get("doctrine_active") or {}
    check("F36b the Cleric Cowl's pick is OBSERVED Ice Block (every recording build runs it)",
          da.get("id") == "ICEBLOCK2" and da.get("source") == "observed" and da.get("votes", 0) >= 2
          and da.get("votes") == da.get("of"), str(da))
    ex = e.gear_extra("HEAD_CLOTH_SET2")
    check("F36c the engine scores the observed active: Ice Block's tankiness, no Force Field shove",
          ex.get("tankiness", 0) > 0 and not ex.get("knockback_displace") and not ex.get("peel"),
          str(ex))
    # an item with no recording build assumes its OWN active, even where
    # the shared Force Field would score more under the template weights
    sc = g["HEAD_CLOTH_SET1"].get("doctrine_active") or {}
    ex1 = e.gear_extra("HEAD_CLOTH_SET1")
    fi = cowl["slot_spells"][ai].index("PBAOE_KNOCKBACK")
    ff = cowl["slots"][ai][fi]
    ff_eff = e._eff(ff, e._bundle_dents(ff, cowl["slot_delivery"][ai][fi]), 0.0,
                    cowl["slot_escal"][ai][fi])
    ff_val = sum(e._weights.get(c, 0.0) * v for c, v in ff_eff.items())
    own_val = sum(e._weights.get(c, 0.0) * v for c, v in ex1.items())
    check("F36d an unrecorded item ASSUMES its own active (Scholar Cowl: Energy Shield), not the "
          "higher-scoring shared Force Field",
          sc.get("source") == "assumed" and sc.get("id") == "ENERGYSHIELD2"
          and not ex1.get("knockback_displace") and ff_val > own_val,
          f"{sc} extra={ex1} force_field={ff_val:.3f} own={own_val:.3f}")
    check("F36e gear_choice_source names the rule: observed / assumed, argmax only without a stamp",
          e.gear_choice_source("HEAD_CLOTH_SET2") == "observed"
          and e.gear_choice_source("HEAD_CLOTH_SET1") == "assumed"
          and e.gear_choice_source("OFF_SHIELD") == "argmax",
          f"{e.gear_choice_source('HEAD_CLOTH_SET2')} {e.gear_choice_source('HEAD_CLOTH_SET1')} "
          f"{e.gear_choice_source('OFF_SHIELD')}")
    # the pick holds across the bands and the templates: the doctrine is
    # evidence, not a template preference
    picks = set()
    for ct, n in (("ancient_lands", 5), ("castle_outpost", 7), ("castle", 20)):
        e.set_content(ct, n)
        picks.add(e._gear_combo_slots("HEAD_PLATE_KEEPER")[e.default_gear_choice("HEAD_PLATE_KEEPER")])
    check("F36f the Judicator Helmet reads Electric Shock at 5, 7 and 20 alike (observed), never Stone Skin by weights",
          picks == {"ELECTRICSHOCK"}, str(picks))
    # fail closed: an observed or assumed active with no scored row is an
    # EMPTY bundle — the slot supplies nothing, never the next-best ability
    e.set_content("blackzone_roam", 20)
    sb = g["SHOES_PLATE_SET1"]
    sda = sb.get("doctrine_active") or {}
    sex = e.gear_extra("SHOES_PLATE_SET1")
    check("F36g an active without a scored row resolves to an empty bundle (Soldier Boots on Wanderlust "
          "supplies nothing; Rejuvenating Sprint is not credited by argmax)",
          sda.get("id") == "WANDERLUST" and sex == {}, f"{sda} extra={sex}")
    # every head / armor / shoes item carries a stamp whose id is on its menu
    stamped = [k for k, v in g.items() if v.get("slot") in ("head", "armor", "shoes")]
    bad = [k for k in stamped if not (g[k].get("doctrine_active") or {}).get("id")
           or (g[k]["doctrine_active"]["id"] not in
               g[k]["loadout"]["slot_spells"][g[k]["loadout"]["slot_names"].index("active")])]
    check("F36h every head, armor and shoes item carries a doctrine_active that resolves to a bundle",
          not bad, str(bad[:8]))


def t_empty_pool():
    """F37: a given pool is the candidate set as given, an empty one
    included, in every entry point that takes one; only pool=None reads
    the default (suggest_pool() for recommend, swap_review, forge and
    replace_options; every non-retired weapon for refine)."""
    e = Engine(content="castle_outpost", size=7, style="balanced")
    party = ["2H_LONGBOW", "MAIN_HOLYSTAFF_AVALON", "2H_MACE"]
    bad = ["2H_LONGBOW"] * 3
    rec = e.recommend(party, 4, pool=[])
    sw = e.swap_review(party, pool=[])
    sw_def = e.swap_review(party)
    ref = e.refine(bad, max_passes=2, pool=[])
    ref_d = e.refine(bad, max_passes=2, pool=[], gears=[None] * 3)
    fg = e.forge(7, locked=["2H_MACE"], pool=[])
    ro = e.replace_options(party, 0, pool=[])
    check("F37a an empty pool offers nothing: recommend no rows, swap_review "
          "every member rank 1 with no options and its own score, refine the "
          "roster unchanged on both paths, forge infeasible on the locks, "
          "replace_options no options",
          rec == []
          and all(m["rank"] == 1 and m["options"] == [] for m in sw)
          and [m["score"] for m in sw] == [m["score"] for m in sw_def]
          and ref == bad
          and ref_d == {"party": bad, "gears": [None] * 3}
          and fg["party"] == ["2H_MACE"] and not fg["feasible"]
          and ro == [],
          f"recommend={len(rec)} swap_options={sum(len(m['options']) for m in sw)} "
          f"refine={ref} forge={fg['party']}/{fg['feasible']} replace={len(ro)}")
    # rank counts every strictly better alternative in the candidate set,
    # so the whole swap_review row tells the two defaults apart; refine
    # needs rosters where a style-gated weapon (Great Holy Staff, unfit for
    # kite at the group band) wins a move the suggestion pool cannot make,
    # on the weapon-only path and on the dressed path alike
    ek = Engine(content="blackzone_roam", size=10, style="kite")
    kite_rosters = (["2H_HALBERD", "2H_DAGGERPAIR_CRYSTAL", "MAIN_SPEAR_KEEPER"],
                    ["MAIN_SCIMITAR_MORGANA", "2H_TWINSCYTHE_HELL", "2H_FROSTSTAFF_CRYSTAL"],
                    ["MAIN_FROSTSTAFF_AVALON", "2H_NATURESTAFF", "MAIN_SWORD",
                     "2H_KNUCKLES_SET2"])

    def ref_rows(dressed):
        kw = lambda p: {"gears": [None] * len(p)} if dressed else {}
        return [(ek.refine(list(p), max_passes=1, **kw(p)),
                 ek.refine(list(p), max_passes=1, pool=list(ek.pool), **kw(p)),
                 ek.refine(list(p), max_passes=1, pool=list(ek.suggest_pool()),
                           **kw(p)))
                for p in kite_rosters]
    rows_w, rows_d = ref_rows(False), ref_rows(True)
    check("F37b pool=None reads the default: recommend and swap_review the "
          "suggestion pool, refine every non-retired weapon (weapon-only and "
          "dressed paths)",
          [r["weapon"] for r in e.recommend(party, 4)]
          == [r["weapon"] for r in e.recommend(party, 4,
                                               pool=list(e.suggest_pool()))]
          and sw_def == e.swap_review(party, pool=list(e.suggest_pool()))
          and sw_def != e.swap_review(party, pool=list(e.pool))
          and all(d == full for rows in (rows_w, rows_d) for d, full, _sp in rows)
          and any(full != sp for _d, full, sp in rows_w)
          and any(full != sp for _d, full, sp in rows_d),
          f"swap ranks={[m['rank'] for m in sw_def]} refine={rows_w[0]}")


def t_short_member_lists():
    """F38: a per-member list shorter than the party reads None past its
    end (the default combo, a naked member): every reader answers exactly
    as for the explicitly padded list, which is how the JS port reads a
    missing entry; a gears tail past the party is worn by no member in the
    self-cost refund (both ports bound that loop by the party)."""
    e = Engine(content="blackzone_roam", size=20, style="clap")
    pool = sorted(e.suggest_pool())
    multi = [w for w in pool if len(e._combo_extras(w)) > 1
             and any(g for _k, g in e.kit_variants(w))]
    party, cand = multi[:3], multi[3]
    c0 = (e.default_combo(party[0]) + 1) % len(e._combo_extras(party[0]))
    kit = next(list(g) for _k, g in e.kit_variants(party[0]) if g)
    short_c, short_g = [c0], [kit]
    pad_c, pad_g = [c0, None, None], [kit, None, None]
    small = pool[::9]
    readers = {
        "comp_score": lambda c, g: e.comp_score(party, c, g),
        "max_fitness": lambda c, g: e.max_fitness(party, c, g),
        "synergy": lambda c, g: e.synergy(party, c),
        "recommend": lambda c, g: e.recommend(party, 5, small, c, g),
        "pick_report": lambda c, g: e.pick_report(party, cand, c, g),
        "explain": lambda c, g: e.explain(party, cand, c, g),
        "swap_review": lambda c, g: e.swap_review(party, 3, small, c, g),
        "comp_identity": lambda c, g: e.comp_identity(party, c, g),
        "fight_chain": lambda c, g: e.fight_chain(party, c, g, cand),
        "analyze": lambda c, g: e.analyze(party, c),
        "kill_pressure": lambda c, g: e.kill_pressure(party, c, g),
        "weaknesses": lambda c, g: e.weaknesses(party, 5, c, g),
        "uncovered_caps": lambda c, g: e.uncovered_caps(party, c, g),
        "duplicate_conflicts": lambda c, g: e.duplicate_conflicts(party, c),
    }
    bad = []
    for name, f in readers.items():
        try:
            if f(short_c, short_g) != f(pad_c, pad_g):
                bad.append(name)
        except IndexError as ex:
            bad.append(f"{name} ({ex})")
    check("F38a a per-member list shorter than the party reads as padded "
          "with None, in every reader", not bad,
          f"differ or crash: {bad}" if bad else f"{len(readers)} readers")
    demon = ["HEAD_PLATE_SET3", "ARMOR_PLATE_HELL", "SHOES_PLATE_SET1"]
    e2 = Engine(content="blackzone_roam", size=20, style="balanced")
    try:
        st = e2.party_state(["2H_CURSEDSTAFF"], None, [None, demon])
        ok, detail = st["pending"] == {}, f"pending={st['pending']}"
    except IndexError as ex:
        ok, detail = False, f"IndexError: {ex}"
    check("F38b a gears tail past the party is worn by no member in the "
          "self-cost refund", ok, detail)
    # F38c: a tail entry counts in no reader. One Demon wearer and a
    # Demon tail would read as the waived pair if the tail counted.
    one, tail = [demon], [demon, demon]
    party = ["2H_CURSEDSTAFF"]
    st1, st2 = e2.party_state(party, None, one), e2.party_state(party, None, tail)
    same = {
        "effective_supply": e2.effective_supply(party, None, tail)
        == e2.effective_supply(party, None, one),
        "comp_score": e2.comp_score(party, None, tail)
        == e2.comp_score(party, None, one),
        "waived": st2["waived"] == st1["waived"],
        "carriers": st2["carriers"] == st1["carriers"],
        "pending": st2["pending"] == st1["pending"],
        "recommend": e2.recommend(party, 5, None, None, tail)
        == e2.recommend(party, 5, None, None, one),
    }
    check("F38c a gears tail past the party counts in no reader: the "
          "waiver, the refund and the carrier quota read the party's own "
          "entries", all(same.values()),
          f"differ: {[k for k, v in same.items() if not v]}"
          if not all(same.values()) else f"waived={sorted(st2['waived'])}")


def t_dressed_nonstack():
    """F39/F40: the count-once rule (a verified non-stacking spell's
    capability keeps only the largest single contribution) holds on the
    DRESSED paths. F39: a dressed candidate duplicating the spell is paid
    synergy on the count-once weapon supply, so its pick score stays the
    exact comp_score delta — the weapon-only vector it was paid on gave a
    second Rotcaller at blackzone_roam 20 clap 0.24 the comp never had.
    F40: a dressed member's contribution is its share as worn (the kit's
    stat channel multiplies the spell's units with the rest of its
    damage), so a duplicate keeps no part of its copy, and every marginal
    and pick_report row stays exact on dressed parties, for dressed and
    naked candidates."""
    e = Engine(content="blackzone_roam", size=20, style="clap")
    carriers = [w for w in sorted(e.weapons)
                if any(e._nonstack_contrib(w, i)
                       for i in range(len(e._combo_extras(w))))]
    worst, n = 0.0, 0
    for content, size, style in (("blackzone_roam", 20, "clap"),
                                 ("castle_outpost", 7, "balanced"),
                                 ("ancient_lands", 20, "balanced"),
                                 ("roads", 20, "kite")):
        e.set_content(content, size, style)
        for a in carriers:
            for ca in range(len(e._combo_extras(a))):
                st = e.party_state([a], [ca])
                base = e.comp_score([a], [ca])
                for b in carriers:
                    sc, _df, _ds, _m, cb, _v, vg = e._eval_pick(st, b)
                    act = e.comp_score([a, b], [ca, cb], [None, vg]) - base
                    worst = max(worst, abs(sc - act))
                    n += 1
    check("F39 a dressed duplicate of a count-once spell: pick score == "
          "exact comp_score delta, synergy included (1e-9)",
          bool(carriers) and worst < 1e-9,
          f"{len(carriers)} carriers, {n} evaluations, worst {worst:.2e}")

    e = Engine(content="castle_outpost", size=7)
    kits = {w: dict(e.kit_variants(w))["v0"] for w in carriers}
    pick = None
    for w in carriers:
        ci = next(i for i in range(len(e._combo_extras(w)))
                  if e._nonstack_contrib(w, i))
        _sid, contrib = next(iter(e._nonstack_contrib(w, ci).items()))
        cap, v = next(iter(contrib.items()))
        if kits[w] and e._ns_share(v, cap, kits[w], w) > v:
            pick = (w, ci, cap, v)
            break
    w, ci, cap, v = pick
    one = e.effective_supply([w], [ci], [kits[w]])[cap]
    two = e.effective_supply([w, w], [ci, ci], [kits[w], kits[w]])[cap]
    share = e._ns_share(v, cap, kits[w], w)
    # the expected share from build_extra alone (not _ns_share, the rule
    # under test): the kit's stat channel is the ratio of the built cap to
    # the member's unmultiplied supply (weapon + the kit's flat abilities),
    # self-costs waived so a cost on the cap cannot bend the ratio
    keys = [e.gear_key(k) for k in kits[w]]
    flat = sum(e.gear_extra(k).get(cap, 0.0) for k in keys)
    built = e.build_extra(w, ci, kits[w], waive_costs=frozenset(keys))[cap]
    exp = v * built / (e.member_extra(w, ci)[cap] + flat)
    worst2, rows_worst = 0.0, 0.0
    for dressing in (True, False):
        e.set_dressing(dressing)   # False: every candidate is naked
        for a in carriers:
            ga = [kits[a]] if kits[a] else None
            ca = next(i for i in range(len(e._combo_extras(a)))
                      if e._nonstack_contrib(a, i))
            st = e.party_state([a], [ca], ga)
            base = e.comp_score([a], [ca], ga)
            for b in carriers:
                sc, d_fit, _ds, _m, cb, _v, vg = e._eval_pick(st, b)
                act = (e.comp_score([a, b], [ca, cb], (ga or [None]) + [vg])
                       - base)
                rows, _cg = e._pick_caps(st, b, cb, vg)
                worst2 = max(worst2, abs(sc - act))
                rows_worst = max(rows_worst,
                                 abs(sum(r["delta"] for r in rows) - d_fit))
    e.set_dressing(True)
    check("F40 the count-once rule reads each dressed member's share as "
          "worn: a dressed duplicate keeps no part of its copy, and pick "
          "scores and pick_report rows stay exact on a dressed party for "
          "dressed and naked candidates (1e-9)",
          abs((two - one) - (one - exp)) < 1e-9 and exp > v
          and worst2 < 1e-9 and rows_worst < 1e-9,
          f"{w} {cap}: one={one:.4f} two={two:.4f} share={share:.4f} "
          f"expected={exp:.4f} worst={worst2:.2e} rows={rows_worst:.2e}")


def t_swap_review_as_built():
    """F41 (the swap advisor reads weapon choice and reports the member as
    built): score, rank and each option's gain value every member exactly
    as _eval_pick values it into the rest (T17's identity), its own combo
    and kit re-resolved; built_score is the exact comp_score delta of the
    member in the combo and kit it wears, and each option's delta is the
    comp_score change of the swap landing in that option's combo and kit,
    the delta replace_options reports for the same build. Case: the forged
    castle_outpost 7 minus its last slot, plus a Longbow on combo 0 in its
    doctrine kit with the chest swapped to Judicator Armor."""
    e = Engine(content="castle_outpost", size=7, style="balanced")
    r = e.forge(7)
    lb = "2H_LONGBOW"
    kit = [("ARMOR_PLATE_KEEPER" if e.gear[k]["slot"] == "armor" else k)
           for k in dict(e.kit_variants(lb))["v0"]]
    party = list(r["party"][:6]) + [lb]
    combos = list(r["combos"][:6]) + [0]
    gears = [list(g) if g else None for g in r["gears"][:6]] + [kit]
    total = e.comp_score(party, combos, gears)
    m = e.swap_review(party, 3, None, combos, gears)[6]
    rest, rc, rg = party[:6], combos[:6], gears[:6]
    built = total - e.comp_score(rest, rc, rg)
    rec = e.recommend(rest, 1, [lb], rc, rg)[0]
    worst, gap_err = 0.0, 0.0
    for o in m["options"]:
        p2, c2, g2 = list(party), list(combos), list(gears)
        p2[6], c2[6], g2[6] = o["weapon"], o["combo"], (list(o["kit"]) or None)
        worst = max(worst, abs(o["delta"] - (e.comp_score(p2, c2, g2) - total)))
        gap_err = max(gap_err, abs((o["gain"] - o["delta"]) + m["build_gap"]))
    rep_err, rep_n = 0.0, 0
    for o in m["options"]:
        rep = e.replace_options(party, 6, combos, gears, 1, [o["weapon"]])
        if rep and rep[0]["combo"] == o["combo"] and rep[0]["kit"] == o["kit"]:
            rep_err = max(rep_err, abs(rep[0]["delta"] - o["delta"]))
            rep_n += 1
    fr = e.swap_review(r["party"], 3, None, r["combos"], r["gears"])
    check("F41 swap review: weapon-choice score and rank (== recommend into "
          "the rest), the member as built beside it, option deltas exact "
          "and equal to replace_options for the same build; a forged "
          "roster's members are built as valued",
          m["kit"] != kit and bool(m["options"])
          and abs(m["score"] - rec["score"]) < 1e-9 and m["kit"] == rec["kit"]
          and abs(m["built_score"] - built) < 1e-9
          and abs(m["build_gap"] - (m["score"] - built)) < 1e-9
          and worst < 1e-9 and gap_err < 1e-9 and rep_err < 1e-9
          and all(abs(x["build_gap"]) < 1e-9 for x in fr),
          f"score={m['score']:.4f} built={m['built_score']:.4f} "
          f"gap={m['build_gap']:.4f} replace_checked={rep_n}")

    # built_score is priced as a marginal on the rest's state (_as_built):
    # exact on the states where a marginal can drift from the comp_score
    # difference — Demon Armor one copy short of its offset (a pending
    # refund) and past it (waived), dressed count-once duplicates, a None,
    # an out-of-range and a negative combo (each on a member where reading
    # it as anything but the default moves the score), lists shorter than
    # the party, a naked roster
    e2 = Engine(content="blackzone_roam", size=20, style="balanced")
    r2 = e2.forge(20)
    demon = ["HEAD_PLATE_SET3", "ARMOR_PLATE_HELL", "SHOES_PLATE_SET1"]
    curse = [w for w in sorted(e2.weapons)
             if any(e2._nonstack_contrib(w, i)
                    for i in range(len(e2._combo_extras(w))))][:3]
    p, c = list(r2["party"]), list(r2["combos"])
    # the forge dresses its own Demon Armor pair: strip it, then place two
    # wearers (each one's rest one copy short) and three (each one's rest
    # at the offset)
    g = [([k for k in x if k != "ARMOR_PLATE_HELL"] or None) if x else None
         for x in r2["gears"]]
    pend = list(g)
    pend[0] = pend[1] = demon
    waived = list(g)
    waived[0] = waived[1] = waived[2] = demon
    n_of, dflt = (lambda w: len(e2._combo_extras(w))), e2.default_combo

    def moves(cc, gg, k, a):
        # combo `a` on member k scores differently from its default
        c1, c2 = list(cc), list(cc)
        c1[k], c2[k] = a, dflt(p[k])
        return abs(e2.comp_score(p, c1, gg) - e2.comp_score(p, c2, gg)) > 1e-6
    # 99: a default inside the range, so a fallback to 0 and a clamp to the
    # last combo both move the score; None: a default other than 0; -1: on
    # the naked roster (a dressed member's fit side re-reads -1 itself)
    k99 = next((k for k, w in enumerate(p) if 0 < dflt(w) < n_of(w) - 1
                and moves(c, waived, k, 0) and moves(c, waived, k, n_of(w) - 1)),
               None)
    k_none = next((k for k, w in enumerate(p) if k != k99 and dflt(w) != 0
                   and moves(c, waived, k, 0)), None)
    k_neg = next((k for k, w in enumerate(p) if dflt(w) != n_of(w) - 1
                  and moves(c, None, k, n_of(w) - 1)), None)
    c_odd, c_neg = list(c), list(c)
    if k99 is not None and k_none is not None:
        c_odd[k99], c_odd[k_none] = 99, None
    if k_neg is not None:
        c_neg[k_neg] = -1
    p_ns, c_ns, g_ns = list(p), list(c), list(g)
    for j, cw in enumerate(curse + curse[:1]):
        p_ns[5 + j] = cw
        c_ns[5 + j] = next(i for i in range(len(e2._combo_extras(cw)))
                           if e2._nonstack_contrib(cw, i))
        g_ns[5 + j] = list(dict(e2.kit_variants(cw))["v0"] or []) or None
    cases = [(p, c, pend), (p, c_odd, waived), (p_ns, c_ns, g_ns),
             (p, c[:7], pend[:9]), (p, c_neg, None)]
    worst2, n2 = 0.0, 0
    for pp, cc, gg in cases:
        total2 = e2.comp_score(pp, cc, gg)
        for mm in e2.swap_review(pp, 1, [], cc, gg):
            i = mm["index"]
            rest2 = pp[:i] + pp[i + 1:]
            rc2 = (cc[:i] + cc[i + 1:]) if cc else None
            rg2 = (gg[:i] + gg[i + 1:]) if gg else None
            worst2 = max(worst2, abs(mm["built_score"]
                                     - (total2 - e2.comp_score(rest2, rc2, rg2))))
            n2 += 1
    st_p = e2.party_state(p[1:], c[1:], pend[1:])
    st_w = e2.party_state(p[1:], c[1:], waived[1:])
    check("F41b built_score == comp_score(party) - comp_score(rest) on a "
          "pending and a waived Demon Armor, dressed count-once duplicates, "
          "odd combos, short lists and a naked roster (1e-9)",
          worst2 < 1e-9 and bool(st_p["pending"]) and bool(st_w["waived"])
          and len(curse) == 3 and None not in (k99, k_none, k_neg),
          f"{n2} members, worst {worst2:.2e}; odd combos on "
          f"{[p[k] if k is not None else None for k in (k99, k_none, k_neg)]}")


def t_kit_options_rest():
    """F42: comp-aware kit_options prices each item against the REST as
    equipped when party_combos / party_gears are given — an option's value
    is the exact fitness delta of the member joining in that item with the
    rest in its own combos and kits; omitted, the rest reads naked at
    default combos, the context the parameters replace."""
    e = Engine(content="blackzone_roam", size=20, style="clap")
    r = e.forge(20)
    k = len(r["party"]) // 2
    w, combo = r["party"][k], r["combos"][k]
    rest = r["party"][:k] + r["party"][k + 1:]
    rc = r["combos"][:k] + r["combos"][k + 1:]
    rg = r["gears"][:k] + r["gears"][k + 1:]
    ko = e.kit_options(w, combo, rest, 8, "auto", rc, rg)
    legacy = e.kit_options(w, combo, rest, 8)
    nn = [None] * len(rest)
    f_bare = e.fitness(rest + [w], rc + [combo], rg + [None])
    n_bare = e.fitness(rest + [w], nn + [combo], nn + [None])
    worst = worst_l = 0.0
    differs = False
    lv = {(s, o["gear"]): o["value"]
          for s, opts in legacy["options"].items() for o in opts}
    for slot, opts in ko["options"].items():
        for o in opts:
            exact = (e.fitness(rest + [w], rc + [combo], rg + [[o["gear"]]])
                     - f_bare)
            worst = max(worst, abs(o["value"] - exact))
            if abs(o["value"] - lv.get((slot, o["gear"]), o["value"])) > 1e-6:
                differs = True
    for slot, opts in legacy["options"].items():
        for o in opts:
            exact = (e.fitness(rest + [w], nn + [combo], nn + [[o["gear"]]])
                     - n_bare)
            worst_l = max(worst_l, abs(o["value"] - exact))
    check("F42 comp-aware kit options price items against the rest as "
          "equipped (exact fitness delta, 1e-9); without the rest's combos "
          "and kits the rest reads naked at default combos",
          bool(ko["options"]) and worst < 1e-9 and worst_l < 1e-9 and differs,
          f"{w}: worst={worst:.2e} legacy={worst_l:.2e} differs={differs}")


# ---------------------------------------------- F43 every row scores on its own spell
def t_per_spell_credit():
    """F43: every composed sheet row is credited to its OWN spell's
    bundle, and a member's capability is the largest value across its
    always-on rows and its chosen bundles — a sheet score is the weapon's
    total with that spell equipped, never a per-spell increment.
    (a) every spell a capability cites carries that capability in its own
        bundle, and the largest bundle value equals the flat capability;
    (b) Mace: Defensive Slam keeps its peel beside Guard Rune's — Charge
        Root + Defensive Slam has peel, Guard Rune + Defensive Slam reads
        the larger of the two, not their sum;
    (c) Bedrock offers Guard Rune again (its W no longer collapses into
        the E's rows);
    (d) a weapon whose own tree's pool reaches none of its menu spells
        takes the spell rows of the pools whose spells it equips (Black
        Hands: knuckles subcategory, dagger menu), never another tree's
        base-stat row."""
    e = Engine(content="castle", size=10)
    bad = []
    for w, d in e.weapons.items():
        lo = d.get("loadout") or {}
        names = lo.get("slot_names") or []
        spells = lo.get("slot_spells") or []
        slots = lo.get("slots") or []
        by_spell = {}
        for oi, n in enumerate(names):
            for sp, b in zip(spells[oi], slots[oi]):
                for c, v in b.items():
                    key = (sp, c)
                    by_spell[key] = max(by_spell.get(key, 0), v)
        for cap, evs in (d.get("evidence") or {}).items():
            top = max([v for (sp, c), v in by_spell.items() if c == cap]
                      + [lo.get("always", {}).get(cap, 0)])
            if top != d["capabilities"].get(cap):
                bad.append(f"{w}.{cap} top {top} != flat {d['capabilities'].get(cap)}")
            for sp in evs:
                if sp in ("WEAPON_STATS",):
                    continue
                if any(sp in s for s in spells) and (sp, cap) not in by_spell:
                    bad.append(f"{w}.{cap} missing from {sp}'s bundle")
    check("F43a every cited spell carries its capability in its own bundle; "
          "the largest bundle value is the flat capability",
          not bad, "; ".join(bad[:4]))

    lo = e.weapons["MAIN_MACE"]["loadout"]
    names, spells = lo["slot_names"], lo["slot_spells"]

    def combo_for(picks):
        return e.combo_from_picks("MAIN_MACE", picks)

    q, wslot = "q", "w"
    c_root = combo_for({q: "DEFENSIVESLAM", wslot: "CHARGE_ROOT"})
    c_rune = combo_for({q: "DEFENSIVESLAM", wslot: "GUARDRUNE"})
    raw_root = e._raw_member_caps("MAIN_MACE", c_root)
    raw_rune = e._raw_member_caps("MAIN_MACE", c_rune)
    peel_slam = next(b.get("peel", 0) for sp, b in zip(spells[names.index(q)], lo["slots"][names.index(q)])
                     if sp == "DEFENSIVESLAM")
    peel_rune = next(b.get("peel", 0) for sp, b in zip(spells[names.index(wslot)], lo["slots"][names.index(wslot)])
                     if sp == "GUARDRUNE")
    check("F43b Mace: Defensive Slam keeps its peel beside Guard Rune's; the "
          "pair reads the larger, never the sum",
          peel_slam > 0 and raw_root.get("peel") == peel_slam
          and raw_rune.get("peel") == max(peel_slam, peel_rune) < peel_slam + peel_rune,
          f"slam={peel_slam} rune={peel_rune} root+slam={raw_root.get('peel')} "
          f"rune+slam={raw_rune.get('peel')}")

    blo = e.weapons["MAIN_ROCKMACE_KEEPER"]["loadout"]
    w_spells = blo["slot_spells"][blo["slot_names"].index("w")]
    check("F43c Bedrock offers Guard Rune as a W option again",
          "GUARDRUNE" in w_spells, f"w options {w_spells}")

    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import sheets_lib
    lines = sheets_lib.load_weapon_lines()
    pools = sheets_lib.load_pools()
    bh = sheets_lib.pool_rows_for(lines["2H_IRONGAUNTLETS_HELL"], pools)
    dagger_spell_rows = [r for r in pools.get("dagger", [])
                         if r.get("evidence") != "WEAPON_STATS"]
    mace = sheets_lib.pool_rows_for(lines["MAIN_MACE"], pools)
    # a base-stat row of the borrowed tree stays with that tree: a synthetic
    # WEAPON_STATS row on a copy of the dagger pool never reaches Black Hands
    stat_row = {"cap": "sustained_dps", "score": 2, "evidence": "WEAPON_STATS"}
    pools_x = dict(pools, dagger=list(pools.get("dagger", [])) + [stat_row])
    bh_x = sheets_lib.pool_rows_for(lines["2H_IRONGAUNTLETS_HELL"], pools_x)
    dagger_x = sheets_lib.pool_rows_for(lines["MAIN_DAGGER"], pools_x)
    check("F43d Black Hands takes the dagger pool's spell rows (its menu) and "
          "no base-stat row of another tree; an ordinary weapon reads its own "
          "tree pool alone",
          all(r in bh for r in dagger_spell_rows)
          and stat_row not in bh_x and stat_row in dagger_x
          and mace == pools.get("mace", []),
          f"black hands rows={len(bh)} dagger spell rows={len(dagger_spell_rows)} "
          f"stat row borrowed={stat_row in bh_x}")


def t_nonstack_marginal():
    """F43e: the count-once share of a non-stacking spell is what it adds to
    the member's total (the max merge): Cursed Staff carries no other
    sustained_dps source (share = the bundle value); Shadowcaller's E row
    equals its Vile Curse (share zero); a synthetic second source above the
    curse takes the share to zero, one below it leaves the excess."""
    e = Engine(content="castle", size=10)
    w = "MAIN_CURSEDSTAFF"
    combo = e.default_combo(w)
    base = e._nonstack_contrib(w, combo)
    lo = e.weapons[w]["loadout"]
    always_eff, slots_eff = e._loadout_eff(w)
    curse = next((slots_eff[oi][ci].get("sustained_dps", 0.0)
                  for oi, ci in e.combo_choices(w, combo)
                  if lo["slot_spells"][oi][ci] == "CURSEDOT"), 0.0)
    ok_base = abs(base.get("CURSEDOT", {}).get("sustained_dps", 0.0) - curse) < 1e-12
    saved = dict(lo.get("always") or {})
    try:
        lo["always"] = dict(saved, sustained_dps=99)
        e._extras_cache.clear(); e._ns_cache.clear(); e._pre_cache.clear()
        dominated = e._nonstack_contrib(w, combo)
        lo["always"] = dict(saved, sustained_dps=1)
        e._extras_cache.clear(); e._ns_cache.clear(); e._pre_cache.clear()
        below = e._nonstack_contrib(w, combo)
    finally:
        lo["always"] = saved
        e._extras_cache.clear(); e._ns_cache.clear(); e._pre_cache.clear()
    sc = "MAIN_CURSEDSTAFF_AVALON"
    sc_share = e._nonstack_contrib(sc, e.combo_from_picks(sc, {"q": "CURSEDOT"}))
    check("F43e count-once share = the spell's excess over the member's other "
          "sources (the bundle value on Cursed Staff; zero on Shadowcaller, whose "
          "E row equals the curse; zero when dominated; the excess when another "
          "source is lower)",
          ok_base and not dominated.get("CURSEDOT") and not sc_share.get("CURSEDOT")
          and 0.0 < below.get("CURSEDOT", {}).get("sustained_dps", 0.0) < curse,
          f"curse={curse:.4f} base={base} shadowcaller={sc_share} "
          f"dominated={dominated} below={below}")


def t_floor_zeroed_gain():
    """F44: a hard-floored capability a kit zeroes (a self-cost) while the
    weapon still supplies it keeps its floor lift in the pick score. The
    floor reads the weapon basis, so the dressed marginal walks that basis
    even where the dressed gain is zero; the why rows carry the lift as a
    zero-gain row. No shipped kit zeroes a floored gain, so the case is
    forced on a scratch dataset in which every gear piece costs its wearer
    the template's floored capabilities (before the fix the tankiness case
    read 4.95 under the comp_score delta)."""
    import json, tempfile
    from engine import DATASET
    probe = Engine(content="castle_outpost", size=7)
    floored = sorted(c for c, row in probe._cap_tab.items() if row[4] is not None)
    cases = []
    for cap in floored:
        cand = next((w for w in sorted(probe.weapons)
                     if not probe.weapons[w].get("removed")
                     and dict(probe.kit_variants(w)).get("v0")
                     and all(x.get(cap, 0.0) > 0 for x in probe._combo_extras(w))),
                    None)
        if cand:
            cases.append((cap, cand))
    with open(DATASET, encoding="utf-8") as f:
        data = json.load(f)
    for g in data["gear"].values():
        costs = dict(g.get("self_costs") or {})
        for cap in floored:
            costs[cap] = 99
        g["self_costs"] = costs
    tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8")
    worst, seen = 0.0, []
    try:
        json.dump(data, tf)
        tf.close()
        e = Engine(tf.name, content="castle_outpost", size=7)
        state = e.party_state([], None, None)
        for cap, cand in cases:
            score, d_fit, _ds, _m, combo, _v, vg = e._eval_pick(state, cand)
            actual = e.comp_score([cand], [combo], [vg]) - e.comp_score([])
            built = e._as_built(state, cand, combo, vg)
            rows, _cg = e._pick_caps(state, cand, combo, vg)
            row = next((r for r in rows if r["cap"] == cap), None)
            worst = max(worst, abs(score - actual), abs(built - actual),
                        abs(sum(r["delta"] for r in rows) - d_fit))
            seen.append((cap, cand, e.build_extra(cand, combo, vg).get(cap, 0.0),
                         row["floor_lift"] if row else None))
    finally:
        os.unlink(tf.name)
    check("F44 a floored capability a kit zeroes keeps its floor lift: the "
          "pick score, the as-built score and the why rows equal the "
          "comp_score delta (scratch dataset, 1e-9)",
          len(cases) >= 1 and worst < 1e-9
          and all(d == 0.0 and fl is not None and fl > 0 for _c, _w, d, fl in seen),
          f"worst |diff| = {worst:.2e}; (cap, candidate, dressed gain, floor lift) {seen}")


def t_top_n_none():
    """F45: an explicit top_n of None reads as each ranked list's default
    (recommend 4, swap_review 3, weaknesses 3, kit_options 3,
    replace_options 5), as pool=None reads as the suggestion pool; the
    browser port reads null the same way (the parity test pins it)."""
    e = Engine(content="castle_outpost", size=7)
    party = ["2H_HAMMER_AVALON", "2H_MACE", "2H_LONGBOW"]
    names = lambda rows: [r["weapon"] for r in rows]
    rec = names(e.recommend(party, None))
    swap = [names(m["options"]) for m in e.swap_review(party, None)]
    weak = [g["cap"] for g in e.weaknesses(party, None)]
    kit = e.kit_options(party[0], None, None, None)
    rep = names(e.replace_options(party, 0, None, None, None))
    check("F45 top_n None reads as the default in recommend, swap_review, "
          "weaknesses, kit_options and replace_options",
          rec == names(e.recommend(party)) and len(rec) == 4
          and swap == [names(m["options"]) for m in e.swap_review(party)]
          and weak == [g["cap"] for g in e.weaknesses(party)] and len(weak) == 3
          and kit == e.kit_options(party[0])
          and rep == names(e.replace_options(party, 0)),
          f"recommend={rec} weaknesses={weak} replace={rep}")


def t_refine_as_built():
    """F46: the forge's refinement pass and replace_options price a slot's
    member on the rest's state (_as_built), the exact comp_score(party) -
    comp_score(rest) the two full comp_scores computed before: every slot
    of a dressed forged roster agrees at 1e-9."""
    worst, n = 0.0, 0
    for content, size, style in (("castle_outpost", 7, "balanced"),
                                 ("blackzone_roam", 12, "clap")):
        e = Engine(content=content, size=size, style=style)
        r = e.forge(size)
        party, combos, gears = r["party"], r["combos"], r["gears"]
        full = e.comp_score(party, combos, gears)
        for i in range(len(party)):
            rest = party[:i] + party[i + 1:]
            rest_c = combos[:i] + combos[i + 1:]
            rest_g = gears[:i] + gears[i + 1:]
            state = e.party_state(rest, rest_c, rest_g)
            built = e._as_built(state, party[i], combos[i], gears[i])
            worst = max(worst, abs(built - (full - e.comp_score(rest, rest_c, rest_g))))
            n += 1
    check("F46 a slot's member priced on the rest's state equals "
          "comp_score(party) - comp_score(rest) on dressed forged rosters (1e-9)",
          n > 0 and worst < 1e-9, f"{n} slots, worst |diff| = {worst:.2e}")


def t_party_cap():
    """F47: one party caps at 20. The game seats at most 20 players in a
    party and a zerg is forged party by party, so the forge (its refresh
    too), replace_options and refine refuse a party past 20 with the cap
    message before any search; a manual roster of any size still scores
    and reads at its size (judged at roster size)."""
    from engine import PARTY_CAP, party_cap_message

    def refusal(fn):
        try:
            fn()
        except ValueError as err:
            return str(err)
        return None

    e = Engine(content="castle", size=25, style="clap")
    party25 = (["MAIN_HOLYSTAFF_AVALON"] * 5 + ["2H_MACE"] * 5
               + ["2H_LONGBOW"] * 15)
    party21 = party25[:21]
    got = {"forge 21": refusal(lambda: e.forge(21)),
           "refresh 21": refusal(lambda: e.forge(21, avoid=[party21])),
           "locked 21": refusal(lambda: e.forge(20, locked=party21)),
           "replace 21": refusal(lambda: e.replace_options(party21, 0)),
           "refine 21": refusal(lambda: e.refine(party21, max_passes=1, pool=[]))}
    forge25 = refusal(lambda: e.forge(25))
    refused = (PARTY_CAP == 20
               and all(v == party_cap_message(21) for v in got.values())
               and forge25 == party_cap_message(25)
               and "20 players" in forge25)
    s25 = e.comp_score(party25)
    reads = (s25 == s25 and s25 != 0.0 and e.fitness(party25) > 0
             and len(e.recommend(party25, 3)) == 3)
    check("F47 one party caps at 20: forge, refresh, a lock list, "
          "replace_options and refine refuse a party past 20 with the cap "
          "message; a 25-member manual roster still scores and reads",
          refused and reads,
          f"refusals={got} forge25={forge25!r} score25={s25:.3f}")

if __name__ == "__main__":
    t_gear_active_doctrine()
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
    t_portal_rows()
    t_portal_fielded()
    t_empty_pool()
    t_short_member_lists()
    t_dressed_nonstack()
    t_swap_review_as_built()
    t_kit_options_rest()
    t_per_spell_credit()
    t_nonstack_marginal()
    t_floor_zeroed_gain()
    t_top_n_none()
    t_refine_as_built()
    t_party_cap()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} forge regression tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
