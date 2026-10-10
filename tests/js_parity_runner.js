// Node-side half of tests/test_js_parity.py.
// Usage: node js_parity_runner.js <app_scoring.js> <dataset.json> <cases.json>
"use strict";
const fs = require("fs");
const CompEngine = require(process.argv[2]);
const dataset = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));

// mirrors SWAP_EVERY / SWAP_MAX_PARTY in test_js_parity.py
const SWAP_EVERY = 6, SWAP_MAX_PARTY = 6;
// mirrors REFINE_* in test_js_parity.py
const REFINE_EVERY = 6, REFINE_MAX_PARTY = 6, REFINE_PASSES = 2;
// mirrors FORGE_* in test_js_parity.py
const FORGE_EVERY = 10, FORGE_SIZE = 8;
// one party caps at 20 (mirrors PARTY_CAP and forge_cap_results in
// test_js_parity.py): each call returns its refusal message
const PARTY_CAP = 20;
const refusal = (fn) => {
  try { fn(); } catch (err) { return String(err.message); }
  return "no refusal";
};
const forgeCapResults = (e, pool) => {
  const over = PARTY_CAP + 1;
  const party = new Array(over).fill(pool[0]);
  return {
    forge: refusal(() => e.forge(over, null, null, pool)),
    locked: refusal(() => e.forge(PARTY_CAP, party, null, pool)),
    replace: refusal(() => e.replaceOptions(party, 0, null, null, null, pool)),
    refine: refusal(() => e.refine(party, 1, [])),
  };
};
// mirrors KIT_* in test_js_parity.py (increment 2 kit doctrine)
const KIT_EVERY = 6, KIT_OFFSET = 3, KIT_MAX_REST = 5;
const kitSer = (ko) => {
  const out = {};
  for (const s of Object.keys(ko.options)) {
    out[s] = ko.options[s].map((o) => ({
      gear: o.gear, value: o.value, doctrine: o.doctrine,
      carries: o.carries, passive: o.passive ? o.passive.id : null }));
  }
  return out;
};

// the dressed and empty-pool outputs, serialized to the fields both ports
// must agree on (mirrors _dressed_results and the _ser_* helpers in
// test_js_parity.py)
const serIdentity = (ia) => ({
  style: ia.style, label: ia.label, strength: ia.strength, band: ia.band,
  carriers: ia.carriers, kit_lean: ia.kit_lean === undefined ? null : ia.kit_lean,
  conflicts: ia.conflicts.map((x) => [x.weapon, x.kind]),
  members: ia.members.map((m) => [m.weapon, m.role, m.side, m.fit]),
  melee_share: ia.melee_share, posture: ia.posture, mode: ia.mode });
const serChain = (fc) => fc === null ? null : {
  style: fc.style,
  stages: fc.stages.map((s) => [s.name, s.verdict, s.caps, s.have, s.bar, s.min,
    s.sources.map((r) => [r.cap, r.member, r.weapon, r.slot, r.spell, r.units])]),
  improves: fc.improves === null ? null : [fc.improves.stage, fc.improves.gain,
    fc.improves.terms.map((t) => [t.cap, t.gain])] };
const serKp = (kp) => {
  if (kp === null || kp === undefined) return null;
  const out = { verdict: kp.verdict };
  for (const k of ["pierce", "heal_cut", "burst"]) out[k] = [kp[k].ok, kp[k].have, kp[k].bar];
  return out;
};
const serExplain = (terms) => terms.map((t) => [t.cap, t.delta, t.before, t.after, t.target]);
const serReport = (pr) => [pr.verdict, pr.combo, pr.kit, pr.score, pr.d_fitness,
  pr.d_synergy, pr.caps_gain,
  pr.caps.map((r) => [r.cap, r.gain, r.coverage, r.floor_lift, r.overstack_cost, r.delta]),
  pr.nonstack.map((n) => [n.spell, n.lost])];
const serSwap = (rev) => rev.map((m) => [m.weapon, m.score, m.rank, m.built_score,
  m.build_gap, m.combo, m.kit, m.caps_gain, m.verdict,
  m.options.map((o) => [o.weapon, o.score, o.gain, o.delta, o.combo, o.kit])]);
const dressedResults = (e, c, sp, rp, i, gl) => {
  const party = c.party, combos = c.combos, gears = c.gears;
  const cand = party.length ? party[0] : null;
  const pool0 = c.refine_pool.length ? c.refine_pool[0] : null;
  return {
    identity_dressed: serIdentity(e.compIdentity(party, combos, gears)),
    fight_chain_dressed: serChain(e.fightChain(party, combos, gears, cand)),
    kill_pressure_dressed: serKp(e.killPressure(party, combos, gears)),
    uncovered_dressed: e.uncoveredCaps(party, combos, gears).slice().sort(),
    explain_dressed: pool0 === null ? null
      : serExplain(e.explain(party, pool0, combos, gears)),
    pick_report_dressed: pool0 === null ? null
      : serReport(e.pickReport(party, pool0, combos, gears)),
    swap_dressed: sp === null ? null
      : serSwap(e.swapReview(sp, 3, null, combos.slice(0, sp.length),
                             gl.slice(0, sp.length))),
    // an explicit empty pool is no candidates (mirrors test_js_parity.py, F37)
    empty_pool: {
      recommend: e.recommend(party, 4, []).map((r) => r.weapon),
      swap: sp === null ? null
        : e.swapReview(sp, 3, []).map((m) => [m.rank, m.options.map((o) => o.weapon)]),
      refine: rp === null ? null : e.refine(rp, REFINE_PASSES, []),
    },
    // the kit advisor with the rest as equipped (F42), on the kit cadence
    kit_rest: (i % KIT_EVERY !== KIT_OFFSET || !party.length) ? null
      : kitSer(e.kitOptions(party[0], combos.length ? combos[0] : null,
                            party.slice(1, 1 + KIT_MAX_REST), 3, "auto",
                            combos.slice(1, 1 + KIT_MAX_REST),
                            gl.slice(1, 1 + KIT_MAX_REST))),
  };
};

const out = cases.map((c, i) => {
  const e = new CompEngine(dataset, c.content, c.size, c.style);
  // a case flagged "swap" (the dressed and short-list cases) always runs it
  const sp = (i % SWAP_EVERY === 0 || c.swap) ? c.party.slice(0, SWAP_MAX_PARTY) : null;
  const gl = c.gears || [];
  const rp = i % REFINE_EVERY === 0 ? c.party.slice(0, REFINE_MAX_PARTY) : null;
  let forged = null;
  const forgeCap = i % FORGE_EVERY === 0 ? forgeCapResults(e, c.refine_pool) : null;
  if (i % FORGE_EVERY === 0) {
    // mirrors forge_case in test_js_parity.py incl. the empty-locked-combos
    // alternation (the [] truthiness divergence shipped once) and the
    // locked_gears alternation
    const even = Math.floor(i / FORGE_EVERY) % 2 === 0;
    const combos = even ? c.combos.slice(0, 2) : [];
    const lgears = even ? c.gears.slice(0, 2) : null;
    const r = e.forge(FORGE_SIZE, c.party.slice(0, 2), combos, c.refine_pool,
                      undefined, lgears);
    // the next-best alternative (`avoid`; mirrors test_js_parity.py)
    const r2 = e.forge(FORGE_SIZE, c.party.slice(0, 2), combos, c.refine_pool,
                       undefined, lgears, [r.party]);
    forged = { party: r.party, combos: r.combos, gears: r.gears,
               score: r.score,
               feasible: r.feasible, filler: r.filler, held: r.held,
               exhausted: r.exhausted,
               next: { party: r2.party, gears: r2.gears, score: r2.score,
                       exhausted: r2.exhausted } };
  }
  // V3-W parity: dressing OFF while incumbents keep their case
  // gears — candidates must evaluate naked (mirrors test_js_parity.py).
  e.setDressing(false);
  const nakedRec = e.recommend(c.party, 5, null, c.combos, c.gears).map((r) => ({
    weapon: r.weapon, score: r.score, combo: r.combo, kit: r.kit }));
  e.setDressing(true);
  return {
    recommend_naked_cand: nakedRec,
    refine: rp === null ? null : e.refine(rp, REFINE_PASSES, c.refine_pool),
    // gear-aware refine (F25/F26; mirrors test_js_parity.py)
    refine_dressed: rp === null ? null
      : e.refine(rp, REFINE_PASSES, c.refine_pool, 0,
                 c.gears.slice(0, rp.length)),
    comp_score: e.compScore(c.party),
    // the meta term's weight at the case's context (mirrors test_js_parity.py)
    delta: e.delta,
    comp_score_locked: e.compScore(c.party, c.combos),
    redundancy: e.redundancy(c.party),
    size_bucket: e.sizeBucket(),
    target_source: (() => { const o = {}; for (const cap in e.reqs) o[cap] = e.targetSource(cap); return o; })(),
    target_min: (() => { const o = {}; for (const cap in e.reqs) o[cap] = e.targetMin(cap); return o; })(),
    constraint_band: e._band,
    forge: forged,
    forge_cap: forgeCap,
    // replaceOptions (mirrors test_js_parity.py)
    replace: (sp === null || sp.length < 2) ? null
      : e.replaceOptions(sp, 0, c.combos.slice(0, sp.length),
                         c.gears.slice(0, sp.length), 5, c.refine_pool).map((o) => ({
          weapon: o.weapon, score: o.score, delta: o.delta, combo: o.combo, kit: o.kit })),
    swap: sp === null ? null : e.swapReview(sp).map((m) => ({
      weapon: m.weapon, score: m.score, rank: m.rank, off_comp: m.off_comp,
      off_style: m.off_style, caps_gain: m.caps_gain, verdict: m.verdict,
      redundant: m.redundant,
      options: m.options.map((o) => ({ weapon: o.weapon, score: o.score })),
    })),
    fitness: e.fitness(c.party),
    // the gear-active doctrine's default pick per item (mirrors test_js_parity.py)
    gear_choice: (() => { const o = {}; for (const k of Object.keys(e.gear).sort()) o[k] = [e.defaultGearChoice(k), e.gearChoiceSource(k), e.gearActiveSpell(k)]; return o; })(),
    fitness_build: ((!c.gears || !c.gears.length) ? null : e.fitness(c.party, null, c.gears)),
    comp_score_build: ((!c.gears || !c.gears.length) ? null : e.compScore(c.party, null, c.gears)),
    fitness_locked: e.fitness(c.party, c.combos),
    synergy: e.synergy(c.party),
    synergy_locked: e.synergy(c.party, c.combos),
    max_fitness: e.maxFitness(),
    max_fitness_party: e.maxFitness(c.party, c.combos, c.gears),
    recommend: e.recommend(c.party, 5).map((r) => ({
      weapon: r.weapon, score: r.score, combo: r.combo, kit: r.kit,
      caps_gain: r.caps_gain, verdict: r.verdict,
      meta_prior: r.meta_prior, meta_solo: r.meta_solo, meta_pair: r.meta_pair,
      meta_partner: r.meta_partner, meta_raise: r.meta_raise })),
    pick_report: c.refine_pool.length
      ? e.pickReport(c.party, c.refine_pool[0], c.combos) : null,
    analyze_bands: (() => {
      const a = e.analyze(c.party, c.combos);
      const row = (x) => ({ cap: x.cap, have: x.have, band: x.band,
                            soft_cap: x.soft_cap });
      return { strengths: a.strengths.map(row),
               missing: a.missing_capabilities.map(row) };
    })(),
    recommend_locked: e.recommend(c.party, 5, null, c.combos).map((r) => ({
      weapon: r.weapon, score: r.score })),
    weaknesses: e.weaknesses(c.party, 5, null, c.gears)
      .map((g) => ({ cap: g.cap, gap: g.gap })),
    uncovered: e.uncoveredCaps(c.party).slice().sort(),
    identity: e.compIdentity(c.party, c.combos),
    kill_pressure: e.killPressure(c.party, c.combos),
    fight_chain: e.fightChain(c.party, c.combos, null,
                              c.party.length ? c.party[0] : null),
    role_advisory: (() => {
      // chest per member: first ARMOR_ item in the case's gear list
      // (mirrors test_js_parity.py)
      const chests = {};
      (c.gears || []).forEach((g, j) => {
        for (const x of (g || [])) {
          if (String(x).indexOf("ARMOR_") === 0) { chests[j] = x; break; }
        }
      });
      return e.roleAdvisory(c.party, chests);
    })(),
    kit: (i % KIT_EVERY !== KIT_OFFSET || !c.party.length) ? null : {
      comp: kitSer(e.kitOptions(c.party[0], null,
                                c.party.slice(1, 1 + KIT_MAX_REST))),
      free: kitSer(e.kitOptions(c.party[0])),
    },
    // the dressed paths (mirrors test_js_parity.py _dressed_results)
    ...dressedResults(e, c, sp, rp, i, gl),
  };
});
process.stdout.write(JSON.stringify(out));
