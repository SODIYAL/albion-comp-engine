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

const out = cases.map((c, i) => {
  const e = new CompEngine(dataset, c.content, c.size, c.style);
  const sp = i % SWAP_EVERY === 0 ? c.party.slice(0, SWAP_MAX_PARTY) : null;
  const rp = i % REFINE_EVERY === 0 ? c.party.slice(0, REFINE_MAX_PARTY) : null;
  let forged = null;
  if (i % FORGE_EVERY === 0) {
    // mirrors forge_case in test_js_parity.py incl. the empty-locked-combos
    // alternation (the [] truthiness divergence shipped once)
    const combos = Math.floor(i / FORGE_EVERY) % 2 === 0 ? c.combos.slice(0, 2) : [];
    const r = e.forge(FORGE_SIZE, c.party.slice(0, 2), combos, c.refine_pool);
    forged = { party: r.party, combos: r.combos, gears: r.gears,
               score: r.score,
               feasible: r.feasible, filler: r.filler, held: r.held };
  }
  // V3-W parity (2026-08-27): dressing OFF while incumbents keep their case
  // gears — candidates must evaluate naked (mirrors test_js_parity.py).
  e.setDressing(false);
  const nakedRec = e.recommend(c.party, 5, null, c.combos, c.gears).map((r) => ({
    weapon: r.weapon, score: r.score, combo: r.combo, kit: r.kit }));
  e.setDressing(true);
  return {
    recommend_naked_cand: nakedRec,
    refine: rp === null ? null : e.refine(rp, REFINE_PASSES, c.refine_pool),
    comp_score: e.compScore(c.party),
    comp_score_locked: e.compScore(c.party, c.combos),
    redundancy: e.redundancy(c.party),
    size_bucket: e.sizeBucket(),
    forge: forged,
    swap: sp === null ? null : e.swapReview(sp).map((m) => ({
      weapon: m.weapon, score: m.score, rank: m.rank, off_comp: m.off_comp,
      off_style: m.off_style, caps_gain: m.caps_gain, verdict: m.verdict,
      redundant: m.redundant,
      options: m.options.map((o) => ({ weapon: o.weapon, score: o.score })),
    })),
    fitness: e.fitness(c.party),
    fitness_build: ((!c.gears || !c.gears.length) ? null : e.fitness(c.party, null, c.gears)),
    comp_score_build: ((!c.gears || !c.gears.length) ? null : e.compScore(c.party, null, c.gears)),
    fitness_locked: e.fitness(c.party, c.combos),
    synergy: e.synergy(c.party),
    synergy_locked: e.synergy(c.party, c.combos),
    max_fitness: e.maxFitness(),
    recommend: e.recommend(c.party, 5).map((r) => ({
      weapon: r.weapon, score: r.score, combo: r.combo, kit: r.kit,
      caps_gain: r.caps_gain, verdict: r.verdict })),
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
  };
});
process.stdout.write(JSON.stringify(out));
