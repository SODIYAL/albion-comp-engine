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
  F14 cost gate (owner ruling 2026-08-23): crystal weapons leave suggestions
      and generation below 30 players; manual/locked picks score, flagged
      off_budget; avalonian is never gated.
  F15 primary-heal minimum (owner ruling 2026-08-23): a hybrid healer can
      never be the comp's sole healing foundation — every forge fields the
      band's full-healer minimum in addition to the healer role band.
  F16 style role bands (owner ruling 2026-08-23): the declared style
      overrides the brawl-calibrated bands — at 20, brawl 3-4 healers,
      clap 2-3, kite exactly 2; kite at 7 runs 1.

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
    e = Engine(content="territory_defense", size=10)
    t = e.target("heal_sustain")             # 6.7 * 10/20 = 3.35
    raw_floor = e.floors["heal_sustain"]["floor_units"]   # 4.2 absolute
    clamped = e._floors_eff["heal_sustain"]
    at_target_ok = not e.floor_armed("heal_sustain", t)
    below_armed = e.floor_armed("heal_sustain", 0.0)
    check("F7 hard floor clamps to the scaled target",
          raw_floor > t and clamped == t and at_target_ok and below_armed,
          f"target {t:.2f}, raw floor {raw_floor}, effective {clamped:.2f}")


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
    """F14 (owner ruling 2026-08-23, forge-quality blind round): crystal
    weapons are a rich-group choice, not a default — "I wouldn't run it
    unless there were 30+ people involved". Barred from suggestions and
    generation below 30 exactly like an exclusion; manual and locked picks
    still score, flagged off_budget; avalonian is never gated (Hand of
    Justice at 7 is fine by the same ruling)."""
    CRYSTAL = ("2H_HOLYSTAFF_CRYSTAL", "MAIN_NATURESTAFF_CRYSTAL")
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    barred = all(w not in set(e.suggest_pool()) for w in CRYSTAL)
    not_rec = all(r["weapon"] not in CRYSTAL
                  for r in e.recommend([], top_n=300))
    r = e.forge(20)
    forge_clean = all(e.weapons[w].get("cost_tier") != "crystal"
                      for w in r["party"])
    party = ["2H_HOLYSTAFF_CRYSTAL", "2H_MACE", "MAIN_HOLYSTAFF_AVALON"]
    score = e.comp_score(party)
    scoreable = score == score and score != 0.0
    review = e.swap_review(party)
    flagged = review[0]["off_budget"] and not review[1]["off_budget"]
    locked = e.forge(20, locked=["2H_HOLYSTAFF_CRYSTAL"])
    locked_kept = locked["party"][0] == "2H_HOLYSTAFF_CRYSTAL"
    e30 = Engine(content="castle", size=30)
    open30 = all(w in set(e30.suggest_pool()) for w in CRYSTAL)
    avalon_open = "2H_HAMMER_AVALON" in set(
        Engine(content="castle_outpost", size=7).suggest_pool())
    check("F14 cost gate: crystal barred below 30 (suggest+forge), scores "
          "when manual/locked, flagged off_budget; open at 30; avalonian free",
          barred and not_rec and forge_clean and scoreable and flagged
          and locked_kept and open30 and avalon_open,
          f"score={score:.3f}, off_budget={[m['off_budget'] for m in review]}, "
          f"open30={open30}, avalon_open={avalon_open}")


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
    """F16 (owner ruling 2026-08-23): style-aware role bands — "having 5
    healers in a party of 20 feels like too much, especially in clap and
    kite". At 20: brawl 3-4 healers (frontline capped at blap's 5), clap
    2-3, kite exactly 2; kite at 7 runs a single healer."""
    ok = True
    lines = []
    for style, lo, hi in (("brawl", 3, 4), ("clap", 2, 3), ("kite", 2, 2),
                          ("clap_kite", 3, 4)):
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
    if kite7 != 1 or not rk["feasible"]:
        ok = False
        lines.append(f"kite@7 healers {kite7}")
    check("F16 style bands at 20: brawl 3-4h/<=5f, clap 2-3h, kite 2h, "
          "clap_kite 3-4h (round 5); kite@7 1h", ok, "; ".join(lines))


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
    d_fit = e._marg_fit_from(st["s"], extra)
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
    t_generation_fit()
    t_dup_and_clump()
    t_curse_slot_earned()
    t_resil_pen()
    t_need_profiles()
    t_dressed_state()
    t_kit_variants()
    t_dressed_eval()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} forge regression tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
