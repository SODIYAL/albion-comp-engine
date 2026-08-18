#!/usr/bin/env python3
"""
Composition scoring engine (design doc §3.2, §4.1).

Consumes the built dataset (pipeline/out/dataset-latest.json) — never hardcoded
capability numbers. This is the graduation of tests/prototype_engine.py from a
throwaway with inline dicts into the real engine reading curated data.

The math is unchanged from the prototype that passed 9/9:
    U_c(s)   = weight * min(1, s/target)^gamma      concave utility
             - omax * weight * x/(1+x), x=(s-soft)/soft   over-stack penalty
             - mult * weight * (floor - s)/floor     hard-floor penalty
    fitness  = sum over capabilities
    score(w) = alpha*dFitness + beta*dSynergy + delta*metaPrior

Party members are weapon unique_names (e.g. "2H_MACE"), matching the dataset.
"""
import json, os, itertools

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
        # Over-stack asymptote (scoring.yaml). Defaulted so an older dataset
        # still loads; the shipped config carries the real value.
        self.overstack_max = w.get("overstack_max", 0.5)
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
        # Candidate pool for every SUGGESTION path (recommend / swap_review /
        # refine). Weapons the game has retired stay in self.weapons so an old
        # permalink containing one still loads and scores — they are only
        # barred from being offered. Insertion order is preserved: steepest-
        # descent in refine() breaks ties by iteration order and the JS mirror
        # must walk the same sequence.
        self.pool = [w for w, d in self.weapons.items() if not d.get("removed")]
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
        # Per-context caches — constant until the next set_content: scaled
        # targets/soft caps, styled weights, and (lazily) each weapon's
        # loadout combos with mechanics applied. The recommend/swap hot path
        # otherwise recomputes all of them per candidate per combo (~2x on
        # swap_review, measured). Same expressions, same floats.
        self._targets = {c: (r["target"] * self.size / self.base_size
                             if r.get("scales") else r["target"])
                         for c, r in self.reqs.items()}
        self._softs = {c: (r["soft_cap"] * self.size / self.base_size
                           if r.get("scales") else r["soft_cap"])
                       for c, r in self.reqs.items()}
        self._weights = {c: r["weight"] * self.style_mults.get(c, 1.0)
                         for c, r in self.reqs.items()}
        self._extras_cache = {}

    @staticmethod
    def _half_up(x):
        """Round half UP, explicitly. Python's round() is half-to-even and
        JS Math.round() is half-up, and grow() lands on exact .5 counts at
        ordinary sizes (e.g. focus 3 grown at scale 2 = 4.5) — the implicit
        rules silently disagreed between the engines (review, 2026-08-15).
        int(x + 0.5) pins ONE rule; app_scoring.js mirrors it."""
        return int(x + 0.5)

    def _table_lookup(self, table, x):
        """Clamped mechanics-table value for count `x` (half-up rounding),
        or None when the table is missing or x is falsy. The single home of
        the clamp rule — it used to live inline in both curve methods."""
        if not table or not x:
            return None
        k = max(1, min(self._half_up(x), max(int(t) for t in table)))
        return table[str(k)]

    def _escalation_mult(self, targets):
        """1 + AoE Escalation bonus for hitting `targets` players (capped at 8)."""
        v = self._table_lookup((self.mechanics.get("aoe_escalation") or {})
                               .get("damage_bonus_by_targets"), targets)
        return 1.0 if v is None else 1.0 + v

    def _resilience_eff(self, attackers):
        """Fraction of ST damage that survives Focus Fire with N attackers."""
        v = self._table_lookup((self.mechanics.get("focus_fire") or {})
                               .get("damage_reduction_unmounted"), attackers)
        return 1.0 if v is None else 1.0 - v

    def weight(self, cap):
        return self._weights[cap]

    def extrapolated(self):
        """True when the requested size is outside the template's validated set."""
        return self.size not in (self.template.get("validated_sizes") or [self.base_size])

    def size_bucket(self):
        """small <12 / mid <=30 / large >30 — sample_battles.py's buckets.
        The one definition both the meta prior and the dashboard's usage
        display read, so they can never quote different buckets."""
        return "small" if self.size < 12 else "mid" if self.size <= 30 else "large"

    def target(self, cap):
        return self._targets[cap]

    def soft_cap(self, cap):
        return self._softs[cap]

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
        Balanced-at-base-size is the identity, so raw == effective there.
        ALL scoring — floors included — reads THIS; `supply` stays raw only
        as the sheet-unit reference (weapon detail views)."""
        s = self.supply(party)
        for cap, m in self.mech_mults.items():
            if m != 1.0 and cap in s:
                s[cap] = s[cap] * m
        return s

    def floor_armed(self, cap, have):
        """True when `cap` is below its hard floor at the current size — the
        ONE definition of that predicate; the dashboard's floor tags read it
        too, so display can never disagree with scoring."""
        f = self.floors.get(cap)
        return bool(f) and self.size >= f["min_party_size"] \
            and have < f["floor_units"]

    def _floor_penalty(self, cap, have):
        if not self.floor_armed(cap, have):
            return 0.0
        f = self.floors[cap]
        w = self.reqs[cap]["weight"]
        return f["penalty_mult"] * w * (f["floor_units"] - have) / f["floor_units"]

    def _overstack(self, cap, have, target, soft):
        """Over-stack penalty at one supply level. Stays on the BASE weight —
        style never changes the economics (T10). One home for a rule that
        used to be written out three times per engine.

        SATURATING (2026-08-18, was linear-unbounded/target). Redundancy is
        worth less and less, but never negative value: the penalty approaches
        overstack_max * weight and never exceeds it. Scaled by soft_cap rather
        than target so a threshold capability with a tiny target is no longer
        punished several times harder per excess unit than a big scaling one.
        Rational (x/(1+x)) not exponential: exp() is not guaranteed
        bit-identical across Python and JS, and the parity test is exact."""
        if have <= soft:
            return 0.0
        scale = soft if soft > 0 else target
        x = (have - soft) / scale
        return self.overstack_max * self.reqs[cap]["weight"] * x / (1.0 + x)

    def _cover_terms(self, cap, have, gain, target):
        """(coverage delta, floor-lift delta) for adding `gain` units. Kept
        as two terms so callers accumulate in their original order — float
        addition is not associative and parity pins the exact sums."""
        cov = self.weight(cap) * (min(1.0, (have + gain) / target) ** self.gamma
                                  - min(1.0, have / target) ** self.gamma)
        return cov, self._floor_penalty(cap, have) - self._floor_penalty(cap, have + gain)

    def fitness(self, party):
        s, total = self.effective_supply(party), 0.0
        for cap in self.reqs:
            have, target, soft = s.get(cap, 0.0), self.target(cap), self.soft_cap(cap)
            # style multiplies the VALUE of coverage; over-stack economics and
            # floors stay on the base weight (T10 caught the alternative:
            # clap style punished a clap comp for stacking bombs)
            total += self.weight(cap) * min(1.0, have / target) ** self.gamma
            total -= self._overstack(cap, have, target, soft)
            total -= self._floor_penalty(cap, have)
        return total

    def max_fitness(self):
        return sum(self.weight(cap) for cap in self.reqs)

    def synergy(self, party):
        s = self.effective_supply(party)
        return sum(b * min(s.get(a, 0), s.get(c, 0)) for a, c, b in self.synergies)

    # -------------------------------------------------------- comp-level score
    def comp_score(self, party):
        """Party-level objective — the SAME alpha/beta/delta blend pick_score
        applies marginally. The greedy builder and this must optimise one
        objective or they disagree about their own output: before this existed
        the builder took Hand of Justice as its FIRST pick (empty party, clump
        unmet) and swap_review then ranked that very slot 132nd (full party,
        clump saturated), with every one of the 20 slots scoring negative."""
        return (self.alpha * self.fitness(party)
                + self.beta * self.synergy(party)
                + self.delta * sum(self.meta_of(w) for w in party))

    def refine(self, party, max_passes=8, pool=None, fixed=0):
        """1-opt local search over a built party: repeatedly apply the single
        slot replacement that most improves comp_score, until none does.

        Greedy fill alone cannot undo an early pick — slot 1 is chosen against
        an EMPTY party and never revisited once the comp is full, which is how
        a forged comp ends up led by a weapon its own advisor ranks 132nd, and
        how the tail fills with narrow single-target weapons chosen only
        because they add least to already-saturated pools. Steepest-descent
        (best move per pass, not first-improvement) so the result does not
        depend on slot or weapon iteration order.

        `fixed` locks the first N slots: members the caller placed by hand
        must survive a "forge the rest" untouched, so only the slots the
        engine itself added are the engine's to rewrite.

        Returns a NEW list; the input is not mutated. Terminates on no
        improvement or max_passes, whichever comes first."""
        party = list(party)
        if not party:
            return party
        candidates = list(pool or self.pool)
        best = self.comp_score(party)
        for _ in range(max_passes):
            move, gain = None, 1e-9   # strictly-positive gain required
            for i in range(fixed, len(party)):
                orig = party[i]
                for w in candidates:
                    if w == orig:
                        continue
                    party[i] = w
                    d = self.comp_score(party) - best
                    if d > gain:
                        move, gain = (i, w), d
                party[i] = orig
            if move is None:
                break
            party[move[0]] = move[1]
            best += gain
        return party

    # ---------------------------------------------------------- loadout model
    # A weapon's sheet lists capabilities across ALL its Q/W/E/passive spell
    # options, but a player equips ONE per slot — a dagger can't run Shadow Edge
    # (catch/stun/peel) AND Dash (disengage) AND Forbidden Stab at once. So a
    # candidate's marginal value is the BEST single loadout (one bundle per
    # slot) for the current party, not the whole menu summed. Base-party supply
    # stays flat-union (fitness()/golden unchanged); only the candidate the
    # engine is *evaluating* is loadout-limited — that is the pick decision.
    def _eff(self, caps):
        """Apply mechanics multipliers (AoE escalation / Resilience) to a bundle."""
        return {c: v * self.mech_mults.get(c, 1.0) for c, v in caps.items()}

    def _loadout_eff(self, weapon):
        """(always_eff, [[bundle_eff, ...], ...]) for a weapon; empty loadout
        (illustrative / no game data) falls back to the flat capability union."""
        lo = self.weapons[weapon].get("loadout")
        if not lo or not lo.get("slots") and not lo.get("always"):
            return self._eff(self.caps_of(weapon)), []
        return (self._eff(lo.get("always", {})),
                [[self._eff(b) for b in slot] for slot in lo.get("slots", [])])

    def _marg_fit_from(self, s, extra):
        """Marginal fitness of adding effective caps `extra` to effective supply
        `s` — same coverage/floor/over-stack terms fitness() sums."""
        total = 0.0
        for cap, gain in extra.items():
            if cap not in self.reqs or not gain:
                continue
            have, target, soft = s.get(cap, 0.0), self.target(cap), self.soft_cap(cap)
            cov, floor_d = self._cover_terms(cap, have, gain, target)
            total += cov
            total += floor_d
            total -= (self._overstack(cap, have + gain, target, soft)
                      - self._overstack(cap, have, target, soft))
        return total

    def _marg_syn_from(self, s, base_syn, extra):
        """Marginal synergy of adding effective caps `extra`."""
        total = 0.0
        for a, c, b in self.synergies:
            total += b * min(s.get(a, 0) + extra.get(a, 0), s.get(c, 0) + extra.get(c, 0))
        return total - base_syn

    def _loadout_extras(self, weapon):
        """The weapon's candidate loadouts as merged effective-caps dicts,
        cached per set_content (they depend only on the weapon and the
        mechanics multipliers). itertools.product order is preserved so the
        argmax tie-break is identical to the uncached enumeration. Treat the
        returned dicts as read-only — best_loadout hands them out directly."""
        extras = self._extras_cache.get(weapon)
        if extras is None:
            always, slots = self._loadout_eff(weapon)
            # each slot equips exactly ONE of its mutually-exclusive spells
            # (no "empty" — a player always has a Q/W/E/passive slotted).
            # This blocks the within-slot double-count (catch AND disengage
            # from two W spells) WITHOUT letting a weapon dodge over-stack
            # penalties by shedding a redundant cap — the latter wrongly
            # inflated generalists in saturated parties and cost 11pts of V4
            # role accuracy.
            choices = [slot for slot in slots if slot]
            extras = []
            for combo in (itertools.product(*choices) if choices else [()]):
                extra = dict(always)
                for b in combo:
                    for cap, v in b.items():
                        if v > extra.get(cap, 0.0):
                            extra[cap] = v
                extras.append(extra)
            self._extras_cache[weapon] = extras
        return extras

    def best_loadout(self, s, base_syn, weapon):
        """Pick the one-spell-per-slot loadout maximizing alpha*dFit+beta*dSyn
        for effective base supply `s`. Returns (d_fit, d_syn, extra_caps)."""
        best = None
        for extra in self._loadout_extras(weapon):
            d_fit = self._marg_fit_from(s, extra)
            d_syn = self._marg_syn_from(s, base_syn, extra)
            val = self.alpha * d_fit + self.beta * d_syn
            if best is None or val > best[0]:
                best = (val, d_fit, d_syn, extra)
        if best is None:
            return 0.0, 0.0, {}
        return best[1], best[2], best[3]

    def explain(self, party, candidate):
        """Per-capability delta terms for the candidate's BEST loadout — these
        ARE the 'why' text, and they match what best_loadout actually picks."""
        s = self.effective_supply(party)
        _dfit, _dsyn, extra = self.best_loadout(s, self.synergy(party), candidate)
        terms = []
        for cap, gain in extra.items():
            if cap not in self.reqs or not gain:
                continue
            have, target = s.get(cap, 0.0), self.target(cap)
            # coverage + credit for lifting a critical floor — the same
            # terms best_loadout scored, from the same helper
            cov, floor_d = self._cover_terms(cap, have, gain, target)
            d = cov + floor_d
            if d > 0.05:
                terms.append({"delta": round(d, 2), "cap": cap,
                              "before": have, "after": have + gain, "target": target})
        return sorted(terms, key=lambda t: -t["delta"])

    def meta_of(self, weapon):
        """Meta-prior value for a weapon at the current size. Flat map -> direct
        lookup; size-bucketed map -> the size_bucket() the current size falls
        in (matching sample_battles.py)."""
        if not self.meta_bucketed:
            return self.meta_prior.get(weapon, 0.0)
        return (self.meta_prior.get(self.size_bucket()) or {}).get(weapon, 0.0)

    def pick_score(self, s, base_syn, weapon):
        """THE candidate score — alpha*dFit + beta*dSyn + delta*meta for
        picking `weapon` into effective supply `s`. recommend() and
        swap_review() (and their JS mirrors) all read this one helper so the
        formula can never drift between them. Returns (score, d_fit, d_syn,
        meta)."""
        d_fit, d_syn, _extra = self.best_loadout(s, base_syn, weapon)
        meta = self.meta_of(weapon)
        return (self.alpha * d_fit + self.beta * d_syn + self.delta * meta,
                d_fit, d_syn, meta)

    def recommend(self, party, top_n=4, pool=None):
        base_syn = self.synergy(party)
        s = self.effective_supply(party)
        out = []
        for w in (pool or self.pool):
            score, d_fit, d_syn, meta = self.pick_score(s, base_syn, w)
            out.append({
                "weapon": w,
                "display_name": self.weapons[w]["display_name"],
                "status": self.weapons[w]["status"],
                "d_fitness": d_fit, "d_synergy": d_syn, "meta_prior": meta,
                "score": score,
            })
        return sorted(out, key=lambda r: -r["score"])[:top_n]

    def swap_review(self, party, top_n=3, pool=None):
        """Per-member swap advisor — the "you'd serve this comp better on X"
        pass. For each member, value their CURRENT weapon exactly as
        recommend() would value it as a pick into the REST of the party (best
        single loadout, alpha*dFit + beta*dSyn + delta*meta), rank that
        against every alternative pick, and return the top upgrade options
        with their gains. rank counts strictly-better alternatives only, so
        ties never demote the member; gain is in score units (same scale as
        recommend()'s score). The caller decides what rank/gain reads as
        "poor fit" — this returns the data, not the verdict."""
        out = []
        for i, cur in enumerate(party):
            rest = party[:i] + party[i + 1:]
            s = self.effective_supply(rest)
            base_syn = self.synergy(rest)
            cur_score = self.pick_score(s, base_syn, cur)[0]
            better = []
            for w in (pool or self.pool):
                if w == cur:
                    continue
                v = self.pick_score(s, base_syn, w)[0]
                if v > cur_score:
                    better.append((v, w))
            better.sort(key=lambda t: (-t[0], t[1]))
            out.append({
                "index": i, "weapon": cur,
                "display_name": self.weapons[cur]["display_name"],
                # rank = strictly-better alternatives + 1 (ties never demote)
                "score": cur_score, "rank": len(better) + 1,
                "options": [{"weapon": w,
                             "display_name": self.weapons[w]["display_name"],
                             "score": v, "gain": v - cur_score}
                            for v, w in better[:top_n]],
            })
        return out

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
    ap.add_argument("--review", action="store_true",
                    help="per-member swap advisor: rank each member's weapon "
                         "against every alternative and list better options")
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
    if args.review:
        print("\nSwap review (rank 1 = nothing beats the current pick):")
        for m in e.swap_review(party):
            opts = ", ".join(f"{o['display_name']} (+{o['gain']:.2f})"
                             for o in m["options"]) or "—"
            print(f"  {m['index'] + 1}. {m['display_name']:<24} "
                  f"rank {m['rank']:>3}/{len(e.weapons)}  better: {opts}")
    recs = e.recommend(party)
    print(f"\nRecommend: {recs[0]['display_name']}  (score {recs[0]['score']:.2f})")
    for t in e.explain(party, recs[0]["weapon"])[:4]:
        print(f"  +{t['delta']:5.2f}  {t['cap']}: {t['before']:.0f} → {t['after']:.0f} "
              f"(target {t['target']:.1f})")
    print(f"Alternatives: {[r['display_name'] for r in recs[1:]]}")
