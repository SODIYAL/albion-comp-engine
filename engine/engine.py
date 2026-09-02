#!/usr/bin/env python3
"""
Composition scoring engine (design doc §3.2, §4.1; Forge rework 2026-08-18).

Consumes the built dataset (pipeline/out/dataset-latest.json) — never hardcoded
capability numbers. This is the graduation of tests/prototype_engine.py from a
throwaway with inline dicts into the real engine reading curated data.

The objective (one, canonical — everything scores THIS, marginally or whole):
    U_c(s)   = weight * min(1, s/target)^gamma      concave utility
             + headroom * weight * min(s-target, span)/span, span=soft-target
                                                     headroom bonus
             - omax * weight * x/(1+x), x=(s-soft)/soft   over-stack penalty
             - mult * weight * (floor - s_floor)/floor    hard-floor penalty
    fitness  = sum over capabilities
    synergy  = sum over TEMPLATE-ACTIVE pairs of
               bonus * max(0, min(capped_a, capped_b) - best_self_joint)
    comp     = alpha*fitness + beta*synergy + delta*sum(meta)
             + viability*sum(core_bonus) - rho*sum(extra-copy units)

A candidate's pick score is EXACTLY comp(party+candidate) - comp(party) for the
candidate's chosen loadout — the invariant tests/test_forge.py pins at 1e-9.
Party members are weapon unique_names (e.g. "2H_MACE"), matching the dataset;
an optional parallel `combos` list pins each member's one-spell-per-slot
loadout (None = the static default for the current content+style), and an
optional parallel `gears` list dresses each member with their worn kit
(dressed forge 2026-08-27; None = weapon-only, bit-identical to the legacy
path). TWO SUPPLIES, deliberately: coverage / headroom / over-stack read the
DRESSED supply, while the hard-floor term reads `s_floor` — the weapon+loadout
supply only (Option C, owner ruling 2026-08-27), so worn gear can never buy
its way past a structural floor.

KNOWN OPEN DEFECT (ruling pending, see HANDOFF.md): every `target` and
`soft_cap` in the dataset was fitted in WEAPON+spell-pick units, while the
supply above is measured on whole dressed people (~1.88x on average, ~7x on
tankiness). The math here is unaffected — but the two sides of every
comparison are currently in different units, and the correction must move
every template row at once.
"""
import json, os, itertools, re

HERE = os.path.dirname(os.path.abspath(__file__))

_KEY_TIER_RX = re.compile(r"^T\d+_")
_KEY_ENCH_RX = re.compile(r"@\d+$")


def _key_form(key):
    """A gear key stripped of tier and enchant: 'T7_POTION_REVIVE@2' ->
    'POTION_REVIVE'. Mirrors pipeline/builds_lib.key_form — see gear_key()."""
    return _KEY_TIER_RX.sub("", _KEY_ENCH_RX.sub("", str(key).strip().upper()))
# BION_DATASET: tooling override for the default dataset PATH (the
# calibration sweep points test suites at patched coefficient copies —
# pipeline/calibrate_scoring.py). Path plumbing only; never set in
# production or normal test runs.
DATASET = os.environ.get("BION_DATASET") or \
    os.path.join(HERE, os.pardir, "pipeline", "out", "dataset-latest.json")

# Mechanics-affected capability families (MECHANICS_TODO.md, 2026-08-13):
# AoE Escalation multiplies AoE damage effectiveness by targets hit;
# Focus Fire (Resilience) cuts focused single-target damage by attackers-on-
# target. sustained_dps is deliberately in NEITHER family — brawl sustained
# damage is spread across targets, so neither curve cleanly applies.
AOE_ESCALATION_CAPS = ("burst_aoe",)
RESILIENCE_CAPS = ("burst_st", "execute")


class Engine:
    # Flag predicate name (2026-08-23): satisfied by the dataset's static
    # full_healer flag, not capability thresholds — see __init__.
    PRIMARY_HEAL = "primary_heal"
    def __init__(self, dataset_path=DATASET, content="castle_outpost", size=7,
                 style="balanced"):
        with open(dataset_path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.weapons = self.data["weapons"]
        self.scoring = self.data["scoring"]
        # 1-7 scale (2026-08-20): score_unit converts sheet points to supply
        # units (2 points = 1 unit) — templates/floors/synergies stay in the
        # units they were calibrated in. Older datasets (0-3 sheets) carry no
        # score_unit and divide by 1.
        self.score_unit = float(self.scoring.get("score_unit", 1))
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
        # Gear capability sheets (full-build members, 2026-08-20)
        self.gear = self.data.get("gear", {}) or {}
        # Tier-agnostic index for gear_key() (owner ruling 2026-08-28). Built
        # only for UNAMBIGUOUS tier-stripped forms: if two curated items share
        # one, the form is dropped so the lookup fails rather than guesses.
        _forms = {}
        for _k in self.gear:
            _forms.setdefault(_key_form(_k), []).append(_k)
        self._gear_alias = {f: ks[0] for f, ks in _forms.items()
                            if len(ks) == 1 and f not in self.gear}
        # PvP interaction records (build_interactions.py, 2026-08-19),
        # spell-keyed. The scoring coupling is deliberately narrow: a
        # VERIFIED record may declare nonstacking_caps — capability names
        # whose party supply counts ONCE across members equipping that same
        # spell (largest single contribution, not the sum: refresh/override
        # semantics). unknown/likely records never change a score; all other
        # interaction data is analysis/display only.
        self.interactions = self.data.get("interactions", {}) or {}
        self.nonstack = {}
        for _sid in sorted(self.interactions):
            _rec = self.interactions[_sid]
            if _rec.get("confidence") == "verified" and _rec.get("nonstacking_caps"):
                self.nonstack[_sid] = list(_rec["nonstacking_caps"])
        # SUPER-ADDITIVE DUPLICATES (2026-08-28) — the mirror of the
        # count-once rule above, and held to the same bar: a VERIFIED record
        # declaring `self_cost_offset_min_copies: N` means N copies of the
        # item cover each other's SELF-COST (Demon Armor wearers stand in one
        # another's aura). Resolved here from the cost's evidence spell to
        # the gear key that carries it, so the hot path is a dict lookup.
        # gear key -> minimum copies. Cancels a cost, never adds supply.
        self._cost_offsets = {}
        for _gk, _g in (self.gear or {}).items():
            for _cap, _sid in (_g.get("self_cost_evidence") or {}).items():
                _rec = self.interactions.get(_sid) or {}
                _n = _rec.get("self_cost_offset_min_copies")
                if _rec.get("confidence") == "verified" and _n:
                    self._cost_offsets[_gk] = min(
                        self._cost_offsets.get(_gk, _n), _n)
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
        # The ROLE BOOK (roles-design.md, owner-approved 2026-08-25):
        # fine roles with evidence-cited membership; weapons carry the
        # derived role_menu. Feeds detect_role/role_advisory only —
        # DESCRIPTIVE, nothing in the scoring path reads it.
        self.roles = {r.get("id"): r for r in (self.data.get("roles") or [])}
        # Typed gear-carried effects (owner 2026-08-25): item id -> the
        # effect ids it grants; role_advisory reports "role + carrying".
        self._item_effects = {}
        for ge in (self.data.get("gear_effects") or []):
            for it in (ge.get("items") or []):
                if it.get("id"):
                    self._item_effects.setdefault(it["id"], []) \
                        .append(ge.get("id"))
        # Capability predicates (composition.yaml). Membership is COMBO-AWARE
        # since 2026-08-19: the §B rework put ranged_presence in spell
        # bundles, so a member counts toward ranged_aoe_core only when the
        # spell combination it actually equips supplies the minima — the flat
        # sheet map says "could, with the right spells", never "does".
        # pred_members keeps the flat could-qualify view (display/back-compat
        # + the optimistic beam bound via _pred_possible); every forge
        # constraint counts through _pred_contrib(weapon, combo).
        self.pred_defs = comp.get("predicates", {}) or {}
        self.pred_members = {}
        for name, mins in self.pred_defs.items():
            self.pred_members[name] = set(
                k for k, d in self.weapons.items()
                if all(d["capabilities"].get(c, 0) >= v for c, v in mins.items()))
        # Flag predicate `primary_heal` (owner ruling 2026-08-23): band
        # minima counted from the static per-weapon full_healer flag
        # (build_dataset derive_economics — high healing on the E; the E is
        # combo-independent, so unlike capability predicates every combo of
        # a full healer qualifies). Routed through the same pred machinery
        # so the forge's feasibility/eval/audit paths need no special case.
        self.pred_members[self.PRIMARY_HEAL] = set(
            k for k, d in self.weapons.items() if d.get("full_healer"))
        # raw-caps predicate caches — content-independent (raw loadout numbers)
        self._pred_cache = {}
        self._pred_possible_cache = {}
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
        # members of derived NON-STACKING groups (shared kit priced
        # count-once — the cursed line): their group-band slots are
        # EARNED (owner ruling 2026-08-25; see the generation-fit gate)
        self.nonstack_members = {wk for g in self.groups
                                 if g.get("nonstacking")
                                 for wk in g.get("weapons", [])}
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
        # Candidate dressing (dressed forge 2026-08-27) is ON by default —
        # production behavior. set_dressing(False) is a VALIDATION affordance
        # (V3-W symmetric weapon-only comparisons); nothing in the product
        # turns it off.
        self.dress_candidates = True
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
        # Clump anchors for the GEOMETRIC transform (2026-08-20): how many
        # enemies this style/size expects an AoE to reach, and the (balanced,
        # base_size) anchor it is normalized against — the same inputs the
        # escalation mult reads, kept so _geo_mult stays anchor-consistent.
        self._clump_now = grown(style_mech.get("expected_aoe_targets"), mult_now)
        self._clump_base = grown(base_mech.get("expected_aoe_targets"), mult_base)
        geo = self.mechanics.get("aoe_geometry") or {}
        self._geo_caps = set(geo.get("geometric_caps") or [])
        self._geo_cc_caps = set(geo.get("cc_duration_caps") or [])
        self._geo_cap_targets = geo.get("escalation_cap_targets", 8)
        self._geo_ref = geo.get("reference_clump")   # null -> base-clump anchor
        rt = geo.get("radius_targets") or {}
        self._radius_targets_table = sorted((float(k), rt[k]) for k in rt)
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
        # Resilience-Penetration context (owner ruling 2026-08-25: "you can
        # wire it as partial rebate"): the Focus-Fire damage reduction at
        # THIS style's grown focus count. A weapon with `resil_pen` p
        # ignores that fraction of the reduction, so its ST supply is
        # rebated by (1 - DR*(1-p)) / (1 - DR) in _eff — pure physics from
        # the owner-confirmed mechanics table, per weapon, on top of the
        # global (weapon-blind) style/size multipliers and the st_value
        # weight devaluation, which stay untouched: high-pen ST is taxed
        # less, never made good.
        self._pen_dr = 0.0
        focus_now = grown(style_mech.get("focus_attackers"), mult_now)
        if focus_now:
            self._pen_dr = 1.0 - self._resilience_eff(focus_now)
        # Per-context caches — constant until the next set_content: scaled
        # targets/soft caps, styled weights, per-weapon loadout combos.
        # PER-STYLE TARGET MODIFIERS (styles.yaml `target_mults`). Weight
        # multipliers say what a style VALUES; these say HOW MUCH OF IT the
        # style actually needs — the owner's case: "clap comp would require
        # more peel and disengage than brawl comp". Target and soft cap scale
        # TOGETHER so the headroom band keeps its shape; hard floors do NOT
        # scale (a kite comp still needs its healers — the same rule the
        # weight overlay has always followed), though the existing clamp
        # still keeps a floor from exceeding the target it guards.
        # DEFAULT IS IDENTITY: every style ships {} until the owner rules a
        # value, so this mechanism changes nothing on its own.
        self.target_mults = (styles.get(style, {}) or {}).get(
            "target_mults", {}) or {}
        _tm = lambda c: self.target_mults.get(c, 1.0)
        self._targets = {c: _tm(c) * (r["target"] * self.size / self.base_size
                                      if r.get("scales") else r["target"])
                         for c, r in self.reqs.items()}
        self._softs = {c: _tm(c) * (r["soft_cap"] * self.size / self.base_size
                                    if r.get("scales") else r["soft_cap"])
                       for c, r in self.reqs.items()}
        self._weights = {c: r["weight"] * self.style_mults.get(c, 1.0)
                         for c, r in self.reqs.items()}
        # OPTIONAL capabilities (owner ruling 2026-08-28). Some capabilities
        # are real and worth having but are not something every comp must
        # field: `anti_zone` exists on exactly ONE weapon in the catalogue
        # (Exalted Staff, the crystal holy staff) and is a 30+ ZvZ tool;
        # `execute` sits on five single-target melee weapons. Owner: "it's
        # fine to keep those targets just maybe make some optional... as for
        # execute keep that too but optional."
        #
        # Optional means: bringing it still earns its coverage exactly as
        # before, but NOT bringing it is not a hole. Mechanically that is a
        # DENOMINATOR-only rule — every fitness term for a capability at zero
        # supply is already zero (coverage 0/target, headroom needs
        # have>target, over-stack needs have>soft) — so an optional capability
        # can only be dropped from max_fitness(), never from fitness(). No
        # score, ranking, or pick value moves; only the percentage shown.
        # A hard floor would break that identity, so the two are incompatible
        # and the build fails loudly rather than scoring inconsistently.
        self.optional = {c for c, r in self.reqs.items() if r.get("optional")}
        bad = sorted(self.optional & set(self.floors))
        if bad:
            raise ValueError(
                f"template '{self.content}': {', '.join(bad)} marked optional "
                "but carries a hard floor — a floor is charged at zero supply, "
                "so the capability is mandatory by construction")
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
        # Hot-path tables (forge profile 2026-08-26): per-cap scoring
        # constants and per-pair synergy constants resolved once per
        # context. Pure lookup elimination for _marg_fit_pre/_marg_syn_pre
        # — every float op keeps the exact operands and order of
        # _cover_terms/_floor_penalty/_overstack/_pair_value.
        self._cap_tab = {}
        for c in self.reqs:
            f = self.floors.get(c)
            armed = f is not None and self.size >= f["min_party_size"]
            self._cap_tab[c] = (
                self._targets[c], self._softs[c], self._weights[c],
                self.reqs[c]["weight"],
                (self._floors_eff[c], f["penalty_mult"]) if armed else None)
        self._syn_tab = [(a, b, bonus, self._targets[a], self._targets[b])
                         for (a, b, bonus) in self._active_syn]
        self._syn_by_cap = {}
        for p, (a, b, _bonus) in enumerate(self._active_syn):
            self._syn_by_cap.setdefault(a, []).append(p)
            self._syn_by_cap.setdefault(b, []).append(p)
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
        # Economics gate (owner ruling 2026-08-23, composition.yaml
        # viability.cost_gate): a cost tier may be barred from SUGGESTIONS
        # and generation below a party size — crystal regear economics make
        # it a rich-group choice, not a default the forge should produce.
        # Exactly like an exclusion: manual/locked picks always score;
        # swap_review flags them off_budget.
        self._cost_gated = set()
        for tier, rule in (via.get("cost_gate", {}) or {}).items():
            mn = (rule or {}).get("min_size")
            if mn and self.size < mn:
                for wk in self.pool:
                    if self.weapons[wk].get("cost_tier") == tier:
                        self._cost_gated.add(wk)
        self._suggest = [w for w in self.pool
                         if w not in excl and w not in self._cost_gated]
        # Style-fit suggestion gate (identity Phase C — owner ruling
        # 2026-08-23: style selection IS build intent; "clap comp should
        # never get suggestions like battle-axe"). A weapon whose derived
        # style_fit verdict is UNFIT for the DECLARED style at this size
        # band leaves the suggestion pool exactly like a viability
        # exclusion: barred from suggestions and generation, never from
        # scoring; swap_review flags such members off_style. Balanced
        # declares no intent and gates nothing; datasets without
        # style_fit gate nothing.
        self._style_unfit = set()
        if self.style in self.IDENTITY_STYLES:
            band = self._fit_band()
            for wk in self.pool:
                sf = self.weapons[wk].get("style_fit")
                if sf and (sf["fit"].get(self.style) or {}).get(band) == "unfit":
                    self._style_unfit.add(wk)
            if self._style_unfit:
                self._suggest = [w for w in self._suggest
                                 if w not in self._style_unfit]
        # Generation-fit gate (owner ruling 2026-08-23, forge-quality round
        # 3): the graded misses — Dagger/Boltcasters at 15 ("can only
        # damage 1 person at a time with e and that's not good for
        # anything higher than 3v3"), ranged bombs and single-target
        # fillers in a 25 brawl — all derive SITUATIONAL for their
        # context, and situational never gated. The rule the gradings
        # imply: a DEFAULT generated comp fields damage picks the
        # derivation says FIT — "situational" means the caller knows a
        # situation the engine cannot, so it stays a manual pick (scores
        # normally, never flagged). DPS role only: healers, frontline and
        # support keep their standing rules (a single-scale healer may
        # still take a non-foundation gang slot — owner ruling, same
        # session). Balanced requires fits for at least ONE style at the
        # band; trio sizes gate nothing (standing Phase C rule).
        # WHERE "situational" COMES FROM (all derived in
        # build_dataset.derive_style_fit, audited in
        # out/style_fit_report.json — this gate only reads the verdict):
        # delivery vs style, the weak-group-E rule, the single-ally-heal-E
        # healer rule, the non-stacking debuff rule, and — since
        # 2026-08-27 — the CONDITIONAL-PAYLOAD rule: a group damage carrier
        # whose every damage E needs ramp (consumes charges other spells
        # build) or a non-ranged channel is situational at clap/kite/
        # clap_kite, because those styles want damage that lands from one
        # action. That is why Clarent Blade and Ursine Maulers stopped
        # generating in clap comps while keeping every brawl slot.
        self._gen_situational = set()
        band = self._fit_band()
        if band != "trio":
            for wk in self.pool:
                role = self.role_of(wk)
                sf = self.weapons[wk].get("style_fit")
                if not sf:
                    continue
                if role == "dps":
                    if self.style in self.IDENTITY_STYLES:
                        ok = (sf["fit"].get(self.style) or {}) \
                            .get(band) == "fits"
                    else:
                        ok = any((sf["fit"].get(s) or {}).get(band) == "fits"
                                 for s in self.IDENTITY_STYLES)
                elif role == "healer" and band == "group":
                    # owner round 4 (2026-08-23): "there is no way 1hand
                    # holy should be in a 15 man party ... no chance above
                    # 9" — a healer unfit at group for EVERY style (the
                    # single-ally-heal-E class) never generates, balanced
                    # included. Gang slots stay open (the Druidic ruling).
                    ok = not all((sf["fit"].get(s) or {}).get(band) == "unfit"
                                 for s in self.IDENTITY_STYLES)
                elif wk in self.nonstack_members and band == "group":
                    # owner ruling 2026-08-25: a non-stacking budget slot
                    # (the cursed line — its shared Q priced count-once)
                    # is EARNED at group scale: "the only weapon i see in
                    # any party bigger than 15 people is the lifecurse,
                    # damnation, or rotcaller." The derivation demotes
                    # debuff-less members to situational at group for
                    # every style; the dps fits-rule then bars them from
                    # DEFAULT generation, balanced included. Manual picks
                    # score normally, never flagged.
                    if self.style in self.IDENTITY_STYLES:
                        ok = (sf["fit"].get(self.style) or {}) \
                            .get(band) == "fits"
                    else:
                        ok = any((sf["fit"].get(s) or {}).get(band) == "fits"
                                 for s in self.IDENTITY_STYLES)
                else:
                    continue
                if not ok:
                    self._gen_situational.add(wk)
            if self._gen_situational:
                self._suggest = [w for w in self._suggest
                                 if w not in self._gen_situational]
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
        # Style role-band overrides (owner ruling 2026-08-23, styles.yaml
        # constraint_overrides): the base bands were calibrated on brawl
        # evidence and were style-blind — kite/clap forged brawl-shaped
        # rosters. A listed key REPLACES the base band's entry; unlisted
        # keys keep the base band. First matching row wins, like the base.
        if self._band is not None:
            for row in (styles.get(self.style, {}) or {}) \
                    .get("constraint_overrides", []) or []:
                if row.get("min_size", 0) <= self.size <= row.get("max_size", 10 ** 9):
                    merged = dict(self._band)
                    for key, rule in row.items():
                        if key not in ("min_size", "max_size"):
                            merged[key] = rule
                    self._band = merged
                    break
        # NEED PROFILES (increment 3, owner-ruled 2026-08-26): fine-seat
        # bands + function coverage minima for the FORGE, scaled by
        # size/reference_size (half-up, the pinned rounding rule) and
        # armed at min_size. SEAT keys count a weapon's PRIMARY menu
        # seat; FUNCTION keys count any primary/secondary membership.
        # Generation-only: manual parties always score.
        self._profile_min, self._profile_max = {}, {}
        self._profile_members, self._profile_primary = {}, {}
        prof = self.data.get("need_profiles") or {}
        if prof and self.size >= prof.get("min_size", 15):
            ref = prof.get("reference_size", 20)
            rules = dict(prof.get("defaults") or {})
            for k, v in (((prof.get("overrides") or {})
                          .get(self.content)) or {}).items():
                rules[k] = v
            for k, rule in rules.items():
                if "min" in rule:
                    mn = self._half_up(rule["min"] * self.size / ref)
                    if mn > 0:
                        self._profile_min[k] = mn
                if "max" in rule:
                    self._profile_max[k] = self._half_up(
                        rule["max"] * self.size / ref)
            keys = set(self._profile_min) | set(self._profile_max)
            for wk, w in self.weapons.items():
                menu = w.get("role_menu") or []
                sec = w.get("role_menu_secondary") or []
                contrib = set()
                if menu and menu[0] in keys:
                    contrib.add(menu[0])
                for f in ("pierce", "anti_heal", "purge", "shield_break"):
                    if f in keys and (f in menu or f in sec):
                        contrib.add(f)
                if contrib:
                    self._profile_members[wk] = frozenset(contrib)
                if menu:
                    self._profile_primary[wk] = menu[0]
        self._extras_cache = {}
        self._pre_cache = {}
        self._default_cache = {}
        self._gear_cache = {}
        self._ns_cache = {}
        self._variant_cache = {}
        self._dressed_cache = {}
        self._dressed_pre_cache = {}
        self._floor_gain_cache = {}

    def set_dressing(self, enabled):
        """Validation affordance (V3-W, 2026-08-27): when OFF, every
        CANDIDATE evaluates naked — kit_variants yields [("v0", None)] for
        all weapons, _dressed_extras aliases the weapon-only combo vectors,
        and _combo_score_dressed's identity check routes into _combo_score.
        Same formula, no second scoring path; with dressing ON, behavior is
        bit-identical to before this switch existed. Clears the dressed
        caches so vectors built under the other setting cannot leak."""
        self.dress_candidates = bool(enabled)
        self._variant_cache = {}
        self._dressed_cache = {}
        self._dressed_pre_cache = {}

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

    def is_style_unfit(self, weapon):
        """True when the weapon's derived style_fit is UNFIT for the
        DECLARED style at this size band (identity Phase C). Bars
        suggestions only — scoring is never blocked; the dashboard flags
        such members off-style."""
        return weapon in self._style_unfit

    def is_cost_gated(self, weapon):
        """True when the weapon's cost tier bars it from GENERATED comps at
        this size (crystal regear economics, owner ruling 2026-08-23).
        Suggestions only — a manual/locked pick always scores; the
        dashboard flags such members off-budget."""
        return weapon in self._cost_gated

    def suggest_pool(self):
        """The default candidate pool for every suggestion/generation path:
        non-retired weapons minus the viability exclusions for this context."""
        return self._suggest

    # ------------------------------------------------------------ role layer
    # roles-design.md increment 1 (owner-approved 2026-08-25): a role is a
    # property of the member-in-comp — weapon x kit x what the team needs —
    # never 1:1 with the weapon. Everything here is DESCRIPTIVE: no scoring
    # or generation path reads it (test_roles R5 pins that).
    @staticmethod
    def _chest_class(gear_id):
        """Armor class of a chest gear id (ARMOR_<CLASS>_...), or None."""
        for c in ("PLATE", "LEATHER", "CLOTH"):
            if gear_id and c in gear_id.split("_"):
                return c.lower()
        return None

    def detect_role(self, weapon, chest=None):
        """The fine role a member is PLAYING: the weapon's role_menu read
        against the equipped chest's armor class. SEAT roles carry a chest
        uniform; FUNCTION roles (pierce/purge/anti_heal — owner correction
        2026-08-25: the function is the role, never the tree) have none
        and ride along in `functions` — kits are judged against seat
        roles only (Incubus cuts heals in tank plate, Carrioncaller in
        brawler leather). kit_match None = nothing to judge; True = the
        chest fits a seat's uniform; False = no seat this weapon plays
        wears that chest class."""
        menu = self.weapons[weapon].get("role_menu") or []
        menu2 = list(self.weapons[weapon].get("role_menu_secondary") or [])
        if not menu:
            return {"role": None, "class": self.role_of(weapon),
                    "kit_match": None, "functions": [],
                    "secondary": menu2}
        uni_of = lambda rid: ((self.roles.get(rid) or {}).get("uniform")
                              or {}).get("chest") or []
        seats = [rid for rid in menu if uni_of(rid)]
        functions = [rid for rid in menu if not uni_of(rid)]
        if not seats:
            rid = menu[0]
            return {"role": rid,
                    "class": (self.roles.get(rid) or {}).get("class")
                    or self.role_of(weapon), "kit_match": None,
                    "functions": [r for r in functions if r != rid],
                    "secondary": menu2}
        cls = self._chest_class(chest)
        if cls is None:
            rid = seats[0]
            return {"role": rid,
                    "class": (self.roles.get(rid) or {}).get("class")
                    or self.role_of(weapon), "kit_match": None,
                    "functions": functions, "secondary": menu2}
        for rid in seats:
            if cls in uni_of(rid):
                return {"role": rid,
                        "class": (self.roles.get(rid) or {}).get("class"),
                        "kit_match": True, "functions": functions,
                        "secondary": menu2}
        rid = seats[0]
        return {"role": rid,
                "class": (self.roles.get(rid) or {}).get("class"),
                "kit_match": False, "functions": functions,
                "secondary": menu2}

    def role_advisory(self, party, chests=None):
        """Descriptive role read of a roster: per-member played role +
        kit_match, a fine-role tally, and comp-level flags. v1 flags:
        `off_role_kit` per member (no role this weapon plays wears that
        chest) and `no_engage_tank` (group sizes, 2+ frontliners, nobody
        who can make a clump — the owner's "3 heavy maces in party and 0
        engage tanks would be an obvious flag"). NEVER a scoring or
        generation input."""
        chests = chests or {}
        members, tally = [], {}
        for i, w in enumerate(party):
            d = dict(self.detect_role(w, chests.get(i)))
            d["weapon"] = w
            d["carrying"] = list(self._item_effects.get(chests.get(i)) or [])
            members.append(d)
            key = d["role"] or d["class"]
            tally[key] = tally.get(key, 0) + 1
        flags = []
        for m in members:
            if m["kit_match"] is False:
                uni = ((self.roles.get(m["role"]) or {}).get("uniform")
                       or {}).get("chest") or []
                flags.append({
                    "kind": "off_role_kit", "weapon": m["weapon"],
                    "role": m["role"],
                    "detail": (f"no role this weapon plays wears that "
                               f"chest; its {m['role']} uniform is "
                               + "/".join(uni))})
        if self.size >= 10:
            front = [m for m in members
                     if ((self.roles.get(m["role"]) or {}).get("class")
                         if m["role"] else m["class"]) == "frontline"]
            engage = [m for m in members
                      if "engage_tank"
                      in (self.weapons[m["weapon"]].get("role_menu") or [])]
            if len(front) >= 2 and not engage:
                flags.append({
                    "kind": "no_engage_tank",
                    "detail": (f"{len(front)} frontliner(s), none can make "
                               "a clump — no engage tank")})
        return {"members": members, "tally": tally, "flags": flags}

    # ---------------------------------------------------------- loadout model
    # A weapon's sheet lists capabilities across ALL its Q/W/E/passive spell
    # options, but a player equips ONE per slot. A party member is therefore
    # (weapon, combo): one bundle per slot, merged over `always`. The SAME
    # combo machinery serves incumbents and candidates — the static-vs-dynamic
    # split that made recommend() disagree with comp_score() is gone. A
    # member's combo defaults to the static best under the current template
    # weights; the forge persists the combo it actually scored; the dashboard
    # pins combos from the player's real Q/W/passive picks.
    def _radius_targets(self, radius):
        """Expected targets AFFECTED by an area of `radius` sweeping the
        clump (mechanics.yaml aoe_geometry step table, PROVISIONAL)."""
        if not self._radius_targets_table:
            return 1.0
        v = self._radius_targets_table[0][1]
        for k, m in self._radius_targets_table:
            if k <= radius:
                v = m
            else:
                break
        return v

    def _geo_mult(self, cap, dent):
        """GEOMETRIC multiplier (2026-08-20, expert ruling in MECHANICS_TODO):
        an AoE effect does one target's worth of work per enemy it reaches, so
        AoE-delivered utility supply scales with expected targets affected —
        min(style clump, what the spell's footprint can plausibly cover) —
        normalized to the (balanced, base_size) anchor, where this is exactly
        1.0 by construction. No delivery facts (no structural area in the
        dumps, self-buffs, single-target) = flat 1.0: +40% self move speed
        catches ONE runner at any size. In-game CC Escalation (duration per
        target, the spell's own dumps factor) composes on top for the CC caps
        that have it."""
        if not dent or not self._clump_now or not self._clump_base:
            return 1.0
        r = dent.get("radius")
        if r is None:
            return 1.0
        reach = self._radius_targets(r)
        mt = dent.get("max_targets")
        if mt and mt < reach:
            reach = mt
        t_now = self._clump_now if self._clump_now < reach else reach
        anchor = self._geo_ref if self._geo_ref else self._clump_base
        t_base = anchor if anchor < reach else reach
        if t_base <= 0:
            return 1.0
        m = t_now / t_base
        f = (dent.get("escalation") or {}).get("duration")
        if f and cap in self._geo_cc_caps:
            cap8 = self._geo_cap_targets
            e_now = 1.0 + f * (min(t_now, cap8) - 1.0)
            e_base = 1.0 + f * (min(t_base, cap8) - 1.0)
            m *= e_now / e_base
        return m

    def _eff(self, caps, delivery=None, pen=0.0):
        """Apply mechanics multipliers (AoE escalation / Resilience) and the
        per-spell geometric transform to a bundle; sheet points convert to
        supply units through score_unit (1-7 scale, 2 points = 1 unit).
        `pen` is the wielder's Resilience Penetration: its burst_st/execute
        supply is rebated by the fraction of Focus-Fire reduction the stat
        ignores at this context's focus count (owner ruling 2026-08-25)."""
        out = {}
        for c, v in caps.items():
            v /= self.score_unit
            v *= self.mech_mults.get(c, 1.0)
            if pen and self._pen_dr > 0.0 and c in RESILIENCE_CAPS:
                v *= (1.0 - self._pen_dr * (1.0 - pen)) / (1.0 - self._pen_dr)
            if delivery is not None and c in self._geo_caps:
                v *= self._geo_mult(c, delivery.get(c))
            out[c] = v
        return out

    def _loadout_eff(self, weapon):
        """(always_eff, [[bundle_eff, ...], ...]) for a weapon; empty loadout
        (no game data) falls back to the flat capability union."""
        lo = self.weapons[weapon].get("loadout")
        dl = self.weapons[weapon].get("cap_delivery") or {}
        pen = self.weapons[weapon].get("resil_pen") or 0.0
        if not lo or not lo.get("slots") and not lo.get("always"):
            return self._eff(self.caps_of(weapon), dl, pen), []
        return (self._eff(lo.get("always", {}), dl, pen),
                [[self._eff(b, dl, pen) for b in slot]
                 for slot in lo.get("slots", [])])

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

    def _combo_pre(self, weapon):
        """Precomputed hot-path views of _combo_extras (cached per
        set_content): per combo, the (cap, gain, cap-table row) items of
        its in-template nonzero gains, and the sorted active-synergy pair
        indices the combo can touch. Skipped caps/pairs contribute an
        exact 0.0 in the originals, so reading these views is
        value-identical to iterating the full dicts."""
        pre = self._pre_cache.get(weapon)
        if pre is None:
            pre = []
            for extra in self._combo_extras(weapon):
                items = [(cap, gain, self._cap_tab[cap])
                         for cap, gain in extra.items()
                         if gain and cap in self._cap_tab]
                ps = set()
                for cap, gain in extra.items():
                    if gain:
                        ps.update(self._syn_by_cap.get(cap) or ())
                pre.append((items, sorted(ps)))
            self._pre_cache[weapon] = pre
        return pre

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

    # ------------------------------------------------------- gear (full build)
    # A member is no longer just weapon + weapon spells (2026-08-20): the
    # full build is weapon + helmet/armor/shoes (one chosen ability each) +
    # cape + offhand + potion + food. person contribution = combined
    # effective capabilities of the whole build. Gear items come from the
    # dataset's `gear` section (sheets/gear/), carry cap_delivery, and go
    # through the SAME _eff physics (a Force Field's 6m AoE shove scales
    # geometrically like any weapon AoE).
    def gear_key(self, key):
        """The CURATED key for a worn item, ignoring tier.

        Consumables (and some armor lines) are curated at ONE representative
        tier while comps record whatever tier they actually ran: the sheets
        carry `T7_POTION_REVIVE` (Major Gigantify), every blap member is
        recorded on `T5_POTION_REVIVE` (plain Gigantify), and an exact-key
        lookup scored 20 real potions as nothing. Tier is not part of an
        item's identity in this model — a 1..7 sheet score is far coarser
        than the tier ladder — so a recorded key falls back to its
        tier-stripped form. Exact keys always win, and an ambiguous form
        (two curated items sharing it) resolves to NOTHING rather than
        guessing. Owner ruling 2026-08-28."""
        if key in self.gear:
            return key
        return self._gear_alias.get(_key_form(key), key)

    def gear_extras(self, key):
        """Every ability-choice loadout of one gear item as effective-caps
        dicts (cached per set_content). Statless items have one entry."""
        key = self.gear_key(key)
        extras = self._gear_cache.get(key)
        if extras is None:
            g = self.gear.get(key)
            if g is None:
                extras = [{}]
            else:
                dl = g.get("cap_delivery") or {}
                lo = g.get("loadout") or {}
                always = self._eff(lo.get("always", {}), dl)
                slots = [[self._eff(b, dl) for b in slot]
                         for slot in (lo.get("slots") or []) if slot]
                extras = []
                for combo in (itertools.product(*slots) if slots else [()]):
                    extra = dict(always)
                    for b in combo:
                        for cap, v in b.items():
                            extra[cap] = extra.get(cap, 0.0) + v
                    extras.append(extra)
            self._gear_cache[key] = extras
        return extras

    def default_gear_choice(self, key):
        """The static ability pick under the current template weights —
        same argmax rule as default_combo."""
        best_i, best_key = 0, None
        for i, extra in enumerate(self.gear_extras(key)):
            val = units = 0.0
            for c, v in extra.items():
                val += self._weights.get(c, 0.0) * v
                units += v
            if best_key is None or (val, units) > best_key:
                best_i, best_key = i, (val, units)
        return best_i

    def gear_extra(self, key, choice=None):
        """One gear item's effective contribution with the chosen ability."""
        extras = self.gear_extras(key)
        if choice is None or choice < 0 or choice >= len(extras):
            choice = self.default_gear_choice(key)
        return extras[choice]

    def build_extra(self, weapon, combo=None, gear=None, role=None,
                    waive_costs=None):
        """A FULL-BUILD member's effective caps: weapon loadout + every gear
        item's ABILITY contribution + the build's STAT channel. `gear` is a
        list of gear keys or (key, choice) pairs.

        Stat channel (mechanics.yaml build_stats — the expert's model:
        item stats MODIFY the person): absolute defense (armor+MR, CCR)
        adds tankiness units; % damage/heal stats MULTIPLY the member's
        damage/heal capability supply. A +50% damage chest is worth 50%
        of whatever damage the build actually has — nearly nothing on a
        control tank, which is exactly the coherence the model wants.
        CC-duration % (increment 2, owner 2026-08-25) multiplies the
        wearer's own duration-bearing CC the same way — the Leering-Cane
        pairing as physics. `role` (a seat id) additionally applies each
        piece's DOCTRINE PASSIVE pick (kit_doctrine, dumps-resolved) —
        generation/display only; comp scoring never passes a role."""
        out = dict(self.member_extra(weapon, combo))
        armor_pts = ccr_pts = dmg_pct = heal_pct = 0.0
        ccdur_pct = ccr_mult = 0.0
        seat_class = (self.roles.get(role) or {}).get("class") if role else None
        for item in (gear or []):
            key, choice = item if isinstance(item, (list, tuple)) else (item, None)
            key = self.gear_key(key)
            for cap, v in self.gear_extra(key, choice).items():
                out[cap] = out.get(cap, 0.0) + v
            st = (self.gear.get(key) or {}).get("stats") or {}
            armor_pts += st.get("physicalarmor", 0.0) + st.get("magicresistance", 0.0)
            ccr_pts += st.get("crowdcontrolresistance", 0.0)
            dmg_pct += st.get("magicspelldamagebonus",
                              st.get("physicalspelldamagebonus", 0.0))
            heal_pct += st.get("healbonus", 0.0)
            ccdur_pct += st.get("bonusccdurationvsplayers", 0.0)
            if seat_class:
                p = ((self.gear.get(key) or {}).get("doctrine_passives")
                     or {}).get(seat_class)
                if p:
                    stat, v = p.get("stat"), p.get("value") or 0.0
                    if stat == "damage_heal_pct":
                        dmg_pct += v
                        heal_pct += v
                    elif stat == "cc_duration_pct":
                        ccdur_pct += v
                    elif stat == "ccr_pct":
                        ccr_mult += v
        bs = self.mechanics.get("build_stats") or {}
        tank = (armor_pts * bs.get("tankiness_per_armor_point", 0.0)
                + ccr_pts * (1.0 + ccr_mult)
                * bs.get("tankiness_per_ccr_point", 0.0))
        if tank > 0.0:
            out["tankiness"] = out.get("tankiness", 0.0) + tank
        if dmg_pct > 0.0:
            for cap in bs.get("damage_mult_caps") or []:
                if cap in out:
                    out[cap] *= 1.0 + dmg_pct
        if heal_pct > 0.0:
            for cap in bs.get("heal_mult_caps") or []:
                if cap in out:
                    out[cap] *= 1.0 + heal_pct
        if ccdur_pct > 0.0:
            for cap in bs.get("cc_mult_caps") or []:
                if cap in out:
                    out[cap] *= 1.0 + ccdur_pct
        # SELF-COSTS (2026-08-28): what the item costs its OWN wearer, in the
        # same 1-7 sheet points as a capability score. Demon Armor's aura
        # buys the group 0.43 damage resistances by spending 0.37 of the
        # wearer's; the model recorded only the upside, which is how a
        # backwards `tankiness` claim survived every review. Applied HERE —
        # on the wearer's own vector — never as a subtraction from the team
        # pool, so it composes correctly with per-member accounting.
        # Charged last so a cost cannot be re-multiplied by the stat
        # channels above, and floored at zero: an item may cancel its own
        # contribution, never invert someone else's.
        # `waive_costs` holds gear keys whose self-cost the PARTY has offset
        # (see effective_supply / _self_cost_waivers) — Demon Armor wearers
        # stand in each other's auras, so with 2+ copies nobody pays.
        for item in (gear or []):
            key = self.gear_key(item[0] if isinstance(item, (list, tuple))
                                else item)
            if waive_costs and key in waive_costs:
                continue
            for cap, pts in ((self.gear.get(key) or {}).get("self_costs")
                             or {}).items():
                if cap in out:
                    out[cap] = max(0.0, out[cap] - pts / self.score_unit)
        return out

    def _self_cost_waivers(self, gears):
        """Gear keys whose self-cost this party has offset. The ONLY
        super-additive duplicate rule in the model, and deliberately narrow
        (owner 2026-08-28: "duplicate is worth more only in special cases
        like demon armor"): an item qualifies solely when a VERIFIED
        interaction record on its cost's evidence spell declares
        `self_cost_offset_min_copies: N` and the party fields N or more of
        that item. It can only CANCEL A COST — never add supply — so a
        duplicate still cannot out-earn two independent first copies."""
        if not self._cost_offsets or not gears:
            return frozenset()
        counts = {}
        for g in gears:
            for item in (g or []):
                key = item[0] if isinstance(item, (list, tuple)) else item
                if key in self._cost_offsets:
                    counts[key] = counts.get(key, 0) + 1
        return frozenset(k for k, n in counts.items()
                         if n >= self._cost_offsets[k])

    def kit_variants(self, weapon):
        """Doctrine kit variants for GENERATION (dressed forge 2026-08-27):
        v0 = the seat's doctrine kit exactly as kit_options ranks it
        context-free (doctrine-tier-first; a slot whose ranked top is
        off-tier stays UNSET — the forge never guesses off-doctrine
        gear); v1/v2 = v0 with the first/second DIVERGENT single-slot
        swap (a tier piece whose top weighted capability differs from
        v0's piece in that slot). [("v0", None)] for weapons with no
        doctrine gear at all — dressed == naked. Deterministic (slot
        order, then tier order); cached per set_content. NO doctrine
        passives anywhere in this path (role stays out of build_extra —
        generation must optimize the exact score the page displays)."""
        if not self.dress_candidates:      # V3-W validation switch
            return [("v0", None)]
        out = self._variant_cache.get(weapon)
        if out is not None:
            return out

        def top_cap(k):
            extra = self.gear_extra(k)
            best = None
            for cap in sorted(extra):
                v = self._weights.get(cap, 0.0) * extra[cap]
                if best is None or v > best[1]:
                    best = (cap, v)
            return best[0] if best else None

        ko = self.kit_options(weapon)
        v0, divergent = {}, []
        for slot in ("head", "armor", "shoes", "cape", "offhand",
                     "potion", "food"):
            opts = [o for o in (ko["options"].get(slot) or [])
                    if o.get("doctrine")]
            if not opts:
                continue
            v0[slot] = opts[0]["gear"]
            t0 = top_cap(opts[0]["gear"])
            for o in opts[1:]:
                if top_cap(o["gear"]) != t0:
                    divergent.append((slot, o["gear"]))
                    break   # one divergent alternative per slot
        if not v0:
            out = [("v0", None)]
        else:
            slots = ("head", "armor", "shoes", "cape", "offhand",
                     "potion", "food")
            def gl(d):
                return [d[s] for s in slots if s in d]
            # variant cap 2 (perf ruling, plan §6: dressed forge measured
            # 2.8x baseline at 3 variants — v0 + the FIRST divergent swap
            # keeps the search's kit dimension at ~2x cost; widen only
            # with a fresh measurement)
            out = [("v0", gl(v0))]
            for n, (slot, piece) in enumerate(divergent[:1]):
                alt = dict(v0)
                alt[slot] = piece
                out.append((f"v{n + 1}", gl(alt)))
        self._variant_cache[weapon] = out
        return out

    def _dressed_extras(self, weapon):
        """Per variant, the member's effective caps per combo index — the
        beam's dressed vectors, precomputed so evaluation never calls
        build_extra inline. The naked variant reuses the combo-extras
        objects THEMSELVES (identity keeps the _combo_pre fast path and
        its exactness proofs intact)."""
        out = self._dressed_cache.get(weapon)
        if out is None:
            extras = self._combo_extras(weapon)
            out = {}
            for vkey, gl in self.kit_variants(weapon):
                out[vkey] = (extras if gl is None else
                             [self.build_extra(weapon, i, gl)
                              for i in range(len(extras))])
            self._dressed_cache[weapon] = out
        return out

    def primary_seat(self, weapon):
        """The weapon's default SEAT role: the first uniform-carrying role
        on its menu (book order = evidence-preference order). Function
        roles (no uniform) never seat; weapons off every menu return
        None and keep the pre-doctrine kit behavior."""
        for rid in self.weapons[weapon].get("role_menu") or []:
            if ((self.roles.get(rid) or {}).get("uniform")
                    or {}).get("chest"):
                return rid
        return None

    def kit_options(self, weapon, combo=None, party=None, top_n=3,
                    role="auto"):
        """IDEAL KIT per weapon, per content/style, per comp (2026-08-20;
        DOCTRINE-LED since increment 2, owner 2026-08-25 "yes its the
        whole build"): ranked gear options for every slot, for the
        player of `weapon`.

        No party -> context-free: each item valued by its weighted
        capability delta to this member's build under the CURRENT template
        weights (the same rule default_combo uses). With `party` (the REST
        of the comp, without this member) -> comp-aware: each item valued
        by the exact fitness delta of this member joining with that item,
        so the kit answers what THIS comp still needs.

        THE ROLE GATE (`role`): "auto" resolves the weapon's primary
        seat, an explicit seat id uses that seat, None is the explicit
        DIAGNOSTIC escape (audits/tests comparing against the ungated
        catalog) — never the default channel. With a seat: the CHEST
        pool hard-gates to the uniform classes (a stopper tank can
        never be handed a dps jacket), and EVERY slot serves ONLY its
        DOCTRINE tier (this weapon's own observed items first, then the
        seat's — items observed in reference builds, cited in
        roles_report kit_doctrine). Each option carries `doctrine`,
        `carries` (typed gear effects) and `passive` (the seat's
        doctrine passive pick for that piece).

        FAIL-CLOSED GENERATION (owner ruling 2026-09-01, "fix the
        underlying issue which allows these items and builds and kits
        to slide into the team comp"): the suggestion channel only
        speaks evidence. No seat -> empty kit and options (the result
        carries `seat: None` so the UI can say why); a seated slot
        with no doctrine tier stays UNSET instead of falling back to
        the marginal-ranked catalog — that fallback is how a full
        comp's one uncovered capability (usually silence) handed the
        same off-role helm to every seatless member. Suggestion-layer
        only — manual builds score anything, role_advisory flags
        mismatches.

        THE OBSERVED-BUILD OVERLAY (owner ruling 2026-09-01, "i want
        gear that each seat is wearing to actually be based on what
        real people wear. the engine keeps making up some random
        builds"): per-slot ranking assembles a Frankenstein no player
        ever fielded, so the KIT pick now follows the observed BUILD
        ARCHETYPE — the conditional-modal combination mined from real
        killboard builds (this weapon's own archetype first, the
        seat's as fallback; `kit_weapon_build`/`kit_build` in the role
        book). The archetype item moves to the FRONT of its slot's
        options (annotated `observed_build: [n, of]`); everything else
        keeps its tier/marginal order for browsing. A gate that
        excludes the archetype item (uniform, brawl cloth) simply
        leaves that slot to the normal ranking.

        Returns {"kit": {slot: choice}, "options": {slot: [ranked choices]}}
        where a choice is {gear, display_name, value, why: [(cap, delta)],
        doctrine, carries, passive}. Greedy per slot (v1): cross-slot stat
        stacking is additive in the model, so per-slot ranking against the
        bare member is faithful."""
        seat = self.primary_seat(weapon) if role == "auto" else role
        if role is not None and seat is None:
            # fail closed: no seat, no suggestion (ruling 2026-09-01)
            return {"kit": {}, "options": {}, "seat": None}
        seat_rec = self.roles.get(seat) or {}
        uniform = (seat_rec.get("uniform") or {}).get("chest") or []
        doctrine = seat_rec.get("kit") or {}
        # Per-weapon doctrine tier (owner design 2026-08-26): THIS
        # weapon's own observed items (effect carriers excluded at the
        # build — those are comp-level allocations) outrank the seat
        # aggregate; `doctrine` becomes "weapon" / "seat" / False and
        # weapon-tier options carry doctrine_n = [count, slot total].
        wdoc = (seat_rec.get("kit_weapon") or {}).get(weapon) or {}
        seat_class = seat_rec.get("class")
        # observed-build archetype (2026-09-01): weapon's own first,
        # seat fallback per slot
        arch = {}
        if role is not None:
            wb = (seat_rec.get("kit_weapon_build") or {}).get(weapon) or {}
            sb = seat_rec.get("kit_build") or {}
            for slot in set(wb) | set(sb):
                arch[slot] = wb.get(slot) or sb.get(slot)
        by_slot = {}
        for k, g in self.gear.items():
            by_slot.setdefault(g.get("slot") or "other", []).append(k)
        if uniform:
            gated = [k for k in by_slot.get("armor", [])
                     if (self.gear[k].get("gear_class") or "") in uniform]
            if gated:
                by_slot["armor"] = gated
        # Style-fit gear gate (identity Phase C, owner ruling 2026-08-23):
        # "a siegebow or a great axe, or longbow etc playing in brawl comp
        # don't work if they are on cloth armor. The brawl comp requires by
        # default that most people will be closely involved in the fight" —
        # under a DECLARED brawl, cloth armor never gets SUGGESTED (manual
        # picks still score; healers keep cloth — their doctrine armor).
        # PROVISIONAL owner-taste rule, overridable per weapon later.
        if (self.style in ("brawl", "brawl_clap")
                and self.role_of(weapon) != "healer"):
            unclothed = [k for k in by_slot.get("armor", [])
                         if "_CLOTH_" not in k]
            if unclothed:
                by_slot["armor"] = unclothed
        bare = self.member_extra(weapon, combo)
        if party is not None:
            joined = list(party) + [weapon]
            base_gears = [None] * len(party)
            f_bare = self.fitness(joined, None, base_gears + [None])
        options = {}
        for slot in sorted(by_slot):
            doc_pool = set(doctrine.get(slot) or [])
            wslot = {p[0]: p[1] for p in (wdoc.get(slot) or [])}
            wtotal = sum(wslot.values())
            pool_keys = sorted(by_slot[slot])
            if role is not None:
                # fail-closed generation (ruling 2026-09-01): only the
                # doctrine tiers may be SUGGESTED; a slot with no
                # observed evidence stays unset, never catalog-filled
                pool_keys = [k for k in pool_keys
                             if k in wslot or k in doc_pool]
                if not pool_keys:
                    continue
            ranked = []
            for k in pool_keys:
                built = self.build_extra(weapon, combo, [k], role=seat)
                deltas = sorted(
                    ((c, built.get(c, 0.0) - bare.get(c, 0.0))
                     for c in built
                     if built.get(c, 0.0) - bare.get(c, 0.0) > 1e-9),
                    key=lambda t: -self._weights.get(t[0], 0.0) * t[1])
                if party is None:
                    value = 0.0
                    for c, d in deltas:
                        value += self._weights.get(c, 0.0) * d
                else:
                    value = self.fitness(joined, None,
                                         base_gears + [[k]]) - f_bare
                passive = None
                if seat_class:
                    p = ((self.gear[k].get("doctrine_passives") or {})
                         .get(seat_class))
                    if p:
                        passive = {"id": p.get("id"), "name": p.get("name")}
                tier = ("weapon" if k in wslot
                        else "seat" if k in doc_pool else False)
                ranked.append({
                    "gear": k,
                    "display_name": self.gear[k]["display_name"],
                    "value": value,
                    "doctrine": tier,
                    "doctrine_n": ([wslot[k], wtotal]
                                   if tier == "weapon" else None),
                    "carries": list(self._item_effects.get(k) or []),
                    "passive": passive,
                    "why": [(c, round(d, 2)) for c, d in deltas[:3]]})
            # DOCTRINE-TIER-FIRST in both modes (owner ruling 2026-08-27,
            # evidence-first: "search more comps to see what tanks are
            # actually wearing"). The observed tier (this weapon's own
            # builds, then the seat's) bounds the suggestion; within a
            # tier, context-free ranks by observed count then weighted
            # value, comp-aware by the EXACT marginal — the comp's needs
            # pick WITHIN doctrine, never outside it. Marginal-first
            # across the whole catalog optimized the comp pool instead
            # of the member's job (the increment-1 root cause) the
            # moment the full catalog was curated: it handed a control
            # tank Mercenary Hood over the observed team pieces. The
            # chest is pool-gated either way — the Hellion bug can't
            # return; off-tier items stay ranked behind the tiers.
            def tier_rank(r):
                return (0 if r["doctrine"] == "weapon"
                        else 1 if r["doctrine"] == "seat" else 2)
            if party is None:
                ranked.sort(key=lambda r: (
                    tier_rank(r), -wslot.get(r["gear"], 0), -r["value"],
                    r["gear"]))
            else:
                ranked.sort(key=lambda r: (
                    tier_rank(r), -r["value"], -wslot.get(r["gear"], 0),
                    r["gear"]))
            a = arch.get(slot)
            if a:
                # the observed build leads the slot (overlay ruling)
                for i, rr in enumerate(ranked):
                    if rr["gear"] == a[0]:
                        rr["observed_build"] = [a[1], a[2]]
                        ranked.insert(0, ranked.pop(i))
                        break
            options[slot] = ranked[:top_n]
        kit = {slot: opts[0] for slot, opts in options.items() if opts}
        return {"kit": kit, "options": options, "seat": seat}

    def member_extra(self, weapon, combo=None):
        """What ONE party member actually brings: the combo's effective caps
        (mechanics applied). combo None -> the static default."""
        extras = self._combo_extras(weapon)
        if combo is None or combo < 0 or combo >= len(extras):
            combo = self.default_combo(weapon)
        return extras[combo]

    def _raw_member_caps(self, weapon, combo=None):
        """The member's RAW one-spell-per-slot capability points (loadout
        always + the chosen bundles, sheet 1-7 scale) — content- and
        style-independent. Weapons without loadout data fall back to the
        flat sheet capabilities."""
        extras = self._combo_extras(weapon)
        if combo is None or combo < 0 or combo >= len(extras):
            combo = self.default_combo(weapon)
        lo = self.weapons[weapon].get("loadout") or {}
        if not (lo.get("slots") or lo.get("always")):
            return dict(self.weapons[weapon]["capabilities"])
        caps = dict(lo.get("always") or {})
        slots = lo.get("slots") or []
        for oi, ci in self.combo_choices(weapon, combo):
            if oi < len(slots) and ci < len(slots[oi]):
                for c, v in slots[oi][ci].items():
                    caps[c] = caps.get(c, 0) + v
        return caps

    def _pred_contrib(self, weapon, combo=None):
        """frozenset of predicate names this member's SELECTED combo
        satisfies, from RAW loadout caps (always + chosen bundles — the
        units the predicate minima were calibrated on). Weapons without
        loadout data fall back to the flat sheet capabilities. Cached per
        (weapon, resolved combo); raw caps are content-independent."""
        extras = self._combo_extras(weapon)
        if combo is None or combo < 0 or combo >= len(extras):
            combo = self.default_combo(weapon)
        key = (weapon, combo)
        hit = self._pred_cache.get(key)
        if hit is not None:
            return hit
        caps = self._raw_member_caps(weapon, combo)
        out = set(
            pn for pn, mins in self.pred_defs.items()
            if all(caps.get(c, 0) >= v for c, v in mins.items()))
        # flag predicate: a full healer qualifies with EVERY combo (the E,
        # which carries the heal, is fixed per weapon)
        if self.weapons[weapon].get("full_healer"):
            out.add(self.PRIMARY_HEAL)
        out = frozenset(out)
        self._pred_cache[key] = out
        return out

    def _pred_possible(self, weapon):
        """Predicates SOME combo of this weapon can satisfy — the optimistic
        bound the beam prune uses before a combo is chosen."""
        hit = self._pred_possible_cache.get(weapon)
        if hit is not None:
            return hit
        out = set()
        for i in range(len(self._combo_extras(weapon))):
            out |= self._pred_contrib(weapon, i)
        out = frozenset(out)
        self._pred_possible_cache[weapon] = out
        return out

    def _nonstack_contrib(self, weapon, combo=None):
        """{spell: {cap: effective value}} for every verified non-stacking
        interaction spell this member's combo equips — the contributions
        effective_supply must count once across the party. Empty when no
        interaction data applies (the common case: zero overhead)."""
        if not self.nonstack:
            return {}
        extras = self._combo_extras(weapon)
        if combo is None or combo < 0 or combo >= len(extras):
            combo = self.default_combo(weapon)
        hit = self._ns_cache.get((weapon, combo))
        if hit is not None:
            return hit
        lo = self.weapons[weapon].get("loadout") or {}
        spells = lo.get("slot_spells") or []
        _always, slots_eff = self._loadout_eff(weapon)
        out = {}
        for oi, ci in self.combo_choices(weapon, combo):
            if oi >= len(spells) or ci >= len(spells[oi]):
                continue
            sid = spells[oi][ci]
            caps = self.nonstack.get(sid)
            if not caps or oi >= len(slots_eff) or ci >= len(slots_eff[oi]):
                continue
            bundle = slots_eff[oi][ci]
            contrib = out.setdefault(sid, {})
            for cap in caps:
                v = bundle.get(cap, 0.0)
                if v:
                    contrib[cap] = contrib.get(cap, 0.0) + v
            if not contrib:
                del out[sid]
        self._ns_cache[(weapon, combo)] = out
        return out

    # ----------------------------------------------------------------- supply
    def supply(self, party):
        """Raw capability units summed over the party (sheet numbers) —
        display/reference only; scoring reads effective_supply."""
        s = {}
        for w in party:
            for cap, v in self.caps_of(w).items():
                s[cap] = s.get(cap, 0) + v
        return s

    def effective_supply(self, party, combos=None, gears=None):
        """Supply after style-delivery physics AND the one-spell-per-slot
        loadout rule. ALL scoring — floors included — reads THIS.

        gears (optional, full-build members): per-member list of gear keys
        or (key, choice) pairs; None = weapon-only (unchanged behavior)."""
        s = {}
        waived = self._self_cost_waivers(gears) if gears else frozenset()
        for i, w in enumerate(party):
            extra = (self.build_extra(w, combos[i] if combos else None,
                                      gears[i] if gears else None,
                                      waive_costs=waived)
                     if gears and gears[i] else
                     self.member_extra(w, combos[i] if combos else None))
            for cap, v in extra.items():
                s[cap] = s.get(cap, 0.0) + v
        if self.nonstack:
            self._apply_nonstack(s, party, combos)
        return s

    def _apply_nonstack(self, s, party, combos):
        """Count-once rule for verified non-stacking interaction spells: when
        two or more members equip the same such spell, each listed capability
        keeps only the LARGEST single-member contribution. Deterministic
        order (sorted spell ids, stored cap order, party order) — the JS
        mirror must accumulate identically."""
        groups = {}
        for i, w in enumerate(party):
            for sid, contrib in self._nonstack_contrib(
                    w, combos[i] if combos else None).items():
                groups.setdefault(sid, []).append(contrib)
        for sid in sorted(groups):
            lst = groups[sid]
            if len(lst) < 2:
                continue
            for cap in self.nonstack[sid]:
                total = 0.0
                mx = 0.0
                for contrib in lst:
                    v = contrib.get(cap, 0.0)
                    total += v
                    if v > mx:
                        mx = v
                excess = total - mx
                if excess > 0.0:
                    s[cap] = s.get(cap, 0.0) - excess

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

    def _cover_terms(self, cap, have, gain, target, have_floor=None,
                     gain_floor=None):
        """(coverage delta, floor-lift delta) for adding `gain` units. Kept
        as two terms so callers accumulate in their original order — float
        addition is not associative and parity pins the exact sums. Coverage
        includes the headroom bonus so marginals stay exact.
        Option C (owner ruling 2026-08-27): STRUCTURAL hard floors read the
        weapon+loadout basis — dressed callers pass `have_floor`/`gain_floor`
        (the naked supply and the candidate's weapon-only gain) so worn gear
        never buys floor relief; defaults keep the naked path bit-identical."""
        soft = self.soft_cap(cap)
        cov = self.weight(cap) * (min(1.0, (have + gain) / target) ** self.gamma
                                  - min(1.0, have / target) ** self.gamma)
        cov += (self._headroom_bonus(cap, have + gain, target, soft)
                - self._headroom_bonus(cap, have, target, soft))
        hf = have if have_floor is None else have_floor
        gf = gain if gain_floor is None else gain_floor
        return cov, self._floor_penalty(cap, hf) - self._floor_penalty(cap, hf + gf)

    # ---------------------------------------------------------------- fitness
    def fitness(self, party, combos=None, gears=None):
        s = self.effective_supply(party, combos, gears)
        # Option C (owner ruling 2026-08-27): STRUCTURAL hard floors read
        # the weapon+loadout supply — worn gear improves coverage/headroom/
        # overstack but can never satisfy a structural floor (the
        # 2026-08-12 pseudo-tankiness ruling extended to the gear stat
        # channel). Naked parties keep the single-supply fast path.
        sf = (self.effective_supply(party, combos)
              if gears and any(gears) else s)
        total = 0.0
        for cap in self.reqs:
            have, target, soft = s.get(cap, 0.0), self.target(cap), self.soft_cap(cap)
            # style multiplies the VALUE of coverage; over-stack economics and
            # floors stay on the base weight (T10)
            total += self.weight(cap) * min(1.0, have / target) ** self.gamma
            total += self._headroom_bonus(cap, have, target, soft)
            total -= self._overstack(cap, have, target, soft)
            total -= self._floor_penalty(cap, have if sf is s
                                         else sf.get(cap, 0.0))
        return total

    def max_fitness(self, party=None, combos=None, gears=None):
        """Supremum of fitness(): full coverage of every capability plus the
        headroom band maxed at each soft cap (review 2026-08-18 — without
        the headroom factor a well-forged comp displayed over 100%).

        Given a party, OPTIONAL capabilities the party fields none of drop
        out of the supremum (owner ruling 2026-08-28): a comp is not marked
        down for skipping a tool that lives on one weapon in the game. Called
        with no party this returns the every-capability supremum, so legacy
        callers are unchanged. fitness() is identical either way — see the
        set_content note; this is a denominator-only rule."""
        caps = self.reqs
        if party is not None and self.optional:
            s = self.effective_supply(party, combos, gears)
            caps = [c for c in self.reqs
                    if c not in self.optional or s.get(c, 0.0) > 0.0]
        return sum(self.weight(cap) for cap in caps) * (1.0 + self.headroom)

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
    def comp_score(self, party, combos=None, gears=None):
        """THE party-level objective. Every suggestion path reports exact
        marginals of this same blend — see _eval_pick. `gears` (optional,
        full-build members) adds each member's gear contributions to the
        fitness supply. Synergy/meta/dup stay WEAPON-KEYED by ruling, not
        by omission: synergy is weapon-interaction synergy (scoring.yaml
        rule 3, owner 2026-08-27 — gear participation moved real comps
        negatively under the current J rule), and meta prior / duplicate
        pricing are properties of the weapon slot."""
        meta = 0.0
        viab = 0.0
        for w in party:
            meta += self.meta_of(w)
            viab += self.viability_of(w)
        return (self.alpha * self.fitness(party, combos, gears)
                + self.beta * self.synergy(party, combos)
                + self.delta * meta
                + self.viability_w * viab
                - self.rho * self.redundancy(party))

    # -------------------------------------------------- candidate evaluation
    def party_state(self, party, combos=None, gears=None):
        """Everything a candidate marginal needs: effective supply, per-pair
        synergy state, exact-weapon counts, and the per-spell max non-stacking
        contributions (so _eval_pick can price a duplicate of a verified
        non-stacking spell exactly). Build once per sweep.

        `gears` (dressed forge, 2026-08-27): comp_score's own seams split
        the supplies — fitness reads gear-inclusive supply, synergy stays
        weapon-keyed (synergy() computes its own gears-free supply). So
        `s` is the FIT supply (dressed when gears are given) and `s_syn`
        the weapon-only supply every synergy term reads. gears=None keeps
        both the same object — bit-identical to the pre-gears state."""
        s_syn, J = self._syn_state(party, combos)
        s = (self.effective_supply(party, combos, gears)
             if gears and any(gears) else s_syn)
        pair_vals = []
        for p in range(len(self._active_syn)):
            a, b, _bonus = self._active_syn[p]
            pair_vals.append(self._pair_value(p, s_syn.get(a, 0.0),
                                              s_syn.get(b, 0.0), J[p]))
        counts = {}
        for w in party:
            counts[w] = counts.get(w, 0) + 1
        ns_max = {}
        if self.nonstack:
            for i, w in enumerate(party):
                for sid, contrib in self._nonstack_contrib(
                        w, combos[i] if combos else None).items():
                    cur = ns_max.setdefault(sid, {})
                    for cap, v in contrib.items():
                        if v > cur.get(cap, 0.0):
                            cur[cap] = v
        return {"s": s, "s_syn": s_syn, "J": J, "pair_vals": pair_vals,
                "counts": counts, "ns_max": ns_max}

    def _marg_fit_from(self, s, extra, s_floor=None, extra_floor=None):
        """Marginal fitness of adding effective caps `extra` to effective
        supply `s` — same coverage/floor/over-stack terms fitness() sums.
        Option C: dressed callers pass `s_floor` (the weapon+loadout party
        supply) and `extra_floor` (the candidate's weapon-only adjusted
        caps) so floor terms never see gear; the dressed vector holds every
        weapon cap, so one loop covers both bases. Defaults = legacy naked
        path, bit-identical."""
        total = 0.0
        if s_floor is None:
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
        ef = extra_floor if extra_floor is not None else {}
        for cap, gain in extra.items():
            if cap not in self.reqs or not gain:
                continue
            have, target, soft = s.get(cap, 0.0), self.target(cap), self.soft_cap(cap)
            cov, floor_d = self._cover_terms(cap, have, gain, target,
                                             s_floor.get(cap, 0.0),
                                             ef.get(cap, 0.0))
            total += cov
            total += floor_d
            total -= (self._overstack(cap, have + gain, target, soft)
                      - self._overstack(cap, have, target, soft))
        return total

    def _marg_syn_from(self, state, extra, extra_j=None):
        """Marginal synergy of adding effective caps `extra` — exact against
        the same per-pair rule synergy() applies. `extra_j` (default: extra)
        is the member's UNADJUSTED caps for the largest-single-member joint
        term J — synergy() computes J from member_extra, so a non-stacking
        supply adjustment must not leak into it."""
        if extra_j is None:
            extra_j = extra
        total = 0.0
        s, J, pv = state["s_syn"], state["J"], state["pair_vals"]
        for p in range(len(self._active_syn)):
            a, b, _bonus = self._active_syn[p]
            j = min(extra_j.get(a, 0.0), extra_j.get(b, 0.0))
            j2 = J[p] if J[p] > j else j
            total += self._pair_value(p, s.get(a, 0.0) + extra.get(a, 0.0),
                                      s.get(b, 0.0) + extra.get(b, 0.0), j2) - pv[p]
        return total

    def _nonstack_adjust(self, state, weapon, combo, extra):
        """The candidate's effective caps with the count-once rule applied
        against the CURRENT party (state.ns_max): for each verified
        non-stacking spell the combo shares with a member, the listed caps
        gain only max(0, candidate - party_max) — exactly what
        effective_supply(party + candidate) would show. Returns `extra`
        itself when nothing applies (fast path)."""
        ns_max = state.get("ns_max")
        if not self.nonstack or not ns_max:
            return extra
        adj = None
        for sid, contrib in self._nonstack_contrib(weapon, combo).items():
            pmax = ns_max.get(sid)
            if not pmax:
                continue
            if adj is None:
                adj = dict(extra)
            for cap in self.nonstack[sid]:
                v = contrib.get(cap, 0.0)
                if not v:
                    continue
                gain = v - pmax.get(cap, 0.0)
                adj[cap] = adj.get(cap, 0.0) - v + (gain if gain > 0.0 else 0.0)
        return adj if adj is not None else extra

    def _floor_gain(self, weapon):
        """Per combo, the WEAPON+LOADOUT gains on hard-floored caps — the
        Option C floor basis for dressed marginals (cached per
        set_content; dressing-independent, so set_dressing need not clear
        it)."""
        out = self._floor_gain_cache.get(weapon)
        if out is None:
            out = []
            for extra in self._combo_extras(weapon):
                d = {}
                for cap, v in extra.items():
                    row = self._cap_tab.get(cap)
                    if v and row is not None and row[4] is not None:
                        d[cap] = v
                out.append(d)
            self._floor_gain_cache[weapon] = out
        return out

    def _marg_fit_pre(self, s, items, s_floor=None, floor_gains=None):
        """_marg_fit_from over a _combo_pre item list: the same terms with
        _cover_terms/_floor_penalty/_overstack inlined against the per-cap
        table — identical operands in identical order, no per-call
        target/weight/floor lookups (forge profile 2026-08-26).
        Option C: with `s_floor`, floor terms read that supply instead of
        `s`; `floor_gains` (a {cap: weapon-only gain} dict) overrides the
        row's gain for a DRESSED candidate — None means the row's own gain
        already IS the weapon-only gain (naked candidate on a dressed
        party)."""
        gamma, headroom, omax = self.gamma, self.headroom, self.overstack_max
        total = 0.0
        for cap, gain, (target, soft, w, w_base, floor) in items:
            have = s.get(cap, 0.0)
            hg = have + gain
            cov = w * (min(1.0, hg / target) ** gamma
                       - min(1.0, have / target) ** gamma)
            hb1 = hb0 = 0.0
            if headroom > 0.0 and soft > target:
                span = soft - target
                if hg > target:
                    e = hg - target
                    if e > span:
                        e = span
                    hb1 = headroom * w * e / span
                if have > target:
                    e = have - target
                    if e > span:
                        e = span
                    hb0 = headroom * w * e / span
            cov += hb1 - hb0
            total += cov
            if floor is not None:
                fu, pm = floor
                if s_floor is None:
                    hf, hgf = have, hg
                else:
                    hf = s_floor.get(cap, 0.0)
                    hgf = hf + (gain if floor_gains is None
                                else floor_gains.get(cap, 0.0))
                p0 = pm * w_base * (fu - hf) / fu if hf < fu else 0.0
                p1 = pm * w_base * (fu - hgf) / fu if hgf < fu else 0.0
                total += p0 - p1
            if hg > soft or have > soft:
                scale = soft if soft > 0 else target
                o1 = o0 = 0.0
                if hg > soft:
                    x = (hg - soft) / scale
                    o1 = omax * w_base * x / (1.0 + x)
                if have > soft:
                    x = (have - soft) / scale
                    o0 = omax * w_base * x / (1.0 + x)
                total -= o1 - o0
        return total

    def _marg_syn_pre(self, state, extra, pairs):
        """_marg_syn_from with extra_j == extra, walking only the pairs the
        combo touches (_combo_pre): an untouched pair's term is exactly
        pair_vals[p] - pair_vals[p] == 0.0, so the sum is identical."""
        total = 0.0
        s, J, pv = state["s_syn"], state["J"], state["pair_vals"]
        tab = self._syn_tab
        for p in pairs:
            a, b, bonus, ta, tb = tab[p]
            ea = extra.get(a, 0.0)
            eb = extra.get(b, 0.0)
            j = min(ea, eb)
            j2 = J[p] if J[p] > j else j
            va = min(s.get(a, 0.0) + ea, ta)
            vb = min(s.get(b, 0.0) + eb, tb)
            v = (va if va < vb else vb) - j2
            total += (bonus * v if v > 0 else 0.0) - pv[p]
        return total

    def _combo_score(self, state, weapon, i, extra):
        """(value, d_fit, d_syn) of ONE combo against a party state — the
        shared inner term of _eval_pick and the forge's constraint-aware
        variant. Identical float-op order to the original inline loop; when
        no non-stacking adjustment applies (adj is extra — the common case)
        the precomputed _pre views evaluate the same numbers faster."""
        adj = self._nonstack_adjust(state, weapon, i, extra)
        # Option C: on a DRESSED party (s is not the weapon-only supply)
        # the floor terms read s_syn + the candidate's own weapon caps —
        # the candidate here IS naked, so its gains are already the floor
        # basis. Naked parties keep the legacy single-supply path.
        split = state["s"] is not state["s_syn"]
        if adj is extra:
            items, pairs = self._combo_pre(weapon)[i]
            d_fit = (self._marg_fit_pre(state["s"], items, state["s_syn"])
                     if split else self._marg_fit_pre(state["s"], items))
            d_syn = self._marg_syn_pre(state, extra, pairs)
        else:
            d_fit = (self._marg_fit_from(state["s"], adj, state["s_syn"], adj)
                     if split else self._marg_fit_from(state["s"], adj))
            d_syn = self._marg_syn_from(state, adj, extra)
        return self.alpha * d_fit + self.beta * d_syn, d_fit, d_syn

    def _pick_tail(self, state, weapon, best):
        """The combo-independent terms of a candidate score — shared by
        _eval_pick and _forge_eval_pick so the formula can never drift."""
        meta = self.meta_of(weapon)
        dup = state["counts"].get(weapon, 0) + 1 - self._dup_free(weapon)
        score = (best[0] + self.delta * meta
                 + self.viability_w * self.viability_of(weapon)
                 - (self.rho * dup if dup > 0 else 0.0))
        return score, best[1], best[2], meta, best[3]

    def _dressed_pre(self, weapon):
        """_combo_pre's fit-items view over the DRESSED vectors (cached
        per set_content): per variant per combo, the (cap, gain,
        cap-table row) items of the dressed vector's in-template nonzero
        gains. Synergy pairs are NOT duplicated here — the synergy half
        of a dressed candidate reads the weapon-only extras, so
        _combo_pre's pair lists stay the one source. The naked variant
        aliases _combo_pre's item lists."""
        pre = self._dressed_pre_cache.get(weapon)
        if pre is None:
            wpre = self._combo_pre(weapon)
            extras = self._combo_extras(weapon)
            pre = {}
            for vkey, dext in self._dressed_extras(weapon).items():
                if dext is extras:
                    pre[vkey] = [it for it, _ps in wpre]
                else:
                    pre[vkey] = [[(cap, gain, self._cap_tab[cap])
                                  for cap, gain in extra.items()
                                  if gain and cap in self._cap_tab]
                                 for extra in dext]
            self._dressed_pre_cache[weapon] = pre
        return pre

    def _combo_score_dressed(self, state, weapon, i, wextra, dextra,
                             vkey=None):
        """_combo_score for a DRESSED candidate: the fit half prices the
        dressed vector, the synergy half the weapon-only vector — the
        exact decomposition of comp_score-with-gears (fitness reads
        gears, synergy does not; verified 2026-08-27). When the vectors
        are the same object this IS _combo_score. With `vkey` and no
        non-stacking adjustment, the precomputed _pre views evaluate the
        same numbers faster (F1/F22b pin the equality at 1e-9)."""
        if dextra is wextra:
            return self._combo_score(state, weapon, i, wextra)
        # Option C: a DRESSED candidate's floor terms read the weapon-only
        # basis on BOTH sides — s_syn for the party (== s when the party is
        # naked) and the candidate's weapon-only gains — so its kit can
        # never buy floor relief the party's kits are denied.
        adj = self._nonstack_adjust(state, weapon, i, dextra)
        if adj is dextra and vkey is not None:
            items = self._dressed_pre(weapon)[vkey][i]
            _wi, pairs = self._combo_pre(weapon)[i]
            d_fit = self._marg_fit_pre(state["s"], items, state["s_syn"],
                                       self._floor_gain(weapon)[i])
            d_syn = self._marg_syn_pre(state, wextra, pairs)
        else:
            adj_w = self._nonstack_adjust(state, weapon, i, wextra)
            d_fit = self._marg_fit_from(state["s"], adj, state["s_syn"],
                                        adj_w)
            d_syn = self._marg_syn_from(state, wextra)
        return self.alpha * d_fit + self.beta * d_syn, d_fit, d_syn

    def _eval_pick(self, state, weapon):
        """THE candidate score — the exact comp_score delta of adding
        `weapon` with its best loadout AND doctrine-kit variant for this
        party (dressed forge 2026-08-27). Every suggestion path
        (recommend / swap_review / forge beam) reads this one helper so
        the formula can never drift.
        Returns (score, d_fit, d_syn, meta, combo, variant, vgears)."""
        best = None
        extras = self._combo_extras(weapon)
        dressed = self._dressed_extras(weapon)
        for vkey, vgears in self.kit_variants(weapon):
            dext = dressed[vkey]
            for i in range(len(extras)):
                val, d_fit, d_syn = self._combo_score_dressed(
                    state, weapon, i, extras[i], dext[i], vkey)
                if best is None or val > best[0]:
                    best = (val, d_fit, d_syn, i, vkey, vgears)
        if best is None:
            best = (0.0, 0.0, 0.0, None, "v0", None)
        score, d_fit, d_syn, meta, combo = self._pick_tail(
            state, weapon, best[:4])
        return score, d_fit, d_syn, meta, combo, best[4], best[5]

    def best_loadout(self, s, base_syn, weapon):
        """Legacy shim (golden T14; explain callers migrated): the candidate's
        best loadout against bare supply `s`, with no member-level synergy
        state (J=0 — exact for an empty party). Returns (d_fit, d_syn, extra)."""
        state = {"s": s, "s_syn": s, "J": [0.0] * len(self._active_syn),
                 "pair_vals": [], "counts": {}}
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

    def explain(self, party, candidate, combos=None, gears=None):
        """Per-capability delta terms for the candidate's CHOSEN loadout —
        these ARE the 'why' text, and they match what _eval_pick scored."""
        state = self.party_state(party, combos, gears)
        _sc, _df, _ds, _meta, combo, _var, _vg = self._eval_pick(state, candidate)
        extra = self.member_extra(candidate, combo)
        s = state["s"]
        terms = []
        for cap, gain in extra.items():
            if cap not in self.reqs or not gain:
                continue
            have, target = s.get(cap, 0.0), self.target(cap)
            cov, floor_d = self._cover_terms(cap, have, gain, target,
                                             state["s_syn"].get(cap, 0.0))
            d = cov + floor_d
            if d > 0.05:
                terms.append({"delta": round(d, 2), "cap": cap,
                              "before": have, "after": have + gain, "target": target})
        return sorted(terms, key=lambda t: -t["delta"])

    # ------------------------------------- negative recs / redundancy lens
    # (roadmap item 3, 2026-08-24.) A DESCRIPTIVE decomposition of the same
    # exact marginal _eval_pick scores — the "why not" counterpart of
    # explain(), which only ever reported the positive terms. A scoring-side
    # redundancy penalty was investigated and REJECTED (MECHANICS_TODO Q18):
    # concavity + supply already collapse a redundant pick's marginal; this
    # layer surfaces the collapse instead of re-modeling it. Nothing here
    # feeds a score.
    def _nr_gain_max(self):
        """Redundancy verdict threshold (mechanics.yaml negative_recs,
        PROVISIONAL, MASTERSHEET-tunable). Default matches the 0.05 term
        floor explain() has always used."""
        return (self.mechanics.get("negative_recs") or {}).get(
            "redundant_gain_max", 0.05)

    def _pick_caps(self, state, weapon, combo, vgears=None):
        """(rows, caps_gain) for the candidate's chosen combo — DRESSED in
        its chosen kit variant (dressed forge 2026-08-27) — against a
        party state. Each row carries the SIGNED per-capability terms of
        the fitness marginal — coverage, floor lift, over-stack cost — so
        rows sum to _eval_pick's d_fitness (test-pinned at 1e-9; without
        the kit the rows would no longer reconstruct a dressed pick).
        caps_gain is the GAP-CLOSING part alone: below-target coverage +
        floor lift, headroom-band depth deliberately excluded — the small
        headroom bonus is what the engine pays a saturated depth pick, and
        counting it here would make 'redundant' unreachable exactly where
        the warning matters."""
        extra = (self.build_extra(weapon, combo, vgears) if vgears
                 else self.member_extra(weapon, combo))
        adj = self._nonstack_adjust(state, weapon, combo, extra)
        # Option C floor basis: floor_lift rows read the weapon-only party
        # supply and the candidate's weapon-only adjusted gains, exactly as
        # the marginal scored them (rows must still sum to d_fitness).
        adj_w = (self._nonstack_adjust(
                     state, weapon, combo, self.member_extra(weapon, combo))
                 if vgears else adj)
        s, sf = state["s"], state["s_syn"]
        rows, caps_gain = [], 0.0
        for cap, gain in adj.items():
            if cap not in self.reqs or not gain:
                continue
            have, target, soft = s.get(cap, 0.0), self.target(cap), self.soft_cap(cap)
            cov, floor_d = self._cover_terms(cap, have, gain, target,
                                             sf.get(cap, 0.0),
                                             adj_w.get(cap, 0.0))
            over = (self._overstack(cap, have + gain, target, soft)
                    - self._overstack(cap, have, target, soft))
            head = (self._headroom_bonus(cap, have + gain, target, soft)
                    - self._headroom_bonus(cap, have, target, soft))
            caps_gain += cov + floor_d - head
            rows.append({"cap": cap, "gain": gain,
                         "before": have, "after": have + gain,
                         "target": target, "soft_cap": soft,
                         "coverage": cov, "floor_lift": floor_d,
                         "overstack_cost": over,
                         "delta": cov + floor_d - over,
                         "saturated": have >= target})
        rows.sort(key=lambda r: (-r["delta"], r["cap"]))
        return rows, caps_gain

    def _pick_verdict(self, score, caps_gain):
        """One rule, every surface: 'negative' when the exact marginal is
        not positive; 'redundant' when the pick closes no real gap (its
        value is meta prior / viability, not coverage); else 'ok'."""
        if score <= 0.0:
            return "negative"
        if caps_gain <= self._nr_gain_max():
            return "redundant"
        return "ok"

    def pick_report(self, party, candidate, combos=None, gears=None):
        """Full SIGNED decomposition of the candidate's pick score — the
        'why / why not' panel behind a recommendation or a manual add.
        Every number is a term of the exact _eval_pick marginal for the
        candidate's chosen loadout: caps rows sum to d_fitness, and
        alpha*d_fitness + beta*d_synergy + delta*meta + viability*viab
        - dup_penalty reconstructs the score (both pinned at 1e-9).
        `nonstack` names verified count-once spells the party already
        carries and the units the duplicate loses to them.
        DESCRIPTIVE ONLY — computing it never changes a score."""
        state = self.party_state(party, combos, gears)
        score, d_fit, d_syn, meta, combo, _var, vgears = \
            self._eval_pick(state, candidate)
        rows, caps_gain = self._pick_caps(state, candidate, combo, vgears)
        dup = state["counts"].get(candidate, 0) + 1 - self._dup_free(candidate)
        dup_penalty = self.rho * dup if dup > 0 else 0.0
        ns_lines = []
        ns_max = state.get("ns_max") or {}
        contrib = self._nonstack_contrib(candidate, combo)
        for sid in sorted(contrib):
            pmax = ns_max.get(sid)
            if not pmax:
                continue
            lost = {}
            for cap in self.nonstack[sid]:
                v = contrib[sid].get(cap, 0.0)
                cut = v if v < pmax.get(cap, 0.0) else pmax.get(cap, 0.0)
                if v and cut > 0.0:
                    lost[cap] = cut
            if lost:
                rec = self.interactions.get(sid) or {}
                ns_lines.append({"spell": sid,
                                 "name": rec.get("name") or sid,
                                 "lost": lost})
        return {
            "weapon": candidate,
            "display_name": self.weapons[candidate]["display_name"],
            "combo": combo, "kit": vgears or [], "score": score,
            "d_fitness": d_fit, "d_synergy": d_syn,
            "meta_prior": meta, "viability": self.viability_of(candidate),
            "dup_penalty": dup_penalty,
            "caps": rows, "caps_gain": caps_gain,
            "nonstack": ns_lines,
            "verdict": self._pick_verdict(score, caps_gain),
        }

    def recommend(self, party, top_n=4, pool=None, combos=None, gears=None):
        state = self.party_state(party, combos, gears)
        out = []
        for w in (pool or self.suggest_pool()):
            score, d_fit, d_syn, meta, combo, _var, vgears = \
                self._eval_pick(state, w)
            out.append({
                "weapon": w,
                "display_name": self.weapons[w]["display_name"],
                "status": self.weapons[w]["status"],
                "d_fitness": d_fit, "d_synergy": d_syn, "meta_prior": meta,
                "viability": self.viability_of(w),
                "combo": combo, "kit": vgears or [],
                "score": score,
            })
        out = sorted(out, key=lambda r: -r["score"])[:top_n]
        # verdict lens on the returned rows only (the sweep stays lean):
        # a suggestion that survives ranking can still be a depth pick in
        # a saturated comp — say so instead of implying it fills a gap
        for r in out:
            _rows, caps_gain = self._pick_caps(state, r["weapon"], r["combo"],
                                               r["kit"] or None)
            r["caps_gain"] = caps_gain
            r["verdict"] = self._pick_verdict(r["score"], caps_gain)
        return out

    def swap_review(self, party, top_n=3, pool=None, combos=None, gears=None):
        """Per-member swap advisor. Each member's CURRENT weapon is valued
        exactly as _eval_pick would value it as a pick into the REST of the
        party, ranked against every alternative. `off_comp` flags members the
        viability rules bar from generated comps at this content+size —
        loadable, scoreable, advised against."""
        out = []
        for i, cur in enumerate(party):
            rest = party[:i] + party[i + 1:]
            rest_combos = (combos[:i] + combos[i + 1:]) if combos else None
            rest_gears = (gears[:i] + gears[i + 1:]) if gears else None
            state = self.party_state(rest, rest_combos, rest_gears)
            cur_pick = self._eval_pick(state, cur)
            cur_score = cur_pick[0]
            # redundancy lens (roadmap item 3): the member valued exactly as
            # a pick into the rest — does it still close any gap, or are its
            # jobs already covered without it? Descriptive flag only.
            _rows, caps_gain = self._pick_caps(state, cur, cur_pick[4],
                                               cur_pick[6])
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
                "off_style": self.is_style_unfit(cur),
                "off_budget": self.is_cost_gated(cur),
                "caps_gain": caps_gain,
                "verdict": self._pick_verdict(cur_score, caps_gain),
                "redundant": self._pick_verdict(cur_score, caps_gain) != "ok",
                "options": [{"weapon": w,
                             "display_name": self.weapons[w]["display_name"],
                             "score": v, "gain": v - cur_score}
                            for v, w in better[:top_n]],
            })
        return out

    def weaknesses(self, party, top_n=3, combos=None, gears=None):
        s = self.effective_supply(party, combos, gears)
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

    # ----------------------------------------------- interaction analysis
    # ("new prompt" spec §7/§9, 2026-08-19.) Assembly over existing scoring
    # pieces — coverage reads effective_supply, gaps read the weakness logic,
    # duplicate conflicts read the interaction records. No parallel scoring
    # path exists here; everything a message claims is what the score used.
    DAMAGE_CAPS_PROFILE = ("burst_aoe", "burst_st", "sustained_dps", "execute")
    UTILITY_CAPS_PROFILE = ("purge", "cleanse", "silence", "heal_reduction",
                            "resist_shred", "clump_create", "anti_zone",
                            "damage_debuff", "buff_allies")
    DEFENSE_CAPS_PROFILE = ("tankiness", "peel", "heal_sustain", "heal_burst",
                            "disengage", "mobility")

    def duplicate_conflicts(self, party, combos=None):
        """Per-SPELL duplicate analysis: for every spell equipped by two or
        more members that has an interaction record, report what duplicating
        it actually does. Severity: 'high'/'warning' only on VERIFIED
        non-stacking records; verified full value and shared stacks are
        'info'; anything the game data does not state is 'verify' — an
        honest prompt to check, never an invented penalty (§12). Keyed by
        spell, so the same effect via two different weapons is caught and
        two different named effects on one stat are NOT."""
        by_spell = {}
        for i, w in enumerate(party):
            for _slot, sid in self.combo_spells(
                    w, combos[i] if combos else None):
                by_spell.setdefault(sid, []).append(w)
        out = []
        for sid in sorted(by_spell):
            members = by_spell[sid]
            if len(members) < 2:
                continue
            rec = self.interactions.get(sid)
            if not rec:
                continue
            name = rec.get("name") or sid
            dup = rec.get("duplicate", "unknown")
            verified = rec.get("confidence") == "verified"
            ns = [c for c in (rec.get("nonstacking_caps") or [])
                  if c in self.reqs]
            if verified and ns:
                severity = ("high" if dup in ("does_not_stack", "override",
                                              "refresh") else "warning")
                reason = (f"{name}: {', '.join(ns)} counts once for the "
                          f"party ({dup}) — a duplicate adds its other "
                          "components only")
            elif verified and dup == "full":
                severity = "info"
                reason = (f"{name}: duplicates give verified full "
                          "independent value")
            elif dup == "shared_stack":
                severity = "info"
                reason = (f"{name}: duplicates feed one shared stack on the "
                          "target — faster stacking, not wasted value")
            else:
                severity = "verify"
                reason = (f"{name}: duplicate behavior is not stated by the "
                          "game data — verify before stacking "
                          f"({rec.get('confidence')})")
            out.append({"spell": sid, "name": name, "weapons": members,
                        "severity": severity, "duplicate": dup,
                        "effect": rec.get("effect_name"),
                        "confidence": rec.get("confidence"),
                        "reason": reason})
        return out

    def analyze(self, party, combos=None):
        """Whole-composition interaction analysis: strengths (capabilities at
        or above target), missing capabilities (weighted deficit order),
        duplicate conflicts, CC-type coverage from interaction records, and
        the damage/utility/defense supply profiles. Returns plain data —
        callers render it."""
        s = self.effective_supply(party, combos)
        strengths, missing = [], []
        for cap in self.reqs:
            have, target = s.get(cap, 0.0), self.target(cap)
            soft = self.soft_cap(cap)
            # saturation band (roadmap item 3): the engine's own economics —
            # below target a unit earns coverage; target..soft earns only the
            # small headroom bonus; past soft it pays the over-stack penalty.
            band = ("gap" if have < target
                    else "headroom" if have <= soft else "overstacked")
            row = {"cap": cap, "have": have, "target": target,
                   "soft_cap": soft, "band": band}
            if have >= target:
                strengths.append(row)
            elif self.weight(cap) > 0:
                row["gap"] = target - have
                row["weighted_gap"] = self.weight(cap) * (target - have) / target
                missing.append(row)
        missing.sort(key=lambda m: -m["weighted_gap"])
        cc = set()
        for i, w in enumerate(party):
            for _slot, sid in self.combo_spells(
                    w, combos[i] if combos else None):
                rec = self.interactions.get(sid)
                if rec:
                    cc.update(rec.get("cc_types") or [])

        def profile(caps):
            return {cap: s.get(cap, 0.0) for cap in caps if s.get(cap, 0.0)}

        return {
            "strengths": strengths,
            "missing_capabilities": missing,
            "duplicate_conflicts": self.duplicate_conflicts(party, combos),
            "cc_coverage": sorted(cc),
            "damage_profile": profile(self.DAMAGE_CAPS_PROFILE),
            "utility_coverage": profile(self.UTILITY_CAPS_PROFILE),
            "defensive_coverage": profile(self.DEFENSE_CAPS_PROFILE),
        }

    # Identity thresholds (descriptive layer, F-V3-2). Calibrated 2026-08-23
    # against every style-declared comp on file — blap / Bist roam 15 /
    # push-monkey melee balls read brawl (73-90% melee damage), the
    # albioncompo ss-kite 20 and the golden kite10 fixture read kite, the
    # golden clap10 fixture reads clap (62% bomb share), and the V3 case-6
    # party the expert called "clashing" lands in the split band (43:57
    # across one carrier each). See VALIDATION.md, V3 round 1.
    IDENTITY_MELEE_CORE = 0.65     # melee damage share at/above -> brawl ball
    IDENTITY_RANGED_CORE = 0.35    # at/below -> ranged core (clap or kite)
    IDENTITY_STRONG = 0.80         # a share past this reads "strong", not "leaning"
    IDENTITY_CLAP_AOE = 0.50       # ranged core at/above this bomb share -> clap
    IDENTITY_BC_AOE = 0.45         # mid band: bomb share half of brawl_clap
    IDENTITY_BC_POSTURE = 0.45     # mid band: commit posture half of brawl_clap
    IDENTITY_CARRIER_MIN = 4       # raw damage points that make a damage carrier
    IDENTITY_MIN_MEMBERS = 3       # below this the comp is still "forming"
    IDENTITY_RANGED_ATTACK = 9.0   # attackrange at/above -> ranged delivery
    # Clap-Kite hybrid (owner 2026-08-23): a ranged core with BOTH real
    # bomb share and real reset mobility. Calibrated on the owner-labeled
    # comps: DH P1 / 20v20 (aoe ~.53, evade ~2.6/member) read hybrid;
    # pure clap10 (evade 1.8) and pure kite10 (aoe .26) do not.
    IDENTITY_HYBRID_AOE = 0.40     # bomb share at/above -> clap half present
    IDENTITY_HYBRID_EVADE = 2.0    # mobility+disengage pts/member -> kite half
    IDENTITY_STYLES = ("brawl", "clap", "kite", "brawl_clap", "clap_kite")

    def _style_fit_of(self, weapon):
        """The weapon's derived style/size identity (build_dataset
        derive_style_fit + style_overrides.yaml). Absent on pre-identity
        datasets -> None, and every consumer degrades gracefully."""
        return self.weapons[weapon].get("style_fit")

    def _fit_band(self):
        """Size band for style-fit verdicts: trio <=3, gang 4-9, group 10+
        (the same breakpoints the derivation documents)."""
        return ("trio" if self.size <= 3
                else "gang" if self.size <= 9 else "group")

    def comp_identity(self, party, combos=None):
        """What this comp is BECOMING, in the caller's own playstyle
        vocabulary (styles.yaml): brawl / clap / kite / brawl_clap, plus
        'mixed' for split identities and 'forming' while too small to say.

        v2 (owner-specified 2026-08-23): identity builds up from MEMBER
        identities. Each member's side comes from the weapon's derived
        style_fit delivery — a flex weapon (melee stat line whose E damage
        lands at range, e.g. Realmbreaker) counts its damage on its home
        melee side but never PULLS AGAINST a core, because it can serve
        either fight. Each member also gets a fit verdict for the declared
        (or detected) style at this party size, from the E-first
        derivation + owner overrides; unfit members are named conflicts
        (the Battleaxe rule).

        DESCRIPTIVE ONLY (F-V3-2): nothing here feeds fitness,
        recommendation order, or the forge."""
        n = len(party)
        melee = ranged = aoe = sus = st = commit = evade = 0.0
        carriers = {"melee": [], "ranged": []}
        carrier_count = {}
        n_carrier_members = 0
        flex = set()
        sides = {}
        for i, w in enumerate(party):
            caps = self._raw_member_caps(w, combos[i] if combos else None)
            dmg = sum(caps.get(c, 0) for c in self.DAMAGE_CAPS_PROFILE)
            aoe += caps.get("burst_aoe", 0)
            sus += caps.get("sustained_dps", 0)
            st += caps.get("burst_st", 0) + caps.get("execute", 0)
            commit += caps.get("engage", 0) + caps.get("clump_create", 0)
            evade += caps.get("mobility", 0) + caps.get("disengage", 0)
            if dmg < self.IDENTITY_CARRIER_MIN:
                continue
            sf = self._style_fit_of(w)
            if sf:
                delivery = sf["delivery"]
            else:
                ar = (self.stats_of(w).get("stats") or {}).get("attackrange", 0)
                delivery = ("ranged" if ar >= self.IDENTITY_RANGED_ATTACK
                            else "melee")
            side = "ranged" if delivery == "ranged" else "melee"
            if delivery == "flex":
                flex.add(w)
            sides[i] = side
            if w not in carriers[side]:
                carriers[side].append(w)
            carrier_count[w] = carrier_count.get(w, 0) + 1
            n_carrier_members += 1
            if side == "ranged":
                ranged += dmg
            else:
                melee += dmg
        tot = melee + ranged
        dmg_tot = aoe + sus + st
        mel = melee / tot if tot else 0.5
        mode = {"aoe": aoe / dmg_tot if dmg_tot else 0.0,
                "sustained": sus / dmg_tot if dmg_tot else 0.0,
                "single_target": st / dmg_tot if dmg_tot else 0.0}
        posture = commit / (commit + evade) if commit + evade else 0.5
        band = self._fit_band()
        out = {"style": None, "label": "", "strength": None,
               "melee_share": mel, "ranged_share": 1.0 - mel if tot else 0.5,
               "carriers": carriers, "mode": mode, "posture": posture,
               "band": band, "members": [], "conflicts": []}
        style_names = {k: (v.get("name") or k)
                       for k, v in (self.data.get("styles") or {}).items()}
        forming = n < self.IDENTITY_MIN_MEMBERS or tot == 0
        if forming:
            out["label"] = "still forming"
        elif mel >= self.IDENTITY_MELEE_CORE:
            out["style"] = "brawl"
            out["strength"] = ("strong" if mel >= self.IDENTITY_STRONG
                              else "leaning")
            out["label"] = f"{style_names.get('brawl', 'Brawl')} — melee ball"
        elif mel <= self.IDENTITY_RANGED_CORE:
            clap = mode["aoe"] >= self.IDENTITY_CLAP_AOE
            out["style"] = "clap" if clap else "kite"
            out["strength"] = ("strong"
                              if mel <= 1.0 - self.IDENTITY_STRONG
                              else "leaning")
            # Bomb-squad archetype (owner, blind label round 2026-08-23):
            # a near-monoculture ranged burst comp is an off-timer artillery
            # DETACHMENT supporting a main party — "a different play style
            # for party" — not an ordinary clap. Signature: one weapon holds
            # at least half of at least 3 damage-carrier bodies.
            top_carrier = max(carrier_count.values()) if carrier_count else 0
            evade_pm = evade / n if n else 0.0
            if (clap and top_carrier >= 3
                    and top_carrier * 2 >= n_carrier_members):
                out["archetype"] = "bomb_squad"
                out["label"] = ("Bomb squad — off-timer artillery "
                                "(clap detachment)")
            elif (mode["aoe"] >= self.IDENTITY_HYBRID_AOE
                    and evade_pm >= self.IDENTITY_HYBRID_EVADE):
                out["style"] = "clap_kite"
                out["strength"] = "leaning"
                out["label"] = (f"{style_names.get('clap_kite', 'Clap-Kite')}"
                                " — bomb from range, reset on cooldowns")
            else:
                out["label"] = (f"{style_names.get('clap', 'Clap')} — ranged bomb"
                                if clap else
                                f"{style_names.get('kite', 'Kite')} — ranged pressure")
        elif (mode["aoe"] >= self.IDENTITY_BC_AOE
              and posture >= self.IDENTITY_BC_POSTURE):
            out["style"] = "brawl_clap"
            out["strength"] = "leaning"
            out["label"] = (f"{style_names.get('brawl_clap', 'Brawl-Clap')}"
                            " — grind into the bomb")
        else:
            minority = ("melee" if (mel, len(carriers["melee"]))
                        < (1.0 - mel, len(carriers["ranged"]))
                        else "ranged")
            majority = "ranged" if minority == "melee" else "melee"
            # flex weapons serve either fight; UTILITY CARRIERS (pierce/
            # catch bots — Harpoon) have a utility identity, not a damage
            # identity, so neither can anchor a damage-identity split
            # (blind-label ruling 2026-08-23: the 20v20 comp is a clap,
            # not a split, and Spirithunter is why it misread).
            rigid = [w for w in carriers[minority]
                     if w not in flex
                     and not ((self._style_fit_of(w) or {})
                              .get("utility_carrier"))]
            if not rigid:
                # every minority carrier is flex — it can serve the
                # majority's fight, so the comp is NOT split
                if majority == "melee":
                    out["style"] = "brawl"
                    out["strength"] = "leaning"
                    out["label"] = (f"{style_names.get('brawl', 'Brawl')}"
                                    " — melee ball")
                else:
                    clap = mode["aoe"] >= self.IDENTITY_CLAP_AOE
                    evade_pm2 = evade / n if n else 0.0
                    if (mode["aoe"] >= self.IDENTITY_HYBRID_AOE
                            and evade_pm2 >= self.IDENTITY_HYBRID_EVADE):
                        out["style"] = "clap_kite"
                        out["strength"] = "leaning"
                        out["label"] = (f"{style_names.get('clap_kite', 'Clap-Kite')}"
                                        " — bomb from range, reset on cooldowns")
                    else:
                        out["style"] = "clap" if clap else "kite"
                        out["strength"] = "leaning"
                        out["label"] = (f"{style_names.get('clap', 'Clap')} — ranged bomb"
                                        if clap else
                                        f"{style_names.get('kite', 'Kite')} — ranged pressure")
            else:
                out["label"] = ("split identity — melee and ranged damage "
                                "pull apart")
                for w in rigid:
                    out["conflicts"].append({
                        "weapon": w,
                        "display_name": self.weapons[w]["display_name"],
                        "side": minority, "kind": "split",
                        "note": (f"{minority} damage inside a {majority}-"
                                 "leaning core — commit to one side or "
                                 "cover the seam"),
                    })
        # ---- per-member fit verdicts (the declared style is the caller's
        # INTENT — owner ruling: picking brawl means asking for brawl
        # builds; balanced falls back to the detected lean) ----
        fit_style = (self.style if self.style in self.IDENTITY_STYLES
                     else out["style"])
        for i, w in enumerate(party):
            sf = self._style_fit_of(w)
            verdict = ((sf["fit"].get(fit_style) or {}).get(band)
                       if sf and fit_style else None)
            m = {"weapon": w,
                 "display_name": self.weapons[w]["display_name"],
                 "role": self.role_of(w),
                 "side": ("flex" if w in flex else sides.get(i)),
                 "fit": verdict}
            if verdict == "unfit" and not forming:
                reason = ("its E is not a group-scale damage tool at this size"
                          if sf and sf["damage_scale"] == "single"
                          else f"off-{fit_style} at this size")
                m["note"] = reason
                out["conflicts"].append({
                    "weapon": w,
                    "display_name": m["display_name"],
                    "side": m["side"], "kind": "unfit",
                    "note": (f"unfit for {style_names.get(fit_style, fit_style)}"
                             f" at {self.size} — {reason}"),
                })
            out["members"].append(m)
        return out

    def kill_pressure(self, party, combos=None, gears=None):
        """The caller's kill checklist as a three-light verdict (identity
        Phase D, owner 2026-08-23): pierce on the clump (resist_shred),
        heal-cut applied (heal_reduction), and enough burst to actually
        kill. Each light's bar is the sum of its capabilities' size-scaled
        template targets — the comp-fitted numbers real comps set
        (VALIDATION.md 2026-08-21) — and `have` reads effective_supply, so
        focus-fire tax and AoE escalation are already priced in.

        DESCRIPTIVE ONLY: a verdict panel, never a score term. Returns
        None when the dataset carries no kill_pressure block."""
        cfg = self.mechanics.get("kill_pressure")
        if not cfg:
            return None
        ratio = cfg.get("pass_ratio", 0.85)
        s = self.effective_supply(party, combos, gears)

        def light(caps):
            used = [c for c in caps if c in self.reqs]
            bar = sum(self.target(c) for c in used)
            have = sum(s.get(c, 0.0) for c in used)
            return {"caps": used, "have": have, "bar": bar,
                    "ok": bar <= 0 or have >= ratio * bar}
        out = {"pierce": light(cfg.get("pierce_caps") or []),
               "heal_cut": light(cfg.get("heal_cut_caps") or []),
               "burst": light(cfg.get("burst_caps") or []),
               "pass_ratio": ratio}
        greens = sum(1 for k in ("pierce", "heal_cut", "burst")
                     if out[k]["ok"])
        out["verdict"] = ("ready" if greens == 3
                          else "partial" if greens == 2 else "lacking")
        return out

    # Fight-chain verdict thresholds (lens over the comp-fitted targets,
    # like kill_pressure): a stage is weak under CHAIN_WEAK of its bar,
    # strong at/above CHAIN_STRONG, missing at zero supply.
    CHAIN_WEAK = 0.85
    CHAIN_STRONG = 1.15

    def fight_chain(self, party, combos=None, gears=None, candidate=None):
        """The comp as the SEQUENCE a caller thinks the fight in (roadmap
        item 1, owner vocabulary): the declared style's chain from
        styles.yaml — balanced falls back to the detected identity's
        chain — with every stage graded against the comp-fitted template
        targets over effective supply. Verdicts: strong / ok / weak /
        missing; stages whose capabilities this content does not require
        read quiet (no bar to fail).

        `candidate` (optional, a weapon key): also reports which stage
        that pick improves most, from the same explain() terms the
        recommendation shows — connecting the engine's pick to the stage
        it repairs.

        DESCRIPTIVE ONLY: nothing here feeds scoring. Returns None when
        no chain applies (no declared style and no detected identity)."""
        styles = self.data.get("styles") or {}
        style = (self.style if self.style in self.IDENTITY_STYLES
                 else self.comp_identity(party, combos)["style"])
        chain = (styles.get(style) or {}).get("chain") if style else None
        if not chain:
            return None
        s = self.effective_supply(party, combos, gears)
        # spell-level sources (2026-08-24): which equipped buttons ARE each
        # stage — every member's resolved loadout (always + chosen bundles,
        # mechanics applied: the same numbers scoring sums) attributed back
        # to the slot/spell that carries each stage capability. `spell` None
        # = the weapon's always-on kit (passives/stats). Units are
        # per-member contributions BEFORE the party-level count-once rule;
        # the stage's `have` stays the authoritative total. Gear
        # contributions are not attributed. Display only.
        members = []
        for mi, w in enumerate(party):
            lo = self.weapons[w].get("loadout") or {}
            names = lo.get("slot_names") or []
            spells = lo.get("slot_spells") or []
            always_eff, slots_eff = self._loadout_eff(w)
            picks = []
            for oi, ci in self.combo_choices(w, combos[mi] if combos else None):
                if oi >= len(slots_eff) or ci >= len(slots_eff[oi]):
                    continue
                sid = (spells[oi][ci]
                       if oi < len(spells) and ci < len(spells[oi]) else None)
                picks.append((names[oi] if oi < len(names) else None,
                              sid, slots_eff[oi][ci]))
            members.append((mi, w, always_eff, picks))
        stages = []
        for st in chain:
            used = [c for c in (st.get("caps") or []) if c in self.reqs]
            bar = sum(self.target(c) for c in used)
            have = sum(s.get(c, 0.0) for c in used)
            sources = []
            for cap in used:
                for mi, w, always_eff, picks in members:
                    v = always_eff.get(cap, 0.0)
                    if v:
                        sources.append({
                            "cap": cap, "member": mi, "weapon": w,
                            "display_name": self.weapons[w]["display_name"],
                            "slot": None, "spell": None, "units": v})
                    for slot_nm, sid, bundle in picks:
                        v = bundle.get(cap, 0.0)
                        if v:
                            sources.append({
                                "cap": cap, "member": mi, "weapon": w,
                                "display_name": self.weapons[w]["display_name"],
                                "slot": slot_nm, "spell": sid, "units": v})
            if not used or bar <= 0:
                verdict = "quiet"
            elif have <= 0:
                verdict = "missing"
            elif have < self.CHAIN_WEAK * bar:
                verdict = "weak"
            elif have >= self.CHAIN_STRONG * bar:
                verdict = "strong"
            else:
                verdict = "ok"
            stages.append({"name": st.get("name"), "caps": used,
                           "have": have, "bar": bar, "verdict": verdict,
                           "sources": sources})
        out = {"style": style, "stages": stages, "improves": None}
        if candidate and candidate in self.weapons:
            # explain() deltas are already weighted fitness terms —
            # summed per stage, never re-weighted
            deltas = {t["cap"]: t["delta"]
                      for t in self.explain(party, candidate, combos)}
            total = sum(deltas.values())
            best_stage, best_gain, best_caps = None, 0.0, []
            for st in stages:
                gain = sum(deltas.get(c, 0.0) for c in st["caps"])
                if gain > best_gain + 1e-9:
                    best_stage, best_gain, best_caps = st["name"], gain, st["caps"]
            # claim the connection only when that stage holds a real share
            # of the pick's explained value — a healer into a clap chain
            # (which has no healing stage) improves SURVIVAL, not a stage,
            # and saying "improves Reset" would mislead the caller
            if (best_stage is not None and total > 0
                    and best_gain >= 0.3 * total):
                # name the terms behind the claim (2026-08-24): a stage can
                # win on SUMMED caps none of which is the pick's single top
                # term — "Reset (+1.7 mobility, +1.6 disengage)" over a
                # bare "Reset" the caller cannot reconcile with the tiles
                out["improves"] = {"stage": best_stage, "gain": best_gain,
                                   "terms": [{"cap": c, "gain": deltas[c]}
                                             for c in best_caps
                                             if deltas.get(c, 0.0) > 0]}
        return out

    # ------------------------------------------------------------ local search
    def refine(self, party, max_passes=8, pool=None, fixed=0, gears=None):
        """1-opt local search over a built party: repeatedly apply the single
        slot replacement that most improves comp_score, until none does.
        Steepest-descent (best move per pass, not first-improvement) so the
        result does not depend on slot or weapon iteration order. `fixed`
        locks the first N slots. Returns a NEW list; the input is not
        mutated. UNCONSTRAINED — the forge runs its own constraint-aware
        refinement; this stays for parity and ad-hoc callers.

        gears (owner ruling 2026-08-27): with a parallel per-member kit
        list, refinement optimizes the SAME dressed comp_score used
        everywhere else — incumbent kits are preserved, a replacement
        candidate is tried in each of its doctrine kit variants (naked
        when it has none or dressing is off; same-weapon re-kitting is
        not searched, matching the legacy same-weapon skip), and the
        result returns {"party", "gears"}. gears=None keeps the legacy
        weapon-only search bit-identical, returning the plain list."""
        party = list(party)
        if gears is None:
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
        gl = [(list(g) if g else None) for g in gears]
        while len(gl) < len(party):
            gl.append(None)
        gl = gl[:len(party)]
        if not party:
            return {"party": party, "gears": gl}
        candidates = list(pool or self.pool)
        best = self.comp_score(party, None, gl)
        for _ in range(max_passes):
            move, gain = None, 1e-9   # strictly-positive gain required
            for i in range(fixed, len(party)):
                orig_w, orig_g = party[i], gl[i]
                for w in candidates:
                    if w == orig_w:
                        continue
                    party[i] = w
                    for _vk, vg in self.kit_variants(w):
                        gl[i] = vg
                        d = self.comp_score(party, None, gl) - best
                        if d > gain:
                            move, gain = (i, w, vg), d
                party[i], gl[i] = orig_w, orig_g
            if move is None:
                break
            party[move[0]] = move[1]
            gl[move[0]] = list(move[2]) if move[2] else None
            best += gain
        return {"party": party, "gears": gl}

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
            if key in self.pred_defs or key == self.PRIMARY_HEAL:
                if "min" in rule:
                    pred_min[key] = rule["min"]
                continue
            if "min" in rule:
                role_min[key] = rule["min"]
            if "max" in rule:
                role_max[key] = rule["max"]
        # need-profile minima ride the predicate channel (membership-based
        # contributions are added in _forge_counts / unions at the eval
        # sites); seat maxima get their own key
        for k, mn in self._profile_min.items():
            pred_min[k] = mn
        # Capacity gates per predicate minimum (deadlock guard, 2026-08-27):
        # the (role, seat) pairs of every pool weapon that could satisfy the
        # predicate. A pick that fills the last band slot those satisfiers
        # need would strand the minimum — _forge_feasible refuses it. Found
        # when Option C floor re-pricing steered every beam into picking a
        # band-capping non-full healer while primary_heal was unmet (the
        # beam died at 6/7); the blind spot itself predates the re-pricing.
        pred_gates = {}
        for pn in pred_min:
            gates = set()
            for w2 in pool:
                if pn in self._pred_possible(w2) \
                        or pn in (self._profile_members.get(w2) or ()):
                    gates.add((self.role_of(w2),
                               self._profile_primary.get(w2)))
            pred_gates[pn] = gates
        return {"pool": pool, "role_min": role_min, "role_max": role_max,
                "pred_min": pred_min, "seat_max": dict(self._profile_max),
                "pred_gates": pred_gates}

    def _forge_counts(self, party, combos=None):
        """(weapon counts, role counts, predicate counts, group counts).
        Predicate counts are COMBO-AWARE: a member counts only when the
        spell combination it actually equips satisfies the minima (review
        2026-08-19 — the flat count marked comps ranged-AoE-legal while the
        selected loadouts supplied less)."""
        counts, roles, preds, groups = {}, {}, {}, {}
        for i, w in enumerate(party):
            counts[w] = counts.get(w, 0) + 1
            r = self.role_of(w)
            roles[r] = roles.get(r, 0) + 1
            for pn in self._pred_contrib(w, combos[i] if combos else None):
                preds[pn] = preds.get(pn, 0) + 1
            for pn in self._profile_members.get(w) or ():
                preds[pn] = preds.get(pn, 0) + 1
            for gi in self.groups_of.get(w, []):
                groups[gi] = groups.get(gi, 0) + 1
        return counts, roles, preds, groups

    def _forge_min_need(self, ctx, roles, preds, w, pred_contrib):
        """Slots still required for unmet role/predicate minima after adding
        `w` whose predicate contribution is `pred_contrib` (a weapon may
        serve one role AND a predicate; the sum slightly over-counts that
        overlap — conservative, documented)."""
        need = 0
        r = self.role_of(w)
        for r2, mn in ctx["role_min"].items():
            have = roles.get(r2, 0) + (1 if r2 == r else 0)
            if mn > have:
                need += mn - have
        for pn, mn in ctx["pred_min"].items():
            have = preds.get(pn, 0) + (1 if pn in pred_contrib else 0)
            if mn > have:
                need += mn - have
        return need

    def _forge_feasible(self, ctx, counts, roles, preds, groups, w, slots_left_after):
        """May the forge add `w` here and still complete a legal roster?
        Predicate contribution is OPTIMISTIC here (any combo could qualify) —
        the cheap prune before a combo is chosen; _forge_eval_pick enforces
        the exact per-combo need afterwards."""
        if counts.get(w, 0) >= self._dup_gen_max(w):
            return False
        for gi in self.groups_of.get(w, []):
            if groups.get(gi, 0) >= self.groups[gi].get("max", 10 ** 9):
                return False
        r = self.role_of(w)
        mx = ctx["role_max"].get(r)
        if mx is not None and roles.get(r, 0) >= mx:
            return False
        p0 = self._profile_primary.get(w)
        smx = ctx["seat_max"].get(p0) if p0 else None
        if smx is not None and preds.get(p0, 0) >= smx:
            return False
        contrib = (self._pred_possible(w)
                   | (self._profile_members.get(w) or frozenset()))
        need = self._forge_min_need(ctx, roles, preds, w, contrib)
        if need > slots_left_after:
            return False
        # Deadlock guard (2026-08-27): after this pick, every UNMET
        # predicate minimum must keep at least one satisfier whose role
        # band AND fine seat still have capacity — otherwise the pick
        # strands the minimum behind a full band and the beam dies short
        # (a full healer can never join once the healer band is spent on
        # hybrids). Gates precomputed per predicate in _forge_ctx.
        for pn, mn in ctx["pred_min"].items():
            have = preds.get(pn, 0) + (1 if pn in contrib else 0)
            if have >= mn:
                continue
            gates = ctx["pred_gates"].get(pn)
            if not gates:
                continue    # no satisfier in pool at all: the old need
            open_gate = False   # arithmetic already reports that honestly
            for r2, s2 in gates:
                mx2 = ctx["role_max"].get(r2)
                if mx2 is not None \
                        and roles.get(r2, 0) + (1 if r2 == r else 0) >= mx2:
                    continue
                smx2 = ctx["seat_max"].get(s2) if s2 else None
                if smx2 is not None \
                        and preds.get(s2, 0) + (1 if s2 == p0 else 0) >= smx2:
                    continue
                open_gate = True
                break
            if not open_gate:
                return False
        return True

    def _forge_eval_pick(self, ctx, beam, w, slots_left_after):
        """_eval_pick restricted to combos that keep the roster completable:
        a combo whose ACTUAL predicate contribution would leave more unmet
        minima than remaining slots is not offered — the beam may not spend
        a needed core slot on a non-qualifying spell kit. With no predicate
        minima active every combo passes and this is exactly _eval_pick."""
        state = beam["state"]
        best = None
        extras = self._combo_extras(w)
        dressed = self._dressed_extras(w)
        variants = self.kit_variants(w)
        for i in range(len(extras)):
            # predicate feasibility is per COMBO only — kit variants never
            # change predicate contributions (predicates are weapon/combo
            # -keyed), so the check runs once per combo, outside variants
            if ctx["pred_min"]:
                need = self._forge_min_need(
                    ctx, beam["roles"], beam["preds"], w,
                    self._pred_contrib(w, i)
                    | (self._profile_members.get(w) or frozenset()))
                if need > slots_left_after:
                    continue
            for vkey, vgears in variants:
                val, d_fit, d_syn = self._combo_score_dressed(
                    state, w, i, extras[i], dressed[vkey][i], vkey)
                if best is None or val > best[0]:
                    best = (val, d_fit, d_syn, i, vkey, vgears)
        if best is None:
            return None
        score, d_fit, d_syn, meta, combo = self._pick_tail(
            state, w, best[:4])
        return score, d_fit, d_syn, meta, combo, best[4], best[5]

    @staticmethod
    def _member_tag(w, combo, vkey="-"):
        """Canonical member key for beam dedup. The kit-variant id is part
        of the identity (dressed forge 2026-08-27): two beams differing
        only by a member's kit are different rosters. Locked members and
        naked picks tag '-'."""
        return (w + "#" + ("d" if combo is None else str(combo))
                + "#" + vkey)

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

    def forge(self, size, locked=None, locked_combos=None, pool=None,
              beam_width=8, locked_gears=None):
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

        counts, roles, preds, groups = self._forge_counts(locked, combos)
        # locked_gears (owner ruling 2026-08-27): a locked member supplied
        # with explicit gear is scored in EXACTLY that kit and never
        # re-dressed; one without stays naked — the forge never invents
        # gear for a lock. Normalized like locked_combos (short list pads
        # with None); legacy calls keep the all-naked seed bit-identically.
        lg = locked_gears or []
        gears0 = [(list(lg[i]) if i < len(lg) and lg[i] else None)
                  for i in range(len(locked))]
        state = self.party_state(locked, combos, gears0)
        items0 = sorted(self._member_tag(w, c) for w, c in zip(locked, combos))
        beams = [{"party": locked, "combos": combos, "gears": gears0,
                  "counts": counts, "roles": roles, "preds": preds,
                  "groups": groups, "state": state, "items": items0,
                  "score": self.comp_score(locked, combos, gears0)}]
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
                    pick = self._forge_eval_pick(ctx, beam, w, slots_left_after)
                    if pick is None:
                        continue      # no combo keeps the minima satisfiable
                    sc, combo, vkey, vgears = pick[0], pick[4], pick[5], pick[6]
                    expansions.append((beam["score"] + sc, bi, w, combo,
                                       vkey, vgears))
            if not expansions:
                feasible = False
                break
            # stable sort by score only: equal scores keep (beam, pool) append
            # order — deterministic in both engines. The canonical multiset
            # key is computed LAZILY, only for candidates actually considered
            # for the beam (it was the hottest line at size 60).
            expansions.sort(key=lambda t: -t[0])
            next_beams, seen = [], set()
            for score, bi, w, combo, vkey, vgears in expansions:
                beam = beams[bi]
                items = self._insert_sorted(beam["items"],
                                            self._member_tag(w, combo, vkey))
                key = "|".join(items)
                if key in seen:
                    continue
                seen.add(key)
                party2 = beam["party"] + [w]
                combos2 = beam["combos"] + [combo]
                gears2 = beam["gears"] + [vgears]
                counts2, roles2, preds2, groups2 = self._forge_counts(party2, combos2)
                next_beams.append({"party": party2, "combos": combos2,
                                   "gears": gears2,
                                   "counts": counts2, "roles": roles2,
                                   "preds": preds2, "groups": groups2,
                                   "state": self.party_state(party2, combos2,
                                                             gears2),
                                   "items": items,
                                   "score": self.comp_score(party2, combos2,
                                                            gears2)})
                if len(next_beams) >= beam_width:
                    break
            beams = next_beams
        best = beams[0]
        party, combos = best["party"], best["combos"]
        gears = best["gears"]
        fixed = len(locked)
        if len(party) > fixed:
            # refine -> pair-trade -> refine: a 2-opt pair gain can leave one
            # of its two slots individually negative; the closing 1-opt pass
            # cleans that up (or the filler audit below surfaces it honestly)
            party, combos, gears = self._refine_constrained(
                ctx, party, combos, gears, fixed)
            party, combos, gears = self._two_opt(
                ctx, party, combos, gears, fixed)
            party, combos, gears = self._refine_constrained(
                ctx, party, combos, gears, fixed)
        # filler audit — a generated member that REDUCES the objective is
        # surfaced, never silently kept quiet. A negative slot whose removal
        # would break a minimum constraint is `held` (mandated structure);
        # one the constraints don't need is `filler` (must not survive the
        # refinement passes — pinned by tests/test_forge.py).
        filler, held = [], []
        base = self.comp_score(party, combos, gears)
        for i in range(fixed, len(party)):
            sub = party[:i] + party[i + 1:]
            sub_c = combos[:i] + combos[i + 1:]
            sub_g = gears[:i] + gears[i + 1:]
            if base - self.comp_score(sub, sub_c, sub_g) >= -1e-9:
                continue
            _counts, roles, preds, _groups = self._forge_counts(sub, sub_c)
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
        # final feasibility net: the SELECTED combos must meet every minimum.
        # Construction guarantees it for generated slots; locked members with
        # non-qualifying spell picks can still leave a minimum unmet — that
        # is reported honestly, never counted through the flat sheet map.
        _c, roles_f, preds_f, _g = self._forge_counts(party, combos)
        for r, mn in ctx["role_min"].items():
            if roles_f.get(r, 0) < mn:
                feasible = False
        for pn, mn in ctx["pred_min"].items():
            if preds_f.get(pn, 0) < mn:
                feasible = False
        kits = {}
        for i in range(fixed, len(party)):
            if gears[i]:
                kits[i] = {"variant": next(
                    (vk for vk, gl in self.kit_variants(party[i])
                     if gl == gears[i]), None), "gears": gears[i]}
        return {"party": party, "combos": combos, "gears": gears,
                "kits": kits, "score": base,
                "feasible": feasible, "filler": filler, "held": held,
                "locked": fixed}

    def _add_ok(self, ctx, counts, roles, preds, groups, w):
        """Copy/group/role-MAX/seat-MAX check for adding `w` to a roster
        whose counts exclude the slot being replaced. Minima (roles AND
        combo-aware predicates) are enforced through _forge_eval_pick's
        exact per-combo need — the old flat pred delta let a swap replace
        a member whose SELECTED spells filled a minimum (review
        2026-08-19)."""
        if counts.get(w, 0) + 1 > self._dup_gen_max(w):
            return False
        for gi in self.groups_of.get(w, []):
            if groups.get(gi, 0) + 1 > self.groups[gi].get("max", 10 ** 9):
                return False
        mx = ctx["role_max"].get(self.role_of(w))
        if mx is not None and roles.get(self.role_of(w), 0) + 1 > mx:
            return False
        p0 = self._profile_primary.get(w)
        smx = ctx["seat_max"].get(p0) if p0 else None
        if smx is not None and preds.get(p0, 0) + 1 > smx:
            return False
        return True

    def _refine_constrained(self, ctx, party, combos, gears, fixed,
                            max_passes=8):
        """Steepest-descent 1-opt over generated slots, constraint-aware.
        Replacement combos AND kit variants re-resolve dynamically (the
        replacement is scored exactly as a dressed pick into the rest of
        the party); minima are checked against the REST roster's
        combo-aware counts, so a swap can never trade away the spells a
        minimum was counting on."""
        party, combos = list(party), list(combos)
        gears = list(gears)
        best = self.comp_score(party, combos, gears)
        for _ in range(max_passes):
            move, gain = None, 1e-9
            for i in range(fixed, len(party)):
                rest = party[:i] + party[i + 1:]
                rest_c = combos[:i] + combos[i + 1:]
                rest_g = gears[:i] + gears[i + 1:]
                counts_r, roles_r, preds_r, groups_r = \
                    self._forge_counts(rest, rest_c)
                state = self.party_state(rest, rest_c, rest_g)
                base_rest = self.comp_score(rest, rest_c, rest_g)
                contrib = best - base_rest
                beam = {"state": state, "roles": roles_r, "preds": preds_r}
                for w in ctx["pool"]:
                    # w == party[i] is deliberately NOT skipped (dressed
                    # forge 2026-08-27): the beam froze this slot's
                    # combo+kit under an earlier partial state, and
                    # re-resolving the SAME weapon can be the best move —
                    # identical picks price d == 0 and are never taken.
                    if not self._add_ok(ctx, counts_r, roles_r, preds_r,
                                        groups_r, w):
                        continue
                    pick = self._forge_eval_pick(ctx, beam, w, 0)
                    if pick is None:
                        continue
                    d = pick[0] - contrib
                    if d > gain:
                        move, gain = (i, w, pick[4], pick[6]), d
            if move is None:
                break
            party[move[0]] = move[1]
            combos[move[0]] = move[2]
            gears[move[0]] = move[3]
            best = self.comp_score(party, combos, gears)
        return party, combos, gears

    def _two_opt(self, ctx, party, combos, gears, fixed, worst_k=4,
                 cand_m=12):
        """Bounded 2-opt: re-solve the `worst_k` weakest generated slots in
        pairs, drawing replacements from the top `cand_m` single-slot
        candidates. Catches pair-trades 1-opt cannot see; bounded so the
        browser build stays under the perf targets. An accepted pair-move
        REORDERS the roster (the pair is removed, replacements append), so
        the pass restarts with freshly computed weakest slots — stale
        indexes used to re-solve arbitrary slots (review 2026-08-18)."""
        party, combos = list(party), list(combos)
        gears = list(gears)
        best = self.comp_score(party, combos, gears)
        if len(party) - fixed < 2:
            return party, combos, gears
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
                sub_g = gears[:i] + gears[i + 1:]
                contribs.append((best - self.comp_score(sub, sub_c, sub_g), i))
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
                    rest_g = gears[:i] + gears[i + 1:j] + gears[j + 1:]
                    state = self.party_state(rest, rest_c, rest_g)
                    ranked = []
                    for w in ctx["pool"]:
                        sc, _df, _ds, _meta, combo, _v, vg = \
                            self._eval_pick(state, w)
                        ranked.append((sc, w, combo, vg))
                    ranked.sort(key=lambda t: (-t[0], t[1]))
                    shortlist = ranked[:cand_m]
                    for sa, wa, ca, ga in shortlist:
                        if improved:
                            break
                        pa = rest + [wa]
                        pca = rest_c + [ca]
                        pga = rest_g + [ga]
                        state2 = self.party_state(pa, pca, pga)
                        for _sb, wb, _cb, _gb in shortlist:
                            sc_b, _df2, _ds2, _m2, cb2, _v2, gb2 = \
                                self._eval_pick(state2, wb)
                            cand_party = pa + [wb]
                            cand_combos = pca + [cb2]
                            cand_gears = pga + [gb2]
                            counts, roles, preds, groups = \
                                self._forge_counts(cand_party, cand_combos)
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
                                for s, mx in ctx["seat_max"].items():
                                    if preds.get(s, 0) > mx:
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
                            d = self.comp_score(cand_party, cand_combos,
                                                cand_gears) - best
                            if d > 1e-9:
                                party = cand_party
                                combos = cand_combos
                                gears = cand_gears
                                best = best + d
                                improved = True
                                break
        return party, combos, gears


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
