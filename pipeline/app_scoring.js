/* Composition scoring — JavaScript port of engine/engine.py.
 *
 * SINGLE SOURCE OF MATH: engine/engine.py is authoritative; this file must
 * mirror it exactly and tests/test_js_parity.py verifies that it does
 * (same fitness, same rankings, across all templates, on random parties).
 * If you change one, change both, then run the parity test.
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
    this.metaPrior = this.scoring.meta_prior || {};
    /* meta_prior is a FLAT {weapon: value} map or SIZE-BUCKETED
       {small|mid|large: {weapon: value}} (usage-derived, Q17). Mirrors
       engine.py meta_bucketed. */
    var mpKeys = Object.keys(this.metaPrior);
    this.metaBucketed = mpKeys.length > 0 &&
      mpKeys.every(function (k) { return k === "small" || k === "mid" || k === "large"; });
    this.synergies = (this.scoring.capability_synergies || []).map(function (s) {
      return [s.a, s.b, s.bonus];
    });
    this.mechanics = data.mechanics || {};
    /* Candidate pool for every SUGGESTION path (recommend/swapReview/refine).
       Retired weapons stay in this.weapons so an old permalink still loads and
       scores; they are only barred from being offered. Insertion order is
       preserved — refine() breaks ties by iteration order and must walk the
       same sequence as engine.py. Mirrors engine.py self.pool. */
    this.pool = [];
    for (var pk in this.weapons) if (!this.weapons[pk].removed) this.pool.push(pk);
    this.setContent(content || "castle_outpost", size, style);
  }

  CompEngine.prototype.setContent = function (content, size, style) {
    this.template = this.data.templates[content];
    this.content = content;
    this.baseSize = this.template.base_size || size;
    this.size = (size === undefined || size === null) ? this.baseSize : size;
    this.reqs = this.template.requirements;
    this.floors = this.template.hard_floors || {};
    /* Playstyle overlay: multiplies capability WEIGHTS only; hard floors
       stay on the base weight (mirrors engine.py). */
    this.style = style || "balanced";
    var styles = this.data.styles || {};
    this.styleMults = (styles[this.style] || {}).multipliers || {};
    /* Mechanics overlay: ABSOLUTE physics by size, anchored to (balanced,
       base size) — base size unchanged, above it single-target damage is
       taxed harder (more focus fire) and AoE boosted (more escalation).
       Sub-linear growth (0.5) capped at 8. Mirrors engine.py set_content. */
    var styleMech = (styles[this.style] || {}).mechanics || {};
    var baseMech = (styles.balanced || {}).mechanics || {};
    var scale = this.baseSize ? this.size / this.baseSize : 1.0;
    var grow = function (p) {
      return p ? Math.min(8.0, p * (1.0 + 0.5 * (scale - 1.0))) : p;
    };
    this.mechMults = {};
    var i;
    for (i = 0; i < AOE_ESCALATION_CAPS.length; i++) {
      this.mechMults[AOE_ESCALATION_CAPS[i]] =
        this._escalationMult(grow(styleMech.expected_aoe_targets))
        / this._escalationMult(baseMech.expected_aoe_targets);
    }
    for (i = 0; i < RESILIENCE_CAPS.length; i++) {
      this.mechMults[RESILIENCE_CAPS[i]] =
        this._resilienceEff(grow(styleMech.focus_attackers))
        / this._resilienceEff(baseMech.focus_attackers);
    }
    /* Per-context caches (mirrors engine.py set_content): scaled targets/
       soft caps, styled weights, per-weapon loadout combos (lazy), pool
       keys. Constant until the next setContent; same expressions, same
       floats — the recommend/swap hot path otherwise recomputes them per
       candidate per combo (~2x on swapReview, measured). */
    this._targets = {}; this._softs = {}; this._weights = {};
    for (var cap2 in this.reqs) {
      var r = this.reqs[cap2];
      this._targets[cap2] = r.scales ? r.target * this.size / this.baseSize : r.target;
      this._softs[cap2] = r.scales ? r.soft_cap * this.size / this.baseSize : r.soft_cap;
      var m2 = this.styleMults[cap2];
      this._weights[cap2] = r.weight * (m2 === undefined ? 1.0 : m2);
    }
    this._extrasCache = {};
    this._poolKeys = null;
  };

  CompEngine.prototype._tableLookup = function (table, x) {
    /* Clamped mechanics-table value for count x, or null when the table is
       missing or x falsy (mirrors engine.py _table_lookup). half-UP rounding,
       explicitly (Math.floor(x+0.5)) — Python round() is half-to-even; the
       implicit rules disagreed on the .5 counts grow() produces at ordinary
       sizes (review 2026-08-15). */
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
    /* small <12 / mid <=30 / large >30 — sample_battles.py's buckets; the
       one definition the meta prior AND the usage display read. */
    return this.size < 12 ? "small" : this.size <= 30 ? "mid" : "large";
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

  CompEngine.prototype.supply = function (party) {
    /* Raw capability units summed over the party (sheet numbers). */
    var s = {};
    for (var i = 0; i < party.length; i++) {
      var caps = this.capsOf(party[i]);
      for (var cap in caps) s[cap] = (s[cap] || 0) + caps[cap];
    }
    return s;
  };

  CompEngine.prototype.effectiveSupply = function (party) {
    /* Supply after style-delivery physics (AoE escalation, Resilience).
       Balanced-at-base-size is the identity. ALL scoring — floors included —
       reads THIS (mirrors engine.py); raw supply() is the sheet-unit
       reference only. */
    var s = this.supply(party);
    for (var cap in this.mechMults) {
      var m = this.mechMults[cap];
      if (m !== 1.0 && cap in s) s[cap] = s[cap] * m;
    }
    return s;
  };

  CompEngine.prototype.floorArmed = function (cap, have) {
    /* THE below-the-hard-floor predicate (mirrors engine.py floor_armed);
       the dashboard's floor tags read it too, so display can never disagree
       with scoring. */
    var f = this.floors[cap];
    return !!f && this.size >= f.min_party_size && have < f.floor_units;
  };

  CompEngine.prototype._floorPenalty = function (cap, have) {
    if (!this.floorArmed(cap, have)) return 0.0;
    var f = this.floors[cap];
    var w = this.reqs[cap].weight;
    return f.penalty_mult * w * (f.floor_units - have) / f.floor_units;
  };

  CompEngine.prototype._overstack = function (cap, have, target, soft) {
    /* Over-stack penalty at one supply level, on the BASE weight (T10) —
       one home for a rule written out three times before (mirrors engine.py).
       SATURATING (2026-08-18): approaches overstackMax*weight and never
       exceeds it, scaled by soft_cap not target. Rational, not exp() — the
       parity test is exact and exp() is not guaranteed identical across
       Python and JS. Mirrors engine.py _overstack. */
    if (have <= soft) return 0.0;
    var scale = soft > 0 ? soft : target;
    var x = (have - soft) / scale;
    return this.overstackMax * this.reqs[cap].weight * x / (1.0 + x);
  };

  CompEngine.prototype._coverTerms = function (cap, have, gain, target) {
    /* [coverage delta, floor-lift delta] — two terms so callers accumulate
       in their original order (float addition is not associative; parity
       pins the exact sums). Mirrors engine.py _cover_terms. */
    var cov = this.weight(cap) * (Math.pow(Math.min(1.0, (have + gain) / target), this.gamma)
                                  - Math.pow(Math.min(1.0, have / target), this.gamma));
    return [cov, this._floorPenalty(cap, have) - this._floorPenalty(cap, have + gain)];
  };

  CompEngine.prototype.fitness = function (party) {
    var s = this.effectiveSupply(party), total = 0.0;
    for (var cap in this.reqs) {
      var have = s[cap] || 0.0, target = this.target(cap), soft = this.softCap(cap);
      /* style multiplies the VALUE of coverage; over-stack economics and
         floors stay on the base weight (mirrors engine.py, see T10) */
      total += this.weight(cap) * Math.pow(Math.min(1.0, have / target), this.gamma);
      total -= this._overstack(cap, have, target, soft);
      total -= this._floorPenalty(cap, have);
    }
    return total;
  };

  CompEngine.prototype.maxFitness = function () {
    var t = 0;
    for (var cap in this.reqs) t += this.weight(cap);
    return t;
  };

  CompEngine.prototype.synergy = function (party) {
    var s = this.effectiveSupply(party), total = 0.0;
    for (var i = 0; i < this.synergies.length; i++) {
      var a = this.synergies[i][0], c = this.synergies[i][1], b = this.synergies[i][2];
      total += b * Math.min(s[a] || 0, s[c] || 0);
    }
    return total;
  };

  /* ---- comp-level score + local search (mirrors engine.py comp_score/refine) */

  CompEngine.prototype.compScore = function (party) {
    /* The SAME alpha/beta/delta blend pickScore applies marginally, so the
       greedy builder and the refine pass optimise ONE objective. Before this
       they disagreed about their own output: the builder took Hand of Justice
       as its first pick (empty party, clump unmet) and swapReview then ranked
       that very slot 132nd (full party, clump saturated). */
    var meta = 0.0;
    for (var i = 0; i < party.length; i++) meta += this.metaOf(party[i]);
    return this.alpha * this.fitness(party)
         + this.beta * this.synergy(party)
         + this.delta * meta;
  };

  CompEngine.prototype.refine = function (party, maxPasses, pool, fixed) {
    /* 1-opt local search: repeatedly apply the single slot replacement that
       most improves compScore, until none does. Greedy fill alone cannot undo
       an early pick — slot 1 is chosen against an EMPTY party and never
       revisited once the comp is full. Steepest-descent (best move per pass,
       not first-improvement) so the result does not depend on iteration
       order. `fixed` locks the first N slots (hand-placed members survive
       "forge the rest" untouched). Returns a NEW array. Mirrors engine.py
       refine. */
    party = party.slice();
    fixed = fixed || 0;
    if (!party.length) return party;
    var candidates;
    if (pool) { candidates = pool.slice(); }
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

  /* ---- loadout model (mirrors engine.py; a player equips one spell per slot,
     so a candidate's marginal is its BEST single loadout, not the whole menu).
     Base-party supply stays flat-union; only the evaluated candidate is
     loadout-limited. Enumeration ORDER matches itertools.product exactly so
     the argmax picks the same loadout in both engines (parity). */
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

  CompEngine.prototype._margSynFrom = function (s, baseSyn, extra) {
    var total = 0.0;
    for (var i = 0; i < this.synergies.length; i++) {
      var a = this.synergies[i][0], c = this.synergies[i][1], b = this.synergies[i][2];
      total += b * Math.min((s[a] || 0) + (extra[a] || 0), (s[c] || 0) + (extra[c] || 0));
    }
    return total - baseSyn;
  };

  CompEngine.prototype._loadoutExtras = function (weapon) {
    /* The weapon's candidate loadouts as merged effective-caps objects,
       cached per setContent (they depend only on the weapon and the
       mechanics multipliers). Enumeration order matches itertools.product
       so the argmax tie-break is identical to the uncached path. Returned
       objects are READ-ONLY — bestLoadout hands them out directly.
       Mirrors engine.py _loadout_extras. */
    var extras = this._extrasCache[weapon];
    if (extras) return extras;
    var le = this._loadoutEff(weapon), always = le.always, slots = le.slots;
    /* each slot equips exactly ONE spell (no empty option) — see engine.py */
    var choices = slots.filter(function (slot) { return slot.length; });
    var combos = [[]], i, j, k, next;
    for (i = 0; i < choices.length; i++) {           /* cartesian product, itertools order */
      next = [];
      for (j = 0; j < combos.length; j++)
        for (k = 0; k < choices[i].length; k++)
          next.push(combos[j].concat([choices[i][k]]));
      combos = next;
    }
    extras = [];
    for (i = 0; i < combos.length; i++) {
      var extra = {}, c0; for (c0 in always) extra[c0] = always[c0];
      var combo = combos[i];
      for (j = 0; j < combo.length; j++) {
        var bd = combo[j];
        if (bd) for (var c in bd) if (bd[c] > (extra[c] || 0)) extra[c] = bd[c];
      }
      extras.push(extra);
    }
    this._extrasCache[weapon] = extras;
    return extras;
  };

  CompEngine.prototype.bestLoadout = function (s, baseSyn, weapon) {
    var extras = this._loadoutExtras(weapon);
    var best = null;
    for (var i = 0; i < extras.length; i++) {
      var extra = extras[i];
      var dFit = this._margFitFrom(s, extra);
      var dSyn = this._margSynFrom(s, baseSyn, extra);
      var val = this.alpha * dFit + this.beta * dSyn;
      if (best === null || val > best.val)
        best = { val: val, dFit: dFit, dSyn: dSyn, extra: extra };
    }
    return best === null ? { dFit: 0.0, dSyn: 0.0, extra: {} } : best;
  };

  CompEngine.prototype.explain = function (party, candidate) {
    var s = this.effectiveSupply(party);
    var bl = this.bestLoadout(s, this.synergy(party), candidate);
    var extra = bl.extra, terms = [];
    for (var cap in extra) {
      var gain = extra[cap];
      if (!(cap in this.reqs) || !gain) continue;
      var have = s[cap] || 0.0, target = this.target(cap);
      /* coverage + floor-lift credit — the same terms bestLoadout scored */
      var ct = this._coverTerms(cap, have, gain, target);
      var d = ct[0] + ct[1];
      if (d > 0.05) {
        terms.push({ delta: Math.round(d * 100) / 100, cap: cap,
                     before: have, after: have + gain, target: target });
      }
    }
    return terms.sort(function (x, y) { return y.delta - x.delta; });
  };

  CompEngine.prototype.metaOf = function (w) {
    if (!this.metaBucketed) return this.metaPrior[w] || 0.0;
    return (this.metaPrior[this.sizeBucket()] || {})[w] || 0.0;
  };

  CompEngine.prototype.pickScore = function (s, baseSyn, weapon) {
    /* THE candidate score (mirrors engine.py pick_score): recommend() and
       swapReview() both read this one helper so the formula cannot drift. */
    var bl = this.bestLoadout(s, baseSyn, weapon);
    var meta = this.metaOf(weapon);
    return { score: this.alpha * bl.dFit + this.beta * bl.dSyn + this.delta * meta,
             dFit: bl.dFit, dSyn: bl.dSyn, meta: meta };
  };

  CompEngine.prototype._pool = function (pool) {
    /* mirrors Python's `pool or self.pool`: an EMPTY pool array also falls
       back to the default catalog (a bare `pool ||` kept truthy empty arrays
       and silently swept nothing — parity bug). The default is this.pool,
       which excludes game-retired weapons; it is built once in the ctor. */
    if (pool && pool.length) return pool;
    return this.pool;
  };

  CompEngine.prototype.recommend = function (party, topN, pool) {
    if (topN === undefined) topN = 4;
    var baseSyn = this.synergy(party);
    var s = this.effectiveSupply(party);
    var out = [];
    var keys = this._pool(pool);
    for (var i = 0; i < keys.length; i++) {
      var w = keys[i];
      var ps = this.pickScore(s, baseSyn, w);
      out.push({
        weapon: w,
        display_name: this.weapons[w].display_name,
        status: this.weapons[w].status,
        d_fitness: ps.dFit, d_synergy: ps.dSyn, meta_prior: ps.meta,
        score: ps.score,
      });
    }
    return out.sort(function (x, y) { return y.score - x.score; }).slice(0, topN);
  };

  CompEngine.prototype.swapReview = function (party, topN, pool) {
    /* Per-member swap advisor (mirrors engine.py swap_review): value each
       member's CURRENT weapon as a pick into the REST of the party, rank it
       against every alternative (strictly-better only, so ties never demote),
       return the top upgrade options with gains. Data, not verdict. */
    if (topN === undefined) topN = 3;
    var out = [];
    for (var i = 0; i < party.length; i++) {
      var cur = party[i];
      var rest = party.slice(0, i).concat(party.slice(i + 1));
      var s = this.effectiveSupply(rest);
      var baseSyn = this.synergy(rest);
      var self = this;
      var curScore = this.pickScore(s, baseSyn, cur).score;
      var better = [];
      var keys = this._pool(pool);
      for (var j = 0; j < keys.length; j++) {
        var w = keys[j];
        if (w === cur) continue;
        var v = this.pickScore(s, baseSyn, w).score;
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
        options: better.slice(0, topN).map(function (t) {
          return { weapon: t[1],
                   display_name: self.weapons[t[1]].display_name,
                   score: t[0], gain: t[0] - curScore };
        }),
      });
    }
    return out;
  };

  CompEngine.prototype.weaknesses = function (party, topN) {
    if (topN === undefined) topN = 3;
    var s = this.effectiveSupply(party), gaps = [];
    for (var cap in this.reqs) {
      var have = s[cap] || 0;
      gaps.push({ cap: cap,
                  gap: this.weight(cap) * (1 - Math.pow(Math.min(1.0, have / this.target(cap)), this.gamma)),
                  have: have, target: this.target(cap) });
    }
    return gaps.sort(function (x, y) { return y.gap - x.gap; }).slice(0, topN);
  };

  CompEngine.prototype.uncoveredCaps = function (party) {
    var s = this.effectiveSupply(party), out = [];
    for (var cap in this.reqs) {
      if (this.weight(cap) >= 5 && (s[cap] || 0) / this.target(cap) < 0.5) out.push(cap);
    }
    return out;
  };

  if (typeof module !== "undefined" && module.exports) module.exports = CompEngine;
  else root.CompEngine = CompEngine;
})(typeof self !== "undefined" ? self : this);
