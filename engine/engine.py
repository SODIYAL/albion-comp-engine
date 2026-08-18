#!/usr/bin/env python3
"""
Composition scoring engine (design doc §3.2, §4.1; Forge rework 2026-08-18).

Consumes the built dataset (pipeline/out/dataset-latest.json) — never hardcoded
capability numbers. This is the graduation of tests/prototype_engine.py from a
throwaway with inline dicts into the real engine reading curated data.

The objective (one, canonical — everything scores THIS, marginally or whole):
    U_c(s)   = weight * min(1, s/target)^gamma      concave utility
             - omax * weight * x/(1+x), x=(s-soft)/soft   over-stack penalty
             - mult * weight * (floor - s)/floor     hard-floor penalty
    fitness  = sum over capabilities
    synergy  = sum over TEMPLATE-ACTIVE pairs of
               bonus * max(0, min(capped_a, capped_b) - best_self_joint)
    comp     = alpha*fitness + beta*synergy + delta*sum(meta)
             + viability*sum(core_bonus) - rho*sum(extra-copy units)

A candidate's pick score is EXACTLY comp(party+candidate) - comp(party) for the
candidate's chosen loadout — the invariant tests/test_forge.py pins at 1e-9.
Party members are weapon unique_names (e.g. "2H_MACE"), matching the dataset;
an optional parallel `combos` list pins each member's one-spell-per-slot
loadout (None = the static default for the current content+style).
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
        # Exact-weapon redundancy weight (design doc §4.1 rho — implemented
        # 2026-08-18) and viability-tier prior weight. Both default to 0 so
        # an older dataset scores exactly as it used to.
        self.rho = w.get("rho", 0.0)
        self.viability_w = w.get("viability", 0.0)
        # Headroom slope (2026-08-18): supply between target and soft cap
        # earns a small capped bonus — see scoring.yaml. 0 = legacy behavior.
        self.headroom = w.get("headroom", 0.0)
        self.meta_prior = self.scoring.get("meta_prior", {}) or {}
        # meta_prior is either a FLAT {weapon: value} map, or SIZE-BUCKETED
        # {small|mid|large: {weapon: value}} (usage-derived, Q17). Bucketed is
        # detected by its top-level keys; the value for a weapon is then chosen
        # by the current party size via size_bucket().
        self.meta_bucketed = bool(self.meta_prior) and \
            set(self.meta_prior) <= {"small", "mid", "large"}
        self.synergies = [(s["a"], s["b"], s["bonus"])
                          for s in self.scoring.get("capability_synergies", [])]
        self.mechanics = self.data.get("mechanics", {}) or {}
        # Composition layer (pipeline/templates/composition.yaml): what the
        # FORGE may generate — role bands, copy limits, groups, viability,
        # size physics. Absent (older dataset) -> everything defaults open.
        comp = self.data.get("composition", {}) or {}
        self.comp_cfg = comp
        roles_cfg = comp.get("roles", {}) or {}
        by_hint = roles_cfg.get("by_hint", {}) or {}
        overrides = roles_cfg.get("overrides", {}) or {}
        self.role_class = {}
        for k, d in self.weapons.items():
            self.role_class[k] = overrides.get(
                k, by_hint.get(d.get("role_hint"), "dps"))
        # capability predicates (flat sheet scores, static per dataset)
        self.pred_members = {}
        for name, mins in (comp.get("predicates", {}) or {}).items():
            self.pred_members[name] = set(
                k for k, d in self.weapons.items()
                if all(d["capabilities"].get(c, 0) >= v for c, v in mins.items()))
        dup = comp.get("duplication", {}) or {}
        self.dup_free_default = dup.get("free_copies_default", 1)
        self.dup_max_small = dup.get("max_copies_default_small", 10 ** 9)
        self.dup_max_large = dup.get("max_copies_default_large", 10 ** 9)
        self.dup_per_weapon = dup.get("per_weapon", {}) or {}
        self.dup_pw_min_size = dup.get("per_weapon_min_size", 10)
        self.groups = comp.get("groups", []) or []
        self.groups_of = {}
        for gi, g in enumerate(self.groups):
            for wk in g.get("weapons", []):
                self.groups_of.setdefault(wk, []).append(gi)
        # size-physics table: {size: mult}, JSON string keys -> sorted int list
        sp = comp.get("size_physics", {}) or {}
        cm = sp.get("count_mult", {}) or {}
        self.count_mult_table = sorted((int(k), cm[k]) for k in cm)
        self.st_boost_max_size = sp.get("st_boost_max_size", 5)
        sv = sp.get("st_value_mult", {}) or {}
        self.st_value_table = sorted((int(k), sv[k]) for k in sv)
        # Item stats bank (pipeline/fetch_item_stats.py) — the game's own
        # numbers for every weapon and worn item. REFERENCE DATA ONLY: no
        # scoring path reads it.
        self.item_stats = self.data.get("item_stats", {}) or {}
        # Candidate pool for every SUGGESTION path. Weapons the game has
        # retired stay in self.weapons so an old permalink containing one
        # still loads and scores — they are only barred from being offered.
        # Insertion order is preserved: deterministic tie-breaks walk it, and
        # the JS mirror must walk the same sequence.
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
        # 2026-08-18: the linear grow() extrapolation is REPLACED by the
        # piecewise absolute size table (composition.yaml size_physics) — a
        # step function of party size multiplying each style's base counts.
        # Both the current (style, size) counts and the anchor (balanced,
        # base_size) read the SAME table, so template calibration at the base
        # is untouched, and size 11 is intentionally defined instead of a
        # linear guess. The Resilience ratio is clamped at 1.0 above
        # st_boost_max_size: dedicated single-target damage is never BOOSTED
        # over the template's base calibration merely because the party is
        # smaller than base_size (the 11-in-a-20-template failure); a true
        # small gang (<= the clamp size) keeps its inversion (golden T16).
        style_mech = (styles.get(style, {}) or {}).get("mechanics", {}) or {}
        base_mech = (styles.get("balanced", {}) or {}).get("mechanics", {}) or {}
        mult_now = self._count_mult(self.size)
        mult_base = self._count_mult(self.base_size)
        grown = lambda p, m: (p * m if p else p)
        self.mech_mults = {}
        for cap in AOE_ESCALATION_CAPS:
            self.mech_mults[cap] = (
                self._escalation_mult(grown(style_mech.get("expected_aoe_targets"), mult_now))
                / self._escalation_mult(grown(base_mech.get("expected_aoe_targets"), mult_base)))
        # Resilience ratio factorized (2026-08-18): the STYLE factor (this
        # style's focus count vs balanced at the SAME size — brawl's 3
        # attackers beat balanced's 4, golden T11b) is always legitimate;
        # the SIZE factor (balanced at this size vs balanced at base) is the
        # cross-size extrapolation, and above st_boost_max_size it may only
        # TAX single-target delivery, never boost it.
        for cap in RESILIENCE_CAPS:
            e_style = self._resilience_eff(grown(style_mech.get("focus_attackers"), mult_now))
            e_bal_now = self._resilience_eff(grown(base_mech.get("focus_attackers"), mult_now))
            e_bal_base = self._resilience_eff(grown(base_mech.get("focus_attackers"), mult_base))
            style_factor = e_style / e_bal_now
            size_factor = e_bal_now / e_bal_base
            if self.size > self.st_boost_max_size and size_factor > 1.0:
                size_factor = 1.0
            self.mech_mults[cap] = style_factor * size_factor
        # Per-context caches — constant until the next set_content: scaled
        # targets/soft caps, styled weights, per-weapon loadout combos.
        self._targets = {c: (r["target"] * self.size / self.base_size
                             if r.get("scales") else r["target"])
                         for c, r in self.reqs.items()}
        self._softs = {c: (r["soft_cap"] * self.size / self.base_size
                           if r.get("scales") else r["soft_cap"])
                       for c, r in self.reqs.items()}
        self._weights = {c: r["weight"] * self.style_mults.get(c, 1.0)
                         for c, r in self.reqs.items()}
        # Dedicated single-target VALUE devaluation by size (2026-08-18,
        # composition.yaml st_value_mult): concave coverage hands the FULL
        # weight to whoever fills an empty capability first, so a token
        # burst_st/execute requirement still dictated tail picks in 20-mans
        # (golden T15). The WEIGHT is what must shrink at scale. A template
        # may opt out with `st_full_value: true` (roads — small-gang content
        # where kill pressure is the win condition). Over-stack and floor
        # economics stay on the base weight, unchanged.
        if not self.template.get("st_full_value"):
            stv = self._st_value_mult(self.size)
            for cap in RESILIENCE_CAPS:
                if cap in self._weights:
                    self._weights[cap] *= stv
        # Effective hard floors: an ABSOLUTE floor may never exceed the SCALED
        # target (2026-08-18) — territory's 4.2-unit heal floor armed at a
        # size-10 party whose scaled heal target is only 3.35, so a party at
        # a perfect target was "below floor". The floor now clamps to the
        # target it guards.
        self._floors_eff = {}
        for c, f in self.floors.items():
            fu = f["floor_units"]
            t = self._targets.get(c)
            self._floors_eff[c] = fu if t is None or t > fu else t
        # Synergy pairs ACTIVE in this template (2026-08-18): a capability
        # synergy is inactive when either capability is absent from the
        # template's requirements — castle_outpost deliberately omits
        # burst_st, so resist_shred x burst_st must pay nothing there.
        self._active_syn = [(a, b, bonus) for (a, b, bonus) in self.synergies
                            if a in self.reqs and b in self.reqs]
        # Viability layer resolved for this content+size (composition.yaml).
        via = self.comp_cfg.get("viability", {}) or {}
        excl = set()
        for rule in via.get("exclusions", []) or []:
            if self.size < rule.get("min_size", 0):
                continue
            allowed = set((rule.get("allow") or {}).get(self.content) or [])
            for wk in rule.get("weapons", []):
                if wk not in allowed:
                    excl.add(wk)
        self._excluded = excl
        self._suggest = [w for w in self.pool if w not in excl]
        self._viability = {}
        if self.size >= via.get("core_min_size", 10):
            bonus = via.get("core_bonus", 1.0)
            for wk in (via.get("core", {}) or {}).get("large", []) or []:
                self._viability[wk] = bonus
        # Constraint band for this size (forge-only; scoring never blocked).
        self._band = None
        for row in self.comp_cfg.get("constraint_bands", []) or []:
            if row.get("min_size", 0) <= self.size <= row.get("max_size", 10 ** 9):
                self._band = row
                break
        self._extras_cache = {}
        self._default_cache = {}

    @staticmethod
    def _step_table(table, size):
        """Piecewise step lookup: value of the LARGEST breakpoint <= size,
        or the smallest row for tinier parties; 1.0 for an empty table."""
        if not table:
            return 1.0
        v = table[0][1]
        for k, m in table:
            if k <= size:
                v = m
            else:
                break
        return v

    def _count_mult(self, size):
        return self._step_table(self.count_mult_table, size)

    def _st_value_mult(self, size):
        return self._step_table(self.st_value_table, size)

    @staticmethod
    def _half_up(x):
        """Round half UP, explicitly. Python's round() is half-to-even and
        JS Math.round() is half-up; the implicit rules silently disagreed
        between the engines (review, 2026-08-15). int(x + 0.5) pins ONE rule;
        app_scoring.js mirrors it."""
        return int(x + 0.5)

    def _table_lookup(self, table, x):
        """Clamped mechanics-table value for count `x` (half-up rounding),
        or None when the table is missing or x is falsy."""
        if not table or not x:
            return None
        k = max(1, min(self._half_up(x), max(int(t) for t in table)))
        return table[str(k)]

    def _escalation_mult(self, targets):
        """1 + AoE Escalation bonus for hitting `targets` players (table-capped)."""
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
        """Usage-DISPLAY bucket. weapon_usage_v2 buckets battles by TOTAL
        participants (both sides); a party of N fights battles of roughly 2N,
        so the axis maps through 2*size (2026-08-18 — party size used to be
        compared directly against participant counts, so an 11-man read the
        under-12-participant sample). Usage stays display-only; the same
        bucket feeds a size-bucketed meta prior if one is ever admitted."""
        n = 2 * self.size
        return "small" if n < 12 else "mid" if n <= 30 else "large"

    def target(self, cap):
        return self._targets[cap]

    def soft_cap(self, cap):
        return self._softs[cap]

    def caps_of(self, weapon):
        return self.weapons[weapon]["capabilities"]

    def stats_of(self, item):
        """Game stats for a weapon or gear key (reference only)."""
        return self.item_stats.get(item) or {}

    def role_of(self, weapon):
        """Constraint role class: healer / frontline / support / dps."""
        return self.role_class.get(weapon, "dps")

    def is_excluded(self, weapon):
        """True when the viability rules bar this weapon from GENERATED comps
        at the current content+size. Scoring is never blocked — the dashboard
        flags such members off-comp with replacement advice instead."""
        return weapon in self._excluded

    def suggest_pool(self):
        """The default candidate pool for every suggestion/generation path:
        non-retired weapons minus the viability exclusions for this context."""
        return self._suggest

    # ---------------------------------------------------------- loadout model
    # A weapon's sheet lists capabilities across ALL its Q/W/E/passive spell
    # options, but a player equips ONE per slot. A party member is therefore
    # (weapon, combo): one bundle per slot, merged over `always`. The SAME
    # combo machinery serves incumbents and candidates — the static-vs-dynamic
    # split that made recommend() disagree with comp_score() is gone. A
    # member's combo defaults to the static best under the current template
    # weights; the forge persists the combo it actually scored; the dashboard
    # pins combos from the player's real Q/W/passive picks.
    def _eff(self, caps):
        """Apply mechanics multipliers (AoE escalation / Resilience) to a bundle."""
        return {c: v * self.mech_mults.get(c, 1.0) for c, v in caps.items()}

    def _loadout_eff(self, weapon):
        """(always_eff, [[bundle_eff, ...], ...]) for a weapon; empty loadout
        (no game data) falls back to the flat capability union."""
        lo = self.weapons[weapon].get("loadout")
        if not lo or not lo.get("slots") and not lo.get("always"):
            return self._eff(self.caps_of(weapon)), []
        return (self._eff(lo.get("always", {})),
                [[self._eff(b) for b in slot] for slot in lo.get("slots", [])])

    def _combo_extras(self, weapon):
        """Every one-spell-per-slot loadout as a merged effective-caps dict,
        in itertools.product order (cached per set_content). Each capability
        lives in exactly one slot's bundle (build_dataset assigns it to its
        first evidence spell), so the merge is a plain union + sum with
        `always`. Treat the returned dicts as read-only."""
        extras = self._extras_cache.get(weapon)
        if extras is None:
            always, slots = self._loadout_eff(weapon)
            choices = [slot for slot in slots if slot]
            extras = []
            for combo in (itertools.product(*choices) if choices else [()]):
                extra = dict(always)
                for b in combo:
                    for cap, v in b.items():
                        extra[cap] = extra.get(cap, 0.0) + v
                extras.append(extra)
            self._extras_cache[weapon] = extras
        return extras

    def _combo_dims(self, weapon):
        """Option count per non-empty slot plus each slot's original index —
        the product-order arithmetic for encoding/decoding combo indexes."""
        lo = self.weapons[weapon].get("loadout") or {}
        dims = []
        for oi, slot in enumerate(lo.get("slots", []) or []):
            if slot:
                dims.append((oi, len(slot)))
        return dims

    def combo_choices(self, weapon, combo):
        """[(original slot index, bundle index)] for a combo index. An
        out-of-range index falls back to the default combo EXACTLY like
        member_extra does — a stale permalink must not make the displayed
        kit differ from the scored kit (review 2026-08-18)."""
        dims = self._combo_dims(weapon)
        total = 1
        for _oi, n in dims:
            total *= n
        if combo is None or combo < 0 or combo >= total:
            combo = self.default_combo(weapon)
        out, stride = [], total
        for oi, n in dims:
            stride //= n
            out.append((oi, (combo // stride) % n))
        return out

    def combo_from_picks(self, weapon, picks):
        """Combo index for a member whose REAL spell picks are known.
        `picks` maps game slot name (q/w/e/passive) -> picked spell id. A
        slot whose picked spell has no curated bundle (or with no pick) keeps
        the default combo's choice — user picks affect scoring exactly where
        curated spell capability data exists."""
        lo = self.weapons[weapon].get("loadout") or {}
        names = lo.get("slot_names") or []
        spells = lo.get("slot_spells") or []
        dims = self._combo_dims(weapon)
        default = {oi: ci for oi, ci in self.combo_choices(weapon, self.default_combo(weapon))}
        combo = 0
        for oi, n in dims:
            choice = default.get(oi, 0)
            name = names[oi] if oi < len(names) else None
            pick = picks.get(name) if name else None
            if pick is not None and oi < len(spells):
                for j, sp in enumerate(spells[oi]):
                    if sp == pick:
                        choice = j
                        break
            combo = combo * n + choice
        return combo

    def combo_spells(self, weapon, combo):
        """[(slot name, spell id)] the combo actually equips — what the
        recommendation explanations describe."""
        lo = self.weapons[weapon].get("loadout") or {}
        names = lo.get("slot_names") or []
        spells = lo.get("slot_spells") or []
        out = []
        for oi, ci in self.combo_choices(weapon, combo):
            if oi < len(names) and oi < len(spells) and ci < len(spells[oi]):
                out.append((names[oi], spells[oi][ci]))
        return out

    def default_combo(self, weapon):
        """The static loadout under the CURRENT template weights — argmax by
        (styled-weight value, unit count, first-in-order). Party-independent,
        so a bare weapon key in a party always means the same combo. Cached
        per set_content (the choice depends on the styled weights)."""
        hit = self._default_cache.get(weapon)
        if hit is not None:
            return hit
        best_i, best_key = 0, None
        for i, extra in enumerate(self._combo_extras(weapon)):
            val = 0.0
            units = 0.0
            for c, v in extra.items():
                val += self._weights.get(c, 0.0) * v
                units += v
            key = (val, units)
            if best_key is None or key > best_key:
                best_i, best_key = i, key
        self._default_cache[weapon] = best_i
        return best_i

    def member_extra(self, weapon, combo=None):
        """What ONE party member actually brings: the combo's effective caps
        (mechanics applied). combo None -> the static default."""
        extras = self._combo_extras(weapon)
        if combo is None or combo < 0 or combo >= len(extras):
            combo = self.default_combo(weapon)
        return extras[combo]

    # ----------------------------------------------------------------- supply
    def supply(self, party):
        """Raw capability units summed over the party (sheet numbers) —
        display/reference only; scoring reads effective_supply."""
        s = {}
        for w in party:
            for cap, v in self.caps_of(w).items():
                s[cap] = s.get(cap, 0) + v
        return s

    def effective_supply(self, party, combos=None):
        """Supply after style-delivery physics AND the one-spell-per-slot
        loadout rule. ALL scoring — floors included — reads THIS."""
        s = {}
        for i, w in enumerate(party):
            extra = self.member_extra(w, combos[i] if combos else None)
            for cap, v in extra.items():
                s[cap] = s.get(cap, 0.0) + v
        return s

    # ----------------------------------------------------------------- floors
    def floor_armed(self, cap, have):
        """True when `cap` is below its (target-clamped) hard floor at the
        current size — the ONE definition of that predicate; the dashboard's
        floor tags read it too, so display can never disagree with scoring."""
        f = self.floors.get(cap)
        return bool(f) and self.size >= f["min_party_size"] \
            and have < self._floors_eff[cap]

    def _floor_penalty(self, cap, have):
        if not self.floor_armed(cap, have):
            return 0.0
        f = self.floors[cap]
        fu = self._floors_eff[cap]
        w = self.reqs[cap]["weight"]
        return f["penalty_mult"] * w * (fu - have) / fu

    def _overstack(self, cap, have, target, soft):
        """Over-stack penalty at one supply level. Stays on the BASE weight —
        style never changes the economics (T10). SATURATING: approaches
        overstack_max * weight, scaled by soft_cap. Rational (x/(1+x)) not
        exponential: exp() is not guaranteed bit-identical across Python and
        JS, and the parity test is exact."""
        if have <= soft:
            return 0.0
        scale = soft if soft > 0 else target
        x = (have - soft) / scale
        return self.overstack_max * self.reqs[cap]["weight"] * x / (1.0 + x)

    def _headroom_bonus(self, cap, have, target, soft):
        """Small linear bonus for supply in the target..soft_cap band, capped
        at headroom * weight (2026-08-18). Without it every unit past target
        was worth exactly zero and a fixed-size roster's tail slots went net
        negative — the model preferred fewer bodies than the requested size."""
        if self.headroom <= 0.0 or soft <= target or have <= target:
            return 0.0
        extra = have - target
        span = soft - target
        if extra > span:
            extra = span
        return self.headroom * self.weight(cap) * extra / span

    def _cover_terms(self, cap, have, gain, target):
        """(coverage delta, floor-lift delta) for adding `gain` units. Kept
        as two terms so callers accumulate in their original order — float
        addition is not associative and parity pins the exact sums. Coverage
        includes the headroom bonus so marginals stay exact."""
        soft = self.soft_cap(cap)
        cov = self.weight(cap) * (min(1.0, (have + gain) / target) ** self.gamma
                                  - min(1.0, have / target) ** self.gamma)
        cov += (self._headroom_bonus(cap, have + gain, target, soft)
                - self._headroom_bonus(cap, have, target, soft))
        return cov, self._floor_penalty(cap, have) - self._floor_penalty(cap, have + gain)

    # ---------------------------------------------------------------- fitness
    def fitness(self, party, combos=None):
        s, total = self.effective_supply(party, combos), 0.0
        for cap in self.reqs:
            have, target, soft = s.get(cap, 0.0), self.target(cap), self.soft_cap(cap)
            # style multiplies the VALUE of coverage; over-stack economics and
            # floors stay on the base weight (T10)
            total += self.weight(cap) * min(1.0, have / target) ** self.gamma
            total += self._headroom_bonus(cap, have, target, soft)
            total -= self._overstack(cap, have, target, soft)
            total -= self._floor_penalty(cap, have)
        return total

    def max_fitness(self):
        """Supremum of fitness(): full coverage of every capability plus the
        headroom band maxed at each soft cap (review 2026-08-18 — without
        the headroom factor a well-forged comp displayed over 100%)."""
        return sum(self.weight(cap) for cap in self.reqs) * (1.0 + self.headroom)

    # ---------------------------------------------------------------- synergy
    def _syn_side(self, cap, amount):
        """One side of a synergy pair, capped at its target — synergy
        saturates exactly where coverage does. Pairs are pre-filtered to
        template-active capabilities, so the target always exists."""
        if cap not in self.reqs:
            return amount
        return min(amount, self.target(cap))

    def _pair_value(self, p, s_a, s_b, j):
        """One active pair's value: bonus * max(0, min(capped sides) - J).
        J is the largest single member's joint supply min(a_m, b_m) — the
        'across players' rule (2026-08-18): one weapon supplying both halves
        cannot self-trigger the pair; two members each covering one half pay
        in full. PROVISIONAL formulation (subtraction keeps partial credit)."""
        a, b, bonus = self._active_syn[p]
        v = min(self._syn_side(a, s_a), self._syn_side(b, s_b)) - j
        return bonus * v if v > 0 else 0.0

    def _syn_state(self, party, combos=None):
        """(effective supply, per-active-pair J) — the synergy inputs."""
        s = self.effective_supply(party, combos)
        J = [0.0] * len(self._active_syn)
        for i, w in enumerate(party):
            extra = self.member_extra(w, combos[i] if combos else None)
            for p in range(len(self._active_syn)):
                a, b, _bonus = self._active_syn[p]
                j = min(extra.get(a, 0.0), extra.get(b, 0.0))
                if j > J[p]:
                    J[p] = j
        return s, J

    def synergy(self, party, combos=None):
        s, J = self._syn_state(party, combos)
        total = 0.0
        for p in range(len(self._active_syn)):
            a, b, _bonus = self._active_syn[p]
            total += self._pair_value(p, s.get(a, 0.0), s.get(b, 0.0), J[p])
        return total

    # ------------------------------------------------------------- redundancy
    def _dup_free(self, weapon):
        """Penalty-free copy allowance. Per-weapon entries are seeded from
        LARGE-group comps and apply only at sizes >= per_weapon_min_size
        (review 2026-08-18): two Permafrosts in a trio pay like any other
        duplicate — the evidence for the allowance is 20-man evidence."""
        pw = self.dup_per_weapon.get(weapon)
        if pw and "free" in pw and self.size >= self.dup_pw_min_size:
            return pw["free"]
        return self.dup_free_default

    def _dup_gen_max(self, weapon):
        """Hard cap on copies the FORGE may generate (never a scoring bar).
        Per-weapon caps are size-gated like the free allowances."""
        pw = self.dup_per_weapon.get(weapon)
        if pw and "max" in pw and self.size >= self.dup_pw_min_size:
            return pw["max"]
        return self.dup_max_small if self.size < 10 else self.dup_max_large

    def redundancy(self, party):
        """Extra-copy units: every copy of a weapon beyond its penalty-free
        allowance adds (copy_index - free) — the marginal cost of each later
        copy GROWS, deliberately non-saturating (design doc §4.1 rho; the
        capability over-stack penalty saturates, which is exactly how a third
        Cursed Staff used to become nearly free)."""
        counts, total = {}, 0.0
        for w in party:
            c = counts.get(w, 0) + 1
            counts[w] = c
            free = self._dup_free(w)
            if c > free:
                total += c - free
        return total

    # ----------------------------------------------------------------- priors
    def meta_of(self, weapon):
        """Meta-prior value for a weapon at the current size. Flat map ->
        direct lookup; size-bucketed map -> size_bucket()."""
        if not self.meta_bucketed:
            return self.meta_prior.get(weapon, 0.0)
        return (self.meta_prior.get(self.size_bucket()) or {}).get(weapon, 0.0)

    def viability_of(self, weapon):
        """Expert-curated viability-tier bonus for this content+size (0 for
        unlisted weapons — absence is neutral, never a penalty)."""
        return self._viability.get(weapon, 0.0)

    # -------------------------------------------------------- comp-level score
    def comp_score(self, party, combos=None):
        """THE party-level objective. Every suggestion path reports exact
        marginals of this same blend — see _eval_pick."""
        meta = 0.0
        viab = 0.0
        for w in party:
            meta += self.meta_of(w)
            viab += self.viability_of(w)
        return (self.alpha * self.fitness(party, combos)
                + self.beta * self.synergy(party, combos)
                + self.delta * meta
                + self.viability_w * viab
                - self.rho * self.redundancy(party))

    # -------------------------------------------------- candidate evaluation
    def party_state(self, party, combos=None):
        """Everything a candidate marginal needs: effective supply, per-pair
        synergy state, and exact-weapon counts. Build once per sweep."""
        s, J = self._syn_state(party, combos)
        pair_vals = []
        for p in range(len(self._active_syn)):
            a, b, _bonus = self._active_syn[p]
            pair_vals.append(self._pair_value(p, s.get(a, 0.0), s.get(b, 0.0), J[p]))
        counts = {}
        for w in party:
            counts[w] = counts.get(w, 0) + 1
        return {"s": s, "J": J, "pair_vals": pair_vals, "counts": counts}

    def _marg_fit_from(self, s, extra):
        """Marginal fitness of adding effective caps `extra` to effective
        supply `s` — same coverage/floor/over-stack terms fitness() sums."""
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

    def _marg_syn_from(self, state, extra):
        """Marginal synergy of adding effective caps `extra` — exact against
        the same per-pair rule synergy() applies."""
        total = 0.0
        s, J, pv = state["s"], state["J"], state["pair_vals"]
        for p in range(len(self._active_syn)):
            a, b, _bonus = self._active_syn[p]
            j = min(extra.get(a, 0.0), extra.get(b, 0.0))
            j2 = J[p] if J[p] > j else j
            total += self._pair_value(p, s.get(a, 0.0) + extra.get(a, 0.0),
                                      s.get(b, 0.0) + extra.get(b, 0.0), j2) - pv[p]
        return total

    def _eval_pick(self, state, weapon):
        """THE candidate score — the exact comp_score delta of adding
        `weapon` with its best loadout for this party. Every suggestion path
        (recommend / swap_review / forge beam) reads this one helper so the
        formula can never drift. Returns (score, d_fit, d_syn, meta, combo)."""
        best = None
        extras = self._combo_extras(weapon)
        for i in range(len(extras)):
            extra = extras[i]
            d_fit = self._marg_fit_from(state["s"], extra)
            d_syn = self._marg_syn_from(state, extra)
            val = self.alpha * d_fit + self.beta * d_syn
            if best is None or val > best[0]:
                best = (val, d_fit, d_syn, i)
        if best is None:
            best = (0.0, 0.0, 0.0, None)
        meta = self.meta_of(weapon)
        dup = state["counts"].get(weapon, 0) + 1 - self._dup_free(weapon)
        score = (best[0] + self.delta * meta
                 + self.viability_w * self.viability_of(weapon)
                 - (self.rho * dup if dup > 0 else 0.0))
        return score, best[1], best[2], meta, best[3]

    def best_loadout(self, s, base_syn, weapon):
        """Legacy shim (golden T14; explain callers migrated): the candidate's
        best loadout against bare supply `s`, with no member-level synergy
        state (J=0 — exact for an empty party). Returns (d_fit, d_syn, extra)."""
        state = {"s": s, "J": [0.0] * len(self._active_syn), "pair_vals": [], "counts": {}}
        for p in range(len(self._active_syn)):
            a, b, _bonus = self._active_syn[p]
            state["pair_vals"].append(self._pair_value(p, s.get(a, 0.0), s.get(b, 0.0), 0.0))
        best = None
        for extra in self._combo_extras(weapon):
            d_fit = self._marg_fit_from(s, extra)
            d_syn = self._marg_syn_from(state, extra)
            val = self.alpha * d_fit + self.beta * d_syn
            if best is None or val > best[0]:
                best = (val, d_fit, d_syn, extra)
        if best is None:
            return 0.0, 0.0, {}
        return best[1], best[2], best[3]

    def explain(self, party, candidate, combos=None):
        """Per-capability delta terms for the candidate's CHOSEN loadout —
        these ARE the 'why' text, and they match what _eval_pick scored."""
        state = self.party_state(party, combos)
        _sc, _df, _ds, _meta, combo = self._eval_pick(state, candidate)
        extra = self.member_extra(candidate, combo)
        s = state["s"]
        terms = []
        for cap, gain in extra.items():
            if cap not in self.reqs or not gain:
                continue
            have, target = s.get(cap, 0.0), self.target(cap)
            cov, floor_d = self._cover_terms(cap, have, gain, target)
            d = cov + floor_d
            if d > 0.05:
                terms.append({"delta": round(d, 2), "cap": cap,
                              "before": have, "after": have + gain, "target": target})
        return sorted(terms, key=lambda t: -t["delta"])

    def recommend(self, party, top_n=4, pool=None, combos=None):
        state = self.party_state(party, combos)
        out = []
        for w in (pool or self.suggest_pool()):
            score, d_fit, d_syn, meta, combo = self._eval_pick(state, w)
            out.append({
                "weapon": w,
                "display_name": self.weapons[w]["display_name"],
                "status": self.weapons[w]["status"],
                "d_fitness": d_fit, "d_synergy": d_syn, "meta_prior": meta,
                "viability": self.viability_of(w),
                "combo": combo,
                "score": score,
            })
        return sorted(out, key=lambda r: -r["score"])[:top_n]

    def swap_review(self, party, top_n=3, pool=None, combos=None):
        """Per-member swap advisor. Each member's CURRENT weapon is valued
        exactly as _eval_pick would value it as a pick into the REST of the
        party, ranked against every alternative. `off_comp` flags members the
        viability rules bar from generated comps at this content+size —
        loadable, scoreable, advised against."""
        out = []
        for i, cur in enumerate(party):
            rest = party[:i] + party[i + 1:]
            rest_combos = (combos[:i] + combos[i + 1:]) if combos else None
            state = self.party_state(rest, rest_combos)
            cur_score = self._eval_pick(state, cur)[0]
            better = []
            for w in (pool or self.suggest_pool()):
                if w == cur:
                    continue
                v = self._eval_pick(state, w)[0]
                if v > cur_score:
                    better.append((v, w))
            better.sort(key=lambda t: (-t[0], t[1]))
            out.append({
                "index": i, "weapon": cur,
                "display_name": self.weapons[cur]["display_name"],
                # rank = strictly-better alternatives + 1 (ties never demote)
                "score": cur_score, "rank": len(better) + 1,
                "off_comp": self.is_excluded(cur),
                "options": [{"weapon": w,
                             "display_name": self.weapons[w]["display_name"],
                             "score": v, "gain": v - cur_score}
                            for v, w in better[:top_n]],
            })
        return out

    def weaknesses(self, party, top_n=3, combos=None):
        s = self.effective_supply(party, combos)
        gaps = [{"cap": cap,
                 "gap": self.weight(cap) * (1 - min(1.0, s.get(cap, 0) / self.target(cap)) ** self.gamma),
                 "have": s.get(cap, 0), "target": self.target(cap)}
                for cap in self.reqs]
        return sorted(gaps, key=lambda g: -g["gap"])[:top_n]

    def uncovered_caps(self, party, combos=None):
        """High-weight capabilities under half-supplied — feeds the greedy-trap
        lookahead warning (design doc §4.4.1)."""
        s = self.effective_supply(party, combos)
        return [cap for cap in self.reqs
                if self.weight(cap) >= 5 and s.get(cap, 0) / self.target(cap) < 0.5]

    # ------------------------------------------------------------ local search
    def refine(self, party, max_passes=8, pool=None, fixed=0):
        """1-opt local search over a built party: repeatedly apply the single
        slot replacement that most improves comp_score, until none does.
        Steepest-descent (best move per pass, not first-improvement) so the
        result does not depend on slot or weapon iteration order. `fixed`
        locks the first N slots. Returns a NEW list; the input is not
        mutated. UNCONSTRAINED — the forge runs its own constraint-aware
        refinement; this stays for parity and ad-hoc callers."""
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

    # ------------------------------------------------------------------ forge
    def _forge_ctx(self, pool):
        """Static per-forge context: role/predicate membership and per-weapon
        caps for the current band."""
        band = self._band or {}
        role_min, role_max = {}, {}
        pred_min = {}
        for key, rule in band.items():
            if key in ("min_size", "max_size") or not isinstance(rule, dict):
                continue
            if key in self.pred_members:
                if "min" in rule:
                    pred_min[key] = rule["min"]
                continue
            if "min" in rule:
                role_min[key] = rule["min"]
            if "max" in rule:
                role_max[key] = rule["max"]
        return {"pool": pool, "role_min": role_min, "role_max": role_max,
                "pred_min": pred_min}

    def _forge_counts(self, party):
        """(weapon counts, role counts, predicate counts, group counts)."""
        counts, roles, preds, groups = {}, {}, {}, {}
        for w in party:
            counts[w] = counts.get(w, 0) + 1
            r = self.role_of(w)
            roles[r] = roles.get(r, 0) + 1
            for name, members in self.pred_members.items():
                if w in members:
                    preds[name] = preds.get(name, 0) + 1
            for gi in self.groups_of.get(w, []):
                groups[gi] = groups.get(gi, 0) + 1
        return counts, roles, preds, groups

    def _forge_feasible(self, ctx, counts, roles, preds, groups, w, slots_left_after):
        """May the forge add `w` here and still complete a legal roster?"""
        if counts.get(w, 0) >= self._dup_gen_max(w):
            return False
        for gi in self.groups_of.get(w, []):
            if groups.get(gi, 0) >= self.groups[gi].get("max", 10 ** 9):
                return False
        r = self.role_of(w)
        mx = ctx["role_max"].get(r)
        if mx is not None and roles.get(r, 0) >= mx:
            return False
        # min-satisfiability: unmet role/predicate minima must fit in the
        # remaining slots (a weapon may serve one role AND a predicate; the
        # sum slightly over-counts that overlap — conservative, documented)
        need = 0
        for r2, mn in ctx["role_min"].items():
            have = roles.get(r2, 0) + (1 if r2 == r else 0)
            if mn > have:
                need += mn - have
        for pn, mn in ctx["pred_min"].items():
            have = preds.get(pn, 0) + (1 if w in self.pred_members[pn] else 0)
            if mn > have:
                need += mn - have
        return need <= slots_left_after

    @staticmethod
    def _member_tag(w, combo):
        return w + "#" + ("d" if combo is None else str(combo))

    @staticmethod
    def _insert_sorted(items, item):
        """New list with `item` inserted at its sorted position — the
        incremental canonical-multiset key (sorting 60 tags per expansion
        was the forge's hottest line at large sizes)."""
        out = list(items)
        lo, hi = 0, len(out)
        while lo < hi:
            mid = (lo + hi) // 2
            if out[mid] < item:
                lo = mid + 1
            else:
                hi = mid
        out.insert(lo, item)
        return out

    def forge(self, size, locked=None, locked_combos=None, pool=None, beam_width=8):
        """Build the best N-player roster the constraints allow: deterministic
        beam search over complete rosters, then constraint-aware 1-opt and a
        bounded 2-opt refinement, then a filler audit.

        `locked` members (with optional `locked_combos`) are the caller's —
        manual or live-party slots. They are never rewritten, they count
        toward every constraint, and they may be weapons the viability rules
        would not generate (their slots are flagged by swap_review, not
        here). Returns {"party", "combos", "score", "feasible", "filler",
        "held", "locked"}; `feasible` False means the constraints could not
        be met at this size (the roster is partial/provisional — the UI must
        say so instead of silently inserting negative filler); `filler`
        lists generated slot indexes whose members REDUCE comp_score while
        NOT being needed by any minimum constraint — structural saturation
        the caller must surface, never hide; `held` lists negative slots a
        minimum constraint mandates (e.g. the required 2nd healer in a party
        whose heal supply the objective already deems covered) — the cost of
        expert structure the scalar objective misses, surfaced as a note."""
        locked = list(locked or [])
        # normalize locked_combos to EXACTLY len(locked): a missing/short/
        # empty list pads with None (default combos), extras are dropped — a
        # misaligned combos list used to crash Python and silently mis-pair
        # combos with members in JS (review 2026-08-18)
        lc = locked_combos or []
        combos = [lc[i] if i < len(lc) else None for i in range(len(locked))]
        cand_pool = list(pool) if pool is not None else list(self.suggest_pool())
        ctx = self._forge_ctx(cand_pool)
        feasible = True

        counts, roles, preds, groups = self._forge_counts(locked)
        state = self.party_state(locked, combos)
        items0 = sorted(self._member_tag(w, c) for w, c in zip(locked, combos))
        beams = [{"party": locked, "combos": combos,
                  "counts": counts, "roles": roles, "preds": preds,
                  "groups": groups, "state": state, "items": items0,
                  "score": self.comp_score(locked, combos)}]
        for depth in range(len(locked), size):
            slots_left_after = size - depth - 1
            expansions = []
            for bi in range(len(beams)):
                beam = beams[bi]
                for w in cand_pool:
                    if not self._forge_feasible(ctx, beam["counts"], beam["roles"],
                                                beam["preds"], beam["groups"], w,
                                                slots_left_after):
                        continue
                    sc, _df, _ds, _meta, combo = self._eval_pick(beam["state"], w)
                    expansions.append((beam["score"] + sc, bi, w, combo))
            if not expansions:
                feasible = False
                break
            # stable sort by score only: equal scores keep (beam, pool) append
            # order — deterministic in both engines. The canonical multiset
            # key is computed LAZILY, only for candidates actually considered
            # for the beam (it was the hottest line at size 60).
            expansions.sort(key=lambda t: -t[0])
            next_beams, seen = [], set()
            for score, bi, w, combo in expansions:
                beam = beams[bi]
                items = self._insert_sorted(beam["items"], self._member_tag(w, combo))
                key = "|".join(items)
                if key in seen:
                    continue
                seen.add(key)
                party2 = beam["party"] + [w]
                combos2 = beam["combos"] + [combo]
                counts2, roles2, preds2, groups2 = self._forge_counts(party2)
                next_beams.append({"party": party2, "combos": combos2,
                                   "counts": counts2, "roles": roles2,
                                   "preds": preds2, "groups": groups2,
                                   "state": self.party_state(party2, combos2),
                                   "items": items,
                                   "score": self.comp_score(party2, combos2)})
                if len(next_beams) >= beam_width:
                    break
            beams = next_beams
        best = beams[0]
        party, combos = best["party"], best["combos"]
        fixed = len(locked)
        if len(party) > fixed:
            # refine -> pair-trade -> refine: a 2-opt pair gain can leave one
            # of its two slots individually negative; the closing 1-opt pass
            # cleans that up (or the filler audit below surfaces it honestly)
            party, combos = self._refine_constrained(ctx, party, combos, fixed)
            party, combos = self._two_opt(ctx, party, combos, fixed)
            party, combos = self._refine_constrained(ctx, party, combos, fixed)
        # filler audit — a generated member that REDUCES the objective is
        # surfaced, never silently kept quiet. A negative slot whose removal
        # would break a minimum constraint is `held` (mandated structure);
        # one the constraints don't need is `filler` (must not survive the
        # refinement passes — pinned by tests/test_forge.py).
        filler, held = [], []
        base = self.comp_score(party, combos)
        for i in range(fixed, len(party)):
            sub = party[:i] + party[i + 1:]
            sub_c = combos[:i] + combos[i + 1:]
            if base - self.comp_score(sub, sub_c) >= -1e-9:
                continue
            _counts, roles, preds, _groups = self._forge_counts(sub)
            needed = False
            for r, mn in ctx["role_min"].items():
                if roles.get(r, 0) < mn:
                    needed = True
                    break
            if not needed:
                for pn, mn in ctx["pred_min"].items():
                    if preds.get(pn, 0) < mn:
                        needed = True
                        break
            (held if needed else filler).append(i)
        return {"party": party, "combos": combos, "score": base,
                "feasible": feasible, "filler": filler, "held": held,
                "locked": fixed}

    def _swap_ok(self, ctx, counts, roles, preds, groups, orig, w):
        """Constraint check for replacing a member `orig` with `w`, against
        the CURRENT roster's precomputed counts — O(1) deltas (a full count
        rebuild per candidate was the forge's dominant cost at size 60).
        Only what the swap can push OVER a max (w's copies, w's groups, w's
        role) or UNDER a min (orig's role, predicate membership orig had)
        needs checking; everything else moves the safe direction."""
        if counts.get(w, 0) + 1 > self._dup_gen_max(w):
            return False
        gw = self.groups_of.get(w, [])
        if gw:
            go = self.groups_of.get(orig, [])
            for gi in gw:
                after = groups.get(gi, 0) + 1 - (1 if gi in go else 0)
                if after > self.groups[gi].get("max", 10 ** 9):
                    return False
        ro, rw = self.role_of(orig), self.role_of(w)
        if rw != ro:
            mx = ctx["role_max"].get(rw)
            if mx is not None and roles.get(rw, 0) + 1 > mx:
                return False
            mn = ctx["role_min"].get(ro)
            if mn is not None and roles.get(ro, 0) - 1 < mn:
                return False
        for pn, mn in ctx["pred_min"].items():
            members = self.pred_members[pn]
            d = (1 if w in members else 0) - (1 if orig in members else 0)
            if preds.get(pn, 0) + d < mn:
                return False
        return True

    def _refine_constrained(self, ctx, party, combos, fixed, max_passes=8):
        """Steepest-descent 1-opt over generated slots, constraint-aware.
        Replacement combos re-resolve dynamically (the replacement is scored
        exactly as a pick into the rest of the party)."""
        party, combos = list(party), list(combos)
        best = self.comp_score(party, combos)
        for _ in range(max_passes):
            counts, roles, preds, groups = self._forge_counts(party)
            move, gain = None, 1e-9
            for i in range(fixed, len(party)):
                rest = party[:i] + party[i + 1:]
                rest_c = combos[:i] + combos[i + 1:]
                state = self.party_state(rest, rest_c)
                base_rest = self.comp_score(rest, rest_c)
                contrib = best - base_rest
                orig = party[i]
                for w in ctx["pool"]:
                    if w == orig:
                        continue
                    if not self._swap_ok(ctx, counts, roles, preds, groups, orig, w):
                        continue
                    sc, _df, _ds, _meta, combo = self._eval_pick(state, w)
                    d = sc - contrib
                    if d > gain:
                        move, gain = (i, w, combo), d
            if move is None:
                break
            party[move[0]] = move[1]
            combos[move[0]] = move[2]
            best = self.comp_score(party, combos)
        return party, combos

    def _two_opt(self, ctx, party, combos, fixed, worst_k=4, cand_m=12):
        """Bounded 2-opt: re-solve the `worst_k` weakest generated slots in
        pairs, drawing replacements from the top `cand_m` single-slot
        candidates. Catches pair-trades 1-opt cannot see; bounded so the
        browser build stays under the perf targets. An accepted pair-move
        REORDERS the roster (the pair is removed, replacements append), so
        the pass restarts with freshly computed weakest slots — stale
        indexes used to re-solve arbitrary slots (review 2026-08-18)."""
        party, combos = list(party), list(combos)
        best = self.comp_score(party, combos)
        if len(party) - fixed < 2:
            return party, combos
        passes = 0
        improved = True
        while improved and passes < 3:
            improved = False
            passes += 1
            gen = list(range(fixed, len(party)))
            contribs = []
            for i in gen:
                sub = party[:i] + party[i + 1:]
                sub_c = combos[:i] + combos[i + 1:]
                contribs.append((best - self.comp_score(sub, sub_c), i))
            contribs.sort(key=lambda t: (t[0], t[1]))
            worst = [i for _c, i in contribs[:worst_k]]
            for x in range(len(worst)):
                if improved:
                    break
                for y in range(x + 1, len(worst)):
                    if improved:
                        break
                    i, j = worst[x], worst[y]
                    if j < i:
                        i, j = j, i
                    rest = party[:i] + party[i + 1:j] + party[j + 1:]
                    rest_c = combos[:i] + combos[i + 1:j] + combos[j + 1:]
                    state = self.party_state(rest, rest_c)
                    ranked = []
                    for w in ctx["pool"]:
                        sc, _df, _ds, _meta, combo = self._eval_pick(state, w)
                        ranked.append((sc, w, combo))
                    ranked.sort(key=lambda t: (-t[0], t[1]))
                    shortlist = ranked[:cand_m]
                    for sa, wa, ca in shortlist:
                        if improved:
                            break
                        pa = rest + [wa]
                        pca = rest_c + [ca]
                        state2 = self.party_state(pa, pca)
                        for _sb, wb, _cb in shortlist:
                            sc_b, _df2, _ds2, _m2, cb2 = self._eval_pick(state2, wb)
                            cand_party = pa + [wb]
                            cand_combos = pca + [cb2]
                            counts, roles, preds, groups = self._forge_counts(cand_party)
                            ok = True
                            for wk, c in counts.items():
                                if c > self._dup_gen_max(wk):
                                    ok = False
                                    break
                            if ok:
                                for gi, g in enumerate(self.groups):
                                    if groups.get(gi, 0) > g.get("max", 10 ** 9):
                                        ok = False
                                        break
                            if ok:
                                for r, mx in ctx["role_max"].items():
                                    if roles.get(r, 0) > mx:
                                        ok = False
                                        break
                            if ok:
                                for r, mn in ctx["role_min"].items():
                                    if roles.get(r, 0) < mn:
                                        ok = False
                                        break
                            if ok:
                                for pn, mn in ctx["pred_min"].items():
                                    if preds.get(pn, 0) < mn:
                                        ok = False
                                        break
                            if not ok:
                                continue
                            d = self.comp_score(cand_party, cand_combos) - best
                            if d > 1e-9:
                                party = cand_party
                                combos = cand_combos
                                best = best + d
                                improved = True
                                break
        return party, combos


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
    ap.add_argument("--forge", action="store_true",
                    help="forge a full comp at --size, locking any listed weapons")
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
    if args.forge:
        r = e.forge(e.size, locked=party)
        print(f"\nForged {len(r['party'])}/{e.size} ({e.template['name']}, "
              f"size {e.size}{style_bit})  score {r['score']:.3f}  "
              f"feasible={r['feasible']}  filler={r['filler']}")
        for i, w in enumerate(r["party"]):
            tag = "locked" if i < r["locked"] else "forged"
            print(f"  {i + 1:2}. [{tag}] {e.weapons[w]['display_name']}")
        raise SystemExit(0)
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
            flag = "  [off-comp]" if m.get("off_comp") else ""
            print(f"  {m['index'] + 1}. {m['display_name']:<24} "
                  f"rank {m['rank']:>3}/{len(e.weapons)}  better: {opts}{flag}")
    recs = e.recommend(party)
    print(f"\nRecommend: {recs[0]['display_name']}  (score {recs[0]['score']:.2f})")
    for t in e.explain(party, recs[0]["weapon"])[:4]:
        print(f"  +{t['delta']:5.2f}  {t['cap']}: {t['before']:.0f} → {t['after']:.0f} "
              f"(target {t['target']:.1f})")
    print(f"Alternatives: {[r['display_name'] for r in recs[1:]]}")
