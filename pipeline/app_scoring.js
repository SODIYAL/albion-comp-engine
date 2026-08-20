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
    /* 1-7 scale: score_unit converts sheet points to supply units
       (mirrors engine.py; older 0-3 datasets divide by 1). */
    this.scoreUnit = this.scoring.score_unit || 1.0;
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
    /* Gear capability sheets — full-build members (mirrors engine.py). */
    this.gear = data.gear || {};
    /* PvP interaction records (build_interactions.py), spell-keyed. Scoring
       coupling: VERIFIED records' nonstacking_caps — party supply counts
       those caps once across members equipping the same spell. unknown/
       likely never scores. Mirrors engine.py __init__. */
    this.interactions = data.interactions || {};
    this.nonstack = {};
    var nsIds = Object.keys(this.interactions).sort();
    for (var ni = 0; ni < nsIds.length; ni++) {
      var nrec = this.interactions[nsIds[ni]];
      if (nrec.confidence === "verified" && nrec.nonstacking_caps &&
          nrec.nonstacking_caps.length) {
        this.nonstack[nsIds[ni]] = nrec.nonstacking_caps.slice();
      }
    }
    this.hasNonstack = Object.keys(this.nonstack).length > 0;
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
    /* Capability predicates — COMBO-AWARE since 2026-08-19 (mirrors
       engine.py): predMembers keeps the flat could-qualify view; every
       forge constraint counts through _predContrib(weapon, combo). */
    this.predDefs = comp.predicates || {};
    this.predMembers = {};
    for (var pn in this.predDefs) {
      var mins = this.predDefs[pn], members = {};
      for (k in this.weapons) {
        var okp = true;
        for (var pc in mins) {
          if ((this.weapons[k].capabilities[pc] || 0) < mins[pc]) { okp = false; break; }
        }
        if (okp) members[k] = true;
      }
      this.predMembers[pn] = members;
    }
    this._predCache = {};
    this._predPossibleCache = {};
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
    /* Clump anchors + AoE geometry config (2026-08-20, mirrors engine.py
       set_content — the geometric utility transform). */
    this._clumpNow = grown(styleMech.expected_aoe_targets, multNow);
    this._clumpBase = grown(baseMech.expected_aoe_targets, multBase);
    var geo = this.mechanics.aoe_geometry || {};
    this._geoCaps = {};
    this._geoCcCaps = {};
    var gl = geo.geometric_caps || [];
    for (var gi = 0; gi < gl.length; gi++) this._geoCaps[gl[gi]] = true;
    gl = geo.cc_duration_caps || [];
    for (gi = 0; gi < gl.length; gi++) this._geoCcCaps[gl[gi]] = true;
    this._geoCapTargets = (geo.escalation_cap_targets === undefined)
      ? 8 : geo.escalation_cap_targets;
    this._geoRef = (geo.reference_clump === undefined) ? null : geo.reference_clump;
    this._radiusTargetsTable = [];
    var rtSrc = geo.radius_targets || {};
    for (var rk in rtSrc) this._radiusTargetsTable.push([parseFloat(rk), rtSrc[rk]]);
    this._radiusTargetsTable.sort(function (a, b) { return a[0] - b[0]; });
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
    this._gearCache = {};
    this._defaultCache = {};
    this._nsCache = {};
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
  CompEngine.prototype._radiusTargets = function (radius) {
    /* Expected targets AFFECTED by an area of `radius` sweeping the clump
       (mirrors engine.py _radius_targets — mechanics.yaml step table). */
    if (!this._radiusTargetsTable.length) return 1.0;
    var v = this._radiusTargetsTable[0][1];
    for (var i = 0; i < this._radiusTargetsTable.length; i++) {
      if (this._radiusTargetsTable[i][0] <= radius) v = this._radiusTargetsTable[i][1];
      else break;
    }
    return v;
  };

  CompEngine.prototype._geoMult = function (cap, dent) {
    /* GEOMETRIC multiplier for AoE-delivered utility supply (mirrors
       engine.py _geo_mult exactly — same operation order for parity). */
    if (!dent || !this._clumpNow || !this._clumpBase) return 1.0;
    var r = dent.radius;
    if (r === undefined || r === null) return 1.0;
    var reach = this._radiusTargets(r);
    var mt = dent.max_targets;
    if (mt && mt < reach) reach = mt;
    var tNow = this._clumpNow < reach ? this._clumpNow : reach;
    var anchor = this._geoRef ? this._geoRef : this._clumpBase;
    var tBase = anchor < reach ? anchor : reach;
    if (tBase <= 0) return 1.0;
    var m = tNow / tBase;
    var f = (dent.escalation || {}).duration;
    if (f && this._geoCcCaps[cap]) {
      var cap8 = this._geoCapTargets;
      var eNow = 1.0 + f * ((tNow < cap8 ? tNow : cap8) - 1.0);
      var eBase = 1.0 + f * ((tBase < cap8 ? tBase : cap8) - 1.0);
      m *= eNow / eBase;
    }
    return m;
  };

  CompEngine.prototype._eff = function (caps, delivery) {
    var out = {}, m, v;
    for (var c in caps) {
      v = caps[c] / this.scoreUnit;
      m = this.mechMults[c];
      v = v * (m === undefined ? 1.0 : m);
      if (delivery !== undefined && delivery !== null && this._geoCaps[c])
        v *= this._geoMult(c, delivery[c]);
      out[c] = v;
    }
    return out;
  };

  CompEngine.prototype._loadoutEff = function (weapon) {
    var lo = this.weapons[weapon].loadout;
    var dl = this.weapons[weapon].cap_delivery || {};
    var hasSlots = lo && lo.slots && lo.slots.length;
    var hasAlways = lo && lo.always && Object.keys(lo.always).length;
    if (!lo || (!hasSlots && !hasAlways))
      return { always: this._eff(this.capsOf(weapon), dl), slots: [] };
    var self = this;
    return {
      always: this._eff(lo.always || {}, dl),
      slots: (lo.slots || []).map(function (slot) {
        return slot.map(function (b) { return self._eff(b, dl); });
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

  /* ---- gear (full-build members, 2026-08-20; mirrors engine.py) ---- */
  CompEngine.prototype.gearExtras = function (key) {
    var extras = this._gearCache[key];
    if (extras !== undefined) return extras;
    var g = this.gear[key];
    if (!g) { extras = [{}]; this._gearCache[key] = extras; return extras; }
    var dl = g.cap_delivery || {};
    var lo = g.loadout || {};
    var always = this._eff(lo.always || {}, dl);
    var slots = [];
    var raw = lo.slots || [];
    for (var i = 0; i < raw.length; i++) {
      if (!raw[i].length) continue;
      var eff = [];
      for (var j = 0; j < raw[i].length; j++) eff.push(this._eff(raw[i][j], dl));
      slots.push(eff);
    }
    extras = [];
    var self = this;
    (function walk(si, acc) {
      if (si === slots.length) {
        var extra = {}, c;
        for (c in always) extra[c] = always[c];
        for (var k = 0; k < acc.length; k++)
          for (c in acc[k]) extra[c] = (extra[c] || 0.0) + acc[k][c];
        extras.push(extra);
        return;
      }
      for (var j2 = 0; j2 < slots[si].length; j2++)
        walk(si + 1, acc.concat([slots[si][j2]]));
    })(0, []);
    this._gearCache[key] = extras;
    return extras;
  };

  CompEngine.prototype.defaultGearChoice = function (key) {
    var extras = this.gearExtras(key);
    var bestI = 0, bestVal = null, bestUnits = null;
    for (var i = 0; i < extras.length; i++) {
      var val = 0.0, units = 0.0;
      for (var c in extras[i]) {
        val += (this._weights[c] || 0.0) * extras[i][c];
        units += extras[i][c];
      }
      if (bestVal === null || val > bestVal
          || (val === bestVal && units > bestUnits)) {
        bestI = i; bestVal = val; bestUnits = units;
      }
    }
    return bestI;
  };

  CompEngine.prototype.gearExtra = function (key, choice) {
    var extras = this.gearExtras(key);
    if (choice === null || choice === undefined || choice < 0
        || choice >= extras.length)
      choice = this.defaultGearChoice(key);
    return extras[choice];
  };

  CompEngine.prototype.buildExtra = function (weapon, combo, gear) {
    var out = {}, c;
    var base = this.memberExtra(weapon, combo);
    for (c in base) out[c] = base[c];
    for (var i = 0; i < (gear || []).length; i++) {
      var item = gear[i];
      var key = Array.isArray(item) ? item[0] : item;
      var choice = Array.isArray(item) ? item[1] : null;
      var extra = this.gearExtra(key, choice);
      for (c in extra) out[c] = (out[c] || 0.0) + extra[c];
    }
    return out;
  };

  CompEngine.prototype.memberExtra = function (weapon, combo) {
    /* One member's effective caps for a combo (null -> static default). */
    var extras = this._comboExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    return extras[combo];
  };

  CompEngine.prototype._nonstackContrib = function (weapon, combo) {
    /* {spell: {cap: effective value}} for every verified non-stacking
       interaction spell this member's combo equips (mirrors engine.py
       _nonstack_contrib). Empty when no interaction data applies. */
    if (!this.hasNonstack) return {};
    var extras = this._comboExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    var key = weapon + " " + combo;
    var hit = this._nsCache[key];
    if (hit !== undefined) return hit;
    var lo = this.weapons[weapon].loadout || {};
    var spells = lo.slot_spells || [];
    var le = this._loadoutEff(weapon), slotsEff = le.slots;
    var out = {};
    var choices = this.comboChoices(weapon, combo);
    for (var ci = 0; ci < choices.length; ci++) {
      var oi = choices[ci][0], bi = choices[ci][1];
      if (oi >= spells.length || bi >= spells[oi].length) continue;
      var sid = spells[oi][bi];
      var caps = this.nonstack[sid];
      if (!caps || oi >= slotsEff.length || bi >= slotsEff[oi].length) continue;
      var bundle = slotsEff[oi][bi];
      var contrib = out[sid] || (out[sid] = {});
      var any = false;
      for (var cj = 0; cj < caps.length; cj++) {
        var v = bundle[caps[cj]] || 0.0;
        if (v) { contrib[caps[cj]] = (contrib[caps[cj]] || 0.0) + v; any = true; }
      }
      if (!any && Object.keys(contrib).length === 0) delete out[sid];
    }
    this._nsCache[key] = out;
    return out;
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

  CompEngine.prototype.effectiveSupply = function (party, combos, gears) {
    /* Supply after physics AND the one-spell-per-slot rule; ALL scoring
       reads this (mirrors engine.py effective_supply). */
    var s = {}, c;
    for (var i = 0; i < party.length; i++) {
      var extra = (gears && gears[i] && gears[i].length)
        ? this.buildExtra(party[i], combos ? combos[i] : null, gears[i])
        : this.memberExtra(party[i], combos ? combos[i] : null);
      for (c in extra) s[c] = (s[c] || 0.0) + extra[c];
    }
    if (this.hasNonstack) this._applyNonstack(s, party, combos);
    return s;
  };

  CompEngine.prototype._applyNonstack = function (s, party, combos) {
    /* Count-once rule for verified non-stacking interaction spells —
       identical accumulation ORDER to engine.py _apply_nonstack (sorted
       spell ids, stored cap order, party order): float parity is exact. */
    var groups = {};
    for (var i = 0; i < party.length; i++) {
      var per = this._nonstackContrib(party[i], combos ? combos[i] : null);
      for (var sid in per) (groups[sid] = groups[sid] || []).push(per[sid]);
    }
    var ids = Object.keys(groups).sort();
    for (var gi = 0; gi < ids.length; gi++) {
      var lst = groups[ids[gi]];
      if (lst.length < 2) continue;
      var caps = this.nonstack[ids[gi]];
      for (var cj = 0; cj < caps.length; cj++) {
        var cap = caps[cj], total = 0.0, mx = 0.0;
        for (var li = 0; li < lst.length; li++) {
          var v = lst[li][cap] || 0.0;
          total += v;
          if (v > mx) mx = v;
        }
        var excess = total - mx;
        if (excess > 0.0) s[cap] = (s[cap] || 0.0) - excess;
      }
    }
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
  CompEngine.prototype.fitness = function (party, combos, gears) {
    var s = this.effectiveSupply(party, combos, gears), total = 0.0;
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
  CompEngine.prototype.compScore = function (party, combos, gears) {
    /* THE party-level objective (mirrors engine.py comp_score). */
    var meta = 0.0, viab = 0.0;
    for (var i = 0; i < party.length; i++) {
      meta += this.metaOf(party[i]);
      viab += this.viabilityOf(party[i]);
    }
    return this.alpha * this.fitness(party, combos, gears)
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
    var nsMax = {};
    if (this.hasNonstack) {
      for (i = 0; i < party.length; i++) {
        var per = this._nonstackContrib(party[i], combos ? combos[i] : null);
        for (var sid in per) {
          var cur = nsMax[sid] || (nsMax[sid] = {});
          for (var cap in per[sid]) {
            if (per[sid][cap] > (cur[cap] || 0.0)) cur[cap] = per[sid][cap];
          }
        }
      }
    }
    return { s: s, J: J, pairVals: pairVals, counts: counts, nsMax: nsMax };
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

  CompEngine.prototype._margSynFrom = function (state, extra, extraJ) {
    /* extraJ (default: extra) is the member's UNADJUSTED caps for the
       largest-single-member joint term J (mirrors engine.py). */
    if (extraJ === undefined || extraJ === null) extraJ = extra;
    var total = 0.0;
    for (var p = 0; p < this._activeSyn.length; p++) {
      var a = this._activeSyn[p][0], b = this._activeSyn[p][1];
      var j = Math.min(extraJ[a] || 0.0, extraJ[b] || 0.0);
      var j2 = state.J[p] > j ? state.J[p] : j;
      total += this._pairValue(p, (state.s[a] || 0.0) + (extra[a] || 0.0),
                               (state.s[b] || 0.0) + (extra[b] || 0.0), j2)
             - state.pairVals[p];
    }
    return total;
  };

  CompEngine.prototype._nonstackAdjust = function (state, weapon, combo, extra) {
    /* Candidate caps with the count-once rule applied against the current
       party (mirrors engine.py _nonstack_adjust). Returns `extra` itself
       when nothing applies. */
    var nsMax = state.nsMax;
    if (!this.hasNonstack || !nsMax) return extra;
    var adj = null;
    var per = this._nonstackContrib(weapon, combo);
    for (var sid in per) {
      var pmax = nsMax[sid];
      if (!pmax) continue;
      if (adj === null) {
        adj = {};
        for (var c in extra) adj[c] = extra[c];
      }
      var caps = this.nonstack[sid];
      for (var cj = 0; cj < caps.length; cj++) {
        var cap = caps[cj], v = per[sid][cap] || 0.0;
        if (!v) continue;
        var gain = v - (pmax[cap] || 0.0);
        adj[cap] = (adj[cap] || 0.0) - v + (gain > 0.0 ? gain : 0.0);
      }
    }
    return adj === null ? extra : adj;
  };

  CompEngine.prototype._comboScore = function (state, weapon, i, extra) {
    /* One combo's value against a party state (mirrors engine.py
       _combo_score) — identical float-op order to the original loop. */
    var adj = this._nonstackAdjust(state, weapon, i, extra);
    var dFit = this._margFitFrom(state.s, adj);
    var dSyn = this._margSynFrom(state, adj, extra);
    return { val: this.alpha * dFit + this.beta * dSyn, dFit: dFit, dSyn: dSyn };
  };

  CompEngine.prototype._pickTail = function (state, weapon, best) {
    /* Combo-independent candidate-score terms (mirrors engine.py
       _pick_tail). */
    var meta = this.metaOf(weapon);
    var dup = (state.counts[weapon] || 0) + 1 - this._dupFree(weapon);
    var score = best.val + this.delta * meta
              + this.viabilityW * this.viabilityOf(weapon)
              - (dup > 0 ? this.rho * dup : 0.0);
    return { score: score, dFit: best.dFit, dSyn: best.dSyn, meta: meta, combo: best.combo };
  };

  CompEngine.prototype._evalPick = function (state, weapon) {
    /* THE candidate score — the exact compScore delta of adding `weapon`
       with its best loadout (mirrors engine.py _eval_pick). Returns
       {score, dFit, dSyn, meta, combo}. */
    var best = null;
    var extras = this._comboExtras(weapon);
    for (var i = 0; i < extras.length; i++) {
      var cs = this._comboScore(state, weapon, i, extras[i]);
      if (best === null || cs.val > best.val)
        best = { val: cs.val, dFit: cs.dFit, dSyn: cs.dSyn, combo: i };
    }
    if (best === null) best = { val: 0.0, dFit: 0.0, dSyn: 0.0, combo: null };
    return this._pickTail(state, weapon, best);
  };

  CompEngine.prototype._predContrib = function (weapon, combo) {
    /* {pred name: true} the member's SELECTED combo satisfies, from RAW
       loadout caps (mirrors engine.py _pred_contrib). */
    var extras = this._comboExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    var key = weapon + " " + combo;
    var hit = this._predCache[key];
    if (hit !== undefined) return hit;
    var lo = this.weapons[weapon].loadout || {};
    var caps;
    if ((lo.slots && lo.slots.length) || lo.always) {
      caps = {};
      var alw = lo.always || {};
      for (var c in alw) caps[c] = alw[c];
      var slots = lo.slots || [];
      var choices = this.comboChoices(weapon, combo);
      for (var ci = 0; ci < choices.length; ci++) {
        var oi = choices[ci][0], bi = choices[ci][1];
        if (oi < slots.length && bi < slots[oi].length) {
          var b = slots[oi][bi];
          for (var c2 in b) caps[c2] = (caps[c2] || 0) + b[c2];
        }
      }
    } else {
      caps = this.weapons[weapon].capabilities;
    }
    var out = {};
    for (var pn in this.predDefs) {
      var mins = this.predDefs[pn], okp = true;
      for (var pc in mins) {
        if ((caps[pc] || 0) < mins[pc]) { okp = false; break; }
      }
      if (okp) out[pn] = true;
    }
    this._predCache[key] = out;
    return out;
  };

  CompEngine.prototype._predPossible = function (weapon) {
    /* Predicates SOME combo can satisfy — the optimistic beam bound
       (mirrors engine.py _pred_possible). */
    var hit = this._predPossibleCache[weapon];
    if (hit !== undefined) return hit;
    var out = {};
    var n = this._comboExtras(weapon).length;
    for (var i = 0; i < n; i++) {
      var per = this._predContrib(weapon, i);
      for (var pn in per) out[pn] = true;
    }
    this._predPossibleCache[weapon] = out;
    return out;
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

  /* ----------------------------------------------- interaction analysis
     (mirrors engine.py duplicate_conflicts / analyze — "new prompt" spec
     §7/§9). Severity high/warning only on VERIFIED non-stacking records;
     verified full and shared stacks are info; anything the game data does
     not state is 'verify', never an invented penalty. */
  var DAMAGE_CAPS_PROFILE = ["burst_aoe", "burst_st", "sustained_dps", "execute"];
  var UTILITY_CAPS_PROFILE = ["purge", "cleanse", "silence", "heal_reduction",
                              "resist_shred", "clump_create", "anti_zone",
                              "damage_debuff", "buff_allies"];
  var DEFENSE_CAPS_PROFILE = ["tankiness", "peel", "heal_sustain", "heal_burst",
                              "disengage", "mobility"];

  CompEngine.prototype.duplicateConflicts = function (party, combos) {
    var bySpell = {};
    for (var i = 0; i < party.length; i++) {
      var eq = this.comboSpells(party[i], combos ? combos[i] : null);
      for (var ei = 0; ei < eq.length; ei++) {
        var sid = eq[ei][1];
        (bySpell[sid] = bySpell[sid] || []).push(party[i]);
      }
    }
    var out = [];
    var ids = Object.keys(bySpell).sort();
    for (var si = 0; si < ids.length; si++) {
      var members = bySpell[ids[si]];
      if (members.length < 2) continue;
      var rec = this.interactions[ids[si]];
      if (!rec) continue;
      var name = rec.name || ids[si];
      var dup = rec.duplicate || "unknown";
      var verified = rec.confidence === "verified";
      var ns = (rec.nonstacking_caps || []).filter(
        function (c) { return c in this.reqs; }, this);
      var severity, reason;
      if (verified && ns.length) {
        severity = (dup === "does_not_stack" || dup === "override" ||
                    dup === "refresh") ? "high" : "warning";
        reason = name + ": " + ns.join(", ") + " counts once for the party (" +
                 dup + ") — a duplicate adds its other components only";
      } else if (verified && dup === "full") {
        severity = "info";
        reason = name + ": duplicates give verified full independent value";
      } else if (dup === "shared_stack") {
        severity = "info";
        reason = name + ": duplicates feed one shared stack on the target — " +
                 "faster stacking, not wasted value";
      } else {
        severity = "verify";
        reason = name + ": duplicate behavior is not stated by the game data" +
                 " — verify before stacking (" + rec.confidence + ")";
      }
      out.push({ spell: ids[si], name: name, weapons: members,
                 severity: severity, duplicate: dup, effect: rec.effect_name,
                 confidence: rec.confidence, reason: reason });
    }
    return out;
  };

  CompEngine.prototype.analyze = function (party, combos) {
    var s = this.effectiveSupply(party, combos);
    var strengths = [], missing = [];
    for (var cap in this.reqs) {
      var have = s[cap] || 0.0, target = this.target(cap);
      if (have >= target) {
        strengths.push({ cap: cap, have: have, target: target });
      } else if (this.weight(cap) > 0) {
        missing.push({ cap: cap, have: have, target: target,
                       gap: target - have,
                       weighted_gap: this.weight(cap) * (target - have) / target });
      }
    }
    missing.sort(function (a, b) { return b.weighted_gap - a.weighted_gap; });
    var cc = {};
    for (var i = 0; i < party.length; i++) {
      var eq = this.comboSpells(party[i], combos ? combos[i] : null);
      for (var ei = 0; ei < eq.length; ei++) {
        var rec = this.interactions[eq[ei][1]];
        if (rec) (rec.cc_types || []).forEach(function (t) { cc[t] = true; });
      }
    }
    var profile = function (caps) {
      var out = {};
      for (var pi = 0; pi < caps.length; pi++) {
        if (s[caps[pi]]) out[caps[pi]] = s[caps[pi]];
      }
      return out;
    };
    return {
      strengths: strengths,
      missing_capabilities: missing,
      duplicate_conflicts: this.duplicateConflicts(party, combos),
      cc_coverage: Object.keys(cc).sort(),
      damage_profile: profile(DAMAGE_CAPS_PROFILE),
      utility_coverage: profile(UTILITY_CAPS_PROFILE),
      defensive_coverage: profile(DEFENSE_CAPS_PROFILE),
    };
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
      if (key in this.predDefs) {
        if (rule.min !== undefined) predMin[key] = rule.min;
        continue;
      }
      if (rule.min !== undefined) roleMin[key] = rule.min;
      if (rule.max !== undefined) roleMax[key] = rule.max;
    }
    return { pool: pool, roleMin: roleMin, roleMax: roleMax, predMin: predMin };
  };

  CompEngine.prototype._forgeCounts = function (party, combos) {
    /* [weapon counts, role counts, predicate counts, group counts].
       Predicate counts are COMBO-AWARE (mirrors engine.py _forge_counts,
       review 2026-08-19). */
    var counts = {}, roles = {}, preds = {}, groups = {};
    for (var i = 0; i < party.length; i++) {
      var w = party[i];
      counts[w] = (counts[w] || 0) + 1;
      var r = this.roleOf(w);
      roles[r] = (roles[r] || 0) + 1;
      var contrib = this._predContrib(w, combos ? combos[i] : null);
      for (var pn in contrib) preds[pn] = (preds[pn] || 0) + 1;
      var gs = this.groupsOf[w] || [];
      for (var g = 0; g < gs.length; g++) groups[gs[g]] = (groups[gs[g]] || 0) + 1;
    }
    return [counts, roles, preds, groups];
  };

  CompEngine.prototype._forgeMinNeed = function (ctx, roles, preds, w, predContrib) {
    /* Slots still required for unmet minima after adding `w` (mirrors
       engine.py _forge_min_need). */
    var need = 0;
    var r = this.roleOf(w);
    for (var r2 in ctx.roleMin) {
      var have = (roles[r2] || 0) + (r2 === r ? 1 : 0);
      if (ctx.roleMin[r2] > have) need += ctx.roleMin[r2] - have;
    }
    for (var pn in ctx.predMin) {
      var haveP = (preds[pn] || 0) + (predContrib[pn] ? 1 : 0);
      if (ctx.predMin[pn] > haveP) need += ctx.predMin[pn] - haveP;
    }
    return need;
  };

  CompEngine.prototype._forgeFeasible = function (ctx, counts, roles, preds, groups, w, slotsLeftAfter) {
    /* May the forge add `w` here and still complete a legal roster?
       Predicate contribution is OPTIMISTIC here; _forgeEvalPick enforces
       the exact per-combo need (mirrors engine.py _forge_feasible). */
    if ((counts[w] || 0) >= this._dupGenMax(w)) return false;
    var gs = this.groupsOf[w] || [];
    for (var g = 0; g < gs.length; g++) {
      var gmax = this.groups[gs[g]].max;
      if ((groups[gs[g]] || 0) >= (gmax === undefined ? 1e9 : gmax)) return false;
    }
    var r = this.roleOf(w);
    var mx = ctx.roleMax[r];
    if (mx !== undefined && (roles[r] || 0) >= mx) return false;
    return this._forgeMinNeed(ctx, roles, preds, w, this._predPossible(w))
           <= slotsLeftAfter;
  };

  CompEngine.prototype._forgeEvalPick = function (ctx, beam, w, slotsLeftAfter) {
    /* _evalPick restricted to combos that keep the roster completable
       (mirrors engine.py _forge_eval_pick). Returns null when no combo
       keeps the minima satisfiable. */
    var state = beam.state;
    var best = null;
    var extras = this._comboExtras(w);
    var hasPred = false;
    for (var k in ctx.predMin) { hasPred = true; break; }
    for (var i = 0; i < extras.length; i++) {
      if (hasPred) {
        var need = this._forgeMinNeed(ctx, beam.roles, beam.preds, w,
                                      this._predContrib(w, i));
        if (need > slotsLeftAfter) continue;
      }
      var cs = this._comboScore(state, w, i, extras[i]);
      if (best === null || cs.val > best.val)
        best = { val: cs.val, dFit: cs.dFit, dSyn: cs.dSyn, combo: i };
    }
    if (best === null) return null;
    return this._pickTail(state, w, best);
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

    var fc = this._forgeCounts(locked, combos);
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
          var pick = this._forgeEvalPick(ctx, beam, w, slotsLeftAfter);
          if (pick === null) continue;  /* no combo keeps minima satisfiable */
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
        var fc2 = this._forgeCounts(party2, combos2);
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
      var fcs = this._forgeCounts(sub, subC);
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
    /* final feasibility net (mirrors engine.py): the SELECTED combos must
       meet every minimum — locked non-qualifying spell picks are reported,
       never counted through the flat sheet map. */
    var fcf = this._forgeCounts(party, combosOut);
    for (var rf in ctx.roleMin) {
      if ((fcf[1][rf] || 0) < ctx.roleMin[rf]) feasible = false;
    }
    for (var pf in ctx.predMin) {
      if ((fcf[2][pf] || 0) < ctx.predMin[pf]) feasible = false;
    }
    return { party: party, combos: combosOut, score: base,
             feasible: feasible, filler: filler, held: held, locked: fixed };
  };

  CompEngine.prototype._addOk = function (ctx, counts, roles, groups, w) {
    /* Copy/group/role-MAX check for adding `w` to a roster whose counts
       exclude the slot being replaced (mirrors engine.py _add_ok). Minima
       are enforced through _forgeEvalPick's exact per-combo need. */
    if ((counts[w] || 0) + 1 > this._dupGenMax(w)) return false;
    var gs = this.groupsOf[w] || [];
    for (var g = 0; g < gs.length; g++) {
      var gmax = this.groups[gs[g]].max;
      if ((groups[gs[g]] || 0) + 1 > (gmax === undefined ? 1e9 : gmax)) return false;
    }
    var r = this.roleOf(w);
    var mx = ctx.roleMax[r];
    if (mx !== undefined && (roles[r] || 0) + 1 > mx) return false;
    return true;
  };

  CompEngine.prototype._refineConstrained = function (ctx, party, combos, fixed, maxPasses) {
    /* Steepest-descent 1-opt over generated slots, constraint-aware:
       minima are checked against the REST roster's combo-aware counts, so
       a swap can never trade away the spells a minimum was counting on
       (mirrors engine.py _refine_constrained, review 2026-08-19). */
    party = party.slice(); combos = combos.slice();
    if (maxPasses === undefined) maxPasses = 8;
    var best = this.compScore(party, combos);
    for (var pass = 0; pass < maxPasses; pass++) {
      var move = null, gain = 1e-9;
      for (var i = fixed; i < party.length; i++) {
        var rest = party.slice(0, i).concat(party.slice(i + 1));
        var restC = combos.slice(0, i).concat(combos.slice(i + 1));
        var fcr = this._forgeCounts(rest, restC);
        var state = this.partyState(rest, restC);
        var baseRest = this.compScore(rest, restC);
        var contrib = best - baseRest;
        var orig = party[i];
        var beam = { state: state, roles: fcr[1], preds: fcr[2] };
        for (var j = 0; j < ctx.pool.length; j++) {
          var w = ctx.pool[j];
          if (w === orig) continue;
          if (!this._addOk(ctx, fcr[0], fcr[1], fcr[3], w)) continue;
          var pick = this._forgeEvalPick(ctx, beam, w, 0);
          if (pick === null) continue;
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
              var fc = this._forgeCounts(candParty, candCombos);
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
