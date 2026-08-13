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

  function CompEngine(data, content, size) {
    this.data = data;
    this.weapons = data.weapons;
    this.scoring = data.scoring;
    var w = this.scoring.weights;
    this.alpha = w.alpha; this.beta = w.beta;
    this.delta = w.delta; this.gamma = w.gamma;
    this.metaPrior = this.scoring.meta_prior || {};
    this.synergies = (this.scoring.capability_synergies || []).map(function (s) {
      return [s.a, s.b, s.bonus];
    });
    this.setContent(content || "castle_outpost", size);
  }

  CompEngine.prototype.setContent = function (content, size) {
    this.template = this.data.templates[content];
    this.content = content;
    this.baseSize = this.template.base_size || size;
    this.size = (size === undefined || size === null) ? this.baseSize : size;
    this.reqs = this.template.requirements;
    this.floors = this.template.hard_floors || {};
  };

  CompEngine.prototype.extrapolated = function () {
    var v = this.template.validated_sizes || [this.baseSize];
    return v.indexOf(this.size) === -1;
  };

  CompEngine.prototype.target = function (cap) {
    var r = this.reqs[cap];
    return r.scales ? r.target * this.size / this.baseSize : r.target;
  };

  CompEngine.prototype.softCap = function (cap) {
    var r = this.reqs[cap];
    return r.scales ? r.soft_cap * this.size / this.baseSize : r.soft_cap;
  };

  CompEngine.prototype.capsOf = function (weapon) {
    return this.weapons[weapon].capabilities;
  };

  CompEngine.prototype.supply = function (party) {
    var s = {};
    for (var i = 0; i < party.length; i++) {
      var caps = this.capsOf(party[i]);
      for (var cap in caps) s[cap] = (s[cap] || 0) + caps[cap];
    }
    return s;
  };

  CompEngine.prototype._floorPenalty = function (cap, have) {
    var f = this.floors[cap];
    if (!f || this.size < f.min_party_size || have >= f.floor_units) return 0.0;
    var w = this.reqs[cap].weight;
    return f.penalty_mult * w * (f.floor_units - have) / f.floor_units;
  };

  CompEngine.prototype.fitness = function (party) {
    var s = this.supply(party), total = 0.0;
    for (var cap in this.reqs) {
      var r = this.reqs[cap];
      var have = s[cap] || 0.0, target = this.target(cap), soft = this.softCap(cap);
      total += r.weight * Math.pow(Math.min(1.0, have / target), this.gamma);
      if (have > soft) total -= 0.5 * r.weight * (have - soft) / target;
      total -= this._floorPenalty(cap, have);
    }
    return total;
  };

  CompEngine.prototype.maxFitness = function () {
    var t = 0;
    for (var cap in this.reqs) t += this.reqs[cap].weight;
    return t;
  };

  CompEngine.prototype.synergy = function (party) {
    var s = this.supply(party), total = 0.0;
    for (var i = 0; i < this.synergies.length; i++) {
      var a = this.synergies[i][0], c = this.synergies[i][1], b = this.synergies[i][2];
      total += b * Math.min(s[a] || 0, s[c] || 0);
    }
    return total;
  };

  CompEngine.prototype.explain = function (party, candidate) {
    var s = this.supply(party), terms = [];
    for (var cap in this.reqs) {
      var r = this.reqs[cap];
      var gain = this.capsOf(candidate)[cap] || 0;
      if (!gain) continue;
      var have = s[cap] || 0.0, target = this.target(cap);
      var d = r.weight * (Math.pow(Math.min(1.0, (have + gain) / target), this.gamma)
                          - Math.pow(Math.min(1.0, have / target), this.gamma));
      d += this._floorPenalty(cap, have) - this._floorPenalty(cap, have + gain);
      if (d > 0.05) {
        terms.push({ delta: Math.round(d * 100) / 100, cap: cap,
                     before: have, after: have + gain, target: target });
      }
    }
    return terms.sort(function (x, y) { return y.delta - x.delta; });
  };

  CompEngine.prototype.recommend = function (party, topN, pool) {
    if (topN === undefined) topN = 4;
    var baseFit = this.fitness(party), baseSyn = this.synergy(party);
    var out = [];
    var keys = pool || Object.keys(this.weapons);
    for (var i = 0; i < keys.length; i++) {
      var w = keys[i];
      var dFit = this.fitness(party.concat([w])) - baseFit;
      var dSyn = this.synergy(party.concat([w])) - baseSyn;
      var meta = this.metaPrior[w] || 0.0;
      out.push({
        weapon: w,
        display_name: this.weapons[w].display_name,
        status: this.weapons[w].status,
        d_fitness: dFit, d_synergy: dSyn, meta_prior: meta,
        score: this.alpha * dFit + this.beta * dSyn + this.delta * meta,
      });
    }
    return out.sort(function (x, y) { return y.score - x.score; }).slice(0, topN);
  };

  CompEngine.prototype.weaknesses = function (party, topN) {
    if (topN === undefined) topN = 3;
    var s = this.supply(party), gaps = [];
    for (var cap in this.reqs) {
      var r = this.reqs[cap];
      var have = s[cap] || 0;
      gaps.push({ cap: cap,
                  gap: r.weight * (1 - Math.pow(Math.min(1.0, have / this.target(cap)), this.gamma)),
                  have: have, target: this.target(cap) });
    }
    return gaps.sort(function (x, y) { return y.gap - x.gap; }).slice(0, topN);
  };

  CompEngine.prototype.uncoveredCaps = function (party) {
    var s = this.supply(party), out = [];
    for (var cap in this.reqs) {
      if (this.reqs[cap].weight >= 5 && (s[cap] || 0) / this.target(cap) < 0.5) out.push(cap);
    }
    return out;
  };

  if (typeof module !== "undefined" && module.exports) module.exports = CompEngine;
  else root.CompEngine = CompEngine;
})(typeof self !== "undefined" ? self : this);
