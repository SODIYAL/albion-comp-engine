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
                    score, _df, _ds, _meta, combo = e._eval_pick(state, cand)
                    actual = e.comp_score(party + [cand], combos + [combo]) - base
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
                problems.append(f"unheld negative filler {r['filler']}")
            if [tuple(x) for x in (r2["party"],)] != [tuple(party)]:
                problems.append("nondeterministic")
            hit = [w for w in party if w in EXCLUDED_TRIO]
            if hit:
                problems.append(f"excluded weapon {hit}")
            roles = {}
            for w in party:
                roles[e.role_of(w)] = roles.get(e.role_of(w), 0) + 1
            if not (2 <= roles.get("healer", 0) <= 3):
                problems.append(f"healers {roles.get('healer', 0)}")
            if not (2 <= roles.get("frontline", 0) <= 5):
                problems.append(f"frontline {roles.get('frontline', 0)}")
            if roles.get("support", 0) > 4:
                problems.append(f"support {roles.get('support', 0)}")
            core = sum(1 for w in party if w in e.pred_members.get("ranged_aoe_core", ()))
            if core < 2:
                problems.append(f"ranged core {core}")
            counts = {}
            for w in party:
                counts[w] = counts.get(w, 0) + 1
            over = {w: c for w, c in counts.items() if c > e._dup_gen_max(w)}
            if over:
                problems.append(f"copy limit {over}")
            # every held slot must genuinely be constraint-mandated
            for i in r["held"]:
                sub = party[:i] + party[i + 1:]
                _c, rr, pp, _g = e._forge_counts(sub)
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
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} forge regression tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
