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
        self.synergies = [(s["a"], s["b"], s["bonus"])
                          for s in self.scoring.get("capability_synergies", [])]
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
        s = {}
        for w in party:
            for cap, v in self.caps_of(w).items():
                s[cap] = s.get(cap, 0) + v
        return s

    def _floor_penalty(self, cap, have):
        f = self.floors.get(cap)
        if not f or self.size < f["min_party_size"] or have >= f["floor_units"]:
            return 0.0
        w = self.reqs[cap]["weight"]
        return f["penalty_mult"] * w * (f["floor_units"] - have) / f["floor_units"]

    def fitness(self, party):
        s, total = self.supply(party), 0.0
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
        s = self.supply(party)
        return sum(b * min(s.get(a, 0), s.get(c, 0)) for a, c, b in self.synergies)

    def explain(self, party, candidate):
        """Per-capability delta terms — these ARE the 'why' text."""
        s, terms = self.supply(party), []
        for cap in self.reqs:
            gain = self.caps_of(candidate).get(cap, 0)
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

    def recommend(self, party, top_n=4, pool=None):
        base_fit, base_syn = self.fitness(party), self.synergy(party)
        out = []
        for w in (pool or self.weapons):
            d_fit = self.fitness(party + [w]) - base_fit
            d_syn = self.synergy(party + [w]) - base_syn
            meta = self.meta_prior.get(w, 0.0)
            out.append({
                "weapon": w,
                "display_name": self.weapons[w]["display_name"],
                "status": self.weapons[w]["status"],
                "d_fitness": d_fit, "d_synergy": d_syn, "meta_prior": meta,
                "score": self.alpha * d_fit + self.beta * d_syn + self.delta * meta,
            })
        return sorted(out, key=lambda r: -r["score"])[:top_n]

    def weaknesses(self, party, top_n=3):
        s = self.supply(party)
        gaps = [{"cap": cap,
                 "gap": self.weight(cap) * (1 - min(1.0, s.get(cap, 0) / self.target(cap)) ** self.gamma),
                 "have": s.get(cap, 0), "target": self.target(cap)}
                for cap in self.reqs]
        return sorted(gaps, key=lambda g: -g["gap"])[:top_n]

    def uncovered_caps(self, party):
        """High-weight capabilities under half-supplied — feeds the greedy-trap
        lookahead warning (design doc §4.4.1)."""
        s = self.supply(party)
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
