#!/usr/bin/env python3
"""
Composition scoring engine (design doc §3.2, §4.1).

Consumes the built dataset (pipeline/out/dataset-latest.json) — never hardcoded
capability numbers. This is the graduation of tests/prototype_engine.py from a
throwaway with inline dicts into the real engine reading curated data.

The math is unchanged from the prototype that passed 9/9:
    U_c(s)   = weight * min(1, s/target)^gamma      concave utility
             - 0.5 * weight * (s - soft_cap)/target  over-stack penalty
             - mult * weight * (floor - s)/floor     hard-floor penalty
    fitness  = sum over capabilities
    score(w) = alpha*dFitness + beta*dSynergy + delta*metaPrior

Party members are weapon unique_names (e.g. "2H_MACE"), matching the dataset.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, os.pardir, "pipeline", "out", "dataset-latest.json")

# Mechanics-affected capability families (MECHANICS_TODO.md, 2026-08-13):
# AoE Escalation multiplies AoE damage effectiveness by targets hit;
# Focus Fire (Resilience) cuts focused single-target damage by attackers-on-
# target. sustained_dps is deliberately in NEITHER family — brawl sustained
# damage is spread across targets, so neither curve cleanly applies.
AOE_ESCALATION_CAPS = ("burst_aoe",)
RESILIENCE_CAPS = ("burst_st", "execute")


class Engine:
    def __init__(self, dataset_path=DATASET, content="castle_outpost", size=7,
                 style="balanced"):
        with open(dataset_path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.weapons = self.data["weapons"]
        self.scoring = self.data["scoring"]
        w = self.scoring["weights"]
        self.alpha, self.beta = w["alpha"], w["beta"]
        self.delta, self.gamma = w["delta"], w["gamma"]
        self.meta_prior = self.scoring.get("meta_prior", {}) or {}
        # meta_prior is either a FLAT {weapon: value} map, or SIZE-BUCKETED
        # {small|mid|large: {weapon: value}} (usage-derived, Q17). Bucketed is
        # detected by its top-level keys; the value for a weapon is then chosen
        # by the current party size — the same buckets sample_battles.py uses.
        self.meta_bucketed = bool(self.meta_prior) and \
            set(self.meta_prior) <= {"small", "mid", "large"}
        self.synergies = [(s["a"], s["b"], s["bonus"])
                          for s in self.scoring.get("capability_synergies", [])]
        self.mechanics = self.data.get("mechanics", {}) or {}
        self.set_content(content, size, style)

    # ---------------------------------------------------------------- context
    def set_content(self, content, size, style="balanced"):
        self.template = self.data["templates"][content]
        self.content = content
        self.size = size
        self.reqs = self.template["requirements"]
        self.floors = self.template.get("hard_floors", {}) or {}
        self.base_size = self.template.get("base_size", size)
        # Playstyle overlay (templates/styles.yaml): multiplies capability
        # WEIGHTS only. Targets/soft caps are content facts; hard floors stay
        # on the base weight — a kite comp still needs its healers.
        self.style = style
        styles = self.data.get("styles", {}) or {}
        self.style_mults = (styles.get(style, {}) or {}).get("multipliers", {}) or {}
        # Mechanics overlay (templates/mechanics.yaml + per-style parameters).
        # Weight multipliers say what a style VALUES; these say what its damage
        # delivery makes EFFECTIVE. Q16: the physics is now ABSOLUTE by size,
        # anchored to (balanced style, base size) — so at base size nothing
        # changes and template calibration is untouched, but ABOVE base size a
        # bigger fight puts more attackers on the called target (more Focus
        # Fire, single-target damage taxed) and hits more clumped enemies (more
        # AoE Escalation). Focus/target counts grow SUB-LINEARLY with size and
        # saturate (bodies can't all reach one target): capped/realistic curve.
        style_mech = (styles.get(style, {}) or {}).get("mechanics", {}) or {}
        base_mech = (styles.get("balanced", {}) or {}).get("mechanics", {}) or {}
        scale = self.size / self.base_size if self.base_size else 1.0
        # sub-linear damping (0.5) + a hard cap of 8 (the AoE-escalation cap and
        # a realistic max pile-on). At base size scale==1 -> counts unchanged.
        grow = lambda p: (min(8.0, p * (1.0 + 0.5 * (scale - 1.0))) if p else p)
        self.mech_mults = {}
        for cap in AOE_ESCALATION_CAPS:
            self.mech_mults[cap] = (
                self._escalation_mult(grow(style_mech.get("expected_aoe_targets")))
                / self._escalation_mult(base_mech.get("expected_aoe_targets")))
        for cap in RESILIENCE_CAPS:
            self.mech_mults[cap] = (
                self._resilience_eff(grow(style_mech.get("focus_attackers")))
                / self._resilience_eff(base_mech.get("focus_attackers")))

    def _escalation_mult(self, targets):
        """1 + AoE Escalation bonus for hitting `targets` players (capped at 8)."""
        table = (self.mechanics.get("aoe_escalation") or {}).get(
            "damage_bonus_by_targets") or {}
        if not table or not targets:
            return 1.0
        t = max(1, min(int(round(targets)), max(int(k) for k in table)))
        return 1.0 + table[str(t)]

    def _resilience_eff(self, attackers):
        """Fraction of ST damage that survives Focus Fire with N attackers."""
        table = (self.mechanics.get("focus_fire") or {}).get(
            "damage_reduction_unmounted") or {}
        if not table or not attackers:
            return 1.0
        n = max(1, min(int(round(attackers)), max(int(k) for k in table)))
        return 1.0 - table[str(n)]

    def weight(self, cap):
        return self.reqs[cap]["weight"] * self.style_mults.get(cap, 1.0)

    def extrapolated(self):
        """True when the requested size is outside the template's validated set."""
        return self.size not in (self.template.get("validated_sizes") or [self.base_size])

    def target(self, cap):
        r = self.reqs[cap]
        return r["target"] * self.size / self.base_size if r.get("scales") else r["target"]

    def soft_cap(self, cap):
        r = self.reqs[cap]
        return r["soft_cap"] * self.size / self.base_size if r.get("scales") else r["soft_cap"]

    def caps_of(self, weapon):
        return self.weapons[weapon]["capabilities"]

    # ----------------------------------------------------------------- core
    def supply(self, party):
        """Raw capability units summed over the party (sheet numbers)."""
        s = {}
        for w in party:
            for cap, v in self.caps_of(w).items():
                s[cap] = s.get(cap, 0) + v
        return s

    def effective_supply(self, party):
        """Supply after style-delivery physics (AoE escalation, Resilience).
        Balanced is the identity, so raw == effective there. All scoring
        reads THIS; `supply` stays raw for display and floors semantics."""
        s = self.supply(party)
        for cap, m in self.mech_mults.items():
            if m != 1.0 and cap in s:
                s[cap] = s[cap] * m
        return s

    def _floor_penalty(self, cap, have):
        f = self.floors.get(cap)
        if not f or self.size < f["min_party_size"] or have >= f["floor_units"]:
            return 0.0
        w = self.reqs[cap]["weight"]
        return f["penalty_mult"] * w * (f["floor_units"] - have) / f["floor_units"]

    def fitness(self, party):
        s, total = self.effective_supply(party), 0.0
        for cap in self.reqs:
            have, target, soft = s.get(cap, 0.0), self.target(cap), self.soft_cap(cap)
            # style multiplies the VALUE of coverage; over-stack economics and
            # floors stay on the base weight (T10 caught the alternative:
            # clap style punished a clap comp for stacking bombs)
            total += self.weight(cap) * min(1.0, have / target) ** self.gamma
            if have > soft:
                total -= 0.5 * self.reqs[cap]["weight"] * (have - soft) / target
            total -= self._floor_penalty(cap, have)
        return total

    def max_fitness(self):
        return sum(self.weight(cap) for cap in self.reqs)

    def synergy(self, party):
        s = self.effective_supply(party)
        return sum(b * min(s.get(a, 0), s.get(c, 0)) for a, c, b in self.synergies)

    def explain(self, party, candidate):
        """Per-capability delta terms — these ARE the 'why' text."""
        s, terms = self.effective_supply(party), []
        for cap in self.reqs:
            gain = (self.caps_of(candidate).get(cap, 0)
                    * self.mech_mults.get(cap, 1.0))
            if not gain:
                continue
            have, target = s.get(cap, 0.0), self.target(cap)
            d = self.weight(cap) * (min(1.0, (have + gain) / target) ** self.gamma
                                    - min(1.0, have / target) ** self.gamma)
            # credit for lifting a critical floor
            d += self._floor_penalty(cap, have) - self._floor_penalty(cap, have + gain)
            if d > 0.05:
                terms.append({"delta": round(d, 2), "cap": cap,
                              "before": have, "after": have + gain, "target": target})
        return sorted(terms, key=lambda t: -t["delta"])

    def meta_of(self, weapon):
        """Meta-prior value for a weapon at the current size. Flat map -> direct
        lookup; size-bucketed map -> the bucket the current size falls in
        (small <12, mid 12-30, large >30, matching sample_battles.py)."""
        if not self.meta_bucketed:
            return self.meta_prior.get(weapon, 0.0)
        b = "small" if self.size < 12 else "mid" if self.size <= 30 else "large"
        return (self.meta_prior.get(b) or {}).get(weapon, 0.0)

    def recommend(self, party, top_n=4, pool=None):
        base_fit, base_syn = self.fitness(party), self.synergy(party)
        out = []
        for w in (pool or self.weapons):
            d_fit = self.fitness(party + [w]) - base_fit
            d_syn = self.synergy(party + [w]) - base_syn
            meta = self.meta_of(w)
            out.append({
                "weapon": w,
                "display_name": self.weapons[w]["display_name"],
                "status": self.weapons[w]["status"],
                "d_fitness": d_fit, "d_synergy": d_syn, "meta_prior": meta,
                "score": self.alpha * d_fit + self.beta * d_syn + self.delta * meta,
            })
        return sorted(out, key=lambda r: -r["score"])[:top_n]

    def weaknesses(self, party, top_n=3):
        s = self.effective_supply(party)
        gaps = [{"cap": cap,
                 "gap": self.weight(cap) * (1 - min(1.0, s.get(cap, 0) / self.target(cap)) ** self.gamma),
                 "have": s.get(cap, 0), "target": self.target(cap)}
                for cap in self.reqs]
        return sorted(gaps, key=lambda g: -g["gap"])[:top_n]

    def uncovered_caps(self, party):
        """High-weight capabilities under half-supplied — feeds the greedy-trap
        lookahead warning (design doc §4.4.1)."""
        s = self.effective_supply(party)
        return [cap for cap in self.reqs
                if self.weight(cap) >= 5 and s.get(cap, 0) / self.target(cap) < 0.5]


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Score a party from the CLI. Weapons are UniqueNames "
                    "(2H_MACE) or unambiguous display-name substrings (heavy mace).")
    ap.add_argument("weapons", nargs="*",
                    help="party members; default is the design-doc §4.3 worked example")
    ap.add_argument("--content", default="castle_outpost")
    ap.add_argument("--size", type=int, default=None,
                    help="party size (default: the template's base size)")
    ap.add_argument("--style", default="balanced")
    args = ap.parse_args()

    e = Engine(content=args.content, size=7, style=args.style)
    e.set_content(args.content, args.size or e.base_size, args.style)

    def resolve(text):
        if text in e.weapons:
            return text
        hits = [k for k, w in e.weapons.items()
                if text.lower() in w["display_name"].lower()]
        if len(hits) != 1:
            raise SystemExit(f"'{text}' is {'ambiguous: ' + ', '.join(sorted(e.weapons[h]['display_name'] for h in hits)) if hits else 'not a known weapon'}")
        return hits[0]

    party = [resolve(t) for t in args.weapons] or \
            [w for w in ("2H_LONGBOW", "MAIN_ARCANESTAFF_UNDEAD", "2H_ICECRYSTAL_UNDEAD")
             if w in e.weapons]

    meta = e.data["_meta"]
    print(f"dataset v{meta['version']}  "
          f"{meta['weapons_curated']} curated / {meta['weapons_illustrative']} illustrative  "
          f"release_clean={meta['release_clean']}")
    style_bit = f", {e.style}" if e.style != "balanced" else ""
    print(f"\nParty: {[e.weapons[w]['display_name'] for w in party]}  "
          f"({e.template['name']}, size {e.size}{style_bit})")
    print(f"Fitness {e.fitness(party):.1f} / {e.max_fitness():.0f}")
    print("\nWeaknesses:")
    for w in e.weaknesses(party):
        print(f"  {w['cap']:<16} {w['have']:.0f}/{w['target']:.1f}  −{w['gap']:.1f}")
    recs = e.recommend(party)
    print(f"\nRecommend: {recs[0]['display_name']}  (score {recs[0]['score']:.2f})")
    for t in e.explain(party, recs[0]["weapon"])[:4]:
        print(f"  +{t['delta']:5.2f}  {t['cap']}: {t['before']:.0f} → {t['after']:.0f} "
              f"(target {t['target']:.1f})")
    print(f"Alternatives: {[r['display_name'] for r in recs[1:]]}")
