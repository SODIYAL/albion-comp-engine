/* Composition scoring — JavaScript port of engine/engine.py.
 *
 * SINGLE SOURCE OF MATH: engine/engine.py is authoritative; this file must
 * mirror it exactly and tests/test_js_parity.py verifies that it does
 * (same fitness, same rankings, same forged rosters, across all templates,
 * on random parties). If you change one, change both, then run the parity
 * test.
 *
 * Used two ways:
 *   - inlined into dashboard/index.html by build_dashboard.py (browser —
 *     dashboard/_app.js is rendering-only and calls this engine)
 *   - require()'d by tests/js_parity_runner.js (node)
 */
(function (root) {
  "use strict";

  /* Mechanics-affected capability families (MECHANICS_TODO.md): mirrors
     AOE_ESCALATION_CAPS / RESILIENCE_CAPS in engine.py. */
  var AOE_ESCALATION_CAPS = ["burst_aoe"];
  var RESILIENCE_CAPS = ["burst_st", "execute"];

  function CompEngine(data, content, size, style) {
    this.data = data;
    this.weapons = data.weapons;
    this.scoring = data.scoring;
    var w = this.scoring.weights;
    this.alpha = w.alpha; this.beta = w.beta;
    this.delta = w.delta; this.gamma = w.gamma;
    /* Over-stack asymptote (scoring.yaml); defaulted for older datasets. */
    this.overstackMax = (w.overstack_max === undefined) ? 0.5 : w.overstack_max;
    /* Redundancy weight (rho), viability prior weight and headroom slope
       (2026-08-18) — all default 0 so an older dataset scores as it used to.
       Mirrors engine.py __init__. */
    this.rho = w.rho || 0.0;
    this.viabilityW = w.viability || 0.0;
    this.headroom = w.headroom || 0.0;
    this.metaPrior = this.scoring.meta_prior || {};
    var mpKeys = Object.keys(this.metaPrior);
    this.metaBucketed = mpKeys.length > 0 &&
      mpKeys.every(function (k) { return k === "small" || k === "mid" || k === "large"; });
    this.synergies = (this.scoring.capability_synergies || []).map(function (s) {
      return [s.a, s.b, s.bonus];
    });
    this.mechanics = data.mechanics || {};
    /* Composition layer (composition.yaml -> dataset): forge constraints,
       duplication, viability, size physics. Mirrors engine.py __init__. */
    var comp = data.composition || {};
    this.compCfg = comp;
    var rolesCfg = comp.roles || {};
    var byHint = rolesCfg.by_hint || {};
    var overrides = rolesCfg.overrides || {};
    this.roleClass = {};
    var k;
    for (k in this.weapons) {
      this.roleClass[k] = overrides[k] !== undefined ? overrides[k]
        : (byHint[this.weapons[k].role_hint] !== undefined
           ? byHint[this.weapons[k].role_hint] : "dps");
    }
    this.predMembers = {};
    var preds = comp.predicates || {};
    for (var pn in preds) {
      var mins = preds[pn], members = {};
      for (k in this.weapons) {
        var okp = true;
        for (var pc in mins) {
          if ((this.weapons[k].capabilities[pc] || 0) < mins[pc]) { okp = false; break; }
        }
        if (okp) members[k] = true;
      }
      this.predMembers[pn] = members;
    }
    var dup = comp.duplication || {};
    this.dupFreeDefault = (dup.free_copies_default === undefined) ? 1 : dup.free_copies_default;
    this.dupMaxSmall = (dup.max_copies_default_small === undefined) ? 1e9 : dup.max_copies_default_small;
    this.dupMaxLarge = (dup.max_copies_default_large === undefined) ? 1e9 : dup.max_copies_default_large;
    this.dupPerWeapon = dup.per_weapon || {};
    this.dupPwMinSize = (dup.per_weapon_min_size === undefined) ? 10 : dup.per_weapon_min_size;
    this.groups = comp.groups || [];
    this.groupsOf = {};
    for (var gi = 0; gi < this.groups.length; gi++) {
      var gw = this.groups[gi].weapons || [];
      for (var gj = 0; gj < gw.length; gj++) {
        (this.groupsOf[gw[gj]] = this.groupsOf[gw[gj]] || []).push(gi);
      }
    }
    var sp = comp.size_physics || {};
    this.countMultTable = sortedTable(sp.count_mult || {});
    this.stBoostMaxSize = (sp.st_boost_max_size === undefined) ? 5 : sp.st_boost_max_size;
    this.stValueTable = sortedTable(sp.st_value_mult || {});
    /* Item stats bank — REFERENCE DATA ONLY, no scoring path reads it. */
    this.itemStats = data.item_stats || {};
    /* Candidate pool: non-retired weapons, insertion order preserved (the
       deterministic tie-breaks and refine() walk the same sequence as
       engine.py). */
    this.pool = [];
    for (var pk in this.weapons) if (!this.weapons[pk].removed) this.pool.push(pk);
    this.setContent(content || "castle_outpost", size, style);
  }

  function sortedTable(obj) {
    var out = [];
    for (var k in obj) out.push([parseInt(k, 10), obj[k]]);
    out.sort(function (a, b) { return a[0] - b[0]; });
    return out;
  }

  CompEngine.prototype.setContent = function (content, size, style) {
    this.template = this.data.templates[content];
    this.content = content;
    this.baseSize = this.template.base_size || size;
    this.size = (size === undefined || size === null) ? this.baseSize : size;
    this.reqs = this.template.requirements;
    this.floors = this.template.hard_floors || {};
    /* Playstyle overlay: multiplies capability WEIGHTS only (mirrors
       engine.py). */
    this.style = style || "balanced";
    var styles = this.data.styles || {};
    this.styleMults = (styles[this.style] || {}).multipliers || {};
    /* Mechanics overlay (2026-08-18): the linear grow() extrapolation is
       replaced by the piecewise absolute size table (size_physics). The
       Resilience ratio is factorized into a STYLE factor (never clamped)
       and a SIZE factor (clamped at 1.0 above stBoostMaxSize). Mirrors
       engine.py set_content. */
    var styleMech = (styles[this.style] || {}).mechanics || {};
    var baseMech = (styles.balanced || {}).mechanics || {};
    var multNow = this._countMult(this.size);
    var multBase = this._countMult(this.baseSize);
    var grown = function (p, m) { return p ? p * m : p; };
    this.mechMults = {};
    var i;
    for (i = 0; i < AOE_ESCALATION_CAPS.length; i++) {
      this.mechMults[AOE_ESCALATION_CAPS[i]] =
        this._escalationMult(grown(styleMech.expected_aoe_targets, multNow))
        / this._escalationMult(grown(baseMech.expected_aoe_targets, multBase));
    }
    for (i = 0; i < RESILIENCE_CAPS.length; i++) {
      var eStyle = this._resilienceEff(grown(styleMech.focus_attackers, multNow));
      var eBalNow = this._resilienceEff(grown(baseMech.focus_attackers, multNow));
      var eBalBase = this._resilienceEff(grown(baseMech.focus_attackers, multBase));
      var styleFactor = eStyle / eBalNow;
      var sizeFactor = eBalNow / eBalBase;
      if (this.size > this.stBoostMaxSize && sizeFactor > 1.0) sizeFactor = 1.0;
      this.mechMults[RESILIENCE_CAPS[i]] = styleFactor * sizeFactor;
    }
    /* Scaled targets/soft caps, styled weights (mirrors engine.py). */
    this._targets = {}; this._softs = {}; this._weights = {};
    for (var cap2 in this.reqs) {
      var r = this.reqs[cap2];
      this._targets[cap2] = r.scales ? r.target * this.size / this.baseSize : r.target;
      this._softs[cap2] = r.scales ? r.soft_cap * this.size / this.baseSize : r.soft_cap;
      var m2 = this.styleMults[cap2];
      this._weights[cap2] = r.weight * (m2 === undefined ? 1.0 : m2);
    }
    /* Dedicated single-target VALUE devaluation by size (composition.yaml
       st_value_mult; a template opts out with st_full_value — roads).
       Mirrors engine.py set_content. */
    if (!this.template.st_full_value) {
      var stv = this._stValueMult(this.size);
      for (i = 0; i < RESILIENCE_CAPS.length; i++) {
        if (RESILIENCE_CAPS[i] in this._weights) this._weights[RESILIENCE_CAPS[i]] *= stv;
      }
    }
    /* Effective hard floors: an absolute floor never exceeds the SCALED
       target it guards (mirrors engine.py). */
    this._floorsEff = {};
    for (var fc in this.floors) {
      var fu = this.floors[fc].floor_units;
      var ft = this._targets[fc];
      this._floorsEff[fc] = (ft === undefined || ft > fu) ? fu : ft;
    }
    /* Synergy pairs ACTIVE in this template (mirrors engine.py). */
    this._activeSyn = [];
    for (i = 0; i < this.synergies.length; i++) {
      if (this.synergies[i][0] in this.reqs && this.synergies[i][1] in this.reqs)
        this._activeSyn.push(this.synergies[i]);
    }
    /* Viability layer for this content+size (mirrors engine.py). */
    var via = this.compCfg.viability || {};
    var excl = {};
    var rules = via.exclusions || [];
    for (i = 0; i < rules.length; i++) {
      var rule = rules[i];
      if (this.size < (rule.min_size || 0)) continue;
      var allowedList = (rule.allow || {})[this.content] || [];
      var allowed = {};
      for (var ai = 0; ai < allowedList.length; ai++) allowed[allowedList[ai]] = true;
      var rw = rule.weapons || [];
      for (var wi = 0; wi < rw.length; wi++) {
        if (!allowed[rw[wi]]) excl[rw[wi]] = true;
      }
    }
    this._excluded = excl;
    this._suggest = [];
    for (i = 0; i < this.pool.length; i++) {
      if (!excl[this.pool[i]]) this._suggest.push(this.pool[i]);
    }
    this._viability = {};
    if (this.size >= ((via.core_min_size === undefined) ? 10 : via.core_min_size)) {
      var bonus = (via.core_bonus === undefined) ? 1.0 : via.core_bonus;
      var coreList = (via.core || {}).large || [];
      for (i = 0; i < coreList.length; i++) this._viability[coreList[i]] = bonus;
    }
    /* Constraint band for this size (forge-only). */
    this._band = null;
    var bands = this.compCfg.constraint_bands || [];
    for (i = 0; i < bands.length; i++) {
      var row = bands[i];
      if ((row.min_size || 0) <= this.size &&
          this.size <= ((row.max_size === undefined) ? 1e9 : row.max_size)) {
        this._band = row;
        break;
      }
    }
    this._extrasCache = {};
    this._defaultCache = {};
  };

  CompEngine.prototype._stepTable = function (table, size) {
    /* Piecewise step lookup (mirrors engine.py _step_table). */
    if (!table.length) return 1.0;
    var v = table[0][1];
    for (var i = 0; i < table.length; i++) {
      if (table[i][0] <= size) v = table[i][1];
      else break;
    }
    return v;
  };

  CompEngine.prototype._countMult = function (size) {
    return this._stepTable(this.countMultTable, size);
  };

  CompEngine.prototype._stValueMult = function (size) {
    return this._stepTable(this.stValueTable, size);
  };

  CompEngine.prototype._tableLookup = function (table, x) {
    /* Clamped mechanics-table value for count x (half-UP rounding, mirrors
       engine.py _table_lookup / _half_up). */
    if (!table || !x) return null;
    var maxK = 0;
    for (var k in table) { var ki = parseInt(k, 10); if (ki > maxK) maxK = ki; }
    if (maxK === 0) return null;
    return table[String(Math.max(1, Math.min(Math.floor(x + 0.5), maxK)))];
  };

  CompEngine.prototype._escalationMult = function (targets) {
    var v = this._tableLookup((this.mechanics.aoe_escalation || {})
                              .damage_bonus_by_targets, targets);
    return v === null || v === undefined ? 1.0 : 1.0 + v;
  };

  CompEngine.prototype._resilienceEff = function (attackers) {
    var v = this._tableLookup((this.mechanics.focus_fire || {})
                              .damage_reduction_unmounted, attackers);
    return v === null || v === undefined ? 1.0 : 1.0 - v;
  };

  CompEngine.prototype.weight = function (cap) {
    return this._weights[cap];
  };

  CompEngine.prototype.extrapolated = function () {
    var v = this.template.validated_sizes || [this.baseSize];
    return v.indexOf(this.size) === -1;
  };

  CompEngine.prototype.sizeBucket = function () {
    /* Usage-DISPLAY bucket, participant axis = 2 x party size (mirrors
       engine.py size_bucket, corrected 2026-08-18). Display-only. */
    var n = 2 * this.size;
    return n < 12 ? "small" : n <= 30 ? "mid" : "large";
  };

  CompEngine.prototype.target = function (cap) {
    return this._targets[cap];
  };

  CompEngine.prototype.softCap = function (cap) {
    return this._softs[cap];
  };

  CompEngine.prototype.capsOf = function (weapon) {
    return this.weapons[weapon].capabilities;
  };

  CompEngine.prototype.statsOf = function (item) {
    return this.itemStats[item] || {};
  };

  CompEngine.prototype.roleOf = function (weapon) {
    /* Constraint role class: healer / frontline / support / dps. */
    return this.roleClass[weapon] === undefined ? "dps" : this.roleClass[weapon];
  };

  CompEngine.prototype.isExcluded = function (weapon) {
    /* Viability bar for GENERATED comps at this content+size — scoring is
       never blocked (mirrors engine.py is_excluded). */
    return !!this._excluded[weapon];
  };

  CompEngine.prototype.suggestPool = function () {
    return this._suggest;
  };

  /* ---- loadout / archetype model (mirrors engine.py): a party member is
     (weapon, combo) — one bundle per slot. The SAME machinery serves
     incumbents and candidates, so recommend() cannot disagree with
     compScore() about a member's loadout. */
  CompEngine.prototype._eff = function (caps) {
    var out = {}, m;
    for (var c in caps) { m = this.mechMults[c]; out[c] = caps[c] * (m === undefined ? 1.0 : m); }
    return out;
  };

  CompEngine.prototype._loadoutEff = function (weapon) {
    var lo = this.weapons[weapon].loadout;
    var hasSlots = lo && lo.slots && lo.slots.length;
    var hasAlways = lo && lo.always && Object.keys(lo.always).length;
    if (!lo || (!hasSlots && !hasAlways))
      return { always: this._eff(this.capsOf(weapon)), slots: [] };
    var self = this;
    return {
      always: this._eff(lo.always || {}),
      slots: (lo.slots || []).map(function (slot) {
        return slot.map(function (b) { return self._eff(b); });
      }),
    };
  };

  CompEngine.prototype._comboExtras = function (weapon) {
    /* Every one-spell-per-slot loadout as a merged effective-caps object,
       in itertools.product order (first slot slowest — mirrors engine.py
       _combo_extras; cached per setContent). */
    var extras = this._extrasCache[weapon];
    if (extras) return extras;
    var le = this._loadoutEff(weapon), always = le.always, slots = le.slots;
    var choices = slots.filter(function (slot) { return slot.length; });
    var combos = [[]], i, j, kk, next;
    for (i = 0; i < choices.length; i++) {
      next = [];
      for (j = 0; j < combos.length; j++)
        for (kk = 0; kk < choices[i].length; kk++)
          next.push(combos[j].concat([choices[i][kk]]));
      combos = next;
    }
    extras = [];
    for (i = 0; i < combos.length; i++) {
      var extra = {}, c0;
      for (c0 in always) extra[c0] = always[c0];
      var combo = combos[i];
      for (j = 0; j < combo.length; j++) {
        var bd = combo[j];
        for (var c in bd) extra[c] = (extra[c] || 0.0) + bd[c];
      }
      extras.push(extra);
    }
    this._extrasCache[weapon] = extras;
    return extras;
  };

  CompEngine.prototype._comboDims = function (weapon) {
    /* [[original slot index, option count], ...] for non-empty slots. */
    var lo = this.weapons[weapon].loadout || {};
    var slots = lo.slots || [];
    var dims = [];
    for (var oi = 0; oi < slots.length; oi++) {
      if (slots[oi] && slots[oi].length) dims.push([oi, slots[oi].length]);
    }
    return dims;
  };

  CompEngine.prototype.comboChoices = function (weapon, combo) {
    /* [(original slot index, bundle index)] for a combo index; out-of-range
       falls back to the default combo exactly like memberExtra (mirrors
       engine.py combo_choices, review 2026-08-18). */
    var dims = this._comboDims(weapon);
    var total = 1, i;
    for (i = 0; i < dims.length; i++) total *= dims[i][1];
    if (combo === null || combo === undefined || combo < 0 || combo >= total)
      combo = this.defaultCombo(weapon);
    var out = [], stride = total;
    for (i = 0; i < dims.length; i++) {
      stride = Math.floor(stride / dims[i][1]);
      out.push([dims[i][0], Math.floor(combo / stride) % dims[i][1]]);
    }
    return out;
  };

  CompEngine.prototype.comboFromPicks = function (weapon, picks) {
    /* Combo index for a member whose REAL spell picks are known (mirrors
       engine.py combo_from_picks): picks = {slot name: spell id}; slots
       without a curated pick keep the default combo's choice. */
    var lo = this.weapons[weapon].loadout || {};
    var names = lo.slot_names || [];
    var spells = lo.slot_spells || [];
    var dims = this._comboDims(weapon);
    var defChoices = this.comboChoices(weapon, this.defaultCombo(weapon));
    var def = {};
    for (var d = 0; d < defChoices.length; d++) def[defChoices[d][0]] = defChoices[d][1];
    var combo = 0;
    for (var i = 0; i < dims.length; i++) {
      var oi = dims[i][0], n = dims[i][1];
      var choice = def[oi] === undefined ? 0 : def[oi];
      var name = oi < names.length ? names[oi] : null;
      var pick = name !== null && picks ? picks[name] : undefined;
      if (pick !== undefined && pick !== null && oi < spells.length) {
        for (var j = 0; j < spells[oi].length; j++) {
          if (spells[oi][j] === pick) { choice = j; break; }
        }
      }
      combo = combo * n + choice;
    }
    return combo;
  };

  CompEngine.prototype.comboSpells = function (weapon, combo) {
    /* [[slot name, spell id], ...] the combo actually equips (mirrors
       engine.py combo_spells). */
    var lo = this.weapons[weapon].loadout || {};
    var names = lo.slot_names || [];
    var spells = lo.slot_spells || [];
    var out = [];
    var ch = this.comboChoices(weapon, combo);
    for (var i = 0; i < ch.length; i++) {
      var oi = ch[i][0], ci = ch[i][1];
      if (oi < names.length && oi < spells.length && ci < spells[oi].length)
        out.push([names[oi], spells[oi][ci]]);
    }
    return out;
  };

  CompEngine.prototype.defaultCombo = function (weapon) {
    /* Static loadout under the CURRENT template weights — argmax by
       (styled-weight value, unit count, first-in-order). Mirrors engine.py
       default_combo; cached per setContent. */
    var hit = this._defaultCache[weapon];
    if (hit !== undefined) return hit;
    var extras = this._comboExtras(weapon);
    var bestI = 0, bestVal = null, bestUnits = 0;
    for (var i = 0; i < extras.length; i++) {
      var val = 0.0, units = 0.0;
      for (var c in extras[i]) {
        val += (this._weights[c] || 0.0) * extras[i][c];
        units += extras[i][c];
      }
      if (bestVal === null || val > bestVal || (val === bestVal && units > bestUnits)) {
        bestI = i; bestVal = val; bestUnits = units;
      }
    }
    this._defaultCache[weapon] = bestI;
    return bestI;
  };

  CompEngine.prototype.memberExtra = function (weapon, combo) {
    /* One member's effective caps for a combo (null -> static default). */
    var extras = this._comboExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    return extras[combo];
  };

  /* ----------------------------------------------------------------- supply */
  CompEngine.prototype.supply = function (party) {
    /* Raw capability units summed over the party (sheet numbers) — display
       reference only. */
    var s = {};
    for (var i = 0; i < party.length; i++) {
      var caps = this.capsOf(party[i]);
      for (var cap in caps) s[cap] = (s[cap] || 0) + caps[cap];
    }
    return s;
  };

  CompEngine.prototype.effectiveSupply = function (party, combos) {
    /* Supply after physics AND the one-spell-per-slot rule; ALL scoring
       reads this (mirrors engine.py effective_supply). */
    var s = {}, c;
    for (var i = 0; i < party.length; i++) {
      var extra = this.memberExtra(party[i], combos ? combos[i] : null);
      for (c in extra) s[c] = (s[c] || 0.0) + extra[c];
    }
    return s;
  };

  /* ----------------------------------------------------------------- floors */
  CompEngine.prototype.floorArmed = function (cap, have) {
    /* THE below-the-(target-clamped)-hard-floor predicate (mirrors
       engine.py floor_armed). */
    var f = this.floors[cap];
    return !!f && this.size >= f.min_party_size && have < this._floorsEff[cap];
  };

  CompEngine.prototype._floorPenalty = function (cap, have) {
    if (!this.floorArmed(cap, have)) return 0.0;
    var f = this.floors[cap];
    var fu = this._floorsEff[cap];
    var w = this.reqs[cap].weight;
    return f.penalty_mult * w * (fu - have) / fu;
  };

  CompEngine.prototype._overstack = function (cap, have, target, soft) {
    /* Saturating over-stack penalty on the BASE weight (mirrors engine.py). */
    if (have <= soft) return 0.0;
    var scale = soft > 0 ? soft : target;
    var x = (have - soft) / scale;
    return this.overstackMax * this.reqs[cap].weight * x / (1.0 + x);
  };

  CompEngine.prototype._headroomBonus = function (cap, have, target, soft) {
    /* Small linear bonus for supply in the target..soft band, capped at
       headroom * weight (mirrors engine.py _headroom_bonus). */
    if (this.headroom <= 0.0 || soft <= target || have <= target) return 0.0;
    var extra = have - target;
    var span = soft - target;
    if (extra > span) extra = span;
    return this.headroom * this.weight(cap) * extra / span;
  };

  CompEngine.prototype._coverTerms = function (cap, have, gain, target) {
    /* [coverage delta (incl. headroom), floor-lift delta] — two terms so
       callers accumulate in their original order (mirrors engine.py). */
    var soft = this.softCap(cap);
    var cov = this.weight(cap) * (Math.pow(Math.min(1.0, (have + gain) / target), this.gamma)
                                  - Math.pow(Math.min(1.0, have / target), this.gamma));
    cov += (this._headroomBonus(cap, have + gain, target, soft)
            - this._headroomBonus(cap, have, target, soft));
    return [cov, this._floorPenalty(cap, have) - this._floorPenalty(cap, have + gain)];
  };

  /* ---------------------------------------------------------------- fitness */
  CompEngine.prototype.fitness = function (party, combos) {
    var s = this.effectiveSupply(party, combos), total = 0.0;
    for (var cap in this.reqs) {
      var have = s[cap] || 0.0, target = this.target(cap), soft = this.softCap(cap);
      total += this.weight(cap) * Math.pow(Math.min(1.0, have / target), this.gamma);
      total += this._headroomBonus(cap, have, target, soft);
      total -= this._overstack(cap, have, target, soft);
      total -= this._floorPenalty(cap, have);
    }
    return total;
  };

  CompEngine.prototype.maxFitness = function () {
    /* Supremum of fitness(): full coverage + the headroom band maxed
       (mirrors engine.py max_fitness, review 2026-08-18). */
    var t = 0;
    for (var cap in this.reqs) t += this.weight(cap);
    return t * (1.0 + this.headroom);
  };

  /* ---------------------------------------------------------------- synergy */
  CompEngine.prototype._synSide = function (cap, amount) {
    if (!(cap in this.reqs)) return amount;
    return Math.min(amount, this.target(cap));
  };

  CompEngine.prototype._pairValue = function (p, sA, sB, j) {
    /* bonus * max(0, min(capped sides) - J) — the 'across players' rule
       (mirrors engine.py _pair_value). */
    var pair = this._activeSyn[p];
    var v = Math.min(this._synSide(pair[0], sA), this._synSide(pair[1], sB)) - j;
    return v > 0 ? pair[2] * v : 0.0;
  };

  CompEngine.prototype._synState = function (party, combos) {
    /* [effective supply, per-active-pair J] (mirrors engine.py _syn_state). */
    var s = this.effectiveSupply(party, combos);
    var J = [];
    var p;
    for (p = 0; p < this._activeSyn.length; p++) J.push(0.0);
    for (var i = 0; i < party.length; i++) {
      var extra = this.memberExtra(party[i], combos ? combos[i] : null);
      for (p = 0; p < this._activeSyn.length; p++) {
        var j = Math.min(extra[this._activeSyn[p][0]] || 0.0,
                         extra[this._activeSyn[p][1]] || 0.0);
        if (j > J[p]) J[p] = j;
      }
    }
    return [s, J];
  };

  CompEngine.prototype.synergy = function (party, combos) {
    var st = this._synState(party, combos), s = st[0], J = st[1];
    var total = 0.0;
    for (var p = 0; p < this._activeSyn.length; p++) {
      total += this._pairValue(p, s[this._activeSyn[p][0]] || 0.0,
                               s[this._activeSyn[p][1]] || 0.0, J[p]);
    }
    return total;
  };

  /* ------------------------------------------------------------- redundancy */
  CompEngine.prototype._dupFree = function (weapon) {
    /* Per-weapon allowances are LARGE-group evidence — size-gated (mirrors
       engine.py _dup_free, review 2026-08-18). */
    var pw = this.dupPerWeapon[weapon];
    if (pw && pw.free !== undefined && this.size >= this.dupPwMinSize) return pw.free;
    return this.dupFreeDefault;
  };

  CompEngine.prototype._dupGenMax = function (weapon) {
    /* Hard cap on copies the FORGE may generate (never a scoring bar). */
    var pw = this.dupPerWeapon[weapon];
    if (pw && pw.max !== undefined && this.size >= this.dupPwMinSize) return pw.max;
    return this.size < 10 ? this.dupMaxSmall : this.dupMaxLarge;
  };

  CompEngine.prototype.redundancy = function (party) {
    /* Extra-copy units, marginal GROWS per copy (mirrors engine.py). */
    var counts = {}, total = 0.0;
    for (var i = 0; i < party.length; i++) {
      var w = party[i];
      var c = (counts[w] || 0) + 1;
      counts[w] = c;
      var free = this._dupFree(w);
      if (c > free) total += c - free;
    }
    return total;
  };

  /* ----------------------------------------------------------------- priors */
  CompEngine.prototype.metaOf = function (w) {
    if (!this.metaBucketed) return this.metaPrior[w] || 0.0;
    return (this.metaPrior[this.sizeBucket()] || {})[w] || 0.0;
  };

  CompEngine.prototype.viabilityOf = function (w) {
    return this._viability[w] || 0.0;
  };

  /* ---------------------------------------------------- comp-level score */
  CompEngine.prototype.compScore = function (party, combos) {
    /* THE party-level objective (mirrors engine.py comp_score). */
    var meta = 0.0, viab = 0.0;
    for (var i = 0; i < party.length; i++) {
      meta += this.metaOf(party[i]);
      viab += this.viabilityOf(party[i]);
    }
    return this.alpha * this.fitness(party, combos)
         + this.beta * this.synergy(party, combos)
         + this.delta * meta
         + this.viabilityW * viab
         - this.rho * this.redundancy(party);
  };

  /* ------------------------------------------------ candidate evaluation */
  CompEngine.prototype.partyState = function (party, combos) {
    /* Everything a candidate marginal needs (mirrors engine.py). */
    var st = this._synState(party, combos), s = st[0], J = st[1];
    var pairVals = [];
    for (var p = 0; p < this._activeSyn.length; p++) {
      pairVals.push(this._pairValue(p, s[this._activeSyn[p][0]] || 0.0,
                                    s[this._activeSyn[p][1]] || 0.0, J[p]));
    }
    var counts = {};
    for (var i = 0; i < party.length; i++) {
      counts[party[i]] = (counts[party[i]] || 0) + 1;
    }
    return { s: s, J: J, pairVals: pairVals, counts: counts };
  };

  CompEngine.prototype._margFitFrom = function (s, extra) {
    var total = 0.0;
    for (var cap in extra) {
      var gain = extra[cap];
      if (!(cap in this.reqs) || !gain) continue;
      var have = s[cap] || 0.0, target = this.target(cap), soft = this.softCap(cap);
      var ct = this._coverTerms(cap, have, gain, target);
      total += ct[0];
      total += ct[1];
      total -= (this._overstack(cap, have + gain, target, soft)
                - this._overstack(cap, have, target, soft));
    }
    return total;
  };

  CompEngine.prototype._margSynFrom = function (state, extra) {
    var total = 0.0;
    for (var p = 0; p < this._activeSyn.length; p++) {
      var a = this._activeSyn[p][0], b = this._activeSyn[p][1];
      var j = Math.min(extra[a] || 0.0, extra[b] || 0.0);
      var j2 = state.J[p] > j ? state.J[p] : j;
      total += this._pairValue(p, (state.s[a] || 0.0) + (extra[a] || 0.0),
                               (state.s[b] || 0.0) + (extra[b] || 0.0), j2)
             - state.pairVals[p];
    }
    return total;
  };

  CompEngine.prototype._evalPick = function (state, weapon) {
    /* THE candidate score — the exact compScore delta of adding `weapon`
       with its best loadout (mirrors engine.py _eval_pick). Returns
       {score, dFit, dSyn, meta, combo}. */
    var best = null;
    var extras = this._comboExtras(weapon);
    for (var i = 0; i < extras.length; i++) {
      var dFit = this._margFitFrom(state.s, extras[i]);
      var dSyn = this._margSynFrom(state, extras[i]);
      var val = this.alpha * dFit + this.beta * dSyn;
      if (best === null || val > best.val)
        best = { val: val, dFit: dFit, dSyn: dSyn, combo: i };
    }
    if (best === null) best = { val: 0.0, dFit: 0.0, dSyn: 0.0, combo: null };
    var meta = this.metaOf(weapon);
    var dup = (state.counts[weapon] || 0) + 1 - this._dupFree(weapon);
    var score = best.val + this.delta * meta
              + this.viabilityW * this.viabilityOf(weapon)
              - (dup > 0 ? this.rho * dup : 0.0);
    return { score: score, dFit: best.dFit, dSyn: best.dSyn, meta: meta, combo: best.combo };
  };

  CompEngine.prototype.bestLoadout = function (s, baseSyn, weapon) {
    /* Legacy shim (mirrors engine.py best_loadout): candidate loadout vs
       bare supply with J=0 — exact for an empty party. */
    var state = { s: s, J: [], pairVals: [], counts: {} };
    var p;
    for (p = 0; p < this._activeSyn.length; p++) {
      state.J.push(0.0);
      state.pairVals.push(this._pairValue(p, s[this._activeSyn[p][0]] || 0.0,
                                          s[this._activeSyn[p][1]] || 0.0, 0.0));
    }
    var best = null;
    var extras = this._comboExtras(weapon);
    for (var i = 0; i < extras.length; i++) {
      var dFit = this._margFitFrom(s, extras[i]);
      var dSyn = this._margSynFrom(state, extras[i]);
      var val = this.alpha * dFit + this.beta * dSyn;
      if (best === null || val > best.val)
        best = { val: val, dFit: dFit, dSyn: dSyn, extra: extras[i] };
    }
    return best === null ? { dFit: 0.0, dSyn: 0.0, extra: {} } : best;
  };

  CompEngine.prototype.explain = function (party, candidate, combos) {
    /* Per-capability delta terms for the candidate's CHOSEN loadout —
       matches what _evalPick scored (mirrors engine.py explain). */
    var state = this.partyState(party, combos);
    var pick = this._evalPick(state, candidate);
    var extra = this.memberExtra(candidate, pick.combo);
    var s = state.s, terms = [];
    for (var cap in extra) {
      var gain = extra[cap];
      if (!(cap in this.reqs) || !gain) continue;
      var have = s[cap] || 0.0, target = this.target(cap);
      var ct = this._coverTerms(cap, have, gain, target);
      var d = ct[0] + ct[1];
      if (d > 0.05) {
        terms.push({ delta: Math.round(d * 100) / 100, cap: cap,
                     before: have, after: have + gain, target: target });
      }
    }
    return terms.sort(function (x, y) { return y.delta - x.delta; });
  };

  CompEngine.prototype._pool = function (pool) {
    /* mirrors Python's `pool or self.suggest_pool()`: default excludes both
       game-retired weapons and the viability exclusions for this context. */
    if (pool && pool.length) return pool;
    return this._suggest;
  };

  CompEngine.prototype.recommend = function (party, topN, pool, combos) {
    if (topN === undefined) topN = 4;
    var state = this.partyState(party, combos);
    var out = [];
    var keys = this._pool(pool);
    for (var i = 0; i < keys.length; i++) {
      var w = keys[i];
      var ps = this._evalPick(state, w);
      out.push({
        weapon: w,
        display_name: this.weapons[w].display_name,
        status: this.weapons[w].status,
        d_fitness: ps.dFit, d_synergy: ps.dSyn, meta_prior: ps.meta,
        viability: this.viabilityOf(w),
        combo: ps.combo,
        score: ps.score,
      });
    }
    return out.sort(function (x, y) { return y.score - x.score; }).slice(0, topN);
  };

  CompEngine.prototype.swapReview = function (party, topN, pool, combos) {
    /* Per-member swap advisor (mirrors engine.py swap_review): each member
       valued exactly as _evalPick would value it into the REST of the
       party. `off_comp` flags viability-excluded members. */
    if (topN === undefined) topN = 3;
    var out = [];
    for (var i = 0; i < party.length; i++) {
      var cur = party[i];
      var rest = party.slice(0, i).concat(party.slice(i + 1));
      var restCombos = combos
        ? combos.slice(0, i).concat(combos.slice(i + 1)) : null;
      var state = this.partyState(rest, restCombos);
      var self = this;
      var curScore = this._evalPick(state, cur).score;
      var better = [];
      var keys = this._pool(pool);
      for (var j = 0; j < keys.length; j++) {
        var w = keys[j];
        if (w === cur) continue;
        var v = this._evalPick(state, w).score;
        if (v > curScore) better.push([v, w]);
      }
      better.sort(function (a, b) {
        if (a[0] !== b[0]) return b[0] - a[0];
        return a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0;
      });
      out.push({
        index: i, weapon: cur,
        display_name: this.weapons[cur].display_name,
        /* rank = strictly-better alternatives + 1 (ties never demote) */
        score: curScore, rank: better.length + 1,
        off_comp: this.isExcluded(cur),
        options: better.slice(0, topN).map(function (t) {
          return { weapon: t[1],
                   display_name: self.weapons[t[1]].display_name,
                   score: t[0], gain: t[0] - curScore };
        }),
      });
    }
    return out;
  };

  CompEngine.prototype.weaknesses = function (party, topN, combos) {
    if (topN === undefined) topN = 3;
    var s = this.effectiveSupply(party, combos), gaps = [];
    for (var cap in this.reqs) {
      var have = s[cap] || 0;
      gaps.push({ cap: cap,
                  gap: this.weight(cap) * (1 - Math.pow(Math.min(1.0, have / this.target(cap)), this.gamma)),
                  have: have, target: this.target(cap) });
    }
    return gaps.sort(function (x, y) { return y.gap - x.gap; }).slice(0, topN);
  };

  CompEngine.prototype.uncoveredCaps = function (party, combos) {
    var s = this.effectiveSupply(party, combos), out = [];
    for (var cap in this.reqs) {
      if (this.weight(cap) >= 5 && (s[cap] || 0) / this.target(cap) < 0.5) out.push(cap);
    }
    return out;
  };

  /* ------------------------------------------------------------ local search */
  CompEngine.prototype.refine = function (party, maxPasses, pool, fixed) {
    /* Steepest-descent 1-opt over compScore, UNCONSTRAINED (mirrors
       engine.py refine; the forge runs its own constraint-aware pass). */
    party = party.slice();
    fixed = fixed || 0;
    if (!party.length) return party;
    var candidates;
    /* empty array falls back to the full pool like Python's `pool or
       self.pool` — [] is truthy in JS (review 2026-08-18) */
    if (pool && pool.length) { candidates = pool.slice(); }
    else { candidates = this.pool.slice(); }
    if (maxPasses === undefined || maxPasses === null) maxPasses = 8;
    var best = this.compScore(party);
    for (var pass = 0; pass < maxPasses; pass++) {
      var moveIdx = -1, moveW = null, gain = 1e-9;   /* strictly-positive */
      for (var i = fixed; i < party.length; i++) {
        var orig = party[i];
        for (var j = 0; j < candidates.length; j++) {
          if (candidates[j] === orig) continue;
          party[i] = candidates[j];
          var d = this.compScore(party) - best;
          if (d > gain) { moveIdx = i; moveW = candidates[j]; gain = d; }
        }
        party[i] = orig;
      }
      if (moveIdx < 0) break;
      party[moveIdx] = moveW;
      best += gain;
    }
    return party;
  };

  /* ------------------------------------------------------------------ forge */
  CompEngine.prototype._forgeCtx = function (pool) {
    /* Static per-forge context (mirrors engine.py _forge_ctx). */
    var band = this._band || {};
    var roleMin = {}, roleMax = {}, predMin = {};
    for (var key in band) {
      if (key === "min_size" || key === "max_size") continue;
      var rule = band[key];
      if (typeof rule !== "object" || rule === null) continue;
      if (key in this.predMembers) {
        if (rule.min !== undefined) predMin[key] = rule.min;
        continue;
      }
      if (rule.min !== undefined) roleMin[key] = rule.min;
      if (rule.max !== undefined) roleMax[key] = rule.max;
    }
    return { pool: pool, roleMin: roleMin, roleMax: roleMax, predMin: predMin };
  };

  CompEngine.prototype._forgeCounts = function (party) {
    /* [weapon counts, role counts, predicate counts, group counts]. */
    var counts = {}, roles = {}, preds = {}, groups = {};
    for (var i = 0; i < party.length; i++) {
      var w = party[i];
      counts[w] = (counts[w] || 0) + 1;
      var r = this.roleOf(w);
      roles[r] = (roles[r] || 0) + 1;
      for (var pn in this.predMembers) {
        if (this.predMembers[pn][w]) preds[pn] = (preds[pn] || 0) + 1;
      }
      var gs = this.groupsOf[w] || [];
      for (var g = 0; g < gs.length; g++) groups[gs[g]] = (groups[gs[g]] || 0) + 1;
    }
    return [counts, roles, preds, groups];
  };

  CompEngine.prototype._forgeFeasible = function (ctx, counts, roles, preds, groups, w, slotsLeftAfter) {
    /* May the forge add `w` here and still complete a legal roster?
       (mirrors engine.py _forge_feasible) */
    if ((counts[w] || 0) >= this._dupGenMax(w)) return false;
    var gs = this.groupsOf[w] || [];
    for (var g = 0; g < gs.length; g++) {
      var gmax = this.groups[gs[g]].max;
      if ((groups[gs[g]] || 0) >= (gmax === undefined ? 1e9 : gmax)) return false;
    }
    var r = this.roleOf(w);
    var mx = ctx.roleMax[r];
    if (mx !== undefined && (roles[r] || 0) >= mx) return false;
    var need = 0;
    for (var r2 in ctx.roleMin) {
      var have = (roles[r2] || 0) + (r2 === r ? 1 : 0);
      if (ctx.roleMin[r2] > have) need += ctx.roleMin[r2] - have;
    }
    for (var pn in ctx.predMin) {
      var haveP = (preds[pn] || 0) + (this.predMembers[pn][w] ? 1 : 0);
      if (ctx.predMin[pn] > haveP) need += ctx.predMin[pn] - haveP;
    }
    return need <= slotsLeftAfter;
  };

  CompEngine.prototype._memberTag = function (w, combo) {
    return w + "#" + (combo === null || combo === undefined ? "d" : String(combo));
  };

  CompEngine.prototype._insertSorted = function (items, item) {
    /* New array with `item` at its sorted position — the incremental
       canonical-multiset key (mirrors engine.py _insert_sorted). */
    var out = items.slice();
    var lo = 0, hi = out.length;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (out[mid] < item) lo = mid + 1;
      else hi = mid;
    }
    out.splice(lo, 0, item);
    return out;
  };

  CompEngine.prototype.forge = function (size, locked, lockedCombos, pool, beamWidth) {
    /* Deterministic constrained beam search over complete rosters + 1-opt
       and bounded 2-opt refinement + filler audit (mirrors engine.py forge
       — see its docstring for the contract; returns {party, combos, score,
       feasible, filler, held, locked}). */
    locked = (locked || []).slice();
    /* normalize lockedCombos to EXACTLY locked.length: missing/short/empty
       pads with null, extras drop — mirrors engine.py (review 2026-08-18;
       an empty array used to mis-pair combos with members here). */
    var lc = lockedCombos || [];
    var combos = [];
    for (var ci = 0; ci < locked.length; ci++)
      combos.push(ci < lc.length ? lc[ci] : null);
    var candPool = pool !== undefined && pool !== null ? pool.slice() : this.suggestPool().slice();
    var ctx = this._forgeCtx(candPool);
    if (beamWidth === undefined || beamWidth === null) beamWidth = 8;
    var feasible = true;

    var fc = this._forgeCounts(locked);
    var items0 = [];
    for (var li = 0; li < locked.length; li++)
      items0.push(this._memberTag(locked[li], combos[li]));
    items0.sort();
    var beams = [{ party: locked, combos: combos,
                   counts: fc[0], roles: fc[1], preds: fc[2], groups: fc[3],
                   state: this.partyState(locked, combos), items: items0,
                   score: this.compScore(locked, combos) }];
    for (var depth = locked.length; depth < size; depth++) {
      var slotsLeftAfter = size - depth - 1;
      var expansions = [];
      for (var bi = 0; bi < beams.length; bi++) {
        var beam = beams[bi];
        for (var wi = 0; wi < candPool.length; wi++) {
          var w = candPool[wi];
          if (!this._forgeFeasible(ctx, beam.counts, beam.roles, beam.preds,
                                   beam.groups, w, slotsLeftAfter)) continue;
          var pick = this._evalPick(beam.state, w);
          expansions.push([beam.score + pick.score, bi, w, pick.combo]);
        }
      }
      if (!expansions.length) { feasible = false; break; }
      /* stable sort by score only: equal scores keep (beam, pool) append
         order — deterministic in both engines. The canonical multiset key
         is computed LAZILY, only for candidates actually considered for
         the beam (mirrors engine.py). */
      expansions.sort(function (a, b) { return b[0] - a[0]; });
      var nextBeams = [], seen = {};
      for (var xi = 0; xi < expansions.length; xi++) {
        var ex = expansions[xi];
        var src = beams[ex[1]];
        var items = this._insertSorted(src.items, this._memberTag(ex[2], ex[3]));
        var key = items.join("|");
        if (seen[key]) continue;
        seen[key] = true;
        var party2 = src.party.concat([ex[2]]);
        var combos2 = src.combos.concat([ex[3]]);
        var fc2 = this._forgeCounts(party2);
        nextBeams.push({ party: party2, combos: combos2,
                         counts: fc2[0], roles: fc2[1], preds: fc2[2], groups: fc2[3],
                         state: this.partyState(party2, combos2), items: items,
                         score: this.compScore(party2, combos2) });
        if (nextBeams.length >= beamWidth) break;
      }
      beams = nextBeams;
    }
    var best = beams[0];
    var party = best.party, combosOut = best.combos;
    var fixed = locked.length;
    if (party.length > fixed) {
      /* refine -> pair-trade -> refine (mirrors engine.py forge) */
      var rc = this._refineConstrained(ctx, party, combosOut, fixed);
      rc = this._twoOpt(ctx, rc[0], rc[1], fixed);
      rc = this._refineConstrained(ctx, rc[0], rc[1], fixed);
      party = rc[0]; combosOut = rc[1];
    }
    /* filler audit (mirrors engine.py): negative slots split into `held`
       (mandated by a minimum constraint) and `filler` (must not survive). */
    var filler = [], held = [];
    var base = this.compScore(party, combosOut);
    for (var i2 = fixed; i2 < party.length; i2++) {
      var sub = party.slice(0, i2).concat(party.slice(i2 + 1));
      var subC = combosOut.slice(0, i2).concat(combosOut.slice(i2 + 1));
      if (base - this.compScore(sub, subC) >= -1e-9) continue;
      var fcs = this._forgeCounts(sub);
      var needed = false;
      for (var rr in ctx.roleMin) {
        if ((fcs[1][rr] || 0) < ctx.roleMin[rr]) { needed = true; break; }
      }
      if (!needed) {
        for (var pn2 in ctx.predMin) {
          if ((fcs[2][pn2] || 0) < ctx.predMin[pn2]) { needed = true; break; }
        }
      }
      (needed ? held : filler).push(i2);
    }
    return { party: party, combos: combosOut, score: base,
             feasible: feasible, filler: filler, held: held, locked: fixed };
  };

  CompEngine.prototype._swapOk = function (ctx, counts, roles, preds, groups, orig, w) {
    /* Constraint check for replacing member `orig` with `w`, against the
       CURRENT roster's precomputed counts — O(1) deltas (mirrors engine.py
       _swap_ok; a full count rebuild per candidate dominated size 60). */
    if ((counts[w] || 0) + 1 > this._dupGenMax(w)) return false;
    var gw = this.groupsOf[w] || [];
    if (gw.length) {
      var go = this.groupsOf[orig] || [];
      for (var g = 0; g < gw.length; g++) {
        var after = (groups[gw[g]] || 0) + 1 - (go.indexOf(gw[g]) >= 0 ? 1 : 0);
        var gmax = this.groups[gw[g]].max;
        if (after > (gmax === undefined ? 1e9 : gmax)) return false;
      }
    }
    var ro = this.roleOf(orig), rw = this.roleOf(w);
    if (rw !== ro) {
      var mx = ctx.roleMax[rw];
      if (mx !== undefined && (roles[rw] || 0) + 1 > mx) return false;
      var mn = ctx.roleMin[ro];
      if (mn !== undefined && (roles[ro] || 0) - 1 < mn) return false;
    }
    for (var pn in ctx.predMin) {
      var members = this.predMembers[pn];
      var d = (members[w] ? 1 : 0) - (members[orig] ? 1 : 0);
      if ((preds[pn] || 0) + d < ctx.predMin[pn]) return false;
    }
    return true;
  };

  CompEngine.prototype._refineConstrained = function (ctx, party, combos, fixed, maxPasses) {
    /* Steepest-descent 1-opt over generated slots, constraint-aware
       (mirrors engine.py _refine_constrained). */
    party = party.slice(); combos = combos.slice();
    if (maxPasses === undefined) maxPasses = 8;
    var best = this.compScore(party, combos);
    for (var pass = 0; pass < maxPasses; pass++) {
      var fc = this._forgeCounts(party);
      var counts = fc[0], roles = fc[1], preds = fc[2], groups = fc[3];
      var move = null, gain = 1e-9;
      for (var i = fixed; i < party.length; i++) {
        var rest = party.slice(0, i).concat(party.slice(i + 1));
        var restC = combos.slice(0, i).concat(combos.slice(i + 1));
        var state = this.partyState(rest, restC);
        var baseRest = this.compScore(rest, restC);
        var contrib = best - baseRest;
        var orig = party[i];
        for (var j = 0; j < ctx.pool.length; j++) {
          var w = ctx.pool[j];
          if (w === orig) continue;
          if (!this._swapOk(ctx, counts, roles, preds, groups, orig, w)) continue;
          var pick = this._evalPick(state, w);
          var d = pick.score - contrib;
          if (d > gain) { move = [i, w, pick.combo]; gain = d; }
        }
      }
      if (move === null) break;
      party[move[0]] = move[1];
      combos[move[0]] = move[2];
      best = this.compScore(party, combos);
    }
    return [party, combos];
  };

  CompEngine.prototype._twoOpt = function (ctx, party, combos, fixed, worstK, candM) {
    /* Bounded 2-opt over the weakest generated slots (mirrors engine.py
       _two_opt). An accepted pair-move reorders the roster, so the pass
       restarts with freshly computed weakest slots (review 2026-08-18). */
    party = party.slice(); combos = combos.slice();
    if (worstK === undefined) worstK = 4;
    if (candM === undefined) candM = 12;
    var best = this.compScore(party, combos);
    if (party.length - fixed < 2) return [party, combos];
    var improved = true, passes = 0;
    while (improved && passes < 3) {
      improved = false;
      passes += 1;
      var contribs = [];
      for (var gi = fixed; gi < party.length; gi++) {
        var sub = party.slice(0, gi).concat(party.slice(gi + 1));
        var subC = combos.slice(0, gi).concat(combos.slice(gi + 1));
        contribs.push([best - this.compScore(sub, subC), gi]);
      }
      contribs.sort(function (a, b) {
        if (a[0] !== b[0]) return a[0] - b[0];
        return a[1] - b[1];
      });
      var worst = [];
      for (var wi = 0; wi < Math.min(worstK, contribs.length); wi++) worst.push(contribs[wi][1]);
      for (var x = 0; x < worst.length && !improved; x++) {
        for (var y = x + 1; y < worst.length && !improved; y++) {
          var i = worst[x], j = worst[y];
          if (j < i) { var tswap = i; i = j; j = tswap; }
          var rest = party.slice(0, i).concat(party.slice(i + 1, j)).concat(party.slice(j + 1));
          var restC = combos.slice(0, i).concat(combos.slice(i + 1, j)).concat(combos.slice(j + 1));
          var state = this.partyState(rest, restC);
          var ranked = [];
          for (var pi = 0; pi < ctx.pool.length; pi++) {
            var pw = ctx.pool[pi];
            var pk = this._evalPick(state, pw);
            ranked.push([pk.score, pw, pk.combo]);
          }
          ranked.sort(function (a, b) {
            if (a[0] !== b[0]) return b[0] - a[0];
            return a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0;
          });
          var shortlist = ranked.slice(0, candM);
          for (var sa = 0; sa < shortlist.length && !improved; sa++) {
            var wa = shortlist[sa][1], ca = shortlist[sa][2];
            var pa = rest.concat([wa]);
            var pca = restC.concat([ca]);
            var state2 = this.partyState(pa, pca);
            for (var sb = 0; sb < shortlist.length; sb++) {
              var wb = shortlist[sb][1];
              var pkb = this._evalPick(state2, wb);
              var candParty = pa.concat([wb]);
              var candCombos = pca.concat([pkb.combo]);
              var fc = this._forgeCounts(candParty);
              var counts = fc[0], roles = fc[1], preds = fc[2], groups = fc[3];
              var ok = true;
              for (var cw in counts) {
                if (counts[cw] > this._dupGenMax(cw)) { ok = false; break; }
              }
              if (ok) {
                for (var g2 = 0; g2 < this.groups.length; g2++) {
                  var gmax2 = this.groups[g2].max;
                  if ((groups[g2] || 0) > (gmax2 === undefined ? 1e9 : gmax2)) { ok = false; break; }
                }
              }
              if (ok) {
                for (var rmx in ctx.roleMax) {
                  if ((roles[rmx] || 0) > ctx.roleMax[rmx]) { ok = false; break; }
                }
              }
              if (ok) {
                for (var rmn in ctx.roleMin) {
                  if ((roles[rmn] || 0) < ctx.roleMin[rmn]) { ok = false; break; }
                }
              }
              if (ok) {
                for (var pmn in ctx.predMin) {
                  if ((preds[pmn] || 0) < ctx.predMin[pmn]) { ok = false; break; }
                }
              }
              if (!ok) continue;
              var d2 = this.compScore(candParty, candCombos) - best;
              if (d2 > 1e-9) {
                party = candParty;
                combos = candCombos;
                best = best + d2;
                improved = true;
                break;
              }
            }
          }
        }
      }
    }
    return [party, combos];
  };

  if (typeof module !== "undefined" && module.exports) module.exports = CompEngine;
  else root.CompEngine = CompEngine;
})(typeof self !== "undefined" ? self : this);
