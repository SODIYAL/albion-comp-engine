/* Composition scoring — JavaScript port of engine/engine.py.
 *
 * SINGLE SOURCE OF MATH: engine/engine.py is authoritative; this file must
 * mirror it exactly and tests/test_js_parity.py verifies that it does
 * (same fitness, same rankings, same forged rosters, across all templates,
 * on random parties). If you change one, change both, then run the parity
 * test.
 *
 * Used two ways:
 *   - inlined into dashboard/index.html by dashboard/build.py (browser —
 *     dashboard/_app.js is rendering-only and calls this engine)
 *   - require()'d by tests/js_parity_runner.js (node)
 *
 * TWO SUPPLIES (mirrors engine.py): coverage / headroom / over-stack read the
 * DRESSED supply (weapon + loadout + worn gear), while the hard-floor term
 * reads the weapon+loadout supply only — Option C, owner ruling 2026-08-27,
 * so worn gear can never buy its way past a structural floor.
 *
 * KNOWN OPEN DEFECT (ruling pending, see HANDOFF.md): dataset targets and
 * soft caps were fitted in WEAPON+spell-pick units while supply is measured
 * on whole dressed people. The math is unaffected; the two sides of every
 * comparison are currently in different units.
 */
(function (root) {
  "use strict";

  /* Mechanics-affected capability families (MECHANICS_TODO.md): mirrors
     AOE_ESCALATION_CAPS / RESILIENCE_CAPS in engine.py. */
  var AOE_ESCALATION_CAPS = ["burst_aoe"];
  var RESILIENCE_CAPS = ["burst_st", "execute"];

  var KEY_TIER_RX = /^T\d+_/;
  var KEY_ENCH_RX = /@\d+$/;
  function keyForm(key) {
    /* A gear key stripped of tier and enchant: 'T7_POTION_REVIVE@2' ->
       'POTION_REVIVE'. Mirrors engine.py _key_form / builds_lib.key_form. */
    return String(key).trim().toUpperCase()
      .replace(KEY_ENCH_RX, "").replace(KEY_TIER_RX, "");
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
    /* SUPER-ADDITIVE DUPLICATES (2026-08-28, mirrors engine.py): gear key ->
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
       detectRole/roleAdvisory (DESCRIPTIVE, never scoring) and, since
       2026-09-03, the coarse role class below. */
    this.rolesBook = {};
    var rb = data.roles || [];
    for (var ri = 0; ri < rb.length; ri++) this.rolesBook[rb[ri].id] = rb[ri];
    /* Coarse role class: composition override > the class of the primary
       SEAT (first uniformed menu role, the detectRole resolution) > the
       sheet's role_hint. Mirrors engine.py (2026-09-03). */
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
    /* Flag predicate `primary_heal` (owner ruling 2026-08-23, mirrors
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
    /* members of derived NON-STACKING groups (shared kit priced
       count-once — the cursed line): their group-band slots are EARNED
       (owner ruling 2026-08-25; see the generation-fit gate) */
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
    this._carrierCapsCache = null;   /* carrierCaps() memo (size-keyed) */
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
    /* Resilience-Penetration context (owner ruling 2026-08-25, mirrors
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
       style ships {} until the owner rules a value. */
    this.targetMults = (styles[this.style] || {}).target_mults || {};
    this._targets = {}; this._softs = {}; this._weights = {};
    for (var cap2 in this.reqs) {
      var r = this.reqs[cap2];
      var tm = this.targetMults[cap2];
      tm = (tm === undefined) ? 1.0 : tm;
      this._targets[cap2] = tm * (r.scales ? r.target * this.size / this.baseSize : r.target);
      this._softs[cap2] = tm * (r.scales ? r.soft_cap * this.size / this.baseSize : r.soft_cap);
      var m2 = this.styleMults[cap2];
      this._weights[cap2] = r.weight * (m2 === undefined ? 1.0 : m2);
    }
    /* OPTIONAL capabilities (owner ruling 2026-08-28) — mirrors engine.py
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
    /* Economics gate (owner ruling 2026-08-23, mirrors engine.py): a cost
       tier may be barred from SUGGESTIONS/generation below a party size
       (crystal regear economics). Manual/locked picks always score;
       swap_review flags them off_budget. */
    this._costGated = {};
    var cg = via.cost_gate || {};
    for (var tier in cg) {
      var cgMin = (cg[tier] || {}).min_size;
      if (cgMin && this.size < cgMin) {
        for (i = 0; i < this.pool.length; i++) {
          if (this.weapons[this.pool[i]].cost_tier === tier)
            this._costGated[this.pool[i]] = true;
        }
      }
    }
    this._suggest = [];
    for (i = 0; i < this.pool.length; i++) {
      if (!excl[this.pool[i]] && !this._costGated[this.pool[i]])
        this._suggest.push(this.pool[i]);
    }
    /* Style-fit suggestion gate (identity Phase C — mirrors engine.py:
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
    /* Generation-fit gate (owner ruling 2026-08-23 round 3, mirrors
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
          if (IDS.indexOf(this.style) >= 0) {
            gOk = gsf.fit[this.style] && gsf.fit[this.style][gBand] === "fits";
          } else {
            gOk = false;
            for (var si2 = 0; si2 < IDS.length; si2++) {
              if (gsf.fit[IDS[si2]] && gsf.fit[IDS[si2]][gBand] === "fits") {
                gOk = true;
                break;
              }
            }
          }
        } else if (gRole === "healer" && gBand === "group") {
          /* owner round 4: a healer unfit at group for EVERY style (the
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
          /* owner ruling 2026-08-25: a non-stacking budget slot (the
             cursed line — its shared Q priced count-once) is EARNED at
             group scale: "the only weapon i see in any party bigger than
             15 people is the lifecurse, damnation, or rotcaller." The
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
    /* Style role-band overrides (owner ruling 2026-08-23, styles.yaml
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
    /* NEED PROFILES (increment 3, owner-ruled 2026-08-26) — mirrors
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
          var pMn = Math.round(pRule.min * this.size / pRef);
          if (pMn > 0) this._profileMin[rk] = pMn;
        }
        if (pRule.max !== undefined)
          this._profileMax[rk] = Math.round(pRule.max * this.size / pRef);
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
    this._gearCache = {};
    this._defaultCache = {};
    this._nsCache = {};
    this._variantCache = {};
    this._dressedCache = {};
  };

  CompEngine.prototype.setDressing = function (enabled) {
    /* Validation affordance (V3-W, 2026-08-27; mirrors engine.py
       set_dressing): when OFF, every CANDIDATE evaluates naked —
       kitVariants yields [["v0", null]] for all weapons, _dressedExtras
       aliases the weapon-only combo vectors, and _comboScoreDressed's
       identity check routes into _comboScore. Same formula, no second
       scoring path. Clears the dressed caches so vectors built under the
       other setting cannot leak. */
    this.dressCandidates = enabled !== false;
    this._variantCache = {};
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

  /* Role layer (roles-design.md increment 1; mirrors engine.py) —
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

  CompEngine.prototype.isStyleUnfit = function (weapon) {
    /* Unfit for the DECLARED style at this size band — bars suggestions
       only, never scoring (mirrors engine.py is_style_unfit). */
    return !!this._styleUnfit[weapon];
  };

  CompEngine.prototype.isExcluded = function (weapon) {
    /* Viability bar for GENERATED comps at this content+size — scoring is
       never blocked (mirrors engine.py is_excluded). */
    return !!this._excluded[weapon];
  };

  CompEngine.prototype.isCostGated = function (weapon) {
    /* Cost-tier bar for GENERATED comps at this size (crystal regear
       economics, owner ruling 2026-08-23) — suggestions only, scoring is
       never blocked (mirrors engine.py is_cost_gated). */
    return !!this._costGated[weapon];
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

  CompEngine.prototype._eff = function (caps, delivery, pen) {
    var out = {}, m, v;
    for (var c in caps) {
      v = caps[c] / this.scoreUnit;
      m = this.mechMults[c];
      v = v * (m === undefined ? 1.0 : m);
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
    var dl = this.weapons[weapon].cap_delivery || {};
    var pen = this.weapons[weapon].resil_pen || 0.0;
    var hasSlots = lo && lo.slots && lo.slots.length;
    var hasAlways = lo && lo.always && Object.keys(lo.always).length;
    if (!lo || (!hasSlots && !hasAlways))
      return { always: this._eff(this.capsOf(weapon), dl, pen), slots: [] };
    var self = this;
    return {
      always: this._eff(lo.always || {}, dl, pen),
      slots: (lo.slots || []).map(function (slot) {
        return slot.map(function (b) { return self._eff(b, dl, pen); });
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
  CompEngine.prototype.gearKey = function (key) {
    /* The CURATED key for a worn item, ignoring tier (owner ruling
       2026-08-28; mirrors engine.py gear_key). Consumables are curated at one
       representative tier while comps record whatever tier they ran, so an
       exact-key lookup scored 20 real Gigantify potions as nothing. Exact
       keys win; an ambiguous tier-stripped form resolves to nothing rather
       than guessing. */
    if (this.gear[key]) return key;
    var alias = this._gearAlias[keyForm(key)];
    return alias === undefined ? key : alias;
  };

  CompEngine.prototype.gearExtras = function (key) {
    key = this.gearKey(key);
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

  CompEngine.prototype.buildExtra = function (weapon, combo, gear, role,
                                              waiveCosts) {
    /* Full-build member: weapon loadout + gear abilities + the STAT
       channel (mirrors engine.py build_extra — same float order).
       CC-duration % (increment 2, owner 2026-08-25) multiplies the
       wearer's own duration-bearing CC — the Leering-Cane pairing as
       physics. `role` (a seat id) additionally applies the DOCTRINE
       PASSIVE picks — generation/display only; scoring never passes
       a role. */
    var out = {}, c;
    var base = this.memberExtra(weapon, combo);
    for (c in base) out[c] = base[c];
    var armorPts = 0.0, ccrPts = 0.0, dmgPct = 0.0, healPct = 0.0;
    var ccdurPct = 0.0, ccrMult = 0.0;
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
    return out;
  };

  /* Gear keys whose self-cost this party has offset — the ONLY
     super-additive duplicate rule in the model, deliberately narrow (owner
     2026-08-28). Mirrors engine.py _self_cost_waivers: a VERIFIED
     interaction record on the cost's evidence spell declares
     self_cost_offset_min_copies, and the party fields that many. Cancels a
     cost, never adds supply. */
  CompEngine.prototype.selfCostWaivers = function (gears) {
    var out = {};
    if (!this.costOffsets || !gears) return out;
    var counts = {};
    for (var i = 0; i < gears.length; i++) {
      var g = gears[i] || [];
      for (var j = 0; j < g.length; j++) {
        var key = Array.isArray(g[j]) ? g[j][0] : g[j];
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

  CompEngine.prototype._chestUniform = function (seat, weapon) {
    /* chest classes admitted for `weapon` in `seat`: the book uniform plus
       the weapon's observed-majority class where the harvest is clear
       (dataset kit_weapon_uniform) -- mirrors engine.py _chest_uniform */
    var rec = this.rolesBook[seat] || {};
    var ext = (rec.kit_weapon_uniform || {})[weapon];
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
                                              role) {
    /* IDEAL KIT per weapon, per content/style, per comp — mirrors
       engine.py kit_options (2026-08-20; JS mirror 2026-08-21;
       DOCTRINE-LED since increment 2, owner 2026-08-25 "yes its the
       whole build"): ranked gear options per slot. No party ->
       context-free weighted-delta value with the DOCTRINE TIER first;
       with `party` -> comp-aware exact fitness delta outranks tier
       membership (doctrine stays annotation + tie-break). `role`:
       undefined/"auto" resolves the weapon's primary seat, null is the
       explicit diagnostic escape (ungated pool), a seat id uses that
       seat. With a seat the CHEST pool hard-gates to the uniform
       classes; options carry doctrine/carries/passive.
       FAIL-CLOSED GENERATION (owner ruling 2026-09-01, mirrors
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
       (kit_weapon_uniform, 2026-09-03) -- mirrors engine.py */
    var uniform = this._chestUniform(seat, weapon);
    var doctrine = seatRec.kit || {};
    /* Per-weapon doctrine tier (owner design 2026-08-26): this weapon's
       own observed items (effect carriers excluded at the build) outrank
       the seat aggregate; `doctrine` is "weapon" / "seat" / false and
       weapon-tier options carry doctrine_n = [count, slot total].
       Mirrors engine.py. */
    var wdoc = (seatRec.kit_weapon || {})[weapon] || {};
    var seatClass = seatRec["class"] || null;
    /* observed-build archetype (2026-09-01, mirrors engine.py): the KIT
       pick follows what real players field — weapon's own conditional-
       modal build first, seat fallback per slot; the archetype item
       moves to the front of its slot's options. */
    var arch = {};
    if (role !== null) {
      var wbArch = (seatRec.kit_weapon_build || {})[weapon] || {};
      var sbArch = seatRec.kit_build || {};
      var aslot;
      for (aslot in sbArch) arch[aslot] = sbArch[aslot];
      for (aslot in wbArch) arch[aslot] = wbArch[aslot];
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
    /* Style-fit gear gate (identity Phase C, owner 2026-08-23): under a
       DECLARED brawl, cloth never gets SUGGESTED for a non-healer —
       mirrors engine.py (drift closed 2026-08-25: the JS port had
       skipped this gate). */
    if ((this.style === "brawl" || this.style === "brawl_clap")
        && this.roleOf(weapon) !== "healer") {
      var unclothed = (bySlot.armor || []).filter(function (g) {
        return g.indexOf("_CLOTH_") < 0;
      });
      if (unclothed.length) bySlot.armor = unclothed;
    }
    var bare = this.memberExtra(weapon, combo);
    var joined = null, baseGears = null, fBare = 0.0;
    if (party !== null && party !== undefined) {
      joined = party.concat([weapon]);
      baseGears = party.map(function () { return null; });
      fBare = this.fitness(joined, null, baseGears.concat([null]));
    }
    var options = {}, slots = Object.keys(bySlot).sort();
    for (var si = 0; si < slots.length; si++) {
      var slot = slots[si], keys = bySlot[slot].slice().sort();
      var docPool = doctrine[slot] || [];
      var wslot = {}, wtotal = 0, wp = wdoc[slot] || [];
      for (var wi = 0; wi < wp.length; wi++) {
        wslot[wp[wi][0]] = wp[wi][1];
        wtotal += wp[wi][1];
      }
      if (role !== null) {
        /* fail-closed generation (ruling 2026-09-01): only doctrine
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
          value = this.fitness(joined, null, baseGears.concat([[k]])) - fBare;
        }
        var passive = null;
        if (seatClass) {
          var p = ((this.gear[k].doctrine_passives) || {})[seatClass];
          if (p) passive = { id: p.id, name: p.name };
        }
        var why = [];
        for (di = 0; di < Math.min(3, deltas.length); di++)
          why.push([deltas[di][0], Math.round(deltas[di][1] * 100) / 100]);
        var tier = Object.prototype.hasOwnProperty.call(wslot, k)
          ? "weapon" : (docPool.indexOf(k) >= 0 ? "seat" : false);
        ranked.push({ gear: k, display_name: this.gear[k].display_name,
                      value: value, doctrine: tier,
                      doctrine_n: tier === "weapon"
                        ? [wslot[k], wtotal] : null,
                      carries: (this.itemEffects[k] || []).slice(),
                      passive: passive, why: why });
      }
      /* DOCTRINE-TIER-FIRST in both modes (owner ruling 2026-08-27,
         evidence-first): the observed tier bounds the suggestion;
         context-free ranks by count then value within a tier,
         comp-aware by the exact marginal — mirrors engine.py. */
      var gearCmp = function (a, b) {
        return a.gear < b.gear ? -1 : a.gear > b.gear ? 1 : 0;
      };
      var tierRank = function (r) {
        return r.doctrine === "weapon" ? 0 : r.doctrine === "seat" ? 1 : 2;
      };
      var wCount = function (r) { return wslot[r.gear] || 0; };
      /* EVIDENCE-FIRST (2026-09-03, mirrors engine.py): count leads the
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
            return [0, 0, -r.value, -(wslot[g] || 0)];
          return [0, inBand(g) ? 0 : 1, -(wslot[g] || 0), -r.value];
        }
        if (t === 1)
          return [1, seatOrder[g] === undefined ? docPool.length : seatOrder[g],
                  0, -r.value];
        return [2, 0, -r.value, 0];
      };
      ranked.sort(function (a, b) {
        var ka = sortKey(a), kb = sortKey(b);
        for (var ci = 0; ci < ka.length; ci++) {
          if (ka[ci] !== kb[ci]) return ka[ci] < kb[ci] ? -1 : 1;
        }
        return gearCmp(a, b);
      });
      var av = arch[slot];
      if (av && (topCount === 0 || inBand(av[0]))) {
        /* the observed build leads the slot (overlay ruling) -- never
           from outside the evidence band */
        for (var ai = 0; ai < ranked.length; ai++) {
          if (ranked[ai].gear === av[0]) {
            ranked[ai].observed_build = [av[1], av[2]];
            ranked.unshift(ranked.splice(ai, 1)[0]);
            break;
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
  CompEngine.prototype._carrierCounts = function (gears) {
    /* {effect: members wearing a chest granting it} (mirrors engine.py) */
    var caps = this.carrierCaps(), out = {}, anyCap = false;
    for (var c0 in caps) { anyCap = true; break; }
    if (!anyCap) return out;
    for (var i = 0; i < (gears || []).length; i++) {
      var g = gears[i] || [];
      for (var j = 0; j < g.length; j++) {
        var effs = this.itemEffects[g[j]] || [];
        for (var k = 0; k < effs.length; k++) {
          if (caps[effs[k]] !== undefined) out[effs[k]] = (out[effs[k]] || 0) + 1;
        }
      }
    }
    return out;
  };
  CompEngine.prototype._variantCapped = function (state, vgears) {
    /* true when dressing in `vgears` would push a carrier past its cap */
    var carriers = state.carriers;
    if (!carriers || !vgears) return false;
    var caps = this.carrierCaps();
    for (var j = 0; j < vgears.length; j++) {
      var effs = this.itemEffects[vgears[j]] || [];
      for (var k = 0; k < effs.length; k++) {
        var eff = effs[k];
        if (caps[eff] !== undefined && (carriers[eff] || 0) >= caps[eff]) return true;
      }
    }
    return false;
  };
  CompEngine.prototype.observedShare = function (weapon, gearId) {
    var seat = this.primarySeat(weapon);
    var rec = this.rolesBook[seat] || {};
    var slot = (this.gear[gearId] || {}).slot;
    var wl = ((rec.kit_weapon || {})[weapon] || {})[slot] || [];
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
    var waived = gears ? this.selfCostWaivers(gears) : null;
    for (var i = 0; i < party.length; i++) {
      var extra = (gears && gears[i] && gears[i].length)
        ? this.buildExtra(party[i], combos ? combos[i] : null, gears[i],
                          null, waived)
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

  CompEngine.prototype._coverTerms = function (cap, have, gain, target,
                                               haveFloor, gainFloor) {
    /* [coverage delta (incl. headroom), floor-lift delta] — two terms so
       callers accumulate in their original order (mirrors engine.py).
       Option C (owner ruling 2026-08-27): STRUCTURAL hard floors read the
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
  CompEngine.prototype.fitness = function (party, combos, gears) {
    var s = this.effectiveSupply(party, combos, gears);
    /* Option C (owner ruling 2026-08-27): STRUCTURAL hard floors read the
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
       (mirrors engine.py max_fitness, review 2026-08-18). Given a party,
       OPTIONAL capabilities it fields none of drop out of the supremum
       (owner ruling 2026-08-28) — a comp is not marked down for skipping a
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
  CompEngine.prototype.partyState = function (party, combos, gears) {
    /* Everything a candidate marginal needs (mirrors engine.py).
       Dressed forge 2026-08-27: `s` is the FIT supply (gear-inclusive
       when gears are given), `sSyn` the weapon-only supply every synergy
       term reads — comp_score's own seams. gears absent keeps both the
       same object (bit-identical to the pre-gears state). */
    var st = this._synState(party, combos), sSyn = st[0], J = st[1];
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
    return { s: s, sSyn: sSyn, J: J, pairVals: pairVals, counts: counts,
             nsMax: nsMax,
             /* carrier quota (2026-09-03): what this roster already wears */
             carriers: this._carrierCounts(gears) };
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
       _combo_score) — identical float-op order to the original loop.
       Option C: on a DRESSED party the floor terms read sSyn + the
       candidate's own (naked) caps. */
    var adj = this._nonstackAdjust(state, weapon, i, extra);
    var dFit = (state.s !== state.sSyn)
      ? this._margFitFrom(state.s, adj, state.sSyn, adj)
      : this._margFitFrom(state.s, adj);
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

  CompEngine.prototype.kitVariants = function (weapon) {
    /* Doctrine kit variants for GENERATION (dressed forge 2026-08-27,
       mirrors engine.py kit_variants): v0 = the seat's context-free
       doctrine kit (off-tier slots stay unset), plus ONE divergent
       single-slot swap (variant cap 2 — perf ruling); [["v0", null]]
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
      for (var oi = 1; oi < opts.length; oi++) {
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
      /* carrier quota (2026-09-03, mirrors engine.py): a carrier modal
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
                                                     wextra, dextra) {
    /* _comboScore for a DRESSED candidate: fit half prices the dressed
       vector, synergy half the weapon-only vector — the exact
       decomposition of compScore-with-gears (mirrors engine.py
       _combo_score_dressed). Same object -> exactly _comboScore. */
    if (dextra === wextra) return this._comboScore(state, weapon, i, wextra);
    /* Option C: a DRESSED candidate's floor terms read the weapon-only
       basis on BOTH sides — sSyn for the party and the candidate's
       weapon-only adjusted gains — so its kit can never buy floor relief
       the party's kits are denied (mirrors engine.py). */
    var adj = this._nonstackAdjust(state, weapon, i, dextra);
    var adjW = this._nonstackAdjust(state, weapon, i, wextra);
    var dFit = this._margFitFrom(state.s, adj, state.sSyn, adjW);
    var dSyn = this._margSynFrom(state, wextra);
    return { val: this.alpha * dFit + this.beta * dSyn,
             dFit: dFit, dSyn: dSyn };
  };

  CompEngine.prototype._evalPick = function (state, weapon) {
    /* THE candidate score — the exact compScore delta of adding `weapon`
       with its best loadout AND doctrine-kit variant (dressed forge
       2026-08-27; mirrors engine.py _eval_pick). Returns
       {score, dFit, dSyn, meta, combo, variant, vgears}. */
    var best = null;
    var extras = this._comboExtras(weapon);
    var dressed = this._dressedExtras(weapon);
    var variants = this.kitVariants(weapon);
    for (var vi = 0; vi < variants.length; vi++) {
      var vkey = variants[vi][0], vgears = variants[vi][1];
      if (this._variantCapped(state, vgears)) continue;   /* carrier quota */
      var dext = dressed[vkey];
      for (var i = 0; i < extras.length; i++) {
        var cs = this._comboScoreDressed(state, weapon, i, extras[i],
                                         dext[i]);
        if (best === null || cs.val > best.val)
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

  CompEngine.prototype._rawMemberCaps = function (weapon, combo) {
    /* The member's RAW one-spell-per-slot capability points (loadout
       always + chosen bundles, sheet 1-7 scale) — content- and style-
       independent; flat sheet fallback (mirrors engine.py
       _raw_member_caps). */
    var extras = this._comboExtras(weapon);
    if (combo === null || combo === undefined || combo < 0 || combo >= extras.length)
      combo = this.defaultCombo(weapon);
    var lo = this.weapons[weapon].loadout || {};
    if (!((lo.slots && lo.slots.length) || lo.always))
      return this.weapons[weapon].capabilities;
    var caps = {};
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
    return caps;
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
    var state = { s: s, sSyn: s, J: [], pairVals: [], counts: {} };
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

  CompEngine.prototype.explain = function (party, candidate, combos, gears) {
    /* Per-capability delta terms for the candidate's CHOSEN loadout —
       matches what _evalPick scored (mirrors engine.py explain). */
    var state = this.partyState(party, combos, gears);
    var pick = this._evalPick(state, candidate);
    var extra = this.memberExtra(candidate, pick.combo);
    var s = state.s, terms = [];
    for (var cap in extra) {
      var gain = extra[cap];
      if (!(cap in this.reqs) || !gain) continue;
      var have = s[cap] || 0.0, target = this.target(cap);
      var ct = this._coverTerms(cap, have, gain, target,
                                state.sSyn[cap] || 0.0);
      var d = ct[0] + ct[1];
      if (d > 0.05) {
        terms.push({ delta: Math.round(d * 100) / 100, cap: cap,
                     before: have, after: have + gain, target: target });
      }
    }
    return terms.sort(function (x, y) { return y.delta - x.delta; });
  };

  /* ------------------------------------- negative recs / redundancy lens
     (roadmap item 3, 2026-08-24 — mirrors engine.py.) A DESCRIPTIVE
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
    var extra = (vgears && vgears.length)
      ? this.buildExtra(weapon, combo, vgears)
      : this.memberExtra(weapon, combo);
    var adj = this._nonstackAdjust(state, weapon, combo, extra);
    /* Option C floor basis: floor_lift rows read the weapon-only party
       supply and the candidate's weapon-only adjusted gains, exactly as
       the marginal scored them (mirrors engine.py _pick_caps). */
    var adjW = (vgears && vgears.length)
      ? this._nonstackAdjust(state, weapon, combo,
                             this.memberExtra(weapon, combo))
      : adj;
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
    rows.sort(function (x, y) {
      if (x.delta !== y.delta) return y.delta - x.delta;
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
    var nsLines = [];
    var nsMax = state.nsMax || {};
    var contrib = this._nonstackContrib(candidate, pick.combo);
    var sids = Object.keys(contrib).sort();
    for (var si = 0; si < sids.length; si++) {
      var sid = sids[si], pmax = nsMax[sid];
      if (!pmax) continue;
      var caps = this.nonstack[sid], lost = {}, any = false;
      for (var cj = 0; cj < caps.length; cj++) {
        var cap = caps[cj], v = contrib[sid][cap] || 0.0;
        var cut = v < (pmax[cap] || 0.0) ? v : (pmax[cap] || 0.0);
        if (v && cut > 0.0) { lost[cap] = cut; any = true; }
      }
      if (any) {
        var rec = this.interactions[sid] || {};
        nsLines.push({ spell: sid, name: rec.name || sid, lost: lost });
      }
    }
    return {
      weapon: candidate,
      display_name: this.weapons[candidate].display_name,
      combo: pick.combo, kit: pick.vgears || [], score: pick.score,
      d_fitness: pick.dFit, d_synergy: pick.dSyn,
      meta_prior: pick.meta, viability: this.viabilityOf(candidate),
      dup_penalty: dupPenalty,
      caps: rows, caps_gain: capsGain,
      nonstack: nsLines,
      verdict: this._pickVerdict(pick.score, capsGain),
    };
  };

  CompEngine.prototype._pool = function (pool) {
    /* mirrors Python's `pool or self.suggest_pool()`: default excludes both
       game-retired weapons and the viability exclusions for this context. */
    if (pool && pool.length) return pool;
    return this._suggest;
  };

  CompEngine.prototype.recommend = function (party, topN, pool, combos,
                                             gears) {
    if (topN === undefined) topN = 4;
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
    out = out.sort(function (x, y) { return y.score - x.score; }).slice(0, topN);
    /* verdict lens on the returned rows only (mirrors engine.py): a
       suggestion that survives ranking can still be a depth pick in a
       saturated comp — say so instead of implying it fills a gap */
    for (i = 0; i < out.length; i++) {
      var pc = this._pickCaps(state, out[i].weapon, out[i].combo,
                              out[i].kit.length ? out[i].kit : null);
      out[i].caps_gain = pc[1];
      out[i].verdict = this._pickVerdict(out[i].score, pc[1]);
    }
    return out;
  };

  CompEngine.prototype.swapReview = function (party, topN, pool, combos,
                                              gears) {
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
      var restGears = gears
        ? gears.slice(0, i).concat(gears.slice(i + 1)) : null;
      var state = this.partyState(rest, restCombos, restGears);
      var self = this;
      var curPick = this._evalPick(state, cur);
      var curScore = curPick.score;
      /* redundancy lens (roadmap item 3, mirrors engine.py): the member
         valued exactly as a pick into the rest — does it still close any
         gap, or are its jobs already covered without it? Flag only. */
      var curPc = this._pickCaps(state, cur, curPick.combo, curPick.vgears);
      var curVerdict = this._pickVerdict(curScore, curPc[1]);
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
        off_style: this.isStyleUnfit(cur),
        off_budget: this.isCostGated(cur),
        caps_gain: curPc[1],
        verdict: curVerdict,
        redundant: curVerdict !== "ok",
        options: better.slice(0, topN).map(function (t) {
          return { weapon: t[1],
                   display_name: self.weapons[t[1]].display_name,
                   score: t[0], gain: t[0] - curScore };
        }),
      });
    }
    return out;
  };

  CompEngine.prototype.weaknesses = function (party, topN, combos, gears) {
    if (topN === undefined) topN = 3;
    var s = this.effectiveSupply(party, combos, gears), gaps = [];
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
      var soft = this.softCap(cap);
      /* saturation band (roadmap item 3, mirrors engine.py analyze):
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

  /* Identity thresholds (descriptive layer, F-V3-2) — mirrors engine.py
     comp_identity, thresholds calibrated 2026-08-23 against every
     style-declared comp on file (see VALIDATION.md, V3 round 1). */
  var IDENTITY_MELEE_CORE = 0.65, IDENTITY_RANGED_CORE = 0.35,
      IDENTITY_STRONG = 0.80, IDENTITY_CLAP_AOE = 0.50,
      IDENTITY_BC_AOE = 0.45, IDENTITY_BC_POSTURE = 0.45,
      IDENTITY_CARRIER_MIN = 4, IDENTITY_MIN_MEMBERS = 3,
      IDENTITY_RANGED_ATTACK = 9.0,
      IDENTITY_HYBRID_AOE = 0.40, IDENTITY_HYBRID_EVADE = 2.0;
  var IDENTITY_STYLES = { brawl: true, clap: true, kite: true,
                          brawl_clap: true, clap_kite: true };

  CompEngine.prototype._styleFitOf = function (weapon) {
    /* The weapon's derived style/size identity; null on pre-identity
       datasets (mirrors engine.py _style_fit_of). */
    return this.weapons[weapon].style_fit || null;
  };

  CompEngine.prototype._fitBand = function () {
    /* trio <=3, gang 4-9, group 10+ (mirrors engine.py _fit_band). */
    return this.size <= 3 ? "trio" : this.size <= 9 ? "gang" : "group";
  };

  CompEngine.prototype.compIdentity = function (party, combos) {
    /* What this comp is BECOMING, in playstyle vocabulary — v2: built up
       from MEMBER identities (weapon style_fit: E-first delivery + owner
       overrides). DESCRIPTIVE ONLY: nothing here feeds fitness,
       recommendation order, or the forge (mirrors engine.py
       comp_identity). */
    var n = party.length;
    var melee = 0.0, ranged = 0.0, aoe = 0.0, sus = 0.0, st = 0.0,
        commit = 0.0, evade = 0.0;
    var carriers = { melee: [], ranged: [] };
    var carrierCount = {};
    var nCarrierMembers = 0;
    var flex = {};
    var sides = {};
    for (var i = 0; i < n; i++) {
      var w = party[i];
      var caps = this._rawMemberCaps(w, combos ? combos[i] : null);
      var dmg = 0;
      for (var di = 0; di < DAMAGE_CAPS_PROFILE.length; di++)
        dmg += caps[DAMAGE_CAPS_PROFILE[di]] || 0;
      aoe += caps.burst_aoe || 0;
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
      if (delivery === "flex") flex[w] = true;
      sides[i] = side;
      if (carriers[side].indexOf(w) === -1) carriers[side].push(w);
      carrierCount[w] = (carrierCount[w] || 0) + 1;
      nCarrierMembers += 1;
      if (side === "ranged") ranged += dmg; else melee += dmg;
    }
    var tot = melee + ranged;
    var dmgTot = aoe + sus + st;
    var mel = tot ? melee / tot : 0.5;
    var mode = { aoe: dmgTot ? aoe / dmgTot : 0.0,
                 sustained: dmgTot ? sus / dmgTot : 0.0,
                 single_target: dmgTot ? st / dmgTot : 0.0 };
    var posture = (commit + evade) ? commit / (commit + evade) : 0.5;
    var band = this._fitBand();
    var out = { style: null, label: "", strength: null,
                melee_share: mel, ranged_share: tot ? 1.0 - mel : 0.5,
                carriers: carriers, mode: mode, posture: posture,
                band: band, members: [], conflicts: [] };
    var styles = this.data.styles || {};
    var sname = function (k, fb) {
      return (styles[k] && styles[k].name) || fb;
    };
    var forming = n < IDENTITY_MIN_MEMBERS || tot === 0;
    var clap;
    if (forming) {
      out.label = "still forming";
    } else if (mel >= IDENTITY_MELEE_CORE) {
      out.style = "brawl";
      out.strength = mel >= IDENTITY_STRONG ? "strong" : "leaning";
      out.label = sname("brawl", "Brawl") + " — melee ball";
    } else if (mel <= IDENTITY_RANGED_CORE) {
      clap = mode.aoe >= IDENTITY_CLAP_AOE;
      out.style = clap ? "clap" : "kite";
      out.strength = mel <= 1.0 - IDENTITY_STRONG ? "strong" : "leaning";
      /* Bomb-squad archetype + clap-kite hybrid (owner, blind label
         rounds 2026-08-23) — mirrors engine.py comp_identity. */
      var topCarrier = 0;
      for (var tc in carrierCount) {
        if (carrierCount[tc] > topCarrier) topCarrier = carrierCount[tc];
      }
      var evadePm = n ? evade / n : 0.0;
      if (clap && topCarrier >= 3 && topCarrier * 2 >= nCarrierMembers) {
        out.archetype = "bomb_squad";
        out.label = "Bomb squad — off-timer artillery (clap detachment)";
      } else if (mode.aoe >= IDENTITY_HYBRID_AOE &&
                 evadePm >= IDENTITY_HYBRID_EVADE) {
        out.style = "clap_kite";
        out.strength = "leaning";
        out.label = sname("clap_kite", "Clap-Kite") +
                    " — bomb from range, reset on cooldowns";
      } else {
        out.label = clap ? sname("clap", "Clap") + " — ranged bomb"
                         : sname("kite", "Kite") + " — ranged pressure";
      }
    } else if (mode.aoe >= IDENTITY_BC_AOE && posture >= IDENTITY_BC_POSTURE) {
      out.style = "brawl_clap";
      out.strength = "leaning";
      out.label = sname("brawl_clap", "Brawl-Clap") + " — grind into the bomb";
    } else {
      /* mirrors Python's tuple compare: (mel, nMelee) < (1-mel, nRanged) */
      var minority = (mel < 1.0 - mel ||
                      (mel === 1.0 - mel &&
                       carriers.melee.length < carriers.ranged.length))
        ? "melee" : "ranged";
      var majority = minority === "melee" ? "ranged" : "melee";
      /* flex and utility-carrier weapons never anchor a damage-identity
         split (mirrors engine.py — blind-label ruling 2026-08-23). */
      var rigid = [];
      for (var ri = 0; ri < carriers[minority].length; ri++) {
        var rw = carriers[minority][ri];
        var rsf = this._styleFitOf(rw);
        if (!flex[rw] && !(rsf && rsf.utility_carrier)) rigid.push(rw);
      }
      if (!rigid.length) {
        /* every minority carrier is flex — the comp is NOT split */
        if (majority === "melee") {
          out.style = "brawl";
          out.strength = "leaning";
          out.label = sname("brawl", "Brawl") + " — melee ball";
        } else {
          clap = mode.aoe >= IDENTITY_CLAP_AOE;
          var evadePm2 = n ? evade / n : 0.0;
          if (mode.aoe >= IDENTITY_HYBRID_AOE &&
              evadePm2 >= IDENTITY_HYBRID_EVADE) {
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
      }
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
        bar += self.target(c);
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

  var CHAIN_WEAK = 0.85, CHAIN_STRONG = 1.15;

  CompEngine.prototype.fightChain = function (party, combos, gears, candidate) {
    /* The comp as the caller's fight SEQUENCE, graded stage by stage —
       DESCRIPTIVE only (mirrors engine.py fight_chain). */
    var styles = this.data.styles || {};
    var style = IDENTITY_STYLES[this.style]
      ? this.style : this.compIdentity(party, combos).style;
    var chain = style && styles[style] ? styles[style].chain : null;
    if (!chain) return null;
    var s = this.effectiveSupply(party, combos, gears);
    /* spell-level sources (2026-08-24, mirrors engine.py): which equipped
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
      var used = [], bar = 0.0, have = 0.0;
      for (var ci = 0; ci < caps.length; ci++) {
        if (!(caps[ci] in this.reqs)) continue;
        used.push(caps[ci]);
        bar += this.target(caps[ci]);
        have += s[caps[ci]] || 0.0;
      }
      var verdict;
      if (!used.length || bar <= 0) verdict = "quiet";
      else if (have <= 0) verdict = "missing";
      else if (have < CHAIN_WEAK * bar) verdict = "weak";
      else if (have >= CHAIN_STRONG * bar) verdict = "strong";
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
                    have: have, bar: bar, verdict: verdict,
                    sources: sources });
    }
    var out = { style: style, stages: stages, improves: null };
    if (candidate && this.weapons[candidate]) {
      /* explain() deltas are already weighted fitness terms */
      var terms = this.explain(party, candidate, combos);
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
        /* name the terms behind the claim (2026-08-24, mirrors engine.py):
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
       gears (owner ruling 2026-08-27): with a parallel kit list the
       search optimizes the SAME dressed compScore used everywhere else
       — incumbent kits preserved, replacements tried in each doctrine
       kit variant, result {party, gears}. gears null keeps the legacy
       weapon-only list return bit-identically. */
    party = party.slice();
    fixed = fixed || 0;
    var candidates;
    /* empty array falls back to the full pool like Python's `pool or
       self.pool` — [] is truthy in JS (review 2026-08-18) */
    if (pool && pool.length) { candidates = pool.slice(); }
    else { candidates = this.pool.slice(); }
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
    var roleMin = {}, roleMax = {}, predMin = {};
    for (var key in band) {
      if (key === "min_size" || key === "max_size") continue;
      var rule = band[key];
      if (typeof rule !== "object" || rule === null) continue;
      if (key in this.predDefs || key === this.PRIMARY_HEAL) {
        if (rule.min !== undefined) predMin[key] = rule.min;
        continue;
      }
      if (rule.min !== undefined) roleMin[key] = rule.min;
      if (rule.max !== undefined) roleMax[key] = rule.max;
    }
    /* need-profile minima ride the predicate channel; seat maxima get
       their own key (mirrors engine.py) */
    var pk, seatMax = {};
    for (pk in this._profileMin) predMin[pk] = this._profileMin[pk];
    for (pk in this._profileMax) seatMax[pk] = this._profileMax[pk];
    /* Capacity gates per predicate minimum (deadlock guard, 2026-08-27;
       mirrors engine.py _forge_ctx): the [role, seat] pairs of every pool
       weapon that could satisfy the predicate — _forgeFeasible refuses a
       pick that would strand an unmet minimum behind full bands. */
    var predGates = {};
    for (var pn2 in predMin) {
      var gates = [], seen = {};
      for (var wi = 0; wi < pool.length; wi++) {
        var w2 = pool[wi];
        var poss = this._predPossible(w2);
        var prof = this._profileMembers[w2];
        if (!poss[pn2] && !(prof && prof[pn2])) continue;
        var role2 = this.roleOf(w2);
        var seat2 = this._profilePrimary[w2];
        var gkey = role2 + "|" + (seat2 === undefined ? "-" : seat2);
        if (seen[gkey]) continue;
        seen[gkey] = true;
        gates.push([role2, seat2]);
      }
      predGates[pn2] = gates;
    }
    return { pool: pool, roleMin: roleMin, roleMax: roleMax,
             predMin: predMin, seatMax: seatMax, predGates: predGates };
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
      var pmC = this._profileMembers[w];
      if (pmC) for (var pk2 in pmC) preds[pk2] = (preds[pk2] || 0) + 1;
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
    var p0 = this._profilePrimary[w];
    if (p0 !== undefined && ctx.seatMax[p0] !== undefined &&
        (preds[p0] || 0) >= ctx.seatMax[p0]) return false;
    var contrib = this._withProfile(w, this._predPossible(w));
    if (this._forgeMinNeed(ctx, roles, preds, w, contrib) > slotsLeftAfter)
      return false;
    /* Deadlock guard (2026-08-27; mirrors engine.py): after this pick,
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
    var hasPred = false;
    for (var k in ctx.predMin) { hasPred = true; break; }
    for (var i = 0; i < extras.length; i++) {
      /* predicate feasibility is per COMBO only — kit variants never
         change predicate contributions (mirrors engine.py) */
      if (hasPred) {
        var need = this._forgeMinNeed(ctx, beam.roles, beam.preds, w,
                                      this._withProfile(
                                        w, this._predContrib(w, i)));
        if (need > slotsLeftAfter) continue;
      }
      for (var vi = 0; vi < variants.length; vi++) {
        var vkey = variants[vi][0], vgears = variants[vi][1];
        if (this._variantCapped(state, vgears)) continue;   /* carrier quota */
        var cs = this._comboScoreDressed(state, w, i, extras[i],
                                         dressed[vkey][i]);
        if (best === null || cs.val > best.val)
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
       of the identity (dressed forge 2026-08-27; mirrors engine.py). */
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

  CompEngine.prototype.forge = function (size, locked, lockedCombos, pool,
                                         beamWidth, lockedGears) {
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
    /* lockedGears (owner ruling 2026-08-27): a locked member supplied
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
      expansions.sort(function (a, b) { return b[0] - a[0]; });
      var nextBeams = [], seen = {};
      for (var xi = 0; xi < expansions.length; xi++) {
        var ex = expansions[xi];
        var src = beams[ex[1]];
        var items = this._insertSorted(src.items,
                                       this._memberTag(ex[2], ex[3], ex[4]));
        var key = items.join("|");
        if (seen[key]) continue;
        seen[key] = true;
        var party2 = src.party.concat([ex[2]]);
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
      beams = nextBeams;
    }
    var best = beams[0];
    var party = best.party, combosOut = best.combos, gearsOut = best.gears;
    var fixed = locked.length;
    if (party.length > fixed) {
      /* refine -> pair-trade -> refine (mirrors engine.py forge) */
      var rc = this._refineConstrained(ctx, party, combosOut, gearsOut, fixed);
      rc = this._twoOpt(ctx, rc[0], rc[1], rc[2], fixed);
      rc = this._refineConstrained(ctx, rc[0], rc[1], rc[2], fixed);
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
             feasible: feasible, filler: filler, held: held, locked: fixed };
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
    return true;
  };

  CompEngine.prototype._refineConstrained = function (ctx, party, combos,
                                                      gears, fixed, maxPasses) {
    /* Steepest-descent 1-opt over generated slots, constraint-aware:
       minima are checked against the REST roster's combo-aware counts, so
       a swap can never trade away the spells a minimum was counting on
       (mirrors engine.py _refine_constrained, review 2026-08-19). */
    party = party.slice(); combos = combos.slice(); gears = gears.slice();
    if (maxPasses === undefined) maxPasses = 8;
    var best = this.compScore(party, combos, gears);
    for (var pass = 0; pass < maxPasses; pass++) {
      var move = null, gain = 1e-9;
      for (var i = fixed; i < party.length; i++) {
        var rest = party.slice(0, i).concat(party.slice(i + 1));
        var restC = combos.slice(0, i).concat(combos.slice(i + 1));
        var restG = gears.slice(0, i).concat(gears.slice(i + 1));
        var fcr = this._forgeCounts(rest, restC);
        var state = this.partyState(rest, restC, restG);
        var baseRest = this.compScore(rest, restC, restG);
        var contrib = best - baseRest;
        var beam = { state: state, roles: fcr[1], preds: fcr[2] };
        for (var j = 0; j < ctx.pool.length; j++) {
          var w = ctx.pool[j];
          /* w === party[i] deliberately NOT skipped (dressed forge
             2026-08-27, mirrors engine.py): re-resolving the SAME
             weapon's combo+kit can be the best move — identical picks
             price d == 0 and are never taken. */
          if (!this._addOk(ctx, fcr[0], fcr[1], fcr[2], fcr[3], w)) continue;
          var pick = this._forgeEvalPick(ctx, beam, w, 0);
          if (pick === null) continue;
          var d = pick.score - contrib;
          if (d > gain) { move = [i, w, pick.combo, pick.vgears]; gain = d; }
        }
      }
      if (move === null) break;
      party[move[0]] = move[1];
      combos[move[0]] = move[2];
      gears[move[0]] = move[3];
      best = this.compScore(party, combos, gears);
    }
    return [party, combos, gears];
  };

  CompEngine.prototype._twoOpt = function (ctx, party, combos, gears,
                                           fixed, worstK, candM) {
    /* Bounded 2-opt over the weakest generated slots (mirrors engine.py
       _two_opt). An accepted pair-move reorders the roster, so the pass
       restarts with freshly computed weakest slots (review 2026-08-18). */
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
            if (a[0] !== b[0]) return b[0] - a[0];
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
              if (!ok) continue;
              /* carrier quota (mirrors engine.py two-opt) */
              var ccaps = this.carrierCaps(), ccnt = this._carrierCounts(candGears), over = false;
              for (var ce0 in ccnt) if (ccnt[ce0] > (ccaps[ce0] === undefined ? 1e9 : ccaps[ce0])) over = true;
              if (over) continue;
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
