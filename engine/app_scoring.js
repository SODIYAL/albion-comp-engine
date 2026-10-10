/* Composition scoring — JavaScript port of engine/engine.py.
 *
 * SINGLE SOURCE OF MATH: engine/engine.py is authoritative; this file must
 * mirror it exactly and tests/test_js_parity.py verifies that it does
 * (same fitness, same rankings, same forged rosters, across all templates,
 * on random parties). A change to one is a change to both, followed by the
 * parity test.
 *
 * Used two ways:
 *   - inlined into dashboard/index.html by dashboard/build.py (browser —
 *     dashboard/_app.js is rendering-only and calls this engine)
 *   - require()'d by tests/js_parity_runner.js (node)
 *
 * TWO SUPPLIES (mirrors engine.py): coverage / headroom / over-stack read the
 * DRESSED supply (weapon + loadout + worn gear), while the hard-floor term
 * reads the weapon+loadout supply only — Option C (F25/F26), so worn gear
 * can never buy its way past a structural floor.
 *
 * ONE UNIT: dataset targets and soft caps speak person units, the same
 * unit the dressed supply is measured in (the unit re-fit, standing rule 9).
 */
(function (root) {
  "use strict";
  /* Ranking key for a score: quantized to the parity tolerance (1e-9) so
     an exact or last-bit tie never falls to iteration order or the
     toolchain's float noise (mirrors engine.py _qrank). */
  var qrank = function (x) { return Math.floor(x * 1e9 + 0.5); };
  /* display rounding of a delta to two decimals, one rule in both ports
     (mirrors engine.py _round2) */
  var round2 = function (x) { return Math.floor(x * 100 + 0.5) / 100; };
  var nonEmpty = function (o) { if (!o) return false; for (var k in o) return true; return false; };

  /* Mechanics-affected capability families (MECHANICS_TODO.md): mirrors
     AOE_ESCALATION_CAPS / RESILIENCE_CAPS in engine.py. The AoE
     Escalation applies per spell (Q10): a bundle takes it only when the
     game files flag its spell (the loadout's slot_escal). */
  var AOE_ESCALATION_CAPS = ["burst_aoe"];
  var RESILIENCE_CAPS = ["burst_st", "execute"];
  /* Two builds of one candidate whose pick values differ by less than
     this are a tie and the earlier build keeps it (mirrors engine.py
     PICK_TIE_EPS): a last-bit float difference must not pick another
     combo. */
  var PICK_TIE_EPS = 1e-9;
  /* The game seats at most 20 players in one party; a zerg is several
     parties, each forged at its own plan (mirrors engine.py PARTY_CAP).
     forge (and its refresh), replaceOptions and refine refuse a party
     past the cap with the same message as engine.py party_cap_message;
     scoring a manual roster of any size stays allowed. */
  var PARTY_CAP = 20;
  function partyCapMessage(n) {
    return "a single party seats at most " + PARTY_CAP + " players, " + n +
      " asked: forge a zerg party by party";
  }
  function refusePastCap(n) {
    if (n > PARTY_CAP) throw new Error(partyCapMessage(n));
  }

  var KEY_TIER_RX = /^T\d+_/;
  var KEY_ENCH_RX = /@\d+$/;
  function keyForm(key) {
    /* A gear key stripped of tier and enchant: 'T7_POTION_REVIVE@2' ->
       'POTION_REVIVE'. Mirrors engine.py _key_form / builds_lib.key_form. */
    return String(key).trim().toUpperCase()
      .replace(KEY_ENCH_RX, "").replace(KEY_TIER_RX, "");
  }

  function mergeMax(always, bundles) {
    /* One item's capability total for a set of chosen bundles: per
       capability the largest of `always` and the bundles (a sheet row
       scores the weapon's or gear item's total with its spell equipped).
       Mirrors engine.py _merge_max. */
    var extra = {}, c, k;
    for (c in always) extra[c] = always[c];
    for (k = 0; k < bundles.length; k++) {
      var b = bundles[k];
      for (c in b) if (!(c in extra) || b[c] > extra[c]) extra[c] = b[c];
    }
    return extra;
  }

  function present(v) {
    /* A dataset value read the way engine.py reads it: an empty object or
       array is absent, as Python's falsy {} and []. */
    if (!v) return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === "object") { for (var k in v) return true; return false; }
    return true;
  }

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
    /* Redundancy weight (rho), viability prior weight and headroom slope —
       all default 0 so an older dataset scores as it used to.
       Mirrors engine.py __init__. */
    this.rho = w.rho || 0.0;
    this.viabilityW = w.viability || 0.0;
    this.headroom = w.headroom || 0.0;
    /* pair-aware prior (weights.meta_pair; mirrors engine.py): blend weight
       for the best observed partner; absent = 0 = pure solo */
    this.metaPairW = w.meta_pair || 0.0;
    this.metaPairs = this.scoring.meta_pairs || {};
    this.metaPrior = this.scoring.meta_prior || {};
    var mpKeys = Object.keys(this.metaPrior);
    this.metaBucketed = mpKeys.length > 0 &&
      mpKeys.every(function (k) { return k === "small" || k === "mid" || k === "large"; });
    /* MATCHMAKING POOL PRIOR (mirrors engine.py): meta_pools {content:
       {pool: {sizes, solo, pairs}}}; at a size inside a pool of the content
       the meta term reads the pool's own tables, weighted pool_delta_x x
       delta (setContent). Absent = none. */
    this.metaPools = this.scoring.meta_pools || {};
    this.poolDeltaX = (w.pool_delta_x === undefined) ? 1.0 : w.pool_delta_x;
    this._deltaBase = this.delta;
    this.synergies = (this.scoring.capability_synergies || []).map(function (s) {
      return [s.a, s.b, s.bonus];
    });
    this.mechanics = data.mechanics || {};
    /* Gear capability sheets — full-build members (mirrors engine.py). */
    this.gear = data.gear || {};
    /* Tier-agnostic index for gearKey(), built only for UNAMBIGUOUS
       tier-stripped forms — a form two curated items share is dropped so the
       lookup fails rather than guesses. Mirrors engine.py __init__. */
    var _forms = {}, _gk;
    for (_gk in this.gear) {
      var _f = keyForm(_gk);
      if (_forms[_f] === undefined) _forms[_f] = [];
      _forms[_f].push(_gk);
    }
    this._gearAlias = {};
    for (var _ff in _forms) {
      if (_forms[_ff].length === 1 && !this.gear[_ff]) {
        this._gearAlias[_ff] = _forms[_ff][0];
      }
    }
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
    /* SUPER-ADDITIVE DUPLICATES (mirrors engine.py): gear key ->
       minimum copies that cover each other's SELF-COST, resolved from the
       cost's evidence spell through a VERIFIED interaction record declaring
       self_cost_offset_min_copies. Cancels a cost, never adds supply. */
    this.costOffsets = {};
    var gKeys = Object.keys(this.gear || {}).sort();
    for (var gi2 = 0; gi2 < gKeys.length; gi2++) {
      var gRec = this.gear[gKeys[gi2]] || {};
      var ev = gRec.self_cost_evidence || {};
      for (var ecap in ev) {
        var irec = this.interactions[ev[ecap]] || {};
        var minCopies = irec.self_cost_offset_min_copies;
        if (irec.confidence === "verified" && minCopies) {
          var cur = this.costOffsets[gKeys[gi2]];
          this.costOffsets[gKeys[gi2]] =
            (cur === undefined || minCopies < cur) ? minCopies : cur;
        }
      }
    }
    /* Composition layer (composition.yaml -> dataset): forge constraints,
       duplication, viability, size physics. Mirrors engine.py __init__. */
    var comp = data.composition || {};
    this.compCfg = comp;
    var rolesCfg = comp.roles || {};
    var byHint = rolesCfg.by_hint || {};
    var overrides = rolesCfg.overrides || {};
    /* The ROLE BOOK (roles-design.md, mirrors engine.py): fine roles with
       evidence-cited membership; weapons carry role_menu. Feeds
       detectRole/roleAdvisory (DESCRIPTIVE, never scoring) and the coarse
       role class below. */
    this.rolesBook = {};
    var rb = data.roles || [];
    for (var ri = 0; ri < rb.length; ri++) this.rolesBook[rb[ri].id] = rb[ri];
    /* Coarse role class: composition override > the class of the primary
       SEAT (first uniformed menu role, the detectRole resolution) > the
       sheet's role_hint. Mirrors engine.py. */
    this.roleClass = {};
    var k;
    for (k in this.weapons) {
      var seatCls = this._primarySeatClass(k);
      this.roleClass[k] = overrides[k] !== undefined ? overrides[k]
        : (seatCls !== null ? seatCls
           : (byHint[this.weapons[k].role_hint] !== undefined
              ? byHint[this.weapons[k].role_hint] : "dps"));
    }
    /* Typed gear-carried effects: item id -> effect ids (mirrors
       engine.py _item_effects); gearEffects keeps the records for
       display-name lookup. */
    this.itemEffects = {};
    this.gearEffects = {};
    var ge = data.gear_effects || [];
    for (var gi2 = 0; gi2 < ge.length; gi2++) {
      this.gearEffects[ge[gi2].id] = ge[gi2];
      var its = ge[gi2].items || [];
      for (var ii = 0; ii < its.length; ii++) {
        if (its[ii].id) {
          (this.itemEffects[its[ii].id] = this.itemEffects[its[ii].id] || [])
            .push(ge[gi2].id);
        }
      }
    }
    /* Capability predicates — COMBO-AWARE (mirrors
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
    /* Flag predicate `primary_heal` (mirrors
       engine.py): band minima counted from the static per-weapon
       full_healer flag (high healing on the E; the E is combo-independent,
       so every combo of a full healer qualifies). Routed through the same
       pred machinery so the forge needs no special case. */
    this.PRIMARY_HEAL = "primary_heal";
    var phMembers = {};
    for (k in this.weapons) {
      if (this.weapons[k].full_healer) phMembers[k] = true;
    }
    this.predMembers[this.PRIMARY_HEAL] = phMembers;
    /* plan-tool flag predicate (seat skeleton; mirrors engine.py
       STANDOFF): the E is a standoff tool, combo-independent */
    this.STANDOFF = "standoff";
    var soMembers = {};
    for (k in this.weapons) {
      if ((this.weapons[k].style_fit || {}).standoff_e) soMembers[k] = true;
    }
    this.predMembers[this.STANDOFF] = soMembers;
    this._predCache = {};
    this._predPossibleCache = {};
    var dup = comp.duplication || {};
    this.dupFreeDefault = (dup.free_copies_default === undefined) ? 1 : dup.free_copies_default;
    this.dupMaxSmall = (dup.max_copies_default_small === undefined) ? 1e9 : dup.max_copies_default_small;
    this.dupMaxLarge = (dup.max_copies_default_large === undefined) ? 1e9 : dup.max_copies_default_large;
    this.dupPerWeapon = dup.per_weapon || {};
    this.dupPwMinSize = (dup.per_weapon_min_size === undefined) ? 10 : dup.per_weapon_min_size;
    /* GENERATED copy allowances per style x band and the seat skeleton
       (derive_skeletons.py; mirrors engine.py): setContent
       resolves one copy cell into dupPerWeapon and one seat row into
       _seatTyp; a dataset without them keeps the hand list and no gate. */
    this._dupPerWeaponBase = this.dupPerWeapon;
    this.dupCells = dup.per_weapon_cells || {};
    this.skeleton = comp.skeleton || {};
    this._seatTyp = {};
    this.groups = comp.groups || [];
    this.groupsOf = {};
    /* members of derived NON-STACKING groups (shared kit priced
       count-once — the cursed line): their group-band slots are EARNED
       (see the generation-fit gate) */
    this.nonstackMembers = {};
    for (var gi = 0; gi < this.groups.length; gi++) {
      var gw = this.groups[gi].weapons || [];
      for (var gj = 0; gj < gw.length; gj++) {
        (this.groupsOf[gw[gj]] = this.groupsOf[gw[gj]] || []).push(gi);
        if (this.groups[gi].nonstacking) this.nonstackMembers[gw[gj]] = true;
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
    /* Candidate dressing is ON by default — production behavior.
       setDressing(false) is a VALIDATION affordance (V3-W symmetric
       weapon-only comparisons; mirrors engine.py dress_candidates). */
    this.dressCandidates = true;
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
    /* the pool's own prior and its weight (mirrors engine.py); outside
       every pool that carries one the size bucket's prior stands at delta */
    this.priorPool = this._priorPool(content, this.size);
    this.delta = this.priorPool !== null ? this._deltaBase * this.poolDeltaX : this._deltaBase;
    this._carrierCapsCache = null;   /* carrierCaps() memo (size-keyed) */
    /* DEMAND RAMP (mirrors engine.py set_content):
       a row with ramp {none_until, full_at} is dropped at sizes <=
       none_until, grows linearly to its measured value at full_at, and
       proportionally beyond. */
    this._ramp = {};
    /* MATCHMAKING POOL ROWS (mirrors engine.py): rows fitted on one pool's
       own winners replace the base row's numbers at a size inside the
       pool, scaled from the pool's ref_size; a `none` row is no
       requirement there; weights stay the base row's. */
    this._rowRef = {};
    var poolR = this._poolRows(this.size);
    this.poolKey = poolR ? poolR.key : null;
    this.reqs = {};
    for (var capR in this.template.requirements) {
      var rowR = this.template.requirements[capR];
      var prR = poolR ? poolR.requirements[capR] : undefined;
      if (prR !== undefined) {
        if (prR.none) continue;
        var mergedR = {};
        for (var kR in rowR) if (kR !== "ramp") mergedR[kR] = rowR[kR];
        for (var kP in prR) if (kP !== "none") mergedR[kP] = prR[kP];
        rowR = mergedR;
        this._rowRef[capR] = poolR.ref_size;
      }
      if (rowR.ramp) {
        var fR = rampFactor(rowR.ramp, this.size);
        if (fR <= 0) continue;
        this._ramp[capR] = fR;
      }
      this.reqs[capR] = rowR;
    }
    this.floors = this.template.hard_floors || {};
    /* Playstyle overlay: multiplies capability WEIGHTS only (mirrors
       engine.py). */
    this.style = style || "balanced";
    var styles = this.data.styles || {};
    this.styleMults = (styles[this.style] || {}).multipliers || {};
    /* Mechanics overlay: party-size counts come from the piecewise absolute
       size table (size_physics), never a linear extrapolation. The
       Resilience ratio is factorized into a STYLE factor (never clamped)
       and a SIZE factor (clamped at 1.0 above stBoostMaxSize). Mirrors
       engine.py set_content. */
    var styleMech = (styles[this.style] || {}).mechanics || {};
    var baseMech = (styles.balanced || {}).mechanics || {};
    var multNow = this._countMult(this.size);
    var multBase = this._countMult(this.baseSize);
    var grown = function (p, m) { return p ? p * m : p; };
    /* Clump anchors + AoE geometry config (mirrors engine.py
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
    /* the in-game AoE Escalation ratio (mirrors engine.py): _eff applies
       it to a bundle only when the game files flag the bundle's spell */
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
    /* Resilience-Penetration context (a partial rebate; mirrors
       engine.py): the Focus-Fire DR at this style's grown focus count; a
       weapon with resil_pen p is rebated (1 - DR*(1-p)) / (1 - DR) on its
       burst_st/execute supply in _eff. */
    this._penDr = 0.0;
    var focusNow = grown(styleMech.focus_attackers, multNow);
    if (focusNow) this._penDr = 1.0 - this._resilienceEff(focusNow);
    /* Scaled targets/soft caps, styled weights (mirrors engine.py).
       PER-STYLE TARGET MODIFIERS (styles.yaml target_mults): weight
       multipliers say what a style VALUES, these say HOW MUCH OF IT it
       needs. Target and soft cap scale together so the headroom band keeps
       its shape; hard floors do NOT scale. Default is identity — every
       style ships {} until a value is set (curation judgment). */
    this.targetMults = (styles[this.style] || {}).target_mults || {};
    this._targets = {}; this._softs = {}; this._weights = {}; this._mins = {};
    for (var cap2 in this.reqs) {
      var r = this.reqs[cap2];
      var tm = this.targetMults[cap2];
      tm = (tm === undefined) ? 1.0 : tm;
      var sz2 = (cap2 in this._ramp) ? this._ramp[cap2]
        : (r.scales ? this.size / (this._rowRef[cap2] || this.baseSize) : 1.0);
      this._targets[cap2] = tm * r.target * sz2;
      this._softs[cap2] = tm * r.soft_cap * sz2;
      /* BARE MINIMUM beside the target (target is the median: the four-stage
         board; mirrors engine.py _mins): a median-fitted content row
         carries `min`, a row still on the old 0.9 x least fit IS its
         minimum. Display only — no scoring term reads it. */
      this._mins[cap2] = tm * ((r.min === undefined || r.min === null) ? r.target : r.min) * sz2;
      var m2 = this.styleMults[cap2];
      this._weights[cap2] = r.weight * (m2 === undefined ? 1.0 : m2);
    }
    /* STYLE x SIZE ROWS (style_bands.yaml; TARGET IS THE MEDIAN; mirrors
       engine.py set_content): at
       min_size+ the harvest's per-band target (the TYPICAL winner, p50),
       min (p10) and soft cap replace the content row's, scaled from
       ref_size; a soft-cap-only row keeps the content target; rows are
       measured per style, so target_mults do not stack on them.
       `balanced` reads the pooled cell when the board carries one.
       _targetSrc records per capability where the target came from —
       display provenance only. */
    this.bandRow = null; this.bandKey = null;
    var fitStat = ((this.template.fit || {}).stat) || "minimum";
    var contentSrc = (fitStat === "median") ? "content" : "content_min";
    this._targetSrc = {};
    for (var capS in this.reqs) this._targetSrc[capS] = contentSrc;
    for (var capP in this._rowRef) this._targetSrc[capP] = "harvest";   /* the pool's own measured median */
    var bands = this.data.style_bands || {};
    var bstyle = (bands.bands || {})[this.style];
    if (bstyle && this.size >= (bands.min_size || 10)) {
      for (var bk in bstyle) {
        var brow = bstyle[bk];
        if (brow.sizes[0] <= this.size && this.size <= brow.sizes[1]) {
          this.bandRow = brow; this.bandKey = bk; break;
        }
      }
    }
    if (this.bandRow) {
      var bref = this.bandRow.ref_size;
      var harvestSrc = this.bandRow.borrowed_from ? "harvest_borrowed" : "harvest";
      for (var capB in this.bandRow.requirements) {
        if (!(capB in this._targets)) continue;
        /* a matchmaking pool's own row outranks the style x size row
           (mirrors engine.py set_content) */
        if (capB in this._rowRef) continue;
        var bv = this.bandRow.requirements[capB];
        if (bv.target !== undefined && bv.target !== null) {
          this._targets[capB] = bv.target * this.size / bref;
          this._softs[capB] = bv.soft_cap * this.size / bref;
          this._mins[capB] = ((bv.min === undefined || bv.min === null) ? bv.target : bv.min) * this.size / bref;
          this._targetSrc[capB] = harvestSrc;
        } else {
          var softB = bv.soft_cap * this.size / bref;
          if (softB > this._targets[capB]) this._softs[capB] = softB;
        }
      }
    }
    /* OPTIONAL capabilities — mirrors engine.py
       set_content. Bringing one still earns its coverage; not bringing it is
       not a hole. Every fitness term is already zero at zero supply, so this
       is a DENOMINATOR-only rule: it can only leave maxFitness(), never
       fitness(). A hard floor would break that identity — incompatible. */
    this.optional = {};
    for (var capO in this.reqs) {
      if (this.reqs[capO].optional) {
        if (capO in this.floors) {
          throw new Error("template '" + this.content + "': " + capO +
            " marked optional but carries a hard floor — a floor is charged " +
            "at zero supply, so the capability is mandatory by construction");
        }
        this.optional[capO] = true;
      }
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
    /* No cost gate (mirrors engine.py): the
       crystal gate is retired; anti_zone demand carries the physics. */
    this._suggest = [];
    for (i = 0; i < this.pool.length; i++) {
      if (!excl[this.pool[i]]) this._suggest.push(this.pool[i]);
    }
    /* Style-fit suggestion gate (mirrors engine.py:
       style selection IS build intent; unfit weapons leave suggestions,
       never scoring; balanced gates nothing). */
    this._styleUnfit = {};
    if (this.style === "brawl" || this.style === "clap" ||
        this.style === "kite" || this.style === "brawl_clap" ||
        this.style === "clap_kite") {
      var sBand = this._fitBand();
      var anyUnfit = false;
      for (i = 0; i < this.pool.length; i++) {
        var sfw = this.weapons[this.pool[i]].style_fit;
        if (sfw && sfw.fit[this.style] &&
            sfw.fit[this.style][sBand] === "unfit") {
          this._styleUnfit[this.pool[i]] = true;
          anyUnfit = true;
        }
      }
      if (anyUnfit) {
        var kept = [];
        for (i = 0; i < this._suggest.length; i++) {
          if (!this._styleUnfit[this._suggest[i]]) kept.push(this._suggest[i]);
        }
        this._suggest = kept;
      }
    }
    /* Generation-fit gate (validation round 3, mirrors
       engine.py): a DEFAULT generated comp fields damage picks the
       derivation says FIT — "situational" stays a manual pick (scores
       normally, never flagged). DPS role only; balanced requires fits for
       at least one style at the band; trio gates nothing. */
    this._genSituational = {};
    var IDS = ["brawl", "clap", "kite", "brawl_clap", "clap_kite"];
    var gBand = this._fitBand();
    if (gBand !== "trio") {
      var anySit = false;
      for (i = 0; i < this.pool.length; i++) {
        var gw = this.pool[i];
        var gRole = this.roleOf(gw);
        var gsf = this.weapons[gw].style_fit;
        if (!gsf) continue;
        var gOk;
        if (gRole === "dps") {
          /* a content that keeps full single-target value (st_full_value:
             roads, the Dragon Portal) says single-target kill pressure is
             a win condition at its sizes: at the gang band a single-scale
             carry's situational verdict earns a default slot; unfit still
             bars (mirrors engine.py). */
          var gEarned = (gBand === "gang" && this.template.st_full_value)
            ? { fits: true, situational: true } : { fits: true };
          if (IDS.indexOf(this.style) >= 0) {
            gOk = !!(gsf.fit[this.style] && gEarned[gsf.fit[this.style][gBand]]);
          } else {
            gOk = false;
            for (var si2 = 0; si2 < IDS.length; si2++) {
              if (gsf.fit[IDS[si2]] && gEarned[gsf.fit[IDS[si2]][gBand]]) {
                gOk = true;
                break;
              }
            }
          }
        } else if (gRole === "healer" && gBand === "group") {
          /* validation round 4: a healer unfit at group for EVERY style (the
             single-ally-heal-E class) never generates, balanced included;
             gang slots stay open (mirrors engine.py). */
          gOk = false;
          for (var si3 = 0; si3 < IDS.length; si3++) {
            if (!gsf.fit[IDS[si3]] || gsf.fit[IDS[si3]][gBand] !== "unfit") {
              gOk = true;
              break;
            }
          }
        } else if (this.nonstackMembers[gw] && gBand === "group") {
          /* a non-stacking budget slot (the cursed line — its shared Q
             priced count-once) is EARNED at group scale: above 15 the
             cursed weapons fielded are Lifecurse, Damnation and Rotcaller
             (curation judgment on the observed comps). The
             derivation demotes debuff-less members to situational at
             group for every style; the dps fits-rule then bars them from
             DEFAULT generation, balanced included. Manual picks score
             normally, never flagged (mirrors engine.py). */
          if (IDS.indexOf(this.style) >= 0) {
            gOk = gsf.fit[this.style] && gsf.fit[this.style][gBand] === "fits";
          } else {
            gOk = false;
            for (var si4 = 0; si4 < IDS.length; si4++) {
              if (gsf.fit[IDS[si4]] && gsf.fit[IDS[si4]][gBand] === "fits") {
                gOk = true;
                break;
              }
            }
          }
        } else {
          continue;
        }
        if (!gOk) { this._genSituational[gw] = true; anySit = true; }
      }
      if (anySit) {
        var kept2 = [];
        for (i = 0; i < this._suggest.length; i++) {
          if (!this._genSituational[this._suggest[i]]) kept2.push(this._suggest[i]);
        }
        this._suggest = kept2;
      }
    }
    /* Pool-fielded gate (mirrors engine.py): at a size inside a
       matchmaking pool that carries `pool_fielded`, a weapon its dominant
       winners do not field leaves the suggestion pool; scoring is never
       blocked. No list for the size: nothing gated. */
    this._unfielded = {};
    var fielded = this._poolFielded(this.size);
    /* THE FIELDED GATE AT 10+ (composition.skeleton.fielded; mirrors
       engine.py): outside a pool's list, the weapons the declared style's
       killer parties of 10+ field in the size's band, barred from
       suggestions and generation only */
    if (!fielded) fielded = this._openFielded();
    if (fielded) {
      var kept3 = [];
      for (i = 0; i < this.pool.length; i++) {
        if (!fielded[this.pool[i]]) this._unfielded[this.pool[i]] = true;
      }
      for (i = 0; i < this._suggest.length; i++) {
        if (!this._unfielded[this._suggest[i]]) kept3.push(this._suggest[i]);
      }
      this._suggest = kept3;
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
    /* Style role-band overrides (styles.yaml
       constraint_overrides — mirrors engine.py): a listed key REPLACES the
       base band's entry; unlisted keys keep the base band. First matching
       row wins. */
    if (this._band !== null) {
      var sOv = (styles[this.style] || {}).constraint_overrides || [];
      for (i = 0; i < sOv.length; i++) {
        var oRow = sOv[i];
        if ((oRow.min_size || 0) <= this.size &&
            this.size <= ((oRow.max_size === undefined) ? 1e9 : oRow.max_size)) {
          var merged = {};
          for (var bk in this._band) merged[bk] = this._band[bk];
          for (var ok2 in oRow) {
            if (ok2 !== "min_size" && ok2 !== "max_size") merged[ok2] = oRow[ok2];
          }
          this._band = merged;
          break;
        }
      }
    }
    /* Size-based style minima (styles.yaml role_min_per_players; mirrors
       engine.py). Floor(size / per), with no inherited maximum. Small
       parties keep their existing band until they reach one complete
       group. */
    if (this._band !== null) {
      var rolePer = (styles[this.style] || {}).role_min_per_players || {};
      for (var ratioRole in rolePer) {
        if (this.size >= rolePer[ratioRole]) {
          this._band = Object.assign({}, this._band);
          this._band[ratioRole] = {min: Math.floor(this.size / rolePer[ratioRole])};
        }
      }
    }
    /* TYPICAL role counts (F31; mirrors engine.py):
       the harvest p50 per exact size (composition.role_typical, GENERATED
       by derive_role_counts.py) laid onto the band as `typical`. The forge
       generates a body beyond it only when a minimum only that role can
       meet still demands one (_typOk). Generation-only: manual parties
       always score. */
    if (this._band !== null) {
      var typRows = this._roleTypical();
      for (var typRole in typRows) {
        this._band = Object.assign({}, this._band);
        var typRule = Object.assign({}, this._band[typRole] || {});
        typRule.typical = typRows[typRole];
        this._band[typRole] = typRule;
      }
    }
    /* SEAT SKELETON (mirrors engine.py set_content): the
       typical count of every PRIMARY SEAT for this style and size and the
       copy-allowance cell for this style and band (composition.skeleton /
       duplication.per_weapon_cells, GENERATED by derive_skeletons.py).
       Generation-only: manual parties always score. */
    this._seatTyp = this._seatTypical();
    this.dupPerWeapon = this._dupCell();
    /* PLAN TOOLS (mirrors engine.py): the typical standoff
       count of the declared style's winners is a generation MINIMUM */
    if (this._band !== null) {
      var planRows = this._planTypical();
      for (var planTool in planRows) {
        this._band = Object.assign({}, this._band);
        this._band[planTool] = { min: planRows[planTool] };
      }
    }
    /* GENERATED BAND MINIMA (composition.skeleton.minima; mirrors
       engine.py): the ranged-AoE core minimum is the typical carrier
       count of the declared style's winners in the band; a row without
       the key sets no minimum; a dataset without the table keeps the
       band as it stands. */
    if (this._band !== null) {
      var bandMin = this._bandMinima();
      if (bandMin !== null) {
        this._band = Object.assign({}, this._band);
        for (i = 0; i < bandMin.keys.length; i++) {
          var minKey = bandMin.keys[i];
          if (Object.prototype.hasOwnProperty.call(bandMin.row, minKey))
            this._band[minKey] = { min: bandMin.row[minKey] };
          else
            delete this._band[minKey];
        }
      }
    }
    /* NEED PROFILES (dataset need_profiles) — mirrors
       engine.py: fine-seat bands + function coverage minima for the
       FORGE, scaled by size/reference_size (half-up, the pinned
       rounding rule) and armed at min_size. SEAT keys count a weapon's
       PRIMARY menu seat; FUNCTION keys count any primary/secondary
       membership. Generation-only: manual parties always score. */
    this._profileMin = {}; this._profileMax = {};
    this._profileMembers = {}; this._profilePrimary = {};
    var prof = this.data.need_profiles || {};
    var hasProf = false;
    for (var pk0 in prof) { hasProf = true; break; }
    if (hasProf &&
        this.size >= ((prof.min_size === undefined) ? 15 : prof.min_size)) {
      var pRef = (prof.reference_size === undefined) ? 20 : prof.reference_size;
      var pRules = {}, rk;
      var pDef = prof.defaults || {};
      for (rk in pDef) pRules[rk] = pDef[rk];
      var pOvr = ((prof.overrides || {})[this.content]) || {};
      for (rk in pOvr) pRules[rk] = pOvr[rk];
      for (rk in pRules) {
        var pRule = pRules[rk];
        if (pRule.min !== undefined) {
          var pMn = Math.floor(pRule.min * this.size / pRef + 0.5);
          if (pMn > 0) this._profileMin[rk] = pMn;
        }
        if (pRule.max !== undefined)
          this._profileMax[rk] = Math.floor(pRule.max * this.size / pRef + 0.5);
      }
      var PROF_FUNCS = ["pierce", "anti_heal", "purge", "shield_break"];
      for (var pwk in this.weapons) {
        var pRec = this.weapons[pwk];
        var pMenu = pRec.role_menu || [];
        var pSec = pRec.role_menu_secondary || [];
        var pContrib = {}, pAny = false;
        if (pMenu.length && (pMenu[0] in this._profileMin ||
                             pMenu[0] in this._profileMax)) {
          pContrib[pMenu[0]] = true; pAny = true;
        }
        for (var pfi = 0; pfi < PROF_FUNCS.length; pfi++) {
          var pf = PROF_FUNCS[pfi];
          if (!(pf in this._profileMin) && !(pf in this._profileMax)) continue;
          if (pMenu.indexOf(pf) >= 0 || pSec.indexOf(pf) >= 0) {
            pContrib[pf] = true; pAny = true;
          }
        }
        if (pAny) this._profileMembers[pwk] = pContrib;
        if (pMenu.length) this._profilePrimary[pwk] = pMenu[0];
      }
    }
    this._extrasCache = {};
    this._unchargedCache = {};
    this._gearCache = {};
    this._defaultCache = {};
    this._nsCache = {};
    this._variantCache = {};
    this._variantFallback = {};
    this._dressedCache = {};
  };

  CompEngine.prototype.setDressing = function (enabled) {
    /* Validation affordance (V3-W; mirrors engine.py
       set_dressing): when OFF, every CANDIDATE evaluates naked —
       kitVariants yields [["v0", null]] for all weapons, _dressedExtras
       aliases the weapon-only combo vectors, and _comboScoreDressed's
       identity check routes into _comboScore. Same formula, no second
       scoring path. Clears the dressed caches so vectors built under the
       other setting cannot leak. */
    this.dressCandidates = !!enabled;
    this._variantCache = {};
    this._variantFallback = {};
    this._dressedCache = {};
  };

  CompEngine.prototype._withProfile = function (w, contrib) {
    /* predicate contribution merged with the weapon's need-profile
       memberships (mirrors the engine.py frozenset unions). */
    var pm = this._profileMembers[w];
    if (!pm) return contrib;
    var out = {}, k;
    for (k in contrib) out[k] = true;
    for (k in pm) out[k] = true;
    return out;
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
    var v = this.template.validated_sizes;
    if (v === undefined || v === null) v = [this.baseSize];
    return v.indexOf(this.size) === -1;
  };

  CompEngine.prototype.sizeBucket = function () {
    /* Participant axis = 2 x party size (mirrors engine.py size_bucket).
       Keys the GENERATED meta prior through metaOf() at ROSTER size; the
       dashboard's usage strip keys off PLAN() instead, deliberately. */
    var n = 2 * this.size;
    return n < 12 ? "small" : n <= 30 ? "mid" : "large";
  };

  CompEngine.prototype.target = function (cap) {
    return this._targets[cap];
  };

  CompEngine.prototype.softCap = function (cap) {
    return this._softs[cap];
  };

  /* the bare minimum winners get away with (harvest p10 / least fitted
     comp), scaled like the target — the board's red/orange line (target
     is the median). Mirrors engine.py target_min. Display only. */
  CompEngine.prototype.targetMin = function (cap) {
    return this._mins[cap];
  };

  /* display provenance of a capability's target (mirrors engine.py
     target_source): harvest | harvest_borrowed | content | content_min */
  CompEngine.prototype.targetSource = function (cap) {
    return this._targetSrc[cap];
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
  /* class of the weapon's primary SEAT role — first role_menu entry with a
     chest uniform (function roles have none); null when unseated.
     Mirrors engine.py _primary_seat_class. */
  CompEngine.prototype._primarySeatClass = function (weapon) {
    var menu = this.weapons[weapon].role_menu || [];
    for (var i = 0; i < menu.length; i++) {
      var rec = this.rolesBook[menu[i]] || {};
      var chest = (rec.uniform || {}).chest || [];
      if (chest.length) return rec["class"] === undefined ? null : rec["class"];
    }
    return null;
  };
  /* the weapon's PRIMARY SEAT: the first role_menu entry with a chest
     uniform, the read roleClass derives from (mirrors engine.py seat_of);
     null when the book seats it nowhere. */
  CompEngine.prototype.seatOf = function (weapon) {
    var menu = (this.weapons[weapon] || {}).role_menu || [];
    for (var i = 0; i < menu.length; i++) {
      var rec = this.rolesBook[menu[i]] || {};
      if (((rec.uniform || {}).chest || []).length) return menu[i];
    }
    return null;
  };

  /* Role layer (roles-design.md; mirrors engine.py) —
     DESCRIPTIVE: no scoring or generation path reads it. */
  CompEngine.prototype._chestClass = function (gearId) {
    if (!gearId) return null;
    var parts = String(gearId).split("_");
    if (parts.indexOf("PLATE") >= 0) return "plate";
    if (parts.indexOf("LEATHER") >= 0) return "leather";
    if (parts.indexOf("CLOTH") >= 0) return "cloth";
    return null;
  };

  CompEngine.prototype.detectRole = function (weapon, chest) {
    /* SEAT roles carry a chest uniform; FUNCTION roles (pierce / purge /
       anti_heal) have none and ride along in `functions` — kits are
       judged against seats only (mirrors engine.py detect_role,
       identical keys; parity carries the advisory). */
    var menu = this.weapons[weapon].role_menu || [];
    var menu2 = (this.weapons[weapon].role_menu_secondary || []).slice();
    if (!menu.length)
      return { role: null, "class": this.roleOf(weapon), kit_match: null,
               functions: [], secondary: menu2 };
    var self = this;
    var uniOf = function (rid) {
      var book = (((self.rolesBook[rid] || {}).uniform) || {}).chest || [];
      return book.length ? self._chestUniform(rid, weapon) : [];
    };
    var seats = menu.filter(function (r) { return uniOf(r).length > 0; });
    var functions = menu.filter(function (r) { return !uniOf(r).length; });
    var rid, rec;
    if (!seats.length) {
      rid = menu[0];
      rec = this.rolesBook[rid] || {};
      return { role: rid, "class": rec["class"] || this.roleOf(weapon),
               kit_match: null,
               functions: functions.filter(function (r) { return r !== rid; }),
               secondary: menu2 };
    }
    var cc = this._chestClass(chest);
    if (cc === null) {
      rid = seats[0];
      rec = this.rolesBook[rid] || {};
      return { role: rid, "class": rec["class"] || this.roleOf(weapon),
               kit_match: null, functions: functions, secondary: menu2 };
    }
    for (var i = 0; i < seats.length; i++) {
      if (uniOf(seats[i]).indexOf(cc) >= 0) {
        rec = this.rolesBook[seats[i]] || {};
        return { role: seats[i], "class": rec["class"], kit_match: true,
                 functions: functions, secondary: menu2 };
      }
    }
    rid = seats[0];
    rec = this.rolesBook[rid] || {};
    return { role: rid, "class": rec["class"], kit_match: false,
             functions: functions, secondary: menu2 };
  };

  CompEngine.prototype.roleAdvisory = function (party, chests) {
    /* Descriptive roster role read: members + tally + flags
       (off_role_kit per member; no_engage_tank at group sizes with 2+
       frontliners and no clump maker). Mirrors engine.py role_advisory. */
    chests = chests || {};
    var members = [], tally = {}, flags = [], i, m;
    for (i = 0; i < party.length; i++) {
      m = this.detectRole(party[i], chests[i]);
      m = { role: m.role, "class": m["class"], kit_match: m.kit_match,
            functions: m.functions, secondary: m.secondary,
            weapon: party[i],
            carrying: (this.itemEffects[chests[i]] || []).slice() };
      members.push(m);
      var key = m.role || m["class"];
      tally[key] = (tally[key] || 0) + 1;
    }
    for (i = 0; i < members.length; i++) {
      m = members[i];
      if (m.kit_match === false) {
        var uni = (((this.rolesBook[m.role] || {}).uniform) || {}).chest || [];
        flags.push({ kind: "off_role_kit", weapon: m.weapon, role: m.role,
                     detail: "no role this weapon plays wears that chest; " +
                             "its " + m.role + " uniform is " +
                             uni.join("/") });
      }
    }
    if (this.size >= 10) {
      var front = 0, engage = 0;
      for (i = 0; i < members.length; i++) {
        m = members[i];
        var cls = m.role ? (this.rolesBook[m.role] || {})["class"]
          : m["class"];
        if (cls === "frontline") front++;
        var menu = this.weapons[m.weapon].role_menu || [];
        if (menu.indexOf("engage_tank") >= 0) engage++;
      }
      if (front >= 2 && !engage)
        flags.push({ kind: "no_engage_tank",
                     detail: front + " frontliner(s), none can make a " +
                             "clump — no engage tank" });
    }
    return { members: members, tally: tally, flags: flags };
  };

  function rampFactor(rp, size) {
    /* mirrors engine.py _ramp_factor */
    var lo = +rp.none_until, hi = +rp.full_at;
    if (size <= lo) return 0.0;
    if (size < hi) return (size - lo) / (hi - lo);
    return size / hi;
  }

  CompEngine.prototype.isStyleUnfit = function (weapon) {
    /* Unfit for the DECLARED style at this size band — bars suggestions
       only, never scoring (mirrors engine.py is_style_unfit). */
    return !!this._styleUnfit[weapon];
  };

  CompEngine.prototype.isUnfielded = function (weapon) {
    /* The winners the size reads from do not field the weapon: a
       matchmaking pool's list, else at 10+ the declared style's band list
       — bars suggestions only (mirrors engine.py is_unfielded). */
    return !!this._unfielded[weapon];
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

  CompEngine.prototype._eff = function (caps, delivery, pen, escal) {
    /* escal: the bundle's spell's AoE escalation stamp (mirrors engine.py
       _eff): the AOE_ESCALATION_CAPS take the in-game ratio only when it
       is a factor above 0; 0 (not flagged) and null (no record, unknown)
       take none; undefined (no stamp passed) fails closed. */
    var out = {}, m, v;
    for (var c in caps) {
      v = caps[c] / this.scoreUnit;
      m = this.mechMults[c];
      if (m === undefined) m = 1.0;
      if (AOE_ESCALATION_CAPS.indexOf(c) >= 0) {
        if (escal === undefined)
          throw new Error(c + ": a bundle read without its spell's AoE escalation "
                          + "stamp (slot_escal); rebuild the dataset");
        if (!escal) m = 1.0;
      }
      v = v * m;
      if (pen && this._penDr > 0.0 && RESILIENCE_CAPS.indexOf(c) >= 0)
        v *= (1.0 - this._penDr * (1.0 - pen)) / (1.0 - this._penDr);
      if (delivery !== undefined && delivery !== null && this._geoCaps[c])
        v *= this._geoMult(c, delivery[c]);
      out[c] = v;
    }
    return out;
  };

  CompEngine.prototype._loadoutEff = function (weapon) {
    var lo = this.weapons[weapon].loadout;
    var pen = this.weapons[weapon].resil_pen || 0.0;
    var hasSlots = lo && lo.slots && lo.slots.length;
    var hasAlways = lo && lo.always && Object.keys(lo.always).length;
    // no game data, no spell: escalation and area are unknown
    if (!lo || (!hasSlots && !hasAlways))
      return { always: this._eff(this.capsOf(weapon), null, pen, null), slots: [] };
    var self = this;
    var st = this._bundleStamps(lo, weapon);
    return {
      always: this._eff(lo.always || {}, st.alwaysDelivery, pen, st.always),
      slots: (lo.slots || []).map(function (slot, oi) {
        return slot.map(function (b, ci) {
          return self._eff(b, bundleDents(b, st.delivery[oi][ci]), pen, st.slots[oi][ci]);
        });
      }),
    };
  };

  /* a bundle's delivery as _eff reads it: every capability of the bundle on
     its own spell's facts (mirrors engine.py _bundle_dents); no facts, no
     geometric term */
  var bundleDents = function (bundle, dent) {
    if (!dent || !nonEmpty(dent)) return null;
    var out = {};
    for (var c in bundle) out[c] = dent;
    return out;
  };

  CompEngine.prototype._bundleStamps = function (lo, key) {
    /* one loadout's per-bundle spell facts (mirrors engine.py
       _bundle_stamps): the AoE escalation factors and the delivery facts;
       a loadout with bundles and no slot_escal or slot_delivery, or an
       always-on row of an AoE escalation or geometric capability without its
       always-on stamp, fails closed. An absent always_escal reads null. */
    var esc = lo.slot_escal, dl = lo.slot_delivery;
    if ((esc === undefined || esc === null || dl === undefined || dl === null)
        && lo.slots && lo.slots.length)
      throw new Error(key + ": loadout carries no slot_escal / slot_delivery "
                      + "(per-bundle spell facts); rebuild the dataset");
    var always = lo.always || {};
    var i;
    if (lo.always_escal === undefined) {
      for (i = 0; i < AOE_ESCALATION_CAPS.length; i++)
        if (always[AOE_ESCALATION_CAPS[i]] !== undefined)
          throw new Error(key + ": always-on AoE escalation row carries no "
                          + "always_escal; rebuild the dataset");
    }
    if (lo.always_delivery === undefined) {
      for (var c in always)
        if (this._geoCaps[c])
          throw new Error(key + ": always-on geometric row carries no "
                          + "always_delivery; rebuild the dataset");
    }
    return { always: lo.always_escal === undefined ? null : lo.always_escal,
             slots: esc || [],
             alwaysDelivery: lo.always_delivery || {},
             delivery: dl || [] };
  };

  CompEngine.prototype._comboExtras = function (weapon) {
    /* Every one-spell-per-slot loadout as a merged effective-caps object,
       in itertools.product order (first slot slowest — mirrors engine.py
       _combo_extras; cached per setContent). A capability may sit in
       several bundles; the merge keeps its largest value (_mergeMax). */
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
    var raw = [];
    for (i = 0; i < combos.length; i++) raw.push(mergeMax(always, combos[i]));
    /* the weapon's own E self-cost is charged on every combo, so each
       weapon-supply reader sees it; buildExtra starts from the uncharged
       combo and charges it on the dressed vector (mirrors engine.py) */
    var costs = this.weapons[weapon].self_costs;
    extras = raw;
    if (costs) {
      extras = [];
      for (i = 0; i < raw.length; i++) extras.push(this._chargeCosts(raw[i], costs));
    }
    this._extrasCache[weapon] = extras;
    this._unchargedCache[weapon] = raw;
    return extras;
  };

  CompEngine.prototype._unchargedExtras = function (weapon) {
    /* _comboExtras before the weapon's own self-cost (buildExtra's start);
       the same list for a weapon without one (mirrors engine.py) */
    this._comboExtras(weapon);
    return this._unchargedCache[weapon];
  };

  CompEngine.prototype._chargeCosts = function (extra, costs) {
    /* a copy of `extra` with self-costs (sheet points) charged on the
       capabilities it holds, floored at zero (mirrors engine.py) */
    var out = {}, c;
    for (c in extra) out[c] = extra[c];
    for (c in costs) {
      if (c in out) out[c] = Math.max(0.0, out[c] - costs[c] / this.scoreUnit);
    }
    return out;
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
       engine.py combo_choices). */
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

  /* ---- gear (full-build members; mirrors engine.py) ---- */
  CompEngine.prototype.gearKey = function (key) {
    /* The CURATED key for a worn item, ignoring tier (mirrors engine.py
       gear_key). Consumables are curated at one
       representative tier while comps record whatever tier they ran, so an
       exact-key lookup scored 20 real Gigantify potions as nothing. Exact
       keys win; an ambiguous tier-stripped form resolves to nothing rather
       than guessing. */
    if (this.gear[key]) return key;
    var form = keyForm(key);
    if (this.gear[form]) return form;   /* curated tierless: T8_ARMOR_PLATE_HELL -> ARMOR_PLATE_HELL */
    var alias = this._gearAlias[form];
    return alias === undefined ? key : alias;
  };

  CompEngine.prototype._gearItemKey = function (item) {
    /* the curated key of one worn-gear entry (a key or a [key, choice]
       pair): the one form every party-level reader compares on
       (mirrors engine.py _gear_item_key) */
    return this.gearKey(Array.isArray(item) ? item[0] : item);
  };

  CompEngine.prototype.gearExtras = function (key) {
    key = this.gearKey(key);
    var extras = this._gearCache[key];
    if (extras !== undefined) return extras;
    var g = this.gear[key];
    if (!g) { extras = [{}]; this._gearCache[key] = extras; return extras; }
    var lo = g.loadout || {};
    var st = this._bundleStamps(lo, key);
    var always = this._eff(lo.always || {}, st.alwaysDelivery, 0.0, st.always);
    var slots = [];
    var raw = lo.slots || [];
    for (var i = 0; i < raw.length; i++) {
      if (!raw[i].length) continue;
      var eff = [];
      for (var j = 0; j < raw[i].length; j++)
        eff.push(this._eff(raw[i][j], bundleDents(raw[i][j], st.delivery[i][j]), 0.0,
                           st.slots[i][j]));
      slots.push(eff);
    }
    extras = [];
    var self = this;
    (function walk(si, acc) {
      if (si === slots.length) {
        extras.push(mergeMax(always, acc));
        return;
      }
      for (var j2 = 0; j2 < slots[si].length; j2++)
        walk(si + 1, acc.concat([slots[si][j2]]));
    })(0, []);
    this._gearCache[key] = extras;
    return extras;
  };

  CompEngine.prototype._gearComboSlots = function (key) {
    /* the spell id per combo index in the item's ACTIVE slot (null when
       the loadout has no active slot), aligned with gearExtras: combos
       enumerate the non-empty slots in order, the last varying fastest
       (mirrors engine.py _gear_combo_slots) */
    var g = this.gear[this.gearKey(key)] || {};
    var lo = g.loadout || {};
    var names = lo.slot_names || [], spells = lo.slot_spells || [];
    var raw = lo.slots || [];
    var sizes = [], activePos = null;
    for (var i = 0; i < raw.length; i++) {
      if (!raw[i].length) continue;
      if (i < names.length && names[i] === "active") activePos = sizes.length;
      sizes.push([raw[i].length, i < spells.length ? spells[i] : []]);
    }
    if (activePos === null) return null;
    var out = [];
    (function walk(si, acc) {
      if (si === sizes.length) {
        var sp = sizes[activePos][1], j = acc[activePos];
        out.push(j < sp.length ? sp[j] : null);
        return;
      }
      for (var j2 = 0; j2 < sizes[si][0]; j2++) walk(si + 1, acc.concat([j2]));
    })(0, []);
    return out;
  };

  CompEngine.prototype.doctrineGearChoice = function (key) {
    /* the combo index the gear-active doctrine names, or null: the item's
       doctrine_active picks the ACTIVE slot's spell — the current band's
       pick where it has one, else the overall pick; any other slot takes
       the argmax among the combos carrying that active (mirrors
       engine.py doctrine_gear_choice) */
    key = this.gearKey(key);
    var da = (this.gear[key] || {}).doctrine_active;
    if (!da) return null;
    var band = this.size <= DOCTRINE_GANG_MAX ? "gang" : "group";
    var pick = (((da.bands || {})[band]) || da).id;
    var perCombo = this._gearComboSlots(key);
    if (!perCombo || perCombo.indexOf(pick) < 0) return null;
    var extras = this.gearExtras(key);
    var bestI = null, bestVal = null, bestUnits = null;
    for (var i = 0; i < extras.length; i++) {
      if (perCombo[i] !== pick) continue;
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

  CompEngine.prototype.gearActiveSpell = function (key, choice) {
    /* the spell id in the item's ACTIVE slot under `choice` (the default
       pick when null), or null where the item has no active slot
       (mirrors engine.py gear_active_spell) */
    var perCombo = this._gearComboSlots(key);
    if (!perCombo) return null;
    if (choice === null || choice === undefined || choice < 0 || choice >= perCombo.length)
      choice = this.defaultGearChoice(key);
    return perCombo[choice];
  };

  CompEngine.prototype.gearChoiceSource = function (key) {
    /* "observed" | "assumed" | "argmax" (mirrors engine.py gear_choice_source) */
    var da = (this.gear[this.gearKey(key)] || {}).doctrine_active;
    if (da && this.doctrineGearChoice(key) !== null) return da.source || "observed";
    return "argmax";
  };

  CompEngine.prototype.defaultGearChoice = function (key) {
    /* the doctrine's combo where the item carries one, else the argmax
       under the template weights (mirrors engine.py default_gear_choice) */
    var d = this.doctrineGearChoice(key);
    if (d !== null) return d;
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

  CompEngine.prototype.buildExtra = function (weapon, combo, gear, role,
                                              waiveCosts) {
    /* Full-build member: weapon loadout + gear abilities + the STAT
       channel (mirrors engine.py build_extra — same float order).
       CC-duration % multiplies the
       wearer's own duration-bearing CC — the Leering-Cane pairing as
       physics. An off-hand's defense % multiplies the wearer's
       tankiness, its cooldown % the output capabilities, its cast-time %
       the outputs the weapon casts, its attack speed the sustained damage.
       `role` (a seat id) additionally applies the DOCTRINE
       PASSIVE picks — generation/display only; scoring never passes
       a role. */
    var out = {}, c;
    var base = this._memberUncharged(weapon, combo);
    for (c in base) out[c] = base[c];
    var armorPts = 0.0, ccrPts = 0.0, dmgPct = 0.0, healPct = 0.0;
    var ccdurPct = 0.0, ccrMult = 0.0;
    var defPct = 0.0, cdrPct = 0.0, castPct = 0.0, aspdPct = 0.0;
    var seatClass = role ? ((this.rolesBook[role] || {})["class"] || null)
                         : null;
    for (var i = 0; i < (gear || []).length; i++) {
      var item = gear[i];
      var key = this.gearKey(Array.isArray(item) ? item[0] : item);
      var choice = Array.isArray(item) ? item[1] : null;
      var extra = this.gearExtra(key, choice);
      for (c in extra) out[c] = (out[c] || 0.0) + extra[c];
      var st = (this.gear[key] || {}).stats || {};
      armorPts += (st.physicalarmor || 0.0) + (st.magicresistance || 0.0);
      ccrPts += st.crowdcontrolresistance || 0.0;
      dmgPct += (st.magicspelldamagebonus !== undefined
                 ? st.magicspelldamagebonus
                 : (st.physicalspelldamagebonus || 0.0));
      healPct += st.healbonus || 0.0;
      ccdurPct += st.bonusccdurationvsplayers || 0.0;
      defPct += st.bonusdefensevsplayers || 0.0;
      cdrPct += st.magiccooldownreduction || 0.0;
      castPct += st.magiccasttimereduction || 0.0;
      aspdPct += st.attackspeedbonus || 0.0;
      if (seatClass) {
        var p = (((this.gear[key] || {}).doctrine_passives) || {})[seatClass];
        if (p) {
          var pv = p.value || 0.0;
          if (p.stat === "damage_heal_pct") { dmgPct += pv; healPct += pv; }
          else if (p.stat === "cc_duration_pct") ccdurPct += pv;
          else if (p.stat === "ccr_pct") ccrMult += pv;
        }
      }
    }
    var bs = this.mechanics.build_stats || {};
    var tank = armorPts * (bs.tankiness_per_armor_point || 0.0)
             + ccrPts * (1.0 + ccrMult) * (bs.tankiness_per_ccr_point || 0.0);
    if (tank > 0.0) out.tankiness = (out.tankiness || 0.0) + tank;
    if (defPct !== 0.0 && "tankiness" in out)
      out.tankiness = Math.max(0.0, out.tankiness * (1.0 + defPct));
    var j;
    if (dmgPct > 0.0) {
      var dc = bs.damage_mult_caps || [];
      for (j = 0; j < dc.length; j++)
        if (dc[j] in out) out[dc[j]] *= 1.0 + dmgPct;
    }
    if (healPct > 0.0) {
      var hc = bs.heal_mult_caps || [];
      for (j = 0; j < hc.length; j++)
        if (hc[j] in out) out[hc[j]] *= 1.0 + healPct;
    }
    if (ccdurPct > 0.0) {
      var cc = bs.cc_mult_caps || [];
      for (j = 0; j < cc.length; j++)
        if (cc[j] in out) out[cc[j]] *= 1.0 + ccdurPct;
    }
    if (cdrPct > 0.0) {
      var cdc = bs.cooldown_mult_caps || [];
      for (j = 0; j < cdc.length; j++)
        if (cdc[j] in out) out[cdc[j]] *= 1.0 + cdrPct;
    }
    if (castPct > 0.0) {
      var casted = this.weapons[weapon].cast_caps || [];
      var ctc = bs.cast_mult_caps || [];
      for (j = 0; j < ctc.length; j++)
        if (ctc[j] in out && casted.indexOf(ctc[j]) >= 0) out[ctc[j]] *= 1.0 + castPct;
    }
    if (aspdPct > 0.0) {
      var asc = bs.attack_speed_mult_caps || [];
      for (j = 0; j < asc.length; j++)
        if (asc[j] in out) out[asc[j]] *= 1.0 + aspdPct;
    }
    /* SELF-COSTS (mirrors engine.py): what the item costs its OWN wearer —
       Demon Armor's aura spends 0.37 of the wearer's resistances to give
       allies 0.43. Charged last so the stat channels above cannot
       re-multiply a cost, floored at zero, and skipped for items the party
       has offset (see selfCostWaivers). */
    for (var si = 0; si < (gear || []).length; si++) {
      var sitem = gear[si];
      var skey = this.gearKey(Array.isArray(sitem) ? sitem[0] : sitem);
      if (waiveCosts && waiveCosts[skey]) continue;
      var costs = (this.gear[skey] || {}).self_costs || {};
      for (var scap in costs) {
        if (scap in out) {
          out[scap] = Math.max(0.0, out[scap] - costs[scap] / this.scoreUnit);
        }
      }
    }
    /* the weapon's own E self-cost, on the dressed vector (memberExtra
       charges it on the naked one; buildExtra started uncharged) */
    var wcosts = this.weapons[weapon].self_costs || {};
    for (var wcap in wcosts) {
      if (wcap in out) out[wcap] = Math.max(0.0, out[wcap] - wcosts[wcap] / this.scoreUnit);
    }
    /* WEAPON-BASIS ROWS (mechanics build_stats weapon_basis_caps; mirrors
       engine.py): the member's weapon + loadout supply as the naked member
       brings it; no worn item adds to or changes it */
    var wbCaps = bs.weapon_basis_caps || [];
    for (var wb = 0; wb < wbCaps.length; wb++) {
      var nakedV = this.memberExtra(weapon, combo)[wbCaps[wb]];
      if (nakedV === undefined) delete out[wbCaps[wb]];
      else out[wbCaps[wb]] = nakedV;
    }
    return out;
  };

  CompEngine.prototype._memberUncharged = function (weapon, combo) {
    /* memberExtra before the weapon's own self-cost (buildExtra's start);
       null -> the static default (mirrors engine.py) */
    var extras = this._unchargedExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    return extras[combo];
  };

  /* Gear keys whose self-cost this party has offset — the ONLY
     super-additive duplicate rule in the model, deliberately narrow.
     Mirrors engine.py _self_cost_waivers: a VERIFIED
     interaction record on the cost's evidence spell declares
     self_cost_offset_min_copies, and the party fields that many. Cancels a
     cost, never adds supply. */
  /* A gears list cut at the party's end: a tail entry is worn by no member
     and counts in no reader (the self-cost waiver, the refund, the carrier
     quota; mirrors engine.py _pad, F38c). A missing entry already reads as
     a naked member. */
  CompEngine.prototype._partyGears = function (gears, n) {
    return gears && gears.length > n ? gears.slice(0, n) : gears;
  };

  CompEngine.prototype.selfCostWaivers = function (gears) {
    var out = {};
    if (!this.costOffsets || !gears) return out;
    var counts = {};
    for (var i = 0; i < gears.length; i++) {
      var g = gears[i] || [];
      for (var j = 0; j < g.length; j++) {
        var key = this._gearItemKey(g[j]);
        if (this.costOffsets[key] !== undefined) {
          counts[key] = (counts[key] || 0) + 1;
        }
      }
    }
    for (var k in counts) {
      if (counts[k] >= this.costOffsets[k]) out[k] = true;
    }
    return out;
  };

  CompEngine.prototype._offsetPending = function (party, combos, gears, waived) {
    /* the self-cost REFUND a candidate can trigger (mirrors engine.py
       _offset_pending): for every offset item the party fields one copy
       short of its waiver count, what the existing wearers gain when the
       count is reached. Empty unless such an item exists. */
    var out = {};
    if (!this.costOffsets || !gears) return out;
    var anyOff = false;
    for (var ko in this.costOffsets) { anyOff = true; break; }
    if (!anyOff) return out;
    var counts = {}, i, j;
    for (i = 0; i < gears.length; i++) {
      var g = gears[i] || [];
      for (j = 0; j < g.length; j++) {
        var key = this._gearItemKey(g[j]);
        if (this.costOffsets[key] !== undefined) counts[key] = (counts[key] || 0) + 1;
      }
    }
    for (var k in this.costOffsets) {
      if ((counts[k] || 0) !== this.costOffsets[k] - 1 || waived[k]) continue;
      var refund = {}, any = false;
      var after = {};
      for (var wk in waived) after[wk] = true;
      after[k] = true;
      /* a gears tail past the party is worn by no member (mirrors
         engine.py _offset_pending) */
      for (i = 0; i < gears.length && i < party.length; i++) {
        var gl = gears[i] || [], wears = false;
        for (j = 0; j < gl.length; j++) if (this._gearItemKey(gl[j]) === k) { wears = true; break; }
        if (!wears) continue;
        var c = combos ? combos[i] : null;
        var was = this.buildExtra(party[i], c, gl, null, waived);
        var now = this.buildExtra(party[i], c, gl, null, after);
        for (var cap in now) {
          var d = now[cap] - (was[cap] || 0.0);
          if (d) { refund[cap] = (refund[cap] || 0.0) + d; any = true; }
        }
      }
      if (any) out[k] = refund;
    }
    return out;
  };

  CompEngine.prototype._offsetVector = function (state, weapon, combo, vgears) {
    /* [dressed extra, refund] for a candidate whose kit carries an offset
       item the party has waived or is one copy short of; null when the
       kit carries no such item (mirrors engine.py _offset_vector) */
    if (!vgears || !vgears.length) return null;
    var waived = state.waived || {}, pending = state.pending || {};
    var anyW = false, k;
    for (k in waived) { anyW = true; break; }
    if (!anyW) for (k in pending) { anyW = true; break; }
    if (!anyW) return null;
    var hit = {}, anyHit = false;
    for (var j = 0; j < vgears.length; j++) {
      var key = this._gearItemKey(vgears[j]);
      if (waived[key] || pending[key]) { hit[key] = true; anyHit = true; }
    }
    if (!anyHit) return null;
    var waive = {};
    for (k in waived) waive[k] = true;
    for (k in hit) waive[k] = true;
    var dext = this.buildExtra(weapon, combo, vgears, null, waive);
    var refund = {};
    for (k in hit) {
      var r = pending[k] || {};
      for (var cap in r) refund[cap] = (refund[cap] || 0.0) + r[cap];
    }
    return [dext, refund];
  };

  CompEngine.prototype._seatKit = function (rec) {
    /* the seat's doctrine for THIS party size and DECLARED style (mirrors
       engine.py _seat_kit): the gang band below 10 members; else a declared
       style's cell (kit_styles.<style>) laid over the band -- the band
       fills what the cell lacks; `balanced` never reads a cell. */
    if (this.size <= DOCTRINE_GANG_MAX) {
      var gang = (rec.kit_bands || {}).gang;
      if (present(gang)) return gang;   /* an empty band is no band, as in engine.py */
    }
    var cell = IDENTITY_STYLES[this.style] ? (rec.kit_styles || {})[this.style] : null;
    if (!present(cell)) return rec;
    var merged = {}, k;
    for (k in rec) merged[k] = rec[k];
    var kit = {};
    for (k in (rec.kit || {})) kit[k] = rec.kit[k];
    for (k in (cell.kit || {})) kit[k] = cell.kit[k];
    merged.kit = kit;
    /* per-weapon tiers merge per SLOT (the band fills every slot the cell
       lacks); a chain replaces the weapon's whole chain; the uniform
       extension replaces per weapon -- mirrors engine.py */
    var kw = {}, w, sl;
    for (w in (rec.kit_weapon || {})) {
      kw[w] = {};
      for (sl in rec.kit_weapon[w]) kw[w][sl] = rec.kit_weapon[w][sl];
    }
    for (w in (cell.kit_weapon || {})) {
      if (!kw[w]) kw[w] = {};
      for (sl in cell.kit_weapon[w]) kw[w][sl] = cell.kit_weapon[w][sl];
    }
    merged.kit_weapon = kw;
    var keys = ["kit_weapon_build", "kit_weapon_uniform"], ki;
    for (ki = 0; ki < keys.length; ki++) {
      var perW = {};
      for (k in (rec[keys[ki]] || {})) perW[k] = rec[keys[ki]][k];
      for (k in (cell[keys[ki]] || {})) perW[k] = cell[keys[ki]][k];
      merged[keys[ki]] = perW;
    }
    if (present(cell.kit_build)) merged.kit_build = cell.kit_build;
    var sw = [];
    for (k in (cell.kit_weapon_build || {})) sw.push(k);
    sw.sort();
    merged._style_arch = { weapons: sw, seat: present(cell.kit_build) };
    return merged;
  };
  CompEngine.prototype._chestUniform = function (seat, weapon) {
    /* chest classes admitted for `weapon` in `seat`: the book uniform plus
       the weapon's observed-majority class where the harvest is clear
       (dataset kit_weapon_uniform) -- mirrors engine.py _chest_uniform */
    var rec = this.rolesBook[seat] || {};
    var ext = (this._seatKit(rec).kit_weapon_uniform || {})[weapon];
    if (ext && ext.length) return ext.slice();
    return ((rec.uniform || {}).chest || []).slice();
  };
  CompEngine.prototype.primarySeat = function (weapon) {
    /* The weapon's default SEAT: first uniform-carrying role on its
       menu (mirrors engine.py primary_seat). */
    var menu = this.weapons[weapon].role_menu || [];
    for (var i = 0; i < menu.length; i++) {
      var uni = (((this.rolesBook[menu[i]] || {}).uniform) || {}).chest || [];
      if (uni.length) return menu[i];
    }
    return null;
  };

  CompEngine.prototype.kitOptions = function (weapon, combo, party, topN,
                                              role, partyCombos, partyGears) {
    /* IDEAL KIT per weapon, per content/style, per comp — mirrors
       engine.py kit_options (DOCTRINE-LED: the kit is the whole build):
       ranked gear options per slot. No party ->
       context-free weighted-delta value with the DOCTRINE TIER first;
       with `party` -> comp-aware exact fitness delta outranks tier
       membership (doctrine stays annotation + tie-break), the rest read
       in partyCombos / partyGears (parallel to party; omitted: naked at
       default combos). `role`:
       undefined/"auto" resolves the weapon's primary seat, null is the
       explicit diagnostic escape (ungated pool), a seat id uses that
       seat. With a seat the CHEST pool hard-gates to the uniform
       classes; options carry doctrine/carries/passive.
       FAIL-CLOSED GENERATION (mirrors
       engine.py): the suggestion channel only speaks evidence — no
       seat -> empty kit/options (`seat: null` says why); a seated
       slot with no doctrine tier stays unset, never catalog-filled.
       Suggestion-layer only — manual builds score anything. `why`
       deltas are display-rounded. */
    if (topN === undefined || topN === null) topN = 3;
    if (role === undefined) role = "auto";
    var seat = role === "auto" ? this.primarySeat(weapon) : role;
    if (role !== null && (seat === null || seat === undefined))
      return { kit: {}, options: {}, seat: null };
    var seatRec = this.rolesBook[seat] || {};
    /* book uniform widened by THIS weapon's observed majority class
       (kit_weapon_uniform) -- mirrors engine.py */
    var uniform = this._chestUniform(seat, weapon);
    var seatClass = seatRec["class"] || null;
    seatRec = this._seatKit(seatRec);   /* the size band's doctrine */
    var doctrine = seatRec.kit || {};
    /* Per-weapon doctrine tier: this weapon's
       own observed items (effect carriers excluded at the build) outrank
       the seat aggregate; `doctrine` is "weapon" / "seat" / false and
       weapon-tier options carry doctrine_n = [count, slot total].
       Mirrors engine.py. */
    var wdoc = (seatRec.kit_weapon || {})[weapon] || {};
    /* observed-build archetype (mirrors engine.py): the KIT
       pick follows what real players field — weapon's own conditional-
       modal build first, seat fallback per slot; the archetype item
       moves to the front of its slot's options. */
    var arch = {}, archSeat = {}, archStyled = {};
    if (role !== null) {
      var wbArch = (seatRec.kit_weapon_build || {})[weapon] || {};
      var sbArch = seatRec.kit_build || {};
      var aslot;
      for (aslot in sbArch) { arch[aslot] = sbArch[aslot]; archSeat[aslot] = true; }
      for (aslot in wbArch) { arch[aslot] = wbArch[aslot]; delete archSeat[aslot]; }
      /* which archetype slots came from the declared style's cell
         (kit_styles; mirrors engine.py): the option carries observed_style */
      var styledArch = seatRec._style_arch || { weapons: [], seat: false };
      for (aslot in arch) {
        if ((wbArch[aslot] && styledArch.weapons.indexOf(weapon) >= 0)
            || (archSeat[aslot] && styledArch.seat)) archStyled[aslot] = true;
      }
    }
    var bySlot = {}, k;
    for (k in this.gear) {
      var slot0 = this.gear[k].slot || "other";
      (bySlot[slot0] = bySlot[slot0] || []).push(k);
    }
    /* a two-hander has no off-hand: drop the slot before the seat pool
       (mined from one-handers too) can propose one — mirrors engine.py */
    if (this.weapons[weapon].two_handed) delete bySlot.offhand;
    var self = this;
    if (uniform.length) {
      var gated = (bySlot.armor || []).filter(function (g) {
        return uniform.indexOf((self.gear[g].gear_class || "")) >= 0;
      });
      if (gated.length) bySlot.armor = gated;
    }
    /* Style-fit gear gate: under a DECLARED brawl, cloth never gets
       SUGGESTED for a non-healer — mirrors engine.py (a closed drift: the
       JS port had skipped this gate). */
    if ((this.style === "brawl" || this.style === "brawl_clap")
        && this.roleOf(weapon) !== "healer") {
      var unclothed = (bySlot.armor || []).filter(function (g) {
        return g.indexOf("_CLOTH_") < 0;
      });
      if (unclothed.length) bySlot.armor = unclothed;
    }
    var bare = this.memberExtra(weapon, combo);
    var joined = null, baseGears = null, joinedCombos = null, fBare = 0.0;
    /* the worn rest is dressed once per waived set, not once per item (an
       item completing a self-cost offset dresses it again) */
    var memo = {};
    if (party !== null && party !== undefined) {
      joined = party.concat([weapon]);
      baseGears = party.map(function (_w, j) {
        var g = partyGears && j < partyGears.length ? partyGears[j] : null;
        return (g && g.length) ? g.slice() : null;
      });
      joinedCombos = party.map(function (_w, j) {
        var c = partyCombos && j < partyCombos.length ? partyCombos[j] : null;
        return c === undefined ? null : c;
      }).concat([combo]);
      fBare = this.fitness(joined, joinedCombos, baseGears.concat([null]),
                           memo);
    }
    var options = {}, slots = Object.keys(bySlot).sort();
    for (var si = 0; si < slots.length; si++) {
      var slot = slots[si], keys = bySlot[slot].slice().sort();
      var docPool = doctrine[slot] || [];
      var wslot = {}, wpeople = {}, wtotal = 0, wp = wdoc[slot] || [];
      for (var wi = 0; wi < wp.length; wi++) {
        wslot[wp[wi][0]] = wp[wi][1];
        wtotal += wp[wi][1];
        /* third element: distinct people behind a killboard-fed row */
        if (wp[wi].length > 2) wpeople[wp[wi][0]] = wp[wi][2];
      }
      if (role !== null) {
        /* fail-closed generation: only doctrine
           tiers may be suggested; an evidence-less slot stays unset */
        keys = keys.filter(function (g) {
          return Object.prototype.hasOwnProperty.call(wslot, g)
              || docPool.indexOf(g) >= 0;
        });
        if (!keys.length) continue;
      }
      var ranked = [];
      for (var ki = 0; ki < keys.length; ki++) {
        k = keys[ki];
        var built = this.buildExtra(weapon, combo, [k], seat);
        var deltas = [], c;
        for (c in built) {
          var d = built[c] - (bare[c] || 0.0);
          if (d > 1e-9) deltas.push([c, d]);
        }
        deltas.sort(function (a, b) {
          return (self._weights[b[0]] || 0.0) * b[1]
               - (self._weights[a[0]] || 0.0) * a[1];
        });
        var value = 0.0, di;
        if (joined === null) {
          for (di = 0; di < deltas.length; di++)
            value += (this._weights[deltas[di][0]] || 0.0) * deltas[di][1];
        } else {
          value = this.fitness(joined, joinedCombos, baseGears.concat([[k]]),
                               memo) - fBare;
        }
        var passive = null;
        if (seatClass) {
          var p = ((this.gear[k].doctrine_passives) || {})[seatClass];
          if (p) passive = { id: p.id, name: p.name };
        }
        var why = [];
        for (di = 0; di < Math.min(3, deltas.length); di++)
          why.push([deltas[di][0], round2(deltas[di][1])]);
        var tier = Object.prototype.hasOwnProperty.call(wslot, k)
          ? "weapon" : (docPool.indexOf(k) >= 0 ? "seat" : false);
        ranked.push({ gear: k, display_name: this.gear[k].display_name,
                      value: value, doctrine: tier,
                      doctrine_n: tier === "weapon"
                        ? [wslot[k], wtotal] : null,
                      carries: (this.itemEffects[k] || []).slice(),
                      passive: passive, why: why });
      }
      /* DOCTRINE-TIER-FIRST in both modes (evidence-first): the observed
         tier bounds the suggestion;
         context-free ranks by count then value within a tier,
         comp-aware by the exact marginal — mirrors engine.py. */
      var gearCmp = function (a, b) {
        return a.gear < b.gear ? -1 : a.gear > b.gear ? 1 : 0;
      };
      var tierRank = function (r) {
        return r.doctrine === "weapon" ? 0 : r.doctrine === "seat" ? 1 : 2;
      };
      var wCount = function (r) { return wslot[r.gear] || 0; };
      /* EVIDENCE-FIRST (the kit audit; mirrors engine.py): count leads the
         weapon tier; comp-aware may reorder only the evidence band (items
         worn >= half as often as the modal one) by the marginal; the seat
         tier keeps the seat pool's count order; value breaks ties. */
      var topCount = 0;
      for (var tk in wslot) if (wslot[tk] > topCount) topCount = wslot[tk];
      var seatOrder = {};
      for (var so = 0; so < docPool.length; so++) seatOrder[docPool[so]] = so;
      var inBand = function (g) { return (wslot[g] || 0) >= 0.5 * topCount; };
      var sortKey = function (r) {
        var t = tierRank(r), g = r.gear;
        if (t === 0) {
          if (joined !== null && inBand(g))
            return [0, 0, -qrank(r.value), -(wslot[g] || 0)];
          return [0, inBand(g) ? 0 : 1, -(wslot[g] || 0), -qrank(r.value)];
        }
        if (t === 1)
          return [1, seatOrder[g] === undefined ? docPool.length : seatOrder[g],
                  0, -qrank(r.value)];
        return [2, 0, -qrank(r.value), 0];
      };
      ranked.sort(function (a, b) {
        var ka = sortKey(a), kb = sortKey(b);
        for (var ci = 0; ci < ka.length; ci++) {
          if (ka[ci] !== kb[ci]) return ka[ci] < kb[ci] ? -1 : 1;
        }
        return gearCmp(a, b);
      });
      var av = arch[slot];
      /* seat archetype = fallback only where the weapon has no counts
         (mirrors engine.py) */
      if (av && (topCount === 0 || (!archSeat[slot] && inBand(av[0])))) {
        /* the observed build leads the slot (the overlay rule) -- never
           from outside the evidence band */
        for (var ai = 0; ai < ranked.length; ai++) {
          if (ranked[ai].gear === av[0]) {
            ranked[ai].observed_build = [av[1], av[2]];
            if (archStyled[slot]) ranked[ai].observed_style = this.style;
            ranked.unshift(ranked.splice(ai, 1)[0]);
            break;
          }
        }
      }
      /* SEAT POOLING (R34a/b; mirrors engine.py): a THIN slot (the
         weapon's own modal under POOL_MIN_VOTES votes) is dressed from the
         seat's pool — helmet/boots/cape from the seat's builds wearing the
         chest this kit wears (armor is ranked first), potion/food from the
         plain seat pool; the first pool item with 5+ players the doctrine
         tier already offers moves to the front, marked pooled/pooled_n. */
      if (role !== null && POOLED_SLOTS[slot]) {
        /* THIN counts distinct PEOPLE where the row carries them (every
           doctrine floor counts people, R27), votes on a reference-only
           row -- mirrors engine.py */
        var topW = 0, modalW = null, tw;
        for (tw in wslot) {
          if (wslot[tw] > topW || (wslot[tw] === topW && (modalW === null || tw > modalW))) {
            topW = wslot[tw]; modalW = tw;
          }
        }
        var topPeople = (modalW !== null && Object.prototype.hasOwnProperty.call(wpeople, modalW))
          ? wpeople[modalW] : topW;
        if (topPeople < POOL_MIN_VOTES) {
          var cands = [];
          if (CHEST_POOLED_SLOTS[slot]) {
            var chestPick = ((options.armor || [])[0] || {}).gear;
            if (chestPick) {
              cands.push(["seat|chest",
                (((seatRec.kit_by_chest || {})[chestPick]) || {})[slot] || []]);
            }
          }
          cands.push(["seat", (seatRec.kit_pool || {})[slot] || []]);
          var placed = false;
          for (var ci = 0; ci < cands.length && !placed; ci++) {
            var rows = cands[ci][1], pick = null;
            for (var ri = 0; ri < rows.length; ri++) {
              if (rows[ri][1] >= POOL_MIN_VOTES) { pick = rows[ri]; break; }
            }
            if (!pick) continue;
            for (var pi = 0; pi < ranked.length; pi++) {
              if (ranked[pi].gear === pick[0]) {
                ranked[pi].pooled = cands[ci][0];
                ranked[pi].pooled_n = pick[1];
                ranked.unshift(ranked.splice(pi, 1)[0]);
                placed = true;
                break;
              }
            }
          }
        }
      }
      options[slot] = ranked.slice(0, topN);
    }
    var kit = {};
    for (var s2 in options) if (options[s2].length) kit[s2] = options[s2][0];
    return { kit: kit, options: options, seat: seat };
  };

  CompEngine.prototype.carrierCaps = function () {
    /* per-roster cap on each effect-carrier chest at this size (mirrors
       engine.py carrier_caps): killboard share x size, half-up, min 1.
       A GENERATION constraint: partyState counts what the roster wears,
       candidates skip capped kit variants. */
    if (this._carrierCapsCache !== null && this._carrierCapsCache !== undefined)
      return this._carrierCapsCache;
    var q = this.data.carrier_quotas || {};
    var buckets = q.buckets || {};
    var any = false;
    for (var bk in buckets) { any = true; break; }
    var caps = {};
    if (any) {
      var key = (this.size >= 60 && buckets["60+"]) ? "60+" : "20-59";
      var share = (buckets[key] || {}).share || {};
      for (var eff in share) caps[eff] = Math.max(1, Math.floor(share[eff] * this.size + 0.5));
    }
    this._carrierCapsCache = caps;
    return caps;
  };
  CompEngine.IDENTITY_CHEST_SHARE = 0.5;
  CompEngine.prototype._identityChest = function (weapon, gearId) {
    /* a chest at least half the weapon's builds wear is IDENTITY, exempt
       from the carrier quota (mirrors engine.py _identity_chest) */
    return this.observedShare(weapon, gearId) >= CompEngine.IDENTITY_CHEST_SHARE;
  };
  CompEngine.prototype._cappedEffects = function (gearId) {
    var caps = this.carrierCaps(), effs = this.itemEffects[gearId] || [], out = [];
    for (var k = 0; k < effs.length; k++) if (caps[effs[k]] !== undefined) out.push(effs[k]);
    return out;
  };
  CompEngine.prototype._carrierCounts = function (party, gears) {
    /* {effect: members wearing a DISCRETIONARY chest granting it}
       (mirrors engine.py _carrier_counts) */
    var caps = this.carrierCaps(), out = {}, anyCap = false;
    for (var c0 in caps) { anyCap = true; break; }
    if (!anyCap) return out;
    for (var i = 0; i < (gears || []).length; i++) {
      var g = gears[i] || [], w = i < party.length ? party[i] : null;
      for (var j = 0; j < g.length; j++) {
        var x = this._gearItemKey(g[j]);
        var effs = this._cappedEffects(x);
        if (!effs.length || (w && this._identityChest(w, x))) continue;
        for (var k = 0; k < effs.length; k++) out[effs[k]] = (out[effs[k]] || 0) + 1;
      }
    }
    return out;
  };
  CompEngine.prototype._variantCapped = function (state, weapon, vgears) {
    /* true when dressing `weapon` in `vgears` would push a DISCRETIONARY
       carrier past its cap; identity chests never are */
    var carriers = state.carriers;
    if (!carriers || !vgears) return false;
    var caps = this.carrierCaps();
    for (var j = 0; j < vgears.length; j++) {
      var x = this._gearItemKey(vgears[j]);
      var effs = this._cappedEffects(x);
      if (!effs.length || this._identityChest(weapon, x)) continue;
      for (var k = 0; k < effs.length; k++) {
        if ((carriers[effs[k]] || 0) >= caps[effs[k]]) return true;
      }
    }
    return false;
  };
  CompEngine.prototype.observedShare = function (weapon, gearId) {
    var seat = this.primarySeat(weapon);
    var rec = this.rolesBook[seat] || {};
    var slot = (this.gear[gearId] || {}).slot;
    var wl = ((this._seatKit(rec).kit_weapon || {})[weapon] || {})[slot] || [];
    var total = 0, n = 0;
    for (var i = 0; i < wl.length; i++) {
      total += wl[i][1];
      if (wl[i][0] === gearId) n = wl[i][1];
    }
    return total ? n / total : 0.0;
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
    var le = this._loadoutEff(weapon), alwaysEff = le.always, slotsEff = le.slots;
    var out = {};
    var choices = this.comboChoices(weapon, combo).filter(function (ch) {
      return ch[0] < slotsEff.length && ch[1] < slotsEff[ch[0]].length;
    });
    for (var ci = 0; ci < choices.length; ci++) {
      var oi = choices[ci][0], bi = choices[ci][1];
      if (oi >= spells.length || bi >= spells[oi].length) continue;
      var sid = spells[oi][bi];
      var caps = this.nonstack[sid];
      if (!caps) continue;
      var bundle = slotsEff[oi][bi];
      var contrib = out[sid] || (out[sid] = {});
      var any = false;
      for (var cj = 0; cj < caps.length; cj++) {
        var v = bundle[caps[cj]] || 0.0;
        if (!v) continue;
        /* the spell's share of the member's total (_mergeMax): what it
           adds over the member's other sources of the capability */
        var other = alwaysEff[caps[cj]] || 0.0;
        for (var ck = 0; ck < choices.length; ck++) {
          if (ck === ci) continue;
          var ov = slotsEff[choices[ck][0]][choices[ck][1]][caps[cj]] || 0.0;
          if (ov > other) other = ov;
        }
        if (v > other) { contrib[caps[cj]] = (contrib[caps[cj]] || 0.0) + (v - other); any = true; }
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

  CompEngine.prototype.effectiveSupply = function (party, combos, gears,
                                                   memo) {
    /* Supply after physics AND the one-spell-per-slot rule; ALL scoring
       reads this (mirrors engine.py effective_supply). `memo` (an object
       the caller keeps for one sweep in one context) reuses each dressed
       member's buildExtra, keyed by weapon, combo, kit and waived: the
       kit advisor prices every item against the same worn rest. */
    var s = {}, c;
    gears = this._partyGears(gears, party.length);
    var waived = gears ? this.selfCostWaivers(gears) : null, wkey = null;
    for (var i = 0; i < party.length; i++) {
      var ci = combos ? combos[i] : null, g = gears ? gears[i] : null;
      var extra;
      if (!(g && g.length)) {
        extra = this.memberExtra(party[i], ci);
      } else if (!memo) {
        extra = this.buildExtra(party[i], ci, g, null, waived);
      } else {
        if (wkey === null) wkey = Object.keys(waived).sort().join(",");
        var mk = party[i] + "|" + ci + "|" + g.map(function (x) {
          return Array.isArray(x) ? x[0] + ":" + x[1] : x;
        }).join(",") + "|" + wkey;
        extra = memo[mk];
        if (extra === undefined)
          extra = memo[mk] = this.buildExtra(party[i], ci, g, null, waived);
      }
      for (c in extra) s[c] = (s[c] || 0.0) + extra[c];
    }
    if (this.hasNonstack) this._applyNonstack(s, party, combos, gears);
    return s;
  };

  CompEngine.prototype._nsShare = function (v, cap, gear, weapon) {
    /* A count-once spell's units on `cap` as a member holding `weapon` and
       wearing `gear` supplies them: buildExtra's stat channel multiplies
       them as it multiplies the member's whole capability, same order, no
       doctrine passives (mirrors engine.py _ns_share). Naked: v; a
       weapon-basis capability reads v dressed too, as buildExtra does. */
    if (!gear || !gear.length) return v;
    if ((((this.mechanics || {}).build_stats || {}).weapon_basis_caps || []).indexOf(cap) >= 0)
      return v;
    var dmg = 0.0, heal = 0.0, ccdur = 0.0;
    var dfn = 0.0, cdr = 0.0, cast = 0.0, aspd = 0.0;
    for (var i = 0; i < gear.length; i++) {
      var item = gear[i];
      var key = this.gearKey(Array.isArray(item) ? item[0] : item);
      var st = (this.gear[key] || {}).stats || {};
      dmg += (st.magicspelldamagebonus !== undefined
              ? st.magicspelldamagebonus
              : (st.physicalspelldamagebonus || 0.0));
      heal += st.healbonus || 0.0;
      ccdur += st.bonusccdurationvsplayers || 0.0;
      dfn += st.bonusdefensevsplayers || 0.0;
      cdr += st.magiccooldownreduction || 0.0;
      cast += st.magiccasttimereduction || 0.0;
      aspd += st.attackspeedbonus || 0.0;
    }
    var bs = this.mechanics.build_stats || {};
    if (dfn !== 0.0 && cap === "tankiness") v = Math.max(0.0, v * (1.0 + dfn));
    if (dmg > 0.0 && (bs.damage_mult_caps || []).indexOf(cap) >= 0) v *= 1.0 + dmg;
    if (heal > 0.0 && (bs.heal_mult_caps || []).indexOf(cap) >= 0) v *= 1.0 + heal;
    if (ccdur > 0.0 && (bs.cc_mult_caps || []).indexOf(cap) >= 0) v *= 1.0 + ccdur;
    if (cdr > 0.0 && (bs.cooldown_mult_caps || []).indexOf(cap) >= 0) v *= 1.0 + cdr;
    if (cast > 0.0 && (bs.cast_mult_caps || []).indexOf(cap) >= 0
        && ((this.weapons[weapon] || {}).cast_caps || []).indexOf(cap) >= 0) v *= 1.0 + cast;
    if (aspd > 0.0 && (bs.attack_speed_mult_caps || []).indexOf(cap) >= 0) v *= 1.0 + aspd;
    return v;
  };

  CompEngine.prototype._applyNonstack = function (s, party, combos, gears) {
    /* Count-once rule for verified non-stacking interaction spells —
       identical accumulation ORDER to engine.py _apply_nonstack (sorted
       spell ids, stored cap order, party order): float parity is exact.
       A dressed member's contribution is its share AS WORN (_nsShare). */
    var groups = {};
    for (var i = 0; i < party.length; i++) {
      var per = this._nonstackContrib(party[i], combos ? combos[i] : null);
      var g = gears ? gears[i] : null;
      for (var sid in per) {
        var contrib = per[sid];
        if (g && g.length) {
          var scaled = {};
          for (var sc in contrib) scaled[sc] = this._nsShare(contrib[sc], sc, g, party[i]);
          contrib = scaled;
        }
        (groups[sid] = groups[sid] || []).push(contrib);
      }
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

  CompEngine.prototype._coverTerms = function (cap, have, gain, target,
                                               haveFloor, gainFloor) {
    /* [coverage delta (incl. headroom), floor-lift delta] — two terms so
       callers accumulate in their original order (mirrors engine.py).
       Option C: STRUCTURAL hard floors read the
       weapon+loadout basis — dressed callers pass haveFloor/gainFloor so
       worn gear never buys floor relief; defaults keep the naked path
       bit-identical. */
    var soft = this.softCap(cap);
    var cov = this.weight(cap) * (Math.pow(Math.min(1.0, (have + gain) / target), this.gamma)
                                  - Math.pow(Math.min(1.0, have / target), this.gamma));
    cov += (this._headroomBonus(cap, have + gain, target, soft)
            - this._headroomBonus(cap, have, target, soft));
    var hf = (haveFloor === undefined || haveFloor === null) ? have : haveFloor;
    var gf = (gainFloor === undefined || gainFloor === null) ? gain : gainFloor;
    return [cov, this._floorPenalty(cap, hf) - this._floorPenalty(cap, hf + gf)];
  };

  /* ---------------------------------------------------------------- fitness */
  CompEngine.prototype.fitness = function (party, combos, gears, memo) {
    gears = this._partyGears(gears, party.length);
    var s = this.effectiveSupply(party, combos, gears, memo);
    /* Option C: STRUCTURAL hard floors read the
       weapon+loadout supply — worn gear improves coverage/headroom/
       overstack but can never satisfy a structural floor (mirrors
       engine.py fitness). Naked parties keep the single-supply path. */
    var anyGear = false;
    if (gears) {
      for (var gi = 0; gi < gears.length; gi++) {
        if (gears[gi] && gears[gi].length) { anyGear = true; break; }
      }
    }
    var sf = anyGear ? this.effectiveSupply(party, combos) : s;
    var total = 0.0;
    for (var cap in this.reqs) {
      var have = s[cap] || 0.0, target = this.target(cap), soft = this.softCap(cap);
      total += this.weight(cap) * Math.pow(Math.min(1.0, have / target), this.gamma);
      total += this._headroomBonus(cap, have, target, soft);
      total -= this._overstack(cap, have, target, soft);
      total -= this._floorPenalty(cap, sf === s ? have : (sf[cap] || 0.0));
    }
    return total;
  };

  CompEngine.prototype.maxFitness = function (party, combos, gears) {
    /* Supremum of fitness(): full coverage + the headroom band maxed
       (mirrors engine.py max_fitness). Given a party, OPTIONAL
       capabilities it fields none of drop out of the supremum — a comp is
       not marked down for skipping a
       tool that lives on one weapon in the game. No party = the
       every-capability supremum, so legacy callers are unchanged. */
    var t = 0, s = null, cap;
    var hasOpt = false;
    for (cap in this.optional) { hasOpt = true; break; }
    if (party && hasOpt) s = this.effectiveSupply(party, combos, gears);
    for (cap in this.reqs) {
      if (s && this.optional[cap] && !(s[cap] > 0)) continue;
      t += this.weight(cap);
    }
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
       engine.py _dup_free). */
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
  CompEngine.prototype._priorPool = function (content, size) {
    /* the matchmaking pool of `content` covering `size` that carries a
       prior of its own (meta_pools), with its key; null without (mirrors
       engine.py _prior_pool) */
    var pools = this.metaPools[content] || {};
    for (var key in pools) {
      var row = pools[key];
      if (row.sizes[0] <= size && size <= row.sizes[1]) {
        var out = {};
        for (var k in row) out[k] = row[k];
        out.key = key;
        return out;
      }
    }
    return null;
  };

  CompEngine.prototype._soloOf = function (w) {
    /* the weapon's own share of killer parties at the current size; inside
       a pool with a prior of its own, the pool's (mirrors engine.py _solo_of) */
    if (this.priorPool !== null) return this.priorPool.solo[w] || 0.0;
    if (!this.metaBucketed) return this.metaPrior[w] || 0.0;
    return (this.metaPrior[this.sizeBucket()] || {})[w] || 0.0;
  };

  CompEngine.prototype._pairTable = function () {
    /* {weapon: {partner: s}} at the current context: the pool's own table
       inside a pool with a prior, else the size bucket's (mirrors engine.py) */
    if (this.priorPool !== null) return this.priorPool.pairs;
    return this.metaPairs[this.sizeBucket()] || {};
  };

  CompEngine.prototype._pairOf = function (weapon, party, skip) {
    /* Best observed partner of `weapon` among the OTHER seats of `party`
       (mirrors engine.py _pair_of): [score, partner|null]; [0, null] with
       no row — absence is neutral, never a penalty. Ties break on the
       partner id so the explanation matches Python. */
    if (!party || !party.length || !this.metaPairW) return [0.0, null];
    var rows = this._pairTable()[weapon];
    if (!rows) return [0.0, null];
    var best = 0.0, who = null;
    for (var i = 0; i < party.length; i++) {
      if (i === skip) continue;
      var m = party[i], s = rows[m] || 0.0;
      if (s > best || (s === best && who !== null && s && m < who)) { best = s; who = m; }
    }
    return [best, who];
  };

  CompEngine.prototype.metaOf = function (w, party, skip) {
    /* (1 - λ)·solo + λ·best observed partner (mirrors engine.py meta_of;
       λ = weights.meta_pair, 0 on an older dataset = the solo prior). */
    var solo = this._soloOf(w), lam = this.metaPairW;
    if (!lam) return solo;
    return (1.0 - lam) * solo + lam * this._pairOf(w, party, skip)[0];
  };

  CompEngine.prototype.metaExplain = function (w, party) {
    /* Descriptive split of a CANDIDATE's meta term (mirrors engine.py
       meta_explain). Never a scoring input. */
    party = party || [];
    var pr = this._pairOf(w, party), raise_ = 0.0;
    if (this.metaPairW && party.length) {
      var plus = party.concat([w]);
      for (var i = 0; i < party.length; i++) {
        var cur = this._pairOf(party[i], party, i)[0];
        var nw = this._pairOf(party[i], plus, i)[0];
        if (nw > cur) raise_ += nw - cur;
      }
    }
    return { meta_solo: this._soloOf(w), meta_pair: pr[0], meta_partner: pr[1],
             meta_raise: raise_ };
  };

  CompEngine.prototype.viabilityOf = function (w) {
    return this._viability[w] || 0.0;
  };

  /* ---------------------------------------------------- comp-level score */
  CompEngine.prototype.compScore = function (party, combos, gears) {
    /* THE party-level objective (mirrors engine.py comp_score). */
    var meta = 0.0, viab = 0.0;
    for (var i = 0; i < party.length; i++) {
      meta += this.metaOf(party[i], party, i);
      viab += this.viabilityOf(party[i]);
    }
    return this.alpha * this.fitness(party, combos, gears)
         + this.beta * this.synergy(party, combos)
         + this.delta * meta
         + this.viabilityW * viab
         - this.rho * this.redundancy(party);
  };

  /* ------------------------------------------------ candidate evaluation */
  CompEngine.prototype.partyState = function (party, combos, gears) {
    /* Everything a candidate marginal needs (mirrors engine.py).
       The dressed forge: `s` is the FIT supply (gear-inclusive
       when gears are given), `sSyn` the weapon-only supply every synergy
       term reads — comp_score's own seams. gears absent keeps both the
       same object (bit-identical to the pre-gears state). */
    var st = this._synState(party, combos), sSyn = st[0], J = st[1];
    gears = this._partyGears(gears, party.length);
    var anyGear = false;
    if (gears) {
      for (var gi = 0; gi < gears.length; gi++) {
        if (gears[gi] && gears[gi].length) { anyGear = true; break; }
      }
    }
    var s = anyGear ? this.effectiveSupply(party, combos, gears) : sSyn;
    var pairVals = [];
    for (var p = 0; p < this._activeSyn.length; p++) {
      pairVals.push(this._pairValue(p, sSyn[this._activeSyn[p][0]] || 0.0,
                                    sSyn[this._activeSyn[p][1]] || 0.0, J[p]));
    }
    var counts = {};
    for (var i = 0; i < party.length; i++) {
      counts[party[i]] = (counts[party[i]] || 0) + 1;
    }
    /* nsMax: the largest count-once contribution per spell on the
       weapon-only basis (synergy and floor terms); nsMaxFit: the largest
       share AS WORN on the fit supply — the same object on a naked party
       (mirrors engine.py party_state) */
    var nsMax = {}, nsFit = anyGear ? {} : null;
    if (this.hasNonstack) {
      for (i = 0; i < party.length; i++) {
        var per = this._nonstackContrib(party[i], combos ? combos[i] : null);
        var mg = anyGear && gears ? gears[i] : null;
        for (var sid in per) {
          var cur = nsMax[sid] || (nsMax[sid] = {});
          for (var cap in per[sid]) {
            if (per[sid][cap] > (cur[cap] || 0.0)) cur[cap] = per[sid][cap];
          }
          if (nsFit !== null) {
            var curf = nsFit[sid] || (nsFit[sid] = {});
            for (var capf in per[sid]) {
              var vf = per[sid][capf];
              if (mg && mg.length) vf = this._nsShare(vf, capf, mg, party[i]);
              if (vf > (curf[capf] || 0.0)) curf[capf] = vf;
            }
          }
        }
      }
    }
    var waived = gears ? this.selfCostWaivers(gears) : {};
    return { s: s, sSyn: sSyn, J: J, pairVals: pairVals, counts: counts,
             nsMax: nsMax, nsMaxFit: nsFit === null ? nsMax : nsFit,
             /* carrier quota: what this roster already wears */
             carriers: this._carrierCounts(party, gears),
             /* self-cost offsets: what this roster has waived, and the
                refund a candidate completing a pair hands the existing
                wearers (mirrors engine.py party_state) */
             waived: waived,
             pending: anyGear ? this._offsetPending(party, combos, gears, waived) : {},
             /* pair-aware prior: each seat's best observed
                partner so far, so a candidate's exact meta delta can include
                the raise it hands existing members */
             party: party.slice(),
             pairMax: party.map(function (w, i) { return this._pairOf(w, party, i)[0]; }, this) };
  };

  CompEngine.prototype._margFitFrom = function (s, extra, sFloor, extraFloor) {
    /* Option C: dressed callers pass sFloor (the weapon+loadout party
       supply) and extraFloor (the candidate's weapon-only adjusted caps)
       so floor terms never see gear (mirrors engine.py _marg_fit_from);
       defaults = legacy naked path, bit-identical. */
    var total = 0.0;
    if (sFloor === undefined || sFloor === null) {
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
    }
    var ef = extraFloor || {};
    for (var cap2 in extra) {
      var gain2 = extra[cap2];
      if (!(cap2 in this.reqs) || !gain2) continue;
      var have2 = s[cap2] || 0.0, target2 = this.target(cap2), soft2 = this.softCap(cap2);
      var ct2 = this._coverTerms(cap2, have2, gain2, target2,
                                 sFloor[cap2] || 0.0, ef[cap2] || 0.0);
      total += ct2[0];
      total += ct2[1];
      total -= (this._overstack(cap2, have2 + gain2, target2, soft2)
                - this._overstack(cap2, have2, target2, soft2));
    }
    /* a capability the kit zeroes (a self-cost) while the weapon still
       supplies it adds no coverage, but the floor reads the weapon basis,
       so its floor lift stands (mirrors engine.py, F44) */
    for (var cap3 in ef) {
      var gf = ef[cap3];
      if (!gf || extra[cap3] || !(cap3 in this.reqs)) continue;
      var hf = sFloor[cap3] || 0.0;
      total += this._floorPenalty(cap3, hf) - this._floorPenalty(cap3, hf + gf);
    }
    return total;
  };

  CompEngine.prototype._margSynFrom = function (state, extra, extraJ) {
    /* extraJ (default: extra) is the member's UNADJUSTED caps for the
       largest-single-member joint term J (mirrors engine.py). */
    if (extraJ === undefined || extraJ === null) extraJ = extra;
    var total = 0.0;
    var sSyn = state.sSyn;
    for (var p = 0; p < this._activeSyn.length; p++) {
      var a = this._activeSyn[p][0], b = this._activeSyn[p][1];
      var j = Math.min(extraJ[a] || 0.0, extraJ[b] || 0.0);
      var j2 = state.J[p] > j ? state.J[p] : j;
      total += this._pairValue(p, (sSyn[a] || 0.0) + (extra[a] || 0.0),
                               (sSyn[b] || 0.0) + (extra[b] || 0.0), j2)
             - state.pairVals[p];
    }
    return total;
  };

  CompEngine.prototype._nonstackAdjust = function (state, weapon, combo, extra,
                                                   fit, gear) {
    /* Candidate caps with the count-once rule applied against the current
       party (mirrors engine.py _nonstack_adjust): the default prices the
       weapon-only basis (state.nsMax), `fit` the fit supply
       (state.nsMaxFit) with the candidate's share as worn in `gear`.
       Returns `extra` itself when nothing applies. */
    var nsMax = fit ? state.nsMaxFit : state.nsMax;
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
        if (gear && gear.length) v = this._nsShare(v, cap, gear, weapon);
        var gain = v - (pmax[cap] || 0.0);
        adj[cap] = (adj[cap] || 0.0) - v + (gain > 0.0 ? gain : 0.0);
      }
    }
    return adj === null ? extra : adj;
  };

  CompEngine.prototype._comboScore = function (state, weapon, i, extra) {
    /* One combo's value against a party state (mirrors engine.py
       _combo_score) — identical float-op order to the original loop.
       Option C: on a DRESSED party the floor terms read sSyn + the
       candidate's own (naked) caps; the fit side prices the dressed
       members' count-once shares (nsMaxFit), the floor and synergy sides
       the weapon-only ones. */
    var adj = this._nonstackAdjust(state, weapon, i, extra);
    var dFit;
    if (state.s !== state.sSyn) {
      var adjFit = adj === extra ? adj
        : this._nonstackAdjust(state, weapon, i, extra, true);
      dFit = this._margFitFrom(state.s, adjFit, state.sSyn, adj);
    } else {
      dFit = this._margFitFrom(state.s, adj);
    }
    var dSyn = this._margSynFrom(state, adj, extra);
    return { val: this.alpha * dFit + this.beta * dSyn, dFit: dFit, dSyn: dSyn };
  };

  CompEngine.prototype._pickTail = function (state, weapon, best) {
    /* Combo-independent candidate-score terms (mirrors engine.py
       _pick_tail). `meta` is the EXACT party-meta delta: the
       candidate's blended prior plus the raise it hands each member's
       best-partner term — same seat order as Python, same bits. */
    var party = state.party || [];
    var meta = this.metaOf(weapon, party), lam = this.metaPairW;
    if (lam && party.length) {
      var rows = this._pairTable();
      for (var i = 0; i < party.length; i++) {
        var s = (rows[party[i]] || {})[weapon] || 0.0;
        if (s > state.pairMax[i]) meta += lam * (s - state.pairMax[i]);
      }
    }
    var dup = (state.counts[weapon] || 0) + 1 - this._dupFree(weapon);
    var score = best.val + this.delta * meta
              + this.viabilityW * this.viabilityOf(weapon)
              - (dup > 0 ? this.rho * dup : 0.0);
    return { score: score, dFit: best.dFit, dSyn: best.dSyn, meta: meta, combo: best.combo };
  };

  CompEngine.prototype.kitVariants = function (weapon) {
    /* Doctrine kit variants for GENERATION (the dressed forge; mirrors
       engine.py kit_variants): v0 = the seat's context-free doctrine kit
       (off-tier slots stay unset), plus ONE divergent single-slot swap
       to a piece with a capability row (variant cap 2 — a performance
       bound; a weapon with no such piece has no v1); [["v0", null]]
       for weapons with no doctrine gear. NO doctrine passives anywhere
       in this path. */
    if (!this.dressCandidates) return [["v0", null]];  /* V3-W switch */
    var out = this._variantCache[weapon];
    if (out !== undefined) return out;
    var self = this;
    var topCap = function (k) {
      var extra = self.gearExtra(k);
      var best = null;
      var caps = Object.keys(extra).sort();
      for (var ci = 0; ci < caps.length; ci++) {
        var v = (self._weights[caps[ci]] || 0.0) * extra[caps[ci]];
        if (best === null || v > best[1]) best = [caps[ci], v];
      }
      return best === null ? null : best[0];
    };
    var ko = this.kitOptions(weapon);
    var SLOTS = ["head", "armor", "shoes", "cape", "offhand",
                 "potion", "food"];
    var v0 = {}, divergent = [];
    for (var si = 0; si < SLOTS.length; si++) {
      var slot = SLOTS[si];
      var opts = (ko.options[slot] || []).filter(function (o) {
        return !!o.doctrine;
      });
      if (!opts.length) continue;
      v0[slot] = opts[0].gear;
      var t0 = topCap(opts[0].gear);
      /* evidence band (mirrors engine.py): a divergent alternative must be
         worn >= half as often as the slot's modal piece */
      var n0 = (opts[0].doctrine_n || [0, 0])[0];
      for (var oi = 1; oi < opts.length; oi++) {
        var n1 = (opts[oi].doctrine_n || [0, 0])[0];
        if (n0 && n1 < 0.5 * n0) continue;
        /* an alternative must supply something (mirrors engine.py): a
           piece with no capability row is never the one alternative */
        var gx = this.gearExtras(opts[oi].gear), hasRow = false;
        for (var gi = 0; gi < gx.length; gi++) {
          if (Object.keys(gx[gi]).length) { hasRow = true; break; }
        }
        if (!hasRow) continue;
        if (topCap(opts[oi].gear) !== t0) {
          divergent.push([slot, opts[oi].gear]);
          break;
        }
      }
    }
    var gl = function (d) {
      var l = [];
      for (var sj = 0; sj < SLOTS.length; sj++) {
        if (d[SLOTS[sj]] !== undefined) l.push(d[SLOTS[sj]]);
      }
      return l;
    };
    if (!Object.keys(v0).length) {
      out = [["v0", null]];
    } else {
      out = [["v0", gl(v0)]];
      /* carrier quota (mirrors engine.py): a carrier modal
         chest gets the best NON-carrier chest as its one alternative */
      var caps = this.carrierCaps(), chest = v0.armor, carrier = false, ce;
      if (chest) {
        ce = this.itemEffects[chest] || [];
        for (var q0 = 0; q0 < ce.length; q0++) if (caps[ce[q0]] !== undefined) carrier = true;
      }
      var altChest = null;
      if (carrier) {
        var aopts = this.kitOptions(weapon, null, null, 8).options.armor || [];
        for (var ao = 0; ao < aopts.length; ao++) {
          if (!aopts[ao].doctrine || aopts[ao].gear === chest) continue;
          var ce2 = this.itemEffects[aopts[ao].gear] || [], isC = false;
          for (var q1 = 0; q1 < ce2.length; q1++) if (caps[ce2[q1]] !== undefined) isC = true;
          if (!isC) { altChest = aopts[ao].gear; break; }
        }
      }
      if (altChest !== null) {
        var alt0 = {};
        for (var k0 in v0) alt0[k0] = v0[k0];
        alt0.armor = altChest;
        out.push(["v1", gl(alt0)]);
        /* the non-carrier chest serves the cap only (mirrors engine.py) */
        this._variantFallback[weapon] = { v1: true };
      } else {
        for (var n = 0; n < Math.min(1, divergent.length); n++) {
          var alt = {};
          for (var k in v0) alt[k] = v0[k];
          alt[divergent[n][0]] = divergent[n][1];
          out.push(["v" + (n + 1), gl(alt)]);
        }
      }
    }
    this._variantCache[weapon] = out;
    return out;
  };

  CompEngine.prototype._dressedExtras = function (weapon) {
    /* Per variant, the member's effective caps per combo index (mirrors
       engine.py _dressed_extras). The naked variant reuses the
       combo-extras objects THEMSELVES (identity keeps the exactness
       proofs intact). */
    var out = this._dressedCache[weapon];
    if (out !== undefined) return out;
    var extras = this._comboExtras(weapon);
    out = {};
    var variants = this.kitVariants(weapon);
    for (var vi = 0; vi < variants.length; vi++) {
      var vkey = variants[vi][0], glist = variants[vi][1];
      if (glist === null) {
        out[vkey] = extras;
      } else {
        var lst = [];
        for (var i = 0; i < extras.length; i++)
          lst.push(this.buildExtra(weapon, i, glist));
        out[vkey] = lst;
      }
    }
    this._dressedCache[weapon] = out;
    return out;
  };

  CompEngine.prototype._comboScoreDressed = function (state, weapon, i,
                                                     wextra, dextra, refund,
                                                     vgears) {
    /* _comboScore for a DRESSED candidate: fit half prices the dressed
       vector, synergy half the weapon-only vector — the exact
       decomposition of compScore-with-gears (mirrors engine.py
       _combo_score_dressed). Same object -> exactly _comboScore.
       `vgears` is the kit dextra wears: its count-once share is priced
       as worn. */
    if (dextra === wextra) return this._comboScore(state, weapon, i, wextra);
    /* Option C: a DRESSED candidate's floor terms read the weapon-only
       basis on BOTH sides — sSyn for the party and the candidate's
       weapon-only adjusted gains — so its kit can never buy floor relief
       the party's kits are denied (mirrors engine.py). */
    var adj = this._nonstackAdjust(state, weapon, i, dextra, true, vgears);
    var adjW = this._nonstackAdjust(state, weapon, i, wextra);
    if (refund) {
      /* gear-side: joins the fit vector after the non-stacking
         adjustment, never the floor basis (mirrors engine.py) */
      var merged = {}, cap;
      for (cap in adj) merged[cap] = adj[cap];
      for (cap in refund) merged[cap] = (merged[cap] || 0.0) + refund[cap];
      adj = merged;
    }
    var dFit = this._margFitFrom(state.s, adj, state.sSyn, adjW);
    /* synergy prices the count-once weapon supply (adjW) with the
       member's unadjusted caps for J, as _comboScore does (mirrors
       engine.py) */
    var dSyn = this._margSynFrom(state, adjW, wextra);
    return { val: this.alpha * dFit + this.beta * dSyn,
             dFit: dFit, dSyn: dSyn };
  };

  CompEngine.prototype._evalPick = function (state, weapon) {
    /* THE candidate score — the exact compScore delta of adding `weapon`
       with its best loadout AND doctrine-kit variant (the dressed forge;
       mirrors engine.py _eval_pick). Returns
       {score, dFit, dSyn, meta, combo, variant, vgears}. */
    var best = null;
    var extras = this._comboExtras(weapon);
    var dressed = this._dressedExtras(weapon);
    var variants = this.kitVariants(weapon);
    var v0Capped = this._variantCapped(state, weapon, variants[0][1]);
    var fallback = this._variantFallback[weapon] || {};
    for (var vi = 0; vi < variants.length; vi++) {
      var vkey = variants[vi][0], vgears = variants[vi][1];
      if (this._variantCapped(state, weapon, vgears)) continue;   /* carrier quota */
      if (fallback[vkey] && !v0Capped) continue;   /* cap fallback only */
      var dext = dressed[vkey];
      for (var i = 0; i < extras.length; i++) {
        var ov = this._offsetVector(state, weapon, i, vgears);
        var cs = ov === null
          ? this._comboScoreDressed(state, weapon, i, extras[i], dext[i],
                                    null, vgears)
          : this._comboScoreDressed(state, weapon, i, extras[i], ov[0], ov[1],
                                    vgears);
        if (best === null || cs.val > best.val + PICK_TIE_EPS)
          best = { val: cs.val, dFit: cs.dFit, dSyn: cs.dSyn, combo: i,
                   variant: vkey, vgears: vgears };
      }
    }
    if (best === null)
      best = { val: 0.0, dFit: 0.0, dSyn: 0.0, combo: null,
               variant: "v0", vgears: null };
    var tail = this._pickTail(state, weapon, best);
    tail.variant = best.variant;
    tail.vgears = best.vgears;
    return tail;
  };

  CompEngine.prototype._asBuilt = function (state, weapon, combo, gear) {
    /* The exact compScore delta of adding `weapon` in ONE given build —
       its own combo (null or out of range: the default) and kit — to the
       party `state` describes: _evalPick's marginal without the search,
       no carrier quota or variant fallback (mirrors engine.py
       _as_built). */
    var extras = this._comboExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    var cs;
    if (gear && gear.length) {
      var ov = this._offsetVector(state, weapon, combo, gear);
      cs = ov === null
        ? this._comboScoreDressed(state, weapon, combo, extras[combo],
                                  this.buildExtra(weapon, combo, gear), null,
                                  gear)
        : this._comboScoreDressed(state, weapon, combo, extras[combo], ov[0],
                                  ov[1], gear);
    } else {
      cs = this._comboScore(state, weapon, combo, extras[combo]);
    }
    return this._pickTail(state, weapon, { val: cs.val, dFit: cs.dFit,
                                           dSyn: cs.dSyn, combo: combo }).score;
  };

  CompEngine.prototype._rawMemberCaps = function (weapon, combo) {
    /* The member's RAW one-spell-per-slot capability points (loadout
       always + chosen bundles, sheet 1-7 scale) — content- and style-
       independent; flat sheet fallback (mirrors engine.py
       _raw_member_caps). */
    var extras = this._comboExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    var lo = this.weapons[weapon].loadout || {};
    /* an empty `always` is no loadout, as in engine.py */
    if (!(present(lo.slots) || present(lo.always)))
      return this.weapons[weapon].capabilities;
    var slots = lo.slots || [];
    var chosen = [];
    var choices = this.comboChoices(weapon, combo);
    for (var ci = 0; ci < choices.length; ci++) {
      var oi = choices[ci][0], bi = choices[ci][1];
      if (oi < slots.length && bi < slots[oi].length) chosen.push(slots[oi][bi]);
    }
    return mergeMax(lo.always || {}, chosen);
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
    var caps = this._rawMemberCaps(weapon, combo);
    var out = {};
    for (var pn in this.predDefs) {
      var mins = this.predDefs[pn], okp = true;
      for (var pc in mins) {
        if ((caps[pc] || 0) < mins[pc]) { okp = false; break; }
      }
      if (okp) out[pn] = true;
    }
    /* flag predicate: a full healer qualifies with EVERY combo (the E,
       which carries the heal, is fixed per weapon — mirrors engine.py) */
    if (this.weapons[weapon].full_healer) out[this.PRIMARY_HEAL] = true;
    if (this.predMembers[this.STANDOFF][weapon]) out[this.STANDOFF] = true;
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

  CompEngine.prototype.explain = function (party, candidate, combos, gears) {
    /* Per-capability delta terms for the candidate's CHOSEN loadout and
       kit — the gap-closing half (coverage + floor lift) of the same
       _pickCaps rows pickReport shows, so the kit, the count-once rule
       and the self-cost offset reach the text exactly as they reached the
       score (mirrors engine.py explain). */
    var state = this.partyState(party, combos, gears);
    var pick = this._evalPick(state, candidate);
    var rows = this._pickCaps(state, candidate, pick.combo, pick.vgears)[0];
    var terms = [];
    for (var ri = 0; ri < rows.length; ri++) {
      var r = rows[ri], d = r.coverage + r.floor_lift;
      if (d > 0.05) {
        terms.push({ delta: round2(d), cap: r.cap,
                     before: r.before, after: r.after, target: r.target });
      }
    }
    return terms.sort(function (x, y) {
      var kx = qrank(x.delta), ky = qrank(y.delta);
      if (kx !== ky) return ky - kx;
      return x.cap < y.cap ? -1 : x.cap > y.cap ? 1 : 0;
    });
  };

  /* ------------------------------------- negative recs / redundancy lens
     (mirrors engine.py.) A DESCRIPTIVE
     decomposition of the same exact marginal _evalPick scores — the
     "why not" counterpart of explain(). A scoring-side redundancy penalty
     was investigated and REJECTED (MECHANICS_TODO Q18); nothing here
     feeds a score. */
  CompEngine.prototype._nrGainMax = function () {
    /* Redundancy verdict threshold (mechanics.yaml negative_recs,
       PROVISIONAL, MASTERSHEET-tunable). */
    var cfg = this.mechanics.negative_recs || {};
    return (cfg.redundant_gain_max === undefined) ? 0.05 : cfg.redundant_gain_max;
  };

  CompEngine.prototype._pickCaps = function (state, weapon, combo, vgears) {
    /* [rows, capsGain] — signed per-capability terms of the fitness
       marginal for the DRESSED chosen variant (rows sum to _evalPick's
       dFit); capsGain is the GAP-CLOSING part alone: below-target
       coverage + floor lift, headroom-band depth excluded (mirrors
       engine.py _pick_caps). */
    var ov = (vgears && vgears.length) ? this._offsetVector(state, weapon, combo, vgears) : null;
    var extra = ov ? ov[0]
      : (vgears && vgears.length)
        ? this.buildExtra(weapon, combo, vgears)
        : this.memberExtra(weapon, combo);
    /* the fit rows price the count-once rule on the fit supply, the
       candidate's share as worn (mirrors engine.py) */
    var adj = this._nonstackAdjust(state, weapon, combo, extra, true, vgears);
    if (ov) {
      var mergedR = {}, rc;
      for (rc in adj) mergedR[rc] = adj[rc];
      for (rc in ov[1]) mergedR[rc] = (mergedR[rc] || 0.0) + ov[1][rc];
      adj = mergedR;
    }
    /* Option C floor basis: floor_lift rows read the weapon-only party
       supply and the candidate's weapon-only adjusted gains, exactly as
       the marginal scored them (mirrors engine.py _pick_caps). */
    var adjW = this._nonstackAdjust(state, weapon, combo,
      (vgears && vgears.length) ? this.memberExtra(weapon, combo) : extra);
    var s = state.s, sf = state.sSyn, rows = [], capsGain = 0.0;
    for (var cap in adj) {
      var gain = adj[cap];
      if (!(cap in this.reqs) || !gain) continue;
      var have = s[cap] || 0.0, target = this.target(cap), soft = this.softCap(cap);
      var ct = this._coverTerms(cap, have, gain, target,
                                sf[cap] || 0.0, adjW[cap] || 0.0);
      var cov = ct[0], floorD = ct[1];
      var over = (this._overstack(cap, have + gain, target, soft)
                  - this._overstack(cap, have, target, soft));
      var head = (this._headroomBonus(cap, have + gain, target, soft)
                  - this._headroomBonus(cap, have, target, soft));
      capsGain += cov + floorD - head;
      rows.push({ cap: cap, gain: gain, before: have, after: have + gain,
                  target: target, soft_cap: soft,
                  coverage: cov, floor_lift: floorD, overstack_cost: over,
                  delta: cov + floorD - over, saturated: have >= target });
    }
    /* a capability the kit zeroes while the weapon still supplies it: no
       coverage, its floor lift on the weapon basis, so the rows still sum
       to dFit (mirrors engine.py, F44) */
    for (var fc in adjW) {
      var gf = adjW[fc];
      if (!gf || adj[fc] || !(fc in this.reqs)) continue;
      var hf = sf[fc] || 0.0;
      var fl = this._floorPenalty(fc, hf) - this._floorPenalty(fc, hf + gf);
      if (!fl) continue;
      var haveF = s[fc] || 0.0, targetF = this.target(fc);
      capsGain += fl;
      rows.push({ cap: fc, gain: 0.0, before: haveF, after: haveF,
                  target: targetF, soft_cap: this.softCap(fc),
                  coverage: 0.0, floor_lift: fl, overstack_cost: 0.0,
                  delta: fl, saturated: haveF >= targetF });
    }
    rows.sort(function (x, y) {
      var kx = qrank(x.delta), ky = qrank(y.delta);
      if (kx !== ky) return ky - kx;
      return x.cap < y.cap ? -1 : x.cap > y.cap ? 1 : 0;
    });
    return [rows, capsGain];
  };

  CompEngine.prototype._pickVerdict = function (score, capsGain) {
    /* One rule, every surface (mirrors engine.py _pick_verdict). */
    if (score <= 0.0) return "negative";
    if (capsGain <= this._nrGainMax()) return "redundant";
    return "ok";
  };

  CompEngine.prototype.pickReport = function (party, candidate, combos,
                                              gears) {
    /* Full SIGNED decomposition of the candidate's pick score — the
       'why / why not' panel (mirrors engine.py pick_report). caps rows sum
       to d_fitness; alpha*d_fitness + beta*d_synergy + delta*meta
       + viability*viab - dup_penalty reconstructs the score.
       DESCRIPTIVE ONLY — computing it never changes a score. */
    var state = this.partyState(party, combos, gears);
    var pick = this._evalPick(state, candidate);
    var pc = this._pickCaps(state, candidate, pick.combo, pick.vgears);
    var rows = pc[0], capsGain = pc[1];
    var dup = (state.counts[candidate] || 0) + 1 - this._dupFree(candidate);
    var dupPenalty = dup > 0 ? this.rho * dup : 0.0;
    /* count-once losses on the fit supply the caps rows price, each
       share as worn (mirrors engine.py pick_report) */
    var nsLines = [];
    var nsMax = state.nsMaxFit || {};
    var contrib = this._nonstackContrib(candidate, pick.combo);
    var sids = Object.keys(contrib).sort();
    for (var si = 0; si < sids.length; si++) {
      var sid = sids[si], pmax = nsMax[sid];
      if (!pmax) continue;
      var caps = this.nonstack[sid], lost = {}, any = false;
      for (var cj = 0; cj < caps.length; cj++) {
        var cap = caps[cj], v = contrib[sid][cap] || 0.0;
        if (v && pick.vgears && pick.vgears.length)
          v = this._nsShare(v, cap, pick.vgears, candidate);
        var cut = v < (pmax[cap] || 0.0) ? v : (pmax[cap] || 0.0);
        if (v && cut > 0.0) { lost[cap] = cut; any = true; }
      }
      if (any) {
        var rec = this.interactions[sid] || {};
        nsLines.push({ spell: sid, name: rec.name || sid, lost: lost });
      }
    }
    var mx = this.metaExplain(candidate, party);
    return {
      weapon: candidate,
      display_name: this.weapons[candidate].display_name,
      combo: pick.combo, kit: pick.vgears || [], score: pick.score,
      d_fitness: pick.dFit, d_synergy: pick.dSyn,
      meta_prior: pick.meta, viability: this.viabilityOf(candidate),
      meta_solo: mx.meta_solo, meta_pair: mx.meta_pair,
      meta_partner: mx.meta_partner, meta_raise: mx.meta_raise,
      dup_penalty: dupPenalty,
      caps: rows, caps_gain: capsGain,
      nonstack: nsLines,
      verdict: this._pickVerdict(pick.score, capsGain),
    };
  };

  CompEngine.prototype._pool = function (pool) {
    /* mirrors engine.py `self.suggest_pool() if pool is None else pool`:
       no pool (null/undefined) is the suggestion pool (game-retired weapons
       and this context's viability exclusions left out); a given list,
       empty included, is the candidate set as given (F37) */
    return (pool === undefined || pool === null) ? this._suggest : pool;
  };

  CompEngine.prototype.recommend = function (party, topN, pool, combos,
                                             gears) {
    /* null reads as the default, as in engine.py (F45) */
    if (topN === undefined || topN === null) topN = 4;
    var state = this.partyState(party, combos, gears);
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
        combo: ps.combo, kit: ps.vgears || [],
        score: ps.score,
      });
    }
    /* Deterministic ranking (mirrors engine.py recommend):
       score quantized to the parity tolerance first, then weapon id -
       an exact tie must not fall to pool order plus last-bit noise. */
    out = out.sort(function (x, y) {
      var kx = qrank(x.score), ky = qrank(y.score);
      if (kx !== ky) return ky - kx;
      return x.weapon < y.weapon ? -1 : (x.weapon > y.weapon ? 1 : 0);
    }).slice(0, topN);
    /* verdict lens on the returned rows only (mirrors engine.py): a
       suggestion that survives ranking can still be a depth pick in a
       saturated comp — say so instead of implying it fills a gap */
    for (i = 0; i < out.length; i++) {
      var pc = this._pickCaps(state, out[i].weapon, out[i].combo,
                              out[i].kit.length ? out[i].kit : null);
      out[i].caps_gain = pc[1];
      out[i].verdict = this._pickVerdict(out[i].score, pc[1]);
      var mx = this.metaExplain(out[i].weapon, party);
      out[i].meta_solo = mx.meta_solo; out[i].meta_pair = mx.meta_pair;
      out[i].meta_partner = mx.meta_partner; out[i].meta_raise = mx.meta_raise;
    }
    return out;
  };

  CompEngine.prototype.swapReview = function (party, topN, pool, combos,
                                              gears) {
    /* Per-member swap advisor (mirrors engine.py swap_review), a
       WEAPON-CHOICE read: each member valued exactly as _evalPick would
       value it into the REST of the party, its combo and kit re-resolved
       like every alternative's (score, rank, verdict, option gain; combo
       and kit name the build score assumed). Beside it the member AS
       BUILT: built_score is the exact compScore(party) - compScore(rest)
       in its own combo and kit (_asBuilt on the rest's state), build_gap
       = score - built_score, and each option's delta is the exact
       compScore change of the swap landing in the option's combo and kit.
       `off_comp` flags viability-excluded members. */
    if (topN === undefined || topN === null) topN = 3;   /* F45 */
    var out = [];
    var keys = this._pool(pool);
    var self = this;
    for (var i = 0; i < party.length; i++) {
      var cur = party[i];
      var rest = party.slice(0, i).concat(party.slice(i + 1));
      var restCombos = combos
        ? combos.slice(0, i).concat(combos.slice(i + 1)) : null;
      var restGears = gears
        ? gears.slice(0, i).concat(gears.slice(i + 1)) : null;
      var state = this.partyState(rest, restCombos, restGears);
      var curPick = this._evalPick(state, cur);
      var curScore = curPick.score;
      var built = this._asBuilt(state, cur, combos ? combos[i] : null,
                                gears ? gears[i] : null);
      /* redundancy lens (mirrors engine.py): the member
         valued exactly as a pick into the rest — does it still close any
         gap, or are its jobs already covered without it? Flag only. */
      var curPc = this._pickCaps(state, cur, curPick.combo, curPick.vgears);
      var curVerdict = this._pickVerdict(curScore, curPc[1]);
      var better = [];
      for (var j = 0; j < keys.length; j++) {
        var w = keys[j];
        if (w === cur) continue;
        var pk = this._evalPick(state, w);
        if (pk.score > curScore) better.push([pk.score, w, pk.combo, pk.vgears]);
      }
      better.sort(function (a, b) {
        var ka = qrank(a[0]), kb = qrank(b[0]);
        if (ka !== kb) return kb - ka;
        return a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0;
      });
      out.push({
        index: i, weapon: cur,
        display_name: this.weapons[cur].display_name,
        /* rank = strictly-better alternatives + 1 (ties never demote) */
        score: curScore, rank: better.length + 1,
        combo: curPick.combo, kit: (curPick.vgears || []).slice(),
        built_score: built, build_gap: curScore - built,
        off_comp: this.isExcluded(cur),
        off_style: this.isStyleUnfit(cur),
        caps_gain: curPc[1],
        verdict: curVerdict,
        redundant: curVerdict !== "ok",
        options: better.slice(0, topN).map(function (t) {
          return { weapon: t[1],
                   display_name: self.weapons[t[1]].display_name,
                   score: t[0], gain: t[0] - curScore, delta: t[0] - built,
                   combo: t[2], kit: (t[3] || []).slice() };
        }),
      });
    }
    return out;
  };

  CompEngine.prototype.weaknesses = function (party, topN, combos, gears) {
    if (topN === undefined || topN === null) topN = 3;   /* F45 */
    var s = this.effectiveSupply(party, combos, gears), gaps = [];
    for (var cap in this.reqs) {
      var have = s[cap] || 0;
      gaps.push({ cap: cap,
                  gap: this.weight(cap) * (1 - Math.pow(Math.min(1.0, have / this.target(cap)), this.gamma)),
                  have: have, target: this.target(cap) });
    }
    return gaps.sort(function (x, y) {
      var kx = qrank(x.gap), ky = qrank(y.gap);
      if (kx !== ky) return ky - kx;
      return x.cap < y.cap ? -1 : x.cap > y.cap ? 1 : 0;
    }).slice(0, topN);
  };

  CompEngine.prototype.uncoveredCaps = function (party, combos, gears) {
    /* gears: the members' worn kits, read like every other board number
       (mirrors engine.py uncovered_caps) */
    var s = this.effectiveSupply(party, combos, gears), out = [];
    for (var cap in this.reqs) {
      if (this.weight(cap) >= 5 && (s[cap] || 0) / this.target(cap) < 0.5) out.push(cap);
    }
    return out;
  };

  /* ----------------------------------------------- interaction analysis
     (mirrors engine.py duplicate_conflicts / analyze). Severity
     high/warning only on VERIFIED non-stacking records;
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
      var soft = this.softCap(cap);
      /* saturation band (mirrors engine.py analyze):
         gap below target, headroom to soft cap, overstacked past it */
      var band = have < target ? "gap"
               : have <= soft ? "headroom" : "overstacked";
      if (have >= target) {
        strengths.push({ cap: cap, have: have, target: target,
                         soft_cap: soft, band: band });
      } else if (this.weight(cap) > 0) {
        missing.push({ cap: cap, have: have, target: target,
                       soft_cap: soft, band: band,
                       gap: target - have,
                       weighted_gap: this.weight(cap) * (target - have) / target });
      }
    }
    missing.sort(function (a, b) {
      var ka = qrank(a.weighted_gap), kb = qrank(b.weighted_gap);
      if (ka !== kb) return kb - ka;
      return a.cap < b.cap ? -1 : a.cap > b.cap ? 1 : 0;
    });
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

  /* Identity thresholds (descriptive layer, F-V3-2) — mirrors engine.py
     comp_identity, thresholds calibrated against every style-declared
     comp on file (see VALIDATION.md, V3 round 1). */
  var IDENTITY_MELEE_CORE = 0.65, IDENTITY_RANGED_CORE = 0.35,
      IDENTITY_STRONG = 0.80, IDENTITY_CLAP_AOE = 0.50,
      IDENTITY_BC_AOE = 0.45,
      IDENTITY_BC_MELEE_BOMB = 0.5,   /* the ball itself carries half the bomb */
      IDENTITY_CARRIER_MIN = 4, IDENTITY_MIN_MEMBERS = 3,
      IDENTITY_RANGED_ATTACK = 9.0,
      IDENTITY_HYBRID_AOE = 0.45,     /* 0.40 -> 0.45, validation round 2 */
      IDENTITY_KITE_TOOLS_PER = 10,   /* standoff tools per members */
      IDENTITY_FLEX_HOME = 2.0,       /* rigid melee : rigid ranged that pulls flex bombs home */
      IDENTITY_LONE_TOOL_AOE = 0.45,  /* a lone standoff body makes a kite only below this bomb share */
      /* the gank read (validation round 4; mirrors engine.py): every catch
         tool on a dps seat, no bomb share, 14 or fewer members */
      IDENTITY_GANK_MAX = 14, IDENTITY_GANK_AOE = 0.45,
      IDENTITY_CATCH_CAPS = ["catch", "engage", "clump_create"];
  var DOCTRINE_GANG_MAX = 9;   /* party sizes that read the gang doctrine band */
  /* SEAT POOLING (R34a/b; mirrors engine.py POOL_MIN_VOTES /
     POOLED_SLOTS / CHEST_POOLED_SLOTS): a thin weapon slot is dressed from
     the seat's pool (same-chest for helmet/boots/cape, plain for
     potion/food) when the pool item has 5+ players */
  var POOL_MIN_VOTES = 5;
  var POOLED_SLOTS = { head: true, shoes: true, cape: true, potion: true, food: true };
  var CHEST_POOLED_SLOTS = { head: true, shoes: true, cape: true };
  var IDENTITY_STYLES = { brawl: true, clap: true, kite: true,
                          brawl_clap: true, clap_kite: true };

  CompEngine.prototype._styleFitOf = function (weapon) {
    /* The weapon's derived style/size identity; null on pre-identity
       datasets (mirrors engine.py _style_fit_of). */
    return this.weapons[weapon].style_fit || null;
  };

  /* the weapons the dominant winners of the pool covering `size` field
     (template pool_fielded), as a lookup; null where no pool covers the
     size (mirrors engine.py _pool_fielded) */
  CompEngine.prototype._poolFielded = function (size) {
    var pools = this.template.pool_fielded || {};
    for (var key in pools) {
      var row = pools[key];
      if (row.sizes[0] <= size && size <= row.sizes[1]) {
        var out = {};
        for (var i = 0; i < row.weapons.length; i++) out[row.weapons[i]] = true;
        return out;
      }
    }
    return null;
  };

  CompEngine.prototype._openFielded = function () {
    /* mirrors engine.py _open_fielded: the declared identity style's band
       list, balanced the pooled one, as a lookup; null below the style
       floor, outside every band or where the cell carries no list */
    var sk = this.skeleton || {};
    var fl = sk.fielded || {};
    var anyF = false;
    for (var k4 in fl) { anyF = true; break; }
    if (!anyF) return null;
    var floor = sk.style_min_size === undefined ? 10 : sk.style_min_size;
    if (this.size < floor) return null;
    var bands = fl.bands || {}, band = null;
    for (var bk in bands) {
      if (bands[bk][0] <= this.size && this.size <= bands[bk][1]) { band = bk; break; }
    }
    if (band === null) return null;
    var row = IDENTITY_STYLES[this.style]
      ? ((fl.styles || {})[this.style] || {})[band]
      : (fl.pooled || {})[band];
    if (!row || !row.length) return null;
    var out = {};
    for (var i = 0; i < row.length; i++) out[row[i]] = true;
    return out;
  };

  /* the matchmaking pool whose sizes cover `size` (template pool_rows,
     derive_portal_rows.py), with its key; null without (mirrors engine.py) */
  CompEngine.prototype._poolRows = function (size) {
    var pools = this.template.pool_rows || {};
    for (var key in pools) {
      var row = pools[key];
      if (row.sizes[0] <= size && size <= row.sizes[1]) {
        var out = {};
        for (var k in row) out[k] = row[k];
        out.key = key;
        return out;
      }
    }
    return null;
  };

  CompEngine.prototype._fitBand = function () {
    /* trio <=3, gang 4-9, group 10+ (mirrors engine.py _fit_band). */
    return this.size <= 3 ? "trio" : this.size <= 9 ? "gang" : "group";
  };

  CompEngine.prototype._chestSide = function (chest) {
    /* the style side a dps chest votes for: the item's harvest lean
       (dataset chest_lean) first, else the class rule (mirrors engine.py) */
    var items = (this.data.chest_lean || {}).items || {};
    var lean = (items[chest] || {}).lean;
    if (lean) return lean;
    var cls = this._chestClass(chest);
    return cls === "leather" ? "brawl" : cls === "cloth" ? "ranged" : null;
  };
  CompEngine.prototype._kitLean = function (party, gears) {
    /* dps chest majority by style side from the worn kits (mirrors
       engine.py _kit_lean): "brawl" / "ranged" / null */
    if (!gears) return null;
    var dps = [], i;
    for (i = 0; i < party.length; i++) if (this.roleOf(party[i]) === "dps") dps.push(i);
    if (!dps.length) return null;
    var counts = {}, known = 0;
    for (i = 0; i < dps.length; i++) {
      var gl = dps[i] < gears.length ? gears[dps[i]] : null, chest = null;
      for (var j = 0; gl && j < gl.length; j++) {
        var gk = this._gearItemKey(gl[j]);
        if (gk.indexOf("ARMOR_") === 0) { chest = gk; break; }
      }
      if (!chest || !this._chestClass(chest)) continue;
      known += 1;
      var side = this._chestSide(chest);
      if (side) counts[side] = (counts[side] || 0) + 1;
    }
    if (known < 0.5 * dps.length) return null;
    if ((counts.brawl || 0) > 0.5 * known) return "brawl";
    if ((counts.ranged || 0) > 0.5 * known) return "ranged";
    return null;
  };
  CompEngine.prototype.compIdentity = function (party, combos, gears) {
    /* What this comp is BECOMING, in playstyle vocabulary — v2: built up
       from MEMBER identities (weapon style_fit: E-first delivery +
       style_overrides.yaml). DESCRIPTIVE ONLY: nothing here feeds fitness,
       recommendation order, or the forge (mirrors engine.py
       comp_identity). */
    var n = party.length;
    var melee = 0.0, ranged = 0.0, aoe = 0.0, sus = 0.0, st = 0.0,
        commit = 0.0, evade = 0.0, kiteTools = 0, meleeBomb = 0.0;
    var pending = [];
    var carriers = { melee: [], ranged: [] };
    var carrierCount = {};
    var nCarrierMembers = 0;
    var flex = {};
    var sides = {};
    /* the gank read's two counts: catch-tool points on the dps seats (the
       core) and on every other seat (the line) — mirrors engine.py */
    var coreCatch = 0, lineCatch = 0;
    for (var i = 0; i < n; i++) {
      var w = party[i];
      var caps = this._rawMemberCaps(w, combos ? combos[i] : null);
      var dmg = 0;
      for (var di = 0; di < DAMAGE_CAPS_PROFILE.length; di++)
        dmg += caps[DAMAGE_CAPS_PROFILE[di]] || 0;
      var hold = 0;
      for (var hi = 0; hi < IDENTITY_CATCH_CAPS.length; hi++)
        hold += caps[IDENTITY_CATCH_CAPS[hi]] || 0;
      if (this.roleOf(w) === "dps") coreCatch += hold; else lineCatch += hold;
      var sf0 = this._styleFitOf(w) || {};
      /* clap half: a ramp-dependent bomb counts as sustained; standoff
         E = kite tool (mirrors engine.py) */
      if (sf0.conditional_payload) sus += caps.burst_aoe || 0;
      else {
        aoe += caps.burst_aoe || 0;
        if (sf0.delivery === "melee" && sf0.damage_scale === "group")
          meleeBomb += caps.burst_aoe || 0;
      }
      if (sf0.standoff_e) kiteTools += 1;
      sus += caps.sustained_dps || 0;
      st += (caps.burst_st || 0) + (caps.execute || 0);
      commit += (caps.engage || 0) + (caps.clump_create || 0);
      evade += (caps.mobility || 0) + (caps.disengage || 0);
      if (dmg < IDENTITY_CARRIER_MIN) continue;
      var sf = this._styleFitOf(w);
      var delivery;
      if (sf) {
        delivery = sf.delivery;
      } else {
        var ar = ((this.statsOf(w).stats || {}).attackrange) || 0;
        delivery = ar >= IDENTITY_RANGED_ATTACK ? "ranged" : "melee";
      }
      var side = delivery === "ranged" ? "ranged" : "melee";
      if (this.roleOf(w) === "frontline") {
        /* a frontline counts melee by its seat, whatever its delivery
           (validation round 4, roster 11); the line, not the damage core:
           it weighs in neither rigid core and anchors no split (mirrors
           engine.py) */
        side = "front";
      } else if (delivery === "flex") {
        flex[w] = true;
        /* a flex BOMB (unconditional group payload at range) joins the
           rigid core below; single-target / ramp flex stays melee */
        if (sf.damage_scale === "group" && !sf.conditional_payload) side = "flex";
      }
      pending.push([i, w, dmg, side]);
      carrierCount[w] = (carrierCount[w] || 0) + 1;
      nCarrierMembers += 1;
    }
    /* flex bombs join the rigid core (validation rounds 1 and 2; mirrors
       engine.py comp_identity) */
    var rigidMelee = 0.0, rigidRanged = 0.0, pi;
    for (pi = 0; pi < pending.length; pi++) {
      if (pending[pi][3] === "melee") rigidMelee += pending[pi][2];
      else if (pending[pi][3] === "ranged") rigidRanged += pending[pi][2];
    }
    /* a flex bomb goes home to melee only when the rigid core is CLEARLY
       melee (validation round 3; mirrors engine.py) */
    var flexSide = (rigidMelee >= IDENTITY_FLEX_HOME * Math.max(rigidRanged, 1e-9)
                    && rigidRanged < rigidMelee) ? "melee" : "ranged";
    for (pi = 0; pi < pending.length; pi++) {
      var pIdx = pending[pi][0], pW = pending[pi][1], pDmg = pending[pi][2],
          pSide = pending[pi][3] === "flex" ? flexSide
                : pending[pi][3] === "front" ? "melee" : pending[pi][3];
      sides[pIdx] = pSide;
      if (carriers[pSide].indexOf(pW) === -1) carriers[pSide].push(pW);
      if (pSide === "ranged") ranged += pDmg; else melee += pDmg;
    }
    var tot = melee + ranged;
    var dmgTot = aoe + sus + st;
    var mel = tot ? melee / tot : 0.5;
    var mode = { aoe: dmgTot ? aoe / dmgTot : 0.0,
                 sustained: dmgTot ? sus / dmgTot : 0.0,
                 single_target: dmgTot ? st / dmgTot : 0.0 };
    var posture = (commit + evade) ? commit / (commit + evade) : 0.5;
    var perTen = Math.floor(n / IDENTITY_KITE_TOOLS_PER + 0.5);
    var kiteMin = Math.max(2, perTen);
    var kiteHalf = kiteTools >= kiteMin;                 /* hybrid: tools at scale */
    /* a lone standoff body below the hybrid floor only makes a kite of a
       comp that is not bombing (validation round 3, roster 4; mirrors
       engine.py) */
    var kiteAny = kiteTools >= kiteMin ||
                  (kiteTools >= Math.max(1, perTen) && mode.aoe < IDENTITY_LONE_TOOL_AOE);
    var bcBomb = aoe ? meleeBomb / aoe : 0.0;
    var band = this._fitBand();
    var out = { style: null, label: "", strength: null,
                melee_share: mel, ranged_share: tot ? 1.0 - mel : 0.5,
                carriers: carriers, mode: mode, posture: posture,
                band: band, members: [], conflicts: [],
                kite_tools: kiteTools, kite_tools_min: kiteMin,
                kite_tools_pure: Math.max(1, perTen), melee_bomb_share: bcBomb,
                core_catch: coreCatch, line_catch: lineCatch };
    var styles = this.data.styles || {};
    var sname = function (k, fb) {
      return (styles[k] && styles[k].name) || fb;
    };
    var forming = n < IDENTITY_MIN_MEMBERS || tot === 0;
    var clap;
    if (forming) {
      out.label = "still forming";
    } else if (mel >= IDENTITY_MELEE_CORE) {
      if (mode.aoe >= IDENTITY_BC_AOE && bcBomb >= IDENTITY_BC_MELEE_BOMB) {
        /* the ball itself carries the bomb (validation round 2, roster 11) */
        out.style = "brawl_clap";
        out.strength = "leaning";
        out.label = sname("brawl_clap", "Brawl-Clap") + " — grind into the bomb";
      } else {
        out.style = "brawl";
        out.strength = mel >= IDENTITY_STRONG ? "strong" : "leaning";
        out.label = sname("brawl", "Brawl") + " — melee ball";
      }
    } else if (mel <= IDENTITY_RANGED_CORE) {
      /* a ranged core with no standoff tools must commit: clap (mirrors
         engine.py) */
      clap = mode.aoe >= IDENTITY_CLAP_AOE || !kiteAny;
      out.style = clap ? "clap" : "kite";
      out.strength = mel <= 1.0 - IDENTITY_STRONG ? "strong" : "leaning";
      /* Bomb-squad archetype + clap-kite hybrid (V3 round 1) — mirrors
         engine.py comp_identity. */
      var topCarrier = 0;
      for (var tc in carrierCount) {
        if (carrierCount[tc] > topCarrier) topCarrier = carrierCount[tc];
      }
      if (clap && topCarrier >= 3 && topCarrier * 2 >= nCarrierMembers) {
        out.archetype = "bomb_squad";
        out.label = "Bomb squad — off-timer artillery (clap detachment)";
      } else if (mode.aoe >= IDENTITY_HYBRID_AOE && kiteHalf) {
        out.style = "clap_kite";
        out.strength = "leaning";
        out.label = sname("clap_kite", "Clap-Kite") +
                    " — bomb from range, reset on cooldowns";
      } else {
        out.label = clap ? sname("clap", "Clap") + " — ranged bomb"
                         : sname("kite", "Kite") + " — ranged pressure";
      }
    } else if (mode.aoe >= IDENTITY_HYBRID_AOE && kiteHalf) {
      /* mid band with standoff tools: kite half outranks the posture
         tiebreak (mirrors engine.py, validation round 1 roster 7) */
      out.style = "clap_kite";
      out.strength = "leaning";
      out.label = sname("clap_kite", "Clap-Kite") +
                  " — bomb from range, throw them back";
    } else if (mode.aoe >= IDENTITY_BC_AOE && bcBomb >= IDENTITY_BC_MELEE_BOMB) {
      out.style = "brawl_clap";
      out.strength = "leaning";
      out.label = sname("brawl_clap", "Brawl-Clap") + " — grind into the bomb";
    } else if (mode.aoe >= IDENTITY_HYBRID_AOE) {
      /* the bomb's delivery names the mid band (validation round 3, roster 8;
         mirrors engine.py) */
      out.style = "clap";
      out.strength = "leaning";
      out.label = sname("clap", "Clap") + " — ranged bomb (mixed bodies, bomb from range)";
    } else {
      /* mirrors Python's tuple compare: (mel, nMelee) < (1-mel, nRanged) */
      var minority = (mel < 1.0 - mel ||
                      (mel === 1.0 - mel &&
                       carriers.melee.length < carriers.ranged.length))
        ? "melee" : "ranged";
      var majority = minority === "melee" ? "ranged" : "melee";
      /* flex and utility-carrier weapons never anchor a damage-identity
         split (mirrors engine.py — V3 round 1), nor does a frontline */
      var rigid = [];
      for (var ri = 0; ri < carriers[minority].length; ri++) {
        var rw = carriers[minority][ri];
        var rsf = this._styleFitOf(rw);
        if (!flex[rw] && this.roleOf(rw) !== "frontline" &&
            !(rsf && rsf.utility_carrier)) rigid.push(rw);
      }
      if (!rigid.length) {
        /* every minority carrier is flex — the comp is NOT split */
        if (majority === "melee") {
          out.style = "brawl";
          out.strength = "leaning";
          out.label = sname("brawl", "Brawl") + " — melee ball";
        } else {
          clap = mode.aoe >= IDENTITY_CLAP_AOE || !kiteAny;
          if (mode.aoe >= IDENTITY_HYBRID_AOE && kiteHalf) {
            out.style = "clap_kite";
            out.strength = "leaning";
            out.label = sname("clap_kite", "Clap-Kite") +
                        " — bomb from range, reset on cooldowns";
          } else {
            out.style = clap ? "clap" : "kite";
            out.strength = "leaning";
            out.label = clap ? sname("clap", "Clap") + " — ranged bomb"
                             : sname("kite", "Kite") + " — ranged pressure";
          }
        }
      } else {
        out.label = "split identity — melee and ranged damage pull apart";
        for (var mi = 0; mi < rigid.length; mi++) {
          out.conflicts.push({
            weapon: rigid[mi],
            display_name: this.weapons[rigid[mi]].display_name,
            side: minority, kind: "split",
            note: minority + " damage inside a " + majority + "-leaning " +
                  "core — commit to one side or cover the seam",
          });
        }
        /* the kits decide a split (mirrors engine.py) */
        var kit = this._kitLean(party, gears);
        if (kit === "brawl") {
          out.style = "brawl"; out.strength = "leaning"; out.kit_lean = "brawl";
          out.label = sname("brawl", "Brawl") + " — melee ball (by the kits: brawl chests)";
        } else if (kit === "ranged") {
          if (mode.aoe >= IDENTITY_HYBRID_AOE && kiteHalf) {
            out.style = "clap_kite";
            out.label = sname("clap_kite", "Clap-Kite") + " — bomb from range, throw them back (by the kits: ranged chests)";
          } else if (mode.aoe >= IDENTITY_CLAP_AOE || !kiteAny) {
            out.style = "clap";
            out.label = sname("clap", "Clap") + " — ranged bomb (by the kits: ranged chests)";
          } else {
            out.style = "kite";
            out.label = sname("kite", "Kite") + " — ranged pressure (by the kits: ranged chests)";
          }
          out.strength = "leaning"; out.kit_lean = "ranged";
        }
      }
    }
    /* leather dps are a brawl whatever the weapons say (the bomb-squad
       archetype is the exception) -- mirrors engine.py */
    if (out.style === "clap" && !out.archetype && this._kitLean(party, gears) === "brawl") {
      out.style = "brawl"; out.strength = "leaning"; out.kit_lean = "brawl";
      out.label = sname("brawl", "Brawl") + " — melee ball (by the kits: brawl chests, bombs or not)";
    }
    /* the gank read (validation round 4, rosters 3 and 18; mirrors
       engine.py): 14 or fewer members, every catch tool on a dps seat,
       one in that core, bomb share under the bomb-half line (the bomb
       squad gives way too) — a label of its own, no style, descriptive
       only */
    if (!forming && n <= IDENTITY_GANK_MAX && lineCatch === 0 && coreCatch > 0 &&
        mode.aoe < IDENTITY_GANK_AOE) {
      out.style = null; out.strength = null; out.archetype = "gank";
      delete out.kit_lean;
      out.conflicts = [];
      out.label = "Gank — the damage catches and executes, no bomb";
    }
    /* per-member fit verdicts: the declared style is the caller's INTENT;
       balanced falls back to the detected lean */
    var fitStyle = IDENTITY_STYLES[this.style] ? this.style : out.style;
    for (var pi = 0; pi < n; pi++) {
      var pw = party[pi];
      var psf = this._styleFitOf(pw);
      var verdict = (psf && fitStyle && psf.fit[fitStyle])
        ? psf.fit[fitStyle][band] : null;
      var m = { weapon: pw,
                display_name: this.weapons[pw].display_name,
                role: this.roleOf(pw),
                side: flex[pw] ? "flex" :
                      (sides[pi] === undefined ? null : sides[pi]),
                fit: verdict };
      if (verdict === "unfit" && !forming) {
        var reason = (psf && psf.damage_scale === "single")
          ? "its E is not a group-scale damage tool at this size"
          : "off-" + fitStyle + " at this size";
        m.note = reason;
        out.conflicts.push({
          weapon: pw,
          display_name: m.display_name,
          side: m.side, kind: "unfit",
          note: "unfit for " + sname(fitStyle, fitStyle) + " at " +
                this.size + " — " + reason,
        });
      }
      out.members.push(m);
    }
    return out;
  };

  CompEngine.prototype.killPressure = function (party, combos, gears) {
    /* The caller's kill checklist as a three-light verdict — pierce /
       heal-cut / burst vs the comp-fitted template targets, over
       effective supply. DESCRIPTIVE ONLY (mirrors engine.py
       kill_pressure). */
    var cfg = this.mechanics.kill_pressure;
    if (!cfg) return null;
    var ratio = cfg.pass_ratio === undefined ? 0.85 : cfg.pass_ratio;
    var s = this.effectiveSupply(party, combos, gears);
    var self = this;
    var light = function (caps) {
      var used = [], bar = 0.0, have = 0.0;
      for (var i = 0; i < (caps || []).length; i++) {
        var c = caps[i];
        if (!(c in self.reqs)) continue;
        used.push(c);
        /* the bar is the BARE MINIMUM (target is the median; mirrors
           engine.py kill_pressure): "enough to kill" is a minimum question */
        bar += self.targetMin(c);
        have += s[c] || 0.0;
      }
      return { caps: used, have: have, bar: bar,
               ok: bar <= 0 || have >= ratio * bar };
    };
    var out = { pierce: light(cfg.pierce_caps),
                heal_cut: light(cfg.heal_cut_caps),
                burst: light(cfg.burst_caps),
                pass_ratio: ratio };
    var greens = (out.pierce.ok ? 1 : 0) + (out.heal_cut.ok ? 1 : 0) +
                 (out.burst.ok ? 1 : 0);
    out.verdict = greens === 3 ? "ready" : greens === 2 ? "partial" : "lacking";
    return out;
  };

  /* verdicts read the board's stages (target is the median; mirrors
       engine.py fight_chain): weak under the bare minimum (targetMin),
       ok up to the typical winner (target), strong at/above it */

  CompEngine.prototype.fightChain = function (party, combos, gears, candidate) {
    /* The comp as the caller's fight SEQUENCE, graded stage by stage —
       DESCRIPTIVE only (mirrors engine.py fight_chain). Balanced reads
       the chain of the identity the worn kits decide (T26d). */
    var styles = this.data.styles || {};
    var style = IDENTITY_STYLES[this.style]
      ? this.style : this.compIdentity(party, combos, gears).style;
    var chain = style && styles[style] ? styles[style].chain : null;
    if (!chain) return null;
    var s = this.effectiveSupply(party, combos, gears);
    /* spell-level sources (mirrors engine.py): which equipped
       buttons ARE each stage — resolved loadouts attributed back to the
       slot/spell carrying each stage capability; spell null = the weapon's
       always-on kit. Units are per-member, before the party-level
       count-once rule; gear is not attributed. Display only. */
    var members = [];
    for (var mi = 0; mi < party.length; mi++) {
      var mw = party[mi];
      var lo = this.weapons[mw].loadout || {};
      var slotNames = lo.slot_names || [];
      var slotSpells = lo.slot_spells || [];
      var le = this._loadoutEff(mw);
      var picks = [];
      var choices = this.comboChoices(mw, combos ? combos[mi] : null);
      for (var pi = 0; pi < choices.length; pi++) {
        var oi = choices[pi][0], bi = choices[pi][1];
        if (oi >= le.slots.length || bi >= le.slots[oi].length) continue;
        var sid = (oi < slotSpells.length && bi < slotSpells[oi].length)
          ? slotSpells[oi][bi] : null;
        picks.push([oi < slotNames.length ? slotNames[oi] : null,
                    sid, le.slots[oi][bi]]);
      }
      members.push([mi, mw, le.always, picks]);
    }
    var stages = [];
    for (var i = 0; i < chain.length; i++) {
      var caps = chain[i].caps || [];
      var used = [], bar = 0.0, low = 0.0, have = 0.0;
      for (var ci = 0; ci < caps.length; ci++) {
        if (!(caps[ci] in this.reqs)) continue;
        used.push(caps[ci]);
        bar += this.target(caps[ci]);
        low += this.targetMin(caps[ci]);
        have += s[caps[ci]] || 0.0;
      }
      var verdict;
      if (!used.length || bar <= 0) verdict = "quiet";
      else if (have <= 0) verdict = "missing";
      else if (have < low) verdict = "weak";
      else if (have >= bar) verdict = "strong";
      else verdict = "ok";
      var sources = [];
      for (var ui = 0; ui < used.length; ui++) {
        var cap = used[ui];
        for (var mj = 0; mj < members.length; mj++) {
          var m = members[mj], v = m[2][cap] || 0.0;
          if (v) sources.push({ cap: cap, member: m[0], weapon: m[1],
                                display_name: this.weapons[m[1]].display_name,
                                slot: null, spell: null, units: v });
          for (var pj = 0; pj < m[3].length; pj++) {
            var pk = m[3][pj];
            v = pk[2][cap] || 0.0;
            if (v) sources.push({ cap: cap, member: m[0], weapon: m[1],
                                  display_name: this.weapons[m[1]].display_name,
                                  slot: pk[0], spell: pk[1], units: v });
          }
        }
      }
      stages.push({ name: chain[i].name, caps: used,
                    have: have, bar: bar, min: low, verdict: verdict,
                    sources: sources });
    }
    var out = { style: style, stages: stages, improves: null };
    if (candidate && this.weapons[candidate]) {
      /* explain() deltas are already weighted fitness terms, on the
         same gears */
      var terms = this.explain(party, candidate, combos, gears);
      var deltas = {}, total = 0.0;
      for (var ti = 0; ti < terms.length; ti++) {
        deltas[terms[ti].cap] = terms[ti].delta;
        total += terms[ti].delta;
      }
      var bestStage = null, bestGain = 0.0, bestCaps = [];
      for (var si = 0; si < stages.length; si++) {
        var gain = 0.0;
        for (var gi = 0; gi < stages[si].caps.length; gi++)
          gain += deltas[stages[si].caps[gi]] || 0.0;
        if (gain > bestGain + 1e-9) {
          bestStage = stages[si].name; bestGain = gain;
          bestCaps = stages[si].caps;
        }
      }
      /* only claim the connection when that stage holds a real share of
         the pick's explained value (mirrors the 0.3 rule) */
      if (bestStage !== null && total > 0 && bestGain >= 0.3 * total) {
        /* name the terms behind the claim (mirrors engine.py):
           a stage can win on SUMMED caps none of which is the pick's
           single top term */
        var impTerms = [];
        for (var bi2 = 0; bi2 < bestCaps.length; bi2++) {
          if ((deltas[bestCaps[bi2]] || 0.0) > 0)
            impTerms.push({ cap: bestCaps[bi2], gain: deltas[bestCaps[bi2]] });
        }
        out.improves = { stage: bestStage, gain: bestGain, terms: impTerms };
      }
    }
    return out;
  };

  /* ------------------------------------------------------------ local search */
  CompEngine.prototype.refine = function (party, maxPasses, pool, fixed,
                                          gears) {
    /* Steepest-descent 1-opt over compScore, UNCONSTRAINED (mirrors
       engine.py refine; the forge runs its own constraint-aware pass).
       gears (the dressed forge): with a parallel kit list the
       search optimizes the SAME dressed compScore used everywhere else
       — incumbent kits preserved, replacements tried in each doctrine
       kit variant, result {party, gears}. gears null keeps the legacy
       weapon-only list return bit-identically. A party past PARTY_CAP is
       refused (mirrors engine.py). */
    refusePastCap(party.length);
    party = party.slice();
    fixed = fixed || 0;
    /* mirrors engine.py `self.pool if pool is None else pool`: no pool
       (null/undefined) is every non-retired weapon; a given list, empty
       included, is the candidate set as given (F37) */
    var candidates = (pool === undefined || pool === null)
      ? this.pool.slice() : pool.slice();
    if (maxPasses === undefined || maxPasses === null) maxPasses = 8;
    if (gears === undefined || gears === null) {
      if (!party.length) return party;
      var best = this.compScore(party);
      for (var pass = 0; pass < maxPasses; pass++) {
        var moveIdx = -1, moveW = null, gain = 1e-9; /* strictly-positive */
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
    }
    var gl = [];
    for (var k = 0; k < party.length; k++) {
      var g = gears[k];
      gl.push((g && g.length) ? g.slice() : null);
    }
    if (!party.length) return { party: party, gears: gl };
    var bestD = this.compScore(party, null, gl);
    for (var passD = 0; passD < maxPasses; passD++) {
      var mIdx = -1, mW = null, mG = null, gainD = 1e-9;
      for (var i2 = fixed; i2 < party.length; i2++) {
        var origW = party[i2], origG = gl[i2];
        for (var j2 = 0; j2 < candidates.length; j2++) {
          if (candidates[j2] === origW) continue;
          party[i2] = candidates[j2];
          var variants = this.kitVariants(candidates[j2]);
          for (var vi = 0; vi < variants.length; vi++) {
            gl[i2] = variants[vi][1];
            var dD = this.compScore(party, null, gl) - bestD;
            if (dD > gainD) {
              mIdx = i2; mW = candidates[j2];
              mG = variants[vi][1]; gainD = dD;
            }
          }
        }
        party[i2] = origW;
        gl[i2] = origG;
      }
      if (mIdx < 0) break;
      party[mIdx] = mW;
      gl[mIdx] = mG ? mG.slice() : null;
      bestD += gainD;
    }
    return { party: party, gears: gl };
  };

  /* ------------------------------------------------------------------ forge */
  CompEngine.prototype._forgeCtx = function (pool) {
    /* Static per-forge context (mirrors engine.py _forge_ctx). */
    var band = this._band || {};
    var roleMin = {}, roleMax = {}, roleTyp = {}, predMin = {};
    for (var key in band) {
      if (key === "min_size" || key === "max_size") continue;
      var rule = band[key];
      if (typeof rule !== "object" || rule === null) continue;
      if (key in this.predDefs || key === this.PRIMARY_HEAL || key === this.STANDOFF) {
        if (rule.min !== undefined) predMin[key] = rule.min;
        continue;
      }
      if (rule.min !== undefined) roleMin[key] = rule.min;
      if (rule.max !== undefined) roleMax[key] = rule.max;
      if (rule.typical !== undefined) roleTyp[key] = rule.typical;
    }
    /* need-profile minima ride the predicate channel; seat maxima get
       their own key (mirrors engine.py) */
    var pk, seatMax = {};
    for (pk in this._profileMin) predMin[pk] = this._profileMin[pk];
    for (pk in this._profileMax) seatMax[pk] = this._profileMax[pk];
    /* Capacity gates per predicate minimum (the deadlock guard; mirrors
       engine.py _forge_ctx): the [role, seat] pairs of every pool
       weapon that could satisfy the predicate — _forgeFeasible refuses a
       pick that would strand an unmet minimum behind full bands. */
    var predGates = {}, predSat = {};
    for (var pn2 in predMin) {
      var gates = [], seen = {}, sats = {};
      for (var wi = 0; wi < pool.length; wi++) {
        var w2 = pool[wi];
        var poss = this._predPossible(w2);
        var prof = this._profileMembers[w2];
        if (!poss[pn2] && !(prof && prof[pn2])) continue;
        var role2 = this.roleOf(w2);
        var seat2 = this._profilePrimary[w2];
        sats[w2] = true;
        var gkey = role2 + "|" + (seat2 === undefined ? "-" : seat2);
        if (seen[gkey]) continue;
        seen[gkey] = true;
        gates.push([role2, seat2]);
      }
      predGates[pn2] = gates;
      predSat[pn2] = sats;
    }
    /* the ROLES a predicate's satisfiers span (mirrors engine.py): the
       admissible minimum-need bound nests a single-role
       predicate in its role family */
    var predRoles = {};
    for (var pr in predGates) {
      var rset = {}, rn = 0;
      for (var gi2 = 0; gi2 < predGates[pr].length; gi2++) {
        if (!rset[predGates[pr][gi2][0]]) { rset[predGates[pr][gi2][0]] = true; rn++; }
      }
      predRoles[pr] = { roles: rset, n: rn };
    }
    /* SEAT SKELETON (mirrors engine.py _forge_ctx): each seat's
       typical clipped to what the pool can generate for it, the seats of
       the pool's weapons per role (the set spill inspects) and the seats
       that can satisfy each predicate minimum. */
    var seatTyp = {}, roleSeats = {}, predSeats = {}, seatGate = false;
    for (var sg in this._seatTyp) { seatGate = true; break; }
    if (seatGate) {
      var cap = {};
      for (var wi2 = 0; wi2 < pool.length; wi2++) {
        var s2 = this.seatOf(pool[wi2]);
        if (s2 === null) continue;
        cap[s2] = (cap[s2] || 0) + this._dupGenMax(pool[wi2]);
        var r2s = this.roleOf(pool[wi2]);
        if (!roleSeats[r2s]) roleSeats[r2s] = {};
        roleSeats[r2s][s2] = true;
      }
      for (var st in this._seatTyp) seatTyp[st] = Math.min(this._seatTyp[st], cap[st] || 0);
      for (var pn3 in predSat) {
        var ss = {};
        for (var sw2 in predSat[pn3]) { var s3 = this.seatOf(sw2); if (s3 !== null) ss[s3] = true; }
        predSeats[pn3] = ss;
      }
    }
    /* ROLE SPILL (mirrors engine.py _forge_ctx): the count at which each
       typed role stands full, its typical (or band minimum, the larger)
       clipped to what the pool can generate for the role and to the
       role's band maximum; roleCap's keys are the roles the pool
       supplies, the set spill inspects. */
    var roleCap = {}, roleFull = {};
    for (var wi3 = 0; wi3 < pool.length; wi3++) {
      var r3 = this.roleOf(pool[wi3]);
      roleCap[r3] = (roleCap[r3] || 0) + this._dupGenMax(pool[wi3]);
    }
    for (var rm in roleMax) {
      if (roleCap[rm] !== undefined) roleCap[rm] = Math.min(roleCap[rm], roleMax[rm]);
    }
    for (var rt in roleTyp) {
      roleFull[rt] = Math.min(Math.max(roleTyp[rt], roleMin[rt] || 0), roleCap[rt] || 0);
    }
    return { pool: pool, roleMin: roleMin, roleMax: roleMax,
             roleTyp: roleTyp, roleCap: roleCap, roleFull: roleFull,
             predMin: predMin, seatMax: seatMax, predGates: predGates,
             predRoles: predRoles, predSat: predSat,
             seatTyp: seatTyp, seatGate: seatGate, roleSeats: roleSeats,
             predSeats: predSeats };
  };

  CompEngine.prototype._forgeCounts = function (party, combos) {
    /* [weapon counts, role counts, predicate counts, group counts].
       Predicate counts are COMBO-AWARE (mirrors engine.py _forge_counts). */
    var counts = {}, roles = {}, preds = {}, groups = {};
    for (var i = 0; i < party.length; i++) {
      var w = party[i];
      counts[w] = (counts[w] || 0) + 1;
      var r = this.roleOf(w);
      roles[r] = (roles[r] || 0) + 1;
      var contrib = this._predContrib(w, combos ? combos[i] : null);
      for (var pn in contrib) preds[pn] = (preds[pn] || 0) + 1;
      var pmC = this._profileMembers[w];
      if (pmC) for (var pk2 in pmC) preds[pk2] = (preds[pk2] || 0) + 1;
      /* primary-seat tally for the seat skeleton, under its own namespace
         (mirrors engine.py _forge_counts) */
      var seatK = this.seatOf(w);
      if (seatK !== null) preds["seat:" + seatK] = (preds["seat:" + seatK] || 0) + 1;
      var gs = this.groupsOf[w] || [];
      for (var g = 0; g < gs.length; g++) groups[gs[g]] = (groups[gs[g]] || 0) + 1;
    }
    return [counts, roles, preds, groups];
  };

  CompEngine.prototype._forgeMinNeed = function (ctx, roles, preds, w, predContrib) {
    /* Bodies still required for unmet minima after adding `w` - the
       ADMISSIBLE bound (F28; mirrors engine.py _forge_min_need):
       per role band the largest of the unmet band minimum, the unmet
       SEAT minima nested in it and any single-role non-seat predicate;
       a cross-role predicate adds only what those counted bodies cannot
       carry; a predicate nothing in the pool satisfies keeps its count.
       The old plain sum read 19 at the clap 15-19 band for a roster
       twelve bodies satisfy, and forged nothing at exactly 15. */
    var r = this.roleOf(w);
    var needByRole = {}, seatSum = {}, otherMax = {}, cross = [];
    var seatItems = {};   /* role -> [[seat predicate, unmet bodies]] */
    for (var r2 in ctx.roleMin) {
      var have = (roles[r2] || 0) + (r2 === r ? 1 : 0);
      if (ctx.roleMin[r2] > have) needByRole[r2] = ctx.roleMin[r2] - have;
    }
    for (var pn in ctx.predMin) {
      var haveP = (preds[pn] || 0) + (predContrib[pn] ? 1 : 0);
      var unmet = ctx.predMin[pn] - haveP;
      if (unmet <= 0) continue;
      var pr = (ctx.predRoles || {})[pn] || { roles: {}, n: 0 };
      if (pr.n === 1) {
        var only = Object.keys(pr.roles)[0];
        if (Object.prototype.hasOwnProperty.call(this._profileMin, pn)) {
          seatSum[only] = (seatSum[only] || 0) + unmet;
          if (!seatItems[only]) seatItems[only] = [];
          seatItems[only].push([pn, unmet]);
        } else otherMax[only] = Math.max(otherMax[only] || 0, unmet);
      } else cross.push([pr.roles, unmet, pn]);
    }
    var keys = {}, k;
    for (k in needByRole) keys[k] = true;
    for (k in seatSum) keys[k] = true;
    for (k in otherMax) keys[k] = true;
    var need = 0;
    for (k in keys) {
      needByRole[k] = Math.max(needByRole[k] || 0, seatSum[k] || 0, otherMax[k] || 0);
      need += needByRole[k];
    }
    /* A cross-role predicate is discounted only against bodies that COULD
       carry it. A body committed to a nested SEAT minimum no satisfier of
       the predicate can fill is proof of a SECOND body (F29; mirrors
       engine.py): territory_defense needs one more stopper tank
       and one more ranged-AoE body, and no stopper delivers ranged AoE,
       so the whole-role discount read 1 where two are required and the
       roster died one short. Admissible means never MORE than a legal
       completion needs - it must never be LESS either. */
    var predSat = ctx.predSat || {};
    for (var ci = 0; ci < cross.length; ci++) {
      var counted = 0, satP = predSat[cross[ci][2]] || {};
      for (var rr in cross[ci][0]) {
        var blocked = 0, items = seatItems[rr] || [];
        for (var si = 0; si < items.length; si++) {
          var satS = predSat[items[si][0]] || {}, shared = false, sk;
          for (sk in satS) { if (satP[sk]) { shared = true; break; } }
          if (!shared) blocked += items[si][1];
        }
        counted += Math.max(0, (needByRole[rr] || 0) - blocked);
      }
      need += Math.max(0, cross[ci][1] - counted);
    }
    return need;
  };

  CompEngine.prototype._roleTypical = function () {
    /* The typical role-count row for this content, style and size
       (mirrors engine.py _role_typical): below the style floor a
       matchmaking pool's own row for the content at this exact size (a
       role may be typical at ZERO), else the content's fitted-comps
       median, else the pooled harvest row; at the floor and above the
       DECLARED identity style's cell, else the pooled row (`balanced`
       never reads a cell). */
    var rt = this.compCfg.role_typical || {};
    var key = String(this.size);
    var floor = rt.style_min_size === undefined ? 10 : rt.style_min_size;
    var row = null;
    if (this.size < floor) {
      row = ((rt.pools || {})[this.content] || {})[key] || null;
      if (!nonEmpty(row)) row = ((rt.comps || {})[this.content] || {})[key] || null;
      if (!nonEmpty(row)) row = (rt.pooled || {})[key] || null;
    } else {
      if (IDENTITY_STYLES[this.style])
        row = ((rt.styles || {})[this.style] || {})[key] || null;
      if (row === null) row = (rt.pooled || {})[key] || null;
    }
    return Object.assign({}, row || {});
  };

  CompEngine.prototype._seatTypical = function () {
    /* mirrors engine.py _seat_typical: at the style floor and above the
       DECLARED identity style's cell, else the pooled row (`balanced`
       never reads a cell); below the floor nothing; {} = no seat gate. */
    var sk = this.skeleton || {};
    var seats = sk.seats || {};
    var anyS = false;
    for (var k0 in seats) { anyS = true; break; }
    if (!anyS) return {};
    var floor = sk.style_min_size === undefined ? 10 : sk.style_min_size;
    if (this.size < floor) return {};
    var key = String(this.size);
    var row = null;
    if (IDENTITY_STYLES[this.style])
      row = ((seats.styles || {})[this.style] || {})[key] || null;
    if (row === null) row = (seats.pooled || {})[key] || null;
    return Object.assign({}, row || {});
  };

  CompEngine.prototype._planTypical = function () {
    /* mirrors engine.py _plan_typical */
    var sk = this.skeleton || {};
    var plan = sk.plan || {};
    var anyP = false;
    for (var k2 in plan) { anyP = true; break; }
    if (!anyP) return {};
    var floor = sk.style_min_size === undefined ? 10 : sk.style_min_size;
    if (this.size < floor) return {};
    var key = String(this.size);
    var row = null;
    if (IDENTITY_STYLES[this.style])
      row = ((plan.styles || {})[this.style] || {})[key] || null;
    if (row === null) row = (plan.pooled || {})[key] || null;
    return Object.assign({}, row || {});
  };

  CompEngine.prototype._bandMinima = function () {
    /* mirrors engine.py _band_minima: at the style floor and above, the
       band covering the size, the DECLARED identity style's row, else
       the pooled row; {keys, row} (a key absent from the row = no
       minimum), or null when no table or band covers the size. */
    var sk = this.skeleton || {};
    var mins = sk.minima || {};
    var anyM = false;
    for (var k3 in mins) { anyM = true; break; }
    if (!anyM) return null;
    var floor = sk.style_min_size === undefined ? 10 : sk.style_min_size;
    if (this.size < floor) return null;
    var bands = mins.bands || {}, band = null;
    for (var bk in bands) {
      if (bands[bk][0] <= this.size && this.size <= bands[bk][1]) { band = bk; break; }
    }
    if (band === null) return null;
    var row = null;
    if (IDENTITY_STYLES[this.style])
      row = ((mins.styles || {})[this.style] || {})[band] || null;
    if (row === null) row = (mins.pooled || {})[band] || null;
    if (row === null) return null;
    return { keys: (mins.keys || []).slice(), row: Object.assign({}, row) };
  };

  CompEngine.prototype._dupCell = function () {
    /* mirrors engine.py _dup_cell: the pooled band row under the declared
       identity style's row; {} outside every band; the hand list when the
       dataset carries no cells (bit-identical to the pre-skeleton engine). */
    var cells = this.dupCells || {};
    var anyC = false;
    for (var k1 in cells) { anyC = true; break; }
    if (!anyC) return this._dupPerWeaponBase;
    var bands = cells.bands || {}, band = null;
    for (var bk in bands) {
      if (bands[bk][0] <= this.size && this.size <= bands[bk][1]) { band = bk; break; }
    }
    if (band === null) return {};
    var row = Object.assign({}, (cells.pooled || {})[band] || {});
    if (IDENTITY_STYLES[this.style]) {
      var srow = ((cells.styles || {})[this.style] || {})[band] || {};
      for (var sw in srow) row[sw] = srow[sw];
    }
    return row;
  };

  CompEngine.prototype._predExclusive = function (ctx, pn, role) {
    /* true when every pool satisfier of predicate `pn` sits in `role`
       (mirrors engine.py's pred_roles == frozenset([r])) */
    var pr = (ctx.predRoles || {})[pn];
    return !!(pr && pr.n === 1 && pr.roles[role]);
  };

  CompEngine.prototype._roleOpen = function (ctx, roles, r) {
    /* can role r still take a body inside its typical (clipped to what
       the pool can generate)? a role without a typical always can
       (mirrors engine.py _role_open) */
    var full = ctx.roleFull[r];
    return full === undefined || (roles[r] || 0) < full;
  };

  CompEngine.prototype._roleSpill = function (ctx, roles) {
    /* ROLE SPILL: every role the pool supplies stands at its typical, or
       the beam found no legal body for any role under its typical at this
       depth (ctx.spill) (mirrors engine.py _role_spill) */
    if (ctx.spill) return true;
    for (var r in ctx.roleCap) { if (this._roleOpen(ctx, roles, r)) return false; }
    return true;
  };

  CompEngine.prototype._predElsewhere = function (ctx, roles, preds, pn, r) {
    /* could a role other than r still under its typical carry predicate
       pn: a satisfier gate of another role with room in its role band and
       its seat? (mirrors engine.py _pred_elsewhere) */
    var gates = ctx.predGates[pn] || [];
    for (var gi = 0; gi < gates.length; gi++) {
      var r3 = gates[gi][0], s3 = gates[gi][1];
      if (r3 === r || !this._roleOpen(ctx, roles, r3)) continue;
      var mx3 = ctx.roleMax[r3];
      if (mx3 !== undefined && (roles[r3] || 0) >= mx3) continue;
      if (s3 !== undefined && ctx.seatMax[s3] !== undefined &&
          (preds[s3] || 0) >= ctx.seatMax[s3]) continue;
      return true;
    }
    return false;
  };

  CompEngine.prototype._typOk = function (ctx, roles, preds, w, contrib) {
    /* May `w` join a roster whose role counts are `roles`, given the
       TYPICAL count of its role (F31; dps at 10+; mirrors engine.py
       _typ_ok)? A body beyond the typical count is generated only for an
       unmet minimum this pick carries that no other role still under its
       typical could meet, or by ROLE SPILL once every role the pool
       supplies stands at its typical.
       SEAT branch (the seat skeleton): once the role allows the body its
       PRIMARY SEAT must too - a seat at its typical admits another body
       only when an unmet minimum this pick meets could not be met by an
       under-typical seat of the role (minima win, cross-role ones
       included), or by SPILL: every seat of the role the pool can still
       supply stands at its typical. No cell for the size = no gate. */
    var r = this.roleOf(w);
    var typ = ctx.roleTyp[r];
    var pn;
    if (typ !== undefined) {
      var have = roles[r] || 0;
      var cap = Math.max(typ, ctx.roleMin[r] || 0);
      if (have < cap) {
        /* within the typical slots: they must carry the role's exclusive
           minima, so a pick that would leave more unmet exclusive need
           than slots remain is refused (mirrors engine.py) */
        var remaining = cap - have - 1;
        for (pn in ctx.predMin) {
          if (!this._predExclusive(ctx, pn, r)) continue;
          var unmet = ctx.predMin[pn] - (preds[pn] || 0) - (contrib[pn] ? 1 : 0);
          if (unmet > remaining) return false;
        }
      } else {
        /* past the typical: an unmet minimum this pick carries that no
           other role under its typical could meet, else the role spill */
        var lifted = false;
        for (pn in ctx.predMin) {
          if (contrib[pn] && (preds[pn] || 0) < ctx.predMin[pn] &&
              !this._predElsewhere(ctx, roles, preds, pn, r)) { lifted = true; break; }
        }
        if (!lifted && !this._roleSpill(ctx, roles)) return false;
      }
    }
    if (!ctx.seatGate) return true;
    var s = this.seatOf(w);
    if (s === null) return true;
    if ((preds["seat:" + s] || 0) < (ctx.seatTyp[s] || 0)) return true;
    var under = [];
    var rs = ctx.roleSeats[r] || {};
    for (var s2 in rs) {
      if ((preds["seat:" + s2] || 0) < (ctx.seatTyp[s2] || 0)) under.push(s2);
    }
    for (pn in ctx.predMin) {
      if (contrib[pn] && (preds[pn] || 0) < ctx.predMin[pn]) {
        var sats = ctx.predSeats[pn] || {}, blocked = false;
        for (var ui = 0; ui < under.length; ui++) { if (sats[under[ui]]) { blocked = true; break; } }
        if (!blocked) return true;
      }
    }
    return under.length === 0;   /* spill: every typed seat of the role is full */
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
    var p0 = this._profilePrimary[w];
    if (p0 !== undefined && ctx.seatMax[p0] !== undefined &&
        (preds[p0] || 0) >= ctx.seatMax[p0]) return false;
    var contrib = this._withProfile(w, this._predPossible(w));
    if (!this._typOk(ctx, roles, preds, w, contrib)) return false;
    if (this._forgeMinNeed(ctx, roles, preds, w, contrib) > slotsLeftAfter)
      return false;
    /* Deadlock guard (mirrors engine.py): after this pick,
       every UNMET predicate minimum must keep a satisfier whose role band
       AND fine seat still have capacity — else the pick strands the
       minimum and the beam dies short. */
    for (var pn in ctx.predMin) {
      var have = (preds[pn] || 0) + (contrib[pn] ? 1 : 0);
      if (have >= ctx.predMin[pn]) continue;
      var gates = ctx.predGates[pn];
      if (!gates || !gates.length) continue;
      var open = false;
      for (var gi = 0; gi < gates.length; gi++) {
        var r2 = gates[gi][0], s2 = gates[gi][1];
        var mx2 = ctx.roleMax[r2];
        if (mx2 !== undefined &&
            (roles[r2] || 0) + (r2 === r ? 1 : 0) >= mx2) continue;
        /* typical (F31): past the typical count the gate is open only
           as _typOk opens it - no other satisfier role under its typical,
           or the role spill - counted after this pick (mirrors engine.py) */
        var ty2 = ctx.roleTyp[r2];
        var n2 = (roles[r2] || 0) + (r2 === r ? 1 : 0);
        if (ty2 !== undefined && n2 >= ty2 && n2 >= (ctx.roleMin[r2] || 0)) {
          var after = {}, afterP = {};
          for (var ak in roles) after[ak] = roles[ak];
          after[r] = (after[r] || 0) + 1;
          for (var pk2 in preds) afterP[pk2] = preds[pk2];
          if (p0 !== undefined) afterP[p0] = (afterP[p0] || 0) + 1;
          if (this._predElsewhere(ctx, after, afterP, pn, r2) && !this._roleSpill(ctx, after)) continue;
        }
        if (s2 !== undefined && ctx.seatMax[s2] !== undefined &&
            (preds[s2] || 0) + (s2 === p0 ? 1 : 0) >= ctx.seatMax[s2])
          continue;
        open = true;
        break;
      }
      if (!open) return false;
    }
    return true;
  };

  CompEngine.prototype._forgeEvalPick = function (ctx, beam, w, slotsLeftAfter) {
    /* _evalPick restricted to combos that keep the roster completable
       (mirrors engine.py _forge_eval_pick). Returns null when no combo
       keeps the minima satisfiable. */
    var state = beam.state;
    var best = null;
    var extras = this._comboExtras(w);
    var dressed = this._dressedExtras(w);
    var variants = this.kitVariants(w);
    var v0CappedW = this._variantCapped(state, w, variants[0][1]);
    var fallbackW = this._variantFallback[w] || {};
    var hasPred = false;
    for (var k in ctx.predMin) { hasPred = true; break; }
    for (var i = 0; i < extras.length; i++) {
      /* predicate feasibility is per COMBO only — kit variants never
         change predicate contributions (mirrors engine.py) */
      if (hasPred) {
        var contribI = this._withProfile(w, this._predContrib(w, i));
        var need = this._forgeMinNeed(ctx, beam.roles, beam.preds, w,
                                      contribI);
        if (need > slotsLeftAfter) continue;
        /* a body beyond its role's typical count must ACTUALLY carry the
           demanding predicate on this combo (F31) */
        if (!this._typOk(ctx, beam.roles, beam.preds, w, contribI)) continue;
      }
      for (var vi = 0; vi < variants.length; vi++) {
        var vkey = variants[vi][0], vgears = variants[vi][1];
        if (this._variantCapped(state, w, vgears)) continue;   /* carrier quota */
        if (fallbackW[vkey] && !v0CappedW) continue;   /* cap fallback only */
        var ovw = this._offsetVector(state, w, i, vgears);
        var cs = ovw === null
          ? this._comboScoreDressed(state, w, i, extras[i], dressed[vkey][i],
                                    null, vgears)
          : this._comboScoreDressed(state, w, i, extras[i], ovw[0], ovw[1],
                                    vgears);
        if (best === null || cs.val > best.val + PICK_TIE_EPS)
          best = { val: cs.val, dFit: cs.dFit, dSyn: cs.dSyn, combo: i,
                   variant: vkey, vgears: vgears };
      }
    }
    if (best === null) return null;
    var tail = this._pickTail(state, w, best);
    tail.variant = best.variant;
    tail.vgears = best.vgears;
    return tail;
  };

  CompEngine.prototype._memberTag = function (w, combo, vkey) {
    /* Canonical member key for beam dedup — the kit-variant id is part
       of the identity (the dressed forge; mirrors engine.py). */
    return w + "#" + (combo === null || combo === undefined ? "d" : String(combo))
             + "#" + (vkey === undefined || vkey === null ? "-" : vkey);
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

  CompEngine.rosterKey = function (party) {
    /* canonical multiset key of a roster's WEAPONS (mirrors engine.py
       roster_key): combos and kits left out */
    return party.slice().sort().join("|");
  };
  CompEngine.prototype.rosterKey = CompEngine.rosterKey;

  CompEngine.prototype.forge = function (size, locked, lockedCombos, pool,
                                         beamWidth, lockedGears, avoid) {
    /* Deterministic constrained beam search over complete rosters + 1-opt
       and bounded 2-opt refinement + filler audit (mirrors engine.py forge
       — see its docstring for the contract; returns {party, combos, score,
       feasible, filler, held, locked, exhausted}). `avoid`:
       rosters already shown — the best roster NOT among them comes back;
       `exhausted` when every reachable completion was shown. A size or a
       locked list past PARTY_CAP is refused before any search. */
    locked = (locked || []).slice();
    refusePastCap(Math.max(size, locked.length));
    var avoidKeys = {}, hasAvoid = false;
    for (var ai = 0; ai < (avoid || []).length; ai++) {
      avoidKeys[CompEngine.rosterKey(avoid[ai])] = true; hasAvoid = true;
    }
    /* normalize lockedCombos to EXACTLY locked.length: missing/short/empty
       pads with null, extras drop — mirrors engine.py (an empty array
       mis-paired combos with members here). */
    var lc = lockedCombos || [];
    var combos = [];
    for (var ci = 0; ci < locked.length; ci++)
      combos.push(ci < lc.length ? lc[ci] : null);
    var candPool = pool !== undefined && pool !== null ? pool.slice() : this.suggestPool().slice();
    var ctx = this._forgeCtx(candPool);
    if (beamWidth === undefined || beamWidth === null) beamWidth = 8;
    var feasible = true;
    var exhausted = false;

    var fc = this._forgeCounts(locked, combos);
    /* lockedGears: a locked member supplied
       with explicit gear is scored in EXACTLY that kit and never
       re-dressed; one without stays naked — the forge never invents gear
       for a lock (mirrors engine.py; normalized like lockedCombos). */
    var lg = lockedGears || [];
    var gears0 = [];
    for (var gi0 = 0; gi0 < locked.length; gi0++) {
      var g0 = gi0 < lg.length ? lg[gi0] : null;
      gears0.push((g0 && g0.length) ? g0.slice() : null);
    }
    var items0 = [];
    for (var li = 0; li < locked.length; li++)
      items0.push(this._memberTag(locked[li], combos[li]));
    items0.sort();
    var beams = [{ party: locked, combos: combos, gears: gears0,
                   counts: fc[0], roles: fc[1], preds: fc[2], groups: fc[3],
                   state: this.partyState(locked, combos, gears0), items: items0,
                   score: this.compScore(locked, combos, gears0) }];
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
          expansions.push([beam.score + pick.score, bi, w, pick.combo,
                           pick.variant, pick.vgears]);
        }
      }
      if (!expansions.length) { feasible = false; break; }
      /* stable sort by score only: equal scores keep (beam, pool) append
         order — deterministic in both engines. The canonical multiset key
         is computed LAZILY, only for candidates actually considered for
         the beam (mirrors engine.py). */
      /* QUANTIZED score (mirrors engine.py): a last-bit
         difference must not order the ports differently */
      expansions.sort(function (a, b) { return qrank(b[0]) - qrank(a[0]); });
      var nextBeams = [], seen = {};
      var finalDepth = slotsLeftAfter === 0;
      for (var xi = 0; xi < expansions.length; xi++) {
        var ex = expansions[xi];
        var src = beams[ex[1]];
        var items = this._insertSorted(src.items,
                                       this._memberTag(ex[2], ex[3], ex[4]));
        var key = items.join("|");
        if (seen[key]) continue;
        seen[key] = true;
        var party2 = src.party.concat([ex[2]]);
        if (finalDepth && hasAvoid && avoidKeys[CompEngine.rosterKey(party2)])
          continue;   /* already shown: the next-best completes */
        var combos2 = src.combos.concat([ex[3]]);
        var gears2 = src.gears.concat([ex[5]]);
        var fc2 = this._forgeCounts(party2, combos2);
        nextBeams.push({ party: party2, combos: combos2, gears: gears2,
                         counts: fc2[0], roles: fc2[1], preds: fc2[2], groups: fc2[3],
                         state: this.partyState(party2, combos2, gears2),
                         items: items,
                         score: this.compScore(party2, combos2, gears2) });
        if (nextBeams.length >= beamWidth) break;
      }
      if (!nextBeams.length && finalDepth && hasAvoid) {
        /* every reachable completion was shown already: return the best
           of them, flagged (mirrors engine.py) */
        exhausted = true;
        hasAvoid = false; avoidKeys = {};
        var ex0 = expansions[0], src0 = beams[ex0[1]];
        var partyX = src0.party.concat([ex0[2]]);
        var combosX = src0.combos.concat([ex0[3]]);
        var gearsX = src0.gears.concat([ex0[5]]);
        var fcX = this._forgeCounts(partyX, combosX);
        nextBeams.push({ party: partyX, combos: combosX, gears: gearsX,
                         counts: fcX[0], roles: fcX[1], preds: fcX[2], groups: fcX[3],
                         state: this.partyState(partyX, combosX, gearsX),
                         items: this._insertSorted(src0.items,
                                                   this._memberTag(ex0[2], ex0[3], ex0[4])),
                         score: this.compScore(partyX, combosX, gearsX) });
      }
      beams = nextBeams;
    }
    var best = beams[0];
    var party = best.party, combosOut = best.combos, gearsOut = best.gears;
    var fixed = locked.length;
    if (party.length > fixed) {
      /* refine -> pair-trade -> refine (mirrors engine.py forge) */
      var av = hasAvoid ? avoidKeys : null;
      var rc = this._refineConstrained(ctx, party, combosOut, gearsOut, fixed,
                                       undefined, av);
      rc = this._twoOpt(ctx, rc[0], rc[1], rc[2], fixed, undefined, undefined, av);
      rc = this._refineConstrained(ctx, rc[0], rc[1], rc[2], fixed, undefined, av);
      party = rc[0]; combosOut = rc[1]; gearsOut = rc[2];
    }
    /* filler audit (mirrors engine.py): negative slots split into `held`
       (mandated by a minimum constraint) and `filler` (must not survive). */
    var filler = [], held = [];
    var base = this.compScore(party, combosOut, gearsOut);
    for (var i2 = fixed; i2 < party.length; i2++) {
      var sub = party.slice(0, i2).concat(party.slice(i2 + 1));
      var subC = combosOut.slice(0, i2).concat(combosOut.slice(i2 + 1));
      var subG = gearsOut.slice(0, i2).concat(gearsOut.slice(i2 + 1));
      if (base - this.compScore(sub, subC, subG) >= -1e-9) continue;
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
    var kits = {};
    for (var ki = fixed; ki < party.length; ki++) {
      if (gearsOut[ki] && gearsOut[ki].length) {
        var kv = this.kitVariants(party[ki]);
        var vname = null;
        for (var kvi = 0; kvi < kv.length; kvi++) {
          var glk = kv[kvi][1];
          if (glk && glk.length === gearsOut[ki].length
              && glk.join("|") === gearsOut[ki].join("|")) {
            vname = kv[kvi][0];
            break;
          }
        }
        kits[ki] = { variant: vname, gears: gearsOut[ki] };
      }
    }
    return { party: party, combos: combosOut, gears: gearsOut, kits: kits,
             score: base,
             feasible: feasible, filler: filler, held: held, locked: fixed,
             exhausted: exhausted };
  };

  CompEngine.prototype.replaceOptions = function (party, index, combos, gears,
                                                  topN, pool) {
    /* Ranked replacements for ONE slot — a one-slot forge (mirrors
       engine.py replace_options): every candidate scored as a dressed
       pick into the REST and passed through the forge's own gates with
       no slot to spare; the slot's current weapon left out. A party past
       PARTY_CAP is refused, as the forge refuses it. */
    refusePastCap(party.length);
    party = party.slice();
    var n = party.length, i;
    var cs = [], gs = [];
    for (i = 0; i < n; i++) {
      cs.push(combos && i < combos.length ? combos[i] : null);
      gs.push(gears && i < gears.length && gears[i] && gears[i].length
              ? gears[i].slice() : null);
    }
    if (topN === undefined || topN === null) topN = 5;
    var candPool = pool !== undefined && pool !== null ? pool.slice() : this.suggestPool().slice();
    var ctx = this._forgeCtx(candPool);
    var rest = party.slice(0, index).concat(party.slice(index + 1));
    var restC = cs.slice(0, index).concat(cs.slice(index + 1));
    var restG = gs.slice(0, index).concat(gs.slice(index + 1));
    var fcr = this._forgeCounts(rest, restC);
    var state = this.partyState(rest, restC, restG);
    /* the slot's member as built, priced on the rest's state: the exact
       compScore(party) - compScore(rest) without two full compScores
       (mirrors engine.py, F46) */
    var contrib = this._asBuilt(state, party[index], cs[index], gs[index]);
    var beam = { state: state, roles: fcr[1], preds: fcr[2] };
    var out = [];
    for (var pi = 0; pi < candPool.length; pi++) {
      var w = candPool[pi];
      if (w === party[index]) continue;
      if (!this._addOk(ctx, fcr[0], fcr[1], fcr[2], fcr[3], w)) continue;
      if (!this._seatMixOk(ctx, rest.concat([w]))) continue;   /* the swap would un-justify a spill */
      var pick = this._forgeEvalPick(ctx, beam, w, 0);
      if (pick === null) continue;
      out.push({ weapon: w, display_name: this.weapons[w].display_name,
                 score: pick.score, delta: pick.score - contrib,
                 combo: pick.combo, kit: (pick.vgears || []).slice() });
    }
    out.sort(function (a, b) {
      var qa = qrank(a.score), qb = qrank(b.score);
      if (qa !== qb) return qb - qa;
      return a.weapon < b.weapon ? -1 : a.weapon > b.weapon ? 1 : 0;
    });
    return out.slice(0, topN);
  };

  CompEngine.prototype._seatMixOk = function (ctx, party) {
    /* The seat-skeleton invariant on a WHOLE roster (mirrors engine.py
       _seat_mix_ok): in every role, a seat past its typical
       while another seat of the role stands under its typical is carried
       only by bodies that satisfy a predicate minimum none of the
       under-typical seats could meet. Refinement and replaceOptions check
       the roster a swap would LEAVE. True when no seat cell is in force. */
    if (!ctx.seatGate) return true;
    var counts = {}, members = {}, i, w, s;
    for (i = 0; i < party.length; i++) {
      w = party[i]; s = this.seatOf(w);
      if (s === null) continue;
      counts[s] = (counts[s] || 0) + 1;
      if (!members[s]) members[s] = [];
      members[s].push(w);
    }
    for (var r in ctx.roleSeats) {
      var under = [];
      for (var s2 in ctx.roleSeats[r]) {
        if ((counts[s2] || 0) < (ctx.seatTyp[s2] || 0)) under.push(s2);
      }
      if (!under.length) continue;
      for (s in counts) {
        var t = ctx.seatTyp[s] || 0;
        var n = counts[s];
        if (n <= t || ((this.rolesBook[s] || {})["class"]) !== r) continue;
        var excused = 0;
        for (i = 0; i < members[s].length; i++) {
          var poss = this._withProfile(members[s][i], this._predPossible(members[s][i]));
          for (var pn in ctx.predMin) {
            if (!poss[pn]) continue;
            var seats = ctx.predSeats[pn] || {}, blocked = false;
            for (var ui = 0; ui < under.length; ui++) { if (seats[under[ui]]) { blocked = true; break; } }
            if (!blocked) { excused++; break; }
          }
        }
        if (excused < n - t) return false;
      }
    }
    return true;
  };

  CompEngine.prototype._addOk = function (ctx, counts, roles, preds, groups, w) {
    /* Copy/group/role-MAX/seat-MAX check for adding `w` to a roster whose
       counts exclude the slot being replaced (mirrors engine.py _add_ok).
       Minima are enforced through _forgeEvalPick's exact per-combo need. */
    if ((counts[w] || 0) + 1 > this._dupGenMax(w)) return false;
    var gs = this.groupsOf[w] || [];
    for (var g = 0; g < gs.length; g++) {
      var gmax = this.groups[gs[g]].max;
      if ((groups[gs[g]] || 0) + 1 > (gmax === undefined ? 1e9 : gmax)) return false;
    }
    var r = this.roleOf(w);
    var mx = ctx.roleMax[r];
    if (mx !== undefined && (roles[r] || 0) + 1 > mx) return false;
    var p0 = this._profilePrimary[w];
    if (p0 !== undefined && ctx.seatMax[p0] !== undefined &&
        (preds[p0] || 0) + 1 > ctx.seatMax[p0]) return false;
    /* typical (F31), optimistic like the prune: the exact
       per-combo check rides _forgeEvalPick */
    return this._typOk(ctx, roles, preds, w,
                       this._withProfile(w, this._predPossible(w)));
  };

  CompEngine.prototype._refineConstrained = function (ctx, party, combos,
                                                      gears, fixed, maxPasses,
                                                      avoid) {
    /* Steepest-descent 1-opt over generated slots, constraint-aware:
       minima are checked against the REST roster's combo-aware counts, so
       a swap can never trade away the spells a minimum was counting on
       (mirrors engine.py _refine_constrained). */
    party = party.slice(); combos = combos.slice(); gears = gears.slice();
    if (maxPasses === undefined) maxPasses = 8;
    for (var pass = 0; pass < maxPasses; pass++) {
      var move = null, gain = 1e-9;
      for (var i = fixed; i < party.length; i++) {
        var rest = party.slice(0, i).concat(party.slice(i + 1));
        var restC = combos.slice(0, i).concat(combos.slice(i + 1));
        var restG = gears.slice(0, i).concat(gears.slice(i + 1));
        var fcr = this._forgeCounts(rest, restC);
        var state = this.partyState(rest, restC, restG);
        /* the slot's member as built, priced on the rest's state it
           already holds (mirrors engine.py, F46) */
        var contrib = this._asBuilt(state, party[i], combos[i], gears[i]);
        var beam = { state: state, roles: fcr[1], preds: fcr[2] };
        for (var j = 0; j < ctx.pool.length; j++) {
          var w = ctx.pool[j];
          /* w === party[i] deliberately NOT skipped (the dressed forge;
             mirrors engine.py): re-resolving the SAME
             weapon's combo+kit can be the best move — identical picks
             price d == 0 and are never taken. */
          if (!this._addOk(ctx, fcr[0], fcr[1], fcr[2], fcr[3], w)) continue;
          if (!this._seatMixOk(ctx, rest.concat([w]))) continue;   /* the swap would un-justify a spill */
          var pick = this._forgeEvalPick(ctx, beam, w, 0);
          if (pick === null) continue;
          var d = pick.score - contrib;
          if (d > gain) {
            if (avoid && w !== party[i] &&
                avoid[CompEngine.rosterKey(rest.concat([w]))]) continue;
            move = [i, w, pick.combo, pick.vgears]; gain = d;
          }
        }
      }
      if (move === null) break;
      party[move[0]] = move[1];
      combos[move[0]] = move[2];
      gears[move[0]] = move[3];
    }
    return [party, combos, gears];
  };

  CompEngine.prototype._twoOpt = function (ctx, party, combos, gears,
                                           fixed, worstK, candM, avoid) {
    /* Bounded 2-opt over the weakest generated slots (mirrors engine.py
       _two_opt). An accepted pair-move reorders the roster, so the pass
       restarts with freshly computed weakest slots. */
    party = party.slice(); combos = combos.slice(); gears = gears.slice();
    if (worstK === undefined) worstK = 4;
    if (candM === undefined) candM = 12;
    var best = this.compScore(party, combos, gears);
    if (party.length - fixed < 2) return [party, combos, gears];
    var improved = true, passes = 0;
    while (improved && passes < 3) {
      improved = false;
      passes += 1;
      var contribs = [];
      for (var gi = fixed; gi < party.length; gi++) {
        var sub = party.slice(0, gi).concat(party.slice(gi + 1));
        var subC = combos.slice(0, gi).concat(combos.slice(gi + 1));
        var subG = gears.slice(0, gi).concat(gears.slice(gi + 1));
        contribs.push([best - this.compScore(sub, subC, subG), gi]);
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
          var restG = gears.slice(0, i).concat(gears.slice(i + 1, j)).concat(gears.slice(j + 1));
          var state = this.partyState(rest, restC, restG);
          var ranked = [];
          for (var pi = 0; pi < ctx.pool.length; pi++) {
            var pw = ctx.pool[pi];
            var pk = this._evalPick(state, pw);
            ranked.push([pk.score, pw, pk.combo, pk.vgears]);
          }
          ranked.sort(function (a, b) {
            var qa = qrank(a[0]), qb = qrank(b[0]);
            if (qa !== qb) return qb - qa;
            return a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0;
          });
          var shortlist = ranked.slice(0, candM);
          for (var sa = 0; sa < shortlist.length && !improved; sa++) {
            var wa = shortlist[sa][1], ca = shortlist[sa][2], ga = shortlist[sa][3];
            var pa = rest.concat([wa]);
            var pca = restC.concat([ca]);
            var pga = restG.concat([ga]);
            var state2 = this.partyState(pa, pca, pga);
            for (var sb = 0; sb < shortlist.length; sb++) {
              var wb = shortlist[sb][1];
              var pkb = this._evalPick(state2, wb);
              var candParty = pa.concat([wb]);
              var candCombos = pca.concat([pkb.combo]);
              var candGears = pga.concat([pkb.vgears]);
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
                for (var smx in ctx.seatMax) {
                  if ((preds[smx] || 0) > ctx.seatMax[smx]) { ok = false; break; }
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
              if (ok) {
                var hasTyp = false;
                for (var tk in ctx.roleTyp) { hasTyp = true; break; }
                if (hasTyp || ctx.seatGate) {
                  /* typical (F31; mirrors engine.py): the pair
                     joins the rest one body at a time, each on its exact
                     combo - the same incremental read the beam makes */
                  var fc0 = this._forgeCounts(rest, restC);
                  var caSet = this._withProfile(wa, this._predContrib(wa, ca));
                  var cbSet = this._withProfile(wb, this._predContrib(wb, pkb.combo));
                  if (!this._typOk(ctx, fc0[1], fc0[2], wa, caSet)) ok = false;
                  else {
                    var fc1 = this._forgeCounts(pa, pca);
                    if (!this._typOk(ctx, fc1[1], fc1[2], wb, cbSet)) ok = false;
                  }
                }
              }
              if (ok && !this._seatMixOk(ctx, candParty)) ok = false;   /* the pair would un-justify a spill */
              if (!ok) continue;
              /* carrier quota (mirrors engine.py two-opt) */
              var ccaps = this.carrierCaps(), ccnt = this._carrierCounts(candParty, candGears), over = false;
              for (var ce0 in ccnt) if (ccnt[ce0] > (ccaps[ce0] === undefined ? 1e9 : ccaps[ce0])) over = true;
              if (over) continue;
              if (avoid && avoid[CompEngine.rosterKey(candParty)]) continue;
              var d2 = this.compScore(candParty, candCombos, candGears) - best;
              if (d2 > 1e-9) {
                party = candParty;
                combos = candCombos;
                gears = candGears;
                best = best + d2;
                improved = true;
                break;
              }
            }
          }
        }
      }
    }
    return [party, combos, gears];
  };

  if (typeof module !== "undefined" && module.exports) module.exports = CompEngine;
  else root.CompEngine = CompEngine;
})(typeof self !== "undefined" ? self : this);
