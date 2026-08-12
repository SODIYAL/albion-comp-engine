"""
Throwaway prototype of the Albion composition recommendation engine.
Purpose: validate the CORE HYPOTHESIS of the design doc before building anything —
that capability vectors + concave utility curves + marginal-gain scoring produce
recommendations an experienced player would agree with, using only ~15 hand-scored
weapons and 1 content template.

This is test infrastructure, not product code. If these golden cases fail and can't
be fixed by tuning, the model design is wrong and the project should be rethought.

Run: python3 prototype_engine.py
"""

# ---------------------------------------------------------------- capability data
# Scores 0-3, per design doc §2.3 (illustrative curation, default kits assumed)

WEAPONS = {
    # CURATION FIX (user review 2026-08-12): bow-line knockback (Frost Shot W) is a
    # SELF-knockback — repositioning for the user, not enemy displacement — and is
    # not part of the standard group-content kit anyway. Removed knockback_displace.
    # Lesson: displacement capabilities must be tagged self- vs enemy-directed.
    "Longbow":       {"burst_aoe": 2, "sustained_dps": 2, "resist_shred": 2,
                      "zone_control": 1, "catch": 1},
    "Witchwork":     {"burst_aoe": 2, "clump_create": 2, "energy_drain": 2,
                      "sustained_dps": 2, "heal_reduction": 1, "zone_control": 1},
    "Permafrost":    {"burst_aoe": 3, "zone_control": 3, "slow": 2,
                      "clump_create": 2, "root": 1, "mobility": 1, "tankiness": 1},
    "Hallowfall":    {"heal_burst": 3, "heal_sustain": 2, "mobility": 2,
                      "cleanse": 2, "self_sustain": 2, "buff_allies": 1},
    "Great Holy":    {"heal_burst": 3, "heal_sustain": 3, "cleanse": 2, "buff_allies": 1},
    "Blight Staff":  {"heal_sustain": 3, "heal_burst": 1, "sustained_dps": 1,
                      "mobility": 1, "cleanse": 1},
    # Mace-line sheets corrected against wiki ability lists (2026-08-12):
    # Heavy Mace E = Battle Howl (AoE PURGE + SILENCE — purge is inherent to E,
    # not a W choice as previously guessed). Peel evidence: Battle Howl + Guard
    # Rune (W: ally stun/knockback immunity). Engage evidence: Snare Charge (W).
    "Heavy Mace":    {"tankiness": 3, "peel": 3, "silence": 3, "purge": 3,
                      "engage": 2, "zone_control": 2, "slow": 1, "sustained_dps": 1},
    "Great Hammer":  {"tankiness": 2, "engage": 3, "clump_create": 3, "stun": 2,
                      "zone_control": 2, "peel": 1},
    # CURATION FIX (user review 2026-08-12): 1H Mace has NO purge — nothing in the
    # mace Q/W list or its E (Deep Leap) removes buffs. Previous sheet invented it.
    # Deep Leap = leap + stun (mobility/engage bruiser per patch notes). Root via
    # Snare Charge (W). Peel via Guard Rune (W).
    "1H Mace":       {"tankiness": 2, "peel": 2, "root": 1, "engage": 2,
                      "stun": 2, "mobility": 2, "zone_control": 1, "sustained_dps": 1},
    "Grovekeeper":   {"tankiness": 2, "engage": 3, "stun": 2, "clump_create": 2, "peel": 1},
    "Dagger Pair":   {"burst_st": 3, "execute": 2, "sustained_dps": 2, "mobility": 1},
    "Bloodletter":   {"mobility": 3, "execute": 2, "burst_st": 2, "catch": 2, "disengage": 2},
    "Spirit Hunter": {"heal_reduction": 3, "sustained_dps": 2, "burst_aoe": 1, "buff_allies": 1},
}

HEALERS = {"Hallowfall", "Great Holy", "Blight Staff"}
FRONTLINE = {"Heavy Mace", "Great Hammer", "1H Mace", "Grovekeeper"}
PURE_DPS = {"Longbow", "Witchwork", "Permafrost", "Dagger Pair", "Bloodletter", "Spirit Hunter"}

# ------------------------------------------------------- content template (size 7)
# target = units needed across party; weight = importance; soft_cap = overstack point
CASTLE_OUTPOST_7 = {
    "heal_sustain":       (3.0, 10, 5.0),
    "heal_burst":         (2.0,  6, 4.0),
    "tankiness":          (4.0,  9, 7.0),
    "peel":               (3.0,  8, 6.0),
    "burst_aoe":          (5.0,  8, 9.0),
    "clump_create":       (2.0,  7, 4.0),
    "engage":             (2.0,  7, 5.0),
    "purge":              (2.0,  6, 4.0),
    "heal_reduction":     (1.0,  6, 3.0),
    "resist_shred":       (2.0,  5, 4.0),
    "cleanse":            (1.0,  5, 3.0),
    "disengage":          (1.0,  4, 3.0),
    "zone_control":       (3.0,  4, 7.0),
    "silence":            (1.0,  4, 3.0),
    "stun":               (2.0,  4, 5.0),
    "sustained_dps":      (3.0,  5, 7.0),
    "mobility":           (2.0,  3, 6.0),
}

# HARD FLOORS (design doc §3.1): capabilities where zero/near-zero supply is
# catastrophic, not just suboptimal. (min_party_size, floor_units, penalty_mult)
# First prototype run omitted these -> breadth weapons out-ranked healers. They
# are load-bearing, not optional.
HARD_FLOORS = {
    "heal_sustain": (4, 2.0, 1.5),   # party of 4+ with <2 units of healing: crippled
    "tankiness":    (5, 2.0, 1.0),   # party of 5+ with no frontline: crippled
}

# capability-level synergy pairs (design doc §4.2.1)
SYNERGY_PAIRS = [("clump_create", "burst_aoe", 1.5),
                 ("engage", "catch", 0.8),
                 ("resist_shred", "burst_st", 0.8),
                 ("heal_reduction", "sustained_dps", 0.8)]

# tiny meta prior (design doc §4.1): guards against on-paper-fits that nobody plays
META_PRIOR = {"Hallowfall": 1.0, "Heavy Mace": 1.0, "Great Hammer": 0.8,
              "Permafrost": 0.8, "Great Holy": 0.6, "Longbow": 0.6, "1H Mace": 0.6}

GAMMA = 0.7
ALPHA, BETA, DELTA = 0.55, 0.20, 0.15   # marginal gain, synergy, meta

# ------------------------------------------------------------------ engine core

def supply(party):
    s = {}
    for w in party:
        for cap, v in WEAPONS[w].items():
            s[cap] = s.get(cap, 0) + v
    return s

TARGET_SIZE = 7   # floors keyed to the size being built toward, not current count

def fitness(party, template):
    s = supply(party)
    total = 0.0
    for cap, (target, weight, soft_cap) in template.items():
        have = s.get(cap, 0.0)
        total += weight * min(1.0, have / target) ** GAMMA
        if have > soft_cap:                          # overstack penalty
            total -= 0.5 * weight * (have - soft_cap) / target
        floor = HARD_FLOORS.get(cap)
        if floor:
            min_n, floor_units, mult = floor
            if TARGET_SIZE >= min_n and have < floor_units:
                total -= mult * weight * (floor_units - have) / floor_units
    return total

def synergy_score(party, template):
    s = supply(party)
    return sum(b * min(s.get(a, 0), s.get(c, 0)) for a, c, b in SYNERGY_PAIRS)

def explain(party, candidate, template):
    """Per-capability delta terms — these ARE the 'why' text."""
    base, s = fitness(party, template), supply(party)
    terms = []
    for cap, (target, weight, soft_cap) in template.items():
        gain = WEAPONS[candidate].get(cap, 0)
        if not gain:
            continue
        have = s.get(cap, 0.0)
        d = weight * (min(1.0, (have + gain) / target) ** GAMMA
                      - min(1.0, have / target) ** GAMMA)
        floor = HARD_FLOORS.get(cap)
        if floor:
            min_n, floor_units, mult = floor
            if TARGET_SIZE >= min_n:
                pen_before = mult * weight * max(0, floor_units - have) / floor_units
                pen_after = mult * weight * max(0, floor_units - have - gain) / floor_units
                d += pen_before - pen_after   # credit for lifting a critical floor
        if d > 0.05:
            terms.append((round(d, 2), cap, have, have + gain))
    return sorted(terms, reverse=True)

def recommend(party, template, top_n=4):
    scored = []
    for w in WEAPONS:
        d_fit = fitness(party + [w], template) - fitness(party, template)
        d_syn = synergy_score(party + [w], template) - synergy_score(party, template)
        score = ALPHA * d_fit + BETA * d_syn + DELTA * META_PRIOR.get(w, 0.0)
        scored.append((score, w))
    return sorted(scored, reverse=True)[:top_n]

def weaknesses(party, template, top_n=3):
    s = supply(party)
    gaps = [(weight * (1 - min(1.0, s.get(cap, 0) / target) ** GAMMA), cap)
            for cap, (target, weight, _) in template.items()]
    return sorted(gaps, reverse=True)[:top_n]

def uncovered_caps(party, template):
    s = supply(party)
    return [cap for cap, (target, weight, _) in template.items()
            if weight >= 5 and s.get(cap, 0) / target < 0.5]

# ------------------------------------------------------------------ golden tests

def run_tests():
    T = CASTLE_OUTPOST_7
    results = []

    def check(name, cond, detail):
        results.append((name, bool(cond), detail))

    # T1 — the user's worked example: 3 DPS -> must recommend a healer
    party = ["Longbow", "Witchwork", "Permafrost"]
    recs = recommend(party, T)
    top = recs[0][1]
    check("T1  3-DPS party -> top rec is a healer",
          top in HEALERS, f"top4={[w for _, w in recs]}")
    check("T1b weaknesses lead with healing",
          weaknesses(party, T)[0][1] in ("heal_sustain", "heal_burst"),
          f"weaknesses={[c for _, c in weaknesses(party, T)]}")

    # T2 — after the healer joins -> must flip to frontline/peel
    party2 = party + [recs[0][1]]
    recs2 = recommend(party2, T)
    check("T2  +healer -> top rec is frontline",
          recs2[0][1] in FRONTLINE, f"top4={[w for _, w in recs2]}")

    # T3 — empty party -> first pick must not be pure DPS
    recs3 = recommend([], T)
    check("T3  empty party -> first pick not pure DPS",
          recs3[0][1] not in PURE_DPS, f"top4={[w for _, w in recs3]}")

    # T4 — party already saturated with healing -> no third healer in top recs
    party4 = ["Hallowfall", "Great Holy", "Heavy Mace", "Permafrost"]
    recs4 = recommend(party4, T)
    check("T4  2 healers in 4 -> no healer in top-3 recs",
          all(w not in HEALERS for _, w in recs4[:3]), f"top4={[w for _, w in recs4]}")

    # T5 — 6-DPS party, last slot -> healer + lookahead flag
    party5 = ["Longbow", "Longbow", "Witchwork", "Permafrost", "Dagger Pair", "Bloodletter"]
    recs5 = recommend(party5, T)
    unc = uncovered_caps(party5, T)
    check("T5  6-DPS last slot -> recommends healer",
          recs5[0][1] in HEALERS, f"top4={[w for _, w in recs5]}")
    check("T5b lookahead flags >=3 uncovered important caps (greedy trap)",
          len(unc) >= 3, f"uncovered={unc}")

    # T6 — discrimination: known-good meta comp must outscore a troll comp
    meta7 = ["Heavy Mace", "Great Hammer", "Hallowfall", "Great Holy",
             "Permafrost", "Longbow", "Witchwork"]
    troll7 = ["Longbow", "Longbow", "Longbow", "Dagger Pair", "Bloodletter",
              "Witchwork", "Permafrost"]
    f_meta, f_troll = fitness(meta7, T), fitness(troll7, T)
    check("T6  meta comp outscores troll comp by >25%",
          f_meta > 1.25 * f_troll, f"meta={f_meta:.1f} troll={f_troll:.1f}")

    # T7 — explainability: reason terms for the T1 rec must lead with healing
    terms = explain(party, recs[0][1], T)
    check("T7  top reason term for T1 rec is a heal capability",
          terms and terms[0][1] in ("heal_sustain", "heal_burst"),
          f"terms={terms[:3]}")

    # ---- report
    print("=" * 74)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL':4}  {name}\n      {detail}")
    print("=" * 74)
    print(f"{passed}/{len(results)} golden tests passed")

    # ---- show the generated explanation for the worked example (qualitative)
    print("\nWorked example — party [Longbow, Witchwork, Permafrost], Castle Outpost 7:")
    print(f"  Recommended: {recs[0][1]}   alternatives: {[w for _, w in recs[1:]]}")
    print("  Why (auto-generated from delta terms):")
    for d, cap, before, after in explain(party, recs[0][1], T)[:4]:
        print(f"    +{d:5.2f}  {cap}: {before:.0f} -> {after:.0f} (target {T[cap][0]:.0f})")
    return passed, len(results)


if __name__ == "__main__":
    run_tests()
